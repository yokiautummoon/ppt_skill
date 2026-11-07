# -*- coding: utf-8 -*-
"""test_spec_fixer.py — 机械侧单测：attribution 归因分类 + spec_fixer R1–R4。

决策部件③④：归因纯函数 + 确定性机械修复（动作库默认项）。同输入必同输出。
运行：win_py -X utf8 tests/test_spec_fixer.py（无 Office 依赖）
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
import params as _P
import spec_fixer as F
from attribution import Violation, classify


class FakeRep(object):
    def __init__(self, checks):
        self.checks = checks


def test_attribution():
    CASES = [
        ("元素 t_title ⊆ 安全区", "fixable", "safety", "t_title", None),
        ("元素 t_body ⊆ slide", "fixable", "safety", "t_body", None),
        ("文本非空 t_title", "fixable", "content", "t_title", None),
        ("水平不溢出 t_body", "fixable", "autofit", "t_body", None),
        ("垂直不溢出 t_title", "fixable", "autofit", "t_title", None),
        ("min_fs 硬底 t_stamp", "fixable", "autofit", "t_stamp", None),
        ("autofit 超框标记 t_stamp", "fixable", "autofit", "t_stamp", None),
        ("遮挡 card_a↔card_b 合法来源", "fixable", "overlap", "card_a", "card_b"),
        ("遮挡 a ~ b", "fixable", "overlap", "a", "b"),
        ("节点字号 s_node", "fixable", "fontscale", "s_node", None),
        ("标签字号 s_lbl", "fixable", "fontscale", "s_lbl", None),
        ("正文字号 t_para", "fixable", "fontscale", "t_para", None),
        ("z_override 冲突 s_deco", "fixable", "zfix", "s_deco", None),
        ("表格格 (2,3) 不溢出", "fixable", "autofit", None, None),
        ("断行重算一致 t_title", "internal", "manual", "t_title", None),
        ("锚点 s_arrow 独立重算一致", "internal", "manual", "s_arrow", None),
        ("orth 折线 f1 结构", "internal", "manual", "f1", None),
        ("容器 g1 节点同高", "internal", "manual", "g1", None),
        ("组 g1 包络 ⊇ 成员", "internal", "manual", "g1", None),
        ("stack 账目[st1]", "internal", "manual", "st1", None),
        ("节点 n1 ⊆ 面板内容区", "internal", "manual", "n1", None),
        ("cover 破格度 2.4", "advisory", "manual", None, None),
        ("section 贯穿度 0.6", "advisory", "manual", None, None),
        ("配色 ⊆ 白名单", "advisory", "manual", None, None),
        ("语义色 ≤ 3", "advisory", "manual", None, None),
    ]
    for i, (name, k, act, el, peer) in enumerate(CASES):
        vs = classify(FakeRep([("X", name, False, "d")]))
        v = vs[0] if vs else None
        got = None if v is None else (v.klass, v.action, v.element, v.peer)
        assert got == (k, act, el, peer), f"[{i}] {name!r}: got {got} exp {(k, act, el, peer)}"
    # 通过项不入列；切分接口
    vs = classify(FakeRep([("G", "元素 ok ⊆ 安全区", True, "d"),
                           ("S", "文本非空 t_a", False, "d")]))
    assert len(vs) == 1
    chk = [("T", "水平不溢出 t_a", False, ""), ("S", "文本非空 t_b", False, ""),
           ("S", "配色 ⊆ 白名单", False, ""), ("I", "断行重算一致 t_d", False, "")]
    assert [v.name for v in __import__("attribution").auto_fixable(classify(FakeRep(chk)))] \
        == ["水平不溢出 t_a"]
    assert [v.name for v in __import__("attribution").llm_or_manual(classify(FakeRep(chk)))] \
        == ["文本非空 t_b", "配色 ⊆ 白名单"]


_PP = _P.resolve({})
_BASE = {"meta": {"margin": {"l": 0.5, "t": 0.5, "r": 0.5, "b": 0.5}}}


def _V(name, detail, action, el, peer=None, klass="fixable"):
    return Violation("X", name, detail, klass, action, el, peer)


def test_r1_autofit():
    # 降号优先：显式 fs=28 溢出 → 26
    revs, _ = F.fix_page({"meta": _BASE["meta"],
                          "elements": [{"id": "t_body", "type": "text", "rect": [1, 1, 8, 3],
                                        "text": "x", "text_style": {"fs": 28}}]},
                         _PP, [_V("水平不溢出 t_body", "max_w=540.0pt 框=500.0pt",
                                  "autofit", "t_body")])
    assert len(revs) == 1 and revs[0]["path"] == ("elements", 0, "text_style", "fs") \
        and revs[0]["new"] == 26 and revs[0]["old"] == 28
    # 已在硬底 + 数值 detail → 扩框（need_h 反推）
    revs, _ = F.fix_page({"meta": _BASE["meta"],
                          "elements": [{"id": "t_stamp", "type": "text", "rect": [1, 1, 2, 0.5],
                                        "text": "x", "text_style": {"fs": 4}}]},
                         _PP, [_V("垂直不溢出 t_stamp", "need_h=54.0pt 框=36.0pt",
                                  "autofit", "t_stamp")])
    assert any(r["path"][3] == 3 for r in revs), revs    # rect 高度被扩
    # 无数值 → manual（诚实边界，不盲调）
    _, audit = F.fix_page({"meta": _BASE["meta"],
                           "elements": [{"id": "t_stamp", "type": "text", "rect": [1, 1, 2, 0.5],
                                         "text": "x", "text_style": {"fs": 4}}]},
                          _PP, [_V("min_fs 硬底 t_stamp", "fs=4.0pt min=4.0pt",
                                   "autofit", "t_stamp")])
    assert any("manual" in a for a in audit), audit


def test_r2_safety():
    # 右溢出 → clamp 平移（slide 13.333，右 margin 0.5 → x ≤ 10.83）
    revs, _ = F.fix_page({"meta": _BASE["meta"],
                          "elements": [{"id": "s_a", "type": "shape", "rect": [12, 1, 2, 2]}]},
                         _PP, [_V("元素 s_a ⊆ 安全区", "rect=(12.0, 1.0, 2.0, 2.0)",
                                  "safety", "s_a")])
    assert revs[0]["path"] == ("elements", 0, "rect", 0) and revs[0]["new"] == 10.83
    # 容器 children（无显式 rect）→ manual；组包络 → manual
    _, audit = F.fix_page({"meta": {}, "elements": [{"id": "c1", "type": "shape"}]},
                          _PP, [_V("元素 c1 ⊆ 安全区", "rect=(1.0, 1.0, 0.3, 0.3)",
                                   "safety", "c1")])
    assert any("manual" in a for a in audit)
    _, audit = F.fix_page({"meta": _BASE["meta"], "elements": []},
                          _PP, [_V("组 g1 ⊆ 安全区", "", "safety", "g1")])
    assert any("manual" in a for a in audit)


def test_r3_overlap():
    sp = {"meta": {}, "elements": [{"id": "a", "type": "shape", "rect": [1, 1, 2, 2]},
                                   {"id": "b", "type": "shape", "rect": [2, 1, 2, 2]}],
          "relations": {}}
    revs, _ = F.fix_page(sp, _PP, [_V("遮挡 a↔b 合法来源", "未声明 ×", "overlap", "a", "b")])
    assert revs[0]["new"] == {"id": "a", "with": "b"} and revs[0]["path"][2] == "+"
    # 已声明 → 不重复补
    sp2 = {"meta": {}, "elements": sp["elements"],
           "relations": {"overlap": [{"id": "a", "with": "b"}]}}
    revs, audit = F.fix_page(sp2, _PP, [_V("遮挡 a↔b 合法来源", "未声明 ×", "overlap", "a", "b")])
    assert not revs and any("已有声明" in a for a in audit)


def test_r4_zfix():
    sp = {"meta": {}, "elements": [{"id": "s1", "type": "shape", "rect": [1, 1, 1, 1]},
                                   {"id": "s2", "type": "shape", "rect": [3, 1, 1, 1]}]}
    revs, _ = F.fix_page(sp, _PP, [_V("z_override 冲突 s2", "z 冲突", "zfix", "s2")])
    assert revs[0]["new"] == {"id": "s2", "z": 2}, revs   # 声明序 1-based


def test_fontscale():
    # clamp 到合法档
    revs, _ = F.fix_page({"meta": {}, "elements": [{"id": "n1", "type": "shape",
                                                    "text_style": {"fs": 20}}]},
                         _PP, [_V("节点字号 n1 ∈ type_scale.node", "fs=20.0 规范[8,16]",
                                  "fontscale", "n1")])
    assert revs[0]["new"] == 16.0
    # 无显式 fs → 新增显式化修正值（old=None）
    revs, _ = F.fix_page({"meta": {}, "elements": [{"id": "t_p", "type": "text",
                                                    "rect": [1, 1, 5, 2]}]},
                         _PP, [_V("正文字号 t_p ≥ 16", "fs=12.0 规范≥16",
                                  "fontscale", "t_p")])
    assert revs[0]["new"] == 16.0 and revs[0]["old"] is None, revs


def test_content_manual():
    _, audit = F.fix_page({"meta": {}, "elements": [{"id": "t", "type": "text"}]},
                          _PP, [_V("文本非空 t", "", "content", "t")])
    assert any("llm/人工" in a for a in audit)


if __name__ == "__main__":
    fails = 0
    for fn in (test_attribution, test_r1_autofit, test_r2_safety, test_r3_overlap,
               test_r4_zfix, test_fontscale, test_content_manual):
        try:
            fn()
            print(f"[OK] {fn.__name__}")
        except AssertionError as ex:
            fails += 1
            print(f"[FAIL] {fn.__name__}: {ex}")
    print(f"== spec_fixer 机械侧：{7 - fails} 通过 / {fails} 失败 ==")
    sys.exit(1 if fails else 0)