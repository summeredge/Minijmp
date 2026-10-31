# Mixture v2 固定72行联合案例：Minitab 19.1.0.1 数值对标

验收结论：PARTIAL

## 两条模型证据

- MIXREG 原生 DOE 对标：UNSUPPORTED：MIXREG 仅取得单总量24行子集，无法代表完整72行模型空间。
- REGRESS 等价模型对标：PASS：REGRESS 显式15列等价模型比较通过。
- SLDESIGN 设计对标：72行 UNSUPPORTED；T=150 的24行子集 PASS。

## 夹具期望与本轮 MiniJMP 生产 API 实得

|指标|独立夹具期望|本轮 API 实得|状态|
|---|---:|---:|---|
|行数 n|72|72|PASS|
|矩阵列数 p|15|15|PASS|
|矩阵秩|15|15|PASS|
|残差自由度|57|57|PASS|
|SSE|12|12.000000000008034|PASS|
|指定点预测|28|28.000000000000011|PASS|

- 本轮模型项：A, B, C, A*B, A*C, B*C, A*P1, B*P1, C*P1, A*P2, B*P2, C*P2, A*T, B*T, C*T。
- 独立冻结矩阵与 API 实算矩阵最大绝对误差：0。
- 本轮 API 系数：10.000000000000043, 19.999999999999996, 29.999999999999996, 1.9999999999999223, 2.9999999999999876, 4.0000000000000284, 0.99999999999999623, 2.0000000000000013, 2.9999999999999996, 4.0000000000000009, 5.0000000000000027, 6.0000000000000018, 7.0000000000000027, 8.0000000000000142, 9.0000000000000124。
- API 实算值与夹具期望分列保存在 mixture_v2_minijmp_results.json。

## Minitab 原生产品证据

- 版本：19.1.0.1；AppPath：D:\Program\Minitab 19\Mtb.exe；进程映像：D:\Program\Minitab 19\Mtb.exe；独立 PID：11716。
- DispatchEx 前已有 PID：[]；worker 退出后 PID：[]；独立进程已退出：True；原有 PID 保留：True。
- 另一次执行观察到既有 PID 34528 在 worker 结束后消失；没有连接该 PID 的 COM 对象，原因不明，见 mixture_v2_process_lifecycle_observation.md。
- 多总量 SLDESIGN command object：True；状态：UNSUPPORTED；单总量子集状态：PASS；子集行数：24；工作表列：标准序, 运行序, 点类型, 区组, A, B, C, X1, X2。
- TOTAL 100/150/200 常数形式与 TOTAL 列形式均返回“不能有多个含过程变量的混合合计”；单总量基础设计的实际组分总和映射为 T=150。
- MIXREG command object：True；错误标记：False；XMATRIX：24×12；秩：12；T=150 子集列空间最大投影误差：6.661338147750939e-16。
- MIXREG 无 AMOUNT 项表含 A/B/C、AB/AC/BC 与 A/B/C×X1/X2；24×12 秩12矩阵与 MiniJMP 的 T=150 子集同空间。
- MIXREG 预测存储：[]。
- MIXREG PROC+AMOUNT 首次尝试：False；错误：* 错误 * 子命令: 不允许将 AMOUNT 和已输入的主命令或子命令一起使用。。
- REGRESS command object：True；模型矩阵：72×15；秩：15；COM 输入列回读误差：0.0。
- 指定点预测的高精度系数点积为 28.000000000000011；直接 PREDICT/PFITS 未存储，Minitab 返回：* 错误 * 变元为常量或矩阵，但应为列。。

## 本机 Session Commands 手册核对

- SLDESIGN：印刷页 374–376；PROC、LEVELS、TOTAL、DESIGN。
- MIXREG：印刷页 377–381；PROC 指定过程列，AMOUNT 指定总量列且禁止将 AMOUNT 列列入项表；实际项矩阵以本轮 XMATRIX 为准。
- REGRESS：印刷页 170–178；NOCONSTANT、CONTINUOUS、TERMS、COEFFICIENTS、FITS、RESIDUALS、XMATRIX。
- 残差方向：手册印刷页 177 写作拟合值−观测值；本机 COM 的 REGRESS RESIDUALS 实存值与观测值−拟合值一致，比较按本机全精度读回。
- PREDICT：印刷页 1183–1186；尝试 multiple_regression|1、KPREDICTORS、PFITS。
- 手册文本：C:\Users\shaoy\AppData\Local\Temp\minitab19_session_commands.pdf.txt。

## 数值比较状态

- 容差：abs_tol=1e-9，rel_tol=1e-9。
- MiniJMP API / 独立夹具：PASS 22, FAIL 0, N/A 0, UNSUPPORTED 0；最大绝对误差：8.0344619846073329e-12，production_api/joint_v2/SSE。
- SLDESIGN 点集/设定：PASS 146, FAIL 0, N/A 0, UNSUPPORTED 1；最大绝对误差：0，single_total_subset/T=150/row_count。
- MIXREG 原生模型空间：PASS 4, FAIL 0, N/A 0, UNSUPPORTED 2；最大绝对误差：6.6613381477509392e-16，single_total_subset/T=150/max_abs_projector_error。
- REGRESS 等价模型：PASS 190, FAIL 0, N/A 17, UNSUPPORTED 1；最大绝对误差：2.2737367544323206e-13，anova_terms/A/partial_SS。
- CSV 逐项列出 PASS/FAIL/N/A/UNSUPPORTED、DIRECT/DERIVED/DISPLAY 来源和误差；Minitab 原始输出及高精度 COM 读回值分别保存在 raw log 与 JSON。

## ANOVA 与统计推断边界

- MiniJMP 实得 pure-error df=0，pure-error SSE=0；推断状态：纯误差不足或残差方差为零，统计推断不可用。
- 比较 CSV 含从 Minitab 全精度 REGRESS 矩阵和响应派生的居中 SST/SSR、MSE、R²、调整 R²、模型/误差自由度及逐项删除平方和；原生 REGRESS ANOVA 显示表保存在 raw log。
- MiniJMP 的 F/p 不可用时记为 N/A；Minitab 舍入显示值不作为唯一高精度证据。

## 证据文件

- verify_mixture_extended.py：单案例脚本。
- mixture_v2_joint_input.csv：72行固定因素/响应及15列生产 API 矩阵。
- mixture_v2_session_commands.txt：实际提交给 COM 的命令。
- mixture_v2_minitab_raw_output.txt：OutputDocument/Outputs、LastError、实际命令及原始记录。
- mixture_v2_minijmp_results.json、mixture_v2_minitab_results.json：双方全精度数据。
- mixture_v2_comparison.csv：逐项数值结果。
- mixture_v2_acceptance_report.md：本报告。

范围仅含本固定 Mixture v2 联合案例；未改生产代码、冻结八案例、DOE 矩阵或依赖；未运行全仓库 pytest。
