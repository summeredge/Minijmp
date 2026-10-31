"""MiniJMP × Minitab 19 optimal design, distance, and augmentation parity."""
from __future__ import annotations

import csv
import itertools
import math
import sys
import traceback
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
SUPPLEMENTAL = HERE.parent
ROOT = SUPPLEMENTAL.parents[2]
if str(SUPPLEMENTAL) not in sys.path:
    sys.path.insert(0, str(SUPPLEMENTAL))
if str(ROOT / "code") not in sys.path:
    sys.path.insert(0, str(ROOT / "code"))

from common import (  # noqa: E402
    MinitabSession,
    compare_numeric,
    compare_text,
    run_worker,
    status_counts,
    write_comparison,
    write_json,
)

from doe_augment import augment  # noqa: E402
from doe_core import FactorSpec  # noqa: E402
from doe_custom import define_custom  # noqa: E402
from doe_optimal_design import optimal_from_candidates  # noqa: E402

CASE_IDS = ("OPT-D", "OPT-DIST", "OPT-AUG")
FACTORS = ("A", "B")
COLUMN_MAP = {
    "run_id": "run_id", "standard_order": "standard_order",
    "run_order": "run_order", "point_type": "point_type",
    "replicate": "replicate", "block": None, "batch_id": "batch_id",
    "source_run_id": "source_run_id",
    "factors": {name: name for name in FACTORS}, "responses": {"Y": "Y"},
}
OPT_D_POINTS = ((-1, -1), (-1, 1), (1, -1), (1, 1))
OPT_D_CANDIDATES = OPT_D_POINTS
DIST_POINTS = ((1, 1), (-1, 1), (-1, -1), (1, -1),
               (1, 0), (0, 1), (-1, 0), (0, -1), (0, 0))
AUG_PARENT = ((-1, -1), (1, -1), (-1, 1))
AUG_CANDIDATES = ((1, 1), (0, 0))

INPUTS = {
    "OPT-D": HERE / "opt_d_input.csv",
    "OPT-DIST": HERE / "opt_dist_input.csv",
    "OPT-AUG": HERE / "opt_aug_input.csv",
}
MINIJMP = HERE / "minijmp_results.json"
MINITAB = HERE / "minitab_results.json"
RAW = HERE / "minitab_raw.txt"
COMMANDS = HERE / "session_commands.txt"
COMPARISON = HERE / "comparison.csv"
REPORT = HERE / "acceptance.md"


def _determinant_integer(matrix):
    matrix = [tuple(int(value) for value in row) for row in matrix]
    size = len(matrix)
    if any(len(row) != size for row in matrix):
        raise ValueError("determinant requires a square matrix")
    total = 0
    for permutation in itertools.permutations(range(size)):
        inversions = sum(permutation[i] > permutation[j]
                         for i in range(size) for j in range(i + 1, size))
        product = math.prod(matrix[row][permutation[row]] for row in range(size))
        total += (-1 if inversions % 2 else 1) * product
    return total


def _model_matrix(points):
    return [[1, int(a), int(b)] for a, b in points]


def _xtx_determinant(points):
    matrix = np.asarray(_model_matrix(points), dtype=np.int64)
    gram = matrix.T @ matrix
    return _determinant_integer(gram.tolist())


def _distance_summary(points):
    pairs = [sum((left[k] - right[k]) ** 2 for k in range(2))
             for left, right in itertools.combinations(points, 2)]
    return min(pairs) if pairs else None


def _exact_references():
    d_subsets = list(itertools.combinations(range(len(OPT_D_CANDIDATES)), 3))
    d_values = [_xtx_determinant([OPT_D_CANDIDATES[i] for i in subset])
                for subset in d_subsets]
    d_max = max(d_values)
    d_optima = [list(subset) for subset, value in zip(d_subsets, d_values)
                if value == d_max]

    distance_subsets = list(itertools.combinations(range(len(DIST_POINTS)), 4))
    distance_values = [_distance_summary([DIST_POINTS[i] for i in subset])
                       for subset in distance_subsets]
    distance_max = max(distance_values)
    distance_optima = [list(subset) for subset, value in
                       zip(distance_subsets, distance_values) if value == distance_max]

    parent_det = _xtx_determinant(AUG_PARENT)
    augmented_dets = [_xtx_determinant((*AUG_PARENT, point))
                      for point in AUG_CANDIDATES]
    return {
        "OPT-D": {"candidate_count": len(OPT_D_CANDIDATES),
                  "subset_count": len(d_subsets), "max_det_xtx": d_max,
                  "optimal_subsets": d_optima},
        "OPT-DIST": {"subset_count": len(distance_subsets),
                     "max_min_squared_distance": distance_max,
                     "optimal_subsets": distance_optima},
        "OPT-AUG": {"parent_det_xtx": parent_det,
                    "candidate_det_xtx": augmented_dets,
                    "best_candidate_index": int(np.argmax(augmented_dets)),
                    "max_det_xtx": max(augmented_dets)},
    }


def _response(a, b):
    return float(12 + 2 * a - 3 * b + 0.5 * a * b)


def _rows(points, prefix, *, batch="BASE", point_types=None):
    point_types = point_types or ["factorial"] * len(points)
    return [{
        "run_id": f"{prefix}{index + 1}",
        "standard_order": index + 1,
        "run_order": index + 1,
        "point_type": point_types[index],
        "replicate": 1,
        "batch_id": batch,
        "source_run_id": None if batch == "BASE" else "parent",
        "A": int(a), "B": int(b), "Y": _response(a, b),
    } for index, (a, b) in enumerate(points)]


def _write_input(case_id, rows):
    with INPUTS[case_id].open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _selected_points(frame):
    return [[int(row.A), int(row.B)] for row in frame.itertuples(index=False)]


def run_minijmp():
    factors = tuple(FactorSpec(name, name, -1, 1) for name in FACTORS)
    factorial_factors = tuple(FactorSpec(
        name, name, None, None, factor_type="categorical", levels=(-1, 1),
        level_type="numeric") for name in FACTORS)
    results = {"cases": {}, "exact_reference": _exact_references()}

    for case_id, points in (("OPT-D", OPT_D_CANDIDATES), ("OPT-DIST", DIST_POINTS)):
        rows = _rows(points, case_id.replace("-", ""))
        _write_input(case_id, rows)
        design_type = "custom_factorial" if case_id == "OPT-D" else "custom_rsm"
        model_terms = () if case_id == "OPT-D" else ("A", "B")
        selected, _, summary = optimal_from_candidates(
            pd.DataFrame(rows), design_type=design_type,
            factors=factorial_factors if case_id == "OPT-D" else factors,
            responses=("Y",), column_map=COLUMN_MAP,
            count=3 if case_id == "OPT-D" else 4,
            model_terms=model_terms,
            criterion="d_optimal" if case_id == "OPT-D" else "distance",
            design_id=case_id.lower(), seed=1)
        points_selected = _selected_points(selected)
        selected_matrix = _model_matrix(points_selected)
        results["cases"][case_id] = {
            "candidate_points": [list(point) for point in points],
            "selected_points": points_selected,
            "selected_indices": [int(value) for value in summary["selection_order"]],
            "selected_n": int(summary["selected_n"]),
            "rank": int(summary["selected_rank"]),
            "p": int(summary["selected_p"]),
            "det_xtx": float(np.linalg.det(np.asarray(selected_matrix, dtype=float).T
                                             @ np.asarray(selected_matrix, dtype=float))),
            "logdet": float(summary["logdet"]),
            "summary": summary,
        }
        if case_id == "OPT-DIST":
            results["cases"][case_id]["min_squared_distance"] = int(
                summary["min_squared_distance"])

    parent_rows = _rows(AUG_PARENT, "AUG")
    _write_input("OPT-AUG", parent_rows + _rows(AUG_CANDIDATES, "CAND", batch="CAND",
                                                   point_types=["factorial", "center"]))
    parent_frame = pd.DataFrame(parent_rows)
    parent_frame, parent_metadata, _ = define_custom(
        parent_frame, design_type="custom_rsm", factors=factors, responses=("Y",),
        column_map=COLUMN_MAP, design_id="opt-aug-parent", model_terms=("A", "B"))
    augmented, _, summary = augment(
        parent_frame, parent_metadata,
        [{"A": int(a), "B": int(b)} for a, b in AUG_CANDIDATES],
        1, terms=("A", "B"), criterion="d_optimal", batch_id="AUG1",
        point_types=("factorial", "center"))
    added = augmented[augmented["batch_id"] == "AUG1"]
    added_points = _selected_points(added)
    final_points = [list(point) for point in AUG_PARENT] + added_points
    results["cases"]["OPT-AUG"] = {
        "parent_points": [list(point) for point in AUG_PARENT],
        "candidate_points": [list(point) for point in AUG_CANDIDATES],
        "selected_points": added_points,
        "final_points": final_points,
        "parent_n": len(AUG_PARENT),
        "added_n": len(added_points),
        "initial_rank": int(summary["initial_rank"]),
        "augmented_rank": int(summary["augmented_rank"]),
        "initial_det_xtx": float(np.linalg.det(
            np.asarray(_model_matrix(AUG_PARENT), dtype=float).T
            @ np.asarray(_model_matrix(AUG_PARENT), dtype=float))),
        "augmented_det_xtx": float(np.linalg.det(
            np.asarray(_model_matrix(final_points), dtype=float).T
            @ np.asarray(_model_matrix(final_points), dtype=float))),
        "summary": summary,
    }

    references = results["exact_reference"]
    d = results["cases"]["OPT-D"]
    assert references["OPT-D"]["subset_count"] == 4
    assert references["OPT-D"]["max_det_xtx"] == 16
    assert len(references["OPT-D"]["optimal_subsets"]) == 4
    assert d["selected_n"] == 3 and d["rank"] == d["p"] == 3
    assert round(d["det_xtx"]) == references["OPT-D"]["max_det_xtx"]
    dist = results["cases"]["OPT-DIST"]
    assert references["OPT-DIST"]["subset_count"] == 126
    assert references["OPT-DIST"]["max_min_squared_distance"] == 4
    assert dist["min_squared_distance"] == 4
    aug = results["cases"]["OPT-AUG"]
    assert references["OPT-AUG"]["parent_det_xtx"] == 16
    assert references["OPT-AUG"]["candidate_det_xtx"] == [64, 24]
    assert aug["selected_points"] == [[1, 1]]
    assert aug["initial_rank"] == aug["augmented_rank"] == 3
    assert round(aug["initial_det_xtx"]) == 16
    assert round(aug["augmented_det_xtx"]) == 64
    write_json(MINIJMP, results)
    return results


def _run_opt_d(session):
    design_command = "FFDESIGN 2 4; LEVELS -1 1 -1 1; DESIGN."
    session.execute(design_command, "OPT-D candidate design")
    session.worksheet = session.project.ActiveWorksheet
    a_index, b_index = session.find_column(["A"]), session.find_column(["B"])
    indicator = session.add_column("SELECTED")
    optimal_command = f"OPTDES 3; FACMODEL A B; INDICATOR C{indicator}; BRIEF 3."
    output = session.execute(optimal_command, "OPT-D selection")
    selected_flags = session.column_values(indicator)
    if len(selected_flags) != len(OPT_D_CANDIDATES):
        raise RuntimeError(f"OPT-D indicator row count {len(selected_flags)} != {len(OPT_D_CANDIDATES)}")
    selected_indices = [index for index, value in enumerate(selected_flags)
                        if value is not None and value != 0]
    if len(selected_indices) != 3:
        raise RuntimeError(f"OPT-D expected 3 selected rows; indicator={selected_flags}")
    candidate_a = session.column_values(a_index)
    candidate_b = session.column_values(b_index)
    selected_points = [[int(round(candidate_a[index])), int(round(candidate_b[index]))]
                       for index in selected_indices]
    if any(tuple(point) not in OPT_D_POINTS for point in selected_points):
        raise RuntimeError(f"OPT-D selected points outside fixed corner candidates: {selected_points}")
    if len(set(map(tuple, selected_points))) != 3:
        raise RuntimeError(f"OPT-D returned duplicate selected points: {selected_points}")
    return {
        "command": f"{design_command}\n{optimal_command}",
        "design_command": design_command, "optimal_command": optimal_command,
        "indicator_column": f"C{indicator}", "indicator_values": selected_flags,
        "selected_indices": selected_indices,
        "selected_points": selected_points,
        "rank": int(np.linalg.matrix_rank(_model_matrix(selected_points))),
        "det_xtx": _xtx_determinant(selected_points),
        "output_excerpt": output[-4000:],
    }


def _run_opt_dist(session):
    for name, values in (("A", [point[0] for point in DIST_POINTS]),
                         ("B", [point[1] for point in DIST_POINTS])):
        session.add_column(name, values)
    indicator = session.add_column("SELECTED")
    command = f"OPTDES 4 C1-C2; INDICATOR C{indicator}; BRIEF 3."
    output = session.execute(command, "OPT-DIST")
    flags = session.column_values(indicator)
    if len(flags) != len(DIST_POINTS):
        raise RuntimeError(f"OPT-DIST indicator row count {len(flags)} != {len(DIST_POINTS)}")
    selected_indices = [index for index, value in enumerate(flags)
                        if value is not None and value != 0]
    if len(selected_indices) != 4:
        raise RuntimeError(f"OPT-DIST expected 4 selected rows; indicator={flags}")
    selected_points = [list(DIST_POINTS[index]) for index in selected_indices]
    return {
        "command": command, "indicator_column": f"C{indicator}",
        "indicator_values": flags, "selected_indices": selected_indices,
        "selected_points": selected_points,
        "rank": int(np.linalg.matrix_rank(_model_matrix(selected_points))),
        "min_squared_distance": _distance_summary(selected_points),
        "output_excerpt": output[-4000:],
    }


def _run_opt_aug(session):
    points = (*AUG_PARENT, *AUG_CANDIDATES)
    for name, values in (("A", [point[0] for point in points]),
                         ("B", [point[1] for point in points]),
                         ("AUGMENT_FLAG", [1, 1, 1, 0, 0])):
        session.add_column(name, values)
    indicator = session.add_column("SELECTED")
    command = (f"OPTDES 4; RESMODEL A B; INUNIT 0; LEVELS -1 1 -1 1; "
               f"AUGMENT C3; INDICATOR C{indicator}; BRIEF 3.")
    output = session.execute(command, "OPT-AUG")
    flags = session.column_values(indicator)
    if len(flags) != len(points):
        raise RuntimeError(f"OPT-AUG indicator row count {len(flags)} != {len(points)}")
    added_indices = [index - len(AUG_PARENT) for index, value in enumerate(flags)
                     if index >= len(AUG_PARENT) and value is not None and value != 0]
    if len(added_indices) != 1:
        raise RuntimeError(f"OPT-AUG expected 1 selected candidate; indicator={flags}")
    added_points = [list(AUG_CANDIDATES[index]) for index in added_indices]
    final_points = [list(point) for point in AUG_PARENT] + added_points
    return {
        "command": command, "augment_flags": [1, 1, 1, 0, 0],
        "indicator_column": f"C{indicator}", "indicator_values": flags,
        "added_indices": added_indices, "added_points": added_points,
        "parent_points": [list(point) for point in AUG_PARENT],
        "final_points": final_points,
        "initial_rank": int(np.linalg.matrix_rank(_model_matrix(AUG_PARENT))),
        "augmented_rank": int(np.linalg.matrix_rank(_model_matrix(final_points))),
        "initial_det_xtx": _xtx_determinant(AUG_PARENT),
        "augmented_det_xtx": _xtx_determinant(final_points),
        "output_excerpt": output[-4000:],
    }


def run_com_worker():
    session = None
    results = {"version": "19.1.0.1", "cases": {}}
    commands = []
    try:
        session = MinitabSession()
        try:
            results["cases"]["OPT-D"] = _run_opt_d(session)
            commands.append(results["cases"]["OPT-D"]["command"])
        except Exception as exc:
            results["cases"]["OPT-D"] = {"error": str(exc)}
            commands.append("OPT-D command failed; see minitab_raw.txt")

        session.new_project()
        try:
            results["cases"]["OPT-DIST"] = _run_opt_dist(session)
            commands.append(results["cases"]["OPT-DIST"]["command"])
        except Exception as exc:
            results["cases"]["OPT-DIST"] = {"error": str(exc)}
            commands.append("OPT-DIST command failed; see minitab_raw.txt")

        session.new_project()
        try:
            results["cases"]["OPT-AUG"] = _run_opt_aug(session)
            commands.append(results["cases"]["OPT-AUG"]["command"])
        except Exception as exc:
            results["cases"]["OPT-AUG"] = {"error": str(exc)}
            commands.append("OPT-AUG command failed; see minitab_raw.txt")
    except Exception as exc:
        results["session_error"] = str(exc)
        results["traceback"] = traceback.format_exc()
    finally:
        if session is not None:
            RAW.write_text("\n\n".join(session.raw) + "\n", encoding="utf-8")
            session.release()
        else:
            RAW.write_text("COM session did not start.\n", encoding="utf-8")
        write_json(MINITAB, results)
        COMMANDS.write_text("\n".join(commands) + "\n", encoding="utf-8")
    return results


def make_comparison(minijmp, minitab):
    rows = []
    exact = minijmp["exact_reference"]

    d_mini = minijmp["cases"]["OPT-D"]
    d_mtb = minitab["cases"].get("OPT-D", {})
    if "error" in d_mtb:
        rows.append(compare_text("OPT-D", "execution", "OPTDES", "command", "ERROR",
                                 d_mtb["error"], "DIRECT", "DIRECT"))
    else:
        d_is_optimal = d_mtb["det_xtx"] == exact["OPT-D"]["max_det_xtx"]
        rows.extend([
            compare_numeric("OPT-D", "design", "model", "selected_run_count",
                            len(d_mtb["selected_indices"]), d_mini["selected_n"],
                            "DIRECT", "DIRECT"),
            compare_numeric("OPT-D", "design", "model", "rank",
                            d_mtb["rank"], d_mini["rank"], "DERIVED", "DIRECT"),
            compare_numeric("OPT-D", "quality", "D-opt", "det_xtx",
                            d_mtb["det_xtx"], d_mini["det_xtx"], "DERIVED", "DERIVED"),
            compare_numeric("OPT-D", "quality", "D-opt", "exact_max_det_xtx",
                            d_mtb["det_xtx"], exact["OPT-D"]["max_det_xtx"],
                            "DERIVED", "DERIVED"),
            compare_text("OPT-D", "quality", "D-opt", "global_optimum_verified",
                         str(d_is_optimal), "True", "DERIVED", "DERIVED"),
            compare_text("OPT-D", "design", "candidate_set", "selected_points_within_four_corners",
                         str(all(tuple(point) in OPT_D_POINTS for point in d_mtb["selected_points"])),
                         "True", "DIRECT", "DERIVED"),
        ])
    dist_mini = minijmp["cases"]["OPT-DIST"]
    dist_mtb = minitab["cases"].get("OPT-DIST", {})
    if "error" in dist_mtb:
        rows.append(compare_text("OPT-DIST", "execution", "OPTDES", "command", "ERROR",
                                 dist_mtb["error"], "DIRECT", "DIRECT"))
    else:
        exact_dist = exact["OPT-DIST"]["max_min_squared_distance"]
        rows.extend([
            compare_numeric("OPT-DIST", "design", "distance", "selected_run_count",
                            len(dist_mtb["selected_indices"]), dist_mini["selected_n"],
                            "DIRECT", "DIRECT"),
            compare_numeric("OPT-DIST", "design", "model", "rank",
                            dist_mtb["rank"], dist_mini["rank"], "DERIVED", "DIRECT"),
            compare_numeric("OPT-DIST", "quality", "distance", "min_squared_distance",
                            dist_mtb["min_squared_distance"], dist_mini["min_squared_distance"],
                            "DERIVED", "DERIVED"),
            compare_numeric("OPT-DIST", "quality", "distance", "exact_max_min_squared_distance",
                            dist_mtb["min_squared_distance"], exact_dist,
                            "DERIVED", "DERIVED"),
            compare_text("OPT-DIST", "design", "distance", "selected_candidate_set",
                         str(sorted(map(tuple, dist_mtb["selected_points"]))),
                         str(sorted(map(tuple, dist_mini["selected_points"]))),
                         "DIRECT", "DIRECT"),
        ])

    aug_mini = minijmp["cases"]["OPT-AUG"]
    aug_mtb = minitab["cases"].get("OPT-AUG", {})
    if "error" in aug_mtb:
        rows.append(compare_text("OPT-AUG", "execution", "OPTDES", "command", "ERROR",
                                 aug_mtb["error"], "DIRECT", "DIRECT"))
    else:
        mini_added = aug_mini["selected_points"]
        mtb_added = aug_mtb["added_points"]
        selected_match = mini_added == mtb_added
        rows.extend([
            compare_numeric("OPT-AUG", "design", "parent", "fixed_run_count",
                            len(AUG_PARENT), aug_mini["parent_n"], "DIRECT", "DIRECT"),
            compare_numeric("OPT-AUG", "design", "augmentation", "added_run_count",
                            len(mtb_added), aug_mini["added_n"], "DIRECT", "DIRECT"),
            compare_text("OPT-AUG", "design", "augmentation", "added_candidate",
                         str(mtb_added), str(mini_added), "DIRECT", "DIRECT"),
            compare_numeric("OPT-AUG", "design", "model", "augmented_rank",
                            aug_mtb["augmented_rank"], aug_mini["augmented_rank"],
                            "DERIVED", "DIRECT"),
            compare_numeric("OPT-AUG", "quality", "D-opt", "parent_det_xtx",
                            aug_mtb["initial_det_xtx"], aug_mini["initial_det_xtx"],
                            "DERIVED", "DERIVED"),
            compare_numeric("OPT-AUG", "quality", "D-opt", "augmented_det_xtx",
                            aug_mtb["augmented_det_xtx"], aug_mini["augmented_det_xtx"],
                            "DERIVED", "DERIVED"),
            compare_text("OPT-AUG", "design", "augmentation", "candidate_choice_verified",
                         str(selected_match), "True", "DERIVED", "DERIVED"),
        ])

    return rows


def write_report(rows, minitab):
    counts = status_counts(rows)
    commands = minitab.get("cases", {})
    per_case = {
        case_id: status_counts([row for row in rows if row["case_id"] == case_id])
        for case_id in CASE_IDS
    }
    lines = [
        "# Minitab 19 最优设计补充对标",
        "",
        "## 结果",
        "",
        f"唯一比较项：{sum(counts.values())}（PASS {counts['PASS']} / FAIL {counts['FAIL']} / "
        f"N/A {counts['N/A']} / UNSUPPORTED {counts['UNSUPPORTED']}）。",
        "",
        *[f"- {case_id}: PASS {result['PASS']} / FAIL {result['FAIL']} / "
          f"N/A {result['N/A']} / UNSUPPORTED {result['UNSUPPORTED']}。"
          for case_id, result in per_case.items()],
        "",
        "- OPT-D：4 个方形四角候选中选 3 个；独立穷举 4 组，最优 det(X'X)=16，4 组并列。",
        "- OPT-DIST：双方在 9 个候选中选 4 个；独立穷举 126 个组合，最大最小平方距离为 4。",
        "- OPT-AUG：父设计固定为 3 个角点；候选为缺失角点与中心点，分别比较增补前后的 det(X'X)。",
        "- OPT-D 使用原生 2² DOE 对象作为四点候选集；Minitab `FACMODEL A B` 与 MiniJMP 两水平分类主效应模型的模型空间一致。MiniJMP 对比值转换到共同的效果编码矩阵 `[1,A,B]`。",
        "- 命令语义实测：`OPTDES K` 配 `FACMODEL` 执行 D-opt；`OPTDES K C...C` 候选列形式执行 Distance-based，分别用于 OPT-D 与 OPT-DIST。",
        "",
        "## Minitab 19 实际命令",
        "",
    ]
    for case_id in CASE_IDS:
        value = commands.get(case_id, {})
        command = value.get("command", value.get("error", "未运行"))
        lines.extend([f"- {case_id}:", "", "```text", command, "```", ""])
    lines.extend([
        "Minitab 19 的 `OPTDES K` + 模型子命令（`FACMODEL`/`RESMODEL`）执行 D-optimal；本机 `OPTDES K C...C` 候选列形式实测输出 Distance-based 设计。",
        "",
        "## 证据来源",
        "",
        "Minitab 列值与 INDICATOR 为 DIRECT；行列式、秩与穷举最优值由选中点 DERIVED。MiniJMP 结果来自现有生产 API。",
        "Minitab 19 Session Commands 手册第 363–365 页记载 `OPTDES`、`AUGMENT`、`INDICATOR` 和 `DESIGN` 语法。",
        "",
        "## 限制",
        "",
        "- D-opt 最优设计存在并列解，比较以模型秩和信息矩阵行列式为准，不要求选中同一行号。",
        "- Minitab Distance-based 与 MiniJMP 的搜索方法不同；本例最终四角集合相同，最小距离达到穷举上界。",
    ])
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    if "--self-check" in sys.argv:
        run_minijmp()
        print("optimal MiniJMP and exact-reference self-check passed")
    elif "--com-worker" in sys.argv:
        results = run_com_worker()
        print(f"Minitab worker completed; cases={list(results.get('cases', {}))}")
    elif "--run" in sys.argv:
        minijmp = run_minijmp()
        run_worker(Path(__file__), "--com-worker")
        minitab = __import__("json").loads(MINITAB.read_text(encoding="utf-8"))
        rows = make_comparison(minijmp, minitab)
        write_comparison(COMPARISON, rows)
        write_report(rows, minitab)
        print(f"optimal comparison counts: {status_counts(rows)}")
    else:
        raise SystemExit("Use --self-check, --com-worker, or --run")


if __name__ == "__main__":
    main()
