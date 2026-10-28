"""候选点 D-optimal 选点；独立于 DOE-4 响应优化搜索。

数学目标：对固定模型矩阵 X 与候选行集合最大化 det(X'X)，数值上用
logdet(X'X) 比较以避免行列式溢出/下溢。本模块只处理设计选点，不预测
响应、不评分期望函数，也不写回用户已执行的运行。
"""
from itertools import combinations
from math import comb, log
from numbers import Integral
import hashlib
import json

import numpy as np


_MAX_EXACT_CANDIDATES = 40
_MAX_EXACT_SUBSETS = 200_000
_MAX_SWEEPS = 100
_SINGULAR_TOLERANCE = 1e-10


def _matrix(rows, label='候选矩阵'):
    try:
        matrix = np.asarray(rows, dtype=float)
    except (TypeError, ValueError, OverflowError) as error:
        raise ValueError(f'{label}必须是有限数值矩阵') from error
    if matrix.ndim != 2 or not len(matrix):
        raise ValueError(f'{label}必须是非空二维矩阵')
    if not np.isfinite(matrix).all():
        raise ValueError(f'{label}必须是有限数值矩阵')
    return matrix


def _logdet(matrix, tolerance=_SINGULAR_TOLERANCE):
    """logdet(X'X)；奇异或近奇异时返回 None，避免负/无穷伪目标值。"""
    singular = np.linalg.svd(matrix, compute_uv=False)
    if not len(singular) or singular[-1] <= tolerance * max(1.0, singular[0]):
        return None
    return float(2 * np.sum(np.log(singular)))


def _rank(matrix):
    return int(np.linalg.matrix_rank(matrix))


def _check(rows, count, label='候选矩阵'):
    matrix = _matrix(rows, label)
    if isinstance(count, bool) or not isinstance(count, Integral) or count < 1:
        raise ValueError('所选运行数必须是正整数')
    count = int(count)
    if count > len(matrix):
        raise ValueError('所选运行数不能超过候选行数')
    if count > len(set(map(tuple, matrix.tolist()))):
        raise ValueError('候选点不足：所选运行数超过不同候选行数')
    return matrix, count


def candidate_digest(rows):
    """候选行顺序无关的摘要；用于持久化候选集身份。"""
    matrix = _matrix(rows)
    unique = sorted(set(map(tuple, matrix.tolist())))
    encoded = json.dumps([[list(row), 1] for row in unique], allow_nan=False,
                         separators=(',', ':')).encode('utf-8')
    return hashlib.sha256(encoded).hexdigest()


def exact_select(rows, count):
    """小候选集穷举；返回 (选中行索引, logdet)，并列取字典序最小。"""
    matrix, count = _check(rows, count)
    if comb(len(matrix), count) > _MAX_EXACT_SUBSETS:
        raise ValueError('候选子集过大，不能精确穷举')
    best, best_value = None, None
    for indices in combinations(range(len(matrix)), count):
        value = _logdet(matrix[list(indices)])
        if value is None:
            continue
        if best_value is None or value > best_value + 1e-12:
            best, best_value = list(indices), value
    if best is None:
        raise ValueError('没有满秩候选子集，无法构造 D-optimal 设计')
    if _rank(matrix[best]) != matrix.shape[1]:
        raise ValueError('所选子集不是满列秩，无法构造 D-optimal 设计')
    return best, best_value


def _greedy(matrix, count, start, tally=None):
    """从 start 起步贪婪增加；允许暂时欠秩，不因 det=0 提前结束。"""
    chosen = [start] if start is not None else []
    remaining = [index for index in range(len(matrix)) if index != start]
    while len(chosen) < count:
        best, best_value = None, None
        for index in remaining:
            trial = chosen + [index]
            value = _logdet(matrix[trial])
            if tally is not None:
                tally[0] += 1
            # 尚未选够点时允许欠秩：先比秩再比 logdet，不能因 det=0 提前结束。
            score = (_rank(matrix[trial]),
                     value if value is not None else float('-inf'))
            if (best_value is None or score[0] > best_value[0]
                    or (score[0] == best_value[0]
                        and score[1] > best_value[1] + 1e-12)):
                best, best_value = index, score
        if best is None:
            raise ValueError('候选点不足以构成满秩设计')
        chosen.append(best)
        remaining.remove(best)
    return chosen


def _exchange(matrix, chosen, tally=None):
    """确定性交换改进；只接受真实改善，避免浮点噪声循环。"""
    chosen = list(chosen)
    current = _logdet(matrix[chosen])
    if current is None:
        return chosen, current
    for _ in range(_MAX_SWEEPS):
        improved = False
        outside = [index for index in range(len(matrix)) if index not in chosen]
        for position in range(len(chosen)):
            for candidate in outside:
                trial = chosen.copy()
                trial[position] = candidate
                value = _logdet(matrix[trial])
                if tally is not None:
                    tally[0] += 1
                if value is not None and value > current + 1e-12:
                    chosen, current = trial, value
                    improved = True
                    break
            if improved:
                break
        if not improved:
            break
    return chosen, current


def _search(matrix, count, seed):
    """多起点贪婪+交换；返回 (选中索引, logdet, 评价次数)。不宣称全局最优。"""
    import random
    rng = random.Random(0 if seed is None else int(seed))
    starts = [None] + list(range(min(len(matrix), 8)))
    rng.shuffle(starts)
    tally = [0]
    best, best_value = None, None
    for start in starts:
        try:
            trial = _greedy(matrix, count, start, tally)
        except ValueError:
            continue
        trial, value = _exchange(matrix, trial, tally)
        tally[0] += 1
        if value is None:
            continue
        if best_value is None or value > best_value + 1e-12:
            best, best_value = trial, value
    if best is None:
        raise ValueError('没有满秩候选子集，无法构造 D-optimal 设计')
    return best, best_value, tally[0]


def select(rows, count, *, seed=None, exact_limit=_MAX_EXACT_CANDIDATES):
    """选择候选行：预算内穷举，否则多起点贪婪+交换。

    精确搜索需同时满足候选规模与组合数预算，避免 "≤40 行" 却要求
    天文数字个子集（如 40 选 20）。返回字典包含实际方法、搜索预算与停止原因；
    只有真正完成穷举才标记 global_optimum_proven。
    """
    matrix, count = _check(rows, count)
    if seed is not None and (isinstance(seed, bool) or not isinstance(seed, Integral)):
        raise ValueError('seed 必须是整数或 None')
    subsets = comb(len(matrix), count)
    if len(matrix) <= exact_limit and subsets <= _MAX_EXACT_SUBSETS:
        chosen, value = exact_select(matrix, count)
        method = 'exact_enumeration'
        global_optimum, reason = True, '完成全部候选子集穷举'
        evaluations = subsets
    else:
        chosen, value, evaluations = _search(matrix, count, seed)
        method = 'greedy_exchange'
        global_optimum = False
        reason = ('候选行数超过精确搜索上限 ' + str(exact_limit)
                  if len(matrix) > exact_limit
                  else f'候选子集数 {subsets} 超过预算 {_MAX_EXACT_SUBSETS}')
    if _rank(matrix[list(chosen)]) != matrix.shape[1]:
        raise ValueError('所选子集不是满列秩，无法构造 D-optimal 设计')
    return {'indices': tuple(sorted(chosen)), 'selection_order': tuple(chosen),
            'logdet': float(value), 'rank': _rank(matrix[list(chosen)]),
            'p': matrix.shape[1], 'candidates': len(matrix), 'count': count,
            'method': method, 'global_optimum_proven': global_optimum,
            'seed': None if seed is None else int(seed),
            'exact_budget': _MAX_EXACT_SUBSETS, 'subsets': subsets,
            'evaluations': evaluations, 'stop_reason': reason}


def select_distance(points, count, *, kind='rsm', initial=()):
    """Distance-based 选点；只支持响应面（编码设计空间）。

    规则：起点取离编码原点最远的候选点；随后每次取到已选点集最小
    欧氏距离最大的候选点。并列时取候选行中索引最小者，保证可复现。
    混料距离合同依赖工作包 F，未建立前明确拒绝。

    initial 为必须保留的编码点（增补时即父设计运行）：此时不再从原点
    起选，直接把固定点并入已选点集，后续仍按最远点规则补点。
    """
    if kind != 'rsm':
        raise ValueError('Distance-based 选点当前只支持响应面设计')
    matrix, count = _check(points, count, '候选编码点')
    if matrix.shape[1] < 1:
        raise ValueError('候选编码点至少需要一个连续因子')
    fixed = _matrix(list(initial), '固定编码点') if len(initial) else None
    if fixed is not None and fixed.shape[1] != matrix.shape[1]:
        raise ValueError('固定点与候选点的编码维度不一致')
    remaining = set(range(len(matrix)))
    chosen = []
    if fixed is None:
        first = max(remaining, key=lambda index: (
            float(matrix[index] @ matrix[index]), -index))
        chosen.append(first)
        remaining.remove(first)
    # taken 以固定父设计点为起点；重复候选不再入选，避免静默复制相同运行。
    taken = [matrix[index] for index in chosen] + (
        [] if fixed is None else list(fixed))
    while len(chosen) < count:
        available = [index for index in sorted(remaining)
                     if all(not np.array_equal(matrix[index], point)
                            for point in taken)]
        if not available:
            raise ValueError('候选点不足：没有可用的新增候选点')
        picked = max(available, key=lambda index: (
            min(float(np.sum((matrix[index] - point) ** 2)) for point in taken),
            -index))
        chosen.append(picked)
        remaining.remove(picked)
        taken.append(matrix[picked])
    combined = taken
    distances = [float(np.sum((combined[a] - combined[b]) ** 2))
                 for a in range(len(combined)) for b in range(a + 1, len(combined))]
    return {'indices': tuple(sorted(chosen)), 'selection_order': tuple(chosen),
            'min_squared_distance': min(distances) if distances else None,
            'criterion': 'distance', 'candidates': len(matrix), 'count': count}


def evaluate(rows, *, det_limit=1e100):
    """固定模型/候选集的质量评价；不跨模型或运行数作优劣结论。"""
    matrix = _matrix(rows)
    singular = np.linalg.svd(matrix, compute_uv=False)
    rank = int(np.linalg.matrix_rank(matrix))
    condition = (float(singular[0] / singular[-1]) if len(singular)
                 and singular[-1] > 0 else None)
    value = _logdet(matrix)
    determinant = None
    if value is not None and value / 2 <= log(det_limit):
        determinant = float(np.exp(value))
    spacing = [float(np.sum((matrix[a] - matrix[b]) ** 2))
               for a in range(len(matrix))
               for b in range(a + 1, len(matrix))]
    return {'n': len(matrix), 'p': matrix.shape[1], 'rank': rank,
            'condition': condition, 'logdet': value, 'det_xtx': determinant,
            'singular': rank < matrix.shape[1],
            'min_squared_distance': min(spacing) if spacing else None,
            'distinct_rows': len(set(map(tuple, matrix.tolist())))}
