"""正规两水平部分因子设计生成及严格结构校验。"""
from dataclasses import replace
from numbers import Integral

import pandas as pd

from doe_core import (
    DesignSpec, randomized_run_order, restore_design_result,
    worksheet_metadata,
)


_MAX_FACTORS = 6
_MAX_RUNS = 10000


def _mask_key(mask, factor_count):
    return mask.bit_count(), tuple(i for i in range(factor_count) if mask & (1 << i))


def _fractional_structure(spec):
    if not isinstance(spec, DesignSpec) or spec.design_type != "two_level_fractional":
        raise ValueError("需要 two_level_fractional 设计定义")
    factors = spec.factors
    factor_ids = tuple(f.factor_id for f in factors)
    count = len(factors)
    if (not 3 <= count <= _MAX_FACTORS
            or factor_ids != tuple(chr(ord("A") + i) for i in range(count))):
        raise ValueError(
            f"部分因子设计需要 3 至 {_MAX_FACTORS} 个因子，ID 必须按 A、B、C… 顺序连续排列")
    if spec.seed is None:
        raise ValueError("随机化必须指定整数 seed")
    if not spec.generators:
        raise ValueError("正规部分因子设计至少需要一个生成元")
    if any(value is not None for value in (
            spec.ccd_alpha, spec.ccd_center_points, spec.ccd_axial_points)):
        raise ValueError("部分因子设计不能包含 CCD 定义")

    parsed = []
    targets = []
    for relation in spec.generators:
        sides = relation.split("=")
        if len(sides) != 2:
            raise ValueError("生成元必须使用单等号形式，例如 D=AB")
        target, rhs = sides
        if (len(target) != 1 or target not in factor_ids or len(rhs) < 2
                or len(set(rhs)) != len(rhs) or any(char not in factor_ids for char in rhs)):
            raise ValueError("生成元必须以一个因子等于至少两个不同因子的乘积")
        targets.append(target)
        parsed.append((target, tuple(rhs)))
    if len(set(targets)) != len(targets):
        raise ValueError("每个生成元必须定义不同的因子")
    target_set = set(targets)
    base_ids = tuple(factor_id for factor_id in factor_ids if factor_id not in target_set)
    if (tuple(targets) != factor_ids[-len(targets):]
            or len(base_ids) < 2
            or any(not set(rhs) <= set(base_ids) for _, rhs in parsed)
            or any(rhs != tuple(sorted(rhs, key=factor_ids.index)) for _, rhs in parsed)):
        raise ValueError("生成元右侧只能引用未生成的基础因子，且至少保留两个基础因子")
    index = {factor_id: i for i, factor_id in enumerate(factor_ids)}
    words = [sum(1 << index[factor_id] for factor_id in (target, *rhs))
             for target, rhs in parsed]
    subgroup = [0]
    for word in words:
        subgroup.extend(mask ^ word for mask in tuple(subgroup))
    if any(mask.bit_count() < 3 for mask in subgroup[1:]):
        raise ValueError("生成元会产生重复列或分辨度 II")

    def word_name(mask):
        return "".join(factor_ids[i] for i in range(count) if mask & (1 << i))

    defining = tuple(
        "I=" + word_name(mask)
        for mask in sorted(subgroup[1:], key=lambda value: _mask_key(value, count))
    )
    remaining = set(range(1, 1 << count))
    aliases = []
    while remaining:
        anchor = min(remaining, key=lambda value: _mask_key(value, count))
        group = sorted({anchor ^ word for word in subgroup},
                       key=lambda value: _mask_key(value, count))
        remaining.difference_update(group)
        if 0 not in group:
            left = word_name(group[0])
            aliases.extend(f"{left}={word_name(member)}" for member in group[1:])

    if spec.defining_relations and spec.defining_relations != defining:
        raise ValueError("DesignSpec.defining_relations 与生成元推导结果不一致")
    if spec.aliases and spec.aliases != tuple(aliases):
        raise ValueError("DesignSpec.aliases 与生成元推导结果不一致")
    return base_ids, parsed, defining, tuple(aliases)


def create_fractional(spec, replicates=1, center_points=0, measured=False):
    """生成 2^(k-p) 运行表，返回 (DataFrame, DOE 元数据)。"""
    base_ids, generators, defining, aliases = _fractional_structure(spec)
    if isinstance(replicates, bool) or not isinstance(replicates, Integral) or replicates < 1:
        raise ValueError("重复数必须是不小于 1 的整数")
    if (isinstance(center_points, bool) or not isinstance(center_points, Integral)
            or center_points != 0):
        raise ValueError("当前部分因子设计不支持中心点，center_points 必须为 0")
    if not isinstance(measured, bool):
        raise ValueError("实测列选项必须是布尔值")

    base_runs = 1 << len(base_ids)
    total = base_runs * int(replicates)
    if total > _MAX_RUNS:
        raise ValueError(f"运行总数不能超过 {_MAX_RUNS}")
    normalized_spec = replace(spec, defining_relations=defining, aliases=aliases)
    columns = {
        "run_id": "运行ID", "standard_order": "标准序", "run_order": "运行序",
        "point_type": "点类型", "replicate": "重复",
        "factors": {f.factor_id: f"设定_{f.factor_id}" for f in spec.factors},
        "measured_levels": {f.factor_id: f"实测_{f.factor_id}" for f in spec.factors}
                           if measured else {},
        "responses": {name: f"响应_{name}" for name in spec.response_names},
    }
    rows = []
    for replicate in range(1, int(replicates) + 1):
        for combination in range(base_runs):
            coded = {
                factor_id: (1 if combination & (1 << i) else -1)
                for i, factor_id in enumerate(base_ids)
            }
            for target, rhs in generators:
                value = 1
                for factor_id in rhs:
                    value *= coded[factor_id]
                coded[target] = value
            levels = [factor.high if coded[factor.factor_id] == 1 else factor.low
                      for factor in spec.factors]
            rows.append(("factorial", replicate, levels))

    run_ids = [f"R{i:05d}" for i in range(1, total + 1)]
    shuffled = randomized_run_order(run_ids, spec.seed)
    positions = {run_id: i for i, run_id in enumerate(run_ids)}
    data = []
    for run_order, run_id in enumerate(shuffled, 1):
        index = positions[run_id]
        point_type, replicate, levels = rows[index]
        row = {"运行ID": run_id, "标准序": index + 1, "运行序": run_order,
               "点类型": point_type, "重复": replicate}
        row.update({columns["factors"][factor.factor_id]: level
                    for factor, level in zip(spec.factors, levels)})
        row.update({name: None for name in columns["measured_levels"].values()})
        row.update({name: None for name in columns["responses"].values()})
        data.append(row)
    frame = pd.DataFrame(data)
    for factor in spec.factors:
        name = columns["factors"][factor.factor_id]
        frame[name] = pd.Series([row[name] for row in data], dtype=object)
    for name in (*columns["measured_levels"].values(), *columns["responses"].values()):
        frame[name] = pd.array([None] * total, dtype="Float64")
    return frame, worksheet_metadata(frame, normalized_spec, columns)


def validate_fractional_design(frame, metadata):
    """恢复 DOE 结构并严格核验生成关系，即使元数据摘要被重新计算也拒绝篡改运行表。"""
    result = restore_design_result(frame, metadata)
    spec = result.spec
    base_ids, generators, defining, aliases = _fractional_structure(spec)
    if spec.defining_relations != defining or spec.aliases != aliases:
        raise ValueError("DOE 别名定义与生成元不一致")
    if len(result.runs) > _MAX_RUNS:
        raise ValueError(f"运行总数不能超过 {_MAX_RUNS}")

    factor_ids = tuple(f.factor_id for f in spec.factors)
    expected_ids = [f"R{i:05d}" for i in range(1, len(result.runs) + 1)]
    expected_run_orders = {
        run_id: order for order, run_id in enumerate(
            randomized_run_order(expected_ids, spec.seed), 1)
    }
    if any(run.run_id != f"R{run.standard_order:05d}" or
           run.run_order != expected_run_orders.get(run.run_id)
           for run in result.runs):
        raise ValueError("运行 ID 或随机运行序与设计 seed 不一致")

    count = 1 << len(base_ids)
    factorial_runs = [run for run in result.runs if run.point_type == "factorial"]
    if len(factorial_runs) != len(result.runs) or any(run.block is not None
                                                       for run in result.runs):
        raise ValueError("当前部分因子设计只支持无中心点、无区组的 factorial 运行")
    replicates = sorted({run.replicate for run in factorial_runs})
    if replicates != list(range(1, len(replicates) + 1)):
        raise ValueError("重复编号必须连续且从 1 开始")
    if len(factorial_runs) != count * len(replicates):
        raise ValueError("每次重复必须包含且仅包含全部基础因子组合")

    factor_map = {factor.factor_id: factor for factor in spec.factors}
    target_map = dict(generators)
    seen = {replicate: set() for replicate in replicates}
    for run in factorial_runs:
        coded = {factor_id: factor_map[factor_id].to_coded(run.settings[factor_id])
                 for factor_id in factor_ids}
        if any(coded[factor_id] not in (-1, 1) for factor_id in factor_ids):
            raise ValueError("因子点必须恰为低或高水平")
        combination = sum(1 << i for i, factor_id in enumerate(base_ids)
                          if coded[factor_id] == 1)
        if combination in seen[run.replicate]:
            raise ValueError("每次重复不能包含重复的基础因子组合")
        seen[run.replicate].add(combination)
        expected_standard = (run.replicate - 1) * count + combination + 1
        if run.standard_order != expected_standard:
            raise ValueError("标准序与基础因子组合不一致")
        for target, rhs in target_map.items():
            expected = 1
            for factor_id in rhs:
                expected *= coded[factor_id]
            if coded[target] != expected:
                raise ValueError(f"运行值不满足生成元 {target}={''.join(rhs)}")
    if any(combinations != set(range(count)) for combinations in seen.values()):
        raise ValueError("每次重复必须包含且仅包含全部基础因子组合")

    return result
