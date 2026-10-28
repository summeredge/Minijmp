"""中心复合设计生成与设计矩阵校验。"""
from collections import Counter
from dataclasses import replace
from fractions import Fraction
from itertools import product
from numbers import Integral
import math

import pandas as pd

from doe_core import (DesignSpec, category_combinations, randomized_run_order,
                      worksheet_metadata)

_CCD_CODE_TOLERANCE = Fraction(1, 100_000_000)
_MAX_RUNS = 10000
_FRACTION_FACTORS = {
    'full': (2, 7), 'half': (5, 8), 'quarter': (8, 9), 'eighth': (10, 10),
}
# (连续因子数, 分数) -> {区组数: (立方块数, 立方中心点, 轴中心点)}
_BLOCKS = {
    (2, 'full'): {2: (1, 3, 3)},
    (3, 'full'): {2: (1, 4, 2), 3: (2, 4, 2)},
    (4, 'full'): {2: (1, 4, 2), 3: (2, 4, 2)},
    (5, 'full'): {2: (1, 8, 4), 3: (2, 8, 4)},
    (6, 'full'): {2: (1, 8, 6), 3: (2, 8, 6), 5: (4, 8, 6)},
    (7, 'full'): {2: (1, 8, 10), 3: (2, 8, 10), 5: (4, 8, 10)},
    (5, 'half'): {2: (1, 6, 1)},
    (6, 'half'): {2: (1, 8, 2), 3: (2, 8, 2)},
    (7, 'half'): {2: (1, 8, 4), 3: (2, 8, 4)},
    (8, 'half'): {2: (1, 8, 8), 3: (2, 8, 8), 5: (4, 8, 8)},
    (8, 'quarter'): {2: (1, 8, 2)},
    (9, 'quarter'): {2: (1, 8, 6), 3: (2, 8, 6)},
    (10, 'eighth'): {2: (1, 8, 4)},
}


def _coded_level(factor, actual):
    low, high = Fraction(factor.low), Fraction(factor.high)
    return 2 * (Fraction(actual) - low) / (high - low) - 1


def _center_level(factor):
    center = factor.from_coded(0)
    if isinstance(center, Fraction):
        try:
            center = float(center)
        except OverflowError as error:
            raise ValueError('中心点超出浮点数范围') from error
    if (isinstance(center, float) and not math.isfinite(center)) or not factor.low < center < factor.high:
        raise ValueError('中心点因浮点精度不足无法与低高水平区分')
    if abs(_coded_level(factor, center)) > _CCD_CODE_TOLERANCE:
        raise ValueError('中心点舍入后无法保持 CCD 编码精度')
    return center


def axial_levels(factor, alpha):
    """返回按存储水平计算并舍入到 float64 的轴点。"""
    low, high = factor.low, factor.high
    try:
        if any(isinstance(v, int) and int(float(v)) != v for v in (low, high)):
            raise ValueError('因子水平不能无损表示为浮点数')
    except OverflowError as error:
        raise ValueError('因子水平超出浮点数范围') from error
    center = _center_level(factor)
    if alpha == 1:
        return low, high
    low_exact, high_exact = Fraction(low), Fraction(high)
    center_exact = (low_exact + high_exact) / 2
    offset = Fraction(alpha) * (high_exact - low_exact) / 2
    try:
        levels = (float(center_exact - offset), float(center_exact + offset))
    except OverflowError as error:
        raise ValueError('轴点超出有限数值范围') from error
    if not all(math.isfinite(v) for v in levels) or not levels[0] < center < levels[1]:
        raise ValueError('轴点超出有限数值范围或因精度不足无法区分')
    if alpha > 1 and (levels[0] >= low or levels[1] <= high):
        raise ValueError('CCC 轴点舍入后未超出低高水平')
    if any(abs(_coded_level(factor, level) - Fraction(sign * alpha)) > _CCD_CODE_TOLERANCE
           for level, sign in zip(levels, (-1, 1))):
        raise ValueError('CCC 轴点舍入后无法保持 CCD 编码精度')
    return levels


def _extended(spec):
    """是否走扩展路径：分数设计、区组、分类因子或 2-5 因子之外的 CC 设计。"""
    continuous = sum(f.factor_type == "continuous" for f in spec.factors)
    return (spec.ccd_fraction not in (None, "full")
            or spec.block_count not in (None, 1)
            or any(factor.factor_type == "categorical" for factor in spec.factors)
            or spec.ccd_alpha is None
            or continuous > 5)


def cube_rows(k, fraction):
    """立方部分；分数设计用互不相交的相邻因子对作为生成元。"""
    p = {"full": 0, "half": 1, "quarter": 2, "eighth": 3}[fraction]
    pairs = [tuple(range(2 * i, 2 * i + 2)) for i in range(p)]
    rows = []
    for bits in product((-1, 1), repeat=k - p):
        row = list(bits)
        for pair in pairs:
            value = 1
            for index in pair:
                value *= row[index]
            row.append(value)
        rows.append(row)
    return rows


def _cube_block(row, cubes, k):
    if cubes == 1:
        return 0
    if cubes == 2:
        return 0 if math.prod(row) > 0 else 1
    half = k // 2
    return (2 if math.prod(row[:half]) > 0 else 0) + (
        1 if math.prod(row[half:]) > 0 else 0)


def _plan(spec, replicates):
    """扩展路径的标准序行；返回 (行, alpha, 区组数, 分类组合数)。"""
    continuous = [f for f in spec.factors if f.factor_type == "continuous"]
    k = len(continuous)
    fraction = spec.ccd_fraction or "full"
    if fraction not in _FRACTION_FACTORS:
        raise ValueError("ccd_fraction 必须是 full、half、quarter 或 eighth")
    low, high = _FRACTION_FACTORS[fraction]
    if not low <= k <= high:
        raise ValueError(f"{fraction} 设计需要 {low} 至 {high} 个连续因子")
    if spec.generators or spec.defining_relations or spec.aliases:
        raise ValueError("CCD 不接受生成元，请使用设计分数")

    fraction_order = {"full": 0, "half": 1, "quarter": 2, "eighth": 3}[fraction]
    cube_count = 1 << (k - fraction_order)
    blocks = 1 if spec.block_count is None else spec.block_count
    if blocks != 1:
        if (k, fraction) not in _BLOCKS or blocks not in _BLOCKS[(k, fraction)]:
            raise ValueError(f"{k} 因子 {fraction} CCD 不支持 {blocks} 个区组")
        cubes, cube_centers, axial_centers = _BLOCKS[(k, fraction)][blocks]
        alpha = math.sqrt(cube_count * (2*k + axial_centers)
                          / (2 * (cube_count + cube_centers)))
        if spec.ccd_alpha is not None and not math.isclose(
                spec.ccd_alpha, alpha, rel_tol=1e-6):
            raise ValueError(
                f"{blocks} 区组设计的正交 alpha 必须是 {alpha:.10g}；"
                "自定义 alpha 会破坏区组正交性")
        centers_per_category = cube_centers + axial_centers
        if (spec.ccd_center_points is not None
                and spec.ccd_center_points != centers_per_category):
            raise ValueError(
                f"区组设计需要 {centers_per_category} 个中心点；"
                f"当前输入为 {spec.ccd_center_points}。请选择默认或输入所需数量。")
    else:
        cubes, cube_centers, axial_centers = 1, 0, 0
        alpha = spec.ccd_alpha if spec.ccd_alpha is not None else cube_count ** 0.25
        centers_per_category = spec.ccd_center_points
        if centers_per_category is None:
            raise ValueError("CCD 需要中心点数")
    if not math.isfinite(alpha) or alpha <= 0:
        raise ValueError("CCD alpha 必须是正有限数")

    category_count = math.prod(
        len(factor.levels) for factor in spec.factors
        if factor.factor_type == "categorical")
    total = category_count * (replicates * (cube_count + 2*k)
                              + centers_per_category)
    if total > _MAX_RUNS:
        raise ValueError(f"运行总数不能超过 {_MAX_RUNS}")

    categories = category_combinations(spec.factors)
    cube = cube_rows(k, fraction)
    rows = []
    for category in categories:
        for replicate in range(1, replicates + 1):
            for row in cube:
                rows.append(("factorial", row,
                             _cube_block(row, cubes, k), replicate, category))
            for i in range(k):
                for sign in (-1, 1):
                    point = [0.0] * k
                    point[i] = sign * alpha
                    rows.append(("axial", point,
                                 0 if blocks == 1 else
                                 cubes + (i % (blocks - cubes)),
                                 replicate, category))
        if blocks == 1:
            rows.extend(("center", [0.0] * k, 0, index + 1, category)
                        for index in range(centers_per_category))
        else:
            rows.extend(("center", [0.0] * k, block, 1, category)
                        for block in range(cubes)
                        for _ in range(cube_centers // cubes))
            rows.extend(("center", [0.0] * k, block, 1, category)
                        for block in range(cubes, blocks)
                        for _ in range(axial_centers // (blocks - cubes)))
    return rows, alpha, blocks, len(categories)


def _create_extended(spec, replicates, measured):
    rows, alpha, blocks, categories = _plan(spec, int(replicates))
    total = len(rows)
    # 元数据记录实际使用的 alpha 与点数，供恢复时核验。
    normalized = replace(
        spec, ccd_alpha=alpha,
        ccd_center_points=sum(row[0] == "center" for row in rows) // categories,
        ccd_axial_points=sum(row[0] == "axial" for row in rows) // categories)
    continuous = [f for f in spec.factors if f.factor_type == "continuous"]
    centers = [_center_level(f) for f in continuous]
    axes = {f.factor_id: axial_levels(f, alpha) for f in continuous}
    columns = {
        "run_id": "运行ID", "standard_order": "标准序", "run_order": "运行序",
        "point_type": "点类型", "replicate": "重复",
        "block": None if blocks == 1 else "区组",
        "factors": {f.factor_id: f"设定_{f.factor_id}" for f in spec.factors},
        "measured_levels": ({f.factor_id: f"实测_{f.factor_id}"
                             for f in spec.factors} if measured else {}),
        "responses": {name: f"响应_{name}" for name in spec.response_names},
    }
    ids = [f"R{i:05d}" for i in range(1, total + 1)]
    order, sequence = {}, 1
    for block in range(blocks):
        block_ids = [rid for rid, row in zip(ids, rows) if row[2] == block]
        for rid in randomized_run_order(block_ids, spec.seed + block):
            order[rid] = sequence
            sequence += 1
    data = []
    for index in sorted(range(total), key=lambda i: order[ids[i]]):
        point, coded, block, replicate, category = rows[index]
        row = {"运行ID": ids[index], "标准序": index + 1,
               "运行序": order[ids[index]], "点类型": point, "重复": replicate}
        if blocks > 1:
            row["区组"] = block + 1
        for factor, value in zip(continuous, coded):
            if value == 1:
                actual = factor.high
            elif value == -1:
                actual = factor.low
            elif value == 0:
                actual = centers[continuous.index(factor)]
            elif value < 0:
                actual = axes[factor.factor_id][0]
            else:
                actual = axes[factor.factor_id][1]
            row[columns["factors"][factor.factor_id]] = actual
            row[f"编码_{factor.factor_id}"] = value
        for key, level in category.items():
            row[columns["factors"][key]] = level
        row.update({name: None for name in
                    (*columns["measured_levels"].values(),
                     *columns["responses"].values())})
        data.append(row)
    frame = pd.DataFrame(data)
    for factor in spec.factors:
        name = columns["factors"][factor.factor_id]
        frame[name] = pd.Series([row[name] for row in data], dtype=object)
    for name in (*columns["measured_levels"].values(),
                 *columns["responses"].values()):
        frame[name] = pd.array([None] * total, dtype="Float64")
    return frame, worksheet_metadata(frame, normalized, columns)


def validate_ccd(result):
    spec, runs = result.spec, result.runs
    k = len([f for f in spec.factors if f.factor_type == "continuous"])
    if _extended(spec) or (
            spec.ccd_alpha is not None
            and spec.ccd_alpha != 1
            and not math.isclose(spec.ccd_alpha, (2 ** k) ** .25, rel_tol=1e-14)):
        return _validate_extended(result)
    k = len(spec.factors)
    if (spec.design_type != 'central_composite' or not 2 <= k <= 5 or
            spec.ccd_alpha is None or spec.ccd_center_points is None or
            spec.ccd_axial_points is None or spec.generators or
            spec.defining_relations or spec.aliases):
        raise ValueError('CCD 设计定义不完整')
    alpha = spec.ccd_alpha
    if alpha != 1 and not math.isclose(alpha, (2 ** k) ** .25, rel_tol=1e-14):
        raise ValueError('仅支持面心或旋转外接 CCD')
    centers = [_center_level(f) for f in spec.factors]
    axial = [axial_levels(f, alpha) for f in spec.factors]
    groups = {}
    center_replicates = []
    coded = []
    for run in runs:
        if run.block is not None:
            raise ValueError('CCD 不支持区组')
        values = [run.settings[f.factor_id] for f in spec.factors]
        if run.point_type == 'center':
            if values != centers:
                raise ValueError('CCD 中心点设定错误')
            center_replicates.append(run.replicate)
            row = (0,) * k
        elif run.point_type == 'factorial':
            row = tuple(-1 if v == f.low else 1 if v == f.high else None
                        for v, f in zip(values, spec.factors))
            if None in row:
                raise ValueError('CCD 因子点设定错误')
        elif run.point_type == 'axial':
            matches = [(i, sign) for i in range(k) for sign in (-1, 1)
                       if values == [axial[j][0 if sign == -1 else 1]
                                     if j == i else centers[j] for j in range(k)]]
            if len(matches) != 1:
                raise ValueError('CCD 轴点设定错误')
            i, sign = matches[0]
            row = tuple(sign * alpha if j == i else 0 for j in range(k))
        else:
            raise ValueError('CCD 点类型错误')
        if run.point_type != 'center':
            groups.setdefault(run.replicate, []).append((run.point_type, row))
        coded.append(row)
    expected = Counter([('factorial', row) for row in product((-1, 1), repeat=k)] +
                       [('axial', tuple(sign * alpha if j == i else 0 for j in range(k)))
                        for i in range(k) for sign in (-1, 1)])
    if (not groups or set(groups) != set(range(1, len(groups) + 1)) or
            any(Counter(group) != expected for group in groups.values()) or
            sorted(center_replicates) != list(range(1, spec.ccd_center_points + 1)) or
            sum(r.point_type == 'axial' for r in runs) != spec.ccd_axial_points):
        raise ValueError('CCD 设计矩阵不完整或重复')
    return coded


def create_ccd(spec, replicates=1, measured=False):
    if not isinstance(spec, DesignSpec) or spec.design_type != 'central_composite':
        raise ValueError('需要中心复合设计定义')
    if isinstance(replicates, bool) or not isinstance(replicates, Integral) or replicates < 1:
        raise ValueError('重复数必须是正整数')
    if not isinstance(measured, bool) or spec.seed is None:
        raise ValueError('实测列选项或随机种子无效')
    if _extended(spec):
        return _create_extended(spec, replicates, measured)
    if spec.ccd_alpha is not None:
        k = len([f for f in spec.factors if f.factor_type == "continuous"])
        if spec.ccd_alpha != 1 and not math.isclose(
                spec.ccd_alpha, (2 ** k) ** .25, rel_tol=1e-14):
            # 自定义 alpha 只在扩展路径中支持（含分数与分类因子）。
            return _create_extended(spec, replicates, measured)
    k = len(spec.factors)
    if not 2 <= k <= 5 or spec.ccd_alpha is None or spec.ccd_center_points is None:
        raise ValueError('CCD 需要 2 至 5 个因子及完整定义')
    total = replicates * (2**k + 2*k) + spec.ccd_center_points
    if total > 10000:
        raise ValueError('运行总数不能超过 10000')
    centers = [_center_level(f) for f in spec.factors]
    axial = [axial_levels(f, spec.ccd_alpha) for f in spec.factors]
    columns = {'run_id': '运行ID', 'standard_order': '标准序', 'run_order': '运行序',
               'point_type': '点类型', 'replicate': '重复',
               'factors': {f.factor_id: f'设定_{f.factor_id}' for f in spec.factors},
               'measured_levels': {f.factor_id: f'实测_{f.factor_id}' for f in spec.factors} if measured else {},
               'responses': {name: f'响应_{name}' for name in spec.response_names}}
    rows = []
    for rep in range(1, replicates + 1):
        for n in range(2**k):
            rows.append(('factorial', rep, [f.high if n & (1 << i) else f.low for i, f in enumerate(spec.factors)]))
        for i in range(k):
            for sign in (0, 1):
                rows.append(('axial', rep, [axial[j][sign] if j == i else centers[j] for j in range(k)]))
    rows.extend(('center', i + 1, centers) for i in range(spec.ccd_center_points))
    ids = [f'R{i:05d}' for i in range(1, total + 1)]
    positions = {run_id: i for i, run_id in enumerate(ids)}
    data = []
    for order, run_id in enumerate(randomized_run_order(ids, spec.seed), 1):
        index = positions[run_id]
        point, rep, levels = rows[index]
        row = {'运行ID': run_id, '标准序': index + 1, '运行序': order, '点类型': point, '重复': rep}
        row.update({columns['factors'][f.factor_id]: v for f, v in zip(spec.factors, levels)})
        for i, factor in enumerate(spec.factors):
            value = (-1 if levels[i] == factor.low else 1) if point == 'factorial' else (
                0 if point == 'center' or levels[i] == centers[i] else
                -spec.ccd_alpha if levels[i] == axial[i][0] else spec.ccd_alpha)
            row[f'编码_{factor.factor_id}'] = value
        row.update({name: None for name in (*columns['measured_levels'].values(), *columns['responses'].values())})
        data.append(row)
    frame = pd.DataFrame(data)
    for name in columns['factors'].values():
        frame[name] = pd.Series([row[name] for row in data], dtype=object)
    for name in (*columns['measured_levels'].values(), *columns['responses'].values()):
        frame[name] = pd.array([None] * total, dtype='Float64')
    meta = worksheet_metadata(frame, spec, columns)
    return frame, meta


def _validate_extended(result):
    """扩展路径的严格核验：重复、点数、编码、区组与分类水平一致。"""
    spec, runs = result.spec, result.runs
    if spec.ccd_axial_points is None or spec.ccd_center_points is None:
        raise ValueError('CCD 设计定义不完整')
    base_rows, alpha, blocks, categories = _plan(spec, 1)
    categorical = [factor for factor in spec.factors
                   if factor.factor_type == 'categorical']

    def category_key(values):
        return tuple(values.get(factor.factor_id) for factor in categorical)

    noncenter_per_category = Counter()
    centers_per_category = Counter()
    axial_per_category = Counter()
    for point, _coded, _block, _replicate, category in base_rows:
        key = category_key(category)
        if point == 'center':
            centers_per_category[key] += 1
        else:
            noncenter_per_category[key] += 1
        if point == 'axial':
            axial_per_category[key] += 1
    if (len(noncenter_per_category) != categories
            or len(set(noncenter_per_category.values())) != 1
            or len(set(centers_per_category.get(key, 0)
                       for key in noncenter_per_category)) != 1
            or len(set(axial_per_category.values())) != 1):
        raise ValueError('CCD 基础设计的分类组合结构无效')

    counts = {key: Counter() for key in noncenter_per_category}
    for run in runs:
        key = tuple(run.settings[factor.factor_id] for factor in categorical)
        if key not in counts:
            raise ValueError('CCD 分类因子水平与设计定义不一致')
        counts[key][run.point_type] += 1
    repeats = set()
    for key, point_counts in counts.items():
        noncenter = sum(count for point, count in point_counts.items()
                        if point != 'center')
        base_noncenter = noncenter_per_category[key]
        if noncenter % base_noncenter:
            raise ValueError('CCD 非中心点数不能组成完整重复')
        repeats.add(noncenter // base_noncenter)
        if point_counts['center'] != centers_per_category.get(key, 0):
            raise ValueError('CCD 中心点数与设计定义不一致')
    if len(repeats) != 1 or not repeats or next(iter(repeats)) < 1:
        raise ValueError('CCD 各分类组合的重复数不一致或缺失')
    replicates = next(iter(repeats))
    expected_axial = next(iter(axial_per_category.values())) * replicates
    expected_centers = next(iter(centers_per_category.values()), 0)
    if (spec.ccd_axial_points != expected_axial
            or spec.ccd_center_points != expected_centers):
        raise ValueError('CCD 轴点数或中心点数与重复结构不一致')

    rows, alpha, blocks, categories = _plan(spec, replicates)
    if len(runs) != len(rows):
        raise ValueError('CCD 运行数与完整重复结构不一致')
    continuous = [f for f in spec.factors if f.factor_type == 'continuous']
    centers = [_center_level(f) for f in continuous]
    ordered = sorted(runs, key=lambda run: run.standard_order)
    by_standard = {}
    for index, run in enumerate(ordered):
        if run.run_id != f'R{index + 1:05d}':
            raise ValueError('CCD 运行 ID 与标准序不一致')
        point, coded, block, replicate, category = rows[index]
        if (run.point_type != point
                or run.replicate != replicate
                or (blocks > 1 and run.block != block + 1)
                or (blocks == 1 and run.block is not None)):
            raise ValueError('CCD 点类型、区组或重复编号与设计定义不一致')
        for factor, value in zip(continuous, coded):
            actual = run.settings[factor.factor_id]
            if value == 0:
                if actual != centers[continuous.index(factor)]:
                    raise ValueError('CCD 中心点设定错误')
            elif abs(value) > 1:
                levels = axial_levels(factor, alpha)
                if actual != (levels[0] if value < 0 else levels[1]):
                    raise ValueError('CCD 轴点设定错误')
            elif abs(float(factor.to_coded(actual)) - value) > 1e-9:
                raise ValueError('CCD 设定水平与编码矩阵不一致')
        for key, level in category.items():
            if run.settings[key] != level:
                raise ValueError('CCD 分类因子水平与设计定义不一致')
        by_standard[run.standard_order] = coded
    if sorted(run.run_order for run in runs) != list(range(1, len(runs) + 1)):
        raise ValueError('CCD 运行序必须是 1 到运行数的排列')
    if sum(run.point_type == 'axial' for run in runs) != (
            spec.ccd_axial_points * categories):
        raise ValueError('轴点数与设计定义不一致')
    if sum(run.point_type == 'center' for run in runs) != (
            spec.ccd_center_points * categories):
        raise ValueError('中心点数与设计定义不一致')
    return [[float(value) for value in by_standard[run.standard_order]]
            for run in runs]


def center_replicate_order(ordered, index):
    """中心点按出现顺序编号 1..n，与原有单区组语义一致。"""
    position = sum(1 for run in ordered[:index] if run.point_type == 'center')
    return position + 1
