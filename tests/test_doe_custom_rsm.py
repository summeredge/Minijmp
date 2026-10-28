import json
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from doe_core import FactorSpec, _fingerprint, restore_design_result
from doe_custom import define_custom, design_matrix, validate_custom
from doe_custom_analysis import analyze_custom_rsm
from doe_rsm_model import TermModel


REFERENCE = json.loads((Path(__file__).parent / "fixtures" / "doe_optimal_reference"
                        / "reference.json").read_text(encoding="utf-8"))
TERMS = ["X1", "X2", "X3", "X1²", "X2²", "X3²", "X1*X2", "X1*X3", "X2*X3"]


def reference_frame():
    case = REFERENCE["custom_rsm"]
    rows = case["rows"]
    frame = pd.DataFrame({
        "运行ID": [f"R{index:05d}" for index in range(1, len(rows) + 1)],
        "标准序": list(range(1, len(rows) + 1)),
        "运行序": list(range(1, len(rows) + 1)),
        "点类型": [row["point_type"] for row in rows],
        "重复": [1] * len(rows),
        "X1": [row["coded"][0] for row in rows],
        "X2": [row["coded"][1] for row in rows],
        "X3": [row["coded"][2] for row in rows],
    })
    x1, x2, x3 = frame["X1"], frame["X2"], frame["X3"]
    frame["Y"] = 10 + 2 * x1 - x2 + 3 * x3 + 1.5 * x1**2 - 0.5 * x2**2 + \
        x1 * x2
    return frame


def factors():
    # 参考行按编码值给出；轴点位于 low/high 之外，与 CCD 一致。
    return tuple(FactorSpec(key, key, -1, 1) for key in ("X1", "X2", "X3"))


def columns():
    return {"run_id": "运行ID", "standard_order": "标准序", "run_order": "运行序",
            "point_type": "点类型", "replicate": "重复",
            "factors": {key: key for key in ("X1", "X2", "X3")},
            "responses": {"Y": "Y"}}


def test_custom_rsm_rebuilds_model_matrix_and_keeps_row_order():
    frame = reference_frame()
    original = frame.copy(deep=True)
    result, metadata, summary = define_custom(
        frame, design_type="custom_rsm", factors=factors(), responses=("Y",),
        column_map=columns(), model_terms=TERMS, design_id="custom-rsm")
    pd.testing.assert_frame_equal(frame, original)
    assert summary["rank"] == 10 == summary["p"]
    assert summary["estimable"] is True
    design = restore_design_result(result, metadata)
    matrix, model = design_matrix(design)
    assert matrix.shape == (17, 10)
    assert model.terms == tuple(TERMS)
    # 实际矩阵与独立参考矩阵一致（列顺序按模型项）。
    expected = []
    for row in REFERENCE["custom_rsm"]["rows"]:
        x1, x2, x3 = row["coded"]
        expected.append([1, x1, x2, x3, x1**2, x2**2, x3**2,
                         x1 * x2, x1 * x3, x2 * x3])
    np.testing.assert_allclose(matrix, np.asarray(expected), atol=1e-12)


def test_custom_rsm_analysis_matches_independent_coefficients():
    frame = reference_frame()
    result, metadata, _ = define_custom(
        frame, design_type="custom_rsm", factors=factors(), responses=("Y",),
        column_map=columns(), model_terms=TERMS)
    analysis = analyze_custom_rsm(result, metadata, "Y")
    beta = analysis["coefficients"]
    assert np.isclose(beta[0], 10)
    assert np.isclose(beta[1], 2)
    assert np.isclose(beta[2], -1)
    assert np.isclose(beta[3], 3)
    assert np.isclose(beta[4], 1.5)
    assert np.isclose(beta[5], -0.5)
    assert np.isclose(beta[7], 1)
    assert np.isclose(beta[8], 0, atol=1e-10)
    assert analysis["n"] == 17 and analysis["p"] == 10


def test_custom_rsm_does_not_claim_ccd_or_bbd_identity():
    frame = reference_frame()
    _, metadata, summary = define_custom(
        frame, design_type="custom_rsm", factors=factors(), responses=("Y",),
        column_map=columns(), model_terms=TERMS)
    assert metadata["design"]["design_type"] == "custom_rsm"
    assert metadata["design"]["ccd_alpha"] is None
    assert summary["design_type"] == "custom_rsm"


def test_custom_rsm_rejects_rank_deficient_terms():
    frame = reference_frame()
    frame = frame[frame["点类型"] == "factorial"].reset_index(drop=True)
    frame["标准序"] = list(range(1, len(frame) + 1))
    frame["运行序"] = list(range(1, len(frame) + 1))
    with pytest.raises(ValueError, match="秩亏"):
        define_custom(frame, design_type="custom_rsm", factors=factors(),
                      responses=("Y",), column_map=columns(),
                      model_terms=TERMS)


def test_custom_rsm_rejects_missing_terms_and_out_of_range_levels():
    frame = reference_frame()
    with pytest.raises(ValueError, match="模型项"):
        define_custom(frame, design_type="custom_rsm", factors=factors(),
                      responses=("Y",), column_map=columns())
    frame.loc[0, "X1"] = 2.5
    with pytest.raises(ValueError, match="范围"):
        define_custom(frame, design_type="custom_rsm", factors=factors(),
                      responses=("Y",), column_map=columns(), model_terms=TERMS)


def test_custom_rsm_rejects_unestimable_extra_term():
    frame = reference_frame()
    with pytest.raises(ValueError, match="两个因子"):
        define_custom(frame, design_type="custom_rsm", factors=factors(),
                      responses=("Y",), column_map=columns(),
                      model_terms=TERMS + ["X1*X2*X3"])


def _blocked_frame():
    """两个区组，各含 2^2 因子点与两个中心点；模型只声明主效应与交互。"""
    rows, index = [], 0
    for block in ("B1", "B2"):
        for point_type, coded in (
                ("factorial", (-1, -1)), ("factorial", (1, -1)),
                ("factorial", (-1, 1)), ("factorial", (1, 1)),
                ("center", (0, 0)), ("center", (0, 0))):
            index += 1
            x1, x2 = coded
            rows.append({"运行ID": f"R{index}", "标准序": index, "运行序": index,
                         "点类型": point_type, "重复": 1, "区组": block,
                         "X1": x1, "X2": x2,
                         "Y": 10 + x1 + 2 * x2 + 3 * (block == "B2")})
    return pd.DataFrame(rows)


def _blocked_columns():
    return {"run_id": "运行ID", "standard_order": "标准序", "run_order": "运行序",
            "point_type": "点类型", "replicate": "重复", "block": "区组",
            "factors": {"X1": "X1", "X2": "X2"}, "responses": {"Y": "Y"}}


def test_custom_rsm_analysis_uses_declared_terms_not_full_quadratic():
    # 设计只声明 X1、X2、X1*X2；分析若退回完整二次模型会因平方项不可估而秩亏。
    result, metadata, summary = define_custom(
        _blocked_frame(), design_type="custom_rsm",
        factors=(FactorSpec("X1", "X1", -1, 1), FactorSpec("X2", "X2", -1, 1)),
        responses=("Y",), column_map=_blocked_columns(),
        model_terms=["X1", "X2", "X1*X2"], block_count=2, design_id="blocked")
    assert summary["rank"] == summary["p"] == 4
    analysis = analyze_custom_rsm(result, metadata, "Y")
    assert analysis["n"] == 12
    assert analysis["names"] == ["截距", "X1", "X2", "X1*X2", "区组2"]
    assert analysis["p"] == 5 and analysis["rank"] == 5
    assert analysis["blocks"] == ["B1", "B2"]
    coefficients = dict(zip(analysis["names"], analysis["coefficients"]))
    assert np.isclose(coefficients["X1"], 1)
    assert np.isclose(coefficients["X2"], 2)
    assert np.isclose(coefficients["区组2"], 3)
    # 忽略区组时模型项数量减少，但数据本身不变。
    plain = analyze_custom_rsm(result, metadata, "Y", use_blocks=False)
    assert plain["p"] == 4 and plain["blocks"] == []


def test_axial_categorical_level_is_checked_even_with_recomputed_digest():
    frame = reference_frame().drop(columns="X3")
    frame["C"] = ["低" if i % 2 else "高" for i in range(len(frame))]
    mixed_factors = (FactorSpec("X1", "X1", -1, 1),
                     FactorSpec("X2", "X2", -1, 1),
                     FactorSpec("C", "C", None, None, factor_type="categorical",
                                levels=("低", "高")))
    mapping = columns()
    mapping["factors"] = {name: name for name in ("X1", "X2", "C")}
    kwargs = dict(design_type="custom_rsm", factors=mixed_factors,
                  responses=("Y",), column_map=mapping,
                  model_terms=["X1", "X2", "C"])
    valid, metadata, _ = define_custom(frame, **kwargs)
    design = restore_design_result(valid, metadata)
    row = frame.index[frame["点类型"] == "axial"][0]
    invalid = valid.copy()
    invalid.loc[row, "C"] = "未知"
    runs = list(design.runs)
    runs[row] = replace(runs[row], settings={**runs[row].settings, "C": "未知"})
    metadata["worksheet"]["input_fingerprint"] = _fingerprint(
        metadata["design"], metadata["column_map"], SimpleNamespace(runs=runs))
    with pytest.raises(ValueError, match="分类因子"):
        define_custom(invalid, **kwargs)
    with pytest.raises(ValueError, match="分类因子"):
        restore_design_result(invalid, metadata)
    with pytest.raises(ValueError, match="水平不在已声明范围"):
        TermModel(mixed_factors, ["X1", "X2", "C"]).row(
            {"X1": 2.0, "X2": 0.0, "C": "未知"})
