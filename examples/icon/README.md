# examples/icon — 矢量图标库（icon）

B1 内化示例（ppt-studio 借鉴批次 3）。

## 内容
- **页 1 图标画廊**：8 枚 Lucide 图标 → 原生 `a:custGeom` 形状（描边语义）。
  演示**名/关键词解析**（`水滴`→droplet、`gear`→settings、`科学`→flask-conical）、
  **描边色/磅值**（`style.color`/`style.weight`）、**实心子路径**
  （`chart-scatter` 的散点 `fill="norm"`）。
- **页 2 应用示例**：图标 + 特性卡（图标在卡上方，无遮挡）。

## 产物
`win_py -X utf8 scripts/build_ppt.py examples/icon/icon.yaml --out examples/icon/out`
→ exit 0，2 页 110/110 物证（图标 custGeom/逐子路径描边 fill=none/a:ln 圆头描线）。

## 语法/边界
见 `references/icon-library.md`。要点：`icon` 必填（名/关键词，未命中回退
circle-dot）；`style` 仅 color/weight（描边）；图标按 24×24 视图盒**正方**适配
声明盒并居中（`align`/`anchor` 控落位）。
