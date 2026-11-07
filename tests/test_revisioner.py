# -*- coding: utf-8 -*-
"""test_revisioner.py — 修订链单测：plan 归位 + 事务应用 + fix.diff + 快照回滚。

决策部件②④（无 Office 依赖）。同输入必同输出。
运行：win_py -X utf8 tests/test_revisioner.py
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
import revisioner as R
from attribution import Violation


def test_plan_attribution():
    vs = [Violation("T", "水平不溢出 t_body", "d", "fixable", "autofit", "t_body"),
          Violation("S", "文本非空 t_t", "d", "fixable", "content", "t_t"),
          Violation("I", "断行重算一致 t_x", "d", "internal", "manual", "t_x"),
          Violation("S", "配色 ⊆ 白名单", "d", "advisory", "manual", None)]
    internal, items = R.plan(vs)
    assert [v.action for v in internal] == ["manual"]
    assert [i["fixer"] for i in items] == ["spec", "llm", "manual", "manual"]
    assert items[0]["candidates"][0] == "降号"
    assert items[1]["candidates"] == ["从brief生成文本", "引用现有文本", "移除(若装饰)", "人工"]


def test_apply_single_page():
    spec = {"meta": {}, "palette": {"ink": "#111111"},
            "elements": [{"id": "t_body", "type": "text", "rect": [1, 1, 8, 3], "text": "x",
                          "text_style": {"fs": 28}},
                         {"id": "s2", "type": "shape", "rect": [3, 1, 1, 1]}],
            "relations": {}}
    revs = [R._annotate_page({"action": "autofit", "path": ("elements", 0, "text_style", "fs"),
                              "old": 28, "new": 26, "basis": "b", "confidence": 0.95,
                              "data_source": "detail"}, 0),
            R._annotate_page({"action": "overlap", "path": ("relations", "overlap", "+"),
                              "old": None, "new": {"id": "t_body", "with": "s2"},
                              "basis": "b", "confidence": 0.95, "data_source": "spec"}, 0)]
    out, diffs, errs = R.apply_revisions(spec, revs)
    assert not errs, errs
    assert out["elements"][0]["text_style"]["fs"] == 26
    assert out["relations"]["overlap"] == [{"id": "t_body", "with": "s2"}]


def test_apply_multi_page():
    mspec = {"meta": {"slides": [{"elements": [{"id": "a", "type": "text", "rect": [1, 1, 2, 1],
                                                "text_style": {"fs": 20}}], "relations": {}},
                                 {"elements": [], "relations": {}}]}, "palette": {}}
    # 页 2 无元素 → 越界拒绝（事务性：不产出部分应用）
    _, _, errs = R.apply_revisions(mspec, [R._annotate_page(
        {"action": "fontscale", "path": ("elements", 0, "text_style", "fs"),
         "old": 20, "new": 16, "basis": "b", "confidence": 0.9, "data_source": "detail"}, 1)])
    assert len(errs) == 1 and "越界" in errs[0]
    out, diffs, errs = R.apply_revisions(mspec, [R._annotate_page(
        {"action": "fontscale", "path": ("elements", 0, "text_style", "fs"),
         "old": 20, "new": 16, "basis": "b", "confidence": 0.9, "data_source": "detail"}, 0)])
    assert not errs
    assert out["meta"]["slides"][0]["elements"][0]["text_style"]["fs"] == 16


def test_apply_txn_guard():
    # old 基准不匹配 → 整体拒绝（返回原样 spec）
    spec = {"meta": {}, "elements": [{"id": "a", "type": "text", "rect": [1, 1, 2, 1],
                                      "text_style": {"fs": 18}}], "relations": {}}
    out, _, errs = R.apply_revisions(spec, [R._annotate_page(
        {"action": "autofit", "path": ("elements", 0, "text_style", "fs"),
         "old": 28, "new": 26, "basis": "b", "confidence": 0.95, "data_source": "detail"}, 0)])
    assert errs and out is spec
    # 缺层创建（text_style 不存在 → 新建）
    spec3 = {"meta": {}, "elements": [{"id": "t_p", "type": "text", "rect": [1, 1, 5, 2]}],
             "relations": {}}
    out, _, errs = R.apply_revisions(spec3, [R._annotate_page(
        {"action": "fontscale", "path": ("elements", 0, "text_style", "fs"),
         "old": None, "new": 16.0, "basis": "b", "confidence": 0.9,
         "data_source": "detail"}, 0)])
    assert not errs and out["elements"][0]["text_style"]["fs"] == 16.0


def test_format_and_diff():
    assert R.format_path(("elements", 3, "text_style", "fs")) == "elements[3].text_style.fs"
    assert R.format_path(("relations", "overlap", "+")) == "relations.overlap+"
    assert R.format_path(("relations", "z_override", 1, "z"), pg=0, multi=True) \
        == "slides[0].relations.z_override[1].z"
    assert R.format_path(("relations", "z_override", "+"), pg=2, multi=True) \
        == "slides[2].relations.z_override+"

    d, tmp = None, tempfile.mkdtemp(suffix="")
    df = os.path.join(tmp, "fix.diff")
    diffs = [R._annotate_page({"action": "fontscale", "path": ("elements", 0, "text_style", "fs"),
                               "old": None, "new": 16.0, "basis": "b", "confidence": 0.9,
                               "data_source": "detail"}, 0)]
    assert R.write_fix_diff(df, diffs, round_n=1) == 1
    assert R.write_fix_diff(df, diffs, round_n=2) == 1
    txt = open(df, encoding="utf-8").read()
    assert "1|spec|fontscale|elements[0].text_style.fs|∅→16.0|b|0.9|detail" in txt, txt


def test_snapshot_rollback_dump():
    tmp = tempfile.mkdtemp(suffix="")
    specf = os.path.join(tmp, "s.yaml")
    open(specf, "w", encoding="utf-8").write("old: 1\n")
    snap = R.snapshot_file(specf, 1)
    open(specf, "a", encoding="utf-8").write("new: 2\n")
    assert R.rollback(specf, 1)
    assert open(specf, encoding="utf-8").read() == "old: 1\n"
    crlf = R.dump_spec({"a": 1}, newline="\r\n")
    assert "\r\n" in crlf and crlf.endswith("\r\n")


if __name__ == "__main__":
    fails = 0
    for fn in (test_plan_attribution, test_apply_single_page, test_apply_multi_page,
               test_apply_txn_guard, test_format_and_diff, test_snapshot_rollback_dump):
        try:
            fn()
            print(f"[OK] {fn.__name__}")
        except AssertionError as ex:
            fails += 1
            print(f"[FAIL] {fn.__name__}: {ex}")
    print(f"== revisioner：{6 - fails} 通过 / {fails} 失败 ==")
    sys.exit(1 if fails else 0)