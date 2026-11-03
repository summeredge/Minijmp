from __future__ import annotations

import csv
import json
import math
import sys
import traceback
from collections import Counter
from pathlib import Path


PHASE = Path(__file__).resolve().parent
ROOT = PHASE.parents[2]
CODE = ROOT / "code"
INPUT = PHASE / "case_inputs.json"
REFERENCE = PHASE / "minitab_reference.csv"
MTB_EXE = Path(r"D:\Program\Minitab 19\Mtb.exe")
PROJECT_PYTHON = ROOT / ".venv" / "Scripts" / "python.exe"
STATUS_ORDER = ("PASS", "FAIL", "METHOD_DIFF", "UNSUPPORTED", "NOT_RUN")
COMPARISON_FIELDS = (
    "case_id", "功能", "统计量", "Minitab值", "MiniJMP值", "绝对误差",
    "容差", "结果", "Minitab结果来源", "MiniJMP结果来源", "统计定义/配置", "判断依据",
    "测试数据集", "Minitab参考版本", "Minitab原生字段", "Minitab存储列", "Minitab存储索引", "Minitab原生输出行",
)

sys.path.insert(0, str(CODE))
sys.path.insert(0, str(ROOT / "Out" / "minitab19_parity"))

import verify_minitab19_com as com_check  # noqa: E402
from verify_doe_2x2 import capture_command_output, running_minitab_pids  # noqa: E402


COMMANDS = {
    "one_sample_t_two_sided": "ONET C1;\n  TEST 10.5;\n  CONFIDENCE 90;\n  SPVALUE C61;\n  SCONF C62 C63.",
    "one_sample_t_right": "ONET C1;\n  TEST 10.5;\n  ALTERNATIVE 1;\n  CONFIDENCE 90;\n  SPVALUE C64;\n  SCONF C65 C66.",
    "paired_t_two_sided": "PAIR C2 C3;\n  TEST 0;\n  CONFIDENCE 90;\n  SPVALUE C67;\n  SCONF C68 C69.",
    "paired_t_right": "PAIR C2 C3;\n  TEST 0;\n  ALTERNATIVE 1;\n  CONFIDENCE 90;\n  SPVALUE C70;\n  SCONF C71 C72.",
    "pooled_t_two_sided": "TWOSAMPLE 90 C4 C5;\n  TEST 0;\n  POOLED;\n  SPVALUE C73;\n  SCONF C74 C75.",
    "pooled_t_right": "TWOSAMPLE 90 C4 C5;\n  TEST 0;\n  POOLED;\n  ALTERNATIVE 1;\n  SPVALUE C76;\n  SCONF C77 C78.",
    "one_variance_two_sided": "ONEV C6;\n  STEST 3;\n  CONFIDENCE 90.",
    "one_variance_right": "ONEV C6;\n  STEST 3;\n  ALTERNATIVE 1;\n  CONFIDENCE 90.",
    "one_proportion_default": "PONE 20 12;\n  TEST 0.5;\n  CONFIDENCE 90;\n  SPVALUE C79;\n  SCONF C80 C81.",
    "one_proportion_normal": "PONE 20 12;\n  TEST 0.5;\n  CONFIDENCE 90;\n  USEZ;\n  SPVALUE C82;\n  SCONF C83 C84.",
    "one_proportion_normal_right": "PONE 20 12;\n  TEST 0.5;\n  ALTERNATIVE 1;\n  CONFIDENCE 90;\n  USEZ;\n  SPVALUE C103;\n  SCONF C104 C105.",
    "two_proportion_default": "PTWO 20 12 20 9;\n  TEST 0;\n  CONFIDENCE 90;\n  SPVALUE C85;\n  SFISHER C86;\n  SCONFC C87 C88.",
    "two_proportion_pooled": "PTWO 20 12 20 9;\n  TEST 0;\n  CONFIDENCE 90;\n  POOLED;\n  SPVALUE C89;\n  SFISHER C90;\n  SCONFC C91 C92.",
    "two_proportion_right": "PTWO 20 12 20 9;\n  TEST 0;\n  ALTERNATIVE 1;\n  CONFIDENCE 90;\n  SPVALUE C106;\n  SFISHER C107;\n  SCONFC C108 C109.",
    "two_proportion_pooled_right": "PTWO 20 12 20 9;\n  TEST 0;\n  POOLED;\n  ALTERNATIVE 1;\n  CONFIDENCE 90;\n  SPVALUE C110;\n  SFISHER C111;\n  SCONFC C112 C113.",
    "multi_variance": "VARTEST C9 C10.",
    "one_way_anova_fisher": (
        "ONEWAY;\n  RESPONSE C11;\n  CATEGORICAL C12;\n  CONFIDENCE 95;\n"
        "  FISHER;\n  TANOVA;\n  TMEANS;\n  TMTEST."
    ),
    "two_way_anova_type3": (
        "GLM;\n  RESPONSE C13;\n  CATEGORICAL C14 C15;\n  TERMS C14 C15 C14*C15;\n"
        "  EFFECT;\n  TANOVA;\n  TSUMMARY."
    ),
    "ols_multiple": (
        "REGRESS;\n  RESPONSE C16;\n  CONTINUOUS C17 C18;\n  TERMS C17 C18;\n"
        "  CONSTANT;\n  UNSTANDARDIZED;\n  CONFIDENCE 95;\n  TCOEFFICIENTS;\n"
        "  TANOVA;\n  TSUMMARY;\n  TDIAGNOSTICS 1;\n  RESIDUALS C93;\n"
        "  SRESIDUALS C94;\n  HI C95;\n  COOK C96;\n  FITS C97."
    ),
    "ols_categorical": (
        "REGRESS;\n  RESPONSE C27;\n  CATEGORICAL C28;\n  TERMS C28;\n  CONSTANT;\n"
        "  UNSTANDARDIZED;\n  BINARY;\n  REFERENCE C28 \"A\";\n  CONFIDENCE 95;\n"
        "  TCOEFFICIENTS;\n  TANOVA;\n  TSUMMARY."
    ),
    "ols_prediction": (
        "PREDICT \"multiple_regression|1\";\n  CPREDICTORS C25 C26;\n  CONFIDENCE 95;\n"
        "  TPREDICTION;\n  PFITS C114;\n  PSEFITS C115;\n  CLIMITS C116 C117;\n  PLIMITS C118 C119."
    ),
    "binary_logistic": (
        "GZLM;\n  BINOMIAL;\n  LOGIT;\n  RESPONSE C21;\n  CONTINUOUS C22;\n"
        "  TERMS C22;\n  TCOEFFICIENTS;\n  TSUMMARY;\n  TDEVIANCE;\n"
        "  COEFFICIENTS C120;\n  SECOEFFICIENTS C121."
    ),
    "poisson": (
        "GZLM;\n  POISSON;\n  LOG;\n  RESPONSE C23;\n  CONTINUOUS C24;\n"
        "  TERMS C24;\n  TCOEFFICIENTS;\n  TSUMMARY;\n  TDEVIANCE;\n"
        "  COEFFICIENTS C122;\n  SECOEFFICIENTS C123."
    ),
    "spearman_correlation": (
        "CORRELATION C29 C30;\n  SPEARMAN;\n  NODEFAULT;\n"
        "  SCORRELATION M3;\n  SPVALUES M4."
    ),
    "kendall_association": "XTABS C29 C30;\n  COUNTS;\n  CONCORDANT.",
}


def load_inputs() -> dict:
    return json.loads(INPUT.read_text(encoding="utf-8"))


def write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def finite(value):
    value = float(value)
    if not math.isfinite(value):
        raise ValueError(f"MiniJMP 结果不是有限值：{value}")
    return value


def production_results(cases: dict) -> dict:
    import pandas as pd
    from advanced_regression import fit_regression
    from chi_sq import multi_pop_var_test, var_1sample
    from one_way_ANOVA import JMP_ANOVA_t_test, one_way_anova
    from proportion_test import prop_2sample, prop_test_1sample
    from t_test import paired_t_test, t_test_1sample, t_test_2samples
    from two_way_anova import two_way_anova

    out = {}

    def add(case_id, metric, value, source):
        out[f"{case_id}.{metric}"] = {"value": finite(value), "source": source}

    c = cases["one_sample_t"]
    r = t_test_1sample(c["values"], c["mu0"], alpha=0.10)
    for key, value in (("n", len(c["values"])), ("mean", r["mean"]), ("stdev", r["stdev"]),
                       ("mean_se", r["stdev"] / math.sqrt(len(c["values"]))),
                       ("t", r["t"]), ("df", r["df"]), ("p_two", r["p"]),
                       ("p_right", r["p gt"]), ("ci_low", r["u0_95range"][0]),
                       ("ci_high", r["u0_95range"][1]), ("right_bound", r["u0 lower"])):
        add("one_sample_t", key, value, "t_test.t_test_1sample")

    c = cases["paired_t"]
    r = paired_t_test(c["sample1"], c["sample2"], u0=c["null_difference"], alpha=0.10)
    for key, value in (("n", len(c["sample1"])), ("mean_difference", r["mean"]), ("stdev_difference", r["stdev"]),
                       ("se_difference", r["stdev"] / math.sqrt(len(c["sample1"]))),
                       ("t", r["t"]), ("df", r["df"]), ("p_two", r["p"]),
                       ("p_right", r["p gt"]), ("ci_low", r["u0_95range"][0]),
                       ("ci_high", r["u0_95range"][1]), ("right_bound", r["u0 lower"])):
        add("paired_t", key, value, "t_test.paired_t_test")

    c = cases["two_sample_pooled_t"]
    r = t_test_2samples(c["sample2"], c["sample1"], alpha=0.10, d0=c["null_difference"], pooled=True)
    n1, n2 = len(c["sample1"]), len(c["sample2"])
    mean1, mean2 = sum(c["sample1"])/n1, sum(c["sample2"])/n2
    import statistics
    pooled_sd = math.sqrt(((n1-1)*statistics.variance(c["sample1"])+(n2-1)*statistics.variance(c["sample2"]))/(n1+n2-2))
    for key, value in (("n1", len(c["sample1"])), ("n2", len(c["sample2"])),
                       ("mean1", mean1), ("mean2", mean2),
                       ("stdev1", statistics.stdev(c["sample1"])),
                       ("stdev2", statistics.stdev(c["sample2"])),
                       ("difference", mean1-mean2), ("pooled_sd", pooled_sd),
                       ("se_difference", pooled_sd*math.sqrt(1/n1+1/n2)),
                       ("t", r["t"]), ("df", r["df"]), ("p_two", r["p"]),
                       ("p_right", r["p upper"]), ("ci_low", r["CI"][0]), ("ci_high", r["CI"][1])):
        add("two_sample_pooled_t", key, value, "t_test.t_test_2samples(pooled=True); contrast sample1 - sample2")

    c = cases["one_variance"]
    r = var_1sample(data=c["values"], s0=c["sigma0"], alpha=0.10)
    chi_square = (r["n"]-1) * (r["stdev"]/c["sigma0"])**2
    for key, value in (("n", r["n"]), ("stdev", r["stdev"]), ("chi_square", chi_square),
                       ("variance", r["stdev"]**2),
                       ("df", r["df"]), ("p_two", r["p"]), ("p_right", r["p gt"]),
                       ("chi_ci_low", r["CI 95"][0]), ("chi_ci_high", r["CI 95"][1]),
                       ("chi_right_lower", r["CI lower"]),
                       ("bonett_p", r["Bonett p"]), ("bonett_ci_low", r["Bonett CI"][0]),
                       ("bonett_ci_high", r["Bonett CI"][1]),
                       ("bonett_right_lower", r["One tail lower boundary"])):
        add("one_variance", key, value, "chi_sq.var_1sample menu entry; chi-square and Bonett methods")

    c = cases["one_proportion"]
    r = prop_test_1sample(c["events"], c["trials"], c["p0"], alpha=0.10)
    sample_p = c["events"] / c["trials"]
    from scipy.stats import norm
    z = (sample_p-c["p0"]) / math.sqrt(c["p0"]*(1-c["p0"])/c["trials"])
    for key, value in (("trials", c["trials"]), ("events", c["events"]), ("sample_p", sample_p),
                       ("z_normal", z), ("p_normal_right", 1-r["Z p less"]),
                       ("ci_normal_right_lower", r["CI norm"]["CI low"]),
                       ("p_default_exact", r["p Blaker"]), ("ci_default_low", r["CI exact"]["CI l"]),
                       ("ci_default_high", r["CI exact"]["CI u"]), ("p_normal", r["p norm"]),
                       ("ci_normal_low", r["CI norm"]["CI l"]), ("ci_normal_high", r["CI norm"]["CI u"])):
        add("one_proportion", key, value, "proportion_test.prop_test_1sample")

    c = cases["two_proportion"]
    r = prop_2sample(c["n1"], c["n2"], c["events1"], c["events2"], alpha=0.10)
    p1, p2 = c["events1"] / c["n1"], c["events2"] / c["n2"]
    se = math.sqrt(p1 * (1-p1) / c["n1"] + p2 * (1-p2) / c["n2"])
    pooled = (c["events1"]+c["events2"])/(c["n1"]+c["n2"])
    se_pooled = math.sqrt(pooled*(1-pooled)*(1/c["n1"]+1/c["n2"]))
    ci = (p1-p2 + norm.ppf(0.05)*se, p1-p2 + norm.ppf(0.95)*se)
    for key, value in (("n1", c["n1"]), ("n2", c["n2"]), ("events1", c["events1"]),
                       ("events2", c["events2"]), ("p1", p1), ("p2", p2), ("difference", p1-p2),
                       ("z_default_normal", (p1-p2)/se), ("z_pooled", (p1-p2)/se_pooled),
                       ("p_default_normal", r["p sep"]), ("p_pooled", r["p Pooled"]),
                       ("p_fisher", r["p Fisher"]), ("p_unpooled_right", r["p p1>p2"]),
                       ("p_pooled_right", r["p p1>p2 Pooled"]),
                       ("p_fisher_right", r["p p1>p2 Fisher"]),
                       ("ci_default_low", ci[0]), ("ci_default_high", ci[1]),
                       ("ci_right_lower", p1-p2+norm.ppf(0.10)*se),
                       ("ci_pooled_right_lower", p1-p2+norm.ppf(0.10)*se_pooled)):
        add("two_proportion", key, value, "proportion_test.prop_2sample; unpooled Wald CI uses the report formula")

    c = cases["multi_variance"]
    groups = list(c["groups"].values())
    r = multi_pop_var_test(groups, list(c["groups"]))
    for key, value in (("F_mean_centered", r["Levene"]["F"]), ("p_mean_centered", r["Levene"]["p"]),
                       ("F_median_centered", r["Brown_Forsythe"]["F"]), ("p_median_centered", r["Brown_Forsythe"]["p"])):
        add("multi_variance", key, value, "chi_sq.multi_pop_var_test")
    for name, values in c["groups"].items():
        add("multi_variance", f"n_{name}", len(values), "chi_sq.multi_pop_var_test input group size")
        add("multi_variance", f"stdev_{name}", statistics.stdev(values), "chi_sq.multi_pop_var_test sample standard deviation")

    c = cases["one_way_anova"]
    groups = list(c["groups"].values())
    labels = list(c["groups"])
    r = one_way_anova(groups, labels, alpha=0.05)
    for key, value in (("N", sum(map(len, groups))), ("df_between", r["df B"]), ("df_error", r["df W"]),
                       ("df_total", r["df TTL"]), ("SS_between", r["MSB"]*r["df B"]),
                       ("MS_between", r["MSB"]), ("SS_error", r["MSW"]*r["df W"]),
                       ("MS_error", r["MSW"]), ("F", r["F"]), ("p", r["p"])):
        add("one_way_anova", key, value, "one_way_ANOVA.one_way_anova; traditional equal-variance model")
    ss_total = r["MSB"]*r["df B"] + r["MSW"]*r["df W"]
    add("one_way_anova", "SS_total", ss_total, "one_way_ANOVA.one_way_anova; total SS from between + error SS")
    add("one_way_anova", "R2_percent", 100*r["MSB"]*r["df B"]/ss_total,
        "one_way_ANOVA.one_way_anova SS; derived model summary")
    add("one_way_anova", "R2_adjusted_percent",
        100*(1-r["MSW"]/(ss_total/r["df TTL"])), "one_way_ANOVA.one_way_anova SS and DF; derived model summary")
    means = {name: sum(values)/len(values) for name, values in c["groups"].items()}
    fisher = JMP_ANOVA_t_test(groups, labels, alpha=0.05)
    for name, value in means.items():
        add("one_way_anova", f"n_{name}", len(c["groups"][name]), "one_way_ANOVA.one_way_anova input group size")
        add("one_way_anova", f"mean_{name}", value, "one_way_ANOVA.one_way_anova group mean")
        add("one_way_anova", f"stdev_{name}", statistics.stdev(c["groups"][name]), "one_way_ANOVA.one_way_anova sample standard deviation")
    for name, interval in zip(labels, r["CI"]):
        add("one_way_anova", f"ci_low_{name}", interval[0], "one_way_ANOVA.one_way_anova group mean CI")
        add("one_way_anova", f"ci_high_{name}", interval[1], "one_way_ANOVA.one_way_anova group mean CI")
    for (i, j) in ((0, 1), (0, 2), (1, 2)):
        add("one_way_anova", f"fisher_p_{labels[i]}_{labels[j]}", fisher["p"][i][j],
            "one_way_ANOVA.JMP_ANOVA_t_test; pooled Fisher LSD, unadjusted pairwise p")

    c = cases["two_way_anova"]
    r = two_way_anova(c["response"], c["factor_a"], interaction=True, factor_listB=c["factor_b"])
    grand_mean = sum(c["response"]) / len(c["response"])
    total_ss = sum((value-grand_mean)**2 for value in c["response"])
    df_error = r["N"]-1-r["DF A"]-r["DF B"]-r["DF AB"]
    for key, value in (("N", r["N"]), ("SSA", r["SSA"]), ("SSB", r["SSB"]), ("SSAB", r["SSAB"]),
                       ("SSE", r["SSE"]), ("SST", total_ss), ("MSE", r["MSE"]), ("dfA", r["DF A"]),
                       ("dfB", r["DF B"]), ("dfAB", r["DF AB"]), ("dfE", df_error),
                       ("df_total", r["N"]-1),
                       ("MSA", r["MSA"]), ("MSB", r["MSB"]),
                       ("MSAB", r["SSAB"]/r["DF AB"]),
                       ("F_A", r["F A"]), ("F_B", r["F B"]), ("F_AB", r["F AB"]),
                       ("p_A", r["p A"]), ("p_B", r["p B"]), ("p_AB", r["p AB"])):
        add("two_way_anova", key, value, "two_way_anova.two_way_anova; Type III adjusted SS")
    add("two_way_anova", "R2_percent", 100*(1-r["SSE"]/total_ss),
        "two_way_anova.two_way_anova; Type III SS and total SS")
    df_error = r["N"]-1-r["DF A"]-r["DF B"]-r["DF AB"]
    add("two_way_anova", "R2_adjusted_percent",
        100*(1-(r["SSE"]/df_error)/(total_ss/(r["N"]-1))),
        "two_way_anova.two_way_anova; Type III SS and model DF")

    c = cases["ols_multiple"]
    df = pd.DataFrame({"y": c["y"], "x1": c["x1"], "x2": c["x2"]})
    r = fit_regression(df, "y", ["x1", "x2"], model="OLS", alpha=0.05)
    for _, row in r.tables["coefficients"].iterrows():
        key = str(row["term"])
        for metric, field in (("estimate", "estimate"), ("se", "std_error"), ("t", "statistic"),
                              ("p", "p_value"), ("ci_low", "ci_lower"), ("ci_high", "ci_upper")):
            add("ols_multiple", f"{key}_{metric}", row[field], "advanced_regression.fit_regression coefficient table")
    summary = r.tables["summary"].iloc[0]
    for key, field in (("N", "n_obs"), ("df_error", "df_resid"), ("S", "residual_std"),
                       ("R2", "r_squared"), ("R2_adjusted", "adj_r_squared"), ("SSE", "sse")):
        add("ols_multiple", key, summary[field], "advanced_regression.fit_regression model summary")
    add("ols_multiple", "R2_percent", summary["r_squared"]*100, "advanced_regression.fit_regression model summary; displayed percent")
    add("ols_multiple", "R2_adjusted_percent", summary["adj_r_squared"]*100, "advanced_regression.fit_regression model summary; displayed percent")
    for _, row in r.tables["anova"].iterrows():
        term = str(row["source"]).casefold()
        if term in ("regression", "residual", "total"):
            for metric, field in (("SS", "sum_sq"), ("df", "df"), ("MS", "mean_sq")):
                if pd.notna(row[field]):
                    add("ols_multiple", f"{term}_{metric}", row[field], "advanced_regression.fit_regression ANOVA table")
            if term == "regression":
                add("ols_multiple", "model_F", row["statistic"], "advanced_regression.fit_regression ANOVA table")
                add("ols_multiple", "model_p", row["p_value"], "advanced_regression.fit_regression ANOVA table")
    pred = r.predict(pd.DataFrame({"x1": [c["prediction"]["x1"]], "x2": [c["prediction"]["x2"]]}), alpha=0.05).iloc[0]
    for key, field in (("prediction", "predicted"), ("prediction_ci_low", "mean_ci_lower"),
                       ("prediction_ci_high", "mean_ci_upper"), ("prediction_pi_low", "pi_lower"),
                       ("prediction_pi_high", "pi_upper")):
        add("ols_multiple", key, pred[field], "advanced_regression.fit_regression.predict; 95% t-based intervals")
    observations = r.tables.get("observations")
    if observations is not None and not observations.empty:
        for key, field in (("fit_row1", "fitted"), ("residual_row1", "residual"),
                           ("standardized_residual_row1", "standardized_residual"),
                           ("leverage_row1", "leverage"), ("cook_row1", "cooks_distance")):
            add("ols_multiple", key, observations.iloc[0][field], "advanced_regression.fit_regression observations table; source row 1")

    c = cases["ols_categorical"]
    r = fit_regression(pd.DataFrame({"y": c["y"], "group": c["group"]}), "y", ["group"],
                       model="OLS", categorical=("group",), alpha=0.05)
    for _, row in r.tables["coefficients"].iterrows():
        term = str(row["term"])
        for metric, field in (("estimate", "estimate"), ("se", "std_error"),
                              ("t", "statistic"), ("p", "p_value")):
            add("ols_categorical", f"{term}_{metric}", row[field],
                "advanced_regression.fit_regression; reference category is first observed level A")
    summary = r.tables["summary"].iloc[0]
    for key, field in (("N", "n_obs"), ("df_error", "df_resid"), ("R2", "r_squared"),
                       ("R2_adjusted", "adj_r_squared")):
        add("ols_categorical", key, summary[field], "advanced_regression.fit_regression categorical model summary")
    add("ols_categorical", "R2_percent", 100*summary["r_squared"],
        "advanced_regression.fit_regression categorical model summary; displayed percent")
    add("ols_categorical", "R2_adjusted_percent", 100*summary["adj_r_squared"],
        "advanced_regression.fit_regression categorical model summary; displayed percent")
    for _, row in r.tables["anova"].iterrows():
        if str(row["source"]).casefold() == "regression":
            for metric, field in (("SS", "sum_sq"), ("df", "df"), ("MS", "mean_sq"),
                                  ("model_F", "statistic"), ("model_p", "p_value")):
                add("ols_categorical", metric, row[field], "advanced_regression.fit_regression categorical ANOVA table")

    for case_id in ("binary_logistic", "poisson"):
        c = cases[case_id]
        model = "Logistic" if case_id == "binary_logistic" else "Poisson"
        r = fit_regression(pd.DataFrame({"y": c["y"], "x": c["x"]}), "y", ["x"], model=model)
        for _, row in r.tables["coefficients"].iterrows():
            key = str(row["term"])
            for metric, field in (("estimate", "estimate"), ("se", "std_error"), ("statistic", "statistic"),
                                  ("p", "p_value")):
                add(case_id, f"{key}_{metric}", row[field], "advanced_regression.fit_regression generalized coefficients")
            if key != "Intercept":
                add(case_id, f"{key}_wald_chi_square", row["statistic"]**2,
                    "advanced_regression.fit_regression generalized coefficient Wald statistic squared")
                if case_id == "binary_logistic":
                    for metric, value in (("odds_ratio", math.exp(row["estimate"])),
                                          ("odds_ratio_ci_low", math.exp(row["ci_lower"])),
                                          ("odds_ratio_ci_high", math.exp(row["ci_upper"]))):
                        add(case_id, f"{key}_{metric}", value,
                            "advanced_regression.fit_regression coefficient/CI exponentiated to odds ratio")
        summary = r.tables["summary"].iloc[0]
        for metric, field in (("N", "n_obs"), ("df_error", "df_resid"),
                              ("log_likelihood", "log_likelihood"),
                              ("AIC", "aic"), ("BIC", "bic"), ("deviance_R2", "pseudo_r_squared")):
            if field in summary:
                add(case_id, metric, summary[field], "advanced_regression.fit_regression generalized model summary")
                if metric == "deviance_R2":
                    add(case_id, "deviance_R2_percent", summary[field]*100,
                        "advanced_regression.fit_regression generalized summary; displayed percent")
        anova = r.tables.get("anova")
        if anova is not None and not anova.empty:
            for _, row in anova.iterrows():
                key = str(row["source"]).casefold()
                for metric, field in (("statistic", "statistic"), ("p", "p_value")):
                    add(case_id, f"{key}_{metric}", row[field], "advanced_regression.fit_regression generalized ANOVA table")
        diagnostics = r.tables.get("diagnostics")
        if diagnostics is not None and not diagnostics.empty:
            for _, row in diagnostics.iterrows():
                name = str(row["test"]).casefold().replace(" ", "_")
                add(case_id, f"{name}_statistic", row["statistic"], "advanced_regression.fit_regression diagnostics")
                if "df" in row and pd.notna(row["df"]):
                    add(case_id, f"{name}_df", row["df"], "advanced_regression.fit_regression diagnostics")
                if pd.notna(row["p_value"]):
                    add(case_id, f"{name}_p", row["p_value"], "advanced_regression.fit_regression diagnostics")

    from nonpara_cor import hoeffding, kendall, spearman
    c = cases["rank_correlation"]
    for method, result in (("spearman", spearman(c["x"], c["y"])),
                           ("kendall", kendall(c["x"], c["y"])),
                           ("hoeffding", hoeffding(c["x"], c["y"]))):
        for metric, value in (("N", len(c["x"])), ("coefficient", result["cor"]), ("p", result["p"])):
            add("rank_correlation", f"{method}_{metric}", value, f"nonpara_cor.{method}")
    return out


def input_vectors(cases: dict) -> dict[int, tuple[str, list]]:
    var_groups = cases["multi_variance"]["groups"]
    one_way = cases["one_way_anova"]["groups"]
    return {
        1: ("OneSampleT", cases["one_sample_t"]["values"]),
        2: ("PairedA", cases["paired_t"]["sample1"]), 3: ("PairedB", cases["paired_t"]["sample2"]),
        4: ("TwoSample1", cases["two_sample_pooled_t"]["sample1"]),
        5: ("TwoSample2", cases["two_sample_pooled_t"]["sample2"]),
        6: ("OneVariance", cases["one_variance"]["values"]),
        9: ("VarianceY", [v for values in var_groups.values() for v in values]),
        10: ("VarianceGroup", [name for name, values in var_groups.items() for _ in values]),
        11: ("OneWayY", [v for values in one_way.values() for v in values]),
        12: ("OneWayGroup", [name for name, values in one_way.items() for _ in values]),
        13: ("TwoWayY", cases["two_way_anova"]["response"]),
        14: ("FactorA", cases["two_way_anova"]["factor_a"]),
        15: ("FactorB", cases["two_way_anova"]["factor_b"]),
        16: ("OLS_Y", cases["ols_multiple"]["y"]),
        17: ("OLS_X1", cases["ols_multiple"]["x1"]),
        18: ("OLS_X2", cases["ols_multiple"]["x2"]),
        21: ("LogitY", cases["binary_logistic"]["y"]),
        22: ("LogitX", cases["binary_logistic"]["x"]),
        23: ("PoissonY", cases["poisson"]["y"]),
        24: ("PoissonX", cases["poisson"]["x"]),
        25: ("PredictX1", [cases["ols_multiple"]["prediction"]["x1"]]),
        26: ("PredictX2", [cases["ols_multiple"]["prediction"]["x2"]]),
        27: ("CategoricalOLS_Y", cases["ols_categorical"]["y"]),
        28: ("CategoricalOLS_Group", cases["ols_categorical"]["group"]),
        29: ("RankX", cases["rank_correlation"]["x"]),
        30: ("RankY", cases["rank_correlation"]["y"]),
    }


STORAGE_COLUMNS = {
    "one_sample_t_two_sided": {"p": 61, "ci_low": 62, "ci_high": 63},
    "one_sample_t_right": {"p": 64, "bound_low": 65, "bound_high": 66},
    "paired_t_two_sided": {"p": 67, "ci_low": 68, "ci_high": 69},
    "paired_t_right": {"p": 70, "bound_low": 71, "bound_high": 72},
    "pooled_t_two_sided": {"p": 73, "ci_low": 74, "ci_high": 75},
    "pooled_t_right": {"p": 76, "bound_low": 77, "bound_high": 78},
    "one_proportion_default": {"p": 79, "ci_low": 80, "ci_high": 81},
    "one_proportion_normal": {"p": 82, "ci_low": 83, "ci_high": 84},
    "two_proportion_default": {"p": 85, "p_fisher": 86, "ci_low": 87, "ci_high": 88},
    "two_proportion_pooled": {"p": 89, "p_fisher": 90, "ci_low": 91, "ci_high": 92},
    "one_proportion_normal_right": {"p": 103, "bound_low": 104, "bound_high": 105},
    "two_proportion_right": {"p": 106, "p_fisher": 107, "ci_low": 108, "ci_high": 109},
    "two_proportion_pooled_right": {"p": 110, "p_fisher": 111, "ci_low": 112, "ci_high": 113},
    "ols_multiple": {"residual": 93, "standardized_residual": 94, "leverage": 95, "cooks_distance": 96,
                     "fit": 97},
    "ols_prediction": {"fit": 114, "se_fit": 115, "ci_low": 116, "ci_high": 117, "pi_low": 118, "pi_high": 119},
    "binary_logistic": {"coefficients": 120, "se_coefficients": 121},
    "poisson": {"coefficients": 122, "se_coefficients": 123},
}

STORAGE_MATRICES = {
    "spearman_correlation": {
        "SCORRELATION M3[2,1]": ("M3", 2, 1),
        "SPVALUES M4[2,1]": ("M4", 2, 1),
    }
}


def run_minitab() -> dict:
    import gc
    import pythoncom
    import win32com.client

    if not MTB_EXE.is_file() or com_check.file_version(MTB_EXE) != "19.1.0.1":
        raise RuntimeError(f"需要本机 Minitab 19.1.0.1：{MTB_EXE}")
    pids_before = running_minitab_pids()
    if pids_before:
        raise RuntimeError(f"启动前检测到现有 Mtb.exe PID {pids_before}；拒绝连接既有会话")
    clsid, registered_path, registered_command = com_check.registered_server()
    if com_check.canonical(registered_path) != com_check.canonical(MTB_EXE):
        raise RuntimeError(f"COM 注册路径不匹配：{registered_command}")

    app = project = ui = worksheet = columns = None
    outputs = {}
    loaded_inputs = {}
    try:
        app = win32com.client.DispatchEx("Mtb.Application")
        pythoncom.PumpWaitingMessages()
        ui = app.UserInterface
        ui.Visible = False
        ui.UserControl = False
        ui.DisplayAlerts = False
        hwnd = int(app.Handle)
        process_id, process_path = com_check.process_image_path(hwnd)
        app_path = str(app.AppPath)
        pids_after = running_minitab_pids()
        if (com_check.canonical(app_path) != com_check.canonical(MTB_EXE)
                or com_check.canonical(process_path) != com_check.canonical(MTB_EXE)
                or process_id in pids_before or process_id not in pids_after):
            raise RuntimeError(f"COM 新实例路径/PID 核验失败：{app_path}; {process_path}; {process_id}")
        app.New()
        project = app.ActiveProject
        worksheet = project.ActiveWorksheet
        columns = worksheet.Columns
        while int(columns.Count) < 124:
            col = columns.Add(None, None, 1)
            col.Name = f"P4C{int(columns.Count):03d}"
        cases = load_inputs()["cases"]
        for index, (name, values) in input_vectors(cases).items():
            col = columns.Item(index)
            col.Name = name
            col.SetData(tuple(values), 1, len(values))
            back = col.GetData()
            back = list(back) if isinstance(back, (tuple, list)) else [back]
            if len(back) != len(values):
                raise AssertionError(f"Minitab C{index} 回读行数不符")
            if all(isinstance(value, str) for value in values):
                if [str(value) for value in back] != values:
                    raise AssertionError(f"Minitab C{index} 文本数据回读不同")
            elif any(float(a) != float(b) for a, b in zip(back, values)):
                raise AssertionError(f"Minitab C{index} 数值数据回读不同")
            loaded_inputs[str(index)] = {"name": name, "values": back}

        for case_id, command in COMMANDS.items():
            before = int(project.Commands.Count)
            try:
                project.ExecuteCommand(command)
                after = int(project.Commands.Count)
                output = capture_command_output(project, after) if after > before else ""
                error = str(app.LastError or "")
                outputs[case_id] = {
                    "executed": after > before and not error.strip(),
                    "command_count": [before, after], "command": command,
                    "last_error": error, "output": output,
                }
            except Exception as exc:
                outputs[case_id] = {
                    "executed": False, "command_count": [before, int(project.Commands.Count)],
                    "command": command, "error": f"{type(exc).__name__}: {exc}", "output": "",
                    "traceback": traceback.format_exc(),
                }
        for case_id, columns_by_name in STORAGE_COLUMNS.items():
            stored = {}
            storage_errors = {}
            for name, index in columns_by_name.items():
                try:
                    values = columns.Item(index).GetData()
                    values = list(values) if isinstance(values, (tuple, list)) else [values]
                    stored[name] = [None if value is None else float(value) for value in values]
                except Exception as exc:
                    storage_errors[name] = f"C{index}: {type(exc).__name__}: {exc}"
            outputs[case_id]["stored"] = stored
            if storage_errors:
                outputs[case_id]["storage_errors"] = storage_errors
        matrices = worksheet.Matrices
        for case_id, matrices_by_name in STORAGE_MATRICES.items():
            stored = outputs[case_id].setdefault("stored", {})
            matrix_values = {}
            storage_errors = {}
            for field, (name, row, column) in matrices_by_name.items():
                try:
                    matrix = next(matrices.Item(i) for i in range(1, int(matrices.Count) + 1)
                                  if str(matrices.Item(i).Name).casefold() == name.casefold())
                    rows, cols = int(matrix.RowCount), int(matrix.ColumnCount)
                    if (rows, cols) != (2, 2):
                        raise ValueError(f"{name} 应为 2x2，实际 {rows}x{cols}")
                    flat = [float(value) for value in matrix.GetData()]
                    if len(flat) != rows * cols:
                        raise ValueError(f"{name} 应有 4 个值，实际 {len(flat)}")
                    stored[field] = [flat[(column - 1) * rows + row - 1]]
                    matrix_values[field] = {"name": name, "row": row, "column": column,
                                            "rows": rows, "columns": cols, "values": flat}
                except Exception as exc:
                    storage_errors[field] = f"{name}: {type(exc).__name__}: {exc}"
            outputs[case_id]["matrix_storage"] = matrix_values
            if storage_errors:
                outputs[case_id]["matrix_storage_errors"] = storage_errors
        return {
            "version": "19.1.0.1", "clsid": clsid, "registered_server": registered_command,
            "app_path": app_path, "process_path": process_path, "process_id": process_id,
            "project_name": str(project.Name), "worksheet_name": str(worksheet.Name),
            "python": sys.executable, "loaded_inputs": loaded_inputs, "outputs": outputs,
        }
    finally:
        columns = worksheet = project = app = ui = None
        gc.collect()


def load_reference_rows() -> list[dict]:
    if not REFERENCE.is_file():
        return []
    with REFERENCE.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def compare(local: dict, native: dict) -> list[dict]:
    rows = []
    outputs = native["outputs"]
    for ref in load_reference_rows():
        case_id = ref["case_id"]
        command_id = ref["command_id"]
        command_result = outputs.get(command_id, {})
        status = ref["status_override"].strip()
        local_row = local.get(ref["minijmp_key"])
        native_output = command_result.get("output", "")
        try:
            source_type = ref["Minitab来源"].strip()
            if source_type == "direct":
                native_field = ref["Minitab字段"]
                stored_values = command_result.get("stored", {}).get(native_field, [])
                storage_index = int(ref.get("Minitab存储索引") or 0)
                if len(stored_values) <= storage_index or stored_values[storage_index] is None:
                    raise ValueError(f"Minitab direct storage {native_field} 为空")
                reference = float(stored_values[storage_index])
                tolerance = 1e-10
            elif source_type == "display":
                reference = float(ref["Minitab值"])
                decimals = int(ref["显示小数位"])
                tolerance = 0.5 * 10 ** (-decimals)
            elif source_type == "derived":
                reference = float(ref["Minitab值"])
                tolerance = 1e-12
            else:
                reference, tolerance = None, None
            value = float(local_row["value"]) if local_row else None
            error = abs(value - reference) if value is not None and reference is not None else None
            if not local_row:
                status = status or "NOT_RUN"
            elif source_type == "unavailable":
                status = status or "NOT_RUN"
            elif not status:
                within_tolerance = error <= tolerance or math.isclose(error, tolerance, rel_tol=1e-12, abs_tol=1e-15)
                status = "PASS" if within_tolerance else "FAIL"
            if command_result.get("executed") is not True and status not in ("NOT_RUN", "UNSUPPORTED"):
                status = "NOT_RUN"
            unavailable_reason = command_result.get("last_error", command_result.get("error", "")) or ref["判断依据"]
            source = (f"{command_id} / Minitab worksheet storage {ref['Minitab字段']}"
                      if source_type == "direct" else
                      (f"{command_id} / OutputDocument.Text；{ref['原生输出字段']}"
                       if source_type == "display" else
                       (f"{command_id} / 由 Minitab 原生样本量按 df 规则推导"
                        if source_type == "derived" else
                        f"{command_id} / 未取得原生参考：{unavailable_reason}")))
            row = {
                "case_id": case_id, "功能": ref["功能"], "统计量": ref["统计量"],
                "Minitab值": format(reference, ".15g") if reference is not None else "",
                "MiniJMP值": format(value, ".15g") if value is not None else "",
                "绝对误差": format(error, ".8g") if error is not None else "",
                "容差": format(tolerance, ".8g") if tolerance is not None else "",
                "结果": status, "Minitab结果来源": source,
                "MiniJMP结果来源": local_row["source"] if local_row else "",
                "统计定义/配置": ref["配置"],
                "判断依据": ref["判断依据"] or (
                    f"Minitab 显示 {decimals} 位小数，按半个显示单位容差比较。"
                    if source_type == "display" else "Minitab 存储值与 MiniJMP 生产入口比较。"),
                "测试数据集": ref["测试数据集"], "Minitab参考版本": ref["Minitab参考版本"],
                "Minitab原生字段": ref["Minitab字段"] or ref["原生输出字段"],
                "Minitab存储列": ref["Minitab存储列"],
                "Minitab存储索引": ref["Minitab存储索引"],
                "Minitab原生输出行": ref["原生输出行"],
            }
            rows.append(row)
            if command_result.get("executed") is True and source_type in ("direct", "display", "derived") and ref["原生输出行"] and ref["原生输出行"] not in native_output:
                rows[-1]["结果"] = "NOT_RUN"
                rows[-1]["判断依据"] += " 原生输出未找到所记录的数值行。"
        except (TypeError, ValueError, KeyError) as exc:
            rows.append({"case_id": case_id, "功能": ref.get("功能", ""), "统计量": ref.get("统计量", ""),
                         "结果": "NOT_RUN", "判断依据": f"参考值或精度字段无效：{exc}"})
    return rows


def main() -> int:
    PHASE.mkdir(parents=True, exist_ok=True)
    if com_check.canonical(sys.executable) != com_check.canonical(PROJECT_PYTHON):
        raise RuntimeError(f"请使用项目解释器运行：{PROJECT_PYTHON}")
    inputs = load_inputs()
    local = production_results(inputs["cases"])
    write_json(PHASE / "minijmp_results.json", {"python": sys.executable, "case_inputs": inputs, "results": local})
    (PHASE / "minitab_session_commands.txt").write_text(
        "\n\n".join(f"===== {key} =====\n{command}" for key, command in COMMANDS.items()) + "\n",
        encoding="utf-8",
    )
    native = run_minitab()
    write_json(PHASE / "minitab_results.json", native)
    raw = []
    for case_id, item in native["outputs"].items():
        raw.append(
            f"===== {case_id} =====\n{item['command']}\n"
            f"Commands.Count: {item['command_count']}\nLastError: {item.get('last_error', item.get('error', ''))}\n"
            f"===== OutputDocument.Text / Output.Text =====\n{item.get('output') or '(empty)'}\n"
        )
    (PHASE / "minitab_raw_outputs.txt").write_text("\n".join(raw), encoding="utf-8")
    metadata = {key: native[key] for key in ("version", "clsid", "registered_server", "app_path", "process_path", "process_id", "project_name", "worksheet_name", "python")}
    write_json(PHASE / "minitab_metadata.json", metadata)
    comparison = compare(local, native)
    if comparison:
        with (PHASE / "comparison.csv").open("w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=COMPARISON_FIELDS, extrasaction="ignore", lineterminator="\n")
            writer.writeheader()
            writer.writerows(comparison)
    summary = []
    by_case = {}
    for row in comparison:
        by_case.setdefault(row["case_id"], []).append(row)
    for case_id, rows in by_case.items():
        counts = Counter(row["结果"] for row in rows)
        states = [name for name in STATUS_ORDER if counts[name]]
        summary.append({"case_id": case_id, "比较指标数": len(rows), **{name: counts[name] for name in STATUS_ORDER},
                        "功能状态": "PASS" if states == ["PASS"] else (states[0] if len(states) == 1 else "MIXED"),
                        "备注": "；".join(dict.fromkeys(row["判断依据"] for row in rows if row["结果"] != "PASS"))})
    if summary:
        fields = ("case_id", "比较指标数", *STATUS_ORDER, "功能状态", "备注")
        with (PHASE / "summary.csv").open("w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
            writer.writeheader()
            writer.writerows(summary)
    failed_commands = [case for case, item in native["outputs"].items() if not item.get("executed")]
    expected_unavailable = {"ols_prediction"}
    unexpected_failures = [case for case in failed_commands if case not in expected_unavailable]
    print(f"Minitab {native['version']} COM 新建项目 PID={native['process_id']}；命令 {len(COMMANDS)-len(failed_commands)}/{len(COMMANDS)} 成功。")
    if failed_commands:
        print("命令未执行：" + ", ".join(failed_commands))
        for case in failed_commands:
            print(f"{case}: {native['outputs'][case].get('last_error', native['outputs'][case].get('error', ''))}")
    print(f"载入 {len(native['loaded_inputs'])} 个固定数据列；对标指标 {len(comparison)} 项。")
    return 1 if unexpected_failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
