# 示例 2：递进阶梯（ladder）

`ladder.yaml` 演示**积木表达力**：不用任何特殊形状，仅用"不同宽度、同高度的
圆角矩形 + vertical stack + align center"就搭出对称梯形——宽度递减 = 递进，
背景色递深 = 层级（软 → 中 → 深蓝）。

## 运行

```bash
win_py scripts/build_ppt.py examples/ladder/ladder.yaml --out examples/ladder/out
win_py scripts/build_ppt.py examples/ladder/ladder.yaml --out examples/ladder/out --com
```

## 关键点

- **梯形对称性**：`align: center` 让 stack 求解器把每级矩形水平居中，
  推导出对称梯形（首尾两级中心线对齐）。这是机器可证明的性质
  （`smoke_ladder.py` 断言 cx1==cx3）。
- **规则集机器证明**：ladder 规则集强制——宽度严格递减、step 高度 ∈ [0.7,1.3]、
  stack 高度账目、色数 ≤ 上限。写坏任何一条都会被 S 家族拦下（exit 3）。
- **数值接口化**：`gap`、字号等全部是 params/SPEC 可覆盖的数值，无硬编码 magic。
- `group: true` → `--com` 时三个阶梯由 COM Group 组合成一组（移动整体）。

## 积木思想

这类"视觉模式"（梯形、金字塔、漏斗、层级块……）本质都是同一积木的变奏：
**同高异宽的圆角矩形 + align 居中 + 颜色递进**。改宽度序列与配色即换一种图。