"""Factorial ANOVA error partition for replicated cells and complete blocks."""
from collections import defaultdict

import numpy as np
from scipy import stats


def partition_factorial_error(response, cells, blocks):
    """Split saturated cell/block residuals from within-cell pure error.

    Blocked DOE callers validate complete, balanced blocks before using this
    partition; block-by-cell residuals are not pure error.
    """
    # shortcut: only complete balanced blocks are supported; use weighted projections if expanded.
    groups = defaultdict(list)
    cell_groups = defaultdict(list)
    block_groups = defaultdict(list)
    use_blocks = blocks is not None and len(set(blocks)) > 1
    for index, cell in enumerate(cells):
        value = float(response[index])
        key = (blocks[index], cell) if use_blocks else cell
        groups[key].append(value)
        cell_groups[cell].append(value)
        if use_blocks:
            block_groups[blocks[index]].append(value)

    pure_error_df = sum(len(values) - 1 for values in groups.values())
    pure_error_ss = sum(float(np.sum((values - np.mean(values)) ** 2))
                        for values in (np.asarray(group) for group in groups.values()))
    block_error_ss = 0.0
    block_error_df = 0
    if use_blocks:
        grand = float(np.mean(response))
        block_means = {block: float(np.mean(values))
                       for block, values in block_groups.items()}
        cell_means = {cell: float(np.mean(values)) for cell, values in cell_groups.items()}
        block_error_ss = sum(
            len(values) * (float(np.mean(values)) - block_means[block]
                           - cell_means[cell] + grand) ** 2
            for (block, cell), values in groups.items())
        block_error_df = len(response) - (len(cell_groups) + len(block_groups) - 1) - pure_error_df

    return {
        "pure_error_ss": pure_error_ss,
        "pure_error_df": pure_error_df,
        "block_error_ss": block_error_ss,
        "block_error_df": block_error_df,
    }


def _type_iii_fit(response, groups):
    """Fit grouped fixed effects and test each group by its rank increment."""
    y = np.asarray(response, dtype=float)
    if not len(y):
        raise ValueError("Type III 至少需要一个非缺失响应")
    x = np.column_stack([matrix for _, matrix in groups])
    n, p = x.shape
    centered_y = y - y.mean()
    u, singular, vt = np.linalg.svd(x, full_matrices=False)
    tolerance = (np.finfo(float).eps * max(x.shape) * singular[0]
                 if singular.size else 0.0)
    rank = int(np.count_nonzero(singular > tolerance))
    q = u[:, :rank]
    beta = (vt[:rank].T @ ((q.T @ centered_y) / singular[:rank])
            if rank else np.zeros(p))
    beta[0] += y.mean()
    covariance_diagonal = (
        (vt[:rank].T ** 2) @ (1 / singular[:rank] ** 2)
        if rank else np.zeros(p))
    residuals = centered_y - q @ (q.T @ centered_y)
    fitted = y - residuals
    sse = float(residuals @ residuals)
    df = n - rank
    sst = float(centered_y @ centered_y)
    tolerance_ss = np.finfo(float).eps * max(n, p) * max(sst, 1.0)
    mse = sse / df if df > 0 and sse > tolerance_ss else None

    tests = []
    coefficient_estimable = []
    for index, (name, matrix) in enumerate(groups):
        width = matrix.shape[1]
        reduced = np.column_stack([
            other for other_index, (_, other) in enumerate(groups)
            if other_index != index
        ]) if len(groups) > 1 else np.empty((n, 0))
        if reduced.shape[1]:
            reduced_u, reduced_singular, _ = np.linalg.svd(reduced, full_matrices=False)
            reduced_tolerance = (np.finfo(float).eps * max(reduced.shape)
                                 * reduced_singular[0] if reduced_singular.size else 0.0)
            reduced_rank = int(np.count_nonzero(reduced_singular > reduced_tolerance))
            reduced_q = reduced_u[:, :reduced_rank]
        else:
            reduced_rank = 0
            reduced_q = np.empty((n, 0))
        effect_df = rank - reduced_rank
        estimable = effect_df == width
        ss = None
        if estimable:
            added = q - reduced_q @ (reduced_q.T @ q)
            added_u, _, _ = np.linalg.svd(added, full_matrices=False)
            added_q = added_u[:, :effect_df]
            ss = float(np.sum((added_q.T @ centered_y) ** 2))
        ms = ss / effect_df if estimable and effect_df else None
        f_value = ms / mse if ms is not None and mse is not None else None
        status = ("可估计" if estimable else
                  f"不可估计（秩差 {effect_df}/{width}）")
        if estimable and mse is None:
            status += "；误差自由度或 MSE 不可用"
        tests.append({"term": name, "ss": ss, "df": effect_df,
                      "ms": ms, "f": f_value,
                      "p": float(stats.f.sf(f_value, effect_df, df))
                      if f_value is not None else None,
                      "estimable": estimable, "status": status})
        coefficient_estimable.extend([estimable] * width)

    coefficients = [float(value) if estimable else None
                    for value, estimable in zip(beta, coefficient_estimable)]
    se = [None] * p
    t_values = [None] * p
    p_values = [None] * p
    ci_low = [None] * p
    ci_high = [None] * p
    model_f = model_p = None
    ssr = max(0.0, sst - sse)
    if mse is not None:
        critical = stats.t.ppf(.975, df)
        for i, estimable in enumerate(coefficient_estimable):
            if estimable:
                standard_error = float(np.sqrt(covariance_diagonal[i] * mse))
                se[i] = standard_error
                if standard_error > 0:
                    t_values[i] = float(beta[i] / standard_error)
                    p_values[i] = float(2 * stats.t.sf(abs(t_values[i]), df))
                    ci_low[i] = float(beta[i] - critical * standard_error)
                    ci_high[i] = float(beta[i] + critical * standard_error)
        model_df = rank - 1
        if model_df > 0:
            model_f = (ssr / model_df) / mse
            model_p = float(stats.f.sf(model_f, model_df, df))
    return {
        "coefficients": coefficients, "fitted": fitted, "residuals": residuals,
        "sse": sse, "sst": sst, "ssr": ssr, "rank": rank, "df": df,
        "mse": mse, "tests": tests,
        "inference": {"mse": mse, "se": se, "t": t_values, "p": p_values,
                      "ci_low": ci_low, "ci_high": ci_high,
                      "f": model_f, "model_p": model_p},
    }
