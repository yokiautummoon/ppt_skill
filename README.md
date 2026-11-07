# PPT Builder — 确定性生成式 PowerPoint 幻灯片

用一份 **SPEC YAML** 生成原生可编辑的 `.pptx`。整条链路机器可证：编译校验 → 布局求解 → 断言 → 渲染 → XML 物证；不靠"看截图"保证质量，因此非常适合**无视觉能力的 AI agent** 使用。

作为 [Claude Code](https://claude.com/claude-code) skill 安装后，对 Claude 说"做一组 PPT / 画个流程图 / 搭个架构图 / 做个汇报 deck"即可触发。

- **声明式**：只写内容、关系与版式意图，坐标由布局引擎求解。
- **原生可编辑**：形状、表格、图表、公式、图标、SVG 都是 DrawingML 对象，不是整页位图。
- **可验证**：G/T/D/S 四家族断言 + 逐页 XML 物证；改 SPEC 重跑，绝不手改产物。
- **可自愈**：`--fix` 归因违规并执行确定性修订；语义问题走 LLM 作业模式（exit 6 暂停回填）。

---

## 目录

- [能做什么](#能做什么)
- [工作原理](#工作原理)
- [环境要求](#环境要求)
- [安装](#安装)
- [快速开始](#快速开始)
- [命令行](#命令行)
- [产物](#产物)
- [SPEC 速览](#spec-速览)
- [目录结构](#目录结构)
- [示例导航](#示例导航)
- [测试](#测试)
- [退出码](#退出码)
- [常见问题](#常见问题)
- [文档索引](#文档索引)
- [许可证与第三方资产](#许可证与第三方资产)

---

## 能做什么

| 能力 | 入口 | 说明 |
|---|---|---|
| 流程图 / 依赖图 / 组织树 | `type: graph` | nodes/edges/groups 自动分层、磁吸端口、回边、纵向树 |
| 递进 / 阶梯 / 金字塔 | `style_guide: ladder` + `stack` | 梯形积木自动堆叠 |
| 架构组成图 | `type: diagram` | 外部 PNG 落版；`.vsdx` 经 COM 原生 OLE 嵌入（双击可编辑） |
| 数据表 | `type: table` | 二维 data → 原生 `a:tbl` |
| 数据图表 | `type: chart` | column/bar/line/pie/area，原生 chartSpace，零 COM |
| 数学公式 | `type: formula` 或文本内 `{{…}}` | UnicodeMath → 原生 OMML；公式可**与文字同行**放进现有文本框 |
| 复杂排版 / 矢量示意 | `type: typst` | typst 全量排版 → SVG + PNG 双通道图块（需 typst CLI） |
| 精密矢量图 | `type: svg` | SVG → 原生 DrawingML `custGeom` 形状，可缩放、换色、逐形状动画 |
| 矢量图标 | `type: icon` | Lucide 1857 枚图标 → 原生 `custGeom` 描边形状 |
| 书法矢量字 | `type: brush` | 字体字形 → `custGeom`，实色/渐变/图片填充，换机不丢字形 |
| 方法/机理示意 | `shape.kind: cylinder` + `type: curve` | 复合圆柱、自由曲线、虚线分区框 |
| 设计语言 | `meta.theme` | 16 套命名主题（含 NNSFC 系与 10 套跨色相）；派生色彩角色、类型尺度、背景节奏、图标母题、字体配对 |
| 页型意图 | `slides[i].page_intent` | cover/section/problem/versus/route/panels/columns/kpis/cards/figure_text，引擎确定性展开版式 |
| 多页 deck | `meta.slides` | 每元素一页；页级 margin/framework/params 覆盖 |
| 交付五件套 | `notes` / `transition` / `link` / `page_offset` / `--pdf` | 备注、切换、超链接、页码偏移、PDF 分发 |
| 动画 | `animation` / 页级 `anim` | 35 宏动画库；声明式时间轴（串行/齐进/分组） |
| Morph 平滑切换 | `transition: {effect: morph}` | 跨页同名对象补间，`mc:AlternateContent` 兼容包 |
| 自优修订 | `--fix [--llm]` | 违规归因 → 机械修订/LLM 作业 → 快照与回滚 |

---

## 工作原理

```text
SPEC YAML
   │
   ├─ stage1  compile   语法/单位/引用/白名单校验        → exit 2
   ├─ stage2  layout    布局求解，产出 IR（唯一几何真相源）
   ├─ stage3  verify    G 几何 / T 文本 / D 容器 / S 规范  → exit 3
   ├─ stage4  render    IR → base.pptx                    → exit 4
   ├─ stage5  evidence  解包 XML 逐页物证                 → exit 4
   └─ stage6  com       可选 COM：glue/Group/OLE/动画/PDF/PNG → exit 5
```

三条关键约束：

1. **几何唯一源**：rect、锚点、z 只在 `ir_builder` 决定；渲染器与 COM 绝不重算。
2. **层级唯一源**：OOXML `spTree` 文档序即层级；渲染按 IR 的 z 稳定重排。
3. **遮挡只有两种合法来源**：同容器归属，或 `relations.overlap` 显式声明；其余 `exit 3`。

---

## 环境要求

- **Python 3.10+**（测试基线 3.10）
- **Windows 10/11**：COM 后处理、PDF 导出、`typst.exe` 依赖 Windows 侧环境
- **WSL 可用**：核心管线可跨平台，调用 Windows Python 与 Office 即可
- **Microsoft Office 2016+**（可选）：仅 `--com` / `--pdf` / 动画写入 / OLE 嵌入需要
- **typst CLI**（可选）：仅 `type: typst` 需要，放到 `scripts/typst-cli/typst.exe`

> 本文命令里的 `win_py` 指 **Windows 侧已安装依赖的 Python 解释器**。按你的环境替换为 `python`、`py -3` 或绝对路径，例如 `/mnt/c/.../python.exe`。

---

## 安装

### 1. 获取代码与依赖

```bash
git clone https://github.com/yokiautummoon/ppt_skill.git
cd ppt_skill
win_py -m pip install -r requirements.txt
```

### 2. 作为 Claude Code skill 安装

```bash
# 个人级（所有项目可用）
cp -r ppt_skill ~/.claude/skills/ppt-builder

# 或项目级（仅当前项目）
mkdir -p .claude/skills
cp -r ppt_skill .claude/skills/ppt-builder
```

安装后，`SKILL.md` 的 `description` 会在匹配"做 PPT / 流程图 / 架构图"等请求时触发。

### 3. 启用 typst 链路（可选）

仓库不附带 52MB 的 `typst.exe`。使用 `type: typst` 前，从 [typst releases](https://github.com/typst/typst/releases) 下载 Windows CLI，放到：

```text
scripts/typst-cli/typst.exe
```

未安装时，不含 typst 的 SPEC 不受影响；含 typst 的 SPEC 会在编译期明确报错。

### 4. 检查环境

```bash
win_py -X utf8 tests/run_mutations.py   # 不需要 Office
win_py -X utf8 tests/regression.py      # examples 全链，不需要 Office
```

---

## 快速开始

新建 `hello.yaml`：

```yaml
meta:
  title: 三分钟示例
  style_guide: deck
  slide: {w: 13.333, h: 7.5}
  margin: {l: 0.6, t: 0.6, r: 0.6, b: 0.6}
  theme: modern_light

palette:
  deep: '#1F2A44'
  accent: '#2D6CDF'

elements:
  - id: title
    type: text
    rect: [0.6, 0.65, 12.1, 0.8]
    text: "用 SPEC 生成 [[可编辑]] 幻灯片"
    text_style: {fs: 30, color: deep, bold: true, align: left}

  - id: flow
    type: graph
    rect: [1.0, 1.9, 11.3, 4.5]
    start: a
    nodes:
      - {id: a, text: "声明 SPEC", kind: src}
      - {id: b, text: "编译校验", kind: proc}
      - {id: c, text: "布局与断言", kind: proc}
      - {id: d, text: "渲染 + 物证", kind: end}
    edges:
      - {from: a, to: b}
      - {from: b, to: c}
      - {from: c, to: d}
```

运行：

```bash
win_py -X utf8 scripts/build_ppt.py hello.yaml --out out_hello
```

成功时输出 `exit 0`，并生成：

```text
out_hello/
├── base.pptx      # 可编辑产物
├── report.md      # 逐页校验清单
└── ir.json        # 布局中间表示（调试/复现）
```

需要预览图 / PDF / 动画时加 `--com`：

```bash
win_py -X utf8 scripts/build_ppt.py hello.yaml --out out_hello --com --pdf
```

---

## 命令行

```bash
win_py -X utf8 scripts/build_ppt.py <spec.yaml> [选项]
```

| 选项 | 作用 |
|---|---|
| `--out DIR` | 输出目录（默认与 SPEC 同目录） |
| `--com` | 启用 COM 后处理：glue/Group/OLE/动画/PNG 预览/公式兜底 |
| `--pdf` | 导出 `base.pdf`（隐含 `--com`，需 Office） |
| `--com-strict` | COM 失败改为阻断（`exit 5`）；默认仅 WARN |
| `--report md\|json\|none` | 校验报告格式（默认 `md`） |
| `--param KEY=VALUE` | 临时覆盖未显式声明的默认参数，可重复，last-wins |
| `--strict-images` | 图片缺失/占位即编译失败（`exit 2`） |
| `--embed-fonts` | 请求 Office 端嵌入字体（能力不足时 WARN 降级） |
| `--fix` | 校验失败后进入自优修订链（确定性快路径） |
| `--fix --llm` | 追加语义修订通道；需人工回填时 `exit 6` 稳态暂停 |
| `--max-fix N` / `--max-llm-fix N` | 修订轮数上限 |
| `--revert` | 回滚最近一次修订快照（`.snap.N`） |

示例：

```bash
# 完整设计编排示范（6 页零重复骨架）
win_py -X utf8 scripts/build_ppt.py examples/showcase/showcase.yaml --out out_showcase

# 交付闭环：备注/切换/超链接/页码/PDF
win_py -X utf8 scripts/build_ppt.py examples/closure/closure.yaml --out out_closure --pdf

# 公式放进标题文本框（行内 + 显示式）
win_py -X utf8 scripts/build_ppt.py examples/formula/inline.yaml --out out_formula

# 自优修订
win_py -X utf8 scripts/build_ppt.py my.yaml --fix
```

---

## 产物

| 文件 | 说明 |
|---|---|
| `base.pptx` | 主产物，原生可编辑 |
| `report.md` / `report.json` | 逐页校验报告（G/T/D/S 家族与违规详情） |
| `ir.json` | 布局 IR（单页 dict / 多页 list） |
| `preview.png` | `--com` 导出的逐页预览（agent 不读图，交用户目视） |
| `base.pdf` | `--pdf` 分发格式 |
| `com_out.json` | COM 后处理结果（glue/groups/ole/anim 等） |
| `img_prompts.md` | 占位图/缺图清单（id、目标尺寸、提示词） |
| `llm_job.json` / `llm_out.json` | `--fix --llm` 作业协议文件 |
| `fix.diff` / `.snap.N` | 修订审计与快照 |

---

## SPEC 速览

一个 SPEC 由四块组成：

```yaml
meta:        # 标题、style_guide、画布尺寸、边距、brief、params、theme、slides…
palette:     # 色彩 token（字面 hex / {solid} / 主题角色名）
elements:    # 平铺的元素声明（或放进 slides[i].elements）
relations:   # overlap / glue / links 等关系
```

### 常用元素

| 类型 | 关键字段 | 说明 |
|---|---|---|
| `shape` | `kind`, `rect`, `style`, `text` | 基本形状；`kind: cylinder` 复合圆柱 |
| `text` | `rect`, `text`, `text_style` | 文本块；支持富文本标记 |
| `stack` / `dock` | `direction`, `gap`, `children` | 自动布局容器 |
| `graph` | `nodes`, `edges`, `groups` | 自动流程图/树 |
| `table` | `data`, `header` | 原生表格 |
| `chart` | `chart_type`, `categories`, `series` | 原生图表 |
| `formula` | `expr`, `fs`, `color` | 独立公式块 |
| `typst` | `src` / `typst`, `rect` | typst 排版图块 |
| `svg` | `src` / `svg`, `rect` | SVG → 原生形状组 |
| `icon` | `icon`, `style` | Lucide 矢量图标 |
| `brush` | `text`, `font`, `style` | 书法矢量字 |
| `curve` | `points`, `style` | freeform 自由曲线 |
| `image` | `src` / `placeholder` | 图片或占位框 |
| `diagram` | `src` | PNG 落版 / VSDX OLE |

### 行内富文本

任意 `text`（含表格单元格、graph 节点与边标签）支持：

```yaml
text: "关键结论：**必须**强调 [[37%]]，公式 {{x^2+y^2=1}} 与文字同行。"
```

- `**加粗**`、`[[强调]]`（强调色默认 `#C00000`）
- `{{UnicodeMath}}`：与文字同行 → 行内 `m:oMath`；独占一行/一段 → 显示式 `m:oMathPara`
- 可嵌套 `**[[…]]**`，不可交叉/空标记/未闭合（编译期 `exit 2`）

### 多页与页型意图

```yaml
meta:
  slides:
    - title: 封面
      page_intent: cover
      cover: {title: "让每一页都有设计意图", subtitle: "声明 · 校验 · 物证"}
    - title: 内容
      page_intent: kpis
      kpis: {items: [{value: "37%", label: "效率提升"}, …]}
```

页型意图的版式由引擎展开并带断言，agent 不写坐标。完整字段见 [references/page-intents.md](references/page-intents.md)。

---

## 目录结构

```text
ppt_skill/
├── SKILL.md                 # Claude Code skill 入口（frontmatter + 工作流）
├── CLAUDE.md                # agent 项目引导：模块索引、关键概念、坑位
├── README.md
├── LICENSE
├── requirements.txt
├── .gitignore
│
├── scripts/                 # 管线与积木实现
│   ├── build_ppt.py         # 单入口 CLI（stage0–6）
│   ├── spec_compile.py      # SPEC 编译、单位/引用/富文本校验
│   ├── spec_validator.py    # 白名单静态校验
│   ├── ir_builder.py        # 布局求解 → IR（唯一几何源）
│   ├── verify.py            # G/T/D/S 断言
│   ├── render_pptx.py       # IR → pptx
│   ├── render_check_xml.py  # 逐页 XML 物证
│   ├── com_layer.py         # COM 后处理（Windows + Office）
│   ├── spec_fixer.py / revisioner.py / llm_fixer.py  # --fix 修订链
│   ├── typst_compile.py     # typst → SVG/PNG 图块
│   ├── svg_doc.py / icon_lib.py / ink_text.py        # SVG / 图标 / 书法字
│   ├── themes.py / intents.py                        # 设计语言 / 页型意图
│   ├── typst-cli/typst.exe  # 需自行下载（未入库）
│   └── …                    # 布局容器、动画、报告、参数栈等
│
├── references/              # 人读规范（按需加载）
│   ├── spec-v2-language.md  # SPEC 全语法
│   ├── pipeline.md          # 命令、gates、退出码、产物
│   ├── design-norms.md      # 量化设计规范与 AI 感规避
│   ├── page-intents.md      # 页型意图与变体家族
│   ├── formula-omml.md      # 公式：内联/显示/OMML 边界
│   ├── animation.md         # 35 宏与动画编排组
│   ├── svg-figures.md / icon-library.md / ink-brush.md / typst-chain.md
│   └── …
│
├── examples/                # 37 份可运行 SPEC，每目录含 README
│   ├── showcase/            # 设计编排活样板（6 页零重复骨架）
│   ├── pageintent/          # 封面/节页/主题/变体
│   ├── layouts/             # panels/columns/kpis/cards/figure_text
│   ├── research/            # 科研三件套 problem/versus/route
│   ├── formula/             # 独立公式 + 文本框内联公式
│   ├── chart/ table/ ladder/ orgchart/ deck/ closure/ …
│   └── animation/ ink/ icon/ svg/ typst/ method/ template/
│
├── tests/                   # 单元 / 契约 / 回归 / COM 自检
├── assets/                  # 内置资产
│   ├── icons/lucide.json    # Lucide 图标数据 + LICENSE
│   └── figures/radar.svg    # SVG 示例图
│
├── wiki/                    # 项目知识库：模块页 / 概念 / 决策 / runbook
└── _probe/                  # 测试夹具（仅 *.yaml 与 assets 入库）
```

> `examples/*/out/`、`examples/typst/typst_cache/`、`scripts/__pycache__/`、`_probe/` 下的生成物均已被 `.gitignore` 排除。

---

## 示例导航

| 想看什么 | 打开 |
|---|---|
| 一页一个骨架、如何做设计编排 | [examples/showcase/showcase.yaml](examples/showcase/showcase.yaml) |
| 封面 / 节标题 / 变体家族 | [examples/pageintent/](examples/pageintent/) |
| 内容页五样板（面板/分栏/指标/卡片/图文） | [examples/layouts/](examples/layouts/) |
| 科研三件套（问题/对照/路线） | [examples/research/sci.yaml](examples/research/sci.yaml) |
| 公式放进文本框、行内与显示式 | [examples/formula/inline.yaml](examples/formula/inline.yaml) |
| 原生图表样式全键 | [examples/chart/chart_style.yaml](examples/chart/chart_style.yaml) |
| 动画与声明式时间轴 | [examples/animation/](examples/animation/) |
| 书法字 + Morph | [examples/ink/ink.yaml](examples/ink/ink.yaml) |
| 矢量图标 / SVG / 相对坐标 | [examples/icon/](examples/icon/)、[examples/svg/](examples/svg/) |
| typst 复杂排版 | [examples/typst/](examples/typst/) |
| 完整交付闭环（五件套 + PDF） | [examples/closure/closure.yaml](examples/closure/closure.yaml) |

每个示例目录通常带一份 `README.md`，说明该示例演示的积木与预期产物。

---

## 测试

全部测试统一使用 Windows Python：

```bash
win_py -X utf8 tests/run_mutations.py   # 契约/突变套件（227 项，无需 Office）
win_py -X utf8 tests/regression.py      # examples 端到端回归（43 条，无需 Office）
win_py -X utf8 tests/render_guards.py   # 渲染默认规则（5 项）
win_py -X utf8 tests/test_deck_rules.py # 富文本/排版规范/版式多样性（60 项）
win_py -X utf8 tests/test_capabilities.py  # 能力档案漂移断言（154 项）
win_py -X utf8 tests/com_office_check.py   # COM 自检（需 Office）
```

其它专项测试见 `tests/`：SVG、typst、主题、动画组、参数栈、图片占位、字体、修订链等。

---

## 退出码

| 码 | 含义 | 处理 |
|---|---|---|
| `0` | 全链通过 | 交付 |
| `1` | IO / 内部错误 | 检查路径与依赖 |
| `2` | 编译 / 静态校验失败 | 按报错改 SPEC |
| `3` | 布局校验失败 | 看 `report.md`，改 SPEC 或 `--fix` |
| `4` | 渲染 / XML 物证失败 | 通常是引擎 bug；保留复现 SPEC |
| `5` | COM 失败（仅 `--com-strict`） | 检查 Office / 关闭驻留 POWERPNT.EXE |
| `6` | 需要 LLM 修订（稳态暂停，非错误） | 回填 `llm_out.json` 后重跑同命令 |

---

## 常见问题

**`win_py` 找不到？**
替换为你自己的 Windows Python，例如 `python`、`py -3` 或 `/mnt/c/.../python.exe`。

**本地 `python3` 报 `ModuleNotFoundError: yaml`？**
项目依赖已装在 Windows Python；请统一使用该解释器。

**PPT 打开报 `0x80070570`？**
多为 OOXML 结构违规。请确认产物由当前版本渲染器生成；不要手改 pptx/XML，改 SPEC 重跑。

**COM 报 `-2146959355` 或 Dispatch 失败？**
先关闭驻留的 `POWERPNT.EXE`（GUI 实例会阻断自动化）；代码内置重试但无法绕过人工打开的实例。

**`type: typst` 报找不到 typst？**
按[安装](#3-启用-typst-链路可选)把 `typst.exe` 放到 `scripts/typst-cli/`。

**可以只用 Python、不装 Office 吗？**
可以。除 `--com` / `--pdf` / 动画写入 / OLE / 真实溢出回读外，其余能力均不需要 Office。

**改了 `base.pptx` 后为什么校验不过？**
铁律：产物只读。所有修改回到 SPEC，重跑管线。

---

## 文档索引

- [SKILL.md](SKILL.md) — skill 工作流与完成判据（agent 入口）
- [references/spec-v2-language.md](references/spec-v2-language.md) — SPEC 全语法
- [references/pipeline.md](references/pipeline.md) — 管线契约与产物
- [references/design-norms.md](references/design-norms.md) — 量化设计规范
- [references/page-intents.md](references/page-intents.md) — 页型意图 / 变体家族
- [references/formula-omml.md](references/formula-omml.md) — 公式内联与 OMML 边界
- [references/agent-playbook.md](references/agent-playbook.md) — 绝对+自动混合策略、迭代闭环
- [wiki/_index.md](wiki/_index.md) — 项目知识库总索引
- [wiki/runbooks/fix-loop.md](wiki/runbooks/fix-loop.md) — `--fix` 自优修订手册

---

## 许可证与第三方资产

本项目以 [MIT License](LICENSE) 发布。

第三方资产：

- **Lucide 图标**（`assets/icons/`）：ISC License，见 `assets/icons/LUCIDE_LICENSE.txt`。
- **typst**（`scripts/typst-cli/typst.exe`，需自行下载）：Apache-2.0 / MIT 双许可。
- 书法字与文本渲染使用本机字体，字体的分发/嵌入需遵循各自许可。
