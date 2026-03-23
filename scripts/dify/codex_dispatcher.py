#!/usr/bin/env python3
"""
Codex Task Dispatcher — CC Lead 通过此脚本把编码任务交给 Codex 执行。

可独立运行，也可被 Dify webhook workflow 调用。

Usage:
    # 直接调用
    python3 scripts/dify/codex_dispatcher.py --task "修复 stage4_open_extract.py 的 resume 逻辑"

    # 指定工作目录和分支
    python3 scripts/dify/codex_dispatcher.py \
        --task "添加 token 统计到 stage3_distill.py" \
        --workdir ~/culinary-engine \
        --branch agent/add-token-stats

    # 从 JSON 文件读取任务
    python3 scripts/dify/codex_dispatcher.py --task-file /tmp/task.json
"""

import json
import subprocess
import argparse
import time
from pathlib import Path
from datetime import datetime

CODEX_BIN = Path.home() / "bin" / "codex"
DEFAULT_WORKDIR = Path.home() / "culinary-engine"
RESULT_DIR = Path.home() / "l0-knowledge-engine" / "data" / "codex_results"

TASK_CONTEXT = """## Context
- 项目：culinary-engine（餐饮科学推理引擎）
- 代码仓库：~/culinary-engine
- 数据目录：~/l0-knowledge-engine/output
- 所有 HTTP 客户端必须 trust_env=False（本机有代理 127.0.0.1:7890）
- Ollama 调用必须串行（不能并发跑多本书）
- 保持现有 CLI argparse 接口兼容
- 保持 JSON/JSONL 输出格式兼容
- 不改 STATUS.md / HANDOFF.md / HANDOVER.md（母对话维护）

## Key Files Reference
- config/api.yaml — API 配置
- config/books.yaml — 书籍注册表
- scripts/stage1_pipeline.py — Stage1 全流程
- scripts/stage4_open_extract.py — Stage4 开放提取
- scripts/stage4_dedup.py — Stage4 去重
- scripts/stage4_quality.py — Stage4 质控
- scripts/stage5_recipe_extract.py — Stage5 食谱提取
- scripts/utils/ — 共享工具模块
"""


def create_branch(workdir, branch_name):
    """Create and checkout a new branch."""
    result = subprocess.run(
        ["git", "checkout", "-b", branch_name],
        cwd=workdir, capture_output=True, text=True)
    if result.returncode != 0:
        # Branch might exist, try checkout
        subprocess.run(
            ["git", "checkout", branch_name],
            cwd=workdir, capture_output=True, text=True)
    return result.returncode == 0


def run_codex(task_prompt, workdir, output_file, full_auto=True):
    """Run codex exec with the given task."""
    cmd = [
        str(CODEX_BIN), "exec",
        "-C", str(workdir),
        "-o", str(output_file),
    ]
    if full_auto:
        cmd.append("--full-auto")

    # Combine task with context
    full_prompt = f"{task_prompt}\n\n{TASK_CONTEXT}"
    cmd.append(full_prompt)

    print(f"Running Codex...")
    print(f"  Workdir: {workdir}")
    print(f"  Output:  {output_file}")
    print(f"  Task:    {task_prompt[:100]}...")

    start = time.time()
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=600,  # 10 minute timeout
        env={**dict(__import__('os').environ), "PATH": f"{Path.home()}/bin:" + __import__('os').environ.get("PATH", "")},
    )
    elapsed = time.time() - start

    return {
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "elapsed_seconds": round(elapsed, 1),
    }


def get_git_diff(workdir):
    """Get git diff after Codex execution."""
    result = subprocess.run(
        ["git", "diff", "--stat"],
        cwd=workdir, capture_output=True, text=True)
    return result.stdout


def main():
    parser = argparse.ArgumentParser(description="Dispatch coding task to Codex")
    parser.add_argument("--task", help="Task description")
    parser.add_argument("--task-file", help="JSON file with task details")
    parser.add_argument("--workdir", default=str(DEFAULT_WORKDIR))
    parser.add_argument("--branch", help="Git branch to work on")
    parser.add_argument("--no-auto", action="store_true", help="Don't use --full-auto")
    args = parser.parse_args()

    # Parse task
    if args.task_file:
        task_data = json.loads(Path(args.task_file).read_text())
        task = task_data.get("task", task_data.get("prompt", ""))
        branch = task_data.get("branch", args.branch)
        workdir = Path(task_data.get("workdir", args.workdir))
    elif args.task:
        task = args.task
        branch = args.branch
        workdir = Path(args.workdir)
    else:
        print("ERROR: Provide --task or --task-file")
        return

    # Setup
    RESULT_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = RESULT_DIR / f"codex_{timestamp}.md"

    # Branch
    if branch:
        print(f"Creating branch: {branch}")
        create_branch(workdir, branch)

    # Execute
    result = run_codex(task, workdir, output_file, full_auto=not args.no_auto)

    # Report
    diff = get_git_diff(workdir)

    report = {
        "timestamp": timestamp,
        "task": task,
        "branch": branch,
        "workdir": str(workdir),
        "codex_returncode": result["returncode"],
        "elapsed_seconds": result["elapsed_seconds"],
        "output_file": str(output_file),
        "git_diff_stat": diff,
    }

    # Save report
    report_file = RESULT_DIR / f"codex_{timestamp}_report.json"
    report_file.write_text(json.dumps(report, indent=2, ensure_ascii=False))

    print(f"\n{'='*60}")
    print(f"Codex Task Complete")
    print(f"{'='*60}")
    print(f"  Status:   {'✓ Success' if result['returncode'] == 0 else '✗ Failed'}")
    print(f"  Time:     {result['elapsed_seconds']}s")
    print(f"  Output:   {output_file}")
    print(f"  Report:   {report_file}")
    if diff:
        print(f"  Changes:\n{diff}")
    else:
        print(f"  Changes:  (none)")

    if result["stderr"]:
        print(f"\n  Stderr:\n{result['stderr'][:500]}")

    return report


if __name__ == "__main__":
    main()
