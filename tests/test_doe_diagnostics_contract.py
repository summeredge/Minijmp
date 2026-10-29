import json
from pathlib import Path

import pandas as pd
import pytest

from doe_analysis import analyze_factorial
from doe_core import DesignSpec, FactorSpec
from doe_custom import define_custom
from doe_custom_analysis import analyze_custom_factorial
from doe_diagnostics import contract
from doe_factorial import create_factorial


def factorial_case():
    spec = DesignSpec("diag", (FactorSpec("A", "A", 0, 1),
                               FactorSpec("B", "B", 0, 1)),
                      ("Y",), seed=3, design_type="two_level_full")
    frame, metadata = create_factorial(spec, replicates=2)
    frame["响应_Y"] = pd.array(
        [10 + 2 * (2 * row["设定_A"] - 1) for _, row in frame.iterrows()],
        dtype="Float64")
    return frame, metadata


def test_diagnostics_contract_reports_unified_fields():
    frame, metadata = factorial_case()
    result = analyze_factorial(frame, metadata, "Y", 1)
    data = contract(result, "two_level_full")
    values = {row["item"]: row for row in data["rows"]}
    for label in ("运行数 n", "参数数 p", "矩阵秩", "残差自由度", "SSE", "SST",
                  "纯误差自由度", "失拟自由度", "中心点曲率", "条件数",
                  "模型可估计性", "假设检验", "杠杆值"):
        assert label in values
    assert values["运行数 n"]["value"] == 8
    assert values["假设检验"]["value"] == "未自动检验"
    assert "不证明" in values["假设检验"]["note"]
    assert values["杠杆值"]["value"] is None


def test_diagnostics_do_not_claim_significance_without_error_df():
    frame, metadata = factorial_case()
    result = analyze_factorial(frame, metadata, "Y", 1)
    data = contract(result, "two_level_full")
    values = {row["item"]: row for row in data["rows"]}
    if result["inference"] is None:
        assert values["模型 F / p"]["value"] is None
    assert values["纯误差自由度"]["note"]


def test_custom_diagnostics_include_matrix_rank_and_condition():
    frame = pd.DataFrame({
        "运行ID": ["R1", "R2", "R3", "R4"],
        "标准序": [1, 2, 3, 4], "运行序": [1, 2, 3, 4],
        "点类型": ["factorial"] * 4, "重复": [1] * 4,
        "A": [-1, 1, -1, 1], "B": [-1, -1, 1, 1], "Y": [1.0, 2.0, 3.0, 5.0],
    })
    factors = (FactorSpec("A", "A", -1, 1), FactorSpec("B", "B", -1, 1))
    mapping = {"run_id": "运行ID", "standard_order": "标准序",
               "run_order": "运行序", "point_type": "点类型",
               "replicate": "重复", "factors": {"A": "A", "B": "B"},
               "responses": {"Y": "Y"}}
    result, metadata, _ = define_custom(
        frame, design_type="custom_factorial", factors=factors,
        responses=("Y",), column_map=mapping)
    analysis = analyze_custom_factorial(result, metadata, "Y", 2)
    data = contract(analysis, "custom_factorial")
    values = {row["item"]: row for row in data["rows"]}
    assert values["矩阵秩"]["value"] == analysis["rank"] == 4
    assert values["条件数"]["value"] is not None
    assert values["模型可估计性"]["value"] == "满列秩"


def test_rsm_contract_reports_actual_point_diagnostic_coverage():
    from test_doe_rsm_diagnostics import custom_reference_design
    from doe_custom_analysis import analyze_custom_rsm

    frame, metadata = custom_reference_design()
    result = analyze_custom_rsm(frame, metadata, 'Y')
    rows = {row['item']: row for row in contract(result, 'custom_rsm')['rows']}
    assert rows['杠杆值']['value'] == '9/9'
    assert rows['逐点影响量']['value'].endswith('/9')
    assert '实际模型矩阵' in rows['杠杆值']['note']
