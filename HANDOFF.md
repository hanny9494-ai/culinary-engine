# Agent交接文档

> 最后更新: 2026-03-16
> 母对话维护此文件

---

## 当前活跃任务

### Stage3B 因果链增强（进行中）
- 输入: `~/l0-knowledge-engine/output/stage3/l0_principles_all.jsonl` (597条)
- 输出: `~/l0-knowledge-engine/output/stage3/l0_principles_v2.jsonl`
- 模型: claude-sonnet-4-6
- 配置: config/api.yaml (causal字段已改为sonnet)

### 冰淇淋风味学 Stage1（进行中）
- book_id: ice_cream_flavor
- 输出目录: `~/l0-knowledge-engine/output/ice_cream_flavor/`
- 注意: auto-chapter-split已修复，按heading自动切分

---

## 下一步任务队列

### P1: 阶段B — 597条原理domain→v2域
- 等Stage3B完成后做
- 输入: `l0_principles_v2.jsonl` + `question_domain_remap.json`
- 逻辑: 每条原理的 `question_id` 对应到 remap 表的 `new_domain`

### P1: 冰淇淋Stage2+3
- 等Stage1完成后做
- **必须用v2题库**: `data/l0_question_master_v2.json`
- Stage2要合并已有OFC+MC chunks一起匹配

### P2: 补题
- mass_transfer: 当前4题，补到10-12题
- oxidation_reduction: 当前5题，补到10-12题
- salt_acid_chemistry: 当前8题，补到10-12题
- Jeff审核后入库

---

## 关键文件路径

| 文件 | 路径 | 说明 |
|------|------|------|
| v2题库 | data/l0_question_master_v2.json | 306题v2域 ✅ |
| v1题库(归档) | ~/l0-knowledge-engine/data/l0_question_master.json | 306题旧14域 |
| domain映射 | data/question_domain_remap.json | 旧→新域变更记录 |
| OFC原理 | ~/l0-knowledge-engine/output/stage3/l0_principles_fixed.jsonl | 303条 |
| MC原理 | ~/l0-knowledge-engine/output/stage3_mc/l0_principles.jsonl | 294条 |
| 合并原理 | ~/l0-knowledge-engine/output/stage3/l0_principles_all.jsonl | 597条 |
| API配置 | config/api.yaml | |
| 书目注册 | config/books.yaml | |
| v2域定义 | config/domains_v2.json | 当前配置17域 |
| MC TOC | config/mc_toc.json | |

---

## 技术决策速查

1. v2题库已生效，新任务一律用v2
2. 旧原理不重新蒸馏，只刷domain标签
3. OFC+MC双来源保留，不合并
4. 无TOC书按heading自动切分（已修复）
5. Stage3B逐条独立跑，不需要跨书
6. Neo4j入库时做跨书实体对齐
