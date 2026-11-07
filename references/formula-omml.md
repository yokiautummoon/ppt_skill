# formula-omml.md — 公式支持：OMML 结构与注入边界（实测基准）

PowerPoint 的"插入公式"按钮（2016+ 原生）真实存在，但 **PowerPoint 对象模型没有
暴露任何公式 API**（实测：TextRange/TextFrame2.TextRange/Shape 上 InsertFormula、
Formula、OMath、OMaths、BuildUp 等候选名 GetIDsOfNames 全 ∅；gen_py 类型库
16.0 亦报 TextRange 无 InsertFormula）。UI 背后是 OMML（`m:oMath`）直接写入
OOXML。因此公式的能力边界 = **OMML 是 XML，可注入**。

**先纠正一个常见误解**："对象模型没有公式 API" ≠ "公式不能进现有文本框"。
标准公式本质是文本框内容（`p:sp/p:txBody/a:p > a14:m`），不是独立形状；
PowerPoint UI 的"插入公式"就是往当前文本框的段落里写 `a14:m`。实测样例
`test2/公式示例.pptx`：标题文本框内同一个 `a:p` 里依次是 `a:r`（"你好"）
+ `a:br`（换行）+ `a14:m`（标准公式）。本仓库：
- 任意 `text` 用 `{{UnicodeMath}}` 富文本标记 → 公式写进**既有文本框**（无需新建形状）；
- `type: formula` 只是"整块公式"的便捷写法（单独文本框 + mc 包装）。

## 一、实测原生结构（Word 桥接产物, probe_com_formula.py 实测）

公式文本框 = `mc:AlternateContent` 整体包装（spTree 层）：

```xml
<mc:AlternateContent xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006">
  <mc:Choice xmlns:a14="http://schemas.microsoft.com/office/drawing/2010/main" Requires="a14">
    <p:sp><!-- 完整文本框：a14:m 公式 --></p:sp>
  </mc:Choice>
  <mc:Fallback>
    <p:sp><!-- 同 id 同 xfrm；spLocks 全锁 + blipFill 位图（Word 自动渲染）+ noFill 文本 --></p:sp>
  </mc:Fallback>
</mc:AlternateContent>
```

- Choice/Fallback 两个 p:sp **共用同一 cNvPr id**（合法，Word 即如此）。
- a14 命名空间只在 mc:Choice 元素上声明。
- **mc 包装不是公式本身的前提**：PowerPoint 16.0 实测，`a14:m` 直接写在普通
  `p:sp` 的 `a:p` 里可正常打开；PowerPoint 自己回存时会把该形状补包成
  `mc:AlternateContent`（Choice=公式、Fallback=位图）。本仓库 standalone
  formula 主动写包装（Fallback=表达式原文），文本框内联公式不写包装
  （PowerPoint 接受并可在回存时自行补包装）。

公式文本框 txBody 内（a:p 的子节点，替代普通 a:r）：

```xml
<a:p>
  <a:pPr><a:lnSpc><a:spcPct val="115000"/></a:lnSpc><a:spcAft><a:spcPts val="800"/></a:spcAft></a:pPr>
  <a14:m>
    <m:oMathPara xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/math">
      <m:oMathParaPr><m:jc m:val="centerGroup"/></m:oMathParaPr>
      <m:oMath>
        <m:f>…分式…</m:f>
        <m:r>…运算符 run…</m:r>
        <m:sSup>…上标…</m:sSup>
      </m:oMath>
    </m:oMathPara>
  </a14:m>
</a:p>
```

### 两种段内承载形态（PowerPoint 16.0 实测，`_probe/probe_inline_formula.py`）

| 场景 | XML（`a:p` 的子节点） | 说明 |
|---|---|---|
| 与文字**同一行**（行内式） | `a:r` + `a14:m > m:oMath` + `a:r` | 公式与前后文本同流；实测打开→SaveAs 后仍是 `m:oMath` |
| **独占一行/一段**（显示式） | `a14:m > m:oMathPara > m:oMath` | 公式成行显示（`m:jc=centerGroup`）；可与文字同段、前置 `a:br`（用户样例即此形） |

- 行内式与显示式的唯一差别是 `a14:m` 内层：`m:oMath` vs `m:oMathPara/m:oMath`。
- 本仓库映射：`{{expr}}` 与文字同行 → 行内式；公式独占一段（前后是 `\n` 或整段
  只有公式）→ 显示式。`type: formula` 元素始终用显示式。
- 禁止在 `**` / `[[ ]]` 内嵌 `{{…}}`：OMML run 不参与加粗/强调（编译期 exit 2）。

## 二、数学结构（实测 `a/b + x^2 + c_i`）

| UnicodeMath | OMML 结构 | 要点 |
|---|---|---|
| `a/b` | `m:f` → `m:fPr/m:ctrlPr` + `m:num` + `m:den` | ctrlPr 内 rPr `smtClean="0"` |
| `x^2` | `m:sSup` → `m:sSupPr/m:ctrlPr` + `m:e`(基) + `m:sup` | 上标/下标 run 的 rPr sz 与主同（渲染器自动缩） |
| `c_i` | `m:sSub` → `m:e` + `m:sub` | |
| 运算符 `+` | `m:r`，m:t 内容 `+`（Word 生成时尾随 U+00A0 数学空格） | |
| 变量 | 数学斜体 Unicode：a-z→U+1D44E..、A-Z→U+1D434..（+=0x1D400 映射） | rPr `i="1" kern="100"` |
| 数字 | 原字符 | rPr 同上（数字无斜体形，视觉不变） |

run 的 rPr（公式内容 run，实测）：

```xml
<a:rPr lang="en-US" altLang="zh-CN" sz="1800" i="1" kern="100">
  <a:effectLst/>
  <a:latin typeface="Cambria Math"/>
  <a:ea typeface="等线"/>
  <a:cs typeface="Times New Roman"/>
</a:rPr>
```

ctrlPr 内 rPr langle="zh-CN" 且带 `smtClean="0"`。sz = fs×100（1800=18pt）。

## 三、注入边界（formula_omml.py 契约）

- **v1 语法子集**（可注入，确定性）：单字符变量（斜体映射）、数字、运算符
  `+ - × ÷ = < > ≤ ≥ ≠ ≈ ±`、逗号、括号组 `(...)`（字面括号，不做 m:d）、
  分式 `/`（左结合，分子分母=单 unit）、上标 `^`、下标 `_`（支持 a^2 / a_i /
  a_i^2 嵌套式）、根式 `√`（m:rad + degHide）、希腊字母（保持原字符）。
- **fallback 边界**：`∑ ∫ ∏` 字符式先走离线模板（命中即注入）；其余
  （`\` LaTeX 语法、`∫`、绝对值 `|`、矩阵 `\matrix`、`{ }` 花括号、多行对齐、
  其他未知字符）交 com_layer 批量兜底。空格 = 分隔符（隐式乘法，不生成符号）。
- **文本框内联（推荐用于"公式 + 解释文字"）**：任意 `text`（元素/表格单元格/
  graph 节点/边标签）支持 `{{UnicodeMath}}` 标记；`richtext.paragraphs()` 按显式
  `\n` 切段——与文字同行 → `a14:m > m:oMath`（行内式），独占一段 →
  `a14:m > m:oMathPara`（显示式）。公式段数/形态由渲染与物证共用同一函数判定。
- **注入包装**：standalone `type: formula` 由 renderer 生成 mc:AlternateContent；
  Choice 内 p:sp 的 txBody 用 a14:m；Fallback 内 p:sp 保留**表达式原文文本**
  （可读降级，与 glue"非绑定语义"降级哲学一致）——不生成位图（零 Office）。
  文本框内联公式不写 mc 包装（PowerPoint 接受；其回存时自行补包装）。
- **字号**：text_style.fs 或 params.formula.fs_default（默认 18）；color 可选 →
  rPr.solidFill。
- **物证**：standalone 已注入公式查 `m:oMath` 存在 + AlternativeContent 包装存在
  + fallback 文本 == 表达式原文；文本内 `{{…}}` 查 `a14:m` 数 == IR 公式段数，
  且形态（行内 `m:oMath` / 显示 `m:oMathPara`）与切段结果一致；fallback 占位
  （无 --com 未兜底）查占位文本存在 + report 标注。

## 四、com_layer 批量兜底（吞吐）

兜底不做"每公式一个 Word"：一次 Word 进程吞 N 表达式（逐段 OMaths.Add+BuildUp →
SaveAs2 docx → 解包按 w:p 切 N 个 m:oMath），**零剪贴板**。随后 python-pptx
打开 base.pptx 找到 formula 占位文本框替换为 OMML 注入。吞吐 O(N) 进程 → O(1)。

接口 = `omml_engine.word_batch_omml(exprs)`（用户洞察兑现："剥离成函数接口 ≈
PPT 缺位的公式 COM API"）。`sel.OMaths.Add(rng)` 返回单个 OMath 但 dynamic 分派
属性兼容差 → 用 probe 同模式：Add 后遍历 `sel.OMaths` 集合 BuildUp（幂等）。
docx 提取注意嵌套：独占段落公式是 `w:p > m:oMathPara > m:oMath`。

**兜底语法实测（Word 16.0 zh-CN, 2026-09-09）**：
- ✅ `∑_(i=1)^n x_i`（**Unicode 字符式**）→ 真大运算符 `m:nary`（round-trip 后
  nary 保留，PowerPoint 原生识别）。求和/连乘写字符式 `∑`/`∏` + `_( )^`。
- ❌ `\sum_{i=1}^{n}`（LaTeX 花括号风格）→ Word**不当**求和：`\sum` 按文本处理，
  花括号按下标 → "文本 ∑ 带上下标"而非 nary。**不要用 LaTeX 风格**。
- ✅ `∏_(i=1)^n x_i`、`∏_(i=1)^n`：**真 m:nary（chr=∏，U+220F）**，与 ∑ 同
  模式（引擎 rng.Select 批量修复后实测；此前"未转 nary"是旧批量 bug 的假象）。
  已收录进离线模板库。
- ⚠️ `∫_0^1 x dx`：产 `m:nary` 结构但 **chr/limLoc 缺省**（只有 sub/sup），
  渲染成什么符号 PowerPoint 未机器可证 → **不收录模板**，运行时尚处引擎
  实测覆盖外（占位文本/Word 兜底），后续探测或扩子集。
- 引擎对 `a/b + x^2` 等规则表达式输出与子集解析器等价结构。

## 六、离线模板库（辅助手段，零 Word 命中）

任意子集外表达式走 Word 批量引擎需中间 docx + 解包；对高频固定写法
（∑_(i=1)^n 系字符式）不值得每回启动 Word。解法 = **离线模板**：预先经
Word BuildUp 一次，收**真 m:nary** 条目存 `scripts/formula_templates.json`，
运行时按表达式**原文精确命中** → 直接注入（--com 都不需要）。

- **层级**：parse_expr（子集内主路径）→ 模板命中（子集外高频，辅助）→
  Word 引擎（其余子集外，回退）。
- **重建**：`win_py scripts/build_formula_templates.py`（需 Word）。收录门槛 =
  Word 产出真 **m:nary 且带明确 chr**（∑/∏ 系收；`\sum{}` 花括号式不转、
  ∫ 缺 chr → 自动 skip）——运行时照常走 Word 兜底或占位降级。
- **归一化**：Word docx 的 run 用 `w:rPr`（WordprocessingML），PowerPoint
  公式用 `a:rPr`（DrawingML，实测基准见第二节）。构建时 normalize 把
  `w:rPr` → `a:rPr`（lang/sz/i/kern + effectLst + Cambria 三字体；ctrlPr 带
  smtClean=0）并清根 xmlns，注入后与 parser 产物同构、round-trip 保留（实测
  PASS：5 oMath + 1 nary + 43 a:rPr 重存完整）。
- **resolve 应用 SPEC 的 fs/color**：字符串级确定性替换 rPr 的 sz 与插
  solidFill（与 parse_expr 契约一致）；不写则照模板默认（fs=18 无色）。
- **判型同源**：`supported(expr)` = parse ok ∪ 模板命中；com 只兜
  supported=False 的表达式（模板命中的 render 已注入，不重复兜底）。

## 七、物证与降级边界

- 注入型物证（render_check_xml）：standalone `type: formula` 按 name 定位 sp →
  其所在 mc:AlternateContent Choice 内含 `a14:m > m:oMathPara > m:oMath` +
  Fallback 文本 == 表达式原文。文本内 `{{…}}` 按 name 定位 sp → `a14:m` 数 ==
  IR 公式段数，且行内/显示形态与 `richtext.paragraphs()` 切段结果逐项一致。
- 占位型物证：文本框文本 == 表达式原文（子集外且未跑 --com）。判型 = 渲染器
  同源 `parse_expr` 重算（确定性，不依赖 IR 记忆状态）。
- 权威验证 = PowerPoint COM round-trip：打开→可写 SaveAs→解包查 m:oMath 保留
  （PowerPoint 若拒/修复注入结构，round-trip 后必丢）。已实测：解析器注入与
  引擎注入（含 nary）均 round-trip 无异常、公式内容与结构完整保留。
## 八、文本内符号标注：禁止 ASCII 下划线伪符号（校对经验 §㈣）

普通文本（正文/卡片/图注/表格单元格）里**不得出现 `X_Y` 字面量**（C_D、ω_p、
R_E、λ_D、T_e、σ_P…）——它既不是 OMML 也不是可读假公式。三档处理：

1. **独立成块 → `type: formula`**（本档第 1 节）——整式或关键关系式。
2. **行内符号 → Unicode 假公式**：只要能查到对应下标字符就用（下表）；否则文字化。
3. **无法 Unicode 化的罗马大写下标（C/E/D/B/w 等）→ 文字化**：如 C_D→"阻力系数"、
   R_E→"地球半径"、λ_D→"德拜尺度"，上下文明示物理量，别硬造 "CD"/"RE" 连写。

### 附：可用的 Unicode 下标（假公式）字符表

下标数字：`₀₁₂₃₄₅₆₇₈₉ ₋ ₊ ₌ ₍ ₎`
下标拉丁（仅下列部分，无大写、无 c/d/f/g/h 之外的小写……实际可用）：

```
ₐ         ₑ          ₒ        ₓ            （a/e/o/x）
ₕ ₖ ₗ ₘ ₙ ₚ ₛ ₜ                     （h/k/l/m/n/p/s/t）
ᵢ ᵣ ᵤ ᵥ ₔ                        （i/r/u/v；ᵣ 常用作 R 下标替代）
```

- 希腊字母本身是 Unicode 字符（ω λ ρ σ τ ε 等），无"下标希腊"——同形变体
  U+2090 系只覆盖拉丁。`ω_p → ωₚ`（p 有 ₚ）；`N_e → Nₑ`（e 有 ₑ）；
  `T_e → Tₑ` / `T_i → Tᵢ` / `T_n → Tₙ`；`σ_P → σₚ` / `σ_H → σₕ`（Hall）；
  `σ_0 → σ₀`（数字下标齐）。`R_E`、`C_D`、`λ_D` 无对应 → 文字化。
- 上标仅少量可用（⁰¹²³⁴⁵⁶⁷⁸⁹ ⁺ ⁻ ᵃᵇᶜᵈᵉᵍᵏᵐⁿᵒᵖʳˢᵗᵘᵛʷˣʸᶻ），常用于单位
  （如 `~10⁻⁶`、`v²`）；表内密度 10⁻⁶ 这类已规范。
- 清扫验证口径：只查正文/卡片/表格/图注 XML 的 `a:t` 文本；formula 的
  mc:Fallback / m:t（公式本体）不在列。
