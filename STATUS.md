# 餐饮研发引擎 — 项目状态 v3.2

> 母对话维护此文件，agent不许修改
> 新仓库: https://github.com/hanny9494-ai/culinary-engine

---

## 系统定位
- **目标用户**：专业厨师 / 餐饮老板 / 研发团队
- **核心能力**：因果链科学推理 + 粤菜审美转化（不是配方检索）
- **核心公式**：食材参数 × 风味目标 × 科学原理 = 无限食谱
- **架构文档**：docs/culinary_engine_architecture_v3.docx

---

## 七层知识架构

| 层 | 名称 | 定位 | 状态 |
|----|------|------|------|
| L0 | 科学原理图谱 | "为什么会发生" — 因果链+参数边界+17域 | 🔄 Stage3B完成，阶段B待做 |
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
| OFC Stage 1-3 | ✅ 完成 | 303条L0原理 |
| MC Vol2/3/4 Stage1 | ✅ 完成 | 485+502+703 = 1690 chunks |
| MC Stage2 匹配 | ✅ 完成 | 99.4% matched (3117 chunks × 306题) |
| MC Stage3 蒸馏 | ✅ 完成 | 294条新原理，零失败 |
| OFC+MC 合计 | ✅ 完成 | **597条L0原理**（保留双来源不合并） |
| Stage3B 因果链 | ✅ 完成 | **597→1159条原子命题**（627因果链/309事实/188复合条件/35数学定律） |
| 306题→17域重映射 | ✅ 完成 | 172题变更，14条人工审核，l0_question_master_v2.json |
| 阶段B: 原理domain刷新 | ⏳ 待做 | 1159条标签→17域 |
| 冰淇淋风味学 Stage1 | 🔄 进行中 | 128 chunks已落盘，resume跑中 |
| Pipeline自动化 | ✅ 完成 | 新仓库全部merge |
| auto-chapter-split修复 | ✅ 完成 | 无TOC书按heading自动切分 |
| 架构文档v3 | ✅ 完成 | 七层+L2c+冷启动+自学习闭环 |

---

## L0原理库

| 来源 | 原理数 | Stage3B后 | 状态 |
|------|--------|-----------|------|
| OFC (On Food and Cooking) | 303条 | → 拆分后含在1159条中 | ✅ |
| MC (Modernist Cuisine Vol2/3/4) | 294条 | → 拆分后含在1159条中 | ✅ |
| **合计** | **597条原始** | **1159条原子命题** | 目标1500+ |

命题类型分布:
- causal_chain: 627条 (54%)
- fact_atom: 309条 (27%)
- compound_condition: 188条 (16%)
- mathematical_law: 35条 (3%)

质量指标:
- 低置信度 (<0.7): 243条（其中195条是fallback=0.5解析问题，内容质量OK）
- 真低置信度: 48条
- OFC与MC强互补（机制 vs 精确参数）

---

## 题目库

| 版本 | 题数 | 域数 | 状态 |
|------|------|------|------|
| v1 (旧) | 306 | 14域 | 归档 |
| **v2 (当前)** | **306** | **17域** | ✅ 生效 |

17域薄弱域:
- mass_transfer: 4题 ← 需补题
- oxidation_reduction: 5题 ← 需补题

---

## Chunks 总量

| 书目 | chunks | 标注域 | 状态 |
|------|--------|--------|------|
| OFC | 1,427 | 旧14域 | ✅ |
| MC Vol2 | 485 | 旧14域 | ✅ |
| MC Vol3 | 502 | 旧14域 | ✅ |
| MC Vol4 | 703 | 旧14域 | ✅ |
| MC Vol1 | 2,148 | 17域 | ✅ |
| Neurogastronomy | 613 | 17域 | ✅ |
| Salt Fat Acid Heat | 1,055 | 17域 | ✅ |
| Mouthfeel | 🔄 | 17域 | Stage1重跑中(有TOC) |
| Flavorama | 🔄 | 17域 | Stage1重跑中(有TOC) |
| Science of Spice | 🔄 | 17域 | Stage1重跑中(有TOC) |
| Professional Baking | 🔄 | 17域 | Stage1重跑中(有TOC) |
| **合计** | **6,933+** | | **目标10,000+** |

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
3. **v2题库17域已生效** — 新书用v2，旧原理用阶段B批量刷标签
4. **MC Vol2/3/4的9b标注不重跑** — domain迁移在下游处理
5. **OFC+MC原理保留双来源** — 不合并，597条都留
6. **L0是裁判** — 食谱和外部信息必须经L0校验才入库
7. **L6只翻译不判断** — 审美合理性判断在L3
8. **查不到就问** — 不猜测，引导用户提供食材/工艺/口感目标
9. **新书必须先TOC检测→人工审阅→再跑Stage1** — auto-chapter-split已禁用（pipeline强制检查mc_toc.json）
10. **外部数据源ETL导入不蒸馏** — FoodAtlas/FlavorGraph等直接导入Neo4j
11. **Ollama不能并发跑多本书** — 9b标注必须串行，2b切分同理；MinerU/Vision(API)可并行
12. **Ollama调用必须绕过http_proxy** — 本机有代理127.0.0.1:7890，ollama_client.py已用trust_env=False

---

## 待完成任务

| 任务 | 优先级 | 说明 |
|------|--------|------|
| 冰淇淋Stage1完成 | P0 | 🔄 resume跑中 |
| 阶段B: 1159条domain→17域 | P1 | 批量刷标签 |
| 冰淇淋Stage2+3 | P1 | Stage1完成后用v2题库跑 |
| 195条fallback confidence补刷 | P2 | 重新解析JSON，不重新蒸馏 |
| mass_transfer/oxidation_reduction补题 | P2 | 各补5-8题 |
| 外部数据源第一批ETL | P2 | FoodAtlas+FlavorGraph+FooDB+USDA |
| MC Vol1 (epub→PDF→Stage1) | P2 | equipment_physics主要来源 |
| Mouthfeel | P2 | texture_rheology深度 |
| Salt Fat Acid Heat | P2 | 本地已有PDF |
| Neo4j搭建+实体对齐 | P3 | 原理入库，跨书因果链连接 |
| Weaviate填充 | P3 | embedding检索 |
| scan_low_hit补题 | P3 | 发现新知识盲区 |
| 外部数据源第二批ETL | P3 | FlavorDB2+FoodOn |

---

## 技术栈

| 组件 | 选型 | 状态 |
|------|------|------|
| PDF提取 | MinerU API + qwen3-vl-plus | ✅ |
| 文本切分 | qwen3.5:2b Ollama | ✅ |
| Topic标注 | qwen3.5:9b Ollama (think:false) | ✅ |
| 原理蒸馏 | Claude Opus 4.6，代理API | ✅ |
| 因果链蒸馏 | Claude Sonnet 4.6 | ✅ |
| Embedding | qwen3-embedding:8b (本地) | ✅ |
| 向量库 | Weaviate | ⏳ |
| 图谱库 | Neo4j Docker | ⏳ |

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
- 本地数据: ~/l0-knowledge-engine/

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

## 配方Schema v1（ISA-88三段分离）

> 详见 docs/recipe_schema_v1.md

SubRecipe = process（做什么）+ formula（配多少）+ equipment（用什么）
Recipe = components + main_ingredients + garnish + refs + assembly

已验证：French Laundry / Tsuji / EMP / 手写粤菜 / 手写fusion 五种配方格式
