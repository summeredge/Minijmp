from __future__ import annotations

import csv
import json
from pathlib import Path

PHASE = Path(__file__).resolve().parent
HEADERS = (
    "case_id", "command_id", "功能", "统计量", "Minitab来源", "Minitab值",
    "显示小数位", "minijmp_key", "Minitab字段", "Minitab存储列",
    "Minitab存储索引", "原生输出字段", "原生输出行", "配置", "status_override",
    "判断依据", "测试数据集", "Minitab参考版本",
)
DATA = {
    "one_sample_t": "one_sample_t", "paired_t": "paired_t",
    "two_sample_pooled_t": "two_sample_pooled_t", "one_variance": "one_variance",
    "one_proportion": "one_proportion", "two_proportion": "two_proportion",
    "multi_variance": "multi_variance", "one_way_anova": "one_way_anova",
    "two_way_anova": "two_way_anova", "ols_multiple": "ols_multiple",
    "ols_categorical": "ols_categorical", "binary_logistic": "binary_logistic",
    "poisson": "poisson", "rank_correlation": "rank_correlation",
}
with (PHASE / "minitab_results.json").open(encoding="utf-8") as f:
    native = json.load(f)
with (PHASE / "case_inputs.json").open(encoding="utf-8") as f:
    inputs = json.load(f)


def add(case, command, feature, metric, local_key, source, config, *,
        token="", field="", value="", digits="", native_field="", column="",
        index="", status="", reason=""):
    output = native["outputs"].get(command, {}).get("output", "")
    line = next((row.rstrip("\r") for row in output.splitlines() if token and token in row), "")
    if token and not line:
        raise ValueError(f"Native output line missing: {command}: {token!r}")
    rows.append({
        "case_id": case, "command_id": command, "功能": feature, "统计量": metric,
        "Minitab来源": source, "Minitab值": value, "显示小数位": digits,
        "minijmp_key": local_key, "Minitab字段": native_field,
        "Minitab存储列": f"C{column}" if column else "",
        "Minitab存储索引": str(index) if index != "" else "",
        "原生输出字段": field, "原生输出行": line, "配置": config,
        "status_override": status, "判断依据": reason,
        "测试数据集": f"case_inputs.json#cases.{DATA[case]}",
        "Minitab参考版本": native["version"],
    })


def display(case, command, feature, metric, key, value, digits, token, field, config, reason=""):
    add(case, command, feature, metric, key, "display", config, token=token,
        field=field, value=str(value), digits=str(digits), reason=reason)


def stored(case, command, feature, metric, key, native_field, column, token, field, config,
           index="", status="", reason=""):
    add(case, command, feature, metric, key, "direct", config, token=token,
        field=field, native_field=native_field, column=column, index=index,
        status=status, reason=reason)


def derived(case, command, feature, metric, key, value, token, field, config, rule):
    add(case, command, feature, metric, key, "derived", config, token=token,
        field=field, value=str(value), native_field=rule, reason=rule)


def gap(case, command, feature, metric, value, digits, token, field, config, reason):
    add(case, command, feature, metric, "", "display", config, token=token,
        field=field, value=str(value), digits=str(digits), status="UNSUPPORTED", reason=reason)


def no_reference(case, command, feature, metric, key, config, reason):
    add(case, command, feature, metric, key, "unavailable", config,
        status="NOT_RUN", reason=reason)


rows = []

# Hypothesis tests
f = "25单样本均值 t 检验"
c = "μ0=10.5；α=.10；双侧/右侧；df=n−1"
for metric, key, value, digits, token, field in [
    ("有效 N", "one_sample_t.n", 7, 0, "7  10.729  1.138", "N"),
    ("样本均值", "one_sample_t.mean", 10.729, 3, "7  10.729  1.138", "均值"),
    ("样本标准差", "one_sample_t.stdev", 1.138, 3, "7  10.729  1.138", "标准差"),
    ("均值标准误", "one_sample_t.mean_se", .430, 3, "7  10.729  1.138", "均值标准误"),
    ("t 统计量", "one_sample_t.t", .53, 2, "0.53  0.614", "T 值    P 值"),
]:
    display("one_sample_t", "one_sample_t_two_sided", f, metric, key, value, digits, token, field, c)
derived("one_sample_t", "one_sample_t_two_sided", f, "自由度",
        "one_sample_t.df", 6, "0.53  0.614", "T 值；df=n−1", c,
        "Minitab 原生 N=7；单样本 t 自由度按 n−1 推导。")
stored("one_sample_t", "one_sample_t_two_sided", f, "双侧 p 值",
       "one_sample_t.p_two", "p", 61, "0.53  0.614", "SPVALUE C61", c)
stored("one_sample_t", "one_sample_t_two_sided", f, "双侧 90% CI 下限",
       "one_sample_t.ci_low", "ci_low", 62, "9.893, 11.565", "SCONF C62 C63", c)
stored("one_sample_t", "one_sample_t_two_sided", f, "双侧 90% CI 上限",
       "one_sample_t.ci_high", "ci_high", 63, "9.893, 11.565", "SCONF C62 C63", c)
stored("one_sample_t", "one_sample_t_right", f, "右侧 p 值",
       "one_sample_t.p_right", "p", 64, "0.53  0.307", "SPVALUE C64", c)
stored("one_sample_t", "one_sample_t_right", f, "右侧 90% CI 下限",
       "one_sample_t.right_bound", "bound_low", 65, "10.109", "SCONF C65 C66", c)

f = "30配对 t 检验"
c = "差值=样本1−样本2；H0=0；α=.10；双侧/右侧"
for metric, key, value, digits, token, field in [
    ("配对 N", "paired_t.n", 6, 0, "PairedA  6", "描述性统计量"),
    ("平均差", "paired_t.mean_difference", .3833, 4, "0.3833  0.2137  0.0872", "均值/标准差/均值标准误"),
    ("差值标准差", "paired_t.stdev_difference", .2137, 4, "0.3833  0.2137  0.0872", "均值/标准差/均值标准误"),
    ("差值标准误", "paired_t.se_difference", .0872, 4, "0.3833  0.2137  0.0872", "均值/标准差/均值标准误"),
    ("t 统计量", "paired_t.t", 4.39, 2, "4.39  0.007", "T 值    P 值"),
    ("自由度", "paired_t.df", 5, 0, "4.39  0.007", "T 值/配对 N"),
]:
    display("paired_t", "paired_t_two_sided", f, metric, key, value, digits, token, field, c)
stored("paired_t", "paired_t_two_sided", f, "双侧 p 值", "paired_t.p_two", "p", 67, "4.39  0.007", "SPVALUE C67", c)
stored("paired_t", "paired_t_two_sided", f, "双侧 90% CI 下限", "paired_t.ci_low", "ci_low", 68, "0.2075, 0.5591", "SCONF C68 C69", c)
stored("paired_t", "paired_t_two_sided", f, "双侧 90% CI 上限", "paired_t.ci_high", "ci_high", 69, "0.2075, 0.5591", "SCONF C68 C69", c)
stored("paired_t", "paired_t_right", f, "右侧 p 值", "paired_t.p_right", "p", 70, "4.39  0.004", "SPVALUE C70", c)
stored("paired_t", "paired_t_right", f, "右侧 90% CI 下限", "paired_t.right_bound", "bound_low", 71, "0.2546", "SCONF C71 C72", c)

f = "29双样本 t 检验"
c = "两独立样本；POOLED 等方差；对比=样本1−样本2；α=.10；双侧/右侧"
for metric, key, value, digits, token, field in [
    ("样本1 N", "n1", 8, 0, "TwoSample1  8", "描述性统计量"),
    ("样本2 N", "n2", 7, 0, "TwoSample2  7", "描述性统计量"),
    ("样本1均值", "mean1", 13.13, 2, "TwoSample1  8  13.13", "描述性统计量"),
    ("样本2均值", "mean2", 10.43, 2, "TwoSample2  7  10.43", "描述性统计量"),
    ("样本1标准差", "stdev1", 2.03, 2, "TwoSample1  8  13.13", "描述性统计量"),
    ("样本2标准差", "stdev2", 1.72, 2, "TwoSample2  7  10.43", "描述性统计量"),
    ("均值差", "difference", 2.696, 3, "2.696  1.893", "差值估计值"),
    ("合并标准差", "pooled_sd", 1.893, 3, "2.696  1.893", "差值估计值"),
    ("t 统计量", "t", 2.75, 2, "2.75   13  0.016", "T 值/自由度/P 值"),
    ("自由度", "df", 13, 0, "2.75   13  0.016", "T 值/自由度/P 值"),
]:
    display("two_sample_pooled_t", "pooled_t_two_sided", f, metric,
            f"two_sample_pooled_t.{key}", value, digits, token, field, c)
stored("two_sample_pooled_t", "pooled_t_two_sided", f, "双侧 p 值", "two_sample_pooled_t.p_two", "p", 73, "2.75   13  0.016", "SPVALUE C73", c)
stored("two_sample_pooled_t", "pooled_t_two_sided", f, "双侧 90% CI 下限", "two_sample_pooled_t.ci_low", "ci_low", 74, "0.961, 4.432", "SCONF C74 C75", c)
stored("two_sample_pooled_t", "pooled_t_two_sided", f, "双侧 90% CI 上限", "two_sample_pooled_t.ci_high", "ci_high", 75, "0.961, 4.432", "SCONF C74 C75", c)
stored("two_sample_pooled_t", "pooled_t_right", f, "右侧 p 值", "two_sample_pooled_t.p_right", "p", 76, "2.75   13  0.008", "SPVALUE C76", c)
gap("two_sample_pooled_t", "pooled_t_right", f, "右侧 90% CI 下限", 1.374, 3,
    "1.374", "SCONF C77 C78", c,
    "Minitab 提供单侧下限；MiniJMP t_test_2samples 接口只返回双侧 CI 和单侧 p，没有单侧 CI 字段。")

f = "27单样本标准差检验"
c = "σ0=3；正态总体卡方法；α=.10；Bonett 并列参考"
for metric, key, value, digits, token, field in [
    ("N", "n", 8, 0, "8  3.46  12.0", "描述性统计量"),
    ("样本标准差", "stdev", 3.46, 2, "8  3.46  12.0", "描述性统计量"),
    ("样本方差", "variance", 12.0, 1, "8  3.46  12.0", "描述性统计量"),
    ("χ² 统计量", "chi_square", 9.33, 2, "卡方       9.33    7  0.459", "卡方行/统计量/DF/P"),
    ("自由度", "df", 7, 0, "卡方       9.33    7  0.459", "卡方行/统计量/DF/P"),
    ("双侧卡方 p 值", "p_two", .459, 3, "卡方       9.33    7  0.459", "卡方行/统计量/DF/P"),
    ("双侧卡方 90% CI 下限", "chi_ci_low", 2.44, 2, "(2.44, 6.23)", "卡方标准差 90% CI"),
    ("双侧卡方 90% CI 上限", "chi_ci_high", 6.23, 2, "(2.44, 6.23)", "卡方标准差 90% CI"),
    ("Bonett 双侧 p 值", "bonett_p", .407, 3, "Bonett      —    —  0.407", "Bonett 行/双侧 p"),
    ("Bonett 双侧 CI 下限", "bonett_ci_low", 2.49, 2, "(2.49, 6.06)", "Bonett 标准差 90% CI"),
    ("Bonett 双侧 CI 上限", "bonett_ci_high", 6.06, 2, "(2.49, 6.06)", "Bonett 标准差 90% CI"),
    ("右侧卡方 p 值", "p_right", .230, 3, "卡方       9.33    7  0.230", "右侧卡方行"),
    ("右侧卡方 90% CI 下限", "chi_right_lower", 2.64, 2, "2.64", "右侧卡方 90% CI 下限"),
    ("右侧 Bonett 90% CI 下限", "bonett_right_lower", 2.72, 2, "2.72", "右侧 Bonett 90% CI 下限"),
]:
    command = "one_variance_right" if "右侧" in metric else "one_variance_two_sided"
    display("one_variance", command, f, metric, f"one_variance.{key}", value, digits, token, field, c)
gap("one_variance", "one_variance_right", f, "右侧 Bonett p 值", .203, 3,
    "Bonett      —    —  0.203", "Bonett 右侧 p", c,
    "MiniJMP var_1sample 返回 Bonett 双侧 p，但没有右侧 Bonett p 字段；不以 p/2 推导。")

f = "28单比率检验"
c = "n=20；事件=12；p0=.5；α=.10；默认精确、USEZ 正态、USEZ 右侧"
for metric, key, value, digits, token, field, command in [
    ("样本量", "trials", 20, 0, "20  12  0.600000", "N/事件/样本 p", "one_proportion_default"),
    ("事件数", "events", 12, 0, "20  12  0.600000", "N/事件/样本 p", "one_proportion_default"),
    ("样本比例", "sample_p", .600000, 6, "20  12  0.600000", "N/事件/样本 p", "one_proportion_default"),
]:
    display("one_proportion", command, f, metric, f"one_proportion.{key}", value, digits, token, field, c)
stored("one_proportion", "one_proportion_default", f, "默认精确双侧 p 值", "one_proportion.p_default_exact", "p", 79, "0.503", "SPVALUE C79", c)
stored("one_proportion", "one_proportion_default", f, "默认精确 90% CI 下限", "one_proportion.ci_default_low", "ci_low", 80, "0.393585, 0.782931", "SCONF C80 C81", c)
stored("one_proportion", "one_proportion_default", f, "默认精确 90% CI 上限", "one_proportion.ci_default_high", "ci_high", 81, "0.393585, 0.782931", "SCONF C80 C81", c)
display("one_proportion", "one_proportion_normal", f, "正态近似 Z", "one_proportion.z_normal", .89, 2, "0.89  0.371", "Z/P", c)
stored("one_proportion", "one_proportion_normal", f, "正态近似双侧 p 值", "one_proportion.p_normal", "p", 82, "0.89  0.371", "SPVALUE C82", c)
stored("one_proportion", "one_proportion_normal", f, "正态近似双侧 90% CI 下限", "one_proportion.ci_normal_low", "ci_low", 83, "0.419815, 0.780185", "SCONF C83 C84", c)
stored("one_proportion", "one_proportion_normal", f, "正态近似双侧 90% CI 上限", "one_proportion.ci_normal_high", "ci_high", 84, "0.419815, 0.780185", "SCONF C83 C84", c)
stored("one_proportion", "one_proportion_normal_right", f, "正态近似右侧 p 值", "one_proportion.p_normal_right", "p", 103, "0.89  0.186", "SPVALUE C103", c)
stored("one_proportion", "one_proportion_normal_right", f, "正态近似右侧 90% CI 下限", "one_proportion.ci_normal_right_lower", "bound_low", 104, "0.459613", "SCONF C104 C105", c)

f = "31双比率检验"
c = "n1=n2=20；x1=12,x2=9；差=p1−p2；α=.10；未合并/POOLED/Fisher；双侧与右侧"
for metric, key, value, digits, token in [
    ("样本1 N", "n1", 20, 0, "样本 1  20  12"),
    ("样本1 事件数", "events1", 12, 0, "样本 1  20  12"),
    ("样本1 比例", "p1", .600000, 6, "样本 1  20  12  0.600000"),
    ("样本2 N", "n2", 20, 0, "样本 2  20   9"),
    ("样本2 事件数", "events2", 9, 0, "样本 2  20   9"),
    ("样本2 比例", "p2", .450000, 6, "样本 2  20   9  0.450000"),
]:
    display("two_proportion", "two_proportion_default", f, metric,
            f"two_proportion.{key}", value, digits, token, "N/事件/样本 p", c)
display("two_proportion", "two_proportion_default", f, "比例差", "two_proportion.difference",
        .15, 2, "0.15  (-0.106803, 0.406803)", "差值及90% CI", c)
display("two_proportion", "two_proportion_default", f, "未合并 Z", "two_proportion.z_default_normal",
        .96, 2, "正态近似         0.96  0.337", "Z/P", c)
stored("two_proportion", "two_proportion_default", f, "未合并双侧 p 值", "two_proportion.p_default_normal", "p", 85, "0.96  0.337", "SPVALUE C85", c)
stored("two_proportion", "two_proportion_default", f, "Fisher 双侧 p 值", "two_proportion.p_fisher", "p_fisher", 86, "0.527", "SFISHER C86", c)
stored("two_proportion", "two_proportion_default", f, "双侧 90% CI 下限", "two_proportion.ci_default_low", "ci_low", 87, "(-0.106803, 0.406803)", "SCONFC C87 C88", c)
stored("two_proportion", "two_proportion_default", f, "双侧 90% CI 上限", "two_proportion.ci_default_high", "ci_high", 88, "(-0.106803, 0.406803)", "SCONFC C87 C88", c)
display("two_proportion", "two_proportion_pooled", f, "合并 Z", "two_proportion.z_pooled",
        .95, 2, "正态近似         0.95  0.342", "Z/P", c)
stored("two_proportion", "two_proportion_pooled", f, "合并双侧 p 值", "two_proportion.p_pooled", "p", 89, "0.342", "SPVALUE C89 / POOLED", c)
stored("two_proportion", "two_proportion_pooled", f, "Fisher 双侧 p 值", "two_proportion.p_fisher", "p_fisher", 90, "0.527", "SFISHER C90", c)
stored("two_proportion", "two_proportion_pooled", f, "POOLED 选项下双侧 CI 下限", "two_proportion.ci_default_low", "ci_low", 91, "(-0.106803, 0.406803)", "SCONFC C91 C92", c)
stored("two_proportion", "two_proportion_pooled", f, "POOLED 选项下双侧 CI 上限", "two_proportion.ci_default_high", "ci_high", 92, "(-0.106803, 0.406803)", "SCONFC C91 C92", c)
stored("two_proportion", "two_proportion_right", f, "未合并右侧 p 值", "two_proportion.p_unpooled_right", "p", 106, "0.168", "SPVALUE C106", c)
stored("two_proportion", "two_proportion_right", f, "Fisher 右侧 p 值", "two_proportion.p_fisher_right", "p_fisher", 107, "0.264", "SFISHER C107", c)
stored("two_proportion", "two_proportion_right", f, "右侧 90% CI 下限", "two_proportion.ci_right_lower", "ci_low", 108, "0.15   -0.050082", "SCONFC C108 C109", c)
stored("two_proportion", "two_proportion_pooled_right", f, "POOLED 右侧 p 值", "two_proportion.p_pooled_right", "p", 110, "0.171", "SPVALUE C110", c)
stored("two_proportion", "two_proportion_pooled_right", f, "Fisher 右侧 p 值", "two_proportion.p_fisher_right", "p_fisher", 111, "0.264", "SFISHER C111", c)
stored("two_proportion", "two_proportion_pooled_right", f, "POOLED 右侧 90% CI 下限", "two_proportion.ci_right_lower", "ci_low", 112, "0.15   -0.050082", "SCONFC C112 C113", c)

f = "32多样本标准差检验"
c = "三组独立样本；α=.05；Minitab VARTEST Levene 以中位数中心"
for g, sd in [("A", 3.46410), ("B", 3.72012), ("C", 3.48210)]:
    display("multi_variance", "multi_variance", f, f"{g} 组 N", f"multi_variance.n_{g}",
            8, 0, f"{g}  8  {sd:.5f}", "N/标准差/Bonferroni CI", c)
    display("multi_variance", "multi_variance", f, f"{g} 组标准差", f"multi_variance.stdev_{g}",
            sd, 5, f"{g}  8  {sd:.5f}", "N/标准差/Bonferroni CI", c)
display("multi_variance", "multi_variance", f, "median-centered Levene F vs Brown–Forsythe F",
        "multi_variance.F_median_centered", .10, 2, "Levene   0.10  0.908", "Levene F/P", c,
        "Minitab 中位数中心 Levene 对应 MiniJMP Brown-Forsythe。")
display("multi_variance", "multi_variance", f, "median-centered Levene p vs Brown–Forsythe p",
        "multi_variance.p_median_centered", .908, 3, "Levene   0.10  0.908", "Levene F/P", c)
add("multi_variance", "multi_variance", f, "mean-centered Levene p（方法差异）",
    "multi_variance.p_mean_centered", "display", c, token="Levene   0.10  0.908",
    field="Minitab median-centered Levene", value=".908", digits="3", status="METHOD_DIFF",
    reason="MiniJMP Levene uses group means; Minitab 19 VARTEST uses medians. This is a method difference, not an algorithm defect.")
gap("multi_variance", "multi_variance", f, "VARTEST 多重比较 p 值", .966, 3,
    "多重比较        —  0.966", "多重比较", c,
    "Minitab 19 supplies a Bonferroni multiple-comparison result; MiniJMP multi_pop_var_test does not return a matching p value.")
f = "34单因子方差分析"
c = "单因子；组大小 4/5/6；等方差；α=.05；Fisher LSD；95% CI"
derived("one_way_anova", "one_way_anova_fisher", f, "N", "one_way_anova.N", 15,
        "合计            14  204.93", "合计 DF；N=DF+1", c,
        "Minitab 原生 total DF=14；按一因子模型 N=DF+1 推导。")
for metric, key, value, digits, token, field in [
    ("组间 DF", "df_between", 2, 0, "OneWayGroup    2  166.60", "因子项 DF/SS/MS/F/P"),
    ("组间 SS", "SS_between", 166.60, 2, "OneWayGroup    2  166.60  83.300", "Adj SS/Adj MS"),
    ("组间 MS", "MS_between", 83.300, 3, "OneWayGroup    2  166.60  83.300", "Adj SS/Adj MS"),
    ("组内 DF", "df_error", 12, 0, "误差            12   38.33", "误差 DF/SS/MS"),
    ("组内 SS", "SS_error", 38.33, 2, "误差            12   38.33   3.194", "误差 DF/SS/MS"),
    ("组内 MS", "MS_error", 3.194, 3, "误差            12   38.33   3.194", "误差 DF/SS/MS"),
    ("总计 DF", "df_total", 14, 0, "合计            14  204.93", "总计 DF/SS"),
    ("总计 SS", "SS_total", 204.93, 2, "合计            14  204.93", "总计 DF/SS"),
    ("整体 F", "F", 26.08, 2, "OneWayGroup    2  166.60  83.300  26.08  0.000", "F/P"),
    ("整体 p", "p", .000, 3, "OneWayGroup    2  166.60  83.300  26.08  0.000", "F/P"),
    ("R²", "R2_percent", 81.29, 2, "1.78730  81.29%    78.18%    71.64%", "模型汇总 R-sq"),
    ("调整 R²", "R2_adjusted_percent", 78.18, 2, "1.78730  81.29%    78.18%    71.64%", "模型汇总调整 R-sq"),
]:
    display("one_way_anova", "one_way_anova_fisher", f, metric, f"one_way_anova.{key}",
            value, digits, token, field, c)
gap("one_way_anova", "one_way_anova_fisher", f, "预测 R²", 71.64, 2,
    "1.78730  81.29%    78.18%    71.64%", "模型汇总预测 R-sq", c,
    "MiniJMP one_way_anova 返回结构不含 PRESS/预测 R²。")
for group, n, mean, lo, hi in [
    ("A", 4, 8.500, 6.553, 10.447),
    ("B", 5, 12.000, 10.258, 13.742),
    ("C", 6, 16.667, 15.077, 18.256),
]:
    token = f"{group}            {n}"
    display("one_way_anova", "one_way_anova_fisher", f, f"{group} 组 N",
            f"one_way_anova.n_{group}", n, 0, token, "均值表 N", c)
    display("one_way_anova", "one_way_anova_fisher", f, f"{group} 组均值",
            f"one_way_anova.mean_{group}", mean, 3, token, "均值表", c)
    display("one_way_anova", "one_way_anova_fisher", f, f"{group} 组均值 CI 下限",
            f"one_way_anova.ci_low_{group}", lo, 3, f"{lo:.3f}, {hi:.3f}", "均值 95% CI", c)
    display("one_way_anova", "one_way_anova_fisher", f, f"{group} 组均值 CI 上限",
            f"one_way_anova.ci_high_{group}", hi, 3, f"{lo:.3f}, {hi:.3f}", "均值 95% CI", c)
for contrast, key, value, token in [
    ("B−A", "fisher_p_A_B", .013, "B - A  3.50"),
    ("C−A", "fisher_p_A_C", .000, "C - A  8.17"),
    ("C−B", "fisher_p_B_C", .001, "C - B  4.67"),
]:
    display("one_way_anova", "one_way_anova_fisher", f, f"Fisher LSD {contrast} 单个检验 p",
            f"one_way_anova.{key}", value, 3, token,
            "均值差值的 Fisher 单个检验/调整的 P 值", c,
            "Minitab Fisher LSD 为未控制家族错误率的逐对检验；同 MiniJMP Fisher LSD 定义。")

f = "35双因子方差分析"
c = "固定效应 A+B+A*B；不平衡 2×2；EFFECT 编码；Type III Adjusted SS"
derived("two_way_anova", "two_way_anova_type3", f, "N", "two_way_anova.N", 18,
        "合计                  17  180.944", "总计 DF；N=DF+1", c,
        "Minitab 原生 total DF=17；按模型 N=DF+1 推导。")
for metric, key, value, digits, token, field in [
    ("因子 A DF", "dfA", 1, 0, "FactorA            1  113.124", "因子项 DF/SS/MS/F/P"),
    ("因子 A SS", "SSA", 113.124, 3, "FactorA            1  113.124  113.124", "Type III Adj SS/MS"),
    ("因子 A MS", "MSA", 113.124, 3, "FactorA            1  113.124  113.124", "Type III Adj SS/MS"),
    ("因子 A F", "F_A", 58.37, 2, "FactorA            1  113.124  113.124  58.37", "F/P"),
    ("因子 A p", "p_A", .000, 3, "FactorA            1  113.124  113.124  58.37  0.000", "F/P"),
    ("因子 B DF", "dfB", 1, 0, "FactorB            1   25.966", "因子项 DF/SS/MS/F/P"),
    ("因子 B SS", "SSB", 25.966, 3, "FactorB            1   25.966   25.966", "Type III Adj SS/MS"),
    ("因子 B MS", "MSB", 25.966, 3, "FactorB            1   25.966   25.966", "Type III Adj SS/MS"),
    ("因子 B F", "F_B", 13.40, 2, "FactorB            1   25.966   25.966  13.40", "F/P"),
    ("因子 B p", "p_B", .003, 3, "FactorB            1   25.966   25.966  13.40  0.003", "F/P"),
    ("交互 DF", "dfAB", 1, 0, "FactorA*FactorB    1    4.071", "因子项 DF/SS/MS/F/P"),
    ("交互 SS", "SSAB", 4.071, 3, "FactorA*FactorB    1    4.071    4.071", "Type III Adj SS/MS"),
    ("交互 MS", "MSAB", 4.071, 3, "FactorA*FactorB    1    4.071    4.071", "Type III Adj SS/MS"),
    ("交互 F", "F_AB", 2.10, 2, "FactorA*FactorB    1    4.071    4.071   2.10", "F/P"),
    ("交互 p", "p_AB", .169, 3, "FactorA*FactorB    1    4.071    4.071   2.10  0.169", "F/P"),
    ("误差 DF", "dfE", 14, 0, "误差                  14   27.133", "误差 DF/SS/MS"),
    ("误差 SS", "SSE", 27.133, 3, "误差                  14   27.133    1.938", "误差 DF/SS/MS"),
    ("误差 MS", "MSE", 1.938, 3, "误差                  14   27.133    1.938", "误差 DF/SS/MS"),
    ("总计 DF", "df_total", 17, 0, "合计                  17  180.944", "总计 DF/SS"),
    ("总计 SS", "SST", 180.944, 3, "合计                  17  180.944", "总计 DF/SS"),
    ("R²", "R2_percent", 85.00, 2, "1.39215  85.00%    81.79%    76.12%", "模型汇总 R-sq"),
    ("调整 R²", "R2_adjusted_percent", 81.79, 2, "1.39215  85.00%    81.79%    76.12%", "模型汇总调整 R-sq"),
]:
    display("two_way_anova", "two_way_anova_type3", f, metric, f"two_way_anova.{key}",
            value, digits, token, field, c)
gap("two_way_anova", "two_way_anova_type3", f, "预测 R²", 76.12, 2,
    "1.39215  85.00%    81.79%    76.12%", "模型汇总预测 R-sq", c,
    "MiniJMP two_way_anova 返回结构不含 PRESS/预测 R²。")

f = "18完整回归分析（多元线性 OLS）"
c = "OLS；含截距；X1/X2 连续；未标准化；α=.05；全部观测诊断"
for term, key, estimate, se, t, p, token, ed, sd in [
    ("常量", "Intercept", 6.059, .243, 24.91, .000, "常量        6.059", 3, 3),
    ("OLS_X1", "x1", 1.9609, .0511, 38.39, .000, "OLS_X1   1.9609", 4, 4),
    ("OLS_X2", "x2", -.1275, .0856, -1.49, .171, "OLS_X2  -0.1275", 4, 4),
]:
    for metric, suffix, value, digits in [
        ("系数", "estimate", estimate, ed), ("标准误", "se", se, sd),
        ("t", "t", t, 2), ("p", "p", p, 3),
    ]:
        display("ols_multiple", "ols_multiple", f, f"{term} {metric}",
                f"ols_multiple.{key}_{suffix}", value, digits, token, "系数/标准误/t/p", c)
derived("ols_multiple", "ols_multiple", f, "N", "ols_multiple.N", 12,
        "合计         11  517.069", "总计 DF；N=DF+1", c,
        "Minitab 原生 total DF=11；按回归模型 N=DF+1 推导。")
for metric, key, value, digits, token, field in [
    ("误差 DF", "df_error", 9, 0, "误差          9    1.130", "误差 DF/SS/MS"),
    ("残差标准差 S", "S", .354391, 6, "0.354391  99.78%", "模型汇总 S/R-sq"),
    ("R²", "R2_percent", 99.78, 2, "0.354391  99.78%    99.73%    99.60%", "模型汇总 R-sq"),
    ("调整 R²", "R2_adjusted_percent", 99.73, 2, "0.354391  99.78%    99.73%    99.60%", "模型汇总调整 R-sq"),
]:
    display("ols_multiple", "ols_multiple", f, metric, f"ols_multiple.{key}",
            value, digits, token, field, c)
gap("ols_multiple", "ols_multiple", f, "预测 R²", 99.60, 2,
    "0.354391  99.78%    99.73%    99.60%", "模型汇总预测 R-sq", c,
    "MiniJMP advanced_regression summary 不含 PRESS/预测 R²。")
for metric, key, value, digits, token, field in [
    ("回归 SS", "regression_SS", 515.939, 3, "回归          2  515.939  257.969", "ANOVA 回归 SS/MS"),
    ("回归 DF", "regression_df", 2, 0, "回归          2  515.939", "ANOVA 回归 DF"),
    ("回归 MS", "regression_MS", 257.969, 3, "回归          2  515.939  257.969", "ANOVA 回归 SS/MS"),
    ("整体 F", "model_F", 2054.01, 2, "回归          2  515.939  257.969  2054.01", "ANOVA 整体 F"),
    ("整体 p", "model_p", .000, 3, "回归          2  515.939  257.969  2054.01  0.000", "ANOVA 整体 P"),
    ("残差 SS", "residual_SS", 1.130, 3, "误差          9    1.130", "ANOVA 误差 SS/MS"),
    ("残差 MS", "residual_MS", .126, 3, "误差          9    1.130    0.126", "ANOVA 误差 SS/MS"),
    ("总计 SS", "total_SS", 517.069, 3, "合计         11  517.069", "ANOVA 总计"),
]:
    display("ols_multiple", "ols_multiple", f, metric, f"ols_multiple.{key}",
            value, digits, token, field, c)
for metric, key, nfield, col, token in [
    ("拟合值（第1行）", "fit_row1", "fit", 97, "1   8.100   7.765"),
    ("残差（第1行）", "residual_row1", "residual", 93, "1   8.100   7.765   0.335"),
    ("标准化残差（第1行）", "standardized_residual_row1", "standardized_residual", 94, "1   8.100   7.765   0.335   1.13"),
    ("杠杆值（第1行）", "leverage_row1", "leverage", 95, "1   8.100   7.765"),
    ("Cook 距离（第1行）", "cook_row1", "cooks_distance", 96, "1   8.100   7.765"),
]:
    stored("ols_multiple", "ols_multiple", f, metric, f"ols_multiple.{key}",
           nfield, col, token, f"REGRESS {nfield.upper()} C{col}; TDIAGNOSTICS", c)
for metric, key in [
    ("新 X 预测值", "prediction"),
    ("均值响应 95% CI 下限", "prediction_ci_low"),
    ("均值响应 95% CI 上限", "prediction_ci_high"),
    ("新观测 95% PI 下限", "prediction_pi_low"),
    ("新观测 95% PI 上限", "prediction_pi_high"),
]:
    no_reference("ols_multiple", "ols_prediction", f, metric, f"ols_multiple.{key}",
                 "X1=7,X2=5；95% 均值 CI 及个体 PI",
                 "Minitab 19.1.0.1 COM 的 PREDICT 项目模型语法报错，未取到原生预测值；命令和错误见 minitab_raw_outputs.txt。")

f = "18完整回归分析（分类自变量 OLS）"
c = "OLS；分类 X=group；BINARY (1,0)；参考水平 A；含截距"
for term, key, estimate, se, t, p, token in [
    ("常量", "Intercept", 11, .648, 16.97, .000, "常量                    11.000"),
    ("B", "group['B']", 4.4, .917, 4.80, .000, "B                    4.400"),
    ("C", "group['C']", 9, .917, 9.82, .000, "C                    9.000"),
]:
    for metric, suffix, value, digits in [
        ("系数", "estimate", estimate, 3), ("标准误", "se", se, 3),
        ("t", "t", t, 2), ("p", "p", p, 3),
    ]:
        display("ols_categorical", "ols_categorical", f, f"{term} {metric}",
                f"ols_categorical.{key}_{suffix}", value, digits, token,
                "分类系数/标准误/t/p", c)
derived("ols_categorical", "ols_categorical", f, "N", "ols_categorical.N", 15,
        "合计                       14  227.73", "总计 DF；N=DF+1", c,
        "Minitab 原生 total DF=14；按回归模型 N=DF+1 推导。")
for metric, key, value, digits, token, field in [
    ("误差 DF", "df_error", 12, 0, "误差                       12   25.20", "误差 DF/SS/MS"),
    ("R²", "R2_percent", 88.93, 2, "1.44914  88.93%    87.09%    82.71%", "模型汇总 R-sq"),
    ("调整 R²", "R2_adjusted_percent", 87.09, 2, "1.44914  88.93%    87.09%    82.71%", "模型汇总调整 R-sq"),
    ("模型项 SS", "SS", 202.53, 2, "回归                        2  202.53  101.267", "ANOVA SS/MS"),
    ("模型项 DF", "df", 2, 0, "回归                        2  202.53", "ANOVA DF"),
    ("模型项 MS", "MS", 101.267, 3, "回归                        2  202.53  101.267", "ANOVA SS/MS"),
    ("整体 F", "model_F", 48.22, 2, "回归                        2  202.53  101.267  48.22", "ANOVA 整体 F"),
    ("整体 p", "model_p", .000, 3, "回归                        2  202.53  101.267  48.22  0.000", "ANOVA 整体 P"),
]:
    display("ols_categorical", "ols_categorical", f, metric, f"ols_categorical.{key}",
            value, digits, token, field, c)
gap("ols_categorical", "ols_categorical", f, "预测 R²", 82.71, 2,
    "1.44914  88.93%    87.09%    82.71%", "模型汇总预测 R-sq", c,
    "MiniJMP categorical OLS summary 不含 PRESS/预测 R²。")

f = "18完整回归分析（Binary Logistic）"
c = "二值响应 0/1；Logit；连续 X；α=.05；Minitab Wald 检验"
display("binary_logistic", "binary_logistic", f, "N", "binary_logistic.N",
        36, 0, "已使用的行数  36", "已使用的行数", c)
display("binary_logistic", "binary_logistic", f, "截距估计", "binary_logistic.Intercept_estimate",
        -1.420, 3, "常量      -1.420  0.701", "系数", c)
stored("binary_logistic", "binary_logistic", f, "截距标准误", "binary_logistic.Intercept_se",
       "se_coefficients", 121, "常量      -1.420  0.701", "SECOEFFICIENTS C121", c, index=0,
       status="METHOD_DIFF", reason="高精度 Minitab SE 与 MiniJMP BFGS 协方差有实现差异，但两者按 Minitab 显示的 3 位小数一致。Minitab 方法说明其 Logistic SE 使用 observed-Hessian 协方差；MiniJMP 泛型 Logistic 读取 statsmodels BFGS 协方差。方法来源：https://support.minitab.com/en-us/minitab/help-and-how-to/statistical-modeling/regression/how-to/fit-binary-logistic-model/methods-and-formulas/estimated-equation/。")
display("binary_logistic", "binary_logistic", f, "X 系数", "binary_logistic.x_estimate",
        .686, 3, "LogitX   0.686  0.255", "系数", c)
stored("binary_logistic", "binary_logistic", f, "X 标准误", "binary_logistic.x_se",
       "se_coefficients", 121, "LogitX   0.686  0.255", "SECOEFFICIENTS C121", c, index=1,
       status="METHOD_DIFF", reason="高精度 Minitab SE 与 MiniJMP BFGS 协方差有实现差异，但两者按 Minitab 显示的 3 位小数一致。Minitab 方法说明其 Logistic SE 使用 observed-Hessian 协方差；MiniJMP 泛型 Logistic 读取 statsmodels BFGS 协方差。方法来源：https://support.minitab.com/en-us/minitab/help-and-how-to/statistical-modeling/regression/how-to/fit-binary-logistic-model/methods-and-formulas/estimated-equation/。")
for metric, key, value, digits, token, field in [
    ("X Wald χ²（MiniJMP z²）", "x_wald_chi_square", 7.27, 2, "LogitX    1  7.27  0.007", "Wald DF/χ²/P"),
    ("X p 值", "x_p", .007, 3, "LogitX    1  7.27  0.007", "Wald DF/χ²/P"),
    ("优势比", "x_odds_ratio", 1.9863, 4, "LogitX  1.9863  (1.2060, 3.2714)", "优势比及95% CI"),
    ("偏差 R²", "deviance_R2_percent", 19.03, 2, "19.03%   17.01%  44.05", "模型汇总偏差 R-sq"),
    ("AIC", "AIC", 44.05, 2, "19.03%   17.01%  44.05  44.41  47.22", "模型汇总 AIC"),
    ("BIC", "BIC", 47.22, 2, "19.03%   17.01%  44.05  44.41  47.22", "模型汇总 BIC"),
    ("Pearson GOF χ²", "pearson_chi-square_statistic", 36.57, 2, "Pearson           34  36.57  0.350", "Pearson GOF DF/χ²/P"),
]:
    if metric == "偏差 R²":
        key = "deviance_R2_percent"
    display("binary_logistic", "binary_logistic", f, metric,
            f"binary_logistic.{key}", value, digits, token, field, c)
for metric, key, value, token in [
    ("优势比 95% CI 下限", "x_odds_ratio_ci_low", 1.2060, "LogitX  1.9863  (1.2060, 3.2714)"),
    ("优势比 95% CI 上限", "x_odds_ratio_ci_high", 3.2714, "LogitX  1.9863  (1.2060, 3.2714)"),
]:
    add("binary_logistic", "binary_logistic", f, metric, f"binary_logistic.{key}", "display", c,
        token=token, field="优势比及95% CI", value=str(value), digits="4", status="METHOD_DIFF",
        reason="MiniJMP Logistic CI uses its statsmodels BFGS covariance; Minitab native CI uses its stored observed-Hessian SE. Upper endpoint differs at the fourth displayed decimal; formula and link are aligned. See Minitab methods source in the paired SE rows.")
no_reference("binary_logistic", "binary_logistic", f, "截距 z 统计量",
             "binary_logistic.Intercept_statistic", c,
             "Minitab 19 GZLM 原生系数表未显示截距 z/p；未据 MiniJMP 值推造参考。")
no_reference("binary_logistic", "binary_logistic", f, "截距 p 值",
             "binary_logistic.Intercept_p", c,
             "Minitab 19 GZLM 原生系数表未显示截距 z/p；未据 MiniJMP 值推造参考。")
for metric, value, digits, token, field, reason in [
    ("调整偏差 R²", 17.01, 2, "19.03%   17.01%  44.05  44.41", "模型汇总调整偏差 R²", "MiniJMP Logistic summary 不返回调整偏差 R²。"),
    ("AICc", 44.41, 2, "19.03%   17.01%  44.05  44.41  47.22", "模型汇总 AICc", "MiniJMP Logistic summary 不返回 AICc。"),
    ("Pearson GOF p", .350, 3, "Pearson           34  36.57  0.350", "Pearson GOF P 值", "MiniJMP diagnostics 有 Pearson χ²，但没有相同自由度下的 GOF p 字段。"),
    ("偏差 GOF χ²", 40.05, 2, "偏差                34  40.05  0.219", "偏差 GOF DF/χ²/P", "MiniJMP Logistic diagnostics 未返回 Minitab 同口径 residual deviance GOF χ²。"),
    ("偏差 GOF p", .219, 3, "偏差                34  40.05  0.219", "偏差 GOF P 值", "MiniJMP Logistic diagnostics 未返回 Minitab 同口径 residual deviance GOF p。"),
    ("Hosmer–Lemeshow χ²", .24, 2, "Hosmer-Lemeshow    4   0.24  0.993", "Hosmer-Lemeshow DF/χ²/P", "MiniJMP Logistic diagnostics 没有 Hosmer–Lemeshow 分组检验。"),
    ("Hosmer–Lemeshow p", .993, 3, "Hosmer-Lemeshow    4   0.24  0.993", "Hosmer-Lemeshow DF/χ²/P", "MiniJMP Logistic diagnostics 没有 Hosmer–Lemeshow 分组检验。"),
]:
    gap("binary_logistic", "binary_logistic", f, metric, value, digits, token, field, c, reason)

f = "19泊松回归"
c = "Poisson 响应；log 链接；一个连续 X；α=.05"
display("poisson", "poisson", f, "N", "poisson.N", 24, 0,
        "已使用的行数  24", "已使用的行数", c)
stored("poisson", "poisson", f, "截距估计", "poisson.Intercept_estimate",
       "coefficients", 122, "常量        -0.069   0.317", "COEFFICIENTS C122", c, index=0)
stored("poisson", "poisson", f, "截距标准误", "poisson.Intercept_se",
       "se_coefficients", 123, "常量        -0.069   0.317", "SECOEFFICIENTS C123", c, index=0)
stored("poisson", "poisson", f, "X 系数", "poisson.x_estimate",
       "coefficients", 122, "PoissonX  0.3063  0.0858", "COEFFICIENTS C122", c, index=1)
stored("poisson", "poisson", f, "X 标准误", "poisson.x_se",
       "se_coefficients", 123, "PoissonX  0.3063  0.0858", "SECOEFFICIENTS C123", c, index=1)
for metric, key, value, digits, token, field in [
    ("X Wald χ²（MiniJMP z²）", "x_wald_chi_square", 12.75, 2, "PoissonX    1  12.75  0.000", "Wald DF/χ²/P"),
    ("X p 值", "x_p", .000, 3, "PoissonX    1  12.75  0.000", "Wald DF/χ²/P"),
    ("AIC", "AIC", 71.55, 2, "64.11%   59.48%  71.55  72.12", "模型汇总 AIC"),
    ("BIC", "BIC", 73.91, 2, "64.11%   59.48%  71.55  72.12  73.91", "模型汇总 BIC"),
    ("偏差 GOF DF", "df_error", 22, 0, "偏差        22  7.75250", "偏差 GOF DF"),
    ("偏差 GOF χ²", "deviance_statistic", 7.75, 2, "偏差        22  7.75250  0.35239  7.75  0.998", "偏差 GOF χ²/P"),
    ("偏差 GOF p", "deviance_p", .998, 3, "偏差        22  7.75250  0.35239  7.75  0.998", "偏差 GOF χ²/P"),
    ("Pearson GOF DF", "df_error", 22, 0, "Pearson   22  6.07829", "Pearson GOF DF"),
    ("Pearson GOF χ²", "pearson_statistic", 6.08, 2, "Pearson   22  6.07829  0.27629  6.08  1.000", "Pearson GOF χ²/P"),
    ("Pearson GOF p", "pearson_p", 1.000, 3, "Pearson   22  6.07829  0.27629  6.08  1.000", "Pearson GOF χ²/P"),
]:
    display("poisson", "poisson", f, metric, f"poisson.{key}", value, digits, token, field, c)
for metric, value, digits, token, field, reason in [
    ("偏差 R²", 64.11, 2, "64.11%   59.48%  71.55", "模型汇总偏差 R²", "MiniJMP generalized Poisson summary 不返回 deviance R²。"),
    ("调整偏差 R²", 59.48, 2, "64.11%   59.48%  71.55  72.12", "模型汇总调整偏差 R²", "MiniJMP generalized Poisson summary 不返回调整偏差 R²。"),
    ("AICc", 72.12, 2, "64.11%   59.48%  71.55  72.12  73.91", "模型汇总 AICc", "MiniJMP generalized Poisson summary 不返回 AICc。"),
]:
    gap("poisson", "poisson", f, metric, value, digits, token, field, c, reason)
no_reference("poisson", "poisson", f, "截距 z 统计量", "poisson.Intercept_statistic", c,
             "Minitab 19 Poisson 系数表未显示截距 z/p；未据 MiniJMP 值推造参考。")
no_reference("poisson", "poisson", f, "截距 p 值", "poisson.Intercept_p", c,
             "Minitab 19 Poisson 系数表未显示截距 z/p；未据 MiniJMP 值推造参考。")

f = "13相关分析（非参数相关）"
c = "同一组 12 对序数数据；Spearman 平均秩、双侧 p；Kendall tau-b 采用 XTABS CONCORDANT 一致性检验"
stored("rank_correlation", "spearman_correlation", f, "Spearman rho", "rank_correlation.spearman_coefficient",
       "SCORRELATION M3[2,1]", "", "", "", c, index=0,
       reason="Minitab 19 直接存储 2×2 相关矩阵非对角元素；矩阵完整值在 minitab_results.json。")
stored("rank_correlation", "spearman_correlation", f, "Spearman 双侧 p 值", "rank_correlation.spearman_p",
       "SPVALUES M4[2,1]", "", "", "", c, index=0,
       reason="Minitab 19 直接存储 2×2 p 值矩阵非对角元素；矩阵完整值在 minitab_results.json。")
display("rank_correlation", "kendall_association", f, "Kendall tau-b", "rank_correlation.kendall_coefficient",
        0.823558, 6, "Kendall 的 Tau-b", "XTABS CONCORDANT Kendall tau-b", c)
add("rank_correlation", "kendall_association", f, "Kendall p 值", "rank_correlation.kendall_p",
    "display", c, token="0.0001309", field="XTABS CONCORDANT 一致性检验 p 值",
    value="0.0001309", digits="7", status="METHOD_DIFF",
    reason="合理方法差异：Minitab 的 XTABS CONCORDANT 检验序数类别独立性并以正态统计量给出一致性检验 p；MiniJMP nonpara_cor.kendall 返回双侧 Kendall tau-b 检验 p。系数另行比较；未为机械匹配而改算法。Minitab 方法说明：https://support.minitab.com/en-us/minitab/help-and-how-to/statistics/tables/how-to/cross-tabulation-and-chi-square/methods-and-formulas/measures-of-concordance-for-ordinal-categories/。")
for metric, key in (("Hoeffding's D 原生参考", "coefficient"), ("Hoeffding's D p 值原生参考", "p")):
    add("rank_correlation", "spearman_correlation", f, metric,
        f"rank_correlation.hoeffding_{key}", "unavailable", c,
        status="UNSUPPORTED",
        reason="Minitab 19 CORRELATION 命令只提供 Pearson/Spearman，XTABS CONCORDANT 提供 Kendall tau-b；本菜单的 Hoeffding D 无对应 Minitab 19 原生结果，故不伪造参考。")

assert len(rows) > 180
assert all(row["Minitab参考版本"] == "19.1.0.1" for row in rows)
with (PHASE / "minitab_reference.csv").open("w", encoding="utf-8-sig", newline="") as stream:
    writer = csv.DictWriter(stream, fieldnames=HEADERS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
print(f"Wrote {len(rows)} reference rows from Minitab {native['version']}.")
print("Source types:", {kind: sum(row["Minitab来源"] == kind for row in rows)
                       for kind in sorted({row["Minitab来源"] for row in rows})})
print("Overrides:", {kind: sum(row["status_override"] == kind for row in rows)
                     for kind in sorted({row["status_override"] for row in rows if row["status_override"]})})


