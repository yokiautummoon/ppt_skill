# -*- coding: utf-8 -*-
"""verify.py — 校验引擎：家族化收集 violations（不 assert 抛错），产 Report。

家族（按 styleguide_rules.md 约定）：
  G  几何核心（全类型必跑）：引用完整 / 几何有限正 / 面板安全区 / 遮挡显式受控 /
      磁吸锚点贴端口(第二实现重算) / orth 走廊 / 同层同高 / 组包络 ⊇ 成员
  D  容器级：面板互斥 / 节点 ⊆ 面板内容区
  T  文本：非空 / 不溢出（断行独立重算）/ min_fs 硬底
  S  规范（按 style_guide 选）：字号层级 / 配色上限·白名单 / 构件必含 / 栈账目 / 梯形单调

校验器与布局器是两套代码路径（第二实现比对）：锚点端口在此用独立公式重算。
"""
import math
import layout_rect as LR
import textmesh


class Report(object):
    """收集式校验结果：checks 列表 + violations 提取 + 摘要。"""

    def __init__(self, ir, compiled, p):
        self.ir, self.compiled, self.p = ir, compiled, p
        self.checks = []  # (family, name, ok, detail)

    def add(self, family, name, ok, detail=""):
        self.checks.append((family, name, bool(ok), detail))

    def family(self, fam):
        return [(n, ok, d) for f, n, ok, d in self.checks if f == fam]

    @property
    def violations(self):
        return [(f, n, d) for f, n, ok, d in self.checks if not ok]

    @property
    def pass_count(self):
        return sum(1 for _, _, ok, _ in self.checks if ok)

    def summary(self, indent="  "):
        """report.md 摘要段。"""
        fams = ["G", "D", "T", "S"]
        lines = []
        for fam in fams:
            items = self.family(fam)
            if not items:
                continue
            npass = sum(1 for _, ok, _ in items if ok)
            lines.append(f"{indent}[{fam}] {npass}/{len(items)} 通过")
            for name, ok, d in items:
                mark = "PASS" if ok else "FAIL"
                lines.append(f"{indent}  {mark} {name}" + (f"  ({d})" if d else ""))
        if self.violations:
            lines.append(f"{indent}违规 {len(self.violations)} 条 → 建议:")
            for f, n, d in self.violations:
                lines.append(f"{indent}  - [{f}] {n} {d}")
        return "\n".join(lines)


# ---- 独立第二实现：锚点重算（不信任布局器） ----
def _recompute_anchor(rect_a, rect_b, vertical=False):
    """a→b 磁吸锚点：主轴选择 + 端口 = AABB 边中点（供 V6 独立比对）。
    vertical=True（组织树）：跨层强制 N/S（上者出 S、下者入 N），同层回退水平主轴——
    与 layout_graph._v_anchor 同判据（第二实现不调用布局器）。"""
    ca = LR.center(rect_a)
    cb = LR.center(rect_b)
    ports = LR.aabb_nodes(rect_a)
    if vertical:
        overlap_y = min(rect_a[1] + rect_a[3], rect_b[1] + rect_b[3]) - max(rect_a[1], rect_b[1]) > 1e-9
        if overlap_y:
            dx, dy = cb[0] - ca[0], cb[1] - ca[1]
            if abs(dx) >= abs(dy):
                side = "E" if dx >= 0 else "W"
            else:
                side = "S" if dy >= 0 else "N"
            return side, ports[side]
        if rect_a[1] + rect_a[3] <= rect_b[1] + 1e-9:
            return "S", (ca[0], rect_a[1] + rect_a[3])
        return "N", (ca[0], rect_a[1])
    dx, dy = cb[0] - ca[0], cb[1] - ca[1]
    if abs(dx) >= abs(dy):
        side = "E" if dx >= 0 else "W"
    else:
        side = "S" if dy >= 0 else "N"
    return side, ports[side]


def _abs_compiled_anchors(ce):
    """具名锚点第二实现：归一坐标 + compiled rect（SPEC 原位）→ 绝对位。
    与 ir_builder._abs_anchors 独立实现（铁律：verify 不调用布局器）。"""
    x, y, w, h = ce["rect"]
    return {an: (x + nx * w, y + ny * h) for an, (nx, ny) in ce["anchors"].items()}


def _is_background(e, sw, sh, eps=1e-6):
    """全幅底层背景判定（模板惯例：rect 铺满 slide、无文本的 shape）。"""
    if e["type"] != "shape" or "text" in e:
        return False
    x, y, w, h = e["rect"]
    return (x <= eps and y <= eps and sw - (x + w) <= eps and sh - (y + h) <= eps)


def _bfs_layers(start, nodes, edges):
    """graph 层号（与 layout_graph.bfs_layers 同判据的独立实现：G13 判定回边用）。"""
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
    # 与 layout_graph.bfs_layers 同判据（2026-10-09 同步）：0 入度孤立源并入
    # 首层（出边为前向边），其余环上残支补尾层。
    leftover = [n["id"] for n in nodes if n["id"] not in layers]
    has_in = {e2["to"] for e2 in edges}
    srcs0 = [lid for lid in leftover if lid not in has_in]
    for lid in srcs0:
        layers[lid] = 0
    left2 = [lid for lid in leftover if lid not in srcs0]
    for i, lid in enumerate(left2):
        layers[lid] = (max(layers.values()) if layers else 0) + 1 + i
    return layers


def _segments(ln):
    """连线 → 折线段列表（orth 逐段 / 直连单段；curve 自由线不在此列）。"""
    pts = ln.get("pts")
    if pts and not ln.get("curve"):
        return [(pts[i], pts[i + 1]) for i in range(len(pts) - 1)]
    return [(ln["a1"], ln["a2"])]


def run(ir, compiled, p):
    """入口。返回 Report（violations 不抛错，由调用方决定 FAIL / 继续）。"""
    sv = (compiled.get("meta") or {}).get("style_guide")
    rules = None
    if sv:
        import styleguides as _SG
        rules = _SG.RULE_SETS.get(sv)
    eps = p["verify"]["eps"]
    sw, sh = ir["slide"]
    margin = ir["margin"] or {}

    rep = Report(ir, compiled, p)

    # ================= G 几何核心 =================
    elems = {e["id"]: e for e in ir["elements"]}
    # G1 引用完整：line/glue 端点存在且为元素
    for ln in ir["lines"]:
        if ln.get("from_id") is not None:
            rep.add("G", f"边 {ln['id']} 两端存在",
                    ln["from_id"] in elems and ln["to_id"] in elems)
    for gl in ir["glue"]:
        rep.add("G", f"glue {gl['id']} 两端存在",
                gl["from_id"] in elems and gl["to_id"] in elems)
    # G2 几何有限且尺寸为正
    for e in ir["elements"]:
        x, y, w, h = e["rect"]
        ok = all(math.isfinite(v) for v in (x, y, w, h)) and w > 0 and h > 0
        rep.add("G", f"元素 {e['id']} 几何有限/正", ok)
    # G3 安全区：有 margin 声明时全元素 ⊆ slide−margin（全幅背景豁免）
    bg_ids = {e["id"] for e in ir["elements"] if _is_background(e, sw, sh)}
    # ph 元素：seed 打底落点在模板占位符（rect 仅测量输入）→ 安全区/遮挡豁免
    ph_ids = {e["id"] for e in ir["elements"] if e.get("ph_info")}
    if margin:
        m_l, m_t = margin.get("l", 0), margin.get("t", 0)
        m_r, m_b = margin.get("r", 0), margin.get("b", 0)
        for e in ir["elements"]:
            if e["id"] in bg_ids:
                rep.add("G", f"背景 {e['id']} 全幅", True)
                continue
            if e["id"] in ph_ids:
                rep.add("G", f"元素 {e['id']} ⊆ 安全区", True,
                        "ph 占位符填充：落点=模板占位符（rect 仅测量）")
                continue
            ok, _ = LR.audit_rect_inside(e["rect"], (sw, sh), pad=0, eps=eps)
            inside_margin = (e["rect"][0] >= m_l - eps and e["rect"][1] >= m_t - eps and
                             e["rect"][0] + e["rect"][2] <= sw - m_r + eps and
                             e["rect"][1] + e["rect"][3] <= sh - m_b + eps)
            rep.add("G", f"元素 {e['id']} ⊆ 安全区", ok and inside_margin,
                    f"rect={tuple(round(v,3) for v in e['rect'])}")
        for g in ir["groups"]:
            x, y, w, h = g["bbox"]
            inside = (x >= m_l - eps and y >= m_t - eps and
                      x + w <= sw - m_r + eps and y + h <= sh - m_b + eps)
            rep.add("G", f"组 {g['id']} ⊆ 安全区", inside)
    else:
        for e in ir["elements"]:
            if e["id"] in bg_ids:
                rep.add("G", f"背景 {e['id']} 全幅", True)
                continue
            if e["id"] in ph_ids:
                rep.add("G", f"元素 {e['id']} ⊆ slide", True,
                        "ph 占位符填充：落点=模板占位符（rect 仅测量）")
                continue
            ok, _ = LR.audit_rect_inside(e["rect"], (sw, sh), eps=eps)
            rep.add("G", f"元素 {e['id']} ⊆ slide", ok)
    # G4 重叠合法来源三类：同 owner 派生 / relations.overlap 声明 /
    # 同编辑单元（scansci 内化块 2：编辑单元成员互遮 = 组内构图，合法）
    overlap_decl = set()
    for ov in (compiled.get("relations") or {}).get("overlap", []):
        overlap_decl.add(tuple(sorted((ov["id"], ov["with"]))))
    eg_of = {}
    for g in (ir.get("edit_groups") or []):
        for m in g["members"]:
            eg_of[m] = g["id"]
    # 组包络矩形不参与"元素互遮"检查（它含成分是合法包络），只查 elements
    for i, a in enumerate(ir["elements"]):
        if a["id"] in bg_ids or a["id"] in ph_ids:
            continue
        for b in ir["elements"][i + 1:]:
            if b["id"] in bg_ids or b["id"] in ph_ids:
                continue
            if b["id"] == a["id"]:
                continue
            if not LR.rects_intersect(a["rect"], b["rect"], eps):
                continue
            pair = tuple(sorted((a["id"], b["id"])))
            same_owner = a.get("owner") is not None and a.get("owner") == b.get("owner")
            declared = pair in overlap_decl
            same_eg = eg_of.get(a["id"]) is not None and eg_of.get(a["id"]) == eg_of.get(b["id"])
            rep.add("G", f"遮挡 {a['id']}↔{b['id']} 合法来源",
                    same_owner or declared or same_eg,
                    "同容器兄弟" if same_owner
                    else ("overlap 声明" if declared
                          else ("同编辑组" if same_eg else "未声明 ×")))
    # G5/G6 磁吸锚点：贴端口 + 第二实现重算
    # 组织树边（graph orientation: vertical）按垂直主轴独立重算（与 _v_anchor 同判据）
    vertical_nodes = {n["id"]
                      for e in (compiled.get("elements") or [])
                      if e.get("type") == "graph" and e.get("orientation") == "vertical"
                      for n in e.get("nodes", [])}
    for ln in ir["lines"] + ir["glue"]:
        if ln.get("an1"):
            continue   # 具名锚点 glue：端点 = 锚点绝对位由 G10 独立重算（豁免
                       # AABB 边中点判据；编译期已成对强制，an1 ⟹ an2）
        ra = elems.get(ln.get("from_id") or ln.get("from"))
        rb = elems.get(ln.get("to_id") or ln.get("to"))
        if ln.get("from_id") is None and ln.get("from") is None:
            continue  # 自由线（x1y1x2y2）
        if ra is None or rb is None:
            continue  # G1 已记
        # 端口贴边断言：a1 在某端口 ±eps
        pa = LR.aabb_nodes(ra["rect"])
        top = ({side: abs(ln["a1"][0] - pt[0]) <= eps and abs(ln["a1"][1] - pt[1]) <= eps
                for side, pt in pa.items()})
        on_port = any(top.values())
        rep.add("G", f"锚点 {ln['id']} a1 贴端口", on_port,
                f"a1={tuple(round(v,3) for v in ln['a1'])} ports={ {k: tuple(round(v,3) for v in vv) for k,vv in pa.items()} }")
        # 第二实现重算 a1（vertical 边按组织树判据：跨层强制 N/S、同层 E/W 回退）
        vertical = (ln.get("from_id") in vertical_nodes
                    and ln.get("to_id") in vertical_nodes)
        side, exp = _recompute_anchor(ra["rect"], rb["rect"], vertical=vertical)
        rep.add("G", f"锚点 {ln['id']} 独立重算一致",
                abs(exp[0] - ln["a1"][0]) <= eps and abs(exp[1] - ln["a1"][1]) <= eps,
                f"layout={tuple(round(v,3) for v in ln['a1'])} 重算={tuple(round(v,3) for v in exp)} [{side}]")
    # G10 具名锚点解析一致（scansci 连接配方内化）：glue 端点 = 元素 anchors
    # 绝对位 ±eps（第二实现：从 compiled 归一坐标重算，不读 IR 现成锚点值）。
    comp_anchors = {}
    for ce in (compiled.get("elements") or []):
        if ce.get("anchors"):
            comp_anchors[ce["id"]] = _abs_compiled_anchors(ce)
    for gl in ir["glue"]:
        if not gl.get("an1"):
            continue
        want1 = comp_anchors.get(gl["from_id"], {}).get(gl["an1"])
        want2 = comp_anchors.get(gl["to_id"], {}).get(gl["an2"])
        ok1 = want1 is not None and abs(gl["a1"][0] - want1[0]) <= eps \
            and abs(gl["a1"][1] - want1[1]) <= eps
        ok2 = want2 is not None and abs(gl["a2"][0] - want2[0]) <= eps \
            and abs(gl["a2"][1] - want2[1]) <= eps
        rep.add("G", f"锚点一致 {gl['id']}", ok1 and ok2,
                f"a1={tuple(round(v,3) for v in gl['a1'])} 期望"
                f"{tuple(round(v,3) for v in want1) if want1 else '∅'} · "
                f"a2={tuple(round(v,3) for v in gl['a2'])} 期望"
                f"{tuple(round(v,3) for v in want2) if want2 else '∅'}")
    # G7 orth 折线结构：4 段、端点=端口、走廊不越面板内容区。
    # 折线形态按布局方向双态：水平布局先竖段（竖直走廊）、垂直布局先横段（水平走廊）
    for ln in ir["lines"]:
        pts = ln.get("pts")
        if not pts or ln.get("curve"):
            continue   # curve 是自由 polyline（freeform），非 orth 4 段折线
        ok_struct = (len(pts) == 4 and
                     abs(pts[0][0] - ln["a1"][0]) <= eps and abs(pts[0][1] - ln["a1"][1]) <= eps and
                     abs(pts[3][0] - ln["a2"][0]) <= eps and abs(pts[3][1] - ln["a2"][1]) <= eps)
        mon_h = (pts[0][0] == pts[1][0] and pts[2][0] == pts[3][0] and pts[1][1] == pts[2][1])
        mon_v = (pts[0][1] == pts[1][1] and pts[2][1] == pts[3][1] and pts[1][0] == pts[2][0])
        rep.add("G", f"orth 折线 {ln['id']} 结构", ok_struct and (mon_h or mon_v),
                f"pts={[tuple(round(v,3) for v in pt) for pt in pts]}")
    # G8 同层同高（graph 容器节点同列同高）/ 节点 ⊆ 内容区（D3 并入）。
    # 只查 graph 容器：stack/dock children 与 cylinder 展开部件（侧壁/椭圆高
    # 必然不同）不经此不变式——G8 语义本就是 graph 节点同列同高。
    graph_ids = {e["id"] for e in compiled["elements"] if e.get("type") == "graph"}
    owners = set(e.get("owner") for e in ir["elements"] if e.get("owner"))
    for own in owners:
        if own not in graph_ids:
            continue
        owned = [e for e in ir["elements"] if e.get("owner") == own and e["type"] == "shape"]
        if not owned:
            continue
        hs = {round(e["rect"][3], 4) for e in owned}
        rep.add("G", f"容器 {own} 节点同高", len(hs) == 1, f"h={sorted(hs)}")
    # G9 组包络 ⊇ 成员（members rect ⊆ bbox − pad 校验：bbox 是成员外包+pad，故成员必须在内）
    memb = {}
    for g in ir["groups"]:
        for m in g.get("members", []):
            memb.setdefault(g["id"], []).append(m)
    elems_shp = {e["id"]: e for e in ir["elements"] if e["type"] == "shape"}
    for g in ir["groups"]:
        inside_all = True
        for m in g.get("members", []):
            r = elems_shp.get(m)
            if r is None:
                inside_all = False
                continue
            if not LR.rect_contains(g["bbox"], r["rect"], eps):
                inside_all = False
        rep.add("G", f"组 {g['id']} 包络 ⊇ 成员", inside_all,
                f"bbox={tuple(round(v,3) for v in g['bbox'])}")
    # G11 编辑单元区间（scansci 内化块 2）：组成员 z 连续区间且在区间内无外部元素
    # ——独立重算（不读 ir 的 z_lo/z_hi 现成值），z 收拢算法 bug 即违规
    for g in (ir.get("edit_groups") or []):
        ids = set(g["members"])
        zs = [e["z"] for e in ir["elements"] if e["id"] in ids]
        if len(zs) != len(ids):
            rep.add("G", f"编辑组 {g['id']} 成员齐备", False,
                    f"IR 缺成员（有 {len(zs)}/{len(ids)}）")
            continue
        lo, hi = min(zs), max(zs)
        contiguous = (hi - lo + 1 == len(ids))
        outsider = [e["id"] for e in ir["elements"]
                    if lo <= e["z"] <= hi and e["id"] not in ids]
        rep.add("G", f"编辑组 {g['id']} z 区间", contiguous and not outsider,
                f"z 范围[{lo},{hi}] 连续={contiguous} 区间外来客={outsider or '∅'}")
    # G12 连线不得盖节点文字（z 类序不变式）：任一边线段穿越某节点盒时，该边
    # z 必须 < 该节点 z（节点盖线）。2026-10-09 连线治理决策根因 2；编辑组收拢
    # 会压缩元素 z，故按"实际穿越对"断言而非全局"边<节点"。
    for ln in ir["lines"]:
        f, t = ln.get("from_id"), ln.get("to_id")
        if f is None or t is None:
            continue
        nf = elems.get(f)
        own = nf.get("owner") if nf else None
        if own is None:
            continue
        crossed = [nid for nid, ne in elems.items()
                   if ne.get("owner") == own and ne.get("type") == "shape"
                   and nid not in (f, t)
                   and any(LR.segment_rect_overlap(a, b, ne["rect"])
                           for a, b in _segments(ln))]
        if not crossed:
            continue
        nmin = min(ne["z"] for nid, ne in elems.items() if nid in crossed)
        rep.add("G", f"边 {ln['id']} 低于节点", ln["z"] < nmin,
                f"穿越 {crossed}（节点 min z={nmin}） 边 z={ln['z']}")
    # G13 回边绕行：目标层 ≤ 源层的图边不得穿越同图非端点节点盒（布局器自动
    # 走走廊；残留穿越 = 显式 way 强制直连或走廊受阻回退——改拓扑或扩面板）。
    for gc in (compiled.get("elements") or []):
        if gc.get("type") != "graph":
            continue
        if (gc.get("orientation") or "horizontal") == "vertical":
            continue
        gnodes = gc.get("nodes") or []
        gedges = gc.get("edges") or []
        if not gnodes or not gedges:
            continue
        layers = _bfs_layers(gc.get("start"), gnodes, gedges)
        own = gc["id"]
        own_shapes = {nid: ne for nid, ne in elems.items()
                      if ne.get("owner") == own and ne.get("type") == "shape"}
        ln_by = {l["id"]: l for l in ir["lines"]
                 if l.get("from_id") is not None and l.get("to_id") is not None
                 and l.get("from_id") in own_shapes}
        for e in gedges:
            f, t = e.get("from"), e.get("to")
            if f not in layers or t not in layers:
                continue
            if layers[t] > layers[f]:
                continue   # 前向边：允许贴节点走线（节点 z 盖线，可接受）
            ln = ln_by.get(f"{own}.{f}->{t}")
            if ln is None:
                continue
            crossed = [nid for nid, ne in own_shapes.items()
                       if nid not in (f, t)
                       and any(LR.segment_rect_overlap(a, b, ne["rect"])
                               for a, b in _segments(ln))]
            rep.add("G", f"回边 {ln['id']} 绕行不穿节点", not crossed,
                    f"穿越: {crossed or '∅'}")

    # ================= D 容器级 =================
    # D1 叶级元素互斥：不同 owner 的顶层元素（不含容器内）两两不相交已由 G4 管；
    #    此处只查 graph 节点 ⊆ 图面板内容区：经 owner 容器 rect 反向约束
    for own in owners:
        own_rect = elems.get(own)
        if not own_rect:
            continue
        im = p["graph"]["inner_margin"]
        content = LR.pad_rect(own_rect["rect"], im)
        for e in ir["elements"]:
            if e.get("owner") == own and e["type"] == "shape":
                ok, why = LR.audit_rect_inside(e["rect"], (content[2], content[3]),
                                               pad=0, eps=eps)
                # audit 以原点对齐；改用绝对坐标 inside 检查
                x, y, w, h = e["rect"]
                inside = (content[0] - eps <= x and content[1] - eps <= y and
                          x + w <= content[0] + content[2] + eps and
                          y + h <= content[1] + content[3] + eps)
                rep.add("D", f"节点 {e['id']} ⊆ 面板内容区", inside,
                        f"content={tuple(round(v,3) for v in content)}")
    # 顶层元素（无 owner）互不相交已由 G4 覆盖（未声明 → 违例）

    # ================= T 文本 =================
    for e in ir["elements"]:
        if "text" not in e:
            continue
        tid = e["id"]
        rep.add("T", f"文本非空 {tid}", bool(e["text"]) and e["text"].strip())
        tl = e.get("text_layout")
        if tl is None:
            continue
        # 独立重算断行（非矩形节点按形状内切区判定：菱形/椭圆/圆柱顶点不可容文本）
        stf = p["graph"]["shape_text_fit"]
        kind = e.get("shape") or "rounded_rect"
        fx, fy = stf.get(kind, (1.0, 1.0))
        box_w_pt = e["rect"][2] * 72 * fx
        box_h_pt = e["rect"][3] * 72 * fy
        segs = textmesh.measure_prepare(e["text"], tl["fs"])
        lines, max_w = textmesh.wrap_layout(segs, box_w_pt)
        same_lines = len(lines) == tl["lines"]
        h_ok = max_w <= box_w_pt * p["text"]["margin_w"]
        v_ok = tl["need_h"] <= box_h_pt + 1e-6
        rep.add("T", f"断行重算一致 {tid}", same_lines,
                f"layout {tl['lines']} vs 重算 {len(lines)}")
        rep.add("T", f"水平不溢出 {tid}", h_ok,
                f"max_w={max_w:.1f}pt 框={box_w_pt:.1f}pt(fit {fx})")
        rep.add("T", f"垂直不溢出 {tid}", v_ok,
                f"need_h={tl['need_h']:.1f}pt 框={box_h_pt:.1f}pt(fit {fy})")
        rep.add("T", f"min_fs 硬底 {tid}", tl["fs"] >= p["text"]["min_fs"] - 1e-9,
                f"fs={tl['fs']}pt min={p['text']['min_fs']}pt")
        if e.get("overflow"):
            rep.add("T", f"autofit 超框标记 {tid}", False, "缩到硬底仍超框 → 建议拆元素/扩框")

    # ---- T 家族：table 单元格文本 ≤ 单元格（列宽/行高 − 2×cell_pad，与渲染同源）----
    for e in ir["elements"]:
        if e["type"] != "table":
            continue
        rows, cols = e["rows"], e["cols"]
        row_h_pt = e["rect"][3] / rows * 72
        pad = p["table"]["cell_pad"] * 72
        for ri in range(rows):
            fs = e.get("header_fs") if (ri == 0 and e.get("header")) else e.get("cell_fs")
            fs = fs or p["table"]["fs"]
            for ci in range(cols):
                txt = str(e["data"][ri][ci])
                box_w_pt = e["col_widths"][ci] * 72 - 2 * pad
                segs = textmesh.measure_prepare(txt, fs)
                lines, max_w = textmesh.wrap_layout(segs, box_w_pt)
                need_h = len(lines) * p["text"]["line_h"] * fs
                ok = (max_w <= box_w_pt * p["text"]["margin_w"]
                      and need_h <= row_h_pt - 2 * pad + 1e-6)
                rep.add("T", f"表格格 ({ri},{ci}) 不溢出", ok,
                        f"row{ri} col{ci} {txt!r}: max_w={max_w:.1f} need_h={need_h:.1f} "
                        f"格宽={box_w_pt:.1f}pt 行高={row_h_pt:.1f}pt")

    # ================= S 规范（按 style_guide）================
    if rules:
        _s_family(rep, rules, p, sv)

    # S6 页型意图断言（page_intent 审定菜单：每原型专属断言背书引擎展开，见
    #   references/page-intents.md。cover 破格封面族）
    _s_page_intent(rep, p)

    # S10 排版规范（A2 内化：强调密度 / 标题字数 / 正文密度 / 标题字号下限；
    #   阈值 references/design-norms.md，params.verify.typography 可调）
    _s_typography(rep, p)

    # S7 复合部件叠区保真（性质② apart_alpha 移植）：cylinder 端面叠于侧壁
    # 之上，声明 face_opacity 为端面区目标不透明度，展开反解端面 alpha，断言
    # 叠区合成 = face_opacity（α 语义 = 不透明度，与 alpha_math 一致）。
    _s_cylinder_alpha(rep, compiled)

    # S8 主题结构/母题断言（meta.theme.structure / motif；缺省 uniform/none →
    #   不产生断言，零行为变化）。
    _s_theme_structure(rep, p)
    _s_theme_motif(rep, p)

    return rep


def _s_theme_structure(rep, p):
    """S8 三明治/深色结构断言（meta.theme.structure != uniform）：
    深页（compiled.meta._page_dark）须注入全幅 framework.background 且页型文本为
    浅色（深底浅字反色正确）；浅页不得注入背景（透出白底/母版）。"""
    import themes as TH
    structure = (p.get("theme") or {}).get("structure", "uniform")
    if structure == "uniform":
        return
    meta = rep.compiled.get("meta") or {}
    dark = bool(meta.get("_page_dark"))
    bg = (rep.ir.get("framework") or {}).get("background")
    if dark:
        rep.add("S", "三明治深页全幅背景", bool(bg),
                f"structure={structure} · bg={bg!r}")
        cols = [(e["id"], (e.get("text_style") or {}).get("color"))
                for e in rep.ir["elements"]
                if e.get("type") == "text" and (e.get("text_style") or {}).get("color")
                and TH.is_hex((e.get("text_style") or {}).get("color"))]
        ok = all(TH.luma(c) >= 170 for _, c in cols)
        rep.add("S", "三明治深页文字反色", ok,
                "; ".join(f"{i}={c}(luma{TH.luma(c):.0f})" for i, c in cols)
                or "无带色文本（跳过）")
    else:
        rep.add("S", "三明治浅页无注入背景", bg is None,
                f"structure={structure} · bg={bg!r}")


def _s_theme_motif(rep, p):
    """S8 视觉母题断言（meta.theme.motif == circle_icon）：每个 icon 须有背衬圆
    （id 后缀 _circ、type=shape/kind=oval、中心与图标重合、z 低于图标）。"""
    motif = (p.get("theme") or {}).get("motif", "none")
    if motif != "circle_icon":
        return
    eps = p["verify"]["eps"]
    els = {e["id"]: e for e in rep.ir["elements"]}
    for e in rep.ir["elements"]:
        if e.get("type") != "icon":
            continue
        c = els.get(e["id"] + "_circ")
        ix, iy, iw, ih = e["rect"]
        ok = c is not None and c.get("kind") == "oval" and c["z"] < e["z"]
        det = "背衬缺失" if c is None else (
            f"中心差 d={(abs((c['rect'][0] + c['rect'][2] / 2) - (ix + iw / 2)) + abs((c['rect'][1] + c['rect'][3] / 2) - (iy + ih / 2))):.3f} "
            f"z_circ={c['z']} z_icon={e['z']}")
        if c is not None:
            ok = ok and abs((c["rect"][0] + c["rect"][2] / 2) - (ix + iw / 2)) <= eps \
                and abs((c["rect"][1] + c["rect"][3] / 2) - (iy + ih / 2)) <= eps
        rep.add("S", f"母题背衬圆 {e['id']}_circ", ok, det)


def _s_cylinder_alpha(rep, compiled):
    """S7 断言：cylinder 端面叠区合成 alpha = 声明 face_opacity（性质②）。"""
    import alpha_math as AM
    by_part = {e["id"]: e for e in rep.ir["elements"]}
    for e in compiled.get("elements", []):
        if e.get("type") != "shape" or e.get("kind") != "cylinder":
            continue
        eid = e["id"]
        side = by_part.get(eid + ".side")
        if side is None:
            continue
        side_a = float(side["style"].get("opacity", 0.35))
        face_tgt = float(e.get("face_opacity", 1.0))
        for fk in ("top", "bot"):
            face = by_part.get(eid + "." + fk)
            if face is None:
                continue
            face_a = float(face["style"].get("opacity", 1.0))
            got = AM.merge_alpha([side_a, face_a])
            rep.add("S", f"cylinder {eid} 端面{fk} 叠区保真",
                    abs(got - face_tgt) <= AM.EPS,
                    f"merge[{side_a:.3g}, {face_a:.3g}]={got:.3g} ≈ {face_tgt:.3g}")


def _s_page_intent(rep, p):
    """页型意图断言（每原型 = 布局代码 + verify 断言；references/page-intents.md）。
    cover：必需构件 + 破格度（标题中心偏离 slide 中心 ≥ break_ratio×版心）+ 声明
    字段展开。section：必需构件 + 贯穿度（sec_num 高 ≥ 版心×num_h_min_ratio，超大
    数字版面）+ 层级（num 字号 > title 字号，数字是主导视觉）。"""
    intent = rep.ir.get("page_intent")
    # 数据驱动派发：查表（未实现页型 → 无专属断言，如 content 走默认版式）。
    _check = _INTENT_CHECKS.get(intent) if intent else None
    if _check:
        _check(rep, p)


def _intent_variant(rep, intent):
    """页变体：IR 记录优先（ir_builder 已选型），否则取 SPEC 声明，再否则家族首变体
    （单页/直构场景向后兼容）。来源唯一 = scripts/intents.py::FAMILIES。"""
    v = rep.ir.get("page_intent_variant")
    if v:
        return v
    import intents as IN
    decl = (rep.compiled.get("meta") or {}).get(intent) or {}
    return IN.resolve(intent, decl.get("variant"))


def _s_intent_cover(rep, p):
    """cover 断言（按变体分支）：必需构件（cov_deco/cov_title）+ 各变体的反向破格
    断言（left 中心偏离 / band 横向贯穿 / split 纵向贯穿）+ 声明字段展开。"""
    eps = p["verify"]["eps"]
    cp = p["page_intent"]["cover"]
    variant = _intent_variant(rep, "cover")
    elems = {e["id"]: e for e in rep.ir["elements"]}
    sw = rep.ir["slide"][0]
    m = rep.ir["margin"]
    ml = float(m.get("l", 0.5))
    mr = float(m.get("r", 0.5))
    mt = float(m.get("t", 0.5))
    mb = float(m.get("b", 0.5))
    cw = sw - ml - mr
    ch = rep.ir["slide"][1] - mt - mb
    rep.add("S", "页型 cover 变体", variant in ("left", "band", "split"), variant)
    for need in ("cov_deco", "cov_title"):
        rep.add("S", f"页型 cover 必需 {need}", need in elems)
    t, d = elems.get("cov_title"), elems.get("cov_deco")
    if variant == "band" and d:
        bp = cp["band"]
        rep.add("S", "cover 横向贯穿", d["rect"][2] >= cw * bp["band_w_min_ratio"] - eps
                and d["rect"][3] >= bp["band_h_min"] - eps,
                f"色带 {d['rect'][2]:.3f}×{d['rect'][3]:.3f}（版心宽 {cw:.3f} 须 ≥ "
                f"{bp['band_w_min_ratio']:.2f}×；高 ≥ {bp['band_h_min']}）")
    elif variant == "split" and d:
        xp = cp["split"]
        inside = (t and t["rect"][0] >= d["rect"][0] - eps
                  and t["rect"][0] + t["rect"][2] <= d["rect"][0] + d["rect"][2] + eps)
        rep.add("S", "cover 纵向贯穿", d["rect"][3] >= ch * xp["panel_h_min_ratio"] - eps,
                f"色块高 {d['rect'][3]:.3f}（版心高 {ch:.3f} 须 ≥ "
                f"{xp['panel_h_min_ratio']:.2f}×）")
        rep.add("S", "cover 标题嵌色块", bool(inside),
                "标题须落在左侧色块内（split 变体）")
    elif t:
        cx = t["rect"][0] + t["rect"][2] / 2
        drift = abs(cx - sw / 2) / cw
        rep.add("S", "cover 破格度", drift >= cp["break_ratio"] - eps,
                f"标题中心 {cx:.3f}（slide 中心 {sw/2:.3f}）drift={drift:.3f}"
                f" ≥ {cp['break_ratio']}")
    cov = (rep.compiled.get("meta") or {}).get("cover") or {}
    for fld, eid in (("subtitle", "cov_sub"), ("meta", "cov_meta")):
        if cov.get(fld):
            rep.add("S", f"cover {fld} 展开 {eid}", eid in elems)


def _s_intent_section(rep, p):
    """section 断言（按变体分支）：必需构件 + 各变体反向破格断言（num_left 数字
    纵贯 / num_giant 序号贴右下 / band 色带横贯）+ 字号层级（数字主导）。"""
    eps = p["verify"]["eps"]
    sp = p["page_intent"]["section"]
    variant = _intent_variant(rep, "section")
    elems = {e["id"]: e for e in rep.ir["elements"]}
    sw = rep.ir["slide"][0]
    m = rep.ir["margin"]
    ml = float(m.get("l", 0.5))
    mr = float(m.get("r", 0.5))
    cw = sw - ml - mr
    ch = rep.ir["slide"][1] - float(m.get("t", 0.5)) - float(m.get("b", 0.5))
    rep.add("S", "页型 section 变体",
            variant in ("num_left", "num_giant", "band"), variant)
    need = ("sec_num", "sec_title") if variant == "num_giant" \
        else ("sec_deco", "sec_num", "sec_title")
    for nid in need:
        rep.add("S", f"页型 section 必需 {nid}", nid in elems)
    n, d = elems.get("sec_num"), elems.get("sec_deco")
    if n:
        nh = n["rect"][3]
        if variant == "num_giant":
            gp = sp["num_giant"]
            right = n["rect"][0] + n["rect"][2]
            rep.add("S", "section 序号贴右",
                    abs(right - (sw - mr)) <= gp["right_tol"] + eps,
                    f"序号右缘 {right:.3f}（版心右缘 {sw - mr:.3f}，容差 "
                    f"{gp['right_tol']}）")
            rep.add("S", "section 贯穿度",
                    nh >= ch * gp["num_h_min_ratio"] - eps,
                    f"sec_num 高 {nh:.3f}（版心高 {ch:.3f} 须 ≥ "
                    f"{gp['num_h_min_ratio']:.2f}×）")
        elif variant == "band":
            bp = sp["band"]
            if d:
                rep.add("S", "section 横向贯穿",
                        d["rect"][2] >= cw * bp["band_w_min_ratio"] - eps
                        and d["rect"][3] >= ch * bp["band_h_min_ratio"] - eps,
                        f"色带 {d['rect'][2]:.3f}×{d['rect'][3]:.3f}（版心宽 {cw:.3f} "
                        f"须 ≥ {bp['band_w_min_ratio']:.2f}×；高 ≥ "
                        f"{bp['band_h_min_ratio']:.2f}×版心高）")
        else:
            rep.add("S", "section 贯穿度", nh >= ch * sp["num_h_min_ratio"] - eps,
                    f"sec_num 高 {nh:.3f}（版心高 {ch:.3f} 须 ≥ "
                    f"{sp['num_h_min_ratio']:.2f}×）")
        t = elems.get("sec_title")
        if t and "text_layout" in n and "text_layout" in t:
            nf, tf = n["text_layout"]["fs"], t["text_layout"]["fs"]
            rep.add("S", "section 字号层级", nf > tf,
                    f"num fs {nf} > title fs {tf}（大数字是节页主导视觉）")


def _s_intent_problem(rep, p):
    """problem 页型断言（科研问题陈述页）：必需构件 + 贯穿度（标记块高 ≥ 版心×
    比——纵向贯穿破格，反向断言防回刻板）+ 左对齐（非居中破格）+ items 展开。"""
    eps = p["verify"]["eps"]
    pp = p["page_intent"]["problem"]
    elems = {e["id"]: e for e in rep.ir["elements"]}
    mt = float(rep.ir["margin"].get("t", 0.5))
    mb = float(rep.ir["margin"].get("b", 0.5))
    ch = rep.ir["slide"][1] - mt - mb
    for need in ("prb_badge", "prb_title"):
        rep.add("S", f"页型 problem 必需 {need}", need in elems)
    b = elems.get("prb_badge")
    if b:
        rep.add("S", "problem 贯穿度", b["rect"][3] >= ch * pp["badge_h_min_ratio"] - eps,
                f"标记块高 {b['rect'][3]:.3f}（版心高 {ch:.3f} 须 ≥ "
                f"{pp['badge_h_min_ratio']:.2f}×）")
    t = elems.get("prb_title")
    if t:
        align = (t.get("text_style") or {}).get("align")
        rep.add("S", "problem 左对齐破格", align == "left",
                f"主问题 align={align}（须 left，非居中）")
    prb = (rep.compiled.get("meta") or {}).get("problem") or {}
    items = prb.get("items") or []
    if items:
        it = elems.get("prb_items")
        rep.add("S", "problem items 展开",
                it is not None and it["text"].count("\n") + 1 == len(items),
                f"items {len(items)} 项 vs 展开 {it['text'].count(chr(10)) + 1 if it else 0} 行")


def _s_intent_versus(rep, p):
    """versus 页型断言（科研对照页）：必需构件（双面板/分割线/VS 标）+ 均衡
    （两栏等宽）+ 对称（分割线居中）+ 分色（左右面板异色）。"""
    eps = p["verify"]["eps"]
    vp = p["page_intent"]["versus"]
    elems = {e["id"]: e for e in rep.ir["elements"]}
    sw = rep.ir["slide"][0]
    ml = float(rep.ir["margin"].get("l", 0.5))
    mr_ = float(rep.ir["margin"].get("r", 0.5))
    cw = sw - ml - mr_
    for need in ("vsv_panel_l", "vsv_panel_r", "vsv_divider", "vsv_tag"):
        rep.add("S", f"页型 versus 必需 {need}", need in elems)
    l, r = elems.get("vsv_panel_l"), elems.get("vsv_panel_r")
    if l and r:
        rep.add("S", "versus 均衡", abs(l["rect"][2] - r["rect"][2]) <= vp["balance_tol"] + eps,
                f"左栏 {l['rect'][2]:.3f} vs 右栏 {r['rect'][2]:.3f}（差须 ≤ {vp['balance_tol']}）")
        fl = (l.get("style") or {}).get("fill")
        fr = (r.get("style") or {}).get("fill")
        rep.add("S", "versus 分色", fl != fr, f"左 {fl} vs 右 {fr}（对立着色）")
    d = elems.get("vsv_divider")
    if d:
        cx = d["rect"][0] + d["rect"][2] / 2.0
        rep.add("S", "versus 对称", abs(cx - sw / 2.0) <= cw * vp["sym_tol_ratio"] + eps,
                f"分割线中心 {cx:.3f}（slide 中心 {sw / 2.0:.3f}）")


def _s_intent_route(rep, p):
    """route 页型断言（科研技术路线页）：必需构件（rte_stage* 数量 = stages）+ 等步距
    （相邻阶段中心间距极差 ≤ 容差）+ 横向贯穿（首阶段左缘≈版心左、末阶段右缘≈版心右）。"""
    eps = p["verify"]["eps"]
    rp = p["page_intent"]["route"]
    elems = {e["id"]: e for e in rep.ir["elements"]}
    rte = (rep.compiled.get("meta") or {}).get("route") or {}
    stages = rte.get("stages") or []
    stage_els = sorted((e for k, e in elems.items() if k.startswith("rte_stage")),
                       key=lambda e: e["rect"][0])
    rep.add("S", "页型 route 必需 rte_stage*",
            len(stages) >= rp["count_min"] and len(stage_els) == len(stages),
            f"stages {len(stages)} 项 vs 展开 {len(stage_els)} 阶段条")
    if len(stage_els) >= 2:
        centers = [e["rect"][0] + e["rect"][2] / 2.0 for e in stage_els]
        gaps = [centers[i + 1] - centers[i] for i in range(len(centers) - 1)]
        rep.add("S", "route 等步距", max(gaps) - min(gaps) <= rp["even_tol"] + eps,
                f"相邻中心间距 {min(gaps):.3f}~{max(gaps):.3f}（极差须 ≤ {rp['even_tol']}）")
        sw = rep.ir["slide"][0]
        ml = float(rep.ir["margin"].get("l", 0.5))
        mr_ = float(rep.ir["margin"].get("r", 0.5))
        cw = sw - ml - mr_
        fx = stage_els[0]["rect"][0]
        rx = stage_els[-1]["rect"][0] + stage_els[-1]["rect"][2]
        rep.add("S", "route 横向贯穿",
                abs(fx - ml) <= 0.05 and abs(rx - (ml + cw)) <= 0.05,
                f"首阶段左缘 {fx:.3f}（版心左 {ml:.3f}）/ 末阶段右缘 {rx:.3f}"
                f"（版心右 {ml + cw:.3f}）")


def _s_intent_panels(rep, p):
    """panels 断言（内容页结构生成样板 1）：必需构件（pnl_title/pnl_panel*）+
    网格贯穿（铺满版心宽）+ 等宽（even）/首板全宽（hero_left）。"""
    eps = p["verify"]["eps"]
    cp = p["page_intent"]["panels"]
    variant = _intent_variant(rep, "panels")
    elems = {e["id"]: e for e in rep.ir["elements"]}
    sw = rep.ir["slide"][0]
    ml = float(rep.ir["margin"].get("l", 0.5))
    mr = float(rep.ir["margin"].get("r", 0.5))
    cw = sw - ml - mr
    rep.add("S", "页型 panels 变体", variant in ("even", "hero_left"), variant)
    panels = [e for k, e in elems.items() if k.startswith("pnl_panel")]
    rep.add("S", "页型 panels 必需 pnl_title", "pnl_title" in elems)
    rep.add("S", "页型 panels 必需 pnl_panel0", "pnl_panel0" in elems)
    if panels:
        lx = min(e["rect"][0] for e in panels)
        rx = max(e["rect"][0] + e["rect"][2] for e in panels)
        rep.add("S", "panels 网格贯穿", (rx - lx) >= cw * cp["grid_span_ratio_min"] - eps,
                f"网格跨 {rx - lx:.3f}（版心宽 {cw:.3f} 须 ≥ "
                f"{cp['grid_span_ratio_min']:.2f}×）")
        if variant == "hero_left":
            hero = elems.get("pnl_panel0")
            rep.add("S", "panels 首板贯穿",
                    bool(hero) and hero["rect"][2] >= cw - eps,
                    f"首板宽 {hero['rect'][2] if hero else 0:.3f}（须 ≈ 版心宽 {cw:.3f}）")
        else:
            ws = [e["rect"][2] for e in panels]
            rep.add("S", "panels 面板等宽", max(ws) - min(ws) <= eps,
                    f"面板宽 {min(ws):.3f}~{max(ws):.3f}")


def _s_intent_columns(rep, p):
    """columns 断言（内容页结构生成样板 2）：必需构件（col_title/col_head*）+
    栏组贯穿 + 分栏等宽 + arrow 变体栏间箭头在场。"""
    eps = p["verify"]["eps"]
    cp = p["page_intent"]["columns"]
    variant = _intent_variant(rep, "columns")
    elems = {e["id"]: e for e in rep.ir["elements"]}
    sw = rep.ir["slide"][0]
    ml = float(rep.ir["margin"].get("l", 0.5))
    mr = float(rep.ir["margin"].get("r", 0.5))
    cw = sw - ml - mr
    rep.add("S", "页型 columns 变体", variant in ("even", "arrow"), variant)
    heads = sorted((e for k, e in elems.items() if k.startswith("col_head")),
                   key=lambda e: e["rect"][0])
    rep.add("S", "页型 columns 必需 col_title", "col_title" in elems)
    rep.add("S", "页型 columns 必需 col_head0", "col_head0" in elems)
    if heads:
        ws = [e["rect"][2] for e in heads]
        rep.add("S", "columns 分栏等宽", max(ws) - min(ws) <= eps,
                f"栏宽 {min(ws):.3f}~{max(ws):.3f}")
        lx = heads[0]["rect"][0]
        rx = heads[-1]["rect"][0] + heads[-1]["rect"][2]
        rep.add("S", "columns 栏组贯穿", (rx - lx) >= cw * cp["span_ratio_min"] - eps,
                f"栏组跨 {rx - lx:.3f}（版心宽 {cw:.3f} 须 ≥ "
                f"{cp['span_ratio_min']:.2f}×）")
    if variant == "arrow":
        arrows = [ln for ln in rep.ir["lines"] if ln["id"].startswith("col_arrow")]
        rep.add("S", "columns 箭头在场", len(arrows) >= 1,
                f"栏间箭头 {len(arrows)} 条（arrow 变体）")


def _s_intent_kpis(rep, p):
    """kpis 断言（内容页结构生成样板 3）：必需构件（kpi_title/kpi_card*）+
    指标等宽 + 行贯穿 + 数值字号 > 标签字号×比（尺度对比）。"""
    eps = p["verify"]["eps"]
    kp = p["page_intent"]["kpis"]
    elems = {e["id"]: e for e in rep.ir["elements"]}
    sw = rep.ir["slide"][0]
    ml = float(rep.ir["margin"].get("l", 0.5))
    mr = float(rep.ir["margin"].get("r", 0.5))
    cw = sw - ml - mr
    cards = [e for k, e in elems.items() if k.startswith("kpi_card")]
    rep.add("S", "页型 kpis 必需 kpi_title", "kpi_title" in elems)
    rep.add("S", "页型 kpis 必需 kpi_card0", "kpi_card0" in elems)
    if cards:
        ws = [e["rect"][2] for e in cards]
        rep.add("S", "kpis 指标等宽", max(ws) - min(ws) <= eps,
                f"卡宽 {min(ws):.3f}~{max(ws):.3f}")
        lx = min(e["rect"][0] for e in cards)
        rx = max(e["rect"][0] + e["rect"][2] for e in cards)
        rep.add("S", "kpis 行贯穿", (rx - lx) >= cw * kp["span_ratio_min"] - eps,
                f"指标行跨 {rx - lx:.3f}（版心宽 {cw:.3f} 须 ≥ "
                f"{kp['span_ratio_min']:.2f}×）")
    v0 = elems.get("kpi_val0")
    l0 = elems.get("kpi_lab0")
    if v0 and l0 and "text_layout" in v0 and "text_layout" in l0:
        vf, lf = v0["text_layout"]["fs"], l0["text_layout"]["fs"]
        rep.add("S", "kpis 数值层级", vf >= lf * kp["value_ratio_min"] - eps,
                f"数值 fs {vf} ≥ 标签 fs {lf}×{kp['value_ratio_min']}（尺度对比）")


def _s_intent_cards(rep, p):
    """cards 断言（内容页结构生成样板 4）：必需构件（crd_title/crd_card*）+
    网格贯穿 + 卡片等宽 + 顶饰在场（图标/编号）。"""
    eps = p["verify"]["eps"]
    cp = p["page_intent"]["cards"]
    elems = {e["id"]: e for e in rep.ir["elements"]}
    sw = rep.ir["slide"][0]
    ml = float(rep.ir["margin"].get("l", 0.5))
    mr = float(rep.ir["margin"].get("r", 0.5))
    cw = sw - ml - mr
    cards = [e for k, e in elems.items() if k.startswith("crd_card")]
    badges = [k for k in elems if k.startswith("crd_badge")]
    rep.add("S", "页型 cards 必需 crd_title", "crd_title" in elems)
    rep.add("S", "页型 cards 必需 crd_card0", "crd_card0" in elems)
    rep.add("S", "cards 顶饰在场", len(badges) >= 1, f"顶饰 {len(badges)} 个")
    if cards:
        lx = min(e["rect"][0] for e in cards)
        rx = max(e["rect"][0] + e["rect"][2] for e in cards)
        rep.add("S", "cards 网格贯穿", (rx - lx) >= cw * cp["grid_span_ratio_min"] - eps,
                f"网格跨 {rx - lx:.3f}（版心宽 {cw:.3f} 须 ≥ "
                f"{cp['grid_span_ratio_min']:.2f}×）")
        ws = [e["rect"][2] for e in cards]
        rep.add("S", "cards 卡片等宽", max(ws) - min(ws) <= eps,
                f"卡片宽 {min(ws):.3f}~{max(ws):.3f}")


def _s_intent_figure_text(rep, p):
    """figure_text 断言（内容页结构生成样板 5）：必需构件（fgt_title/fgt_fig/
    fgt_body）+ 图文分栏（左右不重叠）+ 破格占比（图侧宽 ≥ 版心×比）。"""
    eps = p["verify"]["eps"]
    fp = p["page_intent"]["figure_text"]
    elems = {e["id"]: e for e in rep.ir["elements"]}
    sw = rep.ir["slide"][0]
    ml = float(rep.ir["margin"].get("l", 0.5))
    mr = float(rep.ir["margin"].get("r", 0.5))
    cw = sw - ml - mr
    for need in ("fgt_title", "fgt_fig", "fgt_body"):
        rep.add("S", f"页型 figure_text 必需 {need}", need in elems)
    fig = elems.get("fgt_fig")
    body = elems.get("fgt_body")
    if fig and body:
        fr = fig["rect"]
        br = body["rect"]
        disjoint = (fr[0] + fr[2] <= br[0] + eps) or (br[0] + br[2] <= fr[0] + eps)
        rep.add("S", "figure_text 图文分栏", disjoint,
                f"图右缘 {fr[0] + fr[2]:.3f} / 文左缘 {br[0]:.3f}（须不重叠）")
        rep.add("S", "figure_text 破格占比", fr[2] >= cw * fp["fig_ratio_min"] - eps,
                f"图宽 {fr[2]:.3f}（版心宽 {cw:.3f} 须 ≥ {fp['fig_ratio_min']:.2f}×）")


# 页型断言注册表（数据驱动派发；键 ⊆ capabilities.PAGE_INTENTS_IMPLEMENTED）。
# 每项签名 (rep, p)；扩展新页型只加一项 + _s_intent_<name>，不再改 _s_page_intent。
_INTENT_CHECKS = {
    "cover": _s_intent_cover,
    "section": _s_intent_section,
    "problem": _s_intent_problem,
    "versus": _s_intent_versus,
    "route": _s_intent_route,
    "panels": _s_intent_panels,
    "columns": _s_intent_columns,
    "kpis": _s_intent_kpis,
    "cards": _s_intent_cards,
    "figure_text": _s_intent_figure_text,
}

_TITLE_IDS = ("title", "cov_title", "sec_title")


def _cjk_units(s):
    """版面字数：CJK 字符计 1；纯西文按 2 字符计 1（标题宽泛化度量）。"""
    if not s:
        return 0
    cjk = sum(1 for ch in s if "\u4e00" <= ch <= "\u9fff")
    if cjk:
        return cjk
    return (len(s.strip()) + 1) // 2


def _s_typography(rep, p):
    """S10 排版规范（逐页；A2/A3 量化设计规范内化）。

    强调密度：[[强调]] run 总数 ≤ max_emphasis（标记丰富但重点不泛滥）；
    标题字数：标题元素（title/cov_title/sec_title）≤ max_title_cjk；
    正文密度：非标题文本 CJK 字数 ∈ [body_chars_min, body_chars_max]；
    标题字号：text_layout.fs ≥ title_fs_min（0 = 关闭，短标题页面可豁免）。
    """
    cfg = p["verify"]["typography"]
    els = rep.ir["elements"]
    n_emph = 0
    for e in els:
        for seg in e.get("runs") or []:
            if seg.get("emph"):
                n_emph += 1
        for row in e.get("cell_runs") or []:
            for rr in row:
                for seg in rr or []:
                    if seg.get("emph"):
                        n_emph += 1
    lim = cfg.get("max_emphasis") or 0
    if lim:
        rep.add("S", "每页强调 ≤ 上限", n_emph <= lim,
                f"{n_emph} 处 [[强调]]（上限 {lim}）——重点过多则弱化提示")
    for e in els:
        if e["id"] not in _TITLE_IDS:
            continue
        n = _cjk_units(e.get("text"))
        cap = cfg.get("max_title_cjk") or 0
        if cap:
            rep.add("S", f"标题字数 {e['id']}", n <= cap,
                    f"{n} 字（上限 {cap}）——标题宜短，长句移入副标题/正文")
        floor = cfg.get("title_fs_min") or 0
        if floor:
            fs = (e.get("text_layout") or {}).get("fs")
            if fs is not None:
                rep.add("S", f"标题字号 {e['id']}", fs >= floor - 1e-9,
                        f"fs={fs}pt（下限 {floor}pt）")
    body = sum(_cjk_units(e.get("text")) for e in els
               if e.get("text") and e["id"] not in _TITLE_IDS)
    hi = cfg.get("body_chars_max") or 0
    if hi:
        rep.add("S", "正文字数 ≤ 上限", body <= hi,
                f"{body} 字（上限 {hi}）——单页信息过载，宜拆分")
    lo = cfg.get("body_chars_min") or 0
    if lo and els:
        rep.add("S", "正文字数 ≥ 下限", body >= lo,
                f"{body} 字（下限 {lo}）——内容过空" if body else "")


def _s_family(rep, rules, p, sv):
    ir, compiled = rep.ir, rep.compiled
    elems = {e["id"]: e for e in ir["elements"]}
    ts = rules.get("type_scale") or {}
    eps = p["verify"]["eps"]
    # 小字角色豁免词（S1b/S8 共用）：图形标签 lab、图注 caption/note、单位 units、
    # 页脚 foot/hdr/ftr、封面 meta —— 独立于"尺寸"语义的角色豁免
    _SMALL_ROLES = ("lab", "caption", "note", "units", "foot", "hdr", "ftr", "meta")

    # S1 字号层级：graph 节点(→node)、边标签(→edge_label，flowchart)
    role_fs = {"node": "edge_label"}
    if "node" in ts:
        for e in ir["elements"]:
            # text_layout 守卫：只查有文本布局的形状（graph 节点）；cylinder
            # 展开部件（侧壁/椭圆无文本）不经此——无 text_layout 会 KeyError
            if e.get("type") == "shape" and e.get("owner") and "node" in ts \
                    and "text_layout" in e:
                lo, hi = ts["node"]
                rep.add("S", f"节点字号 {e['id']} ∈ type_scale.node",
                        lo <= e["text_layout"]["fs"] <= hi,
                        f"fs={e['text_layout']['fs']} 规范[{lo},{hi}]")
    if "edge_label" in ts:
        for e in ir["elements"]:
            if e["id"].endswith(".label") and "text" in e:
                lo, hi = ts["edge_label"]
                rep.add("S", f"标签字号 {e['id']} ∈ type_scale.edge_label",
                        lo <= e["text_layout"]["fs"] <= hi,
                        f"fs={e['text_layout']['fs']} 规范[{lo},{hi}]")

    # S1b 正文下限（deck 等）：type_scale.body 下限消费——普通文本/卡片文本
    #（无 owner 的独立 text/shape）须 ≥ body[0]；小字角色（图形标签 lab、
    # 图注 caption/note、单位 units、页脚 foot/hdr/ftr、封面 meta 等）靠 id
    # 豁免词跳过；容器部件（graph 节点/cylinder 展开）有 owner 不经此。
    # 校对经验：正文 13–14pt 后排不可读 → references/copyediting.md §字号分层。
    if "body" in ts:
        small = _SMALL_ROLES
        for e in ir["elements"]:
            if e.get("type") not in ("text", "shape") or "text_layout" not in e:
                continue
            if e.get("owner"):            # graph 节点/cylinder 等容器部件
                continue
            if any(k in e["id"] for k in small):   # 小字角色豁免
                continue
            # 作者降准通道：meta.params.style.body_fs_min 显式覆盖 styleguide 下限
            #（功能演示/密集表格有意用小字；None = 遵守规范下限）
            lo = (p.get("style") or {}).get("body_fs_min") or ts["body"][0]
            rep.add("S", f"正文字号 {e['id']} ≥ {lo}",
                    e["text_layout"]["fs"] >= lo,
                    f"fs={e['text_layout']['fs']} 规范≥{lo}")

    # S8 小尺寸字号下限（size_fs_floor，scansci「复杂度预算/识别性优先」内化）：
    # 元素 rect 短边 < threshold(in) 时 fs ≥ floor——"缩小后保留辨识特征"转为
    # 可断言规则（区别于 min_fs 硬底：本规则按尺寸生效）。豁免：容器部件（owner）
    # 与 S1b 小字角色同律。
    sff = rules.get("size_fs_floor")
    if sff:
        # rect 单位为英寸（IR 几何，与 spacing 规范同律）；阈值参数化 in
        thr_in = float(sff.get("threshold", 1.0))
        floor = sff.get("fs", 12)
        for e in ir["elements"]:
            if e.get("type") not in ("text", "shape") or "text_layout" not in e:
                continue
            if e.get("owner"):
                continue
            if any(k in e["id"] for k in _SMALL_ROLES):
                continue
            r = e["rect"]
            short_in = min(float(r[2]), float(r[3]))
            if short_in < thr_in:
                rep.add("S", f"小尺寸字号 {e['id']} ≥ {floor}",
                        e["text_layout"]["fs"] >= floor,
                        f"rect短边={short_in:.2f}in fs={e['text_layout']['fs']} 规范≥{floor}")

    # S9 标签组织（labels_follow，scansci「标签随部件 vs 图例独立」内化）：
    # .label 后缀文本须与其目标同 owner 或同 edit_group——graph 边/组标签有
    # owner（容器组织）天然满足；约束自由（顶层）标签与顶层目标的组织。
    lf = rules.get("labels_follow")
    if lf:
        eg_members = set()
        for g in (ir.get("edit_groups") or []):
            eg_members.update(g.get("members") or [])
        for e in ir["elements"]:
            if not (e["id"].endswith(".label") and "text" in e):
                continue
            if e.get("owner"):
                continue                     # 容器派生的标签：已随部件组织
            target = elems.get(e["id"][:-len(".label")])
            if target is None or target.get("owner"):
                continue                     # 目标不可比/目标在容器内：无约束
            ok = e["id"] in eg_members and target["id"] in eg_members
            if not ok:
                rep.add("S", f"标签组织 {e['id']}", False,
                        f"目标 {target['id']} 与标签须同 edit_group（同部件组织）"
                        if not eg_members else
                        f"目标 {target['id']} 与标签须同 edit_group")

    # S2 配色上限 + palette 白名单（fill 非默认即计一色）
    fills = set()
    for e in ir["elements"]:
        st = e.get("style") or {}
        fill = st.get("fill")
        if isinstance(fill, dict):  # grad
            fills.add(tuple(sorted(str(c) for c in fill.get("grad", []))))
        elif isinstance(fill, str):
            fills.add(fill)
    fills.discard(None)
    cmax = rules.get("color_max")
    if cmax:
        rep.add("S", f"语义色 ≤ {cmax}", len(fills) <= cmax,
                f"colors={sorted(map(str, fills))}")
    pal = rules.get("palette")
    if pal:
        bad = {c for c in fills if isinstance(c, str) and c not in pal}
        rep.add("S", "配色 ⊆ 白名单", not bad, f"越界={sorted(bad)}")

    # S3 构件必含（ladder 等要求 title/steps 存在）—— 源在 compiled（IR 已扁平化，容器消失）。
    # 引擎展开的页型（cover/section/…）豁免"内容页 title"构件语义：其标题由引擎
    # 合成（cov_title/sec_title 等）；仅 content/无意图页要求显式 title。
    if ir.get("page_intent") in (None, "content"):
        for need in (rules.get("components_required") or []):
            found = False
            if need == "title":
                found = any(e["id"] == "title" and e["type"] == "text"
                            for e in compiled["elements"])
            elif need == "steps":
                found = any(e["type"] == "stack" and e.get("children")
                            for e in compiled["elements"])
            else:
                found = need in {e["id"] for e in compiled["elements"]}
            rep.add("S", f"必需构件 {need}", found)

    # S4 梯形宽度单调（ladder width_monotonic）—— 读 source children 声明宽
    if rules.get("width_monotonic"):
        for e in compiled["elements"]:
            if e["type"] != "stack":
                continue
            ws = [float(c["width"]) for c in e.get("children", [])
                  if isinstance(c.get("width"), (int, float))]
            monot = all(ws[i] > ws[i + 1] for i in range(len(ws) - 1)) if len(ws) > 1 else True
            rep.add("S", f"梯形宽度严格递减[{e['id']}]", monot, f"w={ws}")

    # S5 栈/坞账目：children 总尺寸 ≤ 容器尺寸（compiled 源 + 绝对 rect）
    # orientation 决定账目轴：vertical 按高度（% 相对容器高），horizontal 按宽度（% 相对容器宽）
    for e in compiled["elements"]:
        if e["type"] == "stack":
            gap = e.get("gap", 0.0)
            kids = e.get("children", [])
            horiz = e.get("orientation") == "horizontal"
            cap = e["rect"][2] if horiz else e["rect"][3]
            dims = []
            for c in kids:
                raw = c.get("width" if horiz else "height", "100%")
                if isinstance(raw, str) and raw.endswith("%"):
                    dims.append(float(raw.rstrip("%")) / 100.0 * cap)
                elif isinstance(raw, (int, float)) and not isinstance(raw, bool):
                    dims.append(float(raw))
                else:
                    dims.append(cap)
            total = sum(dims) + gap * max(0, len(kids) - 1)
            axis = "宽" if horiz else "高"
            rep.add("S", f"stack 账目[{e['id']}]", total <= cap + eps,
                    f"total={total:.3f} vs 容器{axis} {cap:.3f}")
        elif e["type"] == "dock":
            kids = e.get("children", [])
            pads = e.get("padding", {})
            avail_t = e["rect"][3] - pads.get("t", 0) - pads.get("b", 0)
            avail_w = e["rect"][2] - pads.get("l", 0) - pads.get("r", 0)
            # 简单账目：所有 dock=top/bottom 高度和 ≤ 可用高；left/right 宽度和 ≤ 可用宽
            v = sum(float(k.get("height", 1.0)) + k.get("margin", {}).get("t", 0) +
                    k.get("margin", {}).get("b", 0)
                    for k in kids if k.get("dock") in ("top", "bottom"))
            h_ = sum(float(k.get("width", 2.0)) + k.get("margin", {}).get("l", 0) +
                     k.get("margin", {}).get("r", 0)
                     for k in kids if k.get("dock") in ("left", "right"))
            rep.add("S", f"dock 账目[{e['id']}]", v <= avail_t + eps and h_ <= avail_w + eps,
                    f"v={v:.3f}/{avail_t:.3f} h={h_:.3f}/{avail_w:.3f}")


def check_graph_dedup(pages):
    """C 契约（跨页去重，多页模式）：复杂图（节点数 ≥ branch_min_nodes 阈值，
    styleguides.flowchart.semantics 单一事实源）拓扑签名相同 → 同质化违规。

    签名 = graph_sig 拓扑签名（节点数 + kind 直方图 + 出/入度直方图 + 最长链，
    与 id/文案无关——换文案同拓扑仍判重复）。简单图不参与（简单流程重复是
    合法用例，阈值分级化解误杀）；显式 linear: true 的图是授权线性流程，
    不判。返回 [(page_idx, 本页图id, 前页idx, 前页图id, detail)]，
    由 build_ppt 注入对应页 Report（attribution advisory：改拓扑或主题）。"""
    import graph_sig as GS
    import styleguides as _SG
    sem = (_SG.RULE_SETS.get("flowchart") or {}).get("semantics") or {}
    bmin = int(sem.get("branch_min_nodes", 5))
    seen = {}
    hits = []
    for pi, page in enumerate(pages):
        for e in page.get("elements") or []:
            if e.get("type") != "graph" or e.get("linear"):
                continue
            if (e.get("orientation") or "horizontal") == "vertical":
                continue
            f = GS.graph_features(e)
            if f["n_nodes"] < bmin:
                continue
            sig = f["topo_sig"]
            if sig in seen:
                pi0, gid0, n0 = seen[sig]
                hits.append((pi, e["id"], pi0, gid0,
                             f"拓扑同构（{f['n_nodes']} 节点）：页 {pi + 1} 图 "
                             f"{e['id']} 与页 {pi0 + 1} 图 {gid0} 结构相同"
                             f"（换文案不改签名）——多页同质化，请改拓扑或主题"))
            else:
                seen[sig] = (pi, e["id"], f["n_nodes"])
    return hits


def _layout_unit(e, sw, sh, cfg):
    """单个视觉主体 → 版式签名分量：网格落位 + 尺寸档 + 类型/子类。
    小尺寸装饰（面积占比 < min_area_ratio 或短边 < 0.25in）不参与。"""
    rect = e.get("rect")
    if not rect or len(rect) != 4:
        return None
    x, y, w, h = [float(v) for v in rect]
    if w <= 0 or h <= 0 or w < 0.25 or h < 0.25:
        return None
    area = (w * h) / (sw * sh) if sw > 0 and sh > 0 else 0
    if area < cfg["min_area_ratio"]:
        return None
    ncol, nrow = cfg["grid"]
    col = min(ncol - 1, max(0, int((x + w / 2.0) / sw * ncol)))
    row = min(nrow - 1, max(0, int((y + h / 2.0) / sh * nrow)))
    size = "S" if area < 0.08 else ("M" if area < 0.20 else "L")
    t = e.get("type")
    if t == "shape":
        sub = "shape:" + str(e.get("kind") or "rounded_rect")
    elif t == "chart":
        sub = "chart:" + str(e.get("chart_type"))
    elif t == "graph":
        sub = (f"graph:{e.get('orientation') or 'horizontal'}:"
               f"{len(e.get('nodes') or [])}")
    elif t in ("stack", "dock"):
        sub = f"{t}:{len(e.get('children') or [])}"
    elif t == "table":
        rows = len(e.get("data") or [])
        cols = len((e.get("data") or [[]])[0])
        sub = f"table:{rows}x{cols}"
    elif t == "text":
        sub = "text:" + str((e.get("text_style") or {}).get("align", "center"))
    else:
        sub = str(t)
    return (col, row, size, sub)


def _layout_page_sig(page, cfg, slide_dims):
    """页版式签名。页型意图页以 **(intent, 变体)** 为签名参与统计——变体家族让同
    intent 页本就不该逐页相同（轮换），因此不再豁免；同 intent 同变体重复仍受限
    （堵"豁免盲区"：过去 3 个 section 页像素级相同却无人拦）。"""
    meta = page.get("meta") or {}
    intent = meta.get("page_intent")
    if intent:
        import intents as IN
        decl = meta.get(intent) or {}
        return (("intent", intent, IN.resolve(intent, decl.get("variant"))),)
    sl = meta.get("slide") or {}
    sw = float(sl.get("w", slide_dims[0]))
    sh = float(sl.get("h", slide_dims[1]))
    units = []
    for e in page.get("elements") or []:
        if e.get("id") in _TITLE_IDS or e.get("type") == "line":
            continue
        u = _layout_unit(e, sw, sh, cfg)
        if u is not None:
            units.append(u)
    return tuple(sorted(units))


def check_layout_variety(pages, p):
    """A1 版式多样性断言（多页序列）：内容页的视觉结构签名不得高度同质。

    签名 = 非标题视觉主体的 (网格落位, 尺寸档, 类型/子类) 排序元组——换文案
    不改签名；只换配色也不改。内容页数 < min_pages 不判（少页天然少重复）。
    返回 [(page_idx, name, detail)]，由 build_ppt 注入对应页 Report（attribution
    advisory：重排版式或合并内容）。"""
    cfg = p["verify"]["layout_variety"]
    if not cfg.get("enabled"):
        return []
    slide_dims = (float(p["slide"]["w"]), float(p["slide"]["h"]))
    sigs = []
    for pi, page in enumerate(pages):
        sig = _layout_page_sig(page, cfg, slide_dims)
        if sig is not None:
            sigs.append((pi, sig))
    n = len(sigs)
    if n < int(cfg["min_pages"]):
        return []
    counts = {}
    for _, sig in sigs:
        counts[sig] = counts.get(sig, 0) + 1
    distinct = len(counts)
    need = max(int(cfg["min_distinct"]),
               int(math.ceil(n * float(cfg["distinct_ratio"]))))
    hits = []
    if distinct < need:
        hits.append((sigs[-1][0], "版式多样性",
                     f"版式多样性 {distinct}/{n} < 要求 {need}——多页画面同质，"
                     "请更换版式骨架（左右分栏/上下分区/图文混排交替）"))
    seen = {}
    for pi, sig in sigs:
        seen[sig] = seen.get(sig, 0) + 1
        if seen[sig] > int(cfg["max_same"]):
            hits.append((pi, "版式同质",
                         f"版式同质：页 {pi + 1} 与前面 {seen[sig] - 1} 页结构相同"
                         f"（同签名最多 {cfg['max_same']} 页）"))
    return hits