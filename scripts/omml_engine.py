# -*- coding: utf-8 -*-
"""omml_engine.py — Word 公式生成引擎：批量 OMML（零剪贴板，函数接口）。

用户洞察落地：把"分部写入 → OMaths.Add+BuildUp → 存 docx → 解包按段切 OMML"
封装成函数接口 —— 等价于 PowerPoint 缺位的"公式 COM API"的自适应层。

接口：word_batch_omml(exprs) -> list[dict{ok, omml, reason}]
  - omml = m:oMath 内部内容（与 formula_omml.parse_expr 契约一致，可由注入方
    统一 wrap_omath/omath_paragraph）。
  - 一次 Word 进程吞 N 表达式：吞吐从 O(N) 进程降到 O(1)。零剪贴板（不 Copy/Paste，
    产物走 docx 文件解包）。
仅 win_py 运行（import win32com + lxml）。
"""
import os
import shutil
import tempfile
import zipfile

from com_layer import dispatch_retry  # Dispatch 瞬态启动错误重试（-2146959355 等）

_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
_M = "{http://schemas.openxmlformats.org/officeDocument/2006/math}"


def _extract_omml(docx_path):
    """docx 内每个含公式的段落 → m:oMath 内部内容字符串（顺序 = 段落序）。"""
    from lxml import etree
    with zipfile.ZipFile(docx_path) as z:
        root = etree.fromstring(z.read("word/document.xml"))
    out = []
    for p in root.iter(f"{_W}p"):
        # 独占段落公式：w:p > m:oMathPara > m:oMath；行内则直接 m:oMath
        om = p.find(f"{_M}oMathPara/{_M}oMath")
        if om is None:
            om = p.find(f"{_M}oMath")
        if om is None:
            continue
        out.append("".join(etree.tostring(c, encoding="unicode") for c in om))
    return out


def word_batch_omml(exprs):
    """N 个 UnicodeMath 表达式 → N 个结果（ok + omml/reason）。
    整批共享一次 Word 进程；失败项（BuildUp 异常）保留表达式文本不产出公式。"""
    ans = [None] * len(exprs)
    tmp_dir = tempfile.mkdtemp(prefix="omml_")
    tmp_docx = os.path.join(tmp_dir, "src.docx")
    try:
        _batch(exprs, ans, tmp_docx)
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
    return ans


def _batch(exprs, ans, tmp_docx):
    """一次性 Word 进程主体（独立函数便于集中释放资源）。"""
    try:
        import win32com.client as w
    except ImportError:
        for i in range(len(ans)):
            ans[i] = {"ok": False, "reason": "win32com 不可用"}
        return
    try:
        wapp = dispatch_retry("Word.Application", retries=2, wait=2.0, tag="Word")
        wapp.Visible = False
    except Exception as ex:
        for i in range(len(ans)):
            ans[i] = {"ok": False, "reason": "Word 启动失败: %s" % str(ex)[:100]}
        return
    try:
        doc = wapp.Documents.Add()
        doc.Content.Text = "\r".join(exprs)      # \r = 段落分隔
        sel = wapp.Selection
        for i in range(len(exprs)):
            rng = doc.Paragraphs(i + 1).Range
            rng.MoveEnd(1, -1)                    # 去掉段落符（wdCharacter=1）
            try:
                rng.Select()                      # 显式光标定位：批量下不 Select 则
                                                  # 光标滞留上下文，后续 Add 错乱
                                                  # （实测第一段 nary、其余退化 m:r 纯文本）
                sel.OMaths.Add(rng)
                # 只 BuildUp 刚加入的最后一个 OMath（集合索引是标准 COM，
                # 规避 dynamic 分派对 Add 返回值的兼容问题）
                sel.OMaths(sel.OMaths.Count).BuildUp()
                ans[i] = {"ok": True}
            except Exception as ex:
                ans[i] = {"ok": False, "reason": str(ex)[:120]}
        doc.SaveAs2(tmp_docx, 12)                 # wdFormatXMLDocument
        doc.Close(False)
        ommls = _extract_omml(tmp_docx)
        j = 0
        for i, a in enumerate(ans):
            if a and a.get("ok"):
                a["ok"] = j < len(ommls)
                if a["ok"]:
                    a["omml"] = ommls[j]
                    j += 1
                else:
                    a["reason"] = "引擎未产出 OMML（段落提取不足）"
    except Exception as ex:
        for i, a in enumerate(ans):
            if a is None:
                ans[i] = {"ok": False, "reason": "批量作业异常: %s" % str(ex)[:120]}
    finally:
        try:
            wapp.Quit()
        except Exception:
            pass
    return ans