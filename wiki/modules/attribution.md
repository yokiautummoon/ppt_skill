---
tags: [module]
module: attribution
parent: build_ppt
depends_on: []
updated: 2026-09-14
---

# attribution — 一致性归因分类器

`--fix` 修订链第一环（决策 self-improve-loop.md 部件③）：把 verify/物证的四家族
违规**归因**为 internal / fixable / advisory 三类，并映射到修复动作库。纯函数
模块、无副作用，可单测（tests/test_spec_fixer.py 内 25 例归因表）。

## 分类契约

| klass | 含义 | 处置 |
|---|---|---|
| `internal` | IR/渲染/断言算法不一致（断行重算一致 · 锚点独立重算一致 · 节点同高 · 组包络⊇成员 · stack/dock 账目 · **低于节点（G12 类序）** · **不穿节点（G13 回边绕行）**）| **停机 exit 4**：不修 SPEC、不喂 LLM，报 bug 指引 |
| `fixable` | 确定性可修（溢出安全区 · autofit 溢出 · 遮挡无合法源 · 字号越档 · 配色越界 · 内容缺失）| 进修订链：spec_fixer 默认动作 / llm_fixer 语义 |
| `advisory` | 审美偏好（破格度 · 贯穿度 · 语义色数等）| 默认留人工；`--llm` 下 llm_fixer 可调 |

## 接口

```python
Violation = namedtuple("Violation", "family name element peer klass action detail")
ACTIONS = {...}          # 违规名 → 动作库动作（R1–R4 / content / manual）
classify(report) -> [Violation]     # verify.Report → 归因结果（含 detail 解析）
auto_fixable() -> [action]          # 确定性快路径动作集
llm_or_manual() -> [action]         # 语义/人工动作集
```

- `detail` 从 verify 违规文本解析（正则抽数值：rect 坐标 / max_w·need_h·fs·min /
  字号规范区间等）——spec_fixer 的输入，解析不到数值 → 该动作降级 manual；
- 归因纯文本匹配（family + 违规名前缀 + 元素 id 提取），与 verify/render_check_xml
  的 detail 文本契约耦合——**改动 verify 文案须同步 attribution 正则**
  （tests/test_spec_fixer.py 归因表背书）。

## 依赖约束

独立于 spec_fixer/revisioner/llm_fixer（value object 只被消费）；被 build_ppt
`_fix_loop` 加载。internal 判定不误伤 fixable 是回归红线（决策测试节）。