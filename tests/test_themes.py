# -*- coding: utf-8 -*-
"""test_themes.py — 设计语言层（themes.py）单测：派生生成器 + 预设 + 覆盖层契约。

关键不变式：
  1. tint/shade 亮度单调（pale > primary > deep）——派生方向不翻转
  2. palette_tokens 覆盖全部色彩角色；params_overlay **只写 DEFAULTS 既有键**
     （否则 params.resolve 未知键 KeyError）
  3. 命名预设完整可解析；未知名/未知键/非法色值 → ValueError（编译期 fail-closed）
  4. type_scale 遵守 deck 正文下限（body ≥ 16）
  5. 几何深合并 + 未知几何键报错

用法：win_py -X utf8 tests/test_themes.py
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "scripts"))

import themes as TH
import params as P

M = TH.PRESETS["nsfc_blue"]
_fail = []
_pass = []


def ok(name, cond, detail=""):
    if cond:
        _pass.append(name)
        print(f"[OK] {name}" + (f" · {detail}" if detail else ""))
    else:
        _fail.append(name)
        print(f"[FAIL!] {name} · {detail}")


def _overlay_keys_exist(ov, defaults, path="params"):
    """递归核对覆盖层键 ∈ DEFAULTS 键空间。"""
    bad = []
    for k, v in ov.items():
        if k not in defaults:
            bad.append(f"{path}.{k}")
            continue
        if isinstance(v, dict) and isinstance(defaults.get(k), dict):
            bad += _overlay_keys_exist(v, defaults[k], f"{path}.{k}")
    return bad


def main():
    # ---- 1. 派生亮度单调 ----
    t = TH.resolve({"name": "nsfc_blue"})
    c = t["colors"]
    ok("派生 pale > primary > deep（亮度单调）",
       TH.luma(c["pale"]) > TH.luma(c["primary"]) > TH.luma(c["deep"]),
       f"{TH.luma(c['pale']):.0f} > {TH.luma(c['primary']):.0f} > "
       f"{TH.luma(c['deep']):.0f}")
    ok("tint 提亮 / shade 压暗",
       TH.luma(TH.tint("#808080", 50)) > TH.luma("#808080")
       > TH.luma(TH.shade("#808080", 50)))

    # ---- 2. 角色完整 + 覆盖层键空间 ----
    ok("色彩角色全覆盖", set(c) == set(TH.ROLES),
       f"缺 {set(TH.ROLES) - set(c)} / 多 {set(c) - set(TH.ROLES)}")
    ok("palette_tokens 覆盖全部角色",
       set(t["palette_tokens"]) == set(TH.ROLES))
    ov = t["params_overlay"]
    bad = _overlay_keys_exist(ov, P.DEFAULTS)
    ok("params_overlay 只写 DEFAULTS 既有键", not bad, f"越界 {bad}")
    ok("overlay.style.accent = primary", ov["style"]["accent"] == c["primary"])
    ok("overlay 结构含 style/font/text/theme",
       {"style", "font", "text", "theme"} <= set(ov))

    # ---- 3. 记录：nsfc_blue 局部覆盖生效 ----
    ok("预设 overrides 生效（deep=#033E9C）", c["deep"] == "#033E9C", c["deep"])
    ok("emph 缺省红（defense）", c["emph"] == "#C00000", c["emph"])

    # ---- 4. type_scale 正文下限 ----
    ok("type_scale body ≥ 16（deck 下限）", t["type_scale"]["body"] >= 16.0,
       str(t["type_scale"]["body"]))
    ok("type_scale 含全部角色", set(t["type_scale"]) == set(TH.TYPES))

    # ---- 5. 全部预设可解析 ----
    for name in TH.PRESETS:
        try:
            TH.resolve(name)
            ok(f"预设 {name} 可解析", True)
        except Exception as ex:
            ok(f"预设 {name} 可解析", False, str(ex))

    # ---- 6. fail-closed：未知名/键/色值 ----
    for spec, tag in (({"name": "nope"}, "未知预设名"),
                      ({"primary": "#124CAD", "bogus": 1}, "未知 theme 键"),
                      ({"primary": "notacolor"}, "非法主色"),
                      ({"primary": "#124CAD", "style": "fancy"}, "未知 style"),
                      ({"primary": "#124CAD", "overrides": {"zzz": "#000"}},
                       "未知 overrides 角色")):
        try:
            TH.resolve(spec)
            ok(f"fail-closed {tag}", False, "未报错")
        except ValueError:
            ok(f"fail-closed {tag}", True)
    ok("resolve(None) → None", TH.resolve(None) is None)

    # ---- 7. 几何深合并 + 未知几何键 ----
    t2 = TH.resolve({"primary": "#124CAD",
                     "geometry": {"margin": {"l": 0.9}, "card_radius": 0.3}})
    ok("几何深合并（margin.l 覆盖，余键保留）",
       t2["geometry"]["margin"]["l"] == 0.9
       and t2["geometry"]["margin"]["t"] == _DEF_T["t"]
       and t2["geometry"]["card_radius"] == 0.3,
       str(t2["geometry"]["margin"]))
    # card_radius 有真实消费路径：映射到 style.rounded_radius（render_pptx 消费）
    ok("card_radius → style.rounded_radius（有消费方）",
       t2["params_overlay"]["style"]["rounded_radius"] == 0.3
       and t2["params_overlay"]["theme"]["card_radius"] == 0.3,
       str(t2["params_overlay"]["style"]))
    try:
        TH.resolve({"primary": "#124CAD", "geometry": {"wat": 1}})
        ok("未知几何键报错", False, "未报错")
    except ValueError:
        ok("未知几何键报错", True)

    # ---- 8. dark 模式背景压暗 ----
    td = TH.resolve({"primary": "#124CAD", "mode": "dark"})
    ok("dark 模式 bg 亮度 < light", TH.luma(td["colors"]["bg"])
       < TH.luma(TH.resolve({"primary": "#124CAD"})["colors"]["bg"]))

    # ---- 9. 覆盖层经 params.resolve 可用（不 KeyError）----
    p = P.resolve(theme_params=ov)
    ok("覆盖层入 params 配置栈", p["style"]["accent"] == c["primary"]
       and p["text"]["scale"]["hero"] == t["type_scale"]["hero"])

    # ---- 10. 结构/母题/字族配对（三键）----
    ok("缺省 structure=uniform / motif=none / font_pair=sans_sans",
       t["structure"] == "uniform" and t["motif"] == "none"
       and t["font_pair"] == "sans_sans")
    ok("overlay.theme 透传 structure/motif",
       ov["theme"]["structure"] == "uniform" and ov["theme"]["motif"] == "none")
    # 三明治：structure=sandwich 保留 light mode（深页由 build_pages 逐页注入）
    ts_ = TH.resolve({"primary": "#124CAD", "structure": "sandwich"})
    ok("structure=sandwich 可解析（mode 仍 light）",
       ts_["structure"] == "sandwich" and ts_["mode"] == "light")
    # dark 全篇深底须配 mode=dark（否则内容页文字落深底不可见 → fail-closed）
    try:
        TH.resolve({"primary": "#124CAD", "structure": "dark"})
        ok("fail-closed structure=dark 须配 mode=dark", False, "未报错")
    except ValueError:
        ok("fail-closed structure=dark 须配 mode=dark", True)
    ok("structure=dark + mode=dark 可解析",
       TH.resolve({"primary": "#124CAD", "structure": "dark",
                   "mode": "dark"})["structure"] == "dark")
    ok("motif=circle_icon 可解析",
       TH.resolve({"primary": "#124CAD",
                   "motif": "circle_icon"})["motif"] == "circle_icon")
    for bad in ({"structure": "bogus"}, {"motif": "bogus"},
                {"font_pair": "bogus"}):
        spec = {"primary": "#124CAD"}
        spec.update(bad)
        try:
            TH.resolve(spec)
            ok(f"fail-closed {list(bad)[0]}={list(bad.values())[0]}", False, "未报错")
        except ValueError:
            ok(f"fail-closed {list(bad)[0]}={list(bad.values())[0]}", True)
    # 字族配对：serif_sans → 标题 latin=Cambria、正文 latin=Calibri
    tp = TH.resolve({"primary": "#124CAD", "font_pair": "serif_sans"})
    ok("serif_sans 改标题 latin=Cambria",
       tp["fonts"]["title_latin"] == "Cambria"
       and tp["fonts"]["body_latin"] == "Calibri",
       f"title={tp['fonts']['title_latin']} body={tp['fonts']['body_latin']}")
    ok("serif_sans 经 overlay 落 font.title_latin（render_pptx 消费）",
       tp["params_overlay"]["font"]["title_latin"] == "Cambria")
    # 作者 theme.fonts 顶盖配对
    to = TH.resolve({"primary": "#124CAD", "font_pair": "serif_sans",
                     "fonts": {"title_latin": "Arial"}})
    ok("作者 fonts 顶盖配对结果", to["fonts"]["title_latin"] == "Arial")
    # 10 预设（跨色相）色相分散：primary 去重数 ≥ 8
    prims = {TH.resolve(n)["colors"]["primary"] for n in TH.PRESETS}
    ok("预设主色分散（去重 ≥ 8）", len(prims) >= 8, f"去重 {len(prims)}")

    print(f"---\npass={len(_pass)} fail={len(_fail)}")
    if _fail:
        print("FAILED:", *_fail, sep="\n  ")
        raise SystemExit(1)


_DEF_T = TH._GEOMETRY["defense"]["margin"]

if __name__ == "__main__":
    main()
