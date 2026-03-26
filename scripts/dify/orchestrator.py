#!/usr/bin/env python3
"""
Pipeline Orchestrator v2 — 无人值守执行 task-queue 中的 pipeline 任务。

作为 launchd 守护进程永远运行。每 60 秒检查 task-queue，
取 pending 任务按资源纪律并行派发。

架构:
  Phase 0: Dify KB 定期同步 (每10轮)
  Phase 1: Poll open PRs (代码任务)
  Phase 2: 清理已完成 tmux 窗口
  Phase 3: 派发 pending 任务

资源纪律:
  opus_api ×3 并发 | flash_api ×3 并发 | ollama ×1 串行 | codex_general ×2

Usage:
    python3 scripts/dify/orchestrator.py              # 前台运行
    python3 scripts/dify/orchestrator.py --once        # 只跑一轮就退出
    python3 scripts/dify/orchestrator.py --dry-run     # 只看不做
"""

import argparse
import json
import logging
import os
import re
import signal
import sqlite3
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

# ============================================================
# Logging
# ============================================================
LOG_DIR = Path.home() / "culinary-engine" / "reports"
LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(LOG_DIR / "orchestrator.log"),
    ],
)
log = logging.getLogger("orchestrator")

# ============================================================
# Constants
# ============================================================
DB_PATH = Path.home() / "culinary-engine" / "data" / "task_queue.db"
CE_DIR = Path.home() / "culinary-engine"
L0_OUTPUT = Path(__file__).resolve().parent.parent.parent / "output"
REPORT_DIR = LOG_DIR / "task_reports"
LEARNINGS_PATH = LOG_DIR / "learnings.jsonl"
FIX_LOG_PATH = LOG_DIR / "auto_fixes.jsonl"
REPORT_DIR.mkdir(parents=True, exist_ok=True)

GH_BIN = "/opt/homebrew/bin/gh"
CODEX_BIN = str(Path.home() / "bin" / "codex")
TMUX_SESSION = "ce"

LOOP_INTERVAL = 60
KB_SYNC_EVERY = 10

# Dify KB
DIFY_DATASET_KEY = "dataset-DqAtoTYJUES69kEUF7bFBs25"
DIFY_DATASET_ID = "65b3d570-7a71-4a8c-bcc4-b377c635d1d8"
DIFY_URL = "http://localhost"

# ============================================================
# Task type detection (顺序敏感)
# ============================================================
TASK_PATTERNS = [
    ("stage4", re.compile(r"stage4[:\s]", re.I)),
    ("stage1_step5", re.compile(r"stage1.step5[:\s]|9b.annot", re.I)),
    ("ocr_stage1", re.compile(r"ocr\+stage1[:\s]", re.I)),
    ("stage1", re.compile(r"stage1[:\s]|2b\+9b|2b/9b", re.I)),
    ("ocr", re.compile(r"ocr[:\s]|flash ocr", re.I)),
    ("stage5", re.compile(r"stage5[:\s]|recipe", re.I)),
]

DATA_TASK_TYPES = {"stage4", "ocr_stage1", "stage1", "stage1_step5", "ocr", "stage5"}

# Resource slot → task type mapping
RESOURCE_MAP = {
    "stage4": "opus_api",
    "ocr": "flash_api",
    "ocr_stage1": "flash_api",
    "stage1": "ollama",
    "stage1_step5": "ollama",
    "stage5": "flash_api",
}

# ============================================================
# Resource semaphores
# ============================================================
_resource_slots = {
    "opus_api": threading.Semaphore(3),
    "flash_api": threading.Semaphore(3),
    "ollama": threading.Semaphore(1),
    "codex_general": threading.Semaphore(2),
}

# Track running tasks: task_id → thread
_running_tasks: dict[int, threading.Thread] = {}
_running_lock = threading.Lock()

running = True


def signal_handler(sig, frame):
    global running
    log.info("Shutting down gracefully...")
    running = False


# ============================================================
# ENV context and report instruction
# ============================================================
ENV_CONTEXT = """\
IMPORTANT ENVIRONMENT NOTES:
- Ollama runs at http://localhost:11434
- This machine has a proxy at 127.0.0.1:7890. ALL HTTP clients MUST set trust_env=False
- Before running any script, run: export no_proxy=localhost,127.0.0.1 http_proxy= https_proxy=
- Output data goes to ~/culinary-engine/output/
- Do not modify any existing scripts.
"""


def report_instruction(window_name, task_id):
    return f"""

IMPORTANT: When you finish, write a JSON report to {REPORT_DIR}/{window_name}.json with this structure:
{{
  "task_id": {task_id},
  "task": "{window_name}",
  "status": "success" or "failed",
  "started_at": "<ISO timestamp>",
  "finished_at": "<ISO timestamp>",
  "results": {{
    "key_numbers": {{}},
    "output_files": []
  }},
  "problems": [],
  "suggestions": [],
  "token_usage": {{}}
}}
"""


# ============================================================
# Database helpers
# ============================================================
def get_db():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def get_pending_tasks(conn):
    rows = conn.execute(
        "SELECT * FROM tasks WHERE status = 'pending' ORDER BY priority, id"
    ).fetchall()
    return [dict(r) for r in rows]


def get_running_tasks_db(conn):
    rows = conn.execute(
        "SELECT * FROM tasks WHERE status IN ('in_progress', 'pr_open')"
    ).fetchall()
    return [dict(r) for r in rows]


def update_task(conn, task_id, status, result_summary="", pr_url=None):
    updates = ["status = ?", "updated_at = datetime('now')"]
    params = [status]
    if status in ("done", "failed"):
        updates.append("completed_at = datetime('now')")
    if result_summary:
        updates.append("result_summary = ?")
        params.append(result_summary)
    params.append(task_id)
    conn.execute(f"UPDATE tasks SET {', '.join(updates)} WHERE id = ?", params)
    conn.execute(
        "INSERT INTO task_log (task_id, action, detail) VALUES (?, ?, ?)",
        (task_id, status, result_summary[:500] if result_summary else ""),
    )
    conn.commit()


# ============================================================
# Task type detection
# ============================================================
def detect_task_type(task):
    title = task.get("title", "")
    for ttype, pattern in TASK_PATTERNS:
        if pattern.search(title):
            return ttype
    return "code"  # 不匹配数据模式 → 代码任务


def extract_book_id(task):
    title = task.get("title", "")
    # Match "Stage4: book_name" or "Stage4: book_name (extra)"
    m = re.search(r":\s*(\S+?)(?:\s*\(|$)", title)
    if m:
        return m.group(1).rstrip()
    inp = task.get("input_path", "")
    if inp:
        return Path(inp).stem
    return None


# ============================================================
# Tmux + Codex 执行
# ============================================================
def _env():
    env = dict(os.environ)
    env["no_proxy"] = "localhost,127.0.0.1"
    env["http_proxy"] = ""
    env["https_proxy"] = ""
    env["PATH"] = f"{Path.home()}/miniforge3/bin:{Path.home()}/bin:{env.get('PATH', '')}"
    return env


def run_codex_in_tmux(prompt, window_name, task_id=0, dry_run=False, timeout=14400):
    """在 tmux 窗口运行 Codex，阻塞等待完成。"""
    prompt_file = Path(f"/tmp/orchestrator_prompt_{window_name}.txt")
    prompt_file.write_text(prompt, encoding="utf-8")

    done_marker = Path(f"/tmp/orchestrator_{window_name}.done")
    fail_marker = Path(f"/tmp/orchestrator_{window_name}.fail")
    done_marker.unlink(missing_ok=True)
    fail_marker.unlink(missing_ok=True)

    # Shell command: run codex, then touch .done or .fail
    shell_cmd = (
        f"cd {CE_DIR} && "
        f"export no_proxy=localhost,127.0.0.1 http_proxy= https_proxy= && "
        f"{CODEX_BIN} exec --dangerously-bypass-approvals-and-sandbox "
        f"\"$(cat {prompt_file})\" && "
        f"touch {done_marker} || touch {fail_marker}"
    )

    if dry_run:
        log.info("  [DRY-RUN] tmux %s: %s", window_name, prompt[:100])
        return "done", "dry-run"

    # Create tmux window
    try:
        subprocess.run(
            ["tmux", "new-window", "-t", TMUX_SESSION, "-n", window_name, shell_cmd],
            capture_output=True, text=True, check=True,
        )
    except subprocess.CalledProcessError as e:
        # Fallback: try send-keys to existing window
        log.warning("tmux new-window failed: %s, trying send-keys", e.stderr.strip())
        try:
            subprocess.run(
                ["tmux", "send-keys", "-t", f"{TMUX_SESSION}:{window_name}", shell_cmd, "Enter"],
                capture_output=True, check=True,
            )
        except subprocess.CalledProcessError:
            return "failed", f"Cannot create tmux window {window_name}"

    log.info("  Dispatched to tmux:%s", window_name)

    # Poll for done/fail marker
    start = time.time()
    while time.time() - start < timeout:
        if done_marker.exists():
            done_marker.unlink(missing_ok=True)
            break
        if fail_marker.exists():
            fail_marker.unlink(missing_ok=True)
            # Read report if available, otherwise return failed
            report = _read_report(window_name)
            summary = report.get("results", {}).get("key_numbers", {}) if report else {}
            return "failed", json.dumps(summary)[:500] if summary else "Codex failed"
        time.sleep(15)
    else:
        return "failed", f"Timeout after {timeout}s"

    # Read report
    report = _read_report(window_name)
    if report:
        status = report.get("status", "success")
        status = "done" if status == "success" else status
        results = report.get("results", {})
        summary = json.dumps(results.get("key_numbers", {}), ensure_ascii=False)[:500]
        return status, summary
    else:
        return "done", "Completed (no report)"


def _read_report(window_name):
    report_path = REPORT_DIR / f"{window_name}.json"
    if not report_path.exists():
        return None
    try:
        return json.loads(report_path.read_text())
    except Exception:
        return None


def tmux_window_exists(window_name):
    result = subprocess.run(
        ["tmux", "list-windows", "-t", TMUX_SESSION, "-F", "#{window_name}"],
        capture_output=True, text=True,
    )
    return window_name in result.stdout.split("\n")


# ============================================================
# Task executors (prompts)
# ============================================================
def run_stage4(task, book_id, dry_run=False):
    chunks_path = L0_OUTPUT / book_id / "stage1" / "chunks_smart.json"
    if not chunks_path.exists():
        return "deferred", f"chunks_smart.json not found: {chunks_path}"

    output_dir = L0_OUTPUT / book_id / "stage4"
    output_dir.mkdir(parents=True, exist_ok=True)
    window_name = f"s4_{book_id}"

    prompt = f"""{ENV_CONTEXT}
Run Stage4 open extraction for book "{book_id}".

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

IMPORTANT: trust_env=False is already set in the script. Do not modify the script.
{report_instruction(window_name, task['id'])}"""

    return run_codex_in_tmux(prompt, window_name, task["id"], dry_run, timeout=14400)


def run_stage1(task, book_id, dry_run=False):
    output_dir = L0_OUTPUT / book_id / "stage1"
    window_name = f"s1_{book_id}"

    prompt = f"""{ENV_CONTEXT}
Run Stage1 pipeline for book "{book_id}".

Command:
python3 scripts/stage1_pipeline.py \\
  --book-id {book_id} \\
  --config config/api.yaml \\
  --books config/books.yaml \\
  --toc config/mc_toc.json \\
  --output-dir {output_dir} \\
  --start-step 4

After it finishes, report:
1. chunks_raw.json count
2. chunks_smart.json count
3. annotation_failures.json count
4. Any errors

IMPORTANT: Do not modify any scripts.
{report_instruction(window_name, task['id'])}"""

    return run_codex_in_tmux(prompt, window_name, task["id"], dry_run, timeout=7200)


def run_stage1_step5(task, book_id, dry_run=False):
    output_dir = L0_OUTPUT / book_id / "stage1"
    window_name = f"s1s5_{book_id}"

    prompt = f"""{ENV_CONTEXT}
Run Stage1 Step5 (9b annotation) for book "{book_id}".

Command:
python3 scripts/stage1_pipeline.py \\
  --book-id {book_id} \\
  --config config/api.yaml \\
  --books config/books.yaml \\
  --toc config/mc_toc.json \\
  --output-dir {output_dir} \\
  --start-step 5 \\
  --retry-annotations

After it finishes, report annotation coverage and any failures.
{report_instruction(window_name, task['id'])}"""

    return run_codex_in_tmux(prompt, window_name, task["id"], dry_run, timeout=7200)


def run_ocr_stage1(task, book_id, dry_run=False):
    """OCR + Stage1 combo: auto-detect what's needed."""
    window_name = f"ocr_s1_{book_id}"
    raw_merged = L0_OUTPUT / book_id / "stage1" / "raw_merged.md"
    vlm_merged = L0_OUTPUT / book_id / "ocr" / "vlm_ocr_merged.md"
    source_pdf = L0_OUTPUT / book_id / "source_converted.pdf"

    if raw_merged.exists():
        # Already has raw_merged, just run stage1 from step 4
        prompt = f"""{ENV_CONTEXT}
Book "{book_id}" already has raw_merged.md. Run Stage1 from step 4.

Command:
python3 scripts/stage1_pipeline.py \\
  --book-id {book_id} --config config/api.yaml \\
  --books config/books.yaml --toc config/mc_toc.json \\
  --output-dir {L0_OUTPUT / book_id / 'stage1'} --start-step 4

Report chunks count.
{report_instruction(window_name, task['id'])}"""
    elif vlm_merged.exists():
        # Has VLM OCR output, copy to raw_merged then stage1
        prompt = f"""{ENV_CONTEXT}
Book "{book_id}" has vlm_ocr_merged.md. Copy to raw_merged.md then run Stage1.

Commands:
mkdir -p {L0_OUTPUT / book_id / 'stage1'}
cp {vlm_merged} {raw_merged}
python3 scripts/stage1_pipeline.py \\
  --book-id {book_id} --config config/api.yaml \\
  --books config/books.yaml --toc config/mc_toc.json \\
  --output-dir {L0_OUTPUT / book_id / 'stage1'} --start-step 4

Report chunks count.
{report_instruction(window_name, task['id'])}"""
    elif source_pdf.exists():
        # Needs OCR first
        prompt = f"""{ENV_CONTEXT}
Book "{book_id}" needs OCR + Stage1.

Step 1: Flash OCR
python3 scripts/flash_ocr_dashscope.py \\
  --pdf {source_pdf} \\
  --output-dir {L0_OUTPUT / book_id / 'ocr'}

Step 2: Copy OCR output
cp {L0_OUTPUT / book_id / 'ocr' / 'vlm_ocr_merged.md'} {L0_OUTPUT / book_id / 'stage1' / 'raw_merged.md'}

Step 3: Stage1
python3 scripts/stage1_pipeline.py \\
  --book-id {book_id} --config config/api.yaml \\
  --books config/books.yaml --toc config/mc_toc.json \\
  --output-dir {L0_OUTPUT / book_id / 'stage1'} --start-step 4

Report page count and chunks count.
{report_instruction(window_name, task['id'])}"""
    else:
        return "deferred", f"No source PDF found for {book_id}"

    return run_codex_in_tmux(prompt, window_name, task["id"], dry_run, timeout=7200)


def run_ocr_batch(task, dry_run=False):
    """批量 OCR — 找所有需要 OCR 的书。"""
    books_need_ocr = []
    for d in sorted(L0_OUTPUT.iterdir()):
        if not d.is_dir() or d.is_symlink():
            continue
        if d.name.startswith(("stage", "_", ".")):
            continue
        if (d / "stage1" / "raw_merged.md").exists():
            continue
        if (d / "ocr" / "vlm_ocr_merged.md").exists():
            continue
        if (d / "source_converted.pdf").exists():
            books_need_ocr.append(d.name)

    if not books_need_ocr:
        return "done", "No books need OCR"

    window_name = "ocr_batch"
    book_list = ", ".join(books_need_ocr[:5])
    prompt = f"""{ENV_CONTEXT}
Run qwen3.5-flash VLM OCR for these books: {book_list}

For each book:
1. Source PDF at ~/culinary-engine/output/{{book_id}}/source_converted.pdf
2. Output to ~/culinary-engine/output/{{book_id}}/ocr/vlm_ocr_pages.json and vlm_ocr_merged.md
3. Use: python3 scripts/flash_ocr_dashscope.py --pdf <pdf> --output-dir <ocr_dir>
4. MUST use trust_env=False (already in script)
5. Process sequentially (one at a time)

Report per book: total pages, success, failed, output path.
{report_instruction(window_name, task['id'])}"""

    return run_codex_in_tmux(prompt, window_name, task["id"], dry_run, timeout=7200)


def run_stage5(task, book_id, dry_run=False):
    window_name = f"s5_{book_id}"
    prompt = f"""{ENV_CONTEXT}
Run Stage5 recipe extraction for book "{book_id}".

Command:
python3 scripts/stage5_recipe_extract.py \\
  --book-id {book_id} \\
  --config config/api.yaml

Report recipe count and any errors.
{report_instruction(window_name, task['id'])}"""

    return run_codex_in_tmux(prompt, window_name, task["id"], dry_run, timeout=7200)


# ============================================================
# Code task: branch → Codex → PR
# ============================================================
def ensure_clean_main():
    """确保 main 分支干净且最新。"""
    result = subprocess.run(
        ["git", "-C", str(CE_DIR), "status", "--porcelain"],
        capture_output=True, text=True,
    )
    if result.stdout.strip():
        log.warning("Working tree not clean, stashing")
        subprocess.run(["git", "-C", str(CE_DIR), "stash"], capture_output=True)
    subprocess.run(
        ["git", "-C", str(CE_DIR), "checkout", "main"],
        capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(CE_DIR), "pull", "--ff-only"],
        capture_output=True,
    )


def create_task_branch(task):
    agent = task.get("agent", "orchestrator")
    slug = re.sub(r"[^a-z0-9]+", "-", task["title"].lower())[:30].strip("-")
    branch = f"agent/{agent}/{slug}-{task['id']}"
    subprocess.run(
        ["git", "-C", str(CE_DIR), "checkout", "-b", branch],
        capture_output=True,
    )
    return branch


def push_and_create_pr(branch, task):
    """Push 分支并创建 PR。"""
    # Check if there are commits
    result = subprocess.run(
        ["git", "-C", str(CE_DIR), "log", "main.." + branch, "--oneline"],
        capture_output=True, text=True,
    )
    if not result.stdout.strip():
        return None  # 无新 commit

    subprocess.run(
        ["git", "-C", str(CE_DIR), "push", "-u", "origin", branch],
        capture_output=True,
    )
    pr_result = subprocess.run(
        [GH_BIN, "pr", "create",
         "--repo", "hanny9494-ai/culinary-engine",
         "--title", task["title"],
         "--body", f"Auto-generated by orchestrator for task #{task['id']}",
         "--base", "main",
         "--head", branch],
        capture_output=True, text=True, cwd=str(CE_DIR),
    )
    if pr_result.returncode == 0:
        pr_url = pr_result.stdout.strip()
        log.info("  PR created: %s", pr_url)
        return pr_url
    else:
        log.error("  PR creation failed: %s", pr_result.stderr)
        return None


def run_code_task(task, dry_run=False):
    """代码任务: 建分支 → Codex 执行 → 提 PR。"""
    if dry_run:
        log.info("  [DRY-RUN] Would run code task: %s", task["title"][:80])
        return "done", "dry-run"

    ensure_clean_main()
    branch = create_task_branch(task)
    window_name = f"code_{task['id']}"

    prompt = f"""{ENV_CONTEXT}
Code task: {task['title']}

Objective: {task.get('objective', task['title'])}

You are on branch {branch}. Make the necessary changes, then:
1. git add the changed files
2. git commit with a descriptive message
3. Do NOT push — the orchestrator will push and create a PR.

{report_instruction(window_name, task['id'])}"""

    status, summary = run_codex_in_tmux(prompt, window_name, task["id"], dry_run, timeout=3600)

    # Check for commits and create PR
    pr_url = push_and_create_pr(branch, task)

    # Switch back to main
    subprocess.run(["git", "-C", str(CE_DIR), "checkout", "main"], capture_output=True)

    if pr_url:
        return "pr_open", f"PR: {pr_url}"
    elif status == "done":
        # No commits made, clean up branch
        subprocess.run(
            ["git", "-C", str(CE_DIR), "branch", "-d", branch],
            capture_output=True,
        )
        return "done", summary
    else:
        return status, summary


# ============================================================
# Poll open PRs
# ============================================================
def poll_open_prs():
    """检查 pr_open 状态的任务对应的 PR 是否已 merged/closed。"""
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT * FROM tasks WHERE status = 'pr_open'"
        ).fetchall()
        for row in rows:
            task = dict(row)
            branch = task.get("branch", "")
            if not branch:
                continue
            # Check PR status via gh
            result = subprocess.run(
                [GH_BIN, "pr", "view", branch,
                 "--repo", "hanny9494-ai/culinary-engine",
                 "--json", "state"],
                capture_output=True, text=True, cwd=str(CE_DIR),
            )
            if result.returncode == 0:
                try:
                    state = json.loads(result.stdout).get("state", "")
                    if state == "MERGED":
                        update_task(conn, task["id"], "done", "PR merged")
                        log.info("  PR merged for task #%d", task["id"])
                    elif state == "CLOSED":
                        update_task(conn, task["id"], "failed", "PR closed without merge")
                        log.info("  PR closed for task #%d", task["id"])
                except json.JSONDecodeError:
                    pass
    finally:
        conn.close()


# ============================================================
# Learnings & Auto-fix
# ============================================================
def collect_learnings(report_path):
    """从 report 提取 learnings 追加到 learnings.jsonl。"""
    if not report_path.exists():
        return
    try:
        report = json.loads(report_path.read_text())
    except Exception:
        return

    suggestions = report.get("suggestions", [])
    problems = report.get("problems", [])
    if not suggestions and not problems:
        return

    entry = {
        "timestamp": datetime.now().isoformat(),
        "task": report.get("task", ""),
        "task_id": report.get("task_id", 0),
        "suggestions": suggestions,
        "problems": problems,
    }
    with open(LEARNINGS_PATH, "a") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    log.info("  Learnings recorded from %s", report_path.name)


# Auto-fix patterns
AUTO_FIX_PATTERNS = [
    ("script_not_found", re.compile(r"No such file|FileNotFoundError|script not found", re.I)),
    ("permission_error", re.compile(r"PermissionError|permission denied", re.I)),
    ("timeout", re.compile(r"timeout|timed out|TimeoutError", re.I)),
    ("ollama_down", re.compile(r"Connection refused.*11434|ollama.*connect", re.I)),
    ("chunks_missing", re.compile(r"chunks_smart.*not found|chunks_smart\.json", re.I)),
    ("no_pdf_has_md", re.compile(r"source_converted.*not found.*raw_merged", re.I)),
    ("rate_limit", re.compile(r"429|rate.?limit|too many requests", re.I)),
]


def auto_fix_from_report(report):
    """检测可自动修复的模式，返回动作。"""
    if not report:
        return None

    problems_text = json.dumps(report.get("problems", []), ensure_ascii=False)
    for fix_name, pattern in AUTO_FIX_PATTERNS:
        if pattern.search(problems_text):
            return fix_name
    return None


def apply_auto_fix(fix_name, task, conn):
    """根据 auto-fix 模式执行对应动作。"""
    task_id = task["id"]
    log.info("  Auto-fix: %s for task #%d", fix_name, task_id)

    entry = {
        "timestamp": datetime.now().isoformat(),
        "task_id": task_id,
        "fix": fix_name,
        "title": task.get("title", ""),
    }

    if fix_name in ("timeout", "permission_error"):
        # 重试: 重新设为 pending
        update_task(conn, task_id, "pending", f"auto-retry after {fix_name}")
        entry["action"] = "retry"

    elif fix_name in ("ollama_down", "rate_limit"):
        # 推迟: 保持 pending，下一轮自然重试
        entry["action"] = "deferred"

    elif fix_name == "chunks_missing":
        # 推迟等 Stage1 完成
        update_task(conn, task_id, "pending", "deferred: waiting for Stage1")
        entry["action"] = "deferred_stage1"

    elif fix_name == "no_pdf_has_md":
        # 改成 Stage1 任务
        book_id = extract_book_id(task)
        if book_id:
            new_title = f"Stage1: {book_id} (converted from OCR task)"
            conn.execute(
                "INSERT INTO tasks (title, agent, priority, status) VALUES (?, 'pipeline-runner', ?, 'pending')",
                (new_title, task.get("priority", "P1")),
            )
            conn.commit()
            entry["action"] = "converted_to_stage1"

    elif fix_name == "script_not_found":
        # 标记等 CC Lead 人工处理
        update_task(conn, task_id, "failed", f"auto-fix: {fix_name} — needs CC Lead")
        entry["action"] = "escalated"

    else:
        entry["action"] = "logged_only"

    with open(FIX_LOG_PATH, "a") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


# ============================================================
# Dify KB 同步
# ============================================================
def sync_report_to_dify(report_path):
    """上传单个 report 到 Dify KB。"""
    if not report_path.exists():
        return
    try:
        import requests
        s = requests.Session()
        s.trust_env = False
        content = report_path.read_text()
        r = s.post(
            f"{DIFY_URL}/v1/datasets/{DIFY_DATASET_ID}/document/create-by-text",
            headers={"Authorization": f"Bearer {DIFY_DATASET_KEY}"},
            json={
                "name": report_path.name,
                "text": content,
                "indexing_technique": "economy",
                "process_rule": {"mode": "automatic"},
            },
            timeout=30,
        )
        if r.status_code in (200, 201):
            log.info("  Dify: uploaded %s", report_path.name)
        else:
            log.warning("  Dify: upload failed %d", r.status_code)
    except Exception as e:
        log.warning("  Dify sync error: %s", e)


def sync_kb_periodic():
    """定期同步 learnings 和 auto_fixes 到 Dify。"""
    for path in [LEARNINGS_PATH, FIX_LOG_PATH]:
        if path.exists() and path.stat().st_size > 0:
            sync_report_to_dify(path)


# ============================================================
# Data task dispatcher (threaded)
# ============================================================
def _run_data_task(task, dry_run=False):
    """在线程中执行一个数据任务，含资源锁。"""
    task_id = task["id"]
    task_type = detect_task_type(task)
    book_id = extract_book_id(task)
    resource = RESOURCE_MAP.get(task_type, "codex_general")
    sem = _resource_slots.get(resource)

    log.info("Task #%d: %s (type=%s, book=%s, resource=%s)",
             task_id, task["title"][:60], task_type, book_id or "batch", resource)

    # Acquire resource
    if sem:
        log.info("  Acquiring %s slot...", resource)
        sem.acquire()
        log.info("  Got %s slot", resource)

    conn = get_db()
    update_task(conn, task_id, "in_progress")

    try:
        if task_type == "stage4" and book_id:
            status, summary = run_stage4(task, book_id, dry_run)
        elif task_type == "stage1" and book_id:
            status, summary = run_stage1(task, book_id, dry_run)
        elif task_type == "stage1_step5" and book_id:
            status, summary = run_stage1_step5(task, book_id, dry_run)
        elif task_type == "ocr_stage1" and book_id:
            status, summary = run_ocr_stage1(task, book_id, dry_run)
        elif task_type == "ocr":
            status, summary = run_ocr_batch(task, dry_run)
        elif task_type == "stage5" and book_id:
            status, summary = run_stage5(task, book_id, dry_run)
        else:
            status, summary = "failed", f"Unknown data task type: {task_type}"

        # 处理 deferred
        if status == "deferred":
            log.info("  Deferred: %s", summary)
            update_task(conn, task_id, "pending", f"deferred: {summary}")
            return

        update_task(conn, task_id, status, summary)
        log.info("  → %s: %s", status, summary[:100])

        # 完成后处理
        window_name = f"s4_{book_id}" if task_type == "stage4" else f"{task_type}_{book_id or 'batch'}"
        report_path = REPORT_DIR / f"{window_name}.json"
        collect_learnings(report_path)

        report = _read_report(window_name)
        fix = auto_fix_from_report(report)
        if fix and status == "failed":
            apply_auto_fix(fix, task, conn)

        sync_report_to_dify(report_path)

    except Exception as e:
        log.exception("  Error in task #%d: %s", task_id, e)
        update_task(conn, task_id, "failed", str(e)[:200])
    finally:
        if sem:
            sem.release()
        conn.close()
        with _running_lock:
            _running_tasks.pop(task_id, None)


# ============================================================
# Main loop
# ============================================================
def main_loop(once=False, dry_run=False):
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    log.info("=== Orchestrator v2 started ===")
    log.info("  DB: %s", DB_PATH)
    log.info("  Output: %s", L0_OUTPUT)
    log.info("  Interval: %ds", LOOP_INTERVAL)
    log.info("  Dry-run: %s", dry_run)

    loop_count = 0

    while running:
        loop_count += 1
        log.info("--- Loop %d ---", loop_count)

        try:
            # Phase 0: Dify KB 定期同步
            if loop_count % KB_SYNC_EVERY == 0:
                log.info("Phase 0: KB sync")
                sync_kb_periodic()

            # Phase 1: Poll open PRs
            log.info("Phase 1: Poll PRs")
            poll_open_prs()

            # Phase 2: 清理已完成线程
            with _running_lock:
                done_ids = [tid for tid, t in _running_tasks.items() if not t.is_alive()]
                for tid in done_ids:
                    _running_tasks.pop(tid, None)
                    log.info("  Thread for task #%d finished", tid)
                active_count = len(_running_tasks)

            log.info("Phase 2: %d active threads", active_count)

            # Phase 3: 派发 pending 任务
            conn = get_db()
            pending = get_pending_tasks(conn)
            conn.close()

            if not pending:
                log.info("Phase 3: No pending tasks")
            else:
                log.info("Phase 3: %d pending tasks", len(pending))

                for task in pending:
                    task_id = task["id"]

                    # Skip if already running
                    with _running_lock:
                        if task_id in _running_tasks:
                            continue

                    task_type = detect_task_type(task)

                    if task_type in DATA_TASK_TYPES:
                        # 检查资源是否可用（非阻塞）
                        resource = RESOURCE_MAP.get(task_type, "codex_general")
                        sem = _resource_slots.get(resource)
                        if sem and sem._value <= 0:
                            log.info("  Skip task #%d (%s): %s busy", task_id, task_type, resource)
                            continue

                        # 启动线程
                        t = threading.Thread(
                            target=_run_data_task,
                            args=(task, dry_run),
                            name=f"task-{task_id}",
                            daemon=True,
                        )
                        with _running_lock:
                            _running_tasks[task_id] = t
                        t.start()
                    else:
                        # 代码任务: 同步执行（一次只跑一个）
                        conn2 = get_db()
                        update_task(conn2, task_id, "in_progress")
                        conn2.close()

                        status, summary = run_code_task(task, dry_run)

                        conn2 = get_db()
                        update_task(conn2, task_id, status, summary)
                        conn2.close()
                        log.info("  Code task #%d → %s", task_id, status)

        except Exception as e:
            log.exception("Error in main loop: %s", e)

        if once:
            break

        time.sleep(LOOP_INTERVAL)

    # 等待所有线程结束
    with _running_lock:
        threads = list(_running_tasks.values())
    for t in threads:
        t.join(timeout=30)

    log.info("=== Orchestrator v2 stopped ===")


def main():
    parser = argparse.ArgumentParser(description="Pipeline Orchestrator v2")
    parser.add_argument("--once", action="store_true", help="只跑一轮就退出")
    parser.add_argument("--dry-run", action="store_true", help="只看不做")
    parser.add_argument("--interval", type=int, default=60, help="轮询间隔（秒）")
    args = parser.parse_args()

    global LOOP_INTERVAL
    LOOP_INTERVAL = args.interval

    main_loop(once=args.once, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
