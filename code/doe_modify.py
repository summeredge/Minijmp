"""修改现有 DOE：显示顺序与合法重新随机化；不改因子设定、响应或谱系。"""
from collections import defaultdict, deque
from dataclasses import replace

import pandas as pd

from doe_core import restore_design_result, worksheet_metadata


def _supported(spec):
    if spec.foldover_lineage is not None:
        return 'foldover'
    if spec.design_type == 'split_plot':
        return 'split_plot'
    if spec.design_type in ('custom_factorial', 'custom_rsm', 'custom_screening'):
        return 'custom'
    if spec.design_type in ('two_level_full', 'two_level_fractional',
                            'general_full_factorial'):
        return 'factorial'
    if spec.design_type in ('central_composite', 'box_behnken'):
        return 'rsm'
    if spec.design_type in ('plackett_burman', 'definitive_screening'):
        return 'screening'
    return None


def _reject_folded_screening(spec, action):
    """PB Foldover 的原始/新增批次运行身份不可被通用修改改写。"""
    if spec.foldover_lineage is not None and spec.design_type == 'plackett_burman':
        raise ValueError(
            f'已折叠的 Plackett–Burman 设计不支持{action}；'
            '原始批次与折叠批次的运行身份必须保留')


def reorder(frame, metadata, *, by='standard'):
    """仅改变工作表行显示顺序；运行 ID、设定、响应与顺序字段保持不变。"""
    if by not in ('standard', 'run'):
        raise ValueError('显示顺序必须是 standard 或 run')
    if metadata.get('design', {}).get('design_type') == 'split_plot':
        from doe_splitplot import validate_split_plot_design
        design = validate_split_plot_design(frame, metadata)
    else:
        design = restore_design_result(frame, metadata)
    column = metadata['column_map']['standard_order' if by == 'standard' else 'run_order']
    result = frame.sort_values(column, kind='stable').reset_index(drop=True)
    return result, worksheet_metadata(result, design.spec, metadata['column_map'])


def _order_ids(run_ids, seed, family, spec, blocks):
    """按各族构造期使用的同一随机化规则重算运行序，不发明新规则。"""
    if family == 'factorial':
        if spec.design_type == 'general_full_factorial':
            from doe_general_factorial import _ordered_run_ids
            replicates = len({run.replicate for run in blocks['runs']})
            levels = len(run_ids) // replicates
            return _ordered_run_ids(replicates, levels, seed, spec.block_count)
        if spec.block_count is None:
            from doe_core import randomized_run_order
            return randomized_run_order(run_ids, seed)
        from doe_factorial import _blocked_order
        groups = {}
        for run in blocks['runs']:
            groups.setdefault(run.replicate, []).append(run.run_id)
        return _blocked_order(groups, seed)
    if family == 'foldover':
        from doe_core import randomized_run_order
        lineage = spec.foldover_lineage
        base = [run.run_id for run in blocks['runs'] if run.batch_id == 'BASE']
        added = [run.run_id for run in blocks['runs']
                 if run.batch_id == lineage['batch_id']]
        count = len(base)
        ordered = list(randomized_run_order(base, seed))
        ordered += list(randomized_run_order(added, seed))
        return tuple(ordered)
    if family == 'rsm':
        from doe_core import randomized_run_order
        order = {}
        sequence = 1
        for block in range(spec.block_count or 1):
            ids = [run.run_id for run in blocks['runs']
                   if (run.block or 1) == block + 1]
            for run_id in randomized_run_order(ids, seed + block):
                order[run_id] = sequence
                sequence += 1
        return tuple(sorted(order, key=order.get))
    if family == 'screening':
        from doe_core import randomized_run_order
        if spec.design_type == 'plackett_burman' and spec.block_count is None:
            return randomized_run_order(run_ids, seed)
        import random
        rng = random.Random(seed)
        groups = {}
        for run in blocks['runs']:
            groups.setdefault(run.block if run.block is not None else 1,
                              []).append(run.run_id)
        result = []
        for block in sorted(groups):
            group = groups[block]
            rng.shuffle(group)
            result.extend(group)
        return tuple(result)
    if family == 'custom':
        from doe_core import randomized_run_order
        return randomized_run_order(run_ids, seed)
    raise ValueError('该设计类型不支持重新随机化')


def rerandomize(frame, metadata, seed):
    """用新 seed 重新随机化运行序；返回新工作表与元数据。"""
    if metadata.get('design', {}).get('design_type') == 'split_plot':
        from doe_splitplot import validate_split_plot_design
        design = validate_split_plot_design(frame, metadata)
    else:
        design = restore_design_result(frame, metadata)
    spec = design.spec
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise ValueError('seed 必须是整数')
    family = _supported(spec)
    if family is None:
        raise ValueError('该设计类型不支持重新随机化')
    _reject_folded_screening(spec, '重新随机化')
    if family == 'split_plot':
        if design.spec.augmentation_lineage is not None:
            raise ValueError('已增补的 Split-Plot 为保留历史顺序，不支持重新随机化')
    runs = tuple(sorted(design.runs, key=lambda run: run.standard_order))
    run_ids = [run.run_id for run in runs]
    if len(set(map(str, run_ids))) != len(run_ids):
        raise ValueError('运行 ID 重复，无法安全重新随机化')
    if family == 'split_plot':
        from doe_splitplot import _layout
        _, _, actual = _layout(replace(spec, seed=seed))
        by_standard = {item['standard_order']: item for item in actual}
        order = {run.run_id: by_standard[run.standard_order]['run_order']
                 for run in runs}
        whole = {run.run_id: by_standard[run.standard_order]['whole_plot_order']
                 for run in runs}
        sub = {run.run_id: by_standard[run.standard_order]['subplot_order']
               for run in runs}
    else:
        order = {run_id: position for position, run_id in enumerate(
            _order_ids(run_ids, seed, family, spec, {'runs': runs}), 1)}
        whole = sub = None
    columns = metadata['column_map']
    result = frame.copy(deep=True)
    run_column = columns['run_id']
    if result[run_column].isna().any():
        raise ValueError('运行 ID 存在缺失值')
    keys = result[run_column].tolist()
    if any(key not in order for key in keys):
        raise ValueError('工作表运行 ID 与设计定义不一致')
    result[columns['run_order']] = [order[key] for key in keys]
    if whole is not None:
        result[columns['whole_plot_order']] = [whole[key] for key in keys]
        result[columns['subplot_order']] = [sub[key] for key in keys]
    result = result.sort_values(columns['run_order'], kind='stable').reset_index(drop=True)
    result_metadata = worksheet_metadata(result, replace(spec, seed=seed), columns)
    return result, result_metadata


def modify_summary(frame, metadata):
    """修改前后可观察信息：运行数、顺序与是否可重新随机化。"""
    if metadata.get('design', {}).get('design_type') == 'split_plot':
        from doe_splitplot import validate_split_plot_design
        design = validate_split_plot_design(frame, metadata)
    else:
        design = restore_design_result(frame, metadata)
    family = _supported(design.spec)
    split_augmented = (design.spec.design_type == 'split_plot'
                       and design.spec.augmentation_lineage is not None)
    append_unsupported = (design.spec.design_type == 'split_plot'
                          and metadata.get('design', {}).get(
                              'schema_version', design.spec.schema_version) < 5)
    pb_folded = (design.spec.design_type == 'plackett_burman'
                 and design.spec.foldover_lineage is not None)
    reason = (
        '已折叠的 Plackett–Burman 设计保留原始与折叠批次身份；重新随机化、'
        '重编号与增补均已禁用。'
        if pb_folded else
        'Split-Plot 只支持一次区组增补；重新随机化会改写历史顺序。'
        if split_augmented else
        '该 Schema v4 Split-Plot 缺少可验证增补谱系，不能安全增加区组。'
        if append_unsupported else None)
    if reason is None and not spec_allows_replicate(design.spec):
        reason = '该设计类型、混杂区组或已有批次谱系不支持增加完整重复。'
    if reason is None and not _supports_renumber(design.spec):
        reason = '该设计区组规范不支持按标准序重编号；请使用重新随机化。'
    return {'design_type': design.spec.design_type, 'runs': len(design.runs),
            'seed': design.spec.seed, 'family': family,
            'can_rerandomize': (family is not None and not split_augmented
                                and not pb_folded),
            'can_reorder': True,
            'can_renumber': _supports_renumber(design.spec),
            'can_replicate': (spec_allows_replicate(design.spec)
                              and not append_unsupported),
            'unavailable_reason': reason}


def spec_allows_replicate(spec):
    """受支持家族与自定义点集可追加重复，已有批次谱系保持独立。"""
    return (
        spec.design_type in {
            'two_level_full', 'two_level_fractional', 'general_full_factorial',
            'central_composite', 'box_behnken', 'plackett_burman',
            'definitive_screening', 'split_plot',
            'custom_factorial', 'custom_rsm', 'custom_screening',
        }
        and spec.foldover_lineage is None
        and spec.augmentation_lineage is None
        and not (spec.design_type == 'two_level_full'
                 and spec.confounded_block_generators)
    )


def _supports_renumber(spec):
    return (spec.design_type in {
        'two_level_full', 'two_level_fractional', 'general_full_factorial',
        'central_composite', 'box_behnken', 'plackett_burman',
        'definitive_screening', 'custom_factorial', 'custom_rsm', 'custom_screening',
    } and not (spec.design_type == 'plackett_burman' and spec.foldover_lineage is not None)
        and not (spec.design_type == 'box_behnken'
                 and spec.block_count not in (None, 1)))


def _validate_family_design(frame, metadata):
    design = restore_design_result(frame, metadata)
    design_type = design.spec.design_type
    if design_type == 'two_level_full':
        from doe_factorial import validate_factorial_design
        return validate_factorial_design(frame, metadata)
    if design_type == 'two_level_fractional':
        from doe_fractional import validate_fractional_design
        return validate_fractional_design(frame, metadata)
    if design_type == 'general_full_factorial':
        from doe_general_factorial import validate_general_factorial
        return validate_general_factorial(frame, metadata)
    if design_type == 'central_composite':
        from doe_ccd import validate_ccd
        validate_ccd(design)
    elif design_type == 'box_behnken':
        from doe_bbd import validate_bbd
        validate_bbd(design, frame)
    elif design_type == 'plackett_burman':
        from doe_pb import validate_pb
        validate_pb(design)
    elif design_type == 'definitive_screening':
        from doe_dsd import validate_dsd
        validate_dsd(design)
    elif design_type.startswith('custom_'):
        from doe_custom import validate_custom
        validate_custom(design, require_estimable=False)
    else:
        raise ValueError('该设计类型不支持此修改')
    return design


def _rename_generated_columns(frame, generated_map, columns):
    rename = {}
    for key in ('run_id', 'standard_order', 'run_order', 'point_type',
                'replicate', 'block'):
        if generated_map.get(key) is not None and columns.get(key) is not None:
            rename[generated_map[key]] = columns[key]
    for group in ('factors', 'measured_levels', 'responses'):
        for key, generated_column in generated_map.get(group, {}).items():
            target = columns.get(group, {}).get(key)
            if target is not None:
                rename[generated_column] = target
    return frame.rename(columns=rename)


def _observation_array(values, dtype):
    # 新增缺失值不能把整数观测经浮点中转，也应保持表格的数值编辑行为。
    if dtype.kind in 'iu' and not isinstance(dtype, pd.api.extensions.ExtensionDtype):
        dtype = 'Int64' if dtype.kind == 'i' else 'UInt64'
    return pd.array(values, dtype=dtype)


def _preserve_observations(frame, generated, metadata, source_design, generated_metadata):
    """按设计点匹配原观测；中心点移位或同点多次出现时也不串响应。"""
    generated_design = restore_design_result(generated, generated_metadata)
    columns = metadata['column_map']
    generated = _rename_generated_columns(
        generated, generated_metadata['column_map'], columns)
    def point_key(run):
        return (run.point_type, run.replicate, run.block,
                tuple(run.settings[f.factor_id] for f in source_design.spec.factors))

    source_rows = defaultdict(deque)
    for index, run in sorted(enumerate(source_design.runs),
                             key=lambda item: item[1].standard_order):
        source_rows[point_key(run)].append(index)
    matches_by_id = {}
    for run in sorted(generated_design.runs, key=lambda run: run.standard_order):
        rows = source_rows[point_key(run)]
        matches_by_id[run.run_id] = rows.popleft() if rows else None
    matches = [matches_by_id[run.run_id] for run in generated_design.runs]
    if any(source_rows.values()):
        raise ValueError('新增重复不能保留全部原设计点')
    result = generated.reindex(columns=frame.columns).copy()
    preserve = set(columns['responses'].values()) | set(
        columns['measured_levels'].values())
    preserve.update(column for column in frame.columns if column not in generated.columns)
    for column in preserve:
        values = [frame.iloc[index][column] if index is not None else None
                  for index in matches]
        result[column] = _observation_array(values, frame[column].dtype)
    result_metadata = worksheet_metadata(
        result, generated_design.spec, columns)
    _validate_family_design(result, result_metadata)
    return result, result_metadata


def renumber(frame, metadata):
    """按标准序重写运行序 1..n：保留设定、响应、重复与批次，不改设计身份。"""
    design = restore_design_result(frame, metadata)
    _reject_folded_screening(design.spec, '按标准序重编号')
    if design.spec.design_type == 'split_plot':
        raise ValueError('Split-Plot 运行序必须与 seed 随机化一致；请用“重新随机化”更换顺序')
    if not _supports_renumber(design.spec):
        raise ValueError('该设计的区组或批次规范不支持按标准序重编号；请使用重新随机化')
    _validate_family_design(frame, metadata)
    columns = metadata['column_map']
    by_standard = {run.run_id: run.standard_order for run in design.runs}
    result = frame.copy(deep=True)
    keys = result[columns['run_id']].tolist()
    if any(by_standard.get(key) is None for key in keys):
        raise ValueError('工作表运行 ID 与设计定义不一致')
    result[columns['run_order']] = [by_standard[key] for key in keys]
    if columns.get('whole_plot_order') is not None:
        # 裂区整区顺序随标准序重置，保持整区/子区嵌套。
        result[columns['whole_plot_order']] = [
            by_standard[run.run_id] for run in design.runs]
        result[columns['subplot_order']] = [run.subplot_order for run in design.runs]
    result = result.sort_values(columns['run_order'], kind='stable').reset_index(drop=True)
    updated = worksheet_metadata(result, design.spec, columns)
    _validate_family_design(result, updated)
    return result, updated


def replicate(frame, metadata, *, count=2, seed=None):
    """由家族生成器追加 count 个基础重复，原观测按设计点保留。"""
    if metadata.get('design', {}).get('design_type') == 'split_plot':
        from doe_splitplot import append_split_plot_blocks
        return append_split_plot_blocks(frame, metadata, count, seed=seed)
    design = _validate_family_design(frame, metadata)
    spec = design.spec
    if not spec_allows_replicate(spec):
        raise ValueError('该设计类型、混杂区组或折叠/增补规范不支持完整重复')
    if isinstance(count, bool) or not isinstance(count, int) or count < 1:
        raise ValueError('重复数量必须是正整数')
    columns = metadata['column_map']
    spec = replace(spec, seed=spec.seed if seed is None else seed)
    kind = spec.design_type
    if kind.startswith('custom_'):
        if len(frame) * (count + 1) > 10000:
            raise ValueError('运行总数不能超过 10000')
        current = max(run.replicate for run in design.runs)
        pieces = [frame.copy(deep=True)]
        for offset in range(1, count + 1):
            addition = frame.copy(deep=True)
            addition[columns['replicate']] += current * offset
            addition[columns['run_id']] = [
                f'{run.run_id}-R{run.replicate + current * offset}' for run in design.runs]
            for key in ('standard_order', 'run_order'):
                addition[columns[key]] = range(len(frame) * offset + 1,
                                                len(frame) * (offset + 1) + 1)
            for column in (*columns['responses'].values(), *columns['measured_levels'].values()):
                addition[column] = None
            pieces.append(addition)
        result = pd.concat(pieces, ignore_index=True)
        for column in (*columns['responses'].values(), *columns['measured_levels'].values()):
            result[column] = _observation_array(
                frame[column].tolist() + [None] * (len(frame) * count), frame[column].dtype)
        updated = worksheet_metadata(result, spec, columns)
        _validate_family_design(result, updated)
        return result, updated
    runs = [run for run in design.runs if run.point_type != 'center']
    current = max(run.replicate for run in runs)
    total = current + count
    measured = bool(columns['measured_levels'])
    if kind in ('two_level_full', 'two_level_fractional', 'general_full_factorial'):
        if spec.block_count is not None:
            spec = replace(spec, block_count=total)
        if kind == 'general_full_factorial':
            from doe_general_factorial import create_general_factorial
            generated, updated = create_general_factorial(spec, total, measured)
        else:
            from doe_factorial import create_factorial
            from doe_fractional import create_fractional
            centers = sum(run.point_type == 'center' for run in design.runs)
            if spec.block_count is not None:
                centers = centers // current * total
            else:
                centers *= count + 1
            if kind == 'two_level_fractional':
                spec = replace(spec, center_point_count=centers)
            create = create_factorial if kind == 'two_level_full' else create_fractional
            generated, updated = create(spec, total, centers, measured)
    elif kind == 'plackett_burman':
        from doe_pb import create_pb
        size = int(spec.screening_matrix['construction_id'].split('.')[0][2:])
        categories = 2 ** sum(f.factor_type == 'categorical' for f in spec.factors)
        centers = (len(design.runs) // current - size) // categories
        generated, updated = create_pb(spec, size, total, measured, centers,
                                       spec.block_count is not None)
    elif kind == 'definitive_screening':
        from doe_dsd import create_dsd
        generated, updated = create_dsd(spec, total, measured,
                                        spec.block_count or 1, spec.center_point_count)
    elif kind == 'box_behnken':
        from doe_bbd import create_bbd
        generated, updated = create_bbd(spec, total, measured)
    else:
        from doe_ccd import create_ccd
        spec = replace(spec, ccd_axial_points=spec.ccd_axial_points // current * total)
        if spec.block_count in (None, 1):
            spec = replace(spec, ccd_center_points=spec.ccd_center_points * (count + 1))
        generated, updated = create_ccd(spec, total, measured)
    return _preserve_observations(frame, generated, metadata, design, updated)
