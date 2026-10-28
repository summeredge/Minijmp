"""动态 Taguchi 设计与 signal-response 回归、动态 S/N。"""
import math

import pytest

from doe_core import DesignSpec, FactorSpec, restore_design_result
from doe_taguchi import create_taguchi
from doe_taguchi_analysis import analyze_dynamic
from doe_taguchi_arrays import ARRAYS
from doe_taguchi_sn import dynamic_sn, fit_dynamic


def factor(factor_id, levels, numeric=False):
    return FactorSpec(factor_id, factor_id, None, None, factor_type="categorical",
                      levels=tuple(levels),
                      level_type="numeric" if numeric else "text")


def dynamic_spec(array_id="L4(2^3)", signal=(1.0, 2.0, 3.0)):
    array = ARRAYS[array_id]
    factors = (factor("A", ("低", "高")), factor("B", ("低", "高")),
               factor("S", signal, numeric=True))
    return DesignSpec("TG", factors, ("Y",), seed=3, design_type="taguchi",
                      taguchi={"kind": "dynamic", "array_id": array_id,
                               "matrix_sha256": array.sha256,
                               "columns": {"A": 1, "B": 2},
                               "noise_array_id": None, "noise_matrix_sha256": None,
                               "noise_columns": {}, "signal_factor": "S"})


def test_dynamic_design_expands_signal_levels_and_roundtrips():
    frame, metadata = create_taguchi(dynamic_spec())
    design = restore_design_result(frame, metadata)
    assert len(design.runs) == 4 * 3
    assert {run.settings["S"] for run in design.runs} == {1.0, 2.0, 3.0}
    assert metadata["design"]["taguchi"]["signal_factor"] == "S"


def test_static_design_cannot_declare_signal_factor():
    array = ARRAYS["L4(2^3)"]
    with pytest.raises(ValueError, match="信号因子"):
        DesignSpec("TG", (factor("A", ("低", "高")), factor("B", ("低", "高"))),
                   ("Y",), seed=1, design_type="taguchi",
                   taguchi={"kind": "static", "array_id": "L4(2^3)",
                            "matrix_sha256": array.sha256,
                            "columns": {"A": 1, "B": 2},
                            "noise_array_id": None, "noise_matrix_sha256": None,
                            "noise_columns": {}, "signal_factor": "S"})


def test_signal_factor_must_be_ascending_numeric():
    array = ARRAYS["L4(2^3)"]
    with pytest.raises(ValueError, match="升序数值"):
        DesignSpec("TG", (factor("A", ("低", "高")), factor("B", ("低", "高")),
                          factor("S", ("低", "高"))), ("Y",), seed=1,
                   design_type="taguchi",
                   taguchi={"kind": "dynamic", "array_id": "L4(2^3)",
                            "matrix_sha256": array.sha256,
                            "columns": {"A": 1, "B": 2},
                            "noise_array_id": None, "noise_matrix_sha256": None,
                            "noise_columns": {}, "signal_factor": "S"})


def test_free_intercept_fit_matches_closed_form_reference():
    fit = fit_dynamic([1, 2, 3], [2.0, 4.5, 6.0])
    assert fit["slope"] == pytest.approx(2.0, abs=1e-12)
    assert fit["intercept"] == pytest.approx(0.16666666666666696, abs=1e-12)
    assert fit["mse"] == pytest.approx(0.16666666666666666, abs=1e-12)
    assert fit["df"] == 1
    assert dynamic_sn(fit) == pytest.approx(13.80211241711606, abs=1e-12)


def test_reference_point_fit_and_adjusted_dynamic_sn():
    fit = fit_dynamic([1, 2, 3], [2.0, 4.5, 6.0], reference=(2.0, 4.5))
    assert fit["slope"] == pytest.approx(2.0, abs=1e-12)
    assert fit["intercept"] == pytest.approx(0.5, abs=1e-12)
    assert fit["df"] == 2
    assert fit["mse"] == pytest.approx(0.25, abs=1e-12)
    assert dynamic_sn(fit) == pytest.approx(12.041199826559248, abs=1e-12)
    assert dynamic_sn(fit, adjusted=True) == pytest.approx(11.903316981702915, abs=1e-12)


@pytest.mark.parametrize("signal,response,reference,message", [
    ([1, 2], [1.0], None, "长度不一致"),
    ([2, 2], [1.0, 2.0], None, "两个不同信号水平"),
    ([2, 2], [1.0, 2.0], (2, 1.0), "参考"),
    ([1], [1.0], None, "两个不同信号水平"),
])
def test_dynamic_fit_domain_errors(signal, response, reference, message):
    with pytest.raises(ValueError):
        fit_dynamic(signal, response, reference)


def test_zero_residual_mse_makes_dynamic_sn_unavailable():
    fit = fit_dynamic([1, 2, 3], [2.0, 4.0, 6.0])
    assert fit["mse"] == pytest.approx(0, abs=1e-20)
    with pytest.raises(ValueError, match="MSE 为零"):
        dynamic_sn(fit)


def test_dynamic_analysis_reports_slope_per_control_combination():
    frame, metadata = create_taguchi(dynamic_spec())
    design = restore_design_result(frame, metadata)
    values = {}
    for run in design.runs:
        slope = 2.0 if run.settings["A"] == "低" else 4.0
        intercept = 1.0 if run.settings["B"] == "低" else 3.0
        jitter = 0.3 if int(run.settings["S"]) % 2 else -0.2
        values[run.run_id] = intercept + slope * run.settings["S"] + jitter
    frame["响应_Y"] = [values[run_id] for run_id in frame["运行ID"]]
    result = analyze_dynamic(frame, metadata, "Y")
    assert len(result["combinations"]) == 4
    slopes = {row["settings"]["A"]: row["slope"] for row in result["combinations"]}
    assert slopes["低"] == pytest.approx(2.0, abs=1e-9)
    assert slopes["高"] == pytest.approx(4.0, abs=1e-9)
    assert all(row["df"] == 1 for row in result["combinations"])
    assert result["slope_table"]["ranked"][0] == "A"


def test_dynamic_analysis_requires_dynamic_design():
    frame, metadata = create_taguchi(dynamic_spec())
    static = DesignSpec("TG", (factor("A", ("低", "高")), factor("B", ("低", "高"))),
                        ("Y",), seed=3, design_type="taguchi",
                        taguchi={"kind": "static", "array_id": "L4(2^3)",
                                 "matrix_sha256": ARRAYS["L4(2^3)"].sha256,
                                 "columns": {"A": 1, "B": 2},
                                 "noise_array_id": None, "noise_matrix_sha256": None,
                                 "noise_columns": {}, "signal_factor": None})
    frame2, metadata2 = create_taguchi(static, replicates=2)
    frame2["响应_Y"] = 1.0
    with pytest.raises(ValueError, match="动态"):
        analyze_dynamic(frame2, metadata2, "Y")
