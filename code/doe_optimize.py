"""完整 CCD 二次响应面的有界确定性多起点优化。"""
from collections.abc import Mapping
from itertools import product
import math
from numbers import Real

import numpy as np
from scipy.optimize import minimize
from scipy.special import expit

import doe_ccd
import doe_rsm
from doe_predict import snapshot_id as _snapshot_id


_TARGET_TOLERANCE = 1e-8
_MAX_EVALUATIONS_PER_START = 200
# shortcut: cap full category enumeration at 32 combinations; revisit if larger designs are measured as responsive.
_BINARY_CATEGORY_COMBINATION_LIMIT = 32
# shortcut: cap each local start at 100 calls; revisit if representative designs repeatedly exhaust this budget.
_BINARY_EVALUATIONS_PER_START = 100


def _finite(value, name):
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError(f"{name} 必须是有限数值")
    try:
        result = float(value)
    except (OverflowError, TypeError, ValueError) as error:
        raise ValueError(f"{name} 必须是有限数值") from error
    if not math.isfinite(result):
        raise ValueError(f"{name} 必须是有限数值")
    return result


def _normalize_objectives(objectives):
    required = {"mode", "low", "high", "target", "power_low", "power_high", "weight"}
    if not isinstance(objectives, Mapping) or not objectives:
        raise ValueError("objectives 必须是非空的响应配置映射")
    result = {}
    for name, config in objectives.items():
        if not isinstance(name, str) or not name or not isinstance(config, Mapping):
            raise ValueError("响应名必须是非空字符串，配置必须是映射")
        if set(config) != required:
            raise ValueError(f"响应 {name} 必须且只能包含 {sorted(required)}")
        mode = config["mode"]
        if mode not in ("maximize", "minimize", "target"):
            raise ValueError(f"响应 {name} 的 mode 无效")
        low = _finite(config["low"], f"响应 {name} low")
        high = _finite(config["high"], f"响应 {name} high")
        if low >= high:
            raise ValueError(f"响应 {name} 必须满足 low < high")
        target = None if config["target"] is None else _finite(
            config["target"], f"响应 {name} target")
        if mode == "target":
            if target is None or not low < target < high:
                raise ValueError(f"响应 {name} 的 target 必须严格位于 low 与 high 之间")
        elif target is not None:
            raise ValueError(f"响应 {name} 只有 target 模式可以设置 target")
        power_low = _finite(config["power_low"], f"响应 {name} power_low")
        power_high = _finite(config["power_high"], f"响应 {name} power_high")
        weight = _finite(config["weight"], f"响应 {name} weight")
        if min(power_low, power_high, weight) <= 0:
            raise ValueError(f"响应 {name} 的 power 和 weight 必须大于 0")
        result[name] = {
            "mode": mode, "low": low, "high": high, "target": target,
            "power_low": power_low, "power_high": power_high, "weight": weight,
        }
    return result


def _coded_bounds(factors, bounds):
    if bounds is not None and not isinstance(bounds, Mapping):
        raise ValueError("bounds 必须是因子编码范围映射或 None")
    bounds = {} if bounds is None else bounds
    factor_ids = {factor.factor_id for factor in factors}
    if set(bounds) - factor_ids:
        raise ValueError("bounds 含未知因子")
    result = {}
    for factor in factors:
        pair = bounds.get(factor.factor_id, (-1.0, 1.0))
        if not isinstance(pair, (tuple, list)) or len(pair) != 2:
            raise ValueError(f"因子 {factor.factor_id} 的 bounds 必须是两个编码值")
        low = _finite(pair[0], f"因子 {factor.factor_id} bounds low")
        high = _finite(pair[1], f"因子 {factor.factor_id} bounds high")
        if low > high:
            raise ValueError(f"因子 {factor.factor_id} bounds 必须有序")
        if low < -1 or high > 1:
            raise ValueError(f"因子 {factor.factor_id} bounds 只能收紧到 [-1, 1] 内")
        if low < high and high - low <= 8 * math.ulp(max(1.0, abs(low), abs(high))):
            raise ValueError(f"因子 {factor.factor_id} bounds 区间小于可分辨范围")
        result[factor.factor_id] = (low, high)
    return result


def _model_value_gradient(coefficients, coded):
    """用 RSM 正式模型矩阵预测，并按其项顺序求二次模型解析梯度。"""
    coded = np.asarray(coded, dtype=float)
    coefficients = np.asarray(coefficients, dtype=float)
    k = len(coded)
    with np.errstate(over="ignore", invalid="ignore"):
        row = np.asarray(doe_rsm.model_matrix(coded.reshape(1, -1)), dtype=float)[0]
        value = float(row @ coefficients)
        gradient = coefficients[1:k + 1] + 2 * coefficients[k + 1:2 * k + 1] * coded
        index = 1 + 2 * k
        for i in range(k):
            for j in range(i + 1, k):
                gradient[i] += coefficients[index] * coded[j]
                gradient[j] += coefficients[index] * coded[i]
                index += 1
    return value, gradient


def _term_value_gradient(model, coefficients, coded, block=None):
    """用正式模型项求值；分类与区组项固定为参考水平，不送入连续求解变量。"""
    coefficients = np.asarray(coefficients, dtype=float)
    row = model.row(coded, block)
    value = float(row @ coefficients)
    continuous = model.continuous()
    index = {name: i for i, name in enumerate(continuous)}
    gradient = np.zeros(len(continuous))
    for column, coefficient in zip(model.columns[1:], coefficients[1:]):
        name, spec = column
        if spec is None:
            if name.endswith('²'):
                gradient[index[name[:-1]]] += 2 * coefficient * coded[name[:-1]]
            elif '*' in name:
                first, second = name.split('*')
                gradient[index[first]] += coefficient * coded[second]
                gradient[index[second]] += coefficient * coded[first]
            else:
                gradient[index[name]] += coefficient
            continue
        if spec[0] == 'block':
            continue
        term, level = spec
        category = next(part for part in term.split('*')
                        if model.by_id[part].factor_type == 'categorical')
        if coded[category] != level:
            continue
        if '*' in term:
            other = next(part for part in term.split('*') if part != category)
            gradient[index[other]] += coefficient
    return value, gradient


def _response_model(result, config):
    coefficients = np.asarray(result["coefficients"], dtype=float)
    variable_scale = float(np.max(np.abs(coefficients[1:])))
    if variable_scale == 0:
        variable_scale = 1.0
    objective_scale = variable_scale
    if config["mode"] == "target":
        offset = coefficients[0] - config["target"]
        offset_scale = (abs(offset) if math.isfinite(offset)
                        else max(abs(coefficients[0]), abs(config["target"])))
        objective_scale = max(objective_scale, offset_scale)
        if objective_scale == 0:
            objective_scale = 1.0
    objective_coefficients = coefficients / objective_scale
    if config["mode"] in ("maximize", "minimize"):
        objective_coefficients[0] = 0.0
    scale = max(
        1.0, float(np.max(np.abs(coefficients))), abs(config["low"]),
        abs(config["high"]), abs(config["target"]) if config["target"] is not None else 0.0,
    )
    normalized = {key: value / scale for key, value in config.items()
                  if key in ("low", "high", "target") and value is not None}
    if normalized["high"] <= normalized["low"]:
        raise ValueError("响应 low/high 超出 binary64 优化分辨率")
    if normalized["high"] - normalized["low"] <= 4 * max(
            math.ulp(normalized["low"]), math.ulp(normalized["high"])):
        raise ValueError("响应 low/high 区间小于 binary64 可分辨范围")
    if config["target"] is not None and not (
            normalized["low"] < normalized["target"] < normalized["high"]):
        raise ValueError("响应 target 超出 binary64 优化分辨率")
    return {"coefficients": coefficients, "normalized_coefficients": coefficients / scale,
            "objective_coefficients": objective_coefficients,
            "objective_scale": objective_scale,
            "scale": scale, "config": config, "normalized": normalized}


def _raw_desirability(y, model):
    config, limits = model["config"], model["normalized"]
    low, high = limits["low"], limits["high"]
    mode = config["mode"]
    with np.errstate(over="ignore", divide="ignore", invalid="ignore"):
        if mode == "maximize":
            raw, slope = (y - low) / (high - low), 1.0 / (high - low)
        elif mode == "minimize":
            raw, slope = (high - y) / (high - low), -1.0 / (high - low)
        else:
            target = limits["target"]
            if y == target:
                return 1.0, 0.0, config["power_low"]
            if y < target:
                raw, slope = (y - low) / (target - low), 1.0 / (target - low)
            else:
                raw, slope = (high - y) / (high - target), -1.0 / (high - target)
    if not math.isfinite(raw):
        raw = math.copysign(1e12, raw if not math.isnan(raw) else y - low)
    if not math.isfinite(slope):
        raise ValueError("响应 desirability 范围超出 binary64 优化分辨率")
    power = (config["power_low"] if mode == "maximize" or
             (mode == "target" and y < limits["target"])
             else config["power_high"])
    return max(-1e12, min(1e12, float(raw))), float(slope), power


def _desirability_info(y, model):
    config, limits = model["config"], model["normalized"]
    low, high = limits["low"], limits["high"]
    mode = config["mode"]
    if mode == "maximize":
        if y <= low:
            return 0.0, None, True
        if y >= high:
            return 1.0, 0.0, False
        base, power = (y - low) / (high - low), config["power_low"]
    elif mode == "minimize":
        if y <= low:
            return 1.0, 0.0, False
        if y >= high:
            return 0.0, None, True
        base, power = (high - y) / (high - low), config["power_high"]
    else:
        target = limits["target"]
        if y <= low or y >= high:
            return 0.0, None, True
        if y <= target:
            base, power = (y - low) / (target - low), config["power_low"]
        else:
            base, power = (high - y) / (high - target), config["power_high"]
    log_value = power * math.log(base)
    if not math.isfinite(log_value):
        return 0.0, None, True
    value = math.exp(log_value) if log_value > math.log(np.nextafter(0.0, 1.0)) else 0.0
    return value, log_value, False


def _score(predictions, models):
    details = {
        name: _desirability_info(predictions[name] / model["scale"], model)
        for name, model in models.items()
    }
    desirabilities = {name: item[0] for name, item in details.items()}
    weights = {name: model["config"]["weight"] for name, model in models.items()}
    weight_scale = max(weights.values())
    normalized_weights = {name: weight / weight_scale for name, weight in weights.items()}
    weight_total = sum(normalized_weights.values())
    if any(item[2] for item in details.values()):
        return desirabilities, 0.0, None
    log_value = sum((normalized_weights[name] / weight_total) * details[name][1]
                    for name in details)
    composite = math.exp(log_value) if log_value > math.log(np.nextafter(0.0, 1.0)) else 0.0
    return desirabilities, composite, float(log_value)


def _target_reached(prediction, model):
    config = model["config"]
    if config["mode"] != "target":
        return True
    target = config["target"]
    scale = model["objective_scale"]
    return abs(prediction / scale - target / scale) <= _TARGET_TOLERANCE * max(
        1.0, abs(target / scale))


def _candidate_rank(candidate, objectives):
    if len(objectives) == 1:
        config = next(iter(objectives.values()))
        if config["mode"] in ("maximize", "minimize"):
            return (candidate["objective_value"],)
        if config["mode"] == "target":
            return (-candidate["target_difference_normalized"],
                    candidate["composite_desirability"])
    log_score = candidate["log_composite_desirability"]
    return (candidate["composite_desirability"],
            log_score if log_score is not None else -math.inf)


def optimize_rsm(frame, metadata, objectives, bounds=None, categories=None):
    """优化响应面（CCD 或 Box-Behnken）。

    objectives 每项必须包含 mode/low/high/target/power_low/power_high/weight。
    多响应评分使用 Derringer-Suich desirability 的加权几何平均；bounds 是
    [-1, 1] 编码域的收紧范围，等值上下界表示固定因子。分类因子不是连续
    变量：categories 指定其水平，缺省取第一个水平，并在结果中报告。
    """
    objectives = _normalize_objectives(objectives)
    analyses = {}
    for name in objectives:
        result = doe_rsm.analyze_rsm(frame, metadata, name)
        coded = np.asarray(doe_rsm.validate_design(result["design"]), dtype=float)
        if not np.array_equal(coded, np.asarray(result["coded"], dtype=float)):
            raise ValueError("RSM 编码与已验证设计设定不一致")
        analyses[name] = result

    design = analyses[next(iter(analyses))]["design"]
    all_factors = design.spec.factors
    factors = [factor for factor in all_factors
               if factor.factor_type == "continuous"]
    categorical = [factor for factor in all_factors
                   if factor.factor_type == "categorical"]
    fixed_categories = {}
    for factor in categorical:
        level = (categories or {}).get(factor.factor_id, factor.levels[0])
        if level not in factor.levels:
            raise ValueError(f"分类因子 {factor.factor_id} 的水平不在已声明范围内")
        fixed_categories[factor.factor_id] = level
    if categories:
        unknown = set(categories) - {factor.factor_id for factor in categorical}
        if unknown:
            raise ValueError("categories 含未知或非分类因子")
    coded_limits = _coded_bounds(factors, bounds)
    models = {name: _response_model(analyses[name], objectives[name])
              for name in objectives}
    factor_ids = [factor.factor_id for factor in factors]
    limits = [coded_limits[factor_id] for factor_id in factor_ids]
    free = [i for i, (low, high) in enumerate(limits) if low < high]
    fixed = np.array([(low + high) / 2 for low, high in limits], dtype=float)

    def evaluate(point):
        point = np.asarray(point, dtype=float)
        settings = {factor.factor_id: float(value)
                    for factor, value in zip(factors, point)}
        settings.update(fixed_categories)
        predictions, normalized_predictions, gradients = {}, {}, {}
        objective_predictions, objective_gradients = {}, {}
        for name, model in models.items():
            with np.errstate(over="ignore", invalid="ignore"):
                term_model = analyses[name]["term_model"]
                # 区组项按参考区组（第 1 组）评估，区组不作为连续变量搜索。
                block = 1 if term_model.blocks > 1 else None
                value, _ = _term_value_gradient(
                    term_model, model["coefficients"], settings, block)
                scaled, gradient = _term_value_gradient(
                    term_model, model["normalized_coefficients"], settings, block)
                objective_value, objective_gradient = _term_value_gradient(
                    term_model, model["objective_coefficients"], settings, block)
            if (not math.isfinite(value) or not math.isfinite(scaled)
                    or not np.isfinite(gradient).all() or not math.isfinite(objective_value)
                    or not np.isfinite(objective_gradient).all()):
                return None
            predictions[name] = value
            normalized_predictions[name] = scaled
            gradients[name] = gradient
            objective_predictions[name] = objective_value
            objective_gradients[name] = objective_gradient
        return (predictions, normalized_predictions, gradients,
                objective_predictions, objective_gradients)

    def solver_objective(free_point):
        point = fixed.copy()
        if free:
            point[free] = free_point
        evaluated = evaluate(point)
        if evaluated is None:
            return 1e100, np.zeros(len(free))
        _, normalized_predictions, gradients, objective_predictions, objective_gradients = evaluated
        if len(models) == 1:
            name, model = next(iter(models.items()))
            mode = model["config"]["mode"]
            if mode in ("maximize", "minimize"):
                sign = -1.0 if mode == "maximize" else 1.0
                return (sign * objective_predictions[name],
                        sign * objective_gradients[name][free])
            if mode == "target":
                residual = (objective_predictions[name]
                            - model["config"]["target"] / model["objective_scale"])
                return residual * residual, 2 * residual * objective_gradients[name][free]
        desirability_data = {}
        weight_scale = max(model["config"]["weight"] for model in models.values())
        normalized_weights = {
            name: model["config"]["weight"] / weight_scale for name, model in models.items()
        }
        weight_total = sum(normalized_weights.values())
        for name, model in models.items():
            raw, slope, power = _raw_desirability(normalized_predictions[name], model)
            desirability_data[name] = (raw, slope, power)
        value = 0.0
        gradient = np.zeros(len(free), dtype=float)
        for name, model in models.items():
            raw, slope, power = desirability_data[name]
            weight = normalized_weights[name]
            # This finite extension lets starts escape d=0; final scores use exact d.
            epsilon = 1e-12
            if raw < 0:
                term = power * (math.log(epsilon) + raw / epsilon)
                derivative = power / epsilon
            elif raw >= 1:
                term = power * math.log(1 + epsilon)
                derivative = 0.0
            else:
                term = power * math.log(epsilon + raw)
                derivative = power / (epsilon + raw)
            value -= weight * term
            if free:
                gradient -= weight * derivative * slope * gradients[name][free]
        value /= weight_total
        gradient /= weight_total
        if not math.isfinite(value) or not np.isfinite(gradient).all():
            return 1e100, np.zeros(len(free))
        return float(value), gradient

    start_axes = [tuple(sorted({low, (low + high) / 2, high})) for low, high in limits]
    if len(free) <= 5:
        starts = list(product(*(start_axes[i] for i in free))) if free else [()]
    else:
        axes = [start_axes[i] for i in free]
        middle = tuple(axis[1] for axis in axes)
        starts = [middle, tuple(axis[0] for axis in axes),
                  tuple(axis[-1] for axis in axes)]
        for i, axis in enumerate(axes):
            for edge in (axis[0], axis[-1]):
                point = list(middle)
                point[i] = edge
                starts.append(tuple(point))
    single = next(iter(objectives.items())) if len(objectives) == 1 else None

    candidate_records = []

    def reject_candidate(point, solver_success, candidate_type, reason):
        point = np.asarray(point, dtype=float)
        codes = ({factor_id: float(value) for factor_id, value in zip(factor_ids, point)}
                 if point.shape == (len(factors),) else {})
        candidate_records.append({
            "feasible": False, "coded": codes, "factor_levels": {},
            "factor_encoding_errors": {}, "predictions": {}, "desirabilities": {},
            "composite_desirability": None, "log_composite_desirability": None,
            "objective_value": None, "solver_success": bool(solver_success),
            "candidate_type": candidate_type, "status": reason,
            "target_difference": None, "target_difference_normalized": None,
        })
        return None

    def add_candidate(point, solver_success=False, candidate_type="solver result"):
        point = np.asarray(point, dtype=float)
        if (point.shape != (len(factors),) or not np.isfinite(point).all()
                or any(not low <= value <= high
                       for value, (low, high) in zip(point, limits))):
            return reject_candidate(point, solver_success, candidate_type,
                                    "候选点非有限、维数无效或超出 bounds")
        evaluated = evaluate(point)
        if evaluated is None:
            return reject_candidate(point, solver_success, candidate_type,
                                    "完整二次模型预测或梯度非有限")
        predictions, normalized_predictions, _, _, _ = evaluated
        desires, composite, log_composite = _score(predictions, models)
        actual, encoding_errors = {}, {}
        try:
            for factor, value in zip(factors, point):
                actual_value = float(factor.from_coded(float(value)))
                if (not math.isfinite(actual_value)
                        or not factor.low <= actual_value <= factor.high):
                    return reject_candidate(point, solver_success, candidate_type,
                                            f"因子 {factor.factor_id} 实际值不可行")
                reencoded = float(factor.to_coded(actual_value))
                error = abs(reencoded - float(value))
                if not math.isfinite(error) or error > 1e-8:
                    return reject_candidate(point, solver_success, candidate_type,
                                            f"因子 {factor.factor_id} 编码往返误差超限")
                actual[factor.factor_id] = actual_value
                encoding_errors[factor.factor_id] = error
            actual.update(fixed_categories)
        except (OverflowError, ValueError):
            return reject_candidate(point, solver_success, candidate_type,
                                    "实际水平转换或编码复核失败")
        objective_value = composite
        target_difference = target_difference_normalized = None
        if single:
            name, config = single
            prediction = predictions[name]
            if config["mode"] == "maximize":
                objective_value = prediction
            elif config["mode"] == "minimize":
                objective_value = -prediction
            elif config["mode"] == "target":
                scale = models[name]["objective_scale"]
                target_difference_normalized = abs(
                    prediction / scale - config["target"] / scale)
                difference = prediction - config["target"]
                target_difference = abs(difference) if math.isfinite(difference) else None
                objective_value = target_difference_normalized ** 2
        candidate = {
            "feasible": True,
            "coded": {factor_id: float(value) for factor_id, value in zip(factor_ids, point)},
            "factor_levels": actual,
            "factor_encoding_errors": encoding_errors,
            "predictions": predictions,
            "desirabilities": desires,
            "composite_desirability": composite,
            "log_composite_desirability": log_composite,
            "objective_value": objective_value,
            "solver_success": bool(solver_success),
            "candidate_type": candidate_type,
            "status": ("已收敛" if solver_success else
                       "确定性起点" if candidate_type == "起点" else "优化器未收敛"),
            "target_difference": target_difference,
            "target_difference_normalized": target_difference_normalized,
        }
        candidate_records.append(candidate)
        return candidate

    solver_successes = solver_evaluations = 0
    evaluation_limit_hit = False
    solver_failures = []
    class EvaluationLimit(Exception):
        pass

    if not free:
        solver_successes = int(add_candidate(fixed, True, "固定点") is not None)
    else:
        for start in starts:
            start = np.asarray(start, dtype=float)
            full_start = fixed.copy()
            full_start[free] = start
            add_candidate(full_start, candidate_type="起点")
            evaluations_used = 0

            def bounded_objective(point):
                nonlocal evaluations_used
                if evaluations_used >= _MAX_EVALUATIONS_PER_START:
                    raise EvaluationLimit
                evaluations_used += 1
                return solver_objective(point)

            try:
                result = minimize(
                    bounded_objective if len(free) > 5 else solver_objective,
                    start, jac=True, method="L-BFGS-B",
                    bounds=[limits[i] for i in free],
                    options={"maxiter": 300, "maxfun": _MAX_EVALUATIONS_PER_START,
                             "ftol": 1e-13, "gtol": 1e-9, "maxls": 40},
                )
            except EvaluationLimit:
                solver_evaluations += evaluations_used
                evaluation_limit_hit = True
                solver_failures.append("函数评价达到上限")
                continue
            except (FloatingPointError, ValueError, OverflowError):
                if len(free) > 5:
                    solver_evaluations += evaluations_used
                solver_failures.append("优化器抛出数值错误")
                continue
            evaluations = int(getattr(result, "nfev", 0))
            solver_evaluations += evaluations
            if not result.success:
                solver_failures.append(str(getattr(result, "message", "优化器未收敛")))
                evaluation_limit_hit |= evaluations >= _MAX_EVALUATIONS_PER_START
            point = fixed.copy()
            point[free] = np.asarray(result.x, dtype=float)
            candidate = add_candidate(point, result.success, "优化器结果")
            if candidate is not None and result.success:
                solver_successes += 1

    candidates = sorted(
        candidate_records,
        key=lambda item: (item["feasible"],
                          _candidate_rank(item, objectives) if item["feasible"] else (-math.inf,),
                          item["solver_success"]),
        reverse=True,
    )
    best = next((item for item in candidates if item["feasible"]), None)
    snapshot_id = _snapshot_id(frame, metadata)
    status, reason = "success", None
    if evaluation_limit_hit:
        status, reason = "solver_failure", (
            f"至少一个起点超过 {_MAX_EVALUATIONS_PER_START} 次函数评价上限")
    elif best is None or solver_successes == 0:
        status, reason = "solver_failure", "没有收敛且通过有限性与约束边界复核的候选"
    elif single and single[1]["mode"] == "target":
        name = next(iter(objectives))
        if not _target_reached(best["predictions"][name], models[name]):
            status, reason = "infeasible", "目标值在当前边界内未达到"
    if (best is not None and status == "success" and len(objectives) > 1
            and best["log_composite_desirability"] is None):
        status, reason = "zero_desirability", (
            "所有可行候选的综合期望均为 0；响应目标组合未实现（log(0) = −∞）")
    elif (best is not None and status == "success" and len(objectives) > 1
          and best["composite_desirability"] == 0):
        status, reason = "numerical_underflow", (
            "综合期望低于 binary64 最小正数，数值下溢为 0；不能据此判定目标组合严格不可行")
    success = status == "success"
    limitations = [
        f"采用确定性起点和 L-BFGS-B 局部搜索，共 {len(starts)} 个起点，每个起点设置 {_MAX_EVALUATIONS_PER_START} 次函数评价上限；候选不是全局最优证明。",
        "优化范围限于 coded [-1, 1] 内的 bounds；二次响应面在该模型范围外不外推。",
        "零 desirability 的搜索阶段使用有限连续延拓；返回评分仍按精确 desirability 与 log(0) 语义计算。",
    ]
    result = {
        "success": success, "status": status, "method": "deterministic multi-start L-BFGS-B",
        "global_optimum_guaranteed": False, "snapshot_id": snapshot_id,
        "best": best, "candidates": candidates,
        "block": (analyses[next(iter(analyses))]["blocks"] or [None])[0],
        "models": {name: {"coefficients": analysis["coefficients"]}
                   for name, analysis in analyses.items()},
        "categories": fixed_categories,
        "terms": {name: list(analysis["terms"])
                  for name, analysis in analyses.items()},
        "solver_evaluations": solver_evaluations,
        "solver_starts": len(starts),
        "evaluation_limit_per_start": _MAX_EVALUATIONS_PER_START,
        "solver_failures": solver_failures,
        "reason": reason, "feasible": bool(best and best["feasible"]),
        "limitations": limitations,
    }
    return result


def _binary_probability_limit(value, name, required):
    if value is None:
        if required:
            raise ValueError(f"{name} 必须是 0 到 1 之间的概率")
        return None
    value = _finite(value, name)
    if not 0 <= value <= 1:
        raise ValueError(f"{name} 必须在 [0,1] 内")
    return value


def _binary_desirability_and_slope(probability, goal, lower, target, upper, weight):
    if goal == "maximize":
        if probability <= lower:
            return 0.0, 0.0
        if probability >= target:
            return 1.0, 0.0
        scaled = (probability - lower) / (target - lower)
        return scaled ** weight, weight * scaled ** (weight - 1) / (target - lower)
    if goal == "minimize":
        if probability <= target:
            return 1.0, 0.0
        if probability >= upper:
            return 0.0, 0.0
        scaled = (upper - probability) / (upper - target)
        return scaled ** weight, -weight * scaled ** (weight - 1) / (upper - target)
    if probability <= lower or probability >= upper:
        return 0.0, 0.0
    if probability < target:
        scaled = (probability - lower) / (target - lower)
        return scaled ** weight, weight * scaled ** (weight - 1) / (target - lower)
    if probability == target:
        return 1.0, 0.0
    scaled = (upper - probability) / (upper - target)
    return scaled ** weight, -weight * scaled ** (weight - 1) / (upper - target)


def optimize_binary_rsm(analysis, *, goal, criterion, lower=None, target=None,
                        upper=None, weight=1.0, bounds=None, categories=None,
                        start=None, cancel=None):
    """Optimize a fitted grouped-binomial RSM probability over declared DOE bounds."""
    if cancel is not None and not callable(getattr(cancel, "is_set", None)):
        raise ValueError("cancel 必须是支持 is_set() 的取消事件")

    def check_cancelled():
        if cancel is not None and cancel.is_set():
            raise InterruptedError("二元响应优化已取消")

    check_cancelled()
    if not isinstance(analysis, dict) or analysis.get("family") != "rsm":
        raise ValueError("二元响应优化只支持已拟合的 RSM 模型")
    detail = analysis.get("detail")
    design = analysis.get("design")
    model = detail.get("term_model") if isinstance(detail, dict) else None
    if model is None or design is None or not analysis.get("model_snapshot"):
        raise ValueError("二元 RSM 模型缺少模型项或来源快照")
    run_blocks = [run.block for run in design.runs]
    block_levels = {block for block in run_blocks if block is not None}
    if len(block_levels) > 1 or (block_levels and any(block is None for block in run_blocks)):
        raise ValueError("二元响应优化不支持多个或不完整区组")
    if goal not in ("maximize", "minimize", "target"):
        raise ValueError("goal 必须是 maximize、minimize 或 target")
    if criterion not in ("probability", "desirability"):
        raise ValueError("criterion 必须是 probability 或 desirability")
    lower = _binary_probability_limit(lower, "lower", goal in ("maximize", "target"))
    target = _binary_probability_limit(target, "target", True)
    upper = _binary_probability_limit(upper, "upper", goal in ("minimize", "target"))
    if (goal == "maximize" and (lower >= target or upper is not None and target > upper)
            or goal == "minimize" and (target >= upper or lower is not None and lower > target)
            or goal == "target" and not lower < target < upper):
        raise ValueError("lower、target、upper 的顺序与目标不相容")
    weight = _finite(weight, "weight")
    if not 0.1 <= weight <= 10:
        raise ValueError("weight 必须在 0.1 到 10 之间")

    factors = design.spec.factors
    continuous = [factor for factor in factors if factor.factor_type == "continuous"]
    categorical = [factor for factor in factors if factor.factor_type == "categorical"]
    continuous_ids = {factor.factor_id for factor in continuous}
    categorical_ids = {factor.factor_id for factor in categorical}
    bounds = {} if bounds is None else bounds
    if not isinstance(bounds, Mapping) or set(bounds) - continuous_ids:
        raise ValueError("bounds 只能包含连续 DOE 因子的实际单位范围")
    actual_bounds, coded_bounds = {}, {}
    for factor in continuous:
        pair = bounds.get(factor.factor_id, (factor.low, factor.high))
        if not isinstance(pair, (tuple, list)) or len(pair) != 2:
            raise ValueError(f"因子 {factor.factor_id} 的范围必须含两个实际值")
        low, high = (_finite(pair[0], f"{factor.factor_id} 下限"),
                     _finite(pair[1], f"{factor.factor_id} 上限"))
        if low > high:
            raise ValueError(f"因子 {factor.factor_id} 的下限不能大于上限")
        try:
            code_low, code_high = float(factor.to_coded(low)), float(factor.to_coded(high))
        except (OverflowError, TypeError, ValueError) as error:
            raise ValueError(f"因子 {factor.factor_id} 的范围超出 DOE 声明域") from error
        if not math.isfinite(code_low) or not math.isfinite(code_high) or code_low > code_high:
            raise ValueError(f"因子 {factor.factor_id} 的编码范围不可表示")
        if (code_low < code_high
                and code_high - code_low <= 8 * math.ulp(max(1.0, abs(code_low), abs(code_high)))):
            raise ValueError(f"因子 {factor.factor_id} 的范围小于编码可分辨精度")
        actual_bounds[factor.factor_id] = (low, high)
        coded_bounds[factor.factor_id] = (code_low, code_high)

    if start is not None and (not isinstance(start, Mapping)
                              or set(start) - continuous_ids):
        raise ValueError("start 只能包含连续 DOE 因子的实际单位值")
    start_codes = []
    for factor in continuous:
        low, high = actual_bounds[factor.factor_id]
        code_low, code_high = coded_bounds[factor.factor_id]
        if start is None or factor.factor_id not in start:
            start_codes.append((code_low + code_high) / 2)
            continue
        value = start[factor.factor_id]
        value = _finite(value, f"{factor.factor_id} 起始值")
        if not low <= value <= high:
            raise ValueError(f"因子 {factor.factor_id} 的起始值超出搜索范围")
        code = float(factor.to_coded(value))
        if code_low == code_high and code != code_low:
            raise ValueError(f"因子 {factor.factor_id} 固定值与起点不一致")
        start_codes.append(code)

    if categories is not None and (not isinstance(categories, Mapping)
                                   or set(categories) - categorical_ids):
        raise ValueError("categories 只能包含已声明的类别因子")
    category_options = []
    for factor in categorical:
        raw_levels = (categories or {}).get(factor.factor_id, factor.levels)
        if isinstance(raw_levels, (tuple, list)):
            levels = list(raw_levels)
        elif isinstance(raw_levels, (str, Real)):
            levels = [raw_levels]
        else:
            raise ValueError(f"因子 {factor.factor_id} 的允许水平格式无效")
        if (not levels or any(level not in factor.levels for level in levels)
                or any(level in levels[:index] for index, level in enumerate(levels))):
            raise ValueError(f"因子 {factor.factor_id} 的允许水平无效或重复")
        category_options.append(levels)
    combination_count = math.prod(map(len, category_options))
    if combination_count > _BINARY_CATEGORY_COMBINATION_LIMIT:
        raise ValueError(
            f"类别因子组合为 {combination_count}，超过搜索预算 "
            f"{_BINARY_CATEGORY_COMBINATION_LIMIT}；请收窄允许水平。")

    names = analysis.get("column_names")
    coefficients = np.asarray(analysis.get("coefficients_array"), dtype=float)
    matrix = np.asarray(analysis.get("matrix"), dtype=float)
    if (names != model.names or matrix.ndim != 2
            or matrix.shape != (len(design.runs), len(model.names))
            or coefficients.shape != (len(model.names),)
            or not np.isfinite(matrix).all() or not np.isfinite(coefficients).all()):
        raise ValueError("Logistic 系数与拟合 TermModel 矩阵不一致或含非有限值")
    try:
        expected_matrix = model.matrix(detail["settings_rows"], detail["block_rows"])
    except (KeyError, TypeError, ValueError, OverflowError) as error:
        raise ValueError(f"无法验证 Logistic 拟合矩阵：{error}") from error
    if not np.array_equal(matrix, expected_matrix):
        raise ValueError("TermModel 与 Logistic 拟合矩阵不一致")

    coded_center = np.asarray([
        sum(coded_bounds[factor.factor_id]) / 2 for factor in continuous
    ], dtype=float)
    free = [index for index, factor in enumerate(continuous)
            if coded_bounds[factor.factor_id][0] < coded_bounds[factor.factor_id][1]]
    if not free:
        starts = [coded_center.copy()]
    elif len(free) <= 5:
        starts = []
        for corner in product(*(coded_bounds[continuous[index].factor_id]
                                for index in free)):
            point = coded_center.copy()
            point[free] = corner
            starts.append(point)
        starts.append(coded_center.copy())
    else:
        starts = [coded_center.copy()]
        for values in (0, 1):
            point = coded_center.copy()
            for index in free:
                point[index] = coded_bounds[continuous[index].factor_id][values]
            starts.append(point)
        for index in free:
            for edge in coded_bounds[continuous[index].factor_id]:
                point = coded_center.copy()
                point[index] = edge
                starts.append(point)
    starts.append(np.asarray(start_codes, dtype=float))
    unique_starts, seen_starts = [], set()
    for point in starts:
        key = tuple(map(float, point))
        if key not in seen_starts:
            unique_starts.append(np.asarray(point, dtype=float))
            seen_starts.add(key)

    def evaluate(point, selected_categories):
        settings = {factor.factor_id: float(value)
                    for factor, value in zip(continuous, point)}
        settings.update(selected_categories)
        with np.errstate(over="ignore", invalid="ignore"):
            eta, eta_gradient = _term_value_gradient(model, coefficients, settings)
        if not math.isfinite(eta) or not np.isfinite(eta_gradient).all():
            return None
        probability = float(expit(eta))
        probability_gradient = probability * (1 - probability) * eta_gradient
        desirability, desirability_slope = _binary_desirability_and_slope(
            probability, goal, lower, target, upper, weight)
        if criterion == "probability":
            score = (-probability if goal == "maximize" else
                     probability if goal == "minimize" else
                     (probability - target) ** 2)
            objective = probability if goal != "target" else (probability - target) ** 2
        else:
            score, objective = -desirability, desirability
        if not math.isfinite(score) or not math.isfinite(desirability):
            return None
        reached = (probability >= target if goal == "maximize" else
                   probability <= target if goal == "minimize" else
                   abs(probability - target) <= _TARGET_TOLERANCE)
        actual_settings = dict(selected_categories)
        for factor, code in zip(continuous, point):
            actual = _finite(factor.from_coded(float(code)), f"{factor.factor_id} 实际值")
            low, high = actual_bounds[factor.factor_id]
            if not low <= actual <= high:
                return None
            if abs(float(factor.to_coded(actual)) - float(code)) > 1e-8:
                return None
            actual_settings[factor.factor_id] = actual
        coded_settings = {factor.factor_id: float(code)
                          for factor, code in zip(continuous, point)}
        coded_settings.update(selected_categories)
        return {
            "score": score, "objective_value": objective,
            "probability": probability, "desirability": desirability,
            "settings": actual_settings, "coded_settings": coded_settings,
            "target_reached": bool(reached),
            "target_difference": float(probability - target),
        }, probability_gradient, desirability_slope

    center_distance = lambda candidate: sum(
        (candidate["coded_settings"][factor.factor_id] - coded_center[index]) ** 2
        for index, factor in enumerate(continuous))
    level_order = lambda candidate: tuple(
        factor.levels.index(candidate["settings"][factor.factor_id])
        for factor in categorical)
    coordinate_order = lambda candidate: tuple(
        candidate["coded_settings"][factor.factor_id] for factor in continuous)
    tie_key = lambda candidate: (center_distance(candidate), level_order(candidate),
                                 coordinate_order(candidate))
    best, evaluations = None, 0

    def update_best(candidate):
        nonlocal best
        if candidate is None:
            return
        if best is None:
            best = candidate
            return
        if goal == "target" and candidate["target_reached"] != best["target_reached"]:
            if candidate["target_reached"]:
                best = candidate
            return
        tolerance = 32 * np.finfo(float).eps * max(
            1.0, abs(best["score"]), abs(candidate["score"]))
        if (candidate["score"] < best["score"] - tolerance
                or (abs(candidate["score"] - best["score"]) <= tolerance
                    and tie_key(candidate) < tie_key(best))):
            best = candidate

    def consider(point, selected_categories):
        nonlocal evaluations
        evaluations += 1
        evaluated = evaluate(point, selected_categories)
        update_best(None if evaluated is None else evaluated[0])

    solver_successes = solver_starts = iterations = 0
    termination_counts = {}
    class EvaluationLimit(Exception):
        pass

    for selected in product(*category_options):
        check_cancelled()
        selected_categories = dict(zip((factor.factor_id for factor in categorical), selected))
        for initial in unique_starts:
            check_cancelled()
            consider(initial, selected_categories)
            if not free:
                continue
            solver_starts += 1
            evaluations_this_start = 0

            def objective(free_point):
                nonlocal evaluations_this_start, evaluations
                check_cancelled()
                if evaluations_this_start >= _BINARY_EVALUATIONS_PER_START:
                    raise EvaluationLimit
                evaluations_this_start += 1
                evaluations += 1
                point = initial.copy()
                point[free] = free_point
                evaluated = evaluate(point, selected_categories)
                candidate, probability_gradient, desirability_slope = (
                    (None, None, None) if evaluated is None else evaluated)
                update_best(candidate)
                if candidate is None:
                    return 1e100, np.zeros(len(free))
                if criterion == "probability":
                    gradient = (-(probability_gradient) if goal == "maximize" else
                                probability_gradient if goal == "minimize" else
                                2 * (candidate["probability"] - target)
                                * probability_gradient)
                else:
                    gradient = -desirability_slope * probability_gradient
                return candidate["score"], gradient[free]

            solver_point = None
            try:
                solver = minimize(
                    objective, initial[free], method="L-BFGS-B",
                    bounds=[coded_bounds[continuous[index].factor_id] for index in free],
                    jac=True,
                    options={"maxiter": _BINARY_EVALUATIONS_PER_START,
                             "maxfun": _BINARY_EVALUATIONS_PER_START,
                             "ftol": 1e-15, "gtol": 1e-10},
                )
                message = str(solver.message)
                iterations += int(solver.nit)
                solver_point = np.asarray(solver.x, dtype=float)
                if solver.success:
                    solver_successes += 1
            except EvaluationLimit:
                message = f"起点评价达到 {_BINARY_EVALUATIONS_PER_START} 次上限"
            except (FloatingPointError, ValueError, OverflowError) as error:
                message = f"优化器数值错误：{error}"
            termination_counts[message] = termination_counts.get(message, 0) + 1
            check_cancelled()
            if solver_point is not None:
                point = initial.copy()
                point[free] = solver_point
                consider(point, selected_categories)

    if best is None:
        raise ValueError("搜索域内没有产生有限且可行的二元概率候选")
    global_optimum_proven = not free
    all_converged = not free or solver_successes == solver_starts
    termination_reason = (
        "全部类别组合已穷举" if not free else
        "所有多起点局部搜索均收敛" if all_converged else
        "返回可行候选；至少一个局部起点未收敛或达到评价上限"
    )
    reached_status = ("目标已达到" if best["target_reached"] else
                      "当前搜索未达到目标；多起点局部搜索不证明目标在域内不可达")
    return {
        **best,
        "goal": goal, "criterion": criterion, "lower": lower,
        "target": target, "upper": upper, "weight": weight,
        "target_status": reached_status,
        "feasible": True,
        "candidate_found": True,
        "success": all_converged,
        "status": "exact_enumeration" if global_optimum_proven else
                  "solver_converged" if all_converged else "candidate_with_unconverged_starts",
        "method": "分类组合穷举" if not free else
                  "确定性多起点 L-BFGS-B；类别组合完整枚举；不证明连续域全局最优",
        "solver_starts": solver_starts,
        "solver_successes": solver_successes,
        "solver_converged": all_converged,
        "solver_iterations": iterations,
        "evaluations": evaluations,
        "category_combinations_evaluated": combination_count,
        "category_combination_limit": _BINARY_CATEGORY_COMBINATION_LIMIT,
        "evaluations_per_start_limit": _BINARY_EVALUATIONS_PER_START,
        "termination_counts": termination_counts,
        "termination_reason": termination_reason,
        "global_optimum_proven": global_optimum_proven,
        "model_snapshot": analysis["model_snapshot"],
        "note": "结果来自当前拟合模型预测，不是实际设备已验证的操作最优值。",
    }
