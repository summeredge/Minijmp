"""独立混料参考：只用标准库精确分数与自写线性代数，不导入生产模块。"""
from __future__ import annotations

from fractions import Fraction as F
from itertools import combinations
import hashlib
import json
from pathlib import Path


def lattice(q, degree):
    points = []

    def walk(prefix, remaining, left):
        if left == 1:
            points.append(tuple(F(value, degree) for value in (*prefix, remaining)))
            return
        for value in range(remaining + 1):
            walk((*prefix, value), remaining - value, left - 1)

    walk((), degree, q)
    return points


def centroid(q):
    points = []
    for size in range(1, q + 1):
        for indices in combinations(range(q), size):
            point = [F(0)] * q
            for index in indices:
                point[index] = F(1, size)
            points.append(tuple(point))
    return points


def solve(matrix, rhs):
    """Fraction 高斯消元；matrix 为方阵。"""
    size = len(matrix)
    a = [list(row) + [value] for row, value in zip(matrix, rhs)]
    for column in range(size):
        pivot = next((row for row in range(column, size) if a[row][column]), None)
        if pivot is None:
            raise ValueError('奇异方程')
        a[column], a[pivot] = a[pivot], a[column]
        divisor = a[column][column]
        a[column] = [value / divisor for value in a[column]]
        for row in range(size):
            if row != column and a[row][column]:
                factor = a[row][column]
                a[row] = [left - factor * right
                          for left, right in zip(a[row], a[column])]
    return [row[-1] for row in a]


def least_squares(x, y):
    width = len(x[0])
    normal = [[sum(row[i] * row[j] for row in x) for j in range(width)]
              for i in range(width)]
    rhs = [sum(row[i] * value for row, value in zip(x, y)) for i in range(width)]
    return solve(normal, rhs)


def residual_sse(x, y, beta):
    total = F(0)
    for row, value in zip(x, y):
        fitted = sum(a * b for a, b in zip(row, beta))
        total += (value - fitted) ** 2
    return total


def poly_predict(point, coefficients):
    x1, x2, x3 = point
    b1, b2, b3, b12, b13, b23 = coefficients
    return b1 * x1 + b2 * x2 + b3 * x3 + b12 * x1 * x2 + b13 * x1 * x3 + b23 * x2 * x3


def entries(points):
    return [[str(value) for value in point] for point in points]


def fs(value):
    return str(value)


def constrained_vertices(bounds, constraints, q=3):
    """枚举 q-1 个活动约束（含 sum=1）求顶点；bounds/constraints 为 Fraction。"""
    active = []
    for index, (low, high) in enumerate(bounds):
        active.append(('lower', index, low))
        active.append(('upper', index, high))
    for coefficients, bound in constraints:
        active.append(('linear', coefficients, bound))
    vertices = {}
    for chosen in combinations(active, q - 1):
        matrix, rhs = [], []
        for item in chosen:
            row = [F(0)] * q
            if item[0] == 'lower':
                row[item[1]] = F(1)
                rhs.append(item[2])
            elif item[0] == 'upper':
                row[item[1]] = F(1)
                rhs.append(item[2])
            else:
                row = list(item[1])
                rhs.append(item[2])
            matrix.append(row)
        matrix.append([F(1)] * q)
        rhs.append(F(1))
        try:
            point = solve(matrix, rhs)
        except ValueError:
            continue
        if any(value < low or value > high for value, (low, high) in zip(point, bounds)):
            continue
        if any(sum(a * b for a, b in zip(row, point)) > bound for row, bound in constraints):
            continue
        vertices[tuple(point)] = point
    return sorted(vertices.values())


def build():
    data = {'version': 1}

    points2 = lattice(3, 2)
    points3 = lattice(3, 3)
    data['simplex_lattice_degree2'] = {
        'q': 3, 'degree': 2, 'count': len(points2), 'points': entries(points2),
    }
    data['simplex_lattice_degree3'] = {
        'q': 3, 'degree': 3, 'count': len(points3), 'points': entries(points3),
    }
    cent = centroid(3)
    data['simplex_centroid'] = {
        'q': 3, 'count': len(cent), 'points': entries(cent),
        'vertices': entries([p for p in cent if p.count(F(0)) == 2]),
        'edge_midpoints': entries([p for p in cent if p.count(F(1, 2)) == 2]),
        'centroid': entries([p for p in cent if p == (F(1, 3),) * 3]),
    }

    bounds = [(F(1, 5), F(3, 5)), (F(1, 10), F(1, 2)), (F(1, 5), F(7, 10))]
    constraints = [([F(1), F(1), F(0)], F(3, 4)),
                   ([F(1), F(-1), F(0)], F(1, 5))]
    vertices = constrained_vertices(bounds, constraints)
    data['constrained_region'] = {
        'bounds': [[str(low), str(high)] for low, high in bounds],
        'constraints': [{'coefficients': [str(v) for v in row], 'bound': str(bound)}
                        for row, bound in constraints],
        'vertices': entries(vertices),
        'dimension': 2,
    }
    data['infeasible_region'] = {
        'bounds': [[str(F(4, 5)), str(F(1))], [str(F(3, 10)), str(F(1))],
                   [str(F(0)), str(F(1))]],
        'reason': '下界之和 1.1 大于 1',
    }
    data['degenerate_region'] = {
        'bounds': [[str(F(1, 2)), str(F(1, 2))], [str(F(1, 5)), str(F(1, 5))],
                   [str(F(0)), str(F(1))]],
        'points': entries([(F(1, 2), F(1, 5), F(3, 10))]),
        'dimension': 0,
    }

    linear = [F(2), F(5), F(3)]
    data['linear_scheffe'] = {
        'coefficients': [str(v) for v in linear],
        'points': entries(points3),
        'predictions': [fs(sum(a * b for a, b in zip(point, linear))) for point in points3],
        'vertex_values': [{'point': entries([point])[0],
                           'prediction': fs(sum(a * b for a, b in zip(point, linear)))}
                          for point in points2 if point.count(F(0)) == 2],
    }

    quadratic = [F(2), F(4), F(6), F(8), F(2), F(-3)]
    data['quadratic_scheffe'] = {
        'coefficients': [str(v) for v in quadratic],
        'points': entries(points3),
        'predictions': [fs(poly_predict(point, quadratic)) for point in points3],
    }

    # 二次模型 11 行：排除原重心，改用两个重心独立重复；纯误差来自后两行。
    base = [point for point in points3 if point != (F(1, 3),) * 3]
    rows = base + [(F(1, 3),) * 3, (F(1, 3),) * 3]
    y = [poly_predict(point, quadratic) for point in base] + [F(2), F(3)]
    matrix = [[p[0], p[1], p[2], p[0] * p[1], p[0] * p[2], p[1] * p[2]]
              for p in rows]
    beta = least_squares(matrix, y)
    fitted = [sum(a * b for a, b in zip(row, beta)) for row in matrix]
    sse = residual_sse(matrix, y, beta)
    mean = sum(y) / len(y)
    sst = sum((value - mean) ** 2 for value in y)
    pure_sse = (F(2) - F(5, 2)) ** 2 + (F(3) - F(5, 2)) ** 2
    pure_df = 1
    term_ss = {}
    names = ['A', 'B', 'C', 'A*B', 'A*C', 'B*C']
    for index, name in enumerate(names):
        reduced = [[value for column, value in enumerate(row) if column != index]
                   for row in matrix]
        reduced_beta = least_squares(reduced, y)
        term_ss[name] = residual_sse(reduced, y, reduced_beta) - sse
    data['anova_reference'] = {
        'rows': entries(rows), 'y': [str(value) for value in y],
        'coefficients': [str(value) for value in beta],
        'fitted': [str(value) for value in fitted],
        'residuals': [str(value - fit) for value, fit in zip(y, fitted)],
        'n': len(rows), 'p': 6, 'rank': 6, 'df': len(rows) - 6,
        'sse': str(sse), 'sst': str(sst), 'ssr': str(sst - sse),
        'pure_error_df': pure_df, 'pure_error_sse': str(pure_sse),
        'lack_of_fit_df': len(rows) - 6 - pure_df,
        'lack_of_fit_sse': str(sse - pure_sse),
        'term_ss': {name: str(value) for name, value in term_ss.items()},
        'r2': str(1 - sse / sst),
    }

    process_points = cent
    process_rows = []
    process_y = []
    for point in process_points:
        for z in (F(-1), F(1)):
            process_rows.append((*point, z))
            process_y.append(point[0] + 2 * point[1] + 3 * point[2]
                             + F(3, 2) * point[0] * z + F(1, 2) * z)
    data['process_variable'] = {
        'points': entries(process_rows), 'predictions': [str(v) for v in process_y],
        'model': 'y=A+2B+3C+1.5*A*z+0.5*z',
    }
    proportions = (F(1, 5), F(3, 10), F(1, 2))
    total = F(250)
    data['amount_variable'] = {
        'proportions': [str(v) for v in proportions], 'total': '250',
        'amounts': [str(v * total) for v in proportions],
        'prediction': str(2 * proportions[0] + 4 * proportions[1]
                          + 6 * proportions[2] + 8 * proportions[0] * proportions[1]
                          + 2 * proportions[0] * proportions[2]
                          - 3 * proportions[1] * proportions[2]),
    }

    # 优化参考：独立稠密网格上界/下界，生产实现只需不劣于该网格值。
    opt_model = [F(1), F(2), F(3), F(-4), F(-2), F(0)]
    opt_bounds = [(F(1, 10), F(4, 5))] * 3
    best_max, best_min, best_target = None, None, None
    best_max_point = best_min_point = best_target_point = None
    steps = 400
    for i in range(steps + 1):
        for j in range(steps + 1 - i):
            point = (F(i, steps), F(j, steps), F(steps - i - j, steps))
            if any(value < low or value > high for value, (low, high) in zip(point, opt_bounds)):
                continue
            value = poly_predict(point, opt_model)
            if best_max is None or value > best_max:
                best_max, best_max_point = value, point
            if best_min is None or value < best_min:
                best_min, best_min_point = value, point
            distance = abs(value - F(2))
            if best_target is None or distance < best_target:
                best_target, best_target_point = distance, point
    data['optimization'] = {
        'model': [str(v) for v in opt_model],
        'bounds': [[str(low), str(high)] for low, high in opt_bounds],
        'max': {'point': entries([best_max_point])[0], 'value': str(best_max)},
        'min': {'point': entries([best_min_point])[0], 'value': str(best_min)},
        'target': {'target': '2', 'point': entries([best_target_point])[0],
                   'value': str(poly_predict(best_target_point, opt_model))},
    }

    reference = (F(2, 5), F(3, 10), F(3, 10))
    trace_points, trace_values = [], []
    for t in (F(1, 5), F(3, 10), F(2, 5), F(1, 2), F(3, 5)):
        rest = (F(1) - t) / (F(1) - reference[0])
        point = (t, reference[1] * rest, reference[2] * rest)
        trace_points.append(point)
        trace_values.append(poly_predict(point, quadratic))
    data['trace'] = {
        'reference': [str(v) for v in reference], 'component': 'A',
        'points': entries(trace_points), 'predictions': [str(v) for v in trace_values],
    }

    grid_points, grid_values = [], []
    n = 10
    for i in range(n + 1):
        for j in range(n + 1 - i):
            point = (F(i, n), F(j, n), F(n - i - j, n))
            grid_points.append(point)
            grid_values.append(poly_predict(point, quadratic))
    data['contour_grid'] = {
        'n': n, 'points': entries(grid_points),
        'predictions': [str(v) for v in grid_values],
        'center': {'point': entries([(F(1, 3),) * 3])[0], 'prediction': str(poly_predict((F(1, 3),) * 3, quadratic))},
        'vertex': {'point': entries([(F(1), F(0), F(0))])[0], 'prediction': str(poly_predict((F(1), F(0), F(0)), quadratic))},
    }

    y1 = [F(1), F(2), F(4)]
    y2 = [F(4), F(1), F(2)]
    mask_points, intersection = [], 0
    for i in range(n + 1):
        for j in range(n + 1 - i):
            point = (F(i, n), F(j, n), F(n - i - j, n))
            first = sum(a * b for a, b in zip(point, y1))
            second = sum(a * b for a, b in zip(point, y2))
            inside = F(5, 2) <= first <= F(16, 5) and F(2) <= second <= F(3)
            if inside:
                intersection += 1
                mask_points.append(point)
    data['overlay'] = {
        'responses': [{'name': 'Y1', 'coefficients': [str(v) for v in y1], 'low': '2.5', 'high': '3.2'},
                      {'name': 'Y2', 'coefficients': [str(v) for v in y2], 'low': '2', 'high': '3'}],
        'n': n, 'intersection_count': intersection,
        'points': entries(mask_points),
        'empty_limits': [{'name': 'Y1', 'low': '5', 'high': '6'},
                         {'name': 'Y2', 'low': '5', 'high': '6'}],
    }
    return data


def main():
    data = build()
    path = Path(__file__).with_name('reference.json')
    payload = json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True)
    path.write_text(payload + '\n', encoding='utf-8')
    digest = hashlib.sha256((payload + '\n').encode('utf-8')).hexdigest()
    manifest = {
        'source': '独立标准库精确分数与自写线性代数；不导入 MiniJMP 生产模块',
        'files': {'reference.json': {'sha256': digest,
                                     'bytes': len((payload + '\n').encode('utf-8'))}},
    }
    Path(__file__).with_name('manifest.json').write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return digest


if __name__ == '__main__':
    print(main())
