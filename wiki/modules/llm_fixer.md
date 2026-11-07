---
tags: [module]
module: llm_fixer
parent: build_ppt
depends_on:
  - attribution
  - revisioner
updated: 2026-10-09
---

# llm_fixer — LLM 语义修订器 + 作业协议

`--fix` 修订链的**语义通道**（决策 self-improve-loop.md 部件④）：执行者 =
Claude agent 自身（**内化通道，不解耦黑盒**）——引擎把 agent 写出的 SPEC 的
content/advisory 违规反馈给它，让它带意图上下文（brief/notes/菜单）修订后重新
提交。与 spec_fixer 同接口；产物仍走 revisioner.apply_revisions 结构应用。

## 作业协议（与 com_layer 同构：llm_job / llm_out 文件通道）

1. build_ppt `--fix --llm` 遇 content/advisory 违规且 `llm_out.json` 不存在 →
   写 `llm_job.json` + **exit 6（稳态暂停，非错误）**，打印重跑命令；
2. 外层执行者（Claude agent）读 job、按菜单选动作/生成内容，回填
   `llm_out.json`（`{version, revisions[{action, element, field, old, new,
   basis, confidence}], audit}`）；
3. 重跑**同命令** → 读到 llm_out → 事务快照 → CHECK_OUT 护栏校验 → 应用 →
   回环 verify → 收敛 0 / 拒绝 3（回滚）。

```yaml
# llm_job.json（build_ppt 产出）关键键
version: 1
spec: <绝对路径>
brief: <meta.brief 全局+页级>
page: [{index, title}]
violations: [{family, name, element, peer, klass, action, detail}]
menu: {<违规名>: [动作...]}     # 动作库候选菜单（钳制）
context:
  notes: <备注>
  related_text: [...]
  constraints: [{rule, why, types}]   # 负面约束（Evolving Experience，通用项恒注入）
guide: <依据溯源/白名单说明>
```

## 护栏（CHECK_OUT 强制，一条非法 → 整批拒绝）

- 文本字段：new 可改，但 basis（依据）必须 = brief 引文 / 现有文本改写引用 /
  `[占位]`——禁止凭空编造；
- **数据字段（data/categories/series）：new 必须源于 brief 原文或标 `[占位]`，
  禁止自由编造数字**（数据正确性是红线；basis 含 "brief" 或 "[占位]" 才放行）；
- 动作/字段白名单（`_ACTION_ALLOW` / `_FIELD_ALLOW`——动作限菜单、字段限
  文本/数据/样式/几何）；元素必须 `_locate_global` 定位到（页+容器+索引，
  跨页同 id 取首处）；
- **定向补丁（LiveFigure 增量定向修改）**：CHECK_OUT 定位元素后取 `type`，
  `field` 首个段必须 ∈ `spec_validator.PER_TYPE[type]`（`_rev_field_ok`）——只碰
  目标元素真实存在的字段，杜绝把 `data` 塞给 `text`、把 rect 塞给 line 之外的
  分支等既往粗粒度盲区（编译期也会拦，但此处校验早于应用、出错信息更明确）；
- **负面约束注入（Evolving Experience 负例）**：build_job 把 `_CONSTRAINTS` 中
  `types=None` 的通用坑（rect 形态 / morph `mc:AlternateContent` / 数据红线）注入
  `context.constraints`，LLM 回填 llm_out 时受约束——负例来自工程沉淀，追加式
  演进不改 JOB_VERSION；类型专属约束（svg/icon/brush/typst 坑）由 `_rev_field_ok`
  在字段级承担差异化校验（无需 SPEC type 推断）；
- 每次修订记 理由 + 置信度（写入 fix.diff 审计）；回环强制：修订须过 verify
  才接受（build_ppt 主循环），限 `--max-llm-fix` 轮（默认 1，贵）。

## 接口

```python
build_job(spec_path, page, violations, brief, notes, related, menus, guide) -> dict
write_job(job, path) / read_out(path) -> (data, err)     # llm_job/llm_out
check_out(llm_out, spec_raw, brief, page_violations) -> (revisions, errors)
fake_out(revisions, version=1)                            # 测试回放辅助
```

- `--llm-client` 直连 API 可选（模块预留桥接位；当前走作业模式，fake client
  回放测试已覆盖 CHECK_OUT 语义；build_ppt 对 --llm-client 给提示不内置）。
- **方法论注入（D 协议）**：build_ppt 构造 job 时把 styleguides 契约表的
  `semantics.guide` 摘要拼进 `guide` 字段（`方法论(<style_guide>): …`）——LLM
  修订按 style_guide 方法论行事（如 flowchart 不得全线性），单一事实源不写死
  文案；流程图契约见 references/flowchart-method.md 与 styleguides.md。