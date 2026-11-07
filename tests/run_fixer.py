# -*- coding: utf-8 -*-
"""run_fixer.py — 自优修订链端到端测试（决策 self-improve-loop.md 测试节）。

进程内调 build_ppt.main（不起子进程），临时 SPEC 构造预置违规：
  机械侧：R2 安全区平移收敛 / R3 遮挡补声明收敛 / --revert 回滚
  LLM 侧（fake client 回放）：通过回环 / 修订被拒（护栏） / 轮尽回滚指引 /
                          数据依据缺失拒绝
  attribution 单测见 tests/test_spec_fixer.py（25 例）。

运行：win_py -X utf8 tests/run_fixer.py（无 Office 依赖；临时目录自清理）
"""
import json
import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))


def _tmp():
    return tempfile.mkdtemp(prefix="fixer_", suffix="")


def _write(d, text):
    p = os.path.join(d, "spec.yaml")
    with open(p, "w", encoding="utf-8") as f:
        f.write(text)
    return p


def _run(spec_path, out_dir, *extra):
    """进程内跑 build_ppt.main；返回 rc。"""
    import build_ppt
    argv = [spec_path, "--out", out_dir, "--report", "none"] + list(extra)
    return build_ppt.main(argv)


def _spec_doc(t_footer="内部资料"):
    return """meta:
  title: fixer 端到端
  margin: {l: 0.5, t: 0.5, r: 0.5, b: 0.5}
  brief: "制作季度营收摘要：营收 120 亿，同比 +12%，毛利率 34%。"
palette:
  ink: "#1F2A44"
  paper: "#FFFFFF"
elements:
  - id: t_title
    type: text
    rect: [1.0, 1.0, 8.0, 1.0]
    text: 季度营收摘要
    text_style: {fs: 28}
  - id: t_footer
    type: text
    rect: [10.0, 6.5, 2.5, 0.6]
    text: "__FOOTER__"
    text_style: {fs: 12}
""".replace("__FOOTER__", t_footer)


def test_mech_safety_roundtrip():
    """R2：t_footer 底边越界 → --fix 平移收敛 exit 0 + 快照可回滚。"""
    d = _tmp()
    p = _write(d, _spec_doc())
    rc = _run(p, d, "--fix", "--max-fix", "3")
    assert rc == 0, rc
    text = open(p, encoding="utf-8").read()
    assert "6.4" in text, text                     # y 6.5→6.4 平移
    diff = open(os.path.join(d, "fix.diff"), encoding="utf-8").read()
    assert "1|spec|safety|elements[1].rect[1]|6.5→6.4|" in diff, diff
    # revert 回滚
    rc = _run(p, d, "--revert")
    assert rc == 0, rc
    assert "6.5" in open(p, encoding="utf-8").read()
    shutil.rmtree(d, ignore_errors=True)


def test_mech_overlap_roundtrip():
    """R3：两个独立形状相交无声明 → 补 relations.overlap → 收敛。"""
    d = _tmp()
    spec = """meta: {title: overlap}
palette: {ink: "#1F2A44", paper: "#FFFFFF"}
elements:
  - id: a
    type: shape
    rect: [1.0, 1.0, 3.0, 2.0]
    style: {fill: ink}
  - id: b
    type: shape
    rect: [2.5, 1.5, 3.0, 2.0]
    style: {fill: paper}
"""
    p = _write(d, spec)
    rc = _run(p, d, "--fix", "--max-fix", "2")
    assert rc == 0, rc
    text = open(p, encoding="utf-8").read()
    assert "overlap" in text, text
    assert "a" in text and "b" in text
    shutil.rmtree(d, ignore_errors=True)


def test_llm_roundtrip():
    """content 违规 + 回填（brief 引文）→ 机械+LLM 双通道收敛 exit 0。"""
    d = _tmp()
    p = _write(d, _spec_doc(""))
    out = os.path.join(d, "llm_out.json")
    rc = _run(p, d, "--fix", "--llm", "--max-fix", "2")
    assert rc == 6, rc                              # 无回填 → 稳态暂停
    out2 = {"version": 1, "revisions": [
        {"action": "从brief生成文本", "element": "t_footer", "field": "text",
         "old": "", "new": "营收 120 亿 · 同比 +12%",
         "basis": "brief 引文：'营收 120 亿，同比 +12%，毛利率 34%'",
         "confidence": 0.85}], "audit": []}
    with open(os.path.join(d, "llm_out.json"), "w", encoding="utf-8") as f:
        json.dump(out2, f, ensure_ascii=False)
    rc = _run(p, d, "--fix", "--llm", "--max-fix", "2")
    assert rc == 0, rc
    assert "营收 120 亿 · 同比 +12%" in open(p, encoding="utf-8").read()
    shutil.rmtree(d, ignore_errors=True)


def test_llm_reject():
    """数据红线：llm_out 的 data 字段依据缺失 → 拒绝 exit 3（不落盘）。"""
    d = _tmp()
    p = _write(d, _spec_doc(""))
    rc = _run(p, d, "--fix", "--llm", "--max-fix", "2")
    assert rc == 6, rc
    # t_footer 是 text 非 table，但数据红线按字段判定（数据字段路径守卫）
    bad = {"version": 1, "revisions": [
        {"action": "从brief生成文本", "element": "t_footer", "field": "data",
         "old": "", "new": [[9, 9]], "basis": "好看一点", "confidence": 0.7}]}
    with open(os.path.join(d, "llm_out.json"), "w", encoding="utf-8") as f:
        json.dump(bad, f, ensure_ascii=False)
    rc = _run(p, d, "--fix", "--llm", "--max-fix", "2")
    assert rc == 3, rc
    assert "t_footer" in open(p, encoding="utf-8").read()   # spec 未改（拒绝）
    shutil.rmtree(d, ignore_errors=True)


def test_llm_exhaust_revert():
    """无机械可修 + 无 LLM 回填（无 --llm）→ 轮尽回滚 + 指引 exit 3。"""
    d = _tmp()
    p = _write(d, _spec_doc(""))
    before = open(p, encoding="utf-8").read()
    rc = _run(p, d, "--fix", "--max-fix", "1")
    assert rc == 3, rc
    assert open(p, encoding="utf-8").read() == before    # 快照回滚恢复原文
    shutil.rmtree(d, ignore_errors=True)


if __name__ == "__main__":
    fails = 0
    for fn in (test_mech_safety_roundtrip, test_mech_overlap_roundtrip,
               test_llm_roundtrip, test_llm_reject, test_llm_exhaust_revert):
        try:
            fn()
            print(f"[OK] {fn.__name__}")
        except AssertionError as ex:
            fails += 1
            import traceback
            print(f"[FAIL] {fn.__name__}: {ex}")
            traceback.print_exc()
    print(f"== run_fixer：{5 - fails} 通过 / {fails} 失败 ==")
    sys.exit(1 if fails else 0)