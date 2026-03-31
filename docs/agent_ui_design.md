# Agent Management UI — 技术方案

> 版本：v1.0
> 日期：2026-03-26
> 作者：architect agent

---

## 1. 技术栈选型

### 前端

| 选项 | 决定 | 理由 |
|---|---|---|
| Vite + React + TypeScript | **选用** | 轻量、构建快、生态成熟，不需要 Next.js 的 SSR/路由开销 |
| Next.js | 排除 | 对纯本地工具过重，还带 Node server 层 |
| Vanilla JS | 排除 | xterm.js 用 React 封装更好维护 |

关键前端库：
- **xterm.js** — 终端渲染，业界标准，WebGL 加速，不卡顿
- **xterm-addon-fit** — 终端自适应容器大小
- **xterm-addon-web-links** — 路径可点击
- **@xtermjs/headless** — 不需要
- **Tailwind CSS** — 快速布局，无需自写样式

### 后端

| 选项 | 决定 | 理由 |
|---|---|---|
| Node.js + Express + node-pty | **选用** | node-pty 是最成熟的 pty 桥接方案，和 xterm.js 天然配套 |
| Python + FastAPI + ptyprocess | 排除 | ptyprocess 不如 node-pty 稳定，WebSocket 支持也弱一些 |
| Electron | 排除（需求明确排除） | 太重 |

关键后端库：
- **node-pty** — 创建和管理伪终端（PTY），agent 进程跑在里面
- **ws** — WebSocket server，推送终端流到前端
- **express** — REST API（agent 管理、任务列表）
- **chokidar** — 监听 `.claude/agents/*.md` 变化，热更新 agent 列表
- **better-sqlite3** — 直接读 task_queue.db，比 http 调用 task_queue.py 更低延迟

### 通信架构

```
Browser
  ├── REST  → Express API     (agent 列表、任务列表、start/stop)
  └── WS    → WebSocket Hub   (终端 I/O 流、消息总线事件推送)
```

每个 agent 终端对应一个独立 WebSocket 连接，避免多路复用带来的阻塞。
消息总线事件（任务创建/更新）通过一个独立的 `/ws/events` 频道广播。

### 消息总线

**复用 task_queue.db**，新增一张 `agent_messages` 表。

理由：
- 不引入新的进程/依赖（Redis、ZMQ 等）
- task_queue.py 已在 port 8742 提供 HTTP API，UI 可直接调用
- SQLite WAL 模式支持并发读写，不会阻塞
- 消息量级（几十条/天）完全不需要消息队列

---

## 2. 系统架构图

```
┌─────────────────────────────────────────────────────────────┐
│                        Browser UI                           │
│                                                             │
│  ┌─────────────┐  ┌──────────────────────┐  ┌───────────┐  │
│  │  Sidebar    │  │  Terminal Panel      │  │  Message  │  │
│  │  (agents)   │  │  (xterm.js)          │  │  Feed     │  │
│  │             │  │                      │  │  Panel    │  │
│  │  CC Lead ●  │  │  $ claude code ...   │  │           │  │
│  │  researcher │  │  > 正在分析 L0...    │  │  10:32    │  │
│  │  coder      │  │  > chunk 1/234 done  │  │  CC Lead  │  │
│  │  pipeline.. │  │  _                   │  │  → coder  │  │
│  └─────────────┘  └──────────────────────┘  │  Task #42 │  │
│                                             └───────────┘  │
└──────────┬──────────────────────┬───────────────┬──────────┘
           │ REST                 │ WS/terminal   │ WS/events
           │                      │               │
┌──────────▼──────────────────────▼───────────────▼──────────┐
│                    agent-ui server (Node.js)                │
│                                                             │
│  Express API          WebSocket Hub         PTY Manager     │
│  ─────────────        ─────────────         ────────────    │
│  GET  /agents         /ws/term/:agentId     spawn PTY       │
│  POST /agents/start   /ws/events            resize PTY      │
│  POST /agents/stop                          kill PTY        │
│  GET  /tasks                                                │
│  GET  /tasks/summary                                        │
│                                                             │
│  Agent Registry   ←── chokidar ──── .claude/agents/*.md    │
│                                                             │
│  Message Bus      ←── SQLite  ──── task_queue.db           │
│                         ↑                                   │
│                         │ HTTP                              │
│                  task_queue.py (:8742)                      │
└─────────────────────────────────────────────────────────────┘
                          │
           ┌──────────────┼──────────────┐
           │              │              │
        tmux pane      tmux pane      tmux pane
        CC Lead        researcher     coder
        (PTY1)         (PTY2)         (PTY3)
```

### 数据流

```
用户点击侧边栏 agent
  → REST GET /agents/:id
  → 前端建立 WS 连接 /ws/term/:agentId
  → server 检查该 agent 是否已有 PTY
    ├─ 有：attach 到现有 PTY，回放最后 1000 行历史
    └─ 没有：新建 PTY，在 tmux 对应窗口启动 claude code

用户在终端输入
  → WS message { type: "input", data: "..." }
  → server 写入 PTY stdin
  → PTY stdout → WS message { type: "output", data: "..." }
  → xterm.js render

task_queue.db 变化（新任务/状态更新）
  → chokidar 或 SQLite polling（500ms interval）
  → WebSocket /ws/events 广播
  → 消息流面板追加事件
  → 侧边栏 agent 状态灯更新
```

---

## 3. 核心功能设计

### 3.1 Agent 生命周期管理

```
状态机：
  idle ──start──→ running ──stop──→ idle
                     │
                  waiting（等待用户输入，无终端活动 > 30s）
```

**启动 agent**：
1. 读取 `.claude/agents/<name>.md` 获取 agent 定义
2. 在 tmux session `ce` 中找或新建对应 window
3. 用 node-pty 在该 window 内 spawn shell
4. 注册 PTY 到 `ptyManager` map

**停止 agent**：
1. 发送 SIGTERM 到 PTY 进程
2. 等待 3s，若未退出则 SIGKILL
3. 保留 PTY 最后输出到历史缓冲区

**重启 agent**：stop → 清空缓冲区 → start

**状态检测**：
- running：PTY 进程存在 且 stdout 最近 5s 内有输出
- waiting：PTY 进程存在 但 stdout 超过 30s 无输出
- idle：PTY 进程不存在 或 已退出

### 3.2 终端嵌入和交互

- 每个 agent 终端独立 WebSocket 连接，避免互相阻塞
- 历史缓冲区：内存保存最后 2000 行（用 circular buffer），新建连接时回放
- 终端大小：前端 xterm.js resize 事件 → WS 发送 { type: "resize", cols, rows } → node-pty.resize()
- 输入编码：UTF-8，支持中文输入
- 颜色：xterm.js 默认支持 256 色和 truecolor

### 3.3 Agent 间消息传递和可视化

**消息来源**：
- task_queue.db 的 `tasks` 表（任务创建/更新）
- task_queue.db 的 `task_log` 表（任务日志）
- agent_messages 表（新增，用于 agent 自定义消息）

**消息流时间线**：
- 每条消息显示：时间戳 | 发送方 → 接收方 | 类型（task/result/decision） | 摘要
- 颜色区分类型：蓝色=任务派发，绿色=完成，红色=失败，橙色=等待决策
- 点击消息展开详情（完整 JSON）

**新增 agent_messages 表 schema**：

```sql
CREATE TABLE IF NOT EXISTS agent_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    from_agent TEXT NOT NULL,
    to_agent TEXT NOT NULL,
    message_type TEXT NOT NULL,  -- task | result | decision | info
    title TEXT NOT NULL,
    content TEXT DEFAULT '',     -- JSON or plain text
    task_id INTEGER,             -- 关联 task（可选）
    timestamp TEXT DEFAULT (datetime('now'))
);
```

### 3.4 Agent 状态检测

两种检测机制并行：

1. **PTY 进程检测**：`ptyManager` 维护进程存活状态
2. **活动检测**：记录每个 agent 最后一次 stdout 输出时间
3. **任务状态**：查询 task_queue.db 中 `agent = <name>` 且 `status = 'in_progress'` 的任务数

状态合并逻辑：
```
if (ptyClosed) → idle
else if (lastOutputAge > 30s AND noActiveTask) → waiting
else → running
```

---

## 4. 文件结构

```
agent-ui/
├── package.json
├── tsconfig.json
├── vite.config.ts
├── index.html
│
├── src/
│   ├── server/                     — Node.js 后端
│   │   ├── index.ts                — Express + WS server 入口
│   │   ├── ptyManager.ts           — PTY 生命周期管理
│   │   ├── agentRegistry.ts        — 读取 .claude/agents/*.md，监听变化
│   │   ├── messageBus.ts           — SQLite 读写，事件轮询
│   │   ├── tmuxBridge.ts           — tmux session/window 操作
│   │   └── routes/
│   │       ├── agents.ts           — GET/POST /agents
│   │       └── tasks.ts            — GET /tasks（代理 task_queue.py）
│   │
│   ├── components/                 — React 前端组件
│   │   ├── App.tsx                 — 根组件，三栏布局
│   │   ├── Sidebar/
│   │   │   ├── Sidebar.tsx         — agent 列表
│   │   │   ├── AgentItem.tsx       — 单个 agent 条目 + 状态灯
│   │   │   └── StatusDot.tsx       — 状态指示灯（running/waiting/idle）
│   │   ├── TerminalPanel/
│   │   │   ├── TerminalPanel.tsx   — 终端容器，管理 WS 连接
│   │   │   ├── XtermWrapper.tsx    — xterm.js 封装
│   │   │   └── TerminalToolbar.tsx — 顶部工具栏（重启/清空/复制）
│   │   └── MessageFeed/
│   │       ├── MessageFeed.tsx     — 消息流时间线
│   │       ├── MessageItem.tsx     — 单条消息
│   │       └── MessageDetail.tsx   — 消息详情弹窗
│   │
│   └── lib/                        — 共享工具
│       ├── wsClient.ts             — WebSocket 客户端封装
│       ├── types.ts                — 共享类型定义
│       └── constants.ts            — 端口、路径常量
│
└── scripts/
    └── start.sh                    — 一键启动 server + 打开浏览器
```

---

## 5. 关键代码片段

### 5.1 WebSocket + node-pty 集成（server/ptyManager.ts）

```typescript
import * as pty from 'node-pty';
import { WebSocket, WebSocketServer } from 'ws';

interface PtySession {
  pty: pty.IPty;
  history: string[];       // circular buffer
  lastOutputAt: number;
  clients: Set<WebSocket>;
}

const sessions = new Map<string, PtySession>();
const MAX_HISTORY = 2000;

export function getOrCreateSession(agentId: string, shell = 'zsh'): PtySession {
  if (sessions.has(agentId)) return sessions.get(agentId)!;

  const ptyProcess = pty.spawn(shell, [], {
    name: 'xterm-256color',
    cols: 220,
    rows: 50,
    cwd: process.env.HOME + '/culinary-engine',
    env: { ...process.env },
  });

  const session: PtySession = {
    pty: ptyProcess,
    history: [],
    lastOutputAt: Date.now(),
    clients: new Set(),
  };

  ptyProcess.onData((data) => {
    session.lastOutputAt = Date.now();
    // circular buffer
    session.history.push(data);
    if (session.history.length > MAX_HISTORY) session.history.shift();
    // broadcast to all connected clients
    const msg = JSON.stringify({ type: 'output', data });
    session.clients.forEach((ws) => {
      if (ws.readyState === WebSocket.OPEN) ws.send(msg);
    });
  });

  ptyProcess.onExit(() => {
    sessions.delete(agentId);
    const exitMsg = JSON.stringify({ type: 'exit', agentId });
    session.clients.forEach((ws) => {
      if (ws.readyState === WebSocket.OPEN) ws.send(exitMsg);
    });
  });

  sessions.set(agentId, session);
  return session;
}

export function attachClient(agentId: string, ws: WebSocket) {
  const session = sessions.get(agentId);
  if (!session) {
    ws.send(JSON.stringify({ type: 'error', message: 'agent not running' }));
    return;
  }
  // replay history
  if (session.history.length > 0) {
    ws.send(JSON.stringify({ type: 'history', data: session.history.join('') }));
  }
  session.clients.add(ws);
  ws.on('message', (raw) => {
    const msg = JSON.parse(raw.toString());
    if (msg.type === 'input') session.pty.write(msg.data);
    if (msg.type === 'resize') session.pty.resize(msg.cols, msg.rows);
  });
  ws.on('close', () => session.clients.delete(ws));
}
```

### 5.2 xterm.js 前端组件（components/TerminalPanel/XtermWrapper.tsx）

```tsx
import { useEffect, useRef } from 'react';
import { Terminal } from '@xterm/xterm';
import { FitAddon } from '@xterm/addon-fit';
import '@xterm/xterm/css/xterm.css';

interface Props {
  agentId: string;
  wsUrl: string;
}

export function XtermWrapper({ agentId, wsUrl }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const termRef = useRef<Terminal | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const fitAddon = useRef(new FitAddon());

  useEffect(() => {
    if (!containerRef.current) return;

    const term = new Terminal({
      cursorBlink: true,
      fontFamily: '"JetBrains Mono", "Fira Code", monospace',
      fontSize: 13,
      theme: {
        background: '#0d1117',
        foreground: '#e6edf3',
        cursor: '#58a6ff',
      },
      allowProposedApi: true,
    });

    term.loadAddon(fitAddon.current);
    term.open(containerRef.current);
    fitAddon.current.fit();
    termRef.current = term;

    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => {
      // notify server of initial size
      ws.send(JSON.stringify({ type: 'resize', cols: term.cols, rows: term.rows }));
    };

    ws.onmessage = (e) => {
      const msg = JSON.parse(e.data);
      if (msg.type === 'output' || msg.type === 'history') {
        term.write(msg.data);
      }
    };

    // user input → WS
    term.onData((data) => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: 'input', data }));
      }
    });

    // terminal resize → WS
    const resizeObs = new ResizeObserver(() => {
      fitAddon.current.fit();
      if (ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: 'resize', cols: term.cols, rows: term.rows }));
      }
    });
    resizeObs.observe(containerRef.current);

    return () => {
      resizeObs.disconnect();
      ws.close();
      term.dispose();
    };
  }, [agentId, wsUrl]);

  return <div ref={containerRef} style={{ width: '100%', height: '100%' }} />;
}
```

### 5.3 消息总线 — SQLite polling（server/messageBus.ts）

```typescript
import Database from 'better-sqlite3';
import { EventEmitter } from 'events';
import path from 'path';

const DB_PATH = path.join(process.env.HOME!, 'culinary-engine/data/task_queue.db');

// Ensure agent_messages table exists
function initDb(db: Database.Database) {
  db.exec(`
    CREATE TABLE IF NOT EXISTS agent_messages (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      from_agent TEXT NOT NULL,
      to_agent TEXT NOT NULL,
      message_type TEXT NOT NULL,
      title TEXT NOT NULL,
      content TEXT DEFAULT '',
      task_id INTEGER,
      timestamp TEXT DEFAULT (datetime('now'))
    );
  `);
  // Enable WAL for concurrent reads
  db.pragma('journal_mode = WAL');
}

export class MessageBus extends EventEmitter {
  private db: Database.Database;
  private lastTaskId = 0;
  private lastMsgId = 0;

  constructor() {
    super();
    this.db = new Database(DB_PATH);
    initDb(this.db);
    // seed last known IDs to avoid replaying history on startup
    const lastTask = this.db.prepare('SELECT MAX(id) as id FROM tasks').get() as any;
    const lastMsg = this.db.prepare('SELECT MAX(id) as id FROM agent_messages').get() as any;
    this.lastTaskId = lastTask?.id ?? 0;
    this.lastMsgId = lastMsg?.id ?? 0;
  }

  startPolling(intervalMs = 500) {
    setInterval(() => {
      this.pollTasks();
      this.pollMessages();
    }, intervalMs);
  }

  private pollTasks() {
    const newTasks = this.db
      .prepare('SELECT * FROM task_log WHERE id > ? ORDER BY id')
      .all(this.lastTaskId) as any[];

    for (const row of newTasks) {
      this.emit('task_event', {
        type: 'task_update',
        taskId: row.task_id,
        action: row.action,
        detail: row.detail,
        timestamp: row.timestamp,
      });
      this.lastTaskId = row.id;
    }
  }

  private pollMessages() {
    const newMsgs = this.db
      .prepare('SELECT * FROM agent_messages WHERE id > ? ORDER BY id')
      .all(this.lastMsgId) as any[];

    for (const msg of newMsgs) {
      this.emit('agent_message', msg);
      this.lastMsgId = msg.id;
    }
  }

  postMessage(from: string, to: string, type: string, title: string, content = '', taskId?: number) {
    this.db
      .prepare(
        'INSERT INTO agent_messages (from_agent, to_agent, message_type, title, content, task_id) VALUES (?, ?, ?, ?, ?, ?)'
      )
      .run(from, to, type, title, content, taskId ?? null);
  }

  getRecentMessages(limit = 100) {
    return this.db
      .prepare('SELECT * FROM agent_messages ORDER BY id DESC LIMIT ?')
      .all(limit);
  }
}
```

### 5.4 Agent spawn 逻辑（server/tmuxBridge.ts）

```typescript
import { execSync, exec } from 'child_process';

const TMUX_SESSION = 'ce';

export function ensureTmuxWindow(windowName: string): void {
  try {
    // check if window exists
    execSync(`tmux list-windows -t ${TMUX_SESSION} | grep -q "^.*${windowName}"`, {
      stdio: 'ignore',
    });
  } catch {
    // create window if not exists
    execSync(`tmux new-window -t ${TMUX_SESSION} -n ${windowName}`, { stdio: 'ignore' });
  }
}

export function getWindowPid(windowName: string): number | null {
  try {
    const result = execSync(
      `tmux list-panes -t "${TMUX_SESSION}:${windowName}" -F "#{pane_pid}"`,
      { encoding: 'utf8' }
    );
    return parseInt(result.trim(), 10);
  } catch {
    return null;
  }
}

// agent-ui 选择：不依赖 tmux pane，直接用 node-pty 管理 PTY
// tmuxBridge 仅用于"查看已有 tmux 窗口"，attach 到现有 session 的只读镜像
export function attachToTmuxPane(windowName: string): string {
  // Returns the content of the tmux pane as string (snapshot, not streaming)
  try {
    return execSync(
      `tmux capture-pane -t "${TMUX_SESSION}:${windowName}" -p -e`,
      { encoding: 'utf8' }
    );
  } catch {
    return '';
  }
}
```

### 5.5 WebSocket server 入口片段（server/index.ts）

```typescript
import express from 'express';
import { WebSocketServer } from 'ws';
import http from 'http';
import { getOrCreateSession, attachClient } from './ptyManager';
import { MessageBus } from './messageBus';
import { AgentRegistry } from './agentRegistry';

const app = express();
const server = http.createServer(app);
const wss = new WebSocketServer({ server });
const bus = new MessageBus();
const registry = new AgentRegistry();

app.use(express.json());
app.use(express.static('../dist')); // Vite build output

// REST: agent list
app.get('/api/agents', (req, res) => {
  res.json(registry.getAll());
});

// REST: start agent (creates PTY)
app.post('/api/agents/:id/start', (req, res) => {
  const session = getOrCreateSession(req.params.id);
  res.json({ status: 'started', agentId: req.params.id });
});

// REST: task list (proxy to task_queue or direct DB)
app.get('/api/tasks', (req, res) => {
  // direct SQLite read, no HTTP hop to task_queue.py
  const tasks = bus.getRecentMessages(50);
  res.json(tasks);
});

// WebSocket routing
wss.on('connection', (ws, req) => {
  const url = new URL(req.url!, `http://localhost`);

  if (url.pathname.startsWith('/ws/term/')) {
    const agentId = url.pathname.split('/ws/term/')[1];
    attachClient(agentId, ws);
  }

  if (url.pathname === '/ws/events') {
    // events channel: push task & message updates
    bus.on('task_event', (e) => ws.send(JSON.stringify(e)));
    bus.on('agent_message', (e) => ws.send(JSON.stringify({ type: 'agent_message', ...e })));
    ws.on('close', () => {
      bus.off('task_event', () => {});
      bus.off('agent_message', () => {});
    });
  }
});

bus.startPolling(500);
registry.watch();

server.listen(3131, () => {
  console.log('agent-ui server running at http://localhost:3131');
});
```

---

## 6. 与现有系统集成

### 6.1 读取 .claude/agents/*.md（AgentRegistry）

```typescript
// server/agentRegistry.ts
import { watch } from 'chokidar';
import { readFileSync, readdirSync } from 'fs';
import matter from 'gray-matter'; // npm i gray-matter
import path from 'path';

const AGENTS_DIR = path.join(process.env.HOME!, 'culinary-engine/.claude/agents');

export interface AgentDef {
  id: string;           // 文件名（无 .md）
  name: string;         // frontmatter.name
  description: string;  // frontmatter.description
  model: string;        // frontmatter.model
  tools: string[];      // frontmatter.tools
  systemPrompt: string; // body（frontmatter 之后的正文）
}

export class AgentRegistry {
  private agents = new Map<string, AgentDef>();

  constructor() {
    this.loadAll();
  }

  private loadAll() {
    const files = readdirSync(AGENTS_DIR).filter((f) => f.endsWith('.md'));
    for (const file of files) {
      this.loadFile(path.join(AGENTS_DIR, file));
    }
  }

  private loadFile(filePath: string) {
    const raw = readFileSync(filePath, 'utf8');
    const { data, content } = matter(raw);
    const id = path.basename(filePath, '.md');
    this.agents.set(id, {
      id,
      name: data.name ?? id,
      description: data.description ?? '',
      model: data.model ?? 'sonnet',
      tools: data.tools ?? [],
      systemPrompt: content.trim(),
    });
  }

  watch() {
    watch(AGENTS_DIR, { persistent: true }).on('change', (p) => this.loadFile(p));
  }

  getAll(): AgentDef[] {
    return Array.from(this.agents.values());
  }

  get(id: string): AgentDef | undefined {
    return this.agents.get(id);
  }
}
```

### 6.2 与 task_queue.py 集成

两种方式，优先方式 A：

**方式 A（推荐）：直接读 SQLite**
- agent-ui server 用 better-sqlite3 直连 `task_queue.db`
- 不需要 task_queue.py 在线
- WAL 模式下读写互不阻塞
- 读取 `tasks`、`task_log`、`agent_messages` 三张表

**方式 B：HTTP proxy**
- agent-ui server 作为 proxy 转发到 `http://localhost:8742`
- 适合需要写入（创建任务）的场景
- `POST /api/tasks` → `POST http://localhost:8742/tasks/create`

实际建议：读用方式 A（直接 SQLite），写用方式 B（HTTP API），保持 task_queue.py 作为写入权威。

### 6.3 与 orchestrator.py 集成

orchestrator.py 已经在轮询 task_queue.db 的 `tasks` 表。集成点：

1. **agent 状态同步**：orchestrator 在派发任务时更新 `tasks.status = 'in_progress'`，agent-ui 通过 messageBus 轮询反映到侧边栏状态灯
2. **任务创建**：UI 可以让用户直接在界面创建任务（发到 task_queue.py），orchestrator 自动捡起执行
3. **日志查看**：orchestrator 输出到 `~/culinary-engine/reports/orchestrator.log`，UI 可以新建一个只读 "orchestrator" pseudo-agent，把日志文件 tail 到终端面板
4. **tmux window 对应**：orchestrator 用 `TMUX_SESSION = "ce"` + window name 管理 agent 进程，agent-ui 读 `tmux list-windows -t ce` 同步已有窗口

---

## 7. 工作量估算

### MVP（核心功能，可用）— 3-4 天

| 功能 | 时间 |
|---|---|
| Node.js server 脚手架（Express + WS） | 0.5 天 |
| node-pty + PTY 管理 | 1 天 |
| Vite + React 三栏布局 + xterm.js | 1 天 |
| AgentRegistry（读 .claude/agents/*.md） | 0.5 天 |
| MessageBus（SQLite polling + WS 广播） | 0.5 天 |
| 联调 + 启动脚本 | 0.5 天 |

MVP 包含：
- 侧边栏 agent 列表（从 .md 文件读取）
- 点击 agent 打开终端（xterm.js + node-pty）
- 终端可交互（输入、resize）
- 基本状态灯（running/idle，基于 PTY 进程存活）
- 消息流面板显示 task_log 事件

MVP 不包含：
- agent 状态的精细检测（waiting 状态）
- 消息详情弹窗
- tmux 窗口同步
- orchestrator.log 面板

### 完整版（polish 完成）— 再加 2-3 天

| 功能 | 时间 |
|---|---|
| 精细状态检测（waiting 逻辑） | 0.5 天 |
| 消息详情弹窗 + 过滤 | 0.5 天 |
| tmux 窗口同步 | 0.5 天 |
| orchestrator.log tail 面板 | 0.5 天 |
| 任务创建 UI（发到 task_queue.py） | 0.5 天 |
| 样式 polish + 响应式 | 0.5 天 |

---

## 8. 约束汇总

| 约束 | 方案 |
|---|---|
| 不用 Electron | 纯 Node.js server + 浏览器 UI，HTTP/WS 通信 |
| Vite + React 优先 | 前端用 Vite，Next.js 不引入 |
| 终端不能卡顿 | 每个 agent 独立 WS 连接，xterm.js WebGL renderer |
| 消息总线用现有 DB | 复用 task_queue.db，新增 agent_messages 表 |
| 本地运行 | server 监听 localhost:3131，无云依赖 |
| 不破坏现有系统 | task_queue.db 只增不改，task_queue.py 仍可独立运行 |

---

## 9. 第一步：给 coder agent 的 MVP 实现指令

```
Task: agent-ui MVP — Node.js + xterm.js agent 管理界面

Agent: coder
Priority: P1
Branch: agent/agent-ui-mvp
Objective: 实现一个本地浏览器 UI，能查看所有 claude code agent、点击打开可交互终端、查看任务消息流

Context:
- 代码仓库：~/culinary-engine
- target 目录：~/culinary-engine/agent-ui/
- 现有基础设施：
  - task_queue.db 在 ~/culinary-engine/data/task_queue.db（SQLite）
  - agent 定义在 ~/culinary-engine/.claude/agents/*.md（frontmatter 格式）
  - tmux session "ce" 管理 agent 进程
  - task_queue.py HTTP API 在 port 8742
- 架构方案：~/culinary-engine/docs/agent_ui_design.md

Files to create:
  ~/culinary-engine/agent-ui/package.json
  ~/culinary-engine/agent-ui/tsconfig.json
  ~/culinary-engine/agent-ui/vite.config.ts
  ~/culinary-engine/agent-ui/index.html
  ~/culinary-engine/agent-ui/src/server/index.ts
  ~/culinary-engine/agent-ui/src/server/ptyManager.ts
  ~/culinary-engine/agent-ui/src/server/agentRegistry.ts
  ~/culinary-engine/agent-ui/src/server/messageBus.ts
  ~/culinary-engine/agent-ui/src/components/App.tsx
  ~/culinary-engine/agent-ui/src/components/Sidebar/Sidebar.tsx
  ~/culinary-engine/agent-ui/src/components/Sidebar/AgentItem.tsx
  ~/culinary-engine/agent-ui/src/components/TerminalPanel/XtermWrapper.tsx
  ~/culinary-engine/agent-ui/src/components/MessageFeed/MessageFeed.tsx
  ~/culinary-engine/agent-ui/src/lib/types.ts
  ~/culinary-engine/agent-ui/scripts/start.sh

Requirements:
1. package.json 依赖：
   - 后端：express, ws, node-pty, better-sqlite3, gray-matter, chokidar, tsx（dev runner）
   - 前端：react, react-dom, @xterm/xterm, @xterm/addon-fit, tailwindcss
   - TypeScript: typescript, @types/node, @types/react, @types/express, @types/ws
   - 构建：vite, @vitejs/plugin-react

2. 后端 server（port 3131）：
   - Express + WebSocketServer on 同一 http.Server
   - GET /api/agents — 读 .claude/agents/*.md，解析 frontmatter，返回 agent 列表
   - POST /api/agents/:id/start — 启动 PTY session（zsh）
   - POST /api/agents/:id/stop — kill PTY
   - GET /api/tasks — 直接查询 task_queue.db 的 task_log，返回最近 100 条
   - WS /ws/term/:agentId — PTY I/O 流（见代码片段）
   - WS /ws/events — task_log + agent_messages 变化广播（500ms polling）
   - 静态文件：serve ../dist（Vite 构建产物）

3. PTY 管理（ptyManager.ts）：
   - 使用文档中的代码片段
   - history circular buffer：最近 2000 行
   - 新 WS 连接时回放 history
   - onData → 广播到所有 clients
   - onExit → 从 sessions map 删除，广播 exit 事件

4. AgentRegistry（agentRegistry.ts）：
   - 使用 gray-matter 解析 frontmatter
   - 读 ~/culinary-engine/.claude/agents/*.md
   - chokidar 监听变化，热更新
   - 返回 { id, name, description, model, tools }

5. MessageBus（messageBus.ts）：
   - better-sqlite3 直连 task_queue.db
   - WAL pragma
   - 创建 agent_messages 表（如不存在）
   - 每 500ms poll task_log 和 agent_messages 的新行
   - 用 EventEmitter 广播变化

6. 前端三栏布局（App.tsx）：
   - 左侧栏（240px 固定）：agent 列表
   - 主面板（flex-1）：终端
   - 右侧栏（320px 固定）：消息流
   - Tailwind CSS，深色主题（bg-gray-950）

7. Sidebar（Sidebar.tsx + AgentItem.tsx）：
   - 列出所有 agent（从 GET /api/agents）
   - 每个 agent 显示：名字、model badge、状态灯
   - 状态灯颜色：green=running, yellow=waiting, gray=idle
   - 点击 agent → 选中，触发 TerminalPanel 切换
   - 状态通过 WS /ws/events 实时更新

8. XtermWrapper（XtermWrapper.tsx）：
   - 使用文档中的代码片段
   - 连接 /ws/term/:agentId
   - 深色主题，monospace 字体
   - ResizeObserver → fitAddon → ws resize 消息
   - 切换 agent 时 unmount/remount，新建 WS 连接

9. MessageFeed（MessageFeed.tsx）：
   - 连接 /ws/events
   - 显示 task_log 事件：时间 | action | detail（截断 60 chars）
   - 颜色：created=blue, in_progress=yellow, done=green, failed=red
   - 自动滚动到底部
   - 最多显示 200 条，超出截头

10. start.sh：
    - cd ~/culinary-engine/agent-ui
    - npm run build（前端）
    - node dist-server/index.js（或 tsx src/server/index.ts）
    - 打印 http://localhost:3131
    - 用 open 打开浏览器

Constraints:
- 不改 STATUS.md / HANDOFF.md
- 不改任何现有脚本
- task_queue.db 只读（agent-ui server 不写 tasks 表，只写 agent_messages 表）
- server 只监听 127.0.0.1，不对外暴露
- 所有 HTTP 客户端 trust_env=False（本机有代理，不需要，但 node 不受影响，可忽略）
- node-pty 需要 native module，确保 package.json 有正确的 install script

Success Criteria:
- npm install && npm run build && node ... 无报错启动
- 浏览器打开 http://localhost:3131 能看到三栏 UI
- 侧边栏显示 .claude/agents/*.md 中的所有 agent
- 点击任意 agent，主面板出现可交互终端（能输入 ls 看到输出）
- 消息流面板显示 task_log 中的历史事件
```

---

## 附录：端口规划

| 服务 | 端口 |
|---|---|
| task_queue.py | 8742 |
| agent-ui server | 3131 |
| Dify | 80 |
| orchestrator | 无端口（进程） |
