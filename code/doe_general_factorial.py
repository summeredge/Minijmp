"""分类一般全因子设计生成与结构验证。"""
from itertools import product
from math import prod
from numbers import Integral
import random

import pandas as pd

from doe_core import DesignSpec, randomized_run_order, restore_design_result, worksheet_metadata


_MAX_RUNS = 10000
_MIN_FACTORS = 2
_MAX_FACTORS = 10


def _combinations(factors):
    levels = [factor.levels for factor in factors]
    count = prod(map(len, levels))
    for index in range(count):
        quotient, values = index, []
        for choices in levels:
            values.append(choices[quotient % len(choices)])
            quotient //= len(choices)
        yield tuple(values)


def _typed_key(values):
    return tuple(("text" if isinstance(value, str) else "numeric", value)
                 for value in values)


def _ordered_run_ids(replicates, run_count, seed, blocks):
    ids = [f"R{i:05d}" for i in range(1, replicates * run_count + 1)]
    if blocks is None:
        return randomized_run_order(ids, seed)
    rng = random.Random(int(seed))
    per_block = [ids[i * run_count:(i + 1) * run_count]
                 for i in range(replicates)]
    order = list(range(replicates))
    rng.shuffle(order)
    result = []
    for block in order:
        rows = per_block[block].copy()
        rng.shuffle(rows)
        result.extend(rows)
    return tuple(result)


def _check_factor_count(factors):
    if not _MIN_FACTORS <= len(factors) <= _MAX_FACTORS:
        raise ValueError(f"一般全因子设计需要 {_MIN_FACTORS}–{_MAX_FACTORS} 个分类因子")


def create_general_factorial(spec, replicates=1, measured=False):
    """生成 categorical full factorial；区组只允许完整重复作为区组。"""
    if not isinstance(spec, DesignSpec) or spec.design_type != "general_full_factorial":
        raise ValueError("需要 general_full_factorial 设计定义")
    if not spec.factors or any(factor.factor_type != "categorical" for factor in spec.factors):
        raise ValueError("一般全因子设计的所有因子都必须是分类因子")
    _check_factor_count(spec.factors)
    if spec.seed is None:
        raise ValueError("随机化必须指定整数 seed")
    if spec.generators or spec.defining_relations or spec.aliases or any(
            value is not None for value in (spec.ccd_alpha, spec.ccd_center_points,
                                            spec.ccd_axial_points, spec.ccd_fraction)):
        raise ValueError("一般全因子设计不能包含生成元或 CCD 定义")
    if isinstance(replicates, bool) or not isinstance(replicates, Integral) or replicates < 1:
        raise ValueError("重复数必须是不小于 1 的整数")
    if not isinstance(measured, bool):
        raise ValueError("实测列选项必须是布尔值")
    if spec.block_count is not None and (spec.block_count < 2 or spec.block_count != replicates):
        raise ValueError("区组模式只支持每个完整重复作为一个区组")
    if ((spec.block_count is None and spec.randomization_unit != "run")
            or (spec.block_count is not None and spec.randomization_unit != "block")):
        raise ValueError("一般全因子随机化单位必须与完整重复区组设置一致")
    combination_count = prod(len(factor.levels) for factor in spec.factors)
    run_count = combination_count * int(replicates)
    if run_count > _MAX_RUNS:
        raise ValueError(f"运行总数超过 {_MAX_RUNS}，设计尚未生成")
    combinations = list(_combinations(spec.factors))

    columns = {
        "run_id": "运行ID", "standard_order": "标准序", "run_order": "运行序",
        "point_type": "点类型", "replicate": "重复",
        "factors": {factor.factor_id: f"设定_{factor.factor_id}" for factor in spec.factors},
        "measured_levels": ({factor.factor_id: f"实测_{factor.factor_id}"
                             for factor in spec.factors} if measured else {}),
        "responses": {name: f"响应_{name}" for name in spec.response_names},
    }
    if spec.block_count is not None:
        columns["block"] = "区组"
    rows = []
    for replicate in range(1, int(replicates) + 1):
        for values in combinations:
            rows.append((replicate, values))
    run_ids = [f"R{i:05d}" for i in range(1, run_count + 1)]
    shuffled = _ordered_run_ids(int(replicates), len(combinations), spec.seed,
                                 spec.block_count)
    positions = {run_id: index for index, run_id in enumerate(run_ids)}
    data = []
    for run_order, run_id in enumerate(shuffled, 1):
        index = positions[run_id]
        replicate, values = rows[index]
        row = {"运行ID": run_id, "标准序": index + 1, "运行序": run_order,
               "点类型": "factorial", "重复": replicate}
        if spec.block_count is not None:
            row["区组"] = f"B{replicate}"
        row.update({columns["factors"][factor.factor_id]: value
                    for factor, value in zip(spec.factors, values)})
        row.update({name: None for name in columns["measured_levels"].values()})
        row.update({name: None for name in columns["responses"].values()})
        data.append(row)
    frame = pd.DataFrame(data)
    for name in columns["factors"].values():
        frame[name] = pd.Series([row[name] for row in data], dtype=object)
    if spec.block_count is not None:
        frame["区组"] = pd.Series([row["区组"] for row in data], dtype=object)
    for name in (*columns["measured_levels"].values(), *columns["responses"].values()):
        frame[name] = pd.array([None] * run_count, dtype="Float64")
    return frame, worksheet_metadata(frame, spec, columns)


def validate_general_factorial(frame, metadata):
    result = restore_design_result(frame, metadata)
    spec = result.spec
    if spec.design_type != "general_full_factorial" or spec.seed is None:
        raise ValueError("需要有 seed 的 General Full Factorial 设计")
    if any(f.factor_type != "categorical" for f in spec.factors):
        raise ValueError("一般全因子设计只能包含分类因子")
    _check_factor_count(spec.factors)
    levels = list(_combinations(spec.factors))
    standard_indices = {_typed_key(values): index for index, values in enumerate(levels)}
    if len(result.runs) > _MAX_RUNS:
        raise ValueError(f"运行总数不能超过 {_MAX_RUNS}")
    groups = {}
    for run in result.runs:
        if run.point_type != "factorial":
            raise ValueError("一般全因子设计只能包含 factorial 运行")
        groups.setdefault(run.replicate, []).append(run)
    replicates = sorted(groups)
    if replicates != list(range(1, len(replicates) + 1)):
        raise ValueError("重复编号必须连续且从 1 开始")
    expected = {_typed_key(values) for values in levels}
    for replicate, runs in groups.items():
        observed = [_typed_key(tuple(run.settings[f.factor_id] for f in spec.factors))
                    for run in runs]
        if len(observed) != len(expected) or set(observed) != expected:
            raise ValueError(f"重复 {replicate} 必须包含每个分类组合且仅包含一次")
        for run in runs:
            canonical = _typed_key(tuple(run.settings[f.factor_id] for f in spec.factors))
            standard_index = standard_indices[canonical]
            if run.standard_order != (replicate - 1) * len(levels) + standard_index + 1:
                raise ValueError("标准序与因子水平组合不一致")
    block_count = spec.block_count
    if block_count is None:
        if any(run.block is not None for run in result.runs):
            raise ValueError("设计未声明区组，不得包含区组")
        expected_order = randomized_run_order(
            [f"R{i:05d}" for i in range(1, len(result.runs) + 1)], spec.seed)
    else:
        if len(replicates) != block_count or any(
                run.block != f"B{run.replicate}" for run in result.runs):
            raise ValueError("区组必须各自包含一个完整重复")
        expected_order = _ordered_run_ids(len(replicates), len(levels), spec.seed,
                                          block_count)
    expected_orders = {run_id: order for order, run_id in enumerate(expected_order, 1)}
    if any(run.run_id != f"R{run.standard_order:05d}"
           or run.run_order != expected_orders.get(run.run_id) for run in result.runs):
        raise ValueError("运行 ID 或随机运行序与设计 seed 不一致")
    return result
