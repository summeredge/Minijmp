"""Build the post-repair supplemental parity archive from frozen CSV evidence."""
import csv
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent
KEY = ("case_id", "section", "term", "statistic")
CASES = (
    "dsd/comparison.csv", "general_factorial/comparison.csv", "foldover/comparison.csv",
    "binary/comparison.csv", "optimal/comparison.csv", "taguchi_dynamic/comparison.csv",
    "mixture_extended/comparison.csv", "mixture_extended/mixture_v2_comparison.csv",
)
OUT = ROOT / "supplemental_postrepair_summary.csv"
DETAIL = ROOT / "supplemental_postrepair_comparisons.csv"
REPAIRED = ROOT / "binary/fisher_diagnosis/repaired_comparison.csv"
FIELDS = ("case_id", "comparison_run", "section", "term", "statistic",
          "old_status", "old_minijmp_value", "old_absolute_error", "old_relative_error",
          "minitab_value", "minijmp_value", "absolute_error", "relative_error",
          "absolute_tolerance", "relative_tolerance", "minitab_value_source",
          "minijmp_value_source", "status")


def rows(path):
    with path.open(newline="", encoding="utf-8-sig") as stream:
        return list(csv.DictReader(stream))


def main():
    source = [row for relative in CASES for row in rows(ROOT / relative)]
    repaired = {tuple(row[name] for name in KEY): row for row in rows(REPAIRED)}
    merged = []
    for row in source:
        merged.append(repaired.get(tuple(row[name] for name in KEY), row))
    unique = {}
    for row in merged:
        key = tuple(row[name] for name in KEY)
        previous = unique.setdefault(key, row)
        if previous != row:
            raise AssertionError(f"duplicate key has conflicting values: {key}")
    if len(unique) != 2935:
        raise AssertionError(f"expected 2935 unique comparisons, got {len(unique)}")
    counts = Counter(row["status"] for row in unique.values())
    if counts != Counter({"PASS": 2903, "FAIL": 4, "N/A": 23, "UNSUPPORTED": 5}):
        raise AssertionError(f"unexpected totals: {counts}")
    binary = [row for row in unique.values() if row["case_id"].startswith("BIN-")]
    if Counter(row["status"] for row in binary) != Counter({"PASS": 189, "FAIL": 4, "N/A": 2}):
        raise AssertionError("unexpected Binary totals")
    fail_keys = {tuple(row[name] for name in KEY) for row in binary if row["status"] == "FAIL"}
    expected = {("BIN-RSM", "coefficient", term, "wald_z") for term in ("A", "A²", "B²", "A*C")}
    if fail_keys != expected:
        raise AssertionError(f"unexpected Binary FAIL keys: {fail_keys}")
    ordered = sorted(unique.values(), key=lambda row: tuple(row[name] for name in KEY))
    with DETAIL.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(ordered)
    grouped = {}
    for row in ordered:
        grouped.setdefault(row["case_id"], []).append(row)
    summary_fields = ("case_id", "unique_comparisons", "PASS", "FAIL", "N/A", "UNSUPPORTED", "status")
    with OUT.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=summary_fields, lineterminator="\n")
        writer.writeheader()
        for case_id in sorted(grouped):
            case_counts = Counter(row["status"] for row in grouped[case_id])
            writer.writerow({"case_id": case_id, "unique_comparisons": len(grouped[case_id]),
                             "PASS": case_counts["PASS"], "FAIL": case_counts["FAIL"],
                             "N/A": case_counts["N/A"], "UNSUPPORTED": case_counts["UNSUPPORTED"],
                             "status": "PASS" if not case_counts["FAIL"] and not case_counts["UNSUPPORTED"]
                             else "PARTIAL" if not case_counts["FAIL"] else "FAIL"})
    print({"source_rows": len(source), "unique_rows": len(unique), "counts": dict(counts),
           "binary_counts": dict(Counter(row["status"] for row in binary)), "output": str(OUT)})


if __name__ == "__main__":
    main()
