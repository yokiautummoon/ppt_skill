---
tags: [module]
module: omml_engine
depends_on:
  - com_layer
updated: 2026-09-10
---

# omml_engine — Word 批量引擎

子集外公式 → Word COM 批量转 OMML（word_batch_omml）→ python-pptx 注入替换占位。注意反向依赖：omml_engine 复用 com_layer.dispatch_retry（Dispatch 瞬态启动重试，-2146959355 等）——两模块互为延迟 import，无循环加载问题。