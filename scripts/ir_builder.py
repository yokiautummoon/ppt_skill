# -*- coding: utf-8 -*-
"""ir_builder.py — 编译 JSON → 布局中间表示（IR）。

职责：
  1. 顶层元素 rect 直通；容器（stack/dock/graph）求解出 children rect。
  2. z 分配：声明序默认 → z_override 覆盖；容器 children 连续阶梯。
  3. owner 树：容器 children 的 owner = 容器 id（遮挡合法源二类之一）。
  4. text_layout：所有含文本元素 autofit（graph 节点复用 layout_graph 产物）。
  5. edge 端口锚点与折点：graph 边由 layout_graph 产，glue 边用 snap_anchor。

IR 结构（render 层唯一消费物）：
  slide: (w, h)；margin: dict
  elements: 扁平绘制元素 [{id,type,z,rect,owner?,kind?,text?,text_style?,style?,
                            text_layout?,overflow?,src?}]
  lines:    普通画线 [{id,z,a1,a2,pts?,label?}]（graph 内边）
  glue:     COM 绑定连线 [{id,from,to,z,a1,a2,side1,side2,label?}]
  groups:   组包络 [{id,label,bbox,z}]
  z_max:    最大 z（report/metrics 用）
"""
import alpha_math
import copy
import layout_rect as LR
import richtext as RT
import layout_stack as LS
import layout_dock as LD
import layout_graph as LG
import textmesh
import params as _P
import svg_doc

# graph 容器内部 z 类基（相对容器 z）。类序不变式：组包络 < 边 < 节点 <
# 组标签 < 边标签——节点必须严格高于边，否则越层的连线会盖住节点文字
# （2026-10-09 连线治理决策根因 2：旧步长类内=类间=10 直接相撞，边/节点交错）。
# 类基步长 1000 ≫ 类内索引步长 10（_z_of），任意边数/节点数下类序稳定。
_Z_CLASS = {"group_box": 10, "edge": 1000, "node": 2000, "group_label": 3000, "edge_label": 4000}

# cylinder 展开常量：顶/底椭圆透视高 = 宽 × 因子；等高弧条数
_CYL_ELL_FACTOR = 0.16
_CYL_CONTOUR_Y = (0.30, 0.58)


def _z_of(cz, cls, i):
    return cz + _Z_CLASS[cls] + 10 * i


def _intent_accent(ref, palette, p):
    """页型 accent（palette token 或裸 hex）→ hex；缺省用全局强调色（params.style.accent）。

    兼容两式 palette：{"acc": {"solid": "#2D6CDF"}}（模板系）与 {"acc": "#2D6CDF"}（字符串直值）。"""
    if isinstance(ref, str):
        if ref in palette:
            v = palette[ref]
            if isinstance(v, dict) and "solid" in v:
                return str(v["solid"])
            if isinstance(v, str) and (v.startswith("#") or len(v) == 6):
                return v
        if ref.startswith("#") or len(ref) == 6:
            return ref
    return p["style"]["accent"]


def _dark_page(meta):
    """深色结构页（structure=sandwich/dark 的封面/节页）：由 build_pages 写
    meta['_page_dark']。用于文字反色（深底 → 浅字）。"""
    return bool((meta or {}).get("_page_dark"))


def _page_text_color(meta, p):
    """该页常规文字色：深页取 style.text_color_dark（浅），否则常规 text_color。"""
    if _dark_page(meta):
        return p["style"].get("text_color_dark") or "#F2F2F2"
    return p["style"]["text_color"]


def _expand_cover(cover, meta, p, out, alloc, all_rects, palette):
    """cover 页型展开（破格封面变体家族——审定菜单原型 1，references/page-intents.md）：
    变体由 SPEC `cover.variant` 或 deck 级轮换选定（scripts/intents.py）：
      left  陈规破格：cov_deco 强调条（左上脊柱）+ cov_title 左置大标题（中心刻意
            偏离 slide 几何中心 = 破格点）+ cov_sub + 右下 cov_meta；
      band  横向色带贯穿：cov_deco 拉成满版心宽的色带（破格点 = 横贯），标题居上、
            副题居于带下；
      split 左纵贯色块：cov_deco 变高色块（纵贯 = 破格点），标题嵌色块内（同 owner
            令牌 → 遮挡合法），副题/落款居右侧留白。
    rect 全在此解（铁律 1：布局层唯一几何真相源）；渲染照常消费 IR 元素。"""
    import intents as IN
    variant = IN.resolve("cover", cover.get("variant"))
    sw, sh = out["slide"]
    m = out["margin"]
    ml = float(m.get("l", 0.5))
    mr = float(m.get("r", 0.5))
    mt = float(m.get("t", 0.5))
    mb = float(m.get("b", 0.5))
    cw = sw - ml - mr
    ch = sh - mt - mb
    cp = p["page_intent"]["cover"]
    acc = _intent_accent(cover.get("accent"), palette, p)
    base = 0
    OWN = "cover"    # 展开簇共用 owner 令牌（变体内叠放合法；无同名元素）
    # 深色结构页（structure=sandwich/dark）：标题/副题/落款反色（深底浅字）
    dark = _dark_page(meta)
    tc = _page_text_color(meta, p)      # 标题/落款常规色
    sub_c = tc if dark else acc          # 副题：非深页用 accent，深页改用浅字

    def put(cfg, idx, owner=None):
        el = _emit_basic(cfg["id"], cfg["type"], cfg["rect"],
                         alloc(z=base + idx + 1), owner, cfg, p)
        out["elements"].append(el)
        all_rects[cfg["id"]] = cfg["rect"]

    def _ts(style):
        """深页时给文本补显式浅色（非深页保持缺省 → 与历史 IR 字节一致）。"""
        s = dict(style)
        if dark and "color" not in s:
            s["color"] = tc
        return s

    def put_meta(idx):
        if not cover.get("meta"):
            return
        mw = cw * cp["meta_w_ratio"]
        put({"id": "cov_meta", "type": "text", "text": cover["meta"],
             "rect": (sw - mr - mw, sh - mb - cp["meta_h"], mw, cp["meta_h"]),
             "text_style": {"fs": 12, "color": tc, "align": "left"}}, idx)

    if variant == "band":
        bp = cp["band"]
        by = sh * bp["band_y_ratio"]
        put({"id": "cov_deco", "type": "shape", "kind": "rect",
             "rect": (ml, by, cw, bp["band_h"]),
             "style": {"fill": acc, "border": None, "shadow": False}}, 0)
        put({"id": "cov_title", "type": "text", "text": cover["title"],
             "rect": (ml, sh * bp["title_y_ratio"], cw * cp["title_w_ratio"],
                      bp["title_h"]),
             "text_style": _ts({"fs": 36, "bold": True, "align": "left"})}, 1)
        if cover.get("subtitle"):
            put({"id": "cov_sub", "type": "text", "text": cover["subtitle"],
                 "rect": (ml, by + bp["band_h"] + bp["sub_gap"],
                          cw * cp["sub_w_ratio"], 0.6),
                 "text_style": {"fs": 20, "align": "left", "color": sub_c}}, 2)
        put_meta(3)
    elif variant == "split":
        xp = cp["split"]
        pw = cw * xp["panel_w_ratio"]
        ph_ = ch * xp["panel_h_ratio"]
        put({"id": "cov_deco", "type": "shape", "kind": "rect",
             "rect": (ml, mt, pw, ph_),
             "style": {"fill": acc, "border": None, "shadow": False}},
            0, owner=OWN)
        put({"id": "cov_title", "type": "text", "text": cover["title"],
             "rect": (ml + xp["pad"], mt + ph_ * xp["title_y_ratio"],
                      pw - 2 * xp["pad"], xp["title_h"]),
             "text_style": _ts({"fs": 34, "bold": True, "align": "left"})},
            1, owner=OWN)
        if cover.get("subtitle"):
            put({"id": "cov_sub", "type": "text", "text": cover["subtitle"],
                 "rect": (ml + pw + xp["sub_x_gap"], mt + ch * xp["sub_y_ratio"],
                          cw * cp["sub_w_ratio"], 0.6),
                 "text_style": {"fs": 20, "align": "left", "color": sub_c}}, 2)
        put_meta(3)
    else:   # left —— 家族首变体（历史几何，向后兼容）
        put({"id": "cov_deco", "type": "shape", "kind": "rect",
             "rect": (ml, sh * cp["deco_y_ratio"], cw * cp["deco_w_ratio"],
                      cp["deco_h"]),
             "style": {"fill": acc, "border": None, "shadow": False}}, 0)
        put({"id": "cov_title", "type": "text", "text": cover["title"],
             "rect": (ml, sh * cp["title_y_ratio"], cw * cp["title_w_ratio"],
                      cp["title_h"]),
             "text_style": _ts({"fs": 36, "bold": True, "align": "left"})}, 1)
        ty = sh * cp["title_y_ratio"] + cp["title_h"]
        if cover.get("subtitle"):
            put({"id": "cov_sub", "type": "text", "text": cover["subtitle"],
                 "rect": (ml, ty + cp["sub_gap"], cw * cp["sub_w_ratio"], 0.6),
                 "text_style": {"fs": 20, "align": "left", "color": sub_c}}, 2)
        put_meta(3)
    out["page_intent"] = "cover"
    out["page_intent_variant"] = variant


def _expand_section(sec, meta, p, out, alloc, all_rects, palette):
    """section 页型展开（破格节标题变体家族——页型原型 2，references/page-intents.md）：
    变体由 SPEC `section.variant` 或 deck 级轮换选定（scripts/intents.py）：
      num_left   大数字左上纵贯 + 右缘竖条（左右双锚）+ 引导线 + 节名；
      num_giant  巨型序号贴右下（右缘对齐 = 破格点）+ 节名/引导线居左上；
      band       序号与节名同嵌一条横贯色带（横贯 = 破格点，同 owner 令牌）；
    三者同律：序号字号 > 节名字号（数字是节页主导视觉），verify 按变体断言。
    rect 全在此解（铁律 1）；渲染照常消费 IR 元素。"""
    import intents as IN
    variant = IN.resolve("section", sec.get("variant"))
    sw, sh = out["slide"]
    m = out["margin"]
    ml = float(m.get("l", 0.5))
    mr = float(m.get("r", 0.5))
    mt = float(m.get("t", 0.5))
    mb = float(m.get("b", 0.5))
    cw = sw - ml - mr
    ch = sh - mt - mb
    sp = p["page_intent"]["section"]
    acc = _intent_accent(sec.get("accent"), palette, p)
    dark = _dark_page(meta)
    tc = _page_text_color(meta, p)
    base = 0
    OWN = "section"  # 展开簇共用 owner 令牌（band 变体内叠放合法；无同名元素）

    def put(cfg, idx, owner=None):
        el = _emit_basic(cfg["id"], cfg["type"], cfg["rect"],
                         alloc(z=base + idx + 1), owner, cfg, p)
        out["elements"].append(el)
        all_rects[cfg["id"]] = cfg["rect"]

    def _ts(style):
        """深页时给节页文本补显式浅色（非深页保持缺省/原值 → 历史 IR 字节一致）。"""
        s = dict(style)
        if dark and "color" not in s:
            s["color"] = tc
        return s

    if variant == "num_giant":
        gp = sp["num_giant"]
        put({"id": "sec_num", "type": "text", "text": sec["num"],
             "rect": (sw - mr - cw * gp["num_w_ratio"],
                      mt + ch * gp["num_y_ratio"],
                      cw * gp["num_w_ratio"], ch * gp["num_h_ratio"]),
             "text_style": {"fs": gp["num_fs"], "bold": True, "align": "right",
                            "color": tc}}, 1)
        put({"id": "sec_guide", "type": "shape", "kind": "rect",
             "rect": (ml, mt + ch * gp["guide_y_ratio"],
                      cw * sp["guide_w_ratio"], sp["guide_h"]),
             "style": {"fill": acc, "border": None, "shadow": False}}, 2)
        put({"id": "sec_title", "type": "text", "text": sec["title"],
             "rect": (ml, mt + ch * gp["title_y_ratio"],
                      cw * sp["title_w_ratio"], gp["title_h"]),
             "text_style": _ts({"fs": sp["title_fs"], "bold": True,
                                "align": "left"})}, 3)
    elif variant == "band":
        bp = sp["band"]
        by = mt + ch * bp["band_y_ratio"]
        bh = ch * bp["band_h_ratio"]
        put({"id": "sec_deco", "type": "shape", "kind": "rect",
             "rect": (ml, by, cw, bh),
             "style": {"fill": acc, "border": None, "shadow": False}},
            0, owner=OWN)
        put({"id": "sec_num", "type": "text", "text": sec["num"],
             "rect": (ml + bp["pad"], by + bh * 0.10,
                      cw * bp["num_w_ratio"], bh * 0.80),
             "text_style": {"fs": bp["num_fs"], "bold": True, "align": "left"}},
            1, owner=OWN)
        put({"id": "sec_title", "type": "text", "text": sec["title"],
             "rect": (ml + cw * bp["title_x_ratio"], by + bh * 0.22,
                      cw * bp["title_w_ratio"], bh * 0.56),
             "text_style": {"fs": sp["title_fs"], "bold": True,
                            "align": "left"}}, 3, owner=OWN)
    else:   # num_left —— 家族首变体（历史几何，向后兼容）
        put({"id": "sec_deco", "type": "shape",
             "kind": "rect",
             "rect": (sw - mr - sp["deco_w"], mt + ch * sp["deco_y_ratio"],
                      sp["deco_w"], ch * sp["deco_h_ratio"]),
             "style": {"fill": acc, "border": None, "shadow": False}}, 0)
        put({"id": "sec_num", "type": "text", "text": sec["num"],
             "rect": (ml, mt + ch * sp["num_y_ratio"], cw * sp["num_w_ratio"],
                      ch * sp["num_h_ratio"]),
             "text_style": {"fs": sp["num_fs"], "bold": True, "align": "left",
                            "color": tc}}, 1)
        put({"id": "sec_guide", "type": "shape", "kind": "rect",
             "rect": (ml, mt + ch * sp["guide_y_ratio"], cw * sp["guide_w_ratio"],
                      sp["guide_h"]),
             "style": {"fill": acc, "border": None, "shadow": False}}, 2)
        put({"id": "sec_title", "type": "text", "text": sec["title"],
             "rect": (ml, mt + ch * sp["title_y_ratio"], cw * sp["title_w_ratio"],
                      sp["title_h"]),
             "text_style": _ts({"fs": sp["title_fs"], "bold": True,
                                "align": "left"})}, 3)
    out["page_intent"] = "section"
    out["page_intent_variant"] = variant


def _expand_problem(prb, meta, p, out, alloc, all_rects, palette):
    """problem 页型展开（科研问题陈述页——科研三件套 1，references/page-intents.md
    §8）：prb_badge 左上大号 accent 问题标记（纵向贯穿版心 = 破格点 1，宽扁标记块
    内嵌 "?"）→ prb_title 主问题（左对齐、非居中 = 破格点 2）→ prb_items 编号子问题
    清单（声明 items 才展开）。rect 全在此解（铁律 1）。"""
    sw, sh = out["slide"]
    m = out["margin"]
    ml = float(m.get("l", 0.5))
    mr = float(m.get("r", 0.5))
    mt = float(m.get("t", 0.5))
    mb = float(m.get("b", 0.5))
    cw = sw - ml - mr
    ch = sh - mt - mb
    pp = p["page_intent"]["problem"]
    acc = _intent_accent(prb.get("accent"), palette, p)
    base = 0

    def put(cfg, idx):
        el = _emit_basic(cfg["id"], cfg["type"], cfg["rect"],
                         alloc(z=base + idx + 1), None, cfg, p)
        out["elements"].append(el)
        all_rects[cfg["id"]] = cfg["rect"]

    put({"id": "prb_badge", "type": "shape", "kind": "rect",
         "rect": (ml, mt + ch * pp["badge_y_ratio"], pp["badge_w"],
                  ch * pp["badge_h_ratio"]),
         "style": {"fill": acc, "border": None, "shadow": False},
         "text": "?", "text_style": {"fs": pp["badge_fs"], "bold": True,
                                     "align": "center", "color": "#FFFFFF"}}, 0)
    put({"id": "prb_title", "type": "text", "text": prb["title"],
         "rect": (ml + pp["badge_w"] + pp["title_x_gap"],
                  mt + ch * pp["title_y_ratio"],
                  cw - pp["badge_w"] - pp["title_x_gap"], pp["title_h"]),
         "text_style": {"fs": pp["title_fs"], "bold": True, "align": "left"}}, 1)
    items = prb.get("items") or []
    if items:
        body = "\n".join(f"{i + 1}. {s}" for i, s in enumerate(items))
        put({"id": "prb_items", "type": "text", "text": body,
             "rect": (ml, mt + ch * pp["items_y_ratio"],
                      cw * pp["items_w_ratio"], pp["items_h"]),
             "text_style": {"fs": pp["items_fs"], "align": "left"}}, 2)
    out["page_intent"] = "problem"
    out["page_intent_variant"] = "badge"


def _expand_versus(vs, meta, p, out, alloc, all_rects, palette):
    """versus 页型展开（科研对照页——科研三件套 2）：vsv_panel_l/r 左右分色面板
    （对立着色 = 破格点 1）→ vsv_title_l/r 栏题（accent）→ vsv_body_l/r 栏体清单
    → vsv_divider 中缝分割线 + vsv_tag "VS" 标（居中对称锚）。rect 全在此解（铁律 1）。
    两栏等宽 → verify 均衡断言背书。"""
    sw, sh = out["slide"]
    m = out["margin"]
    ml = float(m.get("l", 0.5))
    mr = float(m.get("r", 0.5))
    mt = float(m.get("t", 0.5))
    mb = float(m.get("b", 0.5))
    cw = sw - ml - mr
    ch = sh - mt - mb
    vp = p["page_intent"]["versus"]
    acc = _intent_accent(vs.get("accent"), palette, p)
    fill_l = p["style"]["fill"]
    fill_r = p["style"]["group_fill"]
    base = 0
    OWN = "versus"   # 展开簇共用 owner 令牌（无同名元素 → G4 同 owner / D1 跳过）

    def put(cfg, idx, owner=None):
        el = _emit_basic(cfg["id"], cfg["type"], cfg["rect"],
                         alloc(z=base + idx + 1), owner, cfg, p)
        out["elements"].append(el)
        all_rects[cfg["id"]] = cfg["rect"]

    col_w = (cw - vp["gap"]) / 2.0
    py = mt + ch * vp["panel_y_ratio"]
    ph_ = ch * vp["panel_h_ratio"]
    lx = ml
    rx = ml + col_w + vp["gap"]
    pad = vp["col_pad"]
    body_y = py + pad + vp["title_h"] + 0.12
    body_h = ph_ - pad * 2 - vp["title_h"] - 0.12
    for pid, px, fill in (("vsv_panel_l", lx, fill_l), ("vsv_panel_r", rx, fill_r)):
        put({"id": pid, "type": "shape", "kind": "rounded_rect",
             "rect": (px, py, col_w, ph_),
             "style": {"fill": fill, "border": p["style"]["border"],
                       "shadow": p["style"]["shadow"]}}, 0, owner=OWN)
    # 面板为背景层：栏内文本/标记与面板同挂 owner 令牌（见上）
    for tid, px, key in (("vsv_title_l", lx, "left_title"),
                         ("vsv_title_r", rx, "right_title")):
        put({"id": tid, "type": "text", "text": vs[key],
             "rect": (px + pad, py + pad, col_w - 2 * pad, vp["title_h"]),
             "text_style": {"fs": vp["title_fs"], "bold": True, "align": "left",
                            "color": acc}}, 1, owner=OWN)
    for bid, px, key in (("vsv_body_l", lx, "left_items"),
                         ("vsv_body_r", rx, "right_items")):
        items = vs.get(key) or []
        if not items:
            continue
        body = "\n".join(f"· {s}" for s in items)
        put({"id": bid, "type": "text", "text": body,
             "rect": (px + pad, body_y, col_w - 2 * pad, body_h),
             "text_style": {"fs": vp["body_fs"], "align": "left"}}, 2, owner=OWN)
    cx = ml + col_w + vp["gap"] / 2.0
    put({"id": "vsv_divider", "type": "shape", "kind": "rect",
         "rect": (cx - vp["divider_w"] / 2.0, py, vp["divider_w"], ph_),
         "style": {"fill": acc, "border": None, "shadow": False}}, 3, owner=OWN)
    put({"id": "vsv_tag", "type": "shape", "kind": "oval",
         "rect": (cx - vp["tag_w"] / 2.0, py + ph_ / 2.0 - vp["tag_h"] / 2.0,
                  vp["tag_w"], vp["tag_h"]),
         "style": {"fill": acc, "border": None, "shadow": p["style"]["shadow"]},
         "text": vs.get("vs") or "VS",
         "text_style": {"fs": vp["tag_fs"], "bold": True, "align": "center",
                        "color": "#FFFFFF"}}, 4, owner=OWN)
    out["page_intent"] = "versus"
    out["page_intent_variant"] = "split"


def _expand_route(rte, meta, p, out, alloc, all_rects, palette):
    """route 页型展开（科研技术路线页——科研三件套 3）：rte_title 可选页题 →
    rte_stage1..N 横向等距 hexagon 阶段条（数量 = len(stages)，逐阶段文本）+
    rte_lnk* 阶段间箭头连线。阶段链横向铺满版心、等步距推进（verify 断言背书：
    等距 + 横向贯穿）。rect 全在此解（铁律 1）。"""
    sw, sh = out["slide"]
    m = out["margin"]
    ml = float(m.get("l", 0.5))
    mr = float(m.get("r", 0.5))
    mt = float(m.get("t", 0.5))
    mb = float(m.get("b", 0.5))
    cw = sw - ml - mr
    ch = sh - mt - mb
    rp = p["page_intent"]["route"]
    acc = _intent_accent(rte.get("accent"), palette, p)
    stages = rte["stages"]
    n = len(stages)
    base = 0
    zc = [0]

    def nz():
        zc[0] += 1
        return alloc(z=base + zc[0])

    y = mt + ch * rp["y_ratio"]
    h = rp["h"]
    if rte.get("title"):
        el = _emit_basic("rte_title", "text", (ml, mt + ch * rp["title_y_ratio"],
                                               cw * 0.62, rp["title_h"]),
                         nz(), None,
                         {"text": rte["title"],
                          "text_style": {"fs": rp["title_fs"], "bold": True,
                                         "align": "left"}}, p)
        out["elements"].append(el)
        all_rects["rte_title"] = el["rect"]
    box_w = (cw - (n - 1) * rp["gap"]) / float(n)
    cy = y + h / 2.0
    for i, label in enumerate(stages):
        x = ml + i * (box_w + rp["gap"])
        el = _emit_basic(f"rte_stage{i + 1}", "shape", (x, y, box_w, h),
                         nz(), None,
                         {"kind": "hexagon",
                          "style": {"fill": acc, "border": None,
                                    "shadow": p["style"]["shadow"]},
                          "text": label,
                          "text_style": {"fs": rp["stage_fs"], "bold": True,
                                         "align": "center", "color": "#FFFFFF"}}, p)
        out["elements"].append(el)
        all_rects[el["id"]] = el["rect"]
        if i < n - 1:
            x2 = x + box_w
            out["lines"].append(dict(id=f"rte_lnk{i + 1}", z=nz(),
                                     a1=(x2, cy), a2=(x2 + rp["gap"], cy),
                                     color=acc, weight=rp["arrow_w"],
                                     arrow=True, dash=None))
    out["page_intent"] = "route"
    out["page_intent_variant"] = "chain"


# ---- 内容页结构生成样板（内容处理转换律落地，references/page-intents.md §10）----
# 共同律：每条 items/cols 项既是"内容"也是"结构"——引擎把内容解成网格/分栏/
# 指标行/卡网格/图文版式，逐项产可命名单形状（可动画/链接），并写 owner 令牌
# （卡底 + 卡内文本同 owner → 叠放合法）。rect 全在此解（铁律 1）。


def _ck_fields(it, default_head=""):
    """内容项归一：字符串 → (head, body)；dict → (head|title, body|text)。"""
    if isinstance(it, dict):
        head = it.get("head") or it.get("title") or default_head
        body = it.get("body") or it.get("text") or ""
        return str(head), str(body)
    return (str(it) if it is not None else default_head), ""


def _ck_grid(n, cols, x0, y0, w, h, gap):
    """均分网格：返回 [(x, y, cw, ch)]（n 项、cols 列、rows 行）。"""
    cols = max(1, cols)
    rows = -(-n // cols)
    cw_ = (w - gap * (cols - 1)) / cols
    ch_ = (h - gap * (rows - 1)) / rows
    out = []
    for j in range(n):
        r, c = j // cols, j % cols
        out.append((x0 + c * (cw_ + gap), y0 + r * (ch_ + gap), cw_, ch_))
    return out


def _expand_panels(pnl, meta, p, out, alloc, all_rects, palette):
    """panels 页型展开（并行面板/要点区）：pnl_title 页题 + 网格面板（pnl_panel*/
    pnl_head*/pnl_body*）——even 均分网格；hero_left 首板全宽横幅 + 余项网格。"""
    import intents as IN
    variant = IN.resolve("panels", pnl.get("variant"))
    sw, sh = out["slide"]
    m = out["margin"]
    ml = float(m.get("l", 0.5)); mr = float(m.get("r", 0.5))
    mt = float(m.get("t", 0.5)); mb = float(m.get("b", 0.5))
    cw = sw - ml - mr; ch = sh - mt - mb
    pp = p["page_intent"]["panels"]
    acc = _intent_accent(pnl.get("accent"), palette, p)
    items = pnl.get("items") or []
    cols = int(pnl.get("cols") or pp["cols_default"])
    base = 0
    OWN = "panels"
    zc = [0]

    def put(cfg, owner=None):
        zc[0] += 1
        el = _emit_basic(cfg["id"], cfg["type"], cfg["rect"], alloc(z=base + zc[0]),
                         owner, cfg, p)
        out["elements"].append(el)
        all_rects[cfg["id"]] = cfg["rect"]

    if pnl.get("title"):
        put({"id": "pnl_title", "type": "text", "text": pnl["title"],
             "rect": (ml, mt + ch * pp["title_y_ratio"], cw, pp["title_h"]),
             "text_style": {"fs": pp["title_fs"], "bold": True, "align": "left"}})
    gy = mt + ch * pp["grid_y_ratio"]
    gh = ch * pp["grid_h_ratio"]
    gap = pp["gap"]; pad = pp["pad"]
    start = 0

    def panel(i, x, y, w, h):
        head, body = _ck_fields(items[i])
        put({"id": f"pnl_panel{i}", "type": "shape", "kind": "rounded_rect",
             "rect": (x, y, w, h),
             "style": {"fill": p["style"]["group_fill"],
                       "border": p["style"]["group_border"],
                       "shadow": p["style"]["shadow"]}}, OWN)
        put({"id": f"pnl_head{i}", "type": "text", "text": head,
             "rect": (x + pad, y + pad, w - 2 * pad, min(0.5, h * 0.42)),
             "text_style": {"fs": pp["head_fs"], "bold": True, "align": "left",
                            "color": acc}}, OWN)
        if body:
            put({"id": f"pnl_body{i}", "type": "text", "text": body,
                 "rect": (x + pad, y + pad + 0.5, w - 2 * pad, h - 0.5 - 2 * pad),
                 "text_style": {"fs": pp["body_fs"], "align": "left"}}, OWN)

    if variant == "hero_left" and items:
        hh = max(0.8, gh * pp["hero_h_ratio"])
        panel(0, ml, gy, cw, hh)
        gy += hh + gap; gh -= hh + gap; start = 1
    rest = items[start:]
    for j, (x, y, w, h) in enumerate(_ck_grid(len(rest), cols, ml, gy, cw, gh, gap)):
        panel(start + j, x, y, w, h)
    out["page_intent"] = "panels"
    out["page_intent_variant"] = variant


def _expand_columns(cols_cfg, meta, p, out, alloc, all_rects, palette):
    """columns 页型展开（分栏正文）：col_title 页题 + 逐栏（col_head*/col_body*）+
    可选 col_bottom 底条——even 平铺；arrow 变体加 col_arrow* 栏间箭头。"""
    import intents as IN
    variant = IN.resolve("columns", cols_cfg.get("variant"))
    sw, sh = out["slide"]
    m = out["margin"]
    ml = float(m.get("l", 0.5)); mr = float(m.get("r", 0.5))
    mt = float(m.get("t", 0.5)); mb = float(m.get("b", 0.5))
    cw = sw - ml - mr; ch = sh - mt - mb
    cp = p["page_intent"]["columns"]
    acc = _intent_accent(cols_cfg.get("accent"), palette, p)
    cols = cols_cfg.get("cols") or []
    n = max(1, len(cols))
    base = 0
    zc = [0]

    def put(cfg, owner=None):
        zc[0] += 1
        el = _emit_basic(cfg["id"], cfg["type"], cfg["rect"], alloc(z=base + zc[0]),
                         owner, cfg, p)
        out["elements"].append(el)
        all_rects[cfg["id"]] = cfg["rect"]

    if cols_cfg.get("title"):
        put({"id": "col_title", "type": "text", "text": cols_cfg["title"],
             "rect": (ml, mt + ch * cp["title_y_ratio"], cw, cp["title_h"]),
             "text_style": {"fs": cp["title_fs"], "bold": True, "align": "left"}})
    by = mt + ch * cp["body_y_ratio"]
    bh = ch * cp["body_h_ratio"]
    bottom = cols_cfg.get("bottom")
    if bottom:
        bh -= cp["bottom_h"] + cp["bottom_gap"]
    gap = cp["col_gap"]; pad = cp["pad"]
    col_w = (cw - gap * (n - 1)) / n
    centers = []
    for i, col in enumerate(cols):
        head, body = _ck_fields(col)
        items = col.get("items") if isinstance(col, dict) else None
        if items:
            body = "\n".join(f"· {s}" for s in items)
        x = ml + i * (col_w + gap)
        put({"id": f"col_head{i}", "type": "text", "text": head,
             "rect": (x, by, col_w, 0.6),
             "text_style": {"fs": cp["head_fs"], "bold": True, "align": "left",
                            "color": acc}})
        if body:
            put({"id": f"col_body{i}", "type": "text", "text": body,
                 "rect": (x + pad, by + 0.7, col_w - 2 * pad, bh - 0.7 - pad),
                 "text_style": {"fs": cp["item_fs"], "align": "left"}})
        centers.append((x, by + bh / 2.0, col_w))
    if variant == "arrow":
        for i in range(n - 1):
            x1 = centers[i][0] + centers[i][2]
            x2 = centers[i + 1][0]
            out["lines"].append(dict(id=f"col_arrow{i}", z=alloc(z=base + zc[0] + 1 + i),
                                     a1=(x1 + 0.04, centers[i][1]),
                                     a2=(x2 - 0.04, centers[i][1]),
                                     color=acc, weight=cp["arrow_w"],
                                     arrow=True, dash=None))
    if bottom:
        txt = ", ".join(bottom) if isinstance(bottom, list) else str(bottom)
        put({"id": "col_bottom", "type": "shape", "kind": "rounded_rect",
             "rect": (ml, by + bh + cp["bottom_gap"], cw, cp["bottom_h"]),
             "style": {"fill": p["style"]["group_fill"], "border": None,
                       "shadow": False},
             "text": txt, "text_style": {"fs": cp["item_fs"], "align": "left"}})
    out["page_intent"] = "columns"
    out["page_intent_variant"] = variant


def _expand_kpis(kpi, meta, p, out, alloc, all_rects, palette):
    """kpis 页型展开（指标卡行）：kpi_title 页题 + 一行指标卡（kpi_card*/kpi_val*/
    kpi_lab*）——cards 实色卡；row 扁平无描边；rings 数值嵌圆标（kpi_badge*）。"""
    import intents as IN
    variant = IN.resolve("kpis", kpi.get("variant"))
    sw, sh = out["slide"]
    m = out["margin"]
    ml = float(m.get("l", 0.5)); mr = float(m.get("r", 0.5))
    mt = float(m.get("t", 0.5)); mb = float(m.get("b", 0.5))
    cw = sw - ml - mr; ch = sh - mt - mb
    kp = p["page_intent"]["kpis"]
    acc = _intent_accent(kpi.get("accent"), palette, p)
    items = kpi.get("items") or []
    n = max(1, len(items))
    base = 0
    zc = [0]

    def put(cfg, owner=None):
        zc[0] += 1
        el = _emit_basic(cfg["id"], cfg["type"], cfg["rect"], alloc(z=base + zc[0]),
                         owner, cfg, p)
        out["elements"].append(el)
        all_rects[cfg["id"]] = cfg["rect"]

    if kpi.get("title"):
        put({"id": "kpi_title", "type": "text", "text": kpi["title"],
             "rect": (ml, mt + ch * kp["title_y_ratio"], cw, kp["title_h"]),
             "text_style": {"fs": kp["title_fs"], "bold": True, "align": "left"}})
    gap = kp["gap"]; pad = kp["pad"]
    card_w = (cw - gap * (n - 1)) / n
    cy = mt + ch * kp["row_y_ratio"]
    card_h = kp["card_h"]
    fill = {"cards": p["style"]["fill"], "row": p["style"]["group_fill"],
            "rings": p["style"]["group_fill"]}[variant]
    border = {"cards": p["style"]["border"], "row": None,
              "rings": p["style"]["group_border"]}[variant]
    for i, it in enumerate(items):
        x = ml + i * (card_w + gap)
        val, lab = _ck_fields(it)
        if isinstance(it, dict):
            val = str(it.get("value", val)) if it.get("value") is not None else val
            lab = str(it.get("label", lab)) if it.get("label") is not None else lab
        put({"id": f"kpi_card{i}", "type": "shape", "kind": "rounded_rect",
             "rect": (x, cy, card_w, card_h),
             "style": {"fill": fill, "border": border,
                       "shadow": p["style"]["shadow"] if variant == "cards" else False}},
            "kpis")
        if variant == "rings":
            side = min(card_w - 2 * pad, card_h * kp["badge_side_ratio"])
            bx = x + (card_w - side) / 2.0
            put({"id": f"kpi_badge{i}", "type": "shape", "kind": "oval",
                 "rect": (bx, cy + pad, side, side),
                 "style": {"fill": acc, "border": None, "shadow": False}}, "kpis")
            put({"id": f"kpi_val{i}", "type": "text", "text": val,
                 "rect": (bx, cy + pad, side, side),
                 "text_style": {"fs": kp["value_fs"], "bold": True,
                                "align": "center", "color": "#FFFFFF"}}, "kpis")
        else:
            put({"id": f"kpi_val{i}", "type": "text", "text": val,
                 "rect": (x + pad, cy + pad, card_w - 2 * pad, card_h * 0.55),
                 "text_style": {"fs": kp["value_fs"], "bold": True,
                                "align": "center", "color": acc}}, "kpis")
        if lab:
            put({"id": f"kpi_lab{i}", "type": "text", "text": lab,
                 "rect": (x + pad, cy + card_h * 0.58, card_w - 2 * pad, card_h * 0.34),
                 "text_style": {"fs": kp["label_fs"], "align": "center",
                                "color": p["style"]["text_color"]}}, "kpis")
    out["page_intent"] = "kpis"
    out["page_intent_variant"] = variant


def _expand_cards(crd, meta, p, out, alloc, all_rects, palette):
    """cards 页型展开（图标/编号卡网格）：crd_title 页题 + 卡网格（crd_card*/
    crd_badge* 顶饰 + crd_head*/crd_body*）——icon_top/icon_left 图标顶饰（缺则
    编号兜底）；number 大号编号顶饰。"""
    import intents as IN
    variant = IN.resolve("cards", crd.get("variant"))
    sw, sh = out["slide"]
    m = out["margin"]
    ml = float(m.get("l", 0.5)); mr = float(m.get("r", 0.5))
    mt = float(m.get("t", 0.5)); mb = float(m.get("b", 0.5))
    cw = sw - ml - mr; ch = sh - mt - mb
    cp = p["page_intent"]["cards"]
    acc = _intent_accent(crd.get("accent"), palette, p)
    items = crd.get("items") or []
    cols = int(crd.get("cols") or cp["cols_default"])
    base = 0
    OWN = "cards"     # 卡底 + 卡内顶饰/文本同 owner 令牌（叠放合法）
    zc = [0]

    def put(cfg, owner=None):
        zc[0] += 1
        el = _emit_basic(cfg["id"], cfg["type"], cfg["rect"], alloc(z=base + zc[0]),
                         owner, cfg, p)
        out["elements"].append(el)
        all_rects[cfg["id"]] = cfg["rect"]

    if crd.get("title"):
        put({"id": "crd_title", "type": "text", "text": crd["title"],
             "rect": (ml, mt + ch * cp["title_y_ratio"], cw, cp["title_h"]),
             "text_style": {"fs": cp["title_fs"], "bold": True, "align": "left"}})
    gy = mt + ch * cp["grid_y_ratio"]
    gh = ch * cp["grid_h_ratio"]
    gap = cp["gap"]; pad = cp["pad"]
    boxes = _ck_grid(len(items), cols, ml, gy, cw, gh, gap)
    for i, (x, y, w, h) in enumerate(boxes):
        it = items[i]
        head, body = _ck_fields(it)
        icon = it.get("icon") if isinstance(it, dict) else None
        num = it.get("num") if isinstance(it, dict) else None
        put({"id": f"crd_card{i}", "type": "shape", "kind": "rounded_rect",
             "rect": (x, y, w, h),
             "style": {"fill": p["style"]["group_fill"],
                       "border": p["style"]["group_border"],
                       "shadow": p["style"]["shadow"]}}, "cards")
        side = min(cp["icon_side"], w - 2 * pad, h * 0.4)
        if icon:
            bx = x + pad if variant == "icon_left" else x + (w - side) / 2.0
            by = y + pad
            if _motif_on(p):     # 母题背衬圆先于图标（z 低一档 → 衬底）
                zc[0] += 1
                _emit_motif_circle(f"crd_badge{i}_circ", (bx, by, side, side),
                                   alloc(z=base + zc[0]),
                                   {"icon": icon, "owner": OWN}, OWN, p, out, all_rects)
            zc[0] += 1
            _emit_icon(f"crd_badge{i}", (bx, by, side, side), alloc(z=base + zc[0]),
                       {"icon": icon, "owner": OWN}, out, all_rects)
        else:
            bx = x + pad if variant == "icon_left" else x + (w - side) / 2.0
            put({"id": f"crd_badge{i}", "type": "shape", "kind": "rounded_rect",
                 "rect": (bx, y + pad, side, side),
                 "style": {"fill": acc, "border": None, "shadow": False},
                 "text": str(num if num is not None else i + 1),
                 "text_style": {"fs": cp["num_fs"], "bold": True, "align": "center",
                                "color": "#FFFFFF"}}, "cards")
        if variant == "icon_left":
            tx = x + pad + side + 0.12
            tw = w - pad - (tx - x) - pad
            put({"id": f"crd_head{i}", "type": "text", "text": head,
                 "rect": (tx, y + pad, tw, min(0.5, h * 0.4)),
                 "text_style": {"fs": cp["head_fs"], "bold": True, "align": "left",
                                "color": acc}}, "cards")
            if body:
                put({"id": f"crd_body{i}", "type": "text", "text": body,
                     "rect": (tx, y + pad + 0.5, tw, h - 0.5 - 2 * pad),
                     "text_style": {"fs": cp["body_fs"], "align": "left"}}, "cards")
        else:
            put({"id": f"crd_head{i}", "type": "text", "text": head,
                 "rect": (x + pad, y + pad + side + 0.10, w - 2 * pad,
                          min(0.5, h * 0.34)),
                 "text_style": {"fs": cp["head_fs"], "bold": True, "align": "left",
                                "color": acc}}, "cards")
            if body:
                put({"id": f"crd_body{i}", "type": "text", "text": body,
                     "rect": (x + pad, y + pad + side + 0.60, w - 2 * pad,
                              h - side - 0.60 - 2 * pad),
                     "text_style": {"fs": cp["body_fs"], "align": "left"}}, "cards")
    out["page_intent"] = "cards"
    out["page_intent_variant"] = variant


def _expand_figure_text(fgt, meta, p, out, alloc, all_rects, palette):
    """figure_text 页型展开（图文并置）：fgt_title 页题 + 图侧（fgt_fig 图/占位
    + fgt_cap 图注）+ 文侧（fgt_body 正文块）——right 图右文左；left 图左文右。"""
    import intents as IN
    variant = IN.resolve("figure_text", fgt.get("variant"))
    side = fgt.get("side") or variant
    sw, sh = out["slide"]
    m = out["margin"]
    ml = float(m.get("l", 0.5)); mr = float(m.get("r", 0.5))
    mt = float(m.get("t", 0.5)); mb = float(m.get("b", 0.5))
    cw = sw - ml - mr; ch = sh - mt - mb
    fp = p["page_intent"]["figure_text"]
    acc = _intent_accent(fgt.get("accent"), palette, p)
    base = 0
    zc = [0]

    def put(cfg, owner=None):
        zc[0] += 1
        el = _emit_basic(cfg["id"], cfg["type"], cfg["rect"], alloc(z=base + zc[0]),
                         owner, cfg, p)
        out["elements"].append(el)
        all_rects[cfg["id"]] = cfg["rect"]

    if fgt.get("title"):
        put({"id": "fgt_title", "type": "text", "text": fgt["title"],
             "rect": (ml, mt + ch * fp["title_y_ratio"], cw, fp["title_h"]),
             "text_style": {"fs": fp["title_fs"], "bold": True, "align": "left"}})
    by = mt + ch * fp["body_y_ratio"]
    bh = ch * fp["body_h_ratio"]
    fig_w = cw * fp["fig_w_ratio"]
    gap = fp["gap"]; pad = fp["pad"]
    if side == "left":
        fx, tx = ml, ml + fig_w + gap
    else:
        tx, fx = ml, ml + (cw - fig_w)
    tw = cw - fig_w - gap
    cap_h = fp["cap_fs"] / 72.0 * 2.0 if fgt.get("caption") else 0.0
    put({"id": "fgt_fig", "type": "image", "src": fgt.get("image"),
         "rect": (fx, by, fig_w, bh - cap_h),
         "caption": fgt.get("caption")})
    if fgt.get("caption"):
        put({"id": "fgt_caption", "type": "text", "text": fgt["caption"],
             "rect": (fx, by + bh - cap_h, fig_w, cap_h),
             "text_style": {"fs": fp["cap_fs"], "align": "left",
                            "color": p["style"]["text_color"]}})
    blocks = fgt.get("blocks") or []
    body = "\n".join(("· " + (_ck_fields(b)[0] if isinstance(b, dict) else str(b)))
                     for b in blocks)
    if body:
        put({"id": "fgt_body", "type": "text", "text": body,
             "rect": (tx + pad, by, tw - 2 * pad, bh),
             "text_style": {"fs": fp["block_fs"], "align": "left"}})
    out["page_intent"] = "figure_text"
    out["page_intent_variant"] = variant


# 页型展开注册表（数据驱动派发；键 ⊆ capabilities.PAGE_INTENTS_IMPLEMENTED）。
# 每项签名 (field_dict, meta, p, out, alloc, all_rects, palette)；扩展新页型只加一项
# + capabilities 声明，不再改 build_ir 的 if/elif。
_EXPANDERS = {
    "cover": _expand_cover,
    "section": _expand_section,
    "problem": _expand_problem,
    "versus": _expand_versus,
    "route": _expand_route,
    "panels": _expand_panels,
    "columns": _expand_columns,
    "kpis": _expand_kpis,
    "cards": _expand_cards,
    "figure_text": _expand_figure_text,
}


_AUTO_TEXT = ("进入动画_自下浮入_改", "进入动画_自左浮入_改",
              "进入动画_自上浮入_改")
_AUTO_SHAPE = ("进入动画_自下浮入_改", "进入动画_自上浮入_改")
_AUTO_FIG = ("进入动画_自右缩小浮入", "进入动画_自左缩小浮入")


def _auto_anim_intent(out):
    """intent 展开产物缺省入场：标题快速淡入 → 其余按类型错峰（0.16+0.18s）。

    展开器不产 authored animation（SPEC 侧无法引用展开 id），故当
    params.page_intent.anim_default 为真时在引擎侧补齐；母题背衬圆（*_circ）
    保持静态，避免与图标错峰打架。"""
    step = 0
    for e in out["elements"]:
        if e.get("animation") or str(e.get("id", "")).endswith("_circ"):
            continue
        eid = str(e.get("id", ""))
        if "title" in eid:
            e["animation"] = {"effect": "进入动画_快速淡入",
                              "trigger": "with_previous", "delay": 0.0}
            continue
        t = e.get("type")
        if t in ("image", "svg", "chart"):
            eff = _AUTO_FIG[step % 2]
        elif t == "table":
            eff = "进入动画_快速淡入"
        elif t in ("shape", "icon"):
            eff = _AUTO_SHAPE[step % 2]
        else:
            eff = _AUTO_TEXT[step % 3]
        e["animation"] = {"effect": eff, "trigger": "after_previous",
                          "delay": round(0.16 + 0.18 * step, 2)}
        step += 1


def build_ir(compiled, p=None):
    """compiled: spec_compile 输出；p: 已合并 params。返回 IR dict。"""
    p = p or _P.resolve((compiled.get("meta") or {}).get("params"))
    meta = compiled.get("meta") or {}
    slide = meta.get("slide") or {}
    sw = slide.get("w", p["slide"]["w"])
    sh = slide.get("h", p["slide"]["h"])

    out = {"slide": (sw, sh), "margin": meta.get("margin") or {},
           "elements": [], "lines": [], "glue": [], "groups": [],
           "com_group": [], "z_max": 0,
           # 图面框架层（背景/页眉页脚）：仅存储供渲染/物证/COM，不进 elements
           # （豁免遮挡/安全区校验——本就贴边/叠底的图层）
           "framework": copy.deepcopy(meta.get("framework") or {}),
           # 备注页文本（页级；渲染器写 notes_slide，纯消费不改几何）
           "notes": meta.get("notes"),
           # 页面切换（编译期已解析为页级有效值；渲染器注入 p:transition）
           "transition": meta.get("transition")}
    z_override = {ov["id"]: ov["z"]
                  for ov in (compiled.get("relations") or {}).get("z_override", [])}
    # 顶层元素显式 z（spec 元素级 z 字段；优先级：z_override > 元素 z > 声明序）。
    # 容器 children 的 z 由容器内阶梯分配（base_z + 10*(i+1)），不读 children 的 z 字段。
    elem_z = {e["id"]: e["z"] for e in compiled["elements"] if e.get("z") is not None}
    seen_z = set()

    def alloc(eid=None, idx=None, z=None):
        """唯一 z 出口：显式 z / 声明序 / 容器内阶梯，全走此（冲突顺延）。"""
        if z is None:
            z = z_override.get(eid, elem_z.get(eid, (idx + 1) if idx is not None else None))
            if z is None:
                raise ValueError(f"ir_builder 内部错误: alloc 无 z 来源 ({eid})")
        while z in seen_z:
            z += 1
        seen_z.add(z)
        out["z_max"] = max(out["z_max"], z)
        return z

    # 全元素 rect 表（含容器 rect，供 glue 锚点）
    all_rects = {}

    # 页型意图展开（grilling 收敛：agent 只选 intent token，布局由引擎确定性
    # 解出 → 防刻板且保 harness；每原型 = 布局代码 + verify 断言）。数据驱动派发：
    # _EXPANDERS 查表（缺省/未实现页型 → 无展开，如 content 走默认版式）。
    _pi = meta.get("page_intent")
    _expand = _EXPANDERS.get(_pi) if _pi else None
    if _expand:
        _expand(meta.get(_pi) or {}, meta, p, out, alloc, all_rects,
                compiled.get("palette") or {})

    for idx, e in enumerate(compiled["elements"]):
        eid = e["id"]
        base_z = alloc(eid=eid, idx=idx)
        t = e["type"]
        rect = tuple(e["rect"])
        all_rects[eid] = rect
        if t in ("stack", "dock"):
            if e.get("group"):
                out["com_group"].append(eid)
            _emit_container(e, rect, base_z, alloc, p, out, all_rects)
        elif t == "graph":
            if e.get("group"):
                out["com_group"].append(eid)
            _emit_graph(e, rect, base_z, alloc, p, out, all_rects)
        elif t == "line":
            a1 = (e.get("x1", 0.0), e.get("y1", 0.0))
            a2 = (e.get("x2", 0.0), e.get("y2", 0.0))
            out["lines"].append(dict(id=eid, z=base_z, a1=a1, a2=a2,
                                     color=e.get("color"), weight=e.get("weight"),
                                     arrow=e.get("arrow", False),
                                     dash=e.get("dash")))
        elif t == "curve":
            # 自由曲线：归一化点（0~1 相对 rect）→ 绝对坐标 polyline（freeform 渲染）。
            # 线语义（color/weight/dash）直通；不参与端口/箭头/折线结构校验。
            st = e.get("style") or {}
            pts = [(round(rect[0] + px * rect[2], 3),
                    round(rect[1] + py * rect[3], 3)) for px, py in e["points"]]
            out["lines"].append(dict(id=eid, z=base_z, pts=pts, curve=True,
                                     color=st.get("color"), weight=st.get("weight"),
                                     dash=st.get("dash")))
        elif t == "shape" and e.get("kind") == "cylinder":
            _emit_cylinder(eid, rect, base_z, alloc, e, p, out, all_rects,
                           compiled.get("palette") or {})
        elif t == "brush":
            _emit_brush(eid, rect, base_z, e, out, all_rects)
        elif t == "icon":
            if _motif_on(p):
                # 视觉母题 circle_icon：图标前衬浅 accent 背衬圆（z 低一档 → 衬底）。
                # owner 用非元素令牌（不指向容器 id，避免被容器级 D/G 断言误判）
                own = e.get("owner") or f"_motif_{eid}"
                _emit_motif_circle(eid + "_circ", rect, base_z, e, own, p,
                                   out, all_rects)
                ee = dict(e)
                if not ee.get("owner"):
                    ee["owner"] = own            # 与背衬圆同 owner（叠放合法）
                _emit_icon(eid, rect, alloc(z=base_z + 1), ee, out, all_rects)
            else:
                _emit_icon(eid, rect, base_z, e, out, all_rects)
        elif t == "svg":
            _emit_svg(eid, rect, base_z, e, out, all_rects)
        else:
            el = _emit_basic(eid, t, rect, base_z, None, e, p)
            out["elements"].append(el)
            all_rects[eid] = rect
    if _expand and (p.get("page_intent") or {}).get("anim_default"):
        _auto_anim_intent(out)
    _emit_glue(compiled, out, p, alloc, all_rects)
    _coalesce_edit_groups(compiled, out)
    if compiled.get("anim") is not None:
        _expand_anim_groups(compiled, out)
    return out


def _expand_anim_groups(compiled, out):
    """页级 anim（声明式动画组）→ 确定性时间轴：改写成员 animation.trigger/delay，
    注出 ir.anim_timeline（绝对秒时间轴）与 ir.anim_sequence（AddEffect 序）。

    JAnim 时间区段组合语义的移植（references/animation.md「动画组」节）：
    组内成员的时序全由引擎展开（成员自带 trigger/delay 编译期已拦）；
    com_layer 按 anim_sequence 序 AddEffect（块末 = 最晚结束者 = 父链锚定代表）。"""
    import anim_group as AG
    leaves, seq, _blocks, viol = AG.expand_group(compiled["anim"],
                                                 compiled["elements"])
    if viol:
        # 展开算法回归护栏（时间一致性断言恒真，防浮点/排序回归）
        raise ValueError(f"anim_group 时间一致性断言失败：{viol}")
    ir_el = {el["id"]: el for el in out["elements"]}
    for r in leaves:
        el = ir_el.get(r["id"])
        if el is None or "animation" not in el:
            raise ValueError(f"{r['id']}: 动画组员 IR 元素缺失（top-level 动画元素？）")
        anim = dict(el["animation"])
        anim["trigger"], anim["delay"] = r["trigger"], r["delay"]
        el["animation"] = anim
    out["anim_timeline"] = leaves
    out["anim_sequence"] = seq


def _emit_brush(eid, rect, z, e, out, all_rects):
    """书法矢量字（C3）：字形 ink 盒按声明盒等比适配居中 → 定死元素 rect（铁律 1）；
    字形路径由渲染层用 ink_text 重算（艺术路径非几何，rect 才是唯一几何真相）。
    align/anchor 控字形在声明盒内的落位（缺省水平居中 + 垂直居中）。"""
    import ink_text
    text, font = e["text"], e["font"]
    spacing = float(e.get("spacing") or 0.0)
    w_em, h_em = ink_text.measure(text, font, spacing)
    x, y, w, h = rect
    s = min(w / w_em, h / h_em) if (w_em > 1e-9 and h_em > 1e-9) else 1.0
    gw, gh = w_em * s, h_em * s
    gx = x + {"left": 0.0, "center": (w - gw) / 2, "right": w - gw}[e.get("align", "center")]
    gy = y + {"top": 0.0, "middle": (h - gh) / 2, "bottom": h - gh}[e.get("anchor", "middle")]
    fit = (round(gx, 3), round(gy, 3), round(gw, 3), round(gh, 3))
    out["elements"].append(dict(
        id=eid, type="brush", z=z, rect=fit,
        brush=dict(text=text, font=font, spacing=spacing),
        style=e.get("style"), link=e.get("link"), animation=e.get("animation")))
    all_rects[eid] = fit


def _emit_svg(eid, rect, z, e, out, all_rects):
    """矢量图（svg_doc）：SVG 用户坐标 → 英寸（contain-fit 居中于声明盒）→ 定死
    元素 rect + 片几何（铁律 1）。SVG 解析在 spec_compile 已完成（e["_svg"] 存
    svg_doc 分组表）；本层只做变换（铁律 1：几何唯一源）。每片（顶层元素 × paint
    样式分组）一个内部 type="svgpath" IR 元素：id = {eid}_{i}，owner = eid。
    subpaths 由本层变换到英寸（渲染层只写 custGeom，零重算）。"""
    groups = e.get("_svg")
    if not groups:
        raise ValueError(f"ir_builder 内部错误: svg {eid} 缺 _svg（编译期未解析）")
    x, y, w, h = rect
    fx = str(e.get("fit") or "contain").lower()
    x0, y0, x1, y1 = svg_doc.doc_bbox(groups)
    uw, uh = x1 - x0, y1 - y0
    if uw <= 0 or uh <= 0:
        raise ValueError(f"{eid}: svg 图片空包围盒")
    if fx == "stretch":
        sx, sy = w / uw, h / uh
    else:
        s = min(w / uw, h / uh)
        sx = sy = s
    gw, gh = uw * sx, uh * sy
    gx = x + (w - gw) / 2.0          # contain 居中
    gy = y + (h - gh) / 2.0
    # 精度缩放：仿 icon_lib 归一化 — 局部单位 ×_SC 保小数精度，a:path 视盒同步放大。
    # 分层：英寸层（绝对落位 + 片 rect）→ 局部单位层（视盒 + 子路径，比值无关）。
    _SC = 1000.0

    def tr(px, py):
        """SVG 用户坐标 → 元素坐标（英寸，相对元素左上）。"""
        return gx + (px - x0) * sx, gy + (py - y0) * sy

    for i, g in enumerate(groups):
        bx0, by0, bx1, by1 = g["bbox"]
        # 本组 bbox 的元素英寸坐标（四角扫过取 min/max，覆盖旋转等变换）
        rel = [tr(c[0], c[1]) for c in ((bx0, by0), (bx1, by0), (bx0, by1), (bx1, by1))]
        bxr = min(p[0] for p in rel); bxr1 = max(p[0] for p in rel)
        byr = min(p[1] for p in rel); byr1 = max(p[1] for p in rel)
        sw_in = (g["stroke_w"] or 0.0) * max(sx, sy) / 2.0   # 描边半宽（英寸）
        er = (bxr - sw_in, byr - sw_in,
              (bxr1 - bxr) + 2 * sw_in, (byr1 - byr) + 2 * sw_in)
        # 视盒 = 本组 bbox 尺寸 ×_SC（局部单位）；子路径归一到本组 bbox 起始。
        vw = (bxr1 - bxr) * _SC
        vh = (byr1 - byr) * _SC
        subs = []
        for sp in g["subpaths"]:
            def ltr(px, py):
                ax = round((tr(px, py)[0] - bxr) * _SC, 1)
                ay = round((tr(px, py)[1] - byr) * _SC, 1)
                return ax, ay
            segs = [("L",) + ltr(sg[1], sg[2]) if sg[0] == "L"
                    else ("C",) + ltr(sg[1], sg[2]) + ltr(sg[3], sg[4])
                    + ltr(sg[5], sg[6]) for sg in sp["segs"]]
            subs.append({"start": ltr(*sp["start"]), "segs": segs,
                         "closed": sp["closed"]})
        eid_piece = f"{eid}_{i}"
        out["elements"].append(dict(
            id=eid_piece, type="svgpath", z=z, rect=tuple(round(v, 3) for v in er),
            owner=eid,
            path=dict(subs=subs, fill=g["fill"], stroke=g["stroke"],
                      stroke_w=g["stroke_w"], vb_w=vw, vb_h=vh),
            link=e.get("link"), animation=e.get("animation")))
        all_rects[eid_piece] = tuple(round(v, 3) for v in er)
    all_rects[eid] = (round(x, 3), round(y, 3), round(w, 3), round(h, 3))


def _motif_on(p):
    """视觉母题开关（meta.theme.motif）：circle_icon 时给每个 icon 衬背衬圆。"""
    return (p.get("theme") or {}).get("motif") == "circle_icon"


def _emit_motif_circle(eid, rect, z, e, owner, p, out, all_rects):
    """视觉母题 circle_icon（官方 §Before Starting "icons in colored circles"）：
    在 icon 声明盒位置 emit 一个浅 accent 色背衬圆（oval，无描边/无阴影）——尺寸 =
    图标正方适配盒 × motif_circle_scale、同锚居中、z 低图标一档（衬底）。owner 与
    图标同令牌 → 叠放合法（G4 同 owner 豁免）。缺省 motif=none → 本函数不被调用。"""
    import themes as _TH
    x, y, w, h = rect
    side = min(w, h)
    gx = x + {"left": 0.0, "center": (w - side) / 2, "right": w - side}[e.get("align", "center")]
    gy = y + {"top": 0.0, "middle": (h - side) / 2, "bottom": h - side}[e.get("anchor", "middle")]
    th = p.get("theme") or {}
    d = side * float(th.get("motif_circle_scale", 1.45))
    cx = gx + side / 2.0 - d / 2.0
    cy = gy + side / 2.0 - d / 2.0
    fill = _TH.tint(p["style"]["accent"], float(th.get("motif_circle_tint", 78)))
    out["elements"].append(dict(
        id=eid, type="shape", kind="oval", z=z,
        rect=(round(cx, 3), round(cy, 3), round(d, 3), round(d, 3)),
        style={"fill": fill, "border": None, "shadow": False}, owner=owner))
    all_rects[eid] = (round(cx, 3), round(cy, 3), round(d, 3), round(d, 3))


def _emit_icon(eid, rect, z, e, out, all_rects):
    """矢量图标（B1）：Lucide 24×24 视图盒按声明盒等比适配（保持正方）→ 定死
    元素 rect（铁律 1）；子路径由渲染层用 icon_lib 现算（图标路径非几何，rect 才是
    唯一几何真相）。icon 名经 resolve 归一（关键词 → 图标名，未命中回退 circle-dot）；
    align/anchor 控图标在声明盒内落位（缺省水平居中 + 垂直居中）。"""
    import icon_lib
    name = icon_lib.resolve(e["icon"])
    x, y, w, h = rect
    side = min(w, h)
    gx = x + {"left": 0.0, "center": (w - side) / 2, "right": w - side}[e.get("align", "center")]
    gy = y + {"top": 0.0, "middle": (h - side) / 2, "bottom": h - side}[e.get("anchor", "middle")]
    fit = (round(gx, 3), round(gy, 3), round(side, 3), round(side, 3))
    el = dict(id=eid, type="icon", z=z, rect=fit, icon=name,
              style=e.get("style"), link=e.get("link"),
              animation=e.get("animation"))
    if e.get("owner"):
        el["owner"] = e["owner"]     # 页型展开：图标顶饰与卡同 owner（叠放合法）
    out["elements"].append(el)
    all_rects[eid] = fit


def _emit_basic(eid, t, rect, z, owner, cfg, p):
    """普通元素 emit（顶层 text/shape/image 或容器 children）。"""
    el = dict(id=eid, type=t, z=z, rect=rect)
    if owner:
        el["owner"] = owner
    if t == "text":
        if cfg.get("ph_info"):
            # seed 打底：ph 元素不自绘，落点 = 模板占位符；rect 仅作文本测量输入
            el["ph_info"] = dict(cfg["ph_info"])
        _apply_text(el, cfg, rect, p)
    elif t == "shape":
        el["kind"] = cfg.get("kind", "rounded_rect")
        el["style"] = _style(cfg.get("style"), p)
        if cfg.get("anchors"):
            el["anchors"] = _abs_anchors(rect, cfg["anchors"])
        if "text" in cfg:
            _apply_text(el, cfg, rect, p)
    elif t in ("image", "diagram"):
        el["src"] = cfg.get("src")     # 可能为 None（placeholder 占位，B3）
        el["visual_bounds"] = cfg.get("visual_bounds", "auto")
        if cfg.get("placeholder"):
            el["placeholder"] = cfg["placeholder"]
        if t == "diagram" or cfg.get("caption"):
            el["caption"] = cfg.get("caption")
    elif t == "formula":
        ts = dict(cfg.get("text_style") or {})
        ts.setdefault("fs", p["formula"]["fs_default"])
        el["expr"] = cfg["expr"]
        el["text_style"] = ts
    elif t == "table":
        # 行/列由 data 推导；列宽 = col_widths 或均分 rect.w；
        # header/body 样式原样透传（渲染层做 palette 解析与字体/边框）。
        # 富文本：单元格 plain 进 data（测量/断言），runs 仅在有标记时进 cell_runs。
        data = [[RT.plain(v) if isinstance(v, str) else v for v in row]
                for row in cfg["data"]]
        cell_runs = None
        for ri, row in enumerate(cfg["data"]):
            for ci, v in enumerate(row):
                rr = RT.runs_if_markup(v) if isinstance(v, str) else None
                if rr is not None:
                    if cell_runs is None:
                        cell_runs = [[None] * len(row) for _ in cfg["data"]]
                    cell_runs[ri][ci] = rr
        el["data"] = data
        if cell_runs is not None:
            el["cell_runs"] = cell_runs
        rows, cols = len(data), len(data[0])
        el["rows"], el["cols"] = rows, cols
        cws = cfg.get("col_widths")
        el["col_widths"] = list(cws) if cws else [rect[2] / cols] * cols
        hdr = cfg.get("header")
        el["header"] = dict(hdr) if isinstance(hdr, dict) else (False if hdr is False else None)
        bd = cfg.get("body")
        el["body"] = dict(bd) if isinstance(bd, dict) else None
        el["borders"] = cfg.get("borders", True)
        el["header_fs"] = (hdr.get("fs") if isinstance(hdr, dict) and hdr.get("fs")
                           else None) or p["table"]["header_fs"]
        el["cell_fs"] = (bd or {}).get("fs") or p["table"]["fs"]
    elif t == "chart":
        # 数据/样式直通（渲染层按 params 与 style 决定观感；compile 已背书数据账目）
        el["chart_type"] = cfg["chart_type"]
        el["categories"] = list(cfg["categories"])
        el["series"] = [dict(s) for s in cfg["series"]]
        el["style"] = dict(cfg.get("style") or {})
    elif t == "typst":
        # 排版块（references/typst-chain.md）：stage1.5 typst_compile 产物路径直通
        # 渲染（svg = OOXML 2016+ 矢量通道；png = 全版本栅格 fallback）——本层零重算。
        # 自动围切最小边界盒：元素实际 rect = 声明 rect 原点 + 内容偏移，尺寸 = 内容 bbox
        # （stage1.5 已裁 PNG/重写 SVG viewBox；用户 preamble 自设 page 时 size=画布、offset=0）
        _tp = cfg.get("_typst")
        if not _tp or not _tp.get("png"):
            raise ValueError(f"{eid}: typst 产物缺失（stage1.5 typst_compile 未执行？）")
        el["svg"] = _tp["svg"]
        el["png"] = _tp["png"]
        el["typst_size"] = _tp.get("size")
        _sz, _off = _tp.get("size") or (0.0, 0.0), _tp.get("offset") or (0.0, 0.0)
        if _sz:
            el["rect"] = (rect[0] + _off[0] / 72.0, rect[1] + _off[1] / 72.0,
                          _sz[0] / 72.0, _sz[1] / 72.0)
    if "link" in cfg:
        # 元素级超链接：原样进 IR，渲染层注入 cNvPr hlinkClick（零 COM）
        el["link"] = dict(cfg["link"])
    if "animation" in cfg:
        # 元素级动画：原样进 IR，渲染层不消费（时间轴语义），com_layer 消费
        el["animation"] = dict(cfg["animation"])
    if "animation_exit" in cfg:
        # 附加退出效果（同名形状上的第二个效果，常以 on_click 触发）
        el["animation_exit"] = dict(cfg["animation_exit"])
    return el


def _cyl_hex(fill_ref, palette, fallback):
    """cylinder 主色 → 字面 hex（侧壁/椭圆部件用；grad 取深端、token 展开）。
    渲染层持 hex 即可 resolve，部件间不引入 palette 解析分支。"""
    if isinstance(fill_ref, dict) and "grad" in fill_ref:
        return str(fill_ref["grad"][1])
    if isinstance(fill_ref, str):
        if fill_ref in palette:
            v = palette[fill_ref]
            if "solid" in v:
                return str(v["solid"])
        if fill_ref.startswith("#") or len(fill_ref) == 6:
            return fill_ref
    return fallback


def _arc_pts(x, y, w, h, ell, fy, n=24):
    """侧壁 (x,y,w,h) 上 fy 比例处的椭圆弧（透视圆环投影），polyline 采样。
    弧从 (x, cy) 经 (cx, cy−ell) 到 (x+w, cy)——左右端点与侧壁齐平、中点上凸。"""
    cx = x + w / 2.0
    a = w / 2.0
    cy = y + fy * h
    pts = []
    for i in range(n + 1):
        t = -1.0 + 2.0 * i / n
        pts.append((round(cx + t * a, 3), round(cy - ell * (1.0 - t * t), 3)))
    return pts


def _emit_cylinder(eid, rect, base_z, alloc, cfg, p, out, all_rects, palette):
    """cylinder 复合展开（铁律 1：几何全在布局层解，渲染只按 IR 部件画）。

    部件序（z 递增）：侧壁(半透明 rect) → 底椭圆(oval) → 顶椭圆(oval，slice<1 剖视
    省略，示敞口) → 等高弧×2（freeform curve 进 lines）→ 标注文字（可省略）。
    所有部件 owner = eid（遮挡合法源二类之一；G4 同 owner 兄弟豁免）。
    投影圆环/椭圆高全部派生自 rect。"""
    x, y, w, h = rect
    ell = round(w * _CYL_ELL_FACTOR, 3)
    main = _cyl_hex((cfg.get("style") or {}).get("fill"), palette, p["style"]["fill"])
    op = cfg.get("opacity", 0.35)
    sl = float(cfg.get("slice", 1.0))
    pid = lambda s: f"{eid}.{s}"
    # apart_alpha 反解（references/alpha-blend.md；alpha_math）：端面绘制于侧壁
    # 之上（2 层叠区），声明 face_opacity 为端面区目标不透明度 → 端面自身 alpha
    # 反解使叠区合成 = face_opacity（侧壁 alpha = 声明 opacity 保持）。
    # face_opacity 缺省 1.0 → 端面 alpha = (1−op)/(1−op) = 1.0（实色，向后兼容）。
    face_a = alpha_math.face_alpha(float(cfg.get("face_opacity") or 1.0), op)
    if face_a is None:          # spec_compile 已拦；兜底防御
        raise ValueError(f"{eid}: face_opacity 须 > opacity（端面叠区反解无解）")

    # z+0 侧壁：半透明主色矩形（渲染层 a:alpha）
    out["elements"].append(dict(id=pid("side"), type="shape", z=alloc(z=base_z),
                                rect=rect, owner=eid, kind="rect",
                                style=dict(fill=main, border=None, opacity=op)))
    all_rects[pid("side")] = rect
    # z+1 底椭圆（端面 alpha 反解，叠区合成 = face_opacity）
    eb = (x, y + h - ell, w, ell)
    out["elements"].append(dict(id=pid("bot"), type="shape",
                                z=alloc(z=base_z + 1), rect=eb, owner=eid,
                                kind="oval", style=dict(fill=main, border=None,
                                                        opacity=face_a)))
    all_rects[pid("bot")] = eb
    # z+2 顶椭圆（slice<1 = 剖视：不画顶面，示内部）
    if sl >= 1.0:
        et = (x, y, w, ell)
        out["elements"].append(dict(id=pid("top"), type="shape",
                                    z=alloc(z=base_z + 2), rect=et, owner=eid,
                                    kind="oval", style=dict(fill=main, border=None,
                                                            opacity=face_a)))
        all_rects[pid("top")] = et
    # z+3/+4 两条等高弧（侧壁上的椭圆弧）
    for i, fy in enumerate(_CYL_CONTOUR_Y):
        out["lines"].append(dict(id=pid("c%d" % i),
                                 z=alloc(z=base_z + 3 + i),
                                 pts=_arc_pts(x, y, w, h, ell, fy),
                                 curve=True, color=main, weight=1.0, dash=None))
    # z+5 标注文字（居圆柱中部；guard 以侧壁主色为底自动反色）
    if cfg.get("text"):
        txt_rect = (x, y + h * 0.25, w, h * 0.5)
        sub = dict(cfg)
        sub["text_style"] = dict(cfg.get("text_style") or {})
        el = dict(id=pid("text"), type="text", z=alloc(z=base_z + 5),
                  rect=txt_rect, owner=eid, text=cfg["text"])
        _apply_text(el, sub, txt_rect, p)
        out["elements"].append(el)
        all_rects[pid("text")] = txt_rect


def _apply_text(el, cfg, rect, p):
    """文本 autofit 落到元素；未声明 fs 用块默认。
    富文本标记只解析一次（richtext）：IR 存 plain（测量/断言）+ runs（渲染）。"""
    ts = dict(cfg.get("text_style") or {})
    raw = cfg.get("text", "")
    runs = RT.runs_if_markup(raw)
    text = RT.plain(raw) if runs is not None else raw
    el["text"] = text
    if runs is not None:
        el["runs"] = runs
    # 类型尺度（deck 级）：text_style.scale 角色 → 起始字号 + 字体角色；
    # 逐元素 fs 仍优先（scale 只供 fs0 缺省）。主题 type_scale 经 params 下降。
    scale = ts.get("scale")
    _scales = p["text"].get("scale") or {}
    if scale and scale in _scales:
        fs0 = ts.get("fs", _scales[scale])
        ts["role"] = "title" if scale in ("hero", "title") else "body"
    else:
        fs0 = ts.get("fs", p["text"]["fs0_block"])
    tl = textmesh.autofit_text(text, fs0, rect[2] * 72, rect[3] * 72,
                               min_fs=p["text"]["min_fs"])
    tp = p["text"]
    ts.setdefault("fs", fs0)
    ts.setdefault("color", p["style"]["text_color"])
    if not cfg.get("ph_info"):
        # ph 元素：段落对齐继承模板占位符（用户显式写 align 才覆盖）
        ts.setdefault("align", "center")
    # 圆角卡片：未显式声明对齐时默认居中；显式 left/justify/right 优先
    # （完整段落需要两端对齐时不得被居中规则覆盖）。
    if cfg.get("type") == "shape" and cfg.get("kind") == "rounded_rect"             and ts.get("align") not in ("left", "justify", "right"):
        ts["align"] = "center"
    el["text_style"] = ts
    el["text_layout"] = tl
    el["overflow"] = (tl["fs"] <= tp["min_fs"] + 1e-9 and (
        tl["max_w"] > rect[2] * 72 * tp["margin_w"] or tl["need_h"] > rect[3] * 72 + 1e-6))


def _style(st, p):
    s = dict(p["style"])
    if st:
        s.update(st)
    if s.get("border") in (None, "none"):
        s["border"] = None  # 归一："none" → None（renderer 不画描边）
    return s


def _emit_container(container, rect, base_z, alloc, p, out, all_rects):
    """stack/dock 容器：求解 children rect → emit 子元素。"""
    sub = {}
    if container["type"] == "stack":
        LS.layout_stack(container, rect, sub)
    else:
        LD.layout_dock(container, rect, sub)
    for i, child in enumerate(container.get("children", [])):
        r = sub[child["id"]]["rect"]
        z = alloc(z=base_z + 10 * (i + 1))
        el = _emit_basic(child["id"], child["type"], r, z,
                         container["id"], child, p)
        out["elements"].append(el)
        all_rects[child["id"]] = r


def _emit_graph(g, rect, base_z, alloc, p, out, all_rects):
    """graph 容器：layout_graph 产节点/边/组 → 扁平展开 + z 阶梯。
    富文本：布局测量消费 plain（去标记），runs 在 emit 时从原始声明取。"""
    raw_nodes = {n["id"]: n for n in (g.get("nodes") or [])}
    raw_edges = g.get("edges") or []
    raw_groups = g.get("groups") or []
    g_layout = g
    if (any(isinstance(n.get("text"), str) and RT.has_markup(n["text"])
            for n in raw_nodes.values())
            or any(isinstance(ed.get("label"), str) and RT.has_markup(ed["label"])
                   for ed in raw_edges)
            or any(isinstance(gr.get("label"), str) and RT.has_markup(gr["label"])
                   for gr in raw_groups)):
        g_layout = copy.deepcopy(g)
        for n in g_layout.get("nodes") or []:
            if isinstance(n.get("text"), str):
                n["text"] = RT.plain(n["text"])
        for ed in g_layout.get("edges") or []:
            if isinstance(ed.get("label"), str):
                ed["label"] = RT.plain(ed["label"])
        for gr in g_layout.get("groups") or []:
            if isinstance(gr.get("label"), str):
                gr["label"] = RT.plain(gr["label"])
    res = LG.layout_graph(g_layout, rect, p)
    cz = base_z
    cid = g["id"]
    # 组包络（底层）
    for gi, gr in enumerate(res["groups"]):
        z_box = alloc(z=_z_of(cz, "group_box", gi))
        out["groups"].append(dict(id=gr["id"], label=gr["label"], bbox=gr["bbox"],
                                  members=gr.get("members", []), z=z_box))
        if gr.get("label"):
            zl = alloc(z=_z_of(cz, "group_label", gi))
            raw_gr = raw_groups[gi] if gi < len(raw_groups) else {}
            raw_lbl = raw_gr.get("label") if isinstance(raw_gr.get("label"), str) else None
            el = dict(id=f"{cid}.{gr['id']}.label", type="text", z=zl,
                      rect=_label_rect(gr["label"], gr["bbox"], p),
                      owner=cid, text=gr["label"],
                      text_style={"fs": p["text"]["edge_label_fs"],
                                  "color": p["style"]["group_border"], "align": "center"})
            rr = RT.runs_if_markup(raw_lbl) if raw_lbl else None
            if rr is not None:
                el["runs"] = rr
            el["text_layout"] = textmesh.autofit_text(
                gr["label"], p["text"]["edge_label_fs"],
                el["rect"][2] * 72, el["rect"][3] * 72, min_fs=p["text"]["min_fs"])
            out["elements"].append(el)
            all_rects[el["id"]] = el["rect"]
    # 边
    for i, ed in enumerate(res["edges"]):
        lid = f"{cid}.{ed['from_id']}->{ed['to_id']}"
        ln = dict(id=lid, z=alloc(z=_z_of(cz, "edge", i)),
                  from_id=ed["from_id"], to_id=ed["to_id"],
                  a1=ed["a1"], a2=ed["a2"],
                  side1=ed["side1"], side2=ed["side2"], label=ed.get("label"), way=ed["way"])
        if ed.get("pts"):
            ln["pts"] = [tuple(map(lambda v: round(v, 3), pt)) for pt in ed["pts"]]
        out["lines"].append(ln)
        if ed.get("label"):
            lel = _emit_edge_label(ln, p, out, alloc, _Z_CLASS["edge_label"], cid)
            raw_ed = raw_edges[i] if i < len(raw_edges) else {}
            raw_lbl = raw_ed.get("label") if isinstance(raw_ed.get("label"), str) else None
            rr = RT.runs_if_markup(raw_lbl) if raw_lbl else None
            if rr is not None and lel is not None:
                lel["runs"] = rr
    # 节点（高于边，盖住线端）
    for i, n in enumerate(res["nodes"]):
        z_node = alloc(z=_z_of(cz, "node", i))
        el = dict(id=n["id"], type="shape", z=z_node,
                  rect=n["rect"], owner=cid, kind=n["kind"], shape=n["shape"],
                  style=_style(None, p), text=n["text"],
                  text_style={"fs": p["text"]["fs0_node"], "color": p["style"]["text_color"],
                              "align": "center"},
                  text_layout=n["text_layout"], overflow=n["overflow"])
        raw_n = raw_nodes.get(n["id"]) or {}
        raw_txt = raw_n.get("text") if isinstance(raw_n.get("text"), str) else None
        rr = RT.runs_if_markup(raw_txt) if raw_txt else None
        if rr is not None:
            el["runs"] = rr
        # 节点 kind 区分填充（低调差异化，READ 下无魔法：仅 4 族）
        _node_fill(n["kind"], el["style"], p)
        out["elements"].append(el)
        all_rects[n["id"]] = n["rect"]


def _node_fill(kind, style, p):
    """kind → 填充：src/end 用主色系，proc 默认，judge 警示。颜色全在 params。"""
    m = {"src": "grad", "end": "solid", "judge": "warn", "proc": "fill"}
    role = m.get(kind, "fill")
    if role == "grad":
        style["fill"] = {"grad": ["#2D6CDF", "#1E88E5"]}
    elif role == "solid":
        style["fill"] = "#1F2A44"
        style["text_color"] = "#FFFFFF"
    elif role == "warn":
        style["fill"] = "#FFF3C4"
        style["border"] = "#E0A800"
    style.setdefault("filled", None)  # 占位：颜色族由 verify S 家族审计
    style["kind"] = kind


def _emit_edge_label(ln, p, out, alloc, cls, owner):
    """边标签文本：盖在折线水平段上方居中（封底白遮线）。owner = 容器 id（遮挡合法源）。"""
    label = ln["label"]
    pts = ln.get("pts")
    fs = p["text"]["edge_label_fs"]
    lb = p["label"]
    if pts:
        # 中段方向决定标签基准：水平中段（水平布局走廊）→ 标在中段上方；
        # 竖直中段（垂直布局左右走廊）→ 标在走廊中点，宽取竖直段长
        if abs(pts[2][1] - pts[1][1]) >= abs(pts[2][0] - pts[1][0]):
            mx = (pts[1][0] + pts[2][0]) / 2
            seg_w = max(abs(pts[2][1] - pts[1][1]), lb["seg_floor"])
            my = (pts[1][1] + pts[2][1]) / 2
            anchor_above = False
        else:
            mx = (pts[1][0] + pts[2][0]) / 2
            seg_w = abs(pts[2][0] - pts[1][0])
            my = pts[1][1]
            anchor_above = True
    else:
        mx = (ln["a1"][0] + ln["a2"][0]) / 2
        seg_w = max(abs(ln["a2"][0] - ln["a1"][0]), lb["seg_floor"])
        my = (ln["a1"][1] + ln["a2"][1]) / 2
        anchor_above = False
    tl = textmesh.autofit_text(label, fs, seg_w * 72, lb["h_cap"] * 72,
                               min_fs=p["text"]["min_fs"])
    # rect：水平居中于折线中点，上方偏移
    pad = lb["pad"]
    w = min(seg_w, max(tl["max_w"] / 72 + 2 * pad, lb["min_w"]))
    h = min(lb["h_cap"], tl["need_h"] / 72 + 2 * pad)
    if anchor_above:
        y = my - h - lb["rise"]
    else:
        y = my - h / 2
    rect = (mx - w / 2, y, w, h)
    el = dict(id=f"{ln['id']}.label", type="text",
              z=alloc(z=ln["z"] + 1), rect=rect,
              text=label, text_style={"fs": tl["fs"], "color": p["style"]["text_color"],
                                      "align": "center"},
              text_layout=tl, owner=owner)
    out["elements"].append(el)
    return el


def _label_rect(label, bbox, p, top_pad=0.0):
    """组标签位置：水平居中于包围盒，顶边内下移（位于图形内的文字默认居中）。"""
    fs = p["text"]["edge_label_fs"]
    gl = p["group_label"]
    tl = textmesh.autofit_text(label, fs, bbox[2] * 72, gl["h_cap"] * 72,
                               min_fs=p["text"]["min_fs"])
    w = max(tl["max_w"] / 72 + gl["pad_w"], gl["min_w"])
    h = min(gl["h_cap"], tl["need_h"] / 72 + gl["pad_h"])
    cx = bbox[0] + bbox[2] / 2
    return (cx - w / 2, bbox[1] + gl["off_y"], w, h)


def _abs_anchors(rect, anchors):
    """归一锚点 → 绝对坐标（in，round 3 位与 glue a1/a2 同规；铁律 1 内：唯一
    解在 ir_builder）。"""
    x, y, w, h = rect
    out = {}
    for an, (nx, ny) in anchors.items():
        out[an] = (round(x + nx * w, 3), round(y + ny * h, 3))
    return out


def _side_of(rect, pt):
    """锚点所在边推导（确定性优先序 |nx|≥|ny| → E/W 横向，否则 N/S；角点取
    横向——COM 站点就近绑定的降级哲学背书，verify 零重算）。"""
    cx = rect[0] + rect[2] / 2.0
    cy = rect[1] + rect[3] / 2.0
    nx = (pt[0] - cx) / (rect[2] / 2.0) if rect[2] else 0.0
    ny = (pt[1] - cy) / (rect[3] / 2.0) if rect[3] else 0.0
    if abs(nx) >= abs(ny):
        return "E" if nx >= 0 else "W"
    return "S" if ny >= 0 else "N"


def _emit_glue(compiled, out, p, alloc, all_rects):
    """relations.glue → 顶层连线（COM 绑定候选）。锚点默认 snap_anchor 端口模型
    （AABB 边中点）；具名锚点（from_anchor/to_anchor，编译期已成对强制）优先用
    归一锚点绝对位。"""
    for i, gl in enumerate((compiled.get("relations") or {}).get("glue", [])):
        ra, rb = all_rects.get(gl["from"]), all_rects.get(gl["to"])
        if ra is None or rb is None:
            raise ValueError(f"glue 端点 rect 缺失: {gl['from']}→{gl['to']}（编译期应已拦截）")
        sa, a1, sb, a2 = LR.anchor_pair(ra, rb)
        fa, ta = gl.get("from_anchor"), gl.get("to_anchor")
        ra_el = next((x for x in compiled["elements"] if x["id"] == gl["from"]), None)
        rb_el = next((x for x in compiled["elements"] if x["id"] == gl["to"]), None)
        if fa and ra_el and ra_el.get("anchors"):
            a1 = _abs_anchors(ra, {fa: ra_el["anchors"][fa]})[fa]
            sa = _side_of(ra, a1)
        if ta and rb_el and rb_el.get("anchors"):
            a2 = _abs_anchors(rb, {ta: rb_el["anchors"][ta]})[ta]
            sb = _side_of(rb, a2)
        gid = gl.get("id") or f"glue.{gl['from']}->{gl['to']}"
        rec = dict(id=gid, from_id=gl["from"], to_id=gl["to"],
                   z=alloc(z=out["z_max"] + 1 + i), a1=a1, a2=a2,
                   side1=sa, side2=sb, label=gl.get("label"))
        if fa:
            rec["an1"] = fa
        if ta:
            rec["an2"] = ta
        out["glue"].append(rec)


def _coalesce_edit_groups(compiled, out):
    """编辑单元 z 收拢（scansci「编辑单元分组」内化，块 2）。

    不变量：组内成员 z 连续区间、组间区间互不交叠、组区间参与全局序
    （容器 group:true 现状语义——children 阶梯——的泛化），verify G11 独立重算。

    确定性算法（一次扫描）：
      1) 组表 = 显式组（编译期已校验成员为顶层产生形状的元素）+ 容器并组
         （group:true → 派生物 owner==cid，成员 ≥2 才有组合收益）。
      2) 组按成员当前 min_z 升序（组间相对序 = 现状序的稳定投影）。
      3) 按原 z 升序遍历全元素：首次遇某组员 → 从游标连续分配整组（组内按原
         z 保序）；非组员 → 原 z 未被占则保留、被占则顺延游标。"""
    eg_spec = (compiled.get("relations") or {}).get("edit_groups", [])
    groups = [dict(id=g["id"], members=list(g["members"])) for g in eg_spec]
    now_z = {e["id"]: e["z"] for e in out["elements"]}
    for cid in out.get("com_group", []):
        mems = sorted((e["id"] for e in out["elements"] if e.get("owner") == cid),
                      key=lambda i: now_z.get(i, 0))
        if len(mems) >= 2:      # 单成员组无组合收益，跳过（与 COM len<2 拒合同律）
            groups.append(dict(id=cid, members=mems))

    ordered = sorted(out["elements"], key=lambda e: e["z"])
    group_of = {}
    for g in groups:
        for m in g["members"]:
            group_of[m] = g["id"]
        g["_minz"] = min((now_z.get(m, 0) for m in g["members"]), default=0)
    groups.sort(key=lambda g: g["_minz"])

    # 组按 min_z 升序 → 分配序（组块整体分配，组内保原 z 序）
    new_z = {}
    assigned = set()
    cursor = 0
    for e in ordered:
        eid = e["id"]
        if eid in new_z:
            continue
        gid = group_of.get(eid)
        if gid is not None and gid not in assigned:
            members = sorted([m for m in next(g["members"] for g in groups
                                              if g["id"] == gid)],
                             key=lambda m: now_z.get(m, 0))
            for m in members:
                new_z[m] = cursor
                cursor += 1
            assigned.add(gid)
            continue
        # 非组员（或组已分配完）：保留原 z；被占则顺延
        z = now_z[eid]
        if z < cursor:
            z = cursor
        while z in set(new_z.values()):
            z += 1
        new_z[eid] = z
        cursor = max(cursor, z + 1)

    # 回写 z + 组区间（z_max 保持含 glue/lines 的既有最大值——框架层页眉/页脚
    # 借 z_max 置顶，不能因元素收拢而塌到 glue 之下）
    for e in out["elements"]:
        e["z"] = new_z[e["id"]]
    out["z_max"] = max(max(new_z.values(), default=0), out["z_max"])
    groups_map = []
    for g in groups:
        zs = [new_z[m] for m in g["members"]]
        groups_map.append({"id": g["id"], "members": list(g["members"]),
                           "z_lo": min(zs), "z_hi": max(zs)})
    out["edit_groups"] = groups_map