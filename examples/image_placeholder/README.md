# 示例：图片占位（B3）

`placeholder.yaml` 演示 image 元素的占位用法——**缺图不静默**：

| 写法 | 语义 |
|---|---|
| `placeholder: "<提示词>"` | 无 src，字符串即生成提示词（也进清单与占位框） |
| `placeholder: true` + `caption` | caption 作提示词/占位框文案 |
| `src` 指向的文件缺失 | 降级为占位框，清单记「期望路径（当前缺失）」 |

缺省行为：占位框 = 虚线圆角矩形 + 居中提示文案（几何直接取 IR rect，铁律 1），
并写 `out_dir/img_prompts.md`：逐条列出元素 id / 目标尺寸（in 与 96dpi 像素）/
提示词 / 期望路径。

`--strict-images`：占位或缺图即编译错（exit 2）——交付前"图必须齐"的闸门。

```bash
win_py -X utf8 scripts/build_ppt.py examples/image_placeholder/placeholder.yaml --out out
cat out/img_prompts.md
win_py -X utf8 scripts/build_ppt.py examples/image_placeholder/placeholder.yaml --out out --strict-images  # exit 2
```

物证：占位框按 name=id 的 sp 核对（`占位框 {id}` ∈ stage5 证据链）。
回归：`tests/regression.py` 收录本示例（物证 12 条）；契约测试
`win_py -X utf8 tests/test_images.py`（25 项）。
