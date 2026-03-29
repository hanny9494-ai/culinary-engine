# Mission Control × Culinary Engine 集成方案

> 作者：架构师 agent
> 日期：2026-03-26
> 目标：1-2 天内让 MC 有可用的 agent 协作能力，不追求完美

---

## 现状评估

### MC 已具备（无需改动）
- `GET/POST /api/tasks` — 完整的 tasks CRUD，支持 assigned_to、priority、status、metadata
- `GET /api/agents/comms` — 读 messages 表，conversation_id 匹配 `a2a:*`、`coord:*`、`session:*`
- `GET /api/memory` — 读文件系统，由 `OPENCLAW_MEMORY_DIR` 环境变量控制路径
- `src/lib/claude-sessions.ts` — 自动扫描 `~/.claude/projects/` 的 JSONL，由 `MC_CLAUDE_HOME` 控制

### 需要桥接的缺口
| 缺口 | 严重性 | 工作量 |
|------|--------|--------|
| task_queue.db (port 8742) 与 MC tasks 表不通 | 高 | 低（Python 脚本） |
| Agent comms 面板没有实际数据 | 中 | 低（直写 messages 表） |
| Memory Browser 指向错误目录 | 高 | 极低（改 .env） |
| Session 面板需要 MC_CLAUDE_HOME 配置 | 低 | 极低（改 .env） |
| Chat 功能需要 OpenClaw | 低 | 等 Mac Mini |

---

## 方案一：任务同步（task_queue.db → MC tasks）

### 推荐：同步脚本方案（而非双写）

**理由：** task_queue.py 是 Python 写的简单 HTTP server，修改它引入对 MC SQLite 的依赖会打破关注分离，出错时两个 DB 会不一致。同步脚本更安全，故障隔离好。

### 实现：`scripts/mc_task_sync.py`

```python
#!/usr/bin/env python3
"""
mc_task_sync.py — 把 task_queue.db 的任务单向同步到 Mission Control

运行方式：
  python3 scripts/mc_task_sync.py          # 一次性同步
  python3 scripts/mc_task_sync.py --watch  # 每 30 秒轮询
"""

import sqlite3
import json
import time
import argparse
from pathlib import Path
from datetime import datetime

TASK_QUEUE_DB = Path.home() / "culinary-engine/data/task_queue.db"
MC_DB = Path.home() / "mission-control/.data/mission-control.db"
WORKSPACE_ID = 1  # MC 默认 workspace

# task_queue.db status → MC task status 映射
STATUS_MAP = {
    "pending":     "inbox",
    "in_progress": "in_progress",
    "done":        "done",
    "failed":      "review",   # 失败的任务放 review 列，让人工处理
    "blocked":     "inbox",
}

PRIORITY_MAP = {
    "P0": "urgent",
    "P1": "high",
    "P2": "medium",
    "P3": "low",
}

def get_or_create_project(mc_conn):
    """确保 culinary-engine project 存在，返回 project_id"""
    row = mc_conn.execute(
        "SELECT id FROM projects WHERE slug = 'culinary-engine' AND workspace_id = ?",
        (WORKSPACE_ID,)
    ).fetchone()
    if row:
        return row[0]
    # 创建 project
    cur = mc_conn.execute(
        """INSERT INTO projects (name, slug, description, status, ticket_prefix, ticket_counter, workspace_id)
           VALUES ('Culinary Engine', 'culinary-engine', 'L0 知识引擎 pipeline 任务', 'active', 'CE', 0, ?)""",
        (WORKSPACE_ID,)
    )
    mc_conn.commit()
    return cur.lastrowid

def sync_tasks():
    tq = sqlite3.connect(str(TASK_QUEUE_DB))
    tq.row_factory = sqlite3.Row
    mc = sqlite3.connect(str(MC_DB))
    mc.row_factory = sqlite3.Row

    project_id = get_or_create_project(mc)

    tq_tasks = tq.execute(
        "SELECT * FROM tasks ORDER BY id DESC LIMIT 200"
    ).fetchall()

    synced = 0
    updated = 0

    for t in tq_tasks:
        mc_status = STATUS_MAP.get(t["status"], "inbox")
        mc_priority = PRIORITY_MAP.get(t["priority"], "medium")

        # 用 metadata.source_task_id 做幂等键
        existing = mc.execute(
            """SELECT id, status FROM tasks
               WHERE workspace_id = ? AND json_extract(metadata, '$.source_task_id') = ?""",
            (WORKSPACE_ID, t["id"])
        ).fetchone()

        metadata = json.dumps({
            "source": "task_queue",
            "source_task_id": t["id"],
            "agent": t["agent"],
            "branch": t["branch"],
            "input_path": t["input_path"],
            "output_path": t["output_path"],
        })

        now = int(time.time())

        if existing:
            # 仅在 status 变化时更新（避免刷新 updated_at 时间戳）
            if existing["status"] != mc_status:
                mc.execute(
                    "UPDATE tasks SET status = ?, updated_at = ?, metadata = ? WHERE id = ?",
                    (mc_status, now, metadata, existing["id"])
                )
                updated += 1
        else:
            # 新建
            mc.execute(
                """INSERT INTO tasks
                   (title, description, status, priority, assigned_to, created_by,
                    project_id, created_at, updated_at, tags, metadata, workspace_id)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    t["title"],
                    t.get("objective") or t["title"],
                    mc_status,
                    mc_priority,
                    t["agent"] or None,   # assigned_to = agent 名
                    "task_queue_sync",
                    project_id,
                    now,
                    now,
                    json.dumps(["pipeline", t["agent"]] if t["agent"] else ["pipeline"]),
                    metadata,
                    WORKSPACE_ID,
                )
            )
            synced += 1

    mc.commit()
    tq.close()
    mc.close()
    print(f"[{datetime.now():%H:%M:%S}] 同步完成: {synced} 新建, {updated} 更新")
    return synced + updated

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--watch", action="store_true", help="每 30 秒轮询")
    parser.add_argument("--interval", type=int, default=30)
    args = parser.parse_args()

    if args.watch:
        print(f"开始监听 task_queue.db，每 {args.interval} 秒同步一次...")
        while True:
            try:
                sync_tasks()
            except Exception as e:
                print(f"同步失败: {e}")
            time.sleep(args.interval)
    else:
        sync_tasks()

if __name__ == "__main__":
    main()
```

### 启动方式

```bash
# 一次性同步（测试用）
python3 ~/culinary-engine/scripts/mc_task_sync.py

# 后台持续运行（tmux）
tmux new-window -n mc-sync
python3 ~/culinary-engine/scripts/mc_task_sync.py --watch --interval 30
```

### 注意事项
- 同步是**单向的**（task_queue → MC），MC 里不要手动改这些任务的 status
- 同步脚本直接写 MC 的 SQLite，绕过 MC 的 API（避免认证复杂性），可行因为 MC 用 WAL 模式，并发安全
- 如果以后想双向，改 task_queue.py 的 `update_task()` 加一个 `requests.post` 调用 MC API 即可

---

## 方案二：Agent 间通信（不依赖 OpenClaw）

### 三个方案比较

| | 方案 A：HTTP Bridge | 方案 B：直写 messages 表 | 方案 C：等 OpenClaw |
|---|---|---|---|
| 实现时间 | 1-2 天 | 2 小时 | 未知 |
| 真实执行 | 是（触发 claude --agent） | 否（仅记录） | 是 |
| 双向通信 | 是 | 单向写入 | 是 |
| 风险 | claude CLI 并发/session 管理 | 无 | 依赖外部 |

### 推荐：**方案 B + 方案 A 分两阶段**

**第一步（今天）：方案 B** — 让 Agent Comms 面板有数据，CC Lead 派任务的动作可视化
**第二步（有需要时）：方案 A** — 真正驱动 agent 执行

#### 方案 B 实现：`scripts/mc_comms_bridge.py`

MC 的 comms 面板读 messages 表，过滤条件是 `conversation_id LIKE 'a2a:%'` 或 `coord:%`。
只需往 MC DB 的 messages 表写记录。

```python
#!/usr/bin/env python3
"""
mc_comms_bridge.py — 把 CC Lead 的任务派发动作写入 MC messages 表，
让 Agent Comms 面板能看到 inter-agent 通信流。

用法：
  python3 scripts/mc_comms_bridge.py send --from cc-lead --to pipeline-runner \
    --message "Task #52: Stage1 phoenix_claws" --task-id 52

  python3 scripts/mc_comms_bridge.py sync  # 把现有 task_log 导入 messages
"""

import sqlite3
import json
import time
import argparse
from pathlib import Path
from datetime import datetime

MC_DB = Path.home() / "mission-control/.data/mission-control.db"
TASK_QUEUE_DB = Path.home() / "culinary-engine/data/task_queue.db"
WORKSPACE_ID = 1

def send_message(from_agent: str, to_agent: str, content: str,
                 task_id: int = None, msg_type: str = "task_dispatch"):
    """写一条 agent-to-agent 消息到 MC messages 表"""
    mc = sqlite3.connect(str(MC_DB))
    conv_id = f"a2a:{from_agent}->{to_agent}"
    metadata = json.dumps({
        "channel": "coordinator-inbox",
        "task_id": task_id,
        "dispatched_by": "cc-lead",
    })
    mc.execute(
        """INSERT INTO messages
           (conversation_id, from_agent, to_agent, content, message_type, metadata, workspace_id)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (conv_id, from_agent, to_agent, content, msg_type, metadata, WORKSPACE_ID)
    )
    mc.commit()
    mc.close()
    print(f"[{from_agent}] → [{to_agent}]: {content[:80]}")

def sync_task_log():
    """把 task_queue 的 task_log 导入 MC messages（一次性历史回填）"""
    tq = sqlite3.connect(str(TASK_QUEUE_DB))
    tq.row_factory = sqlite3.Row

    mc = sqlite3.connect(str(MC_DB))

    # 获取 task 详情
    tasks = {r["id"]: dict(r) for r in tq.execute("SELECT * FROM tasks").fetchall()}
    logs = tq.execute("SELECT * FROM task_log ORDER BY id").fetchall()

    inserted = 0
    for log in logs:
        t = tasks.get(log["task_id"])
        if not t:
            continue
        agent = t.get("agent") or "pipeline-runner"
        content = f"[{log['action'].upper()}] Task #{log['task_id']}: {t['title']}"
        if log["detail"]:
            content += f"\n{log['detail']}"

        conv_id = f"coord:cc-lead->{agent}"
        metadata = json.dumps({
            "source": "task_log_import",
            "task_id": log["task_id"],
            "action": log["action"],
        })

        mc.execute(
            """INSERT OR IGNORE INTO messages
               (conversation_id, from_agent, to_agent, content, message_type, metadata, workspace_id)
               VALUES (?, ?, ?, ?, 'task_event', ?, ?)""",
            (conv_id, "cc-lead", agent, content, metadata, WORKSPACE_ID)
        )
        inserted += 1

    mc.commit()
    mc.close()
    tq.close()
    print(f"导入 {inserted} 条历史通信记录")

def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd")

    send_p = sub.add_parser("send")
    send_p.add_argument("--from", dest="from_agent", required=True)
    send_p.add_argument("--to", dest="to_agent", required=True)
    send_p.add_argument("--message", required=True)
    send_p.add_argument("--task-id", type=int)

    sub.add_parser("sync")

    args = parser.parse_args()
    if args.cmd == "send":
        send_message(args.from_agent, args.to_agent, args.message, args.task_id)
    elif args.cmd == "sync":
        sync_task_log()
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
```

#### 方案 A 草图（第二步，有需要时实现）

```
CC Lead 在 MC UI 点"派任务"
  → POST /api/agents/message  (MC 新增 route)
  → bridge.py 收到请求
  → subprocess.run(["claude", "--agent", "pipeline-runner", prompt])
  → bridge 监听 stdout，分批写回 MC messages 表
  → MC comms 面板实时刷新
```

这需要 claude CLI 支持 `--agent` 参数或等价的 non-interactive 模式。先用方案 B 解锁可视化，再根据实际需求决定是否实现 A。

---

## 方案三：Memory 对接

### 结论：改一行 .env，立即生效

MC 的 memory 系统完全由文件路径驱动。`OPENCLAW_MEMORY_DIR` 这个环境变量直接控制 Memory Browser 读哪个目录。

**MC 当前行为：**
- 未设置 `OPENCLAW_MEMORY_DIR` → 读 `~/.openclaw/memory/`（不存在，面板空白）
- Claude Code memory 在 `~/.claude/projects/` 下（格式完全兼容，都是 `.md` 文件）

**修改 `/Users/jeff/mission-control/.env`：**

```bash
# 在 .env 里加这一行：
OPENCLAW_MEMORY_DIR=/Users/jeff/.claude/projects
```

这样 Memory Browser 会展示所有 Claude Code project 的 memory 目录，包括：
- `-Users-jeff-culinary-engine/memory/` (17 个文件)
- `-Users-jeff-l0-knowledge-engine/memory/` (MEMORY.md 等)

**格式兼容性：** MC memory API 读取任意 `.md` 文件，支持 tree 浏览、内容查看、全文搜索（FTS5）、wiki-link 提取。Claude Code 的 memory 文件都是 Markdown，完全兼容，无需转换。

**重启 MC 后生效：**
```bash
cd ~/mission-control && npm run dev
# 或如果是 pm2:
pm2 restart mission-control
```

### 可选：细粒度控制

如果只想展示 culinary-engine 的 memory（不展示所有 project）：
```bash
OPENCLAW_MEMORY_DIR=/Users/jeff/.claude/projects/-Users-jeff-culinary-engine/memory
```

---

## 方案四：Session 可视化

### 结论：已开箱即用，仅需确认 MC_CLAUDE_HOME

`src/lib/claude-sessions.ts` 扫描 `config.claudeHome`（默认 `~/.claude`），自动发现所有 project 的 JSONL session。

**检查当前 .env：**
```bash
grep MC_CLAUDE_HOME ~/mission-control/.env
# 如果没有这行，MC 已经用默认值 ~/.claude（正确）
```

**无需额外配置**，前提是 session 文件存在：
```
~/.claude/projects/-Users-jeff-culinary-engine/*.jsonl
~/.claude/projects/-Users-jeff-l0-knowledge-engine/*.jsonl
```

**Session 面板显示条件：**
- Session 最后活动时间在 90 分钟内 → 显示为"active"
- 超过 90 分钟 → 显示为历史 session（仍可查看）

**活跃 session 检测原理：** 读 JSONL 最后一行的 timestamp，与当前时间对比。只要你在用 claude code，session 就会出现。

---

## 方案五：实施优先级

### 第一档：今天，配置就行（0 代码）

| 操作 | 预计时间 | 收益 |
|------|---------|------|
| 在 `.env` 加 `OPENCLAW_MEMORY_DIR` | 2 分钟 | Memory Browser 立即展示 17 个 culinary memory 文件 |
| 重启 MC | 30 秒 | Session 面板同时激活 |
| 运行 `mc_task_sync.py` 一次 | 5 分钟 | Task Board 出现 50 条 pipeline 历史任务 |

### 第二档：今天，写脚本（约 2 小时）

| 任务 | 文件位置 | 收益 |
|------|---------|------|
| 创建 `mc_task_sync.py` | `~/culinary-engine/scripts/mc_task_sync.py` | Task Board 持续同步，任务状态实时更新 |
| 创建 `mc_comms_bridge.py` | `~/culinary-engine/scripts/mc_comms_bridge.py` | Agent Comms 面板有历史数据，CC Lead 派任务可记录 |
| 把 task_log 历史导入 MC | `mc_comms_bridge.py sync` | Comms 面板立即有内容 |

### 第三档：本周，有需要时

| 任务 | 依赖 | 收益 |
|------|------|------|
| 在 tmux 里挂起 mc_task_sync --watch | 第二档完成 | 全自动实时同步 |
| 封装 `mc_dispatch` 函数到 CC Lead workflow | 第二档完成 | 每次派任务自动记录到 MC comms |

### 第四档：等 OpenClaw（Mac Mini 就绪后）

| 任务 | 依赖 |
|------|------|
| 真实 chat（MC UI → OpenClaw → claude CLI） | OpenClaw 安装 + Mac Mini SSH tunnel |
| WebSocket 实时通信 | OpenClaw Gateway |
| agent 心跳和状态更新 | OpenClaw |

---

## 关键技术决策记录

### 决策 A：同步脚本 vs 双写
- **选择：** 同步脚本（单向，定期轮询）
- **理由：** task_queue.py 保持纯粹，同步失败不影响主流程，两个 DB 独立可查

### 决策 B：直写 MC DB vs 调用 MC API
- **选择：** 直写 SQLite（同步脚本），调用 API（comms bridge）
- **理由：** 同步脚本本地跑，直写更简单；comms bridge 写 messages 可以用 INSERT，都行
- **实际上两种都 OK**，SQLite WAL 模式下并发安全

### 决策 C：方案 B（直写 messages）vs 方案 A（HTTP bridge）
- **选择：** 先 B 后 A
- **理由：** B 是 2 小时的事，A 需要研究 claude CLI 的 non-interactive 模式。先让面板有数据，再做真正的执行驱动

---

## 完整操作清单（今天能做的）

```bash
# 1. 改 MC .env
echo 'OPENCLAW_MEMORY_DIR=/Users/jeff/.claude/projects' >> ~/mission-control/.env

# 2. 重启 MC（根据实际启动方式选一个）
cd ~/mission-control && pm2 restart mission-control
# 或: kill $(lsof -ti:3333) && npm run dev

# 3. 创建并运行同步脚本（代码见方案一）
# 先手动写 ~/culinary-engine/scripts/mc_task_sync.py
python3 ~/culinary-engine/scripts/mc_task_sync.py

# 4. 创建并运行 comms bridge（代码见方案二）
# 先手动写 ~/culinary-engine/scripts/mc_comms_bridge.py
python3 ~/culinary-engine/scripts/mc_comms_bridge.py sync

# 5. 验证
open http://localhost:3333
# 检查：Memory Browser 有没有 culinary-engine 文件夹
# 检查：Task Board 有没有 CE-XXX 任务
# 检查：Agent Comms 有没有 cc-lead → pipeline-runner 消息流
```

---

## 预期效果（1-2 天后）

- Memory Browser：展示 `~/.claude/projects/` 下的 17 个 culinary memory 文件，可以搜索、查看、编辑
- Task Board：50 条 pipeline 历史任务可见，每 30 秒自动更新状态
- Agent Comms：历史任务派发记录可视化，图谱显示 cc-lead ↔ pipeline-runner 通信
- Session 面板：当前活跃的 claude code session 自动出现
- Chat：空白（等 OpenClaw）— 不影响上面四个功能的使用
