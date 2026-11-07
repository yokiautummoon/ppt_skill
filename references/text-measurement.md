# 文本测量模型（textmesh）

无视觉 LLM 要保证文本"装得进框"，不能靠渲染后目测——必须**预测断行与字号**。
textmesh.py 实现确定性文本测量 + autofit。

## 模型

- **字形基准**：`em_cjk=1.00`（CJK 字符 = 1.0 em 宽）、`em_asc=0.54`
  （ASCII 字符平均宽系数）、`margin_w=1.03`（整行 BoundWidth 探测 vs
  逐字符累加有 2~3% 系统误差 → 乘 1.03 余量）。
- **行高**：`line_h=1.2 × fs`（使用 `a:latin` typeface 的 LineSpacing）。
- **断行**：`wrap_layout(segs, width_pt)` 贪心断行——字符累计宽 ≤ 框宽则同
  行，否则换行。返回逐行 + 最大行宽。
- **autofit**：从起始字号向下迭代（`autofit_iters=4` 上限），求令
  `need_h = 行数 × line_h × fs ≤ 框高` 且 `max_w ≤ 框宽 × margin_w`
  的最大字号。**只缩不升**——声明 fs 偏小不会放大。
- **min_fs 硬底**（`4.0pt`）：缩到底仍超框 → `overflow` 标记 →
  verify T 家族`autofit 超框`必然 FAIL，报告建议拆元素/扩框（不静默容忍）。

## verify 背书（text_layout 一致性）

IR 的 `text_layout` 由布局层单一产出；verify T 家族**独立重算**断行并断言：
断行数一致、水平不溢出（max_w ≤ 框宽）、垂直不溢出（need_h ≤ 框高）、fs ≥ 硬底。
任何"手改字号/框几何"导致的矛盾都会被拦——这确保渲染层照抄 IR，
agent 想微调只能改 SPEC（改 fs 起点/扩框）重跑。

## 关键常量（params.text，可 SPEC 覆盖）

| 键 | 默认 | 含义 |
|---|---|---|
| em_cjk | 1.00 | CJK 字符宽系数 |
| em_asc | 0.54 | ASCII 字符宽系数 |
| line_h | 1.2 | 行高 = line_h × fs |
| margin_w | 1.03 | 测量余量系数 |
| min_fs | 4.0 | 字号硬底 (pt) |
| fs0_node | 12 | graph 节点起始字号 |
| fs0_block | 18 | 顶层文本/形状文本起始字号（agent 未声明 fs） |
| edge_label_fs | 9 | 边标签起始字号 |

## 注意

- autofit 只保证"装下"，不保证"美观"。字号层级美学期望由规则集
  `type_scale` 表达（如 node [8,16]、edge_label [6,12]）——超出即 S 家族拦。
- 字宽是近似（CJK 用 1.0em 而非逐字形）——长文本留余量或让 autofit 缩字号。
- 端到端不会因字体缺失崩：所有文本统一微软雅黑双轨（latin + ea typeface）。