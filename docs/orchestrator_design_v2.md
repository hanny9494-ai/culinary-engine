# Orchestrator v2 设计文档

> 给 coder agent 的工单。重写 scripts/dify/orchestrator.py 并 commit+push。

## 1. 文件位置

- 目标文件：`scripts/dify/orchestrator.py`
- 当前版本：398 行，旧版（无 tmux、无并行、无 report、无 auto-fix）
- launchd plist：`~/Library/LaunchAgents/com.culinary-engine.orchestrator.plist`
- Task Queue DB：`~/culinary-engine/data/task_queue.db`

## 2. 架构概览

```
Orchestrator (launchd 守护, 每60s轮询)
│
├── Phase 0: Dify KB 定期同步 (每10轮)
├── Phase 1: Poll open PRs (代码任务)
├── Phase 2: 清理已完成线程
├── Phase 3: 派发 pending 任务
│   ├── 数据任务 → 线程池并行，Codex 在 tmux 窗口执行
│   │   ├── stage4 → opus_api slot (×3并发)
│   │   ├── stage1 → ollama slot (×1串行)
│   │   ├── stage1_step5 → ollama slot (×1串行)
│   │   ├── ocr_stage1 → flash_api slot (×3并发)
│   │   └── ocr → flash_api slot (×3并发)
│   └── 代码任务 → 建分支 → Codex → PR → Jeff review merge
│
└── 完成后：读 report → learnings → auto-fix → Dify sync
```

## 3. 关键常量

```python
DB_PATH = Path.home() / "culinary-engine" / "data" / "task_queue.db"
CE_DIR = Path.home() / "culinary-engine"
L0_OUTPUT = Path.home() / "culinary-engine" / "output"
LOG_DIR = Path.home() / "culinary-engine" / "reports"
GH_BIN = "/opt/homebrew/bin/gh"
TMUX_SESSION = "ce"
REPORT_DIR = LOG_DIR / "task_reports"
LEARNINGS_PATH = LOG_DIR / "learnings.jsonl"
FIX_LOG_PATH = LOG_DIR / "auto_fixes.jsonl"

# Dify KB
DIFY_DATASET_KEY = "dataset-DqAtoTYJUES69kEUF7bFBs25"
DIFY_DATASET_ID = "65b3d570-7a71-4a8c-bcc4-b377c635d1d8"
DIFY_URL = "http://localhost"
```

## 4. 任务类型检测（顺序敏感）

```python
TASK_PATTERNS = [
    ("stage4",      re.compile(r"stage4[:\s]", re.I)),
    ("stage1_step5", re.compile(r"stage1.step5[:\s]|9b.annot", re.I)),
    ("ocr_stage1",  re.compile(r"ocr\+stage1[:\s]", re.I)),
    ("stage1",      re.compile(r"stage1[:\s]|2b\+9b|2b/9b", re.I)),
    ("ocr",         re.compile(r"ocr[:\s]|flash ocr", re.I)),
    ("stage5",      re.compile(r"stage5[:\s]|recipe", re.I)),
]

DATA_TASK_TYPES = {"stage4", "ocr_stage1", "stage1", "stage1_step5", "ocr", "stage5"}
```

## 5. 资源隔离（信号量）

```python
_resource_slots = {
    "opus_api": threading.Semaphore(3),     # 灵雅/AiGoCode Opus — 3并发
    "flash_api": threading.Semaphore(3),    # DashScope flash — 3并发
    "ollama": threading.Semaphore(1),       # Ollama — 串行
    "codex_general": threading.Semaphore(2),# 通用 Codex — 2并发
}
```

资源映射：
- stage4 → opus_api
- ocr, ocr_stage1 → flash_api
- stage1, stage1_step5 → ollama
- 其他 → codex_general

## 6. Codex 执行方式

所有数据任务通过 Codex 在 tmux 窗口执行：

```python
def run_codex_in_tmux(prompt, window_name, task_id=0, dry_run=False, timeout=14400):
    # 1. 拼接 ENV_CONTEXT + prompt + REPORT_INSTRUCTION
    # 2. 创建 tmux 窗口
    # 3. 执行: ~/bin/codex exec --dangerously-bypass-approvals-and-sandbox '{prompt}'
    # 4. 用 .done/.fail marker 文件轮询完成状态
    # 5. 读 report JSON，返回 summary
```

**必须用 `--dangerously-bypass-approvals-and-sandbox`**，否则 Codex 写不了 `~/culinary-engine/output/`。

## 7. ENV_CONTEXT（每个 prompt 前置）

```
IMPORTANT ENVIRONMENT NOTES:
- Ollama runs at http://localhost:11434
- This machine has a proxy at 127.0.0.1:7890. ALL HTTP clients MUST set trust_env=False
- Before running any script, run: export no_proxy=localhost,127.0.0.1 http_proxy= https_proxy=
- Output data goes to ~/culinary-engine/output/
- Do not modify any existing scripts.
```

## 8. REPORT_INSTRUCTION（每个 prompt 后置）

Codex 完成后必须写 JSON report 到 `reports/task_reports/{window_name}.json`：

```json
{
  "task_id": 0,
  "task": "window_name",
  "status": "success" or "failed",
  "started_at": "ISO",
  "finished_at": "ISO",
  "results": {
    "key_numbers": {},
    "output_files": []
  },
  "problems": [{"description": "", "solution": "", "root_cause": ""}],
  "suggestions": [],
  "token_usage": {}
}
```

## 9. 各任务执行器 prompt

### run_stage4
```
Run Stage4 open extraction for book "{book_id}".
python3 scripts/stage4_open_extract.py --chunks {chunks_path} --book-id {book_id} --config config/api.yaml --output-dir {output_dir} --resume --phase all
Do not modify scripts. trust_env=False is already set.
```
**依赖检查**：chunks_smart.json 不存在时 deferred，不执行。

### run_stage1
```
python3 scripts/stage1_pipeline.py --book-id {book_id} --config config/api.yaml --books config/books.yaml --toc config/mc_toc.json --output-dir {output_dir} --start-step 4
```

### run_stage1_step5
```
python3 scripts/stage1_pipeline.py --book-id {book_id} --config config/api.yaml --books config/books.yaml --toc config/mc_toc.json --output-dir {output_dir} --start-step 5 --retry-annotations
```

### run_ocr_single
三种情况：
1. 已有 raw_merged.md → 直接 stage1 --start-step 4
2. 已有 vlm_ocr_merged.md → 复制到 raw_merged.md + stage1 --start-step 4
3. 需要 OCR → Codex 写 OCR 脚本 + stage1 --start-step 4

## 10. 完成后处理

```python
def _run_data_task(task, dry_run=False):
    # ... 执行 ...

    # 收集 learnings
    collect_learnings(report_path)  # → learnings.jsonl

    # Auto-fix（7种模式）
    auto_fix_from_report(report)

    # Dify KB 同步
    sync_report_to_dify(report_path)
```

## 11. Auto-fix 模式（7种）

| 检测 | 动作 |
|---|---|
| script not found | 标记等 CC Lead |
| permission error | 重试 |
| timeout | 重试 |
| Ollama 连不上 (11434) | 推迟 |
| chunks_smart not found | 推迟等 Stage1 |
| source_converted.pdf not found + 有 raw_merged | 改成 Stage1 任务 |
| API rate limit / 429 | 推迟 |

## 12. Dify KB 同步

- 每个任务完成后：上传 report 到 Dify KB
- 每 10 轮：同步 learnings.jsonl 和 auto_fixes.jsonl

```python
DIFY_DATASET_KEY = "dataset-DqAtoTYJUES69kEUF7bFBs25"
# POST http://localhost/v1/datasets/{id}/document/create-by-text
```

## 13. Git/PR 流程（代码任务）

代码类任务（不在 DATA_TASK_TYPES 里的）走分支-PR 流程：
1. `ensure_clean_main()` → `create_task_branch()` → `agent/{agent}/{slug}-{id}`
2. Codex 执行
3. 有 commit → `push_and_create_pr()` → status = pr_open
4. 无 commit → cleanup branch → done
5. `poll_open_prs()` 每轮检查 MERGED/CLOSED

## 14. DB helpers

```python
def update_task(conn, task_id, status, result_summary="", pr_url=None):
    # status: pending/in_progress/pr_open/done/failed
    # 支持 pr_url 字段
    # 写 task_log 表
```

## 15. 不要改的

- task_queue.py — 已经在跑，不动
- launchd plist — 已配置好
- 现有 pipeline 脚本 — 不动

## 16. 测试

写完后：
1. `python3 -m py_compile scripts/dify/orchestrator.py`
2. `python3 scripts/dify/orchestrator.py --once --dry-run`
3. commit + push
4. `launchctl unload/load` 重启

## 17. Commit message

```
feat: orchestrator v2 — parallel tmux dispatch, report, auto-fix, Dify sync
```
