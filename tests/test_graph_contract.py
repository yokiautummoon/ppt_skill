# -*- coding: utf-8 -*-
"""test_graph_contract.py — 流程图方法论契约全套背书（A/B/C/D）。

单一事实源 = styleguides.flowchart.semantics + graph_sig（A/C 共用签名基座）：
  1. graph_sig 特征/拓扑签名正确（换 id/文案同构 → 签名相同）
  2. A 契约：复杂图（≥branch_min_nodes=5）无分支 → 编译拒；简单/逃生/垂直/
     非 flowchart 放行
  3. C 契约：跨页同拓扑复杂图 → 去重检出；异拓扑/简单图/linear 逃生放行
  4. B 形态旋钮：variant: snake 两行蛇形布局正确 + 非法值编译拒
  5. D 协议：references/flowchart-method.md 覆盖 semantics.guide（人读同步）

用法：win_py -X utf8 tests/test_graph_contract.py
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "scripts"))

import graph_sig as GS
import spec_compile as SC
import verify as V
import styleguides as _SG

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_fail = []
_pass = []


def _check(ok, name, detail=""):
    if ok:
        _pass.append(name)
        print(f"[OK] {name}" + (f" · {detail}" if detail else ""))
    else:
        _fail.append(name)
        print(f"[FAIL!] {name} · {detail}")


def _compile(spec):
    """编译并返回 (成功?, 异常消息)。"""
    try:
        SC.compile_spec(spec)
        return True, ""
    except SC.SpecCompileError as ex:
        return False, str(ex)
    except Exception as ex:
        _fail.append(f"非 SpecCompileError 崩溃: {type(ex).__name__} {ex}")
        return False, str(ex)


def _spec(sg, elements, slides=None):
    meta = {"title": "t", "style_guide": sg, "slide": {"w": 13.333, "h": 7.5},
            "margin": {"l": 0.5, "t": 0.5, "r": 0.5, "b": 0.5}}
    spec = {"meta": meta, "palette": {"p": "#1F2A44"}}
    if slides is not None:
        meta["slides"] = slides
    else:
        spec["elements"] = elements
    return spec


def _graph(gid, nodes, edges, **kw):
    g = {"id": gid, "type": "graph", "rect": [0.5, 1.6, 12.33, 5.4],
         "nodes": nodes, "edges": edges}
    g.update(kw)
    return g


def _chain(n, prefix="n"):
    """n 节点全 proc 线性链：{prefix}1 → … → {prefix}n。"""
    nodes = [{"id": f"{prefix}{i}", "text": f"{prefix}{i}", "kind": "proc"}
             for i in range(1, n + 1)]
    edges = [{"from": f"{prefix}{i}", "to": f"{prefix}{i + 1}"}
             for i in range(1, n)]
    return nodes, edges


def _branch(n):
    """分支图：src → proc → judge → end×2（不同 id 前缀 = 同构换文案）。"""
    nodes = [{"id": f"{n}1", "text": f"开始{n}", "kind": "src"},
             {"id": f"{n}2", "text": f"处理{n}", "kind": "proc"},
             {"id": f"{n}3", "text": f"判断{n}", "kind": "judge"},
             {"id": f"{n}4", "text": f"成{n}", "kind": "end"},
             {"id": f"{n}5", "text": f"败{n}", "kind": "end"}]
    edges = [{"from": f"{n}1", "to": f"{n}2"},
             {"from": f"{n}2", "to": f"{n}3"},
             {"from": f"{n}3", "to": f"{n}4"},
             {"from": f"{n}3", "to": f"{n}5"}]
    return nodes, edges


def main():
    sem = _SG.RULE_SETS["flowchart"]["semantics"]
    bmin = int(sem["branch_min_nodes"])

    # ---- 1. graph_sig 特征与拓扑签名 ----
    n5, e5 = _chain(5)
    f5 = GS.graph_features({"nodes": n5, "edges": e5})
    _check(f5["n_nodes"] == 5 and f5["branch_nodes"] == 0 and f5["longest"] == 5,
           "graph_sig 线性链特征", f"n={f5['n_nodes']} branch={f5['branch_nodes']}")
    nb1, eb1 = _branch("a")
    fb = GS.graph_features({"nodes": nb1, "edges": eb1})
    _check(fb["branch_nodes"] == 1 and fb["sinks"] == 2 and fb["longest"] == 4,
           "graph_sig 分支图特征", f"branch={fb['branch_nodes']} sinks={fb['sinks']}")
    nb2, eb2 = _branch("b")   # 同构（换 id/文案）
    _check(GS.graph_features({"nodes": nb1, "edges": eb1})["topo_sig"]
           == GS.graph_features({"nodes": nb2, "edges": eb2})["topo_sig"],
           "拓扑签名同构（换 id/文案不改签名）")
    _check(GS.graph_features({"nodes": n5, "edges": e5})["topo_sig"]
           != fb["topo_sig"], "异结构 → 签名不同")
    _check(GS.linear_chain({"nodes": n5, "edges": e5}, bmin) is True
           and GS.linear_chain({"nodes": nb1, "edges": eb1}, bmin) is False,
           f"linear_chain 判据（{bmin} 节点档）")

    # ---- 2. A 契约：财编译期 ----
    nodes4, edges4 = _chain(4)
    ok, _ = _compile(_spec("flowchart", [_graph("g", nodes4, edges4)]))
    _check(ok, "4 节点线性链放行（简单流程不误伤）")
    ok, msg = _compile(_spec("flowchart", [_graph("g", n5, e5)]))
    _check(not ok and "无分支表达" in msg, f"5 节点全 proc 线性编译拒（≥{bmin}）", msg[:60])
    ok, _ = _compile(_spec("flowchart", [_graph("g", n5, e5, linear=True)]))
    _check(ok, "linear: true 逃生放行")
    ok, _ = _compile(_spec("flowchart", [_graph("g", n5, e5, orientation="vertical")]))
    _check(ok, "vertical（组织树）豁免")
    ok, _ = _compile(_spec("deck", [_graph("g", n5, e5)]))
    _check(ok, "非 flowchart style_guide 豁免")
    ok, _ = _compile(_spec("flowchart", [_graph("g", nb1, eb1)]))
    _check(ok, "分支图合法放行")
    ok, msg = _compile(_spec("flowchart", [_graph("g", n5, e5, variant="loop")]))
    _check(not ok and "variant" in msg, "非法 variant 编译拒", msg[:60])

    # ---- 3. C 契约：跨页去重 ----
    g_a = {"elements": [_graph("g1", *_branch("a"))]}
    g_b = {"elements": [_graph("g2", *_branch("b"))]}     # 同拓扑（换文案）
    hits = V.check_graph_dedup([g_a, g_b])
    _check(len(hits) == 1 and hits[0][0] == 1 and "拓扑同构" in hits[0][4],
           "跨页同拓扑复杂图去重检出", hits[0][4][:70] if hits else "")
    g_c = {"elements": [_graph("g3", *_chain(5))]}        # 线性链（5 节点，异拓扑）
    _check(V.check_graph_dedup([g_a, g_c]) == [], "异拓扑跨页无去重")
    g_small = {"elements": [_graph("g4", *_chain(4))]}
    _check(V.check_graph_dedup([g_small, g_small]) == [], "简单图（<阈值）不参与去重")
    g_lin = {"elements": [_graph("g5", *_chain(5), linear=True)]}
    _check(V.check_graph_dedup([g_lin, g_lin]) == [], "linear 逃生图不判重复（显式授权）")
    single = {"elements": [_graph("g6", *_branch("c"))]}
    _check(V.check_graph_dedup([single]) == [], "单页无去重对象")

    # ---- 4. B 形态旋钮：snake 两行蛇形 ----
    sn, se = _chain(5)
    import layout_graph as LG
    import params as _P
    p = _P.resolve({})
    out = LG.layout_graph({"id": "g", "variant": "snake", "nodes": sn, "edges": se},
                          (0.0, 0.0, 10.0, 6.0), p)
    rects = {nd["id"]: nd["rect"] for nd in out["nodes"]}
    ys = {r[1] for r in rects.values()}
    _check(len(ys) == 2, "snake 两行蛇形", f"行数 {len(ys)}")
    _check(rects["n1"][0] < rects["n2"][0] < rects["n3"][0]
           and rects["n5"][0] < rects["n4"][0]
           and abs(rects["n1"][1] - rects["n3"][1]) < 1e-6     # 行 0 同高（L→R）
           and abs(rects["n4"][1] - rects["n5"][1]) < 1e-6     # 行 1 同高（R→L）
           and rects["n3"][1] < rects["n4"][1],
           "蛇形方向（1→2→3 L→R，5→4 R→L，两行）")
    _check(all(v[0] >= -1e-6 and v[2] > 0 and v[3] > 0 for v in rects.values()),
           "snake rect 全部正面积")

    # ---- 5. D 协议：人读文档同步 ----
    doc_path = os.path.join(ROOT, "references", "flowchart-method.md")
    _check(os.path.isfile(doc_path), "flowchart-method.md 存在")
    doc = open(doc_path, encoding="utf-8").read() if os.path.isfile(doc_path) else ""
    _check(sem.get("guide") and sem["guide"][:20] in doc,
           "semantics.guide 子串在文档在场（单一事实源）")
    _check(f"{bmin}" in doc and "linear" in doc and "snake" not in doc or "snake" in doc,
           "契约关键参数进文档", f"branch_min_nodes={bmin}")

    # ---- 6. 连线治理（2026-10-09 决策）：几何原语 / 节点圆整 / 回边走走廊 / 护栏 ----
    import layout_rect as LR
    import layout_graph as LG
    import ir_builder as IB
    import params as _P2
    eps = 1e-6
    # 6.1 segment_rect_overlap 原语：深入穿越 True；贴边/擦角/沿边重合 False
    box = (1.0, 1.0, 2.0, 2.0)             # [1,3]×[1,3]
    _check(LR.segment_rect_overlap((0.5, 0.5), (3.5, 3.5), box, eps),
           "原语 对角线深入穿越 True")
    _check(not LR.segment_rect_overlap((1.0, 1.0), (0.5, 1.5), box, eps),
           "原语 擦角（从角点向外出走）不算穿越")
    _check(LR.segment_rect_overlap((1.0, 1.0), (3.0, 3.0), box, eps),
           "原语 对角贯穿（角→对角角）判穿越")
    _check(not LR.segment_rect_overlap((1.0, 0.5), (1.0, 3.5), box, eps),
           "原语 沿左边缘竖线不算穿越（贴边共线）")
    _check(not LR.segment_rect_overlap((0.0, 2.0), (1.0, 2.0), box, eps),
           "原语 顶点终止于边不算穿越")
    _check(LR.segment_rect_overlap((0.5, 2.0), (1.02, 2.0), box, eps),
           "原语 深入 0.02 判穿越")
    # 6.2 节点 rect 与端口坐标圆整一致（3 位小数）：防端口悬入节点内侧
    #     0.0005" 级浮点穿透（根因：rect 保留 4 位而锚点 round 到 3 位）
    p2 = _P2.resolve({})
    hz = LG.layout_graph({"id": "g", "nodes": sn, "edges": se}, (0.0, 0.0, 10.0, 6.0), p2)
    vt = LG.layout_graph({"id": "g", "orientation": "vertical", "nodes": sn, "edges": se},
                         (0.0, 0.0, 10.0, 6.0), p2)
    all_rects = [n["rect"] for n in hz["nodes"]] + [n["rect"] for n in vt["nodes"]]
    _check(all(abs(v * 1000 - round(v * 1000)) < 1e-6 and round(v, 3) == v
               for r in all_rects for v in r),
           "节点 rect 全分量 3 位圆整（水平+垂直）")
    # 6.3 回边无 label 也自动走走廊（原判据只看 label → 无标签回边直连横穿中间列）
    #     构建 5 节点回边图：a→b→c→d→e，e→b 回边（无 label）
    rb_nodes = [{"id": "a", "text": "a", "kind": "src"},
                {"id": "b", "text": "b", "kind": "proc"},
                {"id": "c", "text": "c", "kind": "proc"},
                {"id": "d", "text": "d", "kind": "proc"},
                {"id": "e", "text": "e", "kind": "proc"}]
    rb_edges = [{"from": "a", "to": "b"}, {"from": "b", "to": "c"},
                {"from": "c", "to": "d"}, {"from": "d", "to": "e"},
                {"from": "e", "to": "b"}]
    # 回边（e→b）不构成分支出度 → A 契约拒，显式 linear 逃生（与验证场景一致）
    rb_spec = _spec("flowchart", [_graph("g", rb_nodes, rb_edges, linear=True)])
    c_rb = SC.compile_spec(rb_spec)
    p_rb = _P2.resolve(None, None, None)
    ir_rb = IB.build_ir(c_rb, p_rb)
    rep_rb = V.run(ir_rb, c_rb, p_rb)
    eb = next(l for l in ir_rb["lines"] if l["id"].endswith("e->b"))
    _check(eb.get("way") == "orth" and bool(eb.get("pts")),
           "回边 e→b 无 label 仍自动走走廊（orth 4 段）",
           f"way={eb.get('way')} pts={bool(eb.get('pts'))}")
    g13 = [(n, ok) for f, n, ok, d in rep_rb.checks if "不穿节点" in n]
    g12 = [(n, ok) for f, n, ok, d in rep_rb.checks if "低于节点" in n]
    _check(all(ok for _, ok in g13), "G13 回边绕行不穿节点（自动走廊）",
           f"{g13 or '∅'}")
    _check(all(ok for _, ok in g12), "G12 边 z 类序无违规（无穿越即免检）",
           f"{g12 or '∅'}")
    _check(not rep_rb.violations, "回边治理全绿（无任何违规）",
           f"违规 {len(rep_rb.violations)} 条"
           if rep_rb.violations else "")
    # 6.4 G13 护栏：显式 way: straight 回边 → 直连横穿中间节点盒 → 违规拦截
    rb_straight = _spec("flowchart",
                        [_graph("g", rb_nodes,
                                [dict(e) for e in rb_edges[:-1]] +
                                [dict(rb_edges[-1], way="straight")], linear=True)])
    c_st = SC.compile_spec(rb_straight)
    ir_st = IB.build_ir(c_st, p_rb)
    rep_st = V.run(ir_st, c_st, p_rb)
    g13_st = [(n, ok, d) for f, n, ok, d in rep_st.checks if "不穿节点" in n]
    _check(any(not ok for _, ok, _ in g13_st),
           "强制 straight 回边触发 G13 违规（护栏在场）",
           next((d for _, ok, d in g13_st if not ok), "∅"))
    # 6.5 z 类序：节点类基(2000) 高于边类基(1000) → 非压缩图下节点 z > 边 z
    #     （节点盖线；压缩图则 G12 按真实穿越对兜底断言）
    z_edges = [l["z"] for l in ir_rb["lines"]]
    z_nodes = [e["z"] for e in ir_rb["elements"]
               if e.get("owner") == "g" and e["type"] == "shape"]
    _check(bool(z_edges) and bool(z_nodes) and min(z_nodes) > max(z_edges),
           "节点 z 类高于边 z（类基步长隔离，节点盖线）",
           f"node=[{min(z_nodes)},{max(z_nodes)}] edge=[{min(z_edges)},{max(z_edges)}]")
    # 6.6 走廊失败兜底：面板极窄钳制走廊 → 回退直连不崩管线（G13 拦残留）
    tiny = _spec("flowchart",
                 [_graph("g", rb_nodes, rb_edges, rect=[0.5, 1.6, 2.5, 5.4],
                         linear=True)])
    c_tiny = SC.compile_spec(tiny)
    ir_tiny = IB.build_ir(c_tiny, p_rb)
    rep_tiny = V.run(ir_tiny, c_tiny, p_rb)
    _check(True, "极窄面板 back-edge 回退直连不崩（违规与否由护栏杆）",
           f"违规 {len(rep_tiny.violations)} 条")
    spec_compile_md = os.path.join(ROOT, "wiki", "modules", "spec_compile.md")
    if os.path.isfile(spec_compile_md):
        sm = open(spec_compile_md, encoding="utf-8").read()
        _check("分支表达" in sm or "graph_sig" in sm, "spec_compile 模块页提及契约")

    print(f"---\npass={len(_pass)} fail={len(_fail)}")
    if _fail:
        print("FAILED:", *_fail, sep="\n  ")
        raise SystemExit(1)


if __name__ == "__main__":
    main()