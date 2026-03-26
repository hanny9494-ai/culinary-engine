#!/usr/bin/env python3
"""
Lightweight webhook server — receives task JSON from Dify, dispatches to Codex.

Dify workflow sends POST to http://localhost:8741/codex/dispatch with:
{
    "task": "修复 stage4 resume 逻辑",
    "branch": "agent/fix-resume",
    "workdir": "~/culinary-engine",
    "priority": "P0"
}

Server runs Codex, collects result, returns summary.

Usage:
    python3 scripts/dify/codex_webhook_server.py  # starts on port 8741
"""

import json
import subprocess
import time
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from datetime import datetime

PORT = 8741
CODEX_BIN = str(Path.home() / "bin" / "codex")
DEFAULT_WORKDIR = str(Path.home() / "culinary-engine")
RESULT_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "codex_results"
RESULT_DIR.mkdir(parents=True, exist_ok=True)

TASK_CONTEXT = """## Context
- 项目：culinary-engine（餐饮科学推理引擎）
- 代码仓库：~/culinary-engine
- 数据目录：~/culinary-engine/output
- trust_env=False（本机代理 127.0.0.1:7890）
- Ollama 串行，不并发
- 保持 CLI 和输出格式兼容
- 不改 STATUS.md / HANDOFF.md
"""

# Track running tasks
running_tasks = {}
task_history = []


class CodexHandler(BaseHTTPRequestHandler):

    def do_POST(self):
        if self.path == "/codex/dispatch":
            self._dispatch()
        elif self.path == "/codex/status":
            self._status()
        else:
            self._respond(404, {"error": "not found"})

    def do_GET(self):
        if self.path == "/codex/health":
            self._respond(200, {"status": "ok", "running": len(running_tasks)})
        elif self.path == "/codex/history":
            self._respond(200, {"tasks": task_history[-20:]})
        else:
            self._respond(404, {"error": "not found"})

    def _read_body(self):
        length = int(self.headers.get("Content-Length", 0))
        return json.loads(self.rfile.read(length)) if length > 0 else {}

    def _respond(self, code, data):
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode())

    def _dispatch(self):
        body = self._read_body()
        task = body.get("task", "")
        if not task:
            self._respond(400, {"error": "missing 'task' field"})
            return

        branch = body.get("branch", "")
        workdir = body.get("workdir", DEFAULT_WORKDIR)
        workdir = str(Path(workdir).expanduser())

        task_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = RESULT_DIR / f"codex_{task_id}.md"

        # Start Codex in background
        entry = {
            "task_id": task_id,
            "task": task,
            "branch": branch,
            "workdir": workdir,
            "status": "running",
            "started_at": datetime.now().isoformat(),
        }
        running_tasks[task_id] = entry

        thread = threading.Thread(
            target=self._run_codex,
            args=(task_id, task, workdir, branch, output_file),
            daemon=True)
        thread.start()

        self._respond(202, {
            "task_id": task_id,
            "status": "dispatched",
            "message": f"Codex task started. Check /codex/status with task_id={task_id}",
        })

    def _run_codex(self, task_id, task, workdir, branch, output_file):
        import os
        try:
            # Create branch if specified
            if branch:
                subprocess.run(
                    ["git", "checkout", "-b", branch],
                    cwd=workdir, capture_output=True)

            full_prompt = f"{task}\n\n{TASK_CONTEXT}"
            env = {**os.environ, "PATH": f"{Path.home()}/bin:{os.environ.get('PATH', '')}"}

            start = time.time()
            result = subprocess.run(
                [CODEX_BIN, "exec", "--full-auto",
                 "-C", workdir, "-o", str(output_file), full_prompt],
                capture_output=True, text=True, timeout=600, env=env)
            elapsed = time.time() - start

            # Get diff
            diff = subprocess.run(
                ["git", "diff", "--stat"],
                cwd=workdir, capture_output=True, text=True).stdout

            # Read output
            codex_output = ""
            if output_file.exists():
                codex_output = output_file.read_text()[:2000]

            entry = running_tasks[task_id]
            entry.update({
                "status": "done" if result.returncode == 0 else "failed",
                "elapsed_seconds": round(elapsed, 1),
                "returncode": result.returncode,
                "git_diff": diff,
                "output_preview": codex_output[:500],
                "output_file": str(output_file),
                "completed_at": datetime.now().isoformat(),
            })

        except Exception as e:
            running_tasks[task_id]["status"] = "error"
            running_tasks[task_id]["error"] = str(e)

        finally:
            task_history.append(running_tasks.pop(task_id, {}))

    def _status(self):
        body = self._read_body()
        task_id = body.get("task_id", "")

        if task_id in running_tasks:
            self._respond(200, running_tasks[task_id])
        else:
            # Check history
            for t in reversed(task_history):
                if t.get("task_id") == task_id:
                    self._respond(200, t)
                    return
            self._respond(404, {"error": f"task {task_id} not found"})

    def log_message(self, format, *args):
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {args[0]}")


def main():
    server = HTTPServer(("127.0.0.1", PORT), CodexHandler)
    print(f"Codex webhook server on http://127.0.0.1:{PORT}")
    print(f"  POST /codex/dispatch  — submit task")
    print(f"  POST /codex/status    — check task status")
    print(f"  GET  /codex/health    — health check")
    print(f"  GET  /codex/history   — recent tasks")
    server.serve_forever()


if __name__ == "__main__":
    main()
