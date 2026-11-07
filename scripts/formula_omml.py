# -*- coding: utf-8 -*-
"""formula_omml.py — UnicodeMath 子集 → OMML 确定性解析器（公式主路径 C）。

契约（与 omml_engine.py 兜底共享）：表达式字符串 → OMML 片段。
本模块覆盖 v1 语法子集（见 references/formula-omml.md 第三节），全确定性、
零 Office、运行时注入；子集外抛 FormulaUnsupported，交 com_layer 批量引擎。
输出结构对齐实测 PPT 原生 OMML（Word 桥接产物基准）：
  m:oMath 内：m:r(rPr+m:t) / m:f(num/den) / m:sSup(e/sup) / m:sSub(e/sub)
              / m:rad(degHide)；变量做数学斜体映射（a-z→U+1D44E..、A-Z→U+1D434..）。
"""
MATH_NS = "http://schemas.openxmlformats.org/officeDocument/2006/math"
A14_NS = "http://schemas.microsoft.com/office/drawing/2010/main"

GREEK = set("αβγδεζηθικλμνξοπρστυφχψωΑΒΓΔΕΖΗΘΙΚΛΜΝΞΟΠΡΣΤΥΦΧΨΩ")
OPS = set("+−×÷=<>≤≥≠≈±·,;:.-*∗")
STRUCT = {"^": "sup", "_": "sub", "/": "frac", "√": "rad"}


class FormulaUnsupported(ValueError):
    """子集外表达式：交 omml_engine 批量兜底。reason 供 report。"""


def _rpr(sz, color, ctrl=False):
    attrs = "lang=\"zh-CN\" altLang=\"zh-CN\" sz=\"%d\" i=\"1\" kern=\"100\" smtClean=\"0\"" % sz \
        if ctrl else "lang=\"en-US\" altLang=\"zh-CN\" sz=\"%d\" i=\"1\" kern=\"100\"" % sz
    fill = "<a:solidFill><a:srgbClr val=\"%s\"/></a:solidFill>" % color if color else ""
    return ("<a:rPr %s><a:effectLst/>%s<a:latin typeface=\"Cambria Math\"/>"
            "<a:ea typeface=\"Cambria Math\"/><a:cs typeface=\"Times New Roman\"/></a:rPr>"
            % (attrs, fill))


def _mathtext(ch):
    """单字符 → 数学斜体（变量）；数字/运算符/希腊保持原字符。"""
    # U+1D455 is unassigned; math italic small h is U+210E (PLANCK CONSTANT).
    if ch == "h":
        return "\u210e"
    if "a" <= ch <= "z":
        return chr(0x1D44E + ord(ch) - 0x61)
    if "A" <= ch <= "Z":
        return chr(0x1D434 + ord(ch) - 0x41)
    return ch


def _tokenize(expr):
    toks = []
    i = 0
    while i < len(expr):
        c = expr[i]
        if c in " \t":
            i += 1
            continue
        if c in "()":
            toks.append(("paren", c))
        elif c in STRUCT:
            toks.append(("struct", c))
        elif (c.isascii() and (c.isalpha() or c.isdigit())) or c in OPS:
            toks.append(("char", c))
        elif c in GREEK:
            toks.append(("char", c))
        else:
            raise FormulaUnsupported("未知记号 %r（子集见 references/formula-omml.md）" % c)
        i += 1
    return toks


class _Parser:
    def __init__(self, toks, sz, color):
        self.toks = toks
        self.pos = 0
        self.sz = sz
        self.color = color

    def _peek(self):
        return self.toks[self.pos] if self.pos < len(self.toks) else None

    def _next(self):
        t = self.toks[self.pos]
        self.pos += 1
        return t

    def _run(self, text, ctrl=False):
        return "<m:r>%s<m:t>%s</m:t></m:r>" % (_rpr(self.sz, self.color, ctrl), text)

    def _ctrl(self):
        return "<m:ctrlPr>%s</m:ctrlPr>" % _rpr(self.sz, self.color, ctrl=True)

    def _atom(self):
        """单 token 原子：字符 run 或括号组（字面括号字符包裹组内容）。"""
        t = self._peek()
        if t is None:
            raise FormulaUnsupported("表达式以结构记号结尾（缺操作数）")
        if t[0] == "paren" and t[1] == "(":
            self._next()
            inner = self._seq()
            return self._run("(") + inner + self._run(")")
        if t[0] == "char":
            self._next()
            return self._run(_mathtext(t[1]))
        raise FormulaUnsupported("结构记号 %r 缺操作数" % t[1])

    def _seq(self):
        """序列：unit* 直到右括号或末尾。"""
        parts = []
        while True:
            t = self._peek()
            if t is None:
                return "".join(parts)
            if t[0] == "paren" and t[1] == ")":
                self._next()
                return "".join(parts)
            parts.append(self._unit())

    def _unit(self):
        """一个完整单位：原子（可被 / ^ _ √ 组合成结构）。"""
        t = self._peek()
        if t is not None and t[0] == "struct":
            if t[1] == "√":
                self._next()
                radicand = self._atom()
                return ("<m:rad><m:radPr><m:degHide m:val=\"1\"/></m:radPr>"
                        "<m:deg/><m:e>%s</m:e></m:rad>" % radicand)
            if t[1] == "/":
                raise FormulaUnsupported("分式缺分子（禁止行首 /）")
            raise FormulaUnsupported("连续结构记号 %r（缺基）" % t[1])
        base = self._atom()
        while True:
            t = self._peek()
            if t is None or t[0] != "struct":
                break
            op = t[1]
            if op == "^" or op == "_":
                self._next()
                part_a = self._atom()
                t2 = self._peek()
                if t2 is not None and t2[0] == "struct" and t2[1] in ("^", "_") and t2[1] != op:
                    self._next()
                    part_b = self._atom()
                    # a_1^2 / a^2_1：同基上下标兼有（嵌套，渲染等效）
                    if op == "_":
                        base = ("<m:sSup><m:sSupPr>%s</m:sSupPr><m:e>"
                                "<m:sSub><m:sSubPr>%s</m:sSubPr><m:e>%s</m:e>"
                                "<m:sub>%s</m:sub></m:sSub></m:e><m:sup>%s</m:sup></m:sSup>"
                                % (self._ctrl(), self._ctrl(), base, part_a, part_b))
                    else:
                        base = ("<m:sSub><m:sSubPr>%s</m:sSubPr><m:e>"
                                "<m:sSup><m:sSupPr>%s</m:sSupPr><m:e>%s</m:e>"
                                "<m:sup>%s</m:sup></m:sSup></m:e><m:sub>%s</m:sub></m:sSub>"
                                % (self._ctrl(), self._ctrl(), base, part_a, part_b))
                elif op == "^":
                    base = ("<m:sSup><m:sSupPr>%s</m:sSupPr><m:e>%s</m:e>"
                            "<m:sup>%s</m:sup></m:sSup>" % (self._ctrl(), base, part_a))
                else:
                    base = ("<m:sSub><m:sSubPr>%s</m:sSubPr><m:e>%s</m:e>"
                            "<m:sub>%s</m:sub></m:sSub>" % (self._ctrl(), base, part_a))
            elif op == "/":
                self._next()
                den = self._atom()
                base = ("<m:f><m:fPr>%s</m:fPr><m:num>%s</m:num>"
                        "<m:den>%s</m:den></m:f>" % (self._ctrl(), base, den))
            else:
                break
        return base

    def parse(self):
        return self._seq()


def parse_expr(expr, fs=18, color=None):
    """UnicodeMath 表达式 → m:oMath 内容 XML。
    返回 {"ok": True, "omml": str}；子集外 {"ok": False, "reason": str}。"""
    if not expr or not expr.strip():
        return {"ok": False, "reason": "空表达式"}
    try:
        body = _Parser(_tokenize(expr), int(round(fs * 100)), color).parse()
    except FormulaUnsupported as ex:
        return {"ok": False, "reason": str(ex)}
    if not body:
        return {"ok": False, "reason": "空表达式"}
    return {"ok": True, "omml": body}


A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"


def omath_paragraph(omml_body, a14=A14_NS, m_ns=MATH_NS, a_ns=A_NS):
    """显示式公式段（a:p 内容）：a14:m 包 m:oMathPara（独占一行/一段）。
    omml_body 为本模块 parse_expr 产出的 m:oMath 内容。a14/m/a 三个前缀都必须
    自带声明（lxml fromstring 要求前缀绑定）。"""
    return ('<a14:m xmlns:a14="%s" xmlns:m="%s" xmlns:a="%s"><m:oMathPara>'
            '<m:oMathParaPr><m:jc m:val="centerGroup"/></m:oMathParaPr>'
            '<m:oMath>%s</m:oMath></m:oMathPara></a14:m>'
            % (a14, m_ns, a_ns, omml_body))


def omath_inline(omml_body, a14=A14_NS, m_ns=MATH_NS, a_ns=A_NS):
    """行内式公式段（a:p 内容）：a14:m 包 m:oMath，与前后 a:r 文本同流。
    PowerPoint 16.0 实测：a:p 内 a:r + a14:m/m:oMath + a:r 打开/回存原样保留
    （_probe/probe_inline_formula.py，参考用户样例 公式示例.pptx）。"""
    return ('<a14:m xmlns:a14="%s" xmlns:m="%s" xmlns:a="%s">'
            '<m:oMath>%s</m:oMath></a14:m>'
            % (a14, m_ns, a_ns, omml_body))