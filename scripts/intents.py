# -*- coding: utf-8 -*-
"""intents.py — 页型意图的变体家族（variant families）+ 确定性选型。

刻板的根因之一：**一个 intent 只有一个几何展开**。同一 deck 里 3 个 section 页
逐像素相同，而 A1 版式多样性又豁免了 intent 页 → 这类重复不被任何门禁看见。

方案：每个 intent 挂一族**审定变体**（每变体 = 布局代码 + verify 断言，与原型同律），
选型**确定性**，可复现、可断言、可审计：

  1. SPEC 显式 `section: {variant: band}` —— agent 指定；
  2. 缺省按该 intent 在 deck 内的**出现次序轮换**（第 1 次 → family[0]，
     第 2 次 → family[1]，…循环）。

轮换由 `plan()` 在 deck 级（build_pages）算定并写进页 meta，ir_builder 逐页消费；
单页/直构场景缺省 family[0]（历史几何，向后兼容）。
"""
FAMILIES = {
    "cover": ("left", "band", "split"),
    "section": ("num_left", "num_giant", "band"),
    "problem": ("badge",),
    "versus": ("split",),
    "route": ("chain",),
    # 内容页结构生成样板（references/page-intents.md §10）：每族 ≥2 变体
    "panels": ("even", "hero_left"),
    "columns": ("even", "arrow"),
    "kpis": ("cards", "row", "rings"),
    "cards": ("icon_top", "number", "icon_left"),
    "figure_text": ("right", "left"),
}


def family(intent):
    """该 intent 的变体家族（tuple）；未知 intent → 空 tuple。"""
    return FAMILIES.get(intent, ())


def variants(intent):
    return list(FAMILIES.get(intent, ()))


def default(intent):
    """缺省变体（单页/直构场景）；未知 intent → ""（无变体概念）。"""
    fam = FAMILIES.get(intent)
    return fam[0] if fam else ""


def known(intent, variant):
    """variant 是否属于该 intent 的家族（编译期白名单校验用）。"""
    return variant in (FAMILIES.get(intent) or ())


def resolve(intent, explicit=None):
    """展开层取值：显式优先，否则缺省。"""
    if explicit:
        return explicit
    return default(intent)


def plan(slides):
    """deck 级选型：slides（SPEC 页列表）→ [{index, intent, variant, explicit}]。

    只列声明了 page_intent 的页；同 intent 按出现次序在家族内轮换，显式 variant
    不占轮换位（显式页不影响后续页的轮换计数——显式即脱离自动序列）。"""
    seen = {}
    out = []
    for i, s in enumerate(slides or []):
        intent = s.get("page_intent")
        if not intent:
            continue
        fam = FAMILIES.get(intent) or ("",)
        explicit = (s.get(intent) or {}).get("variant")
        if explicit:
            v = explicit
        else:
            n = seen.get(intent, 0)
            v = fam[n % len(fam)]
            seen[intent] = n + 1   # 仅隐式页占轮换位（显式页脱离自动序列）
        out.append({"index": i, "intent": intent, "variant": v,
                    "explicit": bool(explicit)})
    return out
