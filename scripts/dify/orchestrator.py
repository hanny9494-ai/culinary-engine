#!/usr/bin/env python3
"""
Pipeline Orchestrator — 无人值守执行 task-queue 中的 pipeline 任务。

作为 launchd 守护进程永远运行。每 60 秒检查 task-queue，
取最高优先级的 pending 任务执行。

资源纪律：
- Ollama 任务串行（一次只跑一本书的 2b/9b/27b）
- flash OCR 可并发（最多 3 本同时）
- Stage4 Opus API 串行
- 检测到 Ollama 被占用时跳过 Ollama 任务，先做 API 任务

Usage:
    python3 scripts/dify/orchestrator.py              # 前台运行
    python3 scripts/dify/orchestrator.py --once        # 只执行一个任务就退出
    python3 scripts/dify/orchestrator.py --dry-run     # 只看不做
"""

import json
import os
import re
import signal
import sqlite3
import subprocess
import sys
import time
import argparse
from pathlib import Path
from datetime import datetime

DB_PATH = Path.home() / "culinary-engine" / "data" / "task_queue.db"
CE_DIR = Path.home() / "culinary-engine"
L0_OUTPUT = Path.home() / "l0-knowledge-engine" / "output"
LOG_DIR = Path.home() / "culinary-engine" / "reports"

# Task type detection patterns
TASK_PATTERNS = {
    "stage4": re.compile(r"stage4[:\s]", re.I),
    "stage1": re.compile(r"stage1[:\s]|2b\+9b|2b/9b", re.I),
    "ocr": re.compile(r"ocr[:\s]|flash ocr", re.I),
    "stage5": re.compile(r"stage5[:\s]|recipe", re.I),
}

# Resource locks
OLLAMA_LOCK = Path("/tmp/culinary_orchestrator_ollama.lock")
API_LOCK = Path("/tmp/culinary_orchestrator_api.lock")

running = True


def signal_handler(sig, frame):
    global running
    print(f"\n[{now()}] Shutting down gracefully...")
    running = False


def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def log(msg):
    print(f"[{now()}] {msg}", flush=True)


# ============================================================
# Database helpers
# ============================================================
def get_db():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def get_next_task(conn):
    """Get highest priority pending task."""
    row = conn.execute(
        "SELECT * FROM tasks WHERE status = 'pending' ORDER BY priority, id LIMIT 1"
    ).fetchone()
    return dict(row) if row else None


def update_task(conn, task_id, status, result_summary=""):
    updates = ["status = ?", "updated_at = datetime('now')"]
    params = [status]
    if status in ("done", "failed"):
        updates.append("completed_at = datetime('now')")
    if result_summary:
        updates.append("result_summary = ?")
        params.append(result_summary)
    params.append(task_id)
    conn.execute(f"UPDATE tasks SET {', '.join(updates)} WHERE id = ?", params)
    conn.execute("INSERT INTO task_log (task_id, action, detail) VALUES (?, ?, ?)",
                 (task_id, status, result_summary))
    conn.commit()


# ============================================================
# Resource checks
# ============================================================
def is_ollama_busy():
    """Check if Ollama is currently running a model."""
    try:
        import requests
        s = requests.Session()
        s.trust_env = False
        r = s.get("http://localhost:11434/api/ps", timeout=3)
        models = r.json().get("models", [])
        return len(models) > 0
    except Exception:
        return False


def is_pipeline_running(pattern):
    """Check if a pipeline process matching pattern is running."""
    result = subprocess.run(["ps", "aux"], capture_output=True, text=True)
    for line in result.stdout.split("\n"):
        if pattern in line and "grep" not in line and "orchestrator" not in line:
            return True
    return False


def detect_task_type(task):
    """Detect what kind of pipeline task this is."""
    title = task.get("title", "")
    for ttype, pattern in TASK_PATTERNS.items():
        if pattern.search(title):
            return ttype
    return "unknown"


def extract_book_id(task):
    """Extract book_id from task title."""
    title = task.get("title", "")
    # Pattern: "Stage4: book_name (123 chunks)"
    m = re.search(r":\s*(\S+?)[\s(]", title)
    if m:
        return m.group(1)
    # Pattern: book_id in input_path
    inp = task.get("input_path", "")
    if inp:
        return Path(inp).stem
    return None


# ============================================================
# Task executors
# ============================================================
def run_via_codex(prompt, workdir, log_name, dry_run=False, timeout=14400):
    """Execute a task through Codex CLI (cheaper tokens than Claude)."""
    codex_bin = str(Path.home() / "bin" / "codex")
    log_file = LOG_DIR / f"orchestrator_{log_name}.log"
    output_file = LOG_DIR / f"orchestrator_{log_name}_result.md"

    if dry_run:
        log(f"  [DRY-RUN] Would send to Codex: {prompt[:80]}...")
        return "done", "dry-run"

    cmd = [
        codex_bin, "exec",
        "--full-auto",
        "-C", str(workdir),
        "-o", str(output_file),
        prompt,
    ]

    log(f"  Dispatching to Codex...")
    with open(log_file, "w") as lf:
        proc = subprocess.run(cmd, stdout=lf, stderr=subprocess.STDOUT,
                              timeout=timeout, env=_env())

    # Read Codex output
    result_text = ""
    if output_file.exists():
        result_text = output_file.read_text()[:500]

    if proc.returncode == 0:
        return "done", f"Codex completed. {result_text}"
    else:
        return "failed", f"Codex exit {proc.returncode}. {result_text}"


def run_stage4(task, book_id, dry_run=False):
    """Run Stage4 for a book via Codex."""
    chunks_path = L0_OUTPUT / book_id / "stage1" / "chunks_smart.json"
    if not chunks_path.exists():
        return "failed", f"chunks_smart.json not found: {chunks_path}"

    output_dir = L0_OUTPUT / book_id / "stage4"
    output_dir.mkdir(parents=True, exist_ok=True)

    prompt = f"""Run Stage4 open extraction for book "{book_id}".

Command:
python3 scripts/stage4_open_extract.py \\
  --chunks {chunks_path} \\
  --book-id {book_id} \\
  --config config/api.yaml \\
  --output-dir {output_dir} \\
  --resume \\
  --phase all

After it finishes, report:
1. How many raw principles in stage4_raw.jsonl
2. How many passed QC in l0_principles_open.jsonl
3. Any errors encountered

IMPORTANT: trust_env=False is already set in the script. Do not modify the script."""

    return run_via_codex(prompt, CE_DIR, f"stage4_{book_id}", dry_run, timeout=14400)


def run_stage1(task, book_id, dry_run=False):
    """Run Stage1 pipeline for a book via Codex."""
    prompt = f"""Run Stage1 pipeline for book "{book_id}".

Command:
python3 scripts/stage1_pipeline.py \\
  --book-id {book_id} \\
  --config config/api.yaml

After it finishes, report:
1. chunks_raw.json count
2. chunks_smart.json count
3. annotation_failures.json count
4. Any errors

IMPORTANT: Do not modify any scripts. Just run the command and report results."""

    return run_via_codex(prompt, CE_DIR, f"stage1_{book_id}", dry_run, timeout=7200)


def run_ocr_batch(task, dry_run=False):
    """Run flash OCR for books that need it, via Codex."""
    books_need_ocr = []
    for d in sorted(L0_OUTPUT.iterdir()):
        if not d.is_dir() or d.is_symlink():
            continue
        if d.name.startswith("stage") or d.name.startswith("_"):
            continue
        ocr_dir = d / "ocr"
        stage1 = d / "stage1"
        if not ocr_dir.exists() and not (stage1 / "raw_merged.md").exists():
            source = d / "source_converted.pdf"
            if source.exists():
                books_need_ocr.append(d.name)

    if not books_need_ocr:
        return "done", "No books need OCR"

    book_list = ", ".join(books_need_ocr[:5])
    prompt = f"""Run qwen3.5-flash VLM OCR for these books: {book_list}

For each book:
1. Source PDF at ~/l0-knowledge-engine/output/{{book_id}}/source_converted.pdf
2. Output to ~/l0-knowledge-engine/output/{{book_id}}/ocr/vlm_ocr_pages.json and vlm_ocr_merged.md
3. Use DashScope OpenAI compatible API: https://dashscope.aliyuncs.com/compatible-mode/v1
4. Model: qwen3.5-flash
5. MUST support resume: skip already successful pages
6. MUST use trust_env=False
7. Concurrency: up to 3 books in parallel

Report per book: total pages, success, failed, output path."""

    return run_via_codex(prompt, CE_DIR, "ocr_batch", dry_run, timeout=7200)


def _env():
    """Get environment with proxy bypass."""
    env = dict(os.environ)
    env["no_proxy"] = "localhost,127.0.0.1"
    env["PATH"] = f"{Path.home()}/miniforge3/bin:{Path.home()}/bin:{env.get('PATH', '')}"
    return env


# ============================================================
# Main loop
# ============================================================
def execute_task(task, dry_run=False):
    """Execute a single task based on its type."""
    task_type = detect_task_type(task)
    book_id = extract_book_id(task)
    task_id = task["id"]
    title = task["title"]

    log(f"Task #{task_id}: {title}")
    log(f"  Type: {task_type}, Book: {book_id or 'batch'}")

    # Resource check
    if task_type in ("stage1",) and is_ollama_busy():
        log(f"  ⏸ Ollama busy, skipping Ollama task")
        return False  # Don't mark as started, try later

    if task_type == "stage4" and is_pipeline_running("stage4_open_extract"):
        log(f"  ⏸ Stage4 already running, skipping")
        return False

    # Mark as in_progress
    conn = get_db()
    update_task(conn, task_id, "in_progress")
    conn.close()

    # Execute
    try:
        if task_type == "stage4" and book_id:
            status, summary = run_stage4(task, book_id, dry_run)
        elif task_type == "stage1" and book_id:
            status, summary = run_stage1(task, book_id, dry_run)
        elif task_type == "ocr":
            status, summary = run_ocr_batch(task, dry_run)
        else:
            status, summary = "failed", f"Unknown task type: {task_type}"
            log(f"  ⚠ {summary}")
    except subprocess.TimeoutExpired:
        status, summary = "failed", "Timeout exceeded"
        log(f"  ⚠ Task timed out")
    except Exception as e:
        status, summary = "failed", str(e)[:200]
        log(f"  ⚠ Error: {e}")

    # Update status
    conn = get_db()
    update_task(conn, task_id, status, summary)
    conn.close()

    log(f"  → {status}: {summary[:100]}")
    return True


def main_loop(once=False, dry_run=False, interval=60):
    """Main orchestrator loop."""
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    log("Orchestrator started")
    log(f"  DB: {DB_PATH}")
    log(f"  Output: {L0_OUTPUT}")
    log(f"  Interval: {interval}s")
    log(f"  Dry-run: {dry_run}")

    while running:
        try:
            conn = get_db()
            task = get_next_task(conn)
            conn.close()

            if task:
                executed = execute_task(task, dry_run)
                if not executed:
                    # Task skipped (resource busy), try next one
                    conn = get_db()
                    # Look for tasks that don't need the busy resource
                    rows = conn.execute(
                        "SELECT * FROM tasks WHERE status = 'pending' ORDER BY priority, id"
                    ).fetchall()
                    conn.close()

                    for row in rows:
                        t = dict(row)
                        if t["id"] == task["id"]:
                            continue
                        tt = detect_task_type(t)
                        # Skip if also needs Ollama and Ollama is busy
                        if tt in ("stage1",) and is_ollama_busy():
                            continue
                        if tt == "stage4" and is_pipeline_running("stage4_open_extract"):
                            continue
                        # Try this one
                        execute_task(t, dry_run)
                        break
            else:
                pass  # No tasks, idle

        except Exception as e:
            log(f"Error in main loop: {e}")

        if once:
            break

        time.sleep(interval)

    log("Orchestrator stopped")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true", help="Execute one task and exit")
    parser.add_argument("--dry-run", action="store_true", help="Don't actually execute")
    parser.add_argument("--interval", type=int, default=60, help="Check interval in seconds")
    args = parser.parse_args()

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    main_loop(once=args.once, dry_run=args.dry_run, interval=args.interval)


if __name__ == "__main__":
    main()
