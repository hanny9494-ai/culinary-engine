# Stage4 开放扫描 Pipeline 设计

> 母对话设计，2026-03-18
> 定位：补充306题驱动蒸馏的盲区，逐chunk扫描提取所有科学原理

---

## 1. 设计动机

当前 Stage3 是"问题驱动蒸馏"——306题决定能提取什么。局限：
1. 306题覆盖不到的知识点永远被漏掉
2. 每题只取 top-3 chunks 蒸馏一条原理，其余角度丢失
3. 题目本身是人类偏见的产物，天然偏向已知领域

开放扫描是"chunk驱动提取"——让 LLM 直接读每个 chunk，自主发现科学原理。
两者互补：306题蒸馏是骨架，开放扫描是肌肉。

参考：AnalogSeeker（2025）用类似方法从2,698个learning nodes蒸馏出15,310条标注数据。

---

## 2. Pipeline 总览

```
14,041 chunks（11本书，chunks_smart.json）
  ↓
Step 1: 预过滤（本地 qwen3.5:27b）
  → 判断每个 chunk 是否含可提取的科学命题
  → 过滤纯配方/叙事/历史/目录
  → 预计保留 ~9,000-11,000 条
  ↓
Step 2: 核心提取（Claude Opus 4.6，代理API）
  → 每个 chunk 提取 0-N 条完整原子命题（含因果链）
  → 一步到位：scientific_statement + proposition_type + causal_chain_steps + boundary
  ↓
Step 3: 去重（本地 qwen3-embedding:8b）
  → 与306题蒸馏原理 cosine 去重
  → 开放扫描内部 cosine 去重
  ↓
Step 4: 质控（本地 qwen3.5:27b + 规则）
  → 格式检查 + 科学性验证 + confidence评估
  ↓
输出: l0_principles_open.jsonl
```

---

## 3. 11本书全量清单

| 批次 | 书 | book_id | chunks | 科学价值侧重 |
|------|---|---------|--------|-------------|
| 第零批 | On Food and Cooking | ofc | 1,427 | 食品科学百科全书，覆盖最广 |
| 第零批 | MC Vol2 | mc_vol2 | 485 | 烹饪技法+设备物理 |
| 第零批 | MC Vol3 | mc_vol3 | 502 | 肉类/海鲜/植物科学 |
| 第零批 | MC Vol4 | mc_vol4 | 703 | 增稠/凝胶/乳化/泡沫 |
| 第一批 | MC Vol1 | mc_vol1 | 2,148 | 热力学/传热/化学反应基础 |
| 第一批 | Neurogastronomy | neurogastronomy | 613 | 嗅觉神经回路/风味感知 |
| 第一批 | Salt Fat Acid Heat | salt_fat_acid_heat | 1,055 | 盐酸脂肪热实操原理 |
| 第一批 | 冰淇淋风味学 | ice_cream_flavor | 217 | 配方平衡/糖脂转换/打发率 |
| 第二批 | Mouthfeel | mouthfeel | 1,162 | 质构流变学/口感科学 |
| 第二批 | Flavorama | flavorama | 1,159 | 风味创造方法论 |
| 第二批 | Science of Spice | science_of_spice | 1,136 | 香料化合物分类 |
| 第二批 | Professional Baking | professional_baking | 3,434 | 面筋发展/糖结晶/烘焙科学 |
| **合计** | | | **14,041** | |

---

## 4. 各步骤详细设计

### Step 1: 预过滤（本地 27b）

判断每个 chunk 是否含可提取的科学命题。过滤纯配方/叙事/历史。

输出 `stage4_filter.jsonl`，断点续跑。

### Step 2: 核心提取（Claude Opus 4.6）

对每个通过过滤的 chunk，一步到位提取完整原子命题（含因果链、边界条件、命题类型）。

输出 `stage4_raw.jsonl`，每50条保存进度，断点续跑。

### Step 3: 去重（本地 embedding）

- 与306题蒸馏原理 cosine 去重（>0.90 duplicate，0.75-0.90 similar）
- 开放扫描内部去重

### Step 4: 质控（本地 27b + 规则）

- 格式检查、数值参数检查、citation_quote 原文验证
- 输出最终 `l0_principles_open.jsonl`

---

## 5. 成本估算

代理API费率：¥5/1M input tokens，¥25/1M output tokens

| 场景 | Opus调用次数 | 预估成本 |
|------|-------------|---------|
| 试跑（Neurogastronomy 613 chunks） | ~400-500 | ¥15-20 |
| 全量（14,041 chunks过滤后） | ~8,500 | ¥200-280 |

预期产出：4,000-7,000 条新原子命题（去重后净增 3,000-5,000 条）

---

## 6. 脚本设计

```
scripts/
  stage4_open_extract.py    ← 主脚本（Step 1预过滤 + Step 2核心提取）
  stage4_dedup.py            ← 去重脚本（Step 3）
  stage4_quality.py          ← 质控脚本（Step 4）
```

---

## 7. 试跑计划

先跑 Neurogastronomy（613 chunks），评估：
- 新原理发现率
- 每chunk平均原理数
- 与306题蒸馏重叠率
- 17域覆盖率
- 成本验证

确认值得后全量跑。
