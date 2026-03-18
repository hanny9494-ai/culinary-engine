# Agent交接文档

> 最后更新: 2026-03-18
> 母对话维护此文件

---

## 当前活跃任务

### Stage3 全量蒸馏（进行中）
- 306题全量重跑，Claude Opus 4.6
- 全量 14,041 chunks（11本书）× 306题，100%匹配
- 选项2：全量重跑替代旧原理，旧的归档做查重
- 预计费用 ~¥8，时间 ~1小时
- 完成后接 Stage3B 因果链增强 ~¥3-5，~1小时

---

## 已完成任务

### ✅ 阶段B — 1,159条原理domain→17域
### ✅ 第二批4本 TOC + Stage1 重跑
- TOC配置已写入 mc_toc.json，pipeline加了TOC强制检查
- 质量：summary/topics 100%覆盖，chunk大小正常
- 已知问题：TOC heading匹配偏移（不影响Stage2/3）
### ✅ 第一批4本 Stage1
- Neurogastronomy 613 / SFAH 1,055 / MC Vol1 2,148 / 冰淇淋 217
### ✅ 第零批 Stage1-3B
- OFC 303条 + MC 294条 = 597条 → 1,159条原子命题
### ✅ Stage2 全量匹配
- 14,041 chunks × 306题，100%匹配率，avg top1 ~0.66
- Ollama qwen3-embedding:8b，threshold 0.48

---

## 蒸馏完成后任务队列

### P1: L0开放扫描 — Stage4
> 设计文档：docs/stage4_open_extract_design.md

**动机：** 306题驱动蒸馏有盲区——题目覆盖不到的知识永远被漏掉。开放扫描让LLM逐chunk自主发现科学原理，补充306题的视角限制。参考 AnalogSeeker（2025）从2,698个learning nodes蒸馏出15,310条数据。

**Pipeline：**
1. 27b 预过滤（本地免费）→ 判断chunk是否含科学命题
2. Opus 4.6 核心提取（代理API）→ 一步到位出原子命题+因果链
3. embedding 8b 去重（本地免费）→ 与306题蒸馏原理交叉去重
4. 27b 质控（本地免费）→ 格式+科学性验证

**成本：** 试跑Neurogastronomy ¥15-20，全量11本书 ¥200-280
**产出：** 净增3,000-5,000条原子命题 → L0总量5,000-8,000条

**关键决策：**
- 27b做筛选，Opus 4.6做主力提取（不反过来，原理质量是系统根基）
- Stage4（原理）和Stage5（配方）分开扫描，不合并（L0是地基，专注单任务更稳）

### P2: 补题
- scan_low_hit 扫描知识盲区 → candidate_questions.json → 人工审核
- mass_transfer 补到10-12题，oxidation_reduction 补到10-12题
- 补题后增量蒸馏（--append模式）
- 195条 fallback confidence 补刷

### P3: 存储层 + 外部数据
**简化方案（用现成资源替代自建）：**
- ❌ 不自建中英食材名映射表 → ✅ 用 FoodOn + Wikidata 多语言标签 + FoodOntoRAG 自动对齐，粤菜特有食材手工补几十条
- ❌ 不写四个独立ETL → ✅ 导入 FoodKG dump（已整合USDA+Recipe1M+FoodOn 6700万三元组）+ FoodAtlas 补充23万化学关系
- ❌ 不人工逐条实体对齐 → ✅ embedding cosine + FoodOn 标准化自动对齐

**三层存储架构（解决大数据量性能问题）：**
- 热层（Neo4j主库）：L0原理 + 配方 + 映射边 + FoodOn核心子集，~50K节点+100K边，查询<10ms
- 温层（Weaviate）：embedding向量，语义检索 ~50ms
- 冷层（按需查询）：FoodKG完整数据 + FoodAtlas，查询100-500ms，只在需要营养/化学详情时调用
- 日常推理不受外部大数据影响，LLM推理时间(2-5秒)才是瓶颈

### P4: 配方提取 — Stage5
> 设计文档：docs/stage5_recipe_extract_design.md

**核心难题：** 子配方散落——高汤/酱汁/面团定义在书末Basic Recipes，正文通过"see page xxx"引用。

**两阶段方案：**
1. **SubRecipe库先行**：2b筛选配方chunks → 27b提取SubRecipe → 建立SubRecipe Registry（名称→ID映射）
2. **Recipe组装**：27b带着Registry上下文提取正文配方 → 引用解析（"see page xxx"→映射到SR-xxx）

**蒸馏顺序：** 先Basic Recipes章节 → 再正文菜式（与recipe_schema_v1.md一致）

**配方×L0双向映射：** 配方提取时顺带标注每步的domain，后续用embedding精确映射到具体L0条目。这让整个知识库串起来——换食材/换工具/换审美/换风味都能找到对应的L0科学依据。

**模型分工：** 2b筛选 → 27b主力提取 → Opus兜底复杂配方（~¥20-30）

**学术参考已整合：**
- r-NE标签体系（京都大学 r-FG Corpus 2020）→ 27b提取prompt的实体引导
- Cooklang + GPT-4（2023）→ prompt迭代优化参考
- Recipe Flow Graph → P6阶段process升级为DAG
- EaT-PIM（ISWC 2022）→ P6阶段食材替换推理（流图embedding + L0因果链）
- PADME（2025）→ "可复用子程序"概念 = SubRecipe

### P5: 双RAG + L3推理引擎
- Neo4j图谱检索 + Weaviate向量检索
- L3推理引擎雏形
- 端到端测试（粤菜场景）

### P6: 终局架构
- process升级为DAG（并行/汇合/时间优化）
- 审美层（Goal节点动态组合）
- 多Agent分工（诊断/创作/优化/知识/替换）
- 食材替换推理（流图embedding + L0因果链）
- 外部数据源第二批（FlavorDB2爬虫 + FoodOn深度对齐）
- 详见：docs/arch_discussion_v4_20260316.docx

---

## 2.0 方向：AI生成内容

当P0-P5完成后，系统具备从科学原理出发**推理生成从未存在过的配方**的能力：
- 自动生成新菜式：给定食材+风味目标+设备约束 → L0推理 → 完整配方
- 跨菜系融合：粤菜工艺 + 法餐酱汁概念 → L0计算兼容性和调整方案
- 自动适配：换烤箱/换供应商 → L1/L2c自动调整参数
- 教学内容：每个操作步骤自动关联科学解释
- 中餐录入不难：L0是跨菜系的物理化学定律，只需补中餐特有工艺参数和食材参数

---

## 关键文件路径

| 文件 | 路径 | 说明 |
|------|------|------|
| v2题库 | data/l0_question_master_v2.json | 306题17域 ✅ |
| Stage3B原子命题 | data/stage3b/l0_principles_v2.jsonl | 1,159条（归档，新版蒸馏后替代） |
| API配置 | config/api.yaml | |
| 书目注册 | config/books.yaml | 11本书已注册 |
| 17域定义 | config/domains_v2.json | |
| TOC配置 | config/mc_toc.json | 11本书全部有TOC |
| 路线图v2 | docs/roadmap_priorities_v2.md | P0-P6 + 简化方案 + 性能架构 |
| Stage4设计 | docs/stage4_open_extract_design.md | L0开放扫描 |
| Stage5设计 | docs/stage5_recipe_extract_design.md | 配方提取 + 学术参考 |
| 配方Schema | docs/recipe_schema_v1.md | ISA-88三段分离 |
| 架构v4 | docs/arch_discussion_v4_20260316.docx | 终局方向 |

---

## 17域列表

```
protein_science, carbohydrate, lipid_science, fermentation,
food_safety, water_activity, enzyme, color_pigment,
equipment_physics, maillard_caramelization, oxidation_reduction,
salt_acid_chemistry, taste_perception, aroma_volatiles,
thermal_dynamics, mass_transfer, texture_rheology
```

---

## 技术决策速查

1. v2题库17域已生效，新任务一律用v2
2. 旧原理domain标签已刷新（阶段B完成）
3. OFC+MC双来源保留，不合并
4. 新书必须先TOC检测→人工审阅→再跑Stage1（auto-chapter-split已禁用）
5. Stage3B逐条独立跑，不需要跨书
6. 外部数据源用FoodKG dump+FoodAtlas导入，不逐个ETL
7. 中英映射用FoodOn+Wikidata，不自己从零建
8. 中英食材名映射表建一次后所有数据源共用
9. Ollama不能并发跑多本书，9b标注必须串行
10. Ollama调用必须绕过http_proxy（trust_env=False）
11. Stage2用Ollama embedding时threshold=0.48（Gemini时用0.70）
12. 27b做筛选，Opus做原理主力提取（不反过来）
13. Stage4（原理）和Stage5（配方）分开扫描不合并
14. 配方×L0映射融入Stage5提取，不单独一步
15. Step2视觉识别默认启用smart_filter，只送table/equation/文字不足页，纯照片页跳过（Food Lab验证：768→233，省70%）
16. Step5 9b标注新增chunk_type字段（science/recipe/mixed/narrative），第三批书开始生效，已有11本书不重跑

### 配方蒸馏pipeline设计（L0稳定后）
- Schema定义: docs/recipe_schema_v1.md
- ISA-88三段分离: process/formula/equipment
- 蒸馏顺序: 先Basic Recipes章节→再正文菜式
- LLM分工: 2b判断是否配方→27b提取结构化JSON→Opus兜底复杂配方
- 模糊量词必须转数字，只有to_taste允许null
- SubRecipe Registry解决子配方散落问题

### 存储性能架构
- 热层Neo4j：L0+配方+映射，<10ms
- 温层Weaviate：embedding检索，~50ms
- 冷层：FoodKG+FoodAtlas，按需100-500ms
- 日常推理只查热+温层，LLM推理(2-5s)才是瓶颈

### 总成本估算
- P0 Stage3+3B: ~¥13
- P1 Stage4全量: ~¥200-280
- P2 补题: ~¥7
- P4 配方提取: ~¥20-30
- 合计: ~¥240-330（约$50）
