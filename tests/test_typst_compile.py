# -*- coding: utf-8 -*-
"""test_typst_compile.py — typst 排版链路单测。

覆盖：源码装配（默认前导/vars/外链）/ 双产物编译（1:1 尺寸）/ 编译错误结构化 /
SPEC 校验契约（三源互斥/外链存在/顶层限制/design 拦截）/ 渲染 svgBlip 注入 /
SVG 降级纯 PNG。无 Office 依赖（typst.exe 为编译期依赖）。
运行：win_py -X utf8 tests/test_typst_compile.py
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
import spec_compile as SC
import spec_validator as SV
import typst_compile as TC
import ir_builder
import params as P
import render_pptx as RP
import render_check_xml as RCX


def _typst_elem(eid="t1", rect=(0.5, 0.5, 4.0, 2.0), **kw):
    e = {"id": eid, "type": "typst", "rect": list(rect), "typst": "== Hello\nWorld"}
    e.update(kw)
    return e


def test_source_assembly():
    e = _typst_elem(vars={"year": "2026"}, preamble="#set par(leading: 0.7em)")
    src = TC.build_source(e, e["rect"], None)
    # rect 只定宽，高 auto → 页面依内容生长（自动围切最小边界盒）
    assert "#set page(width: 288pt, height: auto, margin: 0pt)" in src
    assert '#let year = "2026"' in src
    assert "#set par(leading: 0.7em)" in src
    assert src.rstrip().endswith("World")
    # 用户 preamble 自带 #set page → 不注入默认（让其自控）
    e2 = _typst_elem(preamble="#set page(width: 100pt, height: 50pt)")
    assert "#set page(width: 288pt" not in TC.build_source(e2, e2["rect"], None)


def test_source_external():
    with tempfile.TemporaryDirectory() as td:
        pth = os.path.join(td, "x.typ")
        with open(pth, "w", encoding="utf-8") as f:
            f.write("= 外链内容")
        e = {"id": "t1", "type": "typst", "rect": [0, 0, 2, 1], "typst_src": "x.typ"}
        assert "= 外链内容" in TC.build_source(e, e["rect"], td)
        e2 = {"id": "t1", "type": "typst", "rect": [0, 0, 2, 1], "typst_src": "nope.typ"}
        try:
            TC.build_source(e2, e2["rect"], td)
            assert False, "缺失外链未报错"
        except TC.TypstCompileError:
            pass


def test_compile_products():
    with tempfile.TemporaryDirectory() as td:
        compiled = {"slides": [{"elements": [_typst_elem()]}]}
        w = TC.compile_all(compiled, td)
        assert w == [], w
        tp = compiled["slides"][0]["elements"][0]["_typst"]
        # 围切：内容 "== Hello\nWorld" 远小于 4×2in → size = 内容 bbox（≤ rect），offset 落版起点
        sz, off = tp["size"], tp["offset"]
        assert 0 < sz[0] <= 288.0 and 0 < sz[1] <= 144.0, tp["size"]
        assert 0 <= off[0] < 288.0 and 0 <= off[1] < 144.0, tp["offset"]
        for k in ("svg", "png", "typ"):
            assert os.path.isfile(tp[k]), k
        import re as _re
        svg_head = open(tp["svg"], encoding="utf-8").read(400)
        assert svg_head.startswith("<svg")
        assert 'viewBox="' in svg_head
        # PNG 已裁至 size（px = pt/72×300；±1px 容抗浮点往返）
        from PIL import Image
        with Image.open(tp["png"]) as im:
            got = im.size
        expect = (round(sz[0] / 72.0 * 300), round(sz[1] / 72.0 * 300))
        assert abs(got[0] - expect[0]) <= 1 and abs(got[1] - expect[1]) <= 1, (got, expect)
        assert expect[0] < 288.0 / 72.0 * 300, expect  # 宽确实裁小了（文本未铺满页宽）


def test_compile_error():
    with tempfile.TemporaryDirectory() as td:
        compiled = {"slides": [{"elements": [
            {"id": "bad", "type": "typst", "rect": [0, 0, 2, 1], "typst": "= _broken("}]}]}
        try:
            TC.compile_all(compiled, td)
            assert False, "语法错误未拦截"
        except TC.TypstCompileError as ex:
            assert "bad" in str(ex) and "编译失败" in str(ex)


def test_compile_warning_page_override():
    with tempfile.TemporaryDirectory() as td:
        compiled = {"slides": [{"elements": [
            _typst_elem(preamble="#set page(width: 100pt, height: 50pt)")]}]}
        w = TC.compile_all(compiled, td)
        assert w and "≠" in w[0], w


def _spec_neg(field, tmpdir=None):
    txt = ("meta:\n  title: t\n  slide: {w: 13.333, h: 7.5}\n"
           "elements:\n  - id: t1\n    type: typst\n    rect: [0.5, 0.5, 6.0, 3.0]\n"
           + field)
    d = SC.load_yaml(txt)
    try:
        SC.compile_spec(d, base_dir=tmpdir)
        return None
    except SC.SpecCompileError as ex:
        return str(ex)


def test_spec_contract():
    assert "须恰声明" in (_spec_neg("    typst_src: x.typ\n    typst: |\n      == hi\n") or "")
    assert "尚未落地" in (_spec_neg("    design: 一句话意图\n") or "")
    assert "不存在" in (_spec_neg("    typst_src: missing.typ\n") or "")
    assert "标识符" in (_spec_neg("    typst: x\n    vars: {1bad: 1}\n") or "")
    # children 内 typst（无 rect）→ 顶层限制拦截
    d = SC.load_yaml(
        "meta:\n  title: t\n  slide: {w: 13.333, h: 7.5}\n"
        "elements:\n  - id: st\n    type: stack\n    rect: [0.5, 0.5, 6.0, 4.0]\n"
        "    children:\n      - id: c1\n        type: typst\n        typst: x\n")
    try:
        SC.compile_spec(d)
        assert False, "children 内 typst 未拦截"
    except SC.SpecCompileError as ex:
        assert "必须为顶层" in str(ex)
    # 白名单放行 typst 字段
    ok = SC.compile_spec(SC.load_yaml(
        "meta:\n  title: t\n  slide: {w: 13.333, h: 7.5}\n"
        "elements:\n  - id: t1\n    type: typst\n    rect: [0.5, 0.5, 6.0, 3.0]\n"
        "    preamble: '#set text(size: 10pt)'\n    vars: {a: 1}\n    typst: x\n"))
    assert SV.validate(ok) == []


def _build_pptx(td, svg_ok=True):
    compiled = {"slides": [{"elements": [_typst_elem()]}], "palette": {}}
    TC.compile_all(compiled, td)
    p = P.resolve(None)
    ir = ir_builder.build_ir(compiled["slides"][0], p)
    if not svg_ok:
        for e in ir["elements"]:
            if e["type"] == "typst":
                e["svg"] = os.path.join(td, "missing.svg")
    out = os.path.join(td, "base.pptx")
    used, errors = RP.render([ir], compiled, p, out)
    return ir, out, used, errors


def test_render_svg_and_evidence():
    with tempfile.TemporaryDirectory() as td:
        ir, out, used, errors = _build_pptx(td)
        assert not errors, errors
        assert "typst_block" in used and "typst_svg" in used, used
        checks = RCX.check(out, ir, P.resolve(None), palette={}, page_idx=0)
        bad = [c for c in checks if not c[1]]
        assert not bad, bad
        names = [c[0] for c in checks]
        assert any("typst PNG fallback" in n for n in names)
        assert any("typst SVG 矢量" in n for n in names)


def test_render_png_fallback():
    """svg 产物缺失 → 降级纯 PNG（WARN 记账，不阻断），物证按降级合法放行。"""
    with tempfile.TemporaryDirectory() as td:
        ir, out, used, errors = _build_pptx(td, svg_ok=False)
        assert not errors, errors
        assert "typst_png_fallback" in used and "typst_svg" not in used, used
        checks = RCX.check(out, ir, P.resolve(None), palette={}, page_idx=0)
        bad = [c for c in checks if not c[1]]
        assert not bad, bad
        svg_check = [c for c in checks if "typst SVG 矢量" in c[0]]
        assert svg_check and svg_check[0][1] and "降级" in svg_check[0][2]


def test_trim_small_content():
    """内容远小于 rect → 围切到内容 bbox，PNG 已裁且与 size 一致。"""
    with tempfile.TemporaryDirectory() as td:
        compiled = {"slides": [{"elements": [
            _typst_elem(rect=(0.5, 0.5, 6.0, 4.0), typst="#text(size: 12pt)[A]")]}]}
        w = TC.compile_all(compiled, td)
        assert w == [], w
        tp = compiled["slides"][0]["elements"][0]["_typst"]
        sz, off = tp["size"], tp["offset"]
        assert 0 < sz[0] * sz[1] < 6.0 * 4.0 * 72 * 72, (sz, off)
        from PIL import Image
        with Image.open(tp["png"]) as im:
            expect = (round(sz[0] / 72.0 * 300), round(sz[1] / 72.0 * 300))
            assert abs(im.size[0] - expect[0]) <= 1 and abs(im.size[1] - expect[1]) <= 1, (im.size, expect)
            assert im.size[0] < 6.0 * 300, im.size  # 单字符未铺满页宽（6in×300ppi=1800px）→ 宽被裁小


def test_trim_formula_no_clip():
    """展示公式行高超出窄 rect → auto 高保证内容完整（无顶部裁剪/无下部空白）。"""
    with tempfile.TemporaryDirectory() as td:
        src = ("#set text(size: 14pt)\n"
               "#align(center)[$x = (-b plus.minus sqrt(b^2 - 4 a c)) / (2a)$]")
        compiled = {"slides": [{"elements": [
            {"id": "fx", "type": "typst", "rect": [0.5, 0.5, 2.5, 1.0], "typst": src}]}]}
        TC.compile_all(compiled, td)
        tp = compiled["slides"][0]["elements"][0]["_typst"]
        sz, off = tp["size"], tp["offset"]
        assert 0 < sz[1] <= 1.0 * 72, sz          # 内容高 = 公式行高，≤ rect 高
        assert 0 <= off[1] < 1.0 * 72, off        # 顶部无负偏移（未裁）
        from PIL import Image, ImageChops
        with Image.open(tp["png"]) as im:
            rgb = im.convert("RGB")
        bg = Image.new("RGB", rgb.size, rgb.getpixel((0, 0)))
        diff = ImageChops.difference(rgb, bg).getbbox()
        assert diff is not None and diff[1] >= 0


def test_explicit_page_no_trim():
    """preamble 自设 #set page → 尊重画布（size=画布、offset=0），跳过硬切。"""
    with tempfile.TemporaryDirectory() as td:
        compiled = {"slides": [{"elements": [
            _typst_elem(preamble="#set page(width: 100pt, height: 50pt)",
                        typst="#text(size: 12pt)[A]")]}]}
        w = TC.compile_all(compiled, td)
        assert w and "≠" in w[0], w           # 画布 ≠ rect → WARN（不阻断）
        tp = compiled["slides"][0]["elements"][0]["_typst"]
        assert tp["size"] == (100.0, 50.0), tp["size"]
        assert tp["offset"] == (0.0, 0.0), tp["offset"]
        from PIL import Image
        with Image.open(tp["png"]) as im:
            assert im.size == (round(100 / 72 * 300), round(50 / 72 * 300)), im.size


if __name__ == "__main__":
    if not TC.cli_available():
        print(f"[SKIP] typst CLI 未安装：{TC.CLI}")
        sys.exit(0)
    fns = (test_source_assembly, test_source_external, test_compile_products,
           test_compile_error, test_compile_warning_page_override, test_spec_contract,
           test_render_svg_and_evidence, test_render_png_fallback,
           test_trim_small_content, test_trim_formula_no_clip,
           test_explicit_page_no_trim)
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
    print(f"== typst_compile：{len(fns) - fails} 通过 / {fails} 失败 ==")
    sys.exit(1 if fails else 0)
