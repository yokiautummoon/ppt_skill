# 演示交付闭环总验收（closure）

`closure.yaml` 是**交付闭环**的端到端演示：一份可实际交付的 6 页战略发布会
演示，五件套（备注 / 切换 / 超链接 / 页码偏移 / PDF 导出）+ 常用图面积木
（表格 / 组织树 / 图表）全部在场。

```bash
# 完整交付链路：base.pptx（可编辑）+ base.pdf（分发）+ PNG 预览 + report.md
win_py -X utf8 -W ignore scripts/build_ppt.py examples/closure/closure.yaml \
    --out out_closure --pdf --report md
```

页面结构：

| 页 | 内容 | 覆盖能力 |
|---|---|---|
| 1 | 封面（无页脚） | 页级 footer 清空 · notes 开场词 |
| 2 | 目录 | 3 张超链接卡片（slide 跳转）· notes 演讲提示 |
| 3 | 战略里程碑 | 原生表格积木 |
| 4 | 组织保障 | 纵向组织树 graph + COM 组组合 |
| 5 | 增长目标 | 原生图表 + 指标文本 |
| 6 | 收尾 | email 超链接卡 · notes 收尾词 |

- **页码偏移**：全局 `params.framework.page_offset=-1` → 封面不计页码，
  正文显示「第 1 ·· 5 页」（物证逐页核对展开文本）。
- **页面切换**：全局 `meta.transition: {effect: fade, spd: slow}`。
- **全链验收**：stage3 verify 全过 → stage5 XML 物证 141/141 →
  COM（组组合 + PDF + PNG）warnings=0。
- **无 Office 降级**：去掉 `--pdf` 只产 base.pptx + report，exit 0。
- 验收脚本：`tests/com_office_check.py`（含 PDF 导出用例）与
  `tests/regression.py`（closure CASE 物证数 141）。