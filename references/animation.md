# animation.md — 动画积木（安逸动画库 35 宏参数化）

> 动画 = **时间轴语义**，不是几何。SPEC 元素级 `animation` 只进 IR、
> 渲染层/verify 完全不消费（不参与 G/T/D/S 断言）；`--com` 时 com_layer
> 按配方在真实 PowerPoint 实时构造 `msoAnimEffectCustom` + 行为叠加。
> 无 Office：动画缺失 WARN 降级（同 glue/group/ole 哲学，`--com-strict` 才阻断）。

## SPEC 语法

元素级字段（text / shape / table / formula / image / diagram 通用；
**容器 stack/dock/graph 拒收**——编译期 `SpecCompileError` exit 2）：

```yaml
elements:
  - id: title
    type: text
    rect: [0.9, 0.35, 11.5, 0.9]
    text: "动画积木"
    animation: {effect: 进入动画_自上浮入_改}     # 配方引用（主用）
  - id: card
    type: shape
    kind: rounded_rect
    rect: [1.0, 2.0, 3.0, 2.0]
    animation:                                  # 逃生通道：behaviors 直写
      behaviors:
        - {type: filter, dur: 0.5, filter_type: fade, reveal: true}
        - {type: property, dur: 0.5, attrib: y, points: [[0, "#ppt_y-.05"], [1, "#ppt_y"]]}
```

校验（spec_compile 编译期，exit 2）：

- `effect` 与 `behaviors` **恰好一个**（同给 → 错；都不给 → 错）。
- `effect` ∈ `animation_recipes.RECIPES` 键，否则 SpecCompileError 并列出可用宏。
- `behaviors` 非空列表；每条 `type` ∈ {set, filter, property, scale, rotation,
  motion}；字段 ⊆ TIMING 字段 ∪ 类型专属字段（`BEHAVIOR_TYPE_FIELDS`）；
  property 的 `points` 为 `[time, value(, formula?)]`，time 为非 bool 数字。
- 编译期静态错误 → exit 2；运行时构造失败 → WARN 降级（不 exit）。

## 35 宏清单（animation_recipes.RECIPES 键）

| 家族 | 宏 |
|---|---|
| enter ×15 | 自上浮入_改 / 自下浮入_改 / 自左浮入_改 / 自右浮入_改 / 自上缩小浮入 / 自下缩小浮入 / 自左缩小浮入 / 自右缩小浮入 / 快速淡入 / 安逸Q弹 / 随机旋入淡入 / 纵向归位 / 落子效果 / 软糖出现 / 旋涡出现 |
| persist ×5 | 九边形抖动 / 呼吸效果 / 无限陀螺旋_顺 / 无限陀螺旋_逆 / 随机抖动_fanbal |
| emphasize ×3 | 两次放大 / 色块儿划过 / 禁止摇摆 |
| exit ×12 | 自上浮出 / 自下浮出 / 自左浮出 / 自右浮出 / 自上放大浮出 / 自下放大浮出 / 自左放大浮出 / 自右放大浮出 / 弹跳跑了 / 随机旋出淡化 / 纵向移出 / 先淡入后淡出_fanbal ⚠ |

⚠ `退出动画_先淡入后淡出_fanbal`：源文件（3081 行 .bas）在末尾截断，仅首段
（set 可见 + delete 前）有谱，注册为 `source_truncated: True`（1 条 behavior、
无 delete_first/text_unit）。用它的效果 = 先淡入后静止，后段淡出未知——需
Office 播放复核后可回填配方。

## 配方 schema（scripts/animation_recipes.py）

```python
RECIPES["进入动画_自上浮入_改"] = {
  "category": "enter",            # enter / persist / emphasize / exit
  "desc": "顶部落入+淡入，缓出",
  "dur": 0.5, "repeat": 1,        # 999 = 无限循环
  "timing": {"smooth_end": True, "decelerate": 1.0},   # 只记非默认值
  "behaviors": [                  # Add 构造序（含将被删的首 set）
    {"type": "set", "dur": 0.001, "prop": "visibility", "to": 1},
    {"type": "filter", "dur": 0.5, "filter_type": "fade", "reveal": True},
    {"type": "property", "dur": 0.5, "attrib": "y",
     "points": [[0, "#ppt_y-.05"], [1, "#ppt_y"]]},     # [time, value] 或 [time, value, formula]
  ],
  "delete_first": True,          # 末尾 Behaviors(1).Delete（PowerPoint 定终态）
  "text_unit": "paragraph",      # None=跳过 ConvertToTextUnitEffect；character 也行
  "notes": "L2-78；Y 起于上（#ppt_y-.05）",   # 源行号 + 特殊点
}
```

- 通用字段：`dur`/`delay`/`smooth_start`/`smooth_end`/`accelerate`/
  `decelerate`/`auto_reverse`（timing + 逐 behavior 同面）。
- 类型专属：set `{prop, to}`；filter `{filter_type, reveal}`；
  property `{attrib, points}`；scale `{from_x, from_y, to_x, to_y}`（百分比）；
  rotation `{from, to}`（度）；motion `{from_x, from_y, to_x, to_y, path}`。
- `selfcheck()` 校验 schema（35 键、behaviors 字段白名单、points 结构）→
  运行 `win_py scripts/animation_recipes.py` 应打印 ok。

## 常量映射（scripts/animation_constants.py）

取常量策略：先 `win32com.client.constants` 按名取（版本精确），缺名回退硬编码表
（PowerPoint 16.0 实测）。com_layer 经 `C("type.set")` 短名取值，配方数据不直接
碰 COM 名。实测值：

| 族 | 名 → 值（PowerPoint 16.0） |
|---|---|
| MsoAnimType | Set=8 Filter=7 Property=5 Rotation=4 Scale=3 Motion=1 None=0 |
| MsoAnimEffect | Custom=0 |
| MsoAnimProperty | Visibility=8 X=1 Y=2 Width=3 Height=4 Rotation=6 |
| MsoAnimFilterEffectType | Fade=8 |
| MsoAnimTriggerType | WithPrevious=2 |
| MsoAnimateByLevel | Paragraph=0 Character=2 |
| MsoTriState | msoTrue=-1 msoFalse=0（Office **共享**类型库，PowerPoint typelib 不含 → 恒回退表） |

无 Office（Linux CI / 精简环境）导入本模块不炸 → 可确定性断言回退表值。

## 作业协议（com_layer `_apply_anims`）

`--com` 时逐页、逐元素（带 `animation` 且非 ph）：

1. `find_shape_by_name` → `seq.AddEffect(shp, msoAnimEffect<PRESET_BASE>,
   0, msoAnimTriggerWithPrevious)`——**effectId 用配方预设基座**（PRESET_BASE
   → msoAnimEffect 预设，见上表；无 preset_base 键的宏回退 Custom=0）。
   **level 参数必须 0**（probe 实测：None → int(None) 转换错；-1 →
   "Invalid enumeration value"；0 稳定接受）。
2. `eff.Timing.*`：Duration / RepeatCount / SmoothStart / SmoothEnd /
   Accelerate / Decelerate / AutoReverse（仅配方非默认值才赋值）。
3. 逐 behavior：`Behaviors.Add(msoAnimTypeX)` + Timing + 类型专属构造
   （SetEffect.Property=Visibility + To；FilterEffect.Reveal(Type=Fade)；
   PropertyEffect.Property + Points 关键帧（Formula 双字段原文落 COM）；
   ScaleEffect.From/To；RotationEffect.From/To；MotionEffect.From/To + Path）。
4. `if delete_first: eff.Behaviors(1).Delete()`——移除 AddEffect 预置的
   set 可见 behavior（预设/custom 都以 set 开头，语义一致），余下预设动画
   行为 + 配方叠加，终态如配方（self-check 回读 `Behaviors.Count`
   只记录不硬断言）。
5. `if text_unit: ConvertToTextUnitEffect(eff, ppAnimateByParagraph|Character)`。

self-check：构造异常 → rec `ok=False` + WARN（不阻断）；`--com-strict` 才 exit 5。
预览为 **静态帧**：多数宏终态可见（首 set To=1 或 delete 后默认可见）；含
set To=0 隐藏阶段的宏预览可能显示为空——需 Office 播放复核。

## 预设基座（WPS 兼容根因）

**WPS 只认 presetID≠0 的效果**：安逸插件版产物 95%+ 的效果 presetID 非零
（53×400、1×25、42×19、8×8、10×6、17×4、6×3、0×82），且大量配 `#ppt_`
公式 + set 可见 + rand()——WPS 播放正常；纯 Custom=0（presetID=0，VBA 宏
转录的旧实现）= 完全无元素动画。`references/` 根因链：COM 实验
`AddEffect(shp, 10, 0, 2)` 序列化出 `presetID="10" presetClass="entr"`
（preset_test.pptx，对照文件保留 9 个旧 custom + 1 个新 fade）。

修复（本仓库 2026-09 落地）：com_layer AddEffect 改用 **PRESET_BASE 预设
基座**（`scripts/animation_recipes.PRESET_BASE`，35 宏全配：
enter→fade/zoom/bounce/spin、persist→grow_shrink/spin、emphasize→
grow_shrink/spin、exit→fade；值 ∈ {fade, zoom, bounce, grow_shrink, spin,
pulse}），预设自带 set 可见由 delete_first 删后余预设动画行为 + 配方叠加，
与插件版产物结构（presetID≠0 + set + 叠加 behaviors）同构。COM 批测本机
（PowerPoint 16.0）7 个候选 ID 全被接受、自带 behaviors 均以 set 开头。

**序列化错位（正常）**：OOXML `presetID` 编号 ≠ msoAnimEffect 枚举值，PowerPoint
把 AddEffect 的 effectId 语义化后自行映射 presetID。本机实测映射：fade(10)→
presetID=10、bounce(27)→26(entr)、grow_shrink(29)→6(emph)、spin(31)→8(emph)。
产物目标是「presetID≠0 + presetClass 正确」，不追求数值对齐。WPS 判据 =
presetID 非零（插件 53 号自制 ID 也播）。

## 验证状态（2026-09 实测）

- `examples/animation/chart.yaml`（9 元素、8 代表宏 + exit）：
  `--com --com-strict` → exit 0，com_out `anim[]` 9/9 ok（预设基座版：
  产物 slide1 timing presetID 全非零 9/9，`entr×6/emph×3`，`presetID=10`×5
  精确命中 fade；余 26/6/8 为 PowerPoint 语义化映射）。
- `tests/run_mutations.py`：容器带 animation / unknown effect / 非法 behavior
  type / 缺 dur / effect+behaviors 共存 / points 非数字 → 全部编译期拦截。
- `tests/com_office_check.py`："动画 COM 构造" → anim[] 全 ok（需 Office）。
- `tests/regression.py`：animation case exit 0 + evidence 31/31（无 Office）。
- 首轮真验 8 宏：自上浮入_改 / 自下浮入_改 / 快速淡入 / 安逸Q弹 / 呼吸效果 /
  无限陀螺旋_顺 / 强调_两次放大 / 退出_自上浮出——全部构造成功被 PowerPoint 接受。
## 动画组（anim：声明式编排——性质① TimeRange/Succession/Aligned 移植）

页级 `anim`（单页模式顶层 `/anim`、多页 `slides[i].anim`）把**整页动画编排**从
"逐元素改 SPEC 调试"升级为"引擎确定性展开时间轴"（JAnim 时间区段组合语义的
移植，`scripts/anim_group.py`）：

```yaml
anim:
  mode: succession            # succession | aligned | group（缺省 succession）
  trigger: on_click           # on_click | with_previous | after_previous（根触发）
  start: 0.2                  # 根链绝对起点（秒，可选）
  gap: 0.35                   # succession 相邻叶间隔（秒，可选）
  items:
    - title                   # 字符串简写 = {id}；或完整 dict：
    - id: card1
      mode: aligned           # 子组模式（aligned/group 与 succession 可嵌套）
      items: [card2, card3]
```

- **计时语义（核心）**：叶 `delay` 由**减法导出** = 自身 start − 锚定目标时刻
  （with_previous → 前驱 start；after_previous → 前驱 end；根触发 → T0=0）。
  AddEffect 序 = 全局按 start 稳定排序 → 前驱 start 恒 ≤ 自身 start → delay
  非负（负 delay 自动降级 with_previous）。
- **aligned/group**：成员 start = 块注入点；块 end = max 成员 end；
  succession：叶 i.start = 前叶.end + gap。组内成员时序全由引擎展开
  （成员自带 trigger/delay 编译期已拦——**组员不得自带时序**）。
- 块内排序：锚点成员（idx0，携带父链 trigger）必须在块首，其余按 end 升序
  （块末 ≈ 最晚结束者 = 父链锚定代表——锚定"最晚结束"使后续链不会互相插入）。
- 展开产物：`ir.anim_timeline`（绝对秒时间轴 leaves）+ `ir.anim_sequence`
  （AddEffect 序）；成员 IR `animation.trigger/delay` 被改写。
- 回归护栏：展开前后**时间一致性断言恒真**（首尾相接量化，ε=1e-4），违反 → 抛
  ValueError（防浮点/排序回归）。
- 编译期校验（exit 2）：模式/trigger/start/gap/items 类型、成员存在且**带
  animation**（无动画成员没意义）、容器（stack/dock/graph）与 cylinder 引用拦截、
  重复成员。

COM 侧（com_layer）：`_apply_anims` 遍历序 = anim_sequence 成员（by_id 查）+
组外独立元素 → 链式锚定 AddEffect（with_previous 锚定"前一个加入 effect 的开始"、
after_previous 锚定其结束）；构造后 `_check_timeline_after` COM 回读
TriggerDelayTime 与引擎 delay 比对，超 0.02s → WARN 记账（不阻断）。

> 时间轴单测 `tests/test_anim_group.py`（12 项）+ 端到端
> `examples/animation/anim_group.yaml`（7 元素 3 组嵌套，evidence 28/28）。
