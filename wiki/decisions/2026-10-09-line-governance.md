---
tags: [decision]
parent: root
status: done
updated: 2026-10-09
scope: 流程图边/箭头绕行与层级治理（回边路由 / z 类序 / verify 护栏 / 几何圆整）
---

# 决策：连线治理（回边走廊 / 节点盖线 / G12·G13 护栏）

## 背景

2026-10-09 用户反馈：流程图中出现**遮盖组件的箭头**——回边/跨层连线直穿节点
盒、盖住节点文字，观感不标准。代码实证根因四层：

1. **回边路由判据只看 label**（layout_graph 水平边循环：
   `"orth" if lbl else "straight"`）——无标签回边 → straight 直连，横穿中间
   列节点盒、盖文字（用户反馈的直接元凶）。
2. **z 类基 = 索引步长 = 10**（ir_builder `_Z_CLASS` 旧值
   group_box/edge/node/label 全 10）：类间步长 == 类内索引步长 → 边/节点 z
   交错，穿越节点盒的边（z 段与节点 z 段重合）可盖节点文字。
3. **无校验护栏**：连线穿越非端点节点盒无任何断言拦截，违规静默产图。
4. **几何圆整不一致**（排查 G12 误报时发现）：布局求解产节点 rect 保留 4 位
   小数（如 ok 左缘 9.6575），而端口锚点 round 3 位（`snap_anchor` 产 9.658）
   → orth 走廊竖线 x=端口 x 悬入节点内侧 0.0005"（浮点穿透）→ 视觉上贴边
   竖线实际盖住节点边缘。校验器用 eps=1e-6 判真实穿越属实（非误报）。

## 决策

### 修复 1：节点 rect 统一 3 位圆整（与端口锚点一致）

layout_graph 水平（`_layout_graph`）与垂直（`_layout_graph_vertical`）布局的
节点 rect 四分量统一 `round(…, 3)`（与 `snap_anchor`/`_v_anchor` 端口 round
一致；snake 已如此）。3 位网格上端口与节点边缘逐位相等 → 走廊竖线贴边共线，
`segment_rect_overlap`（内缩 2×eps）正确不算穿越。

### 修复 2：回边默认走走廊（不再只看 label）

水平布局边循环：`back = layers[to] <= layers[from]` → 回边/同层边默认
`way=orth` 走上下走廊（`_orth_route` 自动取浅侧）；显式 `way` 优先。走廊被
面板钳制 → `ValueError` 回退 straight（z 类序已保证节点盖线，残留穿越由 G13
护栏拦截，不崩管线）。

### 修复 3：z 类基步长 1000 ≫ 索引步长 10

`_Z_CLASS = {"group_box": 10, "edge": 1000, "node": 2000, "group_label": 3000,
"edge_label": 4000}`。类序不变式：组包络 < 边 < 节点 < 组标签 < 边标签——
**节点必须严格高于边**，任意边/节点数下类序稳定（索引步长 10 只在类内递增）。

### 修复 4：verify 两条新断言（第二实现，internal 停机）

- **G12 连线不得盖节点文字**（z 类序不变式）：任一边线段实际穿越某节点盒
  （`segment_rect_overlap`，Liang-Barsky 内缩 2eps，贴边/擦角不算）时，边 z
  必须 < 节点 z。**按实际穿越对断言而非全局"边<节点"**：编辑组收拢
  （`_coalesce_edit_groups`）会把成员 z 压缩到低段而边保持 1000+，全局判即
  误杀（group:true 容器）。只查 graph 容器内边（有 owner）。
- **G13 回边绕行不穿节点**：目标层 ≤ 源层的图边（水平布局）不得穿越同图
  非端点节点盒；层号由 `_bfs_layers`（layout_graph.bfs_layers 的独立副本）
  重算。残留穿越 = 显式 `way: straight` 或走廊受阻回退 → 违规（internal）：
  改拓扑或扩面板。
- attribution `_INTERNAL_SUB` +"低于节点"/"不穿节点"（两类都是布局算法缺陷，
  修 SPEC 会掩盖 bug，不喂 LLM）。

### 原语：`segment_rect_overlap`（layout_rect）

线段×矩形"深入穿越"判定，布局器（回边是否需绕行）与校验器（连线不穿节点）
共用同一实现。对内缩 **2×eps** 矩形做 Liang-Barsky：沿原始边缘共线的标准画法
（正交拐点贴列边缘）被裁出；真正深入内部的穿越（深度 > 2×eps）保留。端点落
在边上、擦角、沿边重合均不算。

## 验证

- `_probe/backedge_probe.py`（诊断，已清理）：回边带/不带 label 均自动
  orth（pts=True）；强制 `way: straight` → G13 拦违规 ✓
- `_probe/g12_probe.py`（诊断，已清理）：节点 rect 圆整前走廊竖线 x=9.658
  vs ok 左缘 9.6575 → 穿越；圆整后 9.658=9.658 贴边共线 → 不判 ✓
- tests/test_graph_contract.py 新增第 6 节（14 项）：原语真/假例、节点圆整
  一致、无 label 回边自动走廊 + G13/G12 全绿、强制 straight 触发 G13、
  z 类序节点高于边、极窄面板回退直连不崩
- 全套件绿：mutations 129/0 · regression 27/27 · capabilities 81/0 ·
  routes 34/0 · graph_contract 38/0 · typst 11/0 · 修订链与三性质套件全绿

顺带修复：test_typst_compile.test_spec_contract 预存文案漂移——children 内
typst 拦截走通用 top_level_only 路径，消息"须为顶层元素"与实现内同类限制
（"必须为顶层元素"）及专属契约断言不一致 → 统一为"必须为顶层元素"。