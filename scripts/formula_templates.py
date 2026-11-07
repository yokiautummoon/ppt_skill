# -*- coding: utf-8 -*-
"""formula_templates.py — 离线公式模板库（辅助手段）。

动机：Word 批量引擎能兜住任意子集外表达式，但必经中间 docx + 解包；对
"高频固定写法"（∑_(i=1)^n x_i 这类实测转真 m:nary 的字符式），预先经 Word
转一次存成模板，运行时按表达式原文**精确命中** → 直接注入，--com 都不需要。

层级（主 → 辅助 → 回退）：
  1. 主路径   formula_omml.parse_expr        —— 子集内确定性注入
  2. 辅助     本模块 resolve（模板命中）      —— 子集外高频写法，零 Word
  3. 回退     com_layer → omml_engine        —— 其余子集外（需 Office --com）

构建：win_py scripts/build_formula_templates.py（需 Word）→
scripts/formula_templates.json（随包分发，无 Office 环境直接用）。
匹配 = 表达式逐字命中（精确 key）；注入时字符串级确定性应用 SPEC 的
fs/color（替换 rPr 的 sz 与插 solidFill，与 parse_expr 契约一致）。
"""
import json
import os
import re

_TEMPLATES_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               "formula_templates.json")
_CACHE = None


def load():
    """模板库 {expr: {omml, fs}}；缺失/损坏 → {}（降级为纯 Word 兜底）。"""
    global _CACHE
    if _CACHE is None:
        try:
            with open(_TEMPLATES_PATH, "r", encoding="utf-8") as f:
                _CACHE = json.load(f)
        except (OSError, ValueError):
            _CACHE = {}
    return _CACHE


def normalize(omml, fs=18):
    """Word docx 解包产出的 OMML → PowerPoint 原生基准（formula-omml.md 二节）。

    Word 的 run 用 w:rPr（w:rFonts/w:i），PowerPoint 公式用 a:rPr（lang/
    sz/i/kern + a:latin/a:ea/a:cs）。归一化 = 确定性字符串级替换：
      · 内容 run 的 w:rPr → a:rPr（en-US + sz + i/kern + effectLst + 三字体）
      · ctrlPr 内的 w:rPr → a:rPr（zh-CN + smtClean=0，同 parse_expr 契约）
      · 清根元素一堆 xmlns（wpc/cx…）——a14/m/a 注入时由 omath_paragraph 声明
    """
    sz = int(round(fs * 100))
    a_rpr = ('<a:rPr lang="en-US" altLang="zh-CN" sz="%d" i="1" kern="100">'
             '<a:effectLst/><a:latin typeface="Cambria Math"/>'
             '<a:ea typeface="Cambria Math"/>'
             '<a:cs typeface="Times New Roman"/></a:rPr>' % sz)
    a_ctrl = ('<a:rPr lang="zh-CN" altLang="zh-CN" sz="%d" i="1" kern="100" '
              'smtClean="0"><a:effectLst/><a:latin typeface="Cambria Math"/>'
              '<a:ea typeface="Cambria Math"/>'
              '<a:cs typeface="Times New Roman"/></a:rPr>' % sz)
    omml = re.sub(r"<m:ctrlPr><w:rPr>.*?</w:rPr></m:ctrlPr>",
                  "<m:ctrlPr>%s</m:ctrlPr>" % a_ctrl, omml)
    omml = re.sub(r"<w:rPr>.*?</w:rPr>", a_rpr, omml)
    omml = re.sub(r"^(<\w+)([^>]*?)(>)", _strip_xmlns, omml, count=1)
    return omml


def _strip_xmlns(m):
    tag, attrs, gt = m.group(1), m.group(2), m.group(3)
    return tag + re.sub(r'\s+xmlns(?::\w+)?="[^"]*"', "", attrs) + gt


def resolve(expr, fs=18, color_hex=None):
    """模板命中：返回已应用 fs/color 的 m:oMath 内容；未命中 None。
    color_hex 不带 #（与 parse_expr 的 color 参数同语义）。"""
    tpl = load().get(expr)
    if not tpl:
        return None
    omml = tpl["omml"]
    if int(tpl.get("fs", 18)) != fs:
        omml = re.sub(r'(sz=")\d+(")', _sz_repl(fs), omml)
    if color_hex:
        omml = re.sub(r"<a:effectLst/>", _fill_repl(color_hex), omml)
    return omml


def _sz_repl(fs):
    sz = str(int(round(fs * 100)))
    return lambda m: m.group(1) + sz + m.group(2)


def _fill_repl(color_hex):
    fill = '<a:solidFill><a:srgbClr val="%s"/></a:solidFill>' % color_hex
    return lambda m: "<a:effectLst/>" + fill


def supported(expr, fs=18):
    """parse 与模板之外的表达式是否需要兜底：True = 已有主/辅助路径可注入。"""
    import formula_omml
    if formula_omml.parse_expr(expr, fs)["ok"]:
        return True
    return resolve(expr, fs) is not None