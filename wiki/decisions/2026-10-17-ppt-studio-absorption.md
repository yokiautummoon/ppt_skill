---
tags: [decision]
parent: root
status: done
updated: 2026-10-17
scope: 借鉴 bvb6417/ppt-studio——A 档（A1 版式多样性 / A2 排版规范 / A3 量化规范）与 B 档（B1 图标库 / B2 设计 DNA / B3 图片占位 / B4 COM 溢出回读 / B5 字体嵌入）全量内化；C1/C3 作视觉补充
---

# 决策：ppt-studio 借鉴（A/B 档内化 + C1/C3 视觉补充）

## 背景

2026-10-17 调研 GitHub `bvb6417/ppt-studio`，逐条对照本 skill 的缺口，
按用户批示执行：**内化 A、B 档中提到的优势；C1、C3 作为本项目的视觉补充**。
另有两项方案确认：A2 采用富文本标记（`**bold**` / `[[emphasis]]`）；
C1 聚焦科研三件套（problem / versus / route）。

候选分级（调研结论）：

- A 档（设计质量断言）：A1 页级版式多样性、A2 排版审美断言、
  A3 量化设计规范。
- B 档（工程与素材能力）：B1 矢量图标库、B2 设计 DNA 分析、B3 图片占位 +
  提示词文件、B4 COM 真实溢出回读、B5 字体嵌入/可移植。
- C 档（视觉补充，按需）：C1 科研页型（problem/versus/route）、
  C3 Morph 切换 + 书法矢量 + 图片填充文字。

## 决策

### 批次 1（本决策已落地）：A1 + A2 + A3 + B2

**A2 富文本标记**（`scripts/richtext.py` 新建）：

- 语法：`**加粗**` / `[[强调]]`，嵌套只允许 `**[[…]]**`；标记交叉、空标记
  → `RichTextError` → 编译 exit 2（fail-closed，不猜作者意图）。
- 解析只发生一次：compile 校验 → ir_builder 存 `text`（plain，供布局测量）
  + `runs`（供渲染）；渲染/COM 不重算文案（铁律 1 的文案对应物）。
- 覆盖范围：element text、table cell、graph node/edge/group label。
- 渲染：多 run，加粗 `font.bold`，强调色 = `style.emphasis`（默认 `#C00000`）。
- 物证：`render_check_xml` 逐 run 核对段数/纯文本/强调色。

**A1 版式多样性**（`verify.check_layout_variety`）：

- 签名 = 非标题视觉主体的（4×3 网格落位, 尺寸档 S/M/L, 类型/子类）排序元组；
  换文案/换配色不改签名；line 与小面积装饰不参与。
- 多页模式且内容页数 ≥ `min_pages`（默认 5）才判；不同版式数 ≥
  max(`min_distinct`, ⌈页数×`distinct_ratio`⌉)，同签名 ≤ `max_same`（默认 3）。
- page_intent 页（cover/section）不参与内容版式统计。
- attribution = advisory（换骨架/并页），不阻断渲染。

**A3 量化设计规范**：

- `styleguides.QUANTITATIVE` = 推荐值可读副本（字号分层/线宽/行距/饱和填充
  面积/强调数/标题字数/版式复用/图片数）。
- 判定阈值仍归 `params.verify.typography` / `layout_variety`（数值接口单一
  事实源）；人读版 `references/design-norms.md`。
- verify S10 排版断言（全部 advisory）：`[[强调]]` run 数 ≤ max_emphasis；
  标题字数 ≤ max_title_cjk（CJK=1、纯西文 2 字符=1）；正文 CJK 字数区间；
  标题字号下限（默认关闭，可用 `--param verify.typography.title_fs_min=24`
  启用）。

**B2 设计 DNA**（`template_analyzer`）：

- 逐页 DrawingML 统计：run 数/加粗/字号（`a:rPr@sz`）/文字色
  （`solidFill/srgbClr`）/latin+ea 字族/形状构成（`a:prstGeom@prst`）/
  图片/表格/图表数；缺 `a:rPr` 的 run 计为继承样式。
- 全局聚合（sizes/colors/fonts/shape_mix 前 N、`pages_with_picture`、
  `size_range`）；`stylecard.md` 增加「设计 DNA」段。
- 纯 zip+lxml，不依赖 python-pptx；模板无页返回空统计。

### 顺带修正

- `layout_graph`：显式 `way: straight` 不再被静默改写为走廊——只有缺省
  straight 遇实际穿越才自动改 orth；残留穿越交 G13 拦截（作者意图优先，
  与 2026-10-09 连线治理决策一致）。

## 取舍公开

- **A3 表不参与判定**：量化表是文档/风格卡比对用的推荐值，避免阈值双源；
  机器判定继续走 params。
- **A1/A2 默认 advisory 而非 exit 3**：信息取舍与审美是语义裁定，机械修订
  收敛不了；阻断会误伤合理破格。需要强约束时由 params 收紧。
- **富文本不引入 HTML/Markdown 全语法**：只保留两个标记，降低解析歧义与
  作者心智负担；颜色/字号仍由样式层统一，避免逐字上色。
- **B1/B3/B4/B5、C1/C3 分批落地**：各批次各自补验收记录（图标库需素材与 OOXML
  端口；图片占位涉及 strict 闸门；字体嵌入依赖 COM；科研页型须按 page-intents
  「每原型 = 布局代码 + 断言」协议落地）。**全部批次已落地 → status: done**。

## 落地验收（批次 1，done）

- 代码：richtext.py（新）、spec_compile.py、ir_builder.py、render_pptx.py、
  render_check_xml.py、verify.py、build_ppt.py、attribution.py、
  styleguides.py、template_analyzer.py、layout_graph.py、params.py。
- 测试：`tests/test_deck_rules.py` 33/33（新：富文本/排版断言/版式多样性/
  渲染物证；后续追加设计体检 8 项 → 41/41）；run_analyzer 14/14（+设计 DNA）；test_graph_contract 38/38
  （显式直线用例）；mutations 129/129、regression 27/27、其余套件全绿。
- 文档：SKILL.md、references/design-norms.md（新）、wiki 模块页
  params/ir_builder/spec_compile/render_pptx/render_check_xml/verify/
  styleguides/template_analyzer、_index.md、_log.md。

## 落地验收（批次 2，done：B3 + B5 + B4）

- B3 图片占位：`type:image` 支持 placeholder 串/布尔 → 占位框 + img_prompts 清单
  + `--strict-images` 闸门；新测试 test_images 25/25。
- B5 字体可移植：params.font.portable/portable_list；COM 请求 EmbedTrueTypeFonts
  + `_scan_embedded_fonts` 核对；新测试 test_font_embed 15/15。
- B4 COM 溢出回读：com_layer._readback_overflow（TextFrame2.BoundHeight 实高
  vs 框内高）；新测试 test_overflow_readback 9/9。
- 文档：wiki 模块页 com_layer/params/render_pptx/render_check_xml、references
  pipeline/spec-v2-language、SKILL.md、_index.md、_log.md。

## 落地验收（C1，done：科研三件套页型）

- 代码：capabilities.py（PAGE_INTENT_CAPS +problem/versus/route +
  COMPONENT_CONTRACTS 三行 + PAGE_INTENT_ID_PREFIX）、ir_builder.py
  （_expand_problem/versus/route）、spec_compile.py（_check_page_intent 三分支）、
  verify.py（_s_intent_problem/versus/route）、params.py（page_intent 三段）、
  routes.py、references/component-contracts.md、references/routing-table.md。
- 示例：examples/research/sci.yaml（3 页 problem/versus/route）全链 63/63 物证 +
  README.md。
- 测试：run_mutations 科研段（对照 3 + 编译负例 8 + IR 负例 6）→ 146/146；
  regression +research-sci → 29/29；test_capabilities 103/0；test_routes 34/0。
- 契约：每原型 = 布局代码（_expand_*）+ verify 断言（_s_intent_*）；破格指标
  均为**反向断言**（problem 贯穿度/左对齐、versus 均衡/分色/对称、route 等步距/
  横向贯穿）——把破格修正回刻板即触发 exit 3。
- 文档：references/page-intents.md §7（+审定菜单表 3 行）、CLAUDE.md、SKILL.md、
  _index.md、_log.md。

## 落地验收（C3，done：Morph 切换 + 书法矢量字 + 图片填充文字）

- Morph 平滑切换：`transition.effect=morph`（+ 可选 dur 100~5000ms，仅 morph）→
  `_inject_morph` 写 `mc:AlternateContent > Choice[Requires=p159] > p:transition
  (p14:dur) > p159:morph[option=byObject]` + `Fallback > fade`；物证 §4.7 核对；
  跨页**同名对象**自动补间（examples/ink 2 页 ink_* 同名）。
- 书法矢量字 `type: brush`：字体字形 → **原生 `a:custGeom` 形状**（单 `a:path`
  内全部子路径 → 口/日 内孔镂空；二次→三次曲线转换），三态填充 = 实色 / `gradFill`
  / `blipFill`（图片填充文字，形状级 blip + `get_or_add_image_part` rel）；换机不丢
  字形、可缩放/渐变/图片填充。新模块 scripts/ink_text.py（fontTools + pathops）。
- 代码：spec_compile.py（`_check_brush` + transition morph/dur + ELEMENT_TYPES brush）、
  ir_builder.py（`_emit_brush` ink 适配）、render_pptx.py（`_set_custgeom` /
  `_set_picture_fill` / `_render_brush` / `_inject_morph`）、render_check_xml.py（§4.4b
  brush + §4.7 morph）、capabilities.py（ELEMENT_CAPS brush + COMPONENT_CONTRACTS brush）、
  spec_validator.py（PER_TYPE brush）。
- 示例：examples/ink/ink.yaml（2 页：brush 三态填充 + Morph）全链 41/41 物证。
- 测试：run_mutations C3 段（morph 4 负例 + brush 6 负例 + ink 适配）→ 162/162；
  regression +ink → 30/30；test_capabilities 107/0（brush required 满减背书）。
- 文档：references/ink-brush.md（新）、references/ooxml-notes.md §16–18、
  references/component-contracts.md brush 行、CLAUDE.md、SKILL.md、_index.md、_log.md、
  wiki/modules/{render_pptx,ir_builder,spec_compile,render_check_xml,capabilities}.md。

## 落地验收（B1，done：矢量图标库）

- 矢量图标 `type: icon`：Lucide 图标（`assets/icons/lucide.json` 1857 枚，ISC）→
  **原生 `a:custGeom` 描边形状**（**逐子路径**一条 `a:path`：描边项 `fill="none"` /
  实心项 `fill="norm"` + 形状级 `a:ln` 色/宽/`cap="rnd"`/圆角连接——**与 brush 单 path
  填充相反**）；`icon` 名/中文关键词/英文标签解析（未命中回退 circle-dot）；随 palette
  着色、缩放不糊、换机不丢。新模块 scripts/icon_lib.py（图标路径产出器）+
  scripts/svgpath.py（SVG path/图元解析，Q/T 与椭圆弧 A 转三次贝塞尔，纯 stdlib）。
- 代码：spec_compile.py（`_check_icon` + ELEMENT_TYPES icon）、ir_builder.py
  （`_emit_icon` 正方适配）、render_pptx.py（`_set_custgeom_stroke` / `_render_icon`）、
  render_check_xml.py（§4.4c icon）、capabilities.py（ELEMENT_CAPS/COMPONENT_CONTRACTS
  icon）、spec_validator.py（PER_TYPE icon）、params.py（style.icon_weight）。
- 示例：examples/icon/icon.yaml（2 页：图标画廊 + 图标/特性卡）全链 110/110 物证。
- 测试：run_mutations B1 段（icon 5 负例 + icon_lib 解析 + IR 正方适配）→ 173/173；
  regression +icon → 31/31（后 +showcase → 32/32）；test_capabilities 110/0（icon required 满减背书）。
- 文档：references/icon-library.md（新）、references/ooxml-notes.md §19、
  references/component-contracts.md icon 行、CLAUDE.md、SKILL.md、_index.md、_log.md、
  examples/icon/README.md、wiki/modules/{icon_lib(新),render_pptx,ir_builder,spec_compile,
  render_check_xml,capabilities}.md。

## 剩余批次

- 无——A/B 档内化 + C1/C3 视觉补充**全部落地**。

