from __future__ import annotations

import ast
import csv
import json
import math
import re
import subprocess
import sys
import time
import traceback
from collections import Counter
from pathlib import Path


OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]
CODE = ROOT / "code"
INPUT = OUT / "case_inputs.json"
MTB_EXE = Path(r"D:\Program\Minitab 19\Mtb.exe")
PROJECT_PYTHON = ROOT / ".venv" / "Scripts" / "python.exe"
DIRECT_TOL = 1e-10
STATUS_ORDER = ("PASS", "FAIL", "METHOD_DIFF", "UNSUPPORTED", "NOT_RUN")

sys.path.insert(0, str(CODE))
sys.path.insert(0, str(ROOT / "Out" / "minitab19_parity"))

import verify_minitab19_com as com_check  # noqa: E402
from verify_doe_2x2 import capture_command_output, running_minitab_pids  # noqa: E402


COMMANDS = {
    "descriptive": "STATS C1;\n  N C20;\n  MEAN C21;\n  STDEV C22.",
    "normality": "NORMTEST C2;\n  SPVALUE C25.",
    "pearson": "CORRELATION C3 C4;\n  PEARSON;\n  NODEFAULT;\n  SCORRELATION M1;\n  SPVALUES M2.",
    "one_sample_t": "ONET C5;\n  TEST 10;\n  CONFIDENCE 95;\n  SPVALUE C26;\n  SCONF C27 C28.",
    "two_sample_t": "TWOSAMPLE 95 C7 C6;\n  TEST 0;\n  SPVALUE C29;\n  SCONF C30 C31.",
    "paired_t": "PAIR C8 C9;\n  TEST 0;\n  CONFIDENCE 95;\n  SPVALUE C32;\n  SCONF C33 C34.",
    "one_way_anova": "ONEWAY;\n  RESPONSE C10;\n  CATEGORICAL C11;\n  CONFIDENCE 95;\n  TANOVA.",
    "ols_linear": (
        "REGRESS;\n  RESPONSE C12;\n  CONTINUOUS C13;\n  TERMS C13;\n  CONSTANT;\n  UNSTANDARDIZED;\n  CONFIDENCE 95;\n"
        "  TCOEFFICIENTS;\n  TANOVA;\n  COEFFICIENTS C40;\n  SPVALUE C41;\n"
        "  SS C42;\n  SRSQ C43;\n  XPXINV M3."
    ),
}
AUXILIARY_COMMANDS = {"descriptive_display": "DESCRIBE C1."}


# product module/method, existing tests, independent-reference coverage, and caveat
FEATURE_INFO = {
    "01描述性统计": ("basic_dialogs.DescribeDialog → describe.describe", "tests/test_statistics_regressions.py; tests/test_g7_tables.py", "是", "是", "描述性汇总使用样本标准差；已有独立数值参考仅覆盖部分字段。", "P0"),
    "02多变量描述性统计": ("basic_dialogs.MultiDescribeDialog → describe.describe", "tests/test_statistics_regressions.py; tests/test_g2_basic_reports.py", "部分", "部分", "复用单列统计计算；未找到覆盖多列完整结果矩阵的独立数值参考。", "P1"),
    "04正态性检验": ("basic_dialogs.NormTestDialog → utilities.norm_test", "tests/test_g2_basic_reports.py; tests/test_g6_chart_presentation.py; tests/test_column_selection.py", "部分", "否", "MiniJMP 使用 Shapiro-Wilk 与 statsmodels normal_ad；未找到独立 AD 参考。本轮 Minitab 19 COM 只回传正态概率图标题，AD 统计量无法稳定读取。", "P0"),
    "05置信区间": ("basic_dialogs.CIDialog → utilities.mean_std_CIs", "tests/test_g2_hypothesis_reports.py; tests/test_review_p1_statistics.py", "部分", "部分", "均值区间用 t 方法；标准差区间用卡方方法并假设总体正态。", "P1"),
    "06分布拟合": ("basic_dialogs.FitDistDialog → dist_fit.compare_dist", "tests/test_g3_distribution_reports.py; tests/test_g16_statistics.py", "部分", "部分", "分布候选及拟合优度准则需分别比较；现有测试不等于 Minitab 对标。", "P1"),
    "13相关分析": ("fit_dialog.CorrelationDialog → utilities.pearson_correlation / nonpara_cor", "tests/test_statistics_regressions.py; tests/test_g3_regression_reports.py", "有", "是", "Pearson p 值采用双侧 t 检验；相关不代表因果。", "P0"),
    "14线性回归": ("fit_dialog.LinearFitDialog → linear_plot.fit_plot → linear_fit.linear_fit", "tests/test_statistics_regressions.py; tests/test_g3_regression_reports.py", "有", "是", "单预测变量 OLS；与“完整回归分析”入口分开。", "P0"),
    "15残差图": ("fit_dialog.ResidDialog → Residual.linear_fit_resid_test", "tests/test_statistics_regressions.py; tests/test_g3_regression_reports.py", "部分", "部分", "用于模型诊断，不会自动修复或选择模型。", "P2"),
    "16正交回归": ("fit_dialog.OrthoFitDialog → ortho_fit.orthogonal_fit", "tests/test_review_p1_statistics.py; tests/test_g3_regression_reports.py", "有", "是", "误差变量模型；结果受输入的误差方差比影响。", "P1"),
    "17相关系数矩阵": ("fit_dialog.MCorDialog → multi_fit", "tests/test_g2_basic_reports.py", "部分", "否", "多列分析使用完整行；现有测试覆盖四种方法的报告路由，未发现完整矩阵数值参考。", "P1"),
    "18完整回归分析": ("regression_dialog.RegressionDialog → advanced_regression.fit_regression", "tests/test_advanced_regression.py", "有", "是", "OLS/WLS 与广义线性模型口径不同；变量筛选后的推断未校正选择偏差。", "P1"),
    "19泊松回归": ("RegressionDialog(model='Poisson') → generalized_regression.fit_generalized", "tests/test_generalized_regression.py", "有", "是", "推断为渐近方法；不包含未实现的过度离散模型。", "P1"),
    "20名义多分类 Logistic 回归": ("RegressionDialog(model='Nominal') → generalized_regression.fit_generalized", "tests/test_generalized_regression.py", "有", "是", "需显式指定参考类别；分离等边界按实现约定处理。", "P1"),
    "21有序 Logistic 回归": ("RegressionDialog(model='Ordinal') → generalized_regression.fit_generalized", "tests/test_generalized_regression.py", "有", "是", "类别顺序需显式指定；不支持 gompit 或比例优势假设检验。", "P1"),
    "22偏最小二乘回归（PLS）": ("RegressionDialog(model='PLS') → pls_regression.fit_pls", "tests/test_pls_regression.py", "有", "是", "仅支持数值 X；交叉验证和成分选择不承诺与 Minitab 一致。", "P1"),
    "23主成分分析": ("pca_dialog.PCADialog → pca_analysis.fit_pca", "tests/test_pca_analysis.py", "有", "是", "测试含协方差矩阵特征分解及 rank-1、T²、Q 独立参考；限值仍受模型假设约束。", "P1"),
    "23时间序列分析": ("advanced_time_series_dialog → time_series_analysis.analyze_time_series", "tests/test_time_series_analysis.py", "有", "是", "预测区间未包含参数估计不确定性；缺失值不自动插补。", "P1"),
    "25单样本均值 t 检验": ("Mean1SampleDialog → t_test.t_test_1sample", "tests/test_g2_hypothesis_reports.py; tests/test_statistics_regressions.py", "有", "是", "双侧 95% 区间及 alpha=.05 有 SciPy/独立公式参考。", "P0"),
    "26单样本均值 Z 检验": ("Mean1SampleZDialog → t_test.z_test_1sample", "tests/test_g2_hypothesis_reports.py; tests/test_statistics_regressions.py", "部分", "部分", "需已知总体标准差或符合汇总输入约定。", "P1"),
    "27单样本标准差检验": ("Var1SampleDialog → chi_sq.var_1sample", "tests/test_g2_hypothesis_reports.py; tests/test_statistical_batch2.py", "部分", "部分", "卡方方法假设总体正态；可选方法的统计定义各不相同。", "P1"),
    "28单比率检验": ("Prop1SDialog → proportion_test.prop_test_1sample", "tests/test_review_proportions.py; tests/test_g2_hypothesis_reports.py", "有", "是", "精确区间与检验定义可能不同；Minitab 22 帮助不是 Minitab 19 证据。", "P1"),
    "29双样本 t 检验": ("Mean2SampleDialog → t_test.t_test_2samples", "tests/test_g2_hypothesis_reports.py; tests/test_statistics_regressions.py", "有", "是", "双方均用 Welch 不等方差。Minitab 22.6 之前的桌面版会将 Welch 自由度截为整数；MiniJMP 保留 Welch-Satterthwaite 小数自由度，p 值因此不同。", "P0"),
    "30配对 t 检验": ("PairedTDialog → t_test.paired_t_test", "tests/test_g2_hypothesis_reports.py", "部分", "部分", "按 sample1−sample2 的配对差值检验；不匹配的额外观测不参与计算。", "P0"),
    "31双比率检验": ("Prop2SDialog → proportion_test.prop_2sample", "tests/test_review_proportions.py; tests/test_g2_hypothesis_reports.py", "有", "是", "精确枚举与大样本近似应分别比较。", "P1"),
    "32多样本标准差检验": ("MultiVarDialog → chi_sq.multi_pop_var_test", "tests/test_g2_hypothesis_reports.py; tests/test_statistical_batch2.py", "部分", "部分", "正态性及方差结构假设取决于所选方法。", "P1"),
    "34单因子方差分析": ("Anova1WayDialog → one_way_ANOVA.one_way_anova", "tests/test_g3_anova_reports.py; tests/test_statistics_regressions.py", "有", "是", "传统等方差单因子 ANOVA；两两比较及多重比较校正另行核对。", "P0"),
    "35双因子方差分析": ("Anova2WayDialog → two_way_anova.two_way_anova", "tests/test_review003_anova.py; tests/test_g3_anova_reports.py", "有", "是", "不平衡或缺失单元按可估性约束处理；Minitab 22 对齐说明不构成 Minitab 19 验证。", "P1"),
    "36试验设计功效与样本量": ("doe_power_dialog.AnalyzeDOEPower → doe_power.calculate_power", "tests/test_doe_power.py", "有", "是", "要求设计矩阵可估且残差自由度为正。", "P1"),
    "42列联表与卡方检验": ("Chi2TableDialog → chi_sq.chi_square", "tests/test_g3_chi_square_reports.py; tests/test_statistical_edges.py", "有", "是", "Pearson/LR 大样本检验不等同精确检验。", "P1"),
    "43比率卡方检验": ("Chi2PropDialog → chi_sq.chi_square", "tests/test_g3_chi_square_reports.py; tests/test_g3_computation_contracts.py", "有", "是", "拟合优度卡方近似；与单比率二项检验不同。", "P1"),
    "01量具 R&R 研究（交叉）": ("GRRDialog → GRR.grr_master", "tests/test_statistical_batch2.py; tests/test_g16_statistics.py; tests/test_g3_anova_reports.py", "部分", "部分", "交叉设计；缺失组合、重复次数及交互项可估性会影响结果。", "P1"),
    "02量具 R&R 研究（嵌套）": ("GRR_Nested_Dialog → GRR.grr_nested", "tests/test_statistical_batch2.py; tests/test_g16_statistics.py", "部分", "部分", "嵌套设计不能与交叉设计互换。", "P1"),
    "07过程能力分析 (Cpk)": ("CpkDialog → cpk.cpk", "tests/test_statistical_edges.py; tests/test_statistics_regressions.py", "部分", "部分", "旧 Cpk 路径；正态性及组内/整体变异口径会影响指数。", "P1"),
    "08含子组的 Cpk": ("CpkSubDialog → cpk.cpk", "tests/test_statistical_batch2.py; tests/test_g5_spc_reports.py", "部分", "部分", "子组边界与大小决定组内变异估计。", "P1"),
    "09正态过程能力（完整）": ("CapabilityDialog(mode='正态能力') → capability.analyze_capability", "tests/test_capability.py; tests/test_capability_plots.py; tests/test_capability_dialog.py", "有", "是", "当前接口约定下部分指数区间不可用。", "P1"),
    "10非正态过程能力": ("CapabilityDialog(mode='非正态能力') → capability.analyze_capability", "tests/test_capability.py; tests/test_capability_plots.py; tests/test_capability_dialog.py", "有", "是", "支持的分布和指数范围有限；自举带有模拟误差。", "P1"),
    "11Box-Cox / Johnson 变换": ("CapabilityDialog(mode='变换诊断') → capability.transform_values", "tests/test_capability.py", "有", "是", "Johnson 变换限 SU；Box-Cox 使用未舍入 λ 的剖面似然。", "P1"),
    "12正态能力 Sixpack": ("CapabilityDialog(mode='正态 Sixpack') → capability.analyze_capability / capability_plots.plot_capability", "tests/test_capability_plots.py; tests/test_capability_dialog.py", "部分", "部分", "复用正态能力结果；控制限不代表已执行全部判异规则。", "P2"),
    "13非正态能力 Sixpack": ("CapabilityDialog(mode='非正态 Sixpack') → capability.analyze_capability / capability_plots.plot_capability", "tests/test_capability_plots.py; tests/test_capability_dialog.py", "部分", "部分", "部分控制限使用正态常数近似。", "P2"),
    "22容差区间": ("TIDialog → ti.ti_norm", "tests/test_review_p1_statistics.py; tests/test_statistical_batch2.py", "部分", "部分", "需区分总体容许比例与置信水平。", "P1"),
    "32控制图 I-MR": ("IMRDialog → control_chart.x_plot(plot_type='x_mR')", "tests/test_g5_spc_reports.py; tests/test_g6_quality_charts.py; tests/test_review_p1_statistics.py", "部分", "部分", "按观测顺序计算；首个移动极差未定义。", "P1"),
    "33控制图 I（单值）": ("IDialog → control_chart.x_plot", "tests/test_g5_spc_reports.py; tests/test_g6_quality_charts.py", "部分", "部分", "单值图；sigma 与基线选项影响控制限。", "P1"),
    "34控制图 MR（移动极差）": ("MRDialog → control_chart.x_plot", "tests/test_g5_spc_reports.py; tests/test_g6_quality_charts.py", "部分", "部分", "仅显示移动极差；首个观测没有前序点。", "P1"),
    "35控制图 Xbar-R": ("XBRDialog → control_chart.x_plot(plot_type='XBAR_R')", "tests/test_g5_spc_reports.py; tests/test_g6_quality_charts.py; tests/test_statistics_regressions.py", "有", "是", "需提供有效子组；R 图常数有支持的子组大小范围。", "P1"),
    "36控制图 Xbar-S": ("XBSDialog → control_chart.x_plot(plot_type='XBAR_S')", "tests/test_g5_spc_reports.py; tests/test_g6_quality_charts.py; tests/test_statistics_regressions.py", "有", "是", "使用 S 图常数，不能与 Xbar-R 口径混用。", "P1"),
    "37高级 SPC 控制图": ("AdvancedSPCDialog → advanced_spc.analyze_spc / nelson_events", "tests/test_advanced_spc.py; tests/test_advanced_spc_dialog.py", "有", "是", "EWMA、CUSUM、Nelson、T² 有各自假设；不支持跨会话在线状态续接。", "P1"),
    "42控制图 NP": ("NPDialog → control_chart.p_np_plot", "tests/test_g5_spc_reports.py; tests/test_g6_quality_charts.py", "部分", "部分", "缺陷数图要求样本量固定。", "P1"),
    "43控制图 P": ("PDialog → control_chart.p_np_plot", "tests/test_g5_spc_reports.py; tests/test_g6_quality_charts.py", "部分", "部分", "不合格率图使用各子组分母。", "P1"),
    "44控制图 C": ("CDialog → control_chart.cu_plot", "tests/test_g5_spc_reports.py; tests/test_g6_quality_charts.py", "部分", "部分", "缺陷数图要求检验机会恒定。", "P1"),
    "45控制图 U": ("UDialog → control_chart.cu_plot", "tests/test_g5_spc_reports.py; tests/test_g6_quality_charts.py", "部分", "部分", "单位缺陷率图使用各子组机会数。", "P1"),
    "50帕累托图": ("QualityToolsDialog(kind='pareto') → quality_tools.pareto_chart", "tests/test_quality_tools.py", "有", "是", "描述图；计数汇总及小类别合并有明确约定。", "P2"),
    "51运行图": ("QualityToolsDialog(kind='run_chart') → quality_tools.run_chart", "tests/test_quality_tools.py", "有", "是", "保留输入顺序；渐近 p 值有样本量与并列值限制。", "P1"),
    "52因果图": ("QualityToolsDialog(kind='cause_effect') → quality_tools.cause_effect", "tests/test_quality_tools.py", "部分", "否", "结构化因果图，不进行统计检验。", "P2"),
    "53多变异图": ("QualityToolsDialog(kind='multi_vari') → quality_tools.multi_vari", "tests/test_quality_tools.py", "有", "是", "描述组合均值、样本标准差和极差，不是 ANOVA。", "P2"),
    "54属性一致性分析": ("QualityToolsDialog(kind='attribute_agreement') → attribute_agreement.attribute_agreement", "tests/test_attribute_agreement.py", "有", "是", "要求完整平衡的长格式设计；不支持加权 Kappa。", "P1"),
}


DOE_EVIDENCE = {
    "01创建两水平全因子设计": "Out/minitab19_parity/verify_doe_2x2.py",
    "03分析因子设计": "Out/minitab19_parity/verify_doe_2x2.py; Out/minitab19_parity/supplemental/general_factorial/",
    "04创建中心复合设计": "Out/minitab19_parity/verify_doe_ccd.py",
    "05分析响应面模型": "Out/minitab19_parity/verify_doe_ccd.py; Out/minitab19_parity/verify_doe_bbd.py",
    "07创建 Box-Behnken 设计": "Out/minitab19_parity/verify_doe_bbd.py",
    "08响应面预测": "Out/minitab19_parity/verify_doe_ccd.py; Out/minitab19_parity/verify_doe_bbd.py",
    "10创建 Plackett–Burman 设计": "Out/minitab19_parity/verify_doe_pb.py",
    "11创建筛选设计（DSD）": "Out/minitab19_parity/supplemental/dsd/",
    "12分析筛选设计": "Out/minitab19_parity/supplemental/dsd/",
    "13创建一般全因子设计": "Out/minitab19_parity/supplemental/general_factorial/",
    "14折叠两水平部分因子设计": "Out/minitab19_parity/supplemental/foldover/",
    "15创建多因子裂区设计": "Out/minitab19_parity/verify_doe_splitplot.py",
    "23选择最优设计": "Out/minitab19_parity/supplemental/optimal/",
    "26创建混料设计": "Out/minitab19_parity/verify_doe_mixture.py",
    "27分析混料设计": "Out/minitab19_parity/verify_doe_mixture.py; Out/minitab19_parity/supplemental/mixture_extended/",
    "28混料预测": "Out/minitab19_parity/verify_doe_mixture.py; Out/minitab19_parity/supplemental/mixture_extended/",
    "33创建 Taguchi 设计（静态）": "Out/minitab19_parity/verify_doe_taguchi.py",
    "34创建 Taguchi 设计（动态）": "Out/minitab19_parity/supplemental/taguchi_dynamic/",
    "35分析 Taguchi 设计": "Out/minitab19_parity/verify_doe_taguchi.py; Out/minitab19_parity/supplemental/taguchi_dynamic/",
}

DOE_CALLS = {
    "CreateDOE": "doe_dialog.CreateDOE",
    "AnalyzeDOE": "doe_dialog.AnalyzeDOE",
    "OptimizeRSM": "doe_optimize_dialog.OptimizeRSM",
    "CreateGeneralFactorial": "doe_dialog.CreateGeneralFactorial",
    "FoldoverDOE": "doe_foldover_dialog.FoldoverDOE",
    "CreateSplitPlot": "doe_splitplot_dialog.CreateSplitPlot",
    "DefineCustomDOE": "doe_custom_dialog.DefineCustomDOE",
    "ModifyDesignDialog": "doe_optimal_dialog.ModifyDesignDialog",
    "AugmentDesignDialog": "doe_optimal_dialog.AugmentDesignDialog",
    "OptimalDesignDialog": "doe_optimal_dialog.OptimalDesignDialog",
    "EvaluateDesignDialog": "doe_optimal_dialog.EvaluateDesignDialog",
    "CreateMixtureDesign": "doe_mixture_dialog.CreateMixtureDesign",
    "AnalyzeMixtureDesign": "doe_mixture_dialog.AnalyzeMixtureDesign",
    "PredictMixture": "doe_mixture_dialog.PredictMixture",
    "OptimizeMixture": "doe_mixture_dialog.OptimizeMixture",
    "MixtureOptimalDesignDialog": "doe_mixture_dialog.MixtureOptimalDesignDialog",
    "MixturePlots": "doe_mixture_dialog.MixturePlots",
    "CreateTaguchi": "doe_taguchi_dialog.CreateTaguchi",
    "AnalyzeTaguchi": "doe_taguchi_analysis_dialog.AnalyzeTaguchi",
    "AnalyzeBinaryDOE": "doe_binary_dialog.AnalyzeBinaryDOE",
    "AnalyzeVariabilityDOE": "doe_variability_dialog.AnalyzeVariabilityDOE",
}

MATRIX_FIELDS = (
    "类别", "功能名称", "MiniJMP菜单功能", "实现入口", "生产模块及调用方法",
    "已有测试", "对应测试文件", "独立验证", "是否已有独立数值参考",
    "Minitab 19 对标", "优先级", "备注及证据来源",
)
COMPARISON_FIELDS = (
    "case_id", "功能名称", "输入案例", "统计量", "Minitab值", "MiniJMP值",
    "绝对误差", "绝对容差", "相对容差", "结果", "Minitab结果来源",
    "MiniJMP结果来源", "统计定义/选项", "备注",
)
SUMMARY_FIELDS = (
    "case_id", "功能名称", "比较指标数", "PASS", "FAIL", "METHOD_DIFF",
    "UNSUPPORTED", "NOT_RUN", "功能状态", "备注",
)


def write_csv(path: Path, fields: tuple[str, ...], rows: list[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def read_cases() -> tuple[dict, dict]:
    payload = json.loads(INPUT.read_text(encoding="utf-8"))
    options, cases = payload["options"], payload["cases"]
    required = set(COMMANDS)
    if set(cases) != required:
        raise ValueError(f"固定输入案例必须为 {sorted(required)}")
    for case_id, case in cases.items():
        arrays = [value for value in case.values() if isinstance(value, list)]
        if any(not all(math.isfinite(float(value)) for value in values) for values in arrays):
            raise ValueError(f"{case_id} 输入包含缺失或非有限观测")
    return options, cases


def production_results(options: dict, cases: dict) -> dict:
    from describe import describe
    from linear_fit import linear_fit
    from one_way_ANOVA import one_way_anova
    from t_test import paired_t_test, t_test_1sample, t_test_2samples
    from utilities import norm_test, pearson_correlation

    alpha = float(options["alpha"])
    result = {}
    x = cases["descriptive"]["values"]
    desc = describe(x)
    result["descriptive"] = {
        "N": (desc["N"], "describe.describe：有效样本数 N"),
        "Mean": (desc["mean"], "describe.describe：均值"),
        "StDev": (desc["stdev"], "describe.describe：样本标准差"),
        "Minimum": (desc["min"], "describe.describe：最小值"),
        "Maximum": (desc["max"], "describe.describe：最大值"),
    }

    normal = norm_test(cases["normality"]["values"], print_out=False)
    result["normality"] = {
        "AD": (normal["AD s"], "utilities.norm_test → statsmodels.normal_ad：调整 AD 统计量"),
        "p": (normal["AD p"], "utilities.norm_test → statsmodels.normal_ad：AD p 值"),
    }

    corr_case = cases["pearson"]
    corr = pearson_correlation(corr_case["x"], corr_case["y"], alpha=alpha, print_out=False)
    result["pearson"] = {
        "r": (corr["r"], "utilities.pearson_correlation：Pearson r"),
        "p": (corr["p"], "utilities.pearson_correlation：双侧 t 检验 p 值"),
    }

    one_case = cases["one_sample_t"]
    one = t_test_1sample(one_case["values"], one_case["mu0"], alpha=alpha)
    result["one_sample_t"] = {
        "t": (one["t"], "t_test.t_test_1sample：t 值"), "df": (one["df"], "t_test.t_test_1sample：自由度"),
        "p": (one["p"], "t_test.t_test_1sample：双侧 p 值"),
        "CI lower": (one["u0_95range"][0], "t_test.t_test_1sample：95% 区间下限"),
        "CI upper": (one["u0_95range"][1], "t_test.t_test_1sample：95% 区间上限"),
    }

    two_case = cases["two_sample_t"]
    two = t_test_2samples(two_case["sample1"], two_case["sample2"], d0=two_case["null_difference"],
                          alpha=alpha, pooled=False)
    from scipy.stats import t as t_distribution
    result["two_sample_t"] = {
        "Mean difference (mu2-mu1)": ((two["CI"][0] + two["CI"][1]) / 2, "t_test.t_test_2samples：95% 区间中点（mu2−mu1）"),
        "SE difference": ((two["CI"][1] - two["CI"][0]) / (2 * t_distribution.ppf(1-alpha/2, two["df"])),
                           "t_test.t_test_2samples：由 95% 区间宽度和自由度推导"),
        "t": (two["t"], "t_test.t_test_2samples：Welch t 值"), "df": (two["df"], "t_test.t_test_2samples：Welch-Satterthwaite 自由度"),
        "p": (two["p"], "t_test.t_test_2samples：双侧 Welch p 值"),
    }

    pair_case = cases["paired_t"]
    paired = paired_t_test(pair_case["sample1"], pair_case["sample2"], u0=pair_case["null_difference"], alpha=alpha)
    result["paired_t"] = {
        "Mean difference (sample1-sample2)": (paired["mean"], "t_test.paired_t_test：配对差值均值"),
        "t": (paired["t"], "t_test.paired_t_test：t 值"), "df": (paired["df"], "t_test.paired_t_test：自由度"),
        "p": (paired["p"], "t_test.paired_t_test：双侧 p 值"),
    }

    groups = cases["one_way_anova"]["groups"]
    anova = one_way_anova(list(groups.values()), list(groups), alpha=alpha)
    ss_between = anova["MSB"] * anova["df B"]
    ss_within = anova["MSW"] * anova["df W"]
    result["one_way_anova"] = {
        "Between SS": (ss_between, "one_way_ANOVA.one_way_anova：组间均方 × 自由度"),
        "Between df": (anova["df B"], "one_way_ANOVA.one_way_anova：组间自由度"),
        "Between MS": (anova["MSB"], "one_way_ANOVA.one_way_anova：组间均方"),
        "F": (anova["F"], "one_way_ANOVA.one_way_anova：F 值"),
        "p": (anova["p"], "one_way_ANOVA.one_way_anova：F 分布上尾 p 值"),
        "Error SS": (ss_within, "one_way_ANOVA.one_way_anova：误差均方 × 自由度"),
        "Error df": (anova["df W"], "one_way_ANOVA.one_way_anova：误差自由度"),
        "Error MS": (anova["MSW"], "one_way_ANOVA.one_way_anova：误差均方"),
        "Total SS": (ss_between + ss_within, "one_way_ANOVA.one_way_anova：组间平方和 + 误差平方和"),
        "Total df": (anova["df TTL"], "one_way_ANOVA.one_way_anova：总自由度"),
    }

    reg_case = cases["ols_linear"]
    linear = linear_fit(reg_case["x"], reg_case["y"], print_out=False)
    result["ols_linear"] = {
        "Intercept coefficient": (linear["intercept"], "linear_fit.linear_fit：截距"),
        "Intercept SE": (linear["Std Error Int."], "linear_fit.linear_fit：截距标准误"),
        "Intercept t": (linear["t int."], "linear_fit.linear_fit：截距 t 绝对值"),
        "Intercept p": (linear["p int."], "linear_fit.linear_fit：截距双侧 p 值"),
        "X coefficient": (linear["slope"], "linear_fit.linear_fit：斜率"),
        "X SE": (linear["Std Error Slope"], "linear_fit.linear_fit：斜率标准误"),
        "X t": (linear["t slope"], "linear_fit.linear_fit：斜率 t 绝对值"),
        "X p": (linear["p slope"], "linear_fit.linear_fit：斜率双侧 p 值"),
        "R2": (linear["R Square"], "linear_fit.linear_fit：R²"),
        "Residual standard deviation": (linear["Root MSE"], "linear_fit.linear_fit：残差标准差"),
    }
    return result


def write_session_commands() -> None:
    lines = ["本机 Minitab 19.1.0.1 的实际 Session 命令；由 verify_statistics_minitab19.py 生成", ""]
    for case_id, command in (*COMMANDS.items(), *AUXILIARY_COMMANDS.items()):
        lines.extend((f"===== {case_id} =====", command, ""))
    (OUT / "minitab_session_commands.txt").write_text("\n".join(lines), encoding="utf-8")


def write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def column_values(worksheet, index: int) -> list:
    values = worksheet.Columns.Item(index).GetData()
    if values is None:
        return []
    if isinstance(values, (tuple, list)):
        return list(values)
    return [values]


def first_column_value(worksheet, index: int) -> float:
    values = column_values(worksheet, index)
    if not values:
        raise ValueError(f"Minitab 存储列 C{index} 没有返回值")
    value = float(values[0])
    if not math.isfinite(value):
        raise ValueError(f"Minitab 存储列 C{index} 的首个值无效: {value}")
    return value


def read_matrix(worksheet, name: str, rows: int, cols: int) -> list[list[float]]:
    matrices = worksheet.Matrices
    matrix = next((matrices.Item(i) for i in range(1, int(matrices.Count) + 1)
                   if str(matrices.Item(i).Name).casefold() == name.casefold()), None)
    if matrix is None or int(matrix.RowCount) != rows or int(matrix.ColumnCount) != cols:
        raise ValueError(f"Minitab {name} 矩阵不存在或维度错误；预期 {rows}x{cols}")
    flat = [float(value) for value in matrix.GetData()]
    if len(flat) != rows * cols:
        raise ValueError(f"Minitab {name} 矩阵数据长度错误")
    return [[flat[c * rows + r] for c in range(cols)] for r in range(rows)]


def com_worker() -> int:
    import pythoncom
    import win32process
    import win32com.client

    app = project = ui = worksheet = columns = None
    outputs = {}
    result_path = OUT / "minitab_results.json"
    raw_path = OUT / "minitab_raw_outputs.txt"
    raw = []
    try:
        if not MTB_EXE.is_file():
            raise FileNotFoundError(f"Minitab 19 不存在: {MTB_EXE}")
        pids_before = running_minitab_pids()
        if pids_before:
            raise RuntimeError(f"启动前检测到 Mtb.exe PID {pids_before}；为保护现有会话，本脚本拒绝连接或运行")
        clsid, server_path, server_command = com_check.registered_server()
        if com_check.canonical(server_path) != com_check.canonical(MTB_EXE):
            raise RuntimeError(f"Mtb.Application 注册路径不符: {server_command}")
        version = com_check.file_version(MTB_EXE)
        if version != "19.1.0.1":
            raise RuntimeError(f"目标版本必须为 Minitab 19.1.0.1，实际为 {version}")

        app = win32com.client.DispatchEx("Mtb.Application")
        pythoncom.PumpWaitingMessages()
        ui = app.UserInterface
        ui.Visible = False
        ui.UserControl = False
        ui.DisplayAlerts = False
        app_path = str(app.AppPath)
        hwnd = int(app.Handle)
        process_id, process_path = com_check.process_image_path(hwnd)
        if (com_check.canonical(app_path) != com_check.canonical(MTB_EXE)
                or com_check.canonical(process_path) != com_check.canonical(MTB_EXE)):
            raise RuntimeError(f"COM 实例路径不符: AppPath={app_path}; process={process_path}")
        pids_after = running_minitab_pids()
        if process_id in pids_before or process_id not in pids_after:
            raise RuntimeError(f"DispatchEx 的 COM PID 未确认为新启动的 Minitab 进程：handle={process_id}, before={pids_before}, after={pids_after}")

        app.New()
        project = app.ActiveProject
        if project is None:
            raise RuntimeError("Minitab 没有返回独立 ActiveProject")
        worksheet = project.ActiveWorksheet
        columns = worksheet.Columns
        _, cases = read_cases()
        input_data = {
            1: ("Desc", cases["descriptive"]["values"]),
            2: ("Normality", cases["normality"]["values"]),
            3: ("CorrX", cases["pearson"]["x"]),
            4: ("CorrY", cases["pearson"]["y"]),
            5: ("OneT", cases["one_sample_t"]["values"]),
            6: ("Sample1", cases["two_sample_t"]["sample1"]),
            7: ("Sample2", cases["two_sample_t"]["sample2"]),
            8: ("Before", cases["paired_t"]["sample1"]),
            9: ("After", cases["paired_t"]["sample2"]),
            10: ("AnovaY", [v for values in cases["one_way_anova"]["groups"].values() for v in values]),
            11: ("Group", [name for name, values in cases["one_way_anova"]["groups"].items() for _ in values]),
            12: ("RegY", cases["ols_linear"]["y"]),
            13: ("RegX", cases["ols_linear"]["x"]),
        }
        loaded_inputs = {}
        for index in range(1, 44):
            name, values = input_data[index] if index in input_data else (f"Parity{index}", None)
            column = columns.Add(None, None, 1)
            column.Name = name
            if values is not None:
                column.SetData(tuple(values), 1, len(values))
            if int(columns.Count) != index or str(columns.Item(index).Name) != name:
                raise RuntimeError(f"创建/命名 Minitab C{index} 失败")
            if values is not None:
                loaded = tuple(column.GetData())
                loaded_inputs[str(index)] = {"name": name, "values": list(loaded)}
                if len(loaded) != len(values):
                    raise AssertionError(f"C{index} 输入行数回读不同")
                if all(isinstance(value, str) for value in values):
                    if tuple(str(v) for v in loaded) != tuple(values):
                        raise AssertionError(f"C{index} 文本输入回读不同")
                elif any(float(a) != float(b) for a, b in zip(loaded, values)):
                    raise AssertionError(f"C{index} 数值输入回读不同")

        for case_id, command_text in (*COMMANDS.items(), *AUXILIARY_COMMANDS.items()):
            before = int(project.Commands.Count)
            try:
                project.ExecuteCommand(command_text)
                after = int(project.Commands.Count)
                output = capture_command_output(project, after) if after > before else ""
                error = str(app.LastError or "")
                outputs[case_id] = {"executed": after > before and not error.strip(), "output": output, "last_error": error}
                raw.append(
                    f"===== {case_id} — 实际 Session 命令 =====\n{command_text}\n"
                    f"===== OutputDocument.Text / Output.Text 原始结果 =====\n{output or '(empty)'}\n"
                    f"===== COM 执行状态 =====\nCommands.Count: {before} -> {after}\nLastError: {error or '(empty)'}\n"
                )
            except Exception as exc:
                outputs[case_id] = {"executed": False, "output": "", "error": f"{type(exc).__name__}: {exc}"}
                raw.append(f"===== {case_id} 执行错误 =====\n{command_text}\n{traceback.format_exc()}\n")

        direct = {}
        try:
            direct["descriptive"] = {key: first_column_value(worksheet, column)
                                     for key, column in (("N", 20), ("Mean", 21), ("StDev", 22))}
        except Exception as exc:
            direct["descriptive_error"] = f"{type(exc).__name__}: {exc}"
        for case_id, pcol, lowcol, highcol in (
            ("normality", 25, None, None), ("one_sample_t", 26, 27, 28),
            ("two_sample_t", 29, 30, 31), ("paired_t", 32, 33, 34),
        ):
            try:
                direct[case_id] = {"p": first_column_value(worksheet, pcol)}
                if lowcol is not None:
                    direct[case_id]["CI lower"] = first_column_value(worksheet, lowcol)
                    direct[case_id]["CI upper"] = first_column_value(worksheet, highcol)
            except Exception as exc:
                direct[case_id + "_error"] = f"{type(exc).__name__}: {exc}"
        try:
            corr = read_matrix(worksheet, "M1", 2, 2)
            pmat = read_matrix(worksheet, "M2", 2, 2)
            direct["pearson"] = {"r": corr[0][1], "p": pmat[0][1]}
        except Exception as exc:
            direct["pearson_error"] = f"{type(exc).__name__}: {exc}"
        try:
            direct["ols_linear"] = {
                "coefficients": [float(value) for value in column_values(worksheet, 40)],
                "p_values": [float(value) for value in column_values(worksheet, 41)],
                "residual_standard_deviation": first_column_value(worksheet, 42),
                "r2": first_column_value(worksheet, 43),
                "xpx_inverse": read_matrix(worksheet, "M3", 2, 2),
            }
        except Exception as exc:
            direct["ols_linear_error"] = f"{type(exc).__name__}: {exc}"

        result = {
            "version": version, "clsid": clsid, "registered_server": server_command,
            "app_path": app_path, "process_path": process_path, "process_id": process_id,
            "project_name": str(project.Name), "worksheet_name": str(worksheet.Name),
            "python": sys.executable, "input_columns": loaded_inputs,
            "outputs": outputs, "direct_results": direct,
        }
        write_json(result_path, result)
        raw_path.write_text("\n".join(raw), encoding="utf-8")
        print(f"Minitab COM {version}；程序路径和进程映像已核对；独立项目={project.Name!r}；"
              f"commands={sum(v['executed'] for v in outputs.values())}/{len(outputs)}")
        return 0
    except Exception:
        raw_path.write_text("\n".join(raw + [traceback.format_exc()]), encoding="utf-8")
        write_json(OUT / "minitab_com_error.json", {"error": traceback.format_exc(), "python": sys.executable})
        traceback.print_exc()
        return 1
    finally:
        columns = worksheet = project = app = ui = None


NUMBER_RE = re.compile(r"(?<![\w.])[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[Ee][-+]?\d+)?")


def _table_cells(line: str) -> list[str]:
    return [cell.strip() for cell in re.split(r"(?:\s{2,}|\t+)", line.strip()) if cell.strip()]


def _header_key(value: str) -> str:
    return re.sub(r"[^a-z0-9\u4e00-\u9fff%]", "", value.casefold())


def displayed_cell(raw: str, row_aliases: tuple[str, ...], column_aliases: tuple[str, ...]) -> tuple[float, str]:
    lines = raw.replace("\r", "\n").replace("\xa0", " ").splitlines()
    wanted = {_header_key(alias) for alias in column_aliases}
    for header_index, header in enumerate(lines):
        cells = _table_cells(header)
        column = next((i for i, cell in enumerate(cells) if _header_key(cell) in wanted), None)
        if column is None:
            continue
        for row in lines[header_index + 1:header_index + 10]:
            row_cells = _table_cells(row)
            if column >= len(row_cells):
                continue
            if row_aliases and not any(alias.casefold() in row.casefold() for alias in row_aliases):
                continue
            match = NUMBER_RE.search(row_cells[column])
            if match:
                return float(match.group()), match.group()
    raise ValueError(f"不能按字段/行标签定位显示值：列={column_aliases}，行={row_aliases}")


def display_tolerance(token: str) -> float:
    mantissa, _, exponent = token.lower().partition("e")
    decimals = len(mantissa.partition(".")[2])
    power = int(exponent) if exponent else 0
    return 0.5 * 10.0 ** (power - decimals)


def one_display(raw: str, rows: tuple[str, ...], columns: tuple[str, ...]) -> tuple[float, str, float]:
    value, token = displayed_cell(raw, rows, columns)
    return value, token, display_tolerance(token)


def minitab_metrics(result: dict, cases: dict) -> tuple[dict, dict]:
    direct = result.get("direct_results", {})
    outputs = result.get("outputs", {})
    values, errors = {}, {}

    def output(case_id: str) -> str:
        state = outputs.get(case_id, {})
        if not state.get("executed"):
            raise ValueError(state.get("error") or state.get("last_error") or f"{case_id} 命令未执行")
        return state.get("output", "")

    def store(case_id: str, key: str, source: str, tolerance: float = DIRECT_TOL) -> None:
        state = outputs.get(case_id, {})
        if not state.get("executed"):
            raise ValueError(state.get("error") or state.get("last_error") or f"{case_id} 命令未成功执行")
        if case_id not in direct or key not in direct[case_id]:
            raise ValueError(direct.get(case_id + "_error", f"Minitab 未返回 {case_id}/{key}"))
        values.setdefault(case_id, {})[key] = (float(direct[case_id][key]), source, tolerance)

    for key, column in zip(("N", "Mean", "StDev"), range(20, 23)):
        try:
            store("descriptive", key, f"Minitab COM 命令 STATS C1；从 C{column} 直接读取")
        except Exception as exc:
            errors.setdefault("descriptive", str(exc))

    try:
        describe_output = output("descriptive_display")
        for key, aliases in (("Minimum", ("Minimum", "最小值")), ("Maximum", ("Maximum", "最大值"))):
            value, token = displayed_cell(describe_output, ("Desc",), aliases)
            values.setdefault("descriptive", {})[key] = (
                value, f"Minitab COM 命令 DESCRIBE C1；Desc 行、{aliases[0]} 列；显示值 {token}", display_tolerance(token))
    except Exception as exc:
        errors["descriptive::Minimum"] = f"{type(exc).__name__}: {exc}"
        errors["descriptive::Maximum"] = f"{type(exc).__name__}: {exc}"

    try:
        normal_output = output("normality")
        try:
            ad, token = displayed_cell(normal_output, ("Anderson-Darling", "Anderson", "AD"), ("AD",))
            values.setdefault("normality", {})["AD"] = (ad, f"Minitab COM 命令 NORMTEST C2；OutputDocument Anderson-Darling 显示值 {token}", display_tolerance(token))
        except ValueError:
            errors["normality::AD"] = "UNSUPPORTED: NORMTEST COM exposes only the graph title; Minitab 19 documents no AD-statistic storage column."
    except Exception as exc:
        errors["normality::AD"] = f"{type(exc).__name__}: {exc}"
    try:
        store("normality", "p", "Minitab COM 命令 NORMTEST C2；SPVALUE C25 存储值精确到 0.001", 0.0005)
    except Exception as exc:
        errors["normality::p"] = f"{type(exc).__name__}: {exc}"

    for key, storage in (("r", "SCORRELATION M1"), ("p", "SPVALUES M2")):
        try:
            store("pearson", key, f"Minitab COM 命令 CORRELATION C3 C4；PEARSON；{storage} 直接存储")
        except Exception as exc:
            errors.setdefault("pearson", f"{type(exc).__name__}: {exc}")

    try:
        n = len(cases["one_sample_t"]["values"])
        mean = sum(cases["one_sample_t"]["values"]) / n
        stdev = math.sqrt(sum((v - mean) ** 2 for v in cases["one_sample_t"]["values"]) / (n - 1))
        t_value = (mean - float(cases["one_sample_t"]["mu0"])) / (stdev / math.sqrt(n))
        try:
            shown, token = displayed_cell(output("one_sample_t"), (), ("T 值", "T-Value", "T Value"))
            t_value, t_source, t_tolerance = shown, f"Minitab COM 命令 ONET；OutputDocument T 值 {token}", display_tolerance(token)
        except ValueError:
            t_source, t_tolerance = "由 Minitab 输入 C5 推导：样本均值、标准差和 TEST 10", DIRECT_TOL
        values["one_sample_t"] = {
            "t": (t_value, t_source, t_tolerance),
            "df": (float(n - 1), "按 Minitab ONET 定义推导：df=N−1；N 来自固定输入", 1e-12),
        }
        for key in ("p", "CI lower", "CI upper"):
            store("one_sample_t", key, f"Minitab COM 命令 ONET C5；SPVALUE/SCONF 直接存储 {key}")
    except Exception as exc:
        errors["one_sample_t"] = f"{type(exc).__name__}: {exc}"

    try:
        two = direct["two_sample_t"]
        two_output = output("two_sample_t")
        one, two_case = cases["two_sample_t"]["sample1"], cases["two_sample_t"]["sample2"]
        mean1, mean2 = sum(one) / len(one), sum(two_case) / len(two_case)
        var1 = sum((v - mean1) ** 2 for v in one) / (len(one) - 1)
        var2 = sum((v - mean2) ** 2 for v in two_case) / (len(two_case) - 1)
        se = math.sqrt(var1 / len(one) + var2 / len(two_case))
        df = (var1 / len(one) + var2 / len(two_case)) ** 2 / (
            (var1 / len(one)) ** 2 / (len(one) - 1) + (var2 / len(two_case)) ** 2 / (len(two_case) - 1))
        low, high = float(two["CI lower"]), float(two["CI upper"])
        try:
            shown_t, shown_t_token = displayed_cell(two_output, (), ("T 值", "T-Value", "T Value"))
            t_value, t_source, t_tol = shown_t, f"Minitab COM 命令 TWOSAMPLE；OutputDocument T 值 {shown_t_token}", display_tolerance(shown_t_token)
        except ValueError:
            t_value, t_source, t_tol = (mean2 - mean1) / se, "由 Minitab 输入 C7、C6 推导：Welch 均值差 / 标准误", DIRECT_TOL
        try:
            shown_df, shown_df_token = displayed_cell(two_output, (), ("自由度", "DF"))
            df, df_source, df_tol = shown_df, f"Minitab COM 命令 TWOSAMPLE；OutputDocument 自由度 {shown_df_token}", display_tolerance(shown_df_token)
        except ValueError:
            df_source, df_tol = "由 Minitab 输入 C7、C6 推导：Welch-Satterthwaite 自由度", DIRECT_TOL
        values["two_sample_t"] = {
            "Mean difference (mu2-mu1)": ((low + high) / 2, "由 Minitab SCONF C30、C31 区间中点推导；C7、C6 顺序对应 mu2−mu1", DIRECT_TOL),
            "SE difference": (se, "由 Minitab 输入 C7、C6 按 Welch 公式推导；SPVALUE/SCONF 为直接存储", DIRECT_TOL),
            "t": (t_value, t_source, t_tol),
            "df": (df, df_source, df_tol),
        }
        store("two_sample_t", "p", "Minitab COM 命令 TWOSAMPLE 95 C7 C6；省略 POOLED；SPVALUE C29 直接存储")
    except Exception as exc:
        errors["two_sample_t"] = f"{type(exc).__name__}: {exc}"

    try:
        pair = direct["paired_t"]
        pair_output = output("paired_t")
        sample1, sample2 = cases["paired_t"]["sample1"], cases["paired_t"]["sample2"]
        diffs = [a - b for a, b in zip(sample1, sample2)]
        n = len(diffs)
        mean = sum(diffs) / n
        stdev = math.sqrt(sum((v - mean) ** 2 for v in diffs) / (n - 1))
        t_value = mean / (stdev / math.sqrt(n))
        t_source, t_tol = "由 Minitab 输入 C8、C9 按配对差值公式推导", DIRECT_TOL
        try:
            shown_t, shown_t_token = displayed_cell(pair_output, (), ("T 值", "T-Value", "T Value"))
            t_value, t_source, t_tol = shown_t, f"Minitab COM 命令 PAIR；OutputDocument T 值 {shown_t_token}", display_tolerance(shown_t_token)
        except ValueError:
            pass
        values["paired_t"] = {
            "Mean difference (sample1-sample2)": ((float(pair["CI lower"]) + float(pair["CI upper"])) / 2,
                                                   "由 Minitab PAIR 的 SCONF C33、C34 区间中点推导", DIRECT_TOL),
            "t": (t_value, t_source, t_tol),
            "df": (float(n - 1), "按 Minitab PAIR 定义推导：df=N−1；N 来自固定输入", 1e-12),
        }
        store("paired_t", "p", "Minitab COM 命令 PAIR C8 C9；SPVALUE C32 直接存储")
    except Exception as exc:
        errors["paired_t"] = f"{type(exc).__name__}: {exc}"

    try:
        anova_output = output("one_way_anova")
        table_fields = {
            "Between SS": (("Group", "Factor", "组别", "因子"), ("Adj SS", "Adjusted SS", "平方和", "调整平方和")),
            "Between df": (("Group", "Factor", "组别", "因子"), ("DF", "自由度")),
            "Between MS": (("Group", "Factor", "组别", "因子"), ("Adj MS", "Adjusted MS", "均方", "调整均方")),
            "F": (("Group", "Factor", "组别", "因子"), ("F-Value", "F Value", "F-值", "F 值", "F值")),
            "p": (("Group", "Factor", "组别", "因子"), ("P-Value", "P Value", "P-值", "P 值", "P值")),
            "Error SS": (("Error", "误差"), ("Adj SS", "Adjusted SS", "平方和", "调整平方和")),
            "Error df": (("Error", "误差"), ("DF", "自由度")),
            "Error MS": (("Error", "误差"), ("Adj MS", "Adjusted MS", "均方", "调整均方")),
            "Total SS": (("Total", "合计", "总计"), ("Adj SS", "Adjusted SS", "平方和", "调整平方和")),
            "Total df": (("Total", "合计", "总计"), ("DF", "自由度")),
        }
        for key, (row_aliases, col_aliases) in table_fields.items():
            value, token = displayed_cell(anova_output, row_aliases, col_aliases)
            values.setdefault("one_way_anova", {})[key] = (value, f"Minitab COM 命令 ONEWAY TANOVA；{row_aliases[0]} 行、{col_aliases[0]} 列；显示值 {token}", display_tolerance(token))
    except Exception as exc:
        errors["one_way_anova"] = f"{type(exc).__name__}: {exc}"

    try:
        output("ols_linear")
        reg = direct["ols_linear"]
        coefs = reg["coefficients"]
        inv = reg["xpx_inverse"]
        sigma = float(reg["residual_standard_deviation"])
        r2 = float(reg["r2"])
        if len(coefs) != 2 or len(inv) != 2 or any(len(row) != 2 for row in inv):
            raise ValueError("Minitab REGRESS 未回读两个系数和 2x2 XPXINV")
        reg_df = len(cases["ols_linear"]["x"]) - 2
        se = [math.sqrt(max(0.0, inv[i][i]) * sigma * sigma) for i in range(2)]
        from scipy.stats import t as t_distribution
        for index, label in enumerate(("Intercept", "X")):
            t_value = abs(coefs[index] / se[index])
            p_values = reg.get("p_values", [])
            stored_p_index = index if len(p_values) == 2 else (0 if index == 1 and len(p_values) == 1 else None)
            p_value = float(p_values[stored_p_index]) if stored_p_index is not None else float(2 * t_distribution.sf(t_value, reg_df))
            values.setdefault("ols_linear", {})[f"{label} coefficient"] = (coefs[index], f"Minitab COM 命令 REGRESS；COEFFICIENTS C40 第 {index + 1} 行直接存储", DIRECT_TOL)
            values["ols_linear"][f"{label} SE"] = (se[index], "由 Minitab XPXINV M3 对角元和 SS C42² 推导", DIRECT_TOL)
            values["ols_linear"][f"{label} t"] = (t_value, f"由 Minitab 系数 / 标准误推导；df=N−2={reg_df}", DIRECT_TOL)
            p_source = "Minitab COM 命令 REGRESS；SPVALUE C41 直接存储" if stored_p_index is not None else "由 Minitab 系数、XPXINV、SS 按双侧 Student t 尾概率推导"
            values["ols_linear"][f"{label} p"] = (p_value, p_source, DIRECT_TOL)
        values.setdefault("ols_linear", {})["R2"] = (r2, "Minitab COM 命令 REGRESS；SRSQ C43 直接存储", DIRECT_TOL)
        values["ols_linear"]["Residual standard deviation"] = (sigma, "Minitab COM 命令 REGRESS；SS C42 直接存储", DIRECT_TOL)
    except Exception as exc:
        errors["ols_linear"] = f"{type(exc).__name__}: {exc}"

    return values, errors


def compare(minijmp: dict, minitab: dict, cases: dict) -> list[dict]:
    comparisons = []
    for case_id, local_metrics in minijmp.items():
        mtb_metrics = minitab.get(case_id, {})
        definition = {
            "normality": "Anderson-Darling 正态性检验；显著性水平 0.05；比较双侧 p 值",
            "pearson": "Pearson 积差相关；H0: rho=0；显著性水平 0.05；按成对完整观测计算",
            "one_sample_t": "单样本双侧 t 检验；H0: mu=mu0；显著性水平 0.05；95% 置信区间",
            "two_sample_t": "独立样本 Welch t 检验；H0: mu2−mu1=0；显著性水平 0.05；95% 区间；Minitab 命令顺序 C7、C6",
            "paired_t": "配对双侧 t 检验；差值 sample1−sample2；H0: 平均差=0；显著性水平 0.05；95% 区间",
            "one_way_anova": "传统等方差单因子 ANOVA；显著性水平 0.05；三组输入一致",
            "ols_linear": "含截距、一个未标准化连续 X 的 OLS；显著性水平 0.05；无缺失行",
        }.get(case_id, "无缺失值；MiniJMP 与 Minitab 使用 case_inputs.json 中的相同固定观测")
        for metric, (local_value, local_source) in local_metrics.items():
            if metric not in mtb_metrics:
                note = minitab.get(f"{case_id}::{metric}", minitab.get(f"{case_id}_error", "Minitab 未返回该字段"))
                comparisons.append({
                    "case_id": case_id, "功能名称": cases[case_id]["feature"], "输入案例": f"case_inputs.json#cases.{case_id}", "统计量": metric,
                    "Minitab值": "", "MiniJMP值": local_value, "绝对误差": "",
                    "绝对容差": "", "相对容差": "", "结果": "UNSUPPORTED" if str(note).startswith("UNSUPPORTED:") else "NOT_RUN",
                    "Minitab结果来源": "", "MiniJMP结果来源": local_source,
                    "统计定义/选项": definition, "备注": note,
                })
                continue
            mtb_value, mtb_source, abs_tol = mtb_metrics[metric]
            rel_tol = 0.0 if "display" in mtb_source else DIRECT_TOL
            error = abs(float(mtb_value) - float(local_value))
            allowed = abs_tol + rel_tol * max(abs(float(mtb_value)), abs(float(local_value)))
            method_note = ""
            local_df = float(local_metrics["df"][0]) if case_id == "two_sample_t" else math.nan
            mtb_df = float(mtb_metrics["df"][0]) if case_id == "two_sample_t" and "df" in mtb_metrics else math.nan
            truncated_df = math.trunc(local_df) if math.isfinite(local_df) else math.nan
            is_truncated_welch = (case_id == "two_sample_t" and math.isfinite(mtb_df)
                                  and mtb_df == truncated_df and mtb_df != local_df)
            welch_method_diff = False
            if is_truncated_welch and all(key in local_metrics and key in mtb_metrics for key in ("t", "p")):
                from scipy.stats import t as t_distribution
                local_t = float(local_metrics["t"][0])
                mtb_t, _, mtb_t_tol = mtb_metrics["t"]
                t_allowed = mtb_t_tol + DIRECT_TOL * max(abs(float(mtb_t)), abs(local_t))
                expected_p = 2 * t_distribution.sf(abs(local_t), mtb_df)
                mtb_p = float(mtb_metrics["p"][0])
                local_p = float(local_metrics["p"][0])
                p_allowed = mtb_metrics["p"][2] + DIRECT_TOL * max(abs(mtb_p), abs(local_p))
                expected_p_tol = DIRECT_TOL + DIRECT_TOL * max(abs(expected_p), abs(mtb_p))
                welch_method_diff = (abs(float(mtb_t) - local_t) <= t_allowed
                                     and abs(mtb_p - expected_p) <= expected_p_tol
                                     and abs(mtb_p - local_p) > p_allowed)
            if case_id == "two_sample_t" and metric == "df" and welch_method_diff:
                status = "METHOD_DIFF"
                method_note = "Minitab 19 将 Welch-Satterthwaite 自由度截为整数；MiniJMP 保留小数自由度。"
            elif case_id == "two_sample_t" and metric == "p" and welch_method_diff:
                status = "METHOD_DIFF"
                method_note = "Minitab p 值吻合整数截断后的自由度；MiniJMP 用小数自由度，故 p 值不同。"
            else:
                status = "PASS" if error <= allowed else "FAIL"
            comparisons.append({
                "case_id": case_id, "功能名称": cases[case_id]["feature"], "输入案例": f"case_inputs.json#cases.{case_id}", "统计量": metric,
                "Minitab值": format(float(mtb_value), ".17g"), "MiniJMP值": format(float(local_value), ".17g"),
                "绝对误差": format(error, ".17g"), "绝对容差": format(abs_tol, ".17g"),
                "相对容差": format(rel_tol, ".17g"), "结果": status,
                "Minitab结果来源": mtb_source, "MiniJMP结果来源": local_source,
                "统计定义/选项": definition, "备注": method_note,
            })
    return comparisons


def feature_summary(comparisons: list[dict]) -> list[dict]:
    grouped = {}
    for row in comparisons:
        grouped.setdefault(row["case_id"], []).append(row)
    summary = []
    for case_id, rows in grouped.items():
        counts = Counter(row["结果"] for row in rows)
        status = next((name for name in ("FAIL", "METHOD_DIFF", "UNSUPPORTED", "NOT_RUN") if counts[name]), "PASS")
        notes = "; ".join(sorted({row["备注"] for row in rows if row["备注"]}))
        summary.append({
            "case_id": case_id, "功能名称": rows[0]["功能名称"], "比较指标数": len(rows),
            **{name: counts[name] for name in STATUS_ORDER}, "功能状态": status, "备注": notes,
        })
    return summary


def menu_dict(tree: ast.Module, name: str) -> ast.Dict:
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        target_match = any(isinstance(t, ast.Attribute) and t.attr == name for t in node.targets)
        if not target_match:
            continue
        if isinstance(node.value, ast.Dict):
            return node.value
        if isinstance(node.value, ast.Call):
            found = next((arg for arg in node.value.args if isinstance(arg, ast.Dict)), None)
            if found:
                return found
    raise ValueError(f"不能从 code/MiniJMP.py 解析 {name}")


def ast_dict_entries(node: ast.Dict):
    for key, value in zip(node.keys, node.values):
        if isinstance(key, ast.Constant) and isinstance(key.value, str):
            yield key.value, value, key.lineno


def called_names(node: ast.AST) -> list[str]:
    return list(dict.fromkeys(child.id for child in ast.walk(node) if isinstance(child, ast.Name)))


def build_feature_matrix(summary: list[dict]) -> list[dict]:
    tree = ast.parse((CODE / "MiniJMP.py").read_text(encoding="utf-8"))
    case_status = {row["case_id"]: row["功能状态"] for row in summary}
    parity_case = {
        "01描述性统计": "descriptive", "04正态性检验": "normality", "13相关分析": "pearson",
        "14线性回归": "ols_linear", "25单样本均值 t 检验": "one_sample_t",
        "29双样本 t 检验": "two_sample_t", "30配对 t 检验": "paired_t",
        "34单因子方差分析": "one_way_anova",
    }
    rows = []
    menus = (("统计", "stats_menu", "direct"), ("质量", "quality_menu", "direct"),
             ("DOE（统计子菜单）", "doe_menu", "doe"))
    for category, name, kind in menus:
        mapping = menu_dict(tree, name)
        for raw_label, descriptor, item_line in ast_dict_entries(mapping):
            if raw_label.casefold().endswith("sep"):
                continue
            entry = descriptor
            if isinstance(descriptor, ast.Dict):
                entry = next((value for key, value, _ in ast_dict_entries(descriptor) if key == "cmd"), descriptor)
            entry_text = ast.unparse(entry)
            info = FEATURE_INFO.get(raw_label)
            historical = DOE_EVIDENCE.get(raw_label, "") if kind == "doe" else ""
            if info:
                production, tests, independent, numeric_reference, note, priority = info
                status = "待验证"
                case_id = parity_case.get(raw_label)
                if case_id and case_id in case_status:
                    status = "已验证" if case_status[case_id] == "PASS" else (
                        "方法不同" if case_status[case_id] == "METHOD_DIFF" else "待验证")
                sources = f"code/MiniJMP.py:{item_line}; {tests}; docs/usage/、docs/advanced-statistics.md"
            elif kind == "doe":
                calls = [call for call in called_names(entry) if call in DOE_CALLS]
                production = "; ".join(DOE_CALLS[call] for call in calls) or f"code/MiniJMP.py: {entry_text}"
                tests = "tests/test_menu_localization.py; tests/test_doe_*.py"
                independent = "部分" if historical else "未找到"
                numeric_reference = "部分" if historical else "否"
                note = "DOE 子项由 docs/doe-minitab/feature-matrix.csv 跟踪；" + (
                    f"历史固定案例证据：{historical}；仅覆盖其已执行的设计/模型/数据范围，未在本轮重跑。"
                    if historical else "未定位到与此具体菜单项一一对应的 Minitab 19 数值结果；既有 DOE 总体材料不推定为本项验收。"
                )
                priority = "P1" if historical else "P2"
                status = "待验证"
                sources = f"code/MiniJMP.py:{item_line}; docs/doe-minitab/feature-matrix.csv; {tests}; {historical or 'Out/minitab19_parity/'}"
            else:
                raise ValueError(f"菜单项缺少矩阵元数据: {raw_label}")
            feature = re.sub(r"^\d+", "", raw_label)
            rows.append({
                "类别": category, "功能名称": feature, "MiniJMP菜单功能": raw_label,
                "实现入口": f"code/MiniJMP.py:{item_line} `{entry_text}`",
                "生产模块及调用方法": production,
                "已有测试": "是" if tests else "否", "对应测试文件": tests,
                "独立验证": independent, "是否已有独立数值参考": numeric_reference,
                "Minitab 19 对标": status, "优先级": priority,
                "备注及证据来源": f"{note} | {sources}",
            })
    write_csv(OUT / "feature_matrix.csv", MATRIX_FIELDS, rows)
    return rows


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    for stale in (OUT / "execution_error.txt", OUT / "minitab_com_error.json"):
        stale.unlink(missing_ok=True)
    if com_check.canonical(sys.executable) != com_check.canonical(PROJECT_PYTHON):
        raise RuntimeError(f"请使用项目解释器运行：{PROJECT_PYTHON}")
    options, cases = read_cases()
    write_session_commands()
    local = production_results(options, cases)
    write_json(OUT / "minijmp_results.json", {
        "python": sys.executable, "options": options, "case_inputs": cases,
        "results": {case: {key: {"value": value, "source": source}
                           for key, (value, source) in metrics.items()} for case, metrics in local.items()},
    })

    minitab = {}
    try:
        if running_minitab_pids():
            raise RuntimeError("启动前检测到 Mtb.exe；未连接已有 Minitab 会话")
        child = None
        worker_error = None
        try:
            child = subprocess.run(
                [str(PROJECT_PYTHON), "-X", "utf8", str(Path(__file__).resolve()), "--com-worker"],
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=240,
            )
        except Exception as exc:
            worker_error = exc
        for _ in range(40):
            if not running_minitab_pids():
                break
            time.sleep(0.5)
        remaining = running_minitab_pids()
        if child is not None:
            (OUT / "com_worker.log").write_text(
                f"exit_code={child.returncode}\n--- stdout ---\n{child.stdout}\n--- stderr ---\n{child.stderr}", encoding="utf-8")
        if worker_error:
            raise RuntimeError(f"Minitab COM worker 执行失败：{worker_error}；剩余 Mtb.exe PID={remaining}") from worker_error
        if remaining:
            raise RuntimeError(f"COM worker 退出后仍有 Mtb.exe PID {remaining}; 未操作或终止这些进程")
        if child is None:
            raise RuntimeError("COM worker 没有返回进程结果")
        if child.returncode:
            raise RuntimeError(f"Minitab COM worker 退出码 {child.returncode}; 详见 com_worker.log")
        result = json.loads((OUT / "minitab_results.json").read_text(encoding="utf-8"))
        if result.get("version") != "19.1.0.1":
            raise RuntimeError(f"Minitab 版本不符: {result.get('version')}")
        if (com_check.canonical(result["app_path"]) != com_check.canonical(MTB_EXE)
                or com_check.canonical(result["process_path"]) != com_check.canonical(MTB_EXE)):
            raise RuntimeError("Minitab COM 的 AppPath 或进程映像与指定版本路径不符")
        minitab, parse_errors = minitab_metrics(result, cases)
        for case_id, error in parse_errors.items():
            minitab[case_id if "::" in case_id else case_id + "_error"] = error
        write_json(OUT / "minitab_metadata.json", {key: result[key] for key in
                    ("version", "clsid", "registered_server", "app_path", "process_path",
                     "process_id", "project_name", "worksheet_name", "python")})
    except Exception as exc:
        message = f"{type(exc).__name__}: {exc}"
        (OUT / "execution_error.txt").write_text(message + "\n\n" + traceback.format_exc(), encoding="utf-8")
        minitab = {case_id + "_error": message for case_id in COMMANDS}
        print(message, file=sys.stderr)

    comparisons = compare(local, minitab, cases)
    summary = feature_summary(comparisons)
    write_csv(OUT / "comparison.csv", COMPARISON_FIELDS, comparisons)
    write_csv(OUT / "summary.csv", SUMMARY_FIELDS, summary)
    matrix = build_feature_matrix(summary)
    counts = Counter(row["结果"] for row in comparisons)
    independent = Counter(row["是否已有独立数值参考"] for row in matrix)
    print(f"菜单功能 {len(matrix)} 项（统计/质量/DOE）；独立数值参考：有 {independent['是']}、部分 {independent['部分']}、未找到 {independent['否'] + independent['未找到']}。")
    print("本轮 Minitab 对标功能：{}；逐指标状态：{}".format(
        len(summary), ", ".join(f"{name}={counts[name]}" for name in STATUS_ORDER)))
    if any(row["结果"] in ("FAIL", "NOT_RUN") for row in comparisons):
        return 1
    return 0


if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1] == "--com-worker":
        raise SystemExit(com_worker())
    raise SystemExit(main())
