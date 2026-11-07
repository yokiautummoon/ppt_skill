# 页型意图（page_intent）—— 破格版式：审定菜单 + 引擎展开

版面刻板的根因是**单页无状态**：引擎对每一页用同一种 "title + content" 结构、
同一种居中/等分默认，页与页之间没有"这页是什么"的语义，agent 也就无从表达
设计意图。页型意图（page_intent）是第一块地基：

> **agent 只从审定菜单里选一个意图 token（cover / section / content / data /
> compare / conclusion / quote）；引擎用确定性代码把意图展开成版式。**
> 意图的语义由引擎算法给出，**绝不是**喂给模型的排版 prose。

配套原则（防刻板双机关之一，另一件是展示原型库）：

> **每原型 = 布局代码 + verify 断言**。一个页型原型要进库，必须同时带上
> 引擎展开函数（`ir_builder._expand_<intent>`）与断言（`verify._s_page_intent`），
> 断言背书"破格"是真的、必需构件不缺失。没有断言的低能力模型启发式不在讨论内
> ——它会让下限守卫失效。

## 1. 页型谱系（审定菜单）

| intent | 版面心智 | 引擎责任 | 断言要点 |
|---|---|---|---|
| `cover` | 破格封面：非几何中心大标题 + 不对称强调条 + 右下落款 | `_expand_cover` 展开 cov_* 四件 | 破格度 ≥ break_ratio、必需构件 |
| `section` | 节标题页：超大节序号贯穿 + 节名层级 + 左右双锚 | `_expand_section` 展开 sec_* 四件 | 贯穿度 ≥ 版心 40%、num 字号 > title 字号 |
| `content` | 常规正文页：标题 + 内容区 | 现有默认布局 | title 在场、安全区 |
| `problem` | 科研问题页：纵贯标记块 + 左对齐主问题 | `_expand_problem` 展开 prb_* | 贯穿度 ≥ 版心×0.32、title 左对齐 |
| `versus` | 科研对照页：双栏分色 + 中缝对称 | `_expand_versus` 展开 vsv_* | 双栏等宽、中缝居中、分色 |
| `route` | 科研路线页：阶段链横向等距铺满 | `_expand_route` 展开 rte_* | 阶段数吻合、等步距、横向贯穿 |
| `data` | 数据页：图表优先、标题弱化 | 规划中 | 规划中 |
| `compare` | 对照页：双栏对置 + 分色 | 规划中 | 规划中 |
| `conclusion` | 收束页：结论句 + 行动项 | 规划中 | 规划中 |
| `quote` | 引语页：大字引言 + 出处 | 规划中 | 规划中 |

当前已落地原型：**cover**（`examples/pageintent/cover.yaml` 全链 27/27 物证）、
**section**（`examples/pageintent/section.yaml` 全链 25/25 物证），以及科研
三件套 **problem / versus / route**（`examples/research/sci.yaml` 3 页全链
63/63 物证，C1）。其余 4 个 intent 枚举与字段白名单已进编译期（未知枚举编译
即 exit 2），展开/断言未写 → 不可当作已可用，见"扩展新原型"。

**防刻板升级（§9 变体家族）**：cover 有 3 变体（left/band/split）、section 有
3 变体（num_left/num_giant/band）；同 intent 多页缺省轮换，`intent:变体` 即页面
签名 → intent 页纳入 A1 版式多样性门禁（不再豁免）。

## 2. 三处契约（编译 → 展开 → 断言）

一个意图从 SPEC 走到物证，经过三层，各管一段：

1. **编译层（spec_compile）**：`page_intent ∈ PAGE_INTENTS`；页型字段
   `cover:`/`section:`/… 只随对应 intent 出现（intent=content 却写 cover → exit 2）；
   字段进白名单（`cover:` 仅 title/subtitle/meta/accent）；`cover.title` 必填非空；
   `accent` 为 palette token 或 hex；页内用户元素 id 不得占用引擎保留
   `cov_*`（cover 的展开产物 id）。
2. **展开层（ir_builder）**：`_expand_cover` 在 build_ir 里按页展开，全部 rect
   在此定死（铁律 1：几何唯一真相源；渲染/COM 绝不重算）。页意图随元数据进 IR
   （`out["page_intent"]`），渲染与 verify 据此识别封面页。
3. **断言层（verify）**：`_s_page_intent` 按 intent 运行原型断言（cover：
   必需构件在场 + 破格度下限 + 可选件展开）；封面页豁免 content 必需 title
   （封面标题由引擎展开生成 cov_title，不是内容页的 title 元素）。

## 3. SPEC 语法

页型意图是**页级**声明（`slides[i]`），仅多页序列可用；顶层
`meta.page_intent` / 单页模式声明 → 编译错（意图是多页序列的版面语义）。

```yaml
palette:
  deep: "#1F2A44"
  acc:  "#2D6CDF"
meta:
  title: 2026 上半年报告
  style_guide: deck
  slide: {w: 13.333, h: 7.5}
  margin: {l: 0.5, t: 0.5, r: 0.5, b: 0.5}
  slides:
    - title: 封面
      page_intent: cover
      cover:
        title: 2026 上半年经营分析报告   # 必填 str —— 引擎据此生成大标题
        subtitle: 聚焦增长 · 控制风险      # 可选 str —— 引擎生成副题（强调色）
        meta: 财务部 · 2026-09-09         # 可选 str —— 右下落款
        accent: acc                       # 可选 —— palette token / hex；缺省全局强调色
      framework: {footer: {text: ""}}     # 封面常去页码；页级覆盖全局框架
    - title: 议程
      elements: [...]                     # 常规内容页（无 page_intent）
```

`cover:` 字段表：

| 键 | 必填 | 类型 | 语义 |
|---|---|---|---|
| `title` | ✓ | str | 封面大标题（引擎放大字左对齐） |
| `subtitle` | | str | 副题（accent 强调色） |
| `meta` | | str | 落款（右下角不对称锚点，正文色） |
| `accent` | | token/hex | 强调条与副题颜色；缺省 `params.style.accent` |

保留 id：`cov_title` / `cov_sub` / `cov_meta` / `cov_deco` 由引擎产出，
用户元素不得占用（编译期拦）。

## 4. cover 展开（IR 产物）

规则几何由 `params.page_intent.cover` 常量驱动（`scripts/params.py`，意即
每个原型 = 布局代码 + 断言，常量一并入库）：

| 常量 | 默认 | 含义 |
|---|---|---|
| `deco_w_ratio` | 0.16 | 强调条宽 = 版心 × 0.16 |
| `deco_h` | 0.14 | 强调条高（固定 inch） |
| `deco_y_ratio` | 0.315 | 强调条顶 = 页高 × 0.315 |
| `title_w_ratio` | 0.72 | 大标题宽 = 版心 × 0.72 |
| `title_y_ratio` | 0.36 | 大标题顶 = 页高 × 0.36 |
| `title_h` | 1.6 | 大标题高 |
| `sub_gap` | 0.12 | 副题距标题底 |
| `sub_w_ratio` | 0.55 | 副题宽 = 版心 × 0.55 |
| `meta_w_ratio` | 0.30 | 落款宽 = 版心 × 0.30 |
| `meta_h` | 0.4 | 落款高 |
| `break_ratio` | 0.10 | 破格度下限（见断言） |

元素排布（全部左对版心缘，刻意**不**几何居中）：

```
cov_deco  强调条   rect = (mx_l,  sh·0.315,  cw·0.16,  0.14)   垫底，accent 纯色
cov_title 大标题   rect = (mx_l,  sh·0.36,   cw·0.72,  1.6)    fs 36 加粗左对齐
cov_sub   副题     rect = (mx_l,  ty+0.12,   cw·0.55,  0.6)    fs 20 左对齐 accent 色
cov_meta  落款     rect = (sw-mx_r-cw·0.30, sh-mx_b-0.4, cw·0.30, 0.4)  右下落款
```

破格点：大标题水平中心 = 版心左缘 + cw·0.72/2 ≈ 0.5 + 4.44 = 4.94in，
而 slide 几何中心 = 6.67in——**故意错开**。偏移量 = 版心相对偏移，
`drift = |标题中心 − slide中心| / 版心宽`，默认展开 drift ≈ 0.14。

## 5. verify 断言（cover）

`_s_page_intent`（verify.py）对 `page_intent = cover` 的页运行：

1. **必需构件**：`cov_deco`、`cov_title` 必须在场（引擎产物是封面的
   必需构件，缺一件即 exit 3）。
2. **破格度下限**：`drift ≥ break_ratio − eps`。把 cov_title 水平中心对准
   slide 几何中心（破格度 → 0）即触发 —— 这是"破格封面"的反向断言：
   **断言不认严谨居中的封面**，防止未来某次改动把它"修正"回刻板态。
3. **可选件展开**：cover 声明了 `subtitle`/`meta` 就必须展开出
   `cov_sub`/`cov_meta`（声明了却不展开 = 引擎违约）。
4. **S3 豁免**：封面页 `components_required=[title]` 不适用（content 页才要求
   显式 title）；封面标题是引擎生成的 cov_title，不是 title 元素。

## 6. section 原型（破格节标题页）

多页 deck 的骨架是 **封面 → 节页 → 内容页**，节页是与封面同一族的第二块
高频破格拼图。语法（`slides[i]`）：

```yaml
- title: 节标题
  page_intent: section
  framework: {footer: {text: ""}}    # 节页常去页码
  section:
    num: "02"                        # 必填 str —— 引擎生成超大节序号
    title: 预算执行与偏差分析          # 必填 str —— 引擎生成节名
    accent: acc                      # 可选 —— palette token / hex；缺省全局强调色
```

字段 `num`/`title` 必填非空，`accent` 同 cover 语义；保留 id：
`sec_num` / `sec_title` / `sec_deco` / `sec_guide`（用户元素不得占用）。

展开（`ir_builder._expand_section`，几何由 `params.page_intent.section` 驱动）：

```
sec_deco  右缘强调条 rect = (sw-mr-deco_w, mt+ch·0.10, 0.10, ch·0.32)  accent
sec_num   大数字    rect = (ml, mt+ch·0.16, cw·0.30, ch·0.50)   fs 96 bold
sec_guide 引导线    rect = (ml, mt+ch·0.70, cw·0.24, 0.05)      accent
sec_title 节名      rect = (ml, mt+ch·0.77, cw·0.62, 1.1)       fs 40 bold
```

构图：左（大数字 + 引导线与节名）右（强调条）双锚不对称；破格点两条——
**贯穿度**（sec_num 高 = 版心 50%，远超普通标题行）与**字号层级**
（num 96 > title 40，数字是节页主导视觉）。fs 96 在编译层以内（engine
展开不经字面上限），普通文本 S1b 只查下限 ≥16，无上限约束——大数字可行。

断言（`verify._s_intent_section`）：

1. **必需构件**：`sec_deco`、`sec_num`、`sec_title` 在场。
2. **贯穿度下限**：`sec_num 高 ≥ 版心高 × num_h_min_ratio(0.40) − eps`。
   把数字块改矮成普通文本行即触发——反向断言，防止"破格"被修正回刻板标题。
3. **字号层级**：`sec_num fs > sec_title fs`。数字降为普通字号即触发。
4. **S3 豁免**：节页同封面，不要求内容页显式 title（`page_intent`
   非 content/None 即豁免 components_required）。

## 7. 科研三件套（problem / versus / route）

承接审定菜单的多页骨架（封面 → 节页 → 内容页 → 对照/路线），科研论文/汇报高频的
三块破格拼图。三者同 cover/section 同构（编译 → 展开 → 断言三层），展示页
`examples/research/sci.yaml`（3 页）。

### problem —— 问题页（纵贯标记 + 左对齐主问题）

```yaml
- title: 研究问题
  page_intent: problem
  problem:
    title: 大规模图上的稀疏化为何失效？   # 必填 str —— 主问题（引擎左对齐放大）
    items:                              # 可选 list[str] —— 编号问题清单
      - 稀疏度上界与收敛性的矛盾未被刻画
      - 现有方法假设图近似稠密
      - 偏差随深度放大而失控
    accent: acc                         # 可选 —— 标记块色；缺省全局强调色
```

保留 id：`prb_badge` / `prb_title` / `prb_items`。展开
（`ir_builder._expand_problem`，几何由 `params.page_intent.problem` 驱动）：

```
prb_badge  纵贯标记块 rect = (ml+0.12, mt+ch·0.06, badge_w, max(ch·0.40, ch·0.32)) accent，文字 "?"
prb_title  主问题      rect = (ml+badge_w+0.30, mt+ch·0.12, cw·0.78, 1.15) fs 30 align left
prb_items  编号清单    rect = (ml+badge_w+0.30, mt+ch·0.55, cw·0.92, 2.6) fs 17，各条 "1. …"
```

破格点：标记块**纵贯**（高 ≥ 版心×0.32，远超普通正文字号块）+ 主问题**左对齐**
（非居中——问题页刻意打破居中默认）。断言（`verify._s_intent_problem`）：
① 必需 `prb_badge`/`prb_title`；② 贯穿度 `prb_badge 高 ≥ 版心高 × badge_h_min_ratio(0.32)`；
③ 左对齐 `prb_title.align == "left"`；④ items 声明的行数 = 清单条目数。

### versus —— 对照页（双栏分色 + 中缝对称）

```yaml
- title: 方法对照
  page_intent: versus
  versus:
    left_title: 基线方法                  # 必填 str —— 左栏标题
    right_title: 本文方法                  # 必填 str —— 右栏标题
    left_items: ["稠密假设", "二次复杂度"]   # 可选 list[str] —— 各条 "· …"
    right_items: ["稀疏刻画", "近线性"]
    vs: VS                                # 可选 str —— 中缝标签；缺省 "VS"
    accent: acc                           # 可选 —— 中缝标签底色
```

保留 id：`vsv_panel_l/r` / `vsv_title_l/r` / `vsv_body_l/r` / `vsv_divider` / `vsv_tag`。
展开（`ir_builder._expand_versus`）：

```
两侧面板 fill_l = style.fill（深色）、fill_r = style.group_fill（浅色）—— 分色对立
vsv_panel_l/r  等宽半栏 rect = 各 (cw−gap)/2 宽，y = mt+ch·0.16，高 ch·0.70
vsv_title_l/r  栏顶标题 fs 22，vsv_body_l/r 栏内正文 fs 16（"· " 项目符号）
vsv_divider    中缝竖线 rect = (cx−divider_w/2, …) —— 恰在幻灯片水平中心
vsv_tag        中缝 VS 椭圆 rect 居中 cx，文字 vs
```

破格点：**双栏分色**（左右面板异色）+ **均衡**（双栏等宽，差 ≤ balance_tol）+
**对称**（中缝分割线居中 slide 中心，偏移 ≤ 版心×sym_tol_ratio）。**展开簇共用
owner 令牌 `versus`**：面板背景 + 前景文本 + 中缝同 owner → verify G4 遮挡
合法来源（同容器），SPEC 无需写 `relations.overlap`。断言（`verify._s_intent_versus`）：
① 必需四件（panel_l/r、title_l/r）；② 均衡 `|l.w − r.w| ≤ balance_tol(0.5)`；
③ 分色 `fill_l != fill_r`；④ 对称 `|divider 中心 − sw/2| ≤ cw×sym_tol_ratio(0.02)`。

### route —— 路线页（阶段链横向等距铺满）

```yaml
- title: 技术路线
  page_intent: route
  route:
    title: 三阶段研究路线                   # 可选 str —— 顶部标题
    stages: ["问题刻画", "算法设计", "实验验证", "理论分析"]  # 必填 list[str]，≥2
    accent: acc                            # 可选 —— 阶段块与箭头色
```

保留 id：`rte_title`（可变产物用前缀 `rte_`：`rte_stage1..N` / `rte_lnk1..N-1`，
编译期按前缀查冲突）。展开（`ir_builder._expand_route`）：

```
rte_title   顶部标题 rect = (ml, mt+ch·0.10, cw, 0.7) fs 26
rte_stageN  阶段六边形 等宽铺满版心：w = (cw − (N−1)·gap)/N，y = mt+ch·0.40，高 h
rte_lnkN-1  阶段间箭头线（arrow=True）连接相邻阶段中点
```

破格点：阶段链**横向铺满版心**（首块左缘 ≈ 版心左、末块右缘 ≈ 版心右）+
**等步距**（相邻阶段间距极差 ≤ even_tol）。断言（`verify._s_intent_route`）：
① 必需 `rte_stage{1..N}` 数 = `len(stages)` 且 ≥ count_min(2)；② 等步距
`max(gaps) − min(gaps) ≤ even_tol(0.4)`；③ 横向贯穿首尾贴版心边缘（±0.05）。

> 三原型均登记进 `references/component-contracts.md`（problem/versus/route 三行）
> 与 `scripts/capabilities.py::COMPONENT_CONTRACTS`（invariants = verify 源码子串）。

## 8. 扩展新原型（recipe）

新增一个页型（如 section）：五处改动 + 三处测试，缺一不可：

1. `spec_compile.py`：已收录 → 无需动枚举；补 `PAGE_INTENT_FIELDS["section"]`
   字段白名单（如 `{"num", "title", "accent"}`）。
2. `ir_builder.py`：写 `_expand_section(...)` 并在 build_ir 的 intent 分支接入；
   保留 id 集合 `PAGE_INTENT_EL_IDS` 加 `sec_*`。
3. `verify.py`：`_s_page_intent` 加 section 分支断言（必需构件 + 该原型的
   "破格"指标下限——每个原型都要有反向断言背书。
4. `params.py`：`page_intent["section"]` 常量段（布局代码 + 断言的数值源）。
5. `examples/pageintent/section.yaml`：展示页 + 全链物证。
6. 测试：`tests/run_mutations.py` pageintent 段补对照/编译负例/IR 负例；
   `tests/regression.py` 加全链条目。
7. 变体家族（§9）：`intents.FAMILIES[intent]` 列族序；`capabilities` 的
   `variants` 同步（漂移断言背书）；每变体在 `_expand_<intent>` 分支 +
   `_s_intent_<intent>` 分支断言；`params.page_intent[intent][<变体>]` 常量段。

参照 cover/section 的完整落地（原型 1/2 同构）：
`examples/pageintent/{cover,section}.yaml`（源码）→
`scripts/ir_builder.py::_expand_{cover,section}`（展开）→
`scripts/verify.py::_s_page_intent`（断言）→ `scripts/params.py::page_intent`
（常量）→ `tests/run_mutations.py` pageintent 段（10 编译负例 + 4 IR 负例）→
`tests/regression.py`（27/27 与 25/25 物证）。

## 9. 变体家族（Variant Families）—— 同 intent 不再逐页同貌

页型意图落地后暴露的残余刻板：**一个 intent 只有一种几何展开** → 同一 deck 里
3 个 section 页像素级相同，而当时 A1 版式多样性又把 intent 页豁免 → 引擎展开的
重复无人拦（门禁盲区）。变体家族是第一块补丁：**每个 intent 拥有一族审定变体**。

> **变体 = 同一 intent 的另一种审定几何展开**。一族 = 布局代码（分支）+
> verify 反向破格断言（每变体）。选型确定性、可复现：**SPEC 显式 `variant:`
> 优先；缺省按该 intent 在本 deck 内的出现次序在家族内轮换**（`intents.plan`）。
> **`intent:变体` 即页面签名** → intent 页以真实签名重新纳入重复门禁（不再豁免）。

### 家族表

| intent | 变体族（序） | 变体心智 |
|---|---|---|
| `cover` | `left` → `band` → `split` | left 中心偏离；band 横向色带贯穿；split 左纵贯色块 + 标题嵌块内（同 owner 合法叠放） |
| `section` | `num_left` → `num_giant` → `band` | num_left 大数字左上纵贯；num_giant 巨型序号贴右下（右缘对齐）；band 序号与节名同嵌横贯色带 |
| `problem` | `badge` | （单变体，预留扩展） |
| `versus` | `split` | （单变体，预留扩展） |
| `route` | `chain` | （单变体，预留扩展） |

事实源唯一：`scripts/intents.py::FAMILIES`；`capabilities.PAGE_INTENT_VARIANTS`
由其快照（test_deck_rules 漂移断言背书）。

### 选型规则（确定性）

```python
# scripts/intents.py
FAMILIES = {"cover": ("left","band","split"), "section": ("num_left","num_giant","band"), ...}
def plan(slides):        # deck 级：显式 variant 优先，否则同 intent 出现次序轮换
    ...
    n = seen.get(intent, 0)
    v = explicit or fam[n % len(fam)]
```

在 `build_ppt.build_pages` 里按页号注入 `meta[intent]["variant"]`（页仅透传，
不自己算）；`ir_builder._expand_<intent>` 用 `IN.resolve(intent, decl.get("variant"))`
取有效变体，写 IR 的 `page_intent_variant`。

### SPEC 用法

```yaml
- title: 封面
  page_intent: cover
  cover:
    title: 同一种意图，不同的脸
    accent: acc
    variant: split        # 显式锁定该页形态（可选；缺省轮换）
- title: 节一
  page_intent: section
  section: {num: "01", title: 大数字左上纵贯, accent: acc}   # 缺省 → 家族[0] num_left
- title: 节二
  page_intent: section
  section: {num: "02", title: 巨型序号贴右下, accent: acc}   # 第 2 次 → 家族[1] num_giant
- title: 节三
  page_intent: section
  section: {num: "03", title: 号名同嵌色带, accent: acc}     # 第 3 次 → 家族[2] band
```

未知变体（`variant: nope`）或跨 intent 误用（cover 写 `num_giant`）→ 编译期
exit 2（`spec_compile` 调 `intents.known` 校验）。

### 断言与门禁

- verify 按变体分支：cover 三变体各断言（`cover 横向贯穿` / `cover 纵向贯穿` +
  `cover 标题嵌色块` / `cover 破格度`），section 三变体各断言（`section 贯穿度` /
  `section 序号贴右` + `section 贯穿度` / `section 横向贯穿`），外加共享
  `页型 <intent> 变体` 成员判定与 `字号层级`。
- **门禁闭盲区**：`verify._layout_page_sig` 对 intent 页返回
  `(("intent", intent, 变体),)`；`report._layout_sig` 同。→ A1 版式多样性把
  intent 页计入（同 intent 同变体重复 = 千页一面，被判同质；轮换变体即换签名 → 放行）。

### 落地参照

`examples/pageintent/variants.yaml`（cover split + 三 section 自动轮换 + 内容对照，
全链 100/100 物证）；测试：`tests/test_deck_rules.py`（capabilities 对齐 /
plan 轮换 / 页型页纳入门禁）、`tests/run_mutations.py`（4 变体对照 + 4 反破格
负例 + 3 编译负例）。

## 10. 内容页结构生成五样板（引擎侧杠杆）

**动机**：变体家族解决了"页与页互为克隆"，但内容页仍可能退化成"标题 + 若干文本框"
——**没被设计过**。修法 = 把内容页的**结构生成**也交给引擎：agent 只声明意图 token
+ 结构化内容（items/cols/kpis/blocks…），网格/分栏/指标行/卡网格/图文并置由引擎
确定性展开（几何唯一源仍在 ir_builder）。这是"每页像被设计过"的引擎侧杠杆，
与设计语言层（`meta.theme`）、转换律（report advisory）三者合力。

五样板各 = 布局代码 + verify 断言 + 变体族（每族 ≥2 变体，缺省轮换）：

| intent | 用途 | 内容字段 | 变体族 | 保留前缀 |
| --- | --- | --- | --- | --- |
| `panels` | 面板网格（并行要点区） | `title, items[{head,body}], cols, accent, variant` | `even` / `hero_left` | `pnl_` |
| `columns` | 分栏正文（对照陈述） | `title, cols[{head,items[]}], bottom?, accent, variant` | `even` / `arrow` | `col_` |
| `kpis` | 指标卡行（关键数字） | `title, items[{value,label}], accent, variant` | `cards` / `row` / `rings` | `kpi_` |
| `cards` | 卡网格（+ 顶饰） | `title, items[{icon?,head,body}], cols, accent, variant` | `icon_top` / `number` / `icon_left` | `crd_` |
| `figure_text` | 图文并置 | `title, image?, caption?, blocks[], side?, accent, variant` | `right` / `left` | `fgt_` |

**SPEC 语法**（`slides[i].page_intent: panels` + 同页 `panels: {…}`）：

```yaml
- title: 三条并行要点
  page_intent: panels
  panels:
    title: 引擎按内容解版式
    cols: 3
    accent: acc           # palette token 或色值；面板头文字色
    items:
      - {head: 选题聚焦, body: 收敛到可验证的核心问题}
      - {head: 方法稳健, body: 双路径互证 + 独立重算断言}
      - {head: 证据完备, body: 逐页物证核对}
```

**展开产物（IR 保留 id）**：`pnl_title` + 逐面板 `pnl_panel{i}/pnl_head{i}/pnl_body{i}`；
`col_title/col_head{i}/col_body{i}`(+`col_bottom`/`col_arrow{i}`)；`kpi_title` +
`kpi_card{i}/kpi_val{i}/kpi_lab{i}`(+`kpi_badge{i}`)；`crd_title` +
`crd_card{i}/crd_head{i}/crd_body{i}`(+`crd_badge{i}`)；`fgt_title/fgt_fig/fgt_body`。

**verify 反破格断言**（每样板 4–6 条，堵"展开合法但版式退化"）：

- **panels**：`页型 panels 变体` + `必需 pnl_title/pnl_panel0` + `panels 网格贯穿`
  （网格跨 ≥ 版心×`grid_span_ratio_min`）+ `panels 面板等宽`（even）/ `panels 首板贯穿`
  （hero_left 首板宽 ≈ 版心宽）。
- **columns**：`必需 col_title/col_head0` + `columns 分栏等宽` + `columns 栏组贯穿` +
  `columns 箭头在场`（arrow 变体 `col_arrow*` ≥1）。
- **kpis**：`必需 kpi_title/kpi_card0` + `kpis 指标等宽` + `kpis 行贯穿` +
  `kpis 数值层级`（数值字号 ≥ 标签字号×`value_ratio_min`——尺度对比）。
- **cards**：`必需 crd_title/crd_card0` + `cards 顶饰在场`（`crd_badge*` ≥1）+
  `cards 网格贯穿` + `cards 卡片等宽`。
- **figure_text**：`必需 fgt_title/fgt_fig/fgt_body` + `figure_text 图文分栏`
  （左右 rect 不重叠）+ `figure_text 破格占比`（图侧宽 ≥ 版心×`fig_ratio_min`）。

**编译期 fail-closed**：未知字段（字段白名单 = caps `fields`）/ 未知变体（家族白名单）/
保留前缀冲突（页内额外元素 id 撞 `pnl_`/`col_`/`kpi_`/`crd_`/`fgt_`）→ exit 2。

**参数旋钮**：`params.page_intent.{panels,columns,kpis,cards,figure_text}` 逐样板几何
（页题 y/高/字号、网格 y/高比例、间隙、内距、正文字号 ≥16 下限、各 `*_ratio_min`
断言阈值）——配置栈可全局/页级/CLI 覆盖。

**落地参照**：`examples/layouts/{panels,columns,kpis,cards,figure_text}.yaml`
（各 2 页覆盖两变体，入 `tests/regression.py` CASES 跑出真值 evidence 计数）；
测试 `tests/run_mutations.py`（5 样板展开对照 + accent token 解析 + 7 编译负例 +
5 反破格负例）、`tests/test_deck_rules.py`（五样板家族对齐 + 轮换）。