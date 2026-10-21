"""G17：复用 G15 输入，冻结旧函数与当前函数交替测量；失败不计作耗时。"""
import argparse
import codecs
import csv
import gc
import hashlib
import inspect
import io
import json
import os
from pathlib import Path
import platform
import re
import statistics
import sys
import time
from types import SimpleNamespace

# Match G15's single-thread numerical environment before importing libraries.
for variable in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS'):
    os.environ[variable] = '1'
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'code'))
import numpy as np
import pandas as pd
from pandas.testing import assert_frame_equal
from df_combine import df_combine
from dialog import findRepDialog
from pandastable_local.dialogs import FindReplaceDialog
from pandastable_local import csv_import
from utilities import is_void, number_2Dlist, transpose_2D_list


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'docs/g17-evidence')
    parser.add_argument('--rows', nargs='+', type=int, default=[1000, 10000, 50000, 100000])
    parser.add_argument('--cases', nargs='+', choices=['df_combine', 'number_2Dlist', 'find_exact',
                        'find_regex_base', 'csv_detect', 'csv_read'], help='仅复测指定路径')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    frozen_path = ROOT / 'tests/fixtures/g17_before.json'
    frozen = json.loads(frozen_path.read_text(encoding='utf-8'))
    namespace = dict(pd=pd, np=np, codecs=codecs, csv=csv, io=io, re=re, Path=Path,
                     NUMBER=csv_import.NUMBER, DELIMITERS=csv_import.DELIMITERS,
                     is_void=is_void, transpose_2D_list=transpose_2D_list)
    for key, source in frozen.items():
        if key.startswith('pandastable_local/csv_import.py:'):
            exec(source, namespace)
    old_csv = namespace.copy()

    def old(key, compatibility=False):
        source = frozen[key]
        if compatibility:
            source = source.replace('found = df.copy()', 'found = df.astype(object).copy()')
            source = source.replace('row.iteritems()', 'row.items()')
        scope = namespace.copy()
        exec(source, scope)
        return scope[key.split(':')[-1]]

    old_combine = old('df_combine.py:df_combine')
    old_numbers = old('utilities.py:number_2Dlist')
    old_exact = old('dialog.py:find', True)
    old_regex = old('pandastable_local/dialogs.py:find', True)

    functions = [df_combine, number_2Dlist, findRepDialog.find, FindReplaceDialog.find,
                 csv_import.detect_csv, csv_import.read_csv, csv_import.read_records]
    metadata = dict(seed=20261021, python=sys.executable, version=sys.version,
                    platform=platform.platform(), pandas=pd.__version__, numpy=np.__version__,
                    frozen_sha256=hashlib.sha256(frozen_path.read_bytes()).hexdigest(),
                    function_sha256={f'{f.__module__}.{f.__qualname__}': hashlib.sha256(
                        inspect.getsource(f).encode()).hexdigest() for f in functions},
                    timing='perf_counter / process_time; GC before timer; setup and equality outside timer',
                    samples='repeat 0 warmup; 1-3 formal; paired variant order alternates',
                    search_baseline='old exact find: only mask dtype changed to object; base: iteritems to items')
    (args.output / 'benchmark-environment.json').write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    measurements, summaries = [], []
    fields = ['case', 'n', 'p', 'variant', 'repeat', 'warmup', 'wall_seconds', 'cpu_seconds', 'status']
    with (args.output / 'performance.csv').open('w', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()

        def compare(name, n, p, before, after, check, baseline='before'):
            if args.cases and name not in args.cases:
                return
            results = {}
            for repeat in range(4):
                pending = []
                variants = [(baseline, before), ('after', after)]
                if repeat % 2:
                    variants.reverse()
                for variant, function in variants:
                    gc.collect()
                    start_cpu, start = time.process_time(), time.perf_counter()
                    result = function()
                    elapsed, cpu = time.perf_counter() - start, time.process_time() - start_cpu
                    row = dict(case=name, n=n, p=p, variant=variant, repeat=repeat,
                               warmup=repeat == 0, wall_seconds=elapsed, cpu_seconds=cpu, status='ok')
                    pending.append(row)
                    results[variant] = result
                check(results[baseline], results['after'])
                writer.writerows(pending)
                stream.flush()
                measurements.extend(pending)
            medians = {v: statistics.median(r['wall_seconds'] for r in measurements
                       if (r['case'], r['n'], r['p'], r['variant']) == (name, n, p, v) and not r['warmup'])
                       for v in (baseline, 'after')}
            summaries.append(dict(case=name, n=n, p=p, baseline=baseline,
                                  before_seconds=medians[baseline], after_seconds=medians['after'],
                                  speedup=medians[baseline] / medians['after']))
            (args.output / 'performance-summary.json').write_text(
                json.dumps(summaries, indent=2) + '\n', encoding='utf-8')
            print(json.dumps(summaries[-1]), flush=True)

        def same(a, b):
            assert a == b

        def search(frame, cls):
            obj = SimpleNamespace(table=SimpleNamespace(model=SimpleNamespace(df=frame)),
                                  searchvar=SimpleNamespace(get=lambda: '42'),
                                  casevar=SimpleNamespace(get=lambda: True), clear=lambda: None)
            cls(obj)
            return obj.table.highlighted, obj.coords

        def same_search(a, b):
            assert_frame_equal(a[0].astype(bool), b[0])
            assert a[1] == b[1]

        for n in args.rows:
            # G15 consumes this normal vector before constructing each scenario's data.
            def rng():
                generator = np.random.default_rng(20261021)
                generator.normal(10, 1, n).tolist()
                return generator

            frame = pd.DataFrame(rng().normal(size=(n, 5)))
            patch = frame.iloc[:max(1, n // 10)].copy()
            compare('df_combine', n, 5,
                    lambda: old_combine(frame, patch, ins_y=n // 2),
                    lambda: df_combine(frame, patch, ins_y=n // 2), assert_frame_equal)
            for p in ([5, 20, 40] if n == 10000 else [5]):
                frame = pd.DataFrame(rng().normal(size=(n, p)), columns=[f'V{i}' for i in range(p)])
                columns = list(frame)
                compare('number_2Dlist', n, p,
                        lambda: old_numbers(frame, columns),
                        lambda: number_2Dlist(frame, columns), same)
            frame = pd.DataFrame(rng().integers(0, 100, size=(n, 5)))
            for name, before, current in [('find_exact', old_exact, findRepDialog.find),
                                           ('find_regex_base', old_regex, FindReplaceDialog.find)]:
                compare(name, n, 5, lambda: search(frame, before),
                        lambda: search(frame, current), same_search, 'before_compat_only')
            path = args.output / 'benchmark-input.csv'
            pd.DataFrame(rng().normal(size=(n, 10)), columns=[f'V{i}' for i in range(10)]).to_csv(path, index=False)
            options = csv_import.detect_csv(path)
            assert options == old_csv['detect_csv'](path)
            compare('csv_detect', n, 10, lambda: old_csv['detect_csv'](path),
                    lambda: csv_import.detect_csv(path), same)
            options.pop('confirm')
            compare('csv_read', n, 10, lambda: old_csv['read_csv'](path, **options),
                    lambda: csv_import.read_csv(path, **options), assert_frame_equal)
            path.unlink()


if __name__ == '__main__':
    main()
