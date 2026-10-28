"""核验参考 JSON 的自洽性；不导入 MiniJMP 生产模块。"""
from __future__ import annotations

from fractions import Fraction as F
from itertools import combinations
import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent


def load():
    return json.loads((HERE / 'reference.json').read_text(encoding='utf-8'))


def fraction(text):
    return F(text)


def points(rows):
    return [tuple(fraction(value) for value in row) for row in rows]


def check_lattice(section):
    q, degree = section['q'], section['degree']
    rows = points(section['points'])
    assert len(rows) == section['count'] == len(set(rows))
    assert len(rows) == len(list(combinations(range(degree + q - 1), q - 1)))
    assert all(sum(row) == 1 for row in rows)
    assert all(all(0 <= value <= 1 for value in row) for row in rows)
    assert all(all((value * degree).denominator == 1 for value in row) for row in rows)


def check_centroid(section):
    rows = points(section['points'])
    assert len(rows) == section['count'] == 2 ** section['q'] - 1
    assert len(set(rows)) == len(rows)
    assert all(sum(row) == 1 for row in rows)
    assert all(len(set(row)) <= 2 for row in rows)


def check_constrained(section):
    bounds = [(fraction(low), fraction(high)) for low, high in section['bounds']]
    constraints = [(points([item['coefficients']])[0], fraction(item['bound']))
                   for item in section['constraints']]
    rows = points(section['vertices'])
    assert len(rows) == len(set(rows)) == 5
    for row in rows:
        assert abs(sum(row) - 1) == 0
        for value, (low, high) in zip(row, bounds):
            assert low <= value <= high
        for row_coefficients, bound in constraints:
            assert sum(a * b for a, b in zip(row_coefficients, row)) <= bound

    active = []
    for index, (low, high) in enumerate(bounds):
        active += [('lower', index, low), ('upper', index, high)]
    active += [('linear', row, bound) for row, bound in constraints]
    found = set()
    for chosen in combinations(active, 2):
        matrix, rhs = [], []
        for item in chosen:
            row = [F(0)] * 3
            if item[0] == 'lower':
                row[item[1]] = 1
                rhs.append(item[2])
            elif item[0] == 'upper':
                row[item[1]] = 1
                rhs.append(item[2])
            else:
                row, bound = list(item[1]), item[2]
                rhs.append(bound)
            matrix.append(row)
        matrix.append([F(1)] * 3)
        rhs.append(F(1))
        delta = (matrix[0][0] * (matrix[1][1] * matrix[2][2] - matrix[1][2] * matrix[2][1])
                 - matrix[0][1] * (matrix[1][0] * matrix[2][2] - matrix[1][2] * matrix[2][0])
                 + matrix[0][2] * (matrix[1][0] * matrix[2][1] - matrix[1][1] * matrix[2][0]))
        if delta == 0:
            continue
        point = []
        for column in range(3):
            replaced = [[rhs[i] if j == column else matrix[i][j]
                         for j in range(3)] for i in range(3)]
            determinant = (replaced[0][0] * (replaced[1][1] * replaced[2][2] - replaced[1][2] * replaced[2][1])
                           - replaced[0][1] * (replaced[1][0] * replaced[2][2] - replaced[1][2] * replaced[2][0])
                           + replaced[0][2] * (replaced[1][0] * replaced[2][1] - replaced[1][1] * replaced[2][0]))
            point.append(determinant / delta)
        if (all(low <= value <= high for value, (low, high) in zip(point, bounds))
                and all(sum(a * b for a, b in zip(row, point)) <= bound
                        for row, bound in constraints)):
            found.add(tuple(point))
    assert found == set(rows)


def check_linear(section):
    coefficients = [fraction(value) for value in section['coefficients']]
    for row, expected in zip(points(section['points']), section['predictions']):
        assert sum(a * b for a, b in zip(row, coefficients)) == fraction(expected)


def check_quadratic(section):
    b = [fraction(value) for value in section['coefficients']]
    for row, expected in zip(points(section['points']), section['predictions']):
        x1, x2, x3 = row
        value = b[0]*x1 + b[1]*x2 + b[2]*x3 + b[3]*x1*x2 + b[4]*x1*x3 + b[5]*x2*x3
        assert value == fraction(expected)


def check_anova(section):
    rows = points(section['rows'])
    y = [fraction(value) for value in section['y']]
    beta = [fraction(value) for value in section['coefficients']]
    matrix = [[p[0], p[1], p[2], p[0]*p[1], p[0]*p[2], p[1]*p[2]] for p in rows]
    fitted = [sum(a * b for a, b in zip(row, beta)) for row in matrix]
    assert [str(value) for value in fitted] == section['fitted']
    sse = sum((value - fit) ** 2 for value, fit in zip(y, fitted))
    assert sse == fraction(section['sse'])
    mean = sum(y) / len(y)
    assert sum((value - mean) ** 2 for value in y) == fraction(section['sst'])
    assert section['df'] == section['n'] - section['p']
    assert section['lack_of_fit_df'] == section['df'] - section['pure_error_df']
    assert fraction(section['lack_of_fit_sse']) + fraction(section['pure_error_sse']) == sse
    assert all(fraction(value) >= 0 for value in section['term_ss'].values())


def check_overlay(section):
    models = [([fraction(v) for v in item['coefficients']], fraction(item['low']),
               fraction(item['high'])) for item in section['responses']]
    n = section['n']
    count = 0
    for i in range(n + 1):
        for j in range(n + 1 - i):
            point = (F(i, n), F(j, n), F(n - i - j, n))
            if all(low <= sum(a * b for a, b in zip(point, coefficients)) <= high
                   for coefficients, low, high in models):
                count += 1
    assert count == section['intersection_count'] == len(section['points'])


def main():
    data = load()
    for key in ('simplex_lattice_degree2', 'simplex_lattice_degree3'):
        check_lattice(data[key])
    check_centroid(data['simplex_centroid'])
    check_constrained(data['constrained_region'])
    check_linear(data['linear_scheffe'])
    check_quadratic(data['quadratic_scheffe'])
    check_anova(data['anova_reference'])
    check_overlay(data['overlay'])
    manifest = json.loads((HERE / 'manifest.json').read_text(encoding='utf-8'))
    raw = (HERE / 'reference.json').read_text(encoding='utf-8')
    payload = raw[:-1] if raw.endswith('\n') else raw
    assert hashlib.sha256(payload.encode('utf-8')).hexdigest() == manifest['files']['reference.json']['sha256']
    return True


if __name__ == '__main__':
    print('mixture reference verified' if main() else 'failed')
