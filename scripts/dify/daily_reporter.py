#!/usr/bin/env python3
"""
Daily Reporter — 扫描本地 output 目录，生成每日进度报告。

两种运行模式：
1. 独立运行：python3 scripts/dify/daily_reporter.py
2. 被 Dify Schedule Trigger 调用：通过 webhook

输出：
- 打印报告到 stdout
- 保存到 ~/culinary-engine/reports/daily_{date}.md
- POST 到 Dify KB（可选）

Usage:
    python3 scripts/dify/daily_reporter.py
    python3 scripts/dify/daily_reporter.py --since 2026-03-22
    python3 scripts/dify/daily_reporter.py --post-dify
"""

import json
import os
import time
import argparse
from pathlib import Path
from datetime import datetime, timedelta
from collections import Counter

L0_OUTPUT = Path(__file__).resolve().parent.parent.parent / "output"
CE_OUTPUT = Path.home() / "culinary-engine" / "output"
REPORT_DIR = Path.home() / "culinary-engine" / "reports"


def scan_stage4_books():
    """Scan all stage4 results."""
    books = {}
    for d in sorted(L0_OUTPUT.iterdir()):
        if not d.is_dir() or d.is_symlink():
            continue
        s4 = d / "stage4"
        if not s4.exists():
            continue

        book = d.name
        qc_file = s4 / "l0_principles_open.jsonl"
        raw_file = s4 / "stage4_raw.jsonl"

        qc_count = 0
        raw_count = 0
        if qc_file.exists():
            with open(qc_file) as f:
                qc_count = sum(1 for _ in f)
        if raw_file.exists():
            with open(raw_file) as f:
                raw_count = sum(1 for _ in f)

        books[book] = {
            "raw": raw_count,
            "qc_passed": qc_count,
            "has_stage4": True,
        }
    return books


def scan_stage1_status():
    """Scan Stage1 status for all books."""
    books = {}

    # Check both output directories
    for base in [L0_OUTPUT, CE_OUTPUT]:
        for d in sorted(base.iterdir()):
            if not d.is_dir() or d.is_symlink():
                continue
            name = d.name
            if name.startswith("stage") or name.startswith("_"):
                continue

            if name not in books:
                books[name] = {"ocr": False, "raw_merged": False,
                               "chunks_raw": 0, "chunks_smart": 0}

            # OCR
            ocr_dir = d / "ocr"
            if not ocr_dir.exists():
                ocr_dir = d / "vlm_full_flash"
            if ocr_dir.exists():
                pages_file = ocr_dir / "vlm_ocr_pages.json"
                if pages_file.exists():
                    books[name]["ocr"] = True

            # Stage1
            s1 = d / "stage1"
            if s1.exists():
                if (s1 / "raw_merged.md").exists():
                    books[name]["raw_merged"] = True
                cr = s1 / "chunks_raw.json"
                if cr.exists():
                    try:
                        books[name]["chunks_raw"] = len(json.load(open(cr)))
                    except Exception:
                        pass
                cs = s1 / "chunks_smart.json"
                if cs.exists():
                    try:
                        books[name]["chunks_smart"] = len(json.load(open(cs)))
                    except Exception:
                        pass
            else:
                # Check root level (legacy)
                if (d / "raw_merged.md").exists():
                    books[name]["raw_merged"] = True
                for fname in ["chunks_raw.json", "chunks_smart.json"]:
                    f = d / fname
                    if f.exists():
                        try:
                            count = len(json.load(open(f)))
                            key = fname.replace(".json", "").replace("chunks_", "chunks_")
                            books[name][key] = count
                        except Exception:
                            pass

    return books


def scan_stage5_status():
    """Scan Stage5 recipe extraction status."""
    books = {}
    for d in L0_OUTPUT.iterdir():
        if not d.is_dir() or d.is_symlink():
            continue
        s5 = d / "stage5"
        if not s5.exists():
            continue
        results = s5 / "stage5_results.jsonl"
        if results.exists():
            with open(results) as f:
                count = sum(1 for _ in f)
            books[d.name] = count
    return books


def find_recently_modified(since_ts):
    """Find files modified since timestamp."""
    changes = []
    for base in [L0_OUTPUT, CE_OUTPUT]:
        for f in base.rglob("*"):
            if f.is_file() and f.stat().st_mtime > since_ts:
                rel = str(f.relative_to(base.parent))
                changes.append((f.stat().st_mtime, rel, f.stat().st_size))

    changes.sort(reverse=True)
    return changes[:50]  # Top 50 most recent


def check_running_processes():
    """Check for running pipeline processes."""
    import subprocess
    result = subprocess.run(
        ["ps", "aux"], capture_output=True, text=True)
    lines = result.stdout.split("\n")
    pipeline_procs = []
    for line in lines:
        if any(kw in line for kw in ["stage1_pipeline", "stage4_open_extract",
                                      "stage5_recipe", "ollama run", "l2a_pilot"]):
            if "grep" not in line:
                parts = line.split()
                if len(parts) > 10:
                    pipeline_procs.append(" ".join(parts[10:])[:80])
    return pipeline_procs


def generate_report(since_date=None):
    """Generate the daily report."""
    now = datetime.now()
    if since_date:
        since = datetime.strptime(since_date, "%Y-%m-%d")
    else:
        since = now - timedelta(hours=24)
    since_ts = since.timestamp()

    # Scan everything
    s4_books = scan_stage4_books()
    s1_books = scan_stage1_status()
    s5_books = scan_stage5_status()
    recent = find_recently_modified(since_ts)
    procs = check_running_processes()

    # Calculate totals
    total_qc = sum(b["qc_passed"] for b in s4_books.values())
    total_raw = sum(b["raw"] for b in s4_books.values())
    s4_count = len(s4_books)

    s1_complete = sum(1 for b in s1_books.values() if b["chunks_smart"] > 0)
    s1_ocr_done = sum(1 for b in s1_books.values() if b["ocr"])
    total_books = len(s1_books)

    s5_count = len(s5_books)
    s5_recipes = sum(s5_books.values())

    # Find what changed today
    changed_books = set()
    for _, path, _ in recent:
        parts = path.split("/")
        if len(parts) >= 3:
            changed_books.add(parts[1])

    # Build report
    lines = []
    lines.append(f"# Daily Report — {now.strftime('%Y-%m-%d %H:%M')}")
    lines.append(f"")
    lines.append(f"## L0 Summary")
    lines.append(f"- **L0 QC通过：{total_qc:,} 条**（{s4_count} 本书）")
    lines.append(f"- L0 raw 提取：{total_raw:,} 条")
    lines.append(f"- Stage3 骨架：690 条")
    lines.append(f"- **L0 总计：{total_qc + 690:,} 条**")
    lines.append(f"")

    lines.append(f"## Pipeline Status")
    lines.append(f"- 总书数：{total_books}")
    lines.append(f"- Stage4 完成：{s4_count}")
    lines.append(f"- Stage1 完成（有 chunks_smart）：{s1_complete}")
    lines.append(f"- OCR 完成：{s1_ocr_done}")
    lines.append(f"- Stage5 食谱提取：{s5_count} 本，{s5_recipes:,} 条")
    lines.append(f"")

    # Categorize books
    ready_for_s4 = []
    need_s1 = []
    need_ocr = []
    for name, s1 in s1_books.items():
        if name in s4_books:
            continue  # Already done
        if s1["chunks_smart"] > 0:
            ready_for_s4.append(f"{name}({s1['chunks_smart']})")
        elif s1["raw_merged"] and s1["chunks_raw"] == 0:
            need_s1.append(f"{name}(need 2b)")
        elif s1["ocr"] and not s1["raw_merged"]:
            need_s1.append(f"{name}(need merge)")
        elif not s1["ocr"] and not s1["raw_merged"]:
            need_ocr.append(name)

    lines.append(f"## Queue")
    lines.append(f"- **就绪进 Stage4**（{len(ready_for_s4)}）：{', '.join(ready_for_s4)}")
    lines.append(f"- **需要 Stage1**（{len(need_s1)}）：{', '.join(need_s1)}")
    lines.append(f"- **需要 OCR**（{len(need_ocr)}）：{', '.join(need_ocr)}")
    lines.append(f"")

    # Running processes
    lines.append(f"## Running Processes")
    if procs:
        for p in procs:
            lines.append(f"- 🔄 {p}")
    else:
        lines.append(f"- (idle)")
    lines.append(f"")

    # Recent changes
    if changed_books:
        lines.append(f"## Today's Changes")
        lines.append(f"Books with file changes since {since.strftime('%Y-%m-%d %H:%M')}:")
        for book in sorted(changed_books)[:20]:
            lines.append(f"- {book}")
        lines.append(f"")

    # Recent files (top 10)
    if recent:
        lines.append(f"## Most Recent Files")
        for mtime, path, size in recent[:10]:
            t = datetime.fromtimestamp(mtime).strftime("%H:%M")
            sz = f"{size/1024:.0f}K" if size < 1e6 else f"{size/1e6:.1f}M"
            lines.append(f"- `{t}` {sz} {path}")
        lines.append(f"")

    return "\n".join(lines)


def save_report(report):
    """Save report to file."""
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    date_str = datetime.now().strftime("%Y%m%d")
    path = REPORT_DIR / f"daily_{date_str}.md"
    path.write_text(report, encoding="utf-8")
    return path


def post_to_dify(report):
    """Upload report to Dify KB."""
    import base64
    import requests

    s = requests.Session()
    s.trust_env = False
    pwd = base64.b64encode(b"Jeffery96352101").decode()
    s.post("http://localhost/console/api/login",
           headers={"Content-Type": "application/json"},
           json={"email": "hanny9494@gmail.com", "password": pwd})
    s.headers["X-CSRF-Token"] = s.cookies.get("csrf_token")

    # Upload to culinary-engine-status KB
    ds_id = "65b3d570-7a71-4a8c-bcc4-b377c635d1d8"
    date_str = datetime.now().strftime("%Y%m%d")
    fname = f"daily_{date_str}.md"

    # Upload file
    csrf = s.headers.get("X-CSRF-Token", "")
    r = s.post("http://localhost/console/api/files/upload",
               headers={"X-CSRF-Token": csrf, "Content-Type": None},
               files={"file": (fname, report.encode(), "text/markdown")},
               data={"source": "datasets"})
    if r.status_code not in (200, 201):
        print(f"  ⚠ Upload failed: {r.status_code}")
        return

    file_id = r.json()["id"]
    s.headers["Content-Type"] = "application/json"
    s.post(f"http://localhost/console/api/datasets/{ds_id}/documents", json={
        "indexing_technique": "high_quality",
        "process_rule": {
            "mode": "custom",
            "rules": {
                "pre_processing_rules": [
                    {"id": "remove_extra_spaces", "enabled": True},
                    {"id": "remove_urls_emails", "enabled": False}
                ],
                "segmentation": {"separator": "\n## ", "max_tokens": 1000, "chunk_overlap": 100}
            }
        },
        "data_source": {
            "type": "upload_file",
            "info_list": {"data_source_type": "upload_file",
                          "file_info_list": {"file_ids": [file_id]}}
        },
        "doc_form": "text_model",
        "doc_language": "Chinese",
    })
    print(f"  ✅ Report uploaded to Dify KB")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--since", help="Report since date (YYYY-MM-DD)")
    parser.add_argument("--post-dify", action="store_true", help="Upload to Dify KB")
    parser.add_argument("--quiet", action="store_true", help="Only save, don't print")
    args = parser.parse_args()

    report = generate_report(args.since)

    if not args.quiet:
        print(report)

    path = save_report(report)
    print(f"\n📄 Saved: {path}")

    if args.post_dify:
        post_to_dify(report)


if __name__ == "__main__":
    main()
