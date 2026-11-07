# examples/ink — 书法矢量字（brush）+ Morph 平滑切换

C3 视觉补充示例（ppt-studio 借鉴批次 2）。

## 内容
- **页 1 书法矢量字**：三个 `type: brush` 元素，分别演示**三态填充**——
  实色（`style.fill`）/ 渐变（`style.grad`）/ 图片填充（`style.image`，
  `assets/ink.png` 水墨纹理透出字形）。字形经 `ink_text` 矢量化成原生
  `a:custGeom` 形状（换机不丢字形，可缩放/渐变/图片填充）。
- **页 2 平滑切换**：`transition: {effect: morph, dur: 900}`；`ink_*` 跨页
  **同名**对象 → Morph 自动补间变形（位置/尺寸过渡）。

## 产物
`win_py -X utf8 scripts/build_ppt.py examples/ink/ink.yaml --out examples/ink/out`
→ exit 0，2 页 41/41 物证（字形 custGeom/单路径/三态填充 + morph AlternateContent）。

## 语法/边界
见 `references/ink-brush.md`。要点：`text`+`font` 必填；`fill` 与 `image` 互斥；
`dur` 仅 morph 可声明（100~5000ms）；字形按 ink 比例适配声明盒并居中
（`align`/`anchor` 控落位）。
