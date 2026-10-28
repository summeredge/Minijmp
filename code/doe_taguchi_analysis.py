"""Taguchi 动态分析、噪声稳健性与最佳设置预测。"""
import math
from itertools import product

import numpy as np

from doe_core import restore_design_result, taguchi_grid
from doe_taguchi_sn import (dynamic_sn, fit_dynamic, signal_to_noise,
                            _finite, _response_table, _responses_by_control)


def analyze_dynamic(frame, metadata, response, reference=None, adjusted=False):
    """动态分析：每控制组合的 signal-response 斜率、MSE 与动态 S/N。"""
    design = restore_design_result(frame, metadata)
    spec = design.spec
    if spec.design_type != "taguchi" or spec.taguchi["kind"] != "dynamic":
        raise ValueError("需要动态 Taguchi 设计")
    if response not in spec.response_names:
        raise ValueError("响应不属于该设计")
    grid, signal, groups = _responses_by_control(spec, design.runs, response)
    if signal is None:
        raise ValueError("动态设计缺少信号因子")
    fits, combinations = [], []
    for control, observations in groups.items():
        x = _finite([value for value, _ in observations], "信号因子")
        y = _finite([value for _, value in observations], "响应")
        fit = fit_dynamic(x, y, reference)
        sn = dynamic_sn(fit, adjusted)
        fits.append(fit)
        combinations.append({"settings": dict(control), "n": x.size,
                             "slope": fit["slope"], "intercept": fit["intercept"],
                             "mse": fit["mse"], "df": fit["df"], "sn": sn,
                             "mean": float(y.mean()), "sd": float(y.std(ddof=1)),
                             "signal": x, "response": y})
    slope_table = _response_table(spec, combinations, "slope")
    sn_table = _response_table(spec, combinations, "sn")
    return {
        "design": design, "response": response, "kind": "dynamic",
        "adjusted": adjusted, "reference": reference, "fits": fits,
        "combinations": combinations, "slope_table": slope_table,
        "response_table": sn_table, "n_observations": len(design.runs),
        "status": ("动态 S/N = 10 log10(slope²/MSE)"
                   + ("（adjusted）" if adjusted else "")
                   + f"；共 {len(design.runs)} 条原始观测，{len(combinations)} 个控制组合"),
        "assumption": ("每个控制组合内信号与响应满足线性关系；"
                       "残差独立同方差，MSE 自由度与所用回归形式一致。"),
    }


def noise_robustness(frame, metadata, response, kind="smaller"):
    """按噪声条件比较同一控制设定下的响应变化。"""
    design = restore_design_result(frame, metadata)
    spec = design.spec
    grid = taguchi_grid(spec)
    if not grid["noise_columns"]:
        raise ValueError("该设计没有噪声因子，不能作稳健性分析")
    signal = spec.taguchi["signal_factor"]
    groups = {}
    for run in design.runs:
        value = run.responses[response]
        if value is None:
            raise ValueError("响应存在缺失值，请填写全部运行")
        control = tuple(sorted((factor_id, run.settings[factor_id])
                               for factor_id in grid["columns"]))
        key = (control, None if signal is None else run.settings[signal])
        groups.setdefault(key, []).append(float(value))
    rows, matrix_sn = [], []
    for (control, signal_level), values in groups.items():
        array = _finite(values)
        if array.size < 2:
            raise ValueError("每个控制设定至少需要两个噪声条件")
        mean = float(array.mean())
        sd = float(array.std(ddof=1))
        sn = signal_to_noise(array, kind)
        matrix_sn.append({"settings": dict(control), "signal": signal_level,
                          "n": array.size, "noise_count": array.size, "mean": mean,
                          "sd": sd, "sn": sn})
        rows.append({"settings": dict(control), "signal": signal_level,
                     "noise_count": array.size, "mean": mean, "sd": sd,
                     "sn": sn})
    table = _response_table(spec, matrix_sn, "sn")
    return {"design": design, "response": response, "kind": kind, "rows": rows,
            "response_table": table,
            "status": (f"按 {len(rows)} 个控制设定比较噪声条件间的均值、SD 与 S/N；"
                       "每个控制设定至少需要两个噪声条件"),
            "assumption": ("同一控制设定的不同噪声条件视为独立观测；"
                           "噪声因子水平来自实验内可控设置。")}


_METRICS = {"sn": "S/N", "mean": "目标均值", "sd": "最小 SD", "slope": "目标斜率"}
_MAX_TARGET_COMBINATIONS = 20_000


def _select_level(levels, metric, target):
    """按指标选水平；返回 (最佳值, 并列水平列表)。"""
    values = [level[metric] for level in levels]
    if any(value is None for value in values):
        raise ValueError(f"{_METRICS[metric]}在部分水平上不可计算")
    if metric in ("sn", "sd") or (metric == "slope" and target is None):
        pick = max(values) if metric == "sn" else min(values)
    else:
        if target is None:
            raise ValueError("目标均值或目标斜率优化需要填写目标值")
        pick = min(values, key=lambda value: abs(value - target))
    return pick, [level for level, value in zip(levels, values) if value == pick]


def _additive_prediction(table, combinations, metric, settings):
    values = [row[metric] for row in combinations]
    if any(value is None or not math.isfinite(value) for value in values):
        return None
    grand = math.fsum(values) / len(values)
    effects = []
    for factor in table["factors"]:
        level = next(item for item in factor["levels"]
                     if item["level"] == settings[factor["factor_id"]])
        value = level[metric]
        if value is None or not math.isfinite(value):
            return None
        effects.append(value - grand)
    return grand + math.fsum(effects)


def _target_settings(table, combinations, metric, target):
    """精确枚举可预算内的完整加性水平组合，稳定保留全部并列解。"""
    factors = table["factors"]
    level_rows = [factor["levels"] for factor in factors]
    candidate_count = math.prod(len(levels) for levels in level_rows)
    if candidate_count > _MAX_TARGET_COMBINATIONS:
        raise ValueError(
            f"目标搜索需要精确枚举 {candidate_count} 个控制水平组合，超过预算 "
            f"{_MAX_TARGET_COMBINATIONS}；未执行搜索，无法声明目标最优设置")
    candidates = []
    for levels in product(*level_rows):
        settings = {factor["factor_id"]: level["level"]
                    for factor, level in zip(factors, levels)}
        prediction = _additive_prediction(table, combinations, metric, settings)
        if prediction is None:
            raise ValueError(f"{_METRICS[metric]}的部分水平不可计算")
        candidates.append((abs(prediction - target), prediction, settings))
    best_distance = min(candidate[0] for candidate in candidates)
    tied = []
    for distance, prediction, settings in candidates:
        scale = max(1.0, abs(target), abs(prediction))
        # Scale only by rounding ULPs and the number of additive terms; do not merge near optima.
        tolerance = math.ulp(scale) * (2 * len(factors) + 2)
        if abs(distance - best_distance) <= tolerance:
            tied.append({"settings": settings, "predicted": prediction,
                         "distance": distance})
    best = tied[0]["settings"]
    per_factor = {
        factor["factor_id"]: {
            "value": None,
            "levels": [level["level"] for level in factor["levels"]
                       if any(item["settings"][factor["factor_id"]] == level["level"]
                              for item in tied)],
            "tied": False,
        }
        for factor in factors
    }
    for item in per_factor.values():
        item["tied"] = len(item["levels"]) > 1
    return best, per_factor, tied, {
        "method": "exact enumeration of additive main-effect combinations",
        "candidate_count": candidate_count,
        "budget": _MAX_TARGET_COMBINATIONS,
        "global_optimum": True,
        "tie_rule": "factor and declared level order; first tied combination selected",
    }


def best_settings(frame, metadata, response, metric="sn", target=None,
                  observed=None, tolerance=None):
    """按指标体系选水平，给出加性主效应预测与确认实验建议。"""
    design = restore_design_result(frame, metadata)
    spec = design.spec
    dynamic = spec.taguchi["kind"] == "dynamic"
    if metric not in _METRICS:
        raise ValueError("优化指标必须是 sn、mean、sd 或 slope")
    if metric == "slope" and not dynamic:
        raise ValueError("目标斜率只适用于动态设计")
    if metric in ("mean", "slope"):
        if target is None:
            raise ValueError(f"{_METRICS[metric]}优化需要填写目标值")
        target = float(_finite([target], "目标值")[0])
    from doe_taguchi_sn import analyze_static
    # 沿用工程保存的分析选项，避免最佳设置与上次分析使用不同的 S/N 或回归形式。
    options = metadata.get("analysis") if isinstance(metadata, dict) else None
    options = options if options and options.get("kind") == spec.taguchi["kind"] else {}
    if dynamic:
        reference = (tuple(options["reference"])
                     if options.get("reference_mode") == "fixed" else None)
        result = analyze_dynamic(frame, metadata, response, reference,
                                 bool(options.get("adjusted")))
        table = result["slope_table"] if metric == "slope" else result["response_table"]
        combinations = result["combinations"]
    else:
        result = analyze_static(frame, metadata, response,
                                options.get("sn_kind", "smaller"),
                                bool(options.get("adjusted")))
        table, combinations = result["response_table"], result["combinations"]
    search = None
    tied_combinations = []
    if metric in ("mean", "slope"):
        best, tied, tied_combinations, search = _target_settings(
            table, combinations, metric, target)
    else:
        best, tied = {}, {}
        for row in table["factors"]:
            value, levels = _select_level(row["levels"], metric, target)
            best[row["factor_id"]] = levels[0]["level"]
            tied[row["factor_id"]] = {
                "value": value,
                "levels": [level["level"] for level in levels],
                "tied": len(levels) > 1,
            }
    observed_settings = [row["settings"] for row in combinations]
    is_observed = any(all(settings[key] == best[key] for key in best)
                      for settings in observed_settings)
    predicted_sd = _additive_prediction(table, combinations, "sd", best)
    predicted_sd_reason = None
    if predicted_sd is None:
        if any(row.get("sd") is None for row in combinations):
            predicted_sd_reason = "样本不足，SD 无法估计"
        else:
            predicted_sd_reason = "SD 水平值不可计算"
    elif predicted_sd < 0:
        predicted_sd = None
        predicted_sd_reason = "加性主效应预测为负，不作为物理标准差显示"
    predicted = {
        "mean": _additive_prediction(table, combinations, "mean", best),
        "sn": _additive_prediction(table, combinations, "sn", best),
        "sd": predicted_sd,
        "slope": (_additive_prediction(table, combinations, "slope", best)
                  if dynamic else None),
    }
    difference = (None if observed is None
                  else float(observed) - predicted["mean"])
    meets = (None if observed is None or target is None or tolerance is None
             else abs(float(observed) - float(target)) <= float(tolerance))
    return {
        "design": design, "response": response, "metric": metric,
        "target": target, "tolerance": tolerance, "best": best,
        "tied": tied, "table": table,
        "is_observed": is_observed, "predicted": predicted,
        "predicted_mean": predicted["mean"], "predicted_sn": predicted["sn"],
        "predicted_sd": predicted["sd"], "predicted_slope": predicted["slope"],
        "confirmation": {
            "settings": best, "predicted_mean": predicted["mean"],
            "predicted_sn": predicted["sn"], "observed": observed,
            "difference": difference, "meets_target": meets,
            "tolerance": tolerance,
        },
        "tied_combinations": tied_combinations,
        "search": search,
        "predicted_sd_reason": predicted_sd_reason,
        "status": (f"按{_METRICS[metric]}"
                   + (f"（目标 {target:g}）" if target is not None else "")
                   + "选水平并使用加性主效应预测；"
                   + (f"精确枚举 {search['candidate_count']} 个控制水平组合，"
                      f"{len(tied_combinations)} 个最优组合并列；"
                      if search is not None else "")
                   + ("该组合已在实验中观测" if is_observed
                      else "该组合未在实验中观测，必须做确认试验")),
        "assumption": ("预测依赖控制因子主效应可加、无显著交互混杂；"
                       "确认试验不修改原始正交表运行"),
    }
