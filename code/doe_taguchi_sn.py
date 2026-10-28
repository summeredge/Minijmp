"""Taguchi 静态/动态 S/N 与响应表；公式依据 Minitab 官方 Methods 页。"""
import math

import numpy as np

from doe_core import restore_design_result, taguchi_grid


STATIC_KINDS = ("smaller", "larger", "nominal", "nominal_ii")


def _finite(values, field="响应"):
    try:
        array = np.asarray(values, dtype=float)
    except (TypeError, ValueError, OverflowError):
        raise ValueError(f"{field}必须可转换为数值") from None
    if array.size == 0:
        raise ValueError(f"{field}为空，无法计算")
    if not np.isfinite(array).all():
        raise ValueError(f"{field}含非有限值")
    return array


def _sample_variance(values):
    n = values.size
    if n < 2:
        raise ValueError("样本方差需要至少两个观测")
    mean = float(values.mean())
    variance = float(((values - mean) ** 2).sum() / (n - 1))
    if not math.isfinite(variance):
        raise ValueError("样本方差超出可计算范围")
    return mean, variance


def _log10(value):
    """以 10 为底对数；非正自变量按公式数据域拒绝。"""
    if not math.isfinite(value) or value <= 0:
        raise ValueError("对数自变量必须为正有限值")
    return math.log10(value)


def signal_to_noise(values, kind, adjusted=False):
    """四类静态 S/N；adjusted 只对 nominal-is-best (I) 生效。"""
    array = _finite(values, "S/N 响应")
    if kind not in STATIC_KINDS:
        raise ValueError("未知静态 S/N 类型")
    if adjusted and kind != "nominal":
        raise ValueError("adjusted 公式只适用于 nominal-is-best (I)")
    # 极值会溢出成 inf/0，随后由 _log10 拒绝；避免 numpy 运行期警告噪声。
    with np.errstate(over="ignore", under="ignore", divide="ignore"):
        if kind == "smaller":
            return -10 * _log10(float((array ** 2).mean()))
        if kind == "larger":
            if (array == 0).any():
                raise ValueError("larger-is-better 的响应不得为 0")
            return -10 * _log10(float((1 / array ** 2).mean()))
    mean, variance = _sample_variance(array)
    if variance == 0:
        raise ValueError("样本方差为零，S/N 无定义")
    if kind == "nominal_ii":
        return -10 * _log10(variance)
    numerator = mean ** 2 - variance / array.size if adjusted else mean ** 2
    if numerator <= 0:
        raise ValueError("均值平方不足以构成正的 S/N 分子")
    return 10 * _log10(numerator / variance)


def fit_dynamic(signal, response, reference=None):
    """动态 signal-response 回归；reference=(信号, 响应) 时过参考点。"""
    x = _finite(signal, "信号因子")
    y = _finite(response, "响应")
    if x.size != y.size:
        raise ValueError("信号与响应长度不一致")
    if x.size < 2 or float(x.max()) == float(x.min()):
        raise ValueError("动态回归需要至少两个不同信号水平")
    if reference is None:
        design = np.column_stack((np.ones(x.size), x))
        coefficients, _, rank, _ = np.linalg.lstsq(design, y, rcond=None)
        if rank != 2:
            raise ValueError("信号因子设计矩阵秩亏，无法同时估计截距与斜率")
        intercept, slope = float(coefficients[0]), float(coefficients[1])
    else:
        signal_ref, response_ref = (_finite([reference[0]], "参考信号")[0],
                                    _finite([reference[1]], "参考响应")[0])
        centred = x - signal_ref
        if not float((centred ** 2).sum()) > 0:
            raise ValueError("全部信号水平等于参考信号，无法估计斜率")
        slope = float((centred * (y - response_ref)).sum() / (centred ** 2).sum())
        intercept = response_ref - slope * signal_ref
    fitted = intercept + slope * x
    residuals = y - fitted
    df = x.size - 2 if reference is None else x.size - 1
    sse = float(residuals @ residuals)
    if df < 1:
        raise ValueError("动态回归残差自由度不足，无法估计 MSE")
    mse = sse / df
    return {"slope": slope, "intercept": intercept, "fitted": fitted,
            "residuals": residuals, "sse": sse, "df": df, "mse": mse,
            "signal": x, "response": y, "reference": reference}


def dynamic_sn(fit, adjusted=False):
    """动态 S/N = 10 log10(slope² / MSE)；adjusted 再减去 1/r。"""
    slope, mse = fit["slope"], fit["mse"]
    scale = max(1.0, float((fit["response"] ** 2).mean()))
    # shortcut: 数值上不可辨识的 MSE 与精确零同样处理，避免报告巨大的伪 S/N
    if not mse > 1e-12 * scale:
        raise ValueError("MSE 为零或数值上不可辨识，动态 S/N 无定义")
    ratio = slope ** 2 / mse
    if adjusted:
        x = fit["signal"]
        reference = fit["reference"]
        ref = reference[0] if reference is not None else float(x.mean())
        r = float(((x - ref) ** 2).sum())
        if r <= 0:
            raise ValueError("adjusted 动态 S/N 需要非零信号跨度")
        ratio -= 1 / r
    if ratio <= 0:
        raise ValueError("动态 S/N 的对数自变量非正")
    return 10 * _log10(ratio)


def _responses_by_control(spec, runs, response):
    grid = taguchi_grid(spec)
    signal = spec.taguchi["signal_factor"]
    groups = {}
    for run in runs:
        value = run.responses[response]
        if value is None:
            raise ValueError("响应存在缺失值，请填写全部运行")
        control = tuple(sorted((factor_id, run.settings[factor_id])
                               for factor_id in grid["columns"]))
        groups.setdefault(control, []).append(
            (None if signal is None else run.settings[signal], float(value)))
    return grid, signal, groups


def analyze_static(frame, metadata, response, kind="smaller", adjusted=False,
                   ln_sd=False):
    """静态分析：每控制组合的 Mean/SD/S/N 与因子水平响应表。"""
    design = restore_design_result(frame, metadata)
    spec = design.spec
    if spec.design_type != "taguchi" or spec.taguchi["kind"] != "static":
        raise ValueError("需要静态 Taguchi 设计")
    if response not in spec.response_names:
        raise ValueError("响应不属于该设计")
    grid, _, groups = _responses_by_control(spec, design.runs, response)
    combination = []
    for control, observations in groups.items():
        values = _finite([value for _, value in observations])
        sn = signal_to_noise(values, kind, adjusted)
        mean = float(values[0]) if values.size == 1 else None
        variance = None
        if values.size > 1:
            mean, variance = _sample_variance(values)
        sd = None if variance is None else math.sqrt(variance)
        combination.append({
            "settings": dict(control), "n": values.size, "mean": mean,
            "sd": sd,
            "ln_sd": (math.log(sd) if ln_sd and sd is not None and sd > 0 else None),
            "sn": sn,
        })
    table = _response_table(spec, combination, "sn")
    return {
        "design": design, "response": response, "kind": kind,
        "adjusted": adjusted, "ln_sd": ln_sd,
        "combinations": combination, "response_table": table,
        "n_observations": len(design.runs),
        "status": ("S/N 越大越好；响应表按控制因子水平平均，"
                   f"共 {len(design.runs)} 条原始观测"),
        "assumption": ("每个控制组合的观测视为独立重复；"
                       "S/N 与 Mean/SD 均为该组合的样本统计量。"),
    }


def _response_table(spec, combinations, metric):
    """按因子水平求响应特征平均，并给出 Delta/Rank/最优水平。"""
    factors = [factor for factor in spec.factors
               if factor.factor_id in combinations[0]["settings"]]
    grand = sum(row[metric] for row in combinations) / len(combinations)
    table, best = [], {}
    for factor in factors:
        levels = []
        for level in factor.levels:
            rows = [row for row in combinations
                    if row["settings"][factor.factor_id] == level]
            if not rows:
                raise ValueError(f"因子 {factor.factor_id} 的水平缺少观测")
            mean_sn = sum(row["sn"] for row in rows) / len(rows)
            sd_values = [row["sd"] for row in rows]
            levels.append({
                "level": level, "sn": mean_sn,
                "slope": (sum(row["slope"] for row in rows) / len(rows)
                          if "slope" in rows[0] else None),
                "mean": sum(row["mean"] for row in rows) / len(rows),
                "sd": (None if any(value is None for value in sd_values)
                       else sum(sd_values) / len(sd_values)),
                "ln_sd": (sum(row["ln_sd"] for row in rows) / len(rows)
                          if all(row.get("ln_sd") is not None for row in rows)
                          else None),
                "n": sum(row["n"] for row in rows),
            })
        deltas = [row[metric] for row in levels]
        delta = max(deltas) - min(deltas)
        for row in levels:
            row["effect"] = row[metric] - grand
        table.append({"factor_id": factor.factor_id, "levels": levels,
                      "delta": delta})
        best[factor.factor_id] = max(levels, key=lambda row: row[metric])["level"]
    ranked = sorted(table, key=lambda row: row["delta"], reverse=True)
    for rank, row in enumerate(ranked, 1):
        row["rank"] = rank
    return {"factors": table, "best": best,
            "ranked": [row["factor_id"] for row in ranked]}

