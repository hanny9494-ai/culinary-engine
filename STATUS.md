# 餐饮研发引擎 — 项目状态 v3.3

> 母对话维护此文件，agent不许修改
> 新仓库: https://github.com/hanny9494-ai/culinary-engine
> 更新时间: 2026-03-18

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
| L0 | 科学原理图谱 | "为什么会发生" — 因果链+参数边界+17域 | 🔄 蒸馏中（11本书） |
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
| Stage2 匹配 | 🔄 进行中 | 7本新书 13,824 chunks × 306题，Ollama qwen3-embedding:8b |
| 冰淇淋 Stage2 | ⏳ 待做 | 等7本完成后加入，全量 ~14,041 chunks |
| 全量 Stage3 蒸馏 | ⏳ 待做 | 等Stage2全部完成后，306题全量重跑 |
| Pipeline自动化 | ✅ 完成 | 新仓库全部merge，TOC强制检查已加 |
| 架构文档v3 | ✅ 完成 | 七层+L2c+冷启动+自学习闭环 |

---

## L0原理库

| 来源 | 原理数 | Stage3B后 | 状态 |
|------|--------|-----------|------|
| OFC (On Food and Cooking) | 303条 | → 拆分后含在1,159条中 | ✅ |
| MC (Modernist Cuisine Vol2/3/4) | 294条 | → 拆分后含在1,159条中 | ✅ |
| **已有合计** | **597条原始** | **1,159条原子命题** | |
| 11本书全量蒸馏后 | — | 预计2,500-4,000条 | ⏳ 待蒸馏 |

命题类型分布（当前1,159条）:
- causal_chain: 627条 (54%)
- fact_atom: 309条 (27%)
- compound_condition: 188条 (16%)
- mathematical_law: 35条 (3%)

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

## Chunks 总量（11本书）

| 书目 | book_id | chunks | 标注域 | 状态 |
|------|---------|--------|--------|------|
| OFC | ofc | 1,427 | 旧14域 | ✅ |
| MC Vol2 | mc_vol2 | 485 | 旧14域 | ✅ |
| MC Vol3 | mc_vol3 | 502 | 旧14域 | ✅ |
| MC Vol4 | mc_vol4 | 703 | 旧14域 | ✅ |
| MC Vol1 | mc_vol1 | 2,148 | 17域 | ✅ |
| Neurogastronomy | neurogastronomy | 613 | 17域 | ✅ |
| Salt Fat Acid Heat | salt_fat_acid_heat | 1,055 | 17域 | ✅ |
| 冰淇淋风味学 | ice_cream_flavor | 217 | 17域 | ✅ |
| Mouthfeel | mouthfeel | 1,162 | 17域 | ✅ |
| Flavorama | flavorama | 1,159 | 17域 | ✅ |
| Science of Spice | science_of_spice | 1,136 | 17域 | ✅ |
| Professional Baking | professional_baking | 3,434 | 17域 | ✅ |
| **合计** | | **14,041** | | |

Topics 分布验证：
- Mouthfeel → texture_rheology 主导 ✅
- Flavorama → taste_perception + aroma_volatiles ✅
- Science of Spice → aroma_volatiles 主导 ✅
- Professional Baking → texture_rheology + carbohydrate ✅

已知问题：TOC heading匹配偏移（大部分chunks归到最后匹配章节），不影响Stage2/3。

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

---

## 当前执行与下一步

### 正在执行
- [ ] Stage2：7本新书 embedding 匹配中（13,824 chunks × 306题）
- [ ] 冰淇淋 Stage2 待跑（完成后全量 14,041 chunks）

### 蒸馏完成后立即做（P2）
- [ ] 全量 Stage3 蒸馏：306题 × 全量 chunks → Claude Opus 4.6（预计 ~$25，~1小时）
- [ ] 全量 Stage3B 因果链增强 → Claude Sonnet 4.6（预计 ~$5-8，~1小时）
- [ ] 195条 fallback confidence 补刷（重新解析JSON，不重新蒸馏）
- [ ] scan_low_hit 补题扫描：发现知识盲区 → candidate_questions.json → 人工审核
- [ ] mass_transfer / oxidation_reduction 定向补题（各5-8题）

### 原理库稳定后（P3）
- [ ] Neo4j 搭建 + 实体对齐：原子命题入图谱，causal_chain解析为节点+边
- [ ] Weaviate 填充：embedding 向量检索层
- [ ] 外部数据源第一批 ETL：FoodAtlas + FlavorGraph + FooDB + USDA API
- [ ] 中英食材名映射表（一次建成，所有数据源共用）

### 终局方向（P4，等P0-P3走通后）
- [ ] 双RAG原型（Neo4j图谱检索 + Weaviate向量检索）
- [ ] L3推理引擎雏形
- [ ] v4多维因果图谱 + 审美驱动 + 多Agent架构
- [ ] 详见：docs/arch_discussion_v4_20260316.docx

---

## 技术栈

| 组件 | 选型 | 状态 |
|------|------|------|
| PDF提取 | MinerU API + qwen3-vl-plus | ✅ |
| 文本切分 | qwen3.5:2b Ollama | ✅ |
| Topic标注 | qwen3.5:9b Ollama (think:false) | ✅ |
| Embedding | qwen3-embedding:8b (本地Ollama) | ✅ |
| 原理蒸馏 | Claude Opus 4.6，代理API | ✅ |
| 因果链蒸馏 | Claude Sonnet 4.6 | ✅ |
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
