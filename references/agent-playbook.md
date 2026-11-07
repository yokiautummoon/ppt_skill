# Agent Playbook —— 无视觉 agent 怎么用好这个包

## 心智模型

你是**图面设计师**，但眼睛被蒙住。你的"视觉" = 三层确定性机器
（编译校验 → 布局断言 → XML 物证），你的"手" = SPEC 声明语言 + COM 后处理。
**永远不要手改产出物**（pptx/XML/坐标）——那会打破物证链；
布局不对 = 改 SPEC 重跑，让机器证明"这次对了"。

## 绝对 + 自动混合策略

- **绝对优先**：顶层布局骨架（标题、主区域、分栏）用绝对 `rect` 钉死，
  agent 完全可控（做什么、位置在哪）。
- **自动兜底**：容器（stack/dock/graph）内部交给求解器——对齐、间距、
  节点尺寸、连线锚点全部自适应。agent 只需声明内容与规则，不必算坐标。
- **数值接口**：想微调间距/字号下限？改 `meta.params`（见 spec-v2-language
  params 表），而不是硬写具体坐标。参数即文档。
- 经验：**一半靠绝对、一半靠自动**的组合在 agent 手里最稳——
  骨架手动排布防漂移，内容自动填充防越界。

## 迭代闭环（每轮必走）

```
写 SPEC → build_ppt（exit code）
   exit 0  → 检查 report.md 通过清单 + 产物 → 给用户预览
   exit 2/3/4 → 看违规家族（G 几何/T 文本/D 容器/S 规范）→ 改 SPEC → 重跑
```

违规症状速查（配合 report.md 明细）：
- **G 遮挡合法来源**：两元素相交但既非同容器兄弟也无 overlap 声明 →
  要么归入同一容器（owner），要么明确 `relations.overlap`。
- **G 锚点**：连线端点没贴端口——说明 IR 被手改或布局上游变了；改 SPEC 重跑。
- **T autofit 超框**：文本太长/框太小；扩框、缩小起始 fs 或拆元素。
- **S 字号**：超 type_scale；给 text_style.fs 起点或调规则集。
- **S 梯形单调**：ladder 宽度序列没严格递减；检查 children width。

## 层级、遮挡与组合（grill 质询回应）

1. **层级（z）**：你不直接"置顶/置底"——z 由 ir_builder 唯一分配
   （声明序 → z_override → 容器内阶梯），渲染器按 z 重排 spTree
   （OOXML 文档序 = 层级铁律）。想让某元素压住别的 = 调 z_override 或声明序。
2. **遮挡合法来源仅两类**：同容器归属（ownership 树：children 的 owner = 容器）
   或 `relations.overlap` 显式声明。ownership 是**组合关系的软件表达**——
   低层元素在高层元素之下是"渲染顺序"问题，而"谁是整体/谁是零件"是
   owner 树问题，两者分开管理。
3. **组合关系**：`group: true` 容器 → COM `Range().Group()` 真正合成
   Office 组对象（PPT 里拖动整体移动），组命名 `{id}.group`。这是超 XML 的
   **原生组合语义**——只有 COM 能做，XML 做不到。
4. **COM 完全控制**：COM 层覆盖 XML 表达不了的能力（见下表）。

## COM 层能力全景（win32com 完全控制 Office API）

XML 只能写静态文件；要让元素有**交互语义**必须 COM：

| 能力 | COM API | 产物验收 |
|---|---|---|
| 连线绑定（随动） | ConnectorFormat.BeginConnect/EndConnect | com_out.glue + 随动自检 follow.ok |
| 组合对象 | Shapes.Range([...]).Group() | com_out.groups ok，组名 `{id}.group` |
| 原生 Visio 嵌入 | AddOLEObject(FileName=.vsdx, Link=0) | com_out.ole ok（双击进 Visio 编辑） |
| 预览图 | Slide.Export(png) | preview.png（给用户目视） |
| 相对层级微调 | ZOrder（实测常量反向，见 ooxml-notes） | — |
| 公式兜底 | Word OMaths.Add+BuildUp 批量引擎 | com_out.formulas.injected（失败=占位文本 WARN） |

**COM 铁律**：COM 绝不重算几何/锚点/z——只做绑定/组合/嵌入/导出。
绑定后几何由 PowerPoint 接管（随动是它的语义，不是我们算的）。

## 公式编写（无视觉写数学式）

公式积木 = `type: formula, expr: "…"`。写表达式守则（detail 见 formula-omml.md）：

- **先选承载**：公式不是必须独立成形状。要放进既有文本框（标题/正文/表格
  单元格/graph 标签）→ 在 `text` 里写 `{{表达式}}`（与文字同行 = 行内式
  `m:oMath`；独占一行/一段 = 显示式 `m:oMathPara`）。只有需要"整块公式区域"
  才用 `type: formula`。
- **默认写真子集**（零 Office 直接注入，确定性）：`a/b + x^2 + c_i`、`√(a+b)`、
  `E=mc^2`、希腊字符原样（`λ`、`α`）。括号是字面括号（不做 m:d 大括号）。
- 求和/连乘用 **Unicode 字符式**：`∑_(i=1)^n x_i`、`∏_(i=1)^n x_i`
  （离线模板库已收录——**无需 --com 直接注入真 nary**，round-trip 保留）。
- **别用 LaTeX 花括号**：`\sum_{i=1}^{n}` 实测不转 nary（\sum 当文本、{ } 当
  下标）→ 若你在 SPEC 里写了这种，com 兜底也救不回来。`∫`（nary chr 缺省）、
  `\matrix` 等未收录 → 占位文本降级，报告中标注。
- **离线模板（辅助）**：`scripts/formula_templates.json` 收录的 ∑/∏_(i=1)^n
  系字符式，命中 = 零 Word 注入（预先 Word 转换 + 归一化的模板）。模板内容
  不可谓灵活——精确命中原文；要加新写法：跑
  `win_py scripts/build_formula_templates.py`（仅收 Word 实测转 nary 的）。
- 子集外且未命中模板、又不跑 `--com` = 占位文本（可读，但非原生公式）——
  交付时说明。
- 写法示例：`text: "质能方程 {{E=mc^2}} 表明质量与能量等价"`（行内）；
  `text: "推导：\n{{a/b + x^2}}\n其中 a、b 为常数"`（中间一行显示式）。
  完整样例见 `examples/formula/inline.yaml`。

## 模板安全区与人机交互

- **安全区**：元素必须落在 slide 减 margin 内（G 家族强制）。把标题/主体放
  margin 内，别贴边。
- **给用户见到的东西**：`--com` 有 preview.png；base.pptx 双击即目视。
  你把产物路径/预览交给用户"过目"，**目视判断归用户**——你负责的是
  机器可证的正确性（几何/文本/物证全绿）。
- **故意让用户复核的点要标注**：外部 vsdx 源路径、OLE 双击行为是否可用、
  字体（微软雅黑双轨之外的字形）、以及任何 user 需要的微调建议清单。

## 架构图逃生通道（外部工具产物嵌入）

用户已有外部绘制图（如小行星支持系统的 mermaid→Visio 管线产 .vsdx）：

```
mermaid (mmd2layout/visio_bridge) → .vsdx + PNG
SPEC: type: diagram, src: 图5-3-10_xxx.vsdx
  → 渲染层跳过图片落版（ole_pending）
  → com_layer AddOLEObject 原生嵌入（双击进 Visio 可编辑）
```

- `.vsdx`：COM OLE 嵌入（原生 Visio 对象）；`.png`：按图片落版（visual_bounds 裁切）。
- 已验证路径（本仓库 `_probe/ole_vsdx.yaml` + tests/com_office_check.py）。
- **src 必须可被 Windows 侧解析**：用 Windows 路径（`D:/...`），
  相对路径按 SPEC 目录解析。引用不存在的文件 = 编译/COM 错误。
- 这是"office 形状操控太复杂"时的官方逃生通道——架构组成图用 Visio 原生对象，
  不逐形状拼装。

## checklist（每次交付前）

1. exit 0 + report.md 无违规（有 --com 时 com_out 项全 ok）。
2. base.pptx / preview.png 已生成并交付路径。
3. 迭代过程中改的是 SPEC，没手改产物。
4. 已知限制/需人复核点已向用户明说。