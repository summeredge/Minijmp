"""Taguchi 静态/动态设计工作表生成：控制×噪声×信号×重复完整网格。"""
import random

import pandas as pd

from doe_core import DesignSpec, taguchi_grid, worksheet_metadata


_MAX_RUNS = 10000


def _plan(spec):
    """按标准序展开完整网格；返回 (行, 控制运行数)。"""
    if not isinstance(spec, DesignSpec) or spec.design_type != "taguchi":
        raise ValueError("需要 taguchi 设计定义")
    if spec.schema_version != 5:
        raise ValueError("Taguchi 需要 schema v5")
    if spec.seed is None:
        raise ValueError("随机化必须指定整数 seed")
    if spec.block_count is not None or spec.generators or spec.defining_relations:
        raise ValueError("Taguchi 暂不支持区组或生成元")
    grid = taguchi_grid(spec)
    array, noise_rows = grid["array"], grid["noise"]
    levels = grid["signal_levels"] or (None,)
    total = len(array.matrix) * len(noise_rows) * len(levels)
    if total > _MAX_RUNS:
        raise ValueError(f"运行总数不能超过 {_MAX_RUNS}")
    control_ids = [f"C{index:05d}" for index in range(1, len(array.matrix) + 1)]
    rows = []
    for control_index, control_row in enumerate(array.matrix, 1):
        for noise_index, noise_row in enumerate(noise_rows, 1):
            for signal_level in levels:
                settings = {
                    factor_id: grid["factors"][factor_id].levels[
                        control_row[column - 1] - 1]
                    for factor_id, column in grid["columns"].items()}
                settings.update({
                    factor_id: grid["factors"][factor_id].levels[
                        noise_row[index] - 1]
                    for index, (factor_id, _) in
                    enumerate(sorted(grid["noise_columns"].items()))})
                if grid["signal_levels"]:
                    settings[spec.taguchi["signal_factor"]] = signal_level
                rows.append({
                    "standard_order": len(rows) + 1,
                    "control_run_id": control_ids[control_index - 1],
                    "noise_condition_id": "N" + "".join(
                        str(grid["factors"][factor_id].levels.index(
                            settings[factor_id]) + 1)
                        for factor_id in sorted(grid["noise_columns"])),
                    "settings": settings,
                })
    return rows, len(array.matrix), len(noise_rows), len(levels)


def create_taguchi(spec, replicates=1):
    """返回随机化工作表与 DOE 元数据；重复为整张网格的独立重复。"""
    if isinstance(replicates, bool) or not isinstance(replicates, int) or replicates < 1:
        raise ValueError("重复数必须是正整数")
    rows, control_count, noise_count, signal_count = _plan(spec)
    if len(rows) * replicates > _MAX_RUNS:
        raise ValueError(f"运行总数不能超过 {_MAX_RUNS}")
    columns = {
        "run_id": "运行ID", "standard_order": "标准序", "run_order": "运行序",
        "point_type": "点类型", "replicate": "重复",
        "control_run_id": "控制运行", "noise_condition_id": "噪声条件",
        "factors": {factor.factor_id: f"设定_{factor.factor_id}"
                    for factor in spec.factors},
        "responses": {name: f"响应_{name}" for name in spec.response_names},
    }
    run_ids = [f"R{index:05d}" for index in range(1, len(rows) * replicates + 1)]
    rng = random.Random(spec.seed)
    rng.shuffle(run_ids)
    records, frame_rows = [], []
    for order, run_id in enumerate(run_ids, 1):
        position = (int(run_id[1:]) - 1) % len(rows)
        replicate = (int(run_id[1:]) - 1) // len(rows) + 1
        plan = rows[position]
        frame_rows.append({
            "运行ID": run_id, "标准序": position * replicates + replicate,
            "运行序": order, "点类型": "taguchi",
            "重复": replicate, "控制运行": plan["control_run_id"],
            "噪声条件": f'{plan["noise_condition_id"]}R{replicate}',
            **{columns["factors"][key]: value
               for key, value in plan["settings"].items()},
            **{name: None for name in columns["responses"].values()},
        })
        records.append((run_id, plan, replicate))
    frame = pd.DataFrame(frame_rows)
    for name in columns["factors"].values():
        frame[name] = pd.Series([row[name] for row in frame_rows], dtype=object)
    for name in columns["responses"].values():
        frame[name] = pd.array([None] * len(frame), dtype="Float64")
    metadata = worksheet_metadata(frame, spec, columns)
    return frame, metadata

