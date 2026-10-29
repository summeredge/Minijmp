"""Build exact, production-independent Mixture optimal-design references."""
from fractions import Fraction as F
from itertools import combinations, combinations_with_replacement
from hashlib import sha256
from math import comb, log, prod
from pathlib import Path
import json


ROOT = Path(__file__).resolve().parent


def determinant(matrix):
    work = [list(map(F, row)) for row in matrix]
    if not work:
        return F(1)
    result = F(1)
    for column in range(len(work)):
        pivot = next((row for row in range(column, len(work))
                      if work[row][column]), None)
        if pivot is None:
            return F(0)
        if pivot != column:
            work[column], work[pivot] = work[pivot], work[column]
            result = -result
        value = work[column][column]
        result *= value
        for row in range(column + 1, len(work)):
            multiplier = work[row][column] / value
            for index in range(column + 1, len(work)):
                work[row][index] -= multiplier * work[column][index]
            work[row][column] = F(0)
    return result


def rank(matrix):
    work = [list(map(F, row)) for row in matrix]
    row = 0
    for column in range(len(work[0]) if work else 0):
        pivot = next((index for index in range(row, len(work))
                      if work[index][column]), None)
        if pivot is None:
            continue
        work[row], work[pivot] = work[pivot], work[row]
        scale = work[row][column]
        work[row] = [value / scale for value in work[row]]
        for index in range(len(work)):
            if index != row and work[index][column]:
                scale = work[index][column]
                work[index] = [a - scale * b
                               for a, b in zip(work[index], work[row])]
        row += 1
        if row == len(work):
            break
    return row


def cross_product(left, right):
    return sum((a * b for a, b in zip(left, right)), F(0))


def information_matrix(rows):
    width = len(rows[0])
    return [[sum((row[i] * row[j] for row in rows), F(0))
             for j in range(width)] for i in range(width)]


def d_optimal(rows, count, allow_repeats=False):
    choices = (combinations_with_replacement(range(len(rows)), count)
               if allow_repeats else combinations(range(len(rows)), count))
    best, optima = None, []
    for choice in choices:
        value = determinant(information_matrix([rows[index] for index in choice]))
        if value <= 0:
            continue
        if best is None or value > best:
            best, optima = value, [choice]
        elif value == best:
            optima.append(choice)
    return best, optima


def d_optimal_augment(initial, candidates, count, allow_repeats=False):
    pool = range(len(candidates))
    choices = (combinations_with_replacement(pool, count) if allow_repeats
               else combinations(pool, count))
    best, optima = None, []
    for choice in choices:
        rows = list(initial) + [candidates[index] for index in choice]
        value = determinant(information_matrix(rows))
        if value <= 0:
            continue
        if best is None or value > best:
            best, optima = value, [choice]
        elif value == best:
            optima.append(choice)
    return best, optima


def unique_points(points):
    seen, kept, duplicates = set(), [], []
    for index, point in enumerate(points):
        key = tuple(point)
        if key in seen:
            duplicates.append(index)
        else:
            seen.add(key)
            kept.append(index)
    return kept, duplicates


def squared_distance(left, right):
    return sum(((a - b) ** 2 for a, b in zip(left, right)), F(0))


def mixture_distance(points, count, component_count, fixed=()):
    remaining = list(range(len(points)))
    chosen, steps = [], []
    if not fixed:
        pure = [tuple(F(i == j) for i in range(component_count))
                for j in range(component_count)]
        first_scores = [min(squared_distance(point[:component_count], target)
                            for target in pure) for point in points]
        first = min(remaining, key=lambda index: (first_scores[index], index))
        chosen.append(first)
        remaining.remove(first)
        steps.append(first_scores[first])
    anchors = [tuple(point) for point in fixed] + [points[i] for i in chosen]
    while len(chosen) < count:
        available = [index for index in remaining
                     if all(points[index] != anchor for anchor in anchors)]
        if not available:
            raise ValueError("candidate shortage")
        scores = {index: min(squared_distance(points[index], anchor)
                             for anchor in anchors) for index in available}
        best = max(available, key=lambda index: (scores[index], -index))
        chosen.append(best)
        remaining.remove(best)
        anchors.append(points[best])
        steps.append(scores[best])
    return chosen, steps


def feasible(point, bounds, constraints):
    return (sum(point, F(0)) == 1
            and all(low <= value <= high
                    for value, (low, high) in zip(point, bounds))
            and all(cross_product(coefficients, point) <= limit
                    for coefficients, limit in constraints))


def scheffe_row(settings, terms):
    return [prod(settings[name] for name in term.split("*"))
            for term in terms]


def encode(value):
    if isinstance(value, F):
        return str(value.numerator) if value.denominator == 1 else f"{value.numerator}/{value.denominator}"
    if isinstance(value, tuple):
        return [encode(item) for item in value]
    if isinstance(value, list):
        return [encode(item) for item in value]
    if isinstance(value, dict):
        return {key: encode(item) for key, item in value.items()}
    return value


def build():
    simplex = [
        (F(1), F(0), F(0)), (F(0), F(1), F(0)), (F(0), F(0), F(1)),
        (F(1, 2), F(1, 2), F(0)), (F(1, 2), F(0), F(1, 2)),
        (F(0), F(1, 2), F(1, 2)), (F(1, 3), F(1, 3), F(1, 3)),
    ]
    distance_order, distance_steps = mixture_distance(simplex, 5, 3)

    quadratic_terms = ["A", "B", "C", "A*B", "A*C", "B*C"]
    quadratic_rows = [scheffe_row(dict(zip(("A", "B", "C"), point)),
                                  quadratic_terms) for point in simplex]
    quadratic_det, quadratic_optima = d_optimal(quadratic_rows, 6)

    bounds = [(F(1, 10), F(3, 5)), (F(1, 10), F(7, 10)),
              (F(0), F(7, 10))]
    constraints = [([F(1), F(2), F(0)], F(11, 10))]
    constrained_points = [
        (F(1, 5), F(1, 5), F(3, 5)),
        (F(1, 2), F(1, 5), F(3, 10)),
        (F(1, 5), F(2, 5), F(2, 5)),
        (F(3, 5), F(1, 5), F(1, 5)),
        (F(1, 5), F(1, 2), F(3, 10)),
        (F(1, 20), F(1, 5), F(3, 4)),
    ]
    feasible_indices = [i for i, point in enumerate(constrained_points)
                        if feasible(point, bounds, constraints)]
    constrained_rows = [list(constrained_points[i]) for i in feasible_indices]
    constrained_det, constrained_optima = d_optimal(constrained_rows, 3)

    process_terms = ["A", "B", "C", "A*P", "B*P", "C*P"]
    process_rows, process_settings = [], []
    for component_index, point in enumerate(simplex[:3]):
        for process in (F(0), F(10)):
            coded = 2 * (process - F(0)) / (F(10) - F(0)) - 1
            settings = dict(zip(("A", "B", "C"), point))
            settings["P"] = coded
            process_settings.append({"components": point, "process": process,
                                     "coded_process": coded})
            process_rows.append(scheffe_row(settings, process_terms))

    linear_terms = ["A", "B", "C"]
    vertices = simplex[:3]
    linear_rows = [scheffe_row(dict(zip(("A", "B", "C"), point)),
                               linear_terms) for point in vertices]
    no_repeat_det, no_repeat_optima = d_optimal(linear_rows, 3)
    repeat_det, repeat_optima = d_optimal(linear_rows, 4, allow_repeats=True)
    duplicate_input = vertices + [vertices[0]]
    unique_indices, duplicate_indices = unique_points(duplicate_input)
    duplicate_rows = [scheffe_row(dict(zip(("A", "B", "C"), duplicate_input[i])),
                                  linear_terms) for i in unique_indices]
    duplicate_repeat_det, duplicate_repeat_optima = d_optimal(
        duplicate_rows, 4, allow_repeats=True)
    distance_unique_indices, distance_duplicate_indices = unique_points(
        simplex[:3] + [simplex[0]])
    distance_points = [simplex[i] for i in distance_unique_indices]
    no_repeat_distance_order, _ = mixture_distance(distance_points, 3, 3)

    augmentation_parent = [linear_rows[0]]
    augmentation_candidates = linear_rows[1:]
    augment_det, augment_optima = d_optimal_augment(
        augmentation_parent, augmentation_candidates, 2)
    repeat_augment_det, repeat_augment_optima = d_optimal_augment(
        augmentation_parent, augmentation_candidates, 3, allow_repeats=True)
    distance_augment_order, distance_augment_steps = mixture_distance(
        simplex, 2, 3, fixed=(simplex[0],))

    rank_deficient_points = [(F(1), F(0), F(0)), (F(0), F(1), F(0)),
                             (F(1, 2), F(1, 2), F(0)), (F(1, 3), F(2, 3), F(0))]
    rank_deficient_rows = [scheffe_row(dict(zip(("A", "B", "C"), point)),
                                       quadratic_terms)
                           for point in rank_deficient_points]

    lower = [F(1, 5), F(1, 10), F(0)]
    actual = (F(2, 5), F(3, 10), F(3, 10))
    pseudo = tuple((value - floor) / (1 - sum(lower, F(0)))
                   for value, floor in zip(actual, lower))
    restored = tuple(floor + value * (1 - sum(lower, F(0)))
                     for value, floor in zip(pseudo, lower))

    distance_process = []
    for point, process in ((simplex[0], F(0)), (simplex[1], F(4)),
                           (simplex[2], F(8))):
        process_unit = (process - F(0)) / (F(8) - F(0))
        distance_process.append({"components": point, "process": process,
                                 "normalized_process": process_unit,
                                 "coordinates": tuple(point) + (process_unit,)})

    search_cases = [
        {"candidate_count": 7, "run_count": 6, "allow_repeats": False,
         "subsets": comb(7, 6), "method": "exact_enumeration",
         "global_optimum_proven": True},
        {"candidate_count": 3, "run_count": 4, "allow_repeats": True,
         "subsets": comb(3 + 4 - 1, 4), "method": "exact_enumeration",
         "global_optimum_proven": True},
        {"candidate_count": 30, "run_count": 15, "allow_repeats": False,
         "subsets": comb(30, 15), "method": "greedy_exchange",
         "global_optimum_proven": False},
    ]
    result = {
        "method": {
            "d_optimal": "maximize det(X'X) using the specified Scheffe row; full rank required",
            "distance": "first nearest pure component; then maximize minimum squared Euclidean distance",
            "tie": "candidate input order; exact duplicate settings retain first occurrence",
            "process_coordinate": "(value-low)/(high-low), a unitless [0,1] coordinate",
            "pseudocomponent": "x'=(x-lower)/(1-sum(lower)); inverse before physical-distance calculation",
        },
        "distance_simplex": {
            "points": simplex, "component_count": 3, "requested": 5,
            "selected_order": distance_order, "step_squared_distance": distance_steps,
        },
        "quadratic_scheffe": {
            "terms": quadratic_terms, "points": simplex,
            "matrix": quadratic_rows, "requested": 6,
            "det_xtx": quadratic_det, "optimal_subsets": quadratic_optima,
            "logdet": log(float(quadratic_det)),
        },
        "constrained_selection": {
            "bounds": bounds, "linear_constraints": constraints,
            "points": constrained_points, "feasible_indices": feasible_indices,
            "rejected_indices": [i for i in range(len(constrained_points))
                                  if i not in feasible_indices],
            "linear_scheffe_terms": linear_terms,
            "selected_feasible_indices": [[feasible_indices[i] for i in subset]
                                           for subset in constrained_optima],
            "det_xtx": constrained_det,
        },
        "process_scheffe": {
            "terms": process_terms, "settings": process_settings,
            "matrix": process_rows, "rank": rank(process_rows),
            "det_xtx": determinant(information_matrix(process_rows)),
        },
        "repetition": {
            "terms": linear_terms, "candidate_points": vertices,
            "without_replacement": {
                "requested": 3, "det_xtx": no_repeat_det,
                "optimal_subsets": no_repeat_optima,
                "multiplicity": [1, 1, 1],
            },
            "with_replacement": {
                "requested": 4, "combination_count": comb(3 + 4 - 1, 4),
                "det_xtx": repeat_det, "optimal_subsets": repeat_optima,
                "chosen_multiplicity": [2, 1, 1],
                "global_optimum_proven": True,
            },
            "duplicate_candidates": {
                "input": duplicate_input, "unique_first_indices": unique_indices,
                "collapsed_indices": duplicate_indices,
                "det_xtx_after_collapse": duplicate_repeat_det,
                "optimal_subsets_after_collapse": duplicate_repeat_optima,
            },
            "distance_duplicate_candidates": {
                "input": simplex[:3] + [simplex[0]],
                "unique_first_indices": distance_unique_indices,
                "collapsed_indices": distance_duplicate_indices,
                "selected_order_on_unique": no_repeat_distance_order,
            },
        },
        "rank_deficiency": {
            "terms": quadratic_terms, "points": rank_deficient_points,
            "matrix": rank_deficient_rows, "rank": rank(rank_deficient_rows),
            "parameter_count": len(quadratic_terms),
            "det_xtx": determinant(information_matrix(rank_deficient_rows)),
        },
        "augmentation": {
            "terms": linear_terms,
            "parent_points": [vertices[0]],
            "candidate_points": vertices[1:],
            "d_optimal_without_replacement": {
                "requested": 2, "selected_indices": augment_optima,
                "det_xtx_after": augment_det,
                "initial_rank": rank(augmentation_parent),
                "augmented_rank": rank(augmentation_parent
                                       + [augmentation_candidates[i]
                                          for i in augment_optima[0]]),
            },
            "d_optimal_with_replacement": {
                "requested": 3, "combination_count": comb(2 + 3 - 1, 3),
                "selected_indices": repeat_augment_optima,
                "det_xtx_after": repeat_augment_det,
                "chosen_multiplicity": [2, 1],
                "initial_rank": rank(augmentation_parent),
                "augmented_rank": rank(augmentation_parent
                                       + [augmentation_candidates[i]
                                          for i in repeat_augment_optima[0]]),
            },
            "distance": {
                "all_points": simplex, "parent_indices": [0],
                "requested": 2, "selected_order": distance_augment_order,
                "step_squared_distance": distance_augment_steps,
                "minimum_squared_distance": min(
                    squared_distance(simplex[i], simplex[j])
                    for i, j in combinations([0] + distance_augment_order, 2)),
            },
        },
        "pseudocomponent_roundtrip": {
            "lower": lower, "actual": actual, "pseudo": pseudo,
            "restored": restored,
        },
        "distance_process_coordinates": distance_process,
        "search_budget": {"exact_subset_budget": 200000,
                          "exact_candidate_limit": 40,
                          "cases": search_cases},
        "boundary_cases": {
            "no_repeat_count_exceeds_unique": {"unique_points": 3,
                                                "requested": 4,
                                                "expected_error": "candidate shortage"},
            "distance_exhausted": {"unique_points": 3, "requested": 4,
                                   "expected_error": "candidate shortage"},
            "rank_deficient": {"rank": rank(rank_deficient_rows),
                               "parameters": len(quadratic_terms),
                               "expected_error": "no full-rank subset"},
            "infeasible_candidate_indices": [4, 5],
        },
    }
    return encode(result)


def main():
    reference_path = ROOT / "reference.json"
    reference_path.write_text(json.dumps(build(), ensure_ascii=False, indent=2) + "\n",
                              encoding="utf-8")
    payload = reference_path.read_bytes()
    manifest = {
        "source": "independent exact Fraction arithmetic and hand-built Scheffe matrices",
        "production_imports": [],
        "files": {"reference.json": {"bytes": len(payload),
                                     "sha256": sha256(payload).hexdigest()}},
    }
    (ROOT / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"built {reference_path.name}: {len(payload)} bytes, "
          f"sha256={sha256(payload).hexdigest()}")


if __name__ == "__main__":
    main()
