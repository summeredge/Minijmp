"""Mixture v2 joint-design comparison against Minitab 19.1.0.1."""
from __future__ import annotations

import csv
import gc
import hashlib
import json
import math
import re
import subprocess
import sys
import time
import traceback
from pathlib import Path


OUT = Path(__file__).resolve().parent
ROOT = Path(__file__).resolve().parents[4]
PARITY = ROOT / "Out" / "minitab19_parity"
CODE = ROOT / "code"
PROJECT_PYTHON = ROOT / ".venv" / "Scripts" / "python.exe"
FIXTURE = ROOT / "tests" / "fixtures" / "doe_phase2_p4bc_reference" / "reference.json"
INPUT = OUT / "mixture_v2_joint_input.csv"
MINIJMP = OUT / "mixture_v2_minijmp_results.json"
MINITAB = OUT / "mixture_v2_minitab_results.json"
RAW = OUT / "mixture_v2_minitab_raw_output.txt"
COMMANDS = OUT / "mixture_v2_session_commands.txt"
COMPARISON = OUT / "mixture_v2_comparison.csv"
REPORT = OUT / "mixture_v2_acceptance_report.md"

TERMS = (
    "A", "B", "C", "A*B", "A*C", "B*C",
    "A*P1", "B*P1", "C*P1", "A*P2", "B*P2", "C*P2",
    "A*T", "B*T", "C*T",
)
INPUT_FIELDS = (
    "standard_order", "run_order", "A", "B", "C", "P1", "P2", "T", "Y",
    *(f"X{index:02d}" for index in range(1, 16)),
)
if str(CODE) not in sys.path:
    sys.path.insert(0, str(CODE))
if str(PARITY / "supplemental") not in sys.path:
    sys.path.insert(0, str(PARITY / "supplemental"))
if str(PARITY) not in sys.path:
    sys.path.insert(0, str(PARITY))

from common import compare_numeric, compare_text, write_comparison, write_json  # noqa: E402
from verify_doe_ccd import canonical, running_minitab_pids  # noqa: E402


def _coded_process(value: float) -> int:
    if math.isclose(value, 1.0, rel_tol=0, abs_tol=1e-10):
        return -1
    if math.isclose(value, 2.0, rel_tol=0, abs_tol=1e-10):
        return 1
    raise ValueError(f"过程水平应为1或2，实际为{value}")


def _design_key(proportions, p1, p2, total):
    return (
        tuple(round(float(value), 12) for value in proportions),
        (_coded_process(float(p1)), _coded_process(float(p2))),
        round(2 * (float(total) - 100) / 100 - 1, 12),
    )


def _key_label(key) -> str:
    proportions, process_codes, amount_code = key
    return (f"mix={','.join(map(str, proportions))};"
            f"proc={','.join(map(str, process_codes))};amount={amount_code:g}")


def run_minijmp_worker() -> None:
    import numpy as np

    from doe_mixture import MixtureSpec, mixture_metadata
    from doe_mixture_analysis import analyze_mixture
    from doe_mixture_constraints import ComponentSpec, VariableSpec
    from doe_mixture_designs import create_mixture_design
    from doe_mixture_predict import predict_mixture

    if Path(sys.executable).resolve() != PROJECT_PYTHON.resolve():
        raise RuntimeError(f"请使用项目解释器运行: {PROJECT_PYTHON}")
    fixture_bytes = FIXTURE.read_bytes()
    reference = json.loads(fixture_bytes.decode("utf-8"))
    section = reference["joint_mixture_process_amount_model"]
    spec = MixtureSpec(
        "MIX-JOINT",
        tuple(ComponentSpec(name, name) for name in "ABC"),
        ("Y",),
        "simplex_lattice",
        2,
        process_variables=tuple(
            VariableSpec(name, name, 1, 2) for name in ("P1", "P2")),
        amount_variables=(VariableSpec("T", "T", 100, 200, role="amount"),),
        amount_settings=(("T", 150),),
        seed=17,
        construction_version="v2",
    )
    frame, _ = create_mixture_design(spec, amount_levels=(100, 150, 200))

    response_by_key = {}
    for item, response in zip(section["rows"], section["responses"]):
        key = (
            tuple(round(float(value), 12) for value in item["proportions"]),
            tuple(item["process_codes"]),
            round(float(item["amount_code"]), 12),
        )
        response_by_key[key] = float(response)

    def row_key(row):
        proportions = [float(row[f"设定_{name}"]) for name in "ABC"]
        return _design_key(proportions, row["设定_P1"], row["设定_P2"], row["设定_T"])

    frame = frame.copy(deep=True)
    frame["响应_Y"] = [response_by_key[row_key(row)] for _, row in frame.iterrows()]
    frame = frame.sort_values("标准序").reset_index(drop=True)
    metadata = mixture_metadata(frame, spec)
    analysis = analyze_mixture(frame, metadata, "Y")
    prediction = predict_mixture(
        frame, metadata, "Y", [1 / 3, 1 / 3, 1 / 3],
        {"P1": 1, "P2": 2}, {"T": 175},
    )
    matrix = analysis["model"].matrix(analysis["settings"])
    terms = list(analysis["terms"])

    reference_matrix = {
        (
            tuple(round(float(value), 12) for value in item["proportions"]),
            tuple(item["process_codes"]),
            round(float(item["amount_code"]), 12),
        ): row
        for item, row in zip(section["rows"], section["matrix"])
    }
    expected_matrix = np.asarray([
        reference_matrix[row_key(row)]
        for _, row in frame.iterrows()
    ], dtype=float)
    matrix_error = float(np.max(np.abs(matrix - expected_matrix)))

    rows = []
    for index, (_, row) in enumerate(frame.iterrows()):
        settings = {
            **{name: float(row[f"设定_{name}"]) for name in "ABC"},
            **{name: float(row[f"设定_{name}"]) for name in ("P1", "P2", "T")},
        }
        rows.append({
            "standard_order": int(row["标准序"]),
            "run_order": int(row["运行序"]),
            "settings": settings,
            "response": float(row["响应_Y"]),
            "matrix": [float(value) for value in matrix[index]],
            "fit": float(analysis["fitted"][index]),
            "residual": float(analysis["residuals"][index]),
        })

    with INPUT.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=INPUT_FIELDS, lineterminator="\n")
        writer.writeheader()
        for item in rows:
            writer.writerow({
                "standard_order": item["standard_order"],
                "run_order": item["run_order"],
                **item["settings"],
                "Y": item["response"],
                **{f"X{index:02d}": value
                   for index, value in enumerate(item["matrix"], 1)},
            })

    expected = section["expected"]
    api_result = {
        "source_fixture": str(FIXTURE),
        "source_fixture_sha256": hashlib.sha256(fixture_bytes).hexdigest(),
        "fixture_expectation": {
            "n": int(expected["n"]),
            "p": int(expected["p"]),
            "rank": int(expected["rank"]),
            "residual_df": int(expected["residual_df"]),
            "sse": float(expected["sse"]),
            "prediction": float(expected["prediction"]["value"]),
            "coefficients": [float(value) for value in section["estimated_beta"]],
        },
        "production_api_actual": {
            "n": int(analysis["n"]),
            "p": int(analysis["p"]),
            "rank": int(analysis["rank"]),
            "error_df": int(analysis["df"]),
            "condition_number_2": float(analysis["condition_number"]),
            "sse": float(analysis["sse"]),
            "terms": terms,
            "coefficients": [float(value) for value in analysis["coefficients"]],
            "has_constant": bool(analysis["has_constant"]),
            "total_df": int(analysis["total_df"]),
            "model_df": int(analysis["model_df"]),
            "sst": float(analysis["sst"]),
            "ssr": float(analysis["ssr"]),
            "r2": float(analysis["r2"]),
            "adjusted_r2": float(analysis["adjusted_r2"]),
            "pure_error_df": int(analysis["pure_error_df"]),
            "pure_error_sse": float(analysis["pure_error_sse"]),
            "lack_of_fit_df": int(analysis["lack_of_fit_df"]),
            "lack_of_fit_sse": float(analysis["lack_of_fit_sse"]),
            "inference_status": analysis["status"],
            "anova": [
                {
                    "term": item["source"], "ss": float(item["ss"]),
                    "df": int(item["df"]),
                    "f": None if item["f"] is None else float(item["f"]),
                    "p": None if item["p"] is None else float(item["p"]),
                }
                for item in analysis["anova"]
            ],
            "prediction": {
                "value": float(prediction["prediction"]),
                "settings": prediction["settings"],
                "proportions": prediction["proportions"],
                "actual_amounts": prediction["actual_amounts"],
                "interval_status": prediction["intervals"]["status"],
            },
            "fixture_matrix_max_abs_error": matrix_error,
            "matrix": [[float(value) for value in row] for row in matrix],
            "rows": rows,
        },
    }
    write_json(MINIJMP, api_result)
    print(
        "MiniJMP production API: "
        f"rows={analysis['n']}, matrix={analysis['n']}x{analysis['p']}, "
        f"rank={analysis['rank']}, SSE={analysis['sse']:.17g}, "
        f"error_df={analysis['df']}, prediction={prediction['prediction']:.17g}; "
        f"independent fixture matrix max abs error={matrix_error:.3g}",
        flush=True,
    )


def _column_values(column):
    value = column.GetData()
    values = [value] if isinstance(value, (int, float)) else list(value)
    return [
        None if item is None or (isinstance(item, str) and item.strip() in ("", "*"))
        else float(item)
        for item in values
    ]


def _raw_column_values(column):
    value = column.GetData()
    values = [value] if isinstance(value, (int, float, str)) else list(value)
    return [
        None if item is None or (isinstance(item, str) and item.strip() in ("", "*"))
        else item
        for item in values
    ]


def _find_column(columns, wanted, required=True):
    targets = {str(name).replace(" ", "").replace("_", "").casefold()
               for name in wanted}
    for index in range(1, int(columns.Count) + 1):
        name = str(columns.Item(index).Name).replace(" ", "").replace("_", "").casefold()
        if name in targets:
            return index
    if required:
        names = [str(columns.Item(index).Name)
                 for index in range(1, int(columns.Count) + 1)]
        raise RuntimeError(f"Minitab 缺少列 {tuple(wanted)}；实际列={names}")
    return None


def _read_matrix(worksheet, name):
    matrices = worksheet.Matrices
    matrix = next(
        (matrices.Item(index) for index in range(1, int(matrices.Count) + 1)
         if str(matrices.Item(index).Name).casefold() == name.casefold()),
        None,
    )
    if matrix is None:
        raise RuntimeError(f"Minitab 未存储矩阵 {name}")
    n, p = int(matrix.RowCount), int(matrix.ColumnCount)
    flat = [float(value) for value in matrix.GetData()]
    if len(flat) != n * p:
        raise RuntimeError(f"Minitab 矩阵 {name} 维度与数据长度不符")
    return [[flat[column * n + row] for column in range(p)] for row in range(n)]


def _execute(project, app, label, command, raw, command_log):
    from verify_doe_ccd import capture_command_output

    command_log.append(f"===== {label} =====\n{command}")
    before = int(project.Commands.Count)
    project.ExecuteCommand(command)
    deadline = time.monotonic() + 12
    while int(project.Commands.Count) <= before and time.monotonic() < deadline:
        time.sleep(0.1)
    after = int(project.Commands.Count)
    output = capture_command_output(project, after) if after > before else ""
    last_error = str(app.LastError or "")
    error_marker = bool(re.search(r"(?im)^\s*\*\s*(?:ERROR|错误)\s*\*", output))
    raw.append(
        f"===== {label}: actual session command =====\n{command}\n"
        f"===== {label}: OutputDocument / Outputs =====\n{output or '(empty)'}\n"
        f"===== {label}: LastError =====\n{last_error or '(empty)'}\n"
        f"===== {label}: command object created =====\n{after > before}"
    )
    return {
        "label": label, "command": command, "command_object_created": after > before,
        "error_marker": error_marker, "last_error": last_error, "output": output,
        "ok": after > before and not error_marker,
    }


def _add_column(columns, name, values=None):
    column = columns.Add(None, None, 1)
    column.Name = name
    index = int(columns.Count)
    if values is not None:
        column.SetData(tuple(values), 1, len(values))
    return index


def _design_rows_from_sldesign(project, local_rows, expected_n=72):
    columns = project.ActiveWorksheet.Columns
    names = [str(columns.Item(index).Name)
             for index in range(1, int(columns.Count) + 1)]
    indices = {
        name: _find_column(columns, (name,))
        for name in "ABC"
    }
    indices["P1"] = _find_column(columns, ("P1", "X1"))
    indices["P2"] = _find_column(columns, ("P2", "X2"))
    std_index = _find_column(columns, ("StdOrder", "StandardOrder", "标准序"), False)
    run_index = _find_column(columns, ("RunOrder", "运行序"), False)
    column_data = {
        name: _column_values(columns.Item(index))
        for name, index in indices.items()
    }
    n = len(column_data["A"])
    if any(len(values) != n for values in column_data.values()):
        raise RuntimeError("SLDESIGN 因子列长度不一致")
    if n != expected_n:
        raise RuntimeError(f"SLDESIGN 应生成{expected_n}行，实际为{n}行")

    local_by_key = {
        _design_key(
            [row["settings"][name] for name in "ABC"],
            row["settings"]["P1"], row["settings"]["P2"], row["settings"]["T"],
        ): row
        for row in local_rows
    }
    process_levels = {
        name: {round(value, 12) for value in column_data[name] if value is not None}
        for name in ("P1", "P2")
    }
    if all(levels == {1.0, 2.0} for levels in process_levels.values()):
        process_code = lambda value: -1 if math.isclose(value, 1, abs_tol=1e-10) else 1
    elif all(levels == {-1.0, 1.0} for levels in process_levels.values()):
        process_code = lambda value: -1 if value < 0 else 1
    else:
        raise RuntimeError(f"SLDESIGN 过程水平与命令不符: {process_levels}")

    std_values = (_column_values(columns.Item(std_index)) if std_index else None)
    run_values = (_column_values(columns.Item(run_index)) if run_index else None)
    rows = []
    for index in range(n):
        amount_components = [column_data[name][index] for name in "ABC"]
        p1, p2 = column_data["P1"][index], column_data["P2"][index]
        if any(value is None for value in (*amount_components, p1, p2)):
            raise RuntimeError(f"SLDESIGN 第{index + 1}行含空因子值")
        total_sum = sum(amount_components)
        total = min((100.0, 150.0, 200.0), key=lambda level: abs(level - total_sum))
        if abs(total_sum - total) > 1e-7:
            raise RuntimeError(f"SLDESIGN 第{index + 1}行组分总量异常: {total_sum:.17g}")
        proportions = [value / total_sum for value in amount_components]
        key = (
            tuple(round(value, 12) for value in proportions),
            (process_code(p1), process_code(p2)),
            round(2 * (total - 100) / 100 - 1, 12),
        )
        local = local_by_key.get(key)
        if local is None:
            raise RuntimeError(f"SLDESIGN 设计点无法映射MiniJMP固定输入: {_key_label(key)}")
        rows.append({
            "worksheet_row": index + 1,
            "standard_order": (int(std_values[index]) if std_values else index + 1),
            "run_order": (int(run_values[index]) if run_values else index + 1),
            "amount_components": [float(value) for value in amount_components],
            "proportions": [float(value) for value in proportions],
            "P1": float(p1), "P2": float(p2), "T": float(total),
            "Y": float(local["response"]),
            "key": _key_label(key),
        })
    if len({row["key"] for row in rows}) != expected_n:
        raise RuntimeError("SLDESIGN 输出含重复联合设计点")
    return {
        "columns": names,
        "column_data": column_data,
        "rows": rows,
        "standard_order_source": (
            str(columns.Item(std_index).Name) if std_index else "worksheet row order"),
        "run_order_source": (
            str(columns.Item(run_index).Name) if run_index else "worksheet row order"),
    }


def _store_mixreg(project, app, raw, command_log, local_rows, native_design=None):
    columns = project.ActiveWorksheet.Columns
    if native_design is None:
        _add_column(columns, "A", [row["settings"]["A"] * row["settings"]["T"]
                                   for row in local_rows])
        _add_column(columns, "B", [row["settings"]["B"] * row["settings"]["T"]
                                   for row in local_rows])
        _add_column(columns, "C", [row["settings"]["C"] * row["settings"]["T"]
                                   for row in local_rows])
        _add_column(columns, "P1", [row["settings"]["P1"] for row in local_rows])
        _add_column(columns, "P2", [row["settings"]["P2"] for row in local_rows])
        total_values = [row["settings"]["T"] for row in local_rows]
        response_values = [row["response"] for row in local_rows]
    else:
        total_values = [row["T"] for row in native_design["rows"]]
        response_values = [row["Y"] for row in native_design["rows"]]
    total_index = _add_column(columns, "MTOTAL", total_values)
    response_index = _add_column(columns, "MY", response_values)
    storage = {
        name: _add_column(columns, name)
        for name in ("MFIT", "MRES", "MCOEF", "MMODEL", "MPRED")
    }
    prediction_columns = [
        _add_column(columns, name, [value])
        for name, value in (
            ("QA", 175 / 3), ("QB", 175 / 3), ("QC", 175 / 3),
            ("QP1", 1), ("QP2", 2), ("QT", 175),
        )
    ]
    component_indices = [_find_column(columns, (name,)) for name in "ABC"]
    process_indices = [
        _find_column(columns, ("P1", "X1")),
        _find_column(columns, ("P2", "X2")),
    ]
    matrix_name = "M1"
    terms = (
        [f"C{index}" for index in component_indices]
        + [f"C{component_indices[a]}*C{component_indices[b]}"
           for a, b in ((0, 1), (0, 2), (1, 2))]
        + [f"C{component}*C{process}"
           for process in process_indices for component in component_indices]
    )
    command = (
        f"MIXREG C{response_index} = {' '.join(terms)};\n"
        f"  PROC C{process_indices[0]} C{process_indices[1]};\n"
        f"  AMOUNT C{total_index};\n"
        "  INUNIT 2;\n  BRIEF 3;\n"
        f"  FITS C{storage['MFIT']};\n"
        f"  RESIDUALS C{storage['MRES']};\n"
        f"  COEFFICIENTS C{storage['MCOEF']};\n"
        f"  MODEL C{storage['MMODEL']};\n"
        f"  XMATRIX {matrix_name};\n"
        + "  PREDICT " + " ".join(f"C{index}" for index in prediction_columns) + ";\n"
        + f"  PSFITS C{storage['MPRED']}."
    )
    attempt = _execute(project, app, "MIXREG native PROC + AMOUNT", command, raw, command_log)
    result = {
        "attempt": attempt,
        "attempts": [attempt],
        "amount_attempt": attempt,
        "input_basis": (
            "SLDESIGN actual component amounts" if native_design is not None
            else "MiniJMP production settings converted to amount units"
        ),
    }
    if (native_design is not None and not attempt["ok"]
            and "AMOUNT" in attempt["last_error"].upper()):
        command_without_amount = (
            f"MIXREG C{response_index} = {' '.join(terms)};\n"
            f"  PROC C{process_indices[0]} C{process_indices[1]};\n"
            "  INUNIT 2;\n  LOWER 0 0 0;\n  BRIEF 3;\n"
            f"  FITS C{storage['MFIT']};\n"
            f"  RESIDUALS C{storage['MRES']};\n"
            f"  COEFFICIENTS C{storage['MCOEF']};\n"
            f"  MODEL C{storage['MMODEL']};\n"
            f"  XMATRIX {matrix_name}."
        )
        attempt = _execute(
            project, app, "MIXREG native PROC without AMOUNT",
            command_without_amount, raw, command_log)
        result["attempts"].append(attempt)
        result["attempt"] = attempt
    if attempt["command_object_created"]:
        try:
            matrix = _read_matrix(project.ActiveWorksheet, matrix_name)
            n, p = len(matrix), len(matrix[0]) if matrix else 0
            if native_design:
                row_order = sorted(
                    range(len(native_design["rows"])),
                    key=lambda index: native_design["rows"][index]["standard_order"],
                )
            else:
                row_order = list(range(n))
            matrix = [matrix[index] for index in row_order]
            fitted = _column_values(columns.Item(storage["MFIT"]))[:n]
            residuals = _column_values(columns.Item(storage["MRES"]))[:n]
            result.update({
                "matrix": matrix,
                "n": n,
                "p": p,
                "row_keys": (
                    [native_design["rows"][index]["key"] for index in row_order]
                    if native_design else [
                        _key_label(_design_key(
                            [row["settings"][name] for name in "ABC"],
                            row["settings"]["P1"], row["settings"]["P2"],
                            row["settings"]["T"],
                        ))
                        for row in local_rows
                    ]
                ),
                "coefficients": [value for value in _column_values(
                    columns.Item(storage["MCOEF"])) if value is not None][:p],
                "fitted": [fitted[index] for index in row_order],
                "residuals": [residuals[index] for index in row_order],
                "model_codes": _raw_column_values(columns.Item(storage["MMODEL"])),
                "prediction_values": (
                    [
                        value for value in _column_values(columns.Item(storage["MPRED"]))
                        if value is not None
                    ] if "AMOUNT" in attempt["command"] else []
                ),
                "row_order": row_order,
            })
        except Exception as exc:
            result["read_error"] = f"{type(exc).__name__}: {exc}"
    return result


def _store_regress(app, project, local_rows, raw, command_log):
    import numpy as np

    app.New()
    project = app.ActiveProject
    worksheet = project.ActiveWorksheet
    columns = worksheet.Columns
    settings = [row["settings"] for row in local_rows]
    _add_column(columns, "A", [row["A"] for row in settings])
    _add_column(columns, "B", [row["B"] for row in settings])
    _add_column(columns, "C", [row["C"] for row in settings])
    _add_column(columns, "P1", [row["P1"] for row in settings])
    _add_column(columns, "P2", [row["P2"] for row in settings])
    _add_column(columns, "T", [row["T"] for row in settings])
    response_index = _add_column(columns, "Y", [row["response"] for row in local_rows])
    matrix = [row["matrix"] for row in local_rows]
    feature_indices = [
        _add_column(columns, f"X{index:02d}",
                    [row[index - 1] for row in matrix])
        for index in range(1, 16)
    ]
    input_readback = [
        _column_values(columns.Item(index))[:len(local_rows)]
        for index in feature_indices
    ]
    matrix_error = max(
        abs(input_readback[column][row] - matrix[row][column])
        for row in range(len(local_rows)) for column in range(15)
    )
    output_columns = {
        name: _add_column(columns, name)
        for name in ("RCOEF", "RFIT", "RRES", "RPRED")
    }
    terms = " ".join(f"C{index}" for index in feature_indices)
    command = (
        "REGRESS;\n"
        f"  RESPONSE C{response_index};\n"
        f"  CONTINUOUS {terms};\n"
        f"  TERMS {terms};\n"
        "  NOCONSTANT;\n"
        f"  COEFFICIENTS C{output_columns['RCOEF']};\n"
        f"  FITS C{output_columns['RFIT']};\n"
        f"  RESIDUALS C{output_columns['RRES']};\n"
        "  XMATRIX M1."
    )
    attempt = _execute(project, app, "REGRESS explicit 15-column NOCONSTANT", command,
                       raw, command_log)
    result = {"attempt": attempt, "input_matrix_max_abs_error": float(matrix_error)}
    if attempt["ok"]:
        try:
            native_matrix = _read_matrix(worksheet, "M1")
            n, p = len(native_matrix), len(native_matrix[0]) if native_matrix else 0
            result.update({
                "matrix": native_matrix,
                "n": n,
                "p": p,
                "coefficients": [
                    value for value in _column_values(
                        columns.Item(output_columns["RCOEF"])) if value is not None
                ][:p],
                "fitted": _column_values(columns.Item(output_columns["RFIT"]))[:n],
                "residuals_fit_minus_y": _column_values(
                    columns.Item(output_columns["RRES"]))[:n],
                "rank": int(np.linalg.matrix_rank(native_matrix)),
            })
        except Exception as exc:
            result["read_error"] = f"{type(exc).__name__}: {exc}"

    query_row = [1 / 3, 1 / 3, 1 / 3, 1 / 9, 1 / 9, 1 / 9,
                 -1 / 3, -1 / 3, -1 / 3, 1 / 3, 1 / 3, 1 / 3,
                 1 / 6, 1 / 6, 1 / 6]
    prediction_command = (
        'PREDICT "multiple_regression|1";\n'
        "  KPREDICTORS " + " ".join(format(value, ".17g") for value in query_row) + ";\n"
        f"  PFITS C{output_columns['RPRED']}."
    )
    prediction_attempt = _execute(
        project, app, "PREDICT REGRESS target", prediction_command, raw, command_log)
    result["prediction_attempt"] = prediction_attempt
    if prediction_attempt["ok"]:
        try:
            result["prediction_values"] = [
                value for value in _column_values(
                    columns.Item(output_columns["RPRED"])) if value is not None
            ]
        except Exception as exc:
            result["prediction_read_error"] = f"{type(exc).__name__}: {exc}"
    return result


def _matrix_space_error(left, right):
    import numpy as np

    left, right = np.asarray(left, dtype=float), np.asarray(right, dtype=float)
    if left.shape[0] != right.shape[0]:
        return 1.0

    def basis(matrix):
        u, singular, _ = np.linalg.svd(matrix, full_matrices=False)
        tolerance = singular[0] * np.finfo(float).eps * max(matrix.shape)
        rank = int(np.sum(singular > tolerance))
        return u[:, :rank]

    left_basis, right_basis = basis(left), basis(right)
    difference = left_basis @ left_basis.T - right_basis @ right_basis.T
    return float(np.max(np.abs(difference)))


def minitab_worker() -> None:
    import pythoncom
    import win32com.client
    import numpy as np

    from verify_minitab19_com import MTB_EXE, file_version, process_image_path

    local = json.loads(MINIJMP.read_text(encoding="utf-8"))
    local_rows = local["production_api_actual"]["rows"]
    initial_pids = running_minitab_pids()
    result = {
        "version": None,
        "app_path": None,
        "process_path": None,
        "pid": None,
        "existing_pids_at_start": initial_pids,
        "sldesign": {"status": "UNSUPPORTED"},
        "mixreg": {"status": "UNSUPPORTED"},
        "regress": {"status": "UNSUPPORTED"},
    }
    raw, command_log = [], []
    app = ui = project = worksheet = columns = None

    def save_logs():
        RAW.write_text("\n\n".join(raw) + "\n", encoding="utf-8")
        COMMANDS.write_text("\n\n".join(command_log) + "\n", encoding="utf-8")

    if initial_pids:
        raise RuntimeError(
            f"检测到已有 Minitab 进程 PID={initial_pids}；"
            "为保护现有会话，本次拒绝启动 COM worker。"
        )

    try:
        if not MTB_EXE.is_file():
            raise FileNotFoundError(MTB_EXE)
        version = file_version(MTB_EXE)
        if version != "19.1.0.1":
            raise RuntimeError(f"要求 Minitab 19.1.0.1，实际版本为{version}")
        pythoncom.CoInitialize()
        app = win32com.client.DispatchEx("Mtb.Application")
        pythoncom.PumpWaitingMessages()
        ui = app.UserInterface
        ui.Visible = False
        ui.UserControl = False
        ui.DisplayAlerts = False
        hwnd = int(app.Handle)
        pid, process_path = process_image_path(hwnd)
        app_path = str(app.AppPath)
        if pid in initial_pids:
            raise RuntimeError(f"DispatchEx 返回了既有 Minitab PID {pid}")
        if canonical(app_path) != canonical(MTB_EXE) or canonical(process_path) != canonical(MTB_EXE):
            raise RuntimeError(
                f"COM 路径与指定 Minitab 不符: AppPath={app_path}; process={process_path}")
        project = app.ActiveProject
        if project is None:
            app.New()
            project = app.ActiveProject
        result.update({
            "version": version, "app_path": app_path,
            "process_path": process_path, "pid": pid,
        })
        raw.append(
            f"Minitab version={version}; AppPath={app_path}; process={process_path}; "
            f"PID={pid}; existing PIDs before DispatchEx={initial_pids}"
        )

        sldesign_command = (
            "SLDESIGN 3 2;\n"
            "  PROC 2;\n"
            "  LEVELS 1 2 1 2;\n"
            "  TOTAL 100 150 200;\n"
            "  DESIGN."
        )
        sldesign = _execute(
            project, app, "SLDESIGN PROC TOTAL", sldesign_command, raw, command_log)
        native_design = None
        result["sldesign"] = {
            "attempt": sldesign, "attempts": [sldesign], "status": "UNSUPPORTED",
            "total_source": "TOTAL 100 150 200 constants",
        }
        if sldesign["ok"]:
            try:
                native_design = _design_rows_from_sldesign(project, local_rows)
                result["sldesign"].update(native_design)
                result["sldesign"]["status"] = "PASS"
                raw.append(
                    "===== SLDESIGN direct worksheet evidence =====\n"
                    + json.dumps(native_design, ensure_ascii=False, indent=2, allow_nan=False)
                )
            except Exception as exc:
                result["sldesign"]["read_error"] = f"{type(exc).__name__}: {exc}"
                raw.append(f"SLDESIGN worksheet extraction failed: {type(exc).__name__}: {exc}")

        if not sldesign["ok"]:
            app.New()
            project = app.ActiveProject
            total_column = _add_column(
                project.ActiveWorksheet.Columns, "TOTIN", [100, 150, 200])
            sldesign_column_command = (
                "SLDESIGN 3 2;\n"
                "  PROC 2;\n"
                "  LEVELS 1 2 1 2;\n"
                f"  TOTAL C{total_column};\n"
                "  DESIGN."
            )
            sldesign = _execute(
                project, app, "SLDESIGN PROC TOTAL-column",
                sldesign_column_command, raw, command_log)
            result["sldesign"]["attempts"].append(sldesign)
            if sldesign["ok"]:
                result["sldesign"]["attempt"] = sldesign
                try:
                    native_design = _design_rows_from_sldesign(project, local_rows)
                    result["sldesign"].update(native_design)
                    result["sldesign"]["status"] = "PASS"
                    result["sldesign"]["total_source"] = "TOTAL C column [100, 150, 200]"
                    raw.append(
                        "===== SLDESIGN TOTAL-column worksheet evidence =====\n"
                        + json.dumps(native_design, ensure_ascii=False, indent=2, allow_nan=False)
                    )
                except Exception as exc:
                    result["sldesign"]["column_read_error"] = (
                        f"{type(exc).__name__}: {exc}")
                    raw.append(
                        f"SLDESIGN TOTAL-column extraction failed: {type(exc).__name__}: {exc}")

        if native_design is None:
            app.New()
            project = app.ActiveProject
            single_total_command = (
                "SLDESIGN 3 2;\n"
                "  PROC 2;\n"
                "  LEVELS 1 2 1 2;\n"
                "  TOTAL 150;\n"
                "  DESIGN."
            )
            single_total = _execute(
                project, app, "SLDESIGN PROC single TOTAL", single_total_command,
                raw, command_log)
            result["sldesign"]["single_total_attempt"] = single_total
            if single_total["ok"]:
                try:
                    single_design = _design_rows_from_sldesign(
                        project, local_rows, expected_n=24)
                    result["sldesign"]["single_total_design"] = single_design
                    result["sldesign"]["single_total_status"] = "PASS"
                    native_design = single_design
                    raw.append(
                        "===== SLDESIGN single-TOTAL worksheet evidence =====\n"
                        + json.dumps(single_design, ensure_ascii=False, indent=2, allow_nan=False)
                    )
                except Exception as exc:
                    result["sldesign"]["single_total_read_error"] = (
                        f"{type(exc).__name__}: {exc}")
                    result["sldesign"]["single_total_status"] = "UNSUPPORTED"
                    raw.append(
                        f"SLDESIGN single-TOTAL extraction failed: {type(exc).__name__}: {exc}")
            else:
                result["sldesign"]["single_total_status"] = "UNSUPPORTED"

        save_logs()

        if native_design is None:
            app.New()
            project = app.ActiveProject
        mixreg = _store_mixreg(project, app, raw, command_log, local_rows, native_design)
        result["mixreg"] = mixreg
        result["mixreg"]["status"] = (
            "DIRECT" if "matrix" in mixreg else "UNSUPPORTED")
        fallback_reason = "MIXREG 输出完整且模型空间等价，无需回退 REGRESS"
        if "matrix" in mixreg:
            local_matrix = local["production_api_actual"]["matrix"]
            try:
                error = _matrix_space_error(mixreg["matrix"], local_matrix)
                complete = (
                    mixreg["n"] == 72
                    and mixreg["p"] == 15
                    and len(mixreg.get("coefficients", [])) == 15
                    and len(mixreg.get("fitted", [])) == 72
                    and len(mixreg.get("residuals", [])) == 72
                    and bool(mixreg.get("prediction_values"))
                    and error <= 1e-9
                )
                result["mixreg"]["model_space_max_abs_projector_error"] = error
            except Exception as exc:
                complete = False
                result["mixreg"]["model_space_read_error"] = (
                    f"{type(exc).__name__}: {exc}")
            if not complete:
                fallback_reason = (
                    "MIXREG 非等价或未能完整提取模型矩阵、系数、拟合/残差、预测")
        else:
            fallback_reason = "MIXREG 命令失败或其输出无法提取完整模型矩阵"
        save_logs()

        if fallback_reason == "MIXREG 输出完整且模型空间等价，无需回退 REGRESS":
            result["regress"] = {"status": "NOT_REQUIRED", "reason": fallback_reason}
        else:
            result["regress"] = _store_regress(
                app, project, local_rows, raw, command_log)
            result["regress"]["status"] = (
                "DIRECT" if "matrix" in result["regress"] else "UNSUPPORTED")
            result["regress"]["fallback_reason"] = fallback_reason
            save_logs()
    except Exception as exc:
        result["worker_error"] = f"{type(exc).__name__}: {exc}"
        raw.append("===== COM worker exception =====\n" + traceback.format_exc())
        raise
    finally:
        columns = worksheet = project = ui = app = None
        gc.collect()
        try:
            pythoncom.PumpWaitingMessages()
            pythoncom.CoUninitialize()
        except Exception:
            pass
        write_json(MINITAB, result)
        save_logs()


def _append_numeric(rows, case_id, section, term, statistic, minitab_value,
                    minijmp_value, minitab_source, minijmp_source):
    row = compare_numeric(
        case_id, section, term, statistic, minitab_value, minijmp_value,
        minitab_source, minijmp_source,
    )
    row["comparison_run"] = "1"
    rows.append(row)


def _append_text(rows, case_id, section, term, statistic, minitab_value,
                 minijmp_value, minitab_source, minijmp_source):
    rows.append(compare_text(
        case_id, section, term, statistic, minitab_value, minijmp_value,
        minitab_source, minijmp_source,
    ))


def _append_unavailable(rows, case_id, section, term, statistic, status, reason,
                        minijmp_source="MiniJMP production API"):
    row = compare_numeric(case_id, section, term, statistic, None, None,
                          reason, minijmp_source)
    row["comparison_run"] = "1"
    row["status"] = status
    rows.append(row)


def _compare_minitab(minijmp, minitab):
    import numpy as np

    local = minijmp["production_api_actual"]
    fixture = minijmp["fixture_expectation"]
    rows = []
    for name, actual_key, expected_key in (
        ("n", "n", "n"), ("p", "p", "p"), ("rank", "rank", "rank"),
        ("error_df", "error_df", "residual_df"), ("SSE", "sse", "sse"),
        ("prediction", "prediction", "prediction"),
    ):
        actual = local["prediction"]["value"] if actual_key == "prediction" else local[actual_key]
        _append_numeric(
            rows, "MINIJMP_FIXTURE", "production_api", "joint_v2", name,
            actual, fixture[expected_key],
            "MiniJMP production API actual calculation",
            "Independent fixed reference fixture expectation",
        )
    _append_numeric(
        rows, "MINIJMP_FIXTURE", "production_api", "joint_v2",
        "fixture_matrix_max_abs_error", local["fixture_matrix_max_abs_error"], 0.0,
        "MiniJMP API matrix versus independent frozen matrix",
        "Independent fixed reference fixture",
    )
    for index, term in enumerate(TERMS):
        _append_numeric(
            rows, "MINIJMP_FIXTURE", "production_api", term, "coefficient",
            local["coefficients"][index], fixture["coefficients"][index],
            "MiniJMP analyze_mixture coefficient",
            "Independent fixed reference fixture coefficient",
        )

    local_rows = local["rows"]
    native_design = minitab.get("sldesign", {})
    if native_design.get("status") == "PASS":
        native_rows = native_design["rows"]
        local_by_key = {
            _key_label(_design_key(
                [item["settings"][name] for name in "ABC"],
                item["settings"]["P1"], item["settings"]["P2"], item["settings"]["T"],
            )): item
            for item in local_rows
        }
        native_by_key = {item["key"]: item for item in native_rows}
        _append_numeric(
            rows, "SLDESIGN", "design", "joint_v2", "row_count",
            len(native_rows), len(local_rows),
            "Minitab SLDESIGN DESIGN columns (DIRECT)",
            "MiniJMP create_mixture_design (DIRECT)",
        )
        _append_numeric(
            rows, "SLDESIGN", "design", "joint_v2", "unique_point_count",
            len(native_by_key), len(local_by_key),
            "Minitab SLDESIGN factor columns (DIRECT)",
            "MiniJMP create_mixture_design (DIRECT)",
        )
        _append_text(
            rows, "SLDESIGN", "design", "joint_v2", "design_point_set",
            "|".join(sorted(native_by_key)), "|".join(sorted(local_by_key)),
            "Minitab SLDESIGN points mapped by proportions/process/total",
            "MiniJMP v2 points mapped by proportions/process/total",
        )
        for key in sorted(native_by_key.keys() & local_by_key.keys()):
            native_row, local_row = native_by_key[key], local_by_key[key]
            for index, name in enumerate("ABC"):
                _append_numeric(
                    rows, "SLDESIGN", "design", key, f"{name}_proportion",
                    native_row["proportions"][index], local_row["settings"][name],
                    "Minitab SLDESIGN component amounts divided by row total (DERIVED)",
                    "MiniJMP design settings (DIRECT)",
                )
            for name in ("P1", "P2", "T"):
                _append_numeric(
                    rows, "SLDESIGN", "design", key, name,
                    native_row[name], local_row["settings"][name],
                    "Minitab SLDESIGN factor columns / component sum (DIRECT/DERIVED)",
                    "MiniJMP design settings (DIRECT)",
                )
    elif native_design.get("single_total_design"):
        single = native_design["single_total_design"]
        subset_rows = [
            row for row in local_rows
            if math.isclose(row["settings"]["T"], 150.0, rel_tol=0, abs_tol=1e-10)
        ]
        local_by_key = {
            _key_label(_design_key(
                [item["settings"][name] for name in "ABC"],
                item["settings"]["P1"], item["settings"]["P2"], item["settings"]["T"],
            )): item
            for item in subset_rows
        }
        native_by_key = {item["key"]: item for item in single["rows"]}
        _append_numeric(
            rows, "SLDESIGN", "single_total_subset", "T=150", "row_count",
            len(native_by_key), len(local_by_key),
            "Minitab SLDESIGN PROC 2; TOTAL 150 (DIRECT)",
            "MiniJMP 72-row design restricted to T=150 (DIRECT)",
        )
        _append_text(
            rows, "SLDESIGN", "single_total_subset", "T=150",
            "design_point_set",
            "|".join(sorted(native_by_key)), "|".join(sorted(local_by_key)),
            "Minitab SLDESIGN mixture/process points",
            "MiniJMP v2 mixture/process points at T=150",
        )
        for key in sorted(native_by_key.keys() & local_by_key.keys()):
            native_row, local_row = native_by_key[key], local_by_key[key]
            for index, name in enumerate("ABC"):
                _append_numeric(
                    rows, "SLDESIGN", "single_total_subset", key,
                    f"{name}_proportion", native_row["proportions"][index],
                    local_row["settings"][name],
                    "Minitab SLDESIGN component amounts divided by row total (DERIVED)",
                    "MiniJMP design settings (DIRECT)",
                )
            for name in ("P1", "P2", "T"):
                _append_numeric(
                    rows, "SLDESIGN", "single_total_subset", key, name,
                    native_row[name], local_row["settings"][name],
                    "Minitab SLDESIGN factor columns / component sum (DIRECT/DERIVED)",
                    "MiniJMP design settings (DIRECT)",
                )
        failed_attempts = native_design.get("attempts", [])
        reason = (
            failed_attempts[0].get("output")
            or failed_attempts[0].get("last_error")
            if failed_attempts else "multi-total SLDESIGN evidence unavailable"
        )
        _append_unavailable(
            rows, "SLDESIGN", "design", "joint_v2", "full72_design_point_set",
            "UNSUPPORTED",
            "Minitab rejects multiple TOTAL values with process variables: " + str(reason),
        )
    else:
        attempt = native_design.get("attempt", {})
        reason = (
            native_design.get("read_error")
            or attempt.get("last_error")
            or "SLDESIGN did not return a complete 72-row factor table"
        )
        _append_unavailable(
            rows, "SLDESIGN", "design", "joint_v2", "design_point_set",
            "UNSUPPORTED", f"Minitab SLDESIGN evidence: {reason}",
        )

    mixreg = minitab.get("mixreg", {})
    mixreg_matrix = mixreg.get("matrix")
    if mixreg_matrix is not None:
        native_x = np.asarray(mixreg_matrix, dtype=float)
        local_x = np.asarray(local["matrix"], dtype=float)
        if native_x.shape[0] == local_x.shape[0]:
            rank = int(np.linalg.matrix_rank(native_x))
            space_error = _matrix_space_error(native_x, local_x)
            _append_numeric(
                rows, "MIXREG_NATIVE", "model_space", "joint_v2", "row_count",
                native_x.shape[0], local_x.shape[0],
                "Minitab MIXREG XMATRIX M1 (DIRECT)",
                "MiniJMP 15-column model matrix (DIRECT)",
            )
            _append_numeric(
                rows, "MIXREG_NATIVE", "model_space", "joint_v2", "column_count",
                native_x.shape[1], local_x.shape[1],
                "Minitab MIXREG XMATRIX M1 (DIRECT)",
                "MiniJMP 15-column model matrix (DIRECT)",
            )
            _append_numeric(
                rows, "MIXREG_NATIVE", "model_space", "joint_v2", "rank",
                rank, local["rank"],
                "Minitab MIXREG XMATRIX M1 rank (DERIVED)",
                "MiniJMP analyze_mixture rank (DIRECT)",
            )
            _append_numeric(
                rows, "MIXREG_NATIVE", "model_space", "joint_v2",
                "max_abs_projector_error", space_error, 0.0,
                "DERIVED: Minitab and MiniJMP full-precision matrix column spaces",
                "Exact equality target",
            )
            equivalent = int(
                native_x.shape[1] == local_x.shape[1]
                and rank == local["rank"] and space_error <= 1e-9
            )
            _append_numeric(
                rows, "MIXREG_NATIVE", "model_space", "joint_v2",
                "equivalent_15_term_model_space", equivalent, 1,
                "DERIVED: Minitab MIXREG XMATRIX column-space comparison",
                "MiniJMP full-rank 15-term Scheffé×process×amount model",
            )
            if len(mixreg.get("fitted", [])) == 72:
                for index, local_row in enumerate(local_rows):
                    _append_numeric(
                        rows, "MIXREG_NATIVE", "fit", f"standard_order={index + 1}",
                        "fitted", mixreg["fitted"][index], local_row["fit"],
                        "Minitab MIXREG FITS storage (DIRECT)",
                        "MiniJMP analyze_mixture fitted (DIRECT)",
                    )
            if len(mixreg.get("residuals", [])) == 72:
                for index, local_row in enumerate(local_rows):
                    _append_numeric(
                        rows, "MIXREG_NATIVE", "fit", f"standard_order={index + 1}",
                        "residual", mixreg["residuals"][index], local_row["residual"],
                        "Minitab MIXREG RESIDUALS=response-fit (DIRECT)",
                        "MiniJMP analyze_mixture residuals=response-fit (DIRECT)",
                    )
                mix_sse = float(np.dot(mixreg["residuals"], mixreg["residuals"]))
                _append_numeric(
                    rows, "MIXREG_NATIVE", "model", "joint_v2", "SSE",
                    mix_sse, local["sse"],
                    "DERIVED: Minitab MIXREG residual storage",
                    "MiniJMP analyze_mixture SSE",
                )
                _append_numeric(
                    rows, "MIXREG_NATIVE", "model", "joint_v2", "error_df",
                    72 - rank, local["error_df"],
                    "DERIVED: Minitab MIXREG XMATRIX rank",
                    "MiniJMP analyze_mixture residual df",
                )
            if native_x.shape[1] == local_x.shape[1] and equivalent:
                coefficients = mixreg.get("coefficients", [])
                if len(coefficients) == 15:
                    transform = np.linalg.lstsq(local_x, native_x, rcond=None)[0]
                    transform_error = float(np.max(np.abs(local_x @ transform - native_x)))
                    converted = transform @ np.asarray(coefficients, dtype=float)
                    _append_numeric(
                        rows, "MIXREG_NATIVE", "model_space", "joint_v2",
                        "basis_reconstruction_max_abs_error", transform_error, 0.0,
                        "DERIVED: Minitab XMATRIX = MiniJMP matrix × basis transform",
                        "Exact equality target",
                    )
                    for index, term in enumerate(TERMS):
                        _append_numeric(
                            rows, "MIXREG_NATIVE", "coefficients", term, "coefficient",
                            converted[index], local["coefficients"][index],
                            "DERIVED: Minitab MIXREG coefficient converted to MiniJMP basis",
                            "MiniJMP analyze_mixture coefficient (DIRECT)",
                        )
                else:
                    _append_unavailable(
                        rows, "MIXREG_NATIVE", "coefficients", "joint_v2",
                        "equivalent_basis_coefficients", "UNSUPPORTED",
                        "Minitab MIXREG did not expose all 15 coefficients",
                    )
            else:
                _append_unavailable(
                    rows, "MIXREG_NATIVE", "coefficients", "joint_v2",
                    "equivalent_basis_coefficients", "N/A",
                    "MIXREG model space is not equivalent; coefficients have no common 15-term basis",
                )
            prediction_values = mixreg.get("prediction_values", [])
            if prediction_values:
                _append_numeric(
                    rows, "MIXREG_NATIVE", "prediction", "P1=1,P2=2,T=175",
                    "mean", prediction_values[0], local["prediction"]["value"],
                    "Minitab MIXREG PSFITS storage (DIRECT)",
                    "MiniJMP predict_mixture point prediction (DIRECT)",
                )
            else:
                attempt = mixreg.get("attempt", {})
                _append_unavailable(
                    rows, "MIXREG_NATIVE", "prediction", "P1=1,P2=2,T=175",
                    "mean", "UNSUPPORTED",
                    "Minitab MIXREG prediction storage unavailable: "
                    + (attempt.get("last_error") or attempt.get("output", "no stored value")),
                )
        elif (native_design.get("single_total_design")
              and native_x.shape[0] == 24
              and len(mixreg.get("row_keys", [])) == 24):
            local_by_key = {
                _key_label(_design_key(
                    [row["settings"][name] for name in "ABC"],
                    row["settings"]["P1"], row["settings"]["P2"], row["settings"]["T"],
                )): row
                for row in local_rows
            }
            if all(key in local_by_key for key in mixreg["row_keys"]):
                subset_x = np.asarray([
                    local_by_key[key]["matrix"] for key in mixreg["row_keys"]
                ], dtype=float)
                native_rank = int(np.linalg.matrix_rank(native_x))
                subset_rank = int(np.linalg.matrix_rank(subset_x))
                subset_error = _matrix_space_error(native_x, subset_x)
                _append_numeric(
                    rows, "MIXREG_NATIVE", "single_total_subset", "T=150",
                    "row_count", native_x.shape[0], subset_x.shape[0],
                    "Minitab MIXREG XMATRIX M1 from native 24-row SLDESIGN (DIRECT)",
                    "MiniJMP 15-column matrix restricted to T=150 (DIRECT)",
                )
                _append_numeric(
                    rows, "MIXREG_NATIVE", "single_total_subset", "T=150",
                    "rank", native_rank, subset_rank,
                    "Minitab MIXREG XMATRIX rank (DERIVED)",
                    "MiniJMP restricted matrix rank (DERIVED)",
                )
                _append_numeric(
                    rows, "MIXREG_NATIVE", "single_total_subset", "T=150",
                    "max_abs_projector_error", subset_error, 0.0,
                    "DERIVED: Minitab and MiniJMP single-total matrix spaces",
                    "Exact equality target",
                )
                _append_numeric(
                    rows, "MIXREG_NATIVE", "single_total_subset", "T=150",
                    "equivalent_subset_model_space",
                    int(native_rank == subset_rank and subset_error <= 1e-9), 1,
                    "DERIVED: Minitab MIXREG versus MiniJMP T=150 subdesign",
                    "MiniJMP restricted 15-column model space",
                )
            _append_unavailable(
                rows, "MIXREG_NATIVE", "model_space", "joint_v2",
                "full72_equivalent_15_term_model_space", "UNSUPPORTED",
                "Native MIXREG matrix was produced only for the 24-row single-TOTAL SLDESIGN subset; "
                "Minitab rejected the 72-row multiple-TOTAL PROC design",
            )
            amount_attempt = mixreg.get("amount_attempt", {})
            amount_error = (
                amount_attempt.get("last_error")
                or amount_attempt.get("output")
                or "no AMOUNT command error was captured"
            )
            _append_unavailable(
                rows, "MIXREG_NATIVE", "command", "joint_v2",
                "PROC_plus_AMOUNT", "UNSUPPORTED",
                f"Minitab MIXREG PROC+AMOUNT command evidence: {amount_error}",
            )
        else:
            _append_unavailable(
                rows, "MIXREG_NATIVE", "model_space", "joint_v2", "matrix_rows",
                "UNSUPPORTED", f"Minitab MIXREG XMATRIX row count is {native_x.shape[0]}",
            )
    else:
        attempt = mixreg.get("attempt", {})
        amount_attempt = mixreg.get("amount_attempt", {})
        reason = (
            mixreg.get("read_error")
            or amount_attempt.get("last_error")
            or amount_attempt.get("output")
            or attempt.get("last_error")
            or attempt.get("output")
            or "Minitab returned no readable MIXREG XMATRIX"
        )
        _append_unavailable(
            rows, "MIXREG_NATIVE", "model_space", "joint_v2",
            "equivalent_15_term_model_space", "UNSUPPORTED",
            f"Minitab MIXREG evidence: {reason}",
        )

    regress = minitab.get("regress", {})
    if regress.get("status") == "NOT_REQUIRED":
        _append_unavailable(
            rows, "REGRESS_EQUIVALENT", "fallback", "joint_v2", "execution",
            "N/A", regress.get("reason", "MIXREG was complete and equivalent"),
        )
    elif regress.get("matrix") is not None:
        native_x = np.asarray(regress["matrix"], dtype=float)
        local_x = np.asarray(local["matrix"], dtype=float)
        expected_fit = np.asarray([row["fit"] for row in local_rows], dtype=float)
        expected_residual = np.asarray([row["residual"] for row in local_rows], dtype=float)
        y = np.asarray([row["response"] for row in local_rows], dtype=float)
        _append_numeric(
            rows, "REGRESS_EQUIVALENT", "input", "joint_v2",
            "COM_input_matrix_max_abs_error", regress["input_matrix_max_abs_error"], 0.0,
            "Minitab worksheet SetData/GetData roundtrip (DIRECT)",
            "MiniJMP production API model matrix (DIRECT)",
        )
        _append_numeric(
            rows, "REGRESS_EQUIVALENT", "model", "joint_v2", "row_count",
            native_x.shape[0], local_x.shape[0],
            "Minitab REGRESS XMATRIX M1 (DIRECT)",
            "MiniJMP production API model matrix (DIRECT)",
        )
        _append_numeric(
            rows, "REGRESS_EQUIVALENT", "model", "joint_v2", "column_count",
            native_x.shape[1], local_x.shape[1],
            "Minitab REGRESS XMATRIX M1 (DIRECT)",
            "MiniJMP production API model matrix (DIRECT)",
        )
        rank = int(regress["rank"])
        _append_numeric(
            rows, "REGRESS_EQUIVALENT", "model", "joint_v2", "rank",
            rank, local["rank"],
            "Minitab REGRESS XMATRIX rank (DERIVED)",
            "MiniJMP analyze_mixture rank (DIRECT)",
        )
        if native_x.shape == local_x.shape:
            matrix_error = float(np.max(np.abs(native_x - local_x)))
            _append_numeric(
                rows, "REGRESS_EQUIVALENT", "model", "joint_v2",
                "matrix_max_abs_error", matrix_error, 0.0,
                "Minitab REGRESS XMATRIX M1 (DIRECT)",
                "MiniJMP production API model matrix (DIRECT)",
            )
            space_error = _matrix_space_error(native_x, local_x)
            _append_numeric(
                rows, "REGRESS_EQUIVALENT", "model_space", "joint_v2",
                "max_abs_projector_error", space_error, 0.0,
                "DERIVED: Minitab REGRESS and MiniJMP matrix column spaces",
                "Exact equality target",
            )
        else:
            _append_unavailable(
                rows, "REGRESS_EQUIVALENT", "model", "joint_v2",
                "matrix_max_abs_error", "FAIL",
                f"Minitab REGRESS matrix shape {native_x.shape} != MiniJMP {local_x.shape}",
            )
        coefficients = regress.get("coefficients", [])
        if len(coefficients) == 15:
            for index, term in enumerate(TERMS):
                _append_numeric(
                    rows, "REGRESS_EQUIVALENT", "coefficients", term, "coefficient",
                    coefficients[index], local["coefficients"][index],
                    "Minitab REGRESS COEFFICIENTS storage (DIRECT)",
                    "MiniJMP analyze_mixture coefficients (DIRECT)",
                )
        else:
            _append_unavailable(
                rows, "REGRESS_EQUIVALENT", "coefficients", "joint_v2",
                "15_coefficients", "UNSUPPORTED",
                f"Minitab REGRESS returned {len(coefficients)} coefficients",
            )
        fits = regress.get("fitted", [])
        residual_fit_minus_y = regress.get("residuals_fit_minus_y", [])
        if len(fits) == 72:
            for index in range(72):
                _append_numeric(
                    rows, "REGRESS_EQUIVALENT", "fit",
                    f"standard_order={index + 1}", "fitted",
                    fits[index], expected_fit[index],
                    "Minitab REGRESS FITS storage (DIRECT)",
                    "MiniJMP analyze_mixture fitted (DIRECT)",
                )
        else:
            _append_unavailable(
                rows, "REGRESS_EQUIVALENT", "fit", "joint_v2", "fitted_values",
                "UNSUPPORTED", f"Minitab REGRESS returned {len(fits)} fitted values",
            )
        if len(residual_fit_minus_y) == 72:
            for index in range(72):
                _append_numeric(
                    rows, "REGRESS_EQUIVALENT", "fit",
                    f"standard_order={index + 1}", "residual",
                    residual_fit_minus_y[index], expected_residual[index],
                    "Minitab REGRESS RESIDUALS storage observed-fit as read by COM (DIRECT)",
                    "MiniJMP analyze_mixture residuals y-fit (DIRECT)",
                )
            sse = float(np.dot(residual_fit_minus_y, residual_fit_minus_y))
        else:
            sse = None
            _append_unavailable(
                rows, "REGRESS_EQUIVALENT", "fit", "joint_v2", "residual_values",
                "UNSUPPORTED", f"Minitab REGRESS returned {len(residual_fit_minus_y)} residuals",
            )
        error_df = native_x.shape[0] - rank
        _append_numeric(
            rows, "REGRESS_EQUIVALENT", "anova", "joint_v2", "error_df",
            error_df, local["error_df"],
            "DERIVED: 72 rows minus Minitab REGRESS XMATRIX rank",
            "MiniJMP analyze_mixture residual df",
        )
        if sse is not None and native_x.shape == local_x.shape:
            _append_numeric(
                rows, "REGRESS_EQUIVALENT", "anova", "joint_v2", "SSE",
                sse, local["sse"],
                "DERIVED: Minitab REGRESS full-precision residual storage",
                "MiniJMP analyze_mixture SSE",
            )
            sst = float(np.sum((y - y.mean()) ** 2))
            ssr = sst - sse
            mse = sse / error_df if error_df else None
            r2 = 1 - sse / sst if sst else None
            adjusted = (
                1 - (sse / error_df) / (sst / (len(y) - 1))
                if error_df and sst and len(y) > 1 else None
            )
            for name, actual, expected in (
                ("SST_centered", sst, local["sst"]),
                ("SSR_centered", ssr, local["ssr"]),
                ("MSE", mse, local["sse"] / local["error_df"]),
                ("R2", r2, local["r2"]),
                ("adjusted_R2", adjusted, local["adjusted_r2"]),
                ("model_df_centered", rank - 1, local["model_df"]),
                ("total_df_centered", len(y) - 1, local["total_df"]),
            ):
                _append_numeric(
                    rows, "REGRESS_EQUIVALENT", "anova", "joint_v2", name,
                    actual, expected,
                    "DERIVED: Minitab REGRESS XMATRIX, FITS/RESIDUALS and fixed response",
                    "MiniJMP analyze_mixture summary",
                )
            local_anova = {item["term"]: item["ss"] for item in local["anova"]}
            for index, term in enumerate(TERMS):
                reduced = np.delete(native_x, index, axis=1)
                beta = np.linalg.lstsq(reduced, y, rcond=None)[0]
                reduced_residual = y - reduced @ beta
                term_ss = max(0.0, float(np.dot(reduced_residual, reduced_residual)) - sse)
                _append_numeric(
                    rows, "REGRESS_EQUIVALENT", "anova_terms", term, "partial_SS",
                    term_ss, local_anova[term],
                    "DERIVED: Minitab REGRESS matrix and fixed response, one-column deletion",
                    "MiniJMP analyze_mixture ANOVA term SS",
                )
                _append_unavailable(
                    rows, "REGRESS_EQUIVALENT", "anova_terms", term, "F_and_p",
                    "N/A", "MiniJMP inference is unavailable because the fixed design has no replicated pure-error df",
                    "MiniJMP analyze_mixture inference=None",
                )
            for statistic in ("model_F", "model_p"):
                _append_unavailable(
                    rows, "REGRESS_EQUIVALENT", "anova", "joint_v2", statistic,
                    "N/A", "MiniJMP analyze_mixture disables inferential statistics for this no-replicate fixture",
                    "MiniJMP analyze_mixture inference=None",
                )
        elif sse is not None:
            _append_unavailable(
                rows, "REGRESS_EQUIVALENT", "anova", "joint_v2",
                "full_precision_anova", "UNSUPPORTED",
                f"Minitab REGRESS matrix shape {native_x.shape} is not the expected 72×15",
            )
        else:
            _append_unavailable(
                rows, "REGRESS_EQUIVALENT", "anova", "joint_v2", "SSE",
                "UNSUPPORTED", "Minitab REGRESS residual storage was unavailable",
            )

        prediction_values = regress.get("prediction_values", [])
        if prediction_values:
            _append_numeric(
                rows, "REGRESS_EQUIVALENT", "prediction", "P1=1,P2=2,T=175",
                "mean", prediction_values[0], local["prediction"]["value"],
                "Minitab PREDICT PFITS storage (DIRECT)",
                "MiniJMP predict_mixture point prediction (DIRECT)",
            )
        elif len(coefficients) == 15:
            query = np.asarray([
                1 / 3, 1 / 3, 1 / 3, 1 / 9, 1 / 9, 1 / 9,
                -1 / 3, -1 / 3, -1 / 3, 1 / 3, 1 / 3, 1 / 3,
                1 / 6, 1 / 6, 1 / 6,
            ])
            derived = float(query @ np.asarray(coefficients, dtype=float))
            _append_numeric(
                rows, "REGRESS_EQUIVALENT", "prediction", "P1=1,P2=2,T=175",
                "mean", derived, local["prediction"]["value"],
                "DERIVED: Minitab REGRESS coefficients × target model row",
                "MiniJMP predict_mixture point prediction (DIRECT)",
            )
            attempt = regress.get("prediction_attempt", {})
            _append_unavailable(
                rows, "REGRESS_EQUIVALENT", "prediction", "P1=1,P2=2,T=175",
                "direct_PFITS_storage", "UNSUPPORTED",
                "Minitab PREDICT did not store PFITS: "
                + (attempt.get("last_error") or attempt.get("output", "no stored value")),
            )
        else:
            attempt = regress.get("prediction_attempt", {})
            _append_unavailable(
                rows, "REGRESS_EQUIVALENT", "prediction", "P1=1,P2=2,T=175",
                "mean", "UNSUPPORTED",
                "Minitab prediction unavailable and no complete coefficient vector: "
                + (attempt.get("last_error") or "REGRESS coefficients unavailable"),
            )
    else:
        attempt = regress.get("attempt", {})
        reason = (
            regress.get("read_error")
            or attempt.get("last_error")
            or attempt.get("output")
            or regress.get("reason", "REGRESS was not executed")
        )
        _append_unavailable(
            rows, "REGRESS_EQUIVALENT", "model", "joint_v2",
            "15_column_model", "UNSUPPORTED",
            f"Minitab REGRESS evidence: {reason}",
        )

    return rows


def _comparison_summary(rows):
    summary = {}
    for row in rows:
        summary.setdefault(row["case_id"], {"PASS": 0, "FAIL": 0, "N/A": 0, "UNSUPPORTED": 0})
        summary[row["case_id"]][row["status"]] += 1
    maxima = {}
    for case_id in summary:
        numeric = [
            row for row in rows
            if row["case_id"] == case_id and row.get("absolute_error") not in (None, "")
        ]
        maxima[case_id] = max(
            numeric, key=lambda row: float(row["absolute_error"]), default=None)
    return summary, maxima


def _write_report(minijmp, minitab, comparisons):
    import numpy as np

    local = minijmp["production_api_actual"]
    fixture = minijmp["fixture_expectation"]
    sldesign = minitab.get("sldesign", {})
    mixreg = minitab.get("mixreg", {})
    regress = minitab.get("regress", {})
    counts, maxima = _comparison_summary(comparisons)

    def count_line(case_id):
        values = counts.get(case_id, {})
        return ", ".join(f"{name} {values.get(name, 0)}"
                         for name in ("PASS", "FAIL", "N/A", "UNSUPPORTED"))

    def max_line(case_id):
        row = maxima.get(case_id)
        if not row:
            return "无可计算的数值误差"
        return (f"{float(row['absolute_error']):.17g}，"
                f"{row['section']}/{row['term']}/{row['statistic']}")

    native_space = next((
        row for row in comparisons
        if row["case_id"] == "MIXREG_NATIVE"
        and row["statistic"] == "equivalent_15_term_model_space"
    ), None)
    mixreg_equivalent = native_space is not None and native_space["status"] == "PASS"
    regress_required = regress.get("status") != "NOT_REQUIRED"
    regress_issues = [
        row for row in comparisons
        if row["case_id"] == "REGRESS_EQUIVALENT"
        and (row["status"] == "FAIL"
             or (row["status"] == "UNSUPPORTED"
                 and row["statistic"] != "direct_PFITS_storage"))
    ]
    regress_complete = not regress_required or (
        regress.get("status") == "DIRECT" and not regress_issues
    )
    api_fail = any(
        row["case_id"] == "MINIJMP_FIXTURE" and row["status"] == "FAIL"
        for row in comparisons
    )
    design_fail = any(
        row["case_id"] == "SLDESIGN" and row["status"] == "FAIL"
        for row in comparisons
    )
    sldesign_assessed = (
        sldesign.get("status") == "PASS"
        or sldesign.get("single_total_status") == "PASS"
    ) and not design_fail
    process_ok = (
        minitab.get("owned_process_exited") is True
        and minitab.get("preexisting_pids_preserved") is True
    )
    process_history_uncertain = (
        OUT / "mixture_v2_process_lifecycle_observation.md"
    ).is_file()
    overall = (
        "PASS" if sldesign_assessed and not api_fail and regress_complete
        and process_ok and not process_history_uncertain
        else "PARTIAL"
    )
    if mixreg_equivalent:
        mixreg_text = "PASS：MIXREG 完整输出模型空间与 MiniJMP 15 列空间等价。"
    elif mixreg.get("matrix") and mixreg.get("n") == 72:
        mixreg_text = "FAIL：MIXREG XMATRIX 模型空间与 MiniJMP 15 列空间不等价。"
    elif mixreg.get("matrix"):
        mixreg_text = "UNSUPPORTED：MIXREG 仅取得单总量24行子集，无法代表完整72行模型空间。"
    else:
        mix_attempt = mixreg.get("attempt", {})
        mixreg_text = (
            "UNSUPPORTED：在单总量24行 SLDESIGN 上运行的 MIXREG 未能生成可读 XMATRIX；"
            + (mix_attempt.get("last_error") or "详见原始输出。")
        )
    regress_text = (
        "未执行：MIXREG 输出完整且模型空间等价。"
        if not regress_required else
        ("PASS：REGRESS 显式15列等价模型比较通过。"
         if regress_complete else "PARTIAL：REGRESS 有未通过或未提取项。")
    )
    mix_attempt = mixreg.get("attempt", {})
    amount_attempt = mixreg.get("amount_attempt", mix_attempt)
    sld_attempt = sldesign.get("attempt", {})
    reg_attempt = regress.get("attempt", {})
    regression_command = "REGRESS" if regress_required else "MIXREG"
    mix_rank = int(np.linalg.matrix_rank(mixreg["matrix"])) if mixreg.get("matrix") else "N/A"
    mixreg_subset_error = next((
        float(row["minitab_value"]) for row in comparisons
        if row["case_id"] == "MIXREG_NATIVE"
        and row["statistic"] == "max_abs_projector_error"
    ), None)
    amount_error = amount_attempt.get("last_error") or amount_attempt.get("output", "")
    amount_error_line = next((
        line.strip() for line in amount_error.splitlines()
        if "* 错误 *" in line or "* ERROR *" in line
    ), "未返回错误文本")
    prediction_attempt = regress.get("prediction_attempt", {})
    prediction_error = prediction_attempt.get("last_error") or prediction_attempt.get("output", "")
    prediction_error_line = next((
        line.strip() for line in prediction_error.splitlines()
        if "* 错误 *" in line or "* ERROR *" in line
    ), "未返回错误文本")
    report = [
        "# Mixture v2 固定72行联合案例：Minitab 19.1.0.1 数值对标",
        "",
        f"验收结论：{overall}",
        "",
        "## 两条模型证据",
        "",
        f"- MIXREG 原生 DOE 对标：{mixreg_text}",
        f"- REGRESS 等价模型对标：{regress_text}",
        f"- SLDESIGN 设计对标：{'PASS：72行' if sldesign.get('status') == 'PASS' else ('72行 UNSUPPORTED；T=150 的24行子集 ' + sldesign.get('single_total_status', '未取得')) if sldesign.get('single_total_status') else 'FAIL/UNSUPPORTED'}。",
        "",
        "## 夹具期望与本轮 MiniJMP 生产 API 实得",
        "",
        "|指标|独立夹具期望|本轮 API 实得|状态|",
        "|---|---:|---:|---|",
    ]
    for name, actual, expected in (
        ("行数 n", local["n"], fixture["n"]),
        ("矩阵列数 p", local["p"], fixture["p"]),
        ("矩阵秩", local["rank"], fixture["rank"]),
        ("残差自由度", local["error_df"], fixture["residual_df"]),
        ("SSE", local["sse"], fixture["sse"]),
        ("指定点预测", local["prediction"]["value"], fixture["prediction"]),
    ):
        status = ("PASS" if math.isclose(
            float(actual), float(expected), rel_tol=1e-9, abs_tol=1e-9) else "FAIL")
        report.append(f"|{name}|{expected:.17g}|{actual:.17g}|{status}|")
    report.extend([
        "",
        f"- 本轮模型项：{', '.join(local['terms'])}。",
        f"- 独立冻结矩阵与 API 实算矩阵最大绝对误差：{local['fixture_matrix_max_abs_error']:.17g}。",
        f"- 本轮 API 系数：{', '.join(format(value, '.17g') for value in local['coefficients'])}。",
        "- API 实算值与夹具期望分列保存在 mixture_v2_minijmp_results.json。",
        "",
        "## Minitab 原生产品证据",
        "",
        f"- 版本：{minitab.get('version')}；AppPath：{minitab.get('app_path')}；"
        f"进程映像：{minitab.get('process_path')}；独立 PID：{minitab.get('pid')}。",
        f"- DispatchEx 前已有 PID：{minitab.get('existing_pids_at_start', [])}；"
        f"worker 退出后 PID：{minitab.get('existing_pids_after_worker_exit', [])}；"
        f"独立进程已退出：{minitab.get('owned_process_exited')}；"
        f"原有 PID 保留：{minitab.get('preexisting_pids_preserved')}。",
        "- 另一次执行观察到既有 PID 34528 在 worker 结束后消失；没有连接该 PID 的 COM 对象，原因不明，见 mixture_v2_process_lifecycle_observation.md。",
        f"- 多总量 SLDESIGN command object：{sld_attempt.get('command_object_created')}；"
        f"状态：{sldesign.get('status')}；单总量子集状态："
        f"{sldesign.get('single_total_status', '未运行')}；"
        f"子集行数：{len(sldesign.get('single_total_design', {}).get('rows', []))}；"
        f"工作表列：{', '.join(sldesign.get('single_total_design', {}).get('columns', sldesign.get('columns', [])))}。",
        "- TOTAL 100/150/200 常数形式与 TOTAL 列形式均返回“不能有多个含过程变量的混合合计”；"
        "单总量基础设计的实际组分总和映射为 T=150。",
        f"- MIXREG command object：{mix_attempt.get('command_object_created')}；"
        f"错误标记：{mix_attempt.get('error_marker')}；"
        f"XMATRIX：{mixreg.get('n', 'N/A')}×{mixreg.get('p', 'N/A')}；秩：{mix_rank}；"
        f"T=150 子集列空间最大投影误差：{mixreg_subset_error if mixreg_subset_error is not None else 'N/A'}。",
        "- MIXREG 无 AMOUNT 项表含 A/B/C、AB/AC/BC 与 A/B/C×X1/X2；24×12 秩12矩阵"
        "与 MiniJMP 的 T=150 子集同空间。",
        f"- MIXREG 预测存储：{mixreg.get('prediction_values', 'N/A')}。",
        f"- MIXREG PROC+AMOUNT 首次尝试：{amount_attempt.get('command_object_created')}；"
        f"错误：{amount_error_line}。",
        f"- {regression_command} command object：{reg_attempt.get('command_object_created')}；"
        f"模型矩阵：{regress.get('n', 'N/A')}×{regress.get('p', 'N/A')}；"
        f"秩：{regress.get('rank', 'N/A')}；COM 输入列回读误差："
        f"{regress.get('input_matrix_max_abs_error', 'N/A')}。",
        f"- 指定点预测的高精度系数点积为 {local['prediction']['value']:.17g}；"
        f"直接 PREDICT/PFITS 未存储，Minitab 返回：{prediction_error_line}。",
        "",
        "## 本机 Session Commands 手册核对",
        "",
        "- SLDESIGN：印刷页 374–376；PROC、LEVELS、TOTAL、DESIGN。",
        "- MIXREG：印刷页 377–381；PROC 指定过程列，AMOUNT 指定总量列且禁止将 AMOUNT 列列入项表；实际项矩阵以本轮 XMATRIX 为准。",
        "- REGRESS：印刷页 170–178；NOCONSTANT、CONTINUOUS、TERMS、COEFFICIENTS、FITS、RESIDUALS、XMATRIX。",
        "- 残差方向：手册印刷页 177 写作拟合值−观测值；本机 COM 的 REGRESS RESIDUALS 实存值与观测值−拟合值一致，比较按本机全精度读回。",
        "- PREDICT：印刷页 1183–1186；尝试 multiple_regression|1、KPREDICTORS、PFITS。",
        "- 手册文本：C:\\Users\\shaoy\\AppData\\Local\\Temp\\minitab19_session_commands.pdf.txt。",
        "",
        "## 数值比较状态",
        "",
        "- 容差：abs_tol=1e-9，rel_tol=1e-9。",
        f"- MiniJMP API / 独立夹具：{count_line('MINIJMP_FIXTURE')}；最大绝对误差：{max_line('MINIJMP_FIXTURE')}。",
        f"- SLDESIGN 点集/设定：{count_line('SLDESIGN')}；最大绝对误差：{max_line('SLDESIGN')}。",
        f"- MIXREG 原生模型空间：{count_line('MIXREG_NATIVE')}；最大绝对误差：{max_line('MIXREG_NATIVE')}。",
        f"- REGRESS 等价模型：{count_line('REGRESS_EQUIVALENT')}；最大绝对误差：{max_line('REGRESS_EQUIVALENT')}。",
        "- CSV 逐项列出 PASS/FAIL/N/A/UNSUPPORTED、DIRECT/DERIVED/DISPLAY 来源和误差；"
        "Minitab 原始输出及高精度 COM 读回值分别保存在 raw log 与 JSON。",
        "",
        "## ANOVA 与统计推断边界",
        "",
        f"- MiniJMP 实得 pure-error df={local['pure_error_df']}，"
        f"pure-error SSE={local['pure_error_sse']:.17g}；推断状态：{local['inference_status']}。",
        f"- 比较 CSV 含从 Minitab 全精度 {regression_command} 矩阵和响应派生的居中 SST/SSR、"
        "MSE、R²、调整 R²、模型/误差自由度及逐项删除平方和；"
        f"原生 {regression_command} ANOVA 显示表保存在 raw log。",
        "- MiniJMP 的 F/p 不可用时记为 N/A；Minitab 舍入显示值不作为唯一高精度证据。",
        "",
        "## 证据文件",
        "",
        "- verify_mixture_extended.py：单案例脚本。",
        "- mixture_v2_joint_input.csv：72行固定因素/响应及15列生产 API 矩阵。",
        "- mixture_v2_session_commands.txt：实际提交给 COM 的命令。",
        "- mixture_v2_minitab_raw_output.txt：OutputDocument/Outputs、LastError、实际命令及原始记录。",
        "- mixture_v2_minijmp_results.json、mixture_v2_minitab_results.json：双方全精度数据。",
        "- mixture_v2_comparison.csv：逐项数值结果。",
        "- mixture_v2_acceptance_report.md：本报告。",
        "",
        "范围仅含本固定 Mixture v2 联合案例；未改生产代码、冻结八案例、DOE 矩阵或依赖；未运行全仓库 pytest。",
    ])
    REPORT.write_text("\n".join(report) + "\n", encoding="utf-8")


def _run_worker(mode, timeout=420):
    if not PROJECT_PYTHON.is_file():
        raise FileNotFoundError(f"项目解释器不存在: {PROJECT_PYTHON}")
    return subprocess.run(
        [str(PROJECT_PYTHON), "-X", "utf8", str(Path(__file__).resolve()), mode],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=timeout,
    )


def main() -> int:
    if Path(sys.executable).resolve() != PROJECT_PYTHON.resolve():
        raise RuntimeError(f"请使用项目解释器运行: {PROJECT_PYTHON}")
    existing_pids = running_minitab_pids()
    if existing_pids:
        print(
            f"检测到已有 Minitab 进程 PID={existing_pids}；本次未启动任何 worker。",
            file=sys.stderr, flush=True,
        )
        return 1
    OUT.mkdir(parents=True, exist_ok=True)
    local_process = _run_worker("--minijmp-worker", timeout=240)
    if local_process.stdout.strip():
        print(local_process.stdout.rstrip(), flush=True)
    if local_process.stderr.strip():
        print("MiniJMP worker stderr:\n" + local_process.stderr.rstrip(), flush=True)
    if local_process.returncode:
        raise RuntimeError(f"MiniJMP worker 退出码 {local_process.returncode}")

    mtb_before = running_minitab_pids()
    com_process = _run_worker("--com-worker", timeout=420)
    if com_process.stdout.strip():
        print(com_process.stdout.rstrip(), flush=True)
    if com_process.stderr.strip():
        print("Minitab COM worker stderr:\n" + com_process.stderr.rstrip(), flush=True)
    minitab = json.loads(MINITAB.read_text(encoding="utf-8")) if MINITAB.exists() else {}
    owned_pid = minitab.get("pid")
    deadline = time.monotonic() + 20
    pids_after = running_minitab_pids()
    while owned_pid and owned_pid in pids_after and time.monotonic() < deadline:
        time.sleep(0.25)
        pids_after = running_minitab_pids()
    minitab["existing_pids_after_worker_exit"] = pids_after
    minitab["owned_process_exited"] = bool(
        owned_pid is not None and owned_pid not in pids_after)
    minitab["preexisting_pids_preserved"] = all(
        pid in pids_after for pid in mtb_before)
    write_json(MINITAB, minitab)

    minijmp = json.loads(MINIJMP.read_text(encoding="utf-8"))
    comparisons = _compare_minitab(minijmp, minitab)
    write_comparison(COMPARISON, comparisons)
    _write_report(minijmp, minitab, comparisons)
    summary, _ = _comparison_summary(comparisons)
    print(f"对标状态：{summary}", flush=True)
    print(
        f"Minitab process cleanup: owned PID {owned_pid} exited="
        f"{minitab['owned_process_exited']}; preexisting PIDs preserved="
        f"{minitab['preexisting_pids_preserved']}",
        flush=True,
    )
    if com_process.returncode:
        return 1
    mixreg_eq = any(
        row["case_id"] == "MIXREG_NATIVE"
        and row["statistic"] == "equivalent_15_term_model_space"
        and row["status"] == "PASS"
        for row in comparisons
    )
    regress = minitab.get("regress", {})
    regress_issue = any(
        row["case_id"] == "REGRESS_EQUIVALENT"
        and (row["status"] == "FAIL"
             or (row["status"] == "UNSUPPORTED"
                 and row["statistic"] != "direct_PFITS_storage"))
        for row in comparisons
    )
    regress_ok = mixreg_eq or (regress.get("status") == "DIRECT" and not regress_issue)
    api_fail = any(
        row["case_id"] == "MINIJMP_FIXTURE" and row["status"] == "FAIL"
        for row in comparisons
    )
    design_fail = any(
        row["case_id"] == "SLDESIGN" and row["status"] == "FAIL"
        for row in comparisons
    )
    sldesign_ok = (
        minitab.get("sldesign", {}).get("status") == "PASS"
        or minitab.get("sldesign", {}).get("single_total_status") == "PASS"
    )
    process_history_uncertain = (
        OUT / "mixture_v2_process_lifecycle_observation.md"
    ).is_file()
    if (not sldesign_ok or design_fail or api_fail or process_history_uncertain
            or not regress_ok or not minitab["owned_process_exited"]
            or not minitab["preexisting_pids_preserved"]):
        return 1
    return 0


if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1] == "--minijmp-worker":
        try:
            run_minijmp_worker()
        except Exception:
            traceback.print_exc()
            raise SystemExit(1)
        raise SystemExit(0)
    if len(sys.argv) == 2 and sys.argv[1] == "--com-worker":
        try:
            minitab_worker()
        except Exception:
            traceback.print_exc()
            raise SystemExit(1)
        raise SystemExit(0)
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception:
        traceback.print_exc()
        raise SystemExit(1)
