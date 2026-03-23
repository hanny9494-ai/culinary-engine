# 文件审计报告 — 2026-03-23

## 一、L0 主线：21 本已完成，14 本待处理

### 已完成 Stage4 的 21 本（34,355 条 L0 QC 通过）

| # | 书 | raw | dedup | QC通过 | 通过率 |
|---|---|---|---|---|---|
| 1 | ofc | 4,868 | 4,680 | 3,955 | 81% |
| 2 | mc_vol1 | 3,983 | 3,314 | 3,110 | 78% |
| 3 | mc_vol2 | 1,085 | 938 | 893 | 82% |
| 4 | mc_vol3 | 1,194 | 1,123 | 1,059 | 89% |
| 5 | mc_vol4 | 1,267 | 1,166 | 1,034 | 82% |
| 6 | science_good_cooking | 4,823 | 4,229 | 3,806 | 79% |
| 7 | food_lab | 3,386 | 2,785 | 2,242 | 66% |
| 8 | mouthfeel | 3,021 | 2,605 | 2,410 | 80% |
| 9 | professional_baking | 3,134 | 2,458 | 2,136 | 68% |
| 10 | cooking_for_geeks | 3,629 | 3,057 | 2,266 | 62% |
| 11 | molecular_gastronomy | 2,439 | 2,246 | 1,951 | 80% |
| 12 | bread_hamelman | 2,612 | 1,971 | 1,669 | 64% |
| 13 | science_of_chocolate | 2,319 | 1,871 | 1,577 | 68% |
| 14 | flavorama | 2,012 | 1,689 | 1,258 | 63% |
| 15 | koji_alchemy | 1,414 | 1,178 | 978 | 69% |
| 16 | science_of_spice | 1,604 | 1,052 | 960 | 60% |
| 17 | salt_fat_acid_heat | 1,348 | 1,163 | 910 | 68% |
| 18 | noma_fermentation | 1,213 | 1,061 | 850 | 70% |
| 19 | bread_science_yoshino | 657 | 568 | 522 | 79% |
| 20 | ice_cream_flavor | 601 | 438 | 414 | 69% |
| 21 | ratio | 594 | 488 | 355 | 60% |
| **合计** | | **47,203** | **37,084** | **34,355** | **73%** |

### 未完成 L0 的 14 本

| # | 书 | OCR | raw_merged | chunks_raw | chunks_smart | 下一步 |
|---|---|---|---|---|---|---|
| 1 | french_sauces | ✅ 316p | ✅ | ✅ 142 | ✅ 127 | → Stage4 |
| 2 | neurogastronomy | — (MinerU) | ✅ | ✅ 619 | ✅ 619 | → Stage4 |
| 3 | dashi_umami | — (MinerU) | ✅ | ✅ 274 | ✅ 268 | → Stage4 |
| 4 | handbook_molecular_gastronomy | ✅ 95p | ✅ | ✅ 530 | ✅ 521 | → Stage4 |
| 5 | chocolates_confections | ✅ 200p | ✅ | ✅ 915 | ✅ 908 | → Stage4 |
| 6 | flavor_equation | ✅ 733p | ✅ | ✅ 209 | ❌ 正在跑9b | → 等9b完成 |
| 7 | essentials_food_science | ✅ 499p | ✅ | ❌ | ❌ | → Stage1 Step4 |
| 8 | flavor_bible | ✅ 1717p | ✅ | ❌ | ❌ | → Stage1 Step4 |
| 9 | bocuse_cookbook | ✅ 630p | ✅ | ❌ | ❌ | → Stage1 Step4 |
| 10 | taste_whats_missing | ✅ 369p | ✅ | ❌ | ❌ | → Stage1 Step4 |
| 11 | modernist_pizza | ✅ 448p | ✅ | ❌ | ❌ | → Stage1 Step4 |
| 12 | professional_pastry_chef | ✅ 1040p | ✅ | ❌ | ❌ | → Stage1 Step4 |
| 13 | french_patisserie | ✅ 659p | ❌ | ❌ | ❌ | → raw_merged → Step4 |
| 14 | phoenix_claws | ✅ 378p | ❌ | ❌ | ❌ | → raw_merged → Step4 |

**Stage1 就绪可直接进 Stage4：5 本**（french_sauces, neurogastronomy, dashi_umami, handbook, chocolates）
**Stage1 Step4 待跑（2b）：6 本**（essentials, flavor_bible, bocuse, taste, modernist_pizza, professional_pastry）
**Stage1 待生成 raw_merged：2 本**（french_patisserie, phoenix_claws）
**Stage1 Step5 正在跑（9b）：1 本**（flavor_equation）

---

## 二、文件散落地图

### 主项目（保留）
| 路径 | 大小 | 用途 |
|---|---|---|
| `~/l0-knowledge-engine/output/` | **14 GB** | 主数据目录，所有书的 OCR/Stage1/Stage4 产物 |
| `~/culinary-engine/output/` | **2.8 GB** | 代码仓库内产物（Stage1 中间文件 + Stage5 + L2a pilot） |
| `~/culinary-engine/` | 2.8 GB | 代码仓库 |

### Documents（源书 + 旧项目）
| 路径 | 大小 | 性质 | 建议 |
|---|---|---|---|
| `~/Documents/New project/` | **4.4 GB** | 旧版项目（l0_extract 多次重跑） | 🗄️ 归档或删除 |
| `~/Documents/厨书数据库/` | 3.2 GB | 源书 PDF/EPUB | ✅ 保留（源文件库） |
| `~/Documents/厨书（mineru）/` | 1.5 GB | MinerU 处理过的书 | 🗄️ 归档（已迁移到新链路） |
| `~/Documents/厨书（待转换）/` | 2.4 GB | 待转换的书 | ⚠️ 检查是否全部已处理 |
| `~/Documents/第二批厨艺书籍/` | 844 MB | 第二批源书 | ⚠️ 检查是否已导入 output/ |
| `~/Documents/厨书数据库（编译）/` | 40 MB | 编译版 md 书 | ✅ 保留（Stage5 L2b 用） |
| `~/Documents/厨书数据库（ocr）/` | 192 KB | 极小，可能是空壳 | 🗑️ 检查后删 |

### Downloads（重复 + 旧版本）
| 路径 | 大小 | 性质 | 建议 |
|---|---|---|---|
| `~/Downloads/厨书数据库/` | **2.6 GB** | Documents 的完全重复 | 🗑️ 删除 |
| `~/Downloads/kb_distill/` | 78 MB | 旧版蒸馏数据 | 🗑️ 删除（已在新 pipeline） |
| `~/Downloads/culinary_pipeline/` | 12 MB | 旧版 pipeline v1 | 🗑️ 删除 |
| `~/Downloads/culinary_pipeline_v2_2/` | 624 KB | 旧版 pipeline v2.2 | 🗑️ 删除 |
| `~/Downloads/culinary-engine-repo/` | 40 KB | 旧 repo 导出 | 🗑️ 删除 |
| `~/Downloads/*.yml` (27 个) | ~1 MB | Dify workflow 导出 v1-v9.1 | 🗄️ 归档一份最新的，删其余 |
| `~/Downloads/*.docx` (3 个) | ~3 MB | 架构文档 v3/v4/v5 | 🗄️ v5 已在 repo，删重复 |
| `~/Downloads/*.md` (4 个) | ~200 KB | 旧提案/工单 | 🗄️ 归档或删 |

### Desktop
| 路径 | 大小 | 建议 |
|---|---|---|
| `~/Desktop/books_food_science.json` | 小 | ⚠️ 检查是否有用 |

---

## 三、两个 output 目录的重叠问题

`~/culinary-engine/output/` 和 `~/l0-knowledge-engine/output/` 存在以下重叠：

**同一本书在两处都有数据的：**
- bread_hamelman, bread_science_yoshino, dashi_umami, chocolates_confections
- handbook_molecular_gastronomy, science_of_chocolate, french_sauces
- bocuse_cookbook, essentials_food_science, flavor_equation, flavor_bible
- modernist_pizza, professional_pastry_chef, taste_whats_missing

**典型模式：**
- OCR 产物在 `l0-knowledge-engine/output/{book}/vlm_full_flash/`
- raw_merged.md 在 `culinary-engine/output/{book}/`
- chunks_raw.json 在 `culinary-engine/output/{book}/`
- chunks_smart.json 在 `l0-knowledge-engine/output/{book}/stage1/` 或 `culinary-engine/output/{book}/stage1/`
- Stage4 产物在 `l0-knowledge-engine/output/stage4_{book}/`

**问题：没有统一的规范路径，同一本书的不同阶段产物散在两个目录。**

---

## 四、culinary-engine/output 里的非书数据

| 目录 | 性质 | 建议 |
|---|---|---|
| `stage5_batch/` (43 本) | Stage5 食谱提取正式产物 | ✅ 保留 |
| `stage5_pilot_flash/` | 测试数据 | 🗄️ 归档 |
| `stage5_pilot_nothink_clean/` | 测试数据 | 🗄️ 归档 |
| `l2a/pilot/` (75 食材) | L2a pilot 完成 | ✅ 保留 |
| `l2a/test/` | 空目录 | 🗑️ 删除 |
| `runtime_*.yaml / runtime_*.json` | 运行时配置 | ✅ 保留（pipeline 需要） |

---

## 五、整理建议（待你确认后执行）

### 立即可做（只删重复/空壳，不动正式产物）
1. 删 `~/Downloads/厨书数据库/` (2.6 GB 重复)
2. 删 `~/Downloads/culinary_pipeline*/` + `kb_distill/` + `culinary-engine-repo/` (旧版)
3. 删 `~/culinary-engine/output/l2a/test/` (空)
4. 归档 `~/culinary-engine/output/stage5_pilot*/` → `_archive/`

### 需要你确认
5. `~/Documents/New project/` (4.4 GB) — 旧版项目，还有价值吗？
6. `~/Documents/厨书（mineru）/` (1.5 GB) — MinerU 已被 flash OCR 替代，还需要保留吗？
7. `~/Documents/厨书（待转换）/` (2.4 GB) — 里面的书全部已经导入 output/ 了吗？
8. 27 个 Downloads yml 文件 — 保留 v9.1 一份归档，其余删？

### 路径规范化（整理完再做）
9. 定义标准：每本书的所有产物统一在 `~/l0-knowledge-engine/output/{book_id}/` 下
10. 把 `culinary-engine/output/{book}/` 的 Stage1 中间产物同步回 `l0-knowledge-engine/output/{book}/`
