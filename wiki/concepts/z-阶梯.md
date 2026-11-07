---
tags: [concept]
module: root
updated: 2026-09-10
---

# z 阶梯

OOXML 层级 = spTree 文档序（越靠后越靠前）。z 由 ir_builder 唯一分配（声明序默认 → z_override → 容器内阶梯，冲突顺延），渲染器按 z 稳定重排。COM ZOrder 只能相对微调，不能设绝对 z。（references/ooxml-notes.md §7）