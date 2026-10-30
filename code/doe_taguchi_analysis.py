"""Taguchi 动态分析、噪声稳健性与最佳设置预测。"""
import math
from itertools import product

import numpy as np
from scipy import stats

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


def noise_response_model(frame, metadata, response, interactions=(), target_mean=None,
                         target_tolerance=None, mean_range=None):
    """拟合二水平控制×噪声 OLS，并在声明的噪声条件上精确搜索稳健设置。"""
    design = restore_design_result(frame, metadata)
    spec = design.spec
    if spec.taguchi["kind"] != "static" or spec.taguchi["signal_factor"] is not None:
        raise ValueError("响应模型法仅支持无信号因子的静态 Taguchi 内外表")
    grid = taguchi_grid(spec)
    control_ids = tuple(factor.factor_id for factor in spec.factors
                        if factor.factor_id in grid["columns"])
    noise_ids = tuple(factor_id for factor_id, _ in sorted(grid["noise_columns"].items()))
    if not control_ids or not noise_ids:
        raise ValueError("响应模型法需要控制因子和噪声因子")
    if response not in spec.response_names:
        raise ValueError("响应不属于该设计")
    factor_map = grid["factors"]
    if any(len(factor_map[key].levels) != 2 for key in (*control_ids, *noise_ids)):
        raise ValueError("首版响应模型仅支持二水平控制因子和二水平噪声因子")
    if (target_mean is not None and mean_range is not None) or (
            target_tolerance is not None and target_mean is None):
        raise ValueError("目标均值约束与均值范围约束只能选择一种")
    if target_mean is not None:
        target_mean = float(_finite([target_mean], "目标均值")[0])
        if target_tolerance is not None:
            target_tolerance = float(_finite([target_tolerance], "目标均值容差")[0])
            if target_tolerance < 0:
                raise ValueError("目标均值容差不能为负")
    if mean_range is not None:
        if not isinstance(mean_range, (tuple, list)) or len(mean_range) != 2:
            raise ValueError("均值范围必须包含下限和上限")
        lower, upper = _finite(mean_range, "均值范围")
        if lower > upper:
            raise ValueError("均值范围下限不能大于上限")
        mean_range = (float(lower), float(upper))

    if isinstance(interactions, str):
        interactions = (interactions,)
    elif (isinstance(interactions, (tuple, list)) and len(interactions) == 2
          and all(isinstance(value, str) for value in interactions)):
        interactions = (interactions,)
    normalized_pairs = []
    for interaction in interactions:
        if isinstance(interaction, str):
            parts = tuple(part.strip() for part in interaction.replace("×", "*").split("*"))
        elif isinstance(interaction, (tuple, list)):
            parts = tuple(interaction)
        else:
            raise ValueError("交互项必须由一个控制因子和一个噪声因子组成")
        if (len(parts) != 2 or parts[0] not in control_ids or parts[1] not in noise_ids
                or parts in normalized_pairs):
            raise ValueError("交互项必须唯一且属于控制因子×噪声因子")
        normalized_pairs.append(parts)
    normalized_pairs = tuple(normalized_pairs)

    def model_matrix(settings_rows, pairs):
        columns = [np.ones(len(settings_rows), dtype=float)]
        labels = ["截距"]
        for factor_id in (*control_ids, *noise_ids):
            factor = factor_map[factor_id]
            columns.append(np.asarray([
                -1.0 if row[factor_id] == factor.levels[0] else 1.0
                for row in settings_rows], dtype=float))
            labels.append(factor_id)
        coded = {factor_id: columns[index + 1]
                 for index, factor_id in enumerate((*control_ids, *noise_ids))}
        for control_id, noise_id in pairs:
            columns.append(coded[control_id] * coded[noise_id])
            labels.append(f"{control_id}×{noise_id}")
        return np.column_stack(columns), labels

    runs = sorted(design.runs, key=lambda run: run.standard_order)
    if any(run.responses[response] is None for run in runs):
        raise ValueError("响应存在缺失值，请填写全部运行")
    settings_rows = [run.settings for run in runs]
    base_matrix, base_labels = model_matrix(settings_rows, ())
    base_rank = int(np.linalg.matrix_rank(base_matrix))
    interaction_estimability = []
    for control_id in control_ids:
        for noise_id in noise_ids:
            matrix, _ = model_matrix(settings_rows, ((control_id, noise_id),))
            estimable = base_rank == base_matrix.shape[1] and \
                int(np.linalg.matrix_rank(matrix)) == matrix.shape[1]
            interaction_estimability.append({"interaction": f"{control_id}×{noise_id}",
                                             "estimable": estimable})
    matrix, labels = model_matrix(settings_rows, normalized_pairs)
    rank = int(np.linalg.matrix_rank(matrix))
    parameter_count = matrix.shape[1]
    n = len(runs)
    df = n - rank
    estimable = rank == parameter_count
    candidate_count = math.prod(len(factor_map[key].levels) for key in control_ids)
    if candidate_count > _MAX_TARGET_COMBINATIONS:
        raise ValueError(
            f"稳健搜索需枚举 {candidate_count} 个控制组合，超过预算 "
            f"{_MAX_TARGET_COMBINATIONS}；未完成优化")
    search_base = {"method": "declared two-level control combinations × declared noise conditions",
                   "candidate_count": candidate_count, "budget": _MAX_TARGET_COMBINATIONS,
                   "evaluation_count": 0, "search_complete": False,
                   "global_optimum": False}
    if not estimable:
        return {"design": design, "response": response, "interactions": normalized_pairs,
                "target_mean": target_mean, "target_tolerance": target_tolerance,
                "mean_range": mean_range,
                "coefficients": None, "rank": rank, "parameter_count": parameter_count,
                "residual_df": df, "residuals": None, "estimable": False,
                "interaction_estimability": interaction_estimability,
                "inference": None, "candidates": [], "best": None,
                "search": {**search_base, "stop_reason": "model_not_estimable"},
                "status": f"模型不可估计（秩 {rank}/{parameter_count}）；未搜索最优设置",
                "assumption": "控制与噪声均使用 −1/+1 编码；交互只含所选控制×噪声项。"}

    y = _finite([run.responses[response] for run in runs], "响应")
    beta, _, _, _ = np.linalg.lstsq(matrix, y, rcond=None)
    fitted = matrix @ beta
    residuals = y - fitted
    sse = float(residuals @ residuals)
    centered = y - float(y.mean())
    mse_floor = np.finfo(float).eps * max(n, parameter_count) * max(
        float(centered @ centered), 1.0)
    mse = sse / df if df > 0 else None
    inference = None
    if df > 0 and mse is not None and sse > mse_floor:
        covariance = np.linalg.inv(matrix.T @ matrix) * mse
        se = np.sqrt(np.diag(covariance))
        tcrit = float(stats.t.ppf(0.975, df))
        inference = [{"term": label, "estimate": float(value), "se": float(error),
                      "t": float(value / error),
                      "p": float(2 * stats.t.sf(abs(value / error), df)),
                      "ci_low": float(value - tcrit * error),
                      "ci_high": float(value + tcrit * error)}
                     for label, value, error in zip(labels, beta, se)]
    residual_rows = [{"run_id": run.run_id, "fitted": float(predicted),
                      "residual": float(residual)}
                     for run, predicted, residual in zip(runs, fitted, residuals)]
    model = {"coefficients": dict(zip(labels, map(float, beta))), "rank": rank,
             "parameter_count": parameter_count, "n": n, "residual_df": df,
             "sse": sse, "mse": mse, "residuals": residual_rows,
             "estimable": True, "inference": inference,
             "inference_status": ("OLS t 推断；误差独立、同方差且正态"
                                  if inference is not None else
                                  "残差自由度或误差方差不可用，推断不可用")}
    if df <= 0 or sse <= mse_floor:
        return {"design": design, "response": response, "interactions": normalized_pairs,
                "target_mean": target_mean, "target_tolerance": target_tolerance,
                "mean_range": mean_range, **model,
                "interaction_estimability": interaction_estimability,
                "candidates": [], "best": None,
                "search": {**search_base, "stop_reason": "no_estimable_error_variance"},
                "status": ("模型饱和或误差方差不可估；保留拟合结果，不生成最优设置"),
                "assumption": "残差自由度必须为正且误差方差可估；不对选点做置信度保证。"}

    noise_rows = []
    for codes in grid["noise"]:
        noise_rows.append({factor_id: factor_map[factor_id].levels[codes[index] - 1]
                           for index, factor_id in enumerate(noise_ids)})
    controls = [factor_map[key] for key in control_ids]
    observed = {tuple(run.settings[key] for key in control_ids) for run in runs}
    candidates = []
    for levels in product(*(factor.levels for factor in controls)):
        settings = dict(zip(control_ids, levels))
        condition_predictions = []
        for noise_settings in noise_rows:
            row_settings = {**settings, **noise_settings}
            row, _ = model_matrix([row_settings], normalized_pairs)
            condition_predictions.append(float(row[0] @ beta))
        predicted_mean = math.fsum(condition_predictions) / len(condition_predictions)
        noise_variance = math.fsum((value - predicted_mean) ** 2
                                   for value in condition_predictions) / len(condition_predictions)
        variance = noise_variance + mse
        deviation = (None if target_mean is None else predicted_mean - target_mean)
        if mean_range is not None:
            deviation = (mean_range[0] - predicted_mean if predicted_mean < mean_range[0]
                         else predicted_mean - mean_range[1] if predicted_mean > mean_range[1]
                         else 0.0)
        candidates.append({"settings": settings, "predicted_mean": predicted_mean,
                           "noise_variance": noise_variance,
                           "residual_variance": mse, "predicted_variance": variance,
                           "predicted_sd": math.sqrt(max(0.0, variance)),
                           "target_deviation": deviation,
                           "observed_control_setting": tuple(levels) in observed})
    if mean_range is not None:
        eligible = [item for item in candidates if item["target_deviation"] == 0]
    elif target_mean is not None and target_tolerance is not None:
        eligible = [item for item in candidates
                    if abs(item["target_deviation"]) <= target_tolerance]
    else:
        eligible = candidates
    unreachable = not eligible
    if unreachable:
        best = None
        tied = []
        reason = "mean_constraint_unreachable"
    elif target_mean is not None and target_tolerance is None:
        nearest = min(abs(item["target_deviation"]) for item in eligible)
        tol = math.ulp(max(1.0, abs(target_mean), nearest)) * (2 * len(control_ids) + 2)
        nearest_items = [item for item in eligible
                         if abs(abs(item["target_deviation"]) - nearest) <= tol]
        minimum = min(item["predicted_variance"] for item in nearest_items)
        best_scale = max(1.0, abs(minimum))
        best_tol = math.ulp(best_scale) * (2 * len(control_ids) + 2)
        tied = [item for item in nearest_items
                if abs(item["predicted_variance"] - minimum) <= best_tol]
        best, reason = tied[0]["settings"], "completed"
    else:
        minimum = min(item["predicted_variance"] for item in eligible)
        scale = max(1.0, abs(minimum))
        tol = math.ulp(scale) * (2 * len(control_ids) + 2)
        tied = [item for item in eligible
                if abs(item["predicted_variance"] - minimum) <= tol]
        best, reason = tied[0]["settings"], "completed"
    scope = ("声明二水平控制组合的精确枚举；噪声条件按声明水平组合等权"
             + ("；另以目标偏差优先、方差次序打破并列" if target_mean is not None
                and target_tolerance is None else ""))
    return {"design": design, "response": response, "interactions": normalized_pairs,
            "target_mean": target_mean, "target_tolerance": target_tolerance,
            "mean_range": mean_range, **model,
            "interaction_estimability": interaction_estimability,
            "candidates": candidates, "best": best, "tied_candidates": tied,
            "search": {**search_base, "evaluation_count": candidate_count,
                       "search_complete": True, "global_optimum": not unreachable,
                       "eligible_count": len(eligible), "stop_reason": reason,
                       "optimality_scope": scope},
            "status": (f"已完成 {candidate_count} 个控制组合的噪声条件搜索"
                       if not unreachable else "没有控制组合满足均值约束；未生成最优设置"),
            "assumption": ("噪声响应均值/方差按声明的噪声水平组合等权计算；"
                           "预测总方差等于条件间方差加残差均方；"
                           "推断要求误差独立、同方差且正态。")}


_METRICS = {"sn": "S/N", "mean": "目标均值", "sd": "最小 SD", "slope": "目标斜率"}
_MAX_TARGET_COMBINATIONS = 20_000


def _normalize_model_terms(spec, terms):
    controls = tuple(factor.factor_id for factor in spec.factors
                     if factor.factor_id in spec.taguchi["columns"])
    if terms is None:
        terms = tuple((factor_id,) for factor_id in controls)
    elif isinstance(terms, str):
        terms = (terms,)
    normalized = []
    for term in terms:
        if isinstance(term, str):
            term = tuple(part.strip() for part in term.replace("×", "*").split("*"))
        elif isinstance(term, (tuple, list)):
            term = tuple(term)
        else:
            raise ValueError("模型项必须是主效应或双因子交互项")
        if (len(term) not in (1, 2) or len(set(term)) != len(term)
                or any(factor_id not in controls for factor_id in term)):
            raise ValueError("模型项只能引用控制因子的主效应或双因子交互")
        term = tuple(sorted(term, key=controls.index))
        if term in normalized:
            raise ValueError("模型项不得重复")
        normalized.append(term)
    return tuple(sorted(normalized, key=lambda term: (len(term),
                                                       tuple(controls.index(key)
                                                             for key in term))))


def _taguchi_model_matrix(spec, settings_rows, terms):
    factors = {factor.factor_id: factor for factor in spec.factors}
    columns = [np.ones(len(settings_rows), dtype=float)]
    labels = ["截距"]
    for term in terms:
        contrast_levels = [factors[factor_id].levels[1:] for factor_id in term]
        for levels in product(*contrast_levels):
            values = np.ones(len(settings_rows), dtype=float)
            labels_for_column = []
            for factor_id, level in zip(term, levels):
                values *= np.asarray([row[factor_id] == level for row in settings_rows],
                                     dtype=float)
                labels_for_column.append(f"{factor_id}={level}")
            columns.append(values)
            labels.append(" × ".join(labels_for_column))
    return np.column_stack(columns), labels


def _fit_taguchi_model(design, response, terms):
    spec = design.spec
    if spec.taguchi["kind"] != "static" or spec.taguchi["signal_factor"] is not None:
        raise ValueError("分类响应模型仅支持无信号因子的静态 Taguchi 设计")
    if response not in spec.response_names:
        raise ValueError("响应不属于该设计")
    terms = _normalize_model_terms(spec, terms)
    runs = sorted(design.runs, key=lambda run: run.standard_order)
    if any(run.responses[response] is None for run in runs):
        raise ValueError("响应存在缺失值，请填写全部运行")
    settings_rows = [run.settings for run in runs]
    matrix, labels = _taguchi_model_matrix(spec, settings_rows, terms)
    y = _finite([run.responses[response] for run in runs], "响应")
    beta, _, rank, _ = np.linalg.lstsq(matrix, y, rcond=None)
    rank = int(rank)
    if rank != matrix.shape[1]:
        raise ValueError(f"所选模型项存在混杂或不可估计（秩 {rank}/{matrix.shape[1]}）")
    fitted = matrix @ beta
    residuals = y - fitted
    sse = float(residuals @ residuals)
    n, p = matrix.shape
    df = n - rank
    centered = y - float(y.mean())
    mse_floor = np.finfo(float).eps * max(n, p) * max(float(centered @ centered), 1.0)
    mse = sse / df if df > 0 else None
    inference = None
    if df > 0 and mse is not None and sse > mse_floor:
        covariance = np.linalg.inv(matrix.T @ matrix) * mse
        standard_errors = np.sqrt(np.diag(covariance))
        critical = float(stats.t.ppf(0.975, df))
        inference = [{"term": label, "estimate": float(value),
                      "se": float(se), "t": float(value / se),
                      "p": float(2 * stats.t.sf(abs(value / se), df)),
                      "ci_low": float(value - critical * se),
                      "ci_high": float(value + critical * se)}
                     for label, value, se in zip(labels, beta, standard_errors)]
    if df <= 0:
        inference_status = "残差自由度不足，无法估计误差方差"
    elif inference is None:
        inference_status = "残差方差为零或数值上不可辨，推断不可用"
    else:
        inference_status = "OLS t 推断；假设误差独立、同方差且正态"
    return {"design": design, "terms": terms, "column_names": labels,
            "matrix": matrix,
            "coefficients_array": beta, "coefficients": dict(zip(labels, map(float, beta))),
            "rank": rank, "parameter_count": p, "n": n, "df": df, "sse": sse,
            "mse": mse, "mse_floor": float(mse_floor), "fitted": fitted,
            "residuals": residuals, "estimable": True, "inference": inference,
            "inference_status": inference_status}


def _taguchi_model_summary(model):
    return {key: model[key] for key in (
        "terms", "column_names", "coefficients", "rank", "parameter_count", "n",
        "df", "sse", "mse", "estimable", "inference", "inference_status") } | {
            "fitted": [float(value) for value in model["fitted"]],
            "residuals": [float(value) for value in model["residuals"]],
            "run_ids": [run.run_id for run in sorted(
                model["design"].runs, key=lambda run: run.standard_order)]}


def _confidence_level(confidence):
    if (isinstance(confidence, bool) or confidence not in (0.9, 0.95, 0.99)):
        raise ValueError("均值置信水平必须为 90%、95% 或 99%")
    return float(confidence)


def _taguchi_mean_ci(model, settings, confidence):
    confidence = _confidence_level(confidence)
    row, _ = _taguchi_model_matrix(model["design"].spec, [settings], model["terms"])
    from doe_predict import _prediction_intervals
    analysis = {"design": model["design"], "df": model["df"],
                "residual_mse": model["mse"], "sse": model["sse"],
                "mse_floor": model["mse_floor"], "matrix": model["matrix"],
                "coefficients": model["coefficients_array"]}
    result = _prediction_intervals(analysis, row[0], confidence, "two_sided")
    result["assumption"] = (
        "分类因子 OLS 均值区间；误差独立、同方差且正态；未校正最优点选择偏差。")
    return result


def predict_taguchi_model(frame, metadata, response, settings, terms=None,
                          confidence=0.95):
    """按选定的分类主效应/交互模型预测一个指定控制组合。"""
    design = restore_design_result(frame, metadata)
    grid = taguchi_grid(design.spec)
    control_ids = tuple(factor.factor_id for factor in design.spec.factors
                        if factor.factor_id in grid["columns"])
    if not isinstance(settings, dict) or set(settings) != set(control_ids):
        raise ValueError("指定预测必须且只能包含全部控制因子")
    for factor_id in control_ids:
        if settings[factor_id] not in grid["factors"][factor_id].levels:
            raise ValueError(f"因子 {factor_id} 的水平不在已声明范围内")
    model = _fit_taguchi_model(design, response, terms)
    row, _ = _taguchi_model_matrix(design.spec, [settings], model["terms"])
    predicted = float(row[0] @ model["coefficients_array"])
    intervals = _taguchi_mean_ci(model, settings, confidence)
    summary = _taguchi_model_summary(model)
    summary["settings"] = dict(settings)
    return {"response": response, "settings": dict(settings),
            "prediction": predicted, "intervals": intervals,
            "model": summary,
            "assumption": "模型条件均值预测；普通置信区间未校正点选择偏差。"}


def _model_target_settings(design, response, terms, target, confidence):
    model = _fit_taguchi_model(design, response, terms)
    spec = design.spec
    control_ids = tuple(factor.factor_id for factor in spec.factors
                        if factor.factor_id in spec.taguchi["columns"])
    factors = {factor.factor_id: factor for factor in spec.factors}
    level_rows = [factors[factor_id].levels for factor_id in control_ids]
    candidate_count = math.prod(map(len, level_rows))
    if candidate_count > _MAX_TARGET_COMBINATIONS:
        raise ValueError(
            f"目标搜索需要精确枚举 {candidate_count} 个控制组合，超过预算 "
            f"{_MAX_TARGET_COMBINATIONS}；未执行搜索，无法声明模型最优设置")
    settings_rows = [dict(zip(control_ids, levels)) for levels in product(*level_rows)]
    matrix, _ = _taguchi_model_matrix(spec, settings_rows, model["terms"])
    predictions = matrix @ model["coefficients_array"]
    distances = np.abs(predictions - target)
    minimum = float(distances.min())
    tied = []
    for settings, prediction, distance in zip(settings_rows, predictions, distances):
        tolerance = math.ulp(max(1.0, abs(target), abs(float(prediction)))) * (
            2 * len(control_ids) + 2)
        if abs(float(distance) - minimum) <= tolerance:
            tied.append({"settings": settings, "predicted": float(prediction),
                         "distance": float(distance)})
    best = tied[0]["settings"]
    per_factor = {
        factor_id: {"value": None,
                    "levels": [level for level in factors[factor_id].levels
                               if any(item["settings"][factor_id] == level for item in tied)],
                    "tied": False}
        for factor_id in control_ids}
    for value in per_factor.values():
        value["tied"] = len(value["levels"]) > 1
    ci = _taguchi_mean_ci(model, best, confidence)
    observed = any(all(run.settings[key] == best[key] for key in control_ids)
                   for run in design.runs)
    return {"model": _taguchi_model_summary(model), "best": best, "tied": per_factor,
            "tied_combinations": tied, "predicted_mean": tied[0]["predicted"],
            "mean_ci": ci, "is_observed": observed,
            "search": {"method": "full-rank categorical OLS with exact finite enumeration",
                       "candidate_count": candidate_count, "budget": _MAX_TARGET_COMBINATIONS,
                       "evaluation_count": candidate_count, "stop_reason": "completed",
                       "global_optimum": True,
                       "optimality_scope": "declared control levels under the selected OLS model",
                       "tie_rule": "factor and declared level order; first tied combination selected"}}


def create_confirmation_frame(frame, metadata, result, source_sheet):
    """复制原始试验并追加独立的确认试验计划行；不返回 DOE 元数据。"""
    import pandas as pd

    if result.get("source_snapshot_id"):
        from doe_predict import snapshot_id
        if snapshot_id(frame, metadata) != result["source_snapshot_id"]:
            raise ValueError("来源试验数据已更改；请重新分析并生成最佳设置")
    design = restore_design_result(frame, metadata)
    if result["best"] is None:
        raise ValueError("没有可用的推荐设置，无法创建确认实验工作表")
    spec = design.spec
    grid = taguchi_grid(spec)
    columns = metadata["column_map"]

    def unique_column(base):
        name, index = base, 2
        while name in frame.columns:
            name = f"{base} ({index})"
            index += 1
        return name

    source_design_column = unique_column("DOE 来源设计ID")
    source_sheet_column = unique_column("DOE 来源工作表")
    trial_type_column = unique_column("DOE 试验类型")
    source_run_column = unique_column("DOE 来源运行ID")
    original = frame.copy(deep=True).reset_index(drop=True)
    original[source_design_column] = spec.design_id
    original[source_sheet_column] = source_sheet
    original[trial_type_column] = "原始运行"
    original[source_run_column] = original[columns["run_id"]]

    noise_factors = sorted(grid["noise_columns"].items())
    noise_rows = grid["noise"]
    signal_levels = grid["signal_levels"] or (None,)
    existing_ids = set(original[columns["run_id"]].astype(str))
    next_standard = int(original[columns["standard_order"]].max())
    next_run = int(original[columns["run_order"]].max())
    additions = []
    for index, (noise_codes, signal) in enumerate(
            ((noise, signal) for noise in noise_rows for signal in signal_levels), 1):
        run_id = f"C{index:05d}"
        while run_id in existing_ids:
            run_id = "C" + run_id
        existing_ids.add(run_id)
        settings = dict(result["best"])
        for position, (factor_id, _) in enumerate(noise_factors):
            factor = grid["factors"][factor_id]
            settings[factor_id] = factor.levels[noise_codes[position] - 1]
        if spec.taguchi["signal_factor"] is not None:
            settings[spec.taguchi["signal_factor"]] = signal
        noise_id = "N" + "".join(str(code) for code in noise_codes) + "R1"
        row = {column: None for column in original.columns}
        row[columns["run_id"]] = run_id
        row[columns["standard_order"]] = next_standard + index
        row[columns["run_order"]] = next_run + index
        row[columns["point_type"]] = "confirmation"
        row[columns["replicate"]] = 1
        row[columns["control_run_id"]] = "CONF00001"
        row[columns["noise_condition_id"]] = noise_id
        row.update({column: settings[factor_id]
                    for factor_id, column in columns["factors"].items()})
        row.update({column: None for column in columns["responses"].values()})
        row.update({column: None for column in columns["measured_levels"].values()})
        row[source_design_column] = spec.design_id
        row[source_sheet_column] = source_sheet
        row[trial_type_column] = "确认试验"
        row[source_run_column] = None
        additions.append(row)
    result_frame = pd.concat((original, pd.DataFrame(additions)), ignore_index=True)
    for column in (*columns["responses"].values(), *columns["measured_levels"].values()):
        dtype = frame[column].dtype
        if pd.api.types.is_integer_dtype(dtype):
            target = "UInt64" if pd.api.types.is_unsigned_integer_dtype(dtype) else "Int64"
        elif pd.api.types.is_float_dtype(dtype):
            target = "Float64"
        else:
            target = dtype
        result_frame[column] = pd.array(result_frame[column], dtype=target)
    return result_frame


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
                  sn_threshold=None, model_terms=None, confidence=0.95):
    """按指标体系选水平；默认沿用加性主效应预测，可选分类 OLS 项。"""
    design = restore_design_result(frame, metadata)
    spec = design.spec
    dynamic = spec.taguchi["kind"] == "dynamic"
    confidence = _confidence_level(confidence)
    selected_model = model_terms is not None
    if selected_model:
        if dynamic or metric != "mean" or selection_mode is not None:
            raise ValueError("交互模型搜索仅适用于静态设计的目标均值")
        model_terms = _normalize_model_terms(spec, model_terms)
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
    if selected_model:
        selected = _model_target_settings(design, response, model_terms, target, confidence)
        best, tied = selected["best"], selected["tied"]
        tied_combinations, search = selected["tied_combinations"], selected["search"]
        model = selected["model"]
        mean_ci = selected["mean_ci"]
    else:
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
        model, mean_ci = None, None
        if not dynamic:
            try:
                fit = _fit_taguchi_model(design, response, None)
                model = _taguchi_model_summary(fit)
                if best is not None:
                    mean_ci = _taguchi_mean_ci(fit, best, confidence)
            except (ValueError, np.linalg.LinAlgError):
                model = None
        if mean_ci is None:
            mean_ci = {"status": "不可用", "reason": (
                "动态设计或所选主效应模型秩亏，无法计算均值置信区间"),
                "confidence": confidence, "ci_low": None, "ci_high": None}
    observed_settings = [row["settings"] for row in combinations]
    is_observed = (None if best is None else
                   any(all(settings[key] == best[key] for key in best)
                       for settings in observed_settings))
    predicted_sd = (None if best is None or selected_model else
                    _additive_prediction(table, combinations, "sd", best))
    predicted_sd_reason = None
    if best is None:
        predicted_sd_reason = "没有组合满足最低 S/N，未生成推荐设置"
    elif selected_model:
        predicted_sd_reason = "所选均值模型未拟合标准差"
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
                 selected["predicted_mean"] if selected_model else
                 _additive_prediction(table, combinations, "mean", best)),
        "sn": (None if best is None or selected_model else
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
    if selected_model:
        status = (f"按所选分类 OLS 模型在 {search['candidate_count']} 个控制组合中"
                  f"搜索目标均值 {target:g}；{len(tied_combinations)} 个并列最优预测")
    elif selection_mode == "sn_maximum":
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
    from doe_predict import snapshot_id
    return {
        "design": design, "response": response, "metric": metric,
        "source_snapshot_id": snapshot_id(frame, metadata),
        "target": target, "tolerance": tolerance, "best": best,
        "selection_mode": selection_mode, "sn_threshold": sn_threshold,
        "model_terms": model_terms if selected_model else None,
        "model": model, "confidence": confidence, "mean_ci": mean_ci,
        "status_code": (search["status_code"] if selection_mode is not None else "ok"),
        "tied": tied, "table": table,
        "is_observed": is_observed, "predicted": predicted,
        "predicted_mean": predicted["mean"], "predicted_sn": predicted["sn"],
        "predicted_sd": predicted["sd"], "predicted_slope": predicted["slope"],
        "confirmation": {
            "settings": best, "predicted_mean": predicted["mean"],
            "mean_ci": mean_ci,
            "predicted_sn": predicted["sn"], "observed": observed,
            "difference": difference, "meets_target": meets,
            "tolerance": tolerance,
        },
        "tied_combinations": tied_combinations,
        "search": search,
        "predicted_sd_reason": predicted_sd_reason,
        "status": status,
        "assumption": (("预测依赖所选分类 OLS 模型；区间基于残差自由度与模型协方差，"
                        "不校正搜索最优点产生的选择偏差。" if selected_model else
                        "预测依赖控制因子主效应可加、无显著交互混杂；"
                        "均值区间未校正最优点选择偏差。")
                       + "确认试验不修改原始正交表运行"),
    }
