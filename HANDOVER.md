# 餐饮研发引擎 — 母对话交接文档 v3
> 更新时间: 2026-03-20
> 本文档供母对话迁移/续接使用

---

## 系统定位
- **目标用户**：专业厨师（粤菜/法餐/融合菜）
- **核心公式**：食材参数 × 风味目标 × 科学原理 = 无限食谱
- **仓库**：https://github.com/hanny9494-ai/culinary-engine
- **本地数据**：~/l0-knowledge-engine/

---

## 七层知识架构

| 层 | 名称 | 状态 |
|----|------|------|
| L0 | 科学原理图谱（17域） | 🔄 蒸馏中 |
| L1 | 设备实践参数层 | ⏳ |
| L2a | 天然食材参数库 | ⏳ |
| L2b | 食谱校准库 | ⏳ |
| L2c | 商业食材数据库 | ⏳ |
| FT | 风味目标库 | ⏳ |
| L3 | 推理引擎 | ⏳ |
| L6 | 翻译层（粤菜语言↔系统语言） | ⏳ |

---

## 当前进度总览

### 数据规模
- **Stage1 完成**：18本书，23,264 chunks
- **L0 原理库**：~4,994 条已通过质控（Stage3 690 + Stage4 Neuro 349 + Stage4 OFC 3,955）
- **Stage4 在跑**：mc_vol2/3/4 Phase B 进行中

### 书目处理状态

**已完成 Stage1 + Stage4（2本试跑完成）：**
- OFC：1,427 chunks → 3,955 条原理通过质控
- Neurogastronomy：613 chunks → 349 条原理通过质控

**已完成 Stage1，Stage4 Phase B 进行中（3本）：**
- mc_vol2：485 chunks
- mc_vol3：502 chunks
- mc_vol4：703 chunks

**已完成 Stage1（旧11本中剩余6本，等排队跑 Stage4）：**
- mc_vol1：2,148 chunks
- salt_fat_acid_heat：1,055 chunks
- ice_cream_flavor：217 chunks
- mouthfeel：1,162 chunks
- flavorama：1,159 chunks
- science_of_spice：1,136 chunks
- professional_baking：3,434 chunks

**第三批 — Stage1 完成，有 chunk_type 字段（7本）：**
- food_lab：2,225 smart chunks（48 failures）
- science_good_cooking：2,865 smart chunks（21 failures）
- molecular_gastronomy：809 smart chunks（9 failures）
- noma_fermentation：651 smart chunks（1 failure）
- koji_alchemy：678 smart chunks（6 failures）
- ratio：500 smart chunks（7 failures）
- cooking_for_geeks：1,495 smart chunks（33 failures）

**第五批 — 待跑 Stage1（6本，L0密度最高）：**
- bread_hamelman：Bread (Hamelman) — pdf
- bread_science_yoshino：面包制作的科学 (吉野精一) — pdf
- chocolates_confections：Chocolates and Confections (Greweling) — pdf
- science_of_chocolate：The Science of Chocolate (Beckett) — pdf
- handbook_molecular_gastronomy：Handbook of Molecular Gastronomy — pdf
- dashi_umami：Dashi Umami Fermented Foods (JCA) — pdf

**第六批 — 待跑 Stage1（6本，L0补充+FT/L2b）：**
- flavor_equation：The Flavor Equation (Nik Sharma) — epub
- essentials_food_science：Essentials of Food Science — pdf
- french_sauces：法式料理酱汁宝典 — pdf
- flavor_bible：The Flavor Bible — mobi
- bocuse_cookbook：博古斯学院法式西餐烹饪宝典 — pdf
- phoenix_claws：Phoenix Claws and Jade Trees — pdf

**第四批候选（Stage4全量跑完后评估）：**
- Japanese Cooking (Tsuji) — 本地已有epub
- 中国烹饪原理 (陈光新) — 需找PDF
- 粤菜烹调技术 — 需找PDF
- 其他日本料理书 — Jeff 待确定

---

## 简化后的 Pipeline 流程

### 旧流程（已废弃）
Stage1 → Stage2（embedding匹配） → Stage3（题目引导蒸馏） → Stage3B → Stage4

### 新流程（当前执行）
**Stage1**（MinerU + Vision + Merge + TOC切分 + 9b标注） → **Stage4**（开放扫描，直接提取L0原理）

Stage2+3 不再对新书跑。全量完成后统计17域分布，仅对薄弱域定向补跑。

### Stage4 流程
1. **Phase A 预过滤**：
   - 有 chunk_type 的新书 → 直接读 science/mixed，跳过27b
   - 无 chunk_type 的旧书 → 27b 预过滤
2. **Phase B Opus 提取**：每 chunk 提取原子命题+因果链，一步到位
3. **Dedup**：内部去重 + 与 Stage3 交叉去重（numpy 矩阵运算，秒级）
4. **Quality**：valid_domain + has_citation + citation_in_chunk + valid_type + causal_chain_format + has_number(warning)

---

## 关键技术决策（所有agent必读）

1. **切分工具：qwen3.5:2b** — 已测试确认
2. **Stage3B独立判断proposition_type** — 不依赖阶段A
3. **v2题库17域已生效** — 新任务一律用v2
4. **OFC+MC原理保留双来源** — 不合并，597条都留
5. **L0是裁判** — 食谱和外部信息必须经L0校验才入库
6. **L6只翻译不判断** — 审美合理性判断在L3
7. **新书必须先TOC检测→人工审阅→再跑Stage1** — auto-chapter-split已禁用
8. **外部数据源ETL导入不蒸馏** — FoodKG dump + FoodAtlas，不逐个ETL
9. **中英映射用FoodOn+Wikidata** — 不自建
10. **Ollama串行** — 绕过http_proxy（trust_env=False）
11. **Stage2 embedding threshold=0.48**（Ollama用）
12. **配方×L0映射融入Stage5提取** — 不单独一步
13. **Stage4（原理）和Stage5（配方）分开扫描** — L0质量优先，原理先稳定
14. **Stage4遇到不属于17域的原理：domain填"unclassified"** — 跑完全量后统一评估
15. **Step2视觉识别默认启用smart_filter** — 只送table/equation/文字不足页，纯照片跳过（Food Lab验证：768→233页，省70%）
16. **Step5 9b标注新增chunk_type字段**（science/recipe/mixed/narrative）— 第三批书开始生效，已有11本不重跑
17. **新书不再跑Stage2+3题目引导蒸馏** — Stage4开放扫描做L0主力。理由：OFC验证Stage4产出是Stage3的7倍且重叠仅0.08%。全量完成后仅对薄弱域补跑
18. **has_number质控改为warning不阻塞** — 神经科学类书籍原理以机制描述为主，无数值参数是正常的
19. **dedup用numpy矩阵运算** — 4753×4753秒级完成，禁止Python双层for循环

---

## Stage4 实际成本数据

### OFC 实测
| 指标 | 值 |
|---|---|
| 每chunk avg input | 1,267 tokens |
| 每chunk avg output | 2,692 tokens |
| 每chunk avg total | 3,959 tokens |
| 875 chunks 总费用 | ¥65 |
| 净产出 | 3,955 条原理（质控后） |
| 每条有效原理成本 | ¥0.016 |

### 全量预估（30本书）
- Phase A 后约 15,000-20,000 chunks 送 Opus
- 预估费用：¥1,500-2,500
- 预算：¥5,000（绰绰有余）
- 预估产出：30,000-50,000 条原子命题

### 代理API费率（人民币）
- Input: ¥5/1M tokens
- Output: ¥25/1M tokens（约官方价1/22）

---

## Stage4 OFC 质控详情

| 阶段 | 数量 |
|---|---|
| Phase A 过滤 | 1,427 → 907 chunks (64%) |
| Phase B 提取 | 907 → 4,753 条原理 |
| Internal dedup | 移除 69 条 |
| Cross dedup (vs Stage3) | 仅 4 条重复 (0.08%) |
| Similar | 391 条 |
| Novel | 4,289 条 |
| Quality 通过 | 3,955 条 (84.5%) |

unclassified 原理（180条）暂时全部保留，跑完全量后统一评估是否扩域。

---

## 存储架构（三层）
- **热层 Neo4j**：L0原理+配方+映射，<10ms
- **温层 Weaviate**：embedding检索，~50ms
- **冷层**：FoodKG 6700万三元组 + FoodAtlas 23万条，100-500ms

---

## 优先级路线图

```
当前：
  Opus API → mc_vol2/3/4 Stage4 Phase B
  Ollama → 空闲，可跑第五批Stage1
  第三批7本 → 等Stage4队列

接下来：
  P0: 完成旧11本 Stage4 全量
  P0: 第三批7本 Stage4（有chunk_type，跳过27b）
  P0: 第五/六批 Stage1 → Stage4
  P1: 17域分布统计，薄弱域补跑Stage2+3
  P2: 存储层（Neo4j+Weaviate+FoodKG）
  P3: Stage5 配方提取
  P4: 双RAG + L3推理引擎
  P5: 终局架构v4
```

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

## 技术栈

| 组件 | 选型 | 状态 |
|---|---|---|
| PDF提取 | MinerU API + qwen3-vl-plus | ✅ |
| 文本切分 | qwen3.5:2b Ollama | ✅ |
| Topic标注 | qwen3.5:9b Ollama (think:false) + chunk_type | ✅ |
| Embedding | qwen3-embedding:8b (本地Ollama) | ✅ |
| Stage4预过滤 | 27b(旧书) / chunk_type(新书) | ✅ |
| 原理提取 | Claude Opus 4.6，代理API | ✅ |
| 去重 | numpy cosine matrix + threshold | ✅ |
| 向量库 | Weaviate | ⏳ |
| 图谱库 | Neo4j Docker | ⏳ |

---

## 关键文件路径

| 文件 | 路径 |
|---|---|
| v2题库 | data/l0_question_master_v2.json |
| Stage3原子命题 | output/stage3/ (690条) |
| Stage4产物 | output/stage4_{book_id}/ |
| API配置 | config/api.yaml |
| 书目注册 | config/books.yaml |
| 17域定义 | config/domains_v2.json |
| TOC配置 | config/mc_toc.json |
| Stage4脚本 | scripts/stage4_open_extract.py |
| Stage4去重 | scripts/stage4_dedup.py |
| Stage4质控 | scripts/stage4_quality.py |
| 路线图 | docs/roadmap_priorities_v2.md |
| Stage4设计 | docs/stage4_open_extract_design.md |
| Stage5设计 | docs/stage5_recipe_extract_design.md |
| 架构讨论 | docs/arch_discussion_v4_20260316.docx |

---

## 工作流程
母对话出工单/设计 → Jeff派给agent → Agent开发push分支 → Jeff把分支链接/diff贴给母对话 → 母对话review → Jeff merge
