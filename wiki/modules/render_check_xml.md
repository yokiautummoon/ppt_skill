---
tags: [module]
module: render_check_xml
parent: build_ppt
depends_on:
  - formula_omml
  - formula_templates
  - layout_rect
updated: 2026-09-10
---

# render_check_xml — OOXML 物证

stage5 解包 base.pptx：逐页核对形状 .name/rect/z 序/framework/备注文本/hlinkClick rel 目标/transition XML/表格单元格、`type:typst` 双通道（`typst PNG fallback <id>`：blip@r:embed → .png；`typst SVG 矢量 <id>`：extLst/ext/svgBlip → .svg part 且 in 包内；无 svgBlip → 降级合法放行）。证据链守护——"看起来对了"不算，物证数断言才过（regression CASES 期望数背书）。

**行内富文本（A2）物证**：文本元素有 `runs` 时核对段数（XML a:r 数 == IR
runs 数）、纯文本拼接（== IR plain text）、强调色（`emph` 段 srgbClr ==
`params.style.emphasis`）；表格有 `cell_runs` 时逐标记单元格核对段数与文本。
`_text_run_styles` 提取 (text, sz, bold, color) 四元组。
**文本内公式物证**：runs 含 `{formula:…}` 时核对 `a14:m` 数 == IR 公式段数，
并用 `richtext.paragraphs()` 重算形态——同段有文字=行内 `m:oMath`、独占一段=
显示 `m:oMathPara`，XML 两侧计数须一致（`公式形态 {id}`）。standalone
`type: formula` 仍走 `a14:m > m:oMathPara > m:oMath` + mc Fallback 原文检查。

**图片占位（B3）物证**：image 声明 `placeholder` 时核对 name=id 的 sp 在场且
rect == IR rect（`占位框 {id}`）。
**书法矢量字（C3）物证（§4.4b）**：brush 元素核对 name=id 的 sp 在场且 rect == 字形
盒（IR）→ `a:custGeom` 在场 → **`a:pathLst` 内 `a:path` 数 == 1**（保内孔镂空）→
三态填充（image→`a:blipFill` rId 目标在包内 / grad→`a:gradFill` / 否则
`a:solidFill/srgbClr` == 声明色）。
**矢量图标（B1）物证（§4.4c）**：icon 元素核对 name=id 的 sp 在场 → `a:custGeom`
在场 → 逐子路径描边（`a:path` 数 ≥1 且 `fill="none"` 数 ≥1）→ `p:spPr/a:ln` 在场且
`cap="rnd"` → `a:ln` 的 `a:solidFill/srgbClr` == 声明色（注意形状属性容器是 **`p:spPr`**，
其子才是 `a:`，XPath 写成 `a:spPr/a:ln` 会找不到）。
**Morph（§4.7）**：`AlternateContent >
Choice[Requires=p159] > p:transition > p159:morph[option=byObject]` 在场 + Fallback
含 fade + `p14:dur` 一致。
