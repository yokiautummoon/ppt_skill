# -*- coding: utf-8 -*-
"""com_layer.py — COM 后处理作业（win_py 子进程，JSON in/out）。

只做 XML/python-pptx 表达不了的事，其余一律不碰（铁律：不重算几何/锚点/z——
改布局 = 改 SPEC 让上游重跑）。

作业输入 com_job.json: {out, base, ir, com?, pdf?}
作业输出 com_out.json: {glue:[...], groups:[...], follow:{...}, png, ole:[...], pdf, warnings}

操作清单（probe 实测背书）：
  1. glue        — BeginConnect/EndConnect 绑定连线端点（stCxn/endCxn 语义，随动）。
                  站点索引 = probe_com_map3 实测表（PowerPoint 16.0）。
  2. follow-test — 移动起点 +60pt 断言连线随动后复原（诊断，WARN 不阻断）。
  3. group       — SPEC group:true 容器：同 owner 形状 Group 成 Office 组对象。
  4. ole         — diagram 元素 src=.vsdx：AddOLEObject 原生 Visio 嵌入（双击可编辑）。
  5. pdf         — job.pdf=true：ExportAsFixedFormat 导出 base.pdf（分发格式，
                  与 ole 同级别：显式请求的产物，失败 = 硬失败）。
  6. png         — Slide.Export 预览（尺寸 = slide 英寸 ×100，plan 契约）。

无 Office/无形状 → 对应项 WARN；退出码 0=全部完成/有 WARN，非 0=硬失败。
"""
import json
import os
import sys

import formula_omml
import formula_templates
import animation_constants
import animation_recipes

# ---- 站点索引 → 边（实测表，PowerPoint 16.0；probe_com_map3.py）----
# 键 = 我们 SPEC 的 kind；值 = {side: site_index(1 基)}
SITE_BY_KIND = {
    "src":     {"N": 2, "S": 4, "E": 5, "W": 3},   # can
    "proc":    {"N": 1, "S": 3, "E": 4, "W": 2},   # rounded_rect
    "judge":   {"N": 1, "S": 3, "E": 4, "W": 2},   # diamond
    "end":     {"N": 1, "S": 5, "E": 7, "W": 3},   # oval
    "rect":    {"N": 1, "S": 3, "E": 4, "W": 2},
    "rounded_rect": {"N": 1, "S": 3, "E": 4, "W": 2},
    "oval":    {"N": 1, "S": 5, "E": 7, "W": 3},
    "diamond": {"N": 1, "S": 3, "E": 4, "W": 2},
    "can":     {"N": 2, "S": 4, "E": 5, "W": 3},
    "parallelogram": {"N": 1, "S": 5, "E": 3, "W": 6},
    "hexagon": {"N": 1, "S": 4, "E": 5, "W": 3},
}
_FOLLOW_PT = 60  # 随动自检步长（params.com.follow_test_pt 同值）

# Dispatch 瞬态启动错误码（重试有效；其余错误立即抛，走调用方降级路径）
_TRANSIENT_HR = {
    -2146959355,   # 0x80080005 CO_E_SERVER_EXEC_FAILURE：Office 进程启动失败（最常见）
    -2147023174,   # 0x800706BA RPC_S_SERVER_UNAVAILABLE：服务器未就绪
    -2147417848,   # 0x80010108 RPC_E_DISCONNECTED：服务器进程掉线
    -2147418113,   # 0x80010001 RPC_E_CALL_REJECTED：服务器忙
}


def dispatch_retry(progid, retries=2, wait=2.0, warnings=None, tag=""):
    """Dispatch 包装：瞬态启动失败自动重试（重试次数/间隔由 params.com 控制）。

    非瞬态错误或重试用尽 → 原样抛回，调用方既有降级/失败路径不变。
    仅 win_py 有效（需要 win32com）。"""
    import time
    import win32com.client as w
    last = None
    for i in range(retries + 1):
        try:
            return w.Dispatch(progid)
        except Exception as ex:
            last = ex
            code = getattr(ex, "hresult", None)
            if code is None and ex.args and isinstance(ex.args[0], int):
                code = ex.args[0]
            if code not in _TRANSIENT_HR or i == retries:
                break
            if "PowerPoint" in (tag or progid):
                # 驻留 GUI 实例（手动打开 POWERPNT.EXE）会阻断 /AUTOMATION 激活，
                # 杀干净后才能干净激活（probe 实测：CO_E_SERVER_EXEC_FAILURE 根因）
                try:
                    import subprocess
                    subprocess.run(["taskkill", "/f", "/im", "POWERPNT.EXE"],
                                   capture_output=True, timeout=20)
                    if warnings is not None:
                        warnings.append(f"已清理驻留 POWERPNT.EXE"
                                        f"（{tag or progid} 激活失败 {code:#010x}）")
                except Exception:
                    pass
            if warnings is not None:
                warnings.append(f"{tag or progid} Dispatch 第 {i + 1} 次失败"
                                f"（{code:#010x}），{wait ** i * wait}s 后重试")
            time.sleep(wait ** i * wait)
    raise last


def _log(m):
    print(m, flush=True)


def find_shape_by_name(slide, name):
    for i in range(1, slide.Shapes.Count + 1):
        sh = slide.Shapes(i)
        try:
            if sh.Name == name:
                return sh
        except Exception:
            continue
    return None


def _add_one_effect(slide, shp, anim):
    """按 animation 配置给形状加一个效果（配方 behaviors 原序），返回回读信息。"""
    C = animation_constants.C
    name = anim["effect"]
    recipe = animation_recipes.RECIPES[name]
    seq = slide.TimeLine.MainSequence
    trig = anim.get("trigger", "with_previous")
    preset = animation_recipes.PRESET_BASE.get(name)
    eff = seq.AddEffect(shp, C("effect." + preset) if preset
                        else C("effect.custom"), 0, C("trigger." + trig))
    eff.Timing.Duration = recipe["dur"]
    eff.Timing.RepeatCount = recipe["repeat"]
    d = anim.get("delay")
    if d:
        eff.Timing.TriggerDelayTime = float(d)
    t = recipe.get("timing") or {}
    if t.get("smooth_start"):
        eff.Timing.SmoothStart = C("tri.true")
    if t.get("smooth_end"):
        eff.Timing.SmoothEnd = C("tri.true")
    if t.get("accelerate") is not None:
        eff.Timing.Accelerate = t["accelerate"]
    if t.get("decelerate") is not None:
        eff.Timing.Decelerate = t["decelerate"]
    if t.get("auto_reverse"):
        eff.Timing.AutoReverse = C("tri.true")
    for b in recipe["behaviors"]:
        bt = b["type"]
        bhv = eff.Behaviors.Add(C("type." + bt))
        bhv.Timing.Duration = b["dur"]
        if b.get("delay"):
            bhv.Timing.TriggerDelayTime = b["delay"]
        if b.get("smooth_start"):
            bhv.Timing.SmoothStart = C("tri.true")
        if b.get("smooth_end"):
            bhv.Timing.SmoothEnd = C("tri.true")
        if b.get("accelerate") is not None:
            bhv.Timing.Accelerate = b["accelerate"]
        if b.get("decelerate") is not None:
            bhv.Timing.Decelerate = b["decelerate"]
        if b.get("auto_reverse"):
            bhv.Timing.AutoReverse = C("tri.true")
        if bt == "set":
            bhv.SetEffect.Property = C("prop.visibility")
            bhv.SetEffect.To = b["to"]
        elif bt == "filter":
            bhv.FilterEffect.Reveal = (C("tri.true") if b["reveal"]
                                       else C("tri.false"))
            bhv.FilterEffect.Type = C("filter.fade")
        elif bt == "property":
            bhv.PropertyEffect.Property = C("prop." + b["attrib"])
            for p in b["points"]:
                pt = bhv.PropertyEffect.Points.Add()
                pt.Time = p[0]
                pt.Value = p[1]
                if len(p) > 2 and p[2]:
                    pt.Formula = p[2]
        elif bt == "scale":
            bhv.ScaleEffect.FromX = b["from_x"]
            bhv.ScaleEffect.FromY = b["from_y"]
            bhv.ScaleEffect.ToX = b["to_x"]
            bhv.ScaleEffect.ToY = b["to_y"]
        elif bt == "rotation":
            bhv.RotationEffect.From = b["from"]
            bhv.RotationEffect.To = b["to"]
        elif bt == "motion":
            bhv.MotionEffect.FromX = b["from_x"]
            bhv.MotionEffect.FromY = b["from_y"]
            bhv.MotionEffect.ToX = b["to_x"]
            bhv.MotionEffect.ToY = b["to_y"]
            bhv.MotionEffect.Path = b["path"]
        else:
            raise ValueError(f"未知 behavior 类型 {bt}")
    nb = len(recipe["behaviors"])
    if recipe.get("delete_first"):
        eff.Behaviors(1).Delete()
    tu = recipe.get("text_unit")
    if tu:
        seq.ConvertToTextUnitEffect(eff, C("level." + tu))
    final_behaviors = eff.Behaviors.Count
    info = {"effect": name, "preset_base": preset, "trigger": trig,
            "detail": f"配方 behaviors={nb} 构造后 Count={final_behaviors}"
                      f"{' 预设=' + preset if preset else ' 预设=Custom(0)'}"}
    if d:
        info["delay"] = float(d)
    return info


def _apply_anims(slide, ir, out, page_tag):
    """SPEC 元素 animation（进入）+ 可选 animation_exit（退出）-> PowerPoint 动画。
    两段效果都用命名配方构造；退出效果排在进入之后（常用 on_click 触发）。"""
    seq_ids = ir.get("anim_sequence")
    if seq_ids:
        in_seq = set(seq_ids)
        by_id = {e["id"]: e for e in ir["elements"]}
        order = [by_id[i] for i in seq_ids] + [
            e for e in ir["elements"]
            if (e.get("animation") or e.get("animation_exit"))
            and e["id"] not in in_seq]
    else:
        order = [e for e in ir["elements"]
                 if e.get("animation") or e.get("animation_exit")]
    for e in order:
        rec = {"id": e["id"], "effect": None, "ok": False, "detail": ""}
        try:
            shp = find_shape_by_name(slide, e["id"])
            if shp is None:
                raise ValueError("形状未找到（渲染未生成）")
            info = _add_one_effect(slide, shp, e["animation"])
            rec.update(ok=True, **info)
            _log(f"[com] anim {page_tag}{e['id']}: OK {info['effect']} {info['detail']}")
            exit_anim = e.get("animation_exit")
            if exit_anim:
                info2 = _add_one_effect(slide, shp, exit_anim)
                rec["exit_effect"] = info2["effect"]
                _log(f"[com] anim-exit {page_tag}{e['id']}: OK {info2['effect']} {info2['detail']}")
        except Exception as exc:
            rec["detail"] = str(exc)[:160]
            _log(f"[com] anim {page_tag}{e['id']}: WARN {rec['detail']}")
        out["anim"].append(rec)
    if seq_ids and ir.get("anim_timeline"):
        _check_timeline_after(slide, ir, order, page_tag)


def _check_timeline_after(slide, ir, order, page_tag):
    """COM 回读动画组时间轴（TimeAligner 量化第二层）：按加入序逐个 effect
    回读 Timing.TriggerDelayTime，与引擎绝对时间轴比对；超差 WARN 记账不阻断
    （PowerPoint 对 delay 的存储精度未知，容差取 1/50 秒）。首尾相接/对齐的
    代数一致性由引擎展开断言（anim_group.violations）保证，此处验运行时接受度。"""
    tl = {r["id"]: r for r in (ir.get("anim_timeline") or [])}
    if not tl:
        return
    seq = slide.TimeLine.MainSequence
    for i, e in enumerate(order):
        want = tl.get(e["id"])
        if not want:
            continue
        try:
            eff = seq.Effects(i + 1)
            got = getattr(eff.Timing, "TriggerDelayTime", None)
        except Exception:
            continue
        if got is None:
            continue
        got = float(got)
        if abs(got - want["delay"]) > 0.02:
            _log(f"[com] anim 时间轴 {page_tag}{e['id']}: WARN 回读 "
                 f"delay={got:.3f} ≠ 引擎 {want['delay']:.3f}")


def _apply_formulas(base, irs, warnings):
    """子集外公式 → Word 批量引擎 → python-pptx 注入替换占位文本框。
    复用 renderer 的 _wrap_formula_mc（mc 包装 + Choice 公式 + Fallback 原文）。
    必须在 PowerPoint 释放文件后调用（python-pptx 写 base.pptx）。
    多页：pending 带页号（公式可能分布在不同页）。"""
    pending = []   # (page_idx, eid, expr, ts, fs)
    for pi, ir in enumerate(irs):
        for e in ir["elements"]:
            if e["type"] != "formula":
                continue
            ts = e.get("text_style") or {}
            fs = ts.get("fs", 18)
            # 只兜"parse 与离线模板都没覆盖"的表达式（模板命中的 render 已注入）
            if not formula_templates.supported(e["expr"], fs):
                pending.append((pi, e["id"], e["expr"], ts, fs))
    if not pending:
        return {"pending": 0, "injected": [], "failed": []}
    _log(f"[com] formula 兜底 {len(pending)} 项：Word 批量引擎…")
    import omml_engine
    results = omml_engine.word_batch_omml([p[2] for p in pending])
    try:
        from pptx import Presentation
        import render_pptx as RP
        prs = Presentation(base)
        injected, failed = [], []
        for (pi, eid, expr, ts, fs), res in zip(pending, results):
            sl = prs.slides[pi]
            sh = None
            for s in sl.shapes:
                if s.name == eid:
                    sh = s
                    break
            if sh is None or not res.get("ok"):
                detail = res.get("reason") if sh is not None else "形状未找到"
                failed.append({"id": eid, "expr": expr, "detail": detail})
                warnings.append(f"formula {eid} 兜底失败（保留占位文本）: {detail}")
                _log(f"[com] formula {eid}: WARN {detail}")
                continue
            RP._wrap_formula_mc(sl, sh._element, res["omml"])
            injected.append(eid)
            _log(f"[com] formula {eid}: OK 引擎注入")
        if injected:
            prs.save(base)
        return {"pending": len(pending), "injected": injected, "failed": failed}
    except Exception as ex:
        warnings.append("公式兜底异常: %s" % str(ex)[:160])
        return {"pending": len(pending), "injected": [], "failed": [{"detail": str(ex)[:160]}]}


def _scan_embedded_fonts(pptx_path):
    """扫包内嵌入字体 part（B5 物证：ppt/fonts/*.fntdata，PowerPoint 嵌入产物）。
    返回排序后的 part 名列表；读取失败/无嵌入返回 []。"""
    import zipfile
    try:
        with zipfile.ZipFile(pptx_path) as z:
            return sorted(n for n in z.namelist()
                          if n.startswith("ppt/fonts/") and n.endswith(".fntdata"))
    except Exception:
        return []


def _readback_overflow(slide, ir, out, page_no, tol_pt):
    """B4 文本溢出真实回读（第二来源）：PowerPoint TextFrame2 报告的文本实高
    （TextRange.BoundHeight）vs 文本框内高（TextFrame2.BoundHeight），超容差即
    记账 + WARN。离线 textmesh 估算是第一来源（渲染期 autofit），此处为 PowerPoint
    自身度量——回读背书「渲染产物在 Office 中的真实排版是否溢出」。只回读带文本
    的形状；读失败静默跳过（不阻断）。"""
    for e in ir["elements"]:
        if e["type"] not in ("text", "shape"):
            continue
        if not (e.get("text") or e.get("runs")):
            continue
        try:
            shp = find_shape_by_name(slide, e["id"])
            if shp is None or not getattr(shp, "HasTextFrame", False):
                continue
            tf2 = shp.TextFrame2
            if not getattr(tf2, "HasText", False):
                continue
            tr_h = float(tf2.TextRange.BoundHeight)
            fr_h = float(tf2.BoundHeight)
            if fr_h <= 0:
                continue
            over = tr_h - fr_h
            rec = {"id": e["id"], "page": page_no,
                   "text_h": round(tr_h, 1), "frame_h": round(fr_h, 1)}
            if over > tol_pt:
                rec["over_pt"] = round(over, 1)
                out["overflow"].append(rec)
                out["warnings"].append(
                    f"{e['id']} 文本溢出回读: 文本高 {tr_h:.1f}pt > 框内高 "
                    f"{fr_h:.1f}pt（超 {over:.1f}pt，PowerPoint 实度）")
                _log(f"[com] overflow {e['id']}: WARN over={over:.1f}pt")
        except Exception:
            continue


def run(job):
    try:
        import win32com.client as w
    except ImportError:
        ws = ["win32com 不可用，COM 层跳过"]
        if job.get("pdf"):
            ws.append("PDF 导出失败: win32com 不可用（无 Office，降级无 PDF）")
        # 早退也要给满键骨架：main() 报表逐键读，缺键会 KeyError（无 Office
        # 跑 --com/--pdf 即触达）；glue/groups/ole/anim 同享此路径。
        return {"glue": [], "groups": [], "follow": {}, "ole": [], "anim": [],
                "formulas": {"pending": 0}, "png": None, "pdf": None,
                "fonts": {"requested": False, "declared": [], "embedded": []},
                "overflow": [], "warnings": ws, "saved": job.get("base")}, 0
    base = job["base"]
    out_dir = job["out"]
    ir_path = job["ir"]
    with open(ir_path, "r", encoding="utf-8") as f:
        ir = json.load(f)
    irs = ir if isinstance(ir, list) else [ir]
    out = {"glue": [], "groups": [], "follow": {}, "ole": [], "anim": [],
           "png": None, "pdf": None,
           "fonts": {"requested": False, "declared": [],
                     "embedded": [], "empty_reason": None},
           "overflow": [], "warnings": [], "saved": base}
    # 重试参数由 build_ppt.py 从合并后的 params.com 传入（无则回退默认）
    com_p = job.get("com") or {}
    _rt = int(com_p.get("dispatch_retries", 2))
    _wt = float(com_p.get("dispatch_wait", 2.0))
    try:
        app = dispatch_retry("PowerPoint.Application", retries=_rt, wait=_wt,
                             warnings=out["warnings"], tag="PowerPoint")
        pres = app.Presentations.Open(base, WithWindow=False)
    except Exception as ex:
        return dict(out, warnings=["打开演示失败: %s" % ex]), 1
    try:
        # ---- 1..4 逐页作业：glue 绑定 / 随动自检(仅页 1) / 组 / OLE ----
        for pi, ir in enumerate(irs):
            slide = pres.Slides(pi + 1)
            _page_tag = f"S{pi + 1} " if len(irs) > 1 else ""
            # ---- 1. glue 绑定 ----
            kind_of = {}
            for e in ir["elements"]:
                if e["type"] == "shape":
                    kind_of[e["id"]] = e.get("kind", "rounded_rect")
            for gl in ir["glue"]:
                rec = {"id": gl["id"], "ok": False,
                       "side1": gl.get("side1"), "side2": gl.get("side2"),
                       "site1": None, "site2": None, "detail": ""}
                try:
                    conn = find_shape_by_name(slide, gl["id"])
                    sa = find_shape_by_name(slide, gl["from_id"])
                    sb = find_shape_by_name(slide, gl["to_id"])
                    if conn is None or sa is None or sb is None:
                        raise ValueError(
                            f"连接器/端点缺失（conn={conn is not None} "
                            f"from={sa is not None} to={sb is not None}）→ 保持坐标锚点直线")
                    s1 = SITE_BY_KIND.get(kind_of.get(gl["from_id"]), {}).get(gl.get("side1"))
                    s2 = SITE_BY_KIND.get(kind_of.get(gl["to_id"]), {}).get(gl.get("side2"))
                    if s1 is None or s2 is None:
                        raise ValueError(f"站点映射缺失 from_kind={kind_of.get(gl['from_id'])} side={gl.get('side1')}")
                    cf = conn.ConnectorFormat
                    cf.BeginConnect(sa, s1)
                    cf.EndConnect(sb, s2)
                    rec.update(ok=True, site1=s1, site2=s2)
                    # 具名锚点（scansci 内化）：绑定就近站点的同时披露锚点绝对位
                    # 与站点位置偏差（>0.25in=18pt 即 WARN；不阻断——降级哲学背书）
                    if gl.get("an1"):
                        try:
                            x, y, w_, h_ = (sa.Left, sa.Top, sa.Width, sa.Height)
                            mid = {"N": (x + w_ / 2, y), "S": (x + w_ / 2, y + h_),
                                   "E": (x + w_, y + h_ / 2), "W": (x, y + h_ / 2)}[gl["side1"]]
                            ax, ay = gl["a1"][0] * 72.0, gl["a1"][1] * 72.0
                            if abs(mid[0] - ax) > 18 or abs(mid[1] - ay) > 18:
                                out["warnings"].append(
                                    f"glue {gl['id']} 锚点 {gl['an1']} 绝对位"
                                    f"({ax:.1f},{ay:.1f}) 偏离侧 {gl['side1']} 站点中点"
                                    f"({mid[0]:.1f},{mid[1]:.1f})—绑定就近站点")
                        except Exception:
                            pass
                except Exception as ex:
                    rec["detail"] = str(ex)[:160]
                out["glue"].append(rec)
                _log(f"[com] glue {_page_tag}{gl['id']}: {'OK' if rec['ok'] else 'WARN'} {rec['detail']}")

        # ---- 2. 随动自检（诊断；仅页 1 代表绑定随动语义）----
            if pi == 0 and out["glue"] and out["glue"][0]["ok"]:
                g0 = out["glue"][0]
                try:
                    conn = find_shape_by_name(slide, g0["id"])
                    sa = find_shape_by_name(slide, ir["glue"][0]["from_id"])
                    gb = conn.ConnectorFormat.BeginConnectedShape
                    before = (conn.Left, conn.Top)
                    sa.IncrementLeft(_FOLLOW_PT)
                    after = (conn.Left, conn.Top)
                    sa.IncrementLeft(-_FOLLOW_PT)
                    moved = after != before and gb.Name == sa.Name
                    out["follow"] = {"ok": moved, "before": before, "after": after,
                                     "bound": gb.Name}
                    _log(f"[com] follow: {'OK' if moved else 'WARN'} bound={gb.Name}")
                except Exception as ex:
                    out["follow"] = {"ok": False, "detail": str(ex)[:120]}

            # ---- 3. 组（SPEC group:true 容器，按页）----
            for g in ir.get("edit_groups") or []:
                try:
                    shapes = [find_shape_by_name(slide, m) for m in g["members"]]
                    shapes = [s for s in shapes if s is not None]
                    if len(shapes) < 2:
                        raise ValueError(
                            f"成员 <2（members={g['members']}，已 Group={len(shapes)}）")
                    grp = slide.Shapes.Range([s.Name for s in shapes]).Group()
                    grp.Name = f"{g['id']}.group"
                    out["groups"].append({"id": g["id"], "ok": True,
                                          "name": grp.Name, "n": len(shapes),
                                          "z_lo": g.get("z_lo"), "z_hi": g.get("z_hi")})
                    _log(f"[com] group {_page_tag}{g['id']}: OK n={len(shapes)}")
                except Exception as ex:
                    out["groups"].append({"id": g["id"], "ok": False,
                                          "detail": str(ex)[:120]})
            # Office Group 改变 spTree 结构 → 组内元素后续 XML 物证须以组为单位
            # 复核（披露性提示，不阻断）
            if ir.get("edit_groups"):
                out["warnings"].append(
                    "编辑组已 Office Group：spTree 结构变更，XML 物证以组为单位复核")

            # ---- 2.5 动画（元素级 animation → 时间轴效应；WARN 降级）----
            _apply_anims(slide, ir, out, _page_tag)

            # ---- 4. OLE 嵌入（diagram src=.vsdx，按页）----
            EMU_PT = 12700
            for e in ir["elements"]:
                if e["type"] != "diagram" or not str(e.get("src", "")).lower().endswith(".vsdx"):
                    continue
                rec = {"id": e["id"], "ok": False, "detail": ""}
                try:
                    x, y, wdt, hgt = (v / EMU_PT for v in e["rect"])
                    ole = slide.Shapes.AddOLEObject(FileName=e["src"], Link=0, DisplayAsIcon=0)
                    ole.Name = e["id"]
                    ole.Left, ole.Top, ole.Width, ole.Height = x, y, wdt, hgt
                    rec.update(ok=True)
                except Exception as ex:
                    rec["detail"] = str(ex)[:160]
                out["ole"].append(rec)
                _log(f"[com] ole {_page_tag}{e['id']}: {'OK' if rec['ok'] else 'FAIL'} {rec['detail']}")

            # ---- 4.7 文本溢出真实回读（B4，第二来源）----
            _readback_overflow(slide, ir, out, pi + 1,
                               float(com_p.get("overflow_tol_pt", 1.0)))

        # ---- 4.6 字体嵌入（B5 font.portable / --embed-fonts）：EmbedTrueTypeFonts
        # 让 PowerPoint 在保存时嵌入 TrueType 字体（须字族授权允许嵌入；MS 自带
        # 字体多为"禁止嵌入"，此时属性置位但包内无 fntdata —— 实测结论见
        # references/ooxml-notes.md「字体嵌入」节，保存后扫包给出诚实结果）。
        if job.get("embed_fonts"):
            out["fonts"]["declared"] = [f for f in (job.get("fonts") or []) if f]
            try:
                pres.EmbedTrueTypeFonts = True
                out["fonts"]["requested"] = True
            except Exception as ex:
                out["warnings"].append("字体嵌入未生效: %s" % str(ex)[:160])
        pres.Save()
    finally:
        try:
            pres.Close()
            app.Quit()
        except Exception:
            pass
    # ---- 5. 公式兜底（PowerPoint 释放文件后才可 python-pptx 写 base.pptx）----
    # 必须在 PNG 预览之前：preview.png 要反映注入后的最终态，否则截图里
    # 子集外公式仍是占位文本（旧顺序导出 → 预览与产物不一致）
    out["formulas"] = _apply_formulas(base, irs, out["warnings"])
    # ---- 字体嵌入物证（B5）：扫最终包 ppt/fonts/*.fntdata ----
    if job.get("embed_fonts"):
        out["fonts"]["embedded"] = _scan_embedded_fonts(base)
        if out["fonts"]["requested"] and not out["fonts"]["embedded"]:
            out["fonts"]["empty_reason"] = "no_fntdata"
            out["warnings"].append(
                "字体嵌入请求生效但包内无 ppt/fonts/*.fntdata：PowerPoint 自动化"
                "路径不产嵌入字体（实测结论），字族授权/可嵌入副本亦可能受限——"
                "见 references/ooxml-notes.md「字体嵌入」节；可用 GUI 另存为勾选"
                "嵌入字体，或改用通用字族")
        elif out["fonts"]["embedded"]:
            _log(f"[com] font embed: OK {len(out['fonts']['embedded'])} 个字体 part 进包")
    # ---- 6. PDF + PNG 预览（同一 PowerPoint 实例：先 ExportAsFixedFormat
    #       再逐页 Slide.Export；两者都消费公式兜底后的最终 base.pptx）----
    try:
        app2 = dispatch_retry("PowerPoint.Application", retries=_rt, wait=_wt,
                              warnings=out["warnings"], tag="PowerPoint(预览)")
        try:
            pres2 = app2.Presentations.Open(base, WithWindow=False)
            if job.get("pdf"):
                try:
                    pdf_path = os.path.join(out_dir, "base.pdf")
                    # 32 = ppSaveAsPDF（PowerPoint 2010+ 标准）。用 SaveAs 而非
                    # ExportAsFixedFormat：后者在精简版 Office 的类型库中参数被
                    # 降成 Object（pywin32/PowerShell 均无法传参），SaveAs 的
                    # (str, int) 签名转换稳定，且是「另存为 PDF」最通用路径。
                    pres2.SaveAs(pdf_path, 32)
                    out["pdf"] = pdf_path
                    _log(f"[com] pdf: OK {pdf_path}")
                except Exception as ex:
                    out["warnings"].append("PDF 导出失败: %s" % str(ex)[:160])
                    out["pdf"] = None
            out["previews"] = []
            if job.get("previews", True):
                for pi, ir in enumerate(irs):
                    sw, sh = ir["slide"]
                    png = os.path.join(out_dir, "preview.png" if pi == 0
                                       else f"preview-{pi + 1}.png")
                    pres2.Slides(pi + 1).Export(png, "PNG",
                                                int(round(sw * 100)),
                                                int(round(sh * 100)))
                    out["previews"].append(png)
            pres2.Close()
        finally:
            try:
                app2.Quit()
            except Exception:
                pass
        out["png"] = out["previews"][0] if out["previews"] else None
        if out["previews"]:
            _log(f"[com] png: OK {len(out['previews'])} 页预览（首页 {out['png']}）")
        else:
            _log("[com] png: skip（job.previews=false）")
    except Exception as ex:
        out["warnings"].append("PNG 导出失败: %s" % str(ex)[:120])
    # OLE / PDF 是明确要求的产物：失败 = 硬失败（非 0）；glue/group/公式兜底
    # 失败已降级 → WARN
    rc = 1 if any(g.get("ok") is False for g in out["ole"]) else 0
    if job.get("pdf") and not out.get("pdf"):
        rc = 1
    return out, rc


def main(argv=None):
    job_path = argv[0] if argv else sys.argv[1]
    with open(job_path, "r", encoding="utf-8") as f:
        job = json.load(f)
    out, rc = run(job)
    out_path = os.path.join(job["out"], "com_out.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1, default=str)
    _log(json.dumps({"exit": rc,
                     "glue_ok": sum(1 for g in out["glue"] if g.get("ok")),
                     "group_ok": sum(1 for g in out["groups"] if g.get("ok")),
                     "ole_ok": sum(1 for g in out["ole"] if g.get("ok")),
                     "anim_ok": sum(1 for a in out["anim"] if a.get("ok")),
                     "pdf": bool(out.get("pdf")),
                     "fonts_embedded": len(out.get("fonts", {}).get("embedded") or []),
                     "overflow_n": len(out.get("overflow") or []),
                     "warnings": len(out["warnings"])},
                    ensure_ascii=False))
    return rc


if __name__ == "__main__":
    sys.exit(main())