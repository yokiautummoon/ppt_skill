# 示例 4：原生图表（chart 积木）

`chart.yaml` 演示 `type: chart` 数据驱动图表——python-pptx `add_chart` 生成原生
chartSpace + 随附 workbook（图表源数据），零 COM；PowerPoint 里双击图表可直接编辑数据。

## 运行

```bash
win_py scripts/build_ppt.py examples/chart/chart.yaml --out examples/chart/out
```

## 积木表达

- `chart_type: column_clustered | bar_clustered | line | pie | area`
  （`column/bar/line/area` 走坐标轴；`pie` 仅单序列——Excel 饼图语义）。
- 数据账目：`categories`（类别）+ `series: [{name, values}]`，
  `series[].values` 个数必须 == categories 个数（编译期背书，不匹配直接 FAIL）。
- `style`：
  - `legend: right|bottom|none`（默认 right，时段序更优时用 bottom）
  - `data_labels: true|false`（数值标签；字号走 `params.chart.label_fs`）
  - `gridlines: true|false`（数值轴主网格线）
  - `colors: [token…]`（按序列循环取色；未声明走 `params.chart.colors` 默认循环）
- 图标题不进图（`has_title=False`）——标题/副题/单位说明由 SPEC 的 `text` 元素排版，
  图面脱离图表默认样式，字号/颜色/位置全在 SPEC 掌控。
- 序列色 token 必须已在 `palette` 声明（编译期校验）；图例/数据标签观感可调。

## 校验背书

图表 `graphicFrame` 按名定位（与形状同机制）→ `r:id` 解析伴生 chart part →
chartSpace 出对应类型标签（`c:barChart`/`c:pieChart`…）+ `c:ser` 数 == series 数。
几何/安全区/遮挡走 G 家族与普通元素同规则。