"""Power and sample-size calculations for replicated two-level DOE designs."""

import math
from numbers import Integral, Real

import numpy as np
from scipy.stats import f, ncf


_MAX_TOTAL_RUNS = 10_000


def calculate_power(
    design_points,
    factor_names,
    tested_factor,
    delta,
    sigma,
    alpha,
    *,
    fixed_replicates=None,
    target_power=None,
):
    """Calculate power or the minimum repeats for one two-level main effect."""
    if (fixed_replicates is None) == (target_power is None):
        raise ValueError("必须且只能指定 fixed_replicates 或 target_power 之一")

    try:
        points = np.asarray(design_points, dtype=float)
    except (TypeError, ValueError) as error:
        raise ValueError("设计矩阵必须是有限的两水平数值矩阵") from error
    if (points.ndim != 2 or not points.shape[0] or not points.shape[1]
            or not np.isfinite(points).all()
            or not np.isin(points, (-1.0, 1.0)).all()):
        raise ValueError("设计矩阵必须是非空且仅含 -1、+1 的二维矩阵")

    if isinstance(factor_names, (str, bytes)):
        raise ValueError("factor_names 必须与设计矩阵列一一对应")
    try:
        names = tuple(factor_names)
    except TypeError as error:
        raise ValueError("factor_names 必须与设计矩阵列一一对应") from error
    if (len(names) != points.shape[1]
            or any(not isinstance(name, str) or not name or name != name.strip()
                   for name in names)
            or len(set(names)) != len(names)):
        raise ValueError("factor_names 必须是唯一、非空且与矩阵列一一对应的名称")
    if tested_factor not in names:
        raise ValueError("目标因子必须属于 factor_names")

    values = (delta, sigma, alpha)
    if any(isinstance(value, bool) or not isinstance(value, Real)
           or not math.isfinite(value) for value in values):
        raise ValueError("delta、sigma 和 alpha 必须是有限数值")
    delta, sigma, alpha = map(float, values)
    if delta == 0:
        raise ValueError("delta 必须不为 0")
    if sigma <= 0:
        raise ValueError("sigma 必须大于 0")
    if not 0 < alpha < 1:
        raise ValueError("alpha 必须介于 0 与 1 之间")

    if fixed_replicates is not None:
        if (isinstance(fixed_replicates, bool)
                or not isinstance(fixed_replicates, Integral)
                or fixed_replicates < 1):
            raise ValueError("fixed_replicates 必须是正整数")
        fixed_replicates = int(fixed_replicates)
        if points.shape[0] * fixed_replicates > _MAX_TOTAL_RUNS:
            raise ValueError("总运行数不得超过 10,000")
    else:
        if (isinstance(target_power, bool) or not isinstance(target_power, Real)
                or not math.isfinite(target_power) or not 0 < target_power < 1):
            raise ValueError("target_power 必须介于 0 与 1 之间")
        target_power = float(target_power)

    if points.shape[0] > _MAX_TOTAL_RUNS:
        raise ValueError("设计运行数不得超过 10,000")

    model = np.column_stack((np.ones(points.shape[0]), points))
    rank = int(np.linalg.matrix_rank(model))
    if rank != model.shape[1]:
        raise ValueError("截距与全部主效应构成的模型矩阵不满秩")

    tested_column = names.index(tested_factor) + 1
    inverse_diagonal = float(np.linalg.inv(model.T @ model)[tested_column, tested_column])
    if not math.isfinite(inverse_diagonal) or inverse_diagonal <= 0:
        raise ValueError("目标主效应的信息矩阵不可逆")

    def result_for(replicates):
        total_runs = points.shape[0] * replicates
        df_error = total_runs - rank
        if df_error <= 0:
            return None
        standardized_effect = (delta / 2) / sigma
        noncentrality = (standardized_effect * standardized_effect
                         * replicates / inverse_diagonal)
        critical_f = float(f.isf(alpha, 1, df_error))
        power = (1.0 if math.isinf(noncentrality)
                 else float(ncf.sf(critical_f, 1, df_error, noncentrality)))
        if not math.isfinite(power):
            raise ArithmeticError("非中心 F 功效计算未返回有限结果")
        return {
            "method": "非中心 F 检验（主效应 1 df）",
            "df": {"model": rank - 1, "test": 1, "error": df_error},
            "power": power,
            "total_runs": total_runs,
            "replicates": replicates,
            "assumptions": [
                "所有基础设计点完整且以相同次数重复。",
                "模型包含截距和全部主效应；误差独立、正态且标准差为 sigma。",
                "未拟合交互视为可忽略；分数因子和 PB 的主效应须按设计别名/混杂结构解释。",
            "这是非方向性的一自由度 F 检验；功效取决于 delta 的平方，不随效应方向改变。",
                "仅适用于无区组、无中心点的两水平设计。",
            ],
        }

    if fixed_replicates is not None:
        result = result_for(fixed_replicates)
        if result is None:
            raise ValueError("该重复数下模型没有正的误差自由度")
        return result

    previous = None
    for replicates in range(1, _MAX_TOTAL_RUNS // points.shape[0] + 1):
        result = result_for(replicates)
        if result is not None and result["power"] >= target_power:
            if previous is not None and previous["power"] >= target_power:
                raise ArithmeticError("样本量反解未通过前一重复数核验")
            return result
        previous = result
    raise ValueError("总运行数不超过 10,000 时无法达到目标功效")
