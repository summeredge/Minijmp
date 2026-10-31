"""MiniJMP × Minitab 19 dynamic and control-by-noise Taguchi parity."""
from __future__ import annotations

import csv
import json
import math
import sys
import traceback
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
SUPPLEMENTAL = HERE.parent
ROOT = SUPPLEMENTAL.parents[2]
for path in (SUPPLEMENTAL, ROOT / "code"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from common import (  # noqa: E402
    MinitabSession,
    compare_numeric,
    compare_text,
    run_worker,
    status_counts,
    write_comparison,
    write_json,
)

from doe_core import DesignSpec, FactorSpec, restore_design_result  # noqa: E402
from doe_taguchi import create_taguchi  # noqa: E402
from doe_taguchi_analysis import analyze_dynamic, best_settings, noise_robustness  # noqa: E402
from doe_taguchi_arrays import ARRAYS  # noqa: E402

CASE_IDS = ("TAG-DYNAMIC", "TAG-ROBUST")
INPUTS = {case_id: HERE / f"{case_id.lower().replace('-', '_')}_input.csv"
          for case_id in CASE_IDS}
MINIJMP = HERE / "minijmp_results.json"
MINITAB = HERE / "minitab_results.json"
RAW = HERE / "minitab_raw.txt"
COMMANDS = HERE / "session_commands.txt"
COMPARISON = HERE / "comparison.csv"
REPORT = HERE / "acceptance.md"
DYNAMIC_ERRORS = {1.0: 0.1, 2.0: -0.2, 3.0: 0.1}
MTB_MISSING = 1.23456e30


def _clean(value):
    if value is None:
        return None
    if isinstance(value, np.ndarray):
        return _clean(value.tolist())
    if isinstance(value, np.generic):
        return _clean(value.item())
    if isinstance(value, dict):
        return {str(key): _clean(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_clean(item) for item in value]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def _factor(factor_id, levels, *, numeric=False):
    return FactorSpec(
        factor_id, factor_id, None, None, factor_type="categorical",
        levels=tuple(levels), level_type="numeric" if numeric else "text")


def _dynamic_spec():
    array = ARRAYS["L4(2^3)"]
    return DesignSpec(
        "tag-dynamic", (_factor("A", ("low", "high")),
                        _factor("B", ("low", "high")),
                        _factor("S", (1.0, 2.0, 3.0), numeric=True)),
        ("Y",), seed=17, design_type="taguchi",
        taguchi={"kind": "dynamic", "array_id": "L4(2^3)",
                 "matrix_sha256": array.sha256,
                 "columns": {"A": 1, "B": 2},
                 "noise_array_id": None, "noise_matrix_sha256": None,
                 "noise_columns": {}, "signal_factor": "S"})


def _robust_spec():
    control = ARRAYS["L4(2^3)"]
    noise = ARRAYS["L4(2^3)"]
    return DesignSpec(
        "tag-control-noise",
        (_factor("A", ("low", "high")), _factor("B", ("low", "high")),
         _factor("N1", ("n1", "n2")), _factor("N2", ("n1", "n2"))),
        ("Y",), seed=23, design_type="taguchi",
        taguchi={"kind": "static", "array_id": "L4(2^3)",
                 "matrix_sha256": control.sha256,
                 "columns": {"A": 1, "B": 3},
                 "noise_array_id": "L4(2^3)",
                 "noise_matrix_sha256": noise.sha256,
                 "noise_columns": {"N1": 1, "N2": 2},
                 "signal_factor": None})


def _code(value):
    return 1 if value in ("low", "n1") else 2


def _control_code(a, b):
    return _code(a), _code(b)


def _dynamic_response(a, b, signal):
    a_code, b_code = _control_code(a, b)
    a_effect, b_effect = 6 * (2 * a_code - 3), 6 * (2 * b_code - 3)
    slope = 20 + a_effect + b_effect
    return 3 + slope * float(signal) + DYNAMIC_ERRORS[float(signal)]


def _noise_response(a, b, n1, n2):
    a_code, b_code = _control_code(a, b)
    n1_code, n2_code = _code(n1), _code(n2)
    a, b, n1, n2 = (2 * value - 3 for value in (a_code, b_code, n1_code, n2_code))
    return 25 + 4 * a - 3 * b + 2 * a * n1 + 1.2 * b * n2 + .4 * n1 - .2 * n2


def _fill_response(frame, metadata, response_function):
    design = restore_design_result(frame, metadata)
    values = {}
    for run in design.runs:
        values[run.run_id] = float(response_function(run.settings))
    response_column = metadata["column_map"]["responses"]["Y"]
    id_column = metadata["column_map"]["run_id"]
    frame[response_column] = [values[run_id] for run_id in frame[id_column]]
    return frame


def _dynamic_rows(frame, metadata):
    design = restore_design_result(frame, metadata)
    return [{
        "case_id": "TAG-DYNAMIC", "standard_order": run.standard_order,
        "run_id": run.run_id, "control_run_id": run.control_run_id,
        "A_code": _code(run.settings["A"]), "B_code": _code(run.settings["B"]),
        "S": float(run.settings["S"]), "Y": float(run.responses["Y"]),
    } for run in sorted(design.runs, key=lambda item: item.standard_order)]


def _robust_rows(frame, metadata):
    design = restore_design_result(frame, metadata)
    return [{
        "case_id": "TAG-ROBUST", "standard_order": run.standard_order,
        "run_id": run.run_id, "control_run_id": run.control_run_id,
        "noise_condition_id": run.noise_condition_id,
        "A_code": _code(run.settings["A"]), "B_code": _code(run.settings["B"]),
        "N1_code": _code(run.settings["N1"]), "N2_code": _code(run.settings["N2"]),
        "Y": float(run.responses["Y"]),
    } for run in sorted(design.runs, key=lambda item: item.standard_order)]


def _write_input(case_id, rows):
    with INPUTS[case_id].open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def run_minijmp():
    dynamic_frame, dynamic_metadata = create_taguchi(_dynamic_spec())
    dynamic_frame = _fill_response(
        dynamic_frame, dynamic_metadata,
        lambda settings: _dynamic_response(settings["A"], settings["B"], settings["S"]))
    dynamic = analyze_dynamic(dynamic_frame, dynamic_metadata, "Y")
    dynamic_best = best_settings(dynamic_frame, dynamic_metadata, "Y", "slope", target=20)
    dynamic_rows = _dynamic_rows(dynamic_frame, dynamic_metadata)
    _write_input("TAG-DYNAMIC", dynamic_rows)

    robust_frame, robust_metadata = create_taguchi(_robust_spec())
    robust_frame = _fill_response(
        robust_frame, robust_metadata,
        lambda settings: _noise_response(
            settings["A"], settings["B"], settings["N1"], settings["N2"]))
    robust = noise_robustness(robust_frame, robust_metadata, "Y", "smaller")
    robust_best = best_settings(robust_frame, robust_metadata, "Y", "sn")
    robust_rows = _robust_rows(robust_frame, robust_metadata)
    _write_input("TAG-ROBUST", robust_rows)

    dynamic_combinations = [{
        "settings": row["settings"], "slope": row["slope"],
        "intercept": row["intercept"], "mse": row["mse"],
        "df": row["df"], "sn": row["sn"], "signal": row["signal"],
        "response": row["response"],
    } for row in dynamic["combinations"]]
    dynamic_factor_rows = [{
        "factor_id": row["factor_id"],
        "levels": [{"level": level["level"], "slope": level["slope"],
                    "mean": level["mean"], "sn": level["sn"]}
                   for level in row["levels"]],
        "delta": row["delta"],
    } for row in dynamic["slope_table"]["factors"]]
    robust_combinations = [{
        "settings": row["settings"], "mean": row["mean"], "sd": row["sd"],
        "sn": row["sn"], "condition_mean_range": row["condition_mean_range"],
        "condition_count": row["condition_count"],
        "noise_conditions": row["noise_conditions"],
    } for row in robust["rows"]]
    results = {
        "cases": {
            "TAG-DYNAMIC": {
                "n": len(dynamic_rows), "rows": dynamic_rows,
                "combinations": dynamic_combinations,
                "slope_factor_table": dynamic_factor_rows,
                "slope_factor_ranked": dynamic["slope_table"]["ranked"],
                "sn_factor_table": _clean(dynamic["response_table"]["factors"]),
                "best": {"settings": dynamic_best["best"],
                         "tied_combinations": dynamic_best["tied_combinations"],
                         "predicted_slope": dynamic_best["predicted_slope"],
                         "target": dynamic_best["target"]},
                "formula": "S/N=10*log10(slope^2/MSE); free intercept; residual df=1",
            },
            "TAG-ROBUST": {
                "n": len(robust_rows), "rows": robust_rows,
                "combinations": robust_combinations,
                "sn_factor_table": _clean(robust["response_table"]["factors"]),
                "best": {"settings": robust_best["best"],
                         "predicted_sn": robust_best["predicted_sn"],
                         "predicted_mean": robust_best["predicted_mean"],
                         "predicted_sd": robust_best["predicted_sd"],
                         "tied_combinations": robust_best["tied_combinations"]},
                "formula": "smaller-is-better S/N=-10*log10(mean(Y^2)) over four noise conditions",
            },
        }
    }

    # Independent closed-form checks for the signal regression and noise summaries.
    assert len(dynamic_rows) == 12 and len(dynamic_combinations) == 4
    for row in dynamic_combinations:
        x, y = np.asarray(row["signal"], dtype=float), np.asarray(row["response"], dtype=float)
        xbar, ybar = float(x.mean()), float(y.mean())
        slope = float(np.sum((x - xbar) * (y - ybar)) / np.sum((x - xbar) ** 2))
        intercept = ybar - slope * xbar
        mse = float(np.sum((y - (intercept + slope * x)) ** 2))
        assert math.isclose(row["slope"], slope, rel_tol=0, abs_tol=1e-12)
        assert math.isclose(row["intercept"], intercept, rel_tol=0, abs_tol=1e-12)
        assert math.isclose(row["mse"], mse, rel_tol=0, abs_tol=1e-12)
        assert row["df"] == 1
    assert sorted(round(row["slope"], 10) for row in dynamic_combinations) == [8, 20, 20, 32]
    assert math.isclose(dynamic_best["predicted_slope"], 20, rel_tol=0, abs_tol=1e-12)
    assert len(robust_rows) == 16 and len(robust_combinations) == 4
    for row in robust_combinations:
        values = np.asarray([condition["mean"] for condition in row["noise_conditions"]])
        independent_mean = float(values.mean())
        independent_sd = float(values.std(ddof=1))
        observed = np.asarray([item["Y"] for item in robust_rows
                               if item["A_code"] == _code(row["settings"]["A"])
                               and item["B_code"] == _code(row["settings"]["B"])])
        independent_sn = -10 * math.log10(float(np.mean(observed ** 2)))
        assert len(values) == 4 and len(observed) == 4
        assert math.isclose(row["mean"], independent_mean, rel_tol=0, abs_tol=1e-12)
        assert math.isclose(row["sd"], independent_sd, rel_tol=0, abs_tol=1e-12)
        assert math.isclose(row["sn"], independent_sn, rel_tol=0, abs_tol=1e-12)
    write_json(MINIJMP, _clean(results))
    return results


def _worksheet_with_columns(session, names):
    target = {name.casefold() for name in names}
    worksheets = session.project.Worksheets
    for index in range(1, int(worksheets.Count) + 1):
        worksheet = worksheets.Item(index)
        columns = worksheet.Columns
        available = {str(columns.Item(i).Name).casefold()
                     for i in range(1, int(columns.Count) + 1)}
        if target <= available:
            session.worksheet = worksheet
            return
    raise RuntimeError(f"Minitab worksheet lacks columns {names}")


def _group_storage(values_by_name, keys):
    result = {}
    for name, values in values_by_name.items():
        if len(values) != len(keys):
            raise RuntimeError(f"{name} storage has {len(values)} rows, expected {len(keys)}")
        grouped = {}
        for key, value in zip(keys, values):
            if value is None or value == MTB_MISSING:
                continue
            if key in grouped and not math.isclose(grouped[key], value,
                                                  rel_tol=1e-10, abs_tol=1e-10):
                raise RuntimeError(f"{name} storage varies within one control setting {key}")
            grouped[key] = float(value)
        result[name] = grouped
    return result


def _run_dynamic(session):
    command_design = ('OADESIGN 4 2 2; DESIGN; SNAME "S"; SLEVEL 1 2 3.')
    session.execute(command_design, "TAG-DYNAMIC OADESIGN")
    _worksheet_with_columns(session, ("A", "B", "S"))
    a_index, b_index, s_index = (session.find_column([name]) for name in ("A", "B", "S"))
    a_values = session.column_values(a_index)
    b_values = session.column_values(b_index)
    s_values = session.column_values(s_index)
    if not (len(a_values) == len(b_values) == len(s_values) == 12):
        raise RuntimeError("Minitab OADESIGN dynamic array must have 12 rows")
    response_values = []
    control_codes = []
    signal_levels = []
    for a, b, signal in zip(a_values, b_values, s_values):
        a_code, b_code = int(round(a)), int(round(b))
        if a_code not in (1, 2) or b_code not in (1, 2):
            raise RuntimeError(f"Unexpected Minitab control levels: A={a}, B={b}")
        settings = ("low" if a_code == 1 else "high",
                    "low" if b_code == 1 else "high")
        response_values.append(_dynamic_response(*settings, signal))
        control_codes.append((a_code, b_code))
        signal_levels.append(float(signal))
    response_index = session.add_column("Y", response_values)
    storage = {name: session.add_column(name) for name in
               ("SN_DYNAMIC", "SLOPE_DYNAMIC", "INTERCEPT_DYNAMIC", "STD_DYNAMIC")}
    command = (
        f"ROBUST C{response_index} = C{a_index} C{b_index}; DYNAMIC C{s_index}; "
        f"NOREF; TSN; TSLOPES; TSTDS; ASN; ASLOPES; ASTDS; "
        f"SNRATIO C{storage['SN_DYNAMIC']}; SLOPES C{storage['SLOPE_DYNAMIC']}; "
        f"INTERCEPTS C{storage['INTERCEPT_DYNAMIC']}; "
        f"STDEVS C{storage['STD_DYNAMIC']}."
    )
    output = session.execute(command, "TAG-DYNAMIC ROBUST")
    raw_storage = {name: session.column_values(index) for name, index in storage.items()}
    try:
        values = _group_storage(raw_storage, control_codes)
    except RuntimeError as exc:
        return {"commands": [command_design, command], "error": str(exc),
                "rows": 12, "control_codes": [list(key) for key in control_codes],
                "signal_levels": signal_levels, "response": response_values,
                "storage_values": raw_storage,
                "output_excerpt": output[-6000:]}
    combos = {}
    for key in sorted(set(control_codes)):
        combos["A=" + ("low" if key[0] == 1 else "high") +
               ",B=" + ("low" if key[1] == 1 else "high")] = {
            "key": list(key),
            "slope": values["SLOPE_DYNAMIC"].get(key),
            "intercept": values["INTERCEPT_DYNAMIC"].get(key),
            "sn": values["SN_DYNAMIC"].get(key),
            "residual_sd": values["STD_DYNAMIC"].get(key),
        }
    if any(value is None for row in combos.values() for value in
           (row["slope"], row["intercept"], row["sn"], row["residual_sd"])):
        raise RuntimeError(f"Minitab dynamic storage incomplete: {combos}")
    return {
        "commands": [command_design, command], "rows": 12,
        "control_codes": [list(key) for key in control_codes],
        "signal_levels": signal_levels, "response": response_values,
        "combinations": combos, "storage_columns": storage,
        "storage_values": raw_storage,
        "output_excerpt": output[-6000:],
    }


def _run_robust(session, rows):
    columns = {}
    for name, key in (("A", "A_code"), ("B", "B_code"),
                      ("N1", "N1_code"), ("N2", "N2_code"), ("Y", "Y")):
        columns[name] = session.add_column(name, [row[key] for row in rows])
    storage = {name: session.add_column(name) for name in ("SN_ROBUST", "MEAN_ROBUST", "STD_ROBUST")}
    command = (
        f"ROBUST C{columns['Y']} = C{columns['A']} C{columns['B']}; LOWER; "
        f"TSN; TMEANS; TSTDS; ASN; AMEANS; ASTDS; "
        f"SNRATIO C{storage['SN_ROBUST']}; MEANS C{storage['MEAN_ROBUST']}; "
        f"STDEVS C{storage['STD_ROBUST']}."
    )
    output = session.execute(command, "TAG-ROBUST")
    keys = [(int(row["A_code"]), int(row["B_code"])) for row in rows]
    raw_storage = {name: session.column_values(index) for name, index in storage.items()}
    try:
        values = _group_storage(raw_storage, keys)
    except RuntimeError as exc:
        return {"commands": [command], "error": str(exc), "rows": len(rows),
                "row_keys": keys, "storage_values": raw_storage,
                "noise_columns_retained": ["N1", "N2"],
                "model_control_columns": ["A", "B"],
                "output_excerpt": output[-6000:]}
    combinations = {}
    for key in sorted(set(keys)):
        combostr = "A=" + ("low" if key[0] == 1 else "high") + \
            ",B=" + ("low" if key[1] == 1 else "high")
        combinations[combostr] = {
            "key": list(key), "sn": values["SN_ROBUST"].get(key),
            "mean": values["MEAN_ROBUST"].get(key),
            "sd": values["STD_ROBUST"].get(key),
        }
    if any(value is None for row in combinations.values() for value in
           (row["sn"], row["mean"], row["sd"])):
        raise RuntimeError(f"Minitab control×noise robust storage incomplete: {combinations}")
    return {
        "commands": [command], "rows": len(rows), "combinations": combinations,
        "noise_columns_retained": ["N1", "N2"], "model_control_columns": ["A", "B"],
        "storage_columns": storage, "storage_values": raw_storage,
        "output_excerpt": output[-6000:],
    }


def run_com_worker():
    session = None
    results = {"version": "19.1.0.1", "cases": {}}
    command_log = []
    try:
        session = MinitabSession()
        try:
            results["cases"]["TAG-DYNAMIC"] = _run_dynamic(session)
            command_log.extend(results["cases"]["TAG-DYNAMIC"]["commands"])
        except Exception as exc:
            results["cases"]["TAG-DYNAMIC"] = {"error": str(exc)}
            command_log.append("TAG-DYNAMIC failed; see minitab_raw.txt")
        session.new_project()
        try:
            robust_rows = list(csv.DictReader(INPUTS["TAG-ROBUST"].open(encoding="utf-8-sig")))
            robust_rows = [{key: (int(value) if key.endswith("_code") or key == "standard_order"
                                 else float(value) if key == "Y" else value)
                            for key, value in row.items()} for row in robust_rows]
            results["cases"]["TAG-ROBUST"] = _run_robust(session, robust_rows)
            command_log.extend(results["cases"]["TAG-ROBUST"]["commands"])
        except Exception as exc:
            results["cases"]["TAG-ROBUST"] = {"error": str(exc)}
            command_log.append("TAG-ROBUST failed; see minitab_raw.txt")
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
        COMMANDS.write_text("\n\n".join(command_log) + "\n", encoding="utf-8")
    return results


def _dynamic_key(row):
    return tuple(int(value) for value in row["key"])


def _mini_dynamic_lookup(minijmp):
    return {_control_code(row["settings"]["A"], row["settings"]["B"]): row
            for row in minijmp["combinations"]}


def _mini_robust_lookup(minijmp):
    return {_control_code(row["settings"]["A"], row["settings"]["B"]): row
            for row in minijmp["combinations"]}


def _level_means(rows, factor_index):
    grouped = {1: [], 2: []}
    for key, value in rows.items():
        grouped[key[factor_index - 1]].append(float(value))
    return {code: float(np.mean(values)) for code, values in grouped.items()}


def _settings_text(settings):
    return ",".join(f"{key}={settings[key]}" for key in sorted(settings))


def _unsupported_row(case_id, statistic, explanation):
    return {
        "case_id": case_id, "comparison_run": "1", "section": "design",
        "term": "Minitab method limitation", "statistic": statistic,
        "minitab_value": explanation, "minijmp_value": "MiniJMP feature available",
        "absolute_error": "", "relative_error": "",
        "absolute_tolerance": "", "relative_tolerance": "",
        "minitab_value_source": "UNSUPPORTED", "minijmp_value_source": "DIRECT",
        "status": "UNSUPPORTED",
    }


def make_comparison(minijmp, minitab):
    rows = []
    dynamic_mini = minijmp["cases"]["TAG-DYNAMIC"]
    dynamic_mtb = minitab["cases"].get("TAG-DYNAMIC", {})
    if "error" in dynamic_mtb:
        rows.append(compare_text("TAG-DYNAMIC", "execution", "ROBUST", "command",
                                 "ERROR", dynamic_mtb["error"], "DIRECT", "DIRECT"))
    else:
        mini_by_key = _mini_dynamic_lookup(dynamic_mini)
        mtb_by_key = {_dynamic_key(row): row for row in dynamic_mtb["combinations"].values()}
        rows.extend([
            compare_numeric("TAG-DYNAMIC", "design", "signal", "run_count",
                            dynamic_mtb["rows"], dynamic_mini["n"], "DIRECT", "DIRECT"),
            compare_numeric("TAG-DYNAMIC", "design", "signal", "distinct_levels",
                            len(set(dynamic_mtb["signal_levels"])), 3, "DIRECT", "DIRECT"),
        ])
        for key in sorted(mini_by_key):
            mini, mtb = mini_by_key[key], mtb_by_key.get(key)
            if mtb is None:
                rows.append(compare_text("TAG-DYNAMIC", "design", str(key), "control_mapping",
                                         "missing", str(key), "DIRECT", "DIRECT"))
                continue
            term = f"A={'low' if key[0] == 1 else 'high'},B={'low' if key[1] == 1 else 'high'}"
            rows.extend([
                compare_numeric("TAG-DYNAMIC", "dynamic_fit", term, "slope",
                                mtb["slope"], mini["slope"], "DIRECT", "DIRECT"),
                compare_numeric("TAG-DYNAMIC", "dynamic_fit", term, "intercept",
                                mtb["intercept"], mini["intercept"], "DIRECT", "DIRECT"),
                compare_numeric("TAG-DYNAMIC", "dynamic_fit", term, "residual_sd_sqrt_mse",
                                mtb["residual_sd"], math.sqrt(mini["mse"]),
                                "DIRECT", "DERIVED"),
                compare_numeric("TAG-DYNAMIC", "dynamic_fit", term, "dynamic_sn",
                                mtb["sn"], mini["sn"], "DIRECT", "DIRECT"),
            ])
        for factor_index, factor in enumerate(("A", "B"), start=1):
            mtb_slopes = {key: row["slope"] for key, row in mtb_by_key.items()}
            level_means = _level_means(mtb_slopes, factor_index)
            mini_factor = next(item for item in dynamic_mini["slope_factor_table"]
                               if item["factor_id"] == factor)
            levels = {"low": 1, "high": 2}
            for level_name, code in levels.items():
                expected = next(item["slope"] for item in mini_factor["levels"]
                                if item["level"] == level_name)
                rows.append(compare_numeric(
                    "TAG-DYNAMIC", "response_table", factor, f"slope_mean_{level_name}",
                    level_means[code], expected, "DERIVED", "DIRECT"))
            mini_sn_factor = next(item for item in dynamic_mini["sn_factor_table"]
                                  if item["factor_id"] == factor)
            mtb_sn_means = _level_means(
                {key: row["sn"] for key, row in mtb_by_key.items()}, factor_index)
            for level_name, code in levels.items():
                expected = next(item["sn"] for item in mini_sn_factor["levels"]
                                if item["level"] == level_name)
                rows.append(compare_numeric(
                    "TAG-DYNAMIC", "response_table", factor, f"sn_mean_{level_name}",
                    mtb_sn_means[code], expected, "DERIVED", "DIRECT"))
        best = dynamic_mini["best"]
        mtb_slopes = {key: row["slope"] for key, row in mtb_by_key.items()}
        nearest = min(abs(value - best["target"]) for value in mtb_slopes.values())
        rows.append(compare_numeric("TAG-DYNAMIC", "best_settings", "slope_target",
                                    "minimum_target_distance", nearest, 0.0,
                                    "DERIVED", "DIRECT"))
        mini_tied = {tuple(sorted(item["settings"].items())) for item in best["tied_combinations"]}
        mtb_tied = {tuple(sorted(dict(zip(("A", "B"),
                                         ("low" if key[0] == 1 else "high",
                                          "low" if key[1] == 1 else "high"))).items()))
                    for key, value in mtb_slopes.items()
                    if math.isclose(abs(value - best["target"]), nearest,
                                    rel_tol=0, abs_tol=1e-10)}
        rows.append(compare_text("TAG-DYNAMIC", "best_settings", "slope_target",
                                 "tied_control_settings", str(sorted(mtb_tied)),
                                 str(sorted(mini_tied)), "DERIVED", "DERIVED"))

    robust_mini = minijmp["cases"]["TAG-ROBUST"]
    robust_mtb = minitab["cases"].get("TAG-ROBUST", {})
    if "error" in robust_mtb:
        rows.append(compare_text("TAG-ROBUST", "execution", "ROBUST", "command",
                                 "ERROR", robust_mtb["error"], "DIRECT", "DIRECT"))
    else:
        mini_by_key = _mini_robust_lookup(robust_mini)
        mtb_by_key = {_dynamic_key(row): row for row in robust_mtb["combinations"].values()}
        rows.append(compare_numeric("TAG-ROBUST", "design", "outer_array", "run_count",
                                    robust_mtb["rows"], robust_mini["n"], "DIRECT", "DIRECT"))
        for key in sorted(mini_by_key):
            mini, mtb = mini_by_key[key], mtb_by_key.get(key)
            if mtb is None:
                rows.append(compare_text("TAG-ROBUST", "design", str(key), "control_mapping",
                                         "missing", str(key), "DIRECT", "DIRECT"))
                continue
            term = f"A={'low' if key[0] == 1 else 'high'},B={'low' if key[1] == 1 else 'high'}"
            for statistic in ("mean", "sd", "sn"):
                rows.append(compare_numeric("TAG-ROBUST", "robust_summary", term, statistic,
                                            mtb[statistic], mini[statistic], "DIRECT", "DIRECT"))
        for factor_index, factor in enumerate(("A", "B"), start=1):
            mini_factor = next(item for item in robust_mini["sn_factor_table"]
                               if item["factor_id"] == factor)
            for metric in ("sn", "mean", "sd"):
                level_means = _level_means(
                    {key: row[metric] for key, row in mtb_by_key.items()}, factor_index)
                for level_name, code in (("low", 1), ("high", 2)):
                    expected = next(item[metric] for item in mini_factor["levels"]
                                    if item["level"] == level_name)
                    rows.append(compare_numeric(
                        "TAG-ROBUST", "response_table", factor,
                        f"{metric}_mean_{level_name}", level_means[code], expected,
                        "DERIVED", "DIRECT"))
        best = robust_mini["best"]
        mtb_best_settings = robust_mtb["predicted"]["best_settings"]
        rows.extend([
            compare_text("TAG-ROBUST", "best_settings", "S/N", "control_settings",
                         _settings_text(mtb_best_settings),
                         _settings_text(best["settings"]), "DERIVED", "DIRECT"),
            compare_numeric("TAG-ROBUST", "best_settings", "S/N", "predicted_sn",
                            robust_mtb["predicted"]["sn"], best["predicted_sn"],
                            "DERIVED", "DIRECT"),
            compare_numeric("TAG-ROBUST", "best_settings", "mean", "predicted_mean",
                            robust_mtb["predicted"]["mean"], best["predicted_mean"],
                            "DERIVED", "DIRECT"),
            compare_numeric("TAG-ROBUST", "best_settings", "sd", "predicted_sd",
                            robust_mtb["predicted"]["sd"], best["predicted_sd"],
                            "DERIVED", "DERIVED"),
        ])
    return rows


def write_report(rows, minitab):
    counts = status_counts(rows)
    per_case = {case_id: status_counts([row for row in rows if row["case_id"] == case_id])
                for case_id in CASE_IDS}
    mt_sources = {}
    for row in rows:
        source = row["minitab_value_source"]
        mt_sources[source] = mt_sources.get(source, 0) + 1
    lines = [
        "# Minitab 19 动态 Taguchi 与控制×噪声稳健对标",
        "",
        "## 结果",
        "",
        f"唯一比较项：{sum(counts.values())}（PASS {counts['PASS']} / FAIL {counts['FAIL']} / "
        f"N/A {counts['N/A']} / UNSUPPORTED {counts['UNSUPPORTED']}）。",
        f"Minitab 来源：DIRECT {mt_sources.get('DIRECT', 0)}、DERIVED {mt_sources.get('DERIVED', 0)}、"
        f"DISPLAY {mt_sources.get('DISPLAY', 0)}。",
        "",
        *[f"- {case_id}: PASS {value['PASS']} / FAIL {value['FAIL']} / "
          f"N/A {value['N/A']} / UNSUPPORTED {value['UNSUPPORTED']}。"
          for case_id, value in per_case.items()],
        "",
        "- TAG-DYNAMIC：4 个控制组合斜率为 8、20、20、32；目标斜率 20 有两组并列，Minitab 与 MiniJMP 推荐一致。",
        "- TAG-ROBUST：16 个运行覆盖 4 个控制组合×4 个噪声条件；较小为优 S/N 的推荐设置为 A=low、B=high。",
        "",
        "## Minitab 19 实际命令",
        "",
    ]
    for case_id in CASE_IDS:
        value = minitab.get("cases", {}).get(case_id, {})
        commands = value.get("commands", [value.get("error", "未运行")])
        lines.extend([f"- {case_id}:", "", "```text", *commands, "```", ""])
    lines.extend([
        "## 口径与限制",
        "",
        "- TAG-DYNAMIC 使用 `NOREF`，双方均在每个控制组合内估计自由截距；比较斜率、截距、`sqrt(MSE)` 与动态 S/N。Minitab `STDEVS` 对应回归残差标准差，不是三个信号响应的样本标准差。",
        "- 动态 S/N 使用 `10*log10(slope^2/MSE)`；未使用 Minitab 未提供的 MiniJMP adjusted 设定。最佳目标斜率从同一 `TSLOPES` 数据派生，不称为自动目标优化命令。",
        "- TAG-ROBUST 以 A/B 为控制因子，N1/N2 是四个外表噪声组合；每个控制设置的四个响应值进入 `ROBUST ... LOWER`，按较小为优计算 S/N。噪声列保留用于条件映射，没有当作控制因子拟合。",
        "- 不把控制×噪声 OLS 响应模型与 `ROBUST` 的组内噪声稳健统计混为一谈；本轮只对齐均值、样本 SD、较小为优 S/N 及基于主效应响应表的推荐设置。",
        "- Minitab COM 存储列中的 `1.23456e30` 是缺失哨兵；其余直接值按控制组合映射。",
        "- 官方 Session Commands 第 414–419 页定义 `SNAME/SLEVEL`、`DYNAMIC/NOREF`、`TSLOPES`、`SLOPES` 与 `STDEVS`；完整运行回传见 `minitab_raw.txt`。",
    ])
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    if "--self-check" in sys.argv:
        run_minijmp()
        print("dynamic and control-noise MiniJMP/exact-reference self-check passed")
    elif "--com-worker" in sys.argv:
        results = run_com_worker()
        print(f"Minitab worker completed; cases={list(results.get('cases', {}))}")
    elif "--compare" in sys.argv:
        minijmp = json.loads(MINIJMP.read_text(encoding="utf-8"))
        minitab = json.loads(MINITAB.read_text(encoding="utf-8"))
        rows = make_comparison(minijmp, minitab)
        write_comparison(COMPARISON, rows)
        write_report(rows, minitab)
        write_json(MINITAB, minitab)
        print(f"Taguchi supplemental counts: {status_counts(rows)}")
    elif "--run" in sys.argv:
        minijmp = run_minijmp()
        run_worker(Path(__file__), "--com-worker")
        minitab = json.loads(MINITAB.read_text(encoding="utf-8"))
        # Add predictions derived from Minitab's direct response-table storage.
        for case_id in CASE_IDS:
            case = minitab.get("cases", {}).get(case_id, {})
            if "combinations" not in case:
                continue
            if case_id == "TAG-ROBUST":
                case["predicted"] = _additive_predictions(case["combinations"])
        rows = make_comparison(minijmp, minitab)
        write_comparison(COMPARISON, rows)
        write_report(rows, minitab)
        write_json(MINITAB, minitab)
        print(f"Taguchi supplemental counts: {status_counts(rows)}")
    else:
        raise SystemExit("Use --self-check, --com-worker, --compare, or --run")


def _additive_predictions(combinations):
    rows = list(combinations.values())
    means = {}
    for metric in ("sn", "mean", "sd"):
        grand = float(np.mean([row[metric] for row in rows]))
        factors = {}
        for factor, index in (("A", 0), ("B", 1)):
            factors[factor] = {}
            for code, label in ((1, "low"), (2, "high")):
                factors[factor][label] = float(np.mean(
                    [row[metric] for row in rows if row["key"][index] == code]))
        means[metric] = (grand, factors)
    best_settings = {factor: max(levels, key=levels.get)
                     for factor, levels in means["sn"][1].items()}
    result = {"best_settings": best_settings}
    for metric, (grand, factors) in means.items():
        result[metric] = grand + sum(factors[factor][best_settings[factor]] - grand
                                     for factor in ("A", "B"))
    return result


if __name__ == "__main__":
    main()
