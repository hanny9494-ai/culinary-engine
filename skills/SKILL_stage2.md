# Skill: Stage 2 — 题目-Chunk 语义匹配

## 概述
Stage 2 负责将 306 道题目母表与所有书目的 chunks 进行语义匹配。
通过 embedding cosine similarity 找出每道题最相关的 top-K chunks，
供下游 Stage 3 蒸馏使用。

## 输入

| 文件 | 格式 | 来源 |
|------|------|------|
| `chunks_smart.json` | OFC: `{"chunks": [...]}` / MC: `[...]` | Stage 1 输出 |
| `l0_question_master.json` | `[{question_id, question_text, domain}]` | 手工维护 |
| `config/api.yaml` | YAML | 项目配置 |

### chunks_smart.json 兼容格式
- **OFC格式**: `{"chunks": [{chunk_idx, full_text, summary, topics, ...}]}`
- **MC格式**: `[{chunk_idx, full_text, summary, topics, source_book, ...}]`
- 多书合并时，chunk_id 格式: `{source_book}:chunk_{chunk_idx}`

## 输出

### question_chunk_matches.json
```json
[
  {
    "question_id": "L0-Q-HT-001",
    "question_text": "为什么水煮温度上限是100°C？",
    "domain": "heat_transfer",
    "top_chunks": [
      {
        "chunk_id": "mc_vol2:chunk_42",
        "score": 0.87,
        "chapter": 7,
        "chapter_title": "TRADITIONAL COOKING",
        "source_book": "mc_vol2",
        "preview": "前200字预览..."
      }
    ],
    "match_status": "matched"
  }
]
```

- `match_status`: `"matched"` (有 >=1 个 chunk 过阈值) / `"unmatched"` (全低于阈值)

### match_report.json
```json
{
  "total_questions": 306,
  "matched": 294,
  "unmatched": 12,
  "match_rate": 0.961,
  "avg_top1_score": 0.83,
  "avg_top3_score": 0.78,
  "domain_coverage": {
    "protein_science": {"matched": 28, "total": 30, "avg_score": 0.85}
  },
  "unmatched_questions": ["L0-Q-XX-001"]
}
```

### embeddings_cache.json
Embedding 结果缓存，key 为文本 SHA256 前16位，value 为向量。
重跑不重复调用 API。

## Embedding 提供方

### Gemini（默认，推荐）
- 模型: `gemini-embedding-2-preview`
- 环境变量: `GEMINI_API_KEY`
- 批处理: 每次最多 100 条
- 限速: 每秒不超过 5 请求

### Ollama（备选，`--use-ollama`）
- 模型: `qwen3-embedding:8b`
- 本地运行，无需 API key

## Embedding 文本构建
- **题目**: `question_text` 原文
- **Chunk**: `summary + " " + full_text[:500]`（summary 优先，中文摘要匹配效果更好）

## 匹配逻辑
1. 对所有题目和 chunks 文本进行 embedding 编码
2. 构建 cosine similarity 矩阵（numpy 矩阵化计算）
3. 每题取 top-k，过滤 < threshold 的结果

## CLI 用法

```bash
# dry-run（不调用 API）
python3 scripts/stage2_match.py \
  --chunks output/mc/vol2/stage1/chunks_smart.json \
  --questions data/l0_question_master.json \
  --output /tmp/test.json --dry-run

# Gemini embedding（多书合并）
python3 scripts/stage2_match.py \
  --chunks output/mc/vol2/stage1/chunks_smart.json \
  --chunks output/mc/vol3/stage1/chunks_smart.json \
  --chunks output/mc/vol4/stage1/chunks_smart.json \
  --questions data/l0_question_master.json \
  --output output/stage2/question_chunk_matches.json \
  --top-k 3 --threshold 0.70

# Ollama 本地
python3 scripts/stage2_match.py \
  --chunks output/mc/vol2/stage1/chunks_smart.json \
  --questions data/l0_question_master.json \
  --output output/stage2/question_chunk_matches.json \
  --use-ollama
```

## 参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--chunks` | (必填，可多次) | chunks_smart.json 路径 |
| `--questions` | (必填) | l0_question_master.json 路径 |
| `--output` | (必填) | 输出路径 |
| `--config` | `config/api.yaml` | API 配置文件 |
| `--top-k` | 3 | 每题取 top-k chunks |
| `--threshold` | 0.70 | cosine 相似度阈值 |
| `--use-ollama` | false | 使用 Ollama 本地 embedding |
| `--dry-run` | false | 只加载数据打印统计 |
| `--cache-dir` | 与 output 同目录 | embedding 缓存目录 |

## 依赖
- `requests`, `numpy`, `pyyaml`
- Gemini API（需 `GEMINI_API_KEY`）或 Ollama 本地

## 与下游 Stage 3 的接口
Stage 3 的 `load_chunks_map()` 函数消费本脚本输出的 `question_chunk_matches.json`，
读取 `question_id` → `top_chunks[].preview` 作为蒸馏的原始文本参考。
