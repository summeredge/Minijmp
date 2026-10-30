"""重建并复核 PB Foldover 参考；不导入生产模块，也不使用正规定义关系。"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_pb_foldover_reference import RUN_COUNTS, build, fold, pb_matrix


ROOT = Path(__file__).resolve().parent


def verify():
    manifest = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["files"]["pb_foldover_reference.json"] == hashlib.sha256(
        (ROOT / "pb_foldover_reference.json").read_bytes()).hexdigest()
    stored = json.loads((ROOT / "pb_foldover_reference.json").read_text(encoding="utf-8"))
    saved = {case["run_count"]: case for case in stored["cases"]}
    rebuilt = {case["run_count"]: case for case in build()}
    assert set(saved) == set(rebuilt) == set(RUN_COUNTS)
    results = {}
    for run_count in RUN_COUNTS:
        case, frozen = rebuilt[run_count], saved[run_count]
        assert case["base_points"] == frozen["base_points"]
        assert case["new_points_all"] == frozen["new_points_all"]
        assert case["new_points_one"] == frozen["new_points_one"]

        matrix, _ = pb_matrix(run_count)
        factor_count = run_count - 1
        base = [row[:factor_count] for row in matrix]
        # 点集、符号与运行数独立重算。
        assert case["base_points"] == base
        assert case["new_points_all"] == fold(base, set(range(factor_count)))
        assert case["new_points_one"] == fold(base, {0})
        assert case["total_runs"] == 2 * run_count
        assert case["added_runs"] == run_count
        assert case["all_is_exact_sign_copy"] is True
        assert case["one_changes_only_first_column"] is True
        assert case["one_flips_first_column"] is True
        for point in base + case["new_points_all"]:
            # PB 允许出现全 −1 基线运行；只要求水平属于两水平编码。
            assert all(value in (-1, 1) for value in point)
            assert len(point) == factor_count

        before, after_all, after_one = (case["before"], case["after_all"],
                                        case["after_one"])
        # 主效应秩保持满秩，联合二阶模型秩严格增加。
        assert before["main_rank"] == run_count
        assert after_all["main_rank"] == run_count
        assert after_one["main_rank"] == run_count
        assert before["joint_rank"] == run_count
        assert after_all["joint_rank"] > before["joint_rank"]
        assert after_one["joint_rank"] > before["joint_rank"]
        assert after_all["joint_rank"] <= 2 * run_count
        # 全因子折叠移除全部完全混杂；单因子折叠只减少与折叠因子相关的混杂。
        # 部分混杂的定义是“可估计但非正交”，因此折叠后可能由完全变为部分。
        assert after_all["complete_confounding_count"] == 0
        assert after_all["partial_confounding_count"] == 0
        assert after_one["complete_confounding_count"] <= before["complete_confounding_count"]
        assert (after_one["complete_confounding_count"] +
                after_one["partial_confounding_count"] <
                before["complete_confounding_count"] +
                before["partial_confounding_count"])
        results[run_count] = {
            "source_kind": case["source_kind"],
            "main_rank": [before["main_rank"], after_all["main_rank"]],
            "joint_rank": [before["joint_rank"], after_all["joint_rank"]],
            "joint_rank_single": [before["joint_rank"], after_one["joint_rank"]],
            "complete_confounding": [before["complete_confounding_count"],
                                     after_all["complete_confounding_count"],
                                     after_one["complete_confounding_count"]],
            "partial_confounding": [before["partial_confounding_count"],
                                    after_all["partial_confounding_count"],
                                    after_one["partial_confounding_count"]],
        }
    return results


if __name__ == "__main__":
    for key, value in verify().items():
        print(f"pb{key}: {json.dumps(value, sort_keys=True)}")
