# -*- coding: utf-8 -*-
"""themes.py — deck 级设计语言（主题）：色彩角色 + 派生 tint/shade + 类型尺度 +
字族栈 + 几何/留白 + 卡/底母题。

移植源项目 `bvb6417/ppt-studio` 的 27 主题 / 视觉系统（本地源材料 `_r_defense-style.md`
§1 · `_r_design-rules.md`）。**纯数据 + 数学，无 IR**——几何仅作值产出（消费归
ir_builder，铁律 1：几何唯一真相源仍在布局层）。

SPEC 用法（`meta.theme`）：
    meta: {theme: nsfc_blue}                                   # 命名预设
    meta: {theme: {primary: "#124CAD", style: defense}}       # 从主色派生
    meta: {theme: {name: nsfc_blue, emph: "#A00000", ...}}    # 预设 + 局部覆盖

产出（供 spec_compile 消费）：
    palette_tokens  角色名 → {"solid": hex}（并入 compiled["palette"]：SPEC 可写
                    `style.fill: pale` / `accent: primary`，渲染层照常解析）
    params_overlay  只含 params.DEFAULTS **既有键**（style.* / font.* / text.scale /
                    theme.*）；作为配置栈**最低层**合并（作者 meta.params 覆盖之）。
"""
import copy

# 色彩角色（flight 用；SPEC 可直接引用为 palette token）
ROLES = ("primary", "deep", "pale", "panel", "panel_line", "emph", "text",
         "muted", "line", "bg", "surface", "accent")
# 类型尺度角色（pt）
TYPES = ("hero", "title", "subtitle", "body", "caption")
# 字族栈槽位
FONTS = ("title_ea", "title_latin", "body_ea", "body_latin", "number")
# 几何/留白键（in）——仅保留有真实消费路径的键（铁律 1：几何唯一源在 ir_builder/
# 渲染样式键；死键一律不入面，见下方 _overlay 注释）
#   margin      → build_pages 打底 meta.margin（版心留白）
#   card_radius → style.rounded_radius（圆角卡母题，render_pptx 消费）
GEO = ("margin", "card_radius")

# ---- 结构 / 母题 / 字族配对（官方 pptx skill §Before Starting / §Typography）----
# structure  背景节奏：uniform（缺省，零变化）| sandwich（封面/节页深底、内容浅底）
#            | dark（全篇深底）。消费方 = build_pages 逐页注入 framework.background。
# motif      视觉母题：none（缺省）| circle_icon（图标加 accent 系圆形背衬，全篇重复
#            = 官方 "icons in colored circles"）。消费方 = ir_builder 展开背衬圆。
# font_pair  字族配对：sans_sans（缺省）| serif_sans / serif_serif（衬线标题，官方
#            §Typography "pair a serif header with a sans body"）。消费方 = _overlay
#            font 槽（render_pptx._set_run_fonts 已按 title/body 角色分字族）。
STRUCTURES = ("uniform", "sandwich", "dark")
MOTIFS = ("none", "circle_icon")
PAIRINGS = ("sans_sans", "serif_sans", "serif_serif")
# 三明治深页页型集合（cover/section；conclusion 待其 status=implemented 再纳入）
STRUCT_DARK_INTENTS = ("cover", "section")
# 配对表：仅覆盖字族槽（作者 theme.fonts 仍可逐槽顶盖）；safe-list 字体（官方向）
_PAIR_FONTS = {
    "sans_sans": {},
    "serif_sans": {"title_latin": "Cambria", "body_latin": "Calibri"},
    "serif_serif": {"title_latin": "Cambria", "body_latin": "Cambria"},
}

# meta.theme 允许的键
_THEME_KEYS = {"name", "primary", "style", "mode", "emph", "overrides",
               "type_scale", "fonts", "geometry", "secondary",
               "structure", "motif", "font_pair"}


# ---------------- 颜色数学（#RRGGBB ↔ RGB） ----------------
def _parse(s):
    s = str(s).lstrip("#")
    if len(s) == 3:
        s = "".join(c * 2 for c in s)
    return tuple(int(s[i:i + 2], 16) for i in (0, 2, 4))


def _fmt(rgb):
    return "#%02X%02X%02X" % tuple(max(0, min(255, int(round(c)))) for c in rgb)


def nmix(a, b, t):
    """a→b 线性内插（t∈[0,1]）。"""
    ra, rb = _parse(a), _parse(b)
    return _fmt([ra[i] * (1 - t) + rb[i] * t for i in range(3)])


def tint(c, pct):
    """向白提亮 pct%（role+NN 语义）。"""
    return nmix(c, "#FFFFFF", pct / 100.0)


def shade(c, pct):
    """向黑压暗 pct%（role-NN 语义）。"""
    return nmix(c, "#000000", pct / 100.0)


def luma(c):
    """感知亮度（0–255；Rec.709 权重）——测试断言 pale>primary>deep 单调。"""
    r, g, b = _parse(c)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def is_hex(s):
    try:
        _parse(s)
        return len(str(s).lstrip("#")) in (3, 6)
    except (ValueError, IndexError):
        return False


def _norm_hex(s, ctx):
    if not is_hex(s):
        raise ValueError(f"{ctx}: 需为 #RRGGBB 色值，得到 {s!r}")
    return _fmt(_parse(s))


# ---------------- 每风格的常量表 ----------------
_TYPE_SCALE = {
    # 字号遵守 deck 规范下限（body ≥ 16；源材料 defense body 15 已上抬以合规）
    "defense": {"hero": 84.0, "title": 28.0, "subtitle": 18.0,
                "body": 16.0, "caption": 11.0},
    "modern":  {"hero": 72.0, "title": 30.0, "subtitle": 20.0,
                "body": 16.0, "caption": 12.0},
}
_FONT_STACK = {
    # ea 用微软雅黑（目标机必有）；latin/number 用 Bahnschrift（Win10+/Win11 自带）
    "defense": {"title_ea": "微软雅黑", "title_latin": "Bahnschrift",
                "body_ea": "微软雅黑", "body_latin": "Calibri",
                "number": "Bahnschrift"},
    "modern":  {"title_ea": "微软雅黑", "title_latin": "Calibri Light",
                "body_ea": "微软雅黑", "body_latin": "Calibri",
                "number": "Calibri"},
}
_GEOMETRY = {
    "defense": {"margin": {"l": 0.5, "t": 0.45, "r": 0.5, "b": 0.45},
                "card_radius": 0.10},
    "modern":  {"margin": {"l": 0.6, "t": 0.5, "r": 0.6, "b": 0.5},
                "card_radius": 0.12},
}

# 命名预设（nsfc_blue 色值来自源材料；其余派生 + 局部覆盖）
# 10 套跨色相命名主题 = 官方 anthropics/skills pptx SKILL.md §Color Palettes 原表
# （开篇铁律 "Don't default to blue"）。primary→primary；secondary→panel_line/line/
# panel（tint 浅版）；accent/emph 逐套手定（浅色 accent 在白底不可用作强调/装饰，
# 落回主色）。style=modern（通用，非 NNSFC 徽记）。
PRESETS = {
    "nsfc_blue":   dict(primary="#124CAD", style="defense", mode="light",
                        overrides={"deep": "#033E9C", "panel": "#F0F3F8",
                                   "panel_line": "#C5D3EA", "emph": "#C00000",
                                   "text": "#1F1F1F"}),
    "nsfc_navy":   dict(primary="#033E9C", style="defense", mode="light"),
    "nsfc_red":    dict(primary="#9E1B1B", style="defense", mode="light",
                        overrides={"emph": "#C00000"}),
    "nsfc_green":  dict(primary="#0E6E4E", style="defense", mode="light"),
    "nsfc_purple": dict(primary="#5B2C86", style="defense", mode="light"),
    "modern_light": dict(primary="#1E66F5", style="modern", mode="light"),
    # --- 官方 10 跨色相命名主题（§Color Palettes）---
    "midnight_executive": dict(primary="#1E2761", secondary="#CADCFC",
                               style="modern", mode="light",
                               overrides={"accent": "#1E2761", "emph": "#1E2761"}),
    "forest_moss": dict(primary="#2C5F2D", secondary="#97BC62",
                        style="modern", mode="light",
                        overrides={"accent": "#2C5F2D", "emph": "#2C5F2D"}),
    "coral_energy": dict(primary="#F96167", secondary="#F9E795",
                         style="modern", mode="light",
                         overrides={"accent": "#2F3C7E", "emph": "#2F3C7E"}),
    "warm_terracotta": dict(primary="#B85042", secondary="#E7E8D1",
                            style="modern", mode="light",
                            overrides={"accent": "#A7BEAE", "emph": "#B85042"}),
    "ocean_gradient": dict(primary="#065A82", secondary="#1C7293",
                           style="modern", mode="light",
                           overrides={"accent": "#21295C", "emph": "#21295C"}),
    "charcoal_minimal": dict(primary="#36454F", secondary="#CCD2D6",
                             style="modern", mode="light",
                             overrides={"accent": "#212121", "emph": "#212121"}),
    "teal_trust": dict(primary="#028090", secondary="#00A896",
                       style="modern", mode="light",
                       overrides={"accent": "#02C39A", "emph": "#028090"}),
    "berry_cream": dict(primary="#6D2E46", secondary="#A26769",
                        style="modern", mode="light",
                        overrides={"accent": "#6D2E46", "emph": "#6D2E46"}),
    "sage_calm": dict(primary="#84B59F", secondary="#69A297",
                      style="modern", mode="light",
                      overrides={"accent": "#50808E", "emph": "#50808E"}),
    "cherry_bold": dict(primary="#990011", secondary="#E0C9CC",
                        style="modern", mode="light",
                        overrides={"accent": "#2F3C7E", "emph": "#990011"}),
}


def _derive(primary, style, mode):
    """从主色派生全部角色（tint/shade）。style=defense 强调用红；modern 强调用主色。"""
    primary = _norm_hex(primary, "theme.primary")
    emph = primary if style == "modern" else "#C00000"
    roles = {
        "primary": primary,
        "deep": shade(primary, 32 if style == "defense" else 28),
        "pale": tint(primary, 84),
        "panel": tint(primary, 93),
        "panel_line": tint(primary, 62),
        "emph": emph,
        "text": "#1F1F1F",
        "muted": nmix("#1F1F1F", "#FFFFFF", 0.45),
        "line": tint(primary, 62),
        "bg": "#FFFFFF",
        "surface": "#FFFFFF",
        "accent": primary,
    }
    if mode == "dark":
        bg = shade(primary, 82)
        roles["bg"] = bg
        roles["surface"] = shade(primary, 68)
        roles["text"] = "#F2F2F2"
        roles["muted"] = nmix("#F2F2F2", bg, 0.5)
        roles["panel"] = shade(primary, 60)
        roles["panel_line"] = shade(primary, 40)
    return roles


def _deep_geo(base, over):
    """geometry 深合并（margin 子字典逐键覆盖）。"""
    geo = copy.deepcopy(base)
    for k, v in (over or {}).items():
        if k not in geo:
            raise ValueError(f"theme.geometry 未知键 {k!r}（可选 {sorted(geo)}）")
        if isinstance(geo[k], dict):
            if not isinstance(v, dict):
                raise ValueError(f"theme.geometry.{k} 应为 dict")
            geo[k].update(v)
        else:
            geo[k] = v
    return geo


def from_color(primary, style="defense", mode="light", overrides=None, emph=None,
               type_scale=None, fonts=None, geometry=None, name="",
               secondary=None, structure="uniform", motif="none",
               font_pair="sans_sans"):
    """派生生成器：单一主色 + 风格 → 完整 Theme dict（含 palette_tokens / params_overlay）。

    secondary  可选第二色：作支撑色 → panel_line/line（描边）+ panel（tint 浅版）。
    structure  背景节奏 uniform|sandwich|dark（缺省 uniform = 零行为变化）。
    motif      视觉母题 none|circle_icon（缺省 none）。
    font_pair  字族配对 sans_sans|serif_sans|serif_serif（缺省 sans_sans）。"""
    if style not in _TYPE_SCALE:
        raise ValueError(f"theme.style 须为 defense|modern，得到 {style!r}")
    if mode not in ("light", "dark"):
        raise ValueError(f"theme.mode 须为 light|dark，得到 {mode!r}")
    if structure not in STRUCTURES:
        raise ValueError(f"theme.structure 须为 {'|'.join(STRUCTURES)}，得到 {structure!r}")
    if motif not in MOTIFS:
        raise ValueError(f"theme.motif 须为 {'|'.join(MOTIFS)}，得到 {motif!r}")
    if font_pair not in PAIRINGS:
        raise ValueError(f"theme.font_pair 须为 {'|'.join(PAIRINGS)}，得到 {font_pair!r}")
    # structure=dark = 全篇深底 → 色彩角色必须本就为深色体系（text/panel 浅→亮），
    # 否则内容页文字（默认 text_color）落在深底上不可见。fail-closed 逼作者显式声明。
    if structure == "dark" and mode != "dark":
        raise ValueError("theme.structure=dark 须配 theme.mode=dark"
                         "（全篇深底需深色色彩角色，否则内容页文字不可见）")
    colors = _derive(primary, style, mode)
    if secondary:   # 第二色 → 支撑角色（描边 secondary、面板 tint 浅版）
        s = _norm_hex(secondary, "theme.secondary")
        colors["panel_line"] = s
        colors["line"] = s
        colors["panel"] = tint(s, 78)
    for k, v in (overrides or {}).items():
        if k not in colors:
            raise ValueError(f"theme.overrides 未知角色 {k!r}（可选 {sorted(ROLES)}）")
        colors[k] = _norm_hex(v, f"theme.overrides.{k}")
    if emph:   # 显式 emph 最后应用（胜过预设 overrides.emph）
        colors["emph"] = _norm_hex(emph, "theme.emph")
    ts = dict(_TYPE_SCALE[style])
    for k, v in (type_scale or {}).items():
        if k not in TYPES:
            raise ValueError(f"theme.type_scale 未知角色 {k!r}（可选 {TYPES}）")
        ts[k] = float(v)
    fo = dict(_FONT_STACK[style])
    fo.update(_PAIR_FONTS[font_pair])   # 配对前置；作者 theme.fonts 后置顶盖
    for k, v in (fonts or {}).items():
        if k not in FONTS:
            raise ValueError(f"theme.fonts 未知槽 {k!r}（可选 {FONTS}）")
        fo[k] = str(v)
    geo = _deep_geo(_GEOMETRY[style], geometry)
    theme = {"name": name, "style": style, "mode": mode, "primary": colors["primary"],
             "colors": colors, "type_scale": ts, "fonts": fo, "geometry": geo,
             "structure": structure, "motif": motif, "font_pair": font_pair}
    theme["palette_tokens"] = {r: {"solid": h} for r, h in colors.items()}
    theme["params_overlay"] = _overlay(theme)
    return theme


def _overlay(theme):
    """Theme → params 覆盖层（**只含 DEFAULTS 既有键**：style.*/font.*/text.scale/theme.*）。

    几何面刻意收窄到有真实消费路径的两键（死键不入面，避免"声明即生效"的假象）：
      · margin      → 写 theme.margin（build_pages 打底 meta.margin）
      · card_radius → 写 style.rounded_radius（render_pptx 圆角卡消费），
                      并同步落 theme.card_radius 供 CLI/审计观察。
    font 槽（含 font_pair 结果）→ render_pptx._set_run_fonts 按 title/body 角色消费；
    theme.structure/motif → build_pages / ir_builder 消费（结构/母题）。"""
    c, ts, fo = theme["colors"], theme["type_scale"], theme["fonts"]
    geo = theme["geometry"]
    return {
        "style": {
            "fill": c["pale"], "border": c["deep"], "text_color": c["text"],
            "emphasis": c["emph"], "line_color": c["deep"], "accent": c["accent"],
            "group_fill": c["panel"], "group_border": c["panel_line"],
            "rounded_radius": geo["card_radius"],
        },
        "font": {
            "ea": fo["body_ea"], "latin": fo["body_latin"],
            "title_ea": fo["title_ea"], "title_latin": fo["title_latin"],
        },
        "text": {"scale": dict(ts)},
        "theme": {
            "margin": dict(geo["margin"]), "card_radius": geo["card_radius"],
            "structure": theme["structure"], "motif": theme["motif"],
        },
    }


def resolve(spec):
    """SPEC `meta.theme`（名 | dict）→ Theme dict；None → None。

    未知键 / 未知预设 / 非法色值 → ValueError（spec_compile 转 SpecCompileError，exit 2）。"""
    if spec is None:
        return None
    if isinstance(spec, str):
        spec = {"name": spec}
    if not isinstance(spec, dict):
        raise ValueError("meta.theme 须为字符串（预设名）或 dict")
    unknown = set(spec) - _THEME_KEYS
    if unknown:
        raise ValueError(f"meta.theme 未知键 {sorted(unknown)}（可选 {sorted(_THEME_KEYS)}）")
    base = {}
    if spec.get("name"):
        if spec["name"] not in PRESETS:
            raise ValueError(f"未知主题 {spec['name']!r}（可选 {sorted(PRESETS)}）")
        base = dict(PRESETS[spec["name"]])
    primary = spec.get("primary") or base.get("primary")
    if not primary:
        raise ValueError("meta.theme 须给 name（预设名）或 primary（派生主色）")
    ov = dict(base.get("overrides") or {})
    ov.update(spec.get("overrides") or {})
    return from_color(
        primary,
        style=spec.get("style") or base.get("style") or "defense",
        mode=spec.get("mode") or base.get("mode") or "light",
        overrides=ov,
        emph=spec.get("emph") or base.get("emph"),
        type_scale=spec.get("type_scale"),
        fonts=spec.get("fonts"),
        geometry=spec.get("geometry"),
        name=(spec.get("name") or ""),
        secondary=spec.get("secondary") or base.get("secondary"),
        structure=spec.get("structure") or base.get("structure") or "uniform",
        motif=spec.get("motif") or base.get("motif") or "none",
        font_pair=spec.get("font_pair") or base.get("font_pair") or "sans_sans",
    )
