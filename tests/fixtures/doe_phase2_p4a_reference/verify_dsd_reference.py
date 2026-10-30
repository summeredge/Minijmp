"""重建并精确复核 DSD Stepwise 参考；不导入 MiniJMP 生产模块。"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_dsd_reference import build


ROOT = Path(__file__).resolve().parent


def _check_hierarchy(terms, label):
    present = set(terms)
    for item in terms:
        if len(item) == 2:
            parents = [(item[0],)] + ([] if item[0] == item[1] else [(item[1],)])
            for parent in parents:
                assert parent in present, (label, item)


def _walk(case):
    terms = [tuple(item) for item in case["initial_terms"]]
    forced = {tuple(item) for item in case["forced_terms"]}
    candidates = [tuple(item) for item in case["candidate_terms"]]
    assert len(set(candidates)) == len(candidates), case["id"]
    _check_hierarchy(terms, case["id"])
    for number, step in enumerate(case["selection_steps"], 1):
        assert step["step"] == number, case["id"]
        term = tuple(step["term"])
        if step["action"] == "enter":
            assert term not in terms and term in candidates, case["id"]
            assert step["rank_after"] > step["rank_before"], case["id"]
            assert step["sse_after"] < step["sse_before"], case["id"]
            terms = terms + [term]
        else:
            assert term in terms and term not in forced, case["id"]
            assert step["rank_after"] < step["rank_before"], case["id"]
            assert step["sse_after"] > step["sse_before"], case["id"]
            terms = [item for item in terms if item != term]
        _check_hierarchy(terms, case["id"])
        assert [tuple(item) for item in step["terms"]] == terms, case["id"]
        assert step["error_df"] >= 0, case["id"]
    assert [tuple(item) for item in case["selected_terms"]] == terms, case["id"]


def verify():
    manifest = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["files"]["dsd_reference.json"] == hashlib.sha256(
        (ROOT / "dsd_reference.json").read_bytes()).hexdigest()
    stored = json.loads((ROOT / "dsd_reference.json").read_text(encoding="utf-8"))
    saved = {case["id"]: case for case in stored["cases"]}
    rebuilt = {case["id"]: case for case in build()}
    assert set(saved) == set(rebuilt)
    results = {}
    for key, case in rebuilt.items():
        frozen = saved[key]
        assert frozen["response"] == case["response"], key
        assert frozen["selected_terms"] == case["selected_terms"], key
        assert frozen["stop_reason"] == case["stop_reason"], key
        assert len(frozen["selection_steps"]) == len(case["selection_steps"]), key
        for want, got in zip(frozen["selection_steps"], case["selection_steps"]):
            assert want["action"] == got["action"] and want["term"] == got["term"], key
            assert want["p"] == got["p"] and want["f"] == got["f"], key
        _walk(case)
        results[key] = {"stop_reason": case["stop_reason"],
                        "selected": ["".join(item) for item in case["selected_terms"]],
                        "final_rank": case["final_rank"],
                        "final_residual_df": case["final_residual_df"]}
    return results


if __name__ == "__main__":
    for key, value in verify().items():
        print(f"{key}: {json.dumps(value, ensure_ascii=False, sort_keys=True)}")
