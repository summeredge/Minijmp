"""汇总已完成的 G19 原始样本；历史测量只标为参照，不推断退化。"""
import csv
import json
import math
import statistics
import sys
from collections import defaultdict
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]
sys.path.insert(0, str(ROOT/'tools'))
from benchmark_statistics import cases
from benchmark_g18 import SCENARIOS


def load(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def grouped(rows, key, value):
    result = defaultdict(list)
    for row in rows:
        if not row.get('warmup', False) and row.get('status', 'ok') == 'ok':
            result[key(row)].append(float(row[value]))
    return result


def check_repeats(rows, phases, field):
    assert {r['phase'] for r in rows} == set(phases)
    for phase in phases:
        selected = [r for r in rows if r['phase'] == phase]
        expected = ([1] if phase == 'cold_integral' else [1, 2, 3]
                    if phase == 'warm_cached_integral' else [0, 1, 2, 3])
        assert sorted(r['repeat'] for r in selected) == expected, phase
        assert all(r['warmup'] == (r['repeat'] == 0) and r.get('status', 'ok') == 'ok'
                   and math.isfinite(r[field]) and r[field] >= 0 for r in selected)


def main():
    output = []
    assert len(list(OUT.glob('statistics-F*.json'))) == 6
    assert len(list((OUT/'render-current').glob('*.json'))) == 12
    assert {p.stem for p in (OUT/'render-before').glob('*.json')} == {
        p.stem for p in (OUT/'render-current').glob('*.json')} - {'vendor'}
    planned = {r['id'] for r in load(OUT/'supplemental-scenarios.json')}
    assert {p.stem for p in (OUT/'supplemental/raw').glob('*.json')} == planned

    def add(family, scenario, n, p, phase, samples, evidence,
            before=(), kind='无有效基线', note=''):
        assert len(samples) == 3, (family, scenario, phase, samples)
        assert all(math.isfinite(x) and x >= 0 for x in samples)
        assert not before or len(before) == 3
        assert all(math.isfinite(x) and x >= 0 for x in before)
        row = dict(family=family, scenario=scenario, n=n, p=p, phase=phase,
                   repeats=len(samples), samples_s=json.dumps(samples),
                   median_s=statistics.median(samples), min_s=min(samples), max_s=max(samples),
                   baseline_kind=kind, baseline_samples_s=json.dumps(list(before)),
                   baseline_median_s=statistics.median(before) if len(before) >= 3 else '',
                   baseline_min_s=min(before) if before else '', baseline_max_s=max(before) if before else '',
                   current_over_baseline='', note=note, evidence=evidence)
        if len(before) >= 3 and statistics.median(before):
            row['current_over_baseline'] = row['median_s'] / statistics.median(before)
        output.append(row)

    with (ROOT/'docs/g16-evidence/performance.csv').open(encoding='utf-8-sig') as stream:
        history = {(r['name'], int(r['n']), int(r['p'])): json.loads(r['after_samples'])
                   for r in csv.DictReader(stream)}
    for path in sorted(OUT.glob('statistics-F*.json')):
        rows = load(path)['rows']
        assert sorted((r['name'], r['n'], r['p']) for r in rows) == sorted(cases(path.stem.split('-')[-1]))
        for row in rows:
            add('统计', row['name'], row['n'], row['p'], 'compute', row['samples'], path.name,
                history.get((row['name'], row['n'], row['p']), ()), 'G16历史优化后',
                'B-01：仅记录耗时，LR统计定义未通过验收' if row['name'] == 'p_likelihood_ratio' else
                '同输入历史参照；负载与调用边界须核对，不凭绝对差判定退化')

    path = OUT/'data/performance.csv'
    with path.open(encoding='utf-8-sig') as stream:
        rows = list(csv.DictReader(stream))
    for row in rows:
        row['warmup'] = row['warmup'] == 'True'
        row['repeat'] = int(row['repeat'])
        row['wall_seconds'] = float(row['wall_seconds'])
    expected_data = {(name, n, p, variant) for n in (1000, 10000, 50000, 100000)
                     for name in ('df_combine', 'number_2Dlist', 'find_exact', 'find_regex_base', 'csv_detect', 'csv_read')
                     for p in ([5, 20, 40] if name == 'number_2Dlist' and n == 10000 else [5])
                     for variant in ('after', 'before_compat_only' if name.startswith('find_') else 'before')}
    expected_data = {(name, n, 10 if name.startswith('csv_') else p, variant)
                     for name, n, p, variant in expected_data}
    assert {(r['case'], int(r['n']), int(r['p']), r['variant']) for r in rows} == expected_data
    for name, n, p, variant in expected_data:
        selected = [dict(r, phase='data_prepare') for r in rows if
                    (r['case'], int(r['n']), int(r['p']), r['variant']) == (name, n, p, variant)]
        check_repeats(selected, ['data_prepare'], 'wall_seconds')
    groups = grouped(rows, lambda r: (r['case'], int(r['n']), int(r['p']), r['variant']), 'wall_seconds')
    for (name, n, p, variant), samples in groups.items():
        if variant != 'after':
            continue
        baseline_variant = 'before_compat_only' if name.startswith('find_') else 'before'
        add('数据', name, n, p, 'data_prepare', samples, 'data/performance.csv',
            groups[(name, n, p, baseline_variant)], '本轮冻结旧实现配对',
            '搜索旧版仅修正 pandas API/mask dtype；校验在计时外')

    matrix = ['matrix_and_artists', 'agg_first_draw', 'agg_redraw']
    pages = ['tk_print_to_updated', 'tk_last_page_to_updated', 'gui_txt_save', 'tk_clear_to_updated']
    render_phases = dict.fromkeys(('matrix', 'matrix-orig'), matrix)
    render_phases.update({'matrix-tk': ['matrix_and_artists', 'tk_first_draw_to_updated', 'tk_redraw_to_updated'],
        'table': ['report_build'], 'spc': ['report_build'], 'excel': ['export_excel', 'txt_write'],
        'series': ['data_prepare', 'plot_build_including_prepare', 'agg_first_draw', 'agg_redraw', 'artist_build_prepared'],
        'series-tk': ['tk_plot_to_updated', 'tk_redraw_to_updated'], 'dialog': ['tk_dialog_apply_to_updated'],
        'reports': pages, 'wide': pages,
        'vendor': ['tk_vendor_viewer_create', 'tk_vendor_replot_to_updated', 'tk_vendor_plotCurrent_to_updated', 'tk_vendor_plot2D_to_updated']})
    assert {p.stem for p in (OUT/'render-current').glob('*.json')} == set(SCENARIOS)
    for path in sorted((OUT/'render-current').glob('*.json')):
        current = load(path)
        assert current['status'] == 'ok', path
        assert (current['n'], current['p']) == SCENARIOS[current['scenario']]
        check_repeats(current['rows'], render_phases[current['scenario']], 'seconds')
        before_path = OUT/'render-before'/path.name
        before = load(before_path) if before_path.exists() else None
        if before:
            assert before['status'] == 'ok'
            assert (before['n'], before['p'], before['scenario']) == (current['n'], current['p'], current['scenario'])
            check_repeats(before['rows'], render_phases[before['scenario']], 'seconds')
        old = grouped(before['rows'], lambda r: r['phase'], 'seconds') if before else {}
        for phase, samples in grouped(current['rows'], lambda r: r['phase'], 'seconds').items():
            add('报告绘图', current['scenario'], current['n'], current['p'], phase,
                samples, str(path.relative_to(OUT)), old.get(phase, ()),
                '本轮G18修改前重放' if before else '无有效旧版曲线基线',
                '同输入同脚本串行；before覆盖G18六模块，其余依赖使用当前集成代码')
        for field in ('pearson_seconds', 'axes_artists_and_report_seconds'):
            matrix_rows = [r for r in current['rows'] if field in r]
            if matrix_rows:
                old_rows = [r for r in before['rows'] if field in r] if before else []
                add('报告绘图', current['scenario'], current['n'], current['p'], field,
                    grouped(matrix_rows, lambda r: field, field)[field], str(path.relative_to(OUT)),
                    grouped(old_rows, lambda r: field, field).get(field, ()), '本轮G18修改前重放',
                    'Pearson累计实测；剩余值为总构建减Pearson，包含轴/Artist/报告及计时包装')

    cold = defaultdict(list)
    cold_pids = defaultdict(set)
    failures = []
    supplemental_plan = {r['id']: r for r in load(OUT/'supplemental-scenarios.json')}
    supplemental_phases = {'multi_fit': matrix, 'multi_fit_orig': matrix, 'report_gui': pages,
        'text_gui': ['tk_add_txt_to_updated'], 'pi_decode': ['pi_json_decode', 'pi_frame_validate'],
        'table_gui': ['tk_table_first_to_updated', 'tk_table_redraw_to_updated', 'tk_table_full_redraw_to_updated', 'tk_table_scroll_to_updated'],
        'vendor_plot': render_phases['vendor'], 'stat_table': ['report_build'],
        'calculate_d3': ['cold_integral', 'warm_cached_integral']}
    for path in sorted((OUT/'supplemental/raw').glob('*.json')):
        record = load(path)
        if record['status'] != 'ok':
            failures.append(dict(file=path.name, status=record['status'], stage=record.get('stage')))
            continue
        scenario = record['scenario']
        assert record['stage'] == 'complete' and scenario == supplemental_plan[path.stem]
        check_repeats(record['rows'], supplemental_phases.get(scenario['name'], ['compute']), 'wall_seconds')
        for phase, samples in grouped(record['rows'], lambda r: r['phase'], 'wall_seconds').items():
            if phase == 'cold_integral':
                cold[(scenario['name'], scenario['n'], phase)].extend(samples)
                cold_pids[scenario['n']].add(record['pid'])
                continue
            add('补充', scenario['id'], scenario['n'], scenario.get('p', 1), phase,
                samples, str(path.relative_to(OUT)), note='G15原场景参数；不将其他规模等同于本场景')
    for (name, n, phase), samples in cold.items():
        add('补充', name, n, 1, phase, samples, 'supplemental/raw/calculate_d3-*.json',
            note='三个独立进程各一次冷积分；暖缓存阶段分开统计')
    assert not failures, failures
    assert set(cold_pids) == {r['n'] for r in supplemental_plan.values() if r['name'] == 'calculate_d3'}
    assert all(len(pids) == 3 for pids in cold_pids.values())
    assert output and len({(r['family'], r['scenario'], r['n'], r['p'], r['phase']) for r in output}) == len(output)
    with (OUT/'G19-performance-results.csv').open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(output[0]))
        writer.writeheader()
        writer.writerows(output)
    (OUT/'performance-summary.json').write_text(json.dumps(dict(
        valid_phases=len(output), samples=sum(r['repeats'] for r in output), failures=failures),
        ensure_ascii=False, indent=2), encoding='utf-8')
    (OUT/'performance-integrity.json').write_text(json.dumps(dict(
        statistics_cases=sum(len(cases(f'F{n:02}')) for n in (1, 11, 2, 4, 6, 8)),
        data_paired_cases=len(expected_data)//2, render_current=len(SCENARIOS), render_before=len(SCENARIOS)-1,
        supplemental=len(supplemental_plan), exact_repeat_ids=True, finite_samples=True,
        planned_phases_complete=True, cold_distinct_processes={str(n): len(pids) for n, pids in cold_pids.items()}),
        ensure_ascii=False, indent=2), encoding='utf-8')
    print(len(output), 'valid phases;', len(failures), 'incomplete scenarios')


if __name__ == '__main__':
    assert grouped([dict(warmup=True, seconds=9), dict(seconds=1)], lambda r: 'p', 'seconds') == {'p': [1.]}
    sample = [dict(phase='compute', repeat=i, warmup=i == 0, seconds=1.) for i in range(4)]
    check_repeats(sample, ['compute'], 'seconds')
    for bad in (sample[:-1], [sample[0], sample[1], sample[1], sample[3]],
                [dict(row, seconds=float('inf')) for row in sample]):
        try:
            check_repeats(bad, ['compute'], 'seconds')
        except AssertionError:
            pass
        else:
            raise AssertionError('Invalid performance samples accepted')
    main()
