# -*- coding: utf-8 -*-
"""llm_fixer.py — LLM 语义修订器 + 作业协议（决策部件④）。

执行者 = Claude agent 自身（内化通道，不解耦黑盒）：build_ppt --llm 遇到
content/advisory 违规 → 写 llm_job.json + exit 6（稳态暂停，非错误）；外层
执行者按 job 回填 llm_out.json → 重跑同命令继续循环。--llm-client 直连 API
可选（测试用 fake client 回放；本模块提供 CHECK_OUT 静态校验，与直连无关）。

护栏（决策部件④ 硬约束，CHECK_OUT 强制）：
  - 文本字段：new 可改，但 basis（依据）必须 = brief 引文 / 现有文本改写引用 /
    [占位] 标识——禁止凭空编造；
  - 数据字段（chart/table 的 data/categories/series 路径）：new 必须源于 brief
    原文数据或标 [占位]，禁止自由编造数字；
  - 每次修订记 理由 + 置信度；回环强制：修订须过 verify 才接受（build_ppt 主循环）。

与 spec_fixer 同接口：input(SPEC, violations, context) → output(revisions, audit)；
差异：真实 LLM 侧经 llm_job/llm_out 文件通道（异步、可人工干预），CHECK_OUT
在回填时做护栏与定位校验，产物仍走 revisioner.apply_revisions 结构应用。
"""
import json
import os

JOB_VERSION = 1

# 数据字段路径标志（数据红线适用）——命中即禁止编造
_DATA_FIELDS = ("data", "categories", "series")
# 动作白名单（动作库键 + 菜单项；人工决策不入）
_ACTION_ALLOW = {
    "autofit", "safety", "overlap", "zfix", "fontscale",
    "从brief生成文本", "引用现有文本", "移除(若装饰)", "浓缩文本",
    "调换位置", "缩放", "移A", "移B", "挪开", "调间距", "拆元素",
    "换白名单邻色token", "扩框", "降号", "平移/收缩", "补overlap",
    "补z_override", "调至合法档", "人工",
}
# 字段白名单（元素字段；文本/数据/样式/几何）
_FIELD_ALLOW = {
    "text", "text_style.fs", "text_style.color", "text_style.align",
    "style.fill", "style.border", "style.shadow",
    "rect", "rect.x", "rect.y", "rect.w", "rect.h",
    "data", "categories", "series", "col_widths", "header", "body",
}


def _field_by_type_map():
    """元素类型 → 该类型显式声明的合法字段集（相对字段 → PER_TYPE 顶级键）。
    LLM 修订的 field 首个段（无点）必须命中此处——定向补丁按元素类型细分
    （LiveFigure 增量定向：只碰目标元素且只碰该元素真实存在的字段，杜绝把
    data 塞给 text、把 rect.y 塞给 line 等既往粗粒度盲区）。
    单页/多页元素 type 全集，取自 spec_validator.PER_TYPE（唯一机器事实源）。"""
    import spec_validator as SV
    top = {}
    for t, allowed in SV.PER_TYPE.items():
        tops = set()
        for k in allowed:
            if k in ("id", "type", "rect_kind", "z", "link", "ph_info", "area"):
                continue          # 通用/引擎定字段：LLM 不修
            tops.add(k.split(".", 1)[0])
        top[t] = tops
    return top


# 元素类型 → 合法修订字段顶级键（定向补丁按类型细分的事实源）
_FIELD_TOP_BY_TYPE = _field_by_type_map()


def _rev_field_ok(etype, field):
    """field 必须 ∈ 该元素类型的合法修订字段（定向补丁：只碰目标元素真实存在的字段）。

    规则：field 的**顶级段**（点前）若 ∈ _FIELD_ALLOW 是修订白名单字段，则其必须
    也 ∈ 该元素类型 spec_validator.PER_TYPE 的键——例如 `data` 全局限白名单放行，
    但对 `text` 元素是非法（text 无 data 字段），补 series/data 到 text/shape 会被
    编译期未知字段拦截。按类型细分在 CHECK_OUT 校验（LLM 回填被拒 → 定向而非整页重排）。
    """
    if etype not in _FIELD_TOP_BY_TYPE:
        return True                                       # 未知/容器：不收紧（保守放行）
    return field.split(".", 1)[0] in _FIELD_TOP_BY_TYPE[etype]


# ---- 负面约束（Evolving Experience：把工程沉淀的"不能做"作为机器可消费约束注入
#      作业，LLM 回填 llm_out 时受约束——LiveFigure 负例注入的落地）----
# 每条：{rule: 禁止项, why: 来源/后果, types: 适用元素类型（None=全类型）}
_CONSTRAINTS = [
    {"rule": "rect 必须 4 元组；改用 rect_kind: ratio 时才可写 dict{x,y,w,h}（0–1 分数）",
     "why": "编译期 _check_rect/spec_validator 锁绝对四元组；ratio 是编译期糖，IR 只见绝对 rect",
     "types": None},
    {"rule": "容器(stack/dock/graph) 的 children 不支持 rect_kind:ratio、动画/挂链（引擎求解/编译期即拦）",
     "why": "求解器产子形状 rect；容器级动画/链接编译期拒绝",
     "types": ("stack", "dock", "graph")},
    {"rule": "svg 遇 image/text/filter/clipPath/mask/线性/径向渐变/pattern/外链use/CSS",
     "why": "一律编译期 exit 2 fail-closed，绝非静默降级；defs 内未引用定义被容忍",
     "types": ("svg",)},
    {"rule": "svg 渲染元素(shape/container) 带 filter=/clip-path=/mask= 属性（引用 defs 定义）会被拒",
     "why": "服用了滤镜/裁剪/遮罩须复现而无法复现 → fail-closed；半透明/渐变直接改 fill 色，别依赖 opacity 透传",
     "types": ("svg",)},
    {"rule": "svg 的 src(外链文件) 与内联 svg: 二选一，fit ∈ {contain, stretch}",
     "why": "双源/非法 fit 编译期 exit 2",
     "types": ("svg",)},
    {"rule": "icon 名必须命中 assets/icons/lucide.json（未命中回退 circle-dot）；rect 由引擎正方适配勿手写",
     "why": "icon 名称/关键词解析决定几何；正方适配由 ir_builder 定（几何唯一源）",
     "types": ("icon",)},
    {"rule": "brush 字形须单 a:path 保 口/日 内孔镂空（引擎排布勿拆）；换机不丢字形需本机字形存在",
     "why": "单 path 保内孔；拆 path 各自填实心会破镂空",
     "types": ("brush",)},
    {"rule": "typst 页面尺寸=元素 rect 1:1，勿加 padding/留白包围；源码不引外部资源",
     "why": "SVG+PNG 双产物 1:1 注入；外部资源在 typst CLI 编译期不可得",
     "types": ("typst",)},
    {"rule": "transition.effect=morph 必须走 mc:AlternateContent 兼容包（Choice Requires=p159 > p159:morph + Fallback fade）",
     "why": "直写 <p:transition><p159:morph/> 非 p159 宿主解析失败；dur 挂 p:transition 非 morph 子元素",
     "types": None},
    {"rule": "data/categories/series 数据字段受数据红线：须 brief 原文或 [占位]，禁止编造数字",
     "why": "CHECK_OUT 强制：数据溯源 redline，无依据整批拒绝",
     "types": ("table", "chart")},
]
# 版本演进：新增 constraint 不改 JOB_VERSION（追加式向后兼容）；CHECK_OUT 不校验
# constraint（advisory），只校验 revisions 本身。


def build_job(spec_path, page, violations, brief, notes, related, menus, guide):
    """组装 llm_job dict（build_ppt --llm 暂停时写出）。
    violations: attribution.Violation；menus: {违规 name: [动作...]}（revisioner.MENU）。
    constraints: 按违规元素类型聚合的负面约束（Evolving Experience）注入 context，
    LLM 回填 llm_out 时受其约束——定向修订保持布局/拓扑不变。"""
    # 通用负面约束恒注入（跨类型坑：rect 形态 / morph / 数据红线）。类型专属约束
    # 依赖 element→type 解析需 SPEC，build_ppt 的 jobs 无 SPEC → 保守仅通用项
    # 注入；类型差异化校验由 CHECK_OUT 的 _rev_field_ok 承担（字段级，无需 SPEC type
    # 推断——element 定位后即知 type）。
    cons = [c for c in _CONSTRAINTS if c["types"] is None]
    return {
        "version": JOB_VERSION,
        "spec": os.path.abspath(spec_path),
        "brief": brief or "",
        "page": page,
        "violations": [{
            "family": v.family, "name": v.name, "element": v.element,
            "peer": v.peer, "klass": v.klass, "action": v.action,
            "detail": v.detail,
        } for v in violations],
        "menu": {v.name: menus.get(v.action, ["人工"]) for v in violations},
        "context": {"notes": notes or "", "related_text": related or [],
                    "constraints": cons},
        "guide": guide,
    }


def write_job(job, path):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(job, f, ensure_ascii=False, indent=1)


def read_out(path):
    """llm_out.json → dict。不存在/坏 JSON → (None, 错误串)。"""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f), None
    except (OSError, ValueError) as ex:
        return None, f"llm_out 读取失败: {ex}"


def _locate_global(spec_raw, element):
    """在原始 SPEC 全页按 id 找 (页标, 页容器, 元素索引)。id 页内唯一（编译期），
    跨页同 id 允许（title 等）——取首处匹配；找不到 → (None, None, None)。"""
    meta = spec_raw.get("meta") or {}
    slides = meta.get("slides") if isinstance(meta.get("slides"), list) else None
    if slides:
        for pg, sl in enumerate(slides):
            for i, e in enumerate(sl.get("elements") or []):
                if e.get("id") == element:
                    return pg, sl, i
        return None, None, None
    for i, e in enumerate(spec_raw.get("elements") or []):
        if e.get("id") == element:
            return 0, spec_raw, i
    return None, None, None


def check_out(llm_out, spec_raw, brief, page_violations):
    """llm_out dict → (revisions, errors)。revisions 可直接交 revisioner 应用（带 old/pg）。
    失败（定位/白名单/数据红线）→ errors；任一失败整批拒绝（与 revisioner 事务一致）。"""
    errors = []
    if not isinstance(llm_out, dict):
        return [], ["llm_out 必须为 dict"]
    if llm_out.get("version") != JOB_VERSION:
        errors.append(f"version {llm_out.get('version')!r} ≠ {JOB_VERSION}")
    try:
        revs_raw = llm_out["revisions"]
    except KeyError:
        return [], errors + ["缺少 revisions"]
    if not isinstance(revs_raw, list):
        return [], errors + ["revisions 必须为列表"]
    revs = []
    for ri, r in enumerate(revs_raw):
        p = f"revisions[{ri}]"
        for k in ("action", "field", "old", "new", "basis", "confidence"):
            if k not in r:
                errors.append(f"{p}: 缺 {k}")
        if not isinstance(r.get("action"), str) or r["action"] not in _ACTION_ALLOW:
            errors.append(f"{p}.action: 白名单外 {r.get('action')!r}")
        if not isinstance(r.get("field"), str) or r["field"] not in _FIELD_ALLOW:
            errors.append(f"{p}.field: 白名单外 {r.get('field')!r}")
        if not isinstance(r.get("basis"), str) or not r["basis"].strip():
            errors.append(f"{p}.basis: 必须写明依据（brief 引文 / 现有文本 / [占位]）")
        if not (isinstance(r.get("confidence"), (int, float))):
            errors.append(f"{p}.confidence: 必须为数值")
        el = r.get("element")
        pg, container, idx = _locate_global(spec_raw, el) if el else (None, None, None)
        if container is None:
            errors.append(f"{p}: 元素 {el!r} 不在任何页")
            continue
        fld = r["field"]
        if not _rev_field_ok((container.get("elements") or [])[idx].get("type") if 0 <= idx < len(container.get("elements") or []) else None, fld):
            errors.append(f"{p}.field: {fld!r} 不属于该元素的合法字段（定向补丁：只碰目标元素类型真实存在的字段）")
            continue
        # 数据红线：data/categories/series 字段必须带依据（[占位] 或 brief 引文标识）
        if fld in _DATA_FIELDS or fld.startswith("series"):
            basis = (r.get("basis") or "").lower()
            if not (("[占位]" in basis) or ("brief" in basis)):
                errors.append(f"{p}: 数据字段 {fld} 依据缺失——数据必须源于 brief 原文或标 "
                              f"[占位]，禁止编造（basis={r.get('basis')!r}）")
        revs.append({
            "action": r["action"],
            "path": ("elements", idx, fld),
            "pg": pg,
            "old": r["old"],
            "new": r["new"],
            "basis": r["basis"],
            "confidence": r["confidence"],
            "data_source": "llm",
        })
    return (revs, errors) if not errors else ([], errors)


# ---- 测试辅助：fake client 回放 ----

def fake_out(revisions, version=JOB_VERSION):
    return {"version": version, "revisions": revisions, "audit": []}