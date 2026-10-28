"""构建工作包 E 的独立数学参考；仅使用标准库与精确有理数运算。"""
from fractions import Fraction
from itertools import combinations, product
from math import comb, log
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def determinant(matrix):
    """Fraction 高斯消元；用于精确判定 X'X 是否奇异及最大行列式。"""
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
        inverse = 1 / work[column][column]
        for row in range(column + 1, size):
            factor = work[row][column] * inverse
            if factor:
                work[row] = [left - factor * right
                             for left, right in zip(work[row], work[column])]
    return result


def gram(matrix):
    """X'X：行数可为 n，列数为参数数。"""
    columns = [list(column) for column in zip(*matrix)]
    return [[sum(Fraction(left) * Fraction(right) for left, right in zip(column, other))
             for other in columns] for column in columns]


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


def criterion(matrix):
    value = determinant(gram(matrix))
    return value


def best_subset(matrix, count):
    """穷举全部子集；最大化 det(X'X)，并列取字典序最小的行索引。"""
    best, best_value = None, None
    for indices in combinations(range(len(matrix)), count):
        value = criterion([matrix[index] for index in indices])
        if best_value is None or value > best_value:
            best, best_value = indices, value
    return list(best), best_value


def exact_text(value):
    value = Fraction(value)
    return str(value.numerator) if value.denominator == 1 else f"{value.numerator}/{value.denominator}"


def effect_label(mask, names):
    if not mask:
        return "I"
    return "".join(names[index] for index in range(len(names)) if mask & (1 << index))


def alias_groups(names, defining):
    groups, seen = [], set()
    for mask in range(1 << len(names)):
        if mask in seen:
            continue
        partners = [mask]
        for relation in defining:
            partners.append(mask ^ relation)
        partners = sorted(set(partners))
        seen.update(partners)
        groups.append([effect_label(item, names) for item in partners])
    return groups


def two_level_rows(count, factors, generator=None):
    """按 A 变化最快的标准序生成两水平组合。"""
    rows = []
    for index in range(count):
        rows.append([-1 if not index & (1 << position) else 1
                     for position in range(factors)])
    if generator is not None:
        target, sources, sign = generator
        rows = [row[:target] + [sign * _product(row, sources)] + row[target + 1:]
                for row in rows]
    return rows


def _product(row, sources):
    value = 1
    for index in sources:
        value *= row[index]
    return value


def build():
    reference = {"version": 1,
                 "generated_by": "tests/fixtures/doe_optimal_reference/build_reference.py",
                 "sources": [
                     "Exact rational linear algebra; determinants by Fraction Gaussian elimination",
                     "D-optimality definition: maximize det(X'X) over fixed candidate rows",
                     "Distance-based rule: farthest coded point from the coded origin, then farthest from the selected set",
                     "Definitive screening necessary properties: main effects orthogonal and orthogonal to two-factor interactions",
                 ]}

    # 1. 两水平 2^3 自定义设计（文本水平），完整因子。
    names = ["A", "B", "C"]
    points = two_level_rows(8, 3)
    run_order = [3, 6, 1, 8, 5, 2, 7, 4]
    rows = []
    for index, point in enumerate(points):
        a, b, c = point
        rows.append({"run_id": f"C{index + 1:02d}", "standard_order": index + 1,
                     "run_order": run_order[index], "replicate": 1,
                     "settings": {name: ("低" if value < 0 else "高")
                                  for name, value in zip(names, point)},
                     "Y": 20 + 2 * a + 3 * b + 4 * c + 5 * a * b})
    matrix = [[1] + list(point) + [point[0] * point[1], point[0] * point[2],
                                   point[1] * point[2], point[0] * point[1] * point[2]]
              for point in points]
    information = gram(matrix)
    coefficients = []
    for column in range(len(matrix[0])):
        total = sum(Fraction(matrix[row][column] * rows[row]["Y"]) for row in range(8))
        coefficients.append(total / 8)
    # 矩阵列顺序为 1, A, B, C, AB, AC, BC, ABC（主效应在前）。
    column_masks = [0, 1, 2, 4, 3, 5, 6, 7]
    column_terms = [effect_label(mask, names) if mask else "I" for mask in column_masks]
    reference["custom_factorial_2x3"] = {
        "factors": [{"id": name, "kind": "text", "levels": ["低", "高"]} for name in names],
        "terms": column_terms,
        "rows": rows,
        "expected": {
            "n": 8, "p": 8, "rank": 8, "full_factorial": True,
            "regular_fraction": True, "unique_points": 8,
            "det_xtx": exact_text(determinant(information)),
            "logdet": log(float(determinant(information))),
            "coefficients": {term: exact_text(value)
                             for term, value in zip(column_terms, coefficients)},
            "alias_groups": [[item] for item in column_terms],
        },
    }

    # 2. 2×3 分类一般全因子候选集；参考水平编码，D-optimal 选 4 行。
    categorical = []
    for a in ("低", "高"):
        for b in (100, 150, 200):
            categorical.append([1, 1 if a == "高" else 0,
                                1 if b == 150 else 0, 1 if b == 200 else 0])
    selected, value = best_subset(categorical, 4)
    reference["categorical_candidates"] = {
        "levels": {"A": ["低", "高"], "B": [100, 150, 200]},
        "terms": ["I", "A", "B"],
        "columns": ["I", "A[高]", "B[150]", "B[200]"],
        "candidates": categorical,
        "select": 4,
        "expected": {"selected": selected, "det_xtx": exact_text(value),
                     "rank": rank([categorical[index] for index in selected])},
    }

    # 3. 小型响应面候选集：3×3 网格、完整二次模型、选 6 行。
    grid = []
    for x1 in (-1, 0, 1):
        for x2 in (-1, 0, 1):
            grid.append([1, x1, x2, x1 * x1, x2 * x2, x1 * x2])
    selected, value = best_subset(grid, 6)
    reference["rsm_candidates"] = {
        "terms": ["I", "X1", "X2", "X1²", "X2²", "X1*X2"],
        "candidates": grid,
        "select": 6,
        "expected": {"selected": selected, "det_xtx": exact_text(value),
                     "rank": rank([grid[index] for index in selected])},
    }

    # 4. 已知秩亏矩阵。
    deficient = [[1, 1, 2], [1, 2, 3], [1, 3, 4]]
    reference["rank_deficient"] = {
        "matrix": deficient,
        "expected": {"rank": rank(deficient), "p": 3,
                     "det_xtx": exact_text(determinant(gram(deficient)))},
    }

    # 5. D-optimal 最小穷举：x∈{-1,0,1}、截距+线性、选 2 点。
    simple = [[1, -1], [1, 0], [1, 1]]
    selected, value = best_subset(simple, 2)
    reference["d_optimal_simple"] = {
        "candidates": simple, "select": 2,
        "expected": {"selected": selected, "det_xtx": exact_text(value),
                     "logdet": log(float(value)), "subsets": comb(3, 2)},
    }

    # 6. 并列最优：正方形四角选 3 点，四个子集行列式相同。
    corners = [[1, -1, -1], [1, -1, 1], [1, 1, -1], [1, 1, 1]]
    values = {indices: criterion([corners[index] for index in indices])
              for indices in combinations(range(4), 3)}
    best_value = max(values.values())
    reference["d_optimal_tie"] = {
        "candidates": corners, "select": 3,
        "expected": {"selected": list(combinations(range(4), 3))[0],
                     "det_xtx": exact_text(best_value),
                     "tied_subsets": sorted([list(key) for key, value in values.items()
                                             if value == best_value])},
    }

    # 7. Distance-based 手算点集：四角、四轴点与中心，选 4 点。
    distance_points = [[1, 1], [-1, 1], [-1, -1], [1, -1],
                       [1, 0], [0, 1], [-1, 0], [0, -1], [0, 0]]
    order = []
    remaining = set(range(len(distance_points)))
    first = max(remaining, key=lambda index: (sum(value * value
                                                 for value in distance_points[index]), -index))
    order.append(first)
    remaining.remove(first)
    while len(order) < 4:
        def spread(index):
            return min(sum((left - right) ** 2
                           for left, right in zip(distance_points[index],
                                                  distance_points[chosen]))
                       for chosen in order)
        chosen = max(remaining, key=lambda index: (spread(index), -index))
        order.append(chosen)
        remaining.remove(chosen)
    reference["distance_rsm"] = {
        "points": distance_points, "select": 4,
        "expected": {"order": order,
                     "squared_distances": [[sum((left - right) ** 2
                                                for left, right in zip(distance_points[a],
                                                                       distance_points[b]))
                                            for b in order] for a in order]},
    }

    # 8. 固定初始设计（秩亏）与增补候选：完整二次模型增补 2 行。
    initial = [[1, 1, 1], [1, 1, -1], [1, -1, 1], [1, -1, -1]]
    candidates = [[1, 1.5, 0], [1, 0, 1.5], [1, -1.5, 0], [1, 0, -1.5], [1, 0, 0]]

    def quadratic(row):
        x1, x2 = row[1], row[2]
        return [1, x1, x2, x1 * x1, x2 * x2, x1 * x2]

    initial_model = [quadratic(row) for row in initial]
    candidate_model = [quadratic(row) for row in candidates]
    best, best_value = None, None
    for indices in combinations(range(len(candidate_model)), 2):
        combined = initial_model + [candidate_model[index] for index in indices]
        if rank(combined) < 6:
            continue
        value = criterion(combined)
        if best_value is None or value > best_value:
            best, best_value = list(indices), value
    reference["augment_initial"] = {
        "initial": initial, "candidates": candidates, "select": 2,
        "terms": ["I", "X1", "X2", "X1²", "X2²", "X1*X2"],
        "expected": {"initial_rank": rank(initial_model),
                     "initial_det": exact_text(criterion(initial_model)),
                     "selected": best, "det_xtx": exact_text(best_value),
                     "logdet": log(float(best_value)),
                     "augmented_rank": rank(initial_model + [candidate_model[i] for i in best])},
    }

    # 8b. Distance-based 增补：四角固定父设计 + 中心/边中点候选，补 2 行。
    # 固定点参与“距已选集合最远”判定，因此新增点不是 D-optimal 解。
    # 手算：中心点到四角距离均为 2，边中点到相邻两角为 1，故首点为中心；
    # 之后四个边中点最小距离同为 1（到中心 1、到相邻角 1），并列取索引最小者。
    distance_initial = [[1, 1], [-1, 1], [-1, -1], [1, -1]]
    distance_candidates = [[0, 0], [1, 0], [0, 1], [-1, 0], [0, -1]]
    distance_order = []
    distance_remaining = list(range(len(distance_candidates)))
    anchors = list(distance_initial)
    while len(distance_order) < 2:
        def spread(index):
            return min(sum((left - right) ** 2
                           for left, right in zip(distance_candidates[index], anchor))
                       for anchor in anchors)
        picked = max(distance_remaining, key=lambda index: (spread(index), -index))
        distance_order.append(picked)
        distance_remaining.remove(picked)
        anchors.append(distance_candidates[picked])
    chosen_points = [distance_candidates[index] for index in distance_order]
    reference["distance_augment"] = {
        "initial": distance_initial, "candidates": distance_candidates,
        "select": 2,
        "expected": {
            "order": distance_order,
            "fixed_min_squared_distance": min(
                sum((left - right) ** 2 for left, right in zip(a, b))
                for position, a in enumerate(distance_initial)
                for b in distance_initial[position + 1:]),
            "augmented_min_squared_distance": min(
                sum((left - right) ** 2 for left, right in zip(a, b))
                for position, a in enumerate(anchors)
                for b in anchors[position + 1:]),
            "selected_points": chosen_points,
        },
    }

    # 9. 自定义响应面矩阵：2^3 因子点 + 6 轴点 + 3 中心点，完整二次模型。
    alpha = 1.682
    rows = []
    for point in two_level_rows(8, 3):
        rows.append({"point_type": "factorial", "coded": point})
    for axis in range(3):
        for sign in (-1, 1):
            coded = [0, 0, 0]
            coded[axis] = sign * alpha
            rows.append({"point_type": "axial", "coded": coded})
    for _ in range(3):
        rows.append({"point_type": "center", "coded": [0, 0, 0]})
    model = []
    for row in rows:
        x1, x2, x3 = row["coded"]
        model.append([1, x1, x2, x3, x1 * x1, x2 * x2, x3 * x3,
                      x1 * x2, x1 * x3, x2 * x3])
    information = gram(model)
    value = determinant(information)
    reference["custom_rsm"] = {
        "alpha": alpha,
        "terms": ["I", "X1", "X2", "X3", "X1²", "X2²", "X3²",
                  "X1*X2", "X1*X3", "X2*X3"],
        "rows": rows,
        "expected": {"n": len(rows), "p": 10, "rank": rank(model),
                     "det_xtx": exact_text(value), "logdet": log(float(value)),
                     "center_rows": 3, "axial_rows": 6, "factorial_rows": 8},
    }

    # 10. 自定义 DSD：6 因子会议矩阵 foldover + 中心行。
    # 会议矩阵取自 C0 已独立核验的 conference 构造（X1..X6 顺序，全 ±1 行）。
    conference = [
        [0, 1, 1, 1, 1, 1],
        [1, 0, -1, 1, 1, -1],
        [1, -1, 0, 1, -1, 1],
        [1, 1, 1, 0, -1, -1],
        [1, 1, -1, -1, 0, 1],
        [1, -1, 1, -1, 1, 0],
    ]
    dsd = conference + [[-value for value in row] for row in conference] + [[0] * 6]
    main = [[1] + row for row in dsd]
    two_factor = []
    for first, second in combinations(range(6), 2):
        two_factor.append([row[first] * row[second] for row in dsd])
    main_columns = [[row[index] for row in dsd] for index in range(6)]
    cross = [[sum(left * right for left, right in zip(main_column, interaction))
              for interaction in two_factor] for main_column in main_columns]
    diagonal = [sum(value * value for value in column) for column in main_columns]
    main_cross = [[sum(left * right for left, right in zip(first, second))
                   for second in main_columns] for first in main_columns]
    reference["custom_dsd"] = {
        "matrix": dsd,
        "continuous_factors": 6,
        "categorical_factors": 0,
        "expected": {
            "n": len(dsd), "center_rows": 1, "main_rank": rank(main),
            "main_sums_of_squares": diagonal,
            "main_orthogonal": all(value == 0 for i, row in enumerate(main_cross)
                                   for j, value in enumerate(row) if i != j),
            "main_two_factor_orthogonal": all(value == 0 for row in cross for value in row),
            "zero_per_factor": [sum(value == 0 for value in column) for column in main_columns],
        },
    }
    # 4 连续 + 1 两水平文本分类（C0 已核验的 jones.dsd4c1 构造）。
    text_matrix = [
        [0, 1, 1, 1, 1], [1, 0, 1, -1, -1], [1, 1, 0, 1, -1],
        [1, -1, 1, 0, 1], [1, -1, -1, 1, 1], [1, 1, -1, -1, 1],
        [0, -1, -1, -1, -1], [-1, 0, -1, 1, 1], [-1, -1, 0, -1, 1],
        [-1, 1, -1, 0, -1], [-1, 1, 1, -1, -1], [-1, -1, 1, 1, -1],
        [0, 0, 0, 0, 1], [0, 0, 0, 0, -1],
    ]
    text_dsd = {"continuous_factors": 4, "categorical_factors": 1,
                "levels": {"E": ["低", "高"]},
                "matrix": text_matrix,
                "expected": {"n": len(text_matrix), "pseudo_center_rows": 2}}
    main_text = [[row[index] for row in text_matrix] for index in range(5)]
    # 混合 DSD：主效应彼此可以相关（分类列与连续列 ±2），但主效应与
    # 二因子交互必须正交；这是官方 DSD 结构而非额外假设。
    pairs = [(a, b) for a in range(5) for b in range(a + 1, 5)]
    text_dsd["expected"]["main_two_factor_orthogonal"] = all(
        sum(main_text[a][row] * main_text[b][row] * main_text[c][row]
            for row in range(len(text_matrix))) == 0
        for a in range(5) for b, c in pairs)
    text_dsd["expected"]["main_cross_products"] = {
        f"{a + 1}{b + 1}": sum(left * right for left, right in
                               zip(main_text[a], main_text[b]))
        for a, b in pairs}
    reference["custom_dsd_text"] = text_dsd

    # 11. 修改运行顺序与新增批次的工程案例：2^(4-1) 父设计。
    parent = two_level_rows(8, 4, generator=(3, (0, 1, 2), 1))
    parent_rows = []
    parent_order = [5, 2, 7, 4, 1, 8, 3, 6]
    for index, point in enumerate(parent):
        parent_rows.append({"run_id": f"R{index + 1:05d}", "standard_order": index + 1,
                            "run_order": parent_order[index],
                            "settings": dict(zip("ABCD", point)),
                            "Y": 10 + point[0] + 2 * point[1]})
    renumbered = sorted(parent_rows, key=lambda row: row["run_order"])
    reference["modify_and_batch"] = {
        "parent": parent_rows,
        "expected": {
            "renumbered": [{"run_id": row["run_id"], "run_order": position + 1}
                           for position, row in enumerate(renumbered)],
            "defining_relation": "I=ABCD",
            "resolution": 4,
            "parent_rank": rank([[1] + [row["settings"][name] for name in "ABCD"]
                                 for row in parent_rows]),
            "batch_rows": 4,
            "batch_ids": [f"A{index + 1:05d}" for index in range(4)],
        },
    }
    return reference


def main():
    reference = build()
    encoded = (json.dumps(reference, ensure_ascii=False, indent=2, sort_keys=True)
               + "\n").encode("utf-8")
    (ROOT / "reference.json").write_bytes(encoded)
    manifest = {"reference.json": {
        "sha256": hashlib.sha256(encoded).hexdigest(),
        "source": "build_reference.py; standard-library exact rational derivations",
        "production_imports": [],
    }}
    (ROOT / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("reference built:", manifest["reference.json"]["sha256"])


if __name__ == "__main__":
    main()
