# 量化设计规范（design norms）

本页是**人读版**量化规范；数值契约以 `params.py` 为唯一事实源：

- `params.verify.typography` — 逐页排版断言（S8）
- `params.verify.layout_variety` — 多页版式多样性断言（A1）
- `styleguides.QUANTITATIVE` — 推荐值可读副本（风格卡 / 设计 DNA 比对）

来源：ppt-studio 的量化设计经验 + 本项目 copyediting / styleguide 既有约束的内化。

## 字号分层

| 角色 | 推荐 | 说明 |
| --- | --- | --- |
| 封面主标题 | 54–96pt | 破格封面可更大 |
| 页标题 | 28–32pt | 大标题至 40pt；`title_fs_min` 默认关闭 |
| 正文 | 14–18pt | 本项 deck 规范下限 16pt（`styleguides.deck.body`） |
| 注释/单位/落款 | 8–14pt | 小字角色豁免正文下限 |

## 版面密度

| 指标 | 阈值 | 参数 |
| --- | --- | --- |
| 标题字数（CJK 计 1，纯西文 2 字符计 1） | ≤ 16 | `typography.max_title_cjk` |
| 单页正文 CJK 字数 | ≤ 220 | `typography.body_chars_max` |
| 单页 `[[强调]]` 处数 | ≤ 4 | `typography.max_emphasis` |
| 正文下限 | 默认关闭 | `typography.body_chars_min` |

标题过长 → 移入副标题或正文；正文过载 → 拆页或改图表/typst 排版块。

## 版式多样性（多页）

| 指标 | 默认 | 参数 |
| --- | --- | --- |
| 参与门槛 | 内容页 ≥ 5 | `layout_variety.min_pages` |
| 不同版式数 | ≥ max(3, ⌈页数×0.5⌉) | `min_distinct` / `distinct_ratio` |
| 同一版式最多页数 | 3 | `max_same` |

版式签名 = 非标题视觉主体的 (4×3 网格落位, 尺寸档 S/M/L, 类型/子类) 排序元组。
换文案、换配色**不会**改变签名——只有真正换版面骨架才行。页型意图页
（cover/section）不参与内容版式统计。

## 色彩与线条

| 指标 | 推荐 |
| --- | --- |
| 语义色数 | 每页 ≤ 6（`styleguides.*.color_max`） |
| 饱和填充面积 | ≤ 25%（`QUANTITATIVE.saturated_fill_ratio`） |
| 描边/连线 | 0.5–1.5pt，默认 1.0–1.5pt |
| 文字对比度 | ≥ 3.0（渲染层 `guard_text_color` 自动反色白/黑） |

## 图文配比

- 关键内容页至少 1 个视觉素材（chart / image / diagram / typst）。
- 纯文字页不超过连续 2 页；第 3 页起应引入视觉主体或改版式骨架。

## AI 感规避（反面清单；源 anthropics/skills pptx SKILL.md §Avoid）

官方 pptx skill 把「什么看起来像 AI 生成的」写成显式清单。`report.design_audit`
把其中可机器判定者做成 advisory 检查（**只对内容页报**；页型意图页的 deco/band
是审定破格点，按 owner 令牌豁免）：

| 痕迹 | 判定 | 参数 |
| --- | --- | --- |
| 标题下细横条 | 标题底 0.22" 内的细横条（高 ≤0.08"）——官方称"AI 生成式水印" | `verify.ai_tells.thin_h/title_gap` |
| 跨页宽装饰条 | 宽 ≥0.9 slide、高 ≤0.38" 且贴上下边的色条（头/脚条） | `full_w_ratio/bar_h_max/edge_band` |
| 卡片单边强调条 | 卡片一边贴边的细竖条（高 ≥0.25"、宽 ≤0.09"）——"单边描边" | `stripe_w_max/stripe_h_min/edge_gap` |
| 配色平分权重 | 全篇最大填充色占比 < 55%——违反"一主色 60–70%" | `verify.color_dominance.min_share` |
| 配色未定制 | 未声明 `meta.theme`——"换到别的 deck 仍成立即不够具体" | 声明 `meta.theme` 即消 |

正面原则（同时是审美判据）：**一个主色占 60–70% 视觉权重 + 1–2 辅色 + 1 锐利
点缀**；**挑一个标志性母题贯穿**（圆图标/图框，**而非色条**）；首尾页深底、
内容页浅底的"三明治"或全程深底。**替代装饰**：留白、底色微差、投影、图标。

## 配色多样性与三明治结构（正面杠杆；源官方 §Before Starting / §Color Palettes）

上节"AI 感规避"是反面清单；本节把官方设计半区的**四条正面杠杆**内化为
`meta.theme` 的显式开关（事实源 `scripts/themes.py`；机器背书 verify S8 +
`capabilities.THEME_CAPS`）：

| 杠杆 | 声明 | 效果 | 背书 |
| --- | --- | --- | --- |
| 配色多样性 | `meta.theme: {name: <预设>}` | 16 套命名预设含官方 **10 套跨色相**（珊瑚/森绿/藏蓝/炭灰/青/浆果/鼠尾草/樱桃…）——开篇铁律 **"Don't default to blue"** | 预设主色去重 ≥ 8（test_themes） |
| 三明治背景 | `meta.theme.structure: sandwich` | 封面/节页深底（主题 `deep` 色全幅背景）+ **浅字反色**；内容页浅底——官方 "Dark for title/conclusion, light for content" | S8 深页全幅背景 + 深页文字反色 |
| 全篇深底 | `meta.theme.structure: dark` | 全部页深底（须配 `mode: dark`，否则内容页文字不可见 → 编译期拒） | S8（同左） |
| 视觉母题 | `meta.theme.motif: circle_icon` | 每个图标加 accent 系圆形背衬（**全篇重复的特征元素**）——官方 "icons in colored circles" | S8 母题背衬圆（id 后缀 `_circ`、居中、z 衬底） |
| 衬线标题配对 | `meta.theme.font_pair: serif_sans` | 标题用衬线（Cambria）、正文无衬线（Calibri）——官方 §Typography "pair a safe-list serif header with a safe-list sans body" | test_themes（title_latin=Cambria） |

映射律：`primary`→主色；`secondary`→支撑色（描边 `panel_line`/`line` + 浅面板
`panel`）；`accent`/`emph` 逐套手定（浅色 accent 在白底不可用作强调 → 落回主色）。
三键缺省 `uniform`/`none`/`sans_sans` = 零行为变化（现有样例字节级不变）。
母题**不用色条**（官方明令"Do not use a color bar as your motif"）。完整示例
`examples/pageintent/theme_deep.yaml`（coral_energy + sandwich + circle_icon +
serif_sans 一页一杠杆）。

## 视觉丰度（advisory；源 _r_design-rules.md §密度目标 + 官方 §For Each Slide）

| 指标 | 阈值 | 参数 |
| --- | --- | --- |
| 视觉主体页占比 | ≥ 34% | `verify.abundance.visual_ratio_min` |
| 单页元素覆盖 cell 占比 | ≤ 85% | `verify.abundance.density_max`（栅格并集，容结构化版式） |
| 全篇字号档数 | ≥ 3 | `verify.abundance.type_span_min` |
| 元素留边 | 不触 0.5" 版心边 | `verify.abundance.margins_respected` |
| 设计一致性 | 有视觉主体的页 vs 纯文字页不应混杂 | 官方 §Avoid |

## 内容处理转换律（advisory；源 `_r_design-rules.md` + 官方 §For Each Slide）

`report.conversion_hints` 逐内容页扫描并提示素材该转成什么形态（**不产生 exit 码**）：

| 触发 | 目标形态 |
| --- | --- |
| ≥3 个数字并置 | 指标卡（kpis）/ 图表（chart） |
| A vs B / 对比 | 对照页（versus） |
| 有序步骤 / 阶段 | 技术路线页（route）/ 流程图（graph） |
| 同构字段重复（"字段：值" 密集） | 表格（table） |
| 长段落（>120 字） | 拆短句项目符号 |

## 与断言的关系

- 上表大部分值已在 params 的 `verify.typography` / `verify.layout_variety` 中生效；
  未开启的项（`body_chars_min`、`title_fs_min`）按需用 `meta.params` 或
  `--param` 打开，例如：

```text
win_py -X utf8 scripts/build_ppt.py spec.yaml --param verify.typography.title_fs_min=24
```

- 违规归因：排版规范与版式同质均为 **advisory**（信息取舍是语义裁定），
  不进入机械修订；`--fix` 时交 LLM/人工决策。
