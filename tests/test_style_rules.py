# -*- coding: utf-8 -*-
"""test_style_rules.py — 块 3 单测：styleguides 可选键 size_fs_floor /
labels_follow 的 verify 消费（不启用 = 零检查；启用 = 按尺寸/组织断言）。

用法：win_py -X utf8 tests/test_style_rules.py
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "scripts"))

import verify as V
from verify import Report


def _mk_ir():
    return {
        "slide": (13.333, 7.5), "margin": {"l": 0.5, "t": 0.5, "r": 0.5, "b": 0.5},
        "elements": [
            {"id": "big", "type": "text", "rect": (1.0, 1.0, 4.0, 1.0),
             "text": "大", "text_layout": {"fs": 20, "lines": 1, "need_h": 28}},
            {"id": "tiny", "type": "text", "rect": (1.0, 3.0, 0.8, 0.5),
             "text": "小", "text_layout": {"fs": 8, "lines": 1, "need_h": 11}},
            {"id": "chip", "type": "shape", "kind": "rounded_rect",
             "rect": (6.0, 1.0, 2.0, 0.3), "style": {"fill": "#1F2A44"},
             "text": "芯片", "text_layout": {"fs": 7, "lines": 1, "need_h": 10}},
            {"id": "reactor.label", "type": "text", "rect": (9.0, 1.0, 1.0, 0.4),
             "text": "反应器", "text_layout": {"fs": 9, "lines": 1, "need_h": 12}},
        ],
        "lines": [], "glue": [], "groups": [], "z_max": 10,
    }


P = {"verify": {"eps": 0.01}, "text": {"min_fs": 4}, "graph": {},
     "style": {"text_color": "#000000"}}

_fail = []
_pass = []


def check(name, rep, expect_bad):
    bad = bool(rep.violations)
    if bad != expect_bad:
        _fail.append(f"{name}: {'该拦没拦' if expect_bad else '误拦'} "
                     f"violations={[(f, n, d) for f, n, ok, d in rep.checks if not ok]}")
        print(f"[FAIL!] {name}")
        for fam, n, ok, d in rep.checks:
            if not ok:
                print(f"        ↳ {fam} {n}: {d}")
    else:
        print(f"[OK] {name} {'拦截 ✓' if expect_bad else '通过 ✓'}")
        _pass.append(name)


def _s(rules, ir=None, sv="t"):
    rep = Report(ir or _mk_ir(), {"elements": []}, P)
    V._s_family(rep, rules, P, sv)
    return rep


def main():
    # 缺省（无 size_fs_floor/labels_follow 键）= 零检查（0 违规）
    rep = _s({}, _mk_ir())
    check("缺省规则零检查", rep, expect_bad=False)

    # S8：小尺寸字号下限——rect 短边 < threshold(in) 且非豁免角色 → fs ≥ floor
    rules = {"size_fs_floor": {"threshold": 1.0, "fs": 12}}
    ir = _mk_ir()
    ir["elements"][2]["rect"] = (6.0, 1.0, 2.0, 0.3)   # chip 短边 0.3in < 1.0
    rep = _s(rules, ir)
    names = {n for f, n, ok, d in rep.checks}
    assert "小尺寸字号 chip ≥ 12" in names, f"S8 未产生检查: {names}"
    check("S8 小盒小号拦截", rep, expect_bad=True)    # chip fs=7 < 12 且短边 0.3in

    # S8 放行：同类元素字号已达标（tiny/chip 都提到 ≥ 12 且短边 < 1.0in）
    ir = _mk_ir()
    ir["elements"][1]["text_layout"]["fs"] = 12
    ir["elements"][2]["text_layout"]["fs"] = 14
    check("S8 小盒达标放行", _s(rules, ir), expect_bad=False)

    # S8 豁免：巨型元素（短边 ≥ threshold）不查（全部元素短边都 ≥ 1.0in）
    ir = _mk_ir()
    ir["elements"][1]["rect"] = (1.0, 3.0, 3.0, 1.2)   # 短边 1.2in ≥ 1.0
    ir["elements"][2]["rect"] = (6.0, 1.0, 2.0, 1.5)   # 短边 1.5in ≥ 1.0
    check("S8 大盒不查", _s(rules, ir), expect_bad=False)

    # S8 豁免：小字角色 id（caption 等不查）——tiny 提门槛避开干扰，新增 caption
    ir = _mk_ir()
    ir["elements"][1]["text_layout"]["fs"] = 12
    ir["elements"][2]["text_layout"]["fs"] = 14
    ir["elements"].append({"id": "n1.caption", "type": "text",
                           "rect": (1.0, 5.0, 0.6, 0.3), "text": "注",
                           "text_layout": {"fs": 6, "lines": 1, "need_h": 9}})
    check("S8 角色豁免", _s(rules, ir), expect_bad=False)

    # S9：labels_follow——顶层 .label 与顶层目标须同 edit_group（无组 → 违规）
    rules9 = {"labels_follow": True}
    ir = _mk_ir()
    ir["elements"].append({"id": "reactor", "type": "shape",
                           "kind": "rounded_rect", "rect": (10.0, 1.0, 2.0, 1.0),
                           "style": {"fill": "#1F2A44"},
                           "text_layout": {"fs": 14, "lines": 1, "need_h": 20}})
    rep = _s(rules9, ir)
    names = {n for f, n, ok, d in rep.checks}
    assert any("标签组织" in n for n in names), f"S9 未产生检查: {names}"
    check("S9 顶层标签无组拦截", rep, expect_bad=True)

    # S9 放行：同 edit_group 成员（ir 直接注入，Task 3 前即测语义）
    ir = _mk_ir()
    ir["elements"].append({"id": "reactor", "type": "shape",
                           "kind": "rounded_rect", "rect": (10.0, 1.0, 2.0, 1.0),
                           "style": {"fill": "#1F2A44"},
                           "text_layout": {"fs": 14, "lines": 1, "need_h": 20}})
    ir["edit_groups"] = [{"id": "r_eg", "members": ["reactor", "reactor.label"]}]
    check("S9 同编辑组放行", _s(rules9, ir), expect_bad=False)

    # S9 放行：容器派生标签（有 owner）天然合法——graph 边标签语义
    ir = _mk_ir()
    ir["elements"].append({"id": "g.e1.label", "type": "text",
                           "rect": (1.0, 6.0, 1.0, 0.4), "text": "边",
                           "owner": "g", "text_layout": {"fs": 8,
                                                         "lines": 1, "need_h": 11}})
    check("S9 容器标签放行", _s(rules9, ir), expect_bad=False)

    # 汇总
    print(f"---\npass={len(_pass)} fail={len(_fail)}")
    if _fail:
        print("FAILED:", *_fail, sep="\n  ")
        raise SystemExit(1)


if __name__ == "__main__":
    main()