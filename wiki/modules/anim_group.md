---
tags: [module]
module: anim_group
parent: build_ppt
depends_on:
  - animation_recipes
updated: 2026-09-14
---

# anim_group — 动画编排组（声明式时间轴展开）

页级 `anim`（单页顶层 / 多页 `slides[i].anim`）→ 纯代数展开为**确定性时间轴**
（性质①：JAnim 时间区段组合语义 TimeRange/Succession/Aligned/AnimGroup/
finalize/TimeAligner 的移植）。`expand_group` 返回 `(leaves, seq, blocks,
violations)`：

- `leaves`：`{id, start, end, trigger, delay}`——绝对秒时间轴（含根组 start
  偏移）；`delay` 由**减法导出** = 自身 start − 锚定目标时刻（with_previous →
  前驱 start；after_previous → 前驱 end；根触发 → T0=0）。
- `seq`：AddEffect 序 = 全局按 start 稳定排序（保证 with_previous 前驱
  start ≤ 自身 start → delay 非负；负 delay 自动降级 with_previous）。
- `blocks`：各子组块（供 ir.anim_timeline 记账）。
- `violations`：时间一致性断言（succession 断链 / aligned·group 对齐偏移），
  恒真护栏（ε=TIMELINE_EPS=1e-4）——ir_builder 违反即 ValueError（防浮点/排序回归）。

语义：`aligned`/`group` 成员 start = 块注入点、块 end = max 成员 end；
succession 叶 i.start = 前叶.end + gap。块内排序：**锚点成员（idx0，携带父链
trigger）必须在块首**，其余按 end 升序（块末 ≈ 最晚结束者 = 父链锚定代表）；
组内成员时序全由引擎展开（成员自带 trigger/delay 编译期已拦）、可嵌套
（子组仅 mode/gap/items）。YAML 字符串简写 `items: [card1]` = `{id: card1}`。

`check_anim_groups(anim, elems, path)` 编译期语义校验（AgError → SpecCompileError
exit 2）：模式/trigger/start/gap/items 类型、成员存在且**带 animation**（容器
stack/dock/graph 与 cylinder 引用拦截）、重复成员。

消费方：spec_compile（页级校验）、ir_builder（`_expand_anim_groups` 改写成员
`animation.trigger/delay` + 注出 `ir.anim_timeline`/`ir.anim_sequence`）、
com_layer（`_apply_anims` 按 seq 序构造 + `_check_timeline_after` COM 回读比对
TriggerDelayTime，超 0.02s WARN）。语法见 references/animation.md「动画组」节。