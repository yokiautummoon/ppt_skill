# -*- coding: utf-8 -*-
"""layout_graph.py — graph 容器：BFS 分层 + 自适应列布局 + 磁吸端口 + 紧凑扁平回边。

布局质量 v2（对应用户反馈三问题 + Sugiyama 稳定性原则）：
  1. 自适应尺寸/间隔：节点宽 = 列步长×(1−gutter_ratio)（面板大→节点/间隔成比例大）；
     节点高 = max(声明高, 文本 autofit 需要高)（同层同高）；列距 = 内容宽/层数。
  2. 磁吸定位：straight 与 orth 端点一律走 N/S/E/W 端口（AABB 边中点），不斜插角。
  3. 紧凑扁平回边：自动比较上/下走廊深度取浅者；走廊 = 全局 min/max 节点边缘
     ±bend_clearance（面板钳制），深度不再硬编码。
  4. 稳定性：BFS 层内按声明序稳定展开（model order）；同层 barycenter 对称分布。
"""
import layout_rect as LR
import textmesh
import params as _P

SHAPE_KIND = {"src": "can", "proc": "rounded_rect", "judge": "diamond", "end": "oval"}

def _seg_rect(a, b, box):
    """线段 a→b 是否与轴对齐矩形 box=(x0,y0,w,h) 相交（含贴边，Liang-Barsky）。"""
    x0, y0, w, h = box
    x1, y1 = x0 + w, y0 + h
    dx, dy = b[0] - a[0], b[1] - a[1]
    t0, t1 = 0.0, 1.0
    for p, q in ((-dx, a[0] - x0), (dx, x1 - a[0]), (-dy, a[1] - y0), (dy, y1 - a[1])):
        if abs(p) < 1e-9:
            if q < 0:
                return False
        else:
            r = q / p
            if p < 0:
                t0 = max(t0, r)
            else:
                t1 = min(t1, r)
        if t0 > t1:
            return False
    return True


def _seg_hits_boxes(node_rect, a, b, ignore, margin=0.03):
    """线段是否穿越（缩边后的）任何非端点节点盒；返回命中的节点 id 列表。"""
    hits = []
    for nid, r in node_rect.items():
        if nid in ignore:
            continue
        x0, y0, w, h = r
        if w <= 2 * margin or h <= 2 * margin:
            continue
        if _seg_rect(a, b, (x0 + margin, y0 + margin, w - 2 * margin, h - 2 * margin)):
            hits.append(nid)
    return hits


def _vseg_clear(node_rect, port, y_line, ignore, margin=0.03):
    """端口竖直段（port → 同 x 的 y_line）是否不穿任何非端点节点盒。"""
    x, y0 = port
    if y0 == y_line:
        return True
    return not _seg_hits_boxes(node_rect, (x, min(y0, y_line)), (x, max(y0, y_line)),
                               ignore, margin)


def bfs_layers(start, nodes, edges):
    """BFS 分层：层内按声明序（model order 稳定）。返回 {id: layer}。"""
    order = {n["id"]: i for i, n in enumerate(nodes)}
    layers, seen = {}, set()
    if start in order:
        layers[start] = 0
        seen.add(start)
    q = [start] if start in order else []
    while q:
        u = q.pop(0)
        outs = sorted((e["to"] for e in edges if e.get("from") == u and e["to"] not in seen),
                      key=lambda t: order.get(t, 0))
        for t in outs:
            seen.add(t)
            layers[t] = layers[u] + 1
            q.append(t)
    # 未达节点保证全覆盖（无错性：不许悬空）：0 入度孤立源（多源图）并入首层
    # 与 start 并列——其出边因此为前向边，避免 0 入度源被落在末列制造"视觉回边"
    # （根因 2026-10-09 连线治理：wind_chain 的 fast→cir 被误判回边 → 走廊被
    # 矮面板钳制 → 回退直连横穿 stm）；其余环上残支补入尾层。
    leftover = [n["id"] for n in nodes if n["id"] not in layers]
    has_in = {e2["to"] for e2 in edges}
    srcs0 = [lid for lid in leftover if lid not in has_in]
    for lid in srcs0:
        layers[lid] = 0
    left2 = [lid for lid in leftover if lid not in srcs0]
    for i, lid in enumerate(left2):
        layers[lid] = (max(layers.values()) if layers else 0) + 1 + i
    return layers

def layout_graph(node, rect, p):
    """node: {id, start, orientation?, variant?, nodes, edges, groups,
       inner_margin?, node_w?, node_h?}
       p: 已合并 params。返回 {nodes, edges, groups}。
       orientation: horizontal（默认，流程图横向）+ vertical（组织树，根上子下）；
       variant: snake（横向蛇形折返，长流程紧凑两行双向流，B 形态多样性旋钮）。"""
    gp = p["graph"]
    im = node.get("inner_margin", gp["inner_margin"])
    content = LR.pad_rect(rect, im)
    cw, ch = content[2], content[3]
    if (node.get("orientation") or "horizontal") == "vertical":
        return _layout_graph_vertical(node, rect, p, gp, im, content)
    if node.get("variant") == "snake":
        return _layout_graph_snake(node, rect, p, gp, im, content)
    layers = bfs_layers(node.get("start"), node["nodes"], node["edges"])

    # ---- 自适应尺寸（问题1）----
    max_lvl = max(layers.values()) if layers else 0
    n_layer = max_lvl + 1
    step_x = cw / n_layer
    nw = step_x * (1.0 - gp["gutter_ratio"])          # 节点宽上限（弹性间隔）
    nh_base = node.get("node_h", gp["node_h_default"])
    fs0 = p["text"]["fs0_node"]
    # 第一轮：在候选宽下求每节点文本需要高（非矩形节点按形状内切区折算）→ 统一节点高
    stf = gp["shape_text_fit"]
    need_h_max = 0.0
    for n in node["nodes"]:
        # max(..., 0.1) = 极窄面板下的零宽保护（文本无从断行）
        kf = SHAPE_KIND.get(n.get("kind", "proc"), "rounded_rect")
        fx, fy = stf.get(kf, (1.0, 1.0))
        fw, fh = max(nw, 0.1) * fx, nh_base * fy
        tl = textmesh.autofit_text(n["text"], fs0, fw * 72, fh * 72,
                                   min_fs=p["text"]["min_fs"])
        need_h_max = max(need_h_max, tl["need_h"] / (fy if fy > 0 else 1.0))
    nh = max(nh_base, need_h_max / 72.0)
    nw = max(nw, gp["min_abs_gap"] * 2)               # 下限保障（窄面板时）
    # 文本平移占用检查：窄到 min_fs 仍放不进形状内切区 → overflow 标记（T 家族断言会拦截）
    text_overflow = []
    texts = []
    for n in node["nodes"]:
        kf = SHAPE_KIND.get(n.get("kind", "proc"), "rounded_rect")
        fx, fy = stf.get(kf, (1.0, 1.0))
        fw, fh = nw * fx, nh * fy
        tl = textmesh.autofit_text(n["text"], fs0, fw * 72, fh * 72,
                                   min_fs=p["text"]["min_fs"])
        recompute = textmesh.wrap_layout(textmesh.measure_prepare(n["text"], tl["fs"]),
                                         fw * 72)
        if tl["fs"] <= p["text"]["min_fs"] + 1e-9 and \
           (recompute[1] > fw * 72 * p["text"]["margin_w"] or tl["need_h"] > fh * 72 + 1e-6):
            text_overflow.append(n["id"])
        texts.append((n, tl))

    # ---- 列坐标 + 同层 barycenter（问题4）----
    cols = {}
    for n in node["nodes"]:
        cols.setdefault(layers[n["id"]], []).append(n)
    out_nodes = []
    x_min = content[0] + nw / 2
    for lvl in sorted(cols):
        xs = x_min + lvl * step_x
        row = [n for n in node["nodes"] if layers[n["id"]] == lvl]   # 声明序稳定
        cnt = len(row)
        for i, n in enumerate(row):
            cy = (content[1] + content[3] * (i + 0.5) / cnt) if cnt > 1 else content[1] + ch / 2
            r = (round(xs - nw / 2, 3), round(cy - nh / 2, 3),
                 round(nw, 3), round(nh, 3))
            tl = dict(texts[[n2["id"] for n2 in node["nodes"]].index(n["id"])][1])
            out_nodes.append(dict(id=n["id"], text=n["text"],
                                  kind=n.get("kind", "proc"), rect=r,
                                  text_layout=tl, overflow=n["id"] in text_overflow,
                                  shape=SHAPE_KIND.get(n.get("kind", "proc"), "rounded_rect")))

    # ---- 边：磁吸端口 + 紧凑回边（问题2/3）----
    out_edges = []
    node_rect = {n["id"]: n["rect"] for n in out_nodes}
    for e in node["edges"]:
        ra, rb = node_rect[e["from"]], node_rect[e["to"]]
        sa, a1, sb, a2 = LR.anchor_pair(ra, rb)
        lbl = e.get("label")
        # 回边/同层边（目标层 ≤ 源层）默认走走廊绕行：直连会横穿中间列节点盒、
        # 盖住节点文字（2026-10-09 连线治理决策根因 1）；显式 way 优先。
        back = layers[e["to"]] <= layers[e["from"]]
        declared = e.get("way")
        way = declared or ("orth" if (lbl or back) else "straight")
        # 默认直线若穿越非端点节点盒 → 改走廊绕行（视觉规范：连线不穿/不断
        # 中间盒）；显式 way: straight 是作者授权，保留并由 verify G13 拦残留
        # 穿越（internal：改拓扑/扩面板），不静默改写作者意图。
        if declared is None and way == "straight" \
                and _seg_hits_boxes(node_rect, a1, a2, {e["from"], e["to"]}):
            way = "orth"
        ed = dict(from_id=e["from"], to_id=e["to"], label=lbl, way=way,
                  a1=a1, a2=a2, side1=sa, side2=sb)
        if way == "orth":
            try:
                ed["pts"] = _orth_route(e["from"], e["to"], node_rect, content, a1, a2, p)
            except ValueError:
                # 走廊均被面板钳制 → 回退直连：z 类序已保证节点盖线（verify
                # G13 会拦下残留穿越，提示改拓扑/扩面板），不崩管线
                ed["way"] = "straight"
        out_edges.append(ed)

    # ---- 组容器（包络 AABB + group_pad；pad 挤出内容区则钳制——包络不越容器）----
    out_groups = []
    cx0, cy0, cx1, cy1 = content[0], content[1], content[0] + content[2], content[1] + content[3]
    for g in node.get("groups", []):
        ms = [node_rect[m] for m in g["members"]]
        x0 = max(min(m[0] for m in ms) - gp["group_pad"], cx0)
        y0 = max(min(m[1] for m in ms) - gp["group_pad"], cy0)
        x1 = min(max(m[0] + m[2] for m in ms) + gp["group_pad"], cx1)
        y1 = min(max(m[1] + m[3] for m in ms) + gp["group_pad"], cy1)
        out_groups.append(dict(id=g["id"], label=g["label"],
                               members=g["members"], bbox=(x0, y0, x1 - x0, y1 - y0)))
    return dict(container=dict(id=node["id"], rect=rect, content=content),
                nodes=out_nodes, edges=out_edges, groups=out_groups)

def _orth_route(f, t, node_rect, content, a1, a2, p):
    """回边 4 段折线：出(端口) → 竖 → 横 → 竖 → 入(端口)。上/下走廊自动取浅。
       仅支持经典"下方走廊"与"上方走廊"；终端端口已在 a1(S/N)/a2 中体现。"""
    rp = p["route"]
    rc = rp["bend_clearance"]
    xc0, yc0, xc1, yc1 = content  # 面板内容区
    n1, n2 = node_rect[f], node_rect[t]
    all_bottoms = {n[1] + n[3] for n in node_rect.values()}
    all_tops = {n[1] for n in node_rect.values()}
    y_below = max(all_bottoms) + rc
    y_above = min(all_tops) - rc
    def _vseg_cross(port, y_line):
        x0, y0 = port
        y1 = y_line
        if y0 == y1:
            return 0
        return len(_seg_hits_boxes(node_rect, (x0, min(y0, y1)), (x0, max(y0, y1)),
                                   {f, t}))
    cand = []
    if y_below <= yc1 - rc:
        d_below = (y_below - n1[1] - n1[3]) + (y_below - n2[1] - n2[3])
        cand.append((_vseg_cross(a1, y_below) + _vseg_cross(a2, y_below),
                     d_below, y_below, "S"))
    if y_above >= yc0 + rc:
        d_above = (n1[1] - y_above) + (n2[1] - y_above)
        cand.append((_vseg_cross(a1, y_above) + _vseg_cross(a2, y_above),
                     d_above, y_above, "N"))
    if not cand:
        raise ValueError(f"orth 回边 {f}→{t} 上下走廊均被面板阻塞（无解）")
    _, _, y_line, _ = min(cand, key=lambda c: (c[0], c[1]))  # 先取竖段穿盒最少，再取浅侧
    p1 = (a1[0], y_line)
    p2 = (a2[0], y_line)
    return [a1, (round(p1[0], 3), round(p1[1], 3)),
            (round(p2[0], 3), round(p2[1], 3)), a2]


def _v_anchor(ra, rb):
    """组织树（垂直主轴）锚点：跨层强制 N/S（上者出 S、下者入 N）——不斜插角；
    同层（y 区间重叠，兄弟链）回退水平主轴 E/W。校验器 G6 用同判据独立重算。"""
    ca, cb = LR.center(ra), LR.center(rb)
    overlap_y = min(ra[1] + ra[3], rb[1] + rb[3]) - max(ra[1], rb[1]) > 1e-9
    if not overlap_y:
        if ra[1] + ra[3] <= rb[1] + 1e-9:      # a 在 b 上方 → a 出 S、b 入 N
            return ("S", (round(ca[0], 3), round(ra[1] + ra[3], 3)),
                    "N", (round(cb[0], 3), round(rb[1], 3)))
        return ("N", (round(ca[0], 3), round(ra[1], 3)),
                "S", (round(cb[0], 3), round(rb[1] + rb[3], 3)))
    return LR.anchor_pair(ra, rb)


def _orth_route_v(f, t, node_rect, content, a1, a2, p):
    """垂直布局的 orth 回边：左右走廊自动取浅侧（水平布局上下走廊的镜像）。
    4 段折线：出 → 竖 → 横 → 竖 → 入；走廊 = 全局 min/max 节点左右缘 ± clearance。"""
    rp = p["route"]
    rc = rp["bend_clearance"]
    xc0, yc0, xc1, yc1 = content
    n1, n2 = node_rect[f], node_rect[t]
    x_left = min(n[0] for n in node_rect.values()) - rc
    x_right = max(n[0] + n[2] for n in node_rect.values()) + rc
    cand = []
    if x_left >= xc0 + rc:
        d = (n1[0] - x_left) + (n2[0] - x_left)
        cand.append((d, x_left))
    if x_right <= xc1 - rc:
        d = (x_right - n1[0] - n1[2]) + (x_right - n2[0] - n2[2])
        cand.append((d, x_right))
    if not cand:
        raise ValueError(f"orth 回边 {f}→{t} 左右走廊均被面板阻塞（无解）")
    _, x_line = min(cand, key=lambda c: c[0])
    return [a1, (round(x_line, 3), round(a1[1], 3)),
            (round(x_line, 3), round(a2[1], 3)), a2]


def _layout_graph_snake(node, rect, p, gp, im, content):
    """蛇形折返（B 形态旋钮）：长流程按声明序两行双向流（1→2→…→n，
    奇数行 L→R、偶数行 R→L）。效果 = 同结构也能出异视觉；复杂度换取
    紧凑布局。边一律直连（anchor_pair，无走廊——蛇形无"同层走廊"语义）。"""
    import math
    cw, ch = content[2], content[3]
    nodes = node["nodes"]
    n = len(nodes)
    rows = 2 if n >= 4 else 1
    cols = int(math.ceil(n / rows)) if n else 0
    nw = max(cw / cols * (1.0 - gp["gutter_ratio"]), 1e-4) if cols else 0
    nh_base = node.get("node_h", gp["node_h_default"])
    fs0 = p["text"]["fs0_node"]
    stf = gp["shape_text_fit"]
    need_h_max = 0.0
    for nd in nodes:
        kf = SHAPE_KIND.get(nd.get("kind", "proc"), "rounded_rect")
        fy = stf.get(kf, (1.0, 1.0))[1]
        tl = textmesh.autofit_text(nd["text"], fs0, max(nw, 0.1) * 72,
                                   nh_base * fy * 72, min_fs=p["text"]["min_fs"])
        need_h_max = max(need_h_max, tl["need_h"] / (fy if fy > 0 else 1.0))
    nh = max(nh_base, need_h_max / 72.0)
    out_nodes, node_rect = [], {}
    for i, nd in enumerate(nodes):
        rw, ci = divmod(i, cols)
        cx = content[0] + nw * ((ci + 0.5) if rw % 2 == 0 else (cols - ci - 0.5))
        cy = content[1] + ch * (rw + 0.5) / rows
        r = (round(cx - nw / 2, 3), round(cy - nh / 2, 3), round(nw, 3), round(nh, 3))
        node_rect[nd["id"]] = r
        out_nodes.append(dict(id=nd["id"], text=nd["text"],
                              kind=nd.get("kind", "proc"), rect=r,
                              text_layout=dict(textmesh.autofit_text(
                                  nd["text"], fs0, max(nw, 0.1) * 72, nh * 72,
                                  min_fs=p["text"]["min_fs"])),
                              overflow=False,
                              shape=SHAPE_KIND.get(nd.get("kind", "proc"),
                                                   "rounded_rect")))
    out_edges = []
    for e in node["edges"]:
        ra, rb = node_rect[e["from"]], node_rect[e["to"]]
        sa, a1, sb, a2 = LR.anchor_pair(ra, rb)
        out_edges.append(dict(from_id=e["from"], to_id=e["to"],
                              label=e.get("label"), way="straight",
                              a1=a1, a2=a2, side1=sa, side2=sb))
    out_groups = []
    cx0, cy0, cx1, cy1 = (content[0], content[1],
                          content[0] + content[2], content[1] + content[3])
    for g in node.get("groups", []):
        ms = [node_rect[m] for m in g["members"]]
        x0 = max(min(m[0] for m in ms) - gp["group_pad"], cx0)
        y0 = max(min(m[1] for m in ms) - gp["group_pad"], cy0)
        x1 = min(max(m[0] + m[2] for m in ms) + gp["group_pad"], cx1)
        y1 = min(max(m[1] + m[3] for m in ms) + gp["group_pad"], cy1)
        out_groups.append(dict(id=g["id"], label=g["label"],
                               members=g["members"], bbox=(x0, y0, x1 - x0, y1 - y0)))
    return dict(container=dict(id=node["id"], rect=rect, content=content),
                nodes=out_nodes, edges=out_edges, groups=out_groups)


def _layout_graph_vertical(node, rect, p, gp, im, content):
    """组织树布局：层 = 行（根上子下），行内节点水平均分 + 同层同高同宽。
    行高 = 面板高/层数×(1−gutter)；节点宽 = 文本需宽与行内容纳宽取最小（文本超宽
    则自动断行、行高对应提升）。边默认 straight（跨层 N/S 正对中点）。"""
    cw0, ch0 = content[2], content[3]
    layers = bfs_layers(node.get("start"), node["nodes"], node["edges"])
    max_lvl = max(layers.values()) if layers else 0
    n_layer = max_lvl + 1
    step_y = ch0 / n_layer
    nh = step_y * (1.0 - gp["gutter_ratio"])
    rows = {}
    for n in node["nodes"]:
        rows.setdefault(layers[n["id"]], []).append(n)
    max_cnt = max(len(r) for r in rows.values())
    # 节点宽：文本单行需宽（fs0）统一 → 声明 node_w 下限 → 行内容纳上限钳制
    text_w = max(sum(w for _, _, w in textmesh.measure_prepare(n["text"],
                                                               p["text"]["fs0_node"]))
                 for n in node["nodes"]) / 72.0
    nw = max(text_w, node.get("node_w", gp["node_w_default"]),
             2 * gp["min_abs_gap"])
    nw = min(nw, cw0 / max_cnt * (1.0 - gp["gutter_ratio"]) if max_cnt else cw0)
    nw = max(nw, 2 * gp["min_abs_gap"])
    # 文本 autofit：候选宽下求统一节点高（同层同高；非矩形按形状内切区折算），
    # min_fs 仍超内切区 → overflow 标记
    fs0 = p["text"]["fs0_node"]
    nh_base = node.get("node_h", gp["node_h_default"])
    stf = gp["shape_text_fit"]
    need_h_max = 0.0
    for n in node["nodes"]:
        kf = SHAPE_KIND.get(n.get("kind", "proc"), "rounded_rect")
        fx, fy = stf.get(kf, (1.0, 1.0))
        fw, fh = max(nw, 0.1) * fx, nh_base * fy
        tl = textmesh.autofit_text(n["text"], fs0, fw * 72, fh * 72,
                                   min_fs=p["text"]["min_fs"])
        need_h_max = max(need_h_max, tl["need_h"] / (fy if fy > 0 else 1.0))
    nh = max(nh_base, need_h_max / 72.0)
    text_overflow, texts = [], {}
    for n in node["nodes"]:
        kf = SHAPE_KIND.get(n.get("kind", "proc"), "rounded_rect")
        fx, fy = stf.get(kf, (1.0, 1.0))
        fw, fh = nw * fx, nh * fy
        tl = textmesh.autofit_text(n["text"], fs0, fw * 72, fh * 72,
                                   min_fs=p["text"]["min_fs"])
        recompute = textmesh.wrap_layout(textmesh.measure_prepare(n["text"], tl["fs"]),
                                         fw * 72)
        if tl["fs"] <= p["text"]["min_fs"] + 1e-9 and \
           (recompute[1] > fw * 72 * p["text"]["margin_w"] or tl["need_h"] > fh * 72 + 1e-6):
            text_overflow.append(n["id"])
        texts[n["id"]] = tl
    # 行内水平均分（声明序稳定）+ 根层自然居中
    out_nodes, node_rect = [], {}
    for lvl in sorted(rows):
        cy = content[1] + (lvl + 0.5) * step_y
        row = rows[lvl]
        cnt = len(row)
        for i, n in enumerate(row):
            cx = content[0] + cw0 * (i + 0.5) / cnt
            r = (round(cx - nw / 2, 3), round(cy - nh / 2, 3),
                 round(nw, 3), round(nh, 3))
            node_rect[n["id"]] = r
            out_nodes.append(dict(id=n["id"], text=n["text"],
                                  kind=n.get("kind", "proc"), rect=r,
                                  text_layout=dict(texts[n["id"]]),
                                  overflow=n["id"] in text_overflow,
                                  shape=SHAPE_KIND.get(n.get("kind", "proc"),
                                                       "rounded_rect")))
    # 边：跨层 N/S 正对中点；orth 走左右走廊（自动取浅侧）
    out_edges = []
    for e in node["edges"]:
        ra, rb = node_rect[e["from"]], node_rect[e["to"]]
        sa, a1, sb, a2 = _v_anchor(ra, rb)
        lbl = e.get("label")
        # 垂直布局：带标签默认走真线（标签居中盖在连线中点上方），
        # 显式 way: orth 才走走廊（回边用；走廊被面板钳制时 FAIL）
        way = e.get("way") or "straight"
        ed = dict(from_id=e["from"], to_id=e["to"], label=lbl, way=way,
                  a1=a1, a2=a2, side1=sa, side2=sb)
        if way == "orth":
            ed["pts"] = _orth_route_v(e["from"], e["to"], node_rect, content, a1, a2, p)
        out_edges.append(ed)
    out_groups = []
    cx0, cy0, cx1, cy1 = (content[0], content[1],
                          content[0] + content[2], content[1] + content[3])
    for g in node.get("groups", []):
        ms = [node_rect[m] for m in g["members"]]
        x0 = max(min(m[0] for m in ms) - gp["group_pad"], cx0)
        y0 = max(min(m[1] for m in ms) - gp["group_pad"], cy0)
        x1 = min(max(m[0] + m[2] for m in ms) + gp["group_pad"], cx1)
        y1 = min(max(m[1] + m[3] for m in ms) + gp["group_pad"], cy1)
        out_groups.append(dict(id=g["id"], label=g["label"],
                               members=g["members"], bbox=(x0, y0, x1 - x0, y1 - y0)))
    return dict(container=dict(id=node["id"], rect=rect, content=content),
                nodes=out_nodes, edges=out_edges, groups=out_groups)