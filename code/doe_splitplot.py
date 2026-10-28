"""两个两水平因子的平衡裂区设计生成与结构校验。"""
import random
from itertools import product

import pandas as pd

from doe_core import DesignSpec, restore_design_result, worksheet_metadata


_MAX_RUNS = 10000


def _layout(spec):
    if not isinstance(spec, DesignSpec) or spec.design_type != "split_plot":
        raise ValueError("需要 split_plot 设计定义")
    if spec.schema_version < 4:
        raise ValueError("Split-Plot 需要 schema v4 或更高")
    if len(spec.factors) != 2:
        raise ValueError("当前 Split-Plot 仅支持两个连续两水平因子")
    hard = [factor for factor in spec.factors
            if factor.randomization_role == "hard_to_change"]
    easy = [factor for factor in spec.factors
            if factor.randomization_role == "easy_to_change"]
    if len(hard) != 1 or len(easy) != 1:
        raise ValueError("Split-Plot 需一个 hard-to-change 和一个 easy-to-change 因子")
    if any(factor.factor_type != "continuous" for factor in spec.factors):
        raise ValueError("Split-Plot 因子必须连续")
    if spec.block_count is None or spec.block_count < 2:
        raise ValueError("Split-Plot 至少需要两个区组")
    if spec.seed is None:
        raise ValueError("随机化必须指定整数 seed")
    if (spec.generators or spec.defining_relations or spec.aliases
            or spec.screening_matrix is not None or spec.foldover_lineage is not None
            or spec.ccd_fraction is not None
            or any(value is not None for value in (
                spec.ccd_alpha, spec.ccd_center_points, spec.ccd_axial_points))):
        raise ValueError("Split-Plot 不能包含生成元、筛选或 CCD 定义")
    if spec.block_count * 4 > _MAX_RUNS:
        raise ValueError(f"运行总数不能超过 {_MAX_RUNS}")
    hard, easy = hard[0], easy[0]
    standard = []
    for block in range(1, spec.block_count + 1):
        for hard_index, hard_code in enumerate((-1, 1), 1):
            whole_plot_id = f"WP{block:05d}H{hard_index}"
            for easy_index, easy_code in enumerate((-1, 1), 1):
                standard.append({
                    "standard_order": len(standard) + 1,
                    "block": block,
                    "hard_code": hard_code,
                    "easy_code": easy_code,
                    "whole_plot_id": whole_plot_id,
                    "subplot_id": f"SP{block:05d}H{hard_index}E{easy_index}",
                })

    by_block = {block: {} for block in range(1, spec.block_count + 1)}
    for row in standard:
        by_block[row["block"]].setdefault(row["whole_plot_id"], []).append(row)

    rng = random.Random(spec.seed)
    actual = []
    block_order = list(by_block)
    rng.shuffle(block_order)
    for block in block_order:
        whole_plots = list(by_block[block].values())
        rng.shuffle(whole_plots)
        for whole_plot_order, subplots in enumerate(whole_plots, 1):
            subplots = list(subplots)
            rng.shuffle(subplots)
            for subplot_order, row in enumerate(subplots, 1):
                actual.append({**row, "whole_plot_order": whole_plot_order,
                               "subplot_order": subplot_order,
                               "run_order": len(actual) + 1})
    return hard, easy, actual


def create_split_plot(spec):
    """返回运行表和 DOE-0 元数据。"""
    hard, easy, actual = _layout(spec)
    columns = {
        "run_id": "运行ID", "standard_order": "标准序", "run_order": "运行序",
        "point_type": "点类型", "replicate": "重复", "block": "区组",
        "factors": {factor.factor_id: f"设定_{factor.factor_id}"
                    for factor in spec.factors},
        "measured_levels": {},
        "responses": {name: f"响应_{name}" for name in spec.response_names},
        "whole_plot_id": "整区ID", "subplot_id": "子区ID",
        "whole_plot_order": "整区序", "subplot_order": "子区序",
    }
    rows = []
    for item in actual:
        row = {
            "运行ID": f"R{item['standard_order']:05d}",
            "标准序": item["standard_order"], "运行序": item["run_order"],
            "点类型": "factorial", "重复": 1, "区组": item["block"],
            "整区ID": item["whole_plot_id"], "子区ID": item["subplot_id"],
            "整区序": item["whole_plot_order"], "子区序": item["subplot_order"],
        }
        row[columns["factors"][hard.factor_id]] = hard.from_coded(item["hard_code"])
        row[columns["factors"][easy.factor_id]] = easy.from_coded(item["easy_code"])
        row.update({name: None for name in columns["responses"].values()})
        rows.append(row)

    frame = pd.DataFrame(rows)
    for name in columns["factors"].values():
        frame[name] = pd.Series([row[name] for row in rows], dtype=object)
    for name in columns["responses"].values():
        frame[name] = pd.array([None] * len(rows), dtype="Float64")
    return frame, worksheet_metadata(frame, spec, columns)


def validate_split_plot_design(frame, metadata):
    """验证 Schema v4 元数据及裂区标准序、随机化和 RunRecord 身份。"""
    result = restore_design_result(frame, metadata)
    spec = result.spec
    hard, easy, actual = _layout(spec)
    if len(result.runs) != len(actual):
        raise ValueError("Split-Plot 运行数与设计定义不一致")
    by_standard = {run.standard_order: run for run in result.runs}
    for expected in actual:
        run = by_standard[expected["standard_order"]]
        settings = {
            hard.factor_id: hard.from_coded(expected["hard_code"]),
            easy.factor_id: easy.from_coded(expected["easy_code"]),
        }
        identity = (
            run.run_id, run.standard_order, run.run_order, run.point_type,
            run.replicate, run.block, run.whole_plot_id, run.subplot_id,
            run.whole_plot_order, run.subplot_order,
        )
        expected_identity = (
            f"R{expected['standard_order']:05d}", expected["standard_order"],
            expected["run_order"], "factorial", 1, expected["block"],
            expected["whole_plot_id"], expected["subplot_id"],
            expected["whole_plot_order"], expected["subplot_order"],
        )
        if (identity != expected_identity or dict(run.settings) != settings
                or run.batch_id is not None or run.source_run_id is not None):
            raise ValueError("Split-Plot 运行身份、标准序或 seed 随机化无效")
    return result
