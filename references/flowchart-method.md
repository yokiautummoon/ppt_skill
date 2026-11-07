# 流程图方法论契约（Flowchart Method Contract）

> 流程图同质化的根因：方法论只做验后校验、不产形状——形状语言全落入手写
> SPEC / LLM 自由裁量区，复杂流程被写成一条直线，多页 deck 页页同构。
> 本契约把方法论拆成**机器约束 A**（编译期 fail-closed）+ **生成指引 D**
> （LLM 作业协议）两份，共享**同一事实源**：`scripts/styleguides.py` 的
> `RULE_SETS["flowchart"]["semantics"]`；不会两处各说各话（改一处漏一处）。
> 机器侧消费：`spec_compile._check_graph_semantics`（A）与
> `verify.check_graph_dedup`（C，签名基座 `scripts/graph_sig.py`）。
> 本文件是人读同步版；`tests/test_graph_contract.py` 卡 `semantics.guide`
> 子串在本文件在场。

## 一句话

**流程图不是一条直线。** 复杂流程（≥5 节点）必须有分支表达；真线性长流程
显式声明 `linear: true` 逃生，简单流程（<5 节点）直接放行。

## A：机器约束（编译期，exit 2）

| 条件 | 行为 |
|---|---|
| `style_guide: flowchart` + 横向（非 vertical）graph | 契约适用 |
| 节点数 ≥ `branch_min_nodes`（默认 5）且无任何出度≥2 节点（无分支）| **编译拒**（全直线链 = 同质化主因，不留 no-op）|
| 同上 + graph 显式 `linear: true` | 放行（真线性流程逃生，不误伤合法直线）|
| 节点数 < 阈值 | 放行（简单流程就该是直线）|
| `orientation: vertical`（组织树）| 放行（天然层级，不适用）|

## C：跨页去重（多页模式，S 家族断言）

- 复用 `graph_sig` 拓扑签名（节点数 + kind 直方图 + 出/入度直方图 + 最长链，
  与 id/文案无关——换文案同拓扑仍判重复）。
- 复杂图（≥ `branch_min_nodes`）签名在多页 deck 中相同 → exit 3 违规
  （ attribution advisory：改拓扑或改主题）。
- 简单图不参与（简单流程重复是合法用例，误杀用阈值分级化解）。
- 签名基座同时服务 A 的线性检测（同特征，不重复实现）。

## D：生成指引（LLM 作业协议）

`--fix --llm` 的 llm_job.json 注入 `semantics.guide` 摘要（build_ppt 构造作业
时拼接，机器源 = `styleguides.RULE_SETS["flowchart"]["semantics"]["guide"]`）：

> 流程图不是一条直线：复杂流程（≥5 节点）须有分支表达（判断/分叉节点，
> 出度≥2）；简单线性流程（<5 节点）直接放行，真线性长流程显式声明
> `linear: true` 逃生。分支用 judge 语义，回边用 way: orth，终点用 end——
> 让每页流程有自己的拓扑，避免多页同质化。

落地细则：

1. 每个流程有自己的拓扑：判断/分叉节点（出度≥2）表达分支语义，建议
   `judge` 菱形 + `way: orth` 回边（"否"走走廊）+ `end` 终点。
2. 多页 deck 不复制前一页的图结构——页与页之间拓扑应不同。
3. 真线性流程（时间线/步骤）显式声明 `linear: true`，不偷偷写一条直线。

## 与 graph 积木契约的关系

graph 是通用生成式积木（`COMPONENT_CONTRACTS`），本契约只作用于
`style_guide: flowchart` 语境——deck/其他 style_guide 下的 graph 不受
线性契约约束（通用图面合法）。