# -*- coding: utf-8 -*-
"""test_deck_rules.py — 批次 1（A1/A2/A3）契约测试，无需 Office。

覆盖：
  A2 富文本：解析 / 嵌套 / 空标记与未闭合拒绝 / 编译期拦截 / IR plain+runs /
             表格 cell_runs / graph 节点与边标签 runs / 渲染+物证全链
  A2 排版断言：强调密度 / 标题字数 / 正文密度 / 标题字号下限
  A1 版式多样性：同质页命中 / 多样页放行 / 页型页以 intent:变体 签名参与
              （堵盲区）+ 变体族 capabilities 对齐 / plan 轮换
  A3 量化规范：styleguides.QUANTITATIVE 键与 params 阈值对齐

用法：win_py -X utf8 -W ignore tests/test_deck_rules.py
退出码：0 全过；1 有失败。
"""
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))

import richtext as RT
import spec_compile as SC
import ir_builder as IB
import intents as IN
import capabilities as CAP
import params as P
import verify as V
import styleguides as SG
import build_ppt as BP
import render_pptx as RP
import render_check_xml as RC

_pass, _fail = [], []


def ok(name, cond, detail=""):
    if cond:
        _pass.append(name)
        print("[OK] %s%s" % (name, (" · " + detail) if detail else ""))
    else:
        _fail.append(name)
        print("[FAIL!] %s · %s" % (name, detail))


def _spec(elements, meta=None):
    m = {"title": "t", "slide": {"w": 13.333, "h": 7.5}}
    m.update(meta or {})
    return SC.compile_spec({"meta": m, "palette": {}, "elements": elements})


def _ir(compiled):
    return IB.build_ir(compiled, P.resolve(compiled.get("meta", {}).get("params")))


def _report(ir, p=None):
    p = p or P.resolve(None)
    return V.Report(ir, {}, p)


def _fails(rep, fam="S"):
    return [(n, d) for f, n, ok_, d in rep.checks if f == fam and not ok_]


def main():
    # ================= A2 富文本解析 =================
    segs = RT.parse("普通**加粗**，[[强调]]，**[[双]]**")
    ok("A2 解析段数", len(segs) == 6, "segs=%s" % segs)
    ok("A2 加粗段", any(s["text"] == "加粗" and s["bold"] and not s["emph"]
                     for s in segs))
    ok("A2 强调段", any(s["text"] == "强调" and s["emph"] and not s["bold"]
                     for s in segs))
    ok("A2 嵌套", any(s["text"] == "双" and s["bold"] and s["emph"] for s in segs))
    ok("A2 plain", RT.plain("a**b**[[c]]") == "abc")

    # 公式段：同一行 = 行内式；独占一行 = 显示式（PowerPoint 原生同形）
    p_in = RT.paragraphs(RT.parse("面积 {{x^2+y^2=1}} 单位"))
    p_disp = RT.paragraphs(RT.parse("前文\n{{a/b}}\n后文"))
    p_two = RT.paragraphs(RT.parse("{{a}}{{b}}"))
    ok("A2 公式行内切段",
       len(p_in) == 1 and [s.get("display") for s in p_in[0]
                           if "formula" in s] == [False], str(p_in))
    ok("A2 公式独占段切段",
       len(p_disp) == 3
       and [s.get("display") for s in p_disp[1]
            if "formula" in s] == [True], str(p_disp))
    ok("A2 相邻公式同行切段",
       len(p_two) == 1
       and [s.get("display") for s in p_two[0]
            if "formula" in s] == [False, False], str(p_two))

    bad = ["**未闭合", "[[未闭合", "****", "[[]]", "[[a[[b]]]]", "**a[[b**c]]"]
    for i, s in enumerate(bad):
        try:
            RT.parse(s)
            ok("A2 拒绝 %d" % i, False, "实为放行: %r" % s)
        except RT.RichTextError:
            ok("A2 拒绝 %d" % i, True)

    # ================= 编译期拦截 =================
    try:
        _spec([{"id": "t1", "type": "text", "rect": [0.8, 0.8, 11, 1],
                "text": "**坏的"}])
        ok("A2 编译期拦截", False, "未抛 SpecCompileError")
    except SC.SpecCompileError as ex:
        ok("A2 编译期拦截", "富文本" in str(ex), str(ex)[:60])

    # ================= IR plain + runs =================
    c = _spec([{"id": "t1", "type": "text", "rect": [0.8, 0.8, 11, 1],
                "text": "a**b**[[c]]"}])
    ir = _ir(c)
    e = next(x for x in ir["elements"] if x["id"] == "t1")
    ok("A2 IR plain", e["text"] == "abc", repr(e["text"]))
    ok("A2 IR runs", e.get("runs") == [
        {"text": "a", "bold": False, "emph": False},
        {"text": "b", "bold": True, "emph": False},
        {"text": "c", "bold": False, "emph": True}], "runs=%s" % e.get("runs"))

    # 表格 cell_runs
    c = _spec([{"id": "tb", "type": "table", "rect": [0.8, 0.8, 11, 2],
                "data": [["**指标**", "值"], ["**营收**", "[[12%]]"]]}])
    ir = _ir(c)
    tb = next(x for x in ir["elements"] if x["id"] == "tb")
    ok("A2 表格 plain", tb["data"][0][0] == "指标" and tb["data"][1][1] == "12%")
    ok("A2 表格 cell_runs", tb.get("cell_runs") is not None
       and tb["cell_runs"][0][0][0]["bold"] is True
       and tb["cell_runs"][1][1][0]["emph"] is True)

    # graph 节点 + 边标签
    c = _spec([{"id": "g", "type": "graph", "rect": [0.8, 0.8, 8.0, 3.0],
                "nodes": [{"id": "a", "kind": "src", "text": "**开始**"},
                          {"id": "b", "kind": "proc", "text": "[[处理]]"}],
                "edges": [{"from": "a", "to": "b", "label": "[[是]]"}]}])
    ir = _ir(c)
    node_a = next(x for x in ir["elements"] if x["id"] == "a")
    node_b = next(x for x in ir["elements"] if x["id"] == "b")
    ok("A2 graph 节点 runs", node_a.get("runs") and node_a["runs"][0]["bold"]
       and node_b.get("runs") and node_b["runs"][0]["emph"])
    ok("A2 graph 边标签 runs", any(x.get("runs") and any(
        s["text"] == "是" and s["emph"] for s in x["runs"])
        for x in ir["elements"]))

    # ================= A2 排版断言 =================
    p = P.resolve(None)
    ir = {"elements": [
        {"id": "title", "type": "text", "text": "字" * 17,
         "text_layout": {"fs": 20}},
        {"id": "body", "type": "text", "text": "文" * 221,
         "runs": [{"text": "x", "emph": True}] * 5},
    ]}
    rep = _report(ir, p)
    V._s_typography(rep, p)
    names = {n for f, n, ok_, d in rep.checks if f == "S" and not ok_}
    ok("A2 标题字数断言", any("标题字数" in n for n in names), str(sorted(names)))
    ok("A2 正文密度断言", any("正文字数" in n for n in names))
    ok("A2 强调密度断言", any("每页强调" in n for n in names))

    ir_ok = {"elements": [
        {"id": "title", "type": "text", "text": "字" * 16,
         "text_layout": {"fs": 20}},
        {"id": "body", "type": "text", "text": "文" * 220,
         "runs": [{"text": "x", "emph": True}] * 4},
    ]}
    rep = _report(ir_ok, p)
    V._s_typography(rep, p)
    ok("A2 阈值边界放行", not _fails(rep), str(_fails(rep)))

    p2 = P.resolve(None)
    p2["verify"]["typography"]["title_fs_min"] = 24
    rep = _report(ir_ok, p2)
    V._s_typography(rep, p2)
    ok("A2 标题字号下限", any("标题字号" in n for f, n, ok_, d in rep.checks
                          if f == "S" and not ok_))

    # ================= A1 版式多样性 =================
    def page(rects, intent=None, variant=None):
        els = [{"id": "title", "type": "text", "rect": [0.8, 0.6, 11, 0.8]}]
        for i, r in enumerate(rects):
            els.append({"id": "b%d" % i, "type": "shape", "kind": "rect",
                        "rect": r})
        meta = {"slide": {"w": 13.333, "h": 7.5}}
        if intent:
            meta["page_intent"] = intent
            if variant:
                meta[intent] = {"variant": variant}
        return {"meta": meta, "elements": els}

    same = [page([[0.8, 2.0, 11.7, 4.5]]) for _ in range(5)]
    hits = V.check_layout_variety(same, p)
    ok("A1 同质命中", any(name == "版式多样性" for _, name, _ in hits)
       and any(name == "版式同质" for _, name, _ in hits),
       "hits=%s" % [(pi, n) for pi, n, _ in hits])

    varied = [page([r]) for r in (
        [0.8, 2.0, 11.7, 4.5],          # 全幅
        [0.8, 2.0, 5.6, 4.5],           # 左半
        [6.9, 2.0, 5.6, 4.5],           # 右半
        [0.8, 2.0, 11.7, 2.0],          # 上横
        [0.8, 4.5, 11.7, 2.0],          # 下横
    )]
    ok("A1 多样放行", not V.check_layout_variety(varied, p),
       str(V.check_layout_variety(varied, p)))

    # 页型页不再豁免（堵盲区）：同 intent 同变体重复 = 千页一面，必须被拦
    intents = [page([[0.8, 2.0, 11.7, 4.5]], intent="cover") for _ in range(6)]
    hits_i = V.check_layout_variety(intents, p)
    ok("A1 页型页同质命中", any(name == "版式多样性" for _, name, _ in hits_i)
       and any(name == "版式同质" for _, name, _ in hits_i),
       "hits=%s" % [(pi, n) for pi, n, _ in hits_i])
    # 轮换变体即换签名 → 放行（变体家族把 intent 页纳入门禁而非豁免）
    _rot = ("left", "band", "split", "left", "band", "split")
    intents_rot = [page([[0.8, 2.0, 11.7, 4.5]], intent="cover", variant=v)
                   for v in _rot]
    ok("A1 页型页轮换放行", not V.check_layout_variety(intents_rot, p),
       str(V.check_layout_variety(intents_rot, p)))

    # 少页不判
    ok("A1 少页不判", not V.check_layout_variety(same[:4], p))

    # ================= 变体家族（堵盲区） =================
    # capabilities 与 intents.FAMILIES 不漂移（单一事实源）：已实现 intent
    # 族序逐一相等；未实现（计划页型）在 caps 里为空族
    ok("变体族 capabilities 对齐",
       all(CAP.PAGE_INTENT_VARIANTS.get(k) == tuple(v)
           for k, v in IN.FAMILIES.items())
       and all(CAP.PAGE_INTENT_VARIANTS.get(k) == ()
               for k in CAP.PAGE_INTENT_VARIANTS if k not in IN.FAMILIES),
       "caps=%s fam=%s" % (CAP.PAGE_INTENT_VARIANTS, IN.FAMILIES))
    ok("变体族 cover 三变体",
       IN.variants("cover") == ["left", "band", "split"]
       and IN.default("cover") == "left", str(IN.variants("cover")))
    ok("变体族 unknown 判定",
       IN.known("section", "band") and not IN.known("section", "nope"))
    ok("变体族 resolve 缺省回退",
       IN.resolve("section", None) == "num_left"
       and IN.resolve("section", "band") == "band")
    # 内容页结构生成五样板家族（每族 ≥2 变体）
    ok("变体族 内容页样板家族",
       IN.variants("panels") == ["even", "hero_left"]
       and IN.variants("columns") == ["even", "arrow"]
       and IN.variants("kpis") == ["cards", "row", "rings"]
       and IN.variants("cards") == ["icon_top", "number", "icon_left"]
       and IN.variants("figure_text") == ["right", "left"]
       and IN.default("figure_text") == "right"
       and IN.known("cards", "icon_left") and not IN.known("cards", "nope"),
       str({k: IN.variants(k) for k in
            ("panels", "columns", "kpis", "cards", "figure_text")}))
    # 内容页家族轮换：kpis 4 页 → cards/row/rings/cards
    _pl_kpi = IN.plan([{"page_intent": "kpis"} for _ in range(4)])
    ok("变体族 内容页轮换",
       [x["variant"] for x in _pl_kpi] == ["cards", "row", "rings", "cards"],
       str([x["variant"] for x in _pl_kpi]))
    # plan：显式优先；缺省按同 intent 出现次序轮换（确定性）
    _sl = [
        {"page_intent": "cover"},                       # 缺省 → left
        {"page_intent": "section"},                     # 缺省 → num_left
        {"page_intent": "section"},                     # 缺省 → num_giant
        {"page_intent": "section", "section": {"variant": "num_left"}},  # 显式
        {"page_intent": "cover", "cover": {"variant": "split"}},         # 显式
    ]
    _pl = IN.plan(_sl)
    ok("变体族 plan 轮换+显式优先",
       [p_["variant"] for p_ in _pl]
       == ["left", "num_left", "num_giant", "num_left", "split"]
       and [p_["explicit"] for p_ in _pl] == [False, False, False, True, True],
       str([(p_["index"], p_["variant"], p_["explicit"]) for p_ in _pl]))


    # ================= A3 量化规范表 =================
    q = SG.QUANTITATIVE
    tp = P.DEFAULTS["verify"]["typography"]
    lv = P.DEFAULTS["verify"]["layout_variety"]
    ok("A3 表键完整", {"body_fs", "title_fs", "hero_fs", "line_w",
                     "saturated_fill_ratio", "max_emphasis",
                     "max_title_cjk", "max_same_layout"} <= set(q))
    ok("A3 与 params 对齐", q["max_emphasis"] == tp["max_emphasis"]
       and q["max_title_cjk"] == tp["max_title_cjk"]
       and q["max_same_layout"] == lv["max_same"])

    # ================= A2 渲染 + 物证全链 =================
    with tempfile.TemporaryDirectory() as td:
        spec = os.path.join(td, "rt.yaml")
        with open(spec, "w", encoding="utf-8") as f:
            f.write("""meta:
  title: 富文本
  style_guide: deck
  slide: {w: 13.333, h: 7.5}
  margin: {l: 0.6, t: 0.6, r: 0.6, b: 0.6}
palette: {deep: "#1F2A44"}
elements:
  - id: title
    type: text
    rect: [0.8, 0.65, 11.7, 0.5]
    text: "富文本"
    text_style: {fs: 16, align: left}
  - id: body
    type: text
    rect: [0.8, 1.4, 11.7, 1.2]
    text: "普通 **加粗** [[强调]] **[[双]]**"
    text_style: {fs: 20, align: left}
  - id: tb
    type: table
    rect: [0.8, 3.2, 11.7, 1.6]
    col_widths: [5.85, 5.85]
    data:
      - ["**指标**", "说明"]
      - ["营收", "[[12%]]"]
  - id: fx
    type: text
    rect: [0.8, 5.2, 11.7, 1.2]
    text: "行内 {{x^2+y^2=1}} 与显示式：\\n{{a/b}}"
    text_style: {fs: 18, align: left}
""")
        rc, *rest = BP._check(spec, td)
        ok("A2 全链编译", rc == 0, str(rest[0] if rc else ""))
        if rc == 0:
            compiled, pages, pg_p, irs, reps = rest
            out = os.path.join(td, "base.pptx")
            used, errs = RP.render(irs, compiled, pg_p, out,
                                   pps=[pg["_p"] for pg in pages])
            ok("A2 全链渲染", not errs, str(errs))
            checks = RC.check(out, irs[0], pages[0]["_p"], compiled["palette"])
            bad_ev = [(n, d) for n, ok_, d in checks if not ok_]
            ok("A2 全链物证", not bad_ev, str(bad_ev[:3]))
            ok("A2 物证含富文本", any("富文本" in n for n, _, _ in checks),
               "checks=%d" % len(checks))
            ok("A2 物证含公式形态", any("公式形态 fx" in n for n, _, _ in checks)
               and any("公式段数 fx" in n for n, _, _ in checks),
               "checks=%d" % len(checks))

    # 设计体检（advisory）：机器统计新版设计能力是否真的被用上
    import report as RPT
    _irs_d = [
        {"slide": (13.333, 7.5), "elements": [
            {"type": "text", "rect": [0.6, 0.6, 8, 0.8]},
            {"type": "icon", "rect": [1, 2, 1, 1]},
            {"type": "text", "rect": [1, 3, 4, 0.6],
             "runs": [{"text": "12%", "emph": True}]}]},
        {"slide": (13.333, 7.5), "elements": [
            {"type": "text", "rect": [0.6, 0.6, 8, 0.8]},
            {"type": "text", "rect": [1, 2, 6, 1]},
            {"type": "text", "rect": [1, 3, 6, 1]}]},
    ]
    _rows, _warns = RPT.design_audit(_irs_d, ["a", "b"])
    ok("设计体检 图标/强调计数",
       _rows[0]["icons"] == 1 and _rows[0]["emph"] == 1,
       "icons=%s emph=%s" % (_rows[0]["icons"], _rows[0]["emph"]))
    ok("设计体检 无视觉主体提示",
       _rows[1]["visual"] == 0 and any("无视觉主体" in t for t in _rows[1]["tips"]),
       str(_rows[1]["tips"]))
    _irs_pi = [
        {"slide": (13.333, 7.5), "page_intent": "versus", "elements": [
            {"type": "text", "rect": [0.6, 0.6, 8, 0.8]},
            {"type": "shape", "rect": [1, 2, 5, 3]},
            {"type": "shape", "rect": [7, 2, 5, 3]}]},
        {"slide": (13.333, 7.5), "elements": [
            {"type": "text", "rect": [0.6, 0.6, 8, 0.8]},
            {"type": "text", "rect": [1, 2, 6, 1]},
            {"type": "text", "rect": [1, 3, 6, 1]}]},
    ]
    _rows_pi, _ = RPT.design_audit(_irs_pi, ["a", "b"])
    ok("设计体检 页型页豁免", not _rows_pi[0]["tips"]
       and any("无视觉主体" in t for t in _rows_pi[1]["tips"]),
       "%s / %s" % (_rows_pi[0]["tips"], _rows_pi[1]["tips"]))
    # 页型意图页（versus）计为有视觉主体；纯文字页不计 → 1/2
    ok("设计体检 页型页计视觉主体",
       _rows_pi[0]["intent"] == "versus" and _rows_pi[1]["intent"] is None
       and "视觉主体 1/2 页" in RPT.format_audit(_rows_pi, []),
       RPT.format_audit(_rows_pi, []))
    ok("设计体检 有图标不提示", not any("图标" in w for w in _warns), str(_warns))
    _rows2, _warns2 = RPT.design_audit(_irs_d[1:] * 3, ["x"] * 3)
    ok("设计体检 全篇无图标警告", any("图标" in w for w in _warns2), str(_warns2))
    ok("设计体检 版式重复警告", any("版式骨架重复" in w for w in _warns2), str(_warns2))
    ok("设计体检 console 摘要", "图标 1" in RPT.format_audit(_rows, _warns),
       RPT.format_audit(_rows, _warns))

    # ---- AI 感痕迹检测（官方 pptx §Avoid 机器化；advisory）----
    _irs_ai = [
        {"slide": (13.333, 7.5), "elements": [
            {"type": "text", "rect": [0.6, 0.6, 6, 0.8], "text": "标题"},
            # ① 标题下细横条
            {"type": "shape", "rect": [0.6, 1.42, 3.0, 0.05]},
            # ③ 卡片 + 卡片单边条
            {"type": "shape", "rect": [0.6, 3.0, 4.0, 2.5]},
            {"type": "shape", "rect": [0.6, 3.1, 0.07, 2.2]},
            # ② 跨页宽头条
            {"type": "shape", "rect": [0.0, 0.0, 13.333, 0.3]},
        ]},
        # 页型意图页：同样的条被 owner 归属豁免，不报
        {"slide": (13.333, 7.5), "page_intent": "panels", "elements": [
            {"type": "shape", "rect": [0.0, 0.0, 13.333, 0.3]},
            {"type": "shape", "rect": [0.5, 3.0, 4.0, 2.5]},
            {"type": "shape", "rect": [0.5, 3.1, 0.07, 2.2]},
        ]},
    ]
    _rows_ai, _ = RPT.design_audit(_irs_ai, ["a", "b"])
    _ai_tips = " ".join(_rows_ai[0]["tips"])
    ok("AI 痕迹 标题下横条", "标题下细横条" in _ai_tips, _ai_tips)
    ok("AI 痕迹 跨页宽装饰条", "跨页宽装饰条" in _ai_tips, _ai_tips)
    ok("AI 痕迹 卡片单边条", "卡片单边强调条" in _ai_tips, _ai_tips)
    ok("AI 痕迹 页型页豁免", not _rows_ai[1]["tips"], str(_rows_ai[1]["tips"]))
    ok("AI 痕迹 全篇汇总告警", any("AI 感痕迹" in w for w in RPT.design_audit(
        _irs_ai, ["a", "b"])[1]), "warns 应含汇总条")
    # 配色平分权重（两色等量 → 无一主导）
    _pg_blue = {"slide": (13.333, 7.5), "elements": [
        {"type": "shape", "rect": [0.2, 0.2, 12.9, 7.1],
         "style": {"fill": "#2D6CDF"}}]}
    _pg_orange = {"slide": (13.333, 7.5), "elements": [
        {"type": "shape", "rect": [0.2, 0.2, 12.9, 7.1],
         "style": {"fill": "#E8590C"}}]}
    _r2, _w2 = RPT.design_audit([_pg_blue, _pg_orange], ["a", "b"])
    ok("配色平分权重告警", any("配色平分权重" in w for w in _w2), str(_w2))
    # 内容处理转换律（advisory）
    import conversion as CV
    _ch = CV.conversion_hints([
        {"slide": (13.333, 7.5), "elements": [
            {"type": "text", "rect": [1, 1, 8, 3],
             "text": "营收 120 万，增长 35%，覆盖 8 城"}]}])
    ok("转换律 3+数字提示", any("指标卡" in h for h in _ch), str(_ch))

    print("\n== 批次1 契约：%d 通过 / %d 失败 ==" % (len(_pass), len(_fail)))
    return 0 if not _fail else 1


if __name__ == "__main__":
    sys.exit(main())
