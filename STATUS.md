# 餐饮研发引擎 — 项目状态 v3.1

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
| L0 | 科学原理图谱 | "为什么会发生" — 因果链+参数边界+17域 | 🔄 蒸馏中 |
| L1 | 设备实践参数层 | "同一原理，不同设备怎么调" | ⏳ 待建 |
| L2a | 天然食材参数库 | 品种/部位/季节/产地/价格 | ⏳ 待建 |
| L2b | 食谱校准库 | 已验证参数组合+可信度评分（L0是裁判） | ⏳ 待建 |
| L2c | 商业食材数据库 | 品牌/型号→成分细分（食谱精确到品牌） | ⏳ 待建 |
| FT | 风味目标库 | 审美词→可量化感官参数 | ⏳ 待建 |
| L3 | 推理引擎 | f(L0,L1,L2a,L2c,FT) 预计算+实时推理 | ⏳ 待建 |
| L6 | 翻译层 | 粤菜语言↔系统语言（纯翻译不判断） | ⏳ 待建 |

---

## 当前进度总览

| 阶段 | 状态 | 说明 |
|------|------|------|
| OFC Stage 1-3 | ✅ 完成 | 303条L0原理 |
| MC Vol2/3/4 Stage1 | ✅ 完成 | 485+502+703 = 1690 chunks |
| MC Stage2 匹配 | ✅ 完成 | 99.4% matched (3117 chunks × 306题) |
| MC Stage3 蒸馏 | ✅ 完成 | 294条新原理，零失败 |
| OFC+MC 合计 | ✅ 完成 | **597条L0原理** (保留双来源) |
| Stage3B 因果链 | 🔄 进行中 | 597条，Sonnet |
| 306题→v2域重映射 | ✅ 完成 | 171题变更，14条人工审核，l0_question_master_v2.json |
| 阶段B: 原理domain刷新 | ⏳ 待做 | 597条标签→v2域 |
| 冰淇淋风味学 Stage1 | 🔄 进行中 | 新书端到端测试（auto-chapter-split修复后） |
| Pipeline自动化 | ✅ 完成 | 新仓库4个agent全部merge |
| auto-chapter-split修复 | ✅ 完成 | 无TOC书按heading自动切分 |
| 架构文档v3 | ✅ 完成 | 七层+L2c+冷启动+自学习闭环 |

---

## L0原理库

| 来源 | 原理数 | 状态 |
|------|--------|------|
| OFC (On Food and Cooking) | 303条 | ✅ 旧schema |
| MC (Modernist Cuisine Vol2/3/4) | 294条 | ✅ domain待刷新 |
| **合计** | **597条** | 目标1500条 |

质量指标（MC 294条）：
- statement含数值: 74.5%
- citation >30词: 5.8%
- boundary为空: 8.2%
- OFC与MC强互补（机制 vs 精确参数）

---

## 题目库

| 版本 | 题数 | 域数 | 状态 |
|------|------|------|------|
| v1 (旧) | 306 | 14域 | 归档 |
| **v2 (当前)** | **306** | **17域** | ✅ 生效 |

v2域分布薄弱域：
- mass_transfer: 4题 ← 需补题
- oxidation_reduction: 5题 ← 需补题
- salt_acid_chemistry: 8题 ← 需补题

---

## Chunks 总量

| 书目 | chunks | 标注域 | 状态 |
|------|--------|--------|------|
| OFC | 1,427 | 旧14域 | ✅ |
| MC Vol2 | 485 | 旧14域 | ✅ |
| MC Vol3 | 502 | 旧14域 | ✅ |
| MC Vol4 | 703 | 旧14域 | ✅ |
| 冰淇淋风味学 | ? | v2域 | 🔄 Stage1跑中 |
| **合计** | **3,117+** | | |

---

## ⚠️ 关键技术决策（所有agent必读）

1. **切分工具：qwen3.5:2b（不是Chonkie）** — 已测试确认
2. **Stage3B独立判断proposition_type** — 不依赖阶段A
3. **v2题库已生效** — 新书用v2，旧原理用阶段B批量刷标签
4. **MC Vol2/3/4的9b标注不重跑** — domain迁移在下游处理
5. **OFC+MC原理保留双来源** — 不合并，597条都留
6. **L0是裁判** — 食谱和外部信息必须经L0校验才入库
7. **L6只翻译不判断** — 审美合理性判断在L3
8. **查不到就问** — 不猜测，引导用户提供食材/工艺/口感目标
9. **无TOC书按heading自动切分** — split_markdown_into_chapters已修复

---

## 待完成任务

| 任务 | 优先级 | 说明 |
|------|--------|------|
| Stage3B因果链完成 | P0 | 🔄 进行中 |
| 冰淇淋Stage1完成 | P0 | 🔄 进行中 |
| 阶段B: 597条domain→v2域 | P1 | Stage3B完成后做 |
| 冰淇淋Stage2+3 | P1 | Stage1完成后用v2题库跑 |
| mass_transfer/oxidation_reduction补题 | P2 | 各补5-8题 |
| salt_acid_chemistry补题 | P2 | 补到10-12题 |
| MC Vol1 (epub→PDF→Stage1) | P2 | equipment_physics主要来源 |
| Mouthfeel | P2 | texture_rheology深度 |
| Salt Fat Acid Heat | P2 | 本地已有PDF |
| Neo4j搭建+实体对齐 | P3 | 原理入库，跨书因果链连接 |
| Weaviate填充 | P3 | embedding检索 |
| scan_low_hit补题 | P3 | 发现新知识盲区 |

---

## 技术栈

| 组件 | 选型 | 状态 |
|------|------|------|
| PDF提取 | MinerU API + qwen3-vl-plus | ✅ |
| 文本切分 | qwen3.5:2b Ollama | ✅ |
| Topic标注 | qwen3.5:9b Ollama (think:false) | ✅ |
| 原理蒸馏 | Claude Opus 4.6，代理API | ✅ |
| 因果链蒸馏 | Claude Sonnet 4.6 | 🔄 |
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
