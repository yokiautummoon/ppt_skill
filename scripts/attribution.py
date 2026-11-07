# -*- coding: utf-8 -*-
"""attribution.py — 一致性归因分类器：违规 → internal / fixable / advisory。

决策 wiki/decisions/self-improve-loop.md 部件③：修 SPEC 之前先分类，三类不同处置：

  internal   IR/渲染/断言算法不一致类（断行重算/锚点重算/节点同高/包络/账目/orth
             结构等"布局层 vs 渲染·断言层应一致"断言）——停机 exit 4 + bug 指引，
             不修 SPEC、不喂 LLM（修 SPEC 会掩盖 bug）。
  fixable    SPEC 字段可修（安全区溢出/autofit 溢出/遮挡无合法源/字号越档/
             内容缺失）——进修订链（动作库默认动作或 LLM/人工）。
  advisory   审美/结构偏好（破格度/贯穿度/语义色数/必需构件/引用悬空）——
             默认留人工；LLM 高权限可调。

分类器是纯函数 + 声明式规则表（确定性、可单测）。违规的字段定位（元素 id、
期望/当前值）从 verify 的 name/detail 文本结构化提取——verify 本体不动
（Report 保持 (family, name, ok, detail) 四元组）。
"""
import re


# ---- 归因类别 ----
INTERNAL = "internal"   # 停机报 bug（exit 4），不修 SPEC
FIXABLE = "fixable"     # 进修订链
ADVISORY = "advisory"   # 默认人工/LLM 高权限

# 可确定性自动修的动作（= 动作库默认项，spec_fixer 实现；decision 部件②）
ACTIONS = {
    "autofit": "R1 降号/扩框",
    "safety": "R2 收缩/平移入安全区",
    "overlap": "R3 补 relations.overlap",
    "zfix": "R4 补 z_override",
    "fontscale": "字号调至合法档",
    "content": "文本内容（从 brief 生成/引用/人工）",
    "manual": "人工/LLM 决策",
}

# ---- internal 模式（name 子串命中即 internal；宁紧勿松）----
_INTERNAL_SUB = (
    "断行重算一致",        # IR 断行 vs 独立重算不一致 = 算法 bug
    "独立重算一致",        # 锚点第二实现重算不一致 = 布局器 bug
    "锚点一致",            # 具名锚点解析一致（布局层算法 bug）
    "orth 折线",           # orth 折线结构断言（布局器生成）不一致
    "节点同高",            # graph 求解器不变式
    "包络 ⊇ 成员",         # 组包络（计算于布局层）断言
    "账目",                # stack/dock 尺寸账目（布局层计算）
    "面板内容区",          # 节点 ⊆ 面板内容区（求解器输出与面板一致）
    "编辑组",              # 编辑单元 z 区间（布局器收拢算法 bug）
    "低于节点",            # graph 类序不变式：边 z 须低于节点 z（z 类基步长）
    "不穿节点",            # 回边绕行：连线不得穿越非端点节点盒（连线路由缺陷）
)

# ---- advisory 模式（默认不自动修；LLM 高权限可按 brief 调）----
_ADVISORY_SUB = (
    "破格度", "贯穿度", "字号层级",     # 页型审美参数
    "配色 ⊆ 白名单", "语义色 ≤",        # 配色选择（换哪个 token 是语义）
    "几何有限/正",                       # 非数/负尺寸：无合法修复值
    "两端存在",                          # 线/glue 引用悬空：删还是补是语义
    "页型", "必需构件",                  # 页面型/构件缺失：引擎归属
    "小尺寸字号", "标签组织",            # scansci 内化规则：按尺寸/组织偏好，人工/LLM 裁定
    "图重复",                            # 跨页拓扑同构：改拓扑或主题是语义裁定
    "版式多样性", "版式同质",            # 跨页版式骨架同质：换骨架/并页是语义裁定
    "每页强调", "标题字数", "标题字号",  # A2 排版规范：信息取舍是语义裁定
    "正文字数",
)

# ---- fixable 模式：name 子串 → 动作 ----
_FIXABLE_MAP = (
    ("⊆ 安全区", "safety"),
    ("⊆ slide", "safety"),
    ("水平不溢出", "autofit"),
    ("垂直不溢出", "autofit"),
    ("autofit 超框标记", "autofit"),
    ("min_fs 硬底", "autofit"),
    ("表格格", "autofit"),
    ("遮挡", "overlap"),
    ("节点字号", "fontscale"),
    ("标签字号", "fontscale"),
    ("正文字号", "fontscale"),
    ("z_override", "zfix"),
    ("文本非空", "content"),
)


# ---- 元素 id 提取 ----
_RE_ID_1 = re.compile(r"(?:元素|文本非空|水平不溢出|垂直不溢出|min_fs 硬底|"
                      r"autofit 超框标记|节点字号|标签字号|正文字号|节点|边|glue|"
                      r"断行重算一致|锚点|orth 折线|容器|组|z_override 冲突|z_override)\s+"
                      r"([A-Za-z_][A-Za-z0-9_.-]*)")
_RE_OVERLAP = re.compile(r"遮挡\s+([A-Za-z_][A-Za-z0-9_.-]*)\s*[↔~]\s*"
                         r"([A-Za-z_][A-Za-z0-9_.-]*)")
_RE_BRACKET = re.compile(r"账目\[([A-Za-z_][A-Za-z0-9_.-]*)\]")
_RE_TABLE = re.compile(r"表格格\s*\((\d+),(\d+)\)")


def _extract_ids(name):
    """从 verify name 提取元素 id 与对端（遮挡对）。"""
    m = _RE_OVERLAP.search(name)
    if m:
        return m.group(1), m.group(2)
    m = _RE_ID_1.search(name)
    if m:
        return m.group(1), None
    m = _RE_BRACKET.search(name)
    if m:
        return m.group(1), None
    return None, None


class Violation(object):
    """结构化违规：family/name/detail（verify 原样）+ 归因与定位。"""

    def __init__(self, family, name, detail, klass, action, element=None,
                 peer=None, expect="", current=""):
        self.family = family
        self.name = name
        self.detail = detail
        self.klass = klass            # internal | fixable | advisory
        self.action = action          # actions 键（fixable 才有语义）
        self.element = element        # 触发元素 id（可解析时）
        self.peer = peer              # 遮挡对端 id（重合类）
        self.expect = expect
        self.current = current

    def as_dict(self):
        return {"family": self.family, "name": self.name, "detail": self.detail,
                "klass": self.klass, "action": self.action,
                "element": self.element, "peer": self.peer,
                "expect": self.expect, "current": self.current}

    def __repr__(self):
        return (f"<Violation [{self.family}] {self.name} → {self.klass}"
                f"/{self.action} {self.element}>")


def classify(report):
    """report: verify.Report。返回 [Violation]（仅违规项，按索引顺序）。"""
    out = []
    for family, name, ok, detail in report.checks:
        if ok:
            continue
        el, peer = _extract_ids(name)
        if any(s in name for s in _INTERNAL_SUB):
            out.append(Violation(family, name, detail, INTERNAL, "manual",
                                 el, peer))
            continue
        if any(s in name for s in _ADVISORY_SUB):
            out.append(Violation(family, name, detail, ADVISORY, "manual",
                                 el, peer))
            continue
        action = "manual"
        for sub, act in _FIXABLE_MAP:
            if sub in name:
                action = act
                break
        out.append(Violation(family, name, detail, FIXABLE, action, el, peer))
    return out


def auto_fixable(violations):
    """可确定性自动修（无语义决策）的违规子集。"""
    return [v for v in violations if v.klass == FIXABLE
            and v.action in ("autofit", "safety", "overlap", "zfix", "fontscale")]


def llm_or_manual(violations):
    """交 LLM（高权限）/人工的违规子集（内容缺失与 advisory）。"""
    return [v for v in violations
            if v.klass == ADVISORY or (v.klass == FIXABLE and v.action == "content")]