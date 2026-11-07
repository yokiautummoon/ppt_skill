# -*- coding: utf-8 -*-
"""test_anim_group.py — 声明式动画组（性质①：JAnim 时间区段组合语义移植）单测。

覆盖：succession 链首尾相接 / aligned 对齐 / group 联合 / 嵌套合成 / block
锚定排序 / 锚点最长与链尾漂移的 delay 补偿与降级 / 校验负例（组谱系/成员
存在/容器拦截/自带时序/重复） / spec_compile 两模式接入（顶层+多页+多页
顶层拦截） / ir_builder 展开（timeline/sequence/成员改写）。无 Office。
运行：win_py -X utf8 tests/test_anim_group.py
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
import anim_group as AG
import spec_compile as SC
import ir_builder


def _el(i, d=0.5):
    return {"id": i, "animation": {"behaviors": [{"type": "filter", "dur": d,
                                                  "reveal": True}]}}


def _els(*ids):
    return [_el(i) for i in ids]


# ---------- 展开代数 ----------

def test_succession_back_to_back():
    anim = {"mode": "succession", "trigger": "on_click", "start": 0.3, "gap": 0.2,
            "items": [{"id": "a"}, {"id": "b"}, {"id": "c"}]}
    leaves, seq, _b, viol = AG.expand_group(anim, _els("a", "b", "c"))
    assert not viol, viol
    assert seq == ["a", "b", "c"]
    by = {r["id"]: r for r in leaves}
    assert by["a"]["start"] == 0.3 and by["a"]["trigger"] == "on_click"
    assert abs(by["a"]["delay"] - 0.3) < 1e-6            # 根链首 delay = start
    # 首尾相接：b.start == a.end + gap；c.start == b.end + gap（EPS 内）
    assert abs(by["b"]["start"] - (by["a"]["end"] + 0.2)) < 1e-6
    assert abs(by["c"]["start"] - (by["b"]["end"] + 0.2)) < 1e-6
    assert by["b"]["trigger"] == "after_previous" and by["c"]["trigger"] == "after_previous"
    assert abs(by["b"]["delay"] - 0.2) < 1e-6
    assert not any(r["delay"] < 0 for r in leaves)


def test_aligned_same_start():
    anim = {"mode": "aligned", "start": 0.5, "items": [{"id": "p"}, {"id": "q"},
                                                       {"id": "r"}]}
    leaves, _seq, _b, viol = AG.expand_group(anim, _els("p", "q", "r"))
    assert not viol, viol
    for r in leaves:
        assert abs(r["start"] - 0.5) < 1e-6, r       # 对齐块全同 start
    by = {r["id"]: r for r in leaves}
    assert by["p"]["delay"] == 0.5                    # 根首 delay = start
    assert by["q"]["delay"] == 0.0 and by["r"]["delay"] == 0.0


def test_group_block_anchor_and_delay_compensation():
    """锚点成员恰为块内最长者（块末 ≠ 块 end 代表）→ 父链下叶 delay 补偿。"""
    els = [_el("a", 0.5), _el("x", 1.6), _el("y", 0.8), _el("c", 0.5)]
    anim = {"mode": "succession", "gap": 0.2, "items": [
        {"id": "a"}, {"mode": "group", "items": [{"id": "x"}, {"id": "y"}]},
        {"id": "c"}]}
    leaves, seq, _b, viol = AG.expand_group(anim, els)
    assert not viol, viol
    assert seq == ["a", "x", "y", "c"]                # 锚点 x 首位（after_previous）
    by = {r["id"]: r for r in leaves}
    assert abs(by["y"]["start"] - by["x"]["start"]) < 1e-6   # 块内对齐
    block_end = max(by["x"]["end"], by["y"]["end"])
    assert abs(by["c"]["start"] - (block_end + 0.2)) < 1e-6
    # y 为块末（end 0.7+0.8=1.5 < block_end 2.3）→ c 锚定 y.end，delay 补偿漂移
    assert abs(by["c"]["delay"] - (block_end + 0.2 - by["y"]["end"])) < 1e-6
    assert not any(r["delay"] < 0 for r in leaves)


def test_chain_tail_in_aligned_root_degrade():
    """aligned 根内嵌 succession 链，链尾 start 漂移出对齐 → after_previous
    负 delay 自动降级 with_previous（绝对时间轴不变）。"""
    els = [_el("i", 0.4), _el("j", 0.7), _el("k", 0.5), _el("m", 0.9)]
    anim = {"mode": "aligned", "items": [
        {"mode": "succession", "gap": 0.1, "items": [{"id": "i"}, {"id": "j"}]},
        {"mode": "group", "items": [{"id": "k"}, {"id": "m"}]}]}
    leaves, seq, _b, viol = AG.expand_group(anim, els)
    assert not viol, viol
    by = {r["id"]: r for r in leaves}
    assert abs(by["i"]["end"] - 0.4) < 1e-6
    assert abs(by["j"]["start"] - 0.5) < 1e-6          # 链 i→j 接续（0.4+0.1）
    assert by["j"]["trigger"] == "with_previous"       # 降级（前驱 m.end 0.9 > 0.5）
    assert abs(by["j"]["delay"] - 0.5) < 1e-6          # 锚定前驱 m.start=0 → 0.5
    assert abs(by["j"]["end"] - 1.2) < 1e-6
    assert not any(r["delay"] < 0 for r in leaves)
    # 时间轴单调（AddEffect 序 = start 升序）
    assert all(leaves[i]["start"] <= leaves[i + 1]["start"] + 1e-6
               for i in range(len(leaves) - 1))


def test_no_delay_negative_across_scenarios():
    from itertools import product
    groups = (
        {"mode": "succession", "gap": 0.2, "items": [{"id": "a"}, {"id": "b"}]},
        {"mode": "aligned", "items": [{"id": "a"}, {"id": "b"}]},
        {"mode": "group", "items": [{"id": "a"}, {"id": "b"}]},
        {"mode": "succession", "items": [
            {"mode": "aligned", "items": [{"id": "a"}, {"id": "b"}]},
            {"id": "c"}]},
        {"mode": "aligned", "items": [
            {"id": "a"}, {"mode": "group", "items": [{"id": "b"}, {"id": "c"}]}]},
    )
    for g in groups:
        n = len("abc") if False else _ids_count(g)
        els = [_el(chr(97 + i), 0.3 + 0.3 * i) for i in range(n)]
        _leaves, _s, _b, viol = AG.expand_group(g, els)
        assert not viol, (g, viol)
        assert all(r["delay"] >= -1e-9 for r in _leaves), (g, [(r["id"], r["delay"]) for r in _leaves])


def _ids_count(g):
    s = {"ids": set()}

    def walk(n):
        for it in n["items"]:
            if "id" in it:
                s["ids"].add(it["id"])
            else:
                walk(it)
    walk(g)
    return len(s["ids"])


# ---------- 校验负例 ----------

def test_check_rejects():
    def neg(anim, els, kw):
        try:
            AG.check_anim_groups(anim, {e["id"]: e for e in els}, "anim")
            assert False, f"未拦截: {kw}"
        except AG.AgError:
            pass
    neg({"mode": "boom", "items": [{"id": "a"}]}, _els("a"), "未知 mode")
    neg({"trigger": "hover", "items": [{"id": "a"}]}, _els("a"), "非法 trigger")
    neg({"start": -1, "items": [{"id": "a"}]}, _els("a"), "负 start")
    neg({"gap": -0.5, "items": [{"id": "a"}]}, _els("a"), "负 gap")
    neg({"items": []}, _els("a"), "空 items")
    neg({"items": [{"id": "nope"}]}, _els("a"), "成员不存在")
    neg({"items": [{"id": "a"}]}, [{"id": "a"}], "成员无 animation")
    neg({"items": [{"id": "a"}]},
        [_el("a") | {"animation": {"effect": "进入动画_快速淡入", "trigger": "on_click"}}],
        "成员自带 trigger")
    neg({"items": [{"id": "a"}, {"id": "a"}]}, _els("a"), "成员重复")
    neg({"mode": "aligned", "items": [
        {"mode": "group", "trigger": "on_click", "items": [{"id": "a"}]}]},
        _els("a"), "嵌套组带 trigger")
    container = {"id": "st", "type": "stack", "rect": [0, 0, 2, 2],
                 "children": [{"id": "c1", "type": "text", "rect": [0, 0, 1, 1],
                               "text": "x"}]}
    neg({"items": [{"id": "st"}]}, [container], "容器为组员")
    cyl = {"id": "cy", "type": "shape", "kind": "cylinder", "rect": [0, 0, 2, 2],
           "text": "c", "animation": {"effect": "进入动画_快速淡入"}}
    neg({"items": [{"id": "cy"}]}, [cyl], "cylinder 为组员")


# ---------- spec_compile 接入 ----------

def _tpl(elements, extra=None, meta=None):
    d = {"meta": dict(meta or {}) or {"title": "t", "slide": {"w": 13.333, "h": 7.5}},
         "elements": elements}
    if extra:
        d.update(extra)
    return d


def _animspec(elements, anim, is_multi=False):
    d = _tpl(elements)
    if is_multi:
        d = {"meta": {"title": "t", "slide": {"w": 13.333, "h": 7.5}, "slides": [{
            "title": "p1", "elements": elements, "anim": anim}]}}
    else:
        d["anim"] = anim
    return d


_LINE = {"id": "ln", "type": "line", "x1": 0, "y1": 0, "x2": 1, "y2": 1}


def test_spec_compile_single_anim():
    els = [_el_a("card1"), _el_a("card2")]
    ok = SC.compile_spec(SC.load_yaml(_yaml(_animspec(els, {
        "mode": "succession", "gap": 0.3, "items": [{"id": "card1"}, {"id": "card2"}]}))))
    assert ok["anim"]["mode"] == "succession"
    assert ok["slides"][0]["anim"]["mode"] == "succession"


def test_spec_compile_multi_anim():
    els = [_el_a("card1"), _el_a("card2")]
    d = _animspec(els, {"mode": "aligned", "items": [{"id": "card1"}, {"id": "card2"}]},
                  is_multi=True)
    ok = SC.compile_spec(SC.load_yaml(_yaml(d)))
    assert ok["slides"][0]["anim"]["mode"] == "aligned"


def test_spec_compile_multi_top_anim_blocked():
    d = dict(_animspec([_el_a("c1")], {"items": [{"id": "c1"}]}))
    d["meta"]["slides"] = [{"title": "p", "elements": d["elements"]}]
    try:
        SC.compile_spec(SC.load_yaml(_yaml(d)))
        assert False, "多页模式顶层 anim 未拦截"
    except SC.SpecCompileError as ex:
        assert "anim" in str(ex)


def test_spec_compile_anim_reject_container():
    els = [{"id": "st", "type": "stack", "rect": [0, 0, 3, 3],
            "children": [{"id": "c1", "type": "text", "rect": [0, 0, 1, 1],
                          "text": "x"}]}, _el_a("card")]
    anim = {"mode": "succession", "items": [{"id": "st"}, {"id": "card"}]}
    try:
        SC.compile_spec(SC.load_yaml(_yaml(_animspec(els, anim))))
        assert False, "容器组员未拦截"
    except SC.SpecCompileError as ex:
        assert "容器" in str(ex)


def test_spec_compile_bad_anim_syntax():
    d = dict(_animspec([_el_a("c1")], {"mode": "succession", "items": [{"id": "c1"}]}))
    d["anim"]["start"] = False
    try:
        SC.compile_spec(SC.load_yaml(_yaml(d)))
        assert False, "bool start 未拦截"
    except SC.SpecCompileError:
        pass


def _el_a(i):
    e = _el(i)
    e["type"] = "shape"
    e["kind"] = "rounded_rect"
    e["rect"] = [0.5, 0.5, 3.0, 1.5]
    return e


def _yaml(d):
    import yaml
    return yaml.safe_dump(d, allow_unicode=True, sort_keys=False)


# ---------- ir_builder 展开 ----------

def test_ir_expansion():
    els = [_el_a("card1"), _el_a("card2"), {"id": "plain", "type": "text",
                                            "rect": [1, 1, 2, 1], "text": "x"}]
    compiled = _animspec(els, {"mode": "succession", "gap": 0.25,
                               "items": [{"id": "card1"}, {"id": "card2"}]})
    compiled = SC.compile_spec(SC.load_yaml(_yaml(compiled)))
    page = compiled["slides"][0]
    ir = ir_builder.build_ir(page)
    tl = ir["anim_timeline"]
    assert ir["anim_sequence"] == ["card1", "card2"]
    assert len(tl) == 2 and not [r for r in tl if r["trigger"] not in
                                 ("with_previous", "after_previous", "on_click")]
    by = {e["id"]: e for e in ir["elements"]}
    assert by["card1"]["animation"]["trigger"] == tl[0]["trigger"]
    assert abs(by["card1"]["animation"]["delay"] - tl[0]["delay"]) < 1e-6
    assert abs(by["card2"]["animation"]["delay"] - tl[1]["delay"]) < 1e-6
    # 组外元素 plain 无 animation → 不受影响
    assert "animation" not in by["plain"]


if __name__ == "__main__":
    fns = (test_succession_back_to_back, test_aligned_same_start,
           test_group_block_anchor_and_delay_compensation,
           test_chain_tail_in_aligned_root_degrade,
           test_no_delay_negative_across_scenarios, test_check_rejects,
           test_spec_compile_single_anim, test_spec_compile_multi_anim,
           test_spec_compile_multi_top_anim_blocked,
           test_spec_compile_anim_reject_container,
           test_spec_compile_bad_anim_syntax, test_ir_expansion)
    fails = 0
    for fn in fns:
        try:
            fn()
            print(f"[OK] {fn.__name__}")
        except AssertionError as ex:
            fails += 1
            print(f"[FAIL] {fn.__name__}: {ex}")
        except Exception as ex:
            fails += 1
            print(f"[FAIL] {fn.__name__}: {type(ex).__name__}: {ex}")
    print(f"== anim_group：{len(fns) - fails} 通过 / {fails} 失败 ==")
    sys.exit(1 if fails else 0)