---
tags: [module]
module: icon_lib
parent: render_pptx
depends_on: [svgpath]
updated: 2026-10-17
---

# icon_lib — 矢量图标库（Lucide → 归一化子路径）

B1 内化：把 Lucide 图标 JSON（`assets/icons/lucide.json`：`{name: {"n": [[tag, attrs],…],
"t": [tags]}}`，24×24 viewBox、描边式）解析成统一子路径表，供 `render_pptx`
写进原生 `a:custGeom` 形状。换主题色即随 palette、缩放不糊、换机不丢。

定位 = **图标路径产出器**：只出「子路径 + viewBox 尺寸 + 实心子路径索引」，
元素 rect 仍由 ir_builder 定（铁律 1 的 icon 对应物）。

## 接口
- `names()` — 全部图标名（有序）。`exists(name)` — 是否在场。
- `find(keyword, limit=8)` — 按中文关键词（内置 ZH→EN 映射）/ 英文名 / 英文标签
  检索（名字精确 100 / 名字含 60 / 标签精确 40 / 标签含 30），按相关度排序。
- `resolve(name_or_kw, default='circle-dot')` — 名或关键词 → 确定图标名；
  未命中 **fail-soft 回退** default。
- `subpaths(name, scale=1000.0)` → `(subs, vb_w, vb_h, filled)`：
  subs = `svgpath` 子路径表（归一化 ×scale、y 向下）；`filled` = 实心子路径下标
  frozenset（谓词 = Lucide 图元有 `fill` 属性，如 `chart-scatter` 的散点）。

## 实现要点
- `_data()`（lru_cache）一次性载入 1857 图标。
- 每图元经 `svgpath.node_to_subpaths` 解析（path 串 M/L/H/V/C/S/Q/T/A/Z + 基础图元）；
  二次贝塞尔 Q/T 与椭圆弧 A 均转三次（custGeom 只支持三次）。
- `_scaled` 仅做 **×scale + 取整**（视图盒原样 24×24，不落位——落位属布局）。

## 依赖
`svgpath`（自研，纯 stdlib）。**无第三方依赖**。

## 消费方
`ir_builder._emit_icon`（resolve + 正方适配）；`render_pptx._render_icon`
（subpaths → `_set_custgeom_stroke`）。能力档案 `capabilities.COMPONENT_CONTRACTS["icon"]`
（renderer 含 icon_lib/svgpath）。详见 references/icon-library.md。
