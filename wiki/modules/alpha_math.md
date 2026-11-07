---
tags: [module]
module: alpha_math
parent: ir_builder
depends_on: []
updated: 2026-09-14
---

# alpha_math — 半透明层叠加反解（性质②：JAnim apart_alpha 移植）

复合形状（cylinder 侧壁/端面）与 JAnim 切分曲线同数学：n 个半透明层叠加的
合成不透明度 = 1 − ∏(1−αi)；**反解每层 alpha 使任意层数组合的合成值 = 声明
目标**（叠区保真，避免叠区过度深色）。

```python
merge_alpha(alphas)      # 1 − ∏(1−αi)（正向，任意层数）
apart_alpha(target, n)   # 1 − (1−target)^(1/n)（n 段切分反解，闭式，免 bisection）
face_alpha(fg, bg)       # (fg − bg)/(1 − bg)；fg ≤ bg 无解 → None
check_merge(alphas, t)   # |merge − t| ≤ EPS 返回合成值，否则 None（断言用）
```

- 闭式解（JAnim bisection 的解析等价，ε=EPS=1e-3）；α 语义 = 不透明度
  （0 透明 ~ 1 不透明），与 cylinder SPEC `opacity` 一致；OOXML `a:alpha`
  val = α × 100000。
- 消费方：ir_builder `_emit_cylinder`（端面反解：`face_a =
  face_alpha(face_opacity, opacity)` → bot/top 椭圆 `opacity=face_a`；
  face_opacity 缺省 1.0 → 实色向后兼容；无解 → ValueError 兜底——spec_compile
  已拦）、verify `_s_cylinder_alpha`（S7 叠区保真断言：独立重算
  `merge([side_a, face_a]) ≈ face_opacity`，与布局器两套代码路径）。
- SPEC 语法/数学推导见 references/alpha-blend.md；单测 tests/test_alpha_math.py
  （9 项，无 Office）。