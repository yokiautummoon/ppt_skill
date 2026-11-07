# -*- coding: utf-8 -*-
"""graph_sig.py — graph 结构特征 + 拓扑签名（方法论契约 A 与去重 C 共用基座）。

纯函数，无逻辑依赖：spec_compile（A 契约）、verify（C 去重）都从本模块取
特征/签名；styleguides.flowchart.semantics 定义"复杂图"阈值（单一事实源）。

graph_features(g) → dict：
  n_nodes           节点总数
  kinds             {kind: 计数}（未声明 kind 归 "proc"）
  out_deg           按 id 的出度（edges 的 from 计数）
  branch_nodes      出度 ≥ 2 的节点数（分支表达量；判断/分叉语义）
  sinks             出度 = 0 的节点数（终点/汇）
  longest           最长链深（BFS 层深最大值；有环 fallback = 节点数）
  topo_sig          拓扑签名（结构同构判据，与 id/文案无关）：
                    (节点数, kind 直方图, 出度直方图, 入度直方图, 最长链)
                    —— 同拓扑不同 id/文本 → 签名相同（C 判重复）

linear_chain(g) → bool：n_nodes ≥ semantics.branch_min_nodes 且无分支节点
  （A 契约判据；简单流程/显式 linear 逃生豁免由调用方判）。
"""
from collections import Counter

_DEFAULT_KIND = "proc"


def graph_features(g):
    nodes = g.get("nodes") or []
    edges = g.get("edges") or []
    kinds = Counter((n.get("kind") or _DEFAULT_KIND) for n in nodes)
    out = Counter()
    indeg = Counter()
    for e in edges:
        out[e.get("from")] += 1
        indeg[e.get("to")] += 1
    branch = sum(1 for v in out.values() if v >= 2)
    sinks = sum(1 for n in nodes if out.get(n["id"], 0) == 0)
    longest = _longest_path(g)
    topo_sig = (
        len(nodes),
        tuple(sorted(kinds.items())),
        _hist(out.values(), len(nodes)),
        _hist(indeg.values(), len(nodes)),
        longest,
    )
    return dict(n_nodes=len(nodes), kinds=dict(kinds), out_deg=dict(out),
                branch_nodes=branch, sinks=sinks, longest=longest,
                topo_sig=topo_sig)


def _hist(values, n):
    """出/入度直方图：长度固定 n（未出现度数补 0），序列可哈希。"""
    h = Counter(values)
    return tuple(h.get(d, 0) for d in range(n))


def _longest_path(g):
    """最长路径（节点数）：Kahn 拓扑序 + DP（DAG 精确；环/孤立保底不越界）。
    与 layout_graph.bfs_layers 不同实现（verify 哲学：两套代码路径独立重算）。"""
    nodes = g.get("nodes") or []
    edges = g.get("edges") or []
    if not nodes:
        return 0
    order = {n["id"]: i for i, n in enumerate(nodes)}
    out = {nid: [] for nid in order}
    indeg = {nid: 0 for nid in order}
    for e in edges:
        f, t = e.get("from"), e.get("to")
        if f in order and t in order:
            out[f].append(t)
            indeg[t] += 1
    indeg_c = dict(indeg)
    q = [nid for nid in order if indeg_c[nid] == 0] or [next(iter(order))]
    topo = []
    while q:
        u = q.pop(0)
        topo.append(u)
        for t in sorted(out[u], key=lambda x: order.get(x, 0)):
            indeg_c[t] -= 1
            if indeg_c[t] == 0:
                q.append(t)
    for nid in order:                    # 有环/不可达：保底补序（dist 不越节点数）
        if nid not in topo:
            topo.append(nid)
    dist = {nid: 1 for nid in order}
    for u in topo:
        for t in out[u]:
            dist[t] = max(dist[t], dist[u] + 1)
    return max(dist.values())


def linear_chain(g, branch_min_nodes=5):
    """复杂图却无分支表达（同质化主因：全 proc 线性链）。"""
    f = graph_features(g)
    return f["n_nodes"] >= branch_min_nodes and f["branch_nodes"] == 0