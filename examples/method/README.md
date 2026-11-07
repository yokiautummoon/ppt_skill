# examples/method — cylinder / curve 积木（P5 方法图最小验证）

`cylinder.yaml` 是一页「区域修复的动边界示意」方法图，用于验证三个新积木的
全链最小闭环（SPEC → 编译 → IR → verify → base.pptx → XML 物证）：

| 积木 | 语法要点 | 本页用法 |
|------|----------|----------|
| `shape.kind: cylinder` | 圆柱复合（半透明侧壁 + 顶/底椭圆 + 2 条等高弧 + 可选标注文字）；`slice`（<1 = 剖视不画顶面）、`opacity`（侧壁透明度） | `cyl_rt0`（大圆柱 = 初始边界 R(t₀)，完整）、`cyl_rt`（小圆柱 = 当前边界 R(t)） |
| `type: curve` | 自由曲线：rect 包围盒 + 归一化点列（0~1 相对 rect，≥3 点），freeform polyline 渲染；`style: {color, weight, dash?}` 线语义 | `u_curve`（扩散前沿示意，非数据驱动） |
| `style.border_dash` / `line.dash` | 虚线描边 / 虚线直线（`dash\|dot\|dash_dot`）；0 宽/0 高线盒合法 | `bd_top/bd_bot/bd_left/bd_right` 虚线分区框 |

## 语义对照

- R(t₀)（大圆柱）= 初始修复边界；R(t)（小圆柱）= 当前时刻边界，二者之间为
  已完成扩散/修复的区域 → 边界向内收缩 R(t) ⊆ R(t₀)。
- 扩散前沿 u(x,t) 用一条示意曲线表达（非数据驱动——数据图请用 `type: chart`）。
- 全部由 SPEC 声明式积木拼成，几何由 ir_builder 解出，产物原生可编辑；
  部件 owner = 元素 id（同容器兄弟豁免遮挡校验）。

## 构建

```bash
win_py scripts/build_ppt.py examples/method/cylinder.yaml --out out_method
```

无 Office 环境 exit 0（verify 0 违规 + XML 物证 40/40）；`--com` 加 COM 后处理。
方法学备注在 `meta.notes`（渲染进演讲者备注页）。

## 还原说明

本页是新模型直接产出 PPT 的方法架构图（`五张方法图_原稿布局_逐项可编辑(1).pptx`
P5 动边界）的**等幂积木还原**：原稿手绘风格的圆柱/曲线/虚线分区，映射为本 skill
的声明式 cylinder/curve/border_dash 积木，逐项可编辑、确定性可复现。