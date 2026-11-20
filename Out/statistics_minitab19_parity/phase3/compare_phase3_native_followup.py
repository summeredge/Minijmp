"""Compare the fixed Phase 3 follow-up against current production functions."""
from collections import Counter
import csv
from itertools import combinations
import json
from math import log, sqrt
from pathlib import Path
import re
import sys

import numpy as np
import pandas as pd
from scipy import stats

from verify_phase3_native_followup import FACTORS, HERE, ROOT

sys.path.insert(0, str(ROOT / "code"))
sys.path.insert(0, str(HERE.parent / "phase6"))
from advanced_regression import _binary_gof, fit_regression
from bonett import var_1sample
from dist_fit import fit_intervals, fit_lognorm, fit_norm
from doe_core import DesignSpec, FactorSpec
from doe_dsd import create_dsd
from ti import ti_nonparametric
from verify_statistics_minitab19_phase6 import (display_tokens, native_parameter_tokens,
                                               native_percentiles, reported_match)


def compare(native):
    rows = []

    def add(case, metric, reference, local, source, status=None):
        if status is None:
            text = str(reference)
            if re.fullmatch(r"-?\d+(?:\.\d+)?", text):
                decimals = len(text.partition(".")[2])
                status = "PASS" if abs(float(text) - local) <= .5 * 10**(-decimals) else "FAIL"
            else:
                status = "PASS" if reference == local else "FAIL"
        rows.append((case, metric, reference, local, status, source))

    def document(label):
        entry = next(value for value in native["commands"] if value.startswith(f"===== {label} "))
        return entry.split("OutputDocument.Text:", 1)[1].split("Output.Text[1]:", 1)[0]

    frozen4 = HERE.parent / "phase4"
    cases4 = json.loads((frozen4 / "case_inputs.json").read_text(encoding="utf-8-sig"))["cases"]
    reference4 = list(csv.DictReader((frozen4 / "minitab_reference.csv").read_text(
        encoding="utf-8-sig").splitlines()))

    def archived(command, field):
        row = next(row for row in reference4
                   if row["command_id"] == command and row["统计量"] == field)
        return f'{float(row["Minitab值"]):.{int(row["显示小数位"])}f}'

    values = cases4["one_variance"]["values"]
    local = var_1sample(values, .1, 3)
    for label, s0, tail in (("G05_left", 3, "lt"), ("G05_right_at_4", 4, "gt"),
                            ("G05_right_at_12", 12, "gt")):
        token = re.search(r"Bonett\s+—\s+—\s+(\d\.\d+)", document(label))[1]
        add("G05", f"p {tail} sigma0={s0}", token,
            var_1sample(values, .1, s0)[f"Bonett p {tail}"], label)
    add("G05", "p gt sigma0=3", archived("one_variance_right", "右侧 Bonett p 值"),
        local["Bonett p gt"], "phase4:one_variance_right")
    add("G05", "90% upper", "5.24", local["One tail upper boundary"], "G05_left")
    add("G05", "90% lower", archived("one_variance_right", "右侧 Bonett 90% CI 下限"),
        local["One tail lower boundary"], "phase4:one_variance_right")
    two_sided = "one_variance_two_sided"
    add("G05", "two-sided p", archived(two_sided, "Bonett 双侧 p 值"),
        local["Bonett p"], f"phase4:{two_sided}")
    for end, field, value in zip(("lower", "upper"), ("下限", "上限"), local["Bonett CI"], strict=True):
        add("G05", f"two-sided CI {end}", archived(two_sided, f"Bonett 双侧 CI {field}"),
            value, f"phase4:{two_sided}")

    frozen6 = json.loads((HERE.parent / "phase6/minitab_results.json").read_text(encoding="utf-8-sig"))
    for case in ("normal_ties", "right_skew_ties_missing"):
        values = [x for x in native["inputs"][case]["values"] if x is not None]
        for name, command, heading in (("Normal", "NORMAL", "正态"),
                                       ("Lognormal", "LNORMAL", "对数正态")):
            label = f"G03_{case}_{command}"
            output = document(label)
            location, scale = re.search(rf"^{heading}\*\s+([\d.]+)\s+([\d.]+)",
                                         output, re.M).groups()
            mu, sigma = (fit_norm if name == "Normal" else fit_lognorm)(values, False)["fits"]
            if name == "Lognormal":
                mu = log(mu)
            for value, token in zip((mu, sigma), native_parameter_tokens(frozen6, case, name),
                                    strict=True):
                assert reported_match(value, token)[0] == "PASS", (case, name, value, token)
            add("G03", f"{case} {name} location", location, mu, label)
            add("G03", f"{case} {name} scale", scale, sigma, label)
            _, intervals = fit_intervals(name, mu, sigma, len(values))
            archived_percentiles = native_percentiles(frozen6, case, name)
            for pct, point, se, lower, upper in intervals:
                tokens = re.search(rf"^{heading}\s+{pct}\s+(.+)$", output, re.M)[1].split()
                old_tokens = display_tokens(archived_percentiles[pct][1])[1:]
                for value, token in zip((point, se, lower, upper), old_tokens, strict=True):
                    assert reported_match(value, token)[0] == "PASS", (case, name, pct, value, token)
                for metric, token, value in zip(("point", "SE", "lower", "upper"), tokens,
                                                (point, se, lower, upper), strict=True):
                    add("G03", f"{case} {name} {pct}% {metric}", token, value, label)
            add("G03", f"{case} {name} parameter SE/CI", "", "reported", label, "NOT_RUN")

    for n in (100, *range(1, 11)):
        local = ti_nonparametric(native["inputs"][f"n{n}"])
        for direction, metric in ((0, "TI"), (-1, "Lower Bound"), (1, "Upper Bound")):
            label = f"G07_{'n100' if n == 100 else 'n1' if n == 1 else 'small'}_{direction}"
            output = document(label)
            if n == 1:
                assert "列中没有足够的数据" in output
                add("G07", f"n{n} {metric}", "unavailable", "unavailable" if
                    local[metric] in (None, (None, None)) else local[metric], label)
                continue
            line = re.search(rf"^n{n}\s+(.+)$", output, re.M)[1]
            tokens = re.findall(r"-?\d+(?:\.\d+)?", line)
            endpoint = tuple(map(float, tokens[2:4])) if direction == 0 else float(tokens[1])
            local_endpoint = local[metric]
            if direction == 0:
                local_endpoint = tuple(None if x is None else float(x) for x in local_endpoint)
            add("G07", f"n{n} {metric}", endpoint, local_endpoint, label,
                "METHOD_DIFF" if n < 100 or direction == 0 else None)
            add("G07", f"n{n} {metric} confidence (%)", tokens[-1],
                100 * local["two_sided_confidence" if direction == 0 else "one_sided_confidence"],
                label, "METHOD_DIFF" if n == 100 and direction == 0 else None)
            if n == 100 and direction == 0:
                # The uniform order-statistic spacing has a Beta(s-r, n+1-s+r) law.
                r, s = map(int, endpoint)
                add("G07", "native two-sided confidence (%) from native ranks",
                    tokens[-1], 100 * stats.beta.sf(.9, s-r, n+1-s+r), label)

    design = native["design"]
    observed = pd.DataFrame(design).sort_values("标准序")
    factors = tuple(FactorSpec(name, name, -1, 1) for name in FACTORS[:13]) + tuple(
        FactorSpec(name, name, None, None, factor_type="categorical", levels=("Low", "High"))
        for name in FACTORS[13:])
    identity = {"construction_id": "dsd13c3.v1", "source_kind": "mathematical_construction",
                "source_id": "jones.dsd13c3", "matrix_sha256": "0" * 64}
    spec = DesignSpec("dsd", factors, ("Y",), seed=41, design_type="definitive_screening",
                      screening_matrix=identity, schema_version=5)
    local, _ = create_dsd(spec, replicates=1, center_points=0)
    local = local.sort_values("标准序")
    native_points = observed[FACTORS].replace({"Low": -1, "High": 1}).to_numpy(dtype=int)
    local_points = local[[f"设定_{name}" for name in FACTORS]].replace(
        {"Low": -1, "High": 1}).to_numpy(dtype=int)

    def design_metrics(points):
        main = np.column_stack((np.ones(len(points)), points))
        two_factor = np.column_stack([points[:, i] * points[:, j]
                                      for i, j in combinations(range(16), 2)])
        return {"runs": len(points),
                "pseudo-centers": int((points[:, :13] == 0).all(axis=1).sum()),
                "main rank": int(np.linalg.matrix_rank(main)),
                "main vs 2FI max cross-product": int(np.abs(points.T @ two_factor).max()),
                "main plus 2FI rank": int(np.linalg.matrix_rank(np.column_stack((main, two_factor)))),
                "levels": tuple(tuple(sorted(set(map(int, column)))) for column in points.T)}

    source = "G08_13plus3 / native worksheet"
    assert list(observed["标准序"]) == list(observed["运行序"]) == list(range(1, 35))
    local_metrics = design_metrics(local_points)
    for field, reference in design_metrics(native_points).items():
        value = local_metrics[field]
        add("G08", field, reference, value, source,
            "METHOD_DIFF" if reference != value else "PASS")
    match = np.array_equal(native_points, local_points)
    add("G08", "same rows in standard order", True, match, source,
        "PASS" if match else "METHOD_DIFF")
    counts = Counter(map(tuple, native_points)) & Counter(map(tuple, local_points))
    add("G08", "point multiset overlap", len(native_points), counts.total(), source,
        "PASS" if counts.total() == len(native_points) else "METHOD_DIFF")
    for group_name, group, native_bounds in zip(
            "ABC", cases4["multi_variance"]["groups"].values(),
            (("1.98865", "8.61111"), ("2.34825", "8.41017"), ("2.06587", "8.37558")), strict=True):
        bounds = var_1sample(group, .05/3, np.std(group, ddof=1))["Bonett CI"]
        for end, token, value in zip(("lower", "upper"), native_bounds, bounds, strict=True):
            add("G06", f"Bonferroni {group_name} {end}", token, value, "phase4:VARTEST")

    groups = [np.sort(group) for group in cases4["multi_variance"]["groups"].values()]
    assert all(len(group) == 8 for group in groups)
    b = []
    for first, second in combinations(groups, 2):
        pooled = 16 * sum(np.sum((g - g[2:-2].mean())**4) for g in (first, second))
        pooled /= sum(np.sum((g - g.mean())**2) for g in (first, second))**2
        # With exactly three groups, least squares fits all three pairwise widths exactly.
        q = sqrt(2) * abs(log(first.var(ddof=1) / second.var(ddof=1))) / sqrt(2*(pooled-5/8)/7)
        b.append(stats.studentized_range.sf(q, 3, np.inf))
    add("G06", "global MC p (independent Minitab formula)", "0.966", min(b), "phase4:VARTEST")
    add("G06", "global MC vs MiniJMP", "0.966", "pairwise Bonett / Bonferroni",
        "phase4:VARTEST", "METHOD_DIFF")

    case = cases4["binary_logistic"]
    fit = fit_regression(pd.DataFrame({"y": case["y"], "x": case["x"]}), "y", ["x"],
                         model="Logistic")
    metrics = fit.tables["summary"].iloc[0]
    y = np.array(case["y"])
    p = fit.tables["observations"]["probability"].to_numpy()
    deviance = float(-2 * np.where(y == 1, np.log(p), np.log1p(-p)).sum())
    pearson = float(((y - p)**2 / (p*(1-p))).sum())
    for field, token, value in (("Bernoulli deviance", "40.05", deviance),
                                ("Bernoulli Pearson", "36.57", pearson),
                                ("Bernoulli df", "34", metrics.df_resid),
                                ("Bernoulli deviance p", "0.219", stats.chi2.sf(deviance, metrics.df_resid)),
                                ("Bernoulli Pearson p", "0.350", stats.chi2.sf(pearson, metrics.df_resid)),
                                ("deviance R2 (%)", "19.03", 100*metrics.deviance_r_squared),
                                ("adjusted deviance R2 (%)", "17.01", 100*metrics.adj_deviance_r_squared),
                                ("AICc", "44.41", metrics.aicc)):
        add("G09", field, token, value, "phase4:GZLM")
    gof = _binary_gof(y, np.column_stack((np.ones(len(y)), case["x"])), p, 2)
    add("G09", "grouped deviance", "40.05", gof["deviance"], "phase4:GZLM", "METHOD_DIFF")
    add("G09", "grouped Pearson", "36.57", gof["pearson"], "phase4:GZLM", "METHOD_DIFF")
    add("G09", "grouped df", "34", gof["df"], "phase4:GZLM", "METHOD_DIFF")
    for statistic, token in (("deviance", "0.219"), ("pearson", "0.350")):
        add("G09", f"grouped {statistic} p", token,
            stats.chi2.sf(gof[statistic], gof["df"]), "phase4:GZLM", "METHOD_DIFF")
    add("G09", "HL chi-square", "0.24", gof["hl_square"], "phase4:GZLM")
    add("G09", "HL df", "4", gof["hl_df"], "phase4:GZLM")
    add("G09", "HL p", "0.993", stats.chi2.sf(gof["hl_square"], gof["hl_df"]), "phase4:GZLM")
    return rows


if __name__ == "__main__":
    native = json.loads((HERE / "native_followup_20261120.json").read_text(encoding="utf-8"))
    assert native["version"] == "19.1.0.1"
    rows = compare(native)
    with (HERE / "comparison_followup.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(("id", "metric", "minitab", "minijmp_or_independent", "status", "source"))
        writer.writerows(rows)
    print(Counter(row[4] for row in rows))
    for row in rows:
        if row[4] == "FAIL":
            print(row)
    raise SystemExit(any(row[4] == "FAIL" for row in rows))
