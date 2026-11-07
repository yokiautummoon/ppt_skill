# -*- coding: utf-8 -*-
"""test_capabilities.py — 能力档案注册表一致性 + 编译期 fail-closed 背书。

三张表（capabilities.py）必须与真实行为一致，否则契约就是橡皮图章：
  1. ELEMENT_CAPS    与 ELEMENT_TYPES 一一对应；容器能力全 False
  2. PAGE_INTENT_CAPS 派生常量正确；planned 页型编译即拒；有专属字段的
                     implemented 页型缺字段 dict 编译即拒
  3. COMPONENT_CONTRACTS required 满减 → 编译必报错；invariants 子串在
                     verify.py 源码在场；renderer 模块在 scripts/ 真实存在

用法：win_py -X utf8 tests/test_capabilities.py
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "scripts"))

import capabilities as CAP
import spec_compile as SC

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


def _compile_error(spec):
    """编译并返回 (成功?, 异常消息)。"""
    try:
        SC.compile_spec(spec)
        return False, ""
    except SC.SpecCompileError as ex:
        return True, str(ex)
    except Exception as ex:  # 非 SpecCompileError 崩溃也算失败
        _fail.append(f"非 SpecCompileError 崩溃: {type(ex).__name__} {ex}")
        return True, str(ex)


def _slides_spec(slides):
    return {"meta": {"title": "t", "style_guide": "deck",
                     "slide": {"w": 13.333, "h": 7.5},
                     "margin": {"l": 0.5, "t": 0.5, "r": 0.5, "b": 0.5},
                     "slides": slides},
            "palette": {"p": "#1F2A44"}}


def _single_spec(elements):
    return {"meta": {"title": "t", "style_guide": "deck",
                     "slide": {"w": 13.333, "h": 7.5},
                     "margin": {"l": 0.5, "t": 0.5, "r": 0.5, "b": 0.5}},
            "palette": {"p": "#1F2A44"},
            "elements": elements}


def main():
    # ---- 表 1：ELEMENT_CAPS 完整性与容器能力归零 ----
    _check(set(SC.ELEMENT_TYPES) == set(CAP.ELEMENT_CAPS),
           "元素类型 ↔ 能力表一一对应",
           f"缺 {sorted(SC.ELEMENT_TYPES - set(CAP.ELEMENT_CAPS))} / "
           f"多 {sorted(set(CAP.ELEMENT_CAPS) - SC.ELEMENT_TYPES)}")
    for t in CAP.ELEMENT_CAPS:
        for ability in ("shape_producing", "animatable", "linkable",
                        "edit_group_member", "anchorable"):
            if ability not in CAP.ELEMENT_CAPS[t]:
                _fail.append(f"{t} 缺能力键 {ability}")
                print(f"[FAIL!] {t} 缺能力键 {ability}")
    _check(CAP.supports("stack", "shape_producing") is False
           and CAP.supports("dock", "shape_producing") is False
           and CAP.supports("graph", "shape_producing") is False,
           "容器 shape_producing 归零")
    for t in ("stack", "dock", "graph"):
        for a in ("animatable", "linkable", "edit_group_member", "anchorable"):
            _check(CAP.supports(t, a) is False,
                   f"{t} 能力 {a} = False（容器不产单形状）")
    _check(tuple(sorted(CAP.CONTAINER_TYPES)) == ("dock", "graph", "stack"),
           "CONTAINER_TYPES 恰为三容器")

    # ---- 表 1 fail-closed：anchors 能力级拒收 / 合法放行 ----
    ok, msg = _compile_error(_single_spec([{"id": "s", "type": "stack",
                                            "rect": [1, 1, 4, 2],
                                            "anchors": {"a": [.5, .5]},
                                            "children": [{"id": "k", "type": "shape",
                                                          "kind": "rounded_rect",
                                                          "width": 1, "height": 1}]}]))
    _check(ok and "anchors" in msg, "容器声明 anchors 编译拒（fail-closed）", msg[:80])
    ok, msg = _compile_error(_single_spec([{"id": "ln", "type": "line",
                                            "rect": [1, 1, 2, 0],
                                            "x1": 1, "y1": 1, "x2": 3, "y2": 1,
                                            "anchors": {"a": [.5, .5]}}]))
    _check(ok and "anchors" in msg, "线声明 anchors 编译拒（缺锚定语义）", msg[:80])
    ok, _ = _compile_error(_single_spec([{"id": "t1", "type": "text",
                                          "rect": [1, 1, 2, 1], "text": "x",
                                          "anchors": {"a": [.5, .5]}}]))
    _check(not ok, "text anchors 合法放行（可锚定 rect 的单形状）")

    # ---- 表 1 fail-closed：top_level_only ----
    ok, msg = _compile_error(_single_spec([{"id": "s", "type": "stack",
                                            "rect": [1, 1, 6, 4],
                                            "children": [{"id": "tb", "type": "table",
                                                          "data": [["a"]]}]}]))
    _check(ok and "顶层元素" in msg, "top_level_only 类型进 children 编译拒", msg[:60])
    for t in ("table", "chart", "typst"):
        _check(CAP.supports(t, "top_level_only"), f"{t} top_level_only=True")

    # ---- 表 2：PAGE_INTENT_CAPS 派生与 fail-closed ----
    _check(SC.PAGE_INTENTS == set(CAP.PAGE_INTENT_CAPS), "PAGE_INTENTS 由注册表派生")
    _check(SC.PAGE_INTENT_FIELDS == CAP.PAGE_INTENT_FIELDS,
           "PAGE_INTENT_FIELDS 由注册表派生")
    _check(SC.PAGE_INTENT_EL_IDS == CAP.PAGE_INTENT_EL_IDS,
           "PAGE_INTENT_EL_IDS 由注册表派生")
    _check("cover" in CAP.PAGE_INTENTS_IMPLEMENTED
           and "section" in CAP.PAGE_INTENTS_IMPLEMENTED
           and "content" in CAP.PAGE_INTENTS_IMPLEMENTED,
           "implemented 集合含 cover/section/content")
    for sci in ("problem", "versus", "route"):
        _check(sci in CAP.PAGE_INTENTS_IMPLEMENTED,
               f"科研页型 {sci} implemented（C1）")
    for planned in ("data", "compare", "conclusion", "quote"):
        ok, msg = _compile_error(_slides_spec([{"title": "x", "page_intent": planned}]))
        _check(ok and "尚未落地" in msg, f"planned 页型 {planned} 编译拒", msg[:70])
    ok, msg = _compile_error(_slides_spec([{"title": "x", "page_intent": "cover"}]))
    _check(ok and "必须声明" in msg, "cover 缺字段 dict 编译拒（fail-closed）", msg[:70])
    ok, _ = _compile_error(_slides_spec([{"title": "c", "page_intent": "cover",
                                          "cover": {"title": "T"}}]))
    _check(not ok, "cover 完整声明合法放行")

    # ---- 表 3：COMPONENT_CONTRACTS 一致性 ----
    # 3a renderer 模块真实存在
    missing = CAP.renderer_modules_exist(os.path.join(ROOT, "scripts"))
    _check(not missing, "renderer 模块全部存在", f"缺 {sorted(missing)}")
    # 3b invariants 子串在 verify.py 源码在场（背书不是空话）
    vp = os.path.join(ROOT, "scripts", "verify.py")
    vsrc = open(vp, encoding="utf-8").read()
    for cid, c in CAP.COMPONENT_CONTRACTS.items():
        for sub, desc in c.get("invariants") or []:
            _check(sub in vsrc, f"契约 {cid} 背书断言在场 [{sub}]",
                   desc if sub in vsrc else "verify.py 缺该断言!")
    # 3b2 文档同步：人读版 component-contracts.md 覆盖全部契约 id
    doc_path = os.path.join(ROOT, "references", "component-contracts.md")
    _check(os.path.isfile(doc_path), "component-contracts.md 存在")
    cdoc = open(doc_path, encoding="utf-8").read() if os.path.isfile(doc_path) else ""
    for cid in CAP.COMPONENT_CONTRACTS:
        _check(f"`{cid}`" in cdoc, f"契约文档覆盖 {cid}", "表格行在场")
    # 3c required 满减 → 编译必报错（最小合法 SPEC 逐字段摘除）
    def spec_for(cid):
        if cid == "cover":
            return _slides_spec([{"title": "c", "page_intent": "cover",
                                  "cover": {"title": "T"}}])
        if cid == "section":
            return _slides_spec([{"title": "s", "page_intent": "section",
                                  "section": {"num": "01", "title": "T"}}])
        if cid == "problem":
            return _slides_spec([{"title": "p", "page_intent": "problem",
                                  "problem": {"title": "T"}}])
        if cid == "versus":
            return _slides_spec([{"title": "v", "page_intent": "versus",
                                  "versus": {"left_title": "A", "right_title": "B"}}])
        if cid == "route":
            return _slides_spec([{"title": "r", "page_intent": "route",
                                  "route": {"stages": ["一", "二"]}}])
        if cid == "panels":
            return _slides_spec([{"title": "p", "page_intent": "panels",
                                  "panels": {"title": "T", "items": ["a"]}}])
        if cid == "columns":
            return _slides_spec([{"title": "c", "page_intent": "columns",
                                  "columns": {"title": "T", "cols": ["a"]}}])
        if cid == "kpis":
            return _slides_spec([{"title": "k", "page_intent": "kpis",
                                  "kpis": {"title": "T",
                                           "items": [{"value": "1", "label": "L"}]}}])
        if cid == "cards":
            return _slides_spec([{"title": "c", "page_intent": "cards",
                                  "cards": {"title": "T", "items": ["a"]}}])
        if cid == "figure_text":
            return _slides_spec([{"title": "f", "page_intent": "figure_text",
                                  "figure_text": {"title": "T", "blocks": ["a"]}}])
        base = {"id": "x", "rect": [1.0, 1.0, 5.0, 3.0]}
        if cid == "cylinder":
            base.update(type="shape", kind="cylinder")
        elif cid == "curve":
            base.update(type="curve", points=[[0, 0], [0.5, 1], [1, 0]])
        elif cid == "brush":
            base.update(type="brush", text="永", font="kai")
        elif cid == "icon":
            base.update(type="icon", icon="droplet")
        elif cid == "typst":
            base.update(type="typst", typst="#text[x]")
        elif cid == "table":
            base.update(type="table", data=[["a"], ["b"]])
        elif cid == "chart":
            base.update(type="chart", chart_type="column_clustered",
                        categories=["a"], series=[{"name": "s", "values": [1]}])
        elif cid == "formula":
            base.update(type="formula", expr="a+b")
        elif cid == "stack":
            base.update(type="stack",
                        children=[{"id": "k", "type": "shape",
                                   "kind": "rounded_rect", "width": 1, "height": 1}])
        elif cid == "dock":
            base.update(type="dock",
                        children=[{"id": "k", "type": "shape",
                                   "kind": "rounded_rect", "width": 2, "height": 1,
                                   "dock": "top"}])
        elif cid == "graph":
            base.update(type="graph", orientation="horizontal",
                        nodes=[{"id": "n1", "title": "A"}],
                        edges=[{"from": "n1", "to": "n1"}])
        return _single_spec([base])

    for cid, c in CAP.COMPONENT_CONTRACTS.items():
        want = list(c["required"])
        is_pi = c.get("kind") == "page_intent"
        if len(want) == 1:
            _check(True, f"契约 {cid} required={want[0]}（单键）")
            ok, msg = _compile_error(spec_for(cid))
            _check(not ok, f"契约 {cid} 完整 SPEC 合法", msg[:60] if not ok else "")
            spec = spec_for(cid)
            if is_pi:
                spec["meta"]["slides"][0].pop(want[0], None)
            else:
                spec["elements"][0].pop(want[0], None)
            ok, msg = _compile_error(spec)
            _check(ok, f"契约 {cid} 摘除 {want[0]} 编译拒", msg[:60])
        else:
            for fk in want:
                spec = spec_for(cid)
                if is_pi:
                    spec["meta"]["slides"][0].pop(fk, None)
                else:
                    spec["elements"][0].pop(fk, None)
                ok, msg = _compile_error(spec)
                _check(ok, f"契约 {cid} 摘除 {fk} 编译拒", msg[:60])

    # ---- 表 4：THEME_CAPS 漂移断言（事实源 themes.py）----
    import themes as TH
    vsrc4 = open(vp, encoding="utf-8").read()
    _src_of = {"structure": TH.STRUCTURES, "motif": TH.MOTIFS,
               "font_pair": TH.PAIRINGS}
    for key, c in CAP.THEME_CAPS.items():
        _check(tuple(_src_of[key]) == c["options"],
               f"THEME_CAPS {key} 选项与 themes.py 一致", f"{c['options']}")
        for sub, desc in c.get("invariants") or []:
            _check(sub in vsrc4, f"THEME_CAPS {key} 背书断言在场 [{sub}]", desc)
    _check(set(CAP.THEME_PRESETS) == set(TH.PRESETS),
           "THEME_PRESETS 与 themes.PRESETS 一致",
           f"差 {set(CAP.THEME_PRESETS) ^ set(TH.PRESETS)}")

    print(f"---\npass={len(_pass)} fail={len(_fail)}")
    if _fail:
        print("FAILED:", *_fail, sep="\n  ")
        raise SystemExit(1)


if __name__ == "__main__":
    main()