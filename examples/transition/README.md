# 页面切换（transition）积木示例

`transition.yaml` 演示页间切换：全局默认 `meta.transition` + 页级覆盖
`slides[i].transition`，纯渲染 XML 注入 `p:transition`（零 COM）。

```bash
win_py -X utf8 -W ignore scripts/build_ppt.py examples/transition/transition.yaml --out out_transition
```

- `effect` ∈ `fade|push|wipe|cut|none`；`spd` ∈ `slow|med|fast`（OOXML 定性档，
  无秒级精度）；`push/wipe` 默认从左（`dir="l"`）。
- 页未声明 `transition` → 继承全局默认（页 1）；页级覆盖全局（页 2/4）；
  `effect: none` 显式关闭（页 3，XML 不注入 `p:transition`）。
- 切换是页间行为：单页模式声明 `meta.transition` → 编译错（需 `meta.slides`）。
- 物证每页一条「页面切换」：无切换 → 断言 XML 无 `p:transition`；
  有切换 → 断言子元素 = `p:{effect}` 且 `spd` 相符。