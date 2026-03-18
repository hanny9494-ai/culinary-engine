# 餐饮研发引擎 — 项目状态 v3.4

> 母对话维护此文件，agent不许修改
> 新仓库: https://github.com/hanny9494-ai/culinary-engine
> 更新时间: 2026-03-19

---

## 系统定位
- **目标用户**：专业厨师 / 餐饮老板 / 研发团队
- **核心能力**：因果链科学推理 + 粤菜审美转化（不是配方检索）
- **核心公式**：食材参数 × 风味目标 × 科学原理 = 无限食谱

---

## 七层知识架构

| 层 | 名称 | 状态 |
|----|------|------|
| L0 | 科学原理图谱（因果链+参数边界+17域） | 🔄 Stage4开放扫描中 |
| L1 | 设备实践参数层 | ⏳ 待建 |
| L2a | 天然食材参数库 | ⏳ 待建 |
| L2b | 食谱校准库 | ⏳ 待建 |
| L2c | 商业食材数据库 | ⏳ 待建 |
| FT | 风味目标库 | ⏳ 待建 |
| L3 | 推理引擎 | ⏳ 待建 |
| L6 | 翻译层（粤菜语言↔系统语言） | ⏳ 待建 |

---

## 当前进度

| 阶段 | 状态 | 说明 |
|------|------|------|
| 11本书 Stage1 | ✅ 完成 | 14,041 chunks |
| Stage2 全量匹配 | ✅ 完成 | 306/306 100%匹配 |
| Stage3 全量蒸馏 | ✅ 完成 | 305条原理（12本书统一蒸馏） |
| Stage3B 因果链 | ✅ 完成 | 690条原子命题 |
| 阶段B domain→17域 | ✅ 完成 | |
| Stage4 开放扫描 | 🔄 进行中 | Neurogastronomy试跑+第零批Phase A |

---

## L0原理库

| 版本 | 原理数 | 原子命题 | 状态 |
|------|--------|---------|------|
| 旧版（OFC+MC分开跑） | 597 | 1,159 | 归档 |
| **新版（12本书统一蒸馏）** | **305** | **690** | ✅ 骨架完成 |
| Stage4开放扫描后 | — | 预计5,000-8,000 | 🔄 进行中 |

新版690条命题类型：causal_chain 412(60%) / compound_condition 175(25%) / fact_atom 73(11%) / mathematical_law 29(4%)
低置信度仅27条（旧版243条），质量显著提升。

---

## Chunks（11本书）

| 书 | chunks | 状态 |
|----|--------|------|
| OFC | 1,427 | ✅ |
| MC Vol2/3/4 | 1,690 | ✅ |
| MC Vol1 | 2,148 | ✅ |
| Neurogastronomy | 613 | ✅ |
| SFAH | 1,055 | ✅ |
| 冰淇淋风味学 | 217 | ✅ |
| Mouthfeel | 1,162 | ✅ |
| Flavorama | 1,159 | ✅ |
| Science of Spice | 1,136 | ✅ |
| Professional Baking | 3,434 | ✅ |
| **合计** | **14,041** | |

---

## Stage4 开放扫描（进行中）

27b预过滤 → Opus 4.6核心提取 → embedding去重 → 27b质控
- Neurogastronomy试跑：613→289通过（47%），Phase B进行中
- 第零批Phase A：OFC+MC Vol2/3/4 预过滤中
- 全量预估：¥200-280，产出3,000-5,000条净增

---

## 路线图（P0-P6）

详见 docs/roadmap_priorities_v2.md

| 优先级 | 任务 | 状态 |
|--------|------|------|
| P0 | L0骨架蒸馏 | ✅ 完成（690条） |
| P1 | L0开放扫描Stage4 | 🔄 进行中 |
| P2 | 补题+confidence补刷 | ⏳ |
| P3 | 存储层+外部数据（FoodKG/FoodOn） | ⏳ |
| P4 | 配方提取Stage5 | ⏳ |
| P5 | 双RAG+L3推理引擎 | ⏳ |
| P6 | 终局架构v4 | ⏳ |

---

## 关键技术决策（所有agent必读）

1. 切分：qwen3.5:2b
2. 标注：qwen3.5:9b (think:false)
3. v2题库17域已生效
4. 新书必须TOC检测→人工审阅→再跑Stage1
5. L0是裁判，配方必须经L0校验
6. 27b做筛选，Opus做原理主力提取
7. Stage4（原理）和Stage5（配方）分开扫描
8. 外部数据用FoodKG dump+FoodAtlas导入，不逐个ETL
9. 中英映射用FoodOn+Wikidata，不自建
10. Ollama串行，绕过http_proxy(trust_env=False)
11. Stage2 Ollama embedding threshold=0.48
12. 配方×L0映射融入Stage5提取

---

## 技术栈

| 组件 | 选型 | 状态 |
|------|------|------|
| PDF提取 | MinerU API + qwen3-vl-plus | ✅ |
| 切分 | qwen3.5:2b Ollama | ✅ |
| 标注 | qwen3.5:9b Ollama | ✅ |
| 预过滤 | qwen3.5:27b Ollama | ✅ |
| Embedding | qwen3-embedding:8b | ✅ |
| 原理蒸馏 | Claude Opus 4.6 代理API | ✅ |
| 因果链 | Claude Sonnet 4.6 | ✅ |
| 向量库 | Weaviate | ⏳ |
| 图谱库 | Neo4j | ⏳ |
