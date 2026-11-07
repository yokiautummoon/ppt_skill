# ooxml-notes.md — 实证陷阱表

> 本表只收**踩过坑、有代码/文档双重实证**的结论。每一条都对应一个曾真实损坏或错位的问题。
> 新陷阱修正本表时，同时回看 grep 是否还有旧写法残留。

## 1. a:outerShdw 的颜色选择器直接是子元素（无 a:clr 包装层）

实测：`a:outerShdw` 的直接子元素即颜色选择器（`a:srgbClr` + `a:alpha`）。
若套用"标准"的 `<a:clr><a:srgbClr/></a:clr>` 包装层，PowerPoint 报 `0x80070570` 文档损坏。
正确结构：

```xml
<a:effectLst><a:outerShdw blurRad="38100" dist="19050" dir="5400000" rotWithShape="0">
  <a:srgbClr val="1F2A44"><a:alpha val="52000"/></a:srgbClr>
</a:outerShdw></a:effectLst>
```

## 2. COM cxnSp 读取 Type=1（不是 msoLine=9）

glue 连线/连线跨进程转储时，COM Connector 的 Type 枚举与直觉相反：`msoLine=9` 的说法是错的，
实测读回来是 `1`（`msoLineTypeStraight` 系）。凡按 Type 判型的分支都以实测值为准。

## 3. COM ZOrder 常量方向与"直觉"相反

probe7 实测：`msoBringToFront=2`、`msoSendToBack=3`、`msoBringForward=1`、`msoSendBackward=4` 之类
并非文档直觉顺序。使用前以本会话 probe7 实测表为准，且**只用于相对微调，不用于绝对 z**。

## 4. lxml 空元素 bool() 为 False —— find(...) or find(...) 链必短路（2026-09 实证）

`<p:cNvPr id="2" name="title"/>` 无子节点、无文本 → `bool(el) is False`。
因此：

```python
# 错误：nv 恒为 None（前一个 find 命中空元素也被当假）
nv = el.find(A) or el.find(B) or el.find(C)
# 正确：显式 None 判断
nv = el.find(A)
if nv is None:
    nv = el.find(B)
if nv is None:
    nv = el.find(C)
```

`scripts/render_check_xml.py::_cnv_name`、`render_pptx.py::_cnv_name` 为正确范本。

## 5. 绝不能用 id(oxml 元素) 作 dict 键做重排（lxml 代理 GC 后 id 复用）

lxml `_Element` 是代理对象；Shape 包装被 GC 后其 `_element` 代理可被回收，`id()` 随即被复用。
渲染完再 `list(spTree)` 得到的新代理与注册时未必同一对象 → 重排错位（实测 z 映射大片 MISS）。
正确做法：name → z 映射（name 唯一），重排时读形状 `cNvPr@name` 查 z。
与 COM 按名查找、XML 物证按名定位同机制。

## 6. cxnSp 的 xfrm 是两端点 min-corner 盒（方向无关）

`add_connector(a1, a2)` 写入 XML 的 `a:off` 恒为 `(min(x1,x2), min(y1,y2))`，
`a:ext` 为 `(|x2-x1|, |y2-y1|)`。向上/向左的线段 off 不是 a1。
物证比对必须用 min-corner 盒公式（`render_check_xml._seg_box`），不能假设 off==a1。

## 7. OOXML 层级真相源：spTree 文档序（越靠后越靠前）

"置于顶/底层"不是属性，是 XML 元素顺序。python-pptx 按创建顺序 append（元素→组→线），
与 IR z 完全无关 → 渲染器必须 `_apply_z_order` 按 IR z 稳定重排，否则组/线盖住更高 z 的节点。
COM ZOrder 方法只能相对移动（BringForward/SendBackward …），无法设绝对 z，仅作后期微调。
物证：`render_check_xml` 第 6 节断言文档序 z 非递减且每形状有 z 映射。

## 8. 其他已实证

- `svgBlip`/无 `a:clr` 的 fill 变体需逐个 Office 验证；`a:alpha` 是 `alpha` 值（52000=52%）。
- 渐变：python-pptx `fill.gradient()`，两 stop 颜色；palette `{grad:[c1,c2]}` 展开。
- CJK 字体双轨：`a:latin` + `a:ea` 都写 typeface（`set_cjk`）。

## 9. COM 绑定物证（2026-09 全链实测）

- **站点索引→边表**（PowerPoint 16.0，`probe_com_map3` 双角点实测法）：
  形状族不同站点数——rect/rounded_rect/diamond `{N:1,S:3,E:4,W:2}`、
  can `{N:2,S:4,E:5,W:3}`、oval `{N:1,S:5,E:7,W:3}`、
  parallelogram `{N:1,S:5,E:3,W:6}`、hexagon `{N:1,S:4,E:5,W:3}`。
  位于 `com_layer.SITE_BY_KIND`（1 基）。
- **stCxn/endCxn 的 idx 是 0 基**：`BeginConnect(sh, s1)` 后 XML 写
  `<a:stCxn id="{sh.id}" idx="{s1-1}"/>`。物证：s1(E 站 4) → idx=3、s2(W 站 2) → idx=1。
- **AddOLEObject(FileName=.vsdx, Link=0) = Type 7 原生嵌入**：双击进 Visio 编辑，
  与 Word 端 OLE 流程一致；`DisplayAsIcon=0`。rect 由 EMU/12700 → 英寸落位。
- **Range().Group() 组合**：成员 .name 保留；组可赋名（`{容器id}.group`）。
- **随动自检**：`IncrementLeft(+60)` 后读连线 `Left` 变化（绑定成立）再复原；
  `ConnectorFormat.BeginConnectedShape` 可回读绑定对象。
- **Windows python 起子进程**：用 `sys.executable`（裸名 `win_py` 在
  CreateProcess 里找不到），`-m com_layer` 配 `cwd=scripts/` 进 sys.path；
  作业路径一律绝对（子进程 cwd 不同）。

## 10. CT_CommonSlideData 的 p:bg 单元素约束（双 bg → 0x80070570）

python-pptx 默认模板的 slideMaster1 自带 `<p:bg><p:bgRef idx="1001"/></p:bg>`，
`cSld.insert(0, bg)` 硬插第二个 bg → XSD 违规（p:bg maxOccurs=1）→ Office 打开报
"不能打开演示"（0x80070570，注释一贯"文档损坏"表象）。必须先 `cSld.remove(旧 bg)`
再 `spTree.addprevious(bg)`（顺带保证 bg → spTree → extLst 的 CT_CommonSlideData 序）。
同类约束：clrScheme 每槽恰一子元素（`_rewrite_theme` 遇 sysClr 整体替换为单个
srgbClr），否则同坏。

## 11. seed 剥离模板页：sldIdLst 移除必须连带 drop_rel

仅移 `<p:sldIdLst>` 项会留下 presentation→slide rel，slide part 仍可达 →
序列化时落重复 partname（坏 zip，COM Documents.Open -2134162428 "发生意外"）。
`_strip_slides` 对每个 sldId 先 `prs.part.drop_rel(rId)` 再 `sldIdLst.remove(sldId)`。
python-pptx 的 prs.part 是 PresentationPart，有 drop_rel（KeyError 需吞）。

## 12. 占位符 idx 继承语义

实例化占位符的 `placeholder_format.idx` 是**生效值**（继承自版式/母版链的最终
值），与 analyzer 读版式 `<p:ph>` 的 idx 一致——seed 打底按 idx 匹配即可；
idx 缺省时按 cNvPr@name 回退（`_find_placeholder` 双轨）。

## 13. 动画 COM 构造实证（2026-09，PowerPoint 16.0 + win32com）

- **常量实测表**（`animation_constants.py` 回退表）：MsoAnimType Set=8
  Filter=7 Property=5 Rotation=4 Scale=3 Motion=1；MsoAnimEffect Custom=0；
  MsoAnimProperty Visibility=8 X=1 Y=2 Width=3 Height=4 Rotation=6；
  MsoAnimFilterEffectType Fade=8；MsoAnimTriggerType WithPrevious=2；
  MsoAnimateByLevel Paragraph=0 Character=2。MsoTriState（msoTrue=-1）在
  **Office 共享类型库**、PowerPoint typelib 不含 → 恒走硬编码。
- **AddEffect level 参数必须 0**：`seq.AddEffect(shp, custom, 0, withPrev)`。
  pywin32 传 `None` → 类型化参数 `int(None)` 报错；传 -1
  （ppAnimateByLevelNone）→ "Invalid enumeration value"；0 稳定接受
  （ppAnimateByParagraph 系）。
- **`Behaviors(1).Delete()` 定终态**：AddEffect(custom) 会预置 1 个默认
  behavior；34/35 宏末尾显式 `Behaviors(1).Delete()` 移除它 → 终态
  `Behaviors.Count == 配方 behaviors 数`（self-check 回读背书，不硬断言）。
  12 个宏首 behavior 是 set To=0（初始隐藏）——Delete 只删第一个，其余行为
  保留，终态由 PowerPoint 定。
- **ConvertToTextUnitEffect(eff, ppAnimateByParagraph=0|Character=2)**：
  尾部切换文本级动画单位；两值 probe 实测合法。
- **粒子公式字符串原文落 COM**：`pt.Value = "#ppt_y-.05"`、`#ppt_x` 等整串
  赋值，无单位换算；个别宏起点/终点不带 # 前缀（如 `ppt_y-0.02`）亦原文。
- **构造序 = 配方序**：set/filter/property/scale/rotation/motion 六种
  behavior 按配方依次 `Behaviors.Add`；type 专属对象（PropertyEffect.Points
  逐点 Add 且 `pt.Time/pt.Value/Formula` 双字段）构造失败即 WARN 不阻断。

## 14. freeform 局部坐标取整陷阱（2026-09，cylinder/curve 积木 probe 实测）

- **build_freeform(start_x, start_y, scale) 的局部坐标被 round() 成整数后乘
  scale 转 EMU**：python-pptx 内部 `_local_to_emu` 对每个点 `round(coord * scale)`
  落 EMU。scale 传 1（局部单位英寸）→ `1.8` 被取整成 `2.0`，物证 xfrm 偏差
  0.2 in，超 eps 判 FAIL。**局部单位必须够细**：用 1/10000 in（
  `S = 10000.0`，`build_freeform(x*S, y*S, 914400/S)`），取整误差 ≤0.00005 in
  < 1pt eps。
- **convert_to_shape(Emu(0), Emu(0))**：freeform 几何 settle 后把局部原点
  落到 slide 原点（0,0），xfrm = 点集 min-max 盒（方向无关）；错误地传
  "左上角"会让 xfrm 偏移双倍。
- **cylinder 复合展开**（ir_builder，部件序 z+0..z+5）：侧壁 rect（a:alpha
  opacity×100000 注进 solidFill 的 srgbClr）、底椭圆（透视高 = 宽×0.16）、
  顶椭圆（slice<1 省略 = 剖视敞口）、2 条等高弧（`_arc_pts` 椭圆弧采样
  25 点 polyline 进 custGeom，曲线不取整——弧点由脚本算不进 freeform）、
  标注文字（居圆柱中部，guard 以侧壁主色为底）。部件 owner = 元素 id
  （verify G4 同 owner 兄弟豁免遮挡）。
- **MSOL 无 DOT**：python-pptx `MSO_LINE_DASH_STYLE` 枚举无 `DOT`，实测成员
  为 `ROUND_DOT`/`SQUARE_DOT`——`dot → ROUND_DOT`（对应 `<a:prstDash
  val="sysDot"/>`，PowerPoint 圆点虚线）。

## 15. 字体嵌入：COM 置位成功但不产 fntdata（2026-10，B5 实测）

- **`Presentation.EmbedTrueTypeFonts = True` 可置位、回读 True，但保存后包内
  无 `ppt/fonts/*.fntdata`、presentation.xml 无 `embeddedFontLst`**（PowerPoint
  16.0 + win32com 实测）。变体均无效：`Save()`、`SaveAs(path, 24)`、
  `SaveAs(path, 24, True)` 位置参、`WithWindow=True`、`pres.SaveSubsetFonts=True`。
- 字族授权不是唯一原因：本地扫描 164 个 .ttf，fsType 多为 0x0/0x8（installable/
  editable embedding 允许），Calibri 亦为 0x8，仍无产物 → 判定为**自动化保存
  路径不执行嵌入**（GUI「另存为 → 工具 → 保存选项 → 嵌入字体」是可靠通道）。
- 因此 B5 的 `--embed-fonts`/`font.portable` 语义 = **请求 + 诚实核对**：
  com_layer 置位后扫包 `ppt/fonts/*.fntdata`，无产物 → WARN
  （`fonts.empty_reason = "no_fntdata"`），不阻断（`--com-strict` 可升级为 exit 5）。
  跨机可移植的等效手法 = 通用字族（params.font.latin/ea 取目标机必有字体）+
  `font.portable_list` 人工确认清单。
## 16. 平滑切换（Morph）必须用 mc:AlternateContent 兼容包（2026-10，C3 probe 实测）

Morph 是 p159（PowerPoint 2015/09 命名空间）能力。**不能**直接写
`<p:transition><p159:morph/></p:transition>`——非 p159 宿主无法解析 p159 子元素。
必须包在 `mc:AlternateContent` 里，Choice 要求 p159、Fallback 给 fade：

```xml
<mc:AlternateContent xmlns:mc="…markup-compatibility/2006"
                     xmlns:p159="…powerpoint/2015/09/main"
                     xmlns:p14="…powerpoint/2010/main">
  <mc:Choice Requires="p159">
    <p:transition spd="med" p14:dur="900"><p159:morph option="byObject"/></p:transition>
  </mc:Choice>
  <mc:Fallback><p:transition spd="med"><p:fade/></p:transition></mc:Fallback>
</mc:AlternateContent>
```
- `p14:dur` 挂在 `p:transition` 上（不是 morph 的子元素）；`spd` 两版都给。
- 插在 `p:clrMapOvr` 之后（CT_Slide 子序）。
- `option`：byObject（默认，按同名对象补间）/ byWord / byChar。

## 17. custGeom 内孔镂空：全部子路径放同一个 a:path（2026-10，C3 brush 实测）

书法字（口/日/回 等）含内孔。custGeom 的 `a:pathLst` 若**每个子路径各放一个
`a:path`**，各 path 独立按非零环绕填充 → 内孔被填成实心。正确做法：**一个
`a:path` 内含全部子路径**（连续 moveTo/lnTo/cubicBezTo/close 序列），跨子路径
的非零环绕才能让内孔（反向绕）镂空。`pathops.Path.simplify(fix_winding=True)`
并集后再落盘，去笔画自重叠。
- custGeom 只支持三次曲线 → 字体二次贝塞尔在 `ink_text._Rec._qCurveToOne` 转三次。

## 18. 形状级图片填充 = a:blipFill（sed 图片 part rel）（2026-10，C3 实测）

「图片填充文字」不是 run 级属性，而是**形状级** `a:blipFill`：
`<a:blipFill rotWithShape="1"><a:blip r:embed="rIdN"/>[<a:alphaModFix amt=…/>]
<a:stretch><a:fillRect/></a:stretch></a:blipFill>`。图片 part/rel 由
`slide.part.get_or_add_image_part(path)` 落（rId 挂 slide rels）。填充选择器
CT 顺序：xfrm → geom(custGeom) → **fill** → ln → effectLst；故 blipFill 须插在
geom 之后、`a:ln` 之前（`ln.addprevious(bf)`）。

## 19. 图标描边 custGeom：逐子路径 a:path + p:spPr 命名空间（2026-10，B1 实测）

矢量图标（Lucide 描边式）与书法字（填充式）**custGeom 用法相反**：
- 图标须**逐子路径各一条 `a:path`**，`a:path@fill ∈ {none, norm}`——描边项
  `fill="none"`（不填充，靠形状级 `a:ln` 线描），实心项 `fill="norm"`（如散点的点）。
  分 path 才各有独立 fill 语义；合并单 path 会把描边区域也填实。
- 书法字须**单 `a:path` 含全部子路径**（见 §17），保内孔镂空。二者不可混用同一写入器。
- 形状级描线：`<a:ln w="…" cap="rnd"><a:solidFill>…</a:solidFill><a:round/></a:ln>`
  （圆头端点 + 圆角连接，贴合 Lucide 圆角风格）。

**命名空间坑**：`p:sp` 的形状属性容器是 **`p:spPr`**（presentationml 域），
其**子**（`a:xfrm`/`a:custGeom`/`a:noFill`/`a:ln`）才是 drawingml 域。物证 XPath
须用 `p:spPr/a:ln`——写成 `a:spPr/a:ln` 会**恒找不到**（该命名空间下无 spPr 元素），
且 `.//a:ln` 仍能命中（易造成「spPr 找不到但 ln 找得到」的错觉）。`p:graphicFrame`
的坐标是 `p:xfrm` 同理（见 §早）。
