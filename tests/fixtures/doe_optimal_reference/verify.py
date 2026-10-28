"""独立复算工作包 E 参考；不导入任何生产模块或优化器。"""
from fractions import Fraction
from itertools import combinations
from hashlib import sha256
from math import log
import json
import math
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def gram(matrix):
    """独立实现 X'X，允许行数不等于参数数。"""
    columns = [list(column) for column in zip(*matrix)]
    return [[sum(Fraction(left) * Fraction(right) for left, right in zip(column, other))
             for other in columns] for column in columns]


def determinant(matrix):
    size = len(matrix)
    work = [[Fraction(value) for value in row] for row in matrix]
    result = Fraction(1)
    for column in range(size):
        pivot = next((row for row in range(column, size) if work[row][column]), None)
        if pivot is None:
            return Fraction(0)
        if pivot != column:
            work[column], work[pivot] = work[pivot], work[column]
            result = -result
        result *= work[column][column]
        for row in range(column + 1, size):
            factor = work[row][column] / work[column][column]
            if factor:
                work[row] = [left - factor * right
                             for left, right in zip(work[row], work[column])]
    return result


def rank(matrix):
    rows = [[Fraction(value) for value in row] for row in matrix]
    if not rows:
        return 0
    current = 0
    for column in range(len(rows[0])):
        pivot = next((row for row in range(current, len(rows)) if rows[row][column]), None)
        if pivot is None:
            continue
        rows[current], rows[pivot] = rows[pivot], rows[current]
        for row in range(current + 1, len(rows)):
            if rows[row][column]:
                factor = rows[row][column] / rows[current][column]
                rows[row] = [left - factor * right
                             for left, right in zip(rows[row], rows[current])]
        current += 1
    return current


def exact(value):
    value = Fraction(value)
    return str(value.numerator) if value.denominator == 1 else f"{value.numerator}/{value.denominator}"


def close(actual, expected):
    assert math.isclose(actual, expected, rel_tol=1e-12, abs_tol=1e-12), (actual, expected)


def best(matrix, count):
    chosen, value = None, None
    for indices in combinations(range(len(matrix)), count):
        candidate = determinant(gram([matrix[index] for index in indices]))
        if value is None or candidate > value:
            chosen, value = list(indices), candidate
    return chosen, value


def verify():
    path = ROOT / "reference.json"
    manifest = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))
    assert sha256(path.read_bytes()).hexdigest() == manifest["reference.json"]["sha256"]
    reference = json.loads(path.read_text(encoding="utf-8"))

    # 1. 两水平 2^3 自定义设计
    custom = reference["custom_factorial_2x3"]
    rows = custom["rows"]
    assert len(rows) == 8 and {row["run_id"] for row in rows} == {
        f"C{index:02d}" for index in range(1, 9)}
    assert sorted(row["standard_order"] for row in rows) == list(range(1, 9))
    assert sorted(row["run_order"] for row in rows) == list(range(1, 9))
    levels = {tuple(row["settings"][name] for name in "ABC") for row in rows}
    assert levels == {combination for combination in
                      __import__("itertools").product(("低", "高"), repeat=3)}
    coded = [[1 if row["settings"][name] == "高" else -1 for name in "ABC"]
             for row in rows]
    design = [[1] + point + [point[0] * point[1], point[0] * point[2],
                             point[1] * point[2], point[0] * point[1] * point[2]]
              for point in coded]
    information = gram(design)
    assert information == [[8 if i == j else 0 for j in range(8)] for i in range(8)]
    assert exact(determinant(information)) == custom["expected"]["det_xtx"] == str(8 ** 8)
    close(log(float(determinant(information))), custom["expected"]["logdet"])
    expected_coefficients = custom["expected"]["coefficients"]
    for column, term in enumerate(custom["terms"]):
        estimate = sum(Fraction(design[row][column] * rows[row]["Y"])
                       for row in range(8)) / 8
        assert exact(estimate) == expected_coefficients[term], term
    assert (expected_coefficients["A"], expected_coefficients["B"],
            expected_coefficients["C"], expected_coefficients["AB"]) == ("2", "3", "4", "5")

    # 2. 分类候选集 D-optimal
    categorical = reference["categorical_candidates"]
    chosen, value = best(categorical["candidates"], categorical["select"])
    assert chosen == categorical["expected"]["selected"]
    assert exact(value) == categorical["expected"]["det_xtx"]
    assert rank([categorical["candidates"][index] for index in chosen]) == 4
    # 4 行 4 列：det(X'X) 最大不超过每列满平方的乘积。
    assert value > 0

    # 3. 响应面候选集 D-optimal
    rsm = reference["rsm_candidates"]
    chosen, value = best(rsm["candidates"], rsm["select"])
    assert chosen == rsm["expected"]["selected"]
    assert exact(value) == rsm["expected"]["det_xtx"]
    assert rank([rsm["candidates"][index] for index in chosen]) == 6

    # 4. 秩亏矩阵
    deficient = reference["rank_deficient"]
    assert rank(deficient["matrix"]) == deficient["expected"]["rank"] == 2
    assert exact(determinant(gram(deficient["matrix"]))) == "0"

    # 5. 最小穷举 D-optimal：x∈{-1,0,1}，截距+线性，选 2 点
    simple = reference["d_optimal_simple"]
    assert simple["candidates"] == [[1, -1], [1, 0], [1, 1]]
    assert len(list(combinations(range(3), 2))) == simple["expected"]["subsets"] == 3
    chosen, value = best(simple["candidates"], 2)
    assert chosen == simple["expected"]["selected"] == [0, 2]
    assert exact(value) == simple["expected"]["det_xtx"] == "4"
    assert determinant(gram([simple["candidates"][0], simple["candidates"][1]])) == 1
    assert determinant(gram([simple["candidates"][1], simple["candidates"][2]])) == 1
    close(log(float(value)), simple["expected"]["logdet"])

    # 6. 并列最优
    tie = reference["d_optimal_tie"]
    values = {tuple(indices): determinant(gram([tie["candidates"][index]
                                               for index in indices]))
              for indices in combinations(range(4), 3)}
    best_value = max(values.values())
    assert exact(best_value) == tie["expected"]["det_xtx"]
    assert sorted([list(key) for key, value in values.items() if value == best_value]
                  ) == sorted(tie["expected"]["tied_subsets"])
    assert len(tie["expected"]["tied_subsets"]) == 4

    # 7. Distance-based 手算点集
    distance = reference["distance_rsm"]
    points = distance["points"]
    order, remaining = [], set(range(len(points)))
    first = max(remaining, key=lambda index: (sum(v * v for v in points[index]), -index))
    order.append(first)
    remaining.remove(first)
    while len(order) < distance["select"]:
        def spread(index):
            return min(sum((left - right) ** 2
                           for left, right in zip(points[index], points[chosen]))
                       for chosen in order)
        chosen = max(remaining, key=lambda index: (spread(index), -index))
        order.append(chosen)
        remaining.remove(chosen)
    assert order == distance["expected"]["order"]
    assert len(set(order)) == len(order)
    assert [sum(v * v for v in points[order[0]])] == [2]
    squared = [[sum((left - right) ** 2 for left, right in zip(points[a], points[b]))
                for b in order] for a in order]
    assert squared == distance["expected"]["squared_distances"]
    # 四角点两两距离为 4；中心点与轴点均不进入该顺序。
    assert min(squared[index][j] for index in range(len(order))
               for j in range(len(order)) if index != j) == 4
    assert 8 not in order and order[0] == 0

    # 8. 固定初始设计 + 增补
    augment = reference["augment_initial"]
    def quadratic(row):
        return [1, row[1], row[2], row[1] ** 2, row[2] ** 2, row[1] * row[2]]
    initial = [quadratic(row) for row in augment["initial"]]
    candidates = [quadratic(row) for row in augment["candidates"]]
    # 四角点上 x1²、x2² 与截距共线，只剩 4 个独立方向，故固定初始集欠秩。
    assert rank(initial) == augment["expected"]["initial_rank"] == 4 < 6
    assert exact(determinant(gram(initial))) == "0"
    chosen, value = None, None
    for indices in combinations(range(len(candidates)), augment["select"]):
        combined = initial + [candidates[index] for index in indices]
        if rank(combined) < 6:
            continue
        candidate = determinant(gram(combined))
        if value is None or candidate > value:
            chosen, value = list(indices), candidate
    assert chosen == augment["expected"]["selected"]
    assert exact(value) == augment["expected"]["det_xtx"]
    close(log(float(value)), augment["expected"]["logdet"])
    assert rank(initial + [candidates[index] for index in chosen]) == 6

    # 8b. Distance-based 增补：固定四角 + 中心/轴点候选，独立按最远点规则复算。
    distance_augment = reference["distance_augment"]
    fixed_points = distance_augment["initial"]
    pool = distance_augment["candidates"]
    order, remaining = [], list(range(len(pool)))
    anchors = [list(point) for point in fixed_points]
    while len(order) < distance_augment["select"]:
        def nearest(index):
            return min(sum((left - right) ** 2
                           for left, right in zip(pool[index], anchor))
                       for anchor in anchors)
        picked = max(remaining, key=lambda index: (nearest(index), -index))
        order.append(picked)
        remaining.remove(picked)
        anchors.append(list(pool[picked]))
    assert order == distance_augment["expected"]["order"] == [0, 1]
    # 手算：中心点到四角距离 2，边中点到最近两角 1，故中心先入选。
    assert sum(value * value for value in pool[order[0]]) == 0
    assert min(sum((left - right) ** 2 for left, right in zip(pool[order[0]], corner))
               for corner in fixed_points) == 2
    assert [pool[index] for index in order] == \
        distance_augment["expected"]["selected_points"]
    fixed_spacing = min(sum((left - right) ** 2 for left, right in zip(a, b))
                        for position, a in enumerate(fixed_points)
                        for b in fixed_points[position + 1:])
    assert fixed_spacing == distance_augment["expected"]["fixed_min_squared_distance"] == 4
    augmented_spacing = min(sum((left - right) ** 2 for left, right in zip(a, b))
                            for position, a in enumerate(anchors)
                            for b in anchors[position + 1:])
    # 边中点到相邻两角距离 1，成为增补后的最小间距。
    assert augmented_spacing == \
        distance_augment["expected"]["augmented_min_squared_distance"] == 1

    # 9. 自定义响应面矩阵
    custom_rsm = reference["custom_rsm"]
    model = []
    for row in custom_rsm["rows"]:
        x1, x2, x3 = row["coded"]
        model.append([1, x1, x2, x3, x1 * x1, x2 * x2, x3 * x3,
                      x1 * x2, x1 * x3, x2 * x3])
    assert len(model) == custom_rsm["expected"]["n"] == 17
    assert rank(model) == custom_rsm["expected"]["rank"] == 10
    value = determinant(gram(model))
    assert exact(value) == custom_rsm["expected"]["det_xtx"]
    close(log(float(value)), custom_rsm["expected"]["logdet"])
    types = [row["point_type"] for row in custom_rsm["rows"]]
    assert types.count("factorial") == 8 and types.count("axial") == 6
    assert types.count("center") == 3
    assert all(math.isclose(abs(value) - 1.682, 0, abs_tol=1e-12)
               for row in custom_rsm["rows"] if row["point_type"] == "axial"
               for value in row["coded"] if value)

    # 10. 自定义 DSD 构造性质
    dsd = reference["custom_dsd"]
    matrix = dsd["matrix"]
    assert len(matrix) == dsd["expected"]["n"] == 13
    assert sum(all(value == 0 for value in row) for row in matrix) == 1
    columns = [[row[index] for row in matrix] for index in range(6)]
    for first, second in combinations(columns, 2):
        assert sum(left * right for left, right in zip(first, second)) == 0
    for column in columns:
        for other in combinations(range(6), 2):
            interaction = [row[other[0]] * row[other[1]] for row in matrix]
            assert sum(left * right for left, right in zip(column, interaction)) == 0
    # 每列 3 个零（会议行、折叠行、中心行），故平方和为 10。
    assert dsd["expected"]["main_sums_of_squares"] == [10] * 6
    assert dsd["expected"]["main_orthogonal"] is True
    assert dsd["expected"]["zero_per_factor"] == [3] * 6
    assert rank([[1] + row for row in matrix]) == dsd["expected"]["main_rank"] == 7
    text_dsd = reference["custom_dsd_text"]
    assert text_dsd["levels"] == {"E": ["低", "高"]}
    assert len(text_dsd["matrix"]) == text_dsd["expected"]["n"]
    text_main = [[row[index] for row in text_dsd["matrix"]] for index in range(5)]
    assert text_dsd["expected"]["main_two_factor_orthogonal"] is True
    for a in range(5):
        for b, c in [(x, y) for x in range(5) for y in range(x + 1, 5)]:
            assert sum(text_main[a][row] * text_main[b][row] * text_main[c][row]
                       for row in range(len(text_dsd["matrix"]))) == 0
    assert text_dsd["expected"]["main_cross_products"]["15"] == 2
    assert sum(1 for row in text_dsd["matrix"] if row[4] == 1) == 7

    # 11. 修改运行顺序与新增批次
    modify = reference["modify_and_batch"]
    parent = modify["parent"]
    assert len(parent) == 8
    assert sorted(row["run_order"] for row in parent) == list(range(1, 9))
    renumbered = sorted(parent, key=lambda row: row["run_order"])
    assert modify["expected"]["renumbered"] == [
        {"run_id": row["run_id"], "run_order": position + 1}
        for position, row in enumerate(renumbered)]
    coded = [[1] + [row["settings"][name] for name in "ABCD"] for row in parent]
    assert rank(coded) == modify["expected"]["parent_rank"] == 5
    assert all(row["settings"]["D"] == row["settings"]["A"] * row["settings"]["B"]
               * row["settings"]["C"] for row in parent)
    assert modify["expected"]["defining_relation"] == "I=ABCD"
    assert len(modify["expected"]["batch_ids"]) == modify["expected"]["batch_rows"] == 4
    return True


if __name__ == "__main__":
    verify()
    print("optimal design independent references verified")
