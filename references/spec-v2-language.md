# SPEC v2 语言全语法（Schema 表）

SPEC 是 **YAML 声明式积木语言**：agent 描述"要什么"，布局/校验/渲染引擎决定"怎么排"。
分四层：`meta`（页面与风格）→ `palette`（色板 token 库）→ `elements`（平铺积木，
声明序 = 默认 z）→ `relations`（元素间关系）。

## 顶层结构（单页模式）

```yaml
meta: {...}        # 页面/风格/数值覆盖（声明 meta.slides 即切多页模式，见下）
palette: {...}     # 色板 token
elements: [...]    # 元素列表（容器内 children 属于容器）
relations: {...}   # glue/overlap/z_override（可选）
anim: {...}        # 页级动画编排组（可选；多页模式写 slides[i].anim——整页编排时间轴）
```

## 动画编排组（anim——声明式时间轴）

元素级 `animation`（配方/behaviors，见 references/animation.md）仍是单元素动画；
**编排组** `anim` 把整页动画的时间轴交给引擎确定性展开（JAnim 时间区段组合语义
的移植 → COM 链式锚定；时序全由引擎导出，组员**不得自带** trigger/delay）：

```yaml
anim:
  mode: succession        # succession | aligned | group（缺省 succession）
  trigger: on_click       # on_click | with_previous | after_previous（根触发）
  start: 0.2              # 根链绝对起点（秒，可选）
  gap: 0.35               # succession 相邻叶间隔（秒，可选）
  items:
    - title               # 字符串简写 = {id}（须是带 animation 的元素，容器/cylinder 拒收）
    - id: card1
      mode: aligned       # 子组（aligned/group 可嵌套 succession）
      items: [card2, card3]
```

- 计时语义/子组嵌套/块排序/负 delay 降级/时间一致性断言见
  references/animation.md「动画组」节；展开产物 `ir.anim_timeline`（绝对秒）+
  `ir.anim_sequence`（AddEffect 序），COM 按序构造并回读比对 delay。
- 示例：`examples/animation/anim_group.yaml`（evidence 28/28）。

## meta.slides（多页序列——演示/课件/宣讲/汇报）

`meta.slides` 每个元素一页；声明后**顶层不得再出现 elements/relations**
（编译期拦截），元素归属按页隔离：

```yaml
meta:
  margin: {l: 0.6, t: 0.6, r: 0.6, b: 0.6}    # 全局打底，页级可覆盖
  framework: {background: ..., header: ..., footer: ...}  # 三页共用的框架层
  slides:
    - title: 封面                                # 可选；report.md 页标题
      elements: [...]                           # 该页元素（每页一组）
      relations: {glue: [...], overlap: [...], z_override: [...]}  # 可选，页内自洽
      margin: {...}                             # 可选页级覆盖（键级 dict 合并）
      framework: {...}                          # 可选页级覆盖（键级 dict 合并）
      params: {text: {min_fs: 8}}               # 可选页级参数覆盖（配置栈页级层，见 meta.params）
      anim: {...}                               # 可选页级动画编排组（见 top-level anim 节）
    - title: 议程
      elements: [...]
      brief: 本月营收环比 +12%，重点讲华东与海外   # 页级意图上下文（覆盖/补充全局）
      notes: 议程讲 3 块：现状 / 方案 / 排期    # 页级备注（演讲者视图）
```

- 备注是页级文本（`slides[i].notes`；单页模式写 `meta.notes`），多行用 YAML
  块标量 `|`；渲染写 notes_slide 部件（零 COM），字号走 `params.text.notes_fs`。
  无备注的页不建 notes part。

- palette 全局共享；**元素 id 唯一作用域 = 页内**（跨页互不感知）；
  遮挡/安全区/文本校验按页隔离——任一页违规 → exit 3。
- footer 的 `{page}` 占位符按实际页号逐页展开（第 1 页 = 1…）。
- 渲染产一文件多 slide；`ir.json` 多页时写 list；COM 按页遍历 Slides(i+1)，
  预览逐页 `preview.png` / `preview-2.png` / …。
- 页数无硬性上限。参考 `examples/deck/`（封面 + 表格议程 + 图表数据页）。

## meta

| 键 | 类型 | 说明 |
|---|---|---|
| `title` | str | 报告/调试用标题 |
| `style_guide` | str | 规则集名：flowchart / ladder / dashboard / deck（see styleguide-rules.md） |
| `slide` | dict | `{w, h}` 英寸，默认 13.333×7.5 |
| `margin` | dict | `{l, t, r, b}` 英寸；安全区＝页内缩 margin |
| `params` | dict | 覆盖数值接口（见下"params 可覆盖键"）；resolve 失败即编译错。**配置栈**：全局 `meta.params` 打底 → 页级 `slides[i].params` 覆盖 → CLI `--param key=value` 顶覆盖（last-wins；`--param` 临时覆盖不改 SPEC）。页级 params 是布局/校验/渲染参数旋钮的页级化（如某页字号硬底/表格 pad），全链路按页取 p |
| `framework` | dict | 图面框架层（背景/页眉/页脚，见下方"meta.framework"节） |
| `template` | dict | 母版版式「提炼/打底」：extract 注入 · seed 打底（见下方"meta.template"节） |
| `notes` | str | 页面备注（演讲者视图；纯渲染零 COM，见下方"备注页"节）。单页模式写 `meta.notes`；多页模式写 `slides[i].notes` 逐页（**多页禁全局 notes**——备注是页级内容） |
| `brief` | str | 意图上下文（用户原始需求，自然语言，默认空）。**全局打底，页级 `slides[i].brief` 覆盖/补充**（与 margin/framework 同语义）。非渲染语义——供 `--fix` 修订器消费（content/advisory 违规的 LLM 依据源与数据红线关联） |
| `transition` | dict | 页面切换（**页间行为，仅多页序列有意义**；单页声明 → 编译错）：全局默认 `{effect, spd?}`，页级 `slides[i].transition` 覆盖（见下方"页面切换"节） |
| `slides` | list | 多页序列：每元素一页（见上方"meta.slides"节）；缺省单页模式 |

## meta.template（母版版式「提炼 / 打底」）

两条腿都以模板风格卡（`template_analyzer.py` 只读分析）为事实源，注入/落点写进
**新产物**；模板 pptx 本身零写入。语法：

| 键 | 类型 | 说明 |
|---|---|---|
| `src` | str | 模板/成品 pptx 路径（相对 SPEC 所在目录解析） |
| `mode` | str | `extract`（提炼：样式卡 → 注入）\| `seed`（打底：以模板为渲染基底） |
| `keys` | list | 仅 extract：注入段白名单（`slide`/`palette`/`framework`/`params`），缺省全开 |
| `layout` | str/int | 仅 seed：目标版式（按名或索引；缺省自动选含 title 者） |

**extract —— 提炼（样式给你，位置自理）**：

- `slide` ← 模板页面尺寸；`palette` 注入主题槽 `accent1..6 + dk1/lt1/dk2/lt2`
  （fill-only：SPEC 已显式声明的同 token 保留 agent 值）；
- `framework.background` ← 母版背景（solid 取色 / grad 取两色 / 否则主题 lt1）；
- `params.font` ← 主题字族双轨（minor→`latin`/`ea`，major→`title_latin`/`title_ea`；
  模板缺 ea 轨则不注入，留默认）；
- 渲染后主题槽写回输出 `theme1.xml` clrScheme——新建形状/图表默认色/取色器即品牌色；
  物证「主题槽注入」背书。

**seed —— 打底（样式留模板，位置用模板占位符）**：

- 渲染器 `Presentation(src)` 为基底，按 `layout` 选中版式 `add_slide`；模板自带
  示例页剥离（母版/版式保留），输出仅 SPEC 页；
- 元素级 `ph`（**仅 text**）：按 idx（int）或占位符名（str）匹配模板占位符，
  文本写入占位符（样式/落点/几何全留模板）；`rect` 仍声明，仅作文本测量输入；
  不进 relations（glue/overlap/z_override 引用 ph 元素 → 编译错）；
- 模板层（母版/版式几何、占位符样式）豁免 G/D/T 校验——不进 IR；
  SPEC 层（文本测量/文本校验）照常；物证「版式引用」（slide rel → slideLayout
  part）+ 逐 ph「ph 填充」。

## meta.framework（图面框架层）

页面级图层：背景垫底、页眉/页脚压顶。**不进 IR**（豁免遮挡/安全区校验，
layout 由渲染器负责，align 用段落对齐实现）。

```yaml
meta:
  framework:
    background: {fill: {grad: ["#FFFFFF", "#EAF1F9"]}}  # 全幅背景：hex/token/{grad:[c1,c2]}
    header: {text: "页眉 · 右侧对齐", align: right, fs: 10, color: deep}
    footer: {text: "机密 · 第 {page} 页", align: right, fs: 9, color: deep}
```

- header/footer 键：`text`(str，空/缺 = 不渲染该层) / `align`(left|center|right，
  默认 params.framework.*_align=left) / `fs`(默认 header 10 / footer 9) / `color`。
- footer 文本内 `{page}` 占位符展开为页码（当前单页恒 1；多页序列逐页编号）。
- 页码偏移：`params.framework.page_offset`（整数可负）→ 显示页码 = 实际页号 +
  offset。典型场景：封面不计页码 → `page_offset: -1` + 封面页页级
  `framework: {footer: {text: ""}}` 清空该页页脚（页级清理与全局声明键级合并，
  同 build_pages 语义）。渲染与物证同规展开。
- 背景 `fill`：solid = hex 或 palette token；grad = `{grad: [c1, c2]}`（端色限字面
  6 位 hex）。背景形状名为 `bg`，页眉/页脚为 `hdr`/`ftr`——**元素 id 不得占用
  这三个保留名**（编译期拦截）。
- 物证：背景全幅 rect + fill 结构/色值核对；页眉/页脚文本存在性。

## 备注页（meta.notes / slides[i].notes）

页级演讲备注：渲染器写 `notes_slide` 部件（演讲者视图可见），**纯渲染零 COM**。

```yaml
meta:
  notes: 单页模式：整页备注            # 或多页模式 slides[i].notes
```

- 多行用 YAML 块标量（`|`），每行一段 run；字号默认 `params.text.notes_fs=12`。
- 无备注的页不建 notes part；`notes` 非字符串 → 编译错 exit 2；
  多页模式写全局 `meta.notes` → 编译错（备注是页级内容，无全局继承）。
- notes 不进 IR 几何（不占 spTree、不参与 G/T/D 校验）——与 framework 同地位；
  ir.json 仅记 `notes` 文本供渲染/物证消费。
- 物证：「备注页」按 slide rel → notesSlide part 解包，a:t 全文去换行后 == SPEC notes。

## brief（意图上下文——--fix 修订器消费）

`meta.brief` 记用户原始需求（自然语言，默认空），**非渲染语义**：不进 IR、
不占 spTree、不参与 G/T/D 校验——它是 `--fix` 修订链（见
wiki/runbooks/fix-loop.md）的意图依据源：

```yaml
meta:
  brief: 制作季度营收摘要：营收 120 亿，同比 +12%，毛利率 34%。   # 全局打底
  slides:
    - title: 封面
      brief: 封面突出"营收 120 亿 · 同比 +12%"                    # 页级覆盖/补充
      elements: [...]
```

- 多页模式 `slides[i].brief` 页级**覆盖**（与 notes 同律：页级非空即取代全局；
  不拼接——意图上下文应页级自洽，build_pages 透传页级值）；
- 引用语义：LLM 侧生成 text/data 时以 brief 原文为**依据**（数据红线）——
  数据字段（data/categories/series）的新值必须能溯源到 brief 原文或标
  `[占位]`，禁止编造；文本字段依据 = brief 引文 / 现有文本改写 / `[占位]`；
- 缺 brief 降级：修订器仅从 title/notes/现文本推断（弱语义），content
  违规转人工指引。brief 非字符串 → 编译错 exit 2。

## 页面切换（meta.transition / slides[i].transition）

页间切换，纯渲染 XML 注入 `p:transition`（零 COM）。切换是**页间行为**——单页
模式声明 `meta.transition` → 编译错（需 `meta.slides`）。

```yaml
meta:
  transition: {effect: fade, spd: slow}     # 全局默认（页缺省时继承）
  slides:
    - title: 页一                            # 未声明 → 继承全局：fade slow
      elements: [...]
    - title: 页二
      transition: {effect: push}            # 页级覆盖；spd 缺省 med
      elements: [...]
    - title: 页三
      transition: {effect: none}            # 显式关闭（XML 不注入）
      elements: [...]
```

- `effect` ∈ `fade|push|wipe|cut|none`；`spd` ∈ `slow|med|fast`（OOXML 定性档，
  无秒级精度）。`push/wipe` 默认从左（`dir="l"`）。
- 页未声明 `transition` → 继承全局默认；`effect: none` 显式关闭该页切换。
- 编译期解析每页有效值（slides[i].transition = 页显式声明优先，否则全局），
  编译产物 `slides[i].transition` 即有效值；IR 携带、渲染按页注入 `p:transition`；
  不进 IR 几何（不占 spTree、不参与 G/T/D 校验）。
- 物证每页一条「页面切换」：none/缺省 → 断言 XML 无 `p:transition`；
  有切换 → 断言子元素 = `p:{effect}` 且 `spd` 相符。
  参考 `examples/transition/`（四页：继承/覆盖/none/覆盖+spd）。

## 元素级超链接（link）

任意非容器元素可挂 `link`（三选一），渲染注入 `cNvPr` 下 `a:hlinkClick`
（零 COM）：

```yaml
elements:
  - id: www
    type: shape
    rect: [0.8, 2.8, 5.2, 0.9]
    text: 外链
    link: {url: "https://example.com"}      # 外部链接
  - id: to_p2
    type: shape
    rect: [0.8, 3.9, 5.2, 0.9]
    text: 跳第 2 页
    link: {slide: 2}                        # 页内跳转（1-based 页号）
  - id: email
    type: shape
    rect: [0.8, 5.0, 5.2, 0.9]
    text: 发邮件
    link: {email: "demo@example.com"}       # mailto 邮件
```

- `url|slide|email` 必须且仅声明其一；`slide` 编译期边界校验（≤ 总页数；
  指向本页的恒等自跳无意义 → 编译错）。
- 容器（stack/dock/graph）不产形状、无从挂 `hlinkClick` → 编译错；
  children 形状（text/shape）可挂，随容器求解出 rect 后同律注入。
  seed 打底的 ph 占位符填充不支持 link（文本写入模板占位符）。
- 渲染：slide → 本包 slide part rel + `action="ppaction://hlinksldjump"`
  （PowerPoint「本文档中的位置」原生格式）；url/email → 外部 hyperlink rel
  （TargetMode=External）。`link` 不进 IR 几何（不参与 G/T/D 校验）。
- 物证每链接一条「链接目标」：`cNvPr/a:hlinkClick@r:id` → 外部 rel 核对原始
  Target == `url` / `mailto:{email}`；内部 rel 核对 part 文件名 == `slide{N}.xml`。
  参考 `examples/link/`（目录页三种链接 + 跳转目标页）。

## palette

token 名 → 三种写法之一：

```yaml
palette:
  prim: {solid: "#2D6CDF"}     # 单色
  grad: {grad: ["#2D6CDF", "#1E88E5"]}  # 渐变
  plain: "#1F2A44"             # 简写 hex
```

引用：style.fill/border/text_style.color/line.color 等写法 = token 名、6 位 hex、
或 `none`（border 专用 = 不描边）。**引用未声明 token = 编译期错误**（spec_validator）。

## elements —— 公共字段

| 键 | 类型 | 说明 |
|---|---|---|
| `id` | str | 全谱唯一；也是渲染后形状的 `.name`（COM 按名查找 / XML 物证同机制） |
| `type` | str | text/shape/image/diagram/line/stack/dock/graph |
| `rect` | [x,y,w,h] | 英寸；**顶层元素必填绝对的放置区**；容器内 children 不需要 |
| `z` | int | 可选显式 z；默认声明序；`relations.z_override` 可覆盖 |
| `group` | bool | 仅容器（stack/dock/graph）：`--com` 时成员 Group 成 Office 组对象 |
| `link` | dict | 元素级超链接：`{url\|slide\|email}` 三选一（见下方"元素级超链接"节）；容器与 ph 占位符元素不支持 |

## 元素分型

### text（文本块）
`text`（内容）、`text_style`（见下）。可选 `style`（bg 底色时启用 cover_label）。
- **行内富文本**：`**加粗**` / `[[强调]]` / `{{UnicodeMath}}`（原生公式，
  写进当前文本框：与文字同行 = 行内式 `m:oMath`，独占一行 = 显示式
  `m:oMathPara`）。公式标记不得嵌在加粗/强调内。

### shape（基本形）
`kind` ∈ `can | diamond | hexagon | oval | parallelogram | rect | rounded_rect |
cylinder`（flow 四族 src/proc/judge/end 是 graph 节点专用，顶层 shape 不可用）。
`text` 可选（有文本则 autofit）；`style: {fill, border, shadow, adjustment?,
border_dash?}`（`border_dash` ∈ `dash|dot|dash_dot` 虚线描边）。
- **cylinder（圆柱复合，仅顶层）**：`slice`（0<slice≤1，1=完整圆柱；<1=剖视
  不画顶面示敞口）、`opacity`（[0,1] 侧壁透明度）、`style.fill` 主色、
  `text/text_style`（居圆柱中部，按侧壁主色自动对比度反色）。
  ir_builder 展开为 5~6 部件（半透明侧壁 + 顶/底椭圆 + 2 条等高弧 + 可选文字），
  owner = 元素 id（遮挡兄弟豁免）；`slice/opacity` 仅 cylinder 支持
  （其余 kind 带它们 → 编译错）。示例 `examples/method/cylinder.yaml`。

### formula（数学公式）
> **先判承载**：公式要放进既有文本框（标题/正文/表格单元格/graph 标签）→ 用
> 文本内联标记 `{{expr}}`（同一行=行内式，独占一行=显示式）；需要一块独立的
> 公式区域才用本元素（单独文本框 + mc 包装）。公式不是必须独立成形状。

`expr`（UnicodeMath 子集表达式，见 formula-omml.md：单字符变量/数字/运算符
`+ - × ÷ = < > ≤ ≥ ≠ ≈ ±`/括号组/分式 `/`/上标 `^`/下标 `_`/根式 `√`/希腊字符；
空格 = 分隔符）+ `text_style.fs`（默认 18）+ 可选 `color`。
- 子集内 → **确定性 OMML 直接注入**（零 Office，PowerPoint 原生识别）；
- 子集外 → 先查**离线模板库**（∑/∏_(i=1)^n 系，命中即零 Word 注入）；
  未命中 → 渲染为**占位文本**，`--com` 时 com_layer 用 Word 批量引擎兜底
  （一次进程吞 N 表达式，产出真 m:oMath）。
- 求和/连乘写 **字符式** `∑_(i=1)^n x_i` / `∏_(i=1)^n x_i`（实测转真 nary，
  且已在离线模板库——命中即注入，免 --com）；
  LaTeX 花括号式 `\sum_{i=1}^{n}` 实测**不**转 nary，勿用。`∫` 产 nary 但
  chr 缺省 → 不收录模板，渲染交 Word 兜底/占位。

### image / diagram（图片与外部图）
`src`（路径；相对路径按 SPEC 所在目录解析）、`visual_bounds: auto`（视觉内容自动
裁剪补偿）。**diagram 多一个逃生通道**：`src` 为 `.vsdx` → 渲染层跳过 →
COM `AddOLEObject` 原生嵌入（双击进 Visio 编辑）。`caption`（元数据）。

**图片占位（B3）**：`src` 可省——改声明 `placeholder`（`true` / 提示字符串）：
渲染层落虚线占位框（文案 = caption > placeholder 串 > `images.missing_key`），
`out_dir/img_prompts.md` 逐条列 id/目标尺寸（in 与 96dpi 像素）/提示词/期望路径。
`src` 文件缺失（未声明 placeholder）同样降级占位框 + 清单，不阻断管线；
`--strict-images`（或 `--param images.strict=true`）→ 占位/缺图即编译错（exit 2）。
diagram 不支持 placeholder（逃生通道必须给 src）。

### table（原生表格积木）

```yaml
- id: tbl
  type: table
  rect: [0.8, 1.8, 11.7, 4.9]
  data:                     # rows×cols 矩阵（首行默认表头）；行/列数由 data 推导
    - ["指标", "Q1", "Q2"]
    - ["营收", 1280, 1520]
  col_widths: [4.0, 3.85, 3.85]   # 可选，英寸；和必须 == rect.w；缺省均分
  header: {fs: 13, fill: ink, color: "#FFFFFF", bold: true}  # 样式 dict 或 false
  body: {fs: 12, fill: soft}
  borders: true              # true（默认色）/ 色值 / none
```

- 原生 `a:tbl`（GraphicFrame），零 COM；单元格文本溢出由 verify **T 家族**机器证明
  （列宽/行高 − 2×cell_pad）。单元格边框手写 `a:tcPr` 四边。
- `header` 缺省 = 深底白字加粗（`params.table.header_fill/header_color/header_bold`）；
  `header: false` 关闭表头行。单元格文本支持数字（自动转字符串）。

### chart（原生图表积木——数据驱动，零 COM）

```yaml
- id: c_sales
  type: chart
  rect: [0.5, 1.6, 7.2, 5.4]
  chart_type: column_clustered    # 见下方族别清单
  categories: [Q1, Q2, Q3, Q4]    # 类别（str/num）
  series:                         # 每序列 values 个数必须 == categories 数
    - {name: 华东, values: [12.4, 15.1, 13.8, 18.2]}
  style:                          # 全部可省；缺省走 params.chart（样式卡）
    legend: right                 # right|bottom|top|left|none
    legend_fs: 9                  # 图例字号(pt)
    legend_color: ink             # 图例字色（palette token/hex）
    data_labels: true             # 数值标签
    label_pos: outside_end        # center|inside_end|inside_base|outside_end|
                                  #   best_fit|above|below|left|right
    label_fs: 9
    label_color: ink
    label_bold: true
    label_format: "0.0"           # 标签数字格式（Excel 记法：0 / 0.0 / 0% / #,##0）
    colors: [acc, accent2]        # 序列色循环（palette token，编译期校验）
    chart_style: 10               # PowerPoint 预设图表样式 1..48
    font_family: "Microsoft YaHei"  # 图表全局字族（缺省 params.font.latin + ea 双轨）
    chart_fill: none              # 图表区填充 none|色（缺省 none=透明，母版透出）
    plot_fill: none               # 绘图区填充 none|色
    gridlines: true               # 数值轴主网格线
    gridline_color: "#E4E9F2"     # 网格线色（浅灰弱化）
    axis_line: true               # 轴线
    tick_fs: 9                    # 轴刻度字号
    tick_color: ink
    value_min: 0                  # 数值轴量程（None=自动）
    value_max: 160
    value_format: "#,##0"         # 数值轴数字格式
    gap_width: 60                 # 柱/条间距（%，Excel 默认 150；收窄显挺拔）
    overlap: -10                  # 簇状重叠%（-100..100）
    line_width: 2.5               # 折线宽度(pt)
    smooth: true                  # 折线平滑
    markers: true                 # 折线数据点标记（line_markers 族恒开）
    donut_hole: 62                # 圆环孔洞（10..90；doughnut 专用）
```
- **chart_type 族别**（17 种）：
  - 柱/条：`column_clustered|column_stacked|column_stacked_100|bar_clustered|
    bar_stacked|bar_stacked_100`（有 gap_width/overlap）
  - 折线：`line|line_stacked|line_markers|line_markers_stacked`（有 line_width/
    smooth/markers）
  - 面积：`area|area_stacked|area_stacked_100`
  - 饼/环：`pie|pie_exploded|doughnut|doughnut_exploded`（无坐标轴；单序列；
    doughnut 有 donut_hole）
- 由 python-pptx `add_chart` 生成原生 chartSpace + 随附 workbook（Excel 源数据，
  双击可编辑图表数据），零 COM。必须顶层元素。
- 序列色缺省走 `params.chart.colors` 循环。
- 图标题不进图（`has_title=False`）——标题/单位说明由 `text` 元素排版。
- **Power BI 式观感缺省**：图表区/绘图区透明（`chart_fill/plot_fill: none`，
  页底/母版透出）；网格线浅灰细线；柱间距收窄；字号/字族统一。
- 数据账目在编译期背书（series.values 个数 == categories）；图表 part 由物证
  按 rId 解析核对。示例 `examples/chart/chart.yaml`。

### line（自由直线）
`x1,y1,x2,y2` + `color, weight, arrow(bool), dash?`（`dash` ∈ `dash|dot|dash_dot`
虚线；0 宽/0 高的线盒合法——端点包围盒语义，用于虚线分区框等）。

### curve（自由曲线）
`rect`（包围盒）+ `points: [[x,y]…]`（**归一化点列 0~1 相对 rect，≥3 个**，
ir_builder 展开为绝对坐标 polyline） + `style: {color, weight, dash?}`（线语义，
无填充）。渲染为 freeform polyline 单形状（非折线连接符）。示意曲线/等高弧等
非数据驱动曲线用此；数据图请用 `chart`。示例 `examples/method/cylinder.yaml`。

### brush（书法矢量字——字形矢量形状）
`rect`（声明盒）+ `text`（字形源，必填）+ `font`（别名 `kai|hei|song|fang|yahei`
或 `.ttf/.ttc` 路径）+ 可选 `align/anchor/spacing`；`style: {fill | grad | image |
alpha}`（三态填充，fill 与 image 互斥）。字形 → 原生 `a:custGeom` 形状（单
`a:path` 保内孔镂空），换机不丢字形。详见 `references/ink-brush.md`。

### icon（矢量图标——Lucide 描边形状）
`rect`（声明盒，正方适配居中）+ `icon`（必填：Lucide 名 `droplet` / 中文关键词
`水滴` / 英文标签；未命中回退 circle-dot）+ 可选 `align/anchor`；
`style: {color, weight}`（描边语义）。图标 → 原生 `a:custGeom` 形状（逐子路径
`a:path`：描边 `fill=none` / 实心 `fill=norm` + `a:ln` 圆头描线），随 palette 着色、
缩放不糊。详见 `references/icon-library.md`。

### stack（栈布局容器——梯形积木）
`orientation: vertical|horizontal`、`align: center|start|end`（十字对齐）、
`gap`（成员间距）、children 只写 `width/height/type/…`。
vertical 账目按高度和，horizontal 按宽度和（≤ 容器边长；`meta.params` 覆盖自适应）。

### dock（停靠布局容器）
`padding: {l,t,r,b}`、children 带 `dock: top|bottom|left|right|fill` + 尺寸 + margin。

### graph（图容器——流程图/组织树核心积木）
自带绝对 rect 放置区，全部内部布局自动：
`start`（入口节点 id）、`nodes: [{id,text,kind}]`、`edges: [{from,to,label?,way?}]`、
`groups: [{id,label,members:[id…]}]`（组包络，label 显示于包围盒左上）、
可选 `orientation / inner_margin / node_w / node_h`。
- kind 四族：`src`（罐形起点）、`proc`（圆角矩形处理）、`judge`（菱形判断）、`end`（椭圆终点）。
- `orientation: horizontal|vertical`（默认 horizontal）。**vertical = 组织树**：层 → 行
  （根上子下），行高 = 面板高 ÷ 层数 × (1−gutter_ratio)，行内节点水平均分；
  跨层连线强制 N/S 正对中点（上者出 S、下者入 N），同层兄弟回退 E/W；
  带标签边默认走真线（标签居中盖线），显式 `way: orth` 才走左右走廊。
  refer 示例 `examples/orgchart/`。暂不做"子节点对齐父节点"（Sugiyama 分层）。
- `way: straight|orth`（horizontal 默认：有 label 自动 orth；orth 回边自动选
  上/下浅走廊，4 段折线（出→竖→横→竖→入）；vertical 走左/右走廊），
  磁吸端口贴正边中点。
- 节点同层同高、列宽自适应（面板宽 ÷ 层数 × (1−gutter_ratio)）、BFS 分层 + 语义序稳定。

## 容器 children 字段

stack/dock children 可用：`id, type(text|shape), text, text_style, style, width, height`
（shape 另加 `kind`）。**children 内不可嵌套容器**（积木是一层原子）。

## text_style

`fs`（字号，不写则 autofit 起于默认）、`bold`、`color`（token/hex）、
`align: left|center|right`。autofit 会向下缩字号直到框内装下（min_fs=4.0 硬底，
缩到底仍超框 = 校验 FAIL 且报告建议拆元素/扩框）。

## relations

```yaml
relations:
  glue:            # COM 绑定连线（BeginConnect/EndConnect 随动语义）
    - {from: id, to: id, label: str, id: 可选}
  overlap:         # 显式声明顶层元素遮挡（合法来源二类之一）
    - {id: A, with: B}    # A 声明（上）与 B 重叠
  z_override:      # 指定元素的显式 z 覆盖
    - {id: name, z: 30}
```

## params 可覆盖键（数值接口——所有 magic number 的唯一事实源）

`params.py` DEFAULTS，SPEC `meta.params` 覆盖任意键（合并报未知键错）：

- `slide.w/h` 默认 13.333/7.5
- `text`: `em_cjk=1.00, em_asc=0.54, line_h=1.2, margin_w=1.03, min_fs=4.0,
  fs0_node=12, fs0_block=18, edge_label_fs=9`
- `style`: `fill/border/text_color/line_color/line_weight/icon_weight/group_fill/group_border/shadow`,
  `body_fs_min=None`——正文下限覆盖（pt）：None 用 styleguide body 下限；
  显式数值 = 作者降准（功能演示/密集表格有意用小字），verify S1b 消费
  （`params: {style: {body_fs_min: 14}}` 即把正文下限降到 14；缺省 None 守规范 16）
- `graph`: `inner_margin=0.18, gutter_ratio=0.18, min_abs_gap=0.08, group_pad=0.3`
- `route`: `bend_clearance=0.10, corner_pad=0.15`
- `formula`: `fs_default=18`（公式积木未写 fs 时的起字号）
- `z_gap`: `edge_label=1, label_group=10`（容器内 z 类阶梯）
- `verify.eps=1e-3`
- `table`: `fs=11, header_fs=12, header_fill=#1F2A44, header_color=#FFFFFF,
  header_bold=True, cell_pad=0.06, border_color=#B8C4D8, border_w=0.75`
- `chart`: `colors=6 色循环, legend_pos=right, legend_fs=9, data_labels=False,
  label_fs=8, label_format=0, tick_fs=9, gridlines=True, gridline_color=#E4E9F2,
  axis_line=True, gap_width=60, line_width=2.0, chart_fill=none, plot_fill=none,
  donut_hole=55`（其余键见 chart 段样式表，缺省不干预）
- `framework`: `header_fs=10, header_color=#8899AA, header_align=left, header_pad=0.15,
  footer_fs=9, footer_color=#8899AA, footer_align=left, footer_pad=0.2, page_token={page},
  page_offset=0`
  - `page_offset`: 页码偏移（整数，可负）——显示页码 = 实际页号 + offset。
    典型用法：封面不计页码，正文从 1 起 → `params: {framework: {page_offset: -1}}`，
    配合封面页页级 `framework: {footer: {text: ""}}` 清空页脚。
    非整数/布尔 → 编译错 exit 2（页码是整数语义）。
- `com`: `follow_test_pt=60, export_scale=100, dispatch_retries=2, dispatch_wait=2.0`
  （Dispatch 瞬态启动失败自动重试，如 `-2146959355` CO_E_SERVER_EXEC_FAILURE）

## 校验拦截速查（违规时到 verify 家族找原因）

| 家族 | 查什么 |
|---|---|
| G 几何 | 安全区/rect 有限正/遮挡合法来源/锚点贴端口+独立重算/orth 结构/同层同高/组包络⊇成员 |
| D 容器 | 节点⊆图面板内容区 / 成员⊆容器 |
| T 文本 | 非空/断行重算一致/水平垂直不溢出/min_fs 硬底 |
| S 规范 | 字号层级/色数上限/配色白名单/必需构件/梯形单调/栈账目 |