# -*- coding: utf-8 -*-
"""spec_fixer.py — R1–R4 确定性机械修复（= 动作库默认项，决策部件②/④）。

修复边界（决策"仅机械可推导类"）：每一动作从 verify 的 **detail 文本**提取
当前数值（attribution 已把元素 id 定位好），按保守算法计算修正值，只产出
revision 列表——不改 IR/产物，由 revisioner 事务应用 + fix.diff 审计。
与 llm_fixer 同接口：input(SPEC 页段, violations, context) → output(revisions, audit)。

revision 条目（revisioner/llm_fixer 同构）：
  {"action", "path", "old", "new", "basis", "confidence", "data_source"}
  path = (段, ...) 结构路径：("elements", idx, 字段) / ("relations", "overlap", "+")。

机械规则表（决策部件②）：
  R1 autofit  T 溢出 → 逐级降号到 min_fs；仍溢 → 安全区内扩框
  R2 safety   G 溢出安全区 → margin 内收缩/平移（保宽高比与相对位）
  R3 overlap  D/S 遮挡无合法源 → 保守补 relations.overlap
  R4 zfix     S z 冲突（物证再报）→ 按声明序补 relations.z_override 显式化
  fontscale   字号越档 → clamp 至 type_scale 合法档

收敛护栏（防 R1↔R2 死循环）：
  - R1 扩框以安全区为界，超界 → manual（拆元素/换内容是语义决策）；
  - R2 收缩保宽高比（等比缩放）；
  - 容器 children（求解器产 rect/fs，SPEC 无显式字段）→ manual；
  - 组包络/无量化 detail → manual（改布局参数是语义）。
"""
import re

# ---- detail 数值提取（verify.py 的 detail 文案契约；attribution 已定位 id）----
_RE_RECT = re.compile(r"rect=\(([-\d.]+), ([-\d.]+), ([-\d.]+), ([-\d.]+)\)")
_RE_HZ = re.compile(r"max_w=([\d.]+)pt 框=([\d.]+)pt")
_RE_VT = re.compile(r"need_h=([\d.]+)pt 框=([\d.]+)pt")
_RE_FS_MIN = re.compile(r"fs=([\d.]+)pt min=([\d.]+)pt")
_RE_SCALE = re.compile(r"fs=([\d.]+) 规范\[([\d.]+),([\d.]+)\]")
_RE_BODY = re.compile(r"fs=([\d.]+) 规范≥([\d.]+)")


def _rev(action, path, old, new, basis, confidence, data_source):
    return {"action": action, "path": path, "old": old, "new": new,
            "basis": basis, "confidence": confidence, "data_source": data_source}


def _find_elem(spec_page, eid):
    """按元素 id 找页 elements 中的 (索引, 元素 dict)；页内 id 唯一（编译期保证）。"""
    for i, e in enumerate(spec_page.get("elements") or []):
        if e.get("id") == eid:
            return i, e
    return None, None


def _explicit_fs(e):
    """SPEC 元素显式 text_style.fs（None = 未声明，IR 用参数默认）。"""
    ts = e.get("text_style")
    if isinstance(ts, dict) and "fs" in ts:
        return ts["fs"]
    return None


def _safety_rect(spec_page, p):
    """安全区：meta.margin（已与全局合并）或整页 ⊆ slide。返回 (l, t, r, b, sw, sh)。"""
    m = (spec_page.get("meta") or {}).get("margin") or {}
    sw, sh = p["slide"]["w"], p["slide"]["h"]
    return (m.get("l", 0), m.get("t", 0), m.get("r", 0), m.get("b", 0), sw, sh)


def _clamp_rect_to_safety(x, y, w, h, m_l, m_t, m_r, m_b, sw, sh):
    """平移 + 等比收缩把 rect 塞回安全区；返回修正后 rect 或 None（物理不可能）。"""
    avail_w = sw - m_l - m_r
    avail_h = sh - m_t - m_b
    if avail_w <= 0 or avail_h <= 0:
        return None
    scale = min(1.0, avail_w / w, avail_h / h)
    if scale <= 0:
        return None
    nw, nh = w * scale, h * scale
    nx = min(max(x, m_l), m_l + avail_w - nw)
    ny = min(max(y, m_t), m_t + avail_h - nh)
    if nx < m_l - 1e-9 or ny < m_t - 1e-9 or nx + nw > sw - m_r + 1e-9 or ny + nh > sh - m_b + 1e-9:
        return None
    return (round(nx, 2), round(ny, 2), round(nw, 2), round(nh, 2))


def _fix_autofit(v, spec_page, p, out, audit):
    """R1：T 溢出。降号优先（决策 R1）；已在硬底或扩框为唯一解时扩框限安全区。"""
    eid = v.element
    i, e = _find_elem(spec_page, eid)
    if i is None:
        audit.append(f"autofit {eid}: 页 elements 无此 id，跳过")
        return
    fs = _explicit_fs(e)
    mn = p["text"]["min_fs"]
    m = _RE_FS_MIN.search(v.detail)      # min_fs 硬底 / 已在硬底
    at_hard = bool(m) and float(m.group(1)) <= mn + 1e-9
    at_floor = fs is not None and fs <= mn + 1e-9
    if fs is not None and not at_floor and not at_hard:
        # 降号一档（步长 2pt，≥ min_fs 硬底）
        new_fs = max(mn, round(fs - 2, 1))
        out.append(_rev("autofit", ("elements", i, "text_style", "fs"),
                        fs, new_fs,
                        f"R1 降号 {fs}→{new_fs}pt（{v.name}）", 0.95, "detail"))
        audit.append(f"autofit {eid}: fs {fs}→{new_fs} 降一档")
        return
    # 已到底/超框：扩框（需 SPEC 显式 rect；需求宽高从 detail 数值反推）
    if "rect" not in e:
        audit.append(f"autofit {eid}: 容器 children 无显式 rect，扩框不可机械定位 → manual")
        return
    x, y, w, h = (float(vv) for vv in e["rect"])
    m_l, m_t, m_r, m_b, sw, sh = _safety_rect(spec_page, p)
    mw = p["text"]["margin_w"]
    need_w = need_h = None
    mz = _RE_HZ.search(v.detail)
    if mz:
        need_w = float(mz.group(1)) / (72.0 * mw)
    vt = _RE_VT.search(v.detail)
    if vt:
        need_h = float(vt.group(1)) / 72.0
    if need_w is None and need_h is None:
        audit.append(f"autofit {eid}: 超框但 detail 无数值，无量化信息 → manual")
        return
    nw = w if need_w is None else max(w, need_w + 0.05)
    nh = h if need_h is None else max(h, need_h + 0.05)
    fixed = _clamp_rect_to_safety(x, y, nw, nh, m_l, m_t, m_r, m_b, sw, sh)
    if fixed is None:
        audit.append(f"autofit {eid}: 扩框超安全区 → manual（拆元素/换内容是语义）")
        return
    for k, (old, new) in enumerate(zip(e["rect"], fixed)):
        if abs(old - new) > 1e-9:
            out.append(_rev("autofit", ("elements", i, "rect", k), old, new,
                            f"R1 扩框 {eid} rect[{k}] {old}→{new}", 0.95, "detail"))
    audit.append(f"autofit {eid}: 降无可降，rect 扩框→{tuple(fixed)}")


def _fix_safety(v, spec_page, p, out, audit):
    """R2：G 溢出安全区。先平移、超界再等比收缩；保宽高比与相对位。"""
    eid = v.element
    if v.name.startswith("组"):
        audit.append(f"safety {eid}: 组包络为派生值，改成员/布局参数是语义 → manual")
        return
    i, e = _find_elem(spec_page, eid)
    if i is None or "rect" not in e:
        audit.append(f"safety {eid}: 无显式 rect，不可机械定位 → manual")
        return
    mw = _RE_RECT.search(v.detail)
    if not mw:
        audit.append(f"safety {eid}: detail 无 rect 数值 → manual")
        return
    x, y, w, h = (float(g) for g in mw.groups())
    m_l, m_t, m_r, m_b, sw, sh = _safety_rect(spec_page, p)
    fixed = _clamp_rect_to_safety(x, y, w, h, m_l, m_t, m_r, m_b, sw, sh)
    if fixed is None:
        audit.append(f"safety {eid}: 安全区物理不可能容纳 → manual")
        return
    for k, (old, new) in enumerate(zip(e["rect"], fixed)):
        if abs(old - new) > 1e-9:
            out.append(_rev("safety", ("elements", i, "rect", k), old, new,
                            f"R2 平移/收缩 {eid} rect[{k}] {old}→{new}", 0.95, "detail"))
    audit.append(f"safety {eid}: rect→{tuple(fixed)}（平移+等比收缩）")


def _fix_overlap(v, spec_page, p, out, audit):
    """R3：遮挡无合法源。保守补 relations.overlap 声明（防重）。"""
    a, b = v.element, v.peer
    rel = spec_page.setdefault("relations", {})
    ovs = rel.setdefault("overlap", [])
    for k, ov in enumerate(ovs):
        if sorted((ov.get("id"), ov.get("with"))) == sorted((a, b)):
            audit.append(f"overlap {a}↔{b}: 已有声明，跳过")
            return
    out.append(_rev("overlap", ("relations", "overlap", "+"), None,
                    {"id": a, "with": b},
                    f"R3 保守补 overlap 声明 {a}↔{b}", 0.95, "spec"))
    audit.append(f"overlap {a}↔{b}: 追加 relations.overlap 声明")


def _fix_zfix(v, spec_page, p, out, audit):
    """R4：z 冲突。按声明序补 relations.z_override 显式化。"""
    eid = v.element
    i, e = _find_elem(spec_page, eid)
    if i is None:
        audit.append(f"zfix {eid}: 页 elements 无此 id，跳过")
        return
    z = i + 1                      # 声明序 1-based 显式化
    rel = spec_page.setdefault("relations", {})
    zs = rel.setdefault("z_override", [])
    for k, oz in enumerate(zs):
        if oz.get("id") == eid:
            if abs(oz.get("z", -1) - z) > 1e-9:
                out.append(_rev("zfix", ("relations", "z_override", k, "z"),
                                oz.get("z"), z,
                                f"R4 z 显式化 {eid} {oz.get('z')}→{z}", 0.95, "spec"))
            return
    out.append(_rev("zfix", ("relations", "z_override", "+"), None,
                    {"id": eid, "z": z},
                    f"R4 按声明序补 z_override {eid} z={z}", 0.95, "spec"))
    audit.append(f"zfix {eid}: z_override z={z}（声明序显式化）")


def _fix_fontscale(v, spec_page, p, out, audit):
    """fontscale：字号越档 → clamp 到 type_scale 合法档（节点/标签/正文）。"""
    eid = v.element
    i, e = _find_elem(spec_page, eid)
    if i is None:
        audit.append(f"fontscale {eid}: 页 elements 无此 id，跳过")
        return
    ms = _RE_SCALE.search(v.detail)
    if ms:
        fs, lo, hi = float(ms.group(1)), float(ms.group(2)), float(ms.group(3))
        new_fs = min(max(fs, lo), hi)
    else:
        mb = _RE_BODY.search(v.detail)
        if not mb:
            audit.append(f"fontscale {eid}: detail 无数值 → manual")
            return
        fs, lo = float(mb.group(1)), float(mb.group(2))
        new_fs = max(fs, lo)
    if abs(new_fs - fs) < 1e-9:
        audit.append(f"fontscale {eid}: fs 已在合法档（detail 与 SPEC 不同源？）→ manual")
        return
    old = _explicit_fs(e)
    ts = e.get("text_style") or {}
    if not isinstance(ts, dict):
        ts = {}
    has_fs = "fs" in ts
    if not has_fs:
        # 显式化修正值：新增 text_style.fs（IR 一直消费默认，加显式即行为变更）
        out.append(_rev("fontscale", ("elements", i, "text_style", "fs"), None,
                        new_fs, f"字号越档 {eid}：显式化 fs={new_fs}（{v.name}）",
                        0.9, "detail"))
        audit.append(f"fontscale {eid}: 新增显式 fs={new_fs}")
        return
    if abs(old - new_fs) > 1e-9:
        out.append(_rev("fontscale", ("elements", i, "text_style", "fs"), old,
                        new_fs, f"字号越档 {eid}：{old}→{new_fs}（{v.name}）",
                        0.95, "detail"))
    audit.append(f"fontscale {eid}: fs {old}→{new_fs}（clamp 合法档）")


_ACTIONS = {
    "autofit": _fix_autofit,
    "safety": _fix_safety,
    "overlap": _fix_overlap,
    "zfix": _fix_zfix,
    "fontscale": _fix_fontscale,
}
# 不机械可修的 fixable 动作（内容缺失）留给 llm_fixer/人工
_SKIP = {"content"}


def fix_page(spec_page, p, violations):
    """spec_page: build_pages 输出的页级 SPEC dict（meta/elements/relations）。
    p: params.resolve 结果。violations: attribution.Violation（本页违规）。
    → (revisions, audit)。audit 条目不产出 revision 的理由链（供 runbook/指引）。"""
    out, audit = [], []
    for v in violations:
        fn = _ACTIONS.get(v.action)
        if fn is None:
            if v.action in _SKIP:
                audit.append(f"{v.name}: 内容缺失 → llm/人工（{v.action}）")
            else:
                audit.append(f"{v.name}: 无机械规则（{v.klass}/{v.action}）→ manual")
            continue
        try:
            fn(v, spec_page, p, out, audit)
        except Exception as ex:
            audit.append(f"{v.name}: 机械修复异常 {type(ex).__name__}: {ex} → manual")
    return out, audit