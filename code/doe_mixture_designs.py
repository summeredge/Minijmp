"""Simplex Lattice / Centroid / Extreme Vertices 设计生成与结构核验。"""
from __future__ import annotations

from itertools import combinations, product
import math
from numbers import Integral

import numpy as np
import pandas as pd

from doe_core import randomized_run_order, worksheet_metadata
from doe_mixture import MixtureSpec, mixture_metadata, mixture_rows
from doe_mixture_constraints import (
    MixtureConstraintError, TOLERANCE, check_point,
)


MAX_RUNS = 10000
MAX_COMBINATIONS = 200000


def lattice_points(q, degree):
    points = []

    def walk(prefix, remaining, left):
        if left == 1:
            vector = (*prefix, remaining)
            values = [value / degree for value in vector[:-1]]
            values.append(1 - sum(values))
            points.append(tuple(values))
            return
        for value in range(remaining + 1):
            walk((*prefix, value), remaining - value, left - 1)

    walk((), degree, q)
    return points


def centroid_points(q):
    points = []
    for size in range(1, q + 1):
        for indices in combinations(range(q), size):
            values = [0.0] * q
            for index in indices:
                values[index] = 1 / size
            if sum(values) != 1:
                values[indices[-1]] = 1 - sum(values[:indices[-1]] +
                                               values[indices[-1] + 1:])
            points.append(tuple(values))
    return points


def _active_sets(components, constraints):
    active = []
    for index, component in enumerate(components):
        active.append(('lower', index, component.lower))
        active.append(('upper', index, component.upper))
    for constraint in constraints:
        active.append(('linear', constraint, constraint.bound))
    return active


def region_vertices(spec):
    """枚举可行多面体全部极端顶点；返回 [(点, 活动约束说明)]。"""
    q = len(spec.components)
    active = _active_sets(spec.components, spec.linear_constraints)
    budget = 1
    for index in range(q - 1):
        budget = budget * (len(active) - index) // (index + 1)
        if budget > MAX_COMBINATIONS:
            raise MixtureConstraintError(
                f'约束组合数超过计算预算 {MAX_COMBINATIONS}，请减少组分或约束')
    coef = np.asarray([[row.coefficients.get(component.component_id, 0.0)
                        for component in spec.components]
                       for row in spec.linear_constraints], dtype=float)
    vertices, seen = [], set()
    for chosen in combinations(active, q - 1):
        matrix, rhs, labels = [], [], []
        for kind, target, bound in chosen:
            row = np.zeros(q)
            if kind == 'lower':
                row[target] = 1
                labels.append(f'{spec.components[target].component_id}={bound:g}')
            elif kind == 'upper':
                row[target] = 1
                labels.append(f'{spec.components[target].component_id}={bound:g}')
            else:
                row = np.array([target.coefficients.get(c.component_id, 0.0)
                                for c in spec.components], dtype=float)
                labels.append('线性约束')
            matrix.append(row)
            rhs.append(bound)
        matrix.append(np.ones(q))
        rhs.append(1.0)
        try:
            point = np.linalg.solve(np.asarray(matrix), np.asarray(rhs))
        except np.linalg.LinAlgError:
            continue
        scale = max(1.0, float(np.max(np.abs(point))))
        if not np.isfinite(point).all() or np.max(np.abs(matrix @ point - rhs)) > 1e-8 * scale:
            continue
        if any(value < component.lower - 1e-8 or value > component.upper + 1e-8
               for value, component in zip(point, spec.components)):
            continue
        if coef.size and np.max(coef @ point - np.asarray(
                [item.bound for item in spec.linear_constraints])) > 1e-8:
            continue
        point = _normalize(spec.components, point)
        key = tuple(round(value, 10) for value in point)
        if key in seen:
            continue
        seen.add(key)
        vertices.append((tuple(float(value) for value in point),
                         '；'.join(labels)))
    if not vertices:
        raise MixtureConstraintError('约束区域没有可行点，不能创建设计')
    vertices.sort(key=lambda item: item[0])
    return vertices


def _normalize(components, point, tol=1e-8):
    values = [float(value) for value in point]
    residual = 1 - sum(values)
    if abs(residual) > tol:
        raise MixtureConstraintError('顶点求解后总和偏离 1')
    if residual:
        index = max(range(len(values)), key=lambda i: (components[i].upper - values[i])
                    if residual > 0 else (values[i] - components[i].lower))
        values[index] += residual
    for value, component in zip(values, components):
        if value < component.lower - TOLERANCE or value > component.upper + TOLERANCE:
            raise MixtureConstraintError('顶点舍入后超出组分边界')
    return values


def region_dimension(vertices):
    if len(vertices) <= 1:
        return 0
    matrix = np.asarray(vertices) - np.asarray(vertices[0])
    return int(np.linalg.matrix_rank(matrix, tol=1e-9))


def _point_kind(point, q):
    nonzero = sum(value > TOLERANCE for value in point)
    if nonzero == 1:
        return 'factorial'
    if all(abs(value - 1 / q) <= TOLERANCE for value in point):
        return 'center'
    if nonzero == 2:
        return 'edge'
    return 'factorial'


def design_points(spec, *, include_centroid=True):
    """确定性标准点集；每个点先通过真实约束核验。"""
    q = len(spec.components)
    if spec.design_type == 'simplex_lattice':
        points = [(point, _point_kind(point, q), '格点')
                  for point in lattice_points(q, spec.degree)]
        for point, _, _ in points:
            try:
                check_point(spec.components, spec.linear_constraints, point)
            except MixtureConstraintError as error:
                raise MixtureConstraintError(
                    'Simplex Lattice 生成的点不满足组分约束；'
                    '带上下界或线性约束时请改用 Extreme Vertices 设计。') from error
    elif spec.design_type == 'simplex_centroid':
        points = []
        for point in centroid_points(q):
            kind = _point_kind(point, q)
            source = '重心' if kind == 'center' else '顶点' if kind == 'factorial' else '边中点'
            points.append((point, kind, source))
        for point, _, _ in points:
            try:
                check_point(spec.components, spec.linear_constraints, point)
            except MixtureConstraintError as error:
                raise MixtureConstraintError(
                    'Simplex Centroid 生成的点不满足组分约束；'
                    '带上下界或线性约束时请改用 Extreme Vertices 设计。') from error
    else:
        vertices = region_vertices(spec)
        points = [(point, 'factorial', source) for point, source in vertices]
        if include_centroid:
            centroid = [float(np.mean([point[index] for point, _ in vertices]))
                        for index in range(q)]
            centroid = _normalize(spec.components, centroid)
            try:
                check_point(spec.components, spec.linear_constraints, centroid)
            except MixtureConstraintError:
                pass
            else:
                if not any(np.allclose(centroid, point, rtol=0, atol=1e-10)
                           for point, _, _ in points):
                    points.append((tuple(centroid), 'center', '可行域质心'))
    return points


def _process_combinations(spec):
    variables = spec.process_variables
    if not variables:
        return [{}]
    return [{variable.variable_id: variable.low if sign < 0 else variable.high
             for variable, sign in zip(variables, signs)}
            for signs in product((-1, 1), repeat=len(variables))]


def create_mixture_design(spec, replicates=1, *, include_centroid=True):
    """生成混料工作表并返回 DOE v4 + mixture 两层元数据。"""
    if not isinstance(spec, MixtureSpec):
        raise MixtureConstraintError('spec 必须是 MixtureSpec')
    if isinstance(replicates, bool) or not isinstance(replicates, Integral) \
            or replicates < 1:
        raise MixtureConstraintError('重复数必须是正整数')
    replicates = int(replicates)
    if spec.design_type == 'simplex_lattice':
        base = math.comb(spec.degree + len(spec.components) - 1, len(spec.components) - 1)
        if base > MAX_RUNS:
            raise MixtureConstraintError(f'运行总数不能超过 {MAX_RUNS}')
    points = design_points(spec, include_centroid=include_centroid)
    processes = _process_combinations(spec)
    total = len(points) * len(processes) * replicates
    if total > MAX_RUNS:
        raise MixtureConstraintError(f'运行总数不能超过 {MAX_RUNS}')
    amount = dict(spec.amount_settings)
    base_rows = []
    for point, kind, source in points:
        for process in processes:
            base_rows.append((point, kind, source, process))
    ids = [f'R{index:05d}' for index in range(1, total + 1)]
    standard = []
    for replicate in range(1, replicates + 1):
        for point, kind, source, process in base_rows:
            standard.append({'point': point, 'kind': kind, 'source': source,
                             'process': process, 'replicate': replicate})
    order = {}
    for replicate in range(1, replicates + 1):
        block_ids = [ids[index] for index, row in enumerate(standard)
                     if row['replicate'] == replicate]
        for run_id in randomized_run_order(block_ids, spec.seed + replicate):
            order[run_id] = len(order) + 1
    data = []
    component_ids = spec.component_ids
    for index in sorted(range(total), key=lambda i: order[ids[i]]):
        row = standard[index]
        item = {'运行ID': ids[index], '标准序': index + 1,
                '运行序': order[ids[index]], '点类型': row['kind'],
                '重复': row['replicate'], '点来源': row['source']}
        item.update({f'设定_{component_id}': value
                     for component_id, value in zip(component_ids, row['point'])})
        item.update({f'设定_{key}': value for key, value in row['process'].items()})
        item.update({f'设定_{key}': value for key, value in amount.items()})
        item.update({f'响应_{name}': None for name in spec.response_names})
        data.append(item)
    columns = ['运行ID', '标准序', '运行序', '点类型', '重复', '点来源']
    columns += [f'设定_{key}' for key in (*component_ids, *spec.variable_ids)]
    columns += [f'响应_{name}' for name in spec.response_names]
    frame = pd.DataFrame(data, columns=columns)
    for name in [f'响应_{name}' for name in spec.response_names]:
        frame[name] = pd.array([None] * total, dtype='Float64')
    map_columns = spec.column_map()
    doe_meta = worksheet_metadata(frame, spec.doe_design_spec(), map_columns)
    return frame, {'doe': doe_meta, 'mixture': mixture_metadata(frame, spec)}


def validate_mixture_design(spec, frame, *, include_centroid=True):
    """核验运行总数、点集、过程组合、重复、顺序与总和。"""
    points = design_points(spec, include_centroid=include_centroid)
    processes = _process_combinations(spec)
    expected = [(point, kind, process)
                for point, kind, _ in points for process in processes]
    replicates = int(frame['重复'].max()) if len(frame) else 0
    if replicates < 1 or len(frame) != len(expected) * replicates:
        raise MixtureConstraintError('混料运行数不是基础设计的整数倍')
    rows = mixture_rows(frame, spec)
    by_standard = {int(row['row']['标准序']): row for row in rows}
    if set(by_standard) != set(range(1, len(frame) + 1)):
        raise MixtureConstraintError('标准序必须是 1 到运行数的排列')
    for index, (point, kind, process) in enumerate(expected):
        for replicate in range(1, replicates + 1):
            standard = (replicate - 1) * len(expected) + index + 1
            row = by_standard.get(standard)
            if row is None:
                raise MixtureConstraintError('混料标准序与设计定义不一致')
            if (row['row']['点类型'] != kind or int(row['row']['重复']) != replicate
                    or abs(row['row']['标准序'] - standard) > 0):
                raise MixtureConstraintError('混料点类型或重复编号与设计定义不一致')
            if not np.allclose(row['proportions'], point, rtol=0, atol=1e-9):
                raise MixtureConstraintError('混料组分比例与设计定义不一致')
            for key, value in process.items():
                if abs(row['settings'][key] - value) > 1e-9:
                    raise MixtureConstraintError('过程变量组合与设计定义不一致')
            for key, value in spec.amount_settings:
                if abs(row['settings'][key] - value) > 1e-9:
                    raise MixtureConstraintError('总量设定与设计定义不一致')
    if sorted(int(row['row']['运行序']) for row in rows) != list(
            range(1, len(frame) + 1)):
        raise MixtureConstraintError('运行序必须是 1 到运行数的排列')
    for replicate in range(1, replicates + 1):
        orders = sorted(int(row['row']['运行序']) for row in rows
                        if int(row['row']['重复']) == replicate)
        if orders != list(range(min(orders), min(orders) + len(orders))):
            raise MixtureConstraintError('重复内运行序必须连续')
    return {'points': len(points), 'process_combinations': len(processes),
            'replicates': replicates, 'runs': len(frame)}
