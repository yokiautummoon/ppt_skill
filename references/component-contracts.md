# 组件包契约（Component Pack Contract）

> 借鉴 EasySlides 的 component pack contract：每个复合积木（积木 = 展开为多形状
> / 整块图的元素，或引擎展开的页型）在此**显式声明**：renderer 归属、必需输入、
> 背书的 verify 断言。机器唯一事实源 = `scripts/capabilities.py` 的
> `COMPONENT_CONTRACTS`；本表是人读同步版，`tests/test_capabilities.py` 卡
> 两者一致（renderer 模块在场 / required 满减必报错 / 断言子串在 verify.py 在场）。

## 契约原则（fail-closed）

1. **required 满减 → 编译必报错**（exit 2）：契约说"必需"，摘除就拦。
2. **invariants = verify 背书的断言**：契约声明的每条断言必须在 `verify.py`
   源码里有对应检查名（子串核对）——背书不是空话。
3. **renderer = 归属模块**：声明了 renderer 模块，该模块必须在 `scripts/`
   真实存在。
4. **能力级拒收**：积木不支持的能力在编译期拒绝（如容器无动画/锚点），
   不留静默 no-op —— 见 `references/routing-table.md` 总则与 capabilities.py。

## 契约表

| 组件 | kind | renderer 模块 | required（SPEC 键） | verify 背书断言 | 容量 |
|---|---|---|---|---|---|
| `cylinder` | shape | ir_builder / render_pptx | `rect` | `cylinder `（S7 端面叠区保真，alpha 反解闭合） | 3 形状（侧壁+顶/底椭圆） |
| `curve` | element | ir_builder / render_pptx | `rect` + `points` | —（自由 polyline，verify 无专属断言） | — |
| `brush` | element | ink_text / ir_builder / render_pptx | `rect` + `text` + `font` | —（字形→custGeom，物证 4.4b 背书：单路径/三态填充） | 1 形状 |
| `icon` | element | icon_lib / svgpath / ir_builder / render_pptx | `rect` + `icon` | —（图标→custGeom，物证 4.4c 背书：逐子路径描边 fill=none + a:ln 圆头描线） | 1 形状 |
| `typst` | element | typst_compile / render_pptx | `rect` | —（整块为图，语义由 `tests/test_typst_compile.py` 背书：svgBlip 双通道注入/围切） | 1 块 |
| `svg` | element | svg_doc / ir_builder / render_pptx | `rect` + `src` | —（SVG→原生 custGeom，语义由 `tests/test_svg_doc.py` 背书：分组/变换/bbox/fail-closed） | N 片（顶层元素×paint 样式） |
| `table` | element | ir_builder / render_pptx | `rect` + `data` | `表格格`（T 家族：单元格文本 ≤ 单元格，列宽/行高 − 2×pad） | — |
| `chart` | element | ir_builder / render_pptx | `rect` + `chart_type` + `categories` + `series` | —（数据账目编译期已背书） | — |
| `formula` | element | ir_builder / render_pptx | `rect` + `expr` | —（OMML 子集，边界见 references/formula-omml.md） | — |
| `stack` | container | ir_builder / layout_stack | `rect` + `children` | `stack 账目`（S5：children 总尺寸 ≤ 容器） | — |
| `dock` | container | ir_builder / layout_dock | `rect` + `children` | `dock 账目`（S5：top/bottom 高和 ≤ 可用高） | — |
| `graph` | container | ir_builder / layout_graph | `rect` + `nodes` | `节点`（D/G 家族：节点同高且 ⊆ 面板内容区） | — |
| `cover` | page_intent | ir_builder / verify | `page_intent` + `cover` | `页型 cover 必需`（S6 必需构件）、`cover 破格度`（S6 破格度下限） | 4 件（cov_deco/title/sub/meta） |
| `section` | page_intent | ir_builder / verify | `page_intent` + `section` | `页型 section 必需`、`section 贯穿度`（S6 贯穿度下限）、`section 字号层级`（S6 层级） | 4 件（sec_num/title/deco/guide） |
| `problem` | page_intent | ir_builder / verify | `page_intent` + `problem` | `页型 problem 必需`、`problem 贯穿度`（S6 纵向贯穿下限）、`problem 左对齐破格`（S6 非居中） | 3 件（prb_badge/title/items） |
| `versus` | page_intent | ir_builder / verify | `page_intent` + `versus` | `页型 versus 必需`、`versus 均衡`（S6 等宽）、`versus 对称`（S6 居中）、`versus 分色`（S6 对立着色） | 8 件（vsv_panel/title/body ×2 + divider + tag） |
| `route` | page_intent | ir_builder / verify | `page_intent` + `route` | `页型 route 必需`、`route 等步距`（S6 等距推进）、`route 横向贯穿`（S6 铺满版心） | rte_title + N 阶段 + (N−1) 箭头 |
| `panels` | page_intent | ir_builder / verify | `page_intent` + `panels` | `页型 panels 必需`、`panels 网格贯穿`、`panels 面板等宽`、`panels 首板贯穿` | pnl_title + N×(panel/head/body) |
| `columns` | page_intent | ir_builder / verify | `page_intent` + `columns` | `页型 columns 必需`、`columns 栏组贯穿`、`columns 分栏等宽`、`columns 箭头在场` | col_title + N×(head/body) + 可选 bottom + 箭头 |
| `kpis` | page_intent | ir_builder / verify | `page_intent` + `kpis` | `页型 kpis 必需`、`kpis 指标等宽`、`kpis 数值层级`、`kpis 行贯穿` | kpi_title + N×(card/val/lab[+badge]) |
| `cards` | page_intent | ir_builder / verify | `page_intent` + `cards` | `页型 cards 必需`、`cards 网格贯穿`、`cards 卡片等宽`、`cards 顶饰在场` | crd_title + N×(card/badge/head/body) |
| `figure_text` | page_intent | ir_builder / verify | `page_intent` + `figure_text` | `页型 figure_text 必需`、`figure_text 图文分栏`、`figure_text 破格占比` | fgt_title + fgt_fig + 可选 fgt_caption + fgt_body |

## 与"每原型 = 布局代码 + verify 断言"的关系

页型原型（cover/section）是本契约的 page_intent 分量：`required`（引擎展开的
必需输入）、invariants（S6 断言）正好对应 page-intents.md §扩展新原型的五处
改动 + 三处测试——新增原型时先在此登记，再写 `_expand_*` 与 S6 断言，测试卡
两者同时在场。

## 积木级扩展要点（示意）

- 新积木：`scripts/capabilities.py` 的 `COMPONENT_CONTRACTS` 加条目（renderer /
  required / invariants）→ 同步本表 → `tests/test_capabilities.py` 逐个背书
  required 满减必报错。
- 新 renderer 模块：确保 `scripts/` 下真实存在（`renderer_modules_exist` 校验）。