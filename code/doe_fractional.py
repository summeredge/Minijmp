"""正规两水平部分因子设计生成及严格结构校验。"""
from dataclasses import replace
from math import prod
from numbers import Integral
import random

import pandas as pd

from doe_core import (
    DesignSpec, foldover_matrix_fingerprint, randomized_run_order, restore_design_result,
    worksheet_metadata,
)


_MAX_FACTORS = 6
_MAX_RUNS = 10000


def _blocked_order(run_groups, seed):
    rng = random.Random(int(seed))
    blocks = list(run_groups)
    rng.shuffle(blocks)
    result = []
    for block in blocks:
        runs = run_groups[block].copy()
        rng.shuffle(runs)
        result.extend(runs)
    return tuple(result)


def _mask_key(mask, factor_count):
    return mask.bit_count(), tuple(i for i in range(factor_count) if mask & (1 << i))


def _fractional_structure(spec, *, verify_identity=True):
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
        target, raw_rhs = sides
        sign = -1 if raw_rhs.startswith("-") else 1
        rhs = raw_rhs[1:] if sign < 0 else raw_rhs
        if (len(target) != 1 or target not in factor_ids or len(rhs) < 2
                or len(set(rhs)) != len(rhs) or any(char not in factor_ids for char in rhs)):
            raise ValueError("生成元必须以一个因子等于至少两个不同因子的乘积")
        targets.append(target)
        parsed.append((target, tuple(rhs), sign))
    if len(set(targets)) != len(targets):
        raise ValueError("每个生成元必须定义不同的因子")
    target_set = set(targets)
    base_ids = tuple(factor_id for factor_id in factor_ids if factor_id not in target_set)
    if (tuple(targets) != factor_ids[-len(targets):]
            or len(base_ids) < 2
            or any(not set(rhs) <= set(base_ids) for _, rhs, _ in parsed)
            or any(rhs != tuple(sorted(rhs, key=factor_ids.index))
                   for _, rhs, _ in parsed)):
        raise ValueError("生成元右侧只能引用未生成的基础因子，且至少保留两个基础因子")
    index = {factor_id: i for i, factor_id in enumerate(factor_ids)}
    words = [(sum(1 << index[factor_id] for factor_id in (target, *rhs)), sign)
             for target, rhs, sign in parsed]
    signed_subgroup = [(0, 1)]
    for word, sign in words:
        signed_subgroup.extend((mask ^ word, relation_sign * sign)
                               for mask, relation_sign in tuple(signed_subgroup))
    if any(mask.bit_count() < 3 for mask, _ in signed_subgroup[1:]):
        raise ValueError("生成元会产生重复列或分辨度 II")

    def word_name(mask):
        return "".join(factor_ids[i] for i in range(count) if mask & (1 << i))

    defining = tuple(
        "I=" + ("-" if sign < 0 else "") + word_name(mask)
        for mask, sign in sorted(signed_subgroup[1:],
                                 key=lambda value: _mask_key(value[0], count))
    )
    remaining = set(range(1, 1 << count))
    aliases = []
    while remaining:
        anchor = min(remaining, key=lambda value: _mask_key(value, count))
        group = sorted(((anchor ^ word, sign) for word, sign in signed_subgroup),
                       key=lambda value: _mask_key(value[0], count))
        remaining.difference_update(mask for mask, _ in group)
        if 0 not in {mask for mask, _ in group}:
            left = word_name(anchor)
            aliases.extend(f"{left}={'-' if sign < 0 else ''}{word_name(member)}"
                           for member, sign in group if member != anchor)

    if verify_identity and spec.defining_relations and spec.defining_relations != defining:
        raise ValueError("DesignSpec.defining_relations 与生成元推导结果不一致")
    if verify_identity and spec.aliases and spec.aliases != tuple(aliases):
        raise ValueError("DesignSpec.aliases 与生成元推导结果不一致")
    return base_ids, parsed, defining, tuple(aliases)


def _matrix_structure(coded_rows, factor_ids):
    """从实际 ±1 点矩阵推导当前定义关系与带符号别名。"""
    rows = tuple(sorted(set(tuple(row) for row in coded_rows)))
    if not rows or any(len(row) != len(factor_ids) or any(value not in (-1, 1)
                                                           for value in row)
                       for row in rows):
        raise ValueError("正规部分因子矩阵必须由完整的 ±1 运行点组成")
    count = len(factor_ids)
    columns = {}
    groups = {}
    for mask in range(1 << count):
        values = tuple(
            prod(row[index] for index in range(count) if mask & (1 << index))
            for row in rows)
        sign = values[0]
        key = tuple(sign * value for value in values)
        columns[mask] = values
        groups.setdefault(key, []).append((mask, sign))

    word = lambda mask: "".join(factor_ids[i] for i in range(count)
                                if mask & (1 << i))
    defining = tuple(
        "I=" + ("-" if values[0] < 0 else "") + word(mask)
        for mask, values in sorted(columns.items(), key=lambda item: _mask_key(item[0], count))
        if mask and len(set(values)) == 1
    )
    aliases = []
    for members in sorted(groups.values(),
                          key=lambda group: min(_mask_key(mask, count)
                                               for mask, _ in group)):
        masks = sorted((mask for mask, _ in members),
                       key=lambda value: _mask_key(value, count))
        if 0 in masks:
            continue
        anchor = masks[0]
        for member in masks[1:]:
            sign = columns[anchor][0] * columns[member][0]
            aliases.append(f"{word(anchor)}={'-' if sign < 0 else ''}{word(member)}")
    return defining, tuple(aliases)


def create_fractional(spec, replicates=1, center_points=0, measured=False):
    """生成 2^(k-p) 运行表，返回 (DataFrame, DOE 元数据)。"""
    base_ids, generators, defining, aliases = _fractional_structure(spec)
    if isinstance(replicates, bool) or not isinstance(replicates, Integral) or replicates < 1:
        raise ValueError("重复数必须是不小于 1 的整数")
    if (isinstance(center_points, bool) or not isinstance(center_points, Integral)
            or center_points < 0):
        raise ValueError("中心点数必须是不小于 0 的整数")
    if spec.center_point_count not in (None, int(center_points)):
        raise ValueError("center_point_count 与中心点数参数不一致")
    if not isinstance(measured, bool):
        raise ValueError("实测列选项必须是布尔值")
    blocked = spec.block_count is not None
    if ((blocked and (spec.block_count < 2 or spec.block_count != replicates
                      or spec.randomization_unit != "block"))
            or (not blocked and spec.randomization_unit != "run")):
        raise ValueError("区组设计只支持每个完整重复作为一个区组")
    if blocked and center_points % replicates:
        raise ValueError("区组中心点必须平均分配到每个完整重复")

    base_runs = 1 << len(base_ids)
    total = base_runs * int(replicates) + int(center_points)
    if total > _MAX_RUNS:
        raise ValueError(f"运行总数不能超过 {_MAX_RUNS}")
    normalized_spec = replace(spec, defining_relations=defining, aliases=aliases,
                              center_point_count=int(center_points))
    columns = {
        "run_id": "运行ID", "standard_order": "标准序", "run_order": "运行序",
        "point_type": "点类型", "replicate": "重复",
        "block": "区组" if blocked else None,
        "factors": {f.factor_id: f"设定_{f.factor_id}" for f in spec.factors},
        "measured_levels": {f.factor_id: f"实测_{f.factor_id}" for f in spec.factors}
                           if measured else {},
        "responses": {name: f"响应_{name}" for name in spec.response_names},
    }
    rows = []
    centers = None
    centers_per_block = int(center_points) // int(replicates) if blocked else 0
    if center_points:
        from doe_core import _number
        centers = [_number(factor.from_coded(0), "中心点水平") for factor in spec.factors]
    for replicate in range(1, int(replicates) + 1):
        for combination in range(base_runs):
            coded = {
                factor_id: (1 if combination & (1 << i) else -1)
                for i, factor_id in enumerate(base_ids)
            }
            for target, rhs, sign in generators:
                value = sign
                for factor_id in rhs:
                    value *= coded[factor_id]
                coded[target] = value
            levels = [factor.high if coded[factor.factor_id] == 1 else factor.low
                      for factor in spec.factors]
            rows.append(("factorial", replicate, levels))
        if blocked:
            rows.extend(("center", replicate, centers)
                        for _ in range(centers_per_block))
    if center_points and not blocked:
        rows.extend(("center", 1, centers) for _ in range(int(center_points)))

    run_ids = [f"R{i:05d}" for i in range(1, total + 1)]
    if blocked:
        grouped_ids = {}
        for run_id, (_, replicate, _) in zip(run_ids, rows):
            grouped_ids.setdefault(replicate, []).append(run_id)
        shuffled = _blocked_order(grouped_ids, spec.seed)
        columns["block"] = "区组"
    else:
        shuffled = randomized_run_order(run_ids, spec.seed)
    positions = {run_id: i for i, run_id in enumerate(run_ids)}
    data = []
    for run_order, run_id in enumerate(shuffled, 1):
        index = positions[run_id]
        point_type, replicate, levels = rows[index]
        row = {"运行ID": run_id, "标准序": index + 1, "运行序": run_order,
               "点类型": point_type, "重复": replicate}
        if blocked:
            row["区组"] = f"B{replicate}"
        row.update({columns["factors"][factor.factor_id]: level
                    for factor, level in zip(spec.factors, levels)})
        row.update({name: None for name in columns["measured_levels"].values()})
        row.update({name: None for name in columns["responses"].values()})
        data.append(row)
    frame = pd.DataFrame(data)
    for factor in spec.factors:
        name = columns["factors"][factor.factor_id]
        frame[name] = pd.Series([row[name] for row in data], dtype=object)
    if blocked:
        frame["区组"] = pd.Series([row["区组"] for row in data], dtype=object)
    for name in (*columns["measured_levels"].values(), *columns["responses"].values()):
        frame[name] = pd.array([None] * total, dtype="Float64")
    return frame, worksheet_metadata(frame, normalized_spec, columns)


def validate_fractional_design(frame, metadata):
    """恢复 DOE 结构并严格核验生成关系，即使元数据摘要被重新计算也拒绝篡改运行表。"""
    result = restore_design_result(frame, metadata)
    spec = result.spec
    lineage = spec.foldover_lineage
    base_ids, generators, base_defining, base_aliases = _fractional_structure(
        spec, verify_identity=lineage is None)
    if lineage is None and (spec.defining_relations != base_defining
                            or spec.aliases != base_aliases):
        raise ValueError("DOE 别名定义与生成元不一致")
    if len(result.runs) > _MAX_RUNS:
        raise ValueError(f"运行总数不能超过 {_MAX_RUNS}")

    factor_ids = tuple(f.factor_id for f in spec.factors)
    base_runs = ([run for run in result.runs if run.batch_id == "BASE"]
                 if lineage is not None else list(result.runs))
    added_runs = ([run for run in result.runs
                   if run.batch_id == lineage["batch_id"]]
                  if lineage is not None else [])
    if lineage is None and any(run.batch_id is not None or run.source_run_id is not None
                               for run in result.runs):
        raise ValueError("没有 Foldover 谱系的设计不能包含批次或来源运行字段")
    if lineage is not None and (
            len(base_runs) + len(added_runs) != len(result.runs)
            or any(run.source_run_id is not None for run in base_runs)):
        raise ValueError("Foldover 仅支持一份原始批次和一个新增批次")

    base_runs_by_order = sorted(base_runs, key=lambda run: run.standard_order)
    base_count = len(base_runs)
    if [run.standard_order for run in base_runs_by_order] != list(range(1, base_count + 1)):
        raise ValueError("原始批次标准序必须连续且保持不变")
    expected_ids = [f"R{i:05d}" for i in range(1, base_count + 1)]
    blocked = spec.block_count is not None and lineage is None
    if lineage is not None:
        if spec.block_count is not None or any(run.block is not None for run in result.runs):
            raise ValueError("当前 Foldover 不支持区组设计")
        expected_ids_order = randomized_run_order(expected_ids, spec.seed)
    elif blocked:
        factorial_replicates = sorted({run.replicate for run in base_runs
                                       if run.point_type == "factorial"})
        if (spec.randomization_unit != "block" or spec.block_count < 2
                or spec.block_count != len(factorial_replicates)
                or any(run.block != f"B{run.replicate}" for run in base_runs)):
            raise ValueError("区组必须各自包含一个完整部分因子重复")
        grouped_ids = {
            replicate: [run.run_id for run in base_runs_by_order
                        if run.replicate == replicate]
            for replicate in factorial_replicates
        }
        expected_ids_order = _blocked_order(grouped_ids, spec.seed)
    else:
        if spec.randomization_unit != "run" or any(run.block is not None for run in base_runs):
            raise ValueError("没有声明区组的部分因子设计不得包含区组")
        expected_ids_order = randomized_run_order(expected_ids, spec.seed)
    expected_run_orders = {run_id: order for order, run_id in enumerate(expected_ids_order, 1)}
    if any(run.run_id != f"R{run.standard_order:05d}" or
           run.run_order != expected_run_orders.get(run.run_id)
           for run in base_runs):
        raise ValueError("原始运行 ID 或随机运行序与设计 seed 不一致")
    if lineage is not None:
        if any(run.batch_id != "BASE" for run in base_runs):
            raise ValueError("Foldover 原始运行必须属于 BASE 批次")
        folded_factors = lineage["folded_factors"]
        if folded_factors != tuple(key for key in factor_ids if key in folded_factors):
            raise ValueError("Foldover 因子顺序与设计因子顺序不一致")
        additions_by_order = sorted(added_runs, key=lambda run: run.standard_order)
        if (len(additions_by_order) != sum(run.point_type == "factorial"
                                          for run in base_runs)
                or [run.standard_order for run in additions_by_order]
                != list(range(base_count + 1, base_count + len(additions_by_order) + 1))):
            raise ValueError("Foldover 新增批次必须逐原始因子运行生成，且标准序连续追加")
        expected_new_ids = [f"F{i:05d}" for i in range(1, len(additions_by_order) + 1)]
        expected_new_order = {
            run_id: base_count + order for order, run_id in enumerate(
                randomized_run_order(expected_new_ids, spec.seed), 1)
        }
        if any(run.run_id != f"F{run.standard_order - base_count:05d}"
               or run.batch_id != lineage["batch_id"]
               or run.run_order != expected_new_order.get(run.run_id)
               for run in additions_by_order):
            raise ValueError("Foldover 新增运行 ID、批次或随机顺序无效")
        if lineage["parent_design_id"] == spec.design_id:
            raise ValueError("Foldover 父设计不能与当前设计相同")

    count = 1 << len(base_ids)
    factorial_runs = [run for run in base_runs if run.point_type == "factorial"]
    centers = [run for run in base_runs if run.point_type == "center"]
    center_count = spec.center_point_count or 0
    if (len(factorial_runs) + len(centers) != len(result.runs)
            and lineage is None) or len(factorial_runs) + len(centers) != len(base_runs):
        raise ValueError("部分因子设计只允许因子运行及声明数量的中心点")
    if len(centers) != center_count:
        raise ValueError("部分因子设计的中心点数与设计声明不一致")
    replicates = sorted({run.replicate for run in factorial_runs})
    if replicates != list(range(1, len(replicates) + 1)):
        raise ValueError("重复编号必须连续且从 1 开始")
    if len(factorial_runs) != count * len(replicates):
        raise ValueError("每次重复必须包含且仅包含全部基础因子组合")
    center_levels = {factor.factor_id: factor.from_coded(0) for factor in spec.factors}
    if blocked:
        if center_count % len(replicates):
            raise ValueError("区组中心点必须平均分配到每个完整重复")
        centers_per_block = center_count // len(replicates)
        for replicate in replicates:
            group = sorted((run for run in centers if run.replicate == replicate),
                           key=lambda item: item.standard_order)
            start = (replicate - 1) * (count + centers_per_block) + count + 1
            if ([run.standard_order for run in group]
                    != list(range(start, start + centers_per_block))
                    or any(any(run.settings[f.factor_id] != center_levels[f.factor_id]
                               for f in spec.factors) for run in group)):
                raise ValueError("每个区组中心点必须在本区组因子点之后且位于中点")
    else:
        for index, run in enumerate(sorted(centers, key=lambda item: item.standard_order), 1):
            if (run.standard_order != count * len(replicates) + index
                    or run.replicate != 1
                    or any(run.settings[f.factor_id] != center_levels[f.factor_id]
                           for f in spec.factors)):
                raise ValueError("中心点必须按标准序追加且位于所有因子的中点")

    factor_map = {factor.factor_id: factor for factor in spec.factors}
    target_map = {target: (rhs, sign) for target, rhs, sign in generators}
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
        expected_standard = (
            (run.replicate - 1) * (count + center_count // len(replicates))
            + combination + 1 if blocked else
            (run.replicate - 1) * count + combination + 1)
        if run.standard_order != expected_standard:
            raise ValueError("标准序与基础因子组合不一致")
        for target, (rhs, sign) in target_map.items():
            expected = sign
            for factor_id in rhs:
                expected *= coded[factor_id]
            if coded[target] != expected:
                raise ValueError(f"运行值不满足生成元 {target}={''.join(rhs)}")
    if any(combinations != set(range(count)) for combinations in seen.values()):
        raise ValueError("每次重复必须包含且仅包含全部基础因子组合")

    if lineage is None:
        if (spec.defining_relations != base_defining or spec.aliases != base_aliases):
            raise ValueError("DOE 别名定义与生成元不一致")
        return result

    run_by_id = {run.run_id: run for run in result.runs}
    mapping = dict(lineage["run_map"])
    if (len(mapping) != len(factorial_runs)
            or set(mapping) != {run.run_id for run in factorial_runs}
            or set(mapping.values()) != {run.run_id for run in added_runs}):
        raise ValueError("Foldover 运行映射必须覆盖每个原始因子运行且一一对应")
    for source_id, addition_id in lineage["run_map"]:
        source, addition = run_by_id.get(source_id), run_by_id.get(addition_id)
        if (source is None or addition is None or source.point_type != "factorial"
                or addition.source_run_id != source_id
                or addition.replicate != source.replicate
                or addition.point_type != "factorial"):
            raise ValueError("Foldover 谱系与运行批次映射不一致")
        for factor in spec.factors:
            expected = source.settings[factor.factor_id]
            if factor.factor_id in lineage["folded_factors"]:
                expected = factor.low if expected == factor.high else factor.high
            if addition.settings[factor.factor_id] != expected:
                raise ValueError("Foldover 新运行与指定因子的反转不一致")
    source_hash = foldover_matrix_fingerprint(base_runs, spec.factors)
    current_hash = foldover_matrix_fingerprint((*base_runs, *added_runs), spec.factors)
    if (source_hash != lineage["source_matrix_sha256"]
            or current_hash != lineage["current_matrix_sha256"]):
        raise ValueError("Foldover 原始或当前模型矩阵摘要不匹配")
    coded = [tuple(int(factor_map[key].to_coded(run.settings[key])) for key in factor_ids)
             for run in (*factorial_runs, *added_runs)]
    current_defining, current_aliases = _matrix_structure(coded, factor_ids)
    if (spec.defining_relations != current_defining or spec.aliases != current_aliases):
        raise ValueError("Foldover 当前别名与实际运行矩阵不一致")

    return result
