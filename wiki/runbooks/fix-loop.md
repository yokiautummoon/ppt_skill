---
tags: [runbook]
parent: root
updated: 2026-09-14
---

# Runbook：--fix 自优修订循环（含 LLM 作业模式）

决策：wiki/decisions/self-improve-loop.md（v2 定稿）。入口：`build_ppt.py
--fix`（含 `--llm` 语义通道）。本手册是 agent 的操作法：**何时用、怎么跑、
exit 6 协议如何回填、失败态如何处置**。

## 何时用

- 写 SPEC 后校验失败（exit 3 / report.md 记 G/T/D/S 违规）→ `--fix` 让确定性
  修订器收敛几何类问题（溢出/遮挡/字号档）——**不再手工 rect 微调**；
- content 违规（文本缺失/占位）、advisory（审美偏好）或机械未能收敛 → 加
  `--llm` 走**作业模式**：agent 自己带着 brief 上下文回填语义修订；
- 主链哲学：agent 在**动作库菜单**里做表现力决策，几何保底交给确定性默认值；
  稳定产出 = verify/物证每一次都证，internal 违规停机报 bug。

## 命令形态

```bash
# 纯机械修订（零 LLM，确定性快路径）
win_py -X utf8 scripts/build_ppt.py spec.yaml --fix [--max-fix 3] [--out DIR]

# 全通道（机械 + LLM 语义；content/advisory 违规时暂停等回填）
win_py -X utf8 scripts/build_ppt.py spec.yaml --fix --llm [--max-llm-fix 1]

# 回滚到最近确定性快照（fix.diff 留痕审计）
win_py -X utf8 scripts/build_ppt.py spec.yaml --revert [--diff FILE]
```

| 参数 | 语义 |
|---|---|
| `--fix` | 校验失败 → 修订循环（每轮快照 .snap.N + fix.diff 追写） |
| `--max-fix N` | 总循环轮默认 3；轮尽仍 FAIL → 回滚最近确定性快照 + 人工指引 |
| `--llm` | 启用 LLM 语义通道（作业模式） |
| `--max-llm-fix N` | LLM 修订轮默认 1（贵，收紧） |
| `--diff FILE` | fix.diff 路径（默认 `out_dir/fix.diff`） |
| `--revert` | 恢复最近 .snap.N（fix.diff 留给人工审计） |
| `--llm-client MOD` | 直连 API 预留位（当前走作业模式；fake client 回放已覆盖） |

## exit 6 稳态暂停 — 回填协议（LLM 作业模式核心）

`--fix --llm` 遇 content/advisory 违规且尚无 llm_out → **exit 6（非错误，
稳态暂停）**，已写 `llm_job.json` 并打印重跑命令。agent 操作法：

1. **读 job**：`out_dir/llm_job.json`——brief（全局+页级）、违规明细、
   候选菜单（`menu`）、notes/related_text、guide；
2. **决策**：每条违规从**菜单动作**里选（不自由发挥）；内容类（text/data）
   从 brief 生成值并写依据；
3. **回填** `out_dir/llm_out.json`：
   ```json
   {"version": 1, "revisions": [
     {"action": "从brief生成文本", "element": "t_body", "field": "text",
      "old": "", "new": "营收 120 亿 · 同比 +12%",
      "basis": "brief 引文：'营收 120 亿，同比 +12%，毛利率 34%'",
      "confidence": 0.85}], "audit": []}
   ```
4. **重跑同命令**（exit 6 打印的那条）→ 主循环读到 llm_out → 事务快照 →
   CHECK_OUT 护栏 → 应用 → 回环 verify → 收敛 exit 0；
5. 修订被拒（exit 3）：`llm_out.json` 有错（依据缺失/白名单外/元素幽灵/old
   不匹配）→ 修 llm_out 后重跑；spec 已回滚快照。

**数据红线**：data/categories/series 字段的新值必须溯源 brief 原文或标
`[占位]`——禁止编造数字；某些字段依据含 "brief"/"[占位]" 字样是 CHECK_OUT
放行条件，编造理由（如"好看一点"）将整批拒绝。

## 失败态处置

| 现象 | 含义 | 处置 |
|---|---|---|
| exit 4 | internal 违规（IR/渲染/断言算法不一致）| **停机报 bug**——不修 SPEC、不喂 LLM |
| exit 3 + "无机械动作命中" | 遗留违规无自动项 | 改 SPEC 重跑，或 `--llm` 走语义修订 |
| exit 3 + LLM 被拒 | llm_out 护栏/定位失败 | 修 llm_out 重跑（spec 已回滚 .snap.N） |
| exit 3 + 轮尽回滚 | 机械未收敛 | 读 fix.diff 审计 → 人工修订 → 重跑 |
| exit 1/2 | IO/编译/白名单 | 修 SPEC 结构，与 --fix 无关 |
| 收敛 exit 0 | 修订通过回环 | 继续 stage4-6 正常交付 |

## 审计与回滚

- `fix.diff` 行格式：`轮次|修订器|动作|字段路径|旧→新|理由|置信度|数据来源`
  （修订器 = spec 机械 / llm 语义）——每次修订留痕，人工复核依据与置信度；
- 每轮修订前整文件快照 `spec.yaml.snap.N`；失败/超限自动回滚到**最近确定性
  快照**；`--revert` 显式恢复最近快照。

## 关联

- 修订器：spec_fixer（R1–R4 机械）/ llm_fixer（语义+作业协议）/ revisioner
  （调度+事务应用+fix.diff）；归因：attribution；
- SPEC 语法：meta.brief 见 references/spec-v2-language.md「brief」节；
  验证套件：tests/run_fixer.py（端到端 5 例）+ test_{spec_fixer,revisioner,
  llm_fixer}.py（单测）。