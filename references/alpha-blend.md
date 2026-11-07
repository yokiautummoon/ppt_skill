# alpha-blend.md — 半透明层叠加反解（性质②：JAnim apart_alpha 移植）

复合形状（cylinder 拆侧壁/端面/弧线等部件）与 JAnim 把整套曲线切 n 段是同一个
数学问题：**n 个半透明层叠加的合成不透明度 = 1 − ∏(1−αi)**。若每层都用声明值，
叠区必然过度深色；正确做法是**反解每层 alpha**，使"任一层数组合的合成值 =
声明目标"（叠区保真）。实现：`scripts/alpha_math.py`；断言：verify S7。

## 数学

```
merge_alpha(alphas)      合成：1 − ∏(1−αi)                      （正向，任意层数）
apart_alpha(target, n)   切分反解：α = 1 − (1−target)^(1/n)      （闭式）
face_alpha(fg, bg)       端面反解：α_face = (fg − bg)/(1 − bg)    （fg ≤ bg 无解）
```

- JAnim 用 bisection（ε=1e-3）解反演；`1−(1−α)^n` 的逆有闭式解，本模块用闭式
  （等价、无迭代漂移），断言容差仍取 ε=1e-3（合成值与目标的偏差阈值）。
- α 语义 = **不透明度**（0 透明 ~ 1 不透明），与 cylinder SPEC `opacity` 一致；
  OOXML 渲染 `a:alpha` val = α × 100000。

## cylinder 应用（SPEC `opacity` / `face_opacity`）

`examples/method/` 的 cylinder 是 2 层叠区：**侧壁**（半透明主色矩形，z+0）+
**端面**（顶/底椭圆，z+1）。侧壁 alpha = 声明 `opacity`（保持）；端面绘制于侧壁
之上，声明 `face_opacity` 为**端面区目标不透明度** → 端面自身 alpha 反解使
`merge([opacity, α_face]) = face_opacity`。

```yaml
- id: cy
  type: shape
  kind: cylinder
  rect: [1.0, 1.0, 3.0, 4.0]
  opacity: 0.3          # 侧壁不透明度
  face_opacity: 0.6     # 端面区目标不透明度（缺省 1.0 = 端面实色，向后兼容）
```

展开（ir_builder `_emit_cylinder`）：`face_a = face_alpha(face_opacity, opacity)`
→ bot/top 椭圆 style `opacity=face_a`（slice<1 剖视省略顶椭圆）。**约束**：
`face_opacity > opacity` 才可解（端面无法比底层更透），编译期 `SpecCompileError`
拦截（exit 2）；缺省 face_opacity=1.0 → α_face=(1−op)/(1−op)=1.0（实色，向后兼容）。

## verify S7 断言（叠区保真）

`verify._s_cylinder_alpha`：对每个 cylinder 按部件 id 查 `eid.side` /
`eid.bot` / `eid.top`（IR 展开部件名，精确匹配——不用 regex），断言
`|merge([side_a, face_a]) − face_opacity| ≤ EPS`。两条（bot + top）记账
"cylinder {eid} 端面{fk} 叠区保真"。

> 校验器与布局器两套代码路径：S7 用 alpha_math 独立重算（漠视 IR 里已反解的
> face_a），与 G 家族锚点重算同哲学——verify 不信任单一实现。

## 测试与物证

- `tests/test_alpha_math.py`（9 项，无 Office）：merge/apart/face/check 工具 +
  cylinder 集成（spec 校验合法/非法、ir 反解 0.429=(0.6−0.3)/0.7、缺省实色、verify
  断言 2 条）。
- `examples/method` 全链 40/40 物证不变（端面新增 a:alpha 不影响物证计数；
  物证按形状名/尺寸/z 序核对，alpha 是填充色细分）。