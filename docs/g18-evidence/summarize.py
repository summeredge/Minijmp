"""合并 G15 原始样本与 G18 前后三轮有效计时，不包含预热/profile/试验版本。"""
import csv
import json
from pathlib import Path
from statistics import median

OUT = Path(__file__).resolve().parent
G15 = {'matrix': 'multi_fit-n1000-p20', 'matrix-orig': 'multi_fit_orig-n1000-p20',
       'table': 'stat_table-n50000-p7', 'spc': 'spc_report-n50000-p1',
       'excel': 'exports-n50000-p7', 'series': 'time_series-n100000-p3',
       'series-tk': 'time_series_tk-n50000-p3', 'dialog': 'time_series_dialog-n50000-p3',
       'reports': 'report_gui-n100-p7-c20', 'wide': 'report_gui-n100-p100'}


def main():
    summary = []
    for source in ('g15', 'baseline', 'after'):
        names = list(G15)
        if source != 'g15':
            names.append('matrix-tk')
        if source == 'after':
            names.append('vendor')
        for name in names:
            path = OUT/source/((G15[name] if source == 'g15' else name)+'.json')
            data = json.loads(path.read_text(encoding='utf-8'))
            assert data['status'] == 'ok', (path, data['status'])
            rows = [r for r in data['rows'] if not r['warmup']]
            for phase in dict.fromkeys(r['phase'] for r in rows):
                samples = [r for r in rows if r['phase'] == phase]
                assert len(samples) == 3 and {r['repeat'] for r in samples} == {1, 2, 3}, (path, phase)
                seconds = [r['wall_seconds' if source == 'g15' else 'seconds'] for r in samples]
                peaks = [r['process_peak_rss_mib'] if source == 'g15' else r['memory_mib']['PeakWorkingSetSize'] for r in samples]
                summary.append(dict(source=source, scenario=name, phase=phase, repeats=3,
                    median_s=median(seconds), min_s=min(seconds), max_s=max(seconds),
                    cpu_median_s=median(r['cpu_seconds'] for r in samples), peak_process_mib=max(peaks)))
                if phase == 'matrix_and_artists' and source != 'g15':
                    for metric in ('pearson_seconds', 'axes_artists_and_report_seconds'):
                        durations = [r[metric] for r in samples]
                        summary.append(dict(source=source, scenario=name, phase=metric, repeats=3,
                            median_s=median(durations), min_s=min(durations), max_s=max(durations),
                            cpu_median_s='', peak_process_mib=''))
    with (OUT/'performance.csv').open('w', newline='', encoding='utf-8-sig') as output:
        writer = csv.DictWriter(output, fieldnames=list(summary[0]))
        writer.writeheader()
        writer.writerows(summary)
    lookup = {(r['source'], r['scenario'], r['phase']): r for r in summary}
    text = ['| 场景 | 阶段 | G15 中位秒 | G18 前 中位秒 [最小, 最大] | G18 后 中位秒 [最小, 最大] |',
            '| --- | --- | ---: | ---: | ---: |']
    for row in summary:
        if row['source'] != 'after':
            continue
        key = row['scenario'], row['phase']
        before = lookup.get(('baseline', *key))
        g15 = lookup.get(('g15', *key))

        def cell(value):
            return f"{value['median_s']:.4f} [{value['min_s']:.4f}, {value['max_s']:.4f}]" if value else '未测得'

        g15_cell = f"{g15['median_s']:.4f}" if g15 else '未测得'
        text.append(f"| {key[0]} | {key[1]} | {g15_cell} | {cell(before)} | {cell(row)} |")
    (OUT/'performance.md').write_text('\n'.join(text)+'\n', encoding='utf-8')
    print(f'{len(summary)} stage summaries; every stage has 3 valid samples')


if __name__ == '__main__':
    main()
