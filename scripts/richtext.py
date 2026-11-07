# -*- coding: utf-8 -*-
"""richtext.py — 行内富文本标记解析（**加粗** / [[强调]] / {{公式}}）。

标记语法（元素 text、表格单元格、graph 节点/边标签通用）：
  **...**   加粗（rPr b=1）
  [[...]]   强调（渲染取 params.style.emphasis 色；渲染层同时置粗+下划线）
  {{...}}   行内公式（UnicodeMath → a14:m 原生 OMML；整行独立成段）
可嵌套（**[[x]]**），不可交叉；未闭合、空标记、嵌套 [[ ]] = 编译期错误
（fail-closed：不把标记字符原样渲染到幻灯片上）。

IR 契约：元素存 plain（无标记文本，供测量/文本断言）与 runs（逐段
{text, bold, emph} 或 {formula: expr}）；渲染层只消费 runs，不重解析
（铁律 1：解析一次）。
"""


class RichTextError(ValueError):
    pass


def parse(text):
    """文本 → [{text, bold, emph}] / [{formula: expr}]。标记字符不计入段文本。"""
    if not isinstance(text, str):
        raise RichTextError("富文本输入必须为字符串")
    segs, buf = [], []
    bold = emph = False
    bold_text = emph_text = False
    stack = []                      # 开启序（"b"/"e"）：闭合必须栈顶匹配 = 禁交叉
    i, n = 0, len(text)

    def flush():
        if buf:
            segs.append({"text": "".join(buf), "bold": bold, "emph": emph})
            del buf[:]

    while i < n:
        if text.startswith("{{", i):
            flush()
            if bold or emph:
                raise RichTextError("公式标记 {{…}} 不得嵌在 **/[[ ]] 内（整行独立成段）")
            j = text.find("}}", i + 2)
            if j < 0:
                raise RichTextError("未闭合的 {{ 公式标记")
            expr = text[i + 2:j].strip()
            if not expr:
                raise RichTextError("空的 {{…}} 公式标记")
            segs.append({"formula": expr})
            i = j + 2
        elif text.startswith("**", i):
            flush()
            if bold:
                if not bold_text:
                    raise RichTextError("空的 **…** 加粗标记")
                if not stack or stack[-1] != "b":
                    raise RichTextError("标记交叉：** 在 [[…]] 内闭合"
                                        "（嵌套请写 **[[…]]**）")
                stack.pop()
                bold, bold_text = False, False
            else:
                stack.append("b")
                bold, bold_text = True, False
            i += 2
        elif text.startswith("[[", i):
            if emph:
                raise RichTextError("不允许嵌套 [[…]] 强调标记")
            flush()
            stack.append("e")
            emph, emph_text = True, False
            i += 2
        elif text.startswith("]]", i):
            if not emph:
                raise RichTextError("出现未配对的 ]] 标记")
            flush()
            if not emph_text:
                raise RichTextError("空的 [[…]] 强调标记")
            if not stack or stack[-1] != "e":
                raise RichTextError("标记交叉：]] 在 **…** 内闭合"
                                    "（嵌套请写 [[**…**]]）")
            stack.pop()
            emph, emph_text = False, False
            i += 2
        else:
            ch = text[i]
            buf.append(ch)
            if not ch.isspace():
                if bold:
                    bold_text = True
                if emph:
                    emph_text = True
            i += 1
    flush()
    if bold:
        raise RichTextError("未闭合的 ** 加粗标记")
    if emph:
        raise RichTextError("未闭合的 [[ 强调标记")
    return segs


def plain(text):
    """去掉标记后的纯文本（IR text / 测量输入）。公式段按表达式原文计入。"""
    return "".join(s.get("text", s.get("formula", "")) for s in parse(text))


def has_markup(text):
    return isinstance(text, str) and ("**" in text or "[[" in text
                                      or "]]" in text or "{{" in text)


def runs_if_markup(text):
    """有标记才返回 runs（无标记保持旧 IR 结构，零行为变化）。"""
    if not has_markup(text):
        return None
    return parse(text)
