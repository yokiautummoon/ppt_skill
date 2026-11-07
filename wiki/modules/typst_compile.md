---
tags: [module]
module: typst_compile
parent: build_ppt
depends_on:
  - spec_compile
updated: 2026-09-14
---

# typst_compile — typst 复杂精美排版链路

把 [typst](https://typst.app)（文本/多栏/表格/数学/ceTZ 矢量绘图）作为一类确定性积木
接入管线：SPEC `type: typst` → stage1.5 用官方 **typst CLI** 编译出 **SVG 矢量 + PNG
300ppi** 双产物 → 渲染层双通道注入图块（整块为图，不可逐字编辑，内容型积木）。

## 链路与位置

`spec_compile`（三源互斥/顶层限制/外链存在/design 拦截，exit 2）→ **stage1.5
`compile_all`**（build_ppt 在 stage1 与 stage2 之间调用）→ `ir_builder`（透传
`svg`/`png`/`typst_size`）→ `render_pptx`（PNG add_picture + SVG svgBlip 注入）→
`render_check_xml`（逐块核对 PNG fallback rId + SVG part）。

## 几何唯一源（铁律 1 的排版块对应物）

typst 页面尺寸 = 元素 `rect`（`1in = 72pt`）→ 产物 viewBox 与目标框 **1:1**，
渲染零重算。用户 preamble 自带 `#set page(...)` 与 rect 不符 → WARN（渲染仍按
rect 落版，可能变形）。

## 关键 API（scripts/typst_compile.py）

- `CLI = scripts/typst-cli/typst.exe`（官方 typst 0.15.x Windows 二进制；`cli_available()` 探测）
- `build_source(e, rect, base_dir)`：注入 `#set page(width/height/margin: 0pt)`（用户 preamble
  含 `#set page` 时跳过）+ `#set text(font: (Microsoft YaHei/SimSun/Times New Roman), size: 11pt)`
  + preamble + `#let <k>=<v>` vars + 正文
- `compile_one(src, base_path)` → `(svg_path, png_path)`（`-f svg` 与 `-f png --ppi 300`）
- `compile_all(compiled, out_dir, base_dir)`：遍历 slides，产物落
  `<out>/typst_cache/<page>_<id>.{typ,png,svg}`，写回 `e["_typst"] = {svg,png,typ,size}`；
  语法错误 → `TypstCompileError`（含文件/行号/源码片段）→ exit 2

## 双通道渲染（OOXML 2016+ SVG 规范）

`a:blip`（栅格 PNG fallback rId）+ `a:extLst > a:ext[@uri={96DAC541-…}] > asvg:svgBlip`
（矢量 SVG rId）。PPT 2016+ 渲染矢量、旧版渲染 PNG。python-pptx 无 svg 支持
（`image_content_types` 无 svg），故手写 `Part`+rel，见 render_pptx `_inject_svg_blip`。
svg 注入失败/缺 svg 产物 → 降级纯 PNG，组件银行记 `typst_png_fallback`（WARN 不阻断）。

## 关键坑（实证）

- **PyPI typst-py 只支持 pdf/png，不支持 svg**——唯一 SVG 通道 = 官方 typst CLI。
- python-pptx `Part(partname, content_type, package, blob)`：blob 在最后（1.0.2）。
- typst.exe 是 Windows 二进制：Bash 调用须 `wslpath -w` 转路径；win_py 调用直接可用。
- typst SVG 字形输出为**轮廓 path**（`<use xlink:href="#gHASH">`），自包含、无字体依赖。

## 边界

整块为图 → 不可逐字编辑、受数据红线约束（排版文案须溯源 brief 或标 `[占位]`）、
须顶层声明（不进容器 children，与 chart 同律）；`@preview` 包首次编译需联网缓存。
`design` 字段（LLM 辅助设计）已在白名单与编译期校验，CLI 通道待实现——协议见
references/typst-chain.md §6。
