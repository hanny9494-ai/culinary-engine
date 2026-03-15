# 餐饮研发引擎 — 子对话启动模板

## 通用前置步骤
```bash
git clone https://github.com/hanny9494-ai/culinary-engine.git
cd culinary-engine
cat STATUS.md
```

## 跑一本新书的完整流程
```bash
python3 scripts/run_book.py \
  --book-id <book_id> \
  --output-root ~/l0-knowledge-engine/output \
  --questions ~/l0-knowledge-engine/data/l0_question_master.json \
  --config config/api.yaml \
  --books config/books.yaml \
  --toc config/mc_toc.json \
  --domains config/domains_v2.json
```

## 单独跑某个 Stage

Stage 1:
```bash
python3 scripts/stage1_pipeline.py \
  --book-id <book_id> \
  --output-dir ~/l0-knowledge-engine/output/<book_id>/stage1 \
  --config config/api.yaml \
  --books config/books.yaml \
  --toc config/mc_toc.json
```

Stage 2:
```bash
python3 scripts/stage2_match.py \
  --chunks ~/l0-knowledge-engine/output/<book_a>/stage1/chunks_smart.json \
           ~/l0-knowledge-engine/output/<book_b>/stage1/chunks_smart.json \
  --questions ~/l0-knowledge-engine/data/l0_question_master.json \
  --output ~/l0-knowledge-engine/output/stage2/question_chunk_matches.json \
  --config config/api.yaml
```

Stage 3:
```bash
python3 scripts/stage3_distill.py \
  --matches ~/l0-knowledge-engine/output/stage2/question_chunk_matches.json \
  --chunks ~/l0-knowledge-engine/output/stage3/merged_chunks.json \
  --output-dir ~/l0-knowledge-engine/output/stage3 \
  --config config/api.yaml \
  --domains config/domains_v2.json \
  --append
```

Stage 3B:
```bash
python3 scripts/stage3b_causal.py \
  --input ~/l0-knowledge-engine/output/stage3/l0_principles.jsonl \
  --matches ~/l0-knowledge-engine/output/stage2/question_chunk_matches.json \
  --output ~/l0-knowledge-engine/output/stage3/l0_principles_v2.jsonl \
  --report ~/l0-knowledge-engine/output/stage3/stage3b_report.txt \
  --config config/api.yaml
```

## 常用参数
- `--start-stage 2`：从 Stage 2 开始跑
- `--stop-stage 3`：只跑到 Stage 3 停止
- `--skip-stage1`：复用已有 chunks
- `--dry-run`：只输出计划命令，不实际执行子进程

## 质量门禁
- Stage 1：`chunks_smart.json` 必须存在且 chunk 数量大于 0
- Stage 2：`question_chunk_matches.json` 必须有记录；`match_rate <= 0.8` 仅警告
- Stage 3：本次运行必须新增至少 1 条原理
- Stage 3B：`l0_principles_v2.jsonl` 必须有记录
- 汇总报告保存在 `output_root/run_report.json`

## 环境变量
```bash
export MINERU_API_KEY=""
export DASHSCOPE_API_KEY=""
export GEMINI_API_KEY=""
export L0_API_ENDPOINT="http://1.95.142.151:3000"
export L0_API_KEY="Bearer"
```

## 依赖清单
- Python 3.10+
- `requests`
- `PyYAML`
- MinerU API
- DashScope / Qwen-VL
- Gemini Embedding
- Claude 代理 API

## 常见排查
- 如果当前仓库缺少 `scripts/stage1_pipeline.py` 或 `scripts/stage2_match.py`，`run_book.py` 在真实执行时会直接报缺失依赖；`--dry-run` 仍可用于检查命令拼装。
- 如果 `--skip-stage1` 失败，先确认 `output_root` 下已经存在目标书的 `stage1/chunks_smart.json`。
- 如果 Stage 3 映射不到 chunk，检查 `output_root/stage3/merged_chunks.json` 是否包含目标书的 chunk 记录。
