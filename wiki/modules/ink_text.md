---
tags: [module]
module: ink_text
parent: render_pptx
depends_on: []
updated: 2026-10-17
---

# ink_text — 书法矢量字字形矢量化

C3 视觉补充：把字体**字形**轮廓矢量化成归一化子路径，供 `render_pptx._set_custgeom`
写进原生 `a:custGeom` 形状。换机不丢字形（字形成为几何，不再依赖字体），且可渐变 /
图片填充 / 缩放不糊。定位 = **艺术路径产出器**：只出「字形路径 + ink 包围盒（em 单位）」，
元素 rect 仍由 ir_builder 定（铁律 1 的 brush 对应物）。

## 接口
- `font_file(name)` — 别名（kai/hei/song/fang/yahei）→ Windows 字体目录；亦接受绝对
  `.ttf/.ttc` 路径。找不到 → `FileNotFoundError`（fail-closed）。
- `measure(text, font, spacing=0.0)` → `(w_em, h_em)`：ink 紧密包围盒（em 单位）。
  ir_builder `_emit_brush` 据此把声明盒等比适配成字形盒。
- `subpaths(text, font, scale=4000.0, spacing=0.0)` → `(subs, vb_w, vb_h)`：归一化子路径
  （平移到原点、y 翻转成向下、乘 scale）。subs = `[{start, segs:[('L',x,y)|('C',x1,y1,
  x2,y2,x3,y3)], closed}]`。

## 实现要点
- 字体解析用 fontTools `TTFont`（lru_cache）：glyphSet + cmap + unitsPerEm。
- 排布：逐字按 `hmtx` 前进量平移，`TransformPen` 缩放 1/upm 画进 `pathops.Path`。
- **并集去重叠**：`path.simplify(fix_winding=True)` 去笔画自重叠，单路径填充不镂空。
- **二次→三次**：`_Rec._qCurveToOne` 用 `_getCurrentPoint()` 把字体二次贝塞尔转三次
  （custGeom 只支持三次）。
- y 轴翻转：字体 Y 向上，custGeom Y 向下 → `tr = ((x-x0)*scale, (y1-y)*scale)`。

## 依赖
`fontTools` + `skia-pathops`（win_py 已装）。

## 消费方
`render_pptx._set_custgeom`（写 a:custGeom）；`ir_builder._emit_brush`（measure 适配）。
能力档案 `capabilities.COMPONENT_CONTRACTS["brush"]`（renderer 含 ink_text）。
详见 references/ink-brush.md。
