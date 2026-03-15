# 餐饮研发引擎 — Culinary R&D Engine

> 因果链科学推理 + 粤菜审美转化（不是配方检索）

## 仓库结构

```
culinary-engine/
├── README.md
├── STATUS.md                    ← 项目状态（母对话维护）
├── AGENTS.md                    ← 多agent协作规范
│
├── config/
│   ├── api.yaml                 ← API配置（endpoint/model/auth）
│   ├── books.yaml               ← 书目注册表
│   ├── mc_toc.json              ← MC各卷TOC章节边界
│   └── domains_v2.json          ← 16域定义 + 旧→新映射
│
├── scripts/
│   ├── stage1_pipeline.py       ← Stage1: PDF→chunks_smart.json
│   ├── stage2_match.py          ← Stage2: 题目-chunk语义匹配
│   ├── stage3_distill.py        ← Stage3: Claude蒸馏L0原理
│   ├── stage3b_causal.py        ← Stage3B: 因果链增强+拆分
│   ├── scan_low_hit.py          ← 补题: 逆向扫描知识盲区
│   ├── run_book.py              ← 总编排: 单书全链路
│   └── utils/
│       ├── mineru_client.py     ← MinerU API客户端
│       ├── vision_client.py     ← DashScope qwen-vl客户端
│       ├── ollama_client.py     ← Ollama统一调用
│       ├── merge.py             ← MinerU+Vision合并
│       └── quality.py           ← 质量检查工具
│
├── skills/                      ← Codex/Claude Code skill文档
│   ├── SKILL_stage1.md
│   ├── SKILL_stage2.md
│   ├── SKILL_stage3.md
│   └── SKILL_full_pipeline.md
│
├── docs/
│   ├── architecture.md          ← 系统总设计
│   ├── domain_v2_spec.md        ← Domain重构方案
│   └── cantonese_stations.md    ← 粤菜工位知识层
│
├── tests/
│   └── (验证脚本)
│
├── review/
│   └── review_questions.html    ← 补题人工审核界面
│
└── .github/
    └── CODEOWNERS               ← 文件所有权声明
```

## Pipeline 全景

```
PDF/EPUB
  ↓
Stage 1: MinerU + qwen-vl → merge → qwen3.5:2b切分 → 9b标注 → chunks_smart.json
  ↓
Stage 2: 306题 × chunks → Gemini Embedding 2 cosine匹配 → question_chunk_matches.json
  ↓
Stage 3: (题目+top3chunks) → Claude Opus蒸馏 → l0_principles.jsonl
  ↓
Stage 3B: 因果链增强 → proposition_type + causal_chain_steps → l0_principles_v2.jsonl
  ↓
补题扫描: 低命中chunk → Claude识别盲区 → candidate_questions.json → 人工审核 → 扩展题库
  ↓
Neo4j图谱 + Weaviate向量 → 双RAG + HiRAG → 餐饮研发引擎
```

## 多Agent协作

详见 [AGENTS.md](AGENTS.md)
