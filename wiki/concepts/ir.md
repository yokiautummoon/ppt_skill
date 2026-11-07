---
tags: [concept]
module: root
updated: 2026-09-10
---

# IR 中间表示

布局层（ir_builder）产出的扁平绘制清单：elements（rect/z/owner/text_layout/overflow/动画透传）+ lines + glue + groups + framework + notes + transition。渲染层唯一消费物——几何/锚点/z 只在此定，渲染与 COM 绝不重算（铁律 1）。