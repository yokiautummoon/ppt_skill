# -*- coding: utf-8 -*-
"""test_llm_fixer.py — 作业协议单测：job 构建/写出 + CHECK_OUT 护栏 + 数据红线。

决策部件④（无 Office、无网络依赖；LLM 侧用 fake client 回放）。
运行：win_py -X utf8 tests/test_llm_fixer.py
"""
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
import revisioner as R
import llm_fixer as LF
from attribution import Violation


def test_job_roundtrip():
    vs = [Violation("S", "文本非空 t_body", "d", "fixable", "content", "t_body"),
          Violation("S", "配色 ⊆ 白名单", "d", "advisory", "manual", None)]
    job = LF.build_job("s.yaml", {"index": 0, "title": "封面"}, vs, "按本周财报制作摘要",
                       "备注", ["文本 a", "文本 b"], R.MENU, "guide")
    assert job["version"] == 1 and job["violations"][0]["element"] == "t_body"
    assert job["menu"]["文本非空 t_body"] == R.MENU["content"]
    tmp = tempfile.mkdtemp(suffix="")
    jf = os.path.join(tmp, "llm_job.json")
    LF.write_job(job, jf)
    assert json.load(open(jf, encoding="utf-8"))["brief"] == "按本周财报制作摘要"


def test_check_text_revision():
    spec = {"meta": {}, "palette": {"ink": "#111111"},
            "elements": [{"id": "t_body", "type": "text", "rect": [1, 1, 8, 3],
                          "text": "旧文案"}], "relations": {}}
    vs = [Violation("S", "文本非空 t_body", "d", "fixable", "content", "t_body")]
    out = LF.fake_out([{"action": "从brief生成文本", "element": "t_body", "field": "text",
                        "old": "旧文案", "new": "摘要：营收 +12%",
                        "basis": "brief 引文：'按本周财报制作摘要'", "confidence": 0.8}])
    revs, errs = LF.check_out(out, spec, "按本周财报制作摘要", vs)
    assert not errs, errs
    assert revs[0]["path"] == ("elements", 0, "text") and revs[0]["data_source"] == "llm"
    out_spec, _, aerrs = R.apply_revisions(spec, [R._annotate_page(revs[0], 0)])
    assert not aerrs and out_spec["elements"][0]["text"] == "摘要：营收 +12%"


def test_data_redline():
    spec = {"meta": {}, "palette": {},
            "elements": [{"id": "tbl", "type": "table", "data": [[1, 2], [3, 4]]}],
            "relations": {}}
    vs = [Violation("S", "文本非空 tbl", "d", "fixable", "content", "tbl")]
    # 无依据 → 拒绝
    bad = LF.fake_out([{"action": "从brief生成文本", "element": "tbl", "field": "data",
                        "old": [[1, 2], [3, 4]], "new": [[9, 9], [9, 9]],
                        "basis": "好看一点", "confidence": 0.7}])
    revs, errs = LF.check_out(bad, spec, "数据来自财报", vs)
    assert not revs and any("依据缺失" in e for e in errs), errs
    # [占位] 放行
    ok = LF.fake_out([{"action": "从brief生成文本", "element": "tbl", "field": "data",
                       "old": [[1, 2], [3, 4]], "new": "[[占位]]",
                       "basis": "[占位] 数据待填", "confidence": 0.5}])
    revs, errs = LF.check_out(ok, spec, "数据来自财报", vs)
    assert not errs and revs


def test_targeted_field_by_type():
    """定向补丁：CHECK_OUT 按元素类型细分字段——data 塞给 text 被拒（不回退整页重排）。"""
    spec = {"meta": {}, "palette": {"ink": "#111111"},
            "elements": [{"id": "t1", "type": "text", "rect": [1, 1, 8, 3],
                          "text": "x"}], "relations": {}}
    # text 元素补 data → 字段类型专属拒绝
    bad = LF.fake_out([{"action": "从brief生成文本", "element": "t1", "field": "data",
                        "old": "x", "new": [[1, 2]], "basis": "brief 引文：'a'",
                        "confidence": 0.5}])
    revs, errs = LF.check_out(bad, spec, "a", [])
    assert not revs and any("不属于该元素的合法字段" in e for e in errs), errs
    # text 元素改自身合法字段 text → 放行
    ok = LF.fake_out([{"action": "从brief生成文本", "element": "t1", "field": "text",
                       "old": "x", "new": "y", "basis": "brief 引文：'a'",
                       "confidence": 0.5}])
    revs, errs = LF.check_out(ok, spec, "a", [])
    assert not errs and revs[0]["path"] == ("elements", 0, "text"), errs


def test_targeted_field_chart_data_ok():
    """chart 元素补 data → 字段类型专属**拒绝**（chart 的 PER_TYPE 键是 categories/series，
    无 data——补 data 会被编译期未知字段拦）。confirm 定向按类型细分对 chart 生效。"""
    spec = {"meta": {}, "palette": {},
            "elements": [{"id": "c1", "type": "chart", "chart_type": "bar",
                          "rect": [1, 1, 8, 4], "categories": ["a"],
                          "series": [{"name": "s", "values": [1]}]}], "relations": {}}
    # chart 补非法字段 data → 拒
    bad = LF.fake_out([{"action": "从brief生成文本", "element": "c1", "field": "data",
                        "old": None, "new": [[1, 2], [3, 4]],
                        "basis": "brief 引文：'按财报'", "confidence": 0.5}])
    revs, errs = LF.check_out(bad, spec, "按财报", [])
    assert not revs and any("不属于该元素的合法字段" in e for e in errs), errs
    # chart 补合法数据字段 series → 放行（数据红线 basis 合规）
    ok = LF.fake_out([{"action": "从brief生成文本", "element": "c1", "field": "series",
                       "old": None, "new": [{"name": "s", "values": [2, 3]}],
                       "basis": "brief 引文：'按财报'", "confidence": 0.5}])
    revs, errs = LF.check_out(ok, spec, "按财报", [])
    assert not errs and revs, errs


def test_job_constraints_injected():
    """Evolving Experience：负面约束（通用坑）作为机器可消费清单注入作业 context。"""
    vs = [Violation("S", "文本非空 t_body", "d", "fixable", "content", "t_body")]
    job = LF.build_job("s.yaml", [{"index": 0, "title": "封面"}], vs, "", "", [],
                       R.MENU, "guide")
    cons = job["context"]["constraints"]
    assert any("rect 必须 4 元组" in c["rule"] for c in cons)
    assert any("morph" in c["rule"].lower() for c in cons)
    # 通用约束注入；类型专属（svg/icon/brush/typst/数据字段）不进通用集合——CHECK_OUT 定位
    for c in cons:
        assert c["types"] is None


def test_guards():
    spec = {"meta": {}, "palette": {"ink": "#111111"},
            "elements": [{"id": "t_body", "type": "text", "rect": [1, 1, 8, 3],
                          "text": "x"}], "relations": {}}
    vs = [Violation("S", "文本非空 t_body", "d", "fixable", "content", "t_body")]
    # 元素幽灵 / 动作白名单外 / 版本不符
    revs, errs = LF.check_out(LF.fake_out([{"action": "从brief生成文本", "element": "ghost",
                                            "field": "text", "old": "x", "new": "y",
                                            "basis": "[占位]", "confidence": 0.5}]),
                              spec, "", vs)
    assert not revs and any("ghost" in e for e in errs)
    revs, errs = LF.check_out(LF.fake_out([{"action": "freehand", "element": "t_body",
                                            "field": "text", "old": "x", "new": "y",
                                            "basis": "[占位]", "confidence": 0.5}]),
                              spec, "", vs)
    assert not revs and any("白名单外" in e for e in errs)
    revs, errs = LF.check_out({"version": 99, "revisions": []}, spec, "", vs)
    assert not revs and any("version" in e for e in errs)
    # 一条非法 → 整批拒绝（与 revisioner 事务一致）
    mixed = LF.fake_out([{"action": "从brief生成文本", "element": "t_body", "field": "text",
                          "old": "x", "new": "y", "basis": "[占位]", "confidence": 0.5},
                         {"action": "从brief生成文本", "element": "t_body", "field": "data",
                          "old": 1, "new": 2, "basis": "随手", "confidence": 0.5}])
    revs, errs = LF.check_out(mixed, spec, "", vs)
    assert not revs and len(errs) >= 1


if __name__ == "__main__":
    fails = 0
    fns = (test_job_roundtrip, test_check_text_revision, test_data_redline,
           test_targeted_field_by_type, test_targeted_field_chart_data_ok,
           test_job_constraints_injected, test_guards)
    for fn in fns:
        try:
            fn()
            print(f"[OK] {fn.__name__}")
        except AssertionError as ex:
            fails += 1
            print(f"[FAIL] {fn.__name__}: {ex}")
    print(f"== llm_fixer：{len(fns) - fails} 通过 / {fails} 失败 ==")
    sys.exit(1 if fails else 0)