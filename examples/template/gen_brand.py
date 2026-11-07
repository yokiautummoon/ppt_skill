# -*- coding: utf-8 -*-
"""gen_brand.py — 生成模板样本 brand.pptx（示例用，非 skill 产物）。

用途：让 extract / seed 示例有真实母版素材——
  - 页面 10×5 in；主题 accent1 品牌蓝 #2D6CDF（zip 重写 theme1.xml）；
  - 母版背景固体色 #EAF1F9（extract 的 framework 背景来源）；
  - 两页：Title Slide（ctrTitle + subTitle 占位符，默认提示文本）+ Blank。

用法：win_py -X utf8 -W ignore examples/template/gen_brand.py
"""
import os
import shutil
import zipfile

from pptx import Presentation
from pptx.oxml.ns import qn
from pptx.util import Inches

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "brand.pptx")


def set_master_bg(prs, color):
    """母版背景固体色（p:cSld 的 p:bg > p:bgPr > a:solidFill）。

    铁律：CT_CommonSlideData 中 p:bg 可选且单元素（maxOccurs=1）——
    默认模板自带 <p:bg><p:bgRef idx="1001"/></p:bg>，直接 insert 会产生
    两个 bg → schema 违规 → Office 0x80070570 文档损坏。必须先移除旧的。"""
    master = prs.slide_masters[0]
    cSld = master._element.find(qn("p:cSld"))
    old = cSld.find(qn("p:bg"))
    if old is not None:
        cSld.remove(old)
    bg = cSld.makeelement(qn("p:bg"), {})
    bgPr = cSld.makeelement(qn("p:bgPr"), {})
    sf = cSld.makeelement(qn("a:solidFill"), {})
    rgb = cSld.makeelement(qn("a:srgbClr"), {"val": color})
    sf.append(rgb)
    bgPr.append(sf)
    bg.append(bgPr)
    cSld.find(qn("p:spTree")).addprevious(bg)   # bg → spTree → extLst 序


def main():
    prs = Presentation()
    prs.slide_width = Inches(10)
    prs.slide_height = Inches(5)
    set_master_bg(prs, "EAF1F9")
    s1 = prs.slides.add_slide(prs.slide_layouts[0])   # Title Slide
    s1.shapes.title.text = "Brand Template"
    s1.placeholders[1].text = "subtitle placeholder"
    prs.slides.add_slide(prs.slide_layouts[6])        # Blank
    prs.save(OUT)
    # theme1.xml：accent1 → #2D6CDF（品牌蓝；zip 重写保序，值与原槽同形）
    tmp = OUT + ".t"
    with zipfile.ZipFile(OUT) as zin, zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            data = zin.read(item.filename)
            if item.filename == "ppt/theme/theme1.xml":
                xml = data.decode("utf-8")
                assert 'val="4F81BD"' in xml, "默认模板 accent1 应为 #4F81BD"
                xml = xml.replace('val="4F81BD"', 'val="2D6CDF"', 1)
                data = xml.encode("utf-8")
            zout.writestr(item, data)
    shutil.move(tmp, OUT)
    print("brand.pptx:", OUT)


if __name__ == "__main__":
    main()