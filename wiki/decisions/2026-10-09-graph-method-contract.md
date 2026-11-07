---
tags: [decision]
parent: root
status: done
updated: 2026-10-09
scope: 流程图多页重复/同质化根因定位 + 四层治理（A 编译期契约 / B 形态旋钮 / C 跨页去重 / D LLM 协议）
---

# 决策：流程图方法论契约（同质化治理 A/B/C/D）

## 背景

2026-10-09 用户反馈：流程图在多页 PPT 中重复、同质化，怀疑"没有按方法论和
对应描述物的逻辑排布"。根因定位（代码实证）：

1. **方法论不进生成链**：styleguides.flowchart 是纯校验契约（type_scale /
   color_max / spacing / connector，`components_required` 为空），verify S 家族
   后验消费，**不产形状、不排布**（scripts/styleguides.py:20-36、
   scripts/verify.py:477 `_s_family`）。
2. **形状语义 = SPEC 作者自由裁量**：spec_compile `_check_graph` 只做枚举白名单
   （kind ∈ src/proc/judge/end/note、edges 引用存在），无任何方法论语义约束；
   layout_graph.SHAPE_KIND 只做 kind→形状映射。LLM 生成线性 proc 链最省事 →
   页页同构。
3. **布局确定性同构**：layout_graph 横向布局对所有 graph 一刀切（BFS 分层 +
   同层同高 + 等宽 + 磁吸），无形态多样性参数。
4. **无跨页防线**：EasySlides 借鉴时 Anti-repetition 被 YAGNI 搁置（决策
   2026-10-08-easyslides-borrow.md），多页 deck 重复页无检测。

用户批准的推进顺序：A+D 先行（共享事实源）→ C 跟上（签名基座复用）→ B 殿后。

## 决策

### 统一事实源 = styleguides.flowchart.semantics + graph_sig

`RULE_SETS["flowchart"]["semantics"]`（`branch_min_nodes`=5 / `linear_escape` /
`guide` 生成指引原文）同时承载**机器约束 A**（spec_compile 消费）与**生成指引
D**（llm_fixer 作业注入）——单一事实源，测试卡 guide 子串在
references/flowchart-method.md 在场（两处写死即漂移）。**graph_sig.py** 签名
基座（特征 + 拓扑签名）由 A（linear_chain 判据）与 C（跨页去重）共用，不重复
实现。

### A：编译期分档分支契约（fail-closed）

style_guide=flowchart 且横向 graph：节点数 ≥ branch_min_nodes 却无分支表达
（无出度≥2 节点）= 全直线链（同质化主因）→ SpecCompileError exit 2。**分档
参数化防误伤**：真线性流程显式 `linear: true` 逃生（付款 4 节点等简单流程
< 阈值直接放行）；vertical（组织树）与非 flowchart 豁免。

### B：布局形态旋钮（第三波，最小实现）

`graph.variant: snake` 蛇形折返流（两行双向，长流程紧凑）；spec_validator
白名单 + spec_compile 枚举校验同步（物证从 IR 读几何，结构未变无需改）。

### C：跨页拓扑去重（第二波，复用签名基座）

verify `check_graph_dedup`（多页模式）：复杂图（≥ 阈值）拓扑签名跨页相同 →
`图重复 sig`（exit 3，attribution advisory：改拓扑或主题）。两级分级：简单图
（< 阈值）不参与（简单流程重复是合法用例，误杀用阈值化解）；`linear: true`
显式授权不判。签名与 id/文案无关——换文案同拓扑仍判重复。

### D：LLM 生成指引注入（第一波）

build_ppt 构造 llm_job 时把 `semantics.guide` 摘要拼进 `guide` 字段（
`方法论(<style_guide>): …`）——修订/生成流程图的 LLM 知道"流程不得全线性"，
从输入端治同质化。

## 取舍公开

- **A 不无条件禁线性**：分档 + 显式逃生，简单流程/时间线不误伤；
- **C 两级分级**：复杂图同构即拒收（拓扑相同、文案不同也算——多页上的
  视觉重复本质是拓扑重复），简单图重复放行；
- **B 只做 snake 一个旋钮**：多 sink 分群等留待后续（YAGNI，效果先靠 C 评估）；
- **`guide` 是短文案**：方法论细则靠 references 文档，guide 只是作业注入摘要。

## 落地验收（status: done）

- graph_sig.py（特征/拓扑签名/linear_chain/longest_path Kahn+DP）新建；
  styleguides.flowchart.semantics 契约表；spec_compile `_check_graph_semantics`
  （两调用点）+ variant 校验；spec_validator graph +linear/+variant；
  layout_graph `_layout_graph_snake`；verify `check_graph_dedup` + build_ppt 注入
  + attribution `_ADVISORY_SUB` +图重复；build_ppt llm job guide 方法论注入；
  references/flowchart-method.md（人读协议，guide 原文引用）。
- tests/test_graph_contract.py 24/24（特征/签名同构/A 阶正反例/escape/vertical/
  非 flowchart/C 去重分级/snake 两行方向/文档同步）。所有负例实测 exit 2/3，
  snake 全链 exit 0（物证 23/23）。
- 批量验证：run_mutations / regression / test_capabilities / test_routes /
  test_graph_contract 全绿，examples（flowchart/orgchart/closure）无回归。
- wiki：styleguides / spec_compile / verify / ir_builder / llm_fixer 模块页 +
  _index + _log 同步。
- 已知边界：pipeflow 线性链显式 linear 逃生；C 仅复杂图；B 仅 snake。