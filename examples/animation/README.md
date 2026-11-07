# examples/animation — 动画积木演示

一页 deck 摆 9 个元素，覆盖安逸动画库 4 族 8 个代表宏（首轮真实验证名单）：

| 元素 | 效应 | 家族 |
|---|---|---|
| title | 进入动画_自上浮入_改 | enter（顶部落入+淡入） |
| sub | 进入动画_快速淡入 | enter（打字机感） |
| card1 | 进入动画_快速淡入 | enter |
| card2 | 进入动画_安逸Q弹 | enter（弹性） |
| card3 | 进入动画_自下浮入_改 | enter |
| badge | 持续动画_呼吸效果 | persist（无限循环） |
| spin | 持续动画_无限陀螺旋_顺 | persist（无限循环） |
| glow | 强调动画_两次放大 | emphasize（Repeat=2+AutoReverse） |
| exitcard | 退出动画_自上浮出 | exit |

## 构建

```bash
# 无 Office：exit 0，动画缺 → WARN 降级（同 glue/group/ole 哲学）
win_py scripts/build_ppt.py examples/animation/chart.yaml --out out_anim
# 有 Office（COM 实时构造，动画写入 base.pptx 时间轴）：
win_py scripts/build_ppt.py examples/animation/chart.yaml --out out_anim --com --com-strict
```

`--com-strict` 下 com_out.json 的 `anim[]` 应 9/9 ok；`report.md` 无 G/T/D/S 违例。

## 说明

- **动画 = 时间轴语义，不是几何**：spec `animation` 字段只进 IR，渲染层/verify
  完全不消费（不参与 G/T/D/S 断言）；`--com` 时 com_layer 按配方实时构造
  `msoAnimEffectCustom` + 行为叠加（`#ppt_` 相对公式关键帧原文落 COM）。
- **预览为静态帧**：preview.png 是动画结束后的终态（多数宏可见；含 To=0 隐藏
  阶段的宏预览可能为空，需 Office 播放复核）。
- **无 Office 降级**：动画缺失 WARN，`--com-strict` 才阻断（exit 5）。
- 全部 **35 宏**配方在 `scripts/animation_recipes.py`（自检：`win_py
  scripts/animation_recipes.py`），语法见 `references/animation.md`。