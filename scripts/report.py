# -*- coding: utf-8 -*-
"""report.py — 校验报告格式化 / 退出码映射（build_ppt 用）。

退出码（pipeline.md 契约）：
  0 全过（无 COM 时降级仍 0） | 1 IO | 2 编译静态失败 | 3 校验 FAIL |
  4 渲染/物证失败。COM 结果默认 WARN 不阻断（--com-strict 才阻断）。
"""
import json


# ---- 设计体检：让 agent 看见「是否真的用了新版设计能力」----
# 不参与 exit 码（审美取舍是语义裁定）；是 report 与 console 的反馈层。
_VISUAL = {"chart", "image", "diagram", "typst", "icon", "brush",
           "graph", "table", "formula"}
_MIX_ORDER = ("text", "shape", "icon", "chart", "image", "diagram", "typst",
              "brush", "table", "formula", "graph", "stack", "dock", "curve")

# AI 感痕迹阈值缺省（params.verify.ai_tells 可覆盖；源 anthropics/skills pptx §Avoid）
_AI_DEFAULT = {"enabled": True, "thin_h": 0.08, "title_gap": 0.22,
               "bar_h_max": 0.38, "full_w_ratio": 0.90, "edge_band": 0.55,
               "stripe_w_max": 0.09, "stripe_h_min": 0.25, "edge_gap": 0.07}
# 配色支配度缺省（params.verify.color_dominance 可覆盖；源官方 §Dominance）
_CD_DEFAULT = {"min_share": 0.55, "area_floor": 4.0}
_CELL = 0.5   # 覆盖栅格粒度(in)——密度/配色权重按 cell 并集算（防重叠重复计）


def _raster(irs):
    """把每页 shape 栅格化到 0.5in cell：①每页被覆盖 cell 数（密度，并集不重复计）；
    ②全篇逐 cell 的 topmost 填充色计数（配色视觉权重）。整幅背景块（≥0.85 slide
    面积）不计入密度——背景是底不是堆砌。"""
    dens = [0] * len(irs)
    colors = {}
    for pi, ir in enumerate(irs):
        sw, sh = ir.get("slide", (13.333, 7.5))
        nx, ny = max(1, int(sw / _CELL)), max(1, int(sh / _CELL))
        slide_area = sw * sh
        covered = set()
        cell_color = {}
        for e in sorted(ir.get("elements") or [], key=lambda x: x.get("z", 0)):
            x, y, w, h = e.get("rect") or (0, 0, 0, 0)
            is_bg = (w * h) >= 0.85 * slide_area
            f = (e.get("style") or {}).get("fill")
            for cx in range(max(0, int(x / _CELL)), min(nx, int((x + w) / _CELL) + 1)):
                for cy in range(max(0, int(y / _CELL)), min(ny, int((y + h) / _CELL) + 1)):
                    if is_bg:
                        # 背景：算配色权重（底层，setdefault 让内容覆盖）不计密度
                        if isinstance(f, str) and f != "none":
                            cell_color.setdefault((cx, cy), f)
                        continue
                    covered.add((cx, cy))
                    if isinstance(f, str) and f != "none":
                        cell_color[(cx, cy)] = f
        dens[pi] = len(covered) / max(nx * ny, 1)
        for f in cell_color.values():
            colors[f] = colors.get(f, 0) + 1
    return dens, colors


def conversion_hints(irs):
    """内容处理转换律（advisory；源 conversion.py）——report 侧薄封装。"""
    import conversion as CV
    return CV.conversion_hints(irs)


def _text_fs(e):
    """元素声明/实测字号（无则 None）。"""
    tl = e.get("text_layout") or {}
    if tl.get("fs") is not None:
        return tl["fs"]
    ts = e.get("text_style") or {}
    return ts.get("fs")


def _ai_tells(ir, ait):
    """内容页 AI 痕迹（advisory）：官方 pptx skill §Avoid 的机器化三条——
    ①标题下细横条（"hallmark of AI-generated slides"）②跨页宽装饰条（头/脚色条）
    ③卡片单边强调条（"单边描边"/侧条）。**只对内容页报**：页型意图页的 deco/band
    是审定破格点（owner 令牌归属），豁免——官方反对的是内容页上重复的填充式色条。"""
    tips = []
    if ir.get("page_intent") or not ait.get("enabled", True):
        return tips
    sw, sh = ir.get("slide", (13.333, 7.5))
    els = ir.get("elements") or []
    titles = [e for e in els if e.get("type") == "text" and e.get("text")]
    bars = []
    for e in els:
        if e.get("type") not in ("shape", "line", "curve", "icon"):
            continue
        x, y, w, h = e.get("rect") or (0, 0, 0, 0)
        if w > 0 and h > 0:
            bars.append((e, x, y, w, h))
    cards = [(e, *e["rect"]) for e in els
             if e.get("type") == "shape" and (e.get("rect") or [0, 0, 0, 0])[2] > 0.8
             and (e.get("rect") or [0, 0, 0, 0])[3] > 0.5]
    for e, x, y, w, h in bars:
        # ① 标题下细横条
        if h <= ait["thin_h"] and w >= 0.25:
            for t in titles:
                tx, ty, tw, th = t["rect"]
                gap = y - (ty + th)
                if -0.02 <= gap <= ait["title_gap"] \
                        and tx <= x + w / 2.0 <= tx + tw:
                    tips.append(f"标题下细横条（{e.get('id', '?')}）——AI 生成式装饰，"
                                "改用留白/底色分隔（官方 pptx skill §Avoid）")
                    break
        # ② 跨页宽装饰条（头/脚色条）
        if w >= ait["full_w_ratio"] * sw and h <= ait["bar_h_max"] \
                and (y <= ait["edge_band"] or y + h >= sh - ait["edge_band"]):
            tips.append(f"跨页宽装饰条（{e.get('id', '?')}）——头/脚色条读作 AI 填充，"
                        "删条或改底色（官方 pptx skill §Avoid）")
        # ③ 卡片单边强调条
        if w <= ait["stripe_w_max"] and h >= ait["stripe_h_min"]:
            for c, cx, cy, cw, ch in cards:
                if c is e or h > ch + 0.02:
                    continue
                if cy - 0.02 <= y and y + h <= cy + ch + 0.02 \
                        and (abs(x - cx) <= ait["edge_gap"]
                             or abs((x + w) - (cx + cw)) <= ait["edge_gap"]):
                    tips.append(f"卡片单边强调条（{e.get('id', '?')}）——AI 填充式装饰，"
                                "改底色/阴影/图标区分（官方 pptx skill §Avoid）")
                    break
    seen, out = set(), []
    for t in tips:
        if t not in seen:
            seen.add(t)
            out.append(t)
    return out


def _layout_sig(ir):
    """页内视觉骨架签名（近似 A1 签名）：非文本元素的 (类型, 4×3 网格, 尺寸档)。
    换文案/配色不改签名——只有真正换版式骨架才改。页型意图页以 (intent, 变体)
    为签名（同 intent 同变体重复算重复——变体家族本就该轮换）。"""
    if ir.get("page_intent"):
        return (("intent", ir["page_intent"], ir.get("page_intent_variant") or ""),)
    sw, sh = ir["slide"]
    items = []
    for e in ir["elements"]:
        if e["type"] == "text":
            continue
        x, y, w, h = e["rect"]
        gx = min(int(x / max(sw / 4.0, 1e-9)), 3)
        gy = min(int(y / max(sh / 3.0, 1e-9)), 2)
        ratio = (w * h) / max(sw * sh, 1e-9)
        sz = "S" if ratio < 0.04 else ("M" if ratio < 0.12 else "L")
        items.append((e["type"], gx, gy, sz))
    return tuple(sorted(items))


def design_audit(irs, titles=None, params=None, theme_used=False):
    """逐页原语构成 / 视觉主体 / 强调密度 + 视觉丰度 + AI 感痕迹 + 全篇建议
    （advisory，不阻断）。

    用途：agent 无视觉能力时，用机器统计确认「新版设计能力」是否真的被用上——
    否则 SPEC 即使全绿，画面也可能与旧版同质。返回 (rows, warns)。

    丰度/AI 痕迹阈值取自 params.verify.abundance / ai_tells / color_dominance；
    theme_used=True 表示 deck 已声明 meta.theme（配色具体性检查用）。"""
    v = (params or {}).get("verify") or {}
    ab = v.get("abundance") or {}
    ait = dict(_AI_DEFAULT, **(v.get("ai_tells") or {}))
    cd = dict(_CD_DEFAULT, **(v.get("color_dominance") or {}))
    vis_min = ab.get("visual_ratio_min", 0.34)
    dens_max = ab.get("density_max", 0.85)
    span_min = ab.get("type_span_min", 3)
    rows = []
    sigs = []
    total_emph = total_icon = 0
    all_fs = set()
    dens_by_page, color_cells = _raster(irs)
    dens_peak = 0.0
    n_tell = 0
    for pi, ir in enumerate(irs):
        els = ir["elements"]
        sw, sh = ir.get("slide", (13.333, 7.5))
        cnt = {}
        for e in els:
            cnt[e["type"]] = cnt.get(e["type"], 0) + 1
        # 视觉主体：图表/图块计 1；svg 块展开为 N 片 svgpath → 按 owner 去重计 1
        visual = sum(1 for e in els if e["type"] in _VISUAL)
        visual += len({e.get("owner") for e in els
                       if e["type"] == "svgpath" and e.get("owner")})
        emph = 0
        for e in els:
            for r in (e.get("runs") or []):
                if r.get("emph"):
                    emph += 1
            for row in (e.get("cell_runs") or []):
                for cell in (row or []):
                    for r in (cell or []):
                        if r.get("emph"):
                            emph += 1
        icons = cnt.get("icon", 0)
        svg_blocks = len({e.get("owner") for e in els
                          if e["type"] == "svgpath" and e.get("owner")})
        total_emph += emph
        total_icon += icons
        # ---- 视觉丰度：留边检查 + 字号档采集（密度由栅格统一算）----
        margin_ok = True
        ml_eps = 0.5 - 1e-6
        for e in els:
            x, y, w, h = e.get("rect") or (0, 0, 0, 0)
            if x < ml_eps or y < ml_eps or x + w > sw - ml_eps or y + h > sh - ml_eps:
                margin_ok = False
            fs = _text_fs(e)
            if fs:
                all_fs.add(round(fs, 1))
        density = dens_by_page[pi]
        dens_peak = max(dens_peak, density)
        tips = []
        # 页型意图页由引擎展开审定版式（面板/序号/阶段链等）——结构本身即
        # 视觉主体，不按「无 chart/icon/typst」误报
        if len(els) >= 3 and visual == 0 and not ir.get("page_intent"):
            tips.append("无视觉主体")
        # AI 感痕迹（仅内容页）
        tell = _ai_tells(ir, ait)
        tips.extend(tell)
        n_tell += len(tell)
        # 页型意图页版式由引擎展开（含 section 分隔页）——同 verify._layout_page_sig，
        # 不计入骨架重复统计，避免分隔页被判「千页一面」
        if len(els) >= 3:
            sigs.append((pi, _layout_sig(ir)))
        rows.append(dict(page=pi + 1,
                         title=(titles[pi] if titles and pi < len(titles) else ""),
                         intent=ir.get("page_intent"),
                         types=cnt, visual=visual, icons=icons, svg=svg_blocks, emph=emph,
                         density=round(density, 3), margin_ok=margin_ok,
                         tips=tips))
    # ---- 内容页 vs 全页统计（页型意图页计为有视觉主体）----
    content = [(i, r) for i, r in enumerate(rows) if not r.get("intent")]
    vis_pages = sum(1 for r in rows if r["visual"] >= 1 or r.get("intent"))
    vis_ratio = vis_pages / max(len(rows), 1)
    warns = []
    if len(irs) >= 3 and total_icon == 0:
        warns.append("全篇未使用矢量图标（type: icon）——并行要点/卡片/流程节点"
                     "建议配图标（见 references/icon-library.md）")
    total_svg = sum(r["svg"] for r in rows)
    if len(irs) >= 3 and total_svg == 0:
        warns.append("全篇未使用矢量图（type: svg）——时间线/螺旋/雷达等示意图宜用"
                     "原生 DrawingML 精密矢量图（可缩放换色），见 references/svg-figures.md")
    if total_emph == 0:
        warns.append("全篇未使用富文本强调（[[…]]）——关键数字/术语建议强调，"
                     "每页 ≤4 处（见 references/design-norms.md）")
    if len(sigs) >= 3:
        groups = {}
        for pi, sig in sigs:
            groups.setdefault(sig, []).append(pi + 1)
        for pages in groups.values():
            if len(pages) > 2:
                warns.append(f"版式骨架重复：页 {pages} 结构相同——换左右分栏/"
                             f"图标行/图文混排骨架（阈值见 design-norms.md）")
                break
    # ---- 视觉丰度（advisory；阈值 params.verify.abundance）----
    if len(rows) >= 3 and vis_ratio < vis_min:
        warns.append(f"视觉主体页占比 {vis_ratio:.0%} < {vis_min:.0%}——每内容页"
                     "应配 ≥1 视觉主体（图/图表/图标/typst），别做纯文字页")
    if dens_peak > dens_max:
        warns.append(f"单页元素覆盖密度峰值 {dens_peak:.0%} > {dens_max:.0%}——"
                     "元素堆砌，留白不足（见 design-norms.md §密度目标）")
    if 0 < len(all_fs) < span_min:
        warns.append(f"全篇字号档数 {len(all_fs)} < {span_min}——尺度对比不足，"
                     "标题/正文拉开字号差（见 design-norms.md §字号分层）")
    if any(not r["margin_ok"] for r in rows):
        bad = [r["page"] for r in rows if not r["margin_ok"]]
        warns.append(f"页 {bad} 元素触/越版心边缘——统一 0.5\" 边距（留白）")
    # ---- 配色支配度（源官方 §Dominance over equality）----
    total_cell = sum(color_cells.values())
    if total_cell * (_CELL ** 2) >= cd["area_floor"]:
        share = max(color_cells.values()) / total_cell
        if share < cd["min_share"]:
            warns.append(f"配色平分权重（最大色占比 {share:.0%} < "
                         f"{cd['min_share']:.0%}）——一个主色应占 60–70%，配 1–2 "
                         "辅色 + 1 锐利点缀（官方 pptx skill §Dominance）")
    if not theme_used and len(rows) >= 3:
        warns.append("未声明 meta.theme——配色未针对主题定制，建议从命名预设"
                     "挑一套（见 SKILL.md §主题；判定：换到别的 deck 仍成立即不够具体）")
    if n_tell:
        warns.append(f"检出 {n_tell} 处 AI 感痕迹（标题下横条/装饰色条/卡片单边条）"
                     "——见 tips 与 design-norms.md §AI 感规避")
    # ---- 设计一致性：别只精修一页 ----
    if len(content) >= 3:
        has = [i for i, r in content if r["visual"] >= 1]
        if has and len(has) < len(content):
            plain = [r["page"] for _, r in content if r["visual"] == 0]
            warns.append(f"页 {plain} 无视觉主体而其余页有——设计不一致，"
                         "要么全篇统一要么整体从简（官方 pptx skill §Avoid）")
    return rows, warns


def format_audit(rows, warns):
    """设计体检一行摘要（console 用）。页型意图页由引擎展开版式，计为有视觉主体。"""
    vis = sum(1 for r in rows if r["visual"] >= 1 or r.get("intent"))
    icons = sum(r["icons"] for r in rows)
    emph = sum(r["emph"] for r in rows)
    dens = max((r.get("density") or 0.0) for r in rows) if rows else 0.0
    line = (f"[design] 视觉主体 {vis}/{len(rows)} 页 · 图标 {icons} · "
            f"强调 {emph} · 密度峰值 {dens:.0%}")
    if warns:
        line += " · ⚠ " + "；".join(warns)
    return line


def format_report(rep, ir, stage=None, verbose=True):
    """Report → 可打印摘要文本。stage: 当前管线阶段名。"""
    lines = []
    if stage:
        lines.append(f"== 校验阶段 [{stage}] ==")
    lines.append(f"元素 {len(ir['elements'])} · 连线 {len(ir['lines'])} · "
                 f"glue {len(ir['glue'])} · 组 {len(ir['groups'])} · "
                 f"z_max {ir['z_max']}")
    lines.append(rep.summary())
    return "\n".join(lines)


def exit_code_for(rep, stage=None):
    """按当前 Report 判定退出码：无违规 → 0；否则 3（校验 FAIL）。"""
    return 0 if not rep.violations else 3


def write_report_md(reps, irs, path, titles=None, params=None, theme_used=False):
    """report.md 摘要（逐页校验清单 + 跨页汇总；单页传 [rep]/[ir]）。
    titles: 可选每页标题（来自 meta.slides[i].title）。
    params/theme_used: 透传给 design_audit，避免已声明 meta.theme 的 deck
    在报告里被误报“未声明主题”。"""
    multi = len(irs) > 1
    npass = sum(r.pass_count for r in reps)
    ntotal = sum(len(r.checks) for r in reps)
    nviol = sum(len(r.violations) for r in reps)
    with open(path, "w", encoding="utf-8") as f:
        f.write("# PPT 生成报告\n\n")
        f.write(f"- 页数: {len(irs)}\n")
        f.write(f"- 检验阶段: 布局校验\n")
        f.write(f"- 结果: {'PASS' if not nviol else 'FAIL'} ({npass}/{ntotal} 通过)\n")
        for pi, (rep, ir) in enumerate(zip(reps, irs)):
            title = ""
            if multi and titles and titles[pi]:
                title = f"：{titles[pi]}"
            f.write(f"\n## 页 {pi + 1}{title}\n\n")
            f.write(f"- 元素 {len(ir['elements'])} · 连线 {len(ir['lines'])} · "
                    f"glue {len(ir['glue'])} · 组 {len(ir['groups'])}\n\n")
            f.write("## 校验清单\n\n```text\n")
            f.write(rep.summary(indent="  "))
            f.write("\n```\n")
        rows, warns = design_audit(irs, titles, params=params,
                                   theme_used=theme_used)
        f.write("\n## 设计体检（advisory）\n\n")
        f.write("| 页 | 标题 | 原语构成 | 视觉主体 | 图标 | 强调 | 提示 |\n")
        f.write("| --- | --- | --- | --- | --- | --- | --- |\n")
        for r in rows:
            mix = " · ".join(f"{k}×{v}" for k, v in
                             sorted(r["types"].items(),
                                    key=lambda kv: (_MIX_ORDER.index(kv[0])
                                                    if kv[0] in _MIX_ORDER else 99)))
            if r.get("intent"):
                mix = f"页型:{r['intent']}" + ((" · " + mix) if mix else "")
            f.write(f"| {r['page']} | {r['title'] or ''} | {mix} | "
                    f"{r['visual']} | {r['icons']} | {r['emph']} | "
                    f"{'；'.join(r['tips']) or '—'} |\n")
        if warns:
            f.write("\n**设计建议**：\n\n")
            for w in warns:
                f.write(f"- {w}\n")
        else:
            f.write("\n设计体检无提示。\n")
        if not nviol:
            f.write("\n## 结论\n\n全部断言通过，可继续渲染。\n")
        else:
            f.write("\n## 结论\n\n存在违规，管线应在渲染前停止并修正 SPEC。\n")


def write_ir_json(irs, path):
    """IR 物证导出（供调试/审计/COM 子进程消费）。
    单页写 dict（向后兼容）；多页写 list（com_layer 按页遍历）。"""
    payload = irs if len(irs) > 1 else irs[0]
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=1)