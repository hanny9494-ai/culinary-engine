# 餐饮研发引擎 — 项目状态 v2

> 母对话维护此文件，agent不许修改
> 每次新对话前: cat STATUS.md

---

## 系统定位
- **目标用户**：专业厨师 / 餐饮老板 / 研发团队
- **核心能力**：因果链科学推理 + 粤菜审美转化（不是配方检索）
- **最终形态**：餐饮研发引擎

---

## 当前进度总览

| 阶段 | 状态 | 说明 |
|------|------|------|
| OFC Stage 1-3 | ✅ 完成 | 303条L0原理（l0_principles_fixed.jsonl）|
| MC Vol2/3/4 Stage1 Step0-3 | ✅ 完成 | raw_merged.md 已生成 |
| MC Vol2/3/4 Stage1 Step4-5 | ✅ 完成 | chunks_smart.json（9b标注完成）|
| MC Vol1 Stage1 | ⏳ 待做 | epub需先转PDF（calibre）|
| Stage2 Embedding | ⏳ 待做 | 切换Gemini Embedding 2 |
| Stage3B 因果链 | ⏳ 待做 | 脚本已就绪，~$6 |
| Stage3.5 粤菜映射 | ⏳ 待做 | Stage3B完成后 |
| Neo4j 图谱 | ⏳ 待做 | Schema v2设计完成 |
| Weaviate 向量库 | ⏳ 待做 | Schema设计完成 |
| L6 风味层 | ⏳ 待做 | Flavor Bible待处理 |
| Station层（粤菜） | ⏳ 待做 | 5个station定义完成 |
| **Pipeline自动化打包** | 🔄 进行中 | 新仓库，多agent并行 |

---

## Pipeline 阶段定义

```
Stage 1:  PDF → MinerU + qwen-vl → merge → 2b切分 → 9b标注 → chunks_smart.json
Stage 2:  306题 × chunks → Gemini Embedding 2 匹配 → question_chunk_matches.json
Stage 3:  (题+chunks) → Claude Opus蒸馏 → l0_principles.jsonl
Stage 3B: 因果链增强 → proposition_type + causal_chain → l0_principles_v2.jsonl
补题:     低命中chunk → Claude扫描 → candidate_questions.json → 人工审核
```

---

## L0 原理库设计（v2）

### 原子命题类型（4种）
- `fact_atom` — 单一数值事实（~35%）
- `causal_chain` — 因果序列A→B→C（~45%）
- `compound_condition` — n元同时条件（~15%，超边候选）
- `mathematical_law` — 定量数学关系（~5%）

### Domain分类（16个，v2）
保留9个：protein_science / carbohydrate / lipid_science / fermentation /
food_safety / water_activity / enzyme / color_pigment / equipment_physics

新增/拆分7个：
- chemical_reaction → maillard_caramelization / oxidation_reduction / salt_acid_chemistry
- flavor_sensory → taste_perception / aroma_volatiles
- heat_transfer + physical_change → thermal_dynamics / mass_transfer
- 新增：texture_rheology

---

## 技术栈

| 组件 | 选型 | 状态 |
|------|------|------|
| PDF提取 | MinerU API + qwen3-vl-plus | ✅ |
| 文本切分 | qwen3.5:2b Ollama | ✅ |
| Topic标注 | qwen3.5:9b Ollama (think:False) | ✅ |
| 原理蒸馏 | Claude Opus 4.6，代理API | ✅ |
| 因果链蒸馏 | Claude Sonnet 4.6 | ⏳ |
| Embedding | gemini-embedding-2-preview | ⏳ 切换中 |
| 向量库 | Weaviate | ⏳ |
| 图谱库 | Neo4j Docker | ⏳ |

---

## 环境变量
```bash
export MINERU_API_KEY=""
export DASHSCOPE_API_KEY=""
export GEMINI_API_KEY=""
export L0_API_ENDPOINT="http://1.95.142.151:3000"
export L0_API_KEY="Bearer"
```

---

## 本地数据路径（不进仓库）
```
/Users/jeff/l0-knowledge-engine/
├── data/l0_question_master.json              306题
├── output/stage3/l0_principles_fixed.jsonl   303条OFC原理
├── output/stage2/question_chunk_matches.json  OFC匹配结果
└── output/mc/vol{2,3,4}/stage1/chunks_smart.json  MC chunks
```
