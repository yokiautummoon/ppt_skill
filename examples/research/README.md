# examples/research — 科研三件套页型（C1）

承接 page_intent 审定菜单（references/page-intents.md §8）：科研论文/汇报的三块
高频破格拼图。agent 只选意图 token，布局由引擎确定性展开（每原型 = 布局代码 +
verify 断言），rect 全由 ir_builder 解出（铁律 1）。

`sci.yaml` 是 3 页 deck，逐页演示一个原型：

| 页 | page_intent | 字段 | 引擎展开（保留 id） | 破格点 / S6 断言 |
|---|---|---|---|---|
| 1 | `problem` | `title`（必填）/`items`（可选 list）/`accent` | `prb_badge` `prb_title` `prb_items` | 标记块纵向贯穿（高 ≥ 版心×0.32）；主问题左对齐（非居中） |
| 2 | `versus` | `left_title`/`right_title`（必填）/`left_items`/`right_items`/`vs`/`accent` | `vsv_panel_l/r` `vsv_title_l/r` `vsv_body_l/r` `vsv_divider` `vsv_tag` | 双栏分色 + 等宽（均衡）+ 中缝分割线居中（对称） |
| 3 | `route` | `stages`（必填 list[str]，≥2）/`title`（可选）/`accent` | `rte_title` `rte_stage1..N` `rte_lnk1..N-1` | 阶段等距推进 + 阶段链横向铺满版心 |

## 用法

```bash
# 全链（零 Office：引擎展开 = 普通元素/线，渲染照常）
win_py -X utf8 scripts/build_ppt.py examples/research/sci.yaml --out out_sci

# 临时调参（如路线阶段条高）
win_py -X utf8 scripts/build_ppt.py examples/research/sci.yaml --out out_sci \
      --param page_intent.route.h=1.3
```

## 说明

- `problem.items` / `versus.left_items|right_items` 为字符串列表，引擎各合成一个
  多行文本块（编号 `1.` / 项目符号 `·`）；不声明则相应文本块不展开。
- 展开簇共用 owner 令牌（`versus`）：面板背景 + 前景文本同 owner → verify G4
  遮挡合法来源（与 cylinder 展开部件同机制），无需在 SPEC 里写 `relations.overlap`。
- 语法与扩展 recipe 见 references/page-intents.md；契约登记见
  references/component-contracts.md（problem/versus/route 三行）。
- 回归：`tests/regression.py` 的 `research-sci` 条目卡 63 条物证。
