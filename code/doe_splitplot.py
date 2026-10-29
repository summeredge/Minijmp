"""两水平平衡 Split-Plot 设计生成与结构校验。"""
import hashlib
import random
from dataclasses import replace
from itertools import product

import pandas as pd

from doe_core import (DesignSpec, design_from_worksheet, restore_design_result,
                      worksheet_metadata)


_MAX_RUNS = 10000
_APPEND_BATCH_ID = "SPLITPLOT_APPEND_V1"


def _layout(spec):
    if not isinstance(spec, DesignSpec) or spec.design_type != "split_plot":
        raise ValueError("需要 split_plot 设计定义")
    if spec.schema_version < 4:
        raise ValueError("Split-Plot 需要 schema v4 或更高")
    hard = tuple(factor for factor in spec.factors
                 if factor.randomization_role == "hard_to_change")
    easy = tuple(factor for factor in spec.factors
                 if factor.randomization_role == "easy_to_change")
    if spec.construction_version not in ("v1", "v2"):
        raise ValueError("未知 Split-Plot 构造版本")
    if spec.construction_version == "v1" and (
            len(spec.factors) != 2 or len(hard) != 1 or len(easy) != 1):
        raise ValueError("Split-Plot v1 固定为一个 hard 和一个 easy 因子")
    if spec.construction_version == "v2" and (
            spec.schema_version < 5 or not 2 <= len(spec.factors) <= 6
            or not 1 <= len(hard) <= 3 or not easy):
        raise ValueError("Split-Plot v2 需 schema v5、2–6 因子、1–3 个 hard 和至少 1 个 easy")
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
    if spec.block_count * (1 << len(spec.factors)) > _MAX_RUNS:
        raise ValueError(f"运行总数不能超过 {_MAX_RUNS}")
    hard_combinations = list(product((-1, 1), repeat=len(hard)))
    easy_combinations = list(product((-1, 1), repeat=len(easy)))
    standard = []
    for block in range(1, spec.block_count + 1):
        for hard_index, hard_codes in enumerate(hard_combinations, 1):
            whole_plot_id = f"WP{block:05d}H{hard_index}"
            hard_settings = dict(zip((factor.factor_id for factor in hard), hard_codes))
            for easy_index, easy_codes in enumerate(easy_combinations, 1):
                coded = {**hard_settings,
                         **dict(zip((factor.factor_id for factor in easy), easy_codes))}
                standard.append({
                    "standard_order": len(standard) + 1,
                    "block": block,
                    "coded": coded,
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


def _appended_layout(spec, first_block, block_count, run_order_start):
    hard = tuple(factor for factor in spec.factors
                 if factor.randomization_role == "hard_to_change")
    easy = tuple(factor for factor in spec.factors
                 if factor.randomization_role == "easy_to_change")
    hard_combinations = list(product((-1, 1), repeat=len(hard)))
    easy_combinations = list(product((-1, 1), repeat=len(easy)))
    run_count = 1 << len(spec.factors)
    easy_count = 1 << len(easy)
    standard = []
    for block in range(first_block, first_block + block_count):
        for hard_index, hard_codes in enumerate(hard_combinations, 1):
            whole_plot_id = f"WP{block:05d}H{hard_index}"
            hard_settings = dict(zip((factor.factor_id for factor in hard), hard_codes))
            for easy_index, easy_codes in enumerate(easy_combinations, 1):
                standard.append({
                    "standard_order": ((block - 1) * run_count
                                       + (hard_index - 1) * easy_count + easy_index),
                    "block": block,
                    "coded": {**hard_settings,
                              **dict(zip((factor.factor_id for factor in easy), easy_codes))},
                    "whole_plot_id": whole_plot_id,
                    "subplot_id": f"SP{block:05d}H{hard_index}E{easy_index}",
                })
    by_block = {block: {} for block in range(first_block, first_block + block_count)}
    for row in standard:
        by_block[row["block"]].setdefault(row["whole_plot_id"], []).append(row)

    rng = random.Random(f"{_APPEND_BATCH_ID}:{spec.seed}:{first_block}:{block_count}")
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
                               "run_order": run_order_start + len(actual) + 1,
                               "batch_id": _APPEND_BATCH_ID})
    return actual


def _split_plot_columns(spec):
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
    return columns


def _frame_from_layout(spec, actual, columns):
    rows = []
    for item in actual:
        row = {
            "运行ID": f"R{item['standard_order']:05d}",
            "标准序": item["standard_order"], "运行序": item["run_order"],
            "点类型": "factorial", "重复": 1, "区组": item["block"],
            "整区ID": item["whole_plot_id"], "子区ID": item["subplot_id"],
            "整区序": item["whole_plot_order"], "子区序": item["subplot_order"],
        }
        if "batch_id" in columns:
            row[columns["batch_id"]] = item.get("batch_id")
        for factor in spec.factors:
            row[columns["factors"][factor.factor_id]] = factor.from_coded(
                item["coded"][factor.factor_id])
        row.update({name: None for name in columns["responses"].values()})
        rows.append(row)

    frame = pd.DataFrame(rows)
    for name in columns["factors"].values():
        frame[name] = pd.Series([row[name] for row in rows], dtype=object)
    for name in columns["responses"].values():
        frame[name] = pd.array([None] * len(rows), dtype="Float64")
    return frame


def create_split_plot(spec):
    """返回运行表和 DOE-0 元数据。"""
    _, _, actual = _layout(spec)
    columns = _split_plot_columns(spec)
    frame = _frame_from_layout(spec, actual, columns)
    return frame, worksheet_metadata(frame, spec, columns)


def append_split_plot_blocks(frame, metadata, count, *, seed=None):
    """追加一次完整区组批次；校验旧随机化前缀并保留原响应列类型。"""
    design = validate_split_plot_design(frame, metadata)
    spec = design.spec
    if spec.augmentation_lineage is not None:
        raise ValueError("Split-Plot 当前只支持一次区组增补；请从原始设计一次增加所需区组数")
    if metadata.get("design", {}).get("schema_version", spec.schema_version) < 5:
        raise ValueError("DOE Schema v4 不含可验证的增补谱系，不能安全增加 Split-Plot 区组")
    if isinstance(count, bool) or not isinstance(count, int) or count < 1:
        raise ValueError("新增完整区组数必须是正整数")
    if seed is not None:
        if isinstance(seed, bool) or not isinstance(seed, int):
            raise ValueError("seed 必须是整数")
        if seed != spec.seed:
            raise ValueError("增补区组必须沿用原 seed，不能重排已执行运行")
    runs_per_block = 1 << len(spec.factors)
    if len(design.runs) + count * runs_per_block > _MAX_RUNS:
        raise ValueError(f"运行总数不能超过 {_MAX_RUNS}")

    columns = dict(metadata["column_map"])
    if "batch_id" not in columns:
        batch_column = "DOE 批次"
        suffix = 2
        while batch_column in frame.columns:
            batch_column = f"DOE 批次_{suffix}"
            suffix += 1
        columns["batch_id"] = batch_column
    batch_id = columns["batch_id"]
    base = frame.copy(deep=True)
    if batch_id not in base.columns:
        base[batch_id] = pd.Series([None] * len(base), dtype=object)

    appended = _appended_layout(
        spec, spec.block_count + 1, count, run_order_start=len(design.runs))
    added = _frame_from_layout(spec, appended, columns)
    for column in base.columns:
        if column not in added.columns:
            added[column] = None
    added = added[base.columns.tolist()]
    result = pd.concat([base, added], ignore_index=True)
    run_column = columns["run_id"]
    for column in columns["responses"].values():
        values_by_id = dict(zip(frame[run_column], frame[column]))
        values = [values_by_id.get(run_id) for run_id in result[run_column]]
        try:
            result[column] = pd.array(values, dtype=frame[column].dtype)
        except (TypeError, ValueError) as error:
            raise ValueError(
                f"响应列 {column} 无法在保留原类型时为新增运行留空") from error

    digest = hashlib.sha256((
        f"{spec.design_id}\0{metadata['worksheet']['input_fingerprint']}\0{count}"
    ).encode("utf-8")).hexdigest()[:20]
    target_spec = replace(
        spec, design_id=f"SPAPPEND-{digest}", block_count=spec.block_count + count)
    from doe_custom import matrix_sha256
    parent_hash = matrix_sha256(design)
    current = design_from_worksheet(result, target_spec, columns)
    lineage = {
        "parent_design_id": spec.design_id,
        "batch_id": _APPEND_BATCH_ID,
        "criterion": "manual",
        "run_map": [(None, f"R{item['standard_order']:05d}") for item in appended],
        "source_matrix_sha256": parent_hash,
        "current_matrix_sha256": matrix_sha256(current),
    }
    target_spec = replace(target_spec, augmentation_lineage=lineage)
    result_metadata = worksheet_metadata(result, target_spec, columns)
    validate_split_plot_design(result, result_metadata)
    return result, result_metadata


def _validate_layout(spec, runs, actual, batch_id=None):
    if len(runs) != len(actual):
        raise ValueError("Split-Plot 运行数与设计定义不一致")
    by_standard = {run.standard_order: run for run in runs}
    if len(by_standard) != len(runs):
        raise ValueError("Split-Plot 标准序必须唯一")
    for expected in actual:
        run = by_standard[expected["standard_order"]]
        settings = {factor.factor_id: factor.from_coded(
            expected["coded"][factor.factor_id]) for factor in spec.factors}
        identity = (
            run.run_id, run.standard_order, run.run_order, run.point_type,
            run.replicate, run.block, run.whole_plot_id, run.subplot_id,
            run.whole_plot_order, run.subplot_order, run.batch_id,
            run.source_run_id,
        )
        expected_identity = (
            f"R{expected['standard_order']:05d}", expected["standard_order"],
            expected["run_order"], "factorial", 1, expected["block"],
            expected["whole_plot_id"], expected["subplot_id"],
            expected["whole_plot_order"], expected["subplot_order"],
            batch_id, None,
        )
        if identity != expected_identity or dict(run.settings) != settings:
            raise ValueError("Split-Plot 运行身份、标准序或 seed 随机化无效")


def _validate_split_plot_result(result):
    spec = result.spec
    lineage = spec.augmentation_lineage
    if lineage is None:
        _, _, actual = _layout(spec)
        _validate_layout(spec, result.runs, actual)
        return result

    if (lineage["batch_id"] != _APPEND_BATCH_ID
            or lineage["criterion"] != "manual"
            or any(source_id is not None for source_id, _ in lineage["run_map"])):
        raise ValueError("Split-Plot 增补谱系或随机化版本无效")
    runs_per_block = 1 << len(spec.factors)
    if spec.block_count * runs_per_block > _MAX_RUNS:
        raise ValueError(f"运行总数不能超过 {_MAX_RUNS}")
    base_runs = tuple(run for run in result.runs if run.batch_id is None)
    added_runs = tuple(run for run in result.runs if run.batch_id == lineage["batch_id"])
    base_blocks = sorted({run.block for run in base_runs})
    added_blocks = sorted({run.block for run in added_runs})
    base_count = len(base_blocks)
    added_count = spec.block_count - base_count
    if (base_count < 2 or base_blocks != list(range(1, base_count + 1))
            or added_count < 1
            or added_blocks != list(range(base_count + 1, spec.block_count + 1))
            or len(base_runs) != base_count * runs_per_block
            or len(added_runs) != added_count * runs_per_block):
        raise ValueError("Split-Plot 增补必须保留完整父区组，并只追加连续新区组")
    base_spec = replace(
        spec, design_id=lineage["parent_design_id"], block_count=base_count,
        augmentation_lineage=None)
    _, _, base_layout = _layout(base_spec)
    _validate_layout(base_spec, base_runs, base_layout)
    append_layout = _appended_layout(
        base_spec, base_count + 1, added_count, run_order_start=len(base_runs))
    _validate_layout(spec, added_runs, append_layout, batch_id=lineage["batch_id"])
    return result


def validate_split_plot_design(frame, metadata):
    """验证 Split-Plot 标准序、随机化和可追溯的单批次追加前缀。"""
    return _validate_split_plot_result(restore_design_result(frame, metadata))
