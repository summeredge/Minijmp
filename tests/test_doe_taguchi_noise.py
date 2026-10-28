"""噪声因子稳健性分析与最佳设置预测。"""
import math

import pytest

from doe_core import DesignSpec, FactorSpec, restore_design_result
from doe_taguchi import create_taguchi
from doe_taguchi_analysis import best_settings, noise_robustness
from doe_taguchi_arrays import ARRAYS


def factor(factor_id, levels):
    return FactorSpec(factor_id, factor_id, None, None, factor_type="categorical",
                      levels=tuple(levels), level_type="text")


def inner_outer_spec():
    """L4 控制 × L4 噪声，控制因子 A、B，噪声因子 N。"""
    return DesignSpec(
        "TG", (factor("A", ("低", "高")), factor("B", ("低", "高")),
               factor("N", ("n1", "n2"))), ("Y",), seed=9, design_type="taguchi",
        taguchi={"kind": "static", "array_id": "L4(2^3)",
                 "matrix_sha256": ARRAYS["L4(2^3)"].sha256,
                 "columns": {"A": 1, "B": 3},
                 "noise_array_id": "L4(2^3)",
                 "noise_matrix_sha256": ARRAYS["L4(2^3)"].sha256,
                 "noise_columns": {"N": 2}, "signal_factor": None})


def test_inner_outer_array_multiplies_runs_and_preserves_mapping():
    frame, metadata = create_taguchi(inner_outer_spec())
    design = restore_design_result(frame, metadata)
    assert len(design.runs) == 8
    assert {run.noise_condition_id for run in design.runs} == {"N1R1", "N2R1"}
    assert len({run.control_run_id for run in design.runs}) == 4


def test_noise_robustness_reports_sd_and_sn_per_control_setting():
    frame, metadata = create_taguchi(inner_outer_spec())
    design = restore_design_result(frame, metadata)
    values = {}
    for run in design.runs:
        spread = 4.0 if run.settings["A"] == "低" else 1.0
        base = 10.0 + (2.0 if run.settings["B"] == "高" else 0.0)
        values[run.run_id] = base + (spread if run.settings["N"] == "n2" else 0.0)
    frame["响应_Y"] = [values[run_id] for run_id in frame["运行ID"]]
    result = noise_robustness(frame, metadata, "Y", "smaller")
    rows = {(row["settings"]["A"], row["settings"]["B"]): row for row in result["rows"]}
    assert len(rows) == 4
    assert rows[("低", "低")]["sd"] > rows[("高", "低")]["sd"]
    assert rows[("低", "低")]["sn"] < rows[("高", "低")]["sn"]


def test_robustness_requires_noise_factors():
    spec = DesignSpec("TG", (factor("A", ("低", "高")), factor("B", ("低", "高"))),
                      ("Y",), seed=2, design_type="taguchi",
                      taguchi={"kind": "static", "array_id": "L4(2^3)",
                               "matrix_sha256": ARRAYS["L4(2^3)"].sha256,
                               "columns": {"A": 1, "B": 2},
                               "noise_array_id": None, "noise_matrix_sha256": None,
                               "noise_columns": {}, "signal_factor": None})
    frame, metadata = create_taguchi(spec, replicates=2)
    frame["响应_Y"] = 1.0
    with pytest.raises(ValueError, match="噪声因子"):
        noise_robustness(frame, metadata, "Y")


def test_best_settings_use_sn_and_never_write_back_to_design():
    spec = DesignSpec("TG", (factor("A", ("低", "高")), factor("B", ("低", "高"))),
                      ("Y",), seed=2, design_type="taguchi",
                      taguchi={"kind": "static", "array_id": "L4(2^3)",
                               "matrix_sha256": ARRAYS["L4(2^3)"].sha256,
                               "columns": {"A": 1, "B": 2},
                               "noise_array_id": None, "noise_matrix_sha256": None,
                               "noise_columns": {}, "signal_factor": None})
    frame, metadata = create_taguchi(spec, replicates=2)
    design = restore_design_result(frame, metadata)
    values = {run.run_id: (12.0 if run.settings["A"] == "高" else 4.0)
              + (0.2 if run.replicate == 1 else -0.2)
              + (1.0 if run.settings["B"] == "低" else 0.0)
              for run in design.runs}
    frame["响应_Y"] = [values[run_id] for run_id in frame["运行ID"]]
    before = frame.copy(deep=True)
    result = best_settings(frame, metadata, "Y", "sn")
    # smaller-is-better 的 S/N 偏好低响应，故最佳水平是"低"
    assert result["best"]["A"] == "低"
    assert frame.equals(before)
    assert result["metric"] == "sn"
    assert math.isfinite(result["predicted_mean"])
    assert result["confirmation"]["observed"] is None


def test_unobserved_best_setting_requires_confirmation():
    spec = DesignSpec("TG", (factor("A", ("低", "中", "高")),
                             factor("B", ("低", "中", "高")),
                             factor("C", ("低", "中", "高"))), ("Y",), seed=4,
                      design_type="taguchi",
                      taguchi={"kind": "static", "array_id": "L9(3^4)",
                               "matrix_sha256": ARRAYS["L9(3^4)"].sha256,
                               "columns": {"A": 1, "B": 2, "C": 3},
                               "noise_array_id": None, "noise_matrix_sha256": None,
                               "noise_columns": {}, "signal_factor": None})
    frame, metadata = create_taguchi(spec, replicates=2)
    design = restore_design_result(frame, metadata)
    values = {run.run_id: (10.0 if run.settings["A"] == "高" else 1.0)
              + (5.0 if run.settings["B"] == "低" else 0.0)
              + (0.2 if run.replicate == 1 else -0.2)
              for run in design.runs}
    frame["响应_Y"] = [values[run_id] for run_id in frame["运行ID"]]
    result = best_settings(frame, metadata, "Y")
    assert result["is_observed"] is False
    assert "确认试验" in result["status"]


def test_target_mean_metric_requires_explicit_target():
    spec = DesignSpec("TG", (factor("A", ("低", "高")), factor("B", ("低", "高"))),
                      ("Y",), seed=2, design_type="taguchi",
                      taguchi={"kind": "static", "array_id": "L4(2^3)",
                               "matrix_sha256": ARRAYS["L4(2^3)"].sha256,
                               "columns": {"A": 1, "B": 2},
                               "noise_array_id": None, "noise_matrix_sha256": None,
                               "noise_columns": {}, "signal_factor": None})
    frame, metadata = create_taguchi(spec, replicates=2)
    frame["响应_Y"] = 1.0
    with pytest.raises(ValueError, match="目标值"):
        best_settings(frame, metadata, "Y", "mean")


def l9_target_spec():
    spec = DesignSpec("TG", tuple(factor(chr(65 + index), ("低", "中", "高"))
                                  for index in range(3)), ("Y",), seed=6,
                      design_type="taguchi",
                      taguchi={"kind": "static", "array_id": "L9(3^4)",
                               "matrix_sha256": ARRAYS["L9(3^4)"].sha256,
                               "columns": {"A": 1, "B": 2, "C": 3},
                               "noise_array_id": None, "noise_matrix_sha256": None,
                               "noise_columns": {}, "signal_factor": None})
    frame, metadata = create_taguchi(spec, replicates=2)
    design = restore_design_result(frame, metadata)
    coded = {"低": -1, "中": 0, "高": 1}
    values = {run.run_id: 50 + 10 * coded[run.settings["A"]]
              + 4 * coded[run.settings["B"]]
              + (0.3 if run.replicate == 1 else -0.3)
              for run in design.runs}
    frame["响应_Y"] = [values[run_id] for run_id in frame["运行ID"]]
    return frame, metadata


def l4_target_spec():
    """独立反例：两因子边际均值均为 14/26，总均值为 20。"""
    spec = DesignSpec(
        "TG", (factor("A", ("低", "高")), factor("B", ("低", "高"))),
        ("Y",), seed=7, design_type="taguchi",
        taguchi={"kind": "static", "array_id": "L4(2^3)",
                 "matrix_sha256": ARRAYS["L4(2^3)"].sha256,
                 "columns": {"A": 1, "B": 2},
                 "noise_array_id": None, "noise_matrix_sha256": None,
                 "noise_columns": {}, "signal_factor": None})
    frame, metadata = create_taguchi(spec, replicates=2)
    design = restore_design_result(frame, metadata)
    values = {}
    for run in design.runs:
        a_effect = -6 if run.settings["A"] == "低" else 6
        b_effect = -6 if run.settings["B"] == "低" else 6
        jitter = -1 if run.replicate == 1 else 1
        values[run.run_id] = 20 + a_effect + b_effect + jitter
    frame["响应_Y"] = [values[run_id] for run_id in frame["运行ID"]]
    return frame, metadata


def test_target_mean_metric_picks_closest_level_and_reports_target():
    frame, metadata = l9_target_spec()
    result = best_settings(frame, metadata, "Y", "mean", target=54)
    assert result["metric"] == "mean" and result["target"] == 54
    assert result["best"]["A"] == "中"
    assert result["predicted_mean"] == pytest.approx(54.0, abs=1e-9)


def test_target_mean_enumerates_full_combinations_and_reports_tied_confirmed_settings():
    frame, metadata = l4_target_spec()
    result = best_settings(frame, metadata, "Y", "mean", target=20)
    # 手算：A={14,26}、B={14,26}、grand=20；加性组合预测为 8,20,20,32。
    assert result["best"] == {"A": "低", "B": "高"}
    assert result["predicted_mean"] == pytest.approx(20.0, abs=1e-12)
    assert [item["settings"] for item in result["tied_combinations"]] == [
        {"A": "低", "B": "高"}, {"A": "高", "B": "低"}]
    assert [item["predicted"] for item in result["tied_combinations"]] == [20, 20]
    assert result["search"]["method"].startswith("exact enumeration")
    assert result["search"]["candidate_count"] == 4
    assert result["search"]["global_optimum"] is True
    assert result["is_observed"] is True
    assert "该组合已在实验中观测" in result["status"]
    assert result["confirmation"]["observed"] is None


def test_target_slope_enumerates_complete_control_combinations():
    from doe_taguchi_analysis import analyze_dynamic
    from test_doe_taguchi_dynamic import dynamic_spec

    frame, metadata = create_taguchi(dynamic_spec())
    design = restore_design_result(frame, metadata)
    run_values = {}
    expected_slopes = {
        ("低", "低"): 8.0, ("低", "高"): 20.0,
        ("高", "低"): 20.0, ("高", "高"): 32.0,
    }
    for run in design.runs:
        slope = expected_slopes[(run.settings["A"], run.settings["B"])]
        error = {1.0: 0.1, 2.0: -0.2, 3.0: 0.1}[run.settings["S"]]
        run_values[run.run_id] = 3.0 + slope * run.settings["S"] + error
    frame["响应_Y"] = [run_values[run_id] for run_id in frame["运行ID"]]
    fits = analyze_dynamic(frame, metadata, "Y")
    assert {(row["settings"]["A"], row["settings"]["B"]): row["slope"]
            for row in fits["combinations"]} == {
                key: pytest.approx(value, abs=1e-12)
                for key, value in expected_slopes.items()}
    result = best_settings(frame, metadata, "Y", "slope", target=20.0)
    assert result["best"] == {"A": "低", "B": "高"}
    assert result["predicted_slope"] == pytest.approx(20.0, abs=1e-12)
    assert [item["settings"] for item in result["tied_combinations"]] == [
        {"A": "低", "B": "高"}, {"A": "高", "B": "低"}]
    assert result["is_observed"] is True


def test_target_search_reports_budget_limit_without_claiming_optimum(monkeypatch):
    import doe_taguchi_analysis as analysis

    frame, metadata = l9_target_spec()
    monkeypatch.setattr(analysis, "_MAX_TARGET_COMBINATIONS", 3)
    with pytest.raises(ValueError, match="精确枚举.*超过预算.*无法声明目标最优"):
        analysis.best_settings(frame, metadata, "Y", "mean", target=54)


def test_target_search_does_not_treat_distinct_near_optima_as_ties():
    spec = DesignSpec(
        "TG", (factor("A", ("低", "高")), factor("B", ("低", "高"))),
        ("Y",), seed=8, design_type="taguchi",
        taguchi={"kind": "static", "array_id": "L4(2^3)",
                 "matrix_sha256": ARRAYS["L4(2^3)"].sha256,
                 "columns": {"A": 1, "B": 2},
                 "noise_array_id": None, "noise_matrix_sha256": None,
                 "noise_columns": {}, "signal_factor": None})
    frame, metadata = create_taguchi(spec)
    design = restore_design_result(frame, metadata)
    means = {("低", "低"): 10.0, ("低", "高"): 10.0 + 3e-10,
             ("高", "低"): 10.0 + 1e-10, ("高", "高"): 10.0 + 4e-10}
    values = {run.run_id: means[(run.settings["A"], run.settings["B"])]
              for run in design.runs}
    frame["响应_Y"] = [values[run_id] for run_id in frame["运行ID"]]
    result = best_settings(frame, metadata, "Y", "mean", target=10.0 + 0.75e-10)
    assert result["best"] == {"A": "高", "B": "低"}
    assert len(result["tied_combinations"]) == 1
    assert result["predicted_mean"] == pytest.approx(10.0 + 1e-10, abs=1e-14)


def test_minimum_sd_metric_selects_lowest_variability_level():
    frame, metadata = l9_target_spec()
    design = restore_design_result(frame, metadata)
    values = {run.run_id: 20 + (6.0 if run.settings["B"] == "高" else 1.0)
              * (1 if run.replicate == 1 else -1) for run in design.runs}
    frame["响应_Y"] = [values[run_id] for run_id in frame["运行ID"]]
    result = best_settings(frame, metadata, "Y", "sd")
    assert result["metric"] == "sd" and result["best"]["B"] != "高"
    assert result["predicted_sd"] >= 0


def test_sd_based_best_settings_rejects_single_observations_and_negative_additive_sd():
    spec = DesignSpec(
        "TG", (factor("A", ("低", "高")), factor("B", ("低", "高"))),
        ("Y",), seed=2, design_type="taguchi",
        taguchi={"kind": "static", "array_id": "L4(2^3)",
                 "matrix_sha256": ARRAYS["L4(2^3)"].sha256,
                 "columns": {"A": 1, "B": 2},
                 "noise_array_id": None, "noise_matrix_sha256": None,
                 "noise_columns": {}, "signal_factor": None})
    frame, metadata = create_taguchi(spec, replicates=1)
    frame["响应_Y"] = 2.0
    single = best_settings(frame, metadata, "Y", "sn")
    assert single["predicted_sd"] is None
    assert single["predicted_sd_reason"] == "样本不足，SD 无法估计"
    with pytest.raises(ValueError, match="最小 SD.*不可计算"):
        best_settings(frame, metadata, "Y", "sd")

    frame, metadata = create_taguchi(spec, replicates=2)
    design = restore_design_result(frame, metadata)
    spreads = {("低", "低"): 1.0, ("低", "高"): 1.0,
               ("高", "低"): 1.0, ("高", "高"): 100.0}
    values = {}
    for run in design.runs:
        key = (run.settings["A"], run.settings["B"])
        jitter = spreads[key] / math.sqrt(2)
        values[run.run_id] = 20 + (-jitter if run.replicate == 1 else jitter)
    frame["响应_Y"] = [values[run_id] for run_id in frame["运行ID"]]
    negative = best_settings(frame, metadata, "Y", "mean", target=0.0)
    assert negative["best"] == {"A": "低", "B": "低"}
    assert negative["predicted_sd"] is None
    assert negative["predicted_sd_reason"] == "加性主效应预测为负，不作为物理标准差显示"


def test_dynamic_target_slope_metric_uses_slope_table():
    from test_doe_taguchi_dynamic import dynamic_spec
    frame, metadata = create_taguchi(dynamic_spec())
    design = restore_design_result(frame, metadata)
    values = {}
    for run in design.runs:
        slope = 2.0 if run.settings["A"] == "低" else 5.0
        values[run.run_id] = 1.0 + slope * run.settings["S"] + (
            0.3 if int(run.settings["S"]) % 2 else -0.2)
    frame["响应_Y"] = [values[run_id] for run_id in frame["运行ID"]]
    result = best_settings(frame, metadata, "Y", "slope", target=4.0)
    assert result["metric"] == "slope" and result["best"]["A"] == "高"
    assert result["predicted_slope"] is not None


def test_best_settings_reuse_saved_analysis_options():
    """保存在工程里的 S/N 类型与参考点必须影响最佳设置，不静默回退默认值。"""
    frame, metadata = l9_target_spec()
    smaller = best_settings(frame, metadata, "Y", "sn")
    nominal = best_settings(
        frame, {**metadata, "analysis": {
            "kind": "static", "sn_kind": "nominal", "adjusted": False,
            "ln_sd": False}}, "Y", "sn")
    assert nominal["predicted_sn"] != smaller["predicted_sn"]
    # 选项生效：同一组合的 S/N 应与 nominal (I) 公式一致
    from doe_taguchi_sn import analyze_static
    direct = analyze_static(
        frame, {**metadata, "analysis": {
            "kind": "static", "sn_kind": "nominal", "adjusted": False,
            "ln_sd": False}}, "Y", "nominal")
    assert [row["sn"] for row in nominal["table"]["factors"][0]["levels"]] == [
        pytest.approx(value) for value in
        [row["sn"] for row in direct["response_table"]["factors"][0]["levels"]]]


def test_static_design_rejects_slope_metric():
    frame, metadata = l9_target_spec()
    with pytest.raises(ValueError, match="动态"):
        best_settings(frame, metadata, "Y", "slope")


def test_tied_levels_are_reported_without_silent_pick():
    frame, metadata = l9_target_spec()
    design = restore_design_result(frame, metadata)
    values = {run.run_id: 30.0 + (0.5 if run.settings["A"] == "高" else 0.0)
              + (0.2 if run.replicate == 1 else -0.2)
              for run in design.runs}
    frame["响应_Y"] = [values[run_id] for run_id in frame["运行ID"]]
    result = best_settings(frame, metadata, "Y", "sn")
    tied = result["tied"]["B"]
    assert tied["tied"] is True and len(tied["levels"]) >= 2
    assert result["best"]["B"] in tied["levels"]


def test_confirmation_difference_and_target_judgement():
    frame, metadata = l9_target_spec()
    result = best_settings(frame, metadata, "Y", "mean", target=54,
                           observed=54.2, tolerance=0.5)
    assert result["confirmation"]["difference"] == pytest.approx(
        54.2 - result["predicted_mean"])
    assert result["confirmation"]["meets_target"] is True
    strict = best_settings(frame, metadata, "Y", "mean", target=54,
                           observed=56.0, tolerance=0.5)
    assert strict["confirmation"]["meets_target"] is False


def test_noise_robustness_reports_factor_level_response_table():
    frame, metadata = create_taguchi(inner_outer_spec())
    design = restore_design_result(frame, metadata)
    values = {}
    for run in design.runs:
        spread = 4.0 if run.settings["A"] == "低" else 1.0
        values[run.run_id] = 10.0 + (spread if run.settings["N"] == "n2" else 0.0)
    frame["响应_Y"] = [values[run_id] for run_id in frame["运行ID"]]
    result = noise_robustness(frame, metadata, "Y", "smaller")
    table = {row["factor_id"]: row for row in result["response_table"]["factors"]}
    assert set(table) == {"A", "B"}
    best = result["response_table"]["best"]["A"]
    assert best == "高"
    assert result["response_table"]["ranked"][0] == "A"


def test_zero_noise_sd_is_reported_instead_of_null():
    frame, metadata = create_taguchi(inner_outer_spec())
    frame["响应_Y"] = 5.0
    with pytest.raises(ValueError, match="SD 为零"):
        noise_robustness(frame, metadata, "Y", "smaller")

