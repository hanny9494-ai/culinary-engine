# 多Agent协作规范

## 角色

| 角色 | 运行环境 | 职责 |
|------|---------|------|
| **母对话 (Opus 4.6)** | Claude.ai | 架构决策、任务拆分、PR审核、STATUS.md维护 |
| **Agent A-D (Codex/CC)** | Codex / Claude Code | 执行具体编码任务，只在自己分支工作 |

## Git 分支模型

```
main (protected — 不允许直接push)
  │
  ├── agent/stage1-cli        ← Agent A 独占
  ├── agent/stage2-match      ← Agent B 独占
  ├── agent/stage3-refactor   ← Agent C 独占
  └── agent/orchestrator      ← Agent D 独占（等A/B/C合并后再开）
```

## 规则

### 1. 分支隔离
- 每个agent只在 `agent/<task-name>` 分支工作
- **绝对不允许**直接push到main
- **绝对不允许**修改其他agent负责的文件

### 2. 文件所有权
每个agent的工单明确列出：
- ✅ **你负责的文件**（只能改这些）
- 🚫 **你不许碰的文件**（改了PR会被打回）

### 3. 合并流程
```
Agent完成 → push到自己分支 → 告诉Jeff "分支xxx已完成"
    ↓
Jeff把分支链接发给母对话 → 母对话review代码
    ↓
母对话确认OK → Jeff在GitHub merge PR到main
    ↓
如果有后续agent依赖 → 后续agent从main拉取最新代码
```

### 4. 冲突预防
- 共享文件（STATUS.md, README.md）**只有母对话能改**
- config/ 目录的文件由创建它的agent负责，其他agent只读
- scripts/utils/ 下的工具函数如果多agent都需要，由第一个创建的agent负责，其他agent import

### 5. Agent启动模板

每个Codex子对话开头粘贴：

```
## 项目上下文
git clone https://github.com/hanny9494-ai/culinary-engine.git
cd culinary-engine
git checkout -b agent/<your-task-name>

先读取项目状态：cat STATUS.md

## 你的任务
[具体工单内容]

## 你的文件边界
✅ 允许修改: [文件列表]
🚫 不许修改: [文件列表]

## 完成标准
1. 所有脚本可以 python3 script.py --help 正常运行
2. 有对应的 skills/SKILL_xxx.md 文档
3. git push origin agent/<your-task-name>
4. 告诉Jeff "分支 agent/<task> 已完成，可以review"
```

## Agent间依赖管理

```
T1 (Stage1 CLI化) ──────────────────┐
T2 (Stage2 新建)  ──────────────────┤──→ T4 (总编排)
T3 (Stage3 重构 + Stage3B整合) ─────┘
```

- T1/T2/T3 **完全并行**，无互相依赖
- T4 **必须等** T1+T2+T3 全部merge到main后再开
- 如果T4开工时main上代码有接口不一致，T4负责修复

## 紧急修复

如果某个agent的代码有bug需要紧急修复：
1. 开一个 `hotfix/<description>` 分支
2. 修复后PR到main
3. 通知其他正在工作的agent: `git pull origin main --rebase`
