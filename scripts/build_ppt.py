# -*- coding: utf-8 -*-
"""build_ppt.py — 单入口 CLI：SPEC YAML → base.pptx（+ 可选 COM 后处理）。

管线（stage 编号 = 退出码断点，pipeline.md 契约）：
  stage0 load     读 YAML（IO/环境/内部错误 → exit 1）
  stage1 compile  spec_compile 结构检查 + spec_validator 白名单（静态失败 → exit 2）
  stage2 layout   params 合并 + ir_builder.build_ir
  stage3 verify   verify.run → Report（FAIL → exit 3，report 已产出）
  stage4 render   render_pptx.render → base.pptx（错误 → exit 4）
  stage5 evidence render_check_xml.check 物证（FAIL → exit 4）
  stage6 com      可选 --com：win_py 子进程跑 com_layer 作业（JSON in/out）；
                  默认 WARN 不阻断；--com-strict 失败 → exit 5

--fix 修订循环（决策 wiki/decisions/self-improve-loop.md，见 scripts/attribution.py
spec_fixer.py revisioner.py llm_fixer.py）：
  失败（非 IO 编译失败）→ 收集违规 → 归因分类 → 修订链：
    internal → 停机 exit 4（不修 SPEC 不喂 LLM）；
    机械可修（R1–R4 默认动作）→ spec_fixer 确定性修订 → 写回 → 重跑；
    content/advisory → --llm 作业模式（llm_job.json + exit 6 稳态暂停，回填
    llm_out.json 后重跑同命令）；无 --llm → 人工指引。
  每轮修订前快照 .snap.N；轮数用尽仍 FAIL → 回滚最近确定性快照 + 指引。
  --revert 从 fix.diff 反演回滚（恢复最近快照并提示）。

用法：
  win_py scripts/build_ppt.py <spec.yaml> [--out DIR] [--com] [--com-strict]
                              [--pdf] [--report json|md|none]
                              [--strict-images] [--embed-fonts]
                              [--fix [--max-fix N]] [--llm [--max-llm-fix N]]
                              [--llm-client MOD] [--diff FILE] [--revert]

--pdf：导出 base.pdf（分发格式）。隐含进入 stage6（需 Office）；无 Office
       降级 WARN（无 PDF 产物）；显式请求失败（--com-strict 下）→ exit 5。
--strict-images：占位/缺图即编译错（exit 2，B3）；缺省 = 占位框 + img_prompts.md。
--embed-fonts：请求 COM 端字体嵌入（B5，隐含 stage6）；失败/无 fntdata → WARN。
（stage6 亦含 B4 文本溢出真实回读：COM TextFrame2 实高 vs 框内高，超差 WARN 记账。）
"""
import argparse
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import spec_compile  # noqa: E402  （stage1 except 用其异常类型）

STAGE_NAMES = ("load", "compile", "layout", "verify", "render", "evidence", "com")


def _log(msg):
    print(msg, flush=True)


def load_and_validate(path):
    import spec_compile
    import spec_validator
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    data = spec_compile.load_yaml(text)
    # base_dir：meta.template.src 相对 SPEC 目录解析（不含时按 CWD）
    compiled = spec_compile.compile_spec(
        data, base_dir=os.path.dirname(os.path.abspath(path)))
    violations = spec_validator.validate(compiled)
    return compiled, violations


def build_pages(compiled, overrides=None):
    """compiled → 页级 shim 列表（每页独立 build_ir / verify / evidence）。

    配置栈（性质③：统一逐层回退链 DEFAULTS → 全局 meta.params → 页级
    slides[i].params → CLI --param）在页级收敛：margin/framework/params 全走
    统一深覆盖原语（layer_merge/resolve），页级 p 存 shim["_p"]。
    其余 meta 键（slide/style_guide）全局共享。shim 结构与单页 compiled
    同构，ir_builder/verify 无感知。"""
    import copy
    import params as _P

    def _fw_merge(base, override):
        """framework 层覆盖：段是配置单元（background/header/footer），页级可
        新增段或段内键（原浅替换能力）；段内深覆盖保留其余显式值。宽松版——
        framework 键集合由 spec_compile 白名单守住，无需 layer_merge 报未知键。"""
        for k, v in override.items():
            if isinstance(v, dict) and isinstance(base.get(k), dict):
                _fw_merge(base[k], v)
            else:
                base[k] = copy.deepcopy(v)
        return base

    pages = []
    import intents as _IN
    import themes as _TH
    # 页型变体选型（deck 级）：显式 variant 优先，否则同 intent 按出现次序轮换
    # ——确定性、可复现（scripts/intents.py::plan）
    _plan = {s["index"]: s["variant"] for s in _IN.plan(compiled["slides"])}
    globale = compiled.get("meta") or {}
    # 主题（meta.theme 下降）：设计语言打底（配置栈最低层）+ 版心边距缺省源
    _theme = compiled.get("_theme")
    _theme_params = compiled.get("_theme_params")
    _theme_margin = ((_theme or {}).get("geometry") or {}).get("margin") or {}
    # 三明治/深色结构（meta.theme.structure）：深页集合由 intent 判定；深页注入
    # 主题 deep 色全幅背景（build_pages = framework 层，独立于 IR 内容）。
    # 守卫：extract/seed 模板模式不注入全页背景（防遮挡母版背景，pitfall）。
    _structure = ((_theme_params or {}).get("theme") or {}).get("structure", "uniform")
    _struct_on = _structure != "uniform" and not globale.get("template")
    for _pi, page in enumerate(compiled["slides"]):
        meta = dict(globale)
        # layer_merge 是原地深覆盖语义 → base 必须深拷贝，否则页级覆盖会
        # 污染全局（页 1 清空 footer 会让后续页 footer 全空）
        # 版心边距：作者全局 margin 优先；缺省用主题 margin 打底（页级再覆盖）
        _mb = meta.get("margin") or _theme_margin
        meta["margin"] = _P.layer_merge(copy.deepcopy(_mb),
                                        page.get("margin") or {}, "margin")
        meta["framework"] = _fw_merge(copy.deepcopy(meta.get("framework") or {}),
                                      page.get("framework") or {})
        if _struct_on:
            _dark = True if _structure == "dark" \
                else (page.get("page_intent") in _TH.STRUCT_DARK_INTENTS)
            meta["_page_dark"] = _dark
            # 只给深页注入 bg（浅页留白/透出母版）；作者显式 framework.background 优先
            if _dark and not (meta["framework"].get("background")):
                meta["framework"]["background"] = {"fill": "deep"}
        # 备注是页级内容（单页来自 meta.notes，编译期已禁多页全局 notes）
        meta["notes"] = page.get("notes")
        # 意图上下文（brief）：全局打底 + 页级覆盖；非渲染语义，供修订器消费
        if page.get("brief"):
            meta["brief"] = page["brief"]
        # 切换：编译期已把全局默认合并进每页（页声明优先），此处只透传有效值
        meta["transition"] = page.get("transition")
        # 页型意图（审定版式菜单）：agent 只选 token，布局由 ir_builder 展开
        meta["page_intent"] = page.get("page_intent")
        if page.get("page_intent"):
            _pv = copy.deepcopy(page.get(page["page_intent"]) or {})
            if _plan.get(_pi) and not _pv.get("variant"):
                _pv["variant"] = _plan[_pi]
            meta[page["page_intent"]] = _pv
        # 页级配置栈：主题打底 + 全局 meta.params + 页级 params + CLI --param
        _p = _P.resolve(globale.get("params"), page.get("params"),
                        overrides, theme_params=_theme_params)
        # 相对坐标（rect_kind: ratio）→ 绝对 rect（编译期糖，铁律 1：IR 只见绝对）。
        # build_pages 处解——版心边距此刻已收敛（全局/主题/页级叠加）。
        _resolve_ratio_rects(page["elements"], meta.get("slide") or {},
                             meta["margin"], _p)
        shim = {"meta": meta, "palette": compiled["palette"],
                "elements": page["elements"],
                "relations": page.get("relations") or {},
                "params": page.get("params"),
                "_title": page.get("title"),
                "_p": _p}
        pages.append(shim)
    return pages


def _resolve_ratio_rects(page_elements, slide_cfg, margin, p):
    """rect_kind: ratio 相对坐标 → 绝对 rect（编译期糖；铁律 1：IR 只见绝对）。
    rect = dict{x,y,w,h}（0–1 分数）；area ∈ content(默认，页内容区=slide−margin)/
    slide（整页）。越界/形态已由 spec_compile 静态校验；此处只在 build_pages
    （版心边距已收敛）做几何解，就地改写为绝对 rect 并移除 rect_kind（幂等）。"""
    sw = float(slide_cfg.get("w", p["slide"]["w"]))
    sh = float(slide_cfg.get("h", p["slide"]["h"]))
    ml = float(margin.get("l", 0.0)); mt = float(margin.get("t", 0.0))
    mr = float(margin.get("r", 0.0)); mb = float(margin.get("b", 0.0))
    for e in page_elements:
        if e.get("rect_kind") != "ratio":
            continue
        r = e["rect"]
        if e.get("area") == "slide":
            fx, fy, fw, fh = 0.0, 0.0, sw, sh
        else:
            fx, fy, fw, fh = ml, mt, sw - ml - mr, sh - mt - mb
        abs_rect = (fx + r["x"] * fw, fy + r["y"] * fh,
                    r["w"] * fw, r["h"] * fh)
        e["rect"] = tuple(round(v, 3) for v in abs_rect)
        e.pop("rect_kind", None)


def run_com(out_dir, strict, com_params=None, pdf=False, embed_fonts=False,
            fonts=None, previews=True):
    """stage6：win_py 子进程跑 com_layer 作业。com_layer 缺失时给出明确降级。
    pdf=True：job 带 pdf 键，com_layer 导出 base.pdf（显式请求产物）。
    embed_fonts=True（B5）：job 带 embed_fonts/fonts 键，com_layer 请求
    EmbedTrueTypeFonts 并扫包核对产物。
    previews=False：跳过逐页 PNG 预览导出（只看 PPTX 时省时省盘）。"""
    out_dir = os.path.abspath(out_dir)  # 子进程 cwd 不同：作业路径一律绝对
    job = {"out": out_dir, "base": os.path.join(out_dir, "base.pptx"),
           "ir": os.path.join(out_dir, "ir.json"),
           "com": com_params or {}, "pdf": pdf,
           "embed_fonts": bool(embed_fonts), "fonts": list(fonts or []),
           "previews": bool(previews)}
    job_path = os.path.join(out_dir, "com_job.json")
    with open(job_path, "w", encoding="utf-8") as f:
        json.dump(job, f, ensure_ascii=False)
    scripts_dir = os.path.dirname(os.path.abspath(__file__))
    if not os.path.exists(os.path.join(scripts_dir, "com_layer.py")):
        _log("[com] WARN com_layer 缺失，跳过 COM 后处理；产物 = base.pptx")
        return 0
    # 用本解释器（win_py）执行：sys.executable 是绝对路径，CreateProcess 无需 PATH 查找
    # 子进程带 -X utf8（UTF-8 stdout，com_layer 日志可含公式字符如 ∑），
    # 主进程必须显式按 UTF-8 解码，否则 locale（GBK）解码报错
    r = subprocess.run([sys.executable, "-X", "utf8", "-W", "ignore", "-m",
                        "com_layer", job_path], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", cwd=scripts_dir)
    if r.returncode != 0:
        _log(f"[com] FAIL: {r.stdout.strip() or r.stderr.strip()}")
        return 5 if strict else 0
    _log(f"[com] OK: {r.stdout.strip()}")
    return 0


def _parse_param_overrides(params):
    """CLI --param key=value（可重复，after-last-wins）→ 嵌套 dict（配置栈 CLI 层）。
    值按 YAML 类型化（true/false/数字/字符串），路径 'font.latin=xxx' 拆为嵌套。"""
    import yaml as _yaml
    out = {}
    if not params:
        return out
    for item in params:
        if "=" not in item:
            raise SystemExit(f"--param 须为 key=value，实为 {item!r}")
        key, _, raw = item.partition("=")
        val = _yaml.safe_load(raw)
        node = out
        parts = key.split(".")
        for i, part in enumerate(parts):
            if not part:
                raise SystemExit(f"--param 键路径非法: {item!r}")
            if i == len(parts) - 1:
                node[part] = val
            else:
                node = node.setdefault(part, {})
    return out


# ---- --fix 修订循环支撑 ----

def _abs_src(compiled, spec_path):
    """image/diagram 相对 src 按 SPEC 所在目录绝对化（渲染器/COM 不猜路径）。"""
    spec_dir = os.path.dirname(os.path.abspath(spec_path))
    for page in compiled["slides"]:
        for e in page["elements"]:
            if e["type"] in ("image", "diagram") and e.get("src") \
               and not os.path.isabs(e["src"]):
                e["src"] = os.path.join(spec_dir, e["src"])


def _image_prompts(p, compiled):
    """缺图清单（B3）：显式 placeholder 或缺 src 文件缺失的 image 元素。
    返回 [{id,page,prompt,caption,src,rect}]（diagram 走 src 强制，不列）。"""
    out = []
    for pi, page in enumerate(compiled.get("slides") or []):
        stack = list(page.get("elements") or [])
        while stack:
            e = stack.pop()
            stack.extend(e.get("children") or [])
            if e.get("type") != "image":
                continue
            ph = e.get("placeholder")
            src = e.get("src")
            missing = (not src) or not os.path.isfile(src)
            if not ph and not missing:
                continue
            prompt = (ph if isinstance(ph, str) and ph.strip()
                      else (e.get("caption") or p["images"]["missing_key"]))
            out.append({"id": e["id"], "page": pi + 1, "prompt": prompt,
                        "caption": e.get("caption"), "src": src,
                        "rect": list(e.get("rect") or [])})
    return out


def _write_img_prompts(path, items):
    """写缺图提示清单（img_prompts.md）：逐条 id/尺寸/提示词/期望路径。"""
    lines = ["# 缺图提示清单（img_prompts）", "",
             "> 由 build_ppt 生成（B3 图片占位）：以下 image 元素无可用源文件或显式",
             "> 声明了 placeholder。补齐图片（生成后替换/补上 src）再重跑即可；",
             "> `--strict-images` 下缺图直接 exit 2。", ""]
    for it in items:
        r = it["rect"]
        lines.append(f"## p{it['page']}. {it['id']}")
        if len(r) == 4:
            lines.append(f"- 目标尺寸：{r[2]:.2f} × {r[3]:.2f} in"
                         f"（{r[2] * 96:.0f} × {r[3] * 96:.0f} px @96dpi）")
        lines.append(f"- 提示词：{it['prompt']}")
        if it["caption"]:
            lines.append(f"- 占位文案：{it['caption']}")
        lines.append(f"- 期望路径：{it['src'] if it['src'] else '未声明（补 src 后重跑）'}"
                     + ("（当前缺失）" if it["src"] else ""))
        lines.append("")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def _check(spec_path, out_dir=None, overrides=None):
    """stage0–3：compile + validate + layout + verify。成功 → (0, compiled, pages,
    p, irs, reps)；失败 → (rc, msg)。不打印日志（调用方统一打）。verify 违规在
    reps 里（rc 仍 0，是否 exit 3 由调用方判）。
    overrides：CLI --param 解析结果（配置栈 CLI 层，last-wins）。"""
    try:
        compiled, wv = load_and_validate(spec_path)
    except OSError as ex:
        return (1, f"[stage0] FAIL IO: {ex}")
    except spec_compile.SpecCompileError as ex:
        return (2, f"[stage1] FAIL {ex}")
    except Exception as ex:
        return (1, f"[stage1] FAIL 内部 {type(ex).__name__}: {ex}")
    if wv:
        return (2, "[stage1] FAIL 白名单校验:\n  " + "\n  ".join(wv))
    _abs_src(compiled, spec_path)
    # stage1.5 typst 编译闸门：排版块 SVG/PNG 双产物落 out_dir/typst_cache
    # （typst_compile 编译失败 = SPEC 后端源错误，同编译期语义 → exit 2）
    if out_dir is None:
        out_dir = os.path.dirname(os.path.abspath(spec_path))
    try:
        import typst_compile as TC
        for w_ in TC.compile_all(compiled, out_dir,
                                 base_dir=os.path.dirname(os.path.abspath(spec_path))):
            _log(f"[stage1.5] typst WARN: {w_}")
    except TC.TypstCompileError as ex:
        return (2, f"[stage1.5] FAIL typst 编译: {ex}")
    pages = build_pages(compiled, overrides)
    import params as _P
    p = _P.resolve((compiled.get("meta") or {}).get("params"), overrides=overrides,
                   theme_params=compiled.get("_theme_params"))
    # B3 图片占位：缺图不阻断（占位框渲染 + 提示清单）；--strict-images 即 exit 2
    ph_items = _image_prompts(p, compiled)
    if ph_items:
        if p["images"]["strict"]:
            return (2, "[stage1] FAIL --strict-images: 缺图 "
                    + "、".join(f"{i['id']}(p{i['page']})" for i in ph_items)
                    + f"；清单见 {p['images']['prompt_file']}")
        _write_img_prompts(os.path.join(out_dir, p["images"]["prompt_file"]), ph_items)
        compiled["_img_placeholders"] = ph_items
    irs, reps = [], []
    for pi, page in enumerate(pages):
        pp = page["_p"]  # 页级配置栈：全局打底 + 页级 params + CLI --param
        try:
            import ir_builder
            ir = ir_builder.build_ir(page, pp)
        except Exception as ex:
            return (1, f"[stage2] FAIL 布局 (page {pi + 1}): {ex}")
        import verify as V
        irs.append(ir)
        reps.append(V.run(ir, page, pp))
    # C 契约：跨页图去重（多页模式）——同质化最后防线，注入对应页 Report
    if len(pages) > 1:
        for pi, gid, pi0, gid0, det in V.check_graph_dedup(pages):
            reps[pi].add("S", "图重复 sig", False, det)
        # A1 版式多样性（内容页结构签名；阈值 params.verify.layout_variety）
        for pi, name, det in V.check_layout_variety(pages, p):
            reps[pi].add("S", name, False, det)
    return (0, compiled, pages, p, irs, reps)


def _read_spec_text(path):
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    newline = "\r\n" if "\r\n" in text else None
    return text, newline


def _log_verify(reps):
    for pi, rep in enumerate(reps):
        _log(f"[stage2/3] page {pi + 1}/{len(reps)}: 元素 {len(rep.ir['elements'])} · "
             f"verify {rep.pass_count} 通过 / {len(rep.violations)} 违规")
        for fam, name, ok, detail in rep.checks:
            if not ok:
                _log(f"  FAIL [{fam}] {name}: {detail}")


def _fix_loop(args, spec_path, out_dir, overrides=None):
    """--fix 修订循环。返回 rc：0=收敛（继续 stage4+）；3=不可修/超限；
    4=internal 停机；6=需 LLM 稳态暂停（llm_job.json 已写）。
    overrides：CLI --param（配置栈 CLI 层，修订回环内每轮重建保持一致）。"""
    import attribution as A
    import llm_fixer as LF
    import revisioner as R
    import spec_fixer as F

    brief = None
    for _ in range(2):  # 首轮取 compiled meta.brief（_check 重建后不变，全局打底）
        break
    fix_diff = args.diff or os.path.join(out_dir, "fix.diff")
    llm_out = os.path.join(out_dir, "llm_out.json")

    maxfix = args.max_fix
    nround = 0
    last_violated = None

    while nround < maxfix:
        rc = _check(spec_path, out_dir, overrides)
        if rc[0] != 0:
            _log(rc[1])
            return rc[0]
        _, compiled, pages, p, irs, reps = rc
        brief = (compiled.get("meta") or {}).get("brief") or ""
        per_page = [A.classify(r) for r in reps]
        allvs = [v for vs in per_page for v in vs]
        internal, items = R.plan(allvs)
        if internal:
            _log("[fix] FAIL internal 违规：IR/渲染/断言算法不一致，停机报 bug"
                 "（不修 SPEC、不喂 LLM）:")
            for v in internal:
                _log(f"  {v.name}")
            return 4
        nviol = len(allvs)
        _log_verify(reps)

        mech = [i for i in items if i["fixer"] == "spec"]
        need_llm = [i for i in items
                    if i["fixer"] == "llm" or (args.llm and i["fixer"] == "manual"
                                               and i["v"].klass == "advisory")]
        if not mech and not need_llm:
            _log(f"[fix] FAIL 遗留违规 {nviol} 条（无机械动作命中且无 LLM 需求）→ 人工指引：")
            _log("  修订链无可自动项；改 SPEC 后重跑，或 --llm 走语义修订。")
            return 3
        if need_llm and args.llm and not os.path.exists(llm_out):
            # ---- exit 6 稳态暂停：写 llm_job.json，等外层回填 ----
            # 方法论摘要（D 协议）：styleguides 契约表的 semantics.guide 注入作业
            # 上下文——LLM 修订按 style_guide 方法论行事（唯一事实源，不写死文案）
            import styleguides as _SG
            sg = (compiled.get("meta") or {}).get("style_guide")
            sem = (_SG.RULE_SETS.get(sg) or {}).get("semantics") if sg else None
            meth = f"\n方法论({sg}): {sem['guide']}" if sem and sem.get("guide") else ""
            job = LF.build_job(
                spec_path, [{"index": i, "title": pg.get("_title")}
                            for i, pg in enumerate(pages)],
                allvs, brief, (compiled.get("meta") or {}).get("notes") or "",
                [], R.MENU,
                "依据溯源：文本= brief 引文/现有文本改写/[占位]；数据= brief 原文/"
                "[占位]（禁止编造）。动作限菜单；confidence 记入 fix.diff。" + meth)
            LF.write_job(job, os.path.join(out_dir, "llm_job.json"))
            _log(f"[fix] 需 LLM 语义修订 {len(need_llm)} 项（content/advisory）")
            _log(f"[fix] 已写作业 {os.path.join(out_dir, 'llm_job.json')} → exit 6 稳态暂停")
            _log(f"[fix] 回填 {llm_out} 后重跑: "
                 f"win_py scripts/build_ppt.py {os.path.abspath(spec_path)} --fix --llm "
                 f"{'--out ' + out_dir if args.out else ''}".rstrip())
            return 6

        # ---- 本轮修订（快照 → 机械 → LLM → 写回 → 重跑回环）----
        nround += 1
        snap = R.snapshot_file(spec_path, nround)
        text, newline = _read_spec_text(spec_path)
        spec_raw = spec_compile.load_yaml(text)
        applied = False
        # 机械默认动作（R1–R4 / fontscale）
        revs, audits = [], []
        for pi, page in enumerate(pages):
            frevs, faudit = F.fix_page(page, page["_p"], per_page[pi])
            revs += [R._annotate_page(r, pi) for r in frevs]
            audits += faudit
        for a in audits:
            _log(f"  [fix 机械] {a}")
        if revs:
            out_raw, diffs, errs = R.apply_revisions(spec_raw, revs)
            if errs:
                _log(f"[fix] 机械修订应用失败（回滚 .snap.{nround}）:")
                for e in errs:
                    _log("  " + e)
                R.rollback(spec_path, nround)
                return 3
            R.write_fix_diff(fix_diff, diffs, nround, fixer="spec")
            _log(f"[fix] 机械修订 {len(diffs)} 项 → fix.diff")
            spec_raw = out_raw
            applied = True
        # LLM 通道（作业已回填）
        if need_llm and args.llm and os.path.exists(llm_out):
            data, err = LF.read_out(llm_out)
            if err:
                _log(f"[fix] {err} → 人工指引")
                return 3
            lrevs, lerrs = LF.check_out(data, spec_raw, brief, allvs)
            if lerrs:
                _log("[fix] LLM 修订被拒（护栏/定位）:")
                for e in lerrs:
                    _log("  " + e)
                _log(f"[fix] 回滚 .snap.{nround}；请修 llm_out.json 后重跑")
                R.rollback(spec_path, nround)
                return 3
            out_raw, diffs, errs = R.apply_revisions(spec_raw, lrevs)
            if errs:
                _log(f"[fix] LLM 修订应用失败: {errs}（回滚 .snap.{nround}）")
                R.rollback(spec_path, nround)
                return 3
            R.write_fix_diff(fix_diff, diffs, nround, fixer="llm")
            _log(f"[fix] LLM 修订 {len(diffs)} 项 → fix.diff")
            spec_raw = out_raw
            applied = True
        if applied:
            with open(spec_path, "w", encoding="utf-8") as f:
                f.write(R.dump_spec(spec_raw, newline=newline))
        else:
            _log(f"[fix] 第 {nround} 轮无可应用修订 → 回滚 .snap.{nround}")
            R.rollback(spec_path, nround)
            return 3

        # ---- 回环重跑验证 ----
        rc = _check(spec_path, out_dir, overrides)
        if rc[0] != 0:
            _log(f"[fix] 修订后重建失败: {rc[1]}（回滚 .snap.{nround}）")
            R.rollback(spec_path, nround)
            return rc[0]
        _, _, _, _, _, reps2 = rc
        nviol2 = sum(len(r.violations) for r in reps2)
        _log(f"[fix] 第 {nround} 轮回环：verify 违规 {nviol} → {nviol2}")
        if nviol2 == 0:
            _log(f"[fix] 收敛（第 {nround} 轮）")
            return 0
        last_violated = nviol2
    # 轮数用尽：回滚到最近确定性快照（= .snap.nround 即本轮修订前）
    _log(f"[fix] FAIL 轮数用尽（--max-fix {maxfix}），回滚最近确定性快照")
    R.rollback(spec_path, nround)
    rc = _check(spec_path, out_dir, overrides)
    if rc[0] == 0:
        _log_verify(rc[5])
    _log("[fix] 详见 fix.diff 审计；人工修订后重跑（--revert 可回滚至 .snap）")
    return 3


def main(argv=None):
    ap = argparse.ArgumentParser(description="SPEC YAML → base.pptx（确定性管线单入口）")
    ap.add_argument("spec", help="SPEC YAML 路径")
    ap.add_argument("--out", default=None, help="输出目录（默认 SPEC 同目录）")
    ap.add_argument("--com", action="store_true", help="启用 COM 后处理（需 Office）")
    ap.add_argument("--com-strict", action="store_true", help="COM 失败阻断（exit 5）")
    ap.add_argument("--no-preview", action="store_true",
                    help="不导出逐页 PNG 预览（只需 PPTX 时更快更省盘）")
    ap.add_argument("--pdf", action="store_true",
                    help="导出 base.pdf（需 Office；无 Office 降级 WARN）")
    ap.add_argument("--report", choices=("json", "md", "none"), default="md",
                    help="报告产出方式（默认 md）")
    ap.add_argument("--fix", action="store_true", help="校验失败 → 修订循环（自优）")
    ap.add_argument("--max-fix", type=int, default=3, help="修订总循环轮（默认 3）")
    ap.add_argument("--llm", action="store_true",
                    help="启用 LLM 语义修订通道（作业模式；exit 6 稳态暂停）")
    ap.add_argument("--max-llm-fix", type=int, default=1, help="LLM 修订轮（默认 1，贵）")
    ap.add_argument("--llm-client", default=None,
                    help="直连 LLM API 客户端模块名（可选；默认作业模式）")
    ap.add_argument("--diff", default=None, help="fix.diff 路径（默认 out_dir/fix.diff）")
    ap.add_argument("--revert", action="store_true",
                    help="从 fix.diff 回滚：恢复最近修订快照（.snap.N）")
    ap.add_argument("--param", action="append", default=None, metavar="KEY=VALUE",
                    help="参数覆盖（配置栈 CLI 层，可重复，last-wins）："
                         "如 --param font.latin='Times New Roman' --param table.fs=10")
    ap.add_argument("--strict-images", action="store_true",
                    help="严格图片模式：占位/缺图即编译错（exit 2）；缺省 = 占位框"
                         "渲染 + out_dir/img_prompts.md 提示清单（B3）")
    ap.add_argument("--embed-fonts", action="store_true",
                    help="请求 COM 端字体嵌入（B5；须 Office，隐含进入 stage6）；"
                         "等价 --param font.portable=true；失败 WARN 降级（--com-strict 才 exit 5）")
    args = ap.parse_args(argv)

    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    out_dir = args.out or os.path.dirname(os.path.abspath(args.spec))
    os.makedirs(out_dir, exist_ok=True)
    spec_path = os.path.abspath(args.spec)
    overrides = _parse_param_overrides(args.param)
    if args.strict_images:
        overrides.setdefault("images", {})["strict"] = True
    if overrides:
        _log("[cli] 参数覆盖（--param）: "
             + " ".join(f"{k}={v!r}" for k, v in overrides.items()))

    if args.revert:
        import revisioner as R
        snaps = sorted(f for f in os.listdir(out_dir)
                       if f.startswith(os.path.basename(spec_path) + ".snap."))
        # 快照写在 SPEC 同目录（snapshot_file）；兼容 out_dir 相对场景
        base_snaps = sorted(f for f in os.listdir(os.path.dirname(spec_path))
                            if f.startswith(os.path.basename(spec_path) + ".snap."))
        snaps = base_snaps or snaps
        if not snaps:
            _log("[revert] 无快照（.snap.N）；fix.diff 审计见 "
                 + (args.diff or os.path.join(out_dir, "fix.diff")))
            return 3
        snap = os.path.join(os.path.dirname(spec_path), snaps[-1])
        with open(snap, "r", encoding="utf-8") as f:
            text = f.read()
        with open(spec_path, "w", encoding="utf-8") as f:
            f.write(text)
        _log(f"[revert] 恢复最近快照 {snap}")
        return 0

    if args.llm_client:
        _log("[fix] --llm-client 直连客户端未内置：当前走作业模式（llm_job/llm_out），"
             "直连 API 客户端可在 llm_fixer 桥接（fake client 回放测试已覆盖）")

    # ---- stage0 load + stage1 compile（首轮；--fix 循环内每轮 _check 重建）----
    rc = _check(spec_path, out_dir, overrides)
    if rc[0] != 0:
        _log(rc[1])
        return rc[0]
    _, compiled, pages, p, irs, reps = rc
    if (compiled.get("meta") or {}).get("template"):
        pass  # 模板注记在首轮 _check 不打印（--fix 循环无感；以下照常）
    _log("[stage1] compile + validate: OK")
    for w in compiled.get("warnings") or []:
        _log(f"[stage1] 提示: {w}")
    tinfo = compiled.get("_template")
    if tinfo:
        _log(f"[stage1] 模板注记（{tinfo['mode']} · {os.path.basename(tinfo['src'])}）:")
        for n in tinfo.get("notes") or []:
            _log("  " + n)
    ph_items = compiled.get("_img_placeholders") or []
    for it in ph_items:
        _log(f"[stage1] 图片占位: {it['id']}（p{it['page']}）→ {it['prompt']}")
    if ph_items:
        _log(f"[stage1] 缺图提示清单: {os.path.join(out_dir, p['images']['prompt_file'])}")

    nviol = sum(len(r.violations) for r in reps)
    _log_verify(reps)

    # report 先行（每分支都产出报告；fix 收敛/失败态复用最终 reps）
    def _write_report(reps_final, irs_final):
        if args.report != "none":
            import report as RPT
            if args.report == "md":
                pth = os.path.join(out_dir, "report.md")
                RPT.write_report_md(reps_final, irs_final, pth,
                                    titles=[pg.get("_title") for pg in pages],
                                    params=p,
                                    theme_used=bool(compiled.get("_theme")))
            else:
                pth = os.path.join(out_dir, "report.json")
                with open(pth, "w", encoding="utf-8") as f:
                    json.dump({"pages": [{"summary": r.summary(),
                                          "pass_count": r.pass_count,
                                          "violations": r.violations,
                                          "checks": [list(c) for c in r.checks]}
                                         for r in reps_final]},
                              f, ensure_ascii=False, indent=1)
            return pth
        return None

    def _log_design(irs_now):
        """设计体检（advisory）：让 agent 看见视觉主体/图标/强调/丰度/AI 痕迹
        是否真的用上（阈值取 params.verify.abundance/ai_tells/color_dominance）。"""
        try:
            import report as RPT
            _theme_used = bool(compiled.get("_theme"))
            _rows, _warns = RPT.design_audit(
                irs_now, [pg.get("_title") for pg in pages],
                params=p, theme_used=_theme_used)
            _log(RPT.format_audit(_rows, _warns))
            for _h in RPT.conversion_hints(irs_now):
                _log(f"[design·转换律] {_h}")
        except Exception as ex:
            _log(f"[design] 设计体检跳过: {ex}")

    if nviol:
        if not args.fix:
            report_path = _write_report(reps, irs)
            _log_design(irs)
            _log(f"[stage3] FAIL 校验违规 {nviol} 条，管线停止（详见 "
                 f"report.{args.report}）")
            return 3
        # ---- --fix 修订循环 ----
        frc = _fix_loop(args, spec_path, out_dir, overrides)
        if frc != 0:
            if frc in (3, 6):
                report_path = _write_report(reps, irs)
                if frc == 6:
                    _log("[stage3] exit 6 = 稳态暂停（非错误）：回填 llm_out.json 后重跑")
            return frc
        # 收敛 → 重取最终状态继续 stage4+
        rc = _check(spec_path, out_dir, overrides)
        if rc[0] != 0:
            _log(rc[1])
            return rc[0]
        _, compiled, pages, p, irs, reps = rc
        _log("[stage3] fix 收敛：verify 全过")

    report_path = _write_report(reps, irs)
    _log_design(irs)

    # ---- stage4 render（多 slide 单文件）----
    try:
        import render_pptx as RP
        base_path = os.path.join(out_dir, "base.pptx")
        used, errors = RP.render(irs, compiled, p, base_path,
                                 pps=[pg["_p"] for pg in pages])
    except Exception as ex:
        _log(f"[stage4] FAIL 渲染异常: {ex}")
        return 4
    if errors:
        _log("[stage4] FAIL:")
        for e in errors:
            _log("  - " + e)
        return 4
    _log(f"[stage4] render: OK {len(irs)} 页 组件银行 {len(used)} 项 → {base_path}")

    # ---- stage5 evidence（逐页：slideN.xml ↔ slides[N-1]）----
    try:
        import render_check_xml as RCX
        checks_by_page = [RCX.check(base_path, ir, pg["_p"], compiled["palette"],
                                    page_idx=i,
                                    template_info=compiled.get("_template"))
                          for i, (ir, pg) in enumerate(zip(irs, pages))]
    except Exception as ex:
        _log(f"[stage5] FAIL 物证异常: {ex}")
        return 4
    fails = [(i, c) for i, ch in enumerate(checks_by_page) for c in ch if not c[1]]
    for pi, (name, ok, detail) in fails:
        _log(f"  FAIL [S{pi + 1}] {name}: {detail}")
    if fails:
        _log(f"[stage5] FAIL XML 物证 {len(fails)} 项不通过")
        return 4
    n_ev = sum(len(ch) for ch in checks_by_page)
    _log(f"[stage5] evidence: OK {n_ev}/{n_ev} 物证全过（{len(checks_by_page)} 页）")

    # ---- stage6 com（可选：--com 后处理 与/或 --pdf 导出）----
    import report as RPT
    RPT.write_ir_json(irs, os.path.join(out_dir, "ir.json"))
    embed_fonts = bool(args.embed_fonts or p["font"].get("portable"))
    if args.com or args.pdf or embed_fonts:
        fonts = [p["font"]["latin"], p["font"]["ea"],
                 p["font"]["title_latin"], p["font"]["title_ea"]]
        rc6 = run_com(out_dir, args.com_strict, com_params=p.get("com"), pdf=args.pdf,
                      embed_fonts=embed_fonts, fonts=fonts,
                      previews=not getattr(args, "no_preview", False))
        if rc6:
            return rc6
        # stage6 回读披露：字体嵌入结果（B5）+ 文本溢出真实回读（B4）
        try:
            with open(os.path.join(out_dir, "com_out.json"), encoding="utf-8") as f:
                co = json.load(f)
        except Exception:
            co = {}
        if embed_fonts:
            fi = co.get("fonts") or {}
            emb = fi.get("embedded") or []
            if emb:
                _log(f"[stage6] 字体嵌入: OK {len(emb)} 个 part（{', '.join(emb)}）")
            elif fi.get("requested"):
                _log("[stage6] 字体嵌入: WARN 请求生效但包内无 fntdata"
                     "（字族未授权嵌入/本机无可嵌入副本，见 report）")
        ov = co.get("overflow") or []
        if ov:
            _log(f"[stage6] 文本溢出回读(B4): {len(ov)} 个形状 PowerPoint 实高"
                 f"超框（{', '.join(o['id'] for o in ov[:6])}"
                 f"{' …' if len(ov) > 6 else ''}）")
    _log("== 管线完成：exit 0 ==")
    if report_path:
        _log(f"报告: {report_path}")
    _log(f"产物: {base_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())