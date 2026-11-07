---
tags: [module]
module: layout_rect
parent: ir_builder
depends_on: []
updated: 2026-09-10
---

# layout_rect — 几何原语

装箱/端口锚点（anchor_pair）、min-corner 盒、安全区/包络判定、线段×矩形深入
穿越判定（segment_rect_overlap）。被 ir_builder（容器求解）、verify（重叠/锚点/
连线断言）、render_check_xml（_seg_box 物证）、layout_stack/dock/graph 依赖——
几何事实的公共底座。

- **segment_rect_overlap（连线治理，2026-10-09 决策）**：线段 pq 是否**深入**
  矩形内部——纯贴边、擦角、沿边重合、端点落在边上均不算。对内缩 **2×eps**
  矩形做 Liang-Barsky 参数裁剪（相交参数区间长度 > eps）：沿原始边缘共线的
  标准画法（正交拐点贴列边缘）被裁出；真正深入内部的穿越（深度 > 2×eps）
  保留。布局器（回边是否需绕行，layout_graph）与校验器（G12/G13 连线不穿
  节点，verify）**共用同一实现**——两处各自第二实现的比对锚点。见
  wiki/decisions/2026-10-09-line-governance.md。