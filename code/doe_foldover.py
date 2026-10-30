"""正规两水平部分因子的全因子或单因子 Foldover。"""
from dataclasses import replace

import pandas as pd

from doe_core import RunRecord, foldover_matrix_fingerprint, worksheet_metadata
from doe_fractional import (
    _matrix_structure, validate_fractional_design,
)


_BATCH_ID = "FOLD1"


def create_foldover(frame, metadata, folded_factors=None):
    """创建独立折叠工作表数据；保留来源响应，新增运行响应留空。"""
    source = validate_fractional_design(frame, metadata)
    spec = source.spec
    if spec.foldover_lineage is not None:
        raise ValueError("不支持对已有 Foldover 设计再次折叠")
    if any(run.block is not None for run in source.runs):
        raise ValueError("当前 Foldover 仅支持无区组的正规部分因子设计")
    factor_ids = tuple(factor.factor_id for factor in spec.factors)
    if folded_factors is None:
        folded = factor_ids
    elif isinstance(folded_factors, str) and folded_factors == "全部":
        folded = factor_ids
    elif isinstance(folded_factors, str):
        folded = (folded_factors,)
    elif isinstance(folded_factors, (tuple, list)):
        folded = tuple(folded_factors)
    else:
        raise ValueError("折叠因子必须是全部或因子 ID 列表")
    if (not folded or any(not isinstance(key, str) for key in folded)
            or len(set(folded)) != len(folded)
            or any(key not in factor_ids for key in folded)):
        raise ValueError("折叠因子必须是非空且不重复的有效因子子集")
    folded = tuple(key for key in factor_ids if key in folded)

    base_runs = tuple(source.runs)
    source_factorial = tuple(sorted(
        (run for run in base_runs if run.point_type == "factorial"),
        key=lambda run: run.standard_order))
    base_count = len(base_runs)
    if base_count + len(source_factorial) > 10000:
        raise ValueError("折叠后运行总数不能超过 10000")

    columns = dict(metadata["column_map"])
    columns["batch_id"] = _unique_column(frame, "DOE 批次")
    columns["source_run_id"] = _unique_column(frame, "DOE 源运行ID")
    original = frame.copy(deep=True).reset_index(drop=True)
    original[columns["batch_id"]] = "BASE"
    original[columns["source_run_id"]] = None

    additions = []
    addition_records = []
    run_map = []
    for index, run in enumerate(source_factorial, 1):
        run_id = f"F{index:05d}"
        settings = dict(run.settings)
        for factor_id in folded:
            factor = next(item for item in spec.factors if item.factor_id == factor_id)
            settings[factor_id] = (factor.low if settings[factor_id] == factor.high
                                   else factor.high)
        additions.append(_addition_row(
            frame, columns, run_id,
            base_count + index, None, run, settings))
        addition_records.append(replace(
            run, run_id=run_id, standard_order=base_count + index,
            run_order=base_count + index, settings=settings,
            measured_levels={key: None for key in run.measured_levels},
            responses={key: None for key in run.responses},
            batch_id=_BATCH_ID, source_run_id=run.run_id))
        run_map.append((run.run_id, run_id))

    from doe_core import randomized_run_order
    new_ids = [run.run_id for run in addition_records]
    shuffled = randomized_run_order(new_ids, spec.seed)
    actual_order = {run_id: base_count + index
                    for index, run_id in enumerate(shuffled, 1)}
    for row, record in zip(additions, addition_records):
        row[columns["run_order"]] = actual_order[record.run_id]
    addition_records = [replace(record, run_order=actual_order[record.run_id])
                        for record in addition_records]

    factor_map = {factor.factor_id: factor for factor in spec.factors}
    coded = [tuple(int(factor_map[key].to_coded(run.settings[key])) for key in factor_ids)
             for run in (*source_factorial, *addition_records)]
    defining, aliases = _matrix_structure(coded, factor_ids)
    source_hash = foldover_matrix_fingerprint(source_factorial, spec.factors)
    current_hash = foldover_matrix_fingerprint(
        (*source_factorial, *addition_records), spec.factors)
    tag = ("all" if folded == factor_ids else folded[0] if len(folded) == 1
           else "M" + "-".join(str(factor_ids.index(key) + 1) for key in folded))
    folded_spec = replace(
        spec, design_id=f"fold-{spec.design_id[:45]}-{tag}",
        construction_version="v2", defining_relations=defining, aliases=aliases,
        foldover_lineage={
            "parent_design_id": spec.design_id, "batch_id": _BATCH_ID,
            "folded_factors": folded, "run_map": tuple(run_map),
            "source_matrix_sha256": source_hash,
            "current_matrix_sha256": current_hash,
        })
    added_frame = pd.DataFrame(additions, columns=original.columns)
    result_frame = pd.concat((original, added_frame), ignore_index=True)
    result_frame = result_frame.sort_values(columns["run_order"], kind="stable").reset_index(drop=True)
    for factor_id, column in columns["factors"].items():
        result_frame[column] = result_frame[column].astype(object)
    for column in (*columns["measured_levels"].values(), *columns["responses"].values()):
        result_frame[column] = pd.array(result_frame[column], dtype="Float64")
    result_metadata = worksheet_metadata(result_frame, folded_spec, columns)
    validate_fractional_design(result_frame, result_metadata)
    return result_frame, result_metadata


def foldover_summary(frame, metadata):
    """从当前因子点矩阵返回别名组、全阶模型秩和正规分辨度。"""
    design = validate_fractional_design(frame, metadata)
    from doe_fractional_analysis import fractional_alias_groups
    groups = fractional_alias_groups(frame, metadata)
    defining = design.spec.defining_relations
    resolution = (min(len(relation.split("=", 1)[1].lstrip("-"))
                      for relation in defining) if defining else None)
    return {"model_rank": len(groups), "resolution": resolution,
            "defining_relations": defining, "alias_groups": groups}


def _unique_column(frame, base):
    names = set(frame.columns)
    candidate = base
    index = 2
    while candidate in names:
        candidate = f"{base} ({index})"
        index += 1
    return candidate


def _addition_row(frame, columns, run_id, standard_order, run_order, source, settings):
    row = {column: None for column in frame.columns}
    row[columns["run_id"]] = run_id
    row[columns["standard_order"]] = standard_order
    row[columns["run_order"]] = run_order
    row[columns["point_type"]] = source.point_type
    row[columns["replicate"]] = source.replicate
    if columns.get("block") is not None:
        row[columns["block"]] = source.block
    row.update({column: settings[factor_id]
                for factor_id, column in columns["factors"].items()})
    row[columns["batch_id"]] = _BATCH_ID
    row[columns["source_run_id"]] = source.run_id
    return row
