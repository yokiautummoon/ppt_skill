# 示例 1：流程图（graph 容器分支）

`chart.yaml` 演示 graph 容器的完整能力——flowchart 是 graph 容器的一个 branch，
graph 本身是通用生成式积木（任何"节点 + 边 + 分组"图面都可表达）。

## 运行

```bash
# 确定性链（无 Office 也可跑，产出 base.pptx）
win_py scripts/build_ppt.py examples/flowchart/chart.yaml --out examples/flowchart/out

# 加 COM 后处理（需 Windows + PowerPoint）：glue 绑定、Group 组合、PNG 预览
win_py scripts/build_ppt.py examples/flowchart/chart.yaml --out examples/flowchart/out --com
```

## 积木表达

- **四族节点**：`kind: src`（罐形，起点）/ `proc`（圆角矩形，处理）/
  `judge`（菱形，判断）/ `end`（椭圆，终点）。
- **磁吸连线**：边端点贴节点正上下左右（N/S/E/W 端口），不斜插角；
  同层节点同高、列宽自适应（面板宽 ÷ 层数 × (1−gutter)）。
- **边标签**：`label: "是"` 盖在连线水平段上方（owner 合法遮挡）；
  `way: orth` 触发正交回边——"否" 自动走下方紧凑走廊（上/下取浅者），不再长下拐。
- **分组包络**：`groups` 声明组包围盒（半透明底色 + 左上角组标签）。
- **组合对象**：`group: true` → `--com` 时由 COM `Range().Group()` 把容器内所有
  节点/标签合成 Office 组对象（拖动整体移动），命名 `g.group`。

## 校验背书

跑通即 35/35 XML 物证全过：字号 = autofit 结果、几何 = IR 布值、z 层级单调、
连线端点磁吸断言、组包围盒包络成员。