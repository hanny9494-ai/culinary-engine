# Agent交接文档

> 最后更新: 2026-03-16
> 母对话维护此文件

---

## 当前活跃任务

### 冰淇淋风味学 Stage1（resume跑中）
- book_id: ice_cream_flavor
- 输出目录: ~/l0-knowledge-engine/output/ice_cream_flavor/
- 128 chunks已落盘，从断点续跑
- 注意: auto-chapter-split已修复，按heading自动切分

---

## 下一步任务队列

### P1: 阶段B — 1159条原理domain→17域
- 输入: data/stage3b/l0_principles_v2.jsonl
- 参照: data/question_domain_remap.json
- 逻辑: 每条原理的question_id对应到remap表的new_domain

### P1: 冰淇淋Stage2+3
- 等Stage1完成后做
- **必须用v2题库**: data/l0_question_master_v2.json（17域）
- Stage2要合并已有OFC+MC chunks一起匹配

### P2: 补题
- mass_transfer: 当前4题，补到10-12题
- oxidation_reduction: 当前5题，补到10-12题
- Jeff审核后入库

### P2: 外部数据源ETL（第一批）
- FoodAtlas → L2a+FT (GitHub TSV)
- FlavorGraph → FT (GitHub pickle/CSV)
- FooDB → L2a (CSV下载)
- USDA API → L2a+L2c (JSON API)
- 均不需要蒸馏，写ETL脚本直接导入
- 最大工作量: 中英食材名映射表

---

## 关键文件路径

| 文件 | 路径 | 说明 |
|------|------|------|
| v2题库 | data/l0_question_master_v2.json | 306题17域 ✅ |
| v1题库(归档) | data/l0_question_master.json | 306题旧14域 |
| domain映射 | data/question_domain_remap.json | 旧→新域变更记录 |
| Stage3B原子命题 | data/stage3b/l0_principles_v2.jsonl | 1159条 |
| 合并原理(Stage3B前) | data/stage3b/l0_principles_all.jsonl | 597条 |
| Stage3B报告 | data/stage3b/stage3b_report.txt | |
| OFC原理 | ~/l0-knowledge-engine/output/stage3/l0_principles_fixed.jsonl | 303条 |
| MC原理 | ~/l0-knowledge-engine/output/stage3_mc/l0_principles.jsonl | 294条 |
| API配置 | config/api.yaml | |
| 书目注册 | config/books.yaml | |
| 17域定义 | config/domains_v2.json | |
| MC TOC | config/mc_toc.json | |

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
2. 旧原理不重新蒸馏，只刷domain标签（阶段B）
3. OFC+MC双来源保留，不合并
4. 无TOC书按heading自动切分（已修复）
5. Stage3B逐条独立跑，不需要跨书
6. Neo4j入库时做跨书实体对齐
7. 外部数据源ETL直接导入，不走蒸馏pipeline
8. 中英食材名映射表建一次后所有数据源共用
