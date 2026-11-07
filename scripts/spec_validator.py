# -*- coding: utf-8 -*-
"""spec_validator.py — 编译期白名单校验（在 spec_compile 结构检查之后）。

职责：未知字段拒绝（YAML 吞错防护）、palette token 引用存在性、
      style_guide 存在性、meta.params 键可解析（params.resolve 权威合并）、
      graph 容器内 palette/尺寸语义。收集式 violations（不 assert），
      由 build_ppt 汇总后 exit 2。
"""
import re

import params as _P

_HEX_RE = re.compile(r"^#?[0-9A-Fa-f]{6}$")

COMMON_FIELDS = {"id", "type", "rect_kind", "rect", "area", "z", "ph_info", "link",
                 "animation", "animation_exit"}
# ph_info = 编译期内部（seed 解析结果）；link = 元素级超链接（容器在编译期被拦）；
# animation = 元素级动效（effect 配方引用/behaviors 直写，容器在编译期被拦）
PER_TYPE = {
    "text": COMMON_FIELDS | {"text", "text_style", "style", "ph"},
    # cylinder（shape.kind）专属键 slice/opacity：kind 语义由 spec_compile 收紧，
    # 此处随 shape 白名单放宽（非 cylinder 带它们被 spec_compile 拦截）
    "shape": COMMON_FIELDS | {"kind", "text", "text_style", "style", "slice", "opacity",
                              "anchors"},
    # curve = 自由曲线（rect 包围盒 + 归一化点列；style 线语义 color/weight/dash）
    "curve": COMMON_FIELDS | {"points", "style"},
    # brush = 书法矢量字（C3）：字体字形 → custGeom 原生矢量形状（换机不丢字形，
    # 可渐变/图片填充）。text 必填；font 别名/路径；style = fill/grad/image/alpha
    "brush": COMMON_FIELDS | {"text", "font", "style", "align", "anchor", "spacing"},
    # icon = 矢量图标（B1）：Lucide 图标 → custGeom 原生矢量形状（描边语义，
    # 缩放不糊、随主题着色）。icon 必填（名/关键词）；style = color/weight
    "icon": COMMON_FIELDS | {"icon", "style", "align", "anchor"},
    # image：src 缺失时须声明 placeholder（占位框 + 缺图提示清单，B3）
    # caption = 占位框显示文案 / 提示清单说明（image 缺省时用 missing_key 兜底）
    "image": COMMON_FIELDS | {"src", "visual_bounds", "placeholder", "caption"},
    # diagram = 逃生通道：外部转换器（如 mermaid→vsdx→PNG）预渲染产物，按图片落版
    "diagram": COMMON_FIELDS | {"src", "visual_bounds", "caption"},
    "formula": COMMON_FIELDS | {"expr", "text_style"},
    "table": COMMON_FIELDS | {"data", "cols", "col_widths", "header", "body", "borders"},
    "chart": COMMON_FIELDS | {"chart_type", "categories", "series", "style"},
    "line": COMMON_FIELDS | {"x1", "y1", "x2", "y2", "color", "weight", "arrow", "dash"},
    "stack": COMMON_FIELDS | {"orientation", "align", "v_align", "h_align", "gap", "children", "group"},
    "dock": COMMON_FIELDS | {"padding", "children", "height", "width", "group"},
    "graph": COMMON_FIELDS | {"start", "orientation", "variant", "nodes", "edges", "groups",
                             "inner_margin", "node_w", "node_h", "group", "linear"},
    # typst 排版块（typst 复杂精美排版链路，references/typst-chain.md）：
    # 源三分 typst/typst_src/design 互斥由 spec_compile 收紧；
    # design = LLM 辅助设计意图（首版未落地，编译期拦截提示）
    "typst": COMMON_FIELDS | {"typst", "typst_src", "design", "preamble", "vars"},
    # svg 矢量图（references/svg-figures.md）：src（外链）/ svg（内联源码）互斥由
    # spec_compile 收紧；fit = contain|stretch（contain 保宽高比居中，缺省）
    "svg": COMMON_FIELDS | {"src", "svg", "style", "fit"},
}
# stack/dock child 元素字段（children 内形状，另含尺寸键；link = 形状级超链接）
CHILD_PER_TYPE = {
    "text": {"id", "type", "text", "text_style", "style", "width", "height", "link",
             "animation"},
    "shape": {"id", "type", "kind", "text", "text_style", "style", "width", "height",
              "link", "animation"},
}
NODE_FIELDS = {"id", "text", "kind"}
EDGE_FIELDS = {"from", "to", "label", "way"}
GROUP_FIELDS = {"id", "label", "members"}


def _unknown(fields, allowed, path):
    # _ 前缀 = 编译期内部缓存字段（如 svg 解析的分组表 _svg），非 SPEC 键、不进白名单
    return [f"{path}.{k}: 未知字段（可选 {sorted(allowed)}）"
            for k in fields if k not in allowed and not k.startswith("_")]


def validate(compiled):
    """compiled: spec_compile.compile_spec 输出。返回 violations 列表。"""
    v = []

    # ---- meta ----
    meta = compiled.get("meta") or {}
    for k in meta:
        if k not in ("title", "style_guide", "slide", "margin", "params", "framework",
                     "slides", "template", "notes", "transition", "brief", "theme"):
            v.append(f"meta.{k}: 未知键（title/style_guide/slide/margin/params/"
                     "framework/slides/template/notes/transition/brief/theme）")
    sg = meta.get("style_guide")
    if sg is not None and sg not in _P.DEFAULTS.get("styleguide", {}) and sg not in _rule_set_names():
        v.append(f"meta.style_guide: 未知规则集 {sg!r}（可选 {sorted(_rule_set_names())}）")
    if "params" in meta:
        try:
            _P.resolve(meta["params"])
        except KeyError as ex:
            v.append(f"meta.params: 无法合并 — 未知键 {ex}")

    # ---- 元素字段白名单 + palette token 引用（按页；单页 = 顶层为唯一页）----
    palette = compiled["palette"]
    # compile_spec 恒产顶层 slides（≥1 页）；对未编译的 raw dict（绕过 compile 直接
    # validate 的调用方）按 SPEC 语法退化：meta.slides → 每页；否则顶层单页形态
    slides = compiled.get("slides") or []
    if not slides:
        _ms = (compiled.get("meta") or {}).get("slides")
        if isinstance(_ms, list) and _ms:
            slides = _ms
        else:
            slides = [{"elements": compiled.get("elements") or [],
                       "relations": compiled.get("relations") or {}}]
    multi = len(slides) > 1
    for si, page in enumerate(slides):
        pre = f"slides[{si}]" if multi else ""
        ep_pre = f"{pre}.elements" if pre else "elements"
        rp_pre = f"{pre}.relations" if pre else "relations"
        for i, e in enumerate(page["elements"]):
            ep = f"{ep_pre}[{i}]({e['id']})"
            etype = e["type"]
            v += _unknown(e.keys(), PER_TYPE[etype], ep)
            if etype in ("stack", "dock"):
                v += _check_children(e, ep)
        for i, e in enumerate(page["elements"]):
            ep = f"{ep_pre}[{i}]({e['id']})"
            v += _check_token_refs(e, palette, ep, child=False)
        rel = page.get("relations") or {}
        for i, gl in enumerate(rel.get("glue", [])):
            st = gl.get("style") or {}
            for col_k in ("color", "fill", "border"):
                tok = st.get(col_k)
                if isinstance(tok, str) and tok not in palette and tok != "none" \
                   and not _HEX_RE.match(tok):
                    v.append(f"{rp_pre}.glue[{i}].style.{col_k}: token {tok!r} 未在 palette 声明")

    return v


def _rule_set_names():
    try:
        import styleguides as _SG
        return set(_SG.RULE_SETS)
    except Exception:
        return set()


def _check_children(container, path):
    v = []
    for i, c in enumerate(container.get("children", [])):
        cp = f"{path}.children[{i}]({c['id']})"
        ctype = c["type"]
        allowed = CHILD_PER_TYPE.get(ctype)
        if allowed is None:
            v.append(f"{cp}: 容器 children 仅支持 text/shape（不支持 {ctype}）")
            continue
        v += _unknown(c.keys(), allowed, cp)
        for k in ("width", "height"):
            if k in c:
                raw = c[k]
                ok = isinstance(raw, (int, float)) and not isinstance(raw, bool) and float(raw) > 0
                if isinstance(raw, str) and raw.endswith("%"):
                    ok = True
                if not ok:
                    v.append(f"{cp}.{k}: 必须为正数值或 'NN%'，实为 {raw!r}")
    return v


def _check_token_refs(e, palette, path, child=False):
    """style/text_style/line.color 里 palette token 必须已声明。"""
    v = []
    for st_key in ("style", "text_style"):
        st = e.get(st_key) or {}
        for col_k in ("fill", "border", "color", "shadow"):
            tok = st.get(col_k)
            if isinstance(tok, str) and tok not in palette:
                if col_k == "border" and tok == "none":
                    continue
                if col_k == "shadow" and tok in (True, False):
                    continue
                if _HEX_RE.match(tok):          # 裸 hex 合法（与 spec_compile 同规）
                    continue
                v.append(f"{path}.{st_key}.{col_k}: token {tok!r} 未在 palette 声明（或不是 6 位 hex）")
    if e["type"] == "line":
        tok = e.get("color")
        if isinstance(tok, str) and tok not in palette and not _HEX_RE.match(tok):
            v.append(f"{path}.color: token {tok!r} 未在 palette 声明")
    if e["type"] == "graph":
        im = e.get("inner_margin")
        if im is not None and not (isinstance(im, (int, float)) and not isinstance(im, bool) and im >= 0):
            v.append(f"{path}.inner_margin: 必须为非负数值")
        for kk in ("node_w", "node_h"):
            if kk in e:
                val = e[kk]
                if not (isinstance(val, (int, float)) and not isinstance(val, bool) and val > 0):
                    v.append(f"{path}.{kk}: 必须为正数值")
        for i, n in enumerate(e.get("nodes", [])):
            for k in n:
                if k not in NODE_FIELDS:
                    v.append(f"{path}.nodes[{i}].{k}: 未知节点字段（可选 {sorted(NODE_FIELDS)}）")
        for i, ed in enumerate(e.get("edges", [])):
            for k in ed:
                if k not in EDGE_FIELDS:
                    v.append(f"{path}.edges[{i}].{k}: 未知边字段（可选 {sorted(EDGE_FIELDS)}）")
        for i, gr in enumerate(e.get("groups", [])):
            for k in gr:
                if k not in GROUP_FIELDS:
                    v.append(f"{path}.groups[{i}].{k}: 未知组字段（可选 {sorted(GROUP_FIELDS)}）")
    return v