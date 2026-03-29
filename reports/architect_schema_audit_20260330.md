# Architecture Proposal: 七层架构合理性审查 + Schema 定稿状态
> 日期: 2026-03-30
> Architect Agent

---

## 1. 架构合理性评估

### 1.1 总体评价

七层架构在概念层面是合理的。L0 科学原理作为裁判层、L2a/L2b/L2c 作为数据层、L3 作为推理层、L6 作为翻译层——这个分层逻辑清晰，职责分离明确。

但在**实现层面**存在若干需要明确的问题。

### 1.2 数据流分析

**正向流（蒸馏→入库→推理）：**
```
书籍 PDF → OCR → 切分 → 标注 → L0 蒸馏 (Stage4)
                                    ↓
                              L0 原理图谱 (34,355条去重后)
                                    ↓
书籍 PDF → OCR → 切分 → L2b 食谱提取 (Stage5) → Step B 增强
                                    ↓
外部数据 → ETL → L2a 食材参数
                                    ↓
                              L3 推理引擎 (Neo4j + LangGraph)
                                    ↓
                              L6 翻译层 → 用户输出
```

**评估：正向流合理，无循环依赖。**

### 1.3 层间依赖关系

| 依赖方向 | 说明 | 状态 |
|---|---|---|
| L2b Step B → L0 | 食谱绑定科学原理 | 设计已完成，待实现 |
| L2b Step B → L2a | 食谱食材标准化 → L2a atom | 设计已完成，待实现 |
| L3 → L0 + L2a + L2b | 推理引擎消费所有数据层 | 设计阶段 |
| L6 → 所有层 | 翻译层需要所有中英对照 | 未开始 |
| FT → L0 (taste_perception, aroma_volatiles) | 风味目标基于科学原理 | 无 schema |
| L1 → L0 | 设备参数是原理的实例化 | 无 schema |

**无循环依赖。** 但 L2b Step B 同时依赖 L0 和 L2a，意味着这两层必须先就绪。

### 1.4 "L0 是裁判" 原则的实现矛盾

**概念上没问题，但实现上有两个隐含问题：**

1. **校验时机**：L2b Step B 设计中，是让 LLM 在提取时就绑定 L0 原理 ID。这意味着 LLM 需要"知道" L0 库的内容。e2e_inference_design.md 提出了 "科学决策点" 的概念，用 Neo4j 向量检索匹配 L0。这个方案合理，但要注意：Step B 生成的 `l0_principle_ids` 绑定的是**预计算**结果，不是实时校验。如果 L0 库后续更新，旧绑定不会自动刷新。

2. **L0 覆盖盲区**：34,355 条 L0 原理来自 27 本书，域分布不均。taste_perception 和 aroma_volatiles 条目可能不够支撑 FT 层。这不是架构问题，是数据完整性问题。

**建议**：绑定关系用 Neo4j 关系（GOVERNED_BY）表达，而非硬编码 ID 数组。这样 L0 更新时可以重新跑匹配，不需要重写 L2b 数据。

---

## 2. 各层 Schema 状态

### 2.1 L0 科学原理图谱

**数据规模**：34,355 条（去重后，来自 27 本书的 stage4 输出）

**实际 Schema（l0_principles_open.jsonl）**：
```json
{
  "id": "ofc_open_0001",
  "scientific_statement": "...",
  "causal_chain": ["cause → mechanism → effect"],
  "parameters": [{"name": "...", "range": "...", "unit": "..."}],
  "domain": "protein_science",
  "confidence": 0.85,
  "source_chunk_id": "...",
  "book_id": "ofc"
}
```

**字段一致性**：7 个字段在所有 27 本书中一致，无缺失字段。

**评估**：
- Schema **已定稿**，无需修改
- `id` 格式为 `{book_id}_open_{序号}`，全局唯一
- `causal_chain` 是字符串数组（箭头链），不是结构化因果图。入 Neo4j 时需要解析
- `parameters` 结构良好（name/range/unit），直接可用

**问题**：
- `causal_chain` 的箭头链格式需要在入 Neo4j 时解析为节点和关系。建议 coder 写一个 `parse_causal_chain()` 工具函数
- 没有 `tags` 或 `keywords` 字段，全文检索依赖 `scientific_statement` + Neo4j 向量索引

### 2.2 L2a 食材参数库

**Schema v2（docs/l2a_atom_schema_v2.md）已定稿**，结构如下：

```
atom 层（最细粒度）:
  atom_id, names{en,zh,aliases}, taxonomy{species,family,part,grade},
  composition{water,protein,fat,carb,fiber,ash,sugar_profile,amino_acid_profile...},
  sensory{taste_tags,aroma_tags,texture_tags,flavor_intensity},
  seasonal{peak_months,available_months},
  sourcing{regions,price_range_cny_per_kg},
  culinary{common_cuts,cooking_affinity,classic_pairings},
  science_refs[l0_principle_ids]

canonical 层（归一化）:
  canonical_id, canonical_name, atom_ids[], category
```

**评估**：
- Schema v2 设计合理，atom/canonical 双层结构适合 18,951 → 3-4k 归一化
- `science_refs` 字段用 L0 principle ID 数组关联——建议改为 Neo4j 关系
- **缺少一个关键字段**：`usda_ndb_no` 或 `foodb_id`，用于与外部数据库对齐
- 归一化脚本的输入是 Stage5 食谱中的原始食材字符串（约 18,951 个唯一字符串），输出是 atom + canonical 两级结构

### 2.3 L2b 食谱校准库

**Step A（当前 Stage5 输出）Schema**：
```json
{
  "recipe_name": "...",
  "source": {"book_id": "...", "chunk_ids": [...]},
  "formula": [
    {"ingredient": "...", "quantity": "...", "unit": "...", "prep": "..."}
  ],
  "process_steps": [
    {"step": 1, "action": "...", "details": "...", "time": "...", "temp": "..."}
  ],
  "equipment": ["..."],
  "yield": "...",
  "category": "...",
  "tags": [...]
}
```

**实际数据规模**：29 本书，29,249 条食谱

**Step A Schema 一致性问题**：
- 不同书的 recipe 字段不完全一致。有些有 `equipment`，有些没有
- `formula` 中 ingredient 是原始字符串，未标准化
- `process_steps` 中的 time/temp 有些是字符串（"3-5 minutes"），有些为 null
- **缺少 `recipe_id` 字段**——目前靠 `recipe_name` + `book_id` 组合去重，不够可靠

**Step B（增强设计）**：
在 Step A 基础上增加：
```json
{
  "science_decision_points": [
    {
      "step_ref": 3,
      "decision": "Maillard reaction onset",
      "l0_principle_ids": ["..."],
      "parameters": {"temp": "140-165C", "time": "2-3min"},
      "why": "..."
    }
  ],
  "flavor_profile": {
    "primary_tastes": [...],
    "aroma_notes": [...],
    "texture_goals": [...]
  },
  "ingredient_atoms": [
    {"raw": "2 cloves garlic", "atom_id": "garlic_fresh_clove", "canonical_id": "garlic"}
  ]
}
```

**评估**：
- Step B 设计合理，`science_decision_points` 是系统的核心价值
- **但 Step B 同时做三件事**（绑 L0 + 绑 L2a + 提取 flavor），建议拆成独立子步骤
- `recipe_id` 必须在 Step A 就分配，不能等到 Step B

### 2.4 FT 风味目标库

**当前状态：无 Schema，无数据。**

**建议 Schema**：
```json
{
  "ft_id": "ft_001",
  "aesthetic_term": {"zh": "镬气", "en": "wok hei"},
  "sensory_parameters": {
    "primary_taste": {"sweet": 0.2, "salty": 0.3, "umami": 0.6, "sour": 0.1, "bitter": 0.05},
    "aroma_descriptors": ["smoky", "caramelized", "charred"],
    "texture_descriptors": ["crisp_exterior", "tender_interior"],
    "temperature": "hot_serve",
    "mouthfeel": ["oily_coating"]
  },
  "l0_principles": ["maillard_xxx", "lipid_oxidation_xxx"],
  "typical_techniques": ["high_heat_stir_fry"],
  "source": "expert_definition"
}
```

**优先级**：FT 不阻塞 L2b Step B。

### 2.5 L1 / L2c / L3 / L6

均不阻塞当前工作。L3 设计文档已有（e2e_inference_design.md），接口未形式化。

---

## 3. 关键风险

### R1: recipe_id 缺失导致后续关联困难
**严重度：高**
29,249 条食谱目前无唯一 ID。Step B 增强、Neo4j 入库、L0 绑定都依赖稳定的 recipe_id。
**建议**：在 Step B 之前先跑一遍 ID 分配脚本，格式 `{book_id}_r{seq:04d}`，写回 Step A 文件。

### R2: L0-L2b 绑定的可维护性
**严重度：中**
Step B 把 `l0_principle_ids` 硬编码进食谱 JSON。如果 L0 库更新，这些 ID 会失效。
**建议**：绑定关系在 Neo4j 中用 `(:Recipe)-[:GOVERNED_BY]->(:Principle)` 关系表达，JSON 中只保留快照引用。

### R3: 食材字符串归一化的歧义
**严重度：中**
同名异物（"stock" = 高汤/库存？）和异名同物（"scallion" / "green onion" / "spring onion"）会导致错误归并。
**建议**：归一化脚本必须输出 confidence score，低置信度走人工审核。

### R4: Neo4j 规模估算
**严重度：低**
~450k 节点 + ~450k 关系。Neo4j 5.x 轻松处理。**无性能风险。**

### R5: Step B 三合一的质量风险
**严重度：中**
一次 LLM 调用同时做三件事，如果任一子任务出错，整条数据需要重跑。
**建议**：至少把 L2a ingredient 归一化拆出来作为独立步骤。

---

## 4. 建议行动项（开始写代码之前）

### 必须做（阻塞 Step B 和 L2a 归一化）

1. **分配 recipe_id**：遍历 stage5_batch 所有文件，给每条食谱分配 `{book_id}_r{seq:04d}` ID
2. **L2a schema v2 加 external_ids**：`external_ids: {usda_ndb_no?, foodb_id?, foodon_id?}` 可选字段
3. **确认 Step B 是否拆步骤**：pilot 10 条食谱对比质量再定

### 建议做

4. **统一 Step A 字段默认值**：缺失的 equipment 给 `[]`，缺失的 time/temp 给 `null`
5. **定义 Neo4j 关系类型**：`USES`, `GOVERNED_BY`, `BELONGS_TO_CANONICAL`, `CAUSES`
6. **FT schema 初稿**

---

## 5. 需要 Jeff 决策

1. **recipe_id 格式**：`{book_id}_r{seq:04d}` vs content hash？推荐前者
2. **Step B 拆不拆**：三合一 vs 拆子步骤？推荐先 pilot 10 条对比
3. **L2a external_ids**：是否加入？推荐加（optional）
4. **Neo4j 核心关系类型**：现在定稿 4 个核心关系？还是等入库再迭代？
