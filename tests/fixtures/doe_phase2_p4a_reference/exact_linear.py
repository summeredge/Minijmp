"""独立于 MiniJMP 生产代码的精确线性代数（Fraction）。

只使用标准库；供 P2-4A 参考构建与复核脚本共用。不得在实现中引用
`doe_core`、`doe_screening_analysis` 等生产模块。
"""
from fractions import Fraction


def _f(value):
    if isinstance(value, Fraction):
        return value
    return Fraction(value)


def _echelon(rows):
    """返回 (化简矩阵, 主元列号)。行按列空间向量展开，主元列即独立列。"""
    work = [[_f(value) for value in row] for row in rows]
    if not work:
        return [], []
    width = len(work[0])
    pivots = []
    rank = 0
    for column in range(width):
        pivot = next((r for r in range(rank, len(work)) if work[r][column] != 0), None)
        if pivot is None:
            continue
        work[rank], work[pivot] = work[pivot], work[rank]
        scale = work[rank][column]
        work[rank] = [value / scale for value in work[rank]]
        for r in range(len(work)):
            if r != rank and work[r][column] != 0:
                factor = work[r][column]
                work[r] = [a - factor * b for a, b in zip(work[r], work[rank])]
        pivots.append(column)
        rank += 1
        if rank == len(work):
            break
    return work, pivots


def independent_columns(columns):
    """返回 column 索引列表；column 为同长度向量。"""
    if not columns:
        return []
    rows = [[_f(column[i]) for column in columns] for i in range(len(columns[0]))]
    _, pivots = _echelon(rows)
    return pivots


def rank(columns):
    return len(independent_columns(columns))


def solve(matrix, rhs):
    """解方阵线性方程组，返回 Fraction 列表。"""
    size = len(matrix)
    work = [[_f(value) for value in row] + [_f(extra)]
            for row, extra in zip(matrix, rhs)]
    for column in range(size):
        pivot = next((r for r in range(column, size) if work[r][column] != 0), None)
        if pivot is None:
            raise ValueError("奇异法方程")
        work[column], work[pivot] = work[pivot], work[column]
        scale = work[column][column]
        work[column] = [value / scale for value in work[column]]
        for r in range(size):
            if r != column and work[r][column] != 0:
                factor = work[r][column]
                work[r] = [a - factor * b for a, b in zip(work[r], work[column])]
    return [row[size] for row in work]


def projection_coefficients(columns, target):
    """用 Moore–Penrose 意义下的最小二乘精确解投影 target 到 columns 张成空间。

    秩亏时对独立列子集求解，其余系数记 0；调用者必须同时读取 rank。
    """
    basis = independent_columns(columns)
    coefficients = [Fraction(0)] * len(columns)
    if not basis:
        return coefficients
    selected = [columns[i] for i in basis]
    gram = [[sum(a * b for a, b in zip(left, right)) for right in selected]
            for left in selected]
    rhs = [sum(a * b for a, b in zip(left, target)) for left in selected]
    for position, value in zip(basis, solve(gram, rhs)):
        coefficients[position] = value
    return coefficients


def sse(columns, y):
    """残差平方和；columns 为模型列（含截距），秩亏时按最小二乘投影。"""
    coefficients = projection_coefficients(columns, y)
    residual = [value - sum(c * column[i] for c, column in zip(coefficients, columns))
                for i, value in enumerate(y)]
    return sum(value * value for value in residual)


def dot(left, right):
    return sum(_f(a) * _f(b) for a, b in zip(left, right))
