# 示例 3：组织架构图（graph 容器 orientation: vertical）

`orgchart.yaml` 演示 graph 容器的纵向 branch——`orientation: vertical` 时布局
旋转 90°：层 = 行（根上子下），行内节点水平均分，跨层连线磁吸 N/S 正对中点。

## 运行

```bash
win_py scripts/build_ppt.py examples/orgchart/orgchart.yaml --out examples/orgchart/out
```

## 与横向流程图（flowchart）的差异

| 维度 | 横向（默认） | 纵向（vertical） |
| --- | --- | --- |
| 层含义 | 列 | 行 |
| 层步进 | 列距 = 内容宽 ÷ 层数 | 行高 = 内容高 ÷ 层数 |
| 跨层锚点 | E/W | N/S（上者出 S、下者入 N） |
| 同层兄弟 | N/S（上下重叠） | E/W 回退（本示例"前端组→后端组"） |
| orth 回边走廊 | 上/下走廊取浅者 | 左/右走廊取浅者 |

## 积木表达

- **kind 体系通用**：`src`（总经理/起点）与 `proc`（中心/组）同横向流程图的族填充。
- **磁吸锚点**：全部连线端点贴节点正上/下（或同层正左/右），不斜插角；
  校验器用同判据独立重算比对（G6 vertical 分支）。
- **边标签**：跨层直连的 `label: "直管"` 盖在线段中点上方（owner 合法遮挡）。
- **同层回退**：`fe → be "协同"` 属同层兄弟连边——y 区间重叠时自动回退 E/W，
  与校验器 `_recompute_anchor(vertical=True)` 的 overlap_y 分支一致。
- **分组/框架**：组包围盒 + 全幅渐变背景 + 页眉页脚，与流程图样例同款。

## 校验背书

edge 全部贴端口（G5）、独立重算一致（G6 vertical 判据）、同层同高（G8）、
节点 ⊆ 面板内容区（D）、文本 autofit 合框（T 家族）。跑通即 exit 0 + 全量物证。