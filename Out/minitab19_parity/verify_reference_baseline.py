"""Verify the fixed Minitab 19 DOE references without starting Minitab."""
from __future__ import annotations

import csv
import hashlib
import importlib
import json
import math
import sys
import tempfile
from collections import Counter, defaultdict
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]
MANIFEST = OUT / "reference_baseline_manifest.csv"
RESULTS = OUT / "reference_baseline_offline_results.csv"
PROJECT_PYTHON = ROOT / ".venv" / "Scripts" / "python.exe"
EXPECTED_CASES = {
    "DOE-2X2", "DOE-CCD", "TAG-L8", "TAG-L9", "MIX-3COMP", "BBD-3FACT",
    "PB-12RUN", "SP-2FACT-3BLOCK",
}
HASH_FIELDS = (
    ("input_path", "input_sha256"),
    ("session_commands_path", "session_commands_sha256"),
    ("raw_output_path", "raw_output_sha256"),
    ("minitab_reference_path", "minitab_reference_sha256"),
    ("minijmp_snapshot_path", "minijmp_snapshot_sha256"),
    ("comparison_path", "comparison_sha256"),
    ("case_report_path", "case_report_sha256"),
    ("batch_summary_path", "batch_summary_sha256"),
    ("batch_report_path", "batch_report_sha256"),
    ("offline_results_path", "offline_results_sha256"),
    ("baseline_report_path", "baseline_report_sha256"),
)
RESULT_FIELDS = (
    "case_id", "comparison_run", "section", "term", "statistic",
    "minitab_value", "minijmp_value", "absolute_error", "relative_error",
    "absolute_tolerance", "relative_tolerance", "minitab_value_source",
    "minijmp_value_source", "status",
)
EXPECTED_COUNT_FIELDS = {
    "PASS": "expected_unique_pass",
    "FAIL": "expected_unique_fail",
    "N/A": "expected_unique_na",
    "UNSUPPORTED": "expected_unique_unsupported",
}

sys.path.insert(0, str(ROOT / "code"))
sys.path.insert(0, str(OUT))


def artifact_path(relative_path: str) -> Path:
    path = Path(relative_path)
    if path.is_absolute():
        raise ValueError(f"基线路径必须相对 Out/minitab19_parity: {relative_path}")
    resolved = (OUT / path).resolve()
    if not resolved.is_relative_to(OUT.resolve()):
        raise ValueError(f"基线路径越界: {relative_path}")
    return resolved


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_manifest() -> list[dict[str, str]]:
    with MANIFEST.open(newline="", encoding="utf-8-sig") as stream:
        rows = list(csv.DictReader(stream))
    if {row["case_id"] for row in rows} != EXPECTED_CASES or len(rows) != len(EXPECTED_CASES):
        raise ValueError("manifest 必须恰好包含八个固定 DOE 案例")
    if any(row["status"] not in {"PASS", "PARTIAL"} for row in rows):
        raise ValueError("manifest 中存在无效案例状态")
    return rows


def verify_manifest(rows: list[dict[str, str]]) -> dict[str, str]:
    hashes = {}
    for row in rows:
        if row["minitab_version"] != "19.1.0.1":
            raise ValueError(f"{row['case_id']} 版本不符: {row['minitab_version']}")
        for path_field, hash_field in HASH_FIELDS:
            path = artifact_path(row[path_field])
            actual = sha256(path)
            if actual != row[hash_field]:
                raise ValueError(f"基线校验失败: {row['case_id']} / {path.name}")
            hashes[row[path_field]] = actual
        reference = json.loads(artifact_path(row["minitab_reference_path"]).read_text(
            encoding="utf-8"))
        versions = ({item.get("version") for item in reference.values()}
                    if row["case_id"] in {"DOE-2X2", "DOE-CCD"}
                    else {reference.get("version")})
        if versions != {row["minitab_version"]}:
            raise ValueError(f"{row['case_id']} Minitab JSON 版本与 manifest 不一致")
    return hashes


def result_row(case_id: str, row: dict) -> dict:
    source = row.get("minitab_value_source", "")
    if case_id in {"DOE-2X2", "DOE-CCD"} and source:
        lowered = source.casefold()
        if "fixed csv" in lowered:
            source = "INPUT: " + source
        elif "derived" in lowered or "m1 rank" in lowered or "xmatrix m1 / minijmp result rank" in lowered:
            source = "DERIVED: " + source
        elif "minijmp" in lowered:
            source = "REFERENCE: " + source
        elif "minitab" in lowered:
            source = "DIRECT: " + source
    return {
        "case_id": case_id,
        "comparison_run": row.get("run", ""),
        **{field: row.get(field, "") for field in RESULT_FIELDS[2:]},
        "minitab_value_source": source,
    }


def _rows(result):
    return result[0] if isinstance(result, tuple) else result


def compare_case(entry: dict[str, str], scratch: Path) -> list[dict]:
    case_id = entry["case_id"]
    family = entry["family"]
    module_name = {
        "2x2": "verify_doe_2x2", "ccd": "verify_doe_ccd",
        "taguchi": "verify_doe_taguchi", "mixture": "verify_doe_mixture",
        "bbd": "verify_doe_bbd", "pb": "verify_doe_pb",
        "splitplot": "verify_doe_splitplot",
    }[family]
    module = importlib.import_module(module_name)
    reference = json.loads(artifact_path(entry["minitab_reference_path"]).read_text(
        encoding="utf-8"))

    if family == "2x2":
        snapshot = json.loads(artifact_path(entry["minijmp_snapshot_path"]).read_text(
            encoding="utf-8"))
        local = module.run_minijmp(module.read_input())
        rows = []
        for run_id in ("1", "2"):
            rows.extend(module.compare_run(int(run_id), reference[run_id], local)[0])
        for software, runs in (("Minitab", reference), ("MiniJMP", snapshot)):
            first = module.flatten_repeatability(runs["1"])
            second = module.flatten_repeatability(runs["2"])
            if set(first) != set(second):
                raise ValueError(f"DOE-2X2 {software} rerun statistic keys differ")
            for key in sorted(first):
                rows.append(module.compare_values(
                    "run1_vs_run2", f"repeatability_{software}", key, "value",
                    first[key], second[key], f"{software} frozen clean-process rerun"))
    elif family == "ccd":
        snapshot = json.loads(artifact_path(entry["minijmp_snapshot_path"]).read_text(
            encoding="utf-8"))
        local = module.run_minijmp(module.read_input())
        rows = []
        for run_id in ("1", "2"):
            rows.extend(module.compare_run(int(run_id), reference[run_id], local)[0])
        for software, runs in (("Minitab", reference), ("MiniJMP", snapshot)):
            first = module.flatten(runs["1"])
            second = module.flatten(runs["2"])
            if set(first) != set(second):
                raise ValueError(f"DOE-CCD {software} rerun statistic keys differ")
            for key in sorted(first):
                source = f"{software} frozen clean-process rerun"
                rows.append(module.compare_values(
                    "run1_vs_run2", f"repeatability_{software}", key, "value",
                    first[key], second[key], source, source))
    elif family == "taguchi":
        taguchi_case = case_id[-2:].lower()
        archived_input = module.read_input(taguchi_case)
        local = module.run_minijmp(taguchi_case, archived_input)
        rows = module.compare_case(taguchi_case, archived_input, local, reference)
    else:
        module.write_input = lambda _rows: None
        module.MINIJMP = scratch / f"{case_id.lower()}_minijmp.json"
        status = module.run_minijmp_worker()
        if status not in (None, 0):
            raise RuntimeError(f"{case_id} MiniJMP API worker failed: {status}")
        local = json.loads(module.MINIJMP.read_text(encoding="utf-8"))
        rows = _rows(module.compare_case(local, reference))

    return [result_row(case_id, row) for row in rows]


def unique_rows(rows: list[dict]) -> list[dict]:
    grouped = defaultdict(list)
    for row in rows:
        key = (row["case_id"], row["section"], row["term"], row["statistic"])
        grouped[key].append(row)
    unique = []
    for key, values in grouped.items():
        if len(values) == 1:
            unique.append(values[0])
            continue
        first = values[0]
        for value in values[1:]:
            if value["status"] != first["status"]:
                raise ValueError(f"同一比较项的重复状态不一致: {key}")
            for field in ("minitab_value", "minijmp_value"):
                left, right = first[field], value[field]
                if left in ("", None) or right in ("", None):
                    if (left in ("", None)) != (right in ("", None)):
                        raise ValueError(f"同一比较项的重复值缺失状态不一致: {key}")
                    continue
                try:
                    left, right = float(left), float(right)
                except (TypeError, ValueError):
                    if left != right:
                        raise ValueError(f"同一比较项的重复值不一致: {key}")
                    continue
                allowed = (max(float(first["absolute_tolerance"] or 0),
                               float(value["absolute_tolerance"] or 0))
                           + max(float(first["relative_tolerance"] or 0),
                                 float(value["relative_tolerance"] or 0))
                           * max(abs(left), abs(right)))
                if abs(left - right) > allowed:
                    raise ValueError(f"同一比较项的重复值不一致: {key}")
        unique.append(first)
    return unique


def validate_case(entry: dict[str, str], rows: list[dict]) -> tuple[list[dict], Counter, str]:
    unique = unique_rows(rows)
    observed = Counter(row["status"] for row in unique)
    expected = {status: int(entry[field]) for status, field in EXPECTED_COUNT_FIELDS.items()}
    if len(rows) != int(entry["expected_raw_rows"]) or any(
            observed[status] != count for status, count in expected.items()):
        raise ValueError(f"{entry['case_id']} 比较覆盖/状态计数不符: "
                         f"raw={len(rows)}, unique={dict(observed)}")
    status = ("FAIL" if observed["FAIL"] else
              "PARTIAL" if observed["UNSUPPORTED"] else "PASS")
    if status != entry["status"]:
        raise ValueError(f"{entry['case_id']} 状态不符: {status} != {entry['status']}")
    return unique, observed, status


def write_results(rows: list[dict], path: Path) -> None:
    with path.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=RESULT_FIELDS, extrasaction="ignore",
                                lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    if Path(sys.executable).resolve() != PROJECT_PYTHON.resolve():
        raise RuntimeError(f"请使用项目解释器运行: {PROJECT_PYTHON}")
    manifest = read_manifest()
    input_hashes = verify_manifest(manifest)
    all_rows = []
    with tempfile.TemporaryDirectory(prefix="minijmp-reference-baseline-") as temp:
        scratch = Path(temp)
        for entry in manifest:
            case_rows = compare_case(entry, scratch)
            all_rows.extend(case_rows)
            case_unique, case_counts, case_status = validate_case(entry, case_rows)
            case_sources = {name: sum(name in row["minitab_value_source"]
                                      for row in case_unique)
                            for name in ("DIRECT", "DERIVED", "DISPLAY")}
            print(f"{entry['case_id']}: {case_status}; unique PASS/FAIL/N/A/UNSUPPORTED "
                  f"{case_counts['PASS']}/{case_counts['FAIL']}/{case_counts['N/A']}/"
                  f"{case_counts['UNSUPPORTED']}; unique DIRECT/DERIVED/DISPLAY "
                  f"{case_sources['DIRECT']}/{case_sources['DERIVED']}/{case_sources['DISPLAY']}; "
                  f"deduplicated rows={len(case_rows)-len(case_unique)}")
        candidate = scratch / RESULTS.name
        write_results(all_rows, candidate)
        candidate_hash = sha256(candidate)
        if candidate_hash != input_hashes[RESULTS.name]:
            raise RuntimeError("离线比较结果与已归档 CSV 不同；保留原文件未覆盖 "
                               f"(actual={candidate_hash}, expected={input_hashes[RESULTS.name]})")
    for path, expected in input_hashes.items():
        if sha256(artifact_path(path)) != expected:
            raise RuntimeError(f"offline calculation changed a baseline artifact: {path}")
    unique = unique_rows(all_rows)
    total = Counter(row["status"] for row in unique)
    sources = {name: sum(name in row["minitab_value_source"] for row in unique)
               for name in ("DIRECT", "DERIVED", "DISPLAY")}
    overall = "PARTIAL" if any(entry["status"] == "PARTIAL" for entry in manifest) else "PASS"
    print(f"离线基线复验完成；案例状态 {overall}；八个案例；unique PASS/FAIL/N/A/UNSUPPORTED "
          f"{total['PASS']}/{total['FAIL']}/{total['N/A']}/{total['UNSUPPORTED']}；"
          f"DIRECT/DERIVED/DISPLAY {sources['DIRECT']}/{sources['DERIVED']}/{sources['DISPLAY']}；"
          "Minitab COM 未启动。")
    print(f"逐项结果: {RESULTS}")
    return 1 if total["FAIL"] else 0


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--self-check":
        try:
            probe = {"case_id": "SELF-CHECK", "status": "PASS", "expected_raw_rows": "1",
                     "expected_unique_pass": "1", "expected_unique_fail": "0",
                     "expected_unique_na": "0", "expected_unique_unsupported": "0"}
            row = {"case_id": "SELF-CHECK", "section": "s", "term": "t", "statistic": "v",
                   "status": "PASS", "minitab_value": 1, "minijmp_value": 1,
                   "absolute_tolerance": 0, "relative_tolerance": 0}
            assert validate_case(probe, [row])[2] == "PASS"
            try:
                validate_case({**probe, "expected_raw_rows": "0"}, [row])
            except ValueError:
                pass
            else:
                raise AssertionError("coverage regression was accepted")
            entries = read_manifest()
            verify_manifest(entries)
            print(f"Reference manifest self-check: PASS ({len(entries)} cases)")
        except Exception as error:
            print(f"Reference manifest self-check: FAIL: {error}", file=sys.stderr)
            raise SystemExit(1)
        raise SystemExit(0)
    raise SystemExit(main())
