# Stage5 配方结构化提取 Pipeline 设计

> 母对话设计，2026-03-18
> 定位：从11本书中提取结构化配方，填充L2b配方校准库

---

## 1. 核心难题：子配方散落

专业厨书的配方不是"一个配方一段文字"。典型结构：

```
书末 Basic Recipes 章节:
  - 高汤（被20+道菜引用）
  - 酥皮面团（被10道甜点引用）

正文某章:
  - 红酒烩牛肉 → refs: 高汤, "see p.xxx酱汁"
  - 巧克力慕斯 → 用到蛋奶酱 + "参见基础配方"
```

子配方（SubRecipe）散落在不同章节，通过文字引用连接。

---

## 2. 学术参考与借鉴

### Recipe Flow Graph（r-FG，京都大学 2020）
- 用有向无环图(DAG)表示配方中食材→动作→中间产物的关系
- r-NE标签体系：食材(F)、工具(T)、动作(Ac)、时间(D)、温度(Q)、状态(Sf)
- F1达87.5
- **借鉴点：** r-NE标签体系直接用于27b提取prompt的实体引导
  - F(食材) + Q(用量) → formula
  - Ac(动作) + D(时间) + Sf(状态) → process
  - T(工具) → equipment

### Cooklang + GPT-4 流图提取（2023）
- GPT-4一步到位从配方文本提取流图结构
- 擅长给中间产物命名（"the chocolate mixture"）
- 需要迭代优化prompt
- **借鉴点：** LLM可以一步提取配方结构，中间产物命名→SubRecipe识别

### EaT-PIM 食材替换（ISWC 2022）
- 解析指令→流图→训练embedding→捕捉食材在流程中的角色→替换
- **借鉴点：** P4阶段L3推理引擎的食材替换能力基础
- 我们有更强基础：L0科学原理可判断替换的科学可行性

### PADME 程序化文本执行（2025）
- 将程序化文本自动转为可执行图，捕获任务依赖、决策点和可复用子程序
- **借鉴点：** "可复用子程序"概念 = 我们的SubRecipe

---

## 3. 方案：两阶段提取

### 阶段一：SubRecipe 库先行（2b筛选 → 27b提取）

```
Step 1: 2b 筛选全部 14,041 chunks
  → 这个 chunk 是不是配方内容？
  → is_recipe: true/false
  → 预计 ~2,000-3,000 条是配方

Step 2: 27b 分类
  → 独立配方（Recipe）？
  → 基础子配方（SubRecipe：高汤/面团/酱汁）？
  → 配方片段（引用了其他配方的部分）？
  → 关键信号："Basic Recipe"、"Foundation"、章末附录

Step 3: 27b 先提取所有 SubRecipe（基础配方优先）
  → 按 ISA-88 Schema: process + formula + equipment
  → 每个 SubRecipe 生成 sub_recipe_id
  → 建立 SubRecipe Registry（名称→ID映射表）
```

**蒸馏顺序关键：先 Basic Recipes 章节 → 再正文菜式**
（与 recipe_schema_v1.md 定义一致）

### 阶段二：Recipe 组装（27b提取 + 引用解析）

```
Step 4: 27b 提取正文 Recipe
  → 带着 SubRecipe Registry 上下文
  → prompt 注入已知 SubRecipe 列表
  → 识别 "see page xxx" → 映射到 refs[{ref: SR-xxx}]
  → 输出完整 Recipe Schema

Step 5: 引用解析（本地规则 + 27b）
  → 扫描跨引用信号：
    - "see page/p. xxx"
    - "recipe on page xxx"
    - "参见第x章"
    - "use the [xxx] from Basic Recipes"
    - 直接提到 SubRecipe 名称
  → 匹配到 SubRecipe Registry
  → 未匹配的标记 unresolved_ref，人工复查
```

---

## 4. SubRecipe Registry 设计

```json
{
  "SR-001": {
    "name": "Chicken Stock",
    "name_zh": "鸡高汤",
    "source_book": "professional_baking",
    "source_chunk_id": "professional_baking:chunk_2801",
    "aliases": ["chicken stock", "light stock", "fond de volaille"],
    "referenced_by": ["RCP-012", "RCP-045", "RCP-089"]
  }
}
```

Registry 是解决散落问题的核心——先收集所有子配方建表，再让正文配方通过名称/页码/引用匹配。

流图"中间产物"概念的全书级应用：
1. 第一遍扫描：识别所有"产出节点"（SubRecipe 定义处）
2. 第二遍扫描：识别所有"引用边"（配方中提到 SubRecipe 的地方）
3. 连接：产出节点 + 引用边 = 跨配方引用图

---

## 5. 27b 提取 Prompt 设计要点

融合 r-NE 标签体系和 Cooklang 经验：

```
你是配方结构化提取专家。按ISA-88三段分离格式提取配方。

实体识别（参考r-NE标签）：
- F: 食材名称 → formula.ingredients[].item
- Q: 用量数值 → formula.ingredients[].qty + unit
- Ac: 动作动词 → process[].action
- D: 时间参数 → process[].text 或 formula.params
- T: 工具设备 → equipment[]
- Sf: 状态描述 → process[].text

关键规则：
1. 模糊量词必须转数字（juice of ½ lemon → lemon_juice 15ml）
2. 只有 "to taste" 允许 qty=null
3. 单位统一公制
4. 如果文中提到其他配方（"see page xxx"/"参见基础配方"），
   放入 refs 字段，不要展开
5. 中间产物如果有独立配方（自己的食材+调味），
   标记为 SubRecipe，不要合并到主配方
```

---

## 6. 模型分工

| 步骤 | 模型 | 理由 |
|------|------|------|
| chunk筛选（是否配方） | 2b | 简单二分类，速度快 |
| 配方分类+结构提取 | 27b | 结构化提取不需要Opus级推理 |
| 引用解析 | 27b + 规则 | 模式匹配为主 |
| 复杂配方兜底 | Opus 4.6 | 仅模糊配方/多层嵌套/三语混合 |

成本估算：配方提取基本全在本地（免费），Opus兜底 ~¥20-30。

---

## 7. 与 L0 的关系

**L0 是裁判原则不变：**
- 每个提取的配方参数（温度、时间、比例）必须能在 L0 原理中找到科学依据
- 如果配方参数与 L0 冲突，标记为 needs_review
- 这是 L2b（配方校准库）的核心价值——每个配方都有科学背书

**配方流图 → L3 推理引擎（P4阶段）：**
- 现阶段 process 保持线性步骤列表
- 预留 parallel_group 字段
- P4升级时：process → DAG，支持并行/汇合/时间优化/设备冲突检测

**食材替换（P4阶段）：**
- EaT-PIM 的流图embedding + L0因果链 = 科学可行的替换推荐
- 例："鲈鱼换石斑" → L0知道蛋白质变性温度不同 → 调整蒸制时间

---

## 8. 脚本设计

```
scripts/
  stage5_recipe_extract.py   ← 主脚本（2b筛选 + 27b提取）
  stage5_registry.py          ← SubRecipe Registry 管理
  stage5_resolve_refs.py      ← 跨配方引用解析
  stage5_quality.py           ← 配方质控（L0校验）
```

---

## 9. 学术参考汇总

| 项目 | 论文/来源 | 对我们的价值 | 使用时机 |
|------|----------|-------------|---------|
| r-FG Corpus | Yamakata et al., LREC 2020 | r-NE标签→提取prompt引导 | 现在 |
| Cooklang+GPT-4 | cooklang.org, 2023 | prompt迭代经验 | 现在 |
| EaT-PIM | ISWC 2022 | 流图embedding→食材替换 | P4 |
| PADME | 2025 | 可复用子程序→SubRecipe概念 | 设计参考 |
| Recipe Flow Graph | Mori et al. | process升级为DAG | P4 |
| RecipeNLG | INLG 2020 | 大规模配方数据集参考 | 数据参考 |
