"""Rebuild and exactly audit the independent DSD reference matrices."""

from __future__ import annotations

import csv
import hashlib
import itertools
import json
from collections import Counter
from fractions import Fraction
from io import StringIO
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def _field_elements(order: int) -> list[tuple[int, int]]:
    if order == 9:
        return [(a, b) for a in range(3) for b in range(3)]
    return [(a, 0) for a in range(order)]


def _field_sub(left: tuple[int, int], right: tuple[int, int], order: int) -> tuple[int, int]:
    modulus = 3 if order == 9 else order
    return ((left[0] - right[0]) % modulus, (left[1] - right[1]) % modulus)


def _field_mul(left: tuple[int, int], right: tuple[int, int], order: int) -> tuple[int, int]:
    if order == 9:
        a, b = left
        c, d = right
        return ((a * c - b * d) % 3, (a * d + b * c) % 3)
    return (left[0] * right[0] % order, 0)


def _field_power(value: tuple[int, int], exponent: int, order: int) -> tuple[int, int]:
    result = (1, 0)
    while exponent:
        if exponent & 1:
            result = _field_mul(result, value, order)
        value = _field_mul(value, value, order)
        exponent >>= 1
    return result


def _quadratic_character(value: tuple[int, int], order: int) -> int:
    if value == (0, 0):
        return 0
    character = _field_power(value, (order - 1) // 2, order)
    modulus = 3 if order == 9 else order
    if character == (1, 0):
        return 1
    if character == (modulus - 1, 0):
        return -1
    raise AssertionError(f"unexpected quadratic character {character} in GF({order})")


def conference_matrix(order: int) -> list[list[int]]:
    """Build a Paley conference matrix of order q+1 for q=5, 7, or 9."""
    if order not in (5, 7, 9):
        raise ValueError(f"unsupported finite-field order: {order}")
    elements = _field_elements(order)
    labels: list[tuple[int, int] | None] = [None, *elements]
    matrix = [[0] * len(labels) for _ in labels]
    for i, left in enumerate(labels):
        for j, right in enumerate(labels):
            if i == j:
                continue
            if left is None:
                matrix[i][j] = 1
            elif right is None:
                matrix[i][j] = 1 if order % 4 == 1 else -1
            else:
                matrix[i][j] = _quadratic_character(_field_sub(left, right, order), order)

    gram = [[sum(row[i] * row[j] for row in matrix) for j in range(len(matrix))]
            for i in range(len(matrix))]
    assert gram == [[order if i == j else 0 for j in range(len(matrix))]
                    for i in range(len(matrix))]
    return matrix


def _dsd_columns(order: int, factor_count: int) -> list[list[int]]:
    conference = conference_matrix(order)
    assert factor_count <= order + 1
    columns = [row[:factor_count] for row in conference]
    return columns + [[-value for value in row] for row in columns] + [[0] * factor_count]


def _gram(columns: list[list[int]]) -> list[list[int]]:
    return [[sum(a * b for a, b in zip(left, right)) for right in columns]
            for left in columns]


def _determinant(matrix: list[list[int]]) -> int:
    work = [[Fraction(value) for value in row] for row in matrix]
    sign = 1
    determinant = Fraction(1)
    for column in range(len(work)):
        pivot = next((r for r in range(column, len(work)) if work[r][column]), None)
        if pivot is None:
            return 0
        if pivot != column:
            work[column], work[pivot] = work[pivot], work[column]
            sign = -sign
        value = work[column][column]
        determinant *= value
        for r in range(column + 1, len(work)):
            scale = work[r][column] / value
            for c in range(column + 1, len(work)):
                work[r][c] -= scale * work[column][c]
    result = sign * determinant
    assert result.denominator == 1
    return result.numerator


def _solve(matrix: list[list[int]], rhs: list[list[int]]) -> list[list[Fraction]]:
    size = len(matrix)
    work = [[Fraction(value) for value in row] + [Fraction(value) for value in extra]
            for row, extra in zip(matrix, rhs)]
    for column in range(size):
        pivot = next((r for r in range(column, size) if work[r][column]), None)
        assert pivot is not None, "first-order information matrix must be nonsingular"
        work[column], work[pivot] = work[pivot], work[column]
        scale = work[column][column]
        work[column] = [value / scale for value in work[column]]
        for r in range(size):
            if r != column and work[r][column]:
                scale = work[r][column]
                work[r] = [a - scale * b for a, b in zip(work[r], work[column])]
    return [row[size:] for row in work]


def _rank(columns: list[list[int]]) -> int:
    if not columns:
        return 0
    work = [[Fraction(value) for value in row] for row in zip(*columns)]
    rank = 0
    for column in range(len(columns)):
        pivot = next((r for r in range(rank, len(work)) if work[r][column]), None)
        if pivot is None:
            continue
        work[rank], work[pivot] = work[pivot], work[rank]
        scale = work[rank][column]
        work[rank] = [value / scale for value in work[rank]]
        for r in range(len(work)):
            if r != rank and work[r][column]:
                scale = work[r][column]
                work[r] = [a - scale * b for a, b in zip(work[r], work[rank])]
        rank += 1
        if rank == len(work):
            break
    return rank


def _dot(left: list[int], right: list[int]) -> int:
    return sum(a * b for a, b in zip(left, right))


def _proportional(left: list[int], right: list[int]) -> bool:
    pivot = next((i for i, value in enumerate(left) if value), None)
    if pivot is None:
        return not any(right)
    return all(left[pivot] * value == right[pivot] * left[i]
               for i, value in enumerate(right))


def _csv_bytes(headers: list[str], rows: list[list[int]]) -> bytes:
    buffer = StringIO(newline="")
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(headers)
    writer.writerows([[i, *row] for i, row in enumerate(rows, 1)])
    return buffer.getvalue().encode("utf-8")


def _columns(rows: list[list[int]]) -> list[list[int]]:
    return [list(column) for column in zip(*rows)]


def _mixed_reference() -> tuple[list[list[int]], dict[str, object]]:
    # The paper's base is a 5-factor, 13-run orthogonal DSD; use 5 columns of C_6.
    base = _dsd_columns(5, 5)[:-1]
    zero_pair = [i for i, row in enumerate(base) if row[-1] == 0]
    assert len(zero_pair) == 2 and zero_pair[1] - zero_pair[0] == 6
    candidates = []
    for z in (-1, 1):
        for b in (-1, 1):
            rows = [row[:] for row in base]
            rows[zero_pair[0]][-1] = z
            rows[zero_pair[1]][-1] = -z
            rows.extend([[0, 0, 0, 0, b], [0, 0, 0, 0, -b]])
            first_order = _columns([[1, *row] for row in rows])
            determinant = abs(_determinant(_gram(first_order)))
            candidates.append((determinant, z, b, rows))
    maximum = max(item[0] for item in candidates)
    determinant, z, b, rows = next(item for item in candidates if item[0] == maximum)
    return rows, {
        "selected_z": z,
        "selected_b": b,
        "maximum_first_order_information_determinant": determinant,
        "candidate_determinants": [
            {"z": candidate_z, "b": candidate_b, "determinant": candidate_det}
            for candidate_det, candidate_z, candidate_b, _ in candidates
        ],
        "tie_rule": "first maximizer in z,b enumeration order (-1,+1)",
    }


def build_reference_matrices() -> dict[str, dict[str, object]]:
    designs: dict[str, dict[str, object]] = {}
    for factor_count, order in ((6, 5), (7, 7), (8, 7), (10, 9)):
        run_count = 2 * (order + 1) + 1
        design_id = f"dsd-{factor_count:02d}-continuous"
        designs[design_id] = {
            "matrix_file": f"dsd_{factor_count:02d}_cont_{run_count:02d}.csv",
            "headers": ["standard_order"] + [f"X{i + 1}" for i in range(factor_count)],
            "rows": _dsd_columns(order, factor_count),
            "factor_count": factor_count,
            "run_count": run_count,
            "conference_order": order + 1,
        }

    mixed_rows, mixed_choice = _mixed_reference()
    designs["dsd-04-cont-01-cat"] = {
        "matrix_file": "dsd_04_cont_01_cat_14.csv",
        "headers": ["standard_order", "X1", "X2", "X3", "X4", "C1"],
        "rows": mixed_rows,
        "factor_count": 5,
        "continuous_factor_count": 4,
        "categorical_factor_count": 1,
        "run_count": len(mixed_rows),
        "conference_order": 6,
        "augmentation_choice": mixed_choice,
    }
    return designs


def audit_continuous(rows: list[list[int]], factor_count: int, conference_order: int) -> dict[str, object]:
    run_count = len(rows)
    assert run_count == 2 * conference_order + 1
    assert all(value in (-1, 0, 1) for row in rows for value in row)
    for i in range(conference_order):
        assert rows[i + conference_order] == [-value for value in rows[i]]
    assert rows[-1] == [0] * factor_count

    columns = _columns(rows)
    counts = [dict(sorted(Counter(column).items())) for column in columns]
    q = conference_order - 1
    assert all(count == {-1: q, 0: 3, 1: q} for count in counts)

    intercept = [1] * run_count
    main = columns
    gram = _gram([intercept] + main)
    assert all(gram[i][j] == 0 for i in range(factor_count + 1)
               for j in range(factor_count + 1) if i != j)
    assert [gram[i][i] for i in range(factor_count + 1)] == [run_count] + [2 * q] * factor_count

    squares = [[value * value for value in column] for column in main]
    interactions = [[main[i][r] * main[j][r] for r in range(run_count)]
                    for i, j in itertools.combinations(range(factor_count), 2)]
    nonlinear = squares + interactions
    assert all(_dot(effect, term) == 0 for effect in main for term in nonlinear)
    assert _rank([intercept] + main) == factor_count + 1
    assert _rank([intercept] + main + squares) == 1 + 2 * factor_count

    full_second_order = [intercept] + main + nonlinear
    full_rank = _rank(full_second_order)
    assert full_rank <= run_count
    projection_count = 0
    for factors in itertools.combinations(range(factor_count), 3):
        projection = [intercept] + [main[i] for i in factors]
        projection.extend([squares[i] for i in factors])
        projection.extend([[main[i][r] * main[j][r] for r in range(run_count)]
                           for i, j in itertools.combinations(factors, 2)])
        assert _rank(projection) == 10
        projection_count += 1

    interaction_pairs = list(itertools.combinations(interactions, 2))
    assert not any(_proportional(left, right) for left, right in interaction_pairs)
    nonorthogonal_pairs = sum(_dot(left, right) != 0 for left, right in interaction_pairs)
    return {
        "run_count": run_count,
        "factor_count": factor_count,
        "level_counts_per_factor": counts[0],
        "main_effect_rank_with_intercept": factor_count + 1,
        "main_gram_diagonal": [run_count] + [2 * q] * factor_count,
        "main_effects_orthogonal_to_all_second_order_columns": True,
        "main_plus_quadratic_rank": 1 + 2 * factor_count,
        "full_second_order_parameter_count": len(full_second_order),
        "full_second_order_rank": full_rank,
        "full_second_order_residual_df": run_count - full_rank,
        "three_factor_projection_count": projection_count,
        "every_three_factor_full_second_order_rank": 10,
        "interaction_pair_count": len(interaction_pairs),
        "nonorthogonal_interaction_pairs": nonorthogonal_pairs,
        "perfectly_aliased_interaction_pairs": 0,
    }


def audit_mixed(rows: list[list[int]], choice: dict[str, object]) -> dict[str, object]:
    assert len(rows) == 14 and all(len(row) == 5 for row in rows)
    assert all(rows[i + 6] == [-value for value in rows[i]] for i in range(6))
    assert rows[12] == [-value for value in rows[13]]
    continuous = _columns([row[:4] for row in rows])
    categorical = [row[4] for row in rows]
    continuous_counts = [dict(sorted(Counter(column).items())) for column in continuous]
    assert all(count == {-1: 5, 0: 4, 1: 5} for count in continuous_counts)
    assert dict(sorted(Counter(categorical).items())) == {-1: 7, 1: 7}

    intercept = [1] * len(rows)
    main = continuous + [categorical]
    first_order = [intercept] + main
    first_order_gram = _gram(first_order)
    first_order_determinant = abs(_determinant(first_order_gram))
    assert _rank(first_order) == 6
    assert first_order_determinant == choice["maximum_first_order_information_determinant"]
    assert first_order_determinant == max(item["determinant"]
                                          for item in choice["candidate_determinants"])

    squares = [[value * value for value in column] for column in continuous]
    cont_interactions = [[continuous[i][r] * continuous[j][r] for r in range(len(rows))]
                         for i, j in itertools.combinations(range(4), 2)]
    cat_interactions = [[continuous[i][r] * categorical[r] for r in range(len(rows))]
                        for i in range(4)]
    second_order = squares + cont_interactions + cat_interactions
    assert all(_dot(effect, term) == 0 for effect in main for term in second_order)

    rhs = [[_dot(effect, term) for term in second_order] for effect in first_order]
    alias = _solve(first_order_gram, rhs)
    assert all(value == 0 for row in alias[1:] for value in row)
    intercept_alias = alias[0]
    interaction_alias = intercept_alias[len(squares):]
    assert max(map(abs, interaction_alias)) == Fraction(1, 7)
    assert all(value == Fraction(5, 7) for value in intercept_alias[:len(squares)])
    nonzero_intercept_alias_terms = [
        f"X{i + 1}:C1={value}" for i, value in enumerate(intercept_alias[-4:]) if value
    ]

    full_model = first_order + second_order
    full_rank = _rank(full_model)
    return {
        "run_count": len(rows),
        "factor_count": 5,
        "continuous_factor_count": 4,
        "categorical_factor_count": 1,
        "continuous_level_counts_per_factor": continuous_counts[0],
        "categorical_level_counts": {-1: 7, 1: 7},
        "base_dsd_runs": 13,
        "n1_center_omitted_runs": 12,
        "foldover_pair_count": 7,
        "first_order_parameter_count": 6,
        "first_order_rank": 6,
        "first_order_information_determinant": first_order_determinant,
        "candidate_determinants": choice["candidate_determinants"],
        "factor_main_effects_orthogonal_to_all_second_order_terms": True,
        "second_order_term_count": len(second_order),
        "full_model_parameter_count": len(full_model),
        "full_model_rank": full_rank,
        "full_model_residual_df": len(rows) - full_rank,
        "factor_main_effect_aliases": "0",
        "intercept_to_interaction_alias_max_abs": "1/7",
        "intercept_to_raw_square_aliases": ["5/7"] * len(squares),
        "intercept_alias_nonzero_terms": nonzero_intercept_alias_terms,
        "published_run_count_and_alias_bound_match": True,
    }


def _read_csv(path: Path, headers: list[str]) -> list[list[int]]:
    records = list(csv.reader(StringIO(path.read_text(encoding="utf-8"), newline="")))
    assert records and records[0] == headers, f"{path.name}: unexpected CSV header"
    assert all(len(record) == len(headers) for record in records[1:]), f"{path.name}: malformed row"
    orders = [int(record[0]) for record in records[1:]]
    assert orders == list(range(1, len(records))), f"{path.name}: invalid construction order"
    rows = [[int(value) for value in record[1:]] for record in records[1:]]
    assert all(str(order) == record[0] and
               all(str(value) == token for value, token in zip(row, record[1:]))
               for order, row, record in zip(orders, rows, records[1:])), \
        f"{path.name}: noncanonical integer encoding"
    return rows


def verify() -> dict[str, dict[str, object]]:
    manifest = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))
    entries = {entry["id"]: entry for entry in manifest["fixtures"]}
    required = {"id", "path", "family", "factors", "runs", "factor_types", "encoding",
                "replicates", "blocks", "source", "source_url", "source_version",
                "equivalence", "sha256", "independent_validation"}
    source_ids = {source["id"] for source in manifest["sources"]}
    next_factor = 2
    for item in manifest["official_scope"]["all_continuous_base_run_count_ranges"]:
        assert item["factor_min"] == next_factor and item["factor_min"] <= item["factor_max"]
        next_factor = item["factor_max"] + 1
    assert next_factor == 49, "official run-count ranges must cover factors 2 through 48"
    # This manifest contains continuous references; the mixed reference has its own parent-manifest audit.
    expected = {key: value for key, value in build_reference_matrices().items()
                if not value.get('categorical_factor_count')}
    assert set(entries) == set(expected), "manifest design list does not match reference files"
    results = {}
    for design_id, spec in expected.items():
        entry = entries[design_id]
        assert required <= entry.keys(), f"{design_id}: missing shared-manifest fields"
        assert entry["family"] == "dsd"
        assert entry["path"] == f"dsd/{spec['matrix_file']}"
        assert entry["factors"] == spec["factor_count"]
        if spec.get("categorical_factor_count"):
            assert entry["factor_types"] == ["continuous"] * 4 + ["categorical"]
            assert entry["encoding"] == {"continuous": [-1, 0, 1], "categorical": [-1, 1]}
        else:
            assert entry["factor_types"] == ["continuous"]
            assert entry["encoding"] == [-1, 0, 1]
        assert set(entry["source_ids"]) <= source_ids
        assert entry["matrix_file"] == spec["matrix_file"]
        path = ROOT / spec["matrix_file"]
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        assert digest == entry["sha256"], f"{design_id}: SHA-256 mismatch"
        actual = _read_csv(path, spec["headers"])
        assert actual == spec["rows"], f"{design_id}: matrix differs from independent construction"
        assert path.read_bytes() == _csv_bytes(spec["headers"], actual), f"{design_id}: noncanonical CSV bytes"
        result = (audit_mixed(actual, spec["augmentation_choice"])
                  if spec.get("categorical_factor_count")
                  else audit_continuous(actual, spec["factor_count"], spec["conference_order"]))
        assert entry["runs"] == result["run_count"]
        results[design_id] = {"sha256": digest, **result}
    return results


if __name__ == "__main__":
    for design_id, result in verify().items():
        print(f"{design_id}: {json.dumps(result, sort_keys=True)}")
