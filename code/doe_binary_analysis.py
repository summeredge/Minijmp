"""Grouped-binomial analysis for verified DOE design families."""
from itertools import combinations, product
import math
from numbers import Integral, Real
import warnings

import numpy as np
import statsmodels.api as sm
from scipy import stats
from scipy.special import expit
from statsmodels.tools.sm_exceptions import (
    ConvergenceWarning, PerfectSeparationError, PerfectSeparationWarning,
)

from doe_core import restore_design_result


_BINARY_FAMILIES = {
    "screening": {"definitive_screening"},
    "factorial": {"two_level_full", "two_level_fractional",
                  "general_full_factorial", "plackett_burman"},
    "rsm": {"central_composite", "box_behnken", "custom_rsm"},
}


def _rank(matrix):
    return int(np.linalg.matrix_rank(matrix))


def _add_term(columns, column_names, term_columns, name, values, names=None):
    if name in term_columns:
        raise ValueError(f"模型项重复：{name}")
    array = np.asarray(values, dtype=float)
    if array.ndim == 1:
        array = array[:, None]
    if array.ndim != 2 or array.shape[0] != len(columns[0]):
        raise ValueError(f"模型项矩阵无效：{name}")
    labels = list(names) if names is not None else [name]
    if len(labels) != array.shape[1]:
        raise ValueError(f"模型项列数不匹配：{name}")
    indices = []
    for label, values_column in zip(labels, array.T):
        indices.append(len(columns))
        columns.append(values_column)
        column_names.append(label)
    term_columns[name] = indices


def _append_blocks(columns, column_names, term_columns, runs):
    levels = list(dict.fromkeys(run.block for run in runs if run.block is not None))
    if levels and any(run.block is None for run in runs):
        raise ValueError("区组列存在部分缺失")
    for level in levels[1:]:
        _add_term(columns, column_names, term_columns, f"区组[{level}]",
                  [float(run.block == level) for run in runs])


def _term_labels(term, factor_ids):
    if len(term) == 1:
        return factor_ids[term[0]]
    if term[0] == term[1]:
        return f"{factor_ids[term[0]]}²"
    return "*".join(factor_ids[index] for index in term)


def _two_level_matrix(design, order):
    spec, runs = design.spec, design.runs
    factors = spec.factors
    factor_ids = [factor.factor_id for factor in factors]
    coded = np.asarray([[float(factor.to_coded(run.settings[factor.factor_id]))
                         for factor in factors] for run in runs], dtype=float)
    if not np.isfinite(coded).all() or not np.isin(coded, (-1.0, 0.0, 1.0)).all():
        raise ValueError("两水平设计含非法编码水平")
    columns, names = [np.ones(len(runs))], ["截距"]
    terms = {}
    selected = [term for degree in range(1, order + 1)
                for term in combinations(range(len(factors)), degree)]
    for term in selected:
        label = _term_labels(term, factor_ids)
        values = np.prod(coded[:, term], axis=1)
        _add_term(columns, names, terms, label, values)
    center = np.asarray([run.point_type == "center" for run in runs], dtype=float)
    if center.any():
        _add_term(columns, names, terms, "中心点偏移", center)
    _append_blocks(columns, names, terms, runs)
    return np.column_stack(columns), names, terms, coded


def _screening_matrix(design, family, terms=None):
    from doe_core import _screening_level

    spec, runs = design.spec, design.runs
    factors = spec.factors
    factor_ids = [factor.factor_id for factor in factors]
    if family == "screening":
        from doe_dsd import validate_dsd
        validate_dsd(design)
    else:
        from doe_pb import validate_pb
        validate_pb(design)
    coded = np.asarray([[_screening_level(factor, run.settings[factor.factor_id])
                         for factor in factors] for run in runs], dtype=float)
    if not np.isfinite(coded).all():
        raise ValueError("筛选设计编码必须是有限数值")
    columns, names = [np.ones(len(runs))], ["截距"]
    term_columns = {}

    if family == "screening":
        main = [(name,) for name in factor_ids]
        squares = [(factor.factor_id, factor.factor_id) for factor in factors
                   if factor.factor_type == "continuous"]
        pairs = list(combinations(factor_ids, 2))
        permitted = set(main + squares + pairs)
        selected = main if terms is None else [tuple(term) for term in terms]
        if (len(set(selected)) != len(selected)
                or any(term not in permitted for term in selected)):
            raise ValueError("DSD 模型项重复或超出允许范围")
        if any((name,) not in selected for term in selected if len(term) == 2
               for name in set(term)):
            raise ValueError("DSD 平方项和交互项必须包含对应主效应")
        positions = {name: index for index, name in enumerate(factor_ids)}
        for term in selected:
            if len(term) == 1:
                label = term[0]
                values = coded[:, positions[label]]
            elif term[0] == term[1]:
                label = f"{term[0]}²"
                values = coded[:, positions[term[0]]] ** 2
            else:
                label = "*".join(term)
                values = coded[:, positions[term[0]]] * coded[:, positions[term[1]]]
            _add_term(columns, names, term_columns, label, values)

    elif family == "factorial" and spec.design_type == "plackett_burman":
        from doe_pb import validate_pb
        validate_pb(design)
        if any(run.point_type != "factorial" for run in runs):
            raise ValueError("PB 二元分析暂不支持中心点或伪中心点")
        for index, factor_id in enumerate(factor_ids):
            _add_term(columns, names, term_columns, factor_id, coded[:, index])

    else:
        raise ValueError("该筛选设计矩阵暂不支持此模型")

    _append_blocks(columns, names, term_columns, runs)
    return np.column_stack(columns), names, term_columns, coded


def _fractional_matrix(frame, metadata, design):
    from doe_fractional_analysis import fractional_alias_groups

    spec, runs = design.spec, design.runs
    factors = spec.factors
    factor_ids = [factor.factor_id for factor in factors]
    coded = np.asarray([[float(factor.to_coded(run.settings[factor.factor_id]))
                         for factor in factors] for run in runs], dtype=float)
    if not np.isfinite(coded).all() or not np.isin(coded, (-1.0, 0.0, 1.0)).all():
        raise ValueError("部分因子设计编码必须为有限两水平值")
    aliases = fractional_alias_groups(frame, metadata, order=1)
    columns, names = [np.ones(len(runs))], ["截距"]
    terms = {}
    positions = {name: index for index, name in enumerate(factor_ids)}
    for group in aliases:
        selectable = group["selectable_terms"]
        if not selectable:
            continue
        representative = selectable[0]
        factor_term = tuple(representative.split("*"))
        values = np.prod(coded[:, [positions[name] for name in factor_term]], axis=1)
        _add_term(columns, names, terms, group["label"], values,
                  [group["label"]])
    if any(run.point_type == "center" for run in runs):
        _add_term(columns, names, terms, "中心点偏移",
                  [float(run.point_type == "center") for run in runs])
    _append_blocks(columns, names, terms, runs)
    return np.column_stack(columns), names, terms, coded


def _general_factorial_matrix(design, order):
    from doe_general_factorial_analysis import _contrast_basis

    spec, runs = design.spec, design.runs
    factors = spec.factors
    factor_ids = [factor.factor_id for factor in factors]
    factor_values = [[run.settings[factor.factor_id] for run in runs]
                     for factor in factors]
    bases = [_contrast_basis(values, factor.levels)
             for factor, values in zip(factors, factor_values)]
    terms_to_fit = [term for degree in range(1, order + 1)
                    for term in combinations(range(len(factors)), degree)]
    width = 1 + sum(int(np.prod([bases[index].shape[1] for index in term]))
                    for term in terms_to_fit)
    block_levels = list(dict.fromkeys(run.block for run in runs if run.block is not None))
    if block_levels and any(run.block is None for run in runs):
        raise ValueError("区组列存在部分缺失")
    width += max(0, len(block_levels) - 1)
    if len(runs) * width > 10_000_000:
        raise ValueError("所选模型矩阵超过 1000 万个单元，请降低模型阶次")
    columns, names = [np.ones(len(runs))], ["截距"]
    term_columns = {}
    for term in terms_to_fit:
        label = "*".join(factor_ids[index] for index in term)
        contrast_combinations = product(*(range(bases[index].shape[1]) for index in term))
        values, labels = [], []
        for contrasts in contrast_combinations:
            column = np.ones(len(runs))
            parts = []
            for factor_index, contrast_index in zip(term, contrasts):
                column *= bases[factor_index][:, contrast_index]
                level = factors[factor_index].levels[contrast_index + 1]
                parts.append(f"{factor_ids[factor_index]}[{level}]")
            values.append(column)
            labels.append("*".join(parts))
        _add_term(columns, names, term_columns, label, np.column_stack(values), labels)
    if block_levels:
        block_basis = _contrast_basis([run.block for run in runs], block_levels)
        block_names = [f"区组[{level}]" for level in block_levels[1:]]
        for label, values in zip(block_names, block_basis.T):
            _add_term(columns, names, term_columns, label, values)
    x = np.column_stack(columns)
    return x, names, term_columns, None


def _rsm_matrix(design, order, selected_terms=None):
    from doe_rsm_model import TermModel

    spec, runs = design.spec, design.runs
    continuous = [factor for factor in spec.factors if factor.factor_type == "continuous"]
    if spec.design_type in ("central_composite", "box_behnken"):
        from doe_rsm import validate_design
        coded = validate_design(design)
    else:
        from doe_custom import coded_value, validate_custom
        validate_custom(design)
        coded = np.asarray([[coded_value(factor, run.settings[factor.factor_id],
                                          run.point_type)
                             for factor in continuous] for run in runs], dtype=float)
    if not np.isfinite(coded).all():
        raise ValueError("响应面编码必须是有限数值")
    if selected_terms is None:
        if spec.design_type == "custom_rsm" and spec.model_terms:
            selected_terms = list(spec.model_terms)
        elif order == 1:
            selected_terms = ([factor.factor_id for factor in spec.factors])
        else:
            selected_terms = None

    block_levels = list(dict.fromkeys(run.block for run in runs if run.block is not None))
    if block_levels and any(run.block is None for run in runs):
        raise ValueError("区组列存在部分缺失")
    block_index = {value: index + 1 for index, value in enumerate(block_levels)}
    model = TermModel(spec.factors, selected_terms, blocks=len(block_levels))
    settings_rows = []
    for row, run in enumerate(runs):
        settings = {factor.factor_id: float(coded[row, index])
                    for index, factor in enumerate(continuous)}
        settings.update({factor.factor_id: run.settings[factor.factor_id]
                         for factor in spec.factors if factor.factor_type == "categorical"})
        settings_rows.append(settings)
    block_rows = [block_index.get(run.block) if block_levels else None for run in runs]
    x = model.matrix(settings_rows, block_rows)
    term_columns = {}
    for index, (name, column_spec) in enumerate(model.columns[1:], 1):
        if isinstance(column_spec, tuple) and column_spec[0] == "block":
            label = f"区组[{column_spec[1]}]"
        elif isinstance(column_spec, tuple):
            label = column_spec[0]
        else:
            label = name
        term_columns.setdefault(label, []).append(index)
    return x, model.names, term_columns, {
        "term_model": model, "settings_rows": settings_rows,
        "block_rows": block_rows, "coded": coded,
    }


def _matrix_for_design(frame, metadata, design, family, model_order, selected_terms):
    if family == "screening":
        return _screening_matrix(design, family, selected_terms)
    if family == "rsm":
        return _rsm_matrix(design, model_order, selected_terms)
    design_type = design.spec.design_type
    if design_type == "two_level_full":
        from doe_factorial import validate_factorial_design
        validate_factorial_design(frame, metadata)
        return _two_level_matrix(design, model_order)
    if design_type == "two_level_fractional":
        if model_order != 1:
            raise ValueError("正规部分因子二元模型首版限主效应别名组")
        return _fractional_matrix(frame, metadata, design)
    if design_type == "general_full_factorial":
        from doe_general_factorial import validate_general_factorial
        validate_general_factorial(frame, metadata)
        return _general_factorial_matrix(design, model_order)
    if design_type == "plackett_burman":
        if model_order != 1:
            raise ValueError("PB 二元模型首版只支持主效应")
        return _screening_matrix(design, family, selected_terms)
    raise ValueError("当前 DOE 设计类型不属于此二元分析入口")


def _column_values(frame, label):
    positions = [index for index, name in enumerate(frame.columns) if name == label]
    if len(positions) != 1:
        raise ValueError(f"工作表列必须唯一：{label}")
    return [frame.iloc[row, positions[0]] for row in range(len(frame))]


def _integer_counts(values, name, positive):
    result = []
    for row, value in enumerate(values, 1):
        if isinstance(value, (bool, np.bool_)):
            raise ValueError(f"{name} 第 {row} 行必须是整数计数")
        if isinstance(value, Integral):
            number = int(value)
        elif isinstance(value, Real):
            numeric = float(value)
            if not np.isfinite(numeric) or not numeric.is_integer():
                raise ValueError(f"{name} 第 {row} 行必须是整数计数")
            number = int(numeric)
        else:
            raise ValueError(f"{name} 第 {row} 行必须是整数计数")
        if number > 2**53:
            raise ValueError(f"{name} 第 {row} 行超出当前浮点极大似然算法的精确整数范围")
        if number < 0 or positive and number == 0:
            rule = "正整数" if positive else "非负整数"
            raise ValueError(f"{name} 第 {row} 行必须是{rule}")
        result.append(number)
    return np.asarray(result, dtype=np.int64)


def _fit_glm(x, events, trials):
    response = np.column_stack((events, trials - events))
    try:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            fitted = sm.GLM(response, x, family=sm.families.Binomial(
                link=sm.families.links.Logit())).fit(maxiter=200, tol=1e-10)
    except (PerfectSeparationError, PerfectSeparationWarning, ConvergenceWarning,
            np.linalg.LinAlgError, FloatingPointError) as error:
        raise ValueError("Logistic 拟合分离、秩亏或未收敛；该模型不提供推断。") from error
    if any(issubclass(item.category, ConvergenceWarning) for item in caught):
        raise ValueError("Logistic 迭代未收敛；该模型不提供推断。")
    pure_rows = (events == 0) | (events == trials)
    if (pure_rows.any() and
            any(issubclass(item.category, PerfectSeparationWarning) for item in caught)):
        raise ValueError("检测到完全或准完全分离；该模型不提供有限的 Logistic 推断。")
    if not fitted.converged:
        raise ValueError("Logistic 迭代未收敛；该模型不提供推断。")
    if not np.isfinite(fitted.params).all() or not np.isfinite(fitted.cov_params()).all():
        raise ValueError("Logistic 参数或协方差非有限值；该模型不提供推断。")
    probabilities = np.asarray(fitted.fittedvalues, dtype=float)
    if (not np.isfinite(probabilities).all() or
            np.any(probabilities <= 0) or np.any(probabilities >= 1)):
        raise ValueError("拟合概率到达 0/1 边界，疑似完全分离；该模型不提供推断。")
    return fitted


def fit_grouped_binomial(x, column_names, term_columns, events, trials, run_ids=None):
    """Fit event/trial counts to a full-rank binomial logit DOE matrix."""
    x = np.asarray(x, dtype=float)
    events = _integer_counts(events, "事件数", positive=False)
    trials = _integer_counts(trials, "试验数", positive=True)
    if x.ndim != 2 or len(x) != len(events) or len(events) != len(trials):
        raise ValueError("设计矩阵、事件数和试验数行数不匹配")
    if not np.isfinite(x).all() or not len(x):
        raise ValueError("设计矩阵为空或包含非有限数值")
    if np.any(events > trials):
        raise ValueError("事件数不能大于试验数")
    if sum(map(int, events)) == 0 or np.array_equal(events, trials):
        raise ValueError("全部试验均为非事件或事件，没有有限的 Logistic 极大似然估计")
    rank = _rank(x)
    if rank != x.shape[1]:
        aliased = []
        for term, indices in term_columns.items():
            if any(_rank(np.delete(x, index, axis=1)) == rank for index in indices):
                aliased.append(term)
        names = "、".join(aliased) if aliased else "模型项"
        raise ValueError(f"所选模型秩亏（秩 {rank}/{x.shape[1]}）；不可估计项：{names}")

    fitted = _fit_glm(x, events, trials)
    probabilities = np.asarray(fitted.fittedvalues, dtype=float)
    null = _fit_glm(np.ones((len(events), 1)), events, trials)
    model_lr = float(2 * (fitted.llf - null.llf))
    model_lr_tolerance = 1e-10 * max(1.0, abs(fitted.llf), abs(null.llf))
    if model_lr < -model_lr_tolerance:
        raise ValueError("全模型与截距模型的似然比较数值不稳定；模型检验不可用。")
    model_lr = max(0.0, model_lr)
    information = x.T @ ((trials * probabilities * (1.0 - probabilities))[:, None] * x)
    try:
        information_cholesky = np.linalg.cholesky(information)
        covariance = np.linalg.solve(
            information_cholesky.T,
            np.linalg.solve(information_cholesky, np.eye(rank)),
        )
    except np.linalg.LinAlgError as error:
        raise ValueError("Logistic 信息矩阵不可逆；该模型不提供推断。") from error
    standard_errors = np.sqrt(np.diag(covariance))
    z_values = np.asarray(fitted.params, dtype=float) / standard_errors
    p_values = 2 * stats.norm.sf(np.abs(z_values))
    model_df = rank - 1
    model_p = float(stats.chi2.sf(model_lr, model_df)) if model_df > 0 else None
    residual_df = int(len(events) - rank)

    coefficient_rows = []
    for name, estimate, se, z_value, p_value in zip(
            column_names, fitted.params, standard_errors, z_values, p_values):
        coefficient_rows.append({
            "term": name, "coefficient": float(estimate), "se": float(se),
            "z": float(z_value), "p": float(p_value),
        })

    term_rows = []
    for term, indices in term_columns.items():
        reduced_x = np.delete(x, indices, axis=1)
        reduced_rank = _rank(reduced_x)
        test_df = rank - reduced_rank
        if test_df <= 0:
            term_rows.append({"term": term, "df": 0, "lr": None, "p": None,
                              "status": "不可估计"})
            continue
        try:
            reduced = _fit_glm(reduced_x, events, trials)
        except ValueError:
            term_rows.append({"term": term, "df": test_df, "lr": None, "p": None,
                              "status": "删项模型分离或不收敛"})
            continue
        lr = float(2 * (fitted.llf - reduced.llf))
        tolerance = 1e-10 * max(1.0, abs(fitted.llf), abs(reduced.llf))
        if lr < -tolerance:
            term_rows.append({"term": term, "df": test_df, "lr": None, "p": None,
                              "status": "似然比较数值不稳定"})
            continue
        lr = max(0.0, lr)
        term_rows.append({"term": term, "df": test_df, "lr": lr,
                          "p": float(stats.chi2.sf(lr, test_df)), "status": "可用"})

    pearson = float(fitted.pearson_chi2)
    deviance = float(fitted.deviance)
    rows = [{
        "run_id": run_ids[index] if run_ids is not None else index + 1,
        "events": int(events[index]), "trials": int(trials[index]),
        "observed_probability": float(events[index] / trials[index]),
        "predicted_probability": float(probabilities[index]),
        "pearson_residual": float((events[index] - trials[index] * probabilities[index]) /
                                   np.sqrt(trials[index] * probabilities[index] *
                                           (1 - probabilities[index]))),
    } for index in range(len(events))]
    return {
        "coefficients": coefficient_rows, "terms": term_rows, "rows": rows,
        "n_runs": len(events), "n_trials": sum(map(int, trials)),
        "rank": rank, "model_df": model_df, "residual_df": residual_df,
        "log_likelihood": float(fitted.llf), "model_lr": model_lr,
        "model_p": model_p, "deviance": deviance,
        "deviance_p": float(stats.chi2.sf(deviance, residual_df))
        if residual_df > 0 else None,
        "pearson_chi_square": pearson,
        "pearson_p": float(stats.chi2.sf(pearson, residual_df))
        if residual_df > 0 else None,
        "inference_status": "可用" if model_df > 0 else "无预测项；仅拟合截距",
        "fit_status": "Logistic 收敛",
        "coefficients_array": np.asarray(fitted.params, dtype=float),
        "covariance_array": covariance,
        "matrix": x,
        "column_names": list(column_names),
        "term_columns": term_columns,
        "probabilities": probabilities,
    }


def analyze_binary_doe(frame, metadata, events_column, trials_column, family,
                       model_order=2, selected_terms=None):
    """Validate the worksheet, build its family-specific matrix, and fit counts."""
    if family not in _BINARY_FAMILIES:
        raise ValueError("未知 DOE 二元分析族")
    design = restore_design_result(frame, metadata)
    if design.spec.design_type not in _BINARY_FAMILIES[family]:
        raise ValueError("当前 DOE 设计类型与二元分析入口不匹配")
    response_columns = set(metadata.get("column_map", {}).get("responses", {}).values())
    if events_column not in response_columns or trials_column not in response_columns:
        raise ValueError("事件数和试验数必须是 DOE 已声明并映射的响应列")
    if events_column == trials_column:
        raise ValueError("事件数列和试验数列必须不同")
    events = _column_values(frame, events_column)
    trials = _column_values(frame, trials_column)
    if (isinstance(model_order, bool) or not isinstance(model_order, Integral)
            or not 1 <= model_order <= 2):
        raise ValueError("模型阶次只支持 1 或 2")
    model_order = int(model_order)
    x, column_names, term_columns, detail = _matrix_for_design(
        frame, metadata, design, family, model_order, selected_terms)
    result = fit_grouped_binomial(
        x, column_names, term_columns, events, trials,
        [run.run_id for run in design.runs])
    result.update({
        "design": design, "family": family, "events_column": events_column,
        "trials_column": trials_column, "settings": [dict(run.settings) for run in design.runs],
        "blocks": [run.block for run in design.runs], "detail": detail,
        "assumption": (
            "各运行中的试验独立；二项 dispersion 固定为 1。"
            "系数 p 值为 Wald z，项/模型检验为渐近似然比 χ²。"
            + ("正规部分因子的项按完整别名组解释。" if design.spec.design_type == "two_level_fractional" else "")
            + ("PB 主效应可能与未拟合交互混杂。" if design.spec.design_type == "plackett_burman" else "")),
    })
    if family == "rsm":
        from doe_predict import snapshot_id
        result["model_snapshot"] = snapshot_id(frame, metadata)
    return result


def predict_binary_probability(result, settings, confidence=0.95,
                               side="two_sided"):
    """Predict an RSM event probability and its logit-scale Wald interval."""
    if not isinstance(result, dict) or result.get("family") != "rsm":
        raise ValueError("概率区间只支持已拟合的二元 RSM 模型")
    if isinstance(confidence, bool) or not isinstance(confidence, Real):
        raise ValueError("置信水平必须是 0 与 1 之间的比例")
    try:
        confidence = float(confidence)
    except (OverflowError, TypeError, ValueError) as error:
        raise ValueError("置信水平必须是 0 与 1 之间的比例") from error
    if not math.isfinite(confidence) or not 0 < confidence < 1:
        raise ValueError("置信水平必须是 0 与 1 之间的比例")
    if side not in ("two_sided", "lower", "upper"):
        raise ValueError("区间方向必须是 two_sided、lower 或 upper")

    design, detail = result.get("design"), result.get("detail")
    model = detail.get("term_model") if isinstance(detail, dict) else None
    if design is None or model is None or not result.get("model_snapshot"):
        raise ValueError("二元 RSM 模型缺少设计项或来源快照")
    run_blocks = [run.block for run in design.runs]
    block_levels = {block for block in run_blocks if block is not None}
    if len(block_levels) > 1 or (block_levels and any(block is None for block in run_blocks)):
        raise ValueError("当前二元概率区间不支持多个区组")
    if not isinstance(settings, dict):
        raise ValueError("因子设置必须是映射")
    factors = design.spec.factors
    factor_ids = {factor.factor_id for factor in factors}
    if set(settings) != factor_ids:
        missing = factor_ids - set(settings)
        unknown = set(settings) - factor_ids
        if missing:
            raise ValueError("缺少因子设置：" + "、".join(sorted(missing)))
        raise ValueError("存在未知因子：" + "、".join(sorted(unknown)))

    actual = {}
    for factor in factors:
        value = settings[factor.factor_id]
        if factor.factor_type == "categorical":
            if value not in factor.levels:
                raise ValueError(f"因子 {factor.factor_id} 的水平不在已声明范围内")
            actual[factor.factor_id] = value
            continue
        if isinstance(value, bool) or not isinstance(value, Real):
            raise ValueError(f"因子 {factor.factor_id} 必须是有限数值")
        value = float(value)
        if not math.isfinite(value):
            raise ValueError(f"因子 {factor.factor_id} 必须是有限数值")
        if not factor.low <= value <= factor.high:
            raise ValueError(f"因子 {factor.factor_id} 超出 DOE 声明范围")
        actual[factor.factor_id] = value

    try:
        coded = model.coded(actual)
        x0 = np.asarray(model.row(coded), dtype=float)
        matrix = np.asarray(result["matrix"], dtype=float)
        coefficients = np.asarray(result["coefficients_array"], dtype=float)
        covariance = np.asarray(result["covariance_array"], dtype=float)
    except (KeyError, TypeError, ValueError, OverflowError) as error:
        raise ValueError(f"无法建立与拟合模型一致的预测行：{error}") from error
    names = result.get("column_names")
    if (names != model.names or matrix.ndim != 2 or matrix.shape[1] != len(names)
            or coefficients.shape != (len(names),) or x0.shape != (len(names),)
            or covariance.shape != (len(names), len(names))):
        raise ValueError("拟合矩阵、模型项、系数和协方差维度不一致")
    if (not np.isfinite(matrix).all() or not np.isfinite(coefficients).all()
            or not np.isfinite(covariance).all() or not np.isfinite(x0).all()):
        raise ValueError("拟合矩阵、系数或协方差包含非有限值")
    try:
        expected_matrix = model.matrix(detail["settings_rows"], detail["block_rows"])
        if not np.array_equal(matrix, expected_matrix):
            raise ValueError("TermModel 与 Logistic 拟合矩阵不一致")
        scale = max(1.0, float(np.linalg.norm(covariance, ord=np.inf)))
        if not math.isfinite(scale):
            raise ValueError("系数协方差矩阵范数非有限")
        tolerance = 64 * np.finfo(float).eps * scale * max(1, len(names))
        if np.max(np.abs(covariance - covariance.T)) > tolerance:
            raise ValueError("系数协方差矩阵不对称")
        symmetric_covariance = (covariance + covariance.T) / 2
        if np.linalg.eigvalsh(symmetric_covariance)[0] < -tolerance:
            raise ValueError("系数协方差矩阵不是半正定矩阵")
        with np.errstate(over="ignore", invalid="ignore"):
            eta_hat = float(x0 @ coefficients)
            variance_eta = float(x0 @ covariance @ x0)
    except (KeyError, TypeError, ValueError, np.linalg.LinAlgError,
            OverflowError, FloatingPointError) as error:
        raise ValueError(f"无法计算二元预测方差：{error}") from error
    if not math.isfinite(eta_hat) or not math.isfinite(variance_eta):
        raise ValueError("Logit 预测值或方差非有限")
    variance_tolerance = (64 * np.finfo(float).eps
                          * max(1.0, float(x0 @ x0) * scale))
    if variance_eta < -variance_tolerance:
        raise ValueError("Logit 预测方差为负")
    variance_eta = max(0.0, variance_eta)
    se_eta = math.sqrt(variance_eta)
    probability = float(expit(eta_hat))
    se_probability = probability * (1 - probability) * se_eta
    result_row = {
        "settings": actual, "coded": coded,
        "eta_hat": eta_hat, "se_eta": se_eta,
        "p_hat": probability, "se_p": se_probability,
        "ci_low": None, "ci_high": None,
        "confidence": float(confidence), "side": side,
        "method": "渐近 Wald 近似（Logit 尺度，正态 z）",
        "interval_status": "可用",
        "assumption": "事件概率估计区间；Binomial dispersion 固定为 1。"
                     "这不是未来单次 0/1 结果的预测区间。",
        "model_snapshot": result["model_snapshot"],
    }
    if probability in (0.0, 1.0):
        result_row["interval_status"] = "不可用：预测概率数值饱和至 0 或 1。"
        return result_row

    tail_probability = ((1 + confidence) / 2 if side == "two_sided"
                        else confidence)
    critical = float(stats.norm.ppf(tail_probability))
    if not math.isfinite(critical):
        raise ValueError("无法取得指定置信水平的正态 z 临界值")
    if side in ("two_sided", "lower"):
        result_row["ci_low"] = float(expit(eta_hat - critical * se_eta))
    if side in ("two_sided", "upper"):
        result_row["ci_high"] = float(expit(eta_hat + critical * se_eta))
    return result_row


def response_surface_probability_grid(result, factor_x, factor_y, points=31):
    """Predict a coded probability grid over two continuous RSM factors."""
    detail = result.get("detail") or {}
    model = detail.get("term_model")
    if model is None:
        raise ValueError("当前二元模型没有响应面项模型")
    factor_map = {factor.factor_id: factor for factor in result["design"].spec.factors}
    if (factor_x == factor_y or factor_x not in factor_map or factor_y not in factor_map
            or factor_map[factor_x].factor_type != "continuous"
            or factor_map[factor_y].factor_type != "continuous"):
        raise ValueError("概率响应图需要两个不同的连续因子")
    if isinstance(points, bool) or not isinstance(points, int) or points < 2:
        raise ValueError("绘图网格至少需要 2 个点")
    coded = detail["coded"]
    continuous = [factor for factor in result["design"].spec.factors
                  if factor.factor_type == "continuous"]
    positions = {factor.factor_id: index for index, factor in enumerate(continuous)}
    x_values = np.linspace(np.min(coded[:, positions[factor_x]]),
                           np.max(coded[:, positions[factor_x]]), points)
    y_values = np.linspace(np.min(coded[:, positions[factor_y]]),
                           np.max(coded[:, positions[factor_y]]), points)
    base = dict(detail["settings_rows"][0])
    for factor in continuous:
        base[factor.factor_id] = 0.0
    for factor in result["design"].spec.factors:
        if factor.factor_type == "categorical":
            base[factor.factor_id] = factor.levels[0]
    block = next((value for value in detail["block_rows"] if value is not None), None)
    rows = []
    for y_value in y_values:
        for x_value in x_values:
            settings = dict(base)
            settings[factor_x], settings[factor_y] = float(x_value), float(y_value)
            rows.append(model.row(settings, block))
    probabilities = expit(np.asarray(rows) @ result["coefficients_array"])
    return x_values, y_values, probabilities.reshape(points, points)
