from pathlib import Path
import json
import os
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "Out/minitab19_parity/supplemental"))
from common import MinitabSession, run_worker

FACTORS = [f"X{i}" for i in range(1, 14)] + ["A", "B", "C"]


def worker(destination):
    cases4 = json.loads((HERE.parent / "phase4/case_inputs.json").read_text(encoding="utf-8-sig"))["cases"]
    cases6 = json.loads((HERE.parent / "phase6/case_inputs.json").read_text(encoding="utf-8-sig"))
    session = MinitabSession()
    evidence = {"version": session.version, "app_path": session.app_path,
                "process_path": session.process_path, "commands": session.raw, "inputs": {}}

    def load(name, values):
        if None in values:
            raise ValueError("Fixture contains missing values; use the Phase 6 loader")
        evidence["inputs"][name] = values
        index = session.add_column(name, values)
        assert session.column_values(index) == values
        return f"C{index}"

    def execute(label, command):
        try:
            session.execute(command, label)
        except Exception as exc:
            evidence.setdefault("errors", {})[label] = {
                "exception": str(exc), "last_error": str(session.app.LastError or "")}
            if not session.raw or not session.raw[-1].startswith(f"===== {label} "):
                session.raw.append(f"===== {label} actual command =====\n{command}")
            return False
        return True

    try:
        column = load("one_variance", cases4["one_variance"]["values"])
        execute("G05_left", f"ONEV {column};\n  STEST 3;\n  ALTERNATIVE -1;\n  CONFIDENCE 90.")
        execute("G05_right_at_4", f"ONEV {column};\n  STEST 4;\n  ALTERNATIVE 1;\n  CONFIDENCE 90.")
        execute("G05_right_at_12", f"ONEV {column};\n  STEST 12;\n  ALTERNATIVE 1;\n  CONFIDENCE 90.")
        for case_id in ("normal_ties", "right_skew_ties_missing"):
            values = cases6["fit"][case_id]["values"]
            # Preserve original worksheet positions, including internal missing entries.
            from verify_statistics_minitab19_phase6 import load_column
            index = session.add_column(case_id)
            evidence["inputs"][case_id], _ = load_column(
                session.app, session.project, session.columns, index, case_id, values)
            for distribution in ("NORMAL", "LNORMAL"):
                execute(f"G03_{case_id}_{distribution}",
                        f"DCAPA C{index} 1;\n  {distribution};\n  RESTIMATE;\n"
                        "  RPTILE 5 50 95;\n  CONFIDENCE 95.")
        large = load("n100", list(range(1, 101)))
        small = [load(f"n{n}", list(range(1, n + 1))) for n in range(1, 11)]
        for direction in (0, -1, 1):
            for label, columns in (("n100", large), ("small", " ".join(small[1:])), ("n1", small[0])):
                execute(f"G07_{label}_{direction}",
                        f"TOLINTERVALS {columns};\n  CONFIDENCE 95;\n  PPERCENT 90;\n"
                        f"  ITYPE {direction};\n  TTOLINTERVAL.")
        session.new_project()
        levels = " ".join(["-1 1"] * 13 + ['"Low" "High"'] * 3)
        names = " ".join(f'"{name}"' for name in FACTORS)
        if execute("G08_13plus3", f"DSDESIGN 16;\n  REPLICATES 1;\n  LEVELS {levels};\n"
                   f"  FNAME {names};\n  BRIEF 3."):
            evidence["design"] = {
                str(session.columns.Item(i).Name): list(session.columns.Item(i).GetData())
                for i in range(1, int(session.columns.Count) + 1)
            }
    finally:
        session.release()
        with destination.open("x", encoding="utf-8") as stream:
            json.dump(evidence, stream, ensure_ascii=False, indent=2)
            stream.write("\n")


if __name__ == "__main__":
    sys.path.insert(0, str(HERE.parent / "phase6"))
    destination = Path(os.environ["MINIJMP_PHASE3_OUTPUT"] if sys.argv[1] == "--com-worker"
                       else sys.argv[1]).resolve()
    if destination.exists():
        raise FileExistsError(destination)
    if sys.argv[1] == "--com-worker":
        worker(destination)
    else:
        # The shared runner passes only the worker mode, so forward the output path.
        os.environ["MINIJMP_PHASE3_OUTPUT"] = str(destination)
        run_worker(Path(__file__), "--com-worker")
