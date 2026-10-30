import json
import math
from pathlib import Path

import pytest

import doe_taguchi_analysis as analysis
import doe_taguchi_sn
from doe_core import DesignSpec, FactorSpec, restore_design_result
from doe_taguchi import create_taguchi
from doe_taguchi_analysis import noise_robustness
from doe_taguchi_arrays import ARRAYS


P4BC_REFERENCE = json.loads((Path(__file__).parent / "fixtures"
                             / "doe_phase2_p4bc_reference" / "reference.json").read_text(
                                 encoding="utf-8"))
REFERENCE = P4BC_REFERENCE["two_stage_selection"]


def selection_input(monkeypatch):
    factors = tuple(FactorSpec(
        factor_id, factor_id, None, None, factor_type="categorical",
        levels=(1, 2), level_type="numeric") for factor_id in ("A", "B"))
    array = ARRAYS["L4(2^3)"]
    spec = DesignSpec(
        "TG", factors, ("Y",), seed=3, design_type="taguchi",
        taguchi={"kind": "static", "array_id": array.array_id,
                 "matrix_sha256": array.sha256, "columns": {"A": 1, "B": 2},
                 "noise_array_id": None, "noise_matrix_sha256": None,
                 "noise_columns": {}, "signal_factor": None})
    frame, metadata = create_taguchi(spec)
    frame["响应_Y"] = [float(index + 1) for index in range(len(frame))]

    sn_effects = REFERENCE["level_effects"]["sn"]
    mean_effects = REFERENCE["level_effects"]["mean"]
    sd_reference = REFERENCE["sd_reference"]
    table = {"factors": []}
    for factor_id in ("A", "B"):
        levels = []
        for level in (1, 2):
            levels.append({
                "level": level,
                "sn": (REFERENCE["intercepts"]["sn"]
                       + sn_effects[factor_id][str(level)]),
                "mean": (REFERENCE["intercepts"]["mean"]
                         + mean_effects[factor_id][str(level)]),
                "sd": (sd_reference["intercept"]
                       + sd_reference["level_effects"][factor_id][str(level)]),
            })
        table["factors"].append({"factor_id": factor_id, "levels": levels})
    combinations = [{
        "settings": row["levels"], "sn": row["predicted_sn"],
        "mean": row["predicted_mean"], "sd": row["observed_sd"],
    } for row in REFERENCE["all_combinations"]]
    monkeypatch.setattr(doe_taguchi_sn, "analyze_static", lambda *args, **kwargs: {
        "response_table": table, "combinations": combinations})
    return frame, metadata


def test_two_selection_modes_match_independent_reference_and_confirmation(monkeypatch):
    frame, metadata = selection_input(monkeypatch)
    before = frame.copy(deep=True)
    maximum = analysis.best_settings(
        frame, metadata, "Y", selection_mode="sn_maximum")
    assert maximum["best"] == {"A": 1, "B": 1}
    assert [item["settings"] for item in maximum["tied_combinations"]] == [
        {"A": 1, "B": 1}]
    assert maximum["predicted_sn"] == pytest.approx(
        REFERENCE["sn_maximum"]["maximum_predicted_sn"])
    assert maximum["search"]["candidate_count"] == 4
    assert maximum["search"]["evaluation_count"] == 4
    assert maximum["search"]["global_optimum"] is True

    expected = REFERENCE["robust_then_target"]
    robust = analysis.best_settings(
        frame, metadata, "Y", target=expected["target"],
        selection_mode="robust_then_target", sn_threshold=expected["sn_threshold"],
        observed=REFERENCE["confirmation"]["observed_mean"],
        tolerance=REFERENCE["confirmation"]["target_tolerance"])
    selected = [item["settings"] for item in robust["tied_combinations"]]
    assert selected == [{"A": 1, "B": 1}, {"A": 2, "B": 1}]
    assert selected == [
        {key: int(value) for key, value in row["levels"].items()}
        for row in REFERENCE["all_combinations"]
        if row["combination_id"] in expected["selected_all_ties"]]
    assert robust["best"] == selected[0]
    assert robust["predicted_mean"] == pytest.approx(105.0)
    assert robust["predicted_sn"] == pytest.approx(23.0)
    assert robust["predicted_sd"] is None
    assert robust["predicted_sd_reason"] == "加性主效应预测为负，不作为物理标准差显示"
    assert robust["confirmation"]["difference"] == pytest.approx(-1.0)
    assert robust["confirmation"]["meets_target"] is True
    assert frame.equals(before)


def test_unreachable_sn_threshold_returns_explicit_status_without_fallback(monkeypatch):
    frame, metadata = selection_input(monkeypatch)
    unreachable = REFERENCE["unreachable_threshold"]
    result = analysis.best_settings(
        frame, metadata, "Y", target=REFERENCE["robust_then_target"]["target"],
        selection_mode="robust_then_target", sn_threshold=unreachable["sn_threshold"])
    assert result["best"] is None
    assert result["status_code"] == "target_unreachable"
    assert result["search"]["stop_reason"] == "no_candidate_meets_sn_threshold"
    assert result["search"]["global_optimum"] is False
    assert result["tied_combinations"] == []
    assert result["predicted_mean"] is None
    assert "未回退" in result["status"]


def test_over_budget_search_rejects_before_enumeration(monkeypatch):
    frame, metadata = selection_input(monkeypatch)
    monkeypatch.setattr(analysis, "_MAX_TARGET_COMBINATIONS", 3)

    def fail_if_enumerated(*args, **kwargs):
        raise AssertionError("over-budget candidate search was started")

    monkeypatch.setattr(analysis, "product", fail_if_enumerated)
    with pytest.raises(ValueError, match="精确枚举.*超过预算.*无法声明预测最优设置"):
        analysis.best_settings(
            frame, metadata, "Y", target=95,
            selection_mode="robust_then_target", sn_threshold=19)


@pytest.mark.parametrize("target,threshold", [(None, 19), (95, None), (float("nan"), 19), (95, float("inf"))])
def test_robust_mode_requires_finite_target_and_threshold(monkeypatch, target, threshold):
    frame, metadata = selection_input(monkeypatch)
    with pytest.raises(ValueError):
        analysis.best_settings(
            frame, metadata, "Y", target=target,
            selection_mode="robust_then_target", sn_threshold=threshold)


def test_noise_summary_matches_independent_two_factor_repeat_reference():
    factors = (
        FactorSpec("A", "A", None, None, factor_type="categorical",
                   levels=(1, 2), level_type="numeric"),
        FactorSpec("B", "B", None, None, factor_type="categorical",
                   levels=(1, 2), level_type="numeric"),
        FactorSpec("N2", "N2", None, None, factor_type="categorical",
                   levels=(1, 2), level_type="numeric"),
        FactorSpec("N3", "N3", None, None, factor_type="categorical",
                   levels=(1, 2, 3), level_type="numeric"),
    )
    inner, outer = ARRAYS["L4(2^3)"], ARRAYS["L18(2^1 3^7)"]
    spec = DesignSpec(
        "TG", factors, ("Y",), seed=15, design_type="taguchi",
        taguchi={"kind": "static", "array_id": inner.array_id,
                 "matrix_sha256": inner.sha256, "columns": {"A": 1, "B": 2},
                 "noise_array_id": outer.array_id,
                 "noise_matrix_sha256": outer.sha256,
                 "noise_columns": {"N2": 1, "N3": 2}, "signal_factor": None})
    frame, metadata = create_taguchi(spec, replicates=2)
    design = restore_design_result(frame, metadata)
    observations = {}
    for run in design.runs:
        a, b = run.settings["A"], run.settings["B"]
        n2, n3 = run.settings["N2"], run.settings["N3"]
        observations[run.run_id] = (
            10 + 2 * a + 3 * b + 1.5 * n2 + 0.75 * n3
            + 0.5 * (run.replicate - 1.5))
    frame["响应_Y"] = [observations[run_id] for run_id in frame["运行ID"]]
    result = noise_robustness(frame, metadata, "Y", "smaller")
    reference = P4BC_REFERENCE["noise_factor_case"]

    def statistics(values):
        mean = math.fsum(values) / len(values)
        sd = math.sqrt(math.fsum((value - mean) ** 2 for value in values)
                        / (len(values) - 1)) if len(values) > 1 else None
        sn = -10 * math.log10(math.fsum(value * value for value in values) / len(values))
        return mean, sd, sn

    assert len(result["rows"]) == reference["expected"]["control_combinations"] == 4
    for control in result["rows"]:
        a, b = control["settings"]["A"], control["settings"]["B"]
        control_id = f"CTRL-{a}{b}"
        source_rows = [row for row in reference["records"]
                       if row["control_id"] == control_id]
        assert control["condition_count"] == reference["expected"]["true_noise_conditions"] == 6
        assert control["observation_count"] == control["noise_count"] == 12
        assert len(control["noise_conditions"]) == 6
        control_values = [row["response"] for row in source_rows]
        mean, sd, sn = statistics(control_values)
        assert control["mean"] == pytest.approx(mean, abs=1e-12)
        assert control["sd"] == pytest.approx(sd, abs=1e-12)
        assert control["sn"] == pytest.approx(sn, abs=1e-12)

        for condition in control["noise_conditions"]:
            n2 = condition["noise_settings"]["N2"]
            n3 = condition["noise_settings"]["N3"]
            condition_rows = [row for row in source_rows
                              if row["noise_levels"] == {"N2": n2, "N3": n3}]
            condition_values = [row["response"] for row in condition_rows]
            cond_mean, cond_sd, _ = statistics(condition_values)
            assert condition["n"] == 2
            assert condition["replicates"] == [1, 2]
            assert len(set(condition["standard_orders"])) == 2
            assert len(set(condition["run_ids"])) == 2
            assert condition["mean"] == pytest.approx(cond_mean, abs=1e-12)
            assert condition["sd"] == pytest.approx(cond_sd, abs=1e-12)
            assert condition["response_range"] == pytest.approx(
                max(condition_values) - min(condition_values), abs=1e-12)

        expected_means = [
            math.fsum(row["response"] for row in source_rows
                      if row["noise_condition_id"] == f"NOISE-{index:02d}") / 2
            for index in range(1, 7)]
        assert control["condition_mean_range"] == pytest.approx(
            max(expected_means) - min(expected_means), abs=1e-12)


def test_robust_then_target_is_rejected_for_dynamic_design():
    from test_doe_taguchi_dynamic import dynamic_spec

    frame, metadata = create_taguchi(dynamic_spec())
    with pytest.raises(ValueError, match="仅适用于静态设计"):
        analysis.best_settings(
            frame, metadata, "Y", target=1, selection_mode="robust_then_target",
            sn_threshold=0)
