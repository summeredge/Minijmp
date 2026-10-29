# DOE Phase 2 二元概率与优化独立参考

本目录只提供数值 fixture，不导入 MiniJMP 的 `code/` 模块。`build_reference.py` 生成数据，`verify.py` 不导入生成器，而从 fixture 输入独立复算并检查 `reference.json` 字节数及 SHA-256。

## 手算 Logit / Wald

`manual.rsm_linear` 固定一阶三因子模型的系数顺序 `[截距, A, B, C]`，参数为 `beta`、`covariance`、`x0=[1, 0.5, -0.25, 0.125]`。协方差矩阵为正定矩阵。复算公式为 `eta=x0 @ beta`、`p=expit(eta)`、`Var(eta)=x0 @ covariance @ x0.T`、`SE(eta)=sqrt(Var(eta))`、`Delta SE(p)=p(1-p)SE(eta)`。

90%、95%、99% 双侧区间先在 eta 尺度取 `eta ± z(1-alpha/2) SE(eta)`，再逐端点应用 expit；单侧下限和上限分别用 `z(confidence)`，概率区间按 `[L,1]` 与 `[0,U]` 定义。因此概率尺度区间通常不对称，且端点在 (0,1)。同一结构还含负 eta、接近 0/1 的拟合概率；`manual.logit_representatives` 另固定 eta=−7、0、7，覆盖接近 0、0.5、接近 1 的概率。

这些 Wald 值是手工指定参数的数学参考，不是对某个生产模型的拟合结果。

## 实测 grouped-binomial GLM

`grouped_glm.design/events/trials/expected` 使用 statsmodels Star98 的 303 条学区实测分组计数：`NABOVE` 为事件数，`NBELOW` 为非事件数。设计矩阵为 `[1, LOWINC/10, PTRATIO/10, AVYRSEXP/10]`，按 statsmodels Binomial GLM 拟合（`maxiter=200`、`tol=1e-10`）；冻结系数、非稳健协方差和拟合概率。数据来源及响应定义见 [statsmodels Star98 文档](https://www.statsmodels.org/stable/datasets/generated/star98.html)。

生成器从当前 statsmodels 安装的数据资源加载 Star98；数据文件不随 fixture 再复制一份。核验器只读取 JSON 中的设计和计数，用 Newton scoring 解 grouped-binomial 对数似然，并由终点观察信息矩阵求协方差，再重算概率。Wald z 分位数由 Python 标准库 `statistics.NormalDist` 独立计算。因此运行核验器不需要下载数据集或导入 statsmodels/SciPy。

## 单因子 Logit optimizer

解析例严格限定 `eta(x)=0.2+x−x²`、`x∈[-1,1]`。极值候选包含两个端点与导数零点；p=0.57 的目标根由 logit 变换后的二次方程求解。Desirability 示例使用 `lower=0.4`、`upper=0.6`，定义 `D=(clip((p-lower)/(upper-lower),0,1))^weight`，同一示例点分别计算 weight=0.5、1、2，并解析给出 `D=1` 的平台区间。

本例解析值可以作为生产数值优化器的检查 oracle。它不把启发式 solver 的某个候选结果称为全局最优证明，也不覆盖其他目标函数、多个因子或约束。

同一 optimizer oracle 还固定 Maximize/Minimize/Target 的 desirability 分段样例，包括 Target 的低侧、高侧和界外响应；verifier 独立复算 `weight=2` 的结果。

## 版本与复现

冻结文件由 Python 3.11.9、statsmodels 0.15.0、NumPy 2.4.6、SciPy 1.15.3 生成。Star98 数据资源、GLM 实现及浮点舍入可能随库版本变化；跨版本重新生成不保证逐字节相同。`verify.py` 用独立 Newton/信息矩阵计算，对 GLM 数值采用浮点容差；manifest 的 SHA-256 则要求当前 `reference.json` 字节完全匹配。

```powershell
$python = 'C:\Users\shaoy\Documents\Minijmp\.venv\Scripts\python.exe'
& $python tests/fixtures/doe_phase2_binary_reference/build_reference.py
& $python tests/fixtures/doe_phase2_binary_reference/verify.py
```
