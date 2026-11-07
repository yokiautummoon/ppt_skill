# -*- coding: utf-8 -*-
"""test_params_stack.py — 配置栈统一参数合并（性质③）单测。

覆盖：resolve 三层链（全局 → 页级 → CLI）优先级 / 未知键拦截 / layer_merge
深覆盖原语（部分键覆盖保留其余，未知键报错）/ build_pages 层间不污染（页级
framework 覆盖不影响全局与后续页）/ spec_compile 页级 params 合法与非法 /
CLI --param 解析类型化 / 页级 params 影响该页 verify 与布局、另一页不受累及。
无 Office。运行：win_py -X utf8 tests/test_params_stack.py
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
import params as P
import build_ppt as B
import spec_compile as SC
import ir_builder
import verify
import yaml


# ---------- resolve 三层链 ----------

def test_resolve_layers_priority():
    meta = {"verify": {"eps": 0.01}}
    page = {"verify": {"eps": 0.02}, "text": {"min_fs": 6}}
    cli = {"text": {"min_fs": 8}}
    p = P.resolve(meta, page, cli)
    assert p["verify"]["eps"] == 0.02          # 页级盖全局
    assert p["text"]["min_fs"] == 8            # CLI 盖页级
    assert p["table"]["fs"] == P.DEFAULTS["table"]["fs"]   # 未覆盖者回退 DEFAULTS


def test_resolve_layers_no_pollution():
    a = P.resolve({"text": {"min_fs": 7}})
    b = P.resolve({})
    assert b["text"]["min_fs"] == P.DEFAULTS["text"]["min_fs"]   # 层间不污染
    assert a["text"]["min_fs"] == 7


def test_resolve_unknown_key_rejected():
    for layer in ({"bogus": 1}, None, None), (None, {"bogus": 1}, None), (None, None, {"bogus": 1}):
        try:
            P.resolve(*layer)
            assert False, f"未拦截未知键 {layer}"
        except KeyError:
            pass


def test_layer_merge_deep_override():
    base = {"a": {"b": 1, "c": 2}, "d": 3}
    out = P.layer_merge(dict(base), {"a": {"b": 9}})
    assert out["a"] == {"b": 9, "c": 2}        # 部分键覆盖保留其余
    assert out["d"] == 3
    try:
        P.layer_merge(dict(base), {"z": 1})
        assert False, "未拦截未知键"
    except KeyError:
        pass


# ---------- CLI --param 解析 ----------

def test_parse_param_overrides():
    ov = B._parse_param_overrides(["font.latin=Times New Roman", "table.fs=10",
                                   "style.shadow=false", "verify.eps=0.5"])
    assert ov["font"]["latin"] == "Times New Roman"
    assert ov["table"]["fs"] == 10
    assert ov["style"]["shadow"] is False
    assert ov["verify"]["eps"] == 0.5
    assert B._parse_param_overrides(None) == {}
    try:
        B._parse_param_overrides(["nokey"])
        assert False, "未拦截无 = 项"
    except SystemExit:
        pass


# ---------- spec_compile 页级 params ----------

_MULTI = {"meta": {"title": "t", "slide": {"w": 13.333, "h": 7.5},
                   "params": {"verify": {"eps": 0.001}},
                   "slides": [
                       {"title": "a", "params": {"verify": {"eps": 0.01}},
                        "elements": [{"id": "x", "type": "text", "rect": [1, 1, 3, 1],
                                      "text": "p1", "text_style": {"fs": 14}}]},
                       {"title": "b",
                        "elements": [{"id": "x", "type": "text", "rect": [1, 1, 3, 1],
                                      "text": "p2", "text_style": {"fs": 14}}]}]}}


def test_spec_page_params_valid():
    c = SC.compile_spec(SC.load_yaml(yaml.safe_dump(_MULTI, allow_unicode=True,
                                                    sort_keys=False)))
    assert c["slides"][0]["params"] == {"verify": {"eps": 0.01}}
    assert c["slides"][1]["params"] is None


def test_spec_page_params_bad_type():
    d = yaml.safe_load(yaml.safe_dump(_MULTI, allow_unicode=True, sort_keys=False))
    d["meta"]["slides"][0]["params"] = {"framework": {"page_offset": 0.5}}
    try:
        SC.compile_spec(SC.load_yaml(yaml.safe_dump(d, allow_unicode=True,
                                                    sort_keys=False)))
        assert False, "未拦截非整数 page_offset"
    except SC.SpecCompileError:
        pass


# ---------- build_pages 层间不污染 + 页级生效 ----------

def _pages_of(d=None):
    d = d or _MULTI
    c = SC.compile_spec(SC.load_yaml(yaml.safe_dump(d, allow_unicode=True,
                                                    sort_keys=False)))
    return B.build_pages(c)


def test_build_pages_deep_merge_no_pollution():
    d = yaml.safe_load(yaml.safe_dump(_MULTI, allow_unicode=True, sort_keys=False))
    d["meta"]["framework"] = {"header": {"text": "H", "fs": 10, "color": "#112233"}}
    d["meta"]["slides"][0]["framework"] = {"footer": {"text": "F1"}}
    pages = _pages_of(d)
    p1, p2 = pages[0], pages[1]
    # 页 1：页级 footer 深盖全局（header 保留全局显式 fs/color）
    fw1 = p1["meta"]["framework"]
    assert fw1["header"] == {"text": "H", "fs": 10, "color": "#112233"}
    assert fw1["footer"]["text"] == "F1"
    # 页 2：无页级覆盖 → 完全继承全局（不被页 1 污染）
    fw2 = p2["meta"]["framework"]
    assert fw2["header"] == {"text": "H", "fs": 10, "color": "#112233"}
    assert "footer" not in fw2


def test_page_params_only_affects_own_page():
    pages = _pages_of()
    assert pages[0]["_p"]["verify"]["eps"] == 0.01   # 页级覆盖生效
    assert pages[1]["_p"]["verify"]["eps"] == 0.001  # 全局回退
    global_p = _pages_of()[1]["_p"]
    eps0 = global_p["verify"]["eps"]
    ir2 = ir_builder.build_ir(pages[1], pages[1]["_p"])
    rep2 = verify.run(ir2, pages[1], pages[1]["_p"])
    assert rep2.p is pages[1]["_p"]


# ---------- 页级 params 影响布局（字号硬底） ----------

_LOW_FS = {"meta": {"title": "t", "slide": {"w": 13.333, "h": 7.5},
                    "slides": [
                        {"title": "a", "params": {"text": {"min_fs": 8}},
                         "elements": [{"id": "x", "type": "text", "rect": [1, 1, 3, 1],
                                       "text": "超长占位文本" * 6, "text_style": {"fs": 40}}]},
                        {"title": "b",
                         "elements": [{"id": "x", "type": "text", "rect": [1, 1, 3, 1],
                                       "text": "超长占位文本" * 6, "text_style": {"fs": 40}}]}]}}


def test_page_params_min_fs_layout():
    c = SC.compile_spec(SC.load_yaml(yaml.safe_dump(_LOW_FS, allow_unicode=True,
                                                    sort_keys=False)))
    pages = B.build_pages(c, None)
    p0, p1 = pages[0], pages[1]
    ir0 = ir_builder.build_ir(p0, p0["_p"])
    ir1 = ir_builder.build_ir(p1, p1["_p"])
    fs0 = ir0["elements"][0]["text_layout"]["fs"]
    fs1 = ir1["elements"][0]["text_layout"]["fs"]
    assert fs0 >= 8.0                       # 页级 min_fs=8 硬底
    assert fs1 >= 4.0                       # 全局 min_fs=4 硬底（页级不波及）
    assert fs0 > fs1


# ---------- 主题层（配置栈最低层） ----------

def test_theme_layer_lowest_priority():
    import themes as TH
    tov = TH.resolve({"name": "nsfc_blue"})["params_overlay"]
    acc = TH.resolve({"name": "nsfc_blue"})["colors"]["primary"]
    p = P.resolve(theme_params=tov)
    assert p["style"]["accent"] == acc            # 主题打底生效
    assert p["text"]["scale"]["body"] >= 16.0
    p2 = P.resolve({"style": {"accent": "#010203"}}, theme_params=tov)
    assert p2["style"]["accent"] == "#010203"      # 作者 meta.params 盖主题
    p3 = P.resolve({"style": {"accent": "#010203"}}, None,
                   {"style": {"accent": "#040506"}}, theme_params=tov)
    assert p3["style"]["accent"] == "#040506"      # CLI 盖两者


_THEMED = {"meta": {"title": "t", "slide": {"w": 13.333, "h": 7.5},
                    "theme": "nsfc_blue",
                    "slides": [
                        {"title": "a", "elements": [
                            {"id": "title", "type": "text", "rect": [1, 1, 6, 1],
                             "text": "x", "text_style": {"fs": 20, "scale": "title"}}]}]}}


def test_theme_margin_seed():
    import themes as TH
    c = SC.compile_spec(SC.load_yaml(yaml.safe_dump(_THEMED, allow_unicode=True,
                                                    sort_keys=False)))
    assert c.get("_theme") is not None
    assert c.get("_theme_params") is not None
    pages = B.build_pages(c, None)
    assert pages[0]["meta"]["margin"] == TH._GEOMETRY["defense"]["margin"]
    # 类型尺度：scale=title → fs0 取主题 title 档（未显式 fs 时）；此处显式 fs=20 优先
    ir = ir_builder.build_ir(pages[0], pages[0]["_p"])
    assert ir["elements"][0]["text_style"].get("role") == "title"


if __name__ == "__main__":
    fns = (test_resolve_layers_priority, test_resolve_layers_no_pollution,
           test_resolve_unknown_key_rejected, test_layer_merge_deep_override,
           test_parse_param_overrides, test_spec_page_params_valid,
           test_spec_page_params_bad_type, test_build_pages_deep_merge_no_pollution,
           test_page_params_only_affects_own_page, test_page_params_min_fs_layout,
           test_theme_layer_lowest_priority, test_theme_margin_seed)
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
    print(f"== params 栈：{len(fns) - fails} 通过 / {fails} 失败 ==")
    sys.exit(1 if fails else 0)