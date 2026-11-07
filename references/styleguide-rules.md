# 规则集（styleguides.py）与新增图面类型

规则库把"什么是好图"编码成机器可检查的断言（verify 的 S 家族）。
SPEC `meta.style_guide` 选择一个规则集；四家族断言中 G/D/T 全图面必跑，
**S 家族按所选规则集**执行。

## 规则集键（schema）

| 键 | 类型 | 含义 |
|---|---|---|
| `type_scale` | {角色: (min, max)} pt | 字号层级规范：title/node/edge_label/step/card/body/caption… |
| `color_max` | int | 同一视觉单元语义色上限（fill 非默认即计一色；grad 计整组） |
| `palette` | [token…] \| None | 配色白名单子集；None = 不限 |
| `components_required` | [str…] | 必需构件：`title`（id 为 title 的 text）、`steps`（有 children 的 stack）、或元素 id |
| `spacing` | {键: (min,max)} | 间距/尺寸规范（当前为声明性约定，未逐项断言） |
| `connector` | {ways, label_max} | 连线方式白名单 / 边标签字数上限 |
| `width_monotonic` | bool | ladder：stack children 宽度必须严格递减（机器证明梯形递进） |

## 现成规则集

| 规则集 | 适用 | 要点 |
|---|---|---|
| **flowchart** | graph 容器图 | node fs [8,16]、edge_label [6,12]、色 ≤5、way ∈ straight/orth、label ≤8 字 |
| **ladder** | 递进阶梯（stack 梯形） | 必需 title+steps、色 ≤3、宽度严格递减、step 高 [0.6,1.4]、gap [0.1,0.6] |
| **dashboard** | 看板（卡片排版） | title、card fs [10,20]、色 ≤6 |
| **deck** | 通用演示版式 | title fs [24,48]、body [12,24]、色 ≤6 |

## 新增图面类型步骤（给规则集加一种图）

1. **选积木组合**：新图面 = 既有积木的排布（如"漏斗"= 倒置梯形 stack、
   "时间轴"= horizontal stack + line + 圆点）。没有专属积木时先组合验证。
2. **定 S 家族契约**：在 `RULE_SETS[新名字]` 里声明 type_scale（角色字号）、
   color_max（色数）、components_required（必需构件）、spacing/connector。
   S 家族的断言器按这些键自动生效（见 verify.py `_s_family`）。
3. **需要新断言**时在 verify.py 加 `rep.add("S", ...)` 项（读 compiled 源，
   扁平化 IR 里容器已消失——必须读 compiled["elements"] 的 children 结构）。
4. **示例 + 突变**：examples/ 下放一个成品 SPEC；tests/run_mutations.py 加
   对应"违反契约"的突变（如宽度不递减/色数超限），确认校验器拦截。
5. **文档**：本文件加一行规则集表 + examples/README。

## 规则与断言的非对称

- `spacing` 键目前是**声明性约定**：自动布局用 params 保证（gutter/group_pad 等），
  未逐项在 verify 断言（防止过度约束合法的自适应缩放）。
- `color_max`/`type_scale`/`width_monotonic`/账目是**机器强断言**，
  违反 = exit 3。这是 agent 改 SPEC 迭代时的"质量护栏"。