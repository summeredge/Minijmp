"""构建 DSD Stepwise 的独立数学参考（精确有理数，不导入生产筛选模块）。

设计矩阵直接读取 `tests/fixtures/doe_screening_reference/dsd/*.csv`（既有独立
构造审计产物），响应由解析模型加显式整数扰动构造。Stepwise 语义按
`docs/doe-minitab/phase2-p4a-method-contract.md` 独立实现。
"""
from __future__ import annotations

import csv
import json
from fractions import Fraction
from itertools import combinations
from pathlib import Path

from scipy import stats

from exact_linear import dot, projection_coefficients, rank, sse


ROOT = Path(__file__).resolve().parent
DSD_DIR = ROOT.parent / "doe_screening_reference" / "dsd"


def read_matrix(name):
    path = DSD_DIR / name
    rows = list(csv.reader(path.read_text(encoding="utf-8").splitlines()))
    header = [f"F{index}" for index in range(1, len(rows[0]))]
    data = [[Fraction(int(value)) for value in row[1:]] for row in rows[1:]]
    return header, data


def columns(rows):
    return [list(column) for column in zip(*rows)]


def term_column(coded, names, term):
    positions = [names.index(item) for item in term]
    result = [Fraction(1)] * len(coded[0])
    for position in positions:
        result = [a * b for a, b in zip(result, coded[position])]
    return result


def _p_value(f_stat, df1, df2):
    if f_stat is None:
        return None
    return float(stats.f.sf(float(f_stat), int(df1), int(df2)))


class Model:
    """截距 + 区组 nuisance + 选定项的唯一模型矩阵。"""

    def __init__(self, n, coded, names, nuisance):
        self.n = n
        self.coded = coded
        self.names = names
        self.nuisance = nuisance

    def matrix(self, terms):
        # 与生产分析一致：截距、选定项、区组 nuisance 依次排列。
        result = [[Fraction(1)] * self.n]
        result += [term_column(self.coded, self.names, term) for term in terms]
        result += [list(column) for column in self.nuisance]
        return result

    def dimension(self, term, selected):
        """候选项在“截距 + 已选项 + 区组”之上的新增维度（正交化判定）。

        与生产实现使用同一判据：对项列做精确正交化，残差非零即计入 1 维。
        """
        base = self.matrix(selected)
        column = term_column(self.coded, self.names, term)
        coefficients = projection_coefficients(base, column)
        residual = [value - sum(c * b[i] for c, b in zip(coefficients, base))
                    for i, value in enumerate(column)]
        return 1 if any(residual) else 0


def _parents(term):
    if len(term) == 1:
        return []
    if term[0] == term[1]:
        return [(term[0],)]
    return [(term[0],), (term[1],)]


def _hierarchical(terms, extra=()):
    present = set(terms) | set(extra)
    return all(parent in present for term in terms for parent in _parents(term))


def stepwise(model, y, candidates, *, initial=(), forced=(), alpha_enter=0.15,
             alpha_remove=0.15, max_steps=200):
    """逐项移除优先、再逐项进入的确定性状态机；返回完整轨迹。"""
    order = list(dict.fromkeys(candidates))
    forced = list(dict.fromkeys(forced))
    terms = list(dict.fromkeys(list(initial) + forced))
    if not _hierarchical(terms):
        raise ValueError("初始模型或强制项不满足层级结构")
    steps, visited = [], set()
    stop = None
    for iteration in range(1, max_steps + 1):
        state = frozenset(terms)
        if state in visited:
            stop = "model_cycle_detected"
            break
        visited.add(state)
        matrix = model.matrix(terms)
        current_rank = rank(matrix)
        current_sse = sse(matrix, y)
        error_df = model.n - current_rank
        mse = None if error_df <= 0 else current_sse / error_df

        removals = []
        for term in terms:
            if term in forced:
                continue
            reduced = [item for item in terms if item != term]
            if not _hierarchical(reduced):
                continue
            reduced_matrix = model.matrix(reduced)
            reduced_rank = rank(reduced_matrix)
            df_removed = current_rank - reduced_rank
            if df_removed <= 0 or mse is None or mse <= 0:
                continue
            reduced_sse = sse(reduced_matrix, y)
            f_stat = ((reduced_sse - current_sse) / df_removed) / mse
            removals.append({"term": term, "f": f_stat, "df": df_removed,
                             "p": _p_value(f_stat, df_removed, error_df),
                             "sse_reduced": reduced_sse})
        if removals:
            best = max(removals, key=lambda row: (row["p"], -order_for(row["term"], order)))
            if best["p"] > alpha_remove:
                steps.append({
                    "step": len(steps) + 1, "action": "remove",
                    "term": list(best["term"]), "f": float(best["f"]),
                    "p": best["p"], "df_removed": best["df"],
                    "sse_before": float(current_sse),
                    "sse_after": float(best["sse_reduced"]),
                    "rank_before": current_rank,
                    "rank_after": current_rank - best["df"],
                    # 移除项降低秩，残差自由度相应增加。
                    "error_df": error_df + best["df"],
                    "terms": [list(item) for item in
                              (item for item in terms if item != best["term"])],
                })
                terms = [item for item in terms if item != best["term"]]
                continue

        entries = []
        for term in order:
            if term in terms:
                continue
            trial = terms + [term]
            if not _hierarchical(trial):
                continue
            trial_matrix = model.matrix(trial)
            df_added = model.dimension(term, terms)
            if df_added <= 0:
                continue
            trial_rank = current_rank + df_added
            trial_sse = sse(trial_matrix, y)
            trial_df = model.n - trial_rank
            if trial_df < 1:
                continue
            trial_mse = trial_sse / trial_df
            if trial_mse <= 0:
                continue
            f_stat = ((current_sse - trial_sse) / df_added) / trial_mse
            entries.append({"term": term, "f": f_stat, "df": df_added,
                            "p": _p_value(f_stat, df_added, trial_df),
                            "sse_trial": trial_sse, "rank": trial_rank})
        if entries:
            best = min(entries, key=lambda row: (row["p"], order.index(row["term"])))
            if best["p"] < alpha_enter:
                steps.append({
                    "step": len(steps) + 1, "action": "enter",
                    "term": list(best["term"]), "f": float(best["f"]),
                    "p": best["p"], "df_added": best["df"],
                    "sse_before": float(current_sse),
                    "sse_after": float(best["sse_trial"]),
                    "rank_before": current_rank, "rank_after": best["rank"],
                    "error_df": model.n - best["rank"],
                    "terms": [list(item) for item in list(terms) + [best["term"]]],
                })
                terms = list(terms) + [best["term"]]
                continue

        remaining = [term for term in order if term not in terms]
        stop = "no_eligible_entry" if remaining else "selection_stable"
        break
    else:
        stop = "iteration_budget"

    matrix = model.matrix(terms)
    final_rank = rank(matrix)
    final_sse = sse(matrix, y)
    coefficients = projection_coefficients(matrix, y)
    return {
        "alpha_enter": alpha_enter, "alpha_remove": alpha_remove,
        "initial_terms": [list(item) for item in initial],
        "forced_terms": [list(item) for item in forced],
        "candidate_terms": [list(item) for item in order],
        "selected_terms": [list(item) for item in terms],
        "selection_steps": steps, "stop_reason": stop,
        "iterations": len(steps),
        "final_rank": final_rank,
        "final_residual_df": model.n - final_rank,
        "final_sse": float(final_sse),
        "coefficients": [float(value) for value in coefficients],
    }


def order_for(term, order):
    return order.index(term) if term in order else len(order)


def orthogonal_noise(coded, seed_vector, span=()):
    """把整数向量投影掉截距、全部主效应及 span 中的列，得到正交扰动。"""
    n = len(coded[0])
    basis = [[Fraction(1)] * n] + [list(column) for column in coded] + [list(column) for column in span]
    coefficients = projection_coefficients(basis, [Fraction(value) for value in seed_vector])
    return [value - sum(c * column[i] for c, column in zip(coefficients, basis))
            for i, value in enumerate(seed_vector)]


def _case_dsd(name, matrix_name, response_builder, candidates, **kwargs):
    names = kwargs.pop("names", None)
    rows = kwargs.pop("rows", None)
    if names is None or rows is None:
        names, rows = read_matrix(matrix_name)
    else:
        rows = [[Fraction(value) for value in row] for row in rows]
    coded = columns(rows)
    n = len(rows)
    nuisance = kwargs.pop("nuisance", [])
    label = kwargs.pop("matrix", matrix_name)
    design = kwargs.pop("design", {"continuous": len(names), "categorical": 0,
                                    "replicates": 1, "blocks": 1})
    model = Model(n, coded, names, nuisance)
    y = response_builder(coded, names, n)
    result = stepwise(model, y, candidates, **kwargs)
    result.update({"id": name, "matrix": label, "factor_names": names,
                   "design": design,
                   "run_count": n, "response": [float(value) for value in y]})
    return result


def build():
    names6, rows6 = read_matrix("dsd_06_cont_13.csv")
    coded6 = columns(rows6)
    mains6 = [(name,) for name in names6]
    squares6 = [(name, name) for name in names6]
    interactions6 = list(combinations(names6, 2))
    seed = [1, -2, 0, 2, -1, 1, -2, 2, 0, -1, 1, -1, 0]

    noise_main = orthogonal_noise(coded6, seed)
    square1 = [value * value for value in coded6[0]]
    noise_square = orthogonal_noise(coded6, seed, [square1])
    interaction12 = [a * b for a, b in zip(coded6[0], coded6[1])]
    noise_interaction = orthogonal_noise(coded6, seed, [interaction12])

    def s01(coded, names, n):
        return [Fraction(40) + 5 * coded[0][i] - 3 * coded[1][i]
                + noise_main[i] / 10 for i in range(n)]

    def s02(coded, names, n):
        return [Fraction(30) + 2 * coded[0][i] + 5 * square1[i]
                + noise_square[i] / 10 for i in range(n)]

    def s03(coded, names, n):
        return [Fraction(10) + 8 * coded[0][i] + 8 * coded[1][i]
                + 6 * interaction12[i] + noise_interaction[i] / 10
                for i in range(n)]

    cases = [
        _case_dsd("DSD-S01-main-effects", "dsd_06_cont_13.csv", s01, mains6),
        _case_dsd("DSD-S02-quadratic", "dsd_06_cont_13.csv", s02,
                  mains6 + squares6),
        _case_dsd("DSD-S03-interaction", "dsd_06_cont_13.csv", s03,
                  mains6 + interactions6),
    ]

    # DSD-S04：混合连续/分类、两个完整重复区组，区组 nuisance 项强制保留。
    names_mixed, rows_mixed = read_matrix("dsd_04_cont_01_cat_14.csv")
    coded_mixed = columns(rows_mixed)
    base = [row for row in zip(rows_mixed)]
    repeated = [[value for value in row] for row in rows_mixed] * 2
    coded_rep = columns(repeated)
    n4 = len(repeated)
    # 区组 2 的指示列，与生产 analyze_dsd() 的 nuisance 列一致。
    block = [Fraction(0)] * 14 + [Fraction(1)] * 14
    interaction4 = [a * b for a, b in zip(coded_rep[0], coded_rep[1])]
    noise4 = orthogonal_noise(coded_rep, [1, -2, 0, 2, -1, 1, -2, 2, 0, -1, 1, -1,
                                          0, 1, -1, 2, 0, 1, -2, 1, 0, -1, 2, -1, 1, 0, -2, 1],
                              [block, interaction4])

    def s04(coded, names, n):
        categorical = coded[4]
        return [Fraction(20) + 4 * block[i] + 3 * coded[0][i]
                + 2 * interaction4[i] - 5 * categorical[i]
                + noise4[i] / 20 for i in range(n)]

    mixed_candidates = ([(name,) for name in names_mixed] +
                        [(name, name) for name in names_mixed[:4]] +
                        list(combinations(names_mixed, 2)))
    cases.append(_case_dsd("DSD-S04-mixed-blocks", None, s04, mixed_candidates,
                           nuisance=[block], rows=repeated,
                           names=names_mixed, forced=[], matrix="mixed-2x14",
                           design={"continuous": len(names_mixed) - 1, "categorical": 1,
                                   "replicates": 2, "blocks": 2}))

    # DSD-S05：真实出现“先进入、再删除”的确定性轨迹（混合设计，单区组）。
    # 响应含不可被候选张成空间吸收的整数扰动，避免 SSE 精确归零。
    coded_s5 = columns(rows_mixed)
    n5 = len(rows_mixed)
    candidates5 = ([(name,) for name in names_mixed] +
                   list(combinations(names_mixed, 2)) +
                   [(name, name) for name in names_mixed[:4]])
    coefficients = [0, -1, -2, 4, -3, -1, -2, -3, 2, 4, 4, -4, 3, 1, -3, 4, -4, -2, 0]
    columns5 = Model(n5, coded_s5, names_mixed, []).matrix(candidates5)[1:]
    perturbation = [Fraction(value, 9) for value in
                    (-2, 1, 0, 0, 2, 2, -2, 1, 2, 0, -2, -2, 0, 0)]

    def s05(coded, names, n):
        return [Fraction(20) + sum(c * column[i]
                                   for c, column in zip(coefficients, columns5))
                + perturbation[i]
                for i in range(n)]

    cases.append(_case_dsd("DSD-S05-enter-then-remove", None, s05, candidates5,
                           names=names_mixed, rows=rows_mixed,
                           alpha_enter=0.2, alpha_remove=0.2,
                           matrix="dsd_04_cont_01_cat_14.csv", max_steps=500,
                           design={"continuous": len(names_mixed) - 1, "categorical": 1,
                                   "replicates": 1, "blocks": 1}))
    return cases


if __name__ == "__main__":
    print(json.dumps(build(), ensure_ascii=False, indent=2)[:4000])
