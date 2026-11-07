---
tags: [module]
module: render_pptx
parent: build_ppt
depends_on:
  - formula_omml
  - typst_compile
updated: 2026-09-14
---

# render_pptx — base.pptx 渲染

纯消费 IR：形状 .name=元素 id（COM/物证按名定位）、按 IR z 稳定重排（OOXML 层级 = spTree 文档序）、framework 背景/页眉/页脚、notes 备注页、transition 注入、hlinkClick 超链接、原生 table/chart/formula、ph_info 模板占位。CJK 双轨字体（a:latin+a:ea）。复合积木：`shape.kind: cylinder` 展开 5~6 部件（半透明侧壁+顶/底椭圆+等高弧）、`curve` 渲染 freeform polyline；page_intent 破格展开（cover→cov_* / section→sec_*）由 ir_builder 出 IR、渲染器照常消费（详见 references/page-intents.md）。

`type: typst`：`add_picture(png)` 建常规图片 + `_inject_svg_blip` 手写 SVG part/rel 与
`a:extLst > a:ext[@uri={96DAC541-…}] > asvg:svgBlip` 注入（OOXML 2016+ 双通道）；svg 注入
失败 → `typst_png_fallback`（WARN 降级）。python-pptx `image_content_types` 无 svg，故
add_picture 不接受 svg 产物。详见 wiki/modules/typst_compile.md。

多页模式渲染：`render(irs, compiled, p, out_path, pps=None)`——`pps = pps or [p]*len(irs)`，
逐页取 pps[pi]（页级 params 旋钮：字号/表格 pad 等按页生效）；typst 围切后
rect 零重算（直接消费 ir.typst_size，铁律 1 的排版块对应物）。

**行内富文本（A2）**：`_set_text(..., runs=)` 与 `_fill_table_cell(..., runs=)`
消费 IR runs 逐段建 run——`bold` 段置 `rPr b=1`；`emph` 段取
`params.style.emphasis`（缺省 #C00000）；每段同字号（autofit 后 fs）与双轨
字族。无 runs 时走单 run 旧路径（零行为变化）；渲染器不重解析标记。

**文本内公式**：runs 含 `{formula: expr}` 时按 `richtext.paragraphs()` 切段——
与文字同行 → `_append_math(display=False)` 写 `a14:m > m:oMath`（行内式）；
独占一段 → `display=True` 写 `a14:m > m:oMathPara`（显示式）。公式写进当前
文本框，不新建形状；文本框不额外包 mc（PowerPoint 接受并在自身回存时补包装）。
`type: formula` 仍走 `_render_formula` + `_wrap_formula_mc`（显示式 + mc 包装 +
表达式原文 Fallback）。

**图片占位（B3）**：image 声明 `placeholder` 或 `src` 文件缺失 → `image_placeholder`
（`_render_image_placeholder` 落虚线圆角矩形 sp，文案 = caption > placeholder 串 >
`images.missing_key`，几何直接取 IR rect）；显式 `placeholder` 的框进 stage5
物证（`占位框 {id}`，rcx 3b 段）。diagram/.vsdx OLE 通道不变。

**书法矢量字（C3，`type: brush`）**：`_render_brush` 建 `add_shape(RECTANGLE)` →
`_set_custgeom` 把 `a:prstGeom` 换成字形轮廓 `a:custGeom`（一个 `a:path` 内含全部
子路径，保 口/日 内孔镂空）→ 三态填充（solid / `gradFill` / `_set_picture_fill`
写 `a:blipFill` + `get_or_add_image_part` rel）。字形路径由 `ink_text` 现算（艺术
路径，非几何）；元素 rect 已由 ir_builder 定（铁律 1 不破）。详见 references/ink-brush.md。

**矢量图标（B1，`type: icon`）**：`_render_icon` 建 `add_shape(RECTANGLE)` →
`_set_custgeom_stroke` 把 `a:prstGeom` 换成图标轮廓 `a:custGeom`（**逐子路径**一条
`a:path`：描边项 `fill="none"`、实心项 `fill="norm"`）→ 形状无填充（`a:noFill`）+
形状级 `a:ln`（色/宽/`cap="rnd"` 圆头/`a:round` 圆角连接）。子路径由 `icon_lib`
现算（图标路径非几何）；元素 rect 已由 ir_builder 定（铁律 1 不破）。
**与 brush 相反**：图标须分 path 描边（非单 path 填充）。详见 references/icon-library.md。

**Morph 平滑切换（C3）**：`_inject_transition` 对 `effect=morph` 走 `_inject_morph`——
`mc:AlternateContent > mc:Choice[Requires=p159] > p:transition(p14:dur) > p159:morph
[option=byObject]` + `mc:Fallback > p:fade` 兼容包，插在 `p:clrMapOvr` 之后。
dur 毫秒紧跟 p14（缺省 700），跨页同名对象自动补间。