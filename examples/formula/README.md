# 示例 3：公式（formula 积木）

`formula.yaml` 演示数学公式支持的双路径：

1. **子集内 → 确定性 OMML 注入**（零 Office）：分式 `a/b`、上标 `x^2`、
   下标 `c_i`（嵌套 `a_i^2` 亦可）、根式 `√(a+b)`、希腊字符 `λ α β`、
   单字符变量（自动转 math italic Unicode）。PowerPoint 原生识别、可编辑。
2. **子集外 → Word 批量引擎兜底**（`--com` 时）：求和写 **Unicode 字符式**
   `∑_(i=1)^n x_i`，一次 Word 进程批量 BuildUp → 真 m:nary 大运算符
   （round-trip 保留）。不跑 `--com` = 可读占位文本（非原生公式）。

## 运行

```bash
# 无 Office 确定性链：子集内注入，∑ 以占位文本呈现
win_py scripts/build_ppt.py examples/formula/formula.yaml --out examples/formula/out

# 带 COM 兜底（需 Windows + PowerPoint）：∑ → Word 批量引擎 → 真 nary
win_py scripts/build_ppt.py examples/formula/formula.yaml --out examples/formula/out --com
```

## 校验背书

- XML 物证：注入型查 `m:oMath` + mc:AlternateContent 包装 + fallback 文本 == 表达式原文；
  占位型查文本框文本 == 表达式原文（判型 = 渲染器同源 parse_expr 重算）。
- `--com` 后 com_out.formulas.injected 含 f_sum（引擎注入成功）。
- 权威验证 = PowerPoint round-trip（打开 → SaveAs → 解包查 m:oMath 保留）。

## 写表达式守则（detail 见 references/formula-omml.md）

- ⚠️ 别写 LaTeX 花括号式 `\sum_{i=1}^{n}`——实测 Word 不当求和（\sum 当文本、
  花括号按下标），兜底也救不回来。
- `∫`（nary chr 缺省）、`|x|`、矩阵等未覆盖 → 占位/Word 兜底（报告中标注）。
  **模板库已收** `∏_(i=1)^n x_i` / `∏_(i=1)^n a_i`（chr=∏，免 --com 注入）。
- 空格是分隔符（隐式乘法），不生成符号。