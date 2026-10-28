"""修改现有 DOE：显示顺序与合法重新随机化；不改因子设定、响应或谱系。"""
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


def reorder(frame, metadata, *, by='standard'):
    """仅改变工作表行显示顺序；运行 ID、设定、响应与顺序字段保持不变。"""
    if by not in ('standard', 'run'):
        raise ValueError('显示顺序必须是 standard 或 run')
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
    design = restore_design_result(frame, metadata)
    spec = design.spec
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise ValueError('seed 必须是整数')
    family = _supported(spec)
    if family is None:
        raise ValueError('该设计类型不支持重新随机化')
    runs = design.runs
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
    design = restore_design_result(frame, metadata)
    family = _supported(design.spec)
    return {'design_type': design.spec.design_type, 'runs': len(design.runs),
            'seed': design.spec.seed, 'family': family,
            'can_rerandomize': family is not None,
            'can_reorder': True, 'can_renumber': True,
            'can_replicate': spec_allows_replicate(design.spec)}


def spec_allows_replicate(spec):
    """折叠/增补设计已有批次谱系，不叠加完整重复。"""
    return spec.foldover_lineage is None and spec.augmentation_lineage is None


def renumber(frame, metadata):
    """按标准序重写运行序 1..n：保留设定、响应、重复与批次，不改设计身份。"""
    design = restore_design_result(frame, metadata)
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
    return result, worksheet_metadata(result, design.spec, columns)


def replicate(frame, metadata, *, count=2, seed=None):
    """追加完整重复：复制全部设计点一次，新重复编号、新运行 ID、响应留空。"""
    design = restore_design_result(frame, metadata)
    spec = design.spec
    if not spec_allows_replicate(spec):
        raise ValueError('折叠或增补设计不提供完整重复')
    if isinstance(count, bool) or not isinstance(count, int) or count < 1:
        raise ValueError('重复数量必须是正整数')
    columns = metadata['column_map']
    if len(design.runs) * (count + 1) > 10000:
        raise ValueError('运行总数不能超过 10000')
    base = frame.copy(deep=True).reset_index(drop=True)
    current = max(run.replicate for run in design.runs)
    existing = {str(run.run_id) for run in design.runs}
    order = max(run.run_order for run in design.runs)
    rows = []
    for offset in range(count):
        number = current + offset + 1
        for index, run in enumerate(design.runs):
            rows.append({
                columns['run_id']: f'{run.run_id}-R{number}',
                columns['standard_order']: len(design.runs) * (offset + 1) + index + 1,
                columns['run_order']: order + len(rows) + 1,
                columns['point_type']: run.point_type,
                columns['replicate']: number,
                **{column: run.settings[factor_id]
                   for factor_id, column in columns['factors'].items()},
                **{column: None for column in columns['responses'].values()},
            })
    if existing & {row[columns['run_id']] for row in rows}:
        raise ValueError('新增运行 ID 与已有运行冲突')
    result = pd.concat([base, pd.DataFrame(rows)], ignore_index=True)
    for column in base.columns:
        if column not in result:
            result[column] = None
    result = result[base.columns.tolist()]
    # 保留原响应列类型：concat 引入的 None 不应把数值列降级为 object。
    for column in columns['responses'].values():
        result[column] = pd.array(result[column], dtype=base[column].dtype
                                  if base[column].dtype != object else object)
    return result, worksheet_metadata(result, replace(spec, seed=seed
                                                     if seed is not None else spec.seed),
                                      columns)
