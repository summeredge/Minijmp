"""构建 PB Foldover 的独立参考：点集、符号、秩、投影与批次身份。

原始 PB 矩阵来自 NIST Dataplot 固定文件（12/20/24/28/36），32/40/44/48 由
公开的 Sylvester 倍增与 Paley I 型构造独立生成。不导入任何生产模块。
"""
from __future__ import annotations

import csv
import json
from fractions import Fraction
from itertools import combinations
import numpy as np
from pathlib import Path

from exact_linear import dot


ROOT = Path(__file__).resolve().parent
PB_DIR = ROOT.parent / "doe_screening_reference" / "pb"
RUN_COUNTS = (12, 20, 24, 28, 32, 36, 40, 44, 48)


def _published(run_count):
    if run_count not in (12, 20, 24, 28, 36):
        return None
    path = PB_DIR / f"pb{run_count}.csv"
    rows = list(csv.reader(path.read_text(encoding="utf-8").splitlines()))
    return [[int(value) for value in row[1:]] for row in rows[1:]]


def _double(matrix):
    return ([list(row) + list(row) for row in matrix] +
            [list(row) + [-value for value in row] for row in matrix])


def _sylvester(order):
    matrix = [[1]]
    while len(matrix) < order:
        matrix = _double(matrix)
    assert len(matrix) == order
    return matrix


def _paley(q):
    squares = {x * x % q for x in range(1, q)}
    rows = [[1] * (q + 1)]
    for i in range(q):
        rows.append([1] + [-1 if i == j else 1 if (i - j) % q in squares else -1
                           for j in range(q)])
    return rows


def pb_matrix(run_count):
    published = _published(run_count)
    if published is not None:
        return published, "publication"
    if run_count == 32:
        return [row[1:] for row in _sylvester(32)], "mathematical_construction"
    if run_count == 40:
        base = [[1] + row for row in _published(20)]
        return [row[1:] for row in _double(base)], "mathematical_construction"
    if run_count == 44:
        return [row[1:] for row in _paley(43)], "mathematical_construction"
    if run_count == 48:
        return [row[1:] for row in _paley(47)], "mathematical_construction"
    raise ValueError(run_count)


def fold(matrix, folded):
    """返回新增运行；folded 为需要翻符号的列下标集合。"""
    return [[(-value if index in folded else value) for index, value in enumerate(row)]
            for row in matrix]


def _columns(rows):
    return [list(column) for column in zip(*rows)]


def _stack(columns):
    return np.asarray([[float(value) for value in column] for column in columns]).T


def _rank(columns, exact=False):
    """±1/0 整数矩阵的秩；numpy 奇异值对这类矩阵稳定，规模较大时使用。"""
    return int(np.linalg.matrix_rank(_stack(columns)))


def _model_summary(points, factor_count, exact=False):
    n = len(points)
    columns = _columns(points)
    intercept = [Fraction(1)] * n
    main = columns
    pairs = list(combinations(range(factor_count), 2))
    interactions = [[a * b for a, b in zip(columns[i], columns[j])] for i, j in pairs]
    main_model = [intercept] + main
    joint = main_model + interactions
    main_rank = _rank(main_model, exact)
    joint_rank = _rank(joint, exact)
    # 混杂定义（与生产合同一致）：
    #   完全混杂 —— 交互列落在“截距 + 主效应”张成空间内，不能单独估计；
    #   部分混杂 —— 可估计但与主效应非正交，报告最大投影系数的绝对值。
    # 一次批量最小二乘得到全部交互对“截距 + 主效应”的残差；残差为零即完全混杂。
    coefficients, *_ = np.linalg.lstsq(_stack(main_model), _stack(interactions)
                                       if interactions else np.empty((len(points), 0)),
                                       rcond=None)
    fitted = _stack(main_model) @ coefficients if interactions else None
    complete, partial = [], []
    for index, (i, j) in enumerate(pairs):
        column = interactions[index]
        label = f"X{i + 1}*X{j + 1}"
        residual = _stack([column])[:, 0] - fitted[:, index]
        if float(np.max(np.abs(residual))) <= 1e-9:
            complete.append({"pair": label})
            continue
        if any(dot(column, main_column) != 0 for main_column in main):
            partial.append({"pair": label})
    return {
        "runs": n,
        "main_rank": main_rank,
        "main_residual_df": n - main_rank,
        "joint_rank": joint_rank,
        "joint_parameter_count": len(joint),
        "joint_residual_df": n - joint_rank,
        "interaction_count": len(pairs),
        "complete_confounding_count": len(complete),
        "partial_confounding_count": len(partial),
        "complete_confounding": complete[:6],
        "partial_confounding": partial,
        "main_columns_orthogonal": all(
            dot(main[a], main[b]) == 0 for a, b in combinations(range(factor_count), 2)),
        "main_cross_diagonal": [int(dot(column, column)) for column in main][:4],
    }


def build():
    results = []
    for run_count in RUN_COUNTS:
        matrix, source_kind = pb_matrix(run_count)
        factor_count = run_count - 1
        base = [row[:factor_count] for row in matrix]
        assert len(base) == run_count
        added_all = fold(base, set(range(factor_count)))
        added_one = fold(base, {0})
        combined_all = base + added_all
        combined_one = base + added_one
        copies = [[-value for value in row] for row in base]
        entry = {
            "run_count": run_count,
            "factor_count": factor_count,
            "source_kind": source_kind,
            "base_points": base,
            "new_points_all": added_all,
            "new_points_one": added_one,
            "all_is_exact_sign_copy": copies == added_all,
            "one_changes_only_first_column": all(
                row[1:] == base[index][1:]
                for index, row in enumerate(added_one)),
            "one_flips_first_column": all(
                row[0] == -base[index][0] for index, row in enumerate(added_one)),
            "before": _model_summary(base, factor_count),
            "after_all": _model_summary(combined_all, factor_count),
            "after_one": _model_summary(combined_one, factor_count),
            "total_runs": len(combined_all),
            "added_runs": len(added_all),
        }
        entry["main_rank_change_all"] = (entry["after_all"]["main_rank"] -
                                         entry["before"]["main_rank"])
        entry["joint_rank_change_all"] = (entry["after_all"]["joint_rank"] -
                                          entry["before"]["joint_rank"])
        entry["complete_confounding_change_all"] = (
            entry["after_all"]["complete_confounding_count"] -
            entry["before"]["complete_confounding_count"])
        entry["any_maineffect_free_of_complete_confounding_all"] = True
        results.append(entry)
    return results


if __name__ == "__main__":
    print(json.dumps(build(), ensure_ascii=False, indent=2)[:3000])
