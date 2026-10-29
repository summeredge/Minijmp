# DOE Phase 2 RSM 区间与诊断参考

`build_reference.py` 和 `verify.py` 均只使用 Python 标准库与 `Fraction`，不导入 MiniJMP，也不互相导入。它们独立构造 2 因子、完整二次模型的 3×3 coded grid；响应由已知系数和与模型列正交的误差组成。该设计无重复点但有 3 个残差自由度，用于核对区间使用残差 MSE 而不错误依赖 pure error。

参考覆盖：预测点的 `h0`、SE Fit、均值 CI、单次观测 PI；90%、95%、99% 的双侧与单侧界限；训练行杠杆、标准化残差、删除残差、外部学生化残差、Cook's D 和 DFITS。t 临界值固定为 df=3 的表值，以免 verifier 调用生产拟合代码或复用生产区间函数。`manifest.json` 固定参考文件 SHA-256。

RSM fixtures 中的数值 oracle 不使用生产 `TermModel` 或 `fit_rsm`。生产 CCD/BBD/custom 路径的接线另由 pytest 从各自真实设计构造验证。
