# 餐饮研发引擎 — 项目状态 v6

> 母对话维护此文件，agent不许修改
> 新仓库: https://github.com/hanny9494-ai/culinary-engine
> 更新时间: 2026-03-23
> CC Lead 基础设施已迁入本仓库（CLAUDE.md + .claude/agents/ + scripts/dify/）

---

## 系统定位
- **目标用户**：专业厨师 / 餐饮老板 / 研发团队
- **核心能力**：因果链科学推理 + 粤菜审美转化（不是配方检索）
- **核心公式**：食材参数 × 风味目标 × 科学原理 = 无限食谱
- **架构文档**：docs/culinary_engine_architecture_v5.docx

---

## 七层知识架构

| 层 | 名称 | 定位 | 状态 |
|----|------|------|------|
| L0 | 科学原理图谱 | "为什么会发生" — 因果链+参数边界+17域 | 🔄 蒸馏中（21/46本完成） |
| L1 | 设备实践参数层 | "同一原理，不同设备怎么调" | ⏳ 待建 |
| L2a | 天然食材参数库 | 品种/部位/季节/产地/价格 | ⏳ 待建（FoodAtlas/FooDB/USDA待导入） |
| L2b | 食谱校准库 | 已验证参数组合+可信度评分（L0是裁判） | ⏳ 待建 |
| L2c | 商业食材数据库 | 品牌/型号→成分细分（食谱精确到品牌） | ⏳ 待建（USDA Branded待导入） |
| FT | 风味目标库 | 审美词→可量化感官参数 | ⏳ 待建（FlavorGraph/FlavorDB2待导入） |
| L3 | 推理引擎 | f(L0,L1,L2a,L2c,FT) 预计算+实时推理 | ⏳ 待建 |
| L6 | 翻译层 | 粤菜语言↔系统语言（纯翻译不判断） | ⏳ 待建（FoodOn本体待对齐） |

---

## 当前进度总览

| 阶段 | 状态 | 说明 |
|------|------|------|
| 第零批 Stage1-3B | ✅ 完成 | OFC 303条 + MC 294条 = 597条 → Stage3B拆分为1,159条原子命题 |
| 306题→17域重映射 | ✅ 完成 | v2题库生效，172题变更 |
| 阶段B: 1,159条domain→17域 | ✅ 完成 | 原理标签已刷新 |
| 第一批 Stage1 | ✅ 完成 | Neurogastronomy 613 / SFAH 1,055 / MC Vol1 2,148 / 冰淇淋 217 |
| 第二批 Stage1 | ✅ 完成 | Mouthfeel 1,162 / Flavorama 1,159 / Science of Spice 1,136 / Professional Baking 3,434 |
| 第二批 TOC配置 | ✅ 完成 | 4本书TOC已写入mc_toc.json，auto-chapter-split已禁用 |
| Stage4 OFC | ✅ 完成 | 3,955条净增 |
| Stage4 Neurogastronomy | ✅ 完成 | 349条净增 |
| Stage4 mc_vol2/3/4 | 🔄 Phase B | API串行中 |
| Stage4 第三批7本书 | ⏳ 待启动 | 等chunk_type快捷路径 |
| Stage2 匹配 | 🔄 进行中 | 7本新书 13,824 chunks × 306题，Ollama qwen3-embedding:8b |
| 冰淇淋 Stage2 | ⏳ 待做 | 等7本完成后加入，全量 ~14,041 chunks |
| 全量 Stage3 蒸馏 | ⏳ 待做 | 等Stage2全部完成后，306题全量重跑 |
| Pipeline自动化 | ✅ 完成 | 新仓库全部merge，TOC强制检查已加 |
| 架构文档v3 | ✅ 完成 | 七层+L2c+冷启动+自学习闭环 |

---

## L0数据规模（2026-03-23 校准）

| 来源 | raw | dedup | QC通过 |
|------|-----|-------|--------|
| Stage3骨架 | — | — | 690 |
| Stage4 21本（详见下表） | 47,203 | 37,084 | 34,355 |
| **L0累计** | | | **35,045** |

**主线盘子：46本（21已完成 + 25待处理）**

### Stage4 完成明细（21本，34,355条QC通过）

| 书 | raw | dedup | QC通过 | 通过率 |
|---|---|---|---|---|
| ofc | 4,868 | 4,680 | 3,955 | 81% |
| science_good_cooking | 4,823 | 4,229 | 3,806 | 79% |
| mc_vol1 | 3,983 | 3,314 | 3,110 | 78% |
| mouthfeel | 3,021 | 2,605 | 2,410 | 80% |
| cooking_for_geeks | 3,629 | 3,057 | 2,266 | 62% |
| food_lab | 3,386 | 2,785 | 2,242 | 66% |
| professional_baking | 3,134 | 2,458 | 2,136 | 68% |
| molecular_gastronomy | 2,439 | 2,246 | 1,951 | 80% |
| bread_hamelman | 2,612 | 1,971 | 1,669 | 64% |
| science_of_chocolate | 2,319 | 1,871 | 1,577 | 68% |
| flavorama | 2,012 | 1,689 | 1,258 | 63% |
| mc_vol4 | 1,267 | 1,166 | 1,034 | 82% |
| mc_vol3 | 1,194 | 1,123 | 1,059 | 89% |
| koji_alchemy | 1,414 | 1,178 | 978 | 69% |
| science_of_spice | 1,604 | 1,052 | 960 | 60% |
| salt_fat_acid_heat | 1,348 | 1,163 | 910 | 68% |
| mc_vol2 | 1,085 | 938 | 893 | 82% |
| noma_fermentation | 1,213 | 1,061 | 850 | 70% |
| bread_science_yoshino | 657 | 568 | 522 | 79% |
| ice_cream_flavor | 601 | 438 | 414 | 69% |
| ratio | 594 | 488 | 355 | 60% |

### 待处理书籍（25本）

**Stage1就绪 → 可直接进Stage4（5本）：**
french_sauces(127), neurogastronomy(619), dashi_umami(268), handbook_molecular_gastronomy(521), chocolates_confections(908)

**Stage1 Step5 正在跑（1本）：**
flavor_equation（9b标注中）

**Stage1 Step4+5 待跑（6本）：**
essentials_food_science, flavor_bible, bocuse_cookbook, taste_whats_missing, modernist_pizza, professional_pastry_chef

**需要OCR+Stage1（2本）：**
french_patisserie, phoenix_claws

**新增11本（需要OCR起步）：**
sous_vide_keller, japanese_cooking_tsuji, professional_chef, charcuterie, jacques_pepin, noma_vegetable, art_of_fermentation, flavor_thesaurus, franklin_barbecue, vegetarian_flavor_bible, whole_fish

## Stage4第一批结果

| 书 | raw | dedup后 | QC通过 | 通过率 |
|---|---|---|---|---|
| mc_vol1 | 3,983 | 3,314 | 3,110 | 78% |
| salt_fat_acid_heat | 1,348 | 1,163 | 910 | 67% |
| ice_cream_flavor | 601 | 438 | 414 | 69% |
| mouthfeel | 3,021 | 2,605 | 2,410 | 80% |
| flavorama | 2,012 | 1,689 | 1,258 | 63% |
| science_of_spice | 1,604 | 1,052 | 960 | 60% |
| professional_baking | 3,134 | 2,458 | 2,136 | 68% |
| **合计** | **15,703** | **12,719** | **11,198** | **71%** |

## Pipeline状态

**已完成Stage4（12本）：**
零批5本 + 一批7本 → 19,178条L0

**Stage4在跑（10本）：**
第三批7本（food_lab, science_good_cooking, molecular_gastronomy, noma_fermentation, koji_alchemy, ratio, cooking_for_geeks）+ 第五批3本（science_of_chocolate, bread_hamelman, bread_science_yoshino）

**Stage1在跑（3本，Codex）：**
handbook_molecular_gastronomy（Step5标注中）, dashi_umami（需补Step5）, chocolates_confections（需2b+9b）

**L0收官批（10本，等前置完成后启动）：**
第六批6本（essentials_food_science, flavor_equation, flavor_bible, french_sauces, bocuse_cookbook, phoenix_claws）+ 第九批4本（taste_whats_missing, modernist_pizza, french_patisserie, professional_pastry_chef）

**L2b食谱提取（不做L0）：**
第七批7本 + 第八批5本（编译md，无图，只做食谱提取）

## VLM OCR新链路

qwen3.5-flash VLM OCR验证通过（决策#22）：
- 3本脏书全量OCR完成，0失败0乱码
- 成本¥0.6/本，速度8.5秒/页
- 新标准pipeline：PDF → flash OCR → md → 2b → 9b
- 替代MinerU+qwen-vl+merge五步流程

## 架构更新

架构文档v5已发布：docs/culinary_engine_architecture_v5.docx
主要更新：
- Neo4j统一图谱（去掉Weaviate，用Neo4j内置向量索引）
- Graphiti做L3-personal动态记忆
- 食谱schema v2：纯配方JSON + Neo4j关系网（科学标注不嵌入食谱）
- 关键科学决策点（3-5个深度绑定）替代逐步L0硬贴
- 裂变推导：每个L0绑定点生成3+条what-if推导
- 五个自主进化机制（查询驱动L3、用户贡献、L0盲区发现、反馈强化、跨食谱模式）
- LangGraph + 7工具的Agentic Graph RAG

---

## 题目库

| 版本 | 题数 | 域数 | 状态 |
|------|------|------|------|
| v1 (旧) | 306 | 14域 | 归档 |
| **v2 (当前)** | **306** | **17域** | ✅ 生效 |

17域薄弱域（蒸馏完后用scan_low_hit补题）:
- mass_transfer: 4题 ← 需补题
- oxidation_reduction: 5题 ← 需补题

---

## Chunks 总量（18本书）

| 书目 | chunks | 状态 |
|------|--------|------|
| OFC | 1,427 | ✅ |
| MC Vol2 | 485 | ✅ |
| MC Vol3 | 502 | ✅ |
| MC Vol4 | 703 | ✅ |
| MC Vol1 | 2,148 | ✅ |
| Neurogastronomy | 613 | ✅ |
| Salt Fat Acid Heat | 1,055 | ✅ |
| 冰淇淋风味学 | 217 | ✅ |
| Mouthfeel | 1,162 | ✅ |
| Flavorama | 1,159 | ✅ |
| Science of Spice | 1,136 | ✅ |
| Professional Baking | 3,434 | ✅ |
| Food Lab | 2,273 | ✅ |
| Science of Good Cooking | 2,886 | ✅ |
| Molecular Gastronomy | — | ✅ |
| Noma Fermentation | — | ✅ |
| Koji Alchemy | — | ✅ |
| Ratio | — | ✅ |
| Cooking for Geeks | 1,528 | ✅ |
| **合计** | **20,728+** | |

Topics 分布验证：
- Mouthfeel → texture_rheology 主导 ✅
- Flavorama → taste_perception + aroma_volatiles ✅
- Science of Spice → aroma_volatiles 主导 ✅
- Professional Baking → texture_rheology + carbohydrate ✅

已知问题：TOC heading匹配偏移（大部分chunks归到最后匹配章节），不影响Stage2/3。

---

## Stage4 开放扫描（进行中）

Pipeline: 27b预过滤(或chunk_type快捷) → Opus 4.6核心提取 → embedding去重 → 27b质控

| 书 | Phase A | Phase B | Dedup+QC | 净增 |
|----|---------|---------|----------|------|
| Neurogastronomy | 613→289 (47%) | 380条 | 349通过 | ✅ 349 |
| OFC | 1,427→907 (64%) | 4,753条 | 3,955通过(84.5%) | ✅ 3,955 |
| mc_vol2/3/4 | — | 在跑 | — | 🔄 Phase B |
| 7本新书（第三批） | 待启动 | — | — | ⏳ |

关键数据：
- 与Stage3重叠仅0.08%（4/4,753），306题只覆盖约12%知识量
- OFC费用实际¥65，全量30本书预估¥1,500-2,000
- API不支持并发，Opus任务串行排队

---

## 外部数据源导入计划（待做）

| 批次 | 数据源 | 灌入层 | 格式 | 状态 |
|------|--------|--------|------|------|
| 第一批 | FoodAtlas | L2a+FT | GitHub TSV | ⏳ |
| 第一批 | FlavorGraph | FT | GitHub pickle/CSV | ⏳ |
| 第一批 | FooDB | L2a | CSV下载 | ⏳ |
| 第一批 | USDA API | L2a+L2c | JSON API | ⏳ |
| 第二批 | FlavorDB2 | FT | 需爬虫 | ⏳ |
| 第二批 | FoodOn | L6 | OWL本体 | ⏳ |
| 第三批 | Recipe1M | L2b | JSON | ⏳ |

均不需要蒸馏，ETL直接导入。最大工作量是中英食材名映射。

---

## ⚠️ 关键技术决策（所有agent必读）

1. **切分工具：qwen3.5:2b（不是Chonkie）** — 已测试确认
2. **Stage3B独立判断proposition_type** — 不依赖阶段A
3. **v2题库17域已生效** — 新书用v2，旧原理已完成阶段B批量刷标签
4. **MC Vol2/3/4的9b标注不重跑** — domain迁移在下游处理
5. **OFC+MC原理保留双来源** — 不合并，597条都留
6. **L0是裁判** — 食谱和外部信息必须经L0校验才入库
7. **L6只翻译不判断** — 审美合理性判断在L3
8. **查不到就问** — 不猜测，引导用户提供食材/工艺/口感目标
9. **新书必须先TOC检测→人工审阅→再跑Stage1** — auto-chapter-split已禁用（pipeline强制检查mc_toc.json）
10. **外部数据源ETL导入不蒸馏** — FoodAtlas/FlavorGraph等直接导入Neo4j
11. **Ollama不能并发跑多本书** — 9b标注必须串行，2b切分同理；MinerU/Vision(API)可并行
12. **Ollama调用必须绕过http_proxy** — 本机有代理127.0.0.1:7890，ollama_client.py已用trust_env=False
17. **新书不再跑Stage2+3** — Stage4开放扫描做L0主力提取，全量完成后仅对薄弱域定向补Stage2+3
18. **Stage4 Phase A支持chunk_type快捷路径** — 有chunk_type的书跳过27b预过滤
19. **stage4_quality.py的has_number改为warning** — 不再fail gate
20. **API不支持并发** — Opus任务串行排队
21. **域外原理暂标unclassified** — 全量跑完再统一处理，17域不扩
22. **qwen3.5-flash替代MinerU为OCR标准**（2026-03-22）
23. **LangGraph + Neo4j + Graphiti，不用Dify**（2026-03-22）
24. **Sonnet 4.6 Thinking记录推理过程**（2026-03-22）
25. **Stage4追加token统计**（2026-03-22）
26. **Neo4j内置向量索引替代Weaviate**（2026-03-22）
27. **Graphiti做L3-personal动态记忆**（2026-03-22）
28. **食谱schema v2——纯JSON + Neo4j关系**（2026-03-22）
29. **关键科学决策点替代逐步L0绑定**（2026-03-22）
30. **三级置信度high/medium/inferred/unmapped**（2026-03-22）
31. **裂变推导——每个L0点→3+ what-if**（2026-03-22）
32. **编译md只做L2b食谱提取不做L0**（2026-03-22）

---

## 里程碑

- ✅ Stage4第一批7本完成：11,198条（2026-03-22）
- ✅ qwen3.5-flash VLM OCR验证通过（2026-03-22）
- ✅ 3本脏书flash全量OCR完成（2026-03-22）
- ✅ L0累计突破19,000条（2026-03-22）
- ✅ 架构文档v5发布（2026-03-22）

## 待办队列

P0（进行中）：
- Stage4第三批+第五批10本（CC在跑）
- 3本脏书Stage1收尾（Codex在跑）

P1（待启动）：
- 3本脏书Stage4
- L0收官批10本（第六批+第九批）flash OCR全链路

P2（L0完成后）：
- Neo4j搭建 + L0导入
- 外部数据库导入（FoodKG/USDA → L2a）
- Stage5食谱提取（Step A结构 + Step B L0绑定）
- Agentic Graph RAG MVP

P3（第二阶段）：
- FT风味层 + L6翻译层
- Graphiti L3-personal
- 用户贡献食谱自动L0绑定
- 自主进化闭环

---

## 技术栈

| 组件 | 选型 | 状态 |
|------|------|------|
| OCR | qwen3.5-flash（DashScope） | ✅ |
| 文本切分 | qwen3.5:2b Ollama | ✅ |
| 食谱提取 | qwen3.5（Ollama本地） | ✅ |
| Embedding | qwen3-embedding:8b (本地Ollama) | ✅ |
| L0蒸馏 | Opus 4.6（代理API） | ✅ |
| Agent LLM | Sonnet 4.6 Thinking | ✅ |
| 深度推理 | Opus 4.6 | ✅ |
| Agent框架 | LangGraph | ✅ |
| 动态记忆 | Graphiti | ⏳ |
| 图数据库 | Neo4j 5.x（graph + vector） | ⏳ |

---

## 环境变量
```bash
export MINERU_API_KEY="..."
export DASHSCOPE_API_KEY="..."
export GEMINI_API_KEY="..."
export L0_API_ENDPOINT="http://1.95.142.151:3000"
export L0_API_KEY="..."
```
（真实值在 ~/.zshrc，不入库）

## GitHub
- 新仓库: https://github.com/hanny9494-ai/culinary-engine
- 旧仓库（参考）: https://github.com/hanny9494-ai/L0-systerm
- 本地数据: ~/culinary-engine/ (output/ symlink → l0-knowledge-engine)

---

## 配方Schema v1（ISA-88三段分离）

> 详见 docs/recipe_schema_v1.md

SubRecipe = process（做什么）+ formula（配多少）+ equipment（用什么）
Recipe = components + main_ingredients + garnish + refs + assembly

已验证：French Laundry / Tsuji / EMP / 手写粤菜 / 手写fusion 五种配方格式

---

## 架构演变讨论（v4方向，未实施）

> 详见 docs/arch_discussion_v4_20260316.docx

**当前执行：v3线性架构（不变）**
**终局方向：多维因果图谱 + 审美驱动 + 多Agent**

关键决策：
1. 先线性走通P0→P3，再升级P4多维重构
2. 审美层是需求驱动源（Goal节点动态组合）
3. 多Agent分工：诊断/创作/优化/知识/替换
4. 1159条原理中627条causal_chain已含因果边，入库时结构化解析即可
5. 配方Schema采用ISA-88三段分离：process/formula/equipment

---
## Stage5 食谱提取（Step A）

- ✅ Pilot验证通过（结构化/多组件/叙事型三种格式）
- ✅ flash vs 27b对比：flash快7倍，质量等同
- ✅ 合并prompt：chunk_type标注+食谱提取一步到位
- 🔄 42本书全量在跑（flash API，3并发自动轮转）
- 已完成: OFC, MC Vol2/3/4, Neurogastronomy
- 在跑: MC Vol1, SFAH, Ice Cream, Alinea
- 排队: 33本

### Pilot对比结果
| 指标 | 27b本地 | flash API |
|------|--------|-----------|
| test1 recipes | 2 | 2 |
| test1 时间 | 114.6s | 16.2s |
| test2 recipes | 5 | 5 |
| test2 时间 | 225.0s | 31.0s |
| test3 空返回 | ✅ | ✅ |

### 关键文件
- 脚本: scripts/stage5_recipe_extract.py
- 配置: config/stage5_batch1_books.json
- 产出: output/stage5_batch/（本地）

### 追加进展
- ⏳ 第二波23本：等Stage1完成后自动接上
- ⏳ 第三波17本编译md：需先切分再提取

**结论：flash比27b快7倍，质量等同，全量用flash。**

### 全量规模
| 批次 | 书数 | 来源 | 状态 |
|------|------|------|------|
| 第一波 | 12 | 已完成Stage4的旧书 | 🔄 在跑 |
| 第二波 | 23 | Stage4在跑+收官批 | ⏳ 等Stage1完成 |
| 第三波 | 17 | 编译md新书 | ⏳ 需先切分 |
| **总计** | **52** | | |

### 食谱Schema v2（决策#28）
纯配方JSON + Neo4j关系网。科学标注（key_science_points/derivations/l0_gaps）全部在Neo4j关系网，不嵌入食谱JSON。

### 两步架构
- **Step A（qwen3.5-flash，已验证）**：提取纯配方JSON + 同时标注chunk_type/topics
- **Step B（Opus，待做）**：找3-5个关键科学决策点，绑定L0，生成裂变推导

### 第三波17本新书清单
Crave, EMP Cookbook, EMP Next Chapter, Manresa, Baltic,
Meat Illustrated, Momofuku, Organum, Hand and Flowers,
Alinea, Bouchon, Core, Daniel, Japanese Farm Food,
Relae, Everlasting Meal, Whole Fish, French Laundry

流程：编译md → 2b切分 → flash提取食谱+标注（不做L0蒸馏）
---
