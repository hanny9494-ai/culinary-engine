# Agent交接文档

> 最后更新: 2026-03-20
> 母对话维护此文件

---

## 当前活跃任务

### Stage4 开放扫描（进行中）
- mc_vol2/3/4 Phase B 在跑（Opus API串行，不支持并发）
- OFC完成：3,955条净增原理（¥65）
- Neurogastronomy完成：349条净增
- 累计已产出4,994+条原子命题（含Stage3骨架690条）
- 7本新书待启动Phase A（等chunk_type快捷路径代码merge后）
- API不支持并发，所有Opus任务必须排队

### CC待执行
- stage4_open_extract.py 加chunk_type快捷路径（工单已发，分支agent/stage4-chunktype-shortcut）
- 三个Stage4脚本修复（同分支）

---

## 已完成任务

### ✅ Stage4 OFC 全流程
- Phase A: 1,427→907 chunks (64%通过)
- Phase B: 907→4,753条原理（每chunk平均5.4条，¥65）
- Dedup: internal去69条，cross vs Stage3仅4条重复(0.08%)
- QC: 3,955条通过(84.5%)，573条citation模糊匹配，180条域外(暂标unclassified)

### ✅ Stage4 Neurogastronomy 全流程
- Phase A: 613→289 (47%) → Phase B: 380条 → QC: 349条通过

### ✅ Stage4 脚本修复
- dedup: numpy矩阵运算替换双层for循环（30分钟→2秒）
- open_extract: Session(trust_env=False) + JSON解析增强 + resume跳过已处理chunk
- quality: has_number从fail gate改为warning

### ✅ 阶段B — 1,159条原理domain→17域
- 已刷新完成

### ✅ 第二批4本 TOC + Stage1 重跑
- TOC配置已写入 mc_toc.json
- pipeline加了TOC强制检查（auto-chapter-split已禁用）
- 质量报告：summary/topics 100%覆盖，chunk大小正常
- 已知问题：TOC heading匹配偏移（不影响Stage2/3）

### ✅ 第一批4本 Stage1
- Neurogastronomy 613 / SFAH 1,055 / MC Vol1 2,148 / 冰淇淋 217

### ✅ 第零批 Stage1-3B
- OFC 303条 + MC 294条 = 597条 → 1,159条原子命题

---

## 蒸馏完成后任务队列

### P2: 补题
- scan_low_hit 扫描知识盲区 → candidate_questions.json → 人工审核
- mass_transfer: 当前4题，补到10-12题
- oxidation_reduction: 当前5题，补到10-12题
- 补题后增量蒸馏（--append模式）

### P2: 195条fallback confidence补刷
- 重新解析JSON，不重新蒸馏

### P2: 外部数据源ETL（第一批）
- FoodAtlas → L2a+FT (GitHub TSV)
- FlavorGraph → FT (GitHub pickle/CSV)
- FooDB → L2a (CSV下载)
- USDA API → L2a+L2c (JSON API)
- 均不需要蒸馏，写ETL脚本直接导入
- 最大工作量: 中英食材名映射表

### P3: 存储层
- Neo4j 搭建 + 实体对齐（原子命题入图谱）
- Weaviate 填充（embedding检索）

### P3: 补题第二轮
- scan_low_hit 发现新知识盲区
- 外部数据源第二批ETL（FlavorDB2+FoodOn）

### P4: 终局架构
- 双RAG原型 + L3推理引擎 + v4多Agent
- 详见 docs/arch_discussion_v4_20260316.docx

---

## 关键文件路径

| 文件 | 路径 | 说明 |
|------|------|------|
| v2题库 | data/l0_question_master_v2.json | 306题17域 ✅ |
| v1题库(归档) | data/l0_question_master.json | 306题旧14域 |
| domain映射 | data/question_domain_remap.json | 旧→新域变更记录 |
| Stage3B原子命题 | data/stage3b/l0_principles_v2.jsonl | 1,159条 |
| 合并原理(Stage3B前) | data/stage3b/l0_principles_all.jsonl | 597条 |
| OFC原理 | ~/l0-knowledge-engine/output/stage3/l0_principles_fixed.jsonl | 303条 |
| MC原理 | ~/l0-knowledge-engine/output/stage3_mc/l0_principles.jsonl | 294条 |
| API配置 | config/api.yaml | |
| 书目注册 | config/books.yaml | 11本书已注册 |
| 17域定义 | config/domains_v2.json | |
| TOC配置 | config/mc_toc.json | 11本书全部有TOC |

---

## 17域列表
protein_science, carbohydrate, lipid_science, fermentation,
food_safety, water_activity, enzyme, color_pigment,
equipment_physics, maillard_caramelization, oxidation_reduction,
salt_acid_chemistry, taste_perception, aroma_volatiles,
thermal_dynamics, mass_transfer, texture_rheology

---

## 技术决策速查

1. v2题库17域已生效，新任务一律用v2
2. 旧原理domain标签已刷新（阶段B完成）
3. OFC+MC双来源保留，不合并
4. 新书必须先TOC检测→人工审阅→再跑Stage1（auto-chapter-split已禁用）
5. Stage3B逐条独立跑，不需要跨书
6. Neo4j入库时做跨书实体对齐
7. 外部数据源ETL直接导入，不走蒸馏pipeline
8. 中英食材名映射表建一次后所有数据源共用
9. Ollama不能并发跑多本书，9b标注必须串行
10. Ollama调用必须绕过http_proxy（trust_env=False）
11. Stage2 embedding用Ollama qwen3-embedding:8b时threshold=0.48（Gemini时用0.70）
17. 新书不跑Stage2+3，Stage4做L0主力，薄弱域再补Stage2+3
18. Phase A支持chunk_type快捷路径（有chunk_type跳过27b）
19. has_number改为warning不再fail gate
20. API不支持并发，Opus任务串行排队
21. 域外原理暂标unclassified，全量跑完再统一处理，17域不扩

### 配方蒸馏pipeline设计（L0稳定后）
- Schema定义: docs/recipe_schema_v1.md
- ISA-88三段分离: process/formula/equipment
- 蒸馏顺序: 先Basic Recipes章节→再正文菜式
- LLM三级递进: 9b判断是否配方→27b提取结构化JSON→Opus校验L0
- 模糊量词必须转数字，只有to_taste允许null

### 架构v4讨论记录
- 文档: docs/arch_discussion_v4_20260316.docx
- 方向: 多维因果图谱+审美驱动+多Agent
- 状态: 设计讨论完成，等P0-P3走通后实施

### 总成本估算
- Stage3+3B: ¥13 ✅ 已花
- Stage4 OFC: ¥65 ✅ 已花
- Stage4 Neuro: ~¥15 ✅ 已花
- Stage4 mc_vol2/3/4: ~¥70 🔄 在跑
- Stage4 全量30本书: ¥1,500-2,000（预估）
- 预算: ¥5,000，绰绰有余
