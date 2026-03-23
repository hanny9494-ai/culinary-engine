#!/usr/bin/env python3
"""
Task Queue — 持久化任务管理，CC Lead 创建任务，Dify/webhook 查询状态。

SQLite 存储，HTTP API 暴露，Dify workflow 可通过 HTTP 调用。

Endpoints:
  POST /tasks/create     — 创建任务
  POST /tasks/update     — 更新任务状态
  GET  /tasks/list       — 列出任务（可按状态过滤）
  GET  /tasks/summary    — 当前摘要（给 CC Lead 恢复上下文用）
  GET  /tasks/health     — 健康检查

Usage:
    python3 scripts/dify/task_queue.py                    # 启动 server (port 8742)
    python3 scripts/dify/task_queue.py --create "任务描述"  # CLI 创建任务
    python3 scripts/dify/task_queue.py --summary           # CLI 查看摘要
"""

import json
import sqlite3
import argparse
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from datetime import datetime
from urllib.parse import urlparse, parse_qs

DB_PATH = Path.home() / "culinary-engine" / "data" / "task_queue.db"
PORT = 8742


# ============================================================
# Database
# ============================================================
def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            agent TEXT DEFAULT '',
            priority TEXT DEFAULT 'P1',
            status TEXT DEFAULT 'pending',
            branch TEXT DEFAULT '',
            objective TEXT DEFAULT '',
            input_path TEXT DEFAULT '',
            output_path TEXT DEFAULT '',
            result_summary TEXT DEFAULT '',
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now')),
            completed_at TEXT DEFAULT ''
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS task_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id INTEGER,
            action TEXT,
            detail TEXT DEFAULT '',
            timestamp TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (task_id) REFERENCES tasks(id)
        )
    """)
    conn.commit()
    return conn


def create_task(conn, title, agent="", priority="P1", objective="",
                input_path="", output_path="", branch=""):
    cur = conn.execute(
        """INSERT INTO tasks (title, agent, priority, status, branch, objective, input_path, output_path)
           VALUES (?, ?, ?, 'pending', ?, ?, ?, ?)""",
        (title, agent, priority, branch, objective, input_path, output_path))
    task_id = cur.lastrowid
    conn.execute("INSERT INTO task_log (task_id, action, detail) VALUES (?, 'created', ?)",
                 (task_id, title))
    conn.commit()
    return task_id


def update_task(conn, task_id, status=None, result_summary=None):
    updates = ["updated_at = datetime('now')"]
    params = []
    if status:
        updates.append("status = ?")
        params.append(status)
        if status in ("done", "failed"):
            updates.append("completed_at = datetime('now')")
    if result_summary:
        updates.append("result_summary = ?")
        params.append(result_summary)
    params.append(task_id)
    conn.execute(f"UPDATE tasks SET {', '.join(updates)} WHERE id = ?", params)
    conn.execute("INSERT INTO task_log (task_id, action, detail) VALUES (?, ?, ?)",
                 (task_id, status or "update", result_summary or ""))
    conn.commit()


def list_tasks(conn, status=None, limit=50):
    if status:
        rows = conn.execute(
            "SELECT * FROM tasks WHERE status = ? ORDER BY id DESC LIMIT ?",
            (status, limit)).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM tasks ORDER BY id DESC LIMIT ?",
            (limit,)).fetchall()
    return [dict(r) for r in rows]


def get_summary(conn):
    """Generate a context-recovery summary for CC Lead."""
    counts = {}
    for row in conn.execute("SELECT status, COUNT(*) as cnt FROM tasks GROUP BY status"):
        counts[row["status"]] = row["cnt"]

    recent_done = conn.execute(
        "SELECT id, title, agent, result_summary, completed_at FROM tasks "
        "WHERE status = 'done' ORDER BY completed_at DESC LIMIT 5").fetchall()

    in_progress = conn.execute(
        "SELECT id, title, agent, priority, updated_at FROM tasks "
        "WHERE status = 'in_progress' ORDER BY priority, id").fetchall()

    pending = conn.execute(
        "SELECT id, title, agent, priority FROM tasks "
        "WHERE status = 'pending' ORDER BY priority, id").fetchall()

    failed = conn.execute(
        "SELECT id, title, agent, result_summary FROM tasks "
        "WHERE status = 'failed' ORDER BY id DESC LIMIT 5").fetchall()

    return {
        "generated_at": datetime.now().isoformat(),
        "counts": counts,
        "in_progress": [dict(r) for r in in_progress],
        "pending": [dict(r) for r in pending],
        "recent_done": [dict(r) for r in recent_done],
        "recent_failed": [dict(r) for r in failed],
    }


def get_summary_text(conn):
    """Human-readable summary for CC Lead."""
    s = get_summary(conn)
    lines = []
    lines.append(f"## Task Queue Summary — {s['generated_at'][:16]}")
    lines.append(f"")

    c = s["counts"]
    lines.append(f"Pending: {c.get('pending', 0)} | In Progress: {c.get('in_progress', 0)} | "
                 f"Done: {c.get('done', 0)} | Failed: {c.get('failed', 0)}")
    lines.append(f"")

    if s["in_progress"]:
        lines.append(f"### 🔄 In Progress")
        for t in s["in_progress"]:
            lines.append(f"- [{t['priority']}] #{t['id']} {t['title']} → {t['agent'] or '?'}")

    if s["pending"]:
        lines.append(f"### ⏳ Pending")
        for t in s["pending"]:
            lines.append(f"- [{t['priority']}] #{t['id']} {t['title']} → {t['agent'] or '?'}")

    if s["recent_done"]:
        lines.append(f"### ✅ Recently Done")
        for t in s["recent_done"]:
            summary = (t["result_summary"] or "")[:80]
            lines.append(f"- #{t['id']} {t['title']}: {summary}")

    if s["recent_failed"]:
        lines.append(f"### ❌ Failed")
        for t in s["recent_failed"]:
            summary = (t["result_summary"] or "")[:80]
            lines.append(f"- #{t['id']} {t['title']}: {summary}")

    return "\n".join(lines)


# ============================================================
# HTTP Server
# ============================================================
_db_lock = threading.Lock()


class TaskHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        params = parse_qs(parsed.query)

        if path == "/tasks/health":
            self._json(200, {"status": "ok", "db": str(DB_PATH)})

        elif path == "/tasks/list":
            with _db_lock:
                conn = init_db()
                status = params.get("status", [None])[0]
                tasks = list_tasks(conn, status=status)
                conn.close()
            self._json(200, {"tasks": tasks, "count": len(tasks)})

        elif path == "/tasks/summary":
            with _db_lock:
                conn = init_db()
                summary = get_summary(conn)
                conn.close()
            self._json(200, summary)

        elif path == "/tasks/summary-text":
            with _db_lock:
                conn = init_db()
                text = get_summary_text(conn)
                conn.close()
            self.send_response(200)
            self.send_header("Content-Type", "text/markdown")
            self.end_headers()
            self.wfile.write(text.encode())

        else:
            self._json(404, {"error": "not found"})

    def do_POST(self):
        body = self._read_body()

        if self.path == "/tasks/create":
            title = body.get("title", "")
            if not title:
                self._json(400, {"error": "title required"})
                return
            with _db_lock:
                conn = init_db()
                task_id = create_task(
                    conn,
                    title=title,
                    agent=body.get("agent", ""),
                    priority=body.get("priority", "P1"),
                    objective=body.get("objective", ""),
                    input_path=body.get("input_path", ""),
                    output_path=body.get("output_path", ""),
                    branch=body.get("branch", ""),
                )
                conn.close()
            self._json(201, {"task_id": task_id, "status": "created"})

        elif self.path == "/tasks/update":
            task_id = body.get("task_id")
            if not task_id:
                self._json(400, {"error": "task_id required"})
                return
            with _db_lock:
                conn = init_db()
                update_task(
                    conn,
                    task_id=task_id,
                    status=body.get("status"),
                    result_summary=body.get("result_summary"),
                )
                conn.close()
            self._json(200, {"task_id": task_id, "status": "updated"})

        else:
            self._json(404, {"error": "not found"})

    def _read_body(self):
        length = int(self.headers.get("Content-Length", 0))
        if length > 0:
            return json.loads(self.rfile.read(length))
        return {}

    def _json(self, code, data):
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False, default=str).encode())

    def log_message(self, format, *args):
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {args[0]}")


# ============================================================
# CLI
# ============================================================
def cli_main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--serve", action="store_true", help="Start HTTP server")
    parser.add_argument("--create", help="Create a task (title)")
    parser.add_argument("--agent", default="")
    parser.add_argument("--priority", default="P1")
    parser.add_argument("--update", type=int, help="Update task by ID")
    parser.add_argument("--status", help="New status (for --update) or filter (for --list)")
    parser.add_argument("--result", help="Result summary (for --update)")
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--summary", action="store_true")
    args = parser.parse_args()

    if args.serve:
        server = HTTPServer(("127.0.0.1", PORT), TaskHandler)
        print(f"Task queue server on http://127.0.0.1:{PORT}")
        print(f"  POST /tasks/create     — create task")
        print(f"  POST /tasks/update     — update status")
        print(f"  GET  /tasks/list       — list tasks")
        print(f"  GET  /tasks/summary    — JSON summary")
        print(f"  GET  /tasks/summary-text — markdown summary")
        server.serve_forever()
        return

    conn = init_db()

    if args.create:
        task_id = create_task(conn, args.create, agent=args.agent, priority=args.priority)
        print(f"Created task #{task_id}: {args.create}")

    elif args.update:
        update_task(conn, args.update, status=args.status, result_summary=args.result)
        print(f"Updated task #{args.update}")

    elif args.list:
        tasks = list_tasks(conn, status=args.status)
        for t in tasks:
            print(f"  [{t['priority']}] #{t['id']} {t['status']:12s} {t['title']}")

    elif args.summary:
        print(get_summary_text(conn))

    else:
        print(get_summary_text(conn))

    conn.close()


if __name__ == "__main__":
    cli_main()
