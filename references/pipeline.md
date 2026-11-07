# 管线：命令 / Gates / 退出码 / 产物 / COM 契约

## 单入口 CLI

```bash
win_py scripts/build_ppt.py <spec.yaml> [--out DIR] [--com] [--com-strict]
                            [--pdf] [--report md|json|none]
```

- `--com`：COM 后处理（glue/group/ole/公式兜底/PNG 预览，需 Office）。
- `--pdf`：导出 `base.pdf`（分发格式）。隐含进入 stage6；需 Office。
  无 Office / Office 缺 PDF 组件 → WARN 降级（无 PDF 产物）；显式请求失败
  在 `--com-strict` 下 → exit 5。

必须用 **win_py**（Windows Python，装了 pyyaml + python-pptx；`--com` 还需
pywin32 + 真实 Office）。WSL 原生 python3 无依赖，不可用。

## Stage 与 Gates（stage 号 = 退出码断点）

| stage | 动作 | 失败 | 产出 |
|---|---|---|---|
| 0 load | YAML 读取 | exit 1 | — |
| 1 compile | spec_compile 结构检查 + spec_validator 白名单 | exit 2 | compiled |
| 2 layout | params 合并 + ir_builder.build_ir | exit 1 | ir.json |
| 3 verify | verify.run（G/T/D/S 家族断言） | exit 3 + report | report.md/json |
| 4 render | render_pptx（纯消费 IR） | exit 4 | base.pptx |
| 5 evidence | render_check_xml 解包 XML 物证 | exit 4 | 物证清单 |
| 6 com | 可选：win_py 子进程跑 com_layer 作业 | (strict→5) | com_out.json, preview.png |

**退出码契约**：`0` 全过（无 COM 时降级仍 0）；`1` IO/环境/内部；
`2` 编译静态失败；`3` 校验 FAIL；`4` 渲染/物证失败；`5` `--com-strict` 下 COM 失败。
COM 默认 **WARN 不阻断**（产物 = base.pptx + report，管线照常 exit 0）。

**多页序列（meta.slides）**：stage2/3/5 逐页执行——每页独立 build_ir +
verify + XML 物证（slideN.xml ↔ 第 N-1 页），violations 跨页汇总，任一页
FAIL → exit 3；渲染产一文件多 slide（footer `{page}` 逐页展开）；
`ir.json` 多页时写 list（单页仍 dict）；COM 按页遍历 Slides(i+1)，
预览逐页 `preview.png` / `preview-2.png` / …（第 1 页 = 无后缀）。
见 examples/deck/。

## stage6 COM 作业契约（com_layer）

主进程把 job 写到 `out/com_job.json` → win_py 子进程 `-m com_layer`（cwd=scripts/）→
写回 `out/com_out.json`。

请求：
```json
{"out": "<out绝对>", "base": "<out>/base.pptx", "ir": "<out>/ir.json",
 "pdf": true|false,                 // --pdf 时为 true：导出 base.pdf
 "embed_fonts": true|false,         // --embed-fonts / font.portable：请求嵌入字体
 "fonts": ["Calibri", "微软雅黑", ...]}  // 请求嵌入的字族清单（declared）
```

响应（com_out.json）：
```json
{
  "glue":   [{"id","ok","side1","side2","site1","site2","detail"}],
  "groups": [{"id","ok","name","n"}],
  "follow": {"ok","bound", "before":[L,T],"after":[L,T]},
  "ole":    [{"id","ok","detail"}],
  "formulas": {"pending", "injected":[], "failed":[]},
  "fonts":  {"requested", "declared":[], "embedded":[], "empty_reason"},
  "overflow": [{"id","page","text_h","frame_h","over_pt"}],
  "png":    "<out>/preview.png",
  "pdf":    "<out>/base.pdf | null",
  "warnings": [...] , "saved": "<base路径>"
}
```

作业项：
- **glue** 绑定：按 IR glue 记录，`ConnectorFormat.BeginConnect/EndConnect`
  把连线端点吸到起始/目标形状的站点（站点索引 ∈ 实测表，PowerPoint 16.0）。
  端点形状缺失 → WARN 并保持"坐标锚点直线"（非绑定语义）。
- **follow 随动自检**（诊断）：对第一条成功绑定的 glue，起点 `IncrementLeft(+60)`
  断言连线 Left 变化（随动成立）后复原。`params.com.follow_test_pt` 控制步长。
- **group** 组合：SPEC 容器 `group: true` 时，同 owner 的形状
  `slide.Shapes.Range([...]).Group()` 组合，组命名 `{容器id}.group`。
- **ole 嵌入**：`diagram` 元素 `src=.vsdx` → `AddOLEObject(FileName=src, Link=0)`
  （Type=7 原生嵌入，双击进 Visio 编辑）；rect 按 EMU→英寸换算落位。
  OLE 失败 = 硬失败（退出码非 0）；glue/group 失败仅记 WARN。
- **png 预览**：`slide.Export(png, "PNG", slide宽英寸×100, 高×100)`。
- **pdf 导出**：`--pdf` 时 `pres.SaveAs(pdf, 32)`（32 = ppSaveAsPDF）在
  公式兜底后的最终 base.pptx 上执行（同一 PowerPoint 实例，先 PDF 后逐页
  PNG）。用 SaveAs 而非 ExportAsFixedFormat：后者在这类精简 Office 的类型库
  中参数被降成 Object（pywin32/PowerShell 均无法传参），SaveAs 的 (str, int)
  签名转换稳定。PDF 失败 = 硬失败（同 OLE）；无 Office 降级无产物。
- **公式兜底**（最后一步，PowerPoint 释放文件后才写 base.pptx）：只处理
  "parse 与离线模板都没覆盖"的 `formula` 积木（模板命中的渲染期已注入）
  → `word_batch_omml(exprs)` 一次 Word 进程吞 N 表达式（零剪贴板、产物走
  docx 解包）→ python-pptx 按名找到占位文本框注入 OMML。结果写
  `com_out.json.formulas: {pending, injected[], failed[]}`；失败项保留占位文本
  → WARN，不阻断（与 glue/group 同降级）；OLE 失败才是唯一硬失败。
- **字体嵌入请求**（B5）：`--embed-fonts`（或 `font.portable`）时置位
  `pres.EmbedTrueTypeFonts=True`，Save 后扫包 `ppt/fonts/*.fntdata` 核对。
  实测自动化保存路径不产嵌入字体 → `fonts.empty_reason="no_fntdata"` + WARN，
  不阻断（--com-strict 升级 exit 5）。详情见 references/ooxml-notes.md §15。
- **文本溢出真实回读**（B4）：逐页对带文本形状读 `TextFrame2.TextRange.BoundHeight`
  vs `TextFrame2.BoundHeight`，超 `com.overflow_tol_pt`（默认 1pt）→ `overflow`
  列表 + WARN。离线 textmesh 估算是第一来源，此处为 PowerPoint 实度第二来源。

## 母版版式模式（meta.template：extract 提炼 / seed 打底）

```bash
win_py scripts/build_ppt.py examples/template/extract.yaml --out out_extract --com
win_py scripts/build_ppt.py examples/template/seed.yaml    --out out_seed    --com
```

模板素材先收集风格卡：`win_py scripts/template_analyzer.py <模板.pptx>`
（详情：examples/template/README.md + 语法：spec-v2-language.md「meta.template」节）。

- **extract**：样式卡按 keys 注入（fill-only：SPEC 显式声明优先）后走常规管线；
  渲染后 `_inject_theme` 把 palette 的 accent1..6/dk1/lt1/dk2/lt2 写回输出
  theme1.xml clrScheme——新建形状/图表默认色/取色器即品牌色（物证「主题槽注入」背书）。
- **seed**：渲染器 `Presentation(src)` + 按名选版式 `add_slide`；`ph` 元素把
  文本填入模板占位符（样式/落点留模板）；模板自带示例页剥离（母版/版式保留），
  输出仅 SPEC 页；模板层几何豁免校验（物证「版式引用」+「ph 填充」背书）。
- 两模式都**零写入模板**；退出码/阶段/gate 契约与普通 SPEC 完全一致
  （模板页剥离属渲染期行为，无独立 stage）。

## 产物清单

- `base.pptx` —— 交付物（原生可编辑，无位图光栅痕迹）
- `base.pdf` —— `--pdf` 时产出的分发格式（最终态，含公式兜底）
- `ir.json` —— 布局中间表示（几何/锚点/z 唯一事实源，调试复现）
- `report.md/json` —— 校验报告（违规明细 + 通过清单）
- `com_out.json` + `preview.png` —— `--com` 或 `--pdf` 时产出

## 降级路径（无 Office）

`--no-com` 或 com_layer 缺失：产物 = base.pptx + report，exit 0。
glue 边以**坐标锚点直线**呈现（stage5 物证不查 stCxn，无绑定语义）——
spec 里 `relations.glue` 变成"静态连线"，agent 需在说明中标明非绑定。

## 测试入口

```bash
win_py tests/run_mutations.py        # 突变套件：52 项全部拦截 + 对照通过
win_py tests/regression.py           # examples 端到端（含 exit 2/3 负例）
win_py tests/run_template.py         # meta.template 契约：提取注入/打底/ph 负例/素材完整性
win_py tests/run_analyzer.py         # 风格卡分析器契约（无 Office）
win_py tests/com_office_check.py     # COM 自检（需 Office）：glue/group/ole/pdf
win_py scripts/build_formula_templates.py   # 重建离线公式模板库（需 Word）
```