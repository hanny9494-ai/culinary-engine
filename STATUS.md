# 餐饮研发引擎 — 项目状态 v3

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
| L0 | 科学原理图谱 | "为什么会发生" — 因果链+参数边界+16域 | 🔄 蒸馏中 |
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
| MC Stage3 蒸馏 | 🔄 进行中 | Claude Opus，16域 |
| Stage3B 因果链 | ⏳ 待做 | OFC 303条 + MC新原理 |
| 阶段A: v2补标注 | ⏳ 待做 | proposition_type/sub_domain/cross_domain_tags |
| 阶段B: domain重映射 | ⏳ 待做 | CR→3域, FS→2域, PC→2域 |
| Pipeline自动化 | ✅ 完成 | 新仓库4个agent全部merge |
| 架构文档v3 | ✅ 完成 | 七层+L2c+冷启动+自学习闭环 |

---

## Chunks 总量

| 书目 | chunks | 标注域 | 状态 |
|------|--------|--------|------|
| OFC | 1,427 | 旧14域 | ✅ |
| MC Vol2 | 485 | 旧14域 | ✅ |
| MC Vol3 | 502 | 旧14域 | ✅ |
| MC Vol4 | 703 | 旧14域 | ✅ |
| **合计** | **3,117** | | ✅ Stage2完成 |

---

## ⚠️ 关键技术决策（所有agent必读）

1. **切分工具：qwen3.5:2b（不是Chonkie）** — 已测试确认
2. **Stage3B独立判断proposition_type** — 不依赖阶段A
3. **306题母表不改动** — domain字段保持旧14域，新域通过sub_domain体现
4. **MC Vol2/3/4的9b标注不重跑** — domain迁移在下游处理
5. **L0是裁判** — 食谱和外部信息必须经L0校验才入库
6. **L6只翻译不判断** — 审美合理性判断在L3
7. **查不到就问** — 不猜测，引导用户提供食材/工艺/口感目标

---

## 技术栈

| 组件 | 选型 | 状态 |
|------|------|------|
| PDF提取 | MinerU API + qwen3-vl-plus | ✅ |
| 文本切分 | qwen3.5:2b Ollama | ✅ |
| Topic标注 | qwen3.5:9b Ollama (think:false) | ✅ |
| 原理蒸馏 | Claude Opus 4.6，代理API | ✅ |
| 因果链蒸馏 | Claude Sonnet 4.6 | ⏳ |
| Embedding | qwen3-embedding:8b (本地) / Gemini Embedding 2 | ✅ |
| 向量库 | Weaviate | ⏳ |
| 图谱库 | Neo4j Docker | ⏳ |

---

## 环境变量
```bash
export MINERU_API_KEY=""
export DASHSCOPE_API_KEY=""
export GEMINI_API_KEY=""
export L0_API_ENDPOINT="http://1.95.142.151:3000"
export L0_API_KEY="Bearer"
```

## GitHub
- 新仓库: https://github.com/hanny9494-ai/culinary-engine
- 旧仓库（参考）: https://github.com/hanny9494-ai/L0-systerm
- 本地数据: ~/l0-knowledge-engine/
