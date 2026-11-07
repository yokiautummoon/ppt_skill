# typst 复杂精美排版链路（type: typst）

把 [typst](https://typst.app)（现代排版系统：文本 / 多栏 / 表格 / 数学 / 绘图）
作为一类确定性积木接入管线：**agent 写 typst 源码（或由 LLM 辅助设计），
引擎确定性编译成图块落版**。解决的场景：用 Office 形状与文本积木难以表达
的复杂版式（多栏、精细排版、版式化图表、ceTZ 矢量示意图）。

> **定位**：示意图/复杂版式首选 typst（ceTZ 是现代 tikz 的等价物）→ 其次组合
> Office 形状（可编辑优先场景）→ Python 制图仅数据图（见 CLAUDE.md 渲染规则）。
> 与公式链**隔离**：typst 块内公式由 typst 自排（整块图），不掺和 `type: formula`
> 的 OMML 原生注入链——两个公式系统各司其职。

## 1. 铁律与边界（先读这一节）

| 约束 | 说明 |
|---|---|
| 整块为图 | 产物是 SVG/PNG 图块，**不可逐字编辑**（内容型积木，同 diagram/image 级）；要逐字改回原生 shape/text 积木 |
| 数据红线 | 排版内文本属内容：数字/分类/引用须溯源 `meta.brief` 原文或标 `[占位]`，禁止编造（同 llm_fixer CHECK_OUT） |
| 几何唯一源 | **页面尺寸 = 元素 rect**（1in = 72pt）→ 渲染零重算（铁律 1 的排版块对应物）。**自动围切最小边界盒**：元素实际 rect = 声明 rect 原点 + 内容偏移，尺寸 = 内容 bbox（stage1.5 编译后裁 PNG / 重写 SVG viewBox；用户 preamble 自设 page 时 size=画布、offset=0）——内容四周无空白、不溢出区外 |
| 顶层限制 | 排版块不进容器 children（与 chart 同律：需顶层声明绝对 rect） |
| 编译闸门 | typst 语法错误 → **exit 2**（含文件/行号/源码片段）；CLI 缺失 → exit 2 提示（显式请求，不静默降级） |

## 2. SPEC 语法

```yaml
- id: hero                     # 页级唯一 id（渲染为图形名，物证/COM 按名定位）
  type: typst
  rect: [0.5, 0.5, 12.3, 2.2]  # 必填：版式区域；typst 页面尺寸即此（×72 = pt）
  # ---- 源三分（恰选其一；编译期互斥校验）----
  typst: |                     # (a) inline 源码
    #set text(size: 15pt)
    #block(fill: rgb("#1F2A44"), inset: 12pt, radius: 6pt)[
      #align(center)[#text(fill: white, size: 28pt)[标题]]
    ]
  # typst_src: assets/section.typ   # (b) 外链 .typ（相对 SPEC 目录；编译期查存在性）
  # design: "一句话设计意图"         # (c) LLM 辅助设计（协议见 §6；当前编译期拦截提示）
  preamble: |                  # 可选：共享前导（字体/宏/@preview 导入），先于正文
    #import "@preview/cetz:0.3.1": *
  vars: {year: "2026", title: "年报"}   # 可选：#let 变量注入（正文用 #year）
```

字段白名单（spec_validator `PER_TYPE["typst"]`）：`typst` / `typst_src` /
`design` / `preamble` / `vars` + COMMON_FIELDS。

## 3. 编译（stage1.5，`typst_compile.py`）

- 编译器：`scripts/typst-cli/typst.exe`（官方 typst 二进制 0.15.x；Windows）。
  调用 `typst compile -f svg` 与 `-f png --ppi 300`，无 Office 依赖。
- 默认前导（用户 preamble 不含 `#set page` 时注入）：
  ```typst
  #set page(width: <rect.w×72>pt, height: <rect.h×72>pt, margin: 0pt)
  #set text(font: ("Microsoft YaHei", "SimSun", "Times New Roman"), size: 11pt)
  ```
- 产物（`<out_dir>/typst_cache/<page>_<id>.{typ,png,svg}`）：
  - `.typ` 源码（审计：完整装配后的源）
  - `.svg` 矢量：typst 字形输出为**轮廓 path**，自包含、不引用字体文件
  - `.png` 栅格 fallback：300ppi
- **自动围切最小边界盒**：typst 排版内容实际占据范围小于页面（margin: 0pt 时
  四周仍常有多余空白）→ 编译后按内容 bbox 裁剪：PNG 裁去空白行/列、SVG 重写
  `viewBox` 为内容范围（`typst compile --overlay` 的 frame bbox 通道）。落版
  语义：**元素实际渲染 rect = 声明 rect 原点 + 内容偏移（offset，pt）→
  尺寸 = 内容 bbox（size，pt）**——内容贴紧区外、无空白。ir_builder 依
  `_typst.size/_typst.offset` 重算元素 rect（`typst_size` 透传递渲染）。
  用户 preamble 自设 `#set page` 时 size=画布、offset=0（自设页面即信任，
  不裁）。
- 比例守护：`_svg_size_pt` 读 viewBox；用户 preamble 自设 page 而与 rect 不符时
  → WARN（渲染仍按 rect 落版，可能变形）。

## 4. 渲染（双通道合一）

OOXML 2016+ 的 SVG 图片规范 = `a:blip`（承载栅格 fallback）+ `a:extLst` 内
`asvg:svgBlip`（矢量），双 rId 结构。python-pptx 的 `add_picture` 不支持 svg
（`image_content_types` 表无 svg），故实现为：

1. `add_picture(png)` 建常规图片（fallback rId）
2. 手动加 svg part（`/ppt/media/imageN.svg`，content type `image/svg+xml`）+ slide 关系
3. 往 `a:blip` 注入 `a:extLst/a:ext[@uri={96DAC541-...}]/asvg:svgBlip@r:embed`

```xml
<a:blip r:embed="rId2">                      <!-- PNG fallback -->
  <a:extLst>
    <a:ext uri="{96DAC541-7B7A-43D3-8B79-37D633B846F1}">
      <asvg:svgBlip xmlns:asvg="http://schemas.microsoft.com/office/drawing/2016/SVG/main"
                    r:embed="rId3"/>          <!-- SVG 矢量 -->
    </a:ext>
  </a:extLst>
</a:blip>
```

显示语义：PPT 2016+ 渲染矢量 SVG；旧版渲染 PNG fallback。svg 注入失败
（或缺 svg 产物）→ 降级纯 PNG，组件银行记 `typst_png_fallback`（WARN，不阻断）。

## 5. 物证（stage5）

- `typst PNG fallback <id>`：`a:blip/@r:embed` → `.png` part
- `typst SVG 矢量 <id>`：`svgBlip/@r:embed` → `.svg` part 且该 part 在包内；
  无 svgBlip → 记 ok（"PNG fallback（svgBlip 未注入，降级合法）"）
- 通用项：`坐标/尺寸`（rect → EMU，±1pt）、`层级`（z 序 = spTree 文档序）

权威验证 = PowerPoint 打开 round-trip（矢量显示、另存后 svgBlip 保留、可右键
"转换为形状"再编辑）。

## 6. LLM 辅助设计（作业协议 v1；同 --fix 修订链同构）

**动机**：typst 表达力强但语法自成一系。让 LLM 从"设计意图"生成 `.typ`，再由
确定性编译闸门把关——编译通过才落地（"精美"可生成、"正确"可验证）。

**当前状态**：`design` 字段已在 SPEC 白名单与编译期校验（未落地 → 明确报错提示
走本协议）；CLI 作业通道与 `typst_designer` 模块待实现（预留）。下面为待实现的
协议设计（与 `llm_fixer` 的 exit 6 稳态暂停模型对齐）：

```
1. SPEC: type:typst + design:"一段设计意图"（无 typst/typst_src）
2. build_ppt 编译期检测 → 写 <out>/typst_job.json → exit 6（稳态暂停，非错误）
     {version, spec, page, element, intent, brief, rect,
      palette, style_guide, fonts(白名单), allow_preview(默认 false), max_rounds(默认 3)}
3. agent / 外部 LLM 读 job → 产出 typst_out.json（写回）：
     {element, typ(完整源码), basis(意图/数据溯源), rounds:[{typ, errors}]}
4. 重跑同命令：管线读 out → typst 编译验证
     成功 → 视同 typst_src 落地（源落 typst_cache 审计）→ 继续渲染
     失败 → stderr 回写 typst_out.json.errors → 再 exit 6（≤ max_rounds）
     max_rounds 用尽 → exit 3（附最后一次错误）
```

- **数据红线**：排版内数字/分类/引用须溯源 `brief` 原文或标 `[占位]`；违反 → 整批
  拒绝（同 llm_fixer CHECK_OUT 事务语义）。
- **离线约束**：`allow_preview: false` 时禁 `@preview` 包（编译期已能捕获网络失败）。
- **真实 API**：`--llm-client` 预留（桥接在 typst_designer；fake client 回放测试）。

## 7. 扩展点

- **多页复用**：同 id 跨页合法（缓存键含页号）；跨页共享前导可放 `meta.params`？
  暂不——首版逐元素 preamble（显式优于隐式）。
- **CEX/EMF 通道**：如需"解除组合转原生形状"，typst→EMF 需外部转换器（Inkscape/
  LibreOffice），非确定性且字体丢失风险 → 不进默认链（用户明确需要再评估）。
- **公式联动**：typst 块内 `$...$` 归 typst 管；若要把 typst 数学作为 OMML 子集外
  的兜底源（替换 Word 引擎），需另立通道（当前不做，避免两系统耦合）。
