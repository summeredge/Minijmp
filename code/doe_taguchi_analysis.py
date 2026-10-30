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
    """按不同噪声设置汇总响应；重复仍是观测，不额外计作噪声条件。"""
    design = restore_design_result(frame, metadata)
    spec = design.spec
    grid = taguchi_grid(spec)
    if not grid["noise_columns"]:
        raise ValueError("该设计没有噪声因子，不能作稳健性分析")
    signal = spec.taguchi["signal_factor"]
    groups = {}
    noise_factors = sorted(grid["noise_columns"])
    for run in sorted(design.runs, key=lambda item: item.standard_order):
        value = run.responses[response]
        if value is None:
            raise ValueError("响应存在缺失值，请填写全部运行")
        control = tuple(sorted((factor_id, run.settings[factor_id])
                               for factor_id in grid["columns"]))
        signal_level = None if signal is None else run.settings[signal]
        noise = tuple((factor_id, run.settings[factor_id]) for factor_id in noise_factors)
        groups.setdefault((control, signal_level), {}).setdefault(noise, []).append(run)
    rows, matrix_sn = [], []
    for (control, signal_level), conditions in groups.items():
        if len(conditions) < 2:
            raise ValueError("每个控制设定至少需要两个噪声条件")
        all_values, condition_means, condition_rows = [], [], []
        control_run_ids = set()
        for noise, runs in conditions.items():
            runs = sorted(runs, key=lambda item: (item.replicate, item.standard_order))
            noise_codes = [grid["factors"][factor_id].levels.index(value) + 1
                           for factor_id, value in noise]
            condition_id = "N" + "".join(str(value) for value in noise_codes)
            values = _finite([run.responses[response] for run in runs])
            replicates = [run.replicate for run in runs]
            for run in runs:
                expected_id = f"{condition_id}R{run.replicate}"
                if run.noise_condition_id != expected_id:
                    raise ValueError("噪声条件 ID 与因子水平或重复编号不一致")
                control_run_ids.add(run.control_run_id)
            mean_condition = float(values.mean())
            condition_means.append(mean_condition)
            all_values.extend(values.tolist())
            condition_rows.append({
                "condition_id": condition_id,
                "noise_settings": dict(noise),
                "replicates": replicates,
                "standard_orders": [run.standard_order for run in runs],
                "run_ids": [run.run_id for run in runs],
                "n": int(values.size),
                "mean": mean_condition,
                "sd": (None if values.size < 2
                       else float(values.std(ddof=1))),
                "response_range": float(values.max() - values.min()),
            })
        if len(control_run_ids) != 1:
            raise ValueError("同一控制组合的控制运行 ID 必须一致")
        array = _finite(all_values)
        mean = float(array.mean())
        sd = None if array.size < 2 else float(array.std(ddof=1))
        condition_mean_range = max(condition_means) - min(condition_means)
        sn = signal_to_noise(array, kind)
        condition_count = len(condition_rows)
        observation_count = int(array.size)
        matrix_sn.append({"settings": dict(control), "signal": signal_level,
                          "n": observation_count, "noise_count": observation_count,
                          "condition_count": condition_count, "mean": mean,
                          "sd": sd, "sn": sn})
        rows.append({"settings": dict(control), "signal": signal_level,
                     "control_run_id": next(iter(control_run_ids)),
                     "noise_count": observation_count,
                     "condition_count": condition_count,
                     "observation_count": observation_count,
                     "n": observation_count, "mean": mean, "sd": sd, "sn": sn,
                     "condition_mean_range": condition_mean_range,
                     "noise_conditions": condition_rows})
    table = _response_table(spec, matrix_sn, "sn")
    return {"design": design, "response": response, "kind": kind, "rows": rows,
            "response_table": table,
            "status": (f"按 {len(rows)} 个控制/信号条件汇总 "
                       f"{sum(row['condition_count'] for row in rows)} 个不同噪声设置；"
                       f"共 {sum(row['observation_count'] for row in rows)} 条观测"),
            "assumption": ("不同噪声因子水平元组各计一个条件，重复号与运行 ID 保留为观测身份；"
                           "Mean、SD、S/N 使用该控制组合的全部观测，条件极差比较各噪声设置的响应均值；"
                           "控制水平响应表对已观测控制组合等权平均。")}


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
        "evaluation_count": candidate_count,
        "stop_reason": "completed",
        "global_optimum": True,
        "optimality_scope": "finite declared-level Cartesian product under the additive prediction model",
        "tie_rule": "factor and declared level order; first tied combination selected",
    }


def _robust_settings(table, combinations, selection_mode, target, sn_threshold):
    factors = table["factors"]
    candidate_count = math.prod(len(row["levels"]) for row in factors)
    if candidate_count > _MAX_TARGET_COMBINATIONS:
        raise ValueError(
            f"稳健设置搜索需要精确枚举 {candidate_count} 个组合，超过预算 "
            f"{_MAX_TARGET_COMBINATIONS}；未执行搜索，无法声明预测最优设置")
    candidates = []
    for levels in product(*(row["levels"] for row in factors)):
        settings = {factor["factor_id"]: level["level"]
                    for factor, level in zip(factors, levels)}
        predicted_sn = _additive_prediction(table, combinations, "sn", settings)
        predicted_mean = _additive_prediction(table, combinations, "mean", settings)
        if predicted_sn is None or predicted_mean is None:
            raise ValueError("S/N 或均值在部分水平上不可计算")
        predicted_sd = _additive_prediction(table, combinations, "sd", settings)
        if predicted_sd is not None and predicted_sd < 0:
            predicted_sd = None
        candidates.append({
            "settings": settings,
            "predicted_sn": predicted_sn, "predicted_mean": predicted_mean,
            "predicted_sd": predicted_sd,
        })

    if selection_mode == "sn_maximum":
        eligible = candidates
        optimum = max(item["predicted_sn"] for item in eligible)
        distance = None
        scale = max(1.0, abs(optimum))
        tolerance = math.ulp(scale) * (2 * len(factors) + 2)
        tied = [item for item in eligible
                if abs(item["predicted_sn"] - optimum) <= tolerance]
    else:
        eligible = [item for item in candidates
                    if item["predicted_sn"] >= sn_threshold]
        if eligible:
            distance = min(abs(item["predicted_mean"] - target) for item in eligible)
            tied = [item for item in eligible
                    if abs(abs(item["predicted_mean"] - target) - distance)
                    <= math.ulp(max(1.0, abs(target), abs(item["predicted_mean"])))
                    * (2 * len(factors) + 2)]
            for item in tied:
                item["distance"] = abs(item["predicted_mean"] - target)
        else:
            distance, tied = None, []

    best = tied[0]["settings"] if tied else None
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
    unreachable = selection_mode == "robust_then_target" and not eligible
    return best, per_factor, tied, {
        "method": ("exact enumeration of additive main-effect combinations"),
        "candidate_count": candidate_count,
        "evaluation_count": candidate_count,
        "eligible_count": len(eligible),
        "budget": _MAX_TARGET_COMBINATIONS,
        "stop_reason": "no_candidate_meets_sn_threshold" if unreachable else "completed",
        "search_complete": True,
        "global_optimum": not unreachable,
        "status_code": "target_unreachable" if unreachable else "ok",
        "optimality_scope": "finite declared-level Cartesian product under the additive prediction model",
        "tie_rule": "factor and declared level order; first tied combination selected",
        "selection_mode": selection_mode,
        "sn_threshold": sn_threshold,
        "target": target,
        "minimum_target_distance": distance,
    }


def best_settings(frame, metadata, response, metric="sn", target=None,
                  observed=None, tolerance=None, selection_mode=None,
                  sn_threshold=None):
    """按指标体系选水平，给出加性主效应预测与确认实验建议。"""
    design = restore_design_result(frame, metadata)
    spec = design.spec
    dynamic = spec.taguchi["kind"] == "dynamic"
    if metric not in _METRICS:
        raise ValueError("优化指标必须是 sn、mean、sd 或 slope")
    if selection_mode not in (None, "sn_maximum", "robust_then_target"):
        raise ValueError("未知的最佳设置选择模式")
    if selection_mode is not None and metric != "sn":
        raise ValueError("新增稳健选择模式必须以 S/N 作为指标")
    if selection_mode == "robust_then_target" and dynamic:
        raise ValueError("先稳健后目标的均值目标模式仅适用于静态设计")
    if selection_mode == "robust_then_target":
        if target is None or sn_threshold is None:
            raise ValueError("稳健后目标模式需要目标均值和最低 S/N")
        target = float(_finite([target], "目标均值")[0])
        sn_threshold = float(_finite([sn_threshold], "最低 S/N")[0])
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
    if selection_mode is not None:
        best, tied, tied_combinations, search = _robust_settings(
            table, combinations, selection_mode, target, sn_threshold)
    elif metric in ("mean", "slope"):
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
    is_observed = (None if best is None else
                   any(all(settings[key] == best[key] for key in best)
                       for settings in observed_settings))
    predicted_sd = (None if best is None else
                    _additive_prediction(table, combinations, "sd", best))
    predicted_sd_reason = None
    if best is None:
        predicted_sd_reason = "没有组合满足最低 S/N，未生成推荐设置"
    elif predicted_sd is None:
        if any(row.get("sd") is None for row in combinations):
            predicted_sd_reason = "样本不足，SD 无法估计"
        else:
            predicted_sd_reason = "SD 水平值不可计算"
    elif predicted_sd < 0:
        predicted_sd = None
        predicted_sd_reason = "加性主效应预测为负，不作为物理标准差显示"
    predicted = {
        "mean": (None if best is None else
                 _additive_prediction(table, combinations, "mean", best)),
        "sn": (None if best is None else
               _additive_prediction(table, combinations, "sn", best)),
        "sd": predicted_sd,
        "slope": (_additive_prediction(table, combinations, "slope", best)
                  if dynamic and best is not None else None),
    }
    difference = (None if observed is None
                  or predicted["mean"] is None
                  else float(observed) - predicted["mean"])
    meets = (None if observed is None or target is None or tolerance is None
             else abs(float(observed) - float(target)) <= float(tolerance))
    if selection_mode == "sn_maximum":
        status = (f"按加性预测 S/N 最大值筛选；精确枚举 {search['candidate_count']} 个组合，"
                  f"{len(tied_combinations)} 个并列；最优仅指声明水平组合中的模型预测")
    elif selection_mode == "robust_then_target" and best is None:
        status = (f"没有组合达到最低 S/N {sn_threshold:g}；已精确枚举 "
                  f"{search['candidate_count']} 个组合，未回退到其他目标")
    elif selection_mode == "robust_then_target":
        status = (f"先筛选预测 S/N ≥ {sn_threshold:g}，再选择预测均值距目标 "
                  f"{target:g} 最近的组合；已精确枚举 {search['candidate_count']} 个组合，"
                  f"{len(tied_combinations)} 个并列最优预测")
    else:
        status = (f"按{_METRICS[metric]}"
                  + (f"（目标 {target:g}）" if target is not None else "")
                  + "选水平并使用加性主效应预测；"
                  + (f"精确枚举 {search['candidate_count']} 个控制水平组合，"
                     f"{len(tied_combinations)} 个最优组合并列；"
                     if search is not None else "")
                  + ("该组合已在实验中观测" if is_observed
                     else "该组合未在实验中观测，必须做确认试验"))
    return {
        "design": design, "response": response, "metric": metric,
        "target": target, "tolerance": tolerance, "best": best,
        "selection_mode": selection_mode, "sn_threshold": sn_threshold,
        "status_code": (search["status_code"] if selection_mode is not None else "ok"),
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
        "status": status,
        "assumption": ("预测依赖控制因子主效应可加、无显著交互混杂；"
                       "确认试验不修改原始正交表运行"),
    }
