# 矢量图内化（type: svg）+ 相对坐标层（rect_kind: ratio）—— agent 启发规范

> 目标：让 agent **自适应地、有品地**插入精美矢量图，且产物是**原生 DrawingML
> 形状**（可缩放 / 换色 / 逐形状编辑 / 换机不丢），非位图。本文 = 决策规范
> （何时用哪个）+ 图式目录（画出哪些）+ 尺寸落位（用 ratio 自适应）。
> 机器事实源：`scripts/svg_doc.py`（解析）。几何唯一源 = ir_builder（铁律 1）。

## 一、什么时候用 `type: svg`（决策规范）

三条精美图形通道，按"可编辑性 × 排版复杂度 × 定位需求"选：

| 通道 | 宜用 | 忌用 |
|---|---|---|
| **`type: svg`（本文）** | **图形为主的示意图**：时间线 / 流程 / 雷达 / 分层堆叠 / 环形循环 / 对比矩阵 / 注解示意——需要**可缩放、可换色、可逐形状编辑**的精密矢量图 | 重排版整段（多栏文本/表格/公式混排）；照片位图 |
| `type: typst`（references/typst-chain.md） | **复杂排版整块**：简历/双栏文档/数学公式/多栏图文——产物是 SVG+PNG **图块**（不可逐形状编辑），适用于"整页为图" | 需要逐形状换色/编辑、或要与周边形状精确对齐的场景 |
| `type: image` | **位图**：实拍照片、数据图（Python 出图）、无法矢量化的图 | 需要放大不糊、换主题色、可编辑 |

**判据**：想让它"像一个会动的几何"（换色、缩放、与其他形状咬合）→ `svg`；
想让它"像一篇排版精良的文档"→ `typst`；是"真实世界影像" → `image`。
**铁律**：`svg`/`typst`/`image` 都**须顶层声明**（不进容器 children，与 chart 同律），
`rect` 固定、整块多形状/多片。svg 内文案仍属内容，受 brief 溯源约束（数据红线）。

## 二、图式目录（archetypes）——agent 只填数据 + 选槽

每原型给 **SVG 骨架**（`src` 指向 assets/ 或内联 `svg:`）+ **数据槽** +
**建议相对尺寸/位置**（`rect_kind: ratio`）。要"精美" = 用审定骨架 + 填数据，
**不即兴排版**（agent 无视觉，即兴 = 翻车）。

| 原型 | 用途 | 建议占比/位置（ratio, area=content） | 数据槽 |
|---|---|---|---|
| **时间线 timeline** | 里程碑/演进/计划阶段 | x:0.55–0.95, y:0.22–0.80（右半栏） | 阶段列表 {年份, 标题, 说明}；节点数 3–6 |
| **横向流程 process** | 步骤链/通路（比 graph 容器更"图形化"） | x:0.12–0.95, y:0.55–0.85（贯穿版心） | 步骤列表 {标题, 说明}；3–6 步 |
| **雷达 radar** | 多维能力/评分对比 | x:0.56–0.94, y:0.25–0.75 | 维度 {轴, 值}；轴 3–10（样例 assets/figures/radar.svg） |
| **环形循环 loop** | 阶段循环/反馈闭环 | 居中或右栏，正方 | 节点列表 {阶段, 说明}；3–6 节 |
| **分层堆叠 stack-layers** | 体系分层/架构层级 | x:0.60–0.95, y:0.25–0.78 | 层列表 {层名, 说明, 相对厚度}; 3–6 层 |
| **注解示意 callout** | 产品/结构局部放大 + 引线 | 左图 + 右侧引线标注 | 底图 + 标注列表 {锚点, 文本} |
| **对比矩阵 matrix** | A×B 双维对比/占位判定 | 左栏或全版心 | 行列标签 + 单元格 {值/布尔} |

**尺寸落位（关键）**：图块与文字并置时，用 `rect_kind: ratio` 让图占"内容区
某百分比"，版式随 `meta.slide`/`margin` 自适应（见第三/四节）——不用再手算
绝对寸，agent 只给意图（"右半栏占 40%、距顶 22%"），引擎定几何。

## 三、语法（type: svg）

```yaml
- id: fig_radar
  type: svg
  rect: {x: 0.56, y: 0.25, w: 0.38, h: 0.50}   # ratio 分数的 dict（见第五节）
  rect_kind: ratio
  src: assets/figures/radar.svg                 # 外链文件
  # 或内联源码（二选一，互斥）：
  # svg: |
  #   <svg xmlns='http://www.w3.org/2000/svg'>...</svg>
  fit: contain                                  # contain(默认,保宽比居中)/stretch
  style: {}                                     # 预留：palette token 换色（暂空）
```

- `src`（现有 .svg 文件）**xor** `svg`（内联源码），且 `fit ∈ {contain, stretch}`。
- 解析（`svg_doc.parse`）→ 按**顶层元素**分组，组内按 paint（fill 色/stroke 色+宽）
  再切分 → N 片原生 custGeom 形状（异色必须拆形状，因为 custGeom `a:path` 只能
  `fill=norm|none`）。子路径含 defs/symbol + `<use>` + `<g transform>`（含 y 翻转）。
- **fail-closed**：遇 `<image>/<text>/<filter>/<clipPath>/<mask>/渐变/pattern/外链
  use/CSS <style>` → 编译期 `SvgDocError`（exit 2，含元素定位），**绝不静默降级**。
  渲染树节点上带 `filter=` / `clip-path=` / `mask=` **属性**（引用 defs 定义的滤镜/
  裁剪/遮罩）同样 fail-closed——绝不静默丢效果；`<defs>` 内未引用的定义是惰性内容，
  被容忍（不影响渲染）。
  v1 局限：fill-opacity/stroke-opacity 忽略、`url(...)` 渐变拒绝——要半透明/渐变
  效果，直接改 fill 色 + 预分层，别指望 SVG opacity 透传。

## 四、为什么不直接"贴一张 PNG"——原生 DrawingML 的意义

`type: svg` 产物 = Office 原生 `a:custGeom` 形状，不是位图：
- **可缩放**：矢量精度，放大不糊；`fit: stretch` 还能拉
- **可换色**：每条 `a:path` 的 `fill`/`a:ln` 是形状级颜色，随 palette/主题换
- **可编辑**：PowerPoint 里 `右键 → 转换为形状` 后逐形状可改
- **可动画/可挂链接**：N 片 = N 个 named 形状，能力档案 `svg: animatable + linkable`
- 对比 `typst`（图块不可逐形状编辑）与 `image`（位图）——见第一节选型。

## 五、相对坐标层（rect_kind: ratio）—— 自适应布局的关节节点

**给意图、引擎定几何**的杠杆：`rect` 写**内容区的 0–1 分数**，版式随
`meta.slide`/`margin`/页型自动重排。这是"自适应地插入矢量图"的**定位底座**。

```yaml
meta:
  slide: {w: 13.333, h: 7.5}
  margin: {l: 0.6, t: 0.6, r: 0.6, b: 0.6}   # 内容区 = 13.333−0.6×2 = 12.133×6.3
elements:
  - id: band
    type: shape
    rect_kind: ratio                          # 矩形占比定位
    rect: {x: 0.0, y: 0.12, w: 1.0, h: 0.035} # 顶端通栏细条
    area: content                             # content(默认)/slide(整版出血)
```

- `rect_kind ∈ {absolute(默认), ratio}`；`ratio` 时 `rect` 为 dict `{x,y,w,h}`，
  `x/y/w/h ∈ [0,1]`、`w/h>0`、`x+w≤1`、`y+h≤1`（越界编译期 exit 2）。
- `area: content`（默认）= 页内容区（slide−margin，逐页）；`area: slide` = 整页
  （出血/背景）。
- **解析在 build_pages 版心边距收敛后**（编译期糖，铁律 1：IR 只见绝对 rect）。
- **容器 children 不支持 ratio**（求解器产 rect）。
- 用途：图块占右半栏 40%、文字自适应；封面通栏；背景出血；任何"跟画布走"的布局。

## 六、观感复核约定

`svg`/`ratio` 的**观感**（形状是否"精美"、比例是否协调）agent 无视觉无法自查——
产物交付前请用户目视复核；形状数/异常颜色等机器可查的由物证 + design 体检背书
（svg 块现计入视觉主体，见 scripts/report.py）。