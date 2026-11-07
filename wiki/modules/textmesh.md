---
tags: [module]
module: textmesh
depends_on:
  - params
updated: 2026-09-10
---

# textmesh — 文本测量与 autofit

autofit_text：以框 w/h（pt）测量、逐级降号到 min_fs；溢出标记（overflow）进 IR 由 verify T 家族断言。内部绝对导入 params。verify/ir_builder/layout_graph 都消费。