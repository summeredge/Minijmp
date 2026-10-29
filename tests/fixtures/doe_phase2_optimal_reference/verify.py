"""Independent verifier for the exact Mixture optimal-design reference."""
from fractions import Fraction
from itertools import combinations, combinations_with_replacement
from hashlib import sha256
from math import comb, log, isclose
from pathlib import Path
import json


ROOT = Path(__file__).resolve().parent


def q(value):
    return Fraction(value)


def matrix(rows):
    return [[q(value) for value in row] for row in rows]


def det(a):
    a = [row[:] for row in a]
    n = len(a)
    if any(len(row) != n for row in a):
        raise AssertionError("determinant requires a square matrix")
    sign, value = 1, Fraction(1)
    for col in range(n):
        pivot = next((r for r in range(col, n) if a[r][col] != 0), None)
        if pivot is None:
            return Fraction(0)
        if pivot != col:
            a[col], a[pivot] = a[pivot], a[col]
            sign *= -1
        pivot_value = a[col][col]
        value *= pivot_value
        for r in range(col + 1, n):
            factor = a[r][col] / pivot_value
            for c in range(col + 1, n):
                a[r][c] -= factor * a[col][c]
            a[r][col] = 0
    return value * sign


def matrix_rank(a):
    a = [row[:] for row in a]
    pivots, row = 0, 0
    for col in range(len(a[0]) if a else 0):
        pivot = next((r for r in range(row, len(a)) if a[r][col]), None)
        if pivot is None:
            continue
        a[row], a[pivot] = a[pivot], a[row]
        divisor = a[row][col]
        a[row] = [value / divisor for value in a[row]]
        for r in range(len(a)):
            if r == row or not a[r][col]:
                continue
            multiplier = a[r][col]
            a[r] = [x - multiplier * y for x, y in zip(a[r], a[row])]
        row += 1
        pivots += 1
        if row == len(a):
            break
    return pivots


def xtx(rows):
    rows = matrix(rows)
    p = len(rows[0])
    return [[sum((r[i] * r[j] for r in rows), Fraction(0))
             for j in range(p)] for i in range(p)]


def row_for(settings, terms):
    output = []
    for term in terms:
        value = Fraction(1)
        for name in term.split("*"):
            value *= q(settings[name])
        output.append(value)
    return output


def enumerate_d(rows, n, replace=False):
    if not replace and n > len(rows):
        raise ValueError("candidate shortage")
    pool = range(len(rows))
    selections = (combinations_with_replacement(pool, n) if replace
                  else combinations(pool, n))
    best, solutions = Fraction(0), []
    for indices in selections:
        value = det(xtx([rows[i] for i in indices]))
        if value > best:
            best, solutions = value, [indices]
        elif value == best and value > 0:
            solutions.append(indices)
    return best, solutions


def enumerate_augmentation(initial, candidates, n, replace=False):
    pool = range(len(candidates))
    choices = (combinations_with_replacement(pool, n) if replace
               else combinations(pool, n))
    best, solutions = Fraction(0), []
    for indices in choices:
        rows = list(initial) + [candidates[index] for index in indices]
        value = det(xtx(rows))
        if value > best:
            best, solutions = value, [indices]
        elif value == best and value > 0:
            solutions.append(indices)
    return best, solutions


def distance2(a, b):
    return sum(((q(x) - q(y)) ** 2 for x, y in zip(a, b)), Fraction(0))


def greedy_distance(points, count, component_count, fixed=()):
    selected, available = [], list(range(len(points)))
    steps = []
    if not fixed:
        pure_points = [tuple(Fraction(i == j) for i in range(component_count))
                       for j in range(component_count)]
        scores = [min(distance2(point[:component_count], pure)
                      for pure in pure_points) for point in points]
        first = min(available, key=lambda i: (scores[i], i))
        selected.append(first)
        available.remove(first)
        steps.append(scores[first])
    anchors = [tuple(q(x) for x in point) for point in fixed]
    anchors.extend(points[i] for i in selected)
    while len(selected) < count:
        available = [i for i in available
                     if all(tuple(points[i]) != anchor for anchor in anchors)]
        if not available:
            raise ValueError("candidate shortage")
        scores = {i: min(distance2(points[i], anchor) for anchor in anchors)
                  for i in available}
        item = max(available, key=lambda i: (scores[i], -i))
        selected.append(item)
        anchors.append(points[item])
        available.remove(item)
        steps.append(scores[item])
    return selected, steps


def is_feasible(point, bounds, constraints):
    point = tuple(map(q, point))
    return (sum(point, Fraction(0)) == 1
            and all(q(low) <= value <= q(high)
                    for value, (low, high) in zip(point, bounds))
            and all(sum((q(a) * x for a, x in zip(coeff, point)), Fraction(0))
                    <= q(bound) for coeff, bound in constraints))


def first_unique_indices(points):
    result, seen, repeats = [], set(), []
    for index, point in enumerate(points):
        key = tuple(map(q, point))
        if key in seen:
            repeats.append(index)
        else:
            result.append(index)
            seen.add(key)
    return result, repeats


def expect(actual, expected, label):
    if actual != expected:
        raise AssertionError(f"{label}: expected {expected!r}, got {actual!r}")


def verify():
    reference_path = ROOT / "reference.json"
    raw = reference_path.read_bytes()
    manifest = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))
    expect(manifest["production_imports"], [], "production imports")
    entry = manifest["files"]["reference.json"]
    expect(entry["bytes"], len(raw), "reference byte count")
    expect(entry["sha256"], sha256(raw).hexdigest(), "reference sha256")
    data = json.loads(raw)

    d = data["distance_simplex"]
    points = [tuple(map(q, point)) for point in d["points"]]
    sequence, steps = greedy_distance(points, d["requested"], d["component_count"])
    expect(sequence, d["selected_order"], "simplex distance order")
    expect(steps, list(map(q, d["step_squared_distance"])), "distance steps")
    # The first point is a pure-component candidate; B and C are an exact tie.
    expect(sequence[:3], [0, 1, 2], "pure start and stable tie")

    model = data["quadratic_scheffe"]
    terms = model["terms"]
    candidate_points = [tuple(map(q, point)) for point in model["points"]]
    rebuilt = [row_for(dict(zip(("A", "B", "C"), point)), terms)
               for point in candidate_points]
    expect(rebuilt, matrix(model["matrix"]), "quadratic Scheffe matrix")
    best, choices = enumerate_d(rebuilt, model["requested"])
    expect(best, q(model["det_xtx"]), "quadratic D-opt determinant")
    expect([list(item) for item in choices], model["optimal_subsets"],
           "quadratic exact optimum set")
    if not isclose(log(float(best)), model["logdet"], rel_tol=0, abs_tol=1e-12):
        raise AssertionError("quadratic logdet mismatch")

    constrained = data["constrained_selection"]
    feasible_indices = [i for i, point in enumerate(constrained["points"])
                        if is_feasible(point, constrained["bounds"],
                                       constrained["linear_constraints"])]
    expect(feasible_indices, constrained["feasible_indices"], "feasible candidate indices")
    expect([i for i in range(len(constrained["points"])) if i not in feasible_indices],
           constrained["rejected_indices"], "rejected candidate indices")
    rows = [row_for(dict(zip(("A", "B", "C"),
                             tuple(map(q, constrained["points"][i])))),
                    constrained["linear_scheffe_terms"])
            for i in feasible_indices]
    best, choices = enumerate_d(rows, 3)
    expect(best, q(constrained["det_xtx"]), "constrained D-opt determinant")
    selected_original = [[feasible_indices[i] for i in choice] for choice in choices]
    expect(selected_original, constrained["selected_feasible_indices"],
           "constrained selected indices")

    process = data["process_scheffe"]
    rows, settings = [], process["settings"]
    for setting in settings:
        raw_value = q(setting["process"])
        coded = 2 * (raw_value - 0) / (10 - 0) - 1
        expect(coded, q(setting["coded_process"]), "coded process value")
        row_settings = dict(zip(("A", "B", "C"), map(q, setting["components"])))
        row_settings["P"] = coded
        rows.append(row_for(row_settings, process["terms"]))
    expect(rows, matrix(process["matrix"]), "process interaction matrix")
    expect(matrix_rank(rows), process["rank"], "process matrix rank")
    expect(det(xtx(rows)), q(process["det_xtx"]), "process information determinant")
    expect(q(process["det_xtx"]), Fraction(64), "hand process determinant")

    repeat = data["repetition"]
    vertices = [tuple(map(q, point)) for point in repeat["candidate_points"]]
    linear_rows = [row_for(dict(zip(("A", "B", "C"), point)), repeat["terms"])
                   for point in vertices]
    no_repeat = repeat["without_replacement"]
    det_no, sets_no = enumerate_d(linear_rows, no_repeat["requested"])
    expect(det_no, q(no_repeat["det_xtx"]), "no replacement determinant")
    expect([list(item) for item in sets_no], no_repeat["optimal_subsets"],
           "no replacement optimum")
    expect(sorted(sum(1 for i in sets_no[0] if i == key) for key in range(3)),
           [1, 1, 1], "no replacement multiplicity")

    with_repeat = repeat["with_replacement"]
    expect(with_repeat["combination_count"],
           comb(len(vertices) + with_repeat["requested"] - 1,
                with_repeat["requested"]), "multiset search size")
    det_rep, sets_rep = enumerate_d(linear_rows, with_repeat["requested"], replace=True)
    expect(det_rep, q(with_repeat["det_xtx"]), "with replacement determinant")
    expect([list(item) for item in sets_rep], with_repeat["optimal_subsets"],
           "with replacement optimum set")
    chosen = sets_rep[0]
    expect([chosen.count(i) for i in range(3)],
           with_repeat["chosen_multiplicity"], "repeated run counts")
    expect(with_repeat["global_optimum_proven"], True, "exact search marker")

    duplicate = repeat["duplicate_candidates"]
    kept, removed = first_unique_indices(duplicate["input"])
    expect(kept, duplicate["unique_first_indices"], "D-opt unique candidate rows")
    expect(removed, duplicate["collapsed_indices"], "D-opt duplicate candidate rows")
    unique_rows = [linear_rows[index] for index in kept]
    det_rep, sets_rep = enumerate_d(unique_rows, 4, replace=True)
    expect(det_rep, q(duplicate["det_xtx_after_collapse"]),
           "deduplicated D-opt determinant")
    expect([list(item) for item in sets_rep],
           duplicate["optimal_subsets_after_collapse"],
           "deduplicated repeated optimum")

    distance_duplicates = repeat["distance_duplicate_candidates"]
    kept, removed = first_unique_indices(distance_duplicates["input"])
    expect(kept, distance_duplicates["unique_first_indices"],
           "distance unique candidate rows")
    expect(removed, distance_duplicates["collapsed_indices"],
           "distance duplicate candidate rows")
    unique_points = [tuple(map(q, distance_duplicates["input"][i])) for i in kept]
    sequence, _ = greedy_distance(unique_points, 3, 3)
    expect(sequence, distance_duplicates["selected_order_on_unique"],
           "distance no-repeat result")
    try:
        greedy_distance(unique_points, 4, 3)
    except ValueError as error:
        expect(str(error), "candidate shortage", "distance exhaustion")
    else:
        raise AssertionError("distance selection must reject exhausted candidates")

    deficient = data["rank_deficiency"]
    deficient_rows = [row_for(dict(zip(("A", "B", "C"), map(q, point))),
                              deficient["terms"])
                      for point in deficient["points"]]
    expect(deficient_rows, matrix(deficient["matrix"]), "rank-deficient Scheffe rows")
    expect(matrix_rank(deficient_rows), deficient["rank"], "rank-deficient model")
    expect(det(xtx(deficient_rows)), q(0), "rank-deficient information")
    expect(deficient["rank"] < deficient["parameter_count"],
           True, "rank-deficient rejection")

    augmentation = data["augmentation"]
    parent = [row_for(dict(zip(("A", "B", "C"), map(q, point))),
                      augmentation["terms"])
              for point in augmentation["parent_points"]]
    additions = [row_for(dict(zip(("A", "B", "C"), map(q, point))),
                         augmentation["terms"])
                 for point in augmentation["candidate_points"]]
    no_repeat_aug = augmentation["d_optimal_without_replacement"]
    best, choices = enumerate_augmentation(
        parent, additions, no_repeat_aug["requested"])
    expect(best, q(no_repeat_aug["det_xtx_after"]), "fixed-parent D-opt determinant")
    expect([list(choice) for choice in choices], no_repeat_aug["selected_indices"],
           "fixed-parent D-opt selection")
    expect(matrix_rank(parent), no_repeat_aug["initial_rank"], "parent rank")
    expect(matrix_rank(parent + [additions[i] for i in choices[0]]),
           no_repeat_aug["augmented_rank"], "augmented rank")

    repeat_aug = augmentation["d_optimal_with_replacement"]
    expect(repeat_aug["combination_count"],
           comb(len(additions) + repeat_aug["requested"] - 1,
                repeat_aug["requested"]), "augmentation multiset budget")
    best, choices = enumerate_augmentation(
        parent, additions, repeat_aug["requested"], replace=True)
    expect(best, q(repeat_aug["det_xtx_after"]), "repeated augmentation determinant")
    expect([list(choice) for choice in choices], repeat_aug["selected_indices"],
           "repeated augmentation optimum")
    expect([choices[0].count(index) for index in range(len(additions))],
           repeat_aug["chosen_multiplicity"], "augmentation multiplicity")

    distance_aug = augmentation["distance"]
    distance_points = [tuple(map(q, point)) for point in distance_aug["all_points"]]
    fixed_points = [distance_points[index] for index in distance_aug["parent_indices"]]
    selected, steps = greedy_distance(
        distance_points, distance_aug["requested"], 3, fixed=fixed_points)
    expect(selected, distance_aug["selected_order"], "distance augmentation order")
    expect(steps, list(map(q, distance_aug["step_squared_distance"])),
           "distance augmentation steps")
    expect(min(distance2(distance_points[i], distance_points[j])
               for i, j in combinations(distance_aug["parent_indices"] + selected, 2)),
           q(distance_aug["minimum_squared_distance"]), "distance augmentation spacing")
    if any(distance_points[index] in fixed_points for index in selected):
        raise AssertionError("distance augmentation repeated a parent point")

    pseudo = data["pseudocomponent_roundtrip"]
    lower, actual = list(map(q, pseudo["lower"])), list(map(q, pseudo["actual"]))
    base = sum(lower, Fraction(0))
    converted = [(x - lo) / (1 - base) for x, lo in zip(actual, lower)]
    expect(converted, list(map(q, pseudo["pseudo"])), "pseudo conversion")
    restored = [lo + value * (1 - base) for lo, value in zip(lower, converted)]
    expect(restored, list(map(q, pseudo["restored"])), "pseudo inverse")
    expect(restored, actual, "pseudo roundtrip")

    for item in data["distance_process_coordinates"]:
        low, high = Fraction(0), Fraction(8)
        normalized = (q(item["process"]) - low) / (high - low)
        expect(normalized, q(item["normalized_process"]),
               "process unit-interval scaling")
        expect(tuple(map(q, item["coordinates"])),
               tuple(map(q, item["components"])) + (normalized,),
               "composed distance coordinates")

    for case in data["search_budget"]["cases"]:
        count, n = case["run_count"], case["candidate_count"]
        possible = comb(n + count - 1, count) if case["allow_repeats"] else comb(n, count)
        expect(possible, case["subsets"], "search subset count")
        exact = n <= data["search_budget"]["exact_candidate_limit"] and possible <= data["search_budget"]["exact_subset_budget"]
        expect(case["method"], "exact_enumeration" if exact else "greedy_exchange",
               "search method")
        expect(case["global_optimum_proven"], exact, "global optimum marker")

    try:
        enumerate_d(linear_rows, 4, replace=False)
    except ValueError as error:
        expect(str(error), data["boundary_cases"]["no_repeat_count_exceeds_unique"]["expected_error"],
               "no replacement shortage")
    else:
        raise AssertionError("no-replacement request must reject candidate shortage")
    bounds, constraints = constrained["bounds"], constrained["linear_constraints"]
    for index in data["boundary_cases"]["infeasible_candidate_indices"]:
        if is_feasible(constrained["points"][index], bounds, constraints):
            raise AssertionError(f"infeasible candidate {index} accepted")

    return 13


if __name__ == "__main__":
    print(f"{verify()} independent Mixture optimal-reference checks passed")
