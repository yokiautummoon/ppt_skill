# 书法矢量字（brush）与平滑切换（Morph）

> C3 视觉补充（ppt-studio 借鉴批次 2）。两项能力都**不新增几何真相源**——
> 铁律 1 不变：brush 的元素 rect 由 ir_builder 定；Morph 只是页级切换声明。

## 一、书法矢量字 `type: brush`

### 动机
艺术/书法字若用字体渲染，换机缺字即丢字形（汉字尤甚）。把**字形轮廓矢量化成
原生 `a:custGeom` 形状**后：字体不再依赖（字形成为几何），且可渐变 / 图片填充 /
缩放不糊。同一机制顺带实现「图片填充文字」。

### 语法
```yaml
- id: ink
  type: brush
  rect: [1.0, 1.5, 3.6, 3.6]     # 声明盒（字形按 ink 比例适配、居中于其中）
  text: 水墨                      # 必填，非空（字形源字符串）
  font: kai                       # 必填：别名 kai/hei/song/fang/yahei 或 .ttf/.ttc 路径
  align: center                   # 可选：字形水平落位 left/center/right（缺省 center）
  anchor: middle                  # 可选：垂直落位 top/middle/bottom（缺省 middle）
  spacing: 0.0                    # 可选：字距（em 比例，≥0）
  style:                          # 可选，三态互斥
    fill: '#1F2A44'               #   实色
    # grad: ['#2D6CDF', '#7AA2F7']  #   渐变（两色；与 fill/image 互斥）
    # image: assets/ink.png        #   图片填充（相对 SPEC 目录解析，编译期校验存在）
    # alpha: 0.85                  #   半透明（0~1）
```

### 语义与铁律
- **几何唯一源仍是 ir_builder**：`_emit_brush` 用 `ink_text.measure()` 取字形 ink
  bbox（em 单位），按 `min(w/w_em, h/h_em)` 等比缩放适配声明盒，再按 align/anchor
  定位 → 产出的元素 `rect` 是**字形紧密盒**（非原声明盒）。渲染层照常消费 IR，
  不重算几何。
- **渲染**：`_render_brush` 建 `add_shape(RECTANGLE)` → 换 `a:custGeom` 为字形轮廓
  → 三态填充（solid / gradFill / blipFill）。字形路径由 `ink_text.subpaths()` 现算
  （艺术路径，非布局几何）。
- **单路径铁律**：一个 custGeom 的 `a:pathLst` 只放**一个 `a:path`**，内含全部子路径
  （moveTo/lnTo/cubicBezTo/close 序列）。分多个 `a:path` 会让 口/日 等内孔各自填成
  实心（非零环绕不再镂空）。物证 4.4b 断言 `a:path` 数 == 1。
- **字体解析 fail-closed**：`ink_text.font_file()` 别名 → Windows 字体目录；找不到
  即抛 `FileNotFoundError`（渲染期进 errors 清单，不静默出空形状）。

### 实现栈
| 模块 | 职责 |
|------|------|
| `scripts/ink_text.py` | 字体解析（fontTools `TTFont`）+ 字形轮廓（`pathops.Path` 并集去重叠）+ 归一化子路径（y 翻转、缩放到 4000 单位） |
| `scripts/ir_builder.py` `_emit_brush` | ink 测量 → 适配声明盒 → IR 元素（`type: brush` + `brush{text,font,spacing}`） |
| `scripts/render_pptx.py` `_set_custgeom` / `_set_picture_fill` / `_render_brush` | custGeom 写入 / blipFill 写入 / 三态填充分派 |
| `scripts/spec_compile.py` `_check_brush` | text/font 必填；align/anchor/spacing/style 白名单；fill↔image 互斥；图片路径存在性 |
| `scripts/render_check_xml.py` §4.4b | custGeom 在场 + 单路径 + 三态填充物证 |

### 依赖
`fontTools` + `skia-pathops`（win_py 已装）。二次贝塞尔曲线在 `_Rec._qCurveToOne`
转三次（custGeom 只支持三次）。

### 边界（不做）
- 整块为**矢量形状**（同 curve 级）——不产可逐字编辑的文本；文案属内容 → 受数据
  红线约束。
- 每个 brush = 一个 named 单形状 → 可动画 / 可挂链接 / 可编辑组 / 可锚点（能力档案）。

## 二、页面切换 `transition: {effect: morph}`

### 语法
```yaml
meta:
  slides:
    - title: 章节
      transition: {effect: morph, dur: 900}   # dur 仅 morph 可声明（毫秒 100~5000）
```

`effect` 枚举：`fade / push / wipe / cut / morph / none`。`dur` 缺省 700ms。

### Morph 的 OOXML 形态
Morph 是 PowerPoint 2019+（p159）能力，须用 **`mc:AlternateContent` 兼容包**：
```xml
<mc:AlternateContent xmlns:mc="…markup-compatibility/2006"
                     xmlns:p159="…powerpoint/2015/09/main"
                     xmlns:p14="…powerpoint/2010/main">
  <mc:Choice Requires="p159">
    <p:transition spd="med" p14:dur="900">
      <p159:morph option="byObject"/>
    </p:transition>
  </mc:Choice>
  <mc:Fallback>
    <p:transition spd="med"><p:fade/></p:transition>   <!-- 老版本回退淡入 -->
  </mc:Fallback>
</mc:AlternateContent>
```
- **补间语义**：跨页**同名对象**（`id` 相同）自动补间变形（位置/尺寸/形状过渡）。
  示例见 `examples/ink/ink.yaml`（ink_* 跨页同名）。
- **`option`**：`byObject`（默认，按对象匹配）/ `byWord` / `byChar`。
- **dur 仅 morph 合法**：非 morph 声明 dur → 编译期 exit 2（`_check_transition`）。
- 渲染：`_inject_morph` 插在 `p:clrMapOvr` 之后（CT_Slide 顺序）。

### 物证
`render_check_xml.py` §4.7 对 morph 核对：`AlternateContent > Choice[Requires=p159] >
p:transition > p159:morph[option=byObject]` 在场 + Fallback 含 fade + `p14:dur` 一致。

### 坑
- 缺 `mc:Fallback` → 老版本 PowerPoint 打开报错（未知命名空间内容需回退）。
- `p14:dur` 挂在 `p:transition` 上（不是 morph 子元素）；`spd` 两版都要给。
- 直接写 `<p:transition><p159:morph/></p:transition>`（无 AlternateContent）→
  非 p159 宿主解析失败。

## 三、测试背书
- 突变套件：morph dur 域 / 非 morph dur / 未知 effect；brush 缺 text/font /
  fill↔image 互斥 / 图片路径不存在 / 渐变非两色 / ink 适配（`tests/run_mutations.py`）。
- 能力契约：`tests/test_capabilities.py` 背书 brush required（rect/text/font）满减必报错
  + 文档覆盖。
- 回归：`tests/regression.py` 的 `ink` 例（2 页 41 物证）。
