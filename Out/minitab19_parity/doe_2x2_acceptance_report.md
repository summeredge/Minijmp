# 2² 两水平全因子首个自动对标

## 验收结果

**PASS**：两次独立 Minitab COM 会话与 MiniJMP 分析均已完成；比较 CSV 共 366 行，其中 356 项数值通过、10 项 N/A、0 项失败。N/A 是 Error/Total 行没有定义的 F/P 或 MS。

## 数据与方法

- 固定输入：`doe_2x2_replicated_input.csv`，8 个运行（2 个完整重复），A/B 编码为 −1/+1。响应由 `Y = 50 + 3A − 2B + 4AB + ε` 构成，重复误差为 −1/+1，确保 SSE 非零。
- MiniJMP 使用生产入口 `code/doe_analysis.py::analyze_factorial(order=2, ss_type='I')`；设计由 `code/doe_factorial.py::create_factorial` 建立，系数顺序为截距、A、B、A*B。
- Minitab 19.1.0.1 使用 COM `DispatchEx("Mtb.Application")`；先由 `FFDESIGN` 创建 2²、两次重复、编码水平 −1/+1 的 DOE，再运行原生 `FFACTORIAL`，模型项为 C5、C6、C5*C6。
- MiniJMP 与 COM worker 均由项目 `.venv` 的 Python 3.11.9 运行，COM 使用 `.venv` 中的 pywin32。
- MiniJMP 报 Type I 平方和。此完整平衡设计的模型列正交，A/B/AB 的 sequential 与 adjusted SS 相等。

## Minitab 精度来源

Minitab 原生 `FFACTORIAL` 的完整输出保存在 `doe_2x2_minitab_raw_run1.txt` 与 `doe_2x2_minitab_raw_run2.txt`。对比不从报表舍入值反推系数、矩阵或拟合值：系数来自 C10，模型矩阵来自 M1，拟合值/残差来自 C8/C9，均由 COM 直接回读。ANOVA SS 由这些机器精度的 Minitab 结果及固定输入重建；F/P 使用对应自由度，P 值由 `scipy.stats.f.sf` 计算，并与原生 Minitab 输出一并保留以便复核。

## 首次运行参考值

- 系数：截距=50，A=3，B=−2，AB=4。
- 模型矩阵：8×4，列为 `[1, A, B, AB]`，rank=4；残差 df=4。
- SSE=8，MSE=2，S=√2；SS(A)=72，SS(B)=32，SS(AB)=128，模型 SS=232，总 SS=240，R²=232/240。
- 单项 F：A=36、B=16、AB=64；精确 P 与逐运行拟合值见 `doe_2x2_comparison.csv`。
- ANOVA 数值源：Model `SS=232, F=38.6666666667, P=0.00206003854607`；Error `SS=8, df=4, MS=2`。

## 文件

- 固定输入：`doe_2x2_replicated_input.csv`
- 本机实际 Session Commands：`doe_2x2_session_commands.txt`
- Minitab 两次原始输出：`doe_2x2_minitab_raw_run1.txt`、`doe_2x2_minitab_raw_run2.txt`
- 精确 Minitab/MiniJMP JSON：`doe_2x2_minitab_results.json`、`doe_2x2_minijmp_results.json`
- 逐项误差与两次重跑一致性：`doe_2x2_comparison.csv`
- 运行日志：`doe_2x2_run.log`

范围仅是一个 2² 完整平衡连续因子案例；不代表其他 DOE 类型或全部统计输出的 parity。
