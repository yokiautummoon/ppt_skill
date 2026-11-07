# 矢量图标库（icon）

> B1 内化（ppt-studio 借鉴批次 3）。图标**不新增几何真相源**——铁律 1 不变：
> 元素 rect 由 ir_builder 定，渲染层照常消费 IR。

## 一、动机

位图图标换主题色要重导出、放大即糊、换机字体图标丢字形。Lucide 是一套
**描边式**（stroke）开源图标集（1857 枚，ISC 许可）：每个图标 = 24×24 viewBox 的
SVG 图元（path/circle/rect/line/polyline/polygon），无填充色、靠 `stroke` 显示。
把图元解析成 **原生 `a:custGeom` 形状**后：图标成为几何——可随 palette 着色、
缩放不糊、换机不丢。

## 二、语法

```yaml
- id: ic
  type: icon
  rect: [1.0, 1.5, 2.0, 2.0]     # 声明盒（图标正方适配居中于其中）
  icon: 水滴                      # 必填：Lucide 名（droplet）/ 中文关键词（水滴）/ 英文标签
  align: center                   # 可选：水平落位 left/center/right（缺省 center）
  anchor: middle                  # 可选：垂直落位 top/middle/bottom（缺省 middle）
  style:                          # 可选，描边语义
    color: '#2D6CDF'              #   描边色（hex / palette token；缺省 params.style.line_color）
    weight: 1.6                   #   描边磅值（> 0；缺省 params.style.icon_weight = 1.5）
```

- `icon` 解析（`icon_lib.resolve`）：先按精确名命中；否则按关键词在**名字/英文标签**
  检索（中文关键词经内置 ZH→EN 映射，如 `水滴`→`droplet`、`科学`→`flask-conical`）；
  均未命中 **fail-soft 回退 `circle-dot`**（编译期不阻断，物证仍背书形状在场）。
- 每个 icon = 一个 named 单形状 → 可动画 / 可挂链接 / 可编辑组 / 可锚点（能力档案）。

## 三、语义与铁律

- **几何唯一源仍是 ir_builder**：`_emit_icon` 把 24×24 视图盒按 `side = min(w, h)`
  **正方**适配声明盒，再按 align/anchor 定位 → 产出的元素 `rect` 是**正方盒**
  （非原声明盒）。图标路径本身由渲染层现算（艺术路径，非布局几何）。
- **描边语义（与 brush 相反）**：`_render_icon` 建 `add_shape(RECTANGLE)` → 换
  `a:custGeom` 为图标轮廓 → **每个子路径一条 `a:path`**：描边项 `fill="none"`
  （保留线描、不填充），实心项 `fill="norm"`（如 `chart-scatter` 的点，
  谓词 = 图元有 `fill` 属性）→ 形状级 `a:ln`（色/宽/`cap="rnd"` 圆头/圆角连接）。
  **区别于 brush 的单路径填充**：图标须线描，分 path 才各有 fill 语义；brush 须
  单 path 才能保留 口/日 内孔镂空。
- **形状无填充**：`sp.fill.background()` → `a:noFill`（图标只显示描边）。

## 四、实现栈

| 模块 | 职责 |
|------|------|
| `scripts/svgpath.py` | SVG path `d` 串（M/L/H/V/C/S/Q/T/A/Z，含相对指令）+ 基础图元（circle/ellipse/rect/line/polyline/polygon）→ 统一子路径表；二次贝塞尔 Q/T 与椭圆弧 A 均转三次贝塞尔（custGeom 只支持三次）。只做语法解析，不缩放/落位 |
| `scripts/icon_lib.py` | 载入 `assets/icons/lucide.json`（`_data` lru_cache）；`exists/names/find/resolve`（ZH 关键词映射 + 名/标签检索 + circle-dot 回退）；`subpaths(name)` → `(subs, vb_w, vb_h, filled)`（归一化 ×1000、y 向下、实心子路径索引 frozenset） |
| `scripts/ir_builder.py` `_emit_icon` | resolve 名 → 正方适配声明盒 → IR 元素（`type: icon` + `icon: <名>`） |
| `scripts/render_pptx.py` `_set_custgeom_stroke` / `_render_icon` | custGeom 逐子路径写 a:path（描边 fill=none）+ a:ln 圆头描线 |
| `scripts/spec_compile.py` `_check_icon` | icon 必填；align/anchor 枚举；style 白名单（color/weight），weight>0 |
| `scripts/render_check_xml.py` §4.4c | custGeom 在场 + 逐子路径描边（fill=none 计数）+ a:ln 圆头 + 描线色物证 |

## 五、依赖与资源

- 纯 stdlib（`json`/`re`/`math`）+ 自研 `svgpath`；**无第三方依赖**。
- 资源 `assets/icons/lucide.json`（1857 图标，591 KB）+ `assets/icons/LUCIDE_LICENSE.txt`（ISC）。

## 六、边界（不做）

- 整块为**矢量形状**（同 curve/brush 级）——不产可逐字编辑的文本。
- 图标**名**属于「选型」而非数据；若用户要求特定图标而回退 circle-dot，属视觉选择
  偏差（非数据红线），由用户目视复核。

## 七、OOXML 形态要点

- 形状属性容器是 **`p:spPr`**（presentationml），其子（xfrm/custGeom/ln）才是
  drawingml（`a:`）——物证 XPath 用 `p:spPr/a:ln`（写成 `a:spPr` 会找不到）。
- `a:custGeom/a:pathLst` 内**逐子路径**一条 `a:path`（本题描边语义使然）；
  `a:path@fill ∈ {none, norm}` 控该路径是否填充。
- CT 顺序：`xfrm → geom → fill → ln`（custGeom 插在 xfrm 之后；a:ln 由 python-pptx
  在 noFill 之后插入）。

## 八、测试背书

- 突变套件：icon 缺 icon / 空 icon / style 未知键 / weight≤0 / 非法 align；
  icon_lib 解析（子路径 / 24×24 viewBox / 实心索引 / 关键词回退）；IR 正方适配
  （`tests/run_mutations.py`）。
- 能力契约：`tests/test_capabilities.py` 背书 icon required（rect/icon）满减必报错
  + 文档覆盖。
- 回归：`tests/regression.py` 的 `icon` 例（2 页 110 物证）。
- 示例：`examples/icon/icon.yaml`（图标画廊 + 图标/特性卡应用）。
