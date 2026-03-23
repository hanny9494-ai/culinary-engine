# 技术决策日志

> 带完整 WHY 的决策记录。STATUS.md 只记结论，这里记推理过程。
> 所有 agent 可读，母对话维护。

---

## #1 切分工具：qwen3.5:2b（不是 Chonkie）
**日期**: 2026-03
**决策**: 用 Ollama qwen3.5:2b 做文本切分
**否决方案**: Chonkie SemanticChunker
**WHY**: Chonkie 在烹饪科学文本上表现不稳定——阈值敏感、跨语义边界碎片化。2b 虽然 chunk 更大（971 avg chars vs Chonkie 735），但语义边界更稳定，annotation 和 embedding 质量更高。RecursiveCharacterTextSplitter 只用于未来食谱提取，不用于 L0。
**注意**: L0母对话V2 一度决定用 Chonkie，后被推翻。最终确认 2b。

## #2 Stage3B 独立判断 proposition_type
**日期**: 2026-03
**WHY**: Stage3 原始输出混合多机制（如"肌球蛋白 50-55°C 变性 AND 胶原蛋白 70-80°C 水解"）在一条原理里。Stage3B 拆分为独立因果链（L0-PS-008 → L0-PS-008-A/B/C），每条只含单一因果关系。
**效果**: 597 → 1,159 条原子命题（93.7% 增长）

## #3 v2 题库 17 域
**日期**: 2026-03
**变化**: 14 域 → 17 域，172 题变更
**WHY**: 原 14 域缺少 mass_transfer、oxidation_reduction 等关键科学领域。域映射通过 sub_domain 字段实现，不修改 306 题主表，保留历史可追溯性。

## #4-#5 MC 9b 标注不重跑 + OFC/MC 双来源保留
**WHY**: 保留来源谱系——不同书对同一现象的解释角度不同。MC Vol2/3/4 的 domain 迁移在下游处理，不回溯重跑 Stage1。

## #6 L0 是裁判
**WHY**: 防止低质量信息传播。所有食谱、外部数据、替换建议必须经 L0 科学原理校验。L0 是整个系统的 ground truth。
**原则**: "宁可不回答，不可给错答案。"

## #7 L6 只翻译不判断
**WHY**: Jeff 明确纠正过——L6（粤菜语言↔系统语言）不做审美合理性判断，那是 L3 的职责。把判断逻辑放 L6 会造成与 L3 的循环依赖。
**Jeff 原话纠正**: AI 曾说"L6 judges whether dish modifications are culturally appropriate"，被纠正为"L6 only translates"。

## #8 查不到就问
**WHY**: 龙穿虎肚事件——AI 猜测是蛇+猫肉，实际是鳗+猪肠（潮州菜）。系统必须诚实说"我不知道"，不猜测。
**教训**: 菜名有大量地方性隐喻，猜测会严重损害用户信任。

## #9 TOC 必须人工审阅
**WHY**: Professional Baking 测试发现 auto-chapter-split 产生 40-45% 噪声（版权页、作者简介、索引）。手动 TOC 配置每本书 10-15 分钟，但消除了 Stage3 被垃圾 chunk 污染的风险。

## #10 外部数据 ETL 直接导入不蒸馏
**WHY**: FoodAtlas/FlavorGraph 等已是结构化数据，不需要 LLM 蒸馏。最大工作量是中英食材名映射。

## #11 Ollama 不能并发跑多本书
**WHY**: 单 GPU 内存限制。2b 和 9b 都必须串行。MinerU/Vision API 可并行。

## #12 trust_env=False 绕过代理
**WHY**: Jeff 机器有 Clash VPN 代理 127.0.0.1:7890。Ollama、DashScope、Claude API 调用如果走代理会随机失败。所有 Python HTTP 客户端必须 trust_env=False。

## #17 新书不再跑 Stage2+3
**日期**: 2026-03-17
**WHY**: OFC 验证显示 Stage4 开放扫描产出是 Stage3 的 7 倍（3,955 vs ~600）。两者重叠仅 0.08%（4/4,753）。306 题框架只覆盖约 12% 知识量。
**新策略**: 新书 Stage1 → Stage4。Stage2+3 只在全量完成后对薄弱域（mass_transfer 4 题、oxidation_reduction 5 题）定向补题。

## #18 chunk_type 快捷路径
**WHY**: Stage1 Step5 标注了 chunk_type（science/recipe/mixed/narrative），Phase A 可直接跳过 27b 预过滤——science/mixed 通过，recipe/narrative 跳过。节省数小时预处理。

## #19 has_number 改为 warning
**WHY**: 神经科学书籍包含机制性原理但没有数值参数。把缺少数字作为 fail gate 会错误删除有效知识。

## #20 API 串行排队
**WHY**: Opus API 不支持并发。但 Phase B（Opus）跑 Book A 时，Phase A（Ollama 27b）可以同时跑 Book B。

## #21 域外原理暂标 unclassified
**WHY**: OFC 有 180 条原理落在 17 域之外（如"包装保存""法规限制"）。不强行归类，先收集再组织。全量跑完再统一处理。

## #22 qwen3.5-flash 替代 MinerU 为 OCR 标准
**日期**: 2026-03-22
**WHY**: 3 本脏书全量 OCR 完成，0 失败 0 乱码。成本 ¥0.6/本，速度 8.5 秒/页。替代 MinerU+qwen-vl+merge 五步流程为单步 flash OCR。
**否决方案**: MinerU（云端、贵、多步骤）

## #23 LangGraph + Neo4j + Graphiti，不用 Dify 做产品层
**日期**: 2026-03-22
**WHY**: Dify 只做项目管理层（任务调度、日报、KB）。产品推理层用 LangGraph（7 工具的 Agentic Graph RAG）+ Neo4j（统一图谱+向量）。
**注意**: Dify 在项目管理层仍然有角色。

## #24-#27 架构决策集（2026-03-22）
- **Sonnet 4.6 Thinking 记录推理过程**: Agent 推理可追溯
- **Stage4 追加 token 统计**: 成本控制
- **Neo4j 内置向量索引替代 Weaviate**: 简化架构，去掉独立向量库
- **Graphiti 做 L3-personal 动态记忆**: 用户级个性化推理缓存

## #28 食谱 schema v2
**日期**: 2026-03-22
**WHY**: 纯配方 JSON + Neo4j 关系网。科学标注（key_science_points/derivations/l0_gaps）不嵌入食谱 JSON，全部在 Neo4j 关系网。
**ISA-88 三段分离**: process（做什么）+ formula（配多少）+ equipment（用什么）
**Garnish 定义**: 不只是装饰——任何没有操作步骤的食材都是 garnish。Jeff 明确纠正过。

## #29 关键科学决策点替代逐步 L0 绑定
**WHY**: 每道食谱只绑 3-5 个关键科学决策点（深度绑定），不逐步贴 L0。每个绑定点生成 3+ 条 what-if 裂变推导。

## #30 三级置信度
**级别**: high / medium / inferred / unmapped
**WHY**: 区分数据来源可靠性——权威书籍 vs 推导 vs 未映射

## #31 裂变推导
**WHY**: 每个 L0 绑定点 → 3+ what-if 推导。让用户理解"如果改变这个参数会怎样"。

## #32 编译 md 只做 L2b 食谱提取不做 L0
**WHY**: 编译 md 无图，质量不足以做 L0 蒸馏。只提取食谱结构。

---

## 成本参考
- OFC Stage3: ~$25.6（306 题 × Claude Opus via proxy）
- Stage4 全量 30 本: 预估 ¥1,500-2,000
- Stage5 食谱提取: ¥20-30（flash API）
- L3 预计算: ¥150-200
- 总预算: ¥5,000 可用
- 代理 API: http://1.95.142.151:3000（官方 1/22 价格）

## 被否决的重要方案
- **Chonkie**: 测试不稳定，改回 2b
- **全书自主扫描（Mode B）**: 无结构=幻觉风险，保留 306 题框架做锚点
- **Fine-tuning**: 用多层 RAG 替代，L3 做预计算缓存
- **题库先扩展再验证**: 先验证框架质量，再横向扩展
- **多本书并行 Stage2+3**: 串行处理，OFC 先做基准
- **Weaviate 独立向量库**: 被 Neo4j 内置向量索引替代
- **Dify 做产品层**: 只做项目管理层
- **L6 做判断**: 只做翻译
- **立即做 L3 预计算**: MVP 用实时 Agent 推理，先观察用户查询模式再缓存
