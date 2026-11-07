---
tags: [decision]
parent: root
status: approved
updated: 2026-09-14
scope: 多轮迭代自优工作流（含 LLM 内化交互内容）
---

# 决策：多轮迭代自优工作流（--fix 循环）最终定稿

## 背景

现状：改动布局/文本/遮挡 → 人工跑 `build_ppt.py` → 看 `report.md` 的 G/T/D/S 违规
与 exit 3 暂停 → 人工改 SPEC → 重跑。同批违规（文本框溢出安全区、遮挡无合法源、
autofit 溢出）反复出现，人工迭代是纯机械劳动。

DSPy 调研（RESEARCH_DSPy启发调研.md）结论：本工程 verify/物证是"内置确定性 metric"，
DSPy 的 Refine/自举"失败反馈再尝试"循环范式可借鉴其**循环结构**，但本工程**走确定性
路径为主链**（可审计、同 SPEC 必同产物）。

本 skill 定位**全套 PPT 设计**：内容（text/data/categories/brief）本身也是 AI 辅助
意图生成的产出 → LLM 内化**可交互内容字段**（不限于排版）。

## 理念锚定（总纲，贯穿本方案的一切取舍）

ppt_skill 由 **Claude agent 操控**，产出目标是**提高 model 表现力 + 稳定产出**：

- **agent 是主导**：llm_job/llm_out 作业模式的执行者就是 Claude agent 自身——
  llm_fixer 不是外部黑盒，而是"agent 的第二次机会"：引擎把 agent 自己写出的
  SPEC 的违规反馈给它，让它带着意图上下文（brief/notes/菜单）修订后重新提交。
- **表现力来自意图与选择，不来自数值**：自优循环把 agent 从几何微调中解放——
  违规发生时 agent 不做手工 rect 微调，而是在动作库里做**表现力决策**
  （浓缩文本 / 换邻色 / 调间距 / 从 brief 生成），几何保底动作由确定性默认值
  兜住稳定下限；与 page_intent"审定菜单 + 引擎展开"哲学一以贯之。
- **稳定产出 = 铁律链不动**：verify/物证每一次都证；internal 违规停机报 bug；
  数据红线（brief 或 [占位]）防内容失真；无 LLM 时主链行为与现状完全一致。

## 决策（用户取舍 2026-09-13/14）

1. **确定性侧为主链**——主循环零 LLM 可跑；LLM 仅作修订器之一（内化，不单独立口）。
2. **机械修复边界：仅机械可推导类**（几何溢出/autofit 降号/遮挡补声明/z 显式化）。
3. **LLM 通道：内化在迭代工作流；可交互内容字段**；无 LLM 时降级人工指引不降质。
4. **原型检索（scaffold）与编译缓存：后置**（原型库扩充 / 大 deck 场景出现再做）。
5. **数据字段边界：源于 brief 或 [占位]**——LLM 可改 chart/table 数据，但必须
   直接引用 brief 原文数据或标 `[占位]`；**禁止自由编造数字**（数据正确性是红线）。
6. **暂停协议：稳态 exit 6**——遇 LLM 需求写 `llm_job.json` 后退出 6（非错误），
   外层执行者处理回填 `llm_out.json` 后重跑同命令继续循环；与 exit 契约及
   com_layer 子进程 JSON 作业模式一致。

## 目标

```
build_ppt(spec, brief?)  [--fix --llm ...]
  → exit2/3/4 失败（非 IO）→ 收集结构化违规(V)
  → 归因分类器（internal / fixable / advisory）
  → 修订链：
       动作库默认动作（=无 LLM 时的机械规则 R1–R4）命中 → 确定性修订，零成本快路径
       未命中/多解 → 候选菜单（同动作库）→ LLM 语义修订器按 brief 选动作/生成内容
       （无 LLM → 人工指引）
  → 重跑（轮数 +1，至 --max-fix / --max-llm-fix）
  → 收敛：exit 0；或轮数用尽 → 回滚到最近确定性快照 → report + fix.diff
  → 需 LLM 且未启用/未回填 → 写 llm_job.json + exit 6（打印重跑命令）
```

## 部件①：意图上下文 `meta.brief`

- SPEC 新增 `meta.brief`：用户原始需求（自然语言，默认空）。多页全局打底，
  页级 `slides[i].brief` 补充；编译白名单 + spec_validator 同步（exit 2）。
- LLM 修订注入上下文 = `brief + 页 title/notes + 违规明细 + 候选菜单 +
  SPEC 相关片段 + 修复指南`。
- 缺 brief 降级：仅从 title/notes/现文本推断（弱语义），或转人工指引。

## 部件②：多解决策——分层修订链 + 修复动作库统一

**修复动作库统一（核心）**：机械修复与 LLM 菜单共用**同一动作库**
`actions = {降号, 扩框, 移元素, 浓缩文本, 补overlap, 缩A, 移B, 调间距,
换白名单邻色token, 从brief生成文本, 引用现有文本, 移除(若装饰), 人工}`。

- 无 LLM：机械规则 R1–R4 = **动作库默认动作**（保守项）→ 确定性执行；
- 有 LLM：LLM 从**同一动作集**按 brief 选（候选菜单钳制，与 page_intent
  "审定菜单"哲学同构——菜单确定性 → 修订可预期、可重放、可审计）；
- 内容字段（text/data）无菜单 → LLM 生成值，须带依据（部件④护栏）。

| 机械规则 | 触发（family） | 默认动作 |
|---|---|---|
| R1 | T 文本 autofit 溢出 | 逐级降号到 min_fs；仍溢 → 安全区内扩框 |
| R2 | G 几何溢出安全区 | margin 内收缩/平移（保宽高比与相对位） |
| R3 | D/S 遮挡无合法源 | 保守补 `relations.overlap` 声明 |
| R4 | S z 冲突（物证再报） | 按声明序补 `z_override` 显式化 |

## 部件③：一致性归因分类器（scripts/attribution.py）

独立纯函数模块（可单测），输入 verify/物证违规，输出三类：
- `internal`（**停机 exit 4 + bug 指引，不修 SPEC 不喂 LLM**）：断行重算一致、
  锚点独立重算一致、节点同高、组包络 ⊇ 成员、stack/dock 账目——此类违反表明
  IR/渲染/断言算法不一致，修 SPEC 会掩盖 bug；
- `fixable`：溢出安全区 / autofit 溢出 / 遮挡无合法源 / 字号越档 / 配色越界 /
  内容缺失 → 进修订链；
- `advisory`：破格度 / 贯穿度 / 语义色数等审美偏好 → 默认留人工，LLM 高权限可调。

## 部件④：LLM 语义修订器（scripts/llm_fixer.py）+ 作业协议

**修订器抽象**：`spec_fixer.py`（确定性 R1–R4）与 `llm_fixer.py`（语义）同接口：
`input(SPEC, violations, context) → output(revisions, audit)`。

**作业协议（与 com_layer 同构）**：
- `llm_job.json`（build_ppt 产出）：`{version, spec 路径, brief, page{index,title},
  violations[{family,name,element,field,expect,current,fixable}],
  menu{<违规>:[动作...]}, context{notes,related_text}, guide}`；
- `llm_out.json`（执行者回填）：`{version, revisions[{action, field 路径,
  old, new, basis(依据), confidence, note}], audit}`；
- 重跑 `--fix` 时读到 llm_out → 事务快照后应用修订 → 回环 verify；
- `--llm-client` 直连 API 可选（测试用 fake client 回放）。

**护栏**：
- 文本字段：LLM 可改，依据 = brief 引文 / 现有文本改写 / `[占位]`；
- **数据字段（chart/table data/categories）：源于 brief 或 `[占位]`，禁止编造**；
- 每次修订记 `理由 + 置信度`；fix.diff 行格式：
  `轮次|修订器|动作|字段路径|旧→新|理由|置信度|数据来源`；
- **事务性**：修订前快照整文件 `.snap.N`；回环失败/超限 → 回滚到最近确定性快照；
- 回环强制：LLM 修订须过 verify 才接受，限 `--max-llm-fix` 轮。

## 组件与改动汇总

| 部件 | 落点 | 类型 |
|---|---|---|
| ① brief | `spec_compile.py` + `spec_validator.py` + SPEC 语法表 | 改 |
| ② 动作库/修订链 | `scripts/revisioner.py`（调度 + 候选菜单枚举 + 默认动作） | 新 |
| ③ 归因分类器 | `scripts/attribution.py` | 新 |
| ④ llm_fixer + 作业协议 | `scripts/llm_fixer.py` + llm_job/llm_out schema | 新 |
| spec_fixer | `scripts/spec_fixer.py`（R1–R4 实现 = 动作默认项） | 新 |
| 驱动 | `build_ppt.py`：`--fix/--max-fix/--llm/--max-llm-fix/--llm-client/--diff/--revert` | 改 |
| 结构化违规 | `verify.py` + `render_check_xml.py`：元素 id/字段路径/期望/当前/`fixable` | 改 |
| exit 契约 | exit 6 = pending-llm（稳态暂停） | 改 |

**参数语义**：`--max-fix` 总循环轮默认 3；`--max-llm-fix` LLM 轮默认 1（贵，收紧）；
每轮全量重跑（缓存后置，现状秒级可接受）；`--revert` 从 fix.diff 回滚。

## 风险控制

- 只改 SPEC；fix.diff 统一审计 + `--diff/--revert`；动作库白名单；
- internal 违规 → 停机报 bug，不修 SPEC；
- 数据禁止编造（brief 或占位）；内容修订人工复核留痕（依据/置信度）；
- 收敛保证：轮数用尽即停 + 事务回滚 + 人工指引；
- 无 LLM / 无 brief：行为与现状一致（纯机械 + 人工指引）。

## 测试

- `tests/run_fixer.py`：
  - 机械突变：溢出/遮挡/z/字号档 预置违规 → `--fix` exit 0 或明确失败+指引；
  - LLM 修订四场景（fake client 回放）：通过回环 / 失败再修 / 超限回滚+指引 /
    **数据依据缺失 → 拒绝**；
  - attribution 单测：internal 判定不误伤 fixable；
- 回归保障：`tests/regression.py` 不回归；修订器机械侧纯函数单测（同输入必同输出）。

## 实施步骤（依赖序）

1. `meta.brief` 字段 + 编译白名单/validator
2. verify/物证违规结构化 + `fixable` 标签 + `attribution.py`（base）
3. `spec_fixer.py` R1–R4（=动作默认项）+ fix.diff
4. `revisioner.py` 修订链调度 + 动作库/候选菜单（核心）
5. `llm_fixer.py` + llm_job/llm_out 作业协议 + exit 6 暂停 + fake client
6. `build_ppt.py` 参数/exit 契约/`--diff/--revert` 集成
7. `tests/run_fixer.py` + 回归
8. 文档：wiki/modules/spec_fixer.md + revisioner.md + llm_fixer.md +
   runbook + CLAUDE.md（使用法与 exit 6 协议）

## 优劣总览（定稿依据）

- 优：覆盖非机械类三大缺口（内容缺失 LLM 生成 / 多解 LLM 按 brief 从动作库选 /
  advisory 偏好 LLM 调参）；动作库统一双路径不漂移；菜单钳制保可预期可审计可重放；
  作业模式与 com_layer 同构、Claude Code 即执行者（exit 6 稳态可介入）；无 LLM 主
  链不回归。
- 劣/成本：LLM 非确定性与延迟（动作选择 + 内容生成两处）+ LLM 客户端运维；内容/
  数据生成需人工复核留痕；回环 + 事务回滚 + exit 6 协议实现复杂度；双路径测试矩阵；
  约 800–1200 行 + 测试。