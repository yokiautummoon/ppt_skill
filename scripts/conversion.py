# -*- coding: utf-8 -*-
"""conversion.py — 内容处理转换律（advisory）：把「一段素材该转成什么视觉形态」
写成纯数据表 + 一个 IR 级启发式扫描器。

源材料 anthropics/skills pptx SKILL.md §For Each Slide（Every slide needs a visual
element / Data display）+ `_r_design-rules.md` §内容处理转换律。触发 → 目标形态：
  3+ 数字 → stats/kpis/chart；A vs B → versus；有序步骤 → route/graph；
  同构字段重复 → table；长段 → 短句项目符号。

**仅供 report 作 advisory tips 消费，绝不产生 exit 码**（形态取舍是语义裁定）。
"""
import re

# (key, target, hint)。target = page_intent token 或积木名（人读提示用）。
CONVERSIONS = (
    ("numbers3plus", "kpis/chart",
     "≥3 个数字并置——转指标卡（kpis）或图表（chart），别埋在正文里"),
    ("versus", "versus",
     "出现 A vs B / 对比——转对照页（versus，左右分色面板）"),
    ("steps", "route/graph",
     "有序步骤/阶段——转技术路线页（route）或流程图（graph），别写成编号段落"),
    ("repeat_fields", "table",
     "同构字段重复——转表格（table）承载多行同构数据"),
    ("long_para", "bullets",
     "长段落——拆成短句项目符号（每句 ≤1 行），提升扫读性"),
)

_NUM_RE = re.compile(r"\d")
_VS_RE = re.compile(r"(?:\bvs\b|VS|对比|比较|区别|差异)")
_STEP_RE = re.compile(r"(?:^|\n)\s*(?:\d+[.、)]|[①-⑩]|步骤|第一步|首先|其次|然后)")
_FIELD_RE = re.compile(r"(?:：|:)\s*\S")


def _page_text(ir):
    return "\n".join(e.get("text") or "" for e in (ir.get("elements") or [])
                     if e.get("type") == "text")


def conversion_hints(irs):
    """逐页扫描内容页，返回建议转换的 hint 列表（保序去重）。页型意图页跳过
    （已由引擎展开审定版式）。"""
    hints = []
    for pi, ir in enumerate(irs):
        if ir.get("page_intent"):
            continue
        txt = _page_text(ir)
        if not txt:
            continue
        prefix = f"页 {pi + 1}："
        if len(_NUM_RE.findall(txt)) >= 3:
            hints.append(prefix + "≥3 个数字并置——转指标卡（kpis）或图表"
                         "（chart），别埋在正文里")
        if _VS_RE.search(txt):
            hints.append(prefix + "出现 A vs B / 对比——转对照页（versus，"
                         "左右分色面板）")
        if _STEP_RE.search(txt):
            hints.append(prefix + "有序步骤/阶段——转技术路线页（route）或流程图"
                         "（graph），别写成编号段落")
        long_hit = next((e for e in (ir.get("elements") or [])
                         if e.get("type") == "text"
                         and len(e.get("text") or "") > 120), None)
        if long_hit is not None:
            hints.append(prefix + "长段落——拆成短句项目符号（每句 ≤1 行），"
                         "提升扫读性")
        fields = sum(1 for e in (ir.get("elements") or [])
                     if e.get("type") == "text" and _FIELD_RE.search(e.get("text") or ""))
        if fields >= 3:
            hints.append(prefix + "同构字段重复——转表格（table）承载多行"
                         "同构数据")
    seen, out = set(), []
    for h in hints:
        if h not in seen:
            seen.add(h)
            out.append(h)
    return out
