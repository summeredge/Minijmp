"""G18 分阶段基准；同 G15 输入、一次预热及三次正式测量。

用项目解释器运行，--source-dir 可重放 docs/g18-evidence/before。
每个场景使用独立进程；GUI 指标计至真实 Tk update 完成。
vendor 仅验收当前源码；G15 空图失败不作为有效基线计时。
"""
import argparse
import gc
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
SCENARIOS = {
    'matrix': (1000, 20), 'matrix-orig': (1000, 20), 'matrix-tk': (1000, 10),
    'table': (50000, 7), 'spc': (50000, 1), 'excel': (50000, 7),
    'series': (100000, 3), 'series-tk': (50000, 3),
    'dialog': (50000, 3), 'reports': (100, 7), 'wide': (100, 100),
    'vendor': (1000, 3),
}


def worker(args):
    sys.path[:0] = [str(args.source_dir), str(ROOT / 'code')]
    import numpy as np
    import pandas as pd
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import tkinter as tk
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from benchmark_report_rendering import memory

    n, p = SCENARIOS[args.scenario]
    rng = np.random.default_rng(20261021)
    data = rng.normal(10, 1, n).tolist()  # G15 在每个场景预先生成此输入。
    result = {'scenario': args.scenario, 'n': n, 'p': p, 'seed': 20261021,
              'python': sys.executable, 'versions': {m.__name__: m.__version__
                  for m in (np, pd, matplotlib)}, 'source': str(args.source_dir),
              'source_sha256': {f.name: hashlib.sha256(f.read_bytes()).hexdigest()
                  for f in args.source_dir.glob('*.py')}, 'rows': [], 'status': 'running'}
    callback_errors = []
    tk.Tk.report_callback_exception = lambda self, exc, value, tb: callback_errors.append(str(value))
    args.output.mkdir(parents=True, exist_ok=True)
    path = args.output / (args.scenario + '.json')

    def save():
        path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')

    def measure(phase, fn, repeat):
        gc.collect()
        start, cpu = time.perf_counter(), time.process_time()
        value = fn()
        assert not callback_errors, callback_errors
        result['rows'].append({'phase': phase, 'repeat': repeat, 'warmup': repeat == 0,
            'seconds': time.perf_counter()-start, 'cpu_seconds': time.process_time()-cpu,
            'memory_mib': memory()})
        save()
        return value

    def null(*a, **kw):
        pass

    save()
    with tempfile.TemporaryDirectory(prefix='minijmp-g18-') as temporary:
        target = Path(temporary)
        if args.scenario.startswith('matrix'):
            import linear_plot
            original = linear_plot.pearson_correlation
            calls = []

            def timed_pearson(*a, **kw):
                start = time.perf_counter()
                value = original(*a, **kw)
                calls.append(time.perf_counter()-start)
                return value

            linear_plot.pearson_correlation = timed_pearson
            values = rng.normal(size=(p, n)).tolist()
            labels = [f'V{i}' for i in range(p)]
            for rep in range(4):
                calls.clear()
                kw = {}
                if args.scenario in ('matrix', 'matrix-tk'):
                    if args.scenario == 'matrix-tk':
                        from types import SimpleNamespace
                        from plots import plot_viewer
                        root = tk.Tk()
                        root.withdraw()
                        viewer = plot_viewer(SimpleNamespace(pf=None))
                        viewer.main.update()
                        fig = viewer.fig
                        fig.clear()
                    else:
                        fig = Figure(figsize=(8, 7), dpi=100, layout='constrained')
                        FigureCanvasAgg(fig)
                    kw = {'ax': fig.add_subplot(111), 'fig': fig}
                fn = linear_plot.multi_fit_orig if args.scenario == 'matrix-orig' else linear_plot.multi_fit
                output = measure('matrix_and_artists', lambda: fn(values, labels, **kw), rep)
                if not kw:
                    fig = plt.gcf()
                total = result['rows'][-1]['seconds']
                result['rows'][-1].update(pearson_seconds=sum(calls),
                    axes_artists_and_report_seconds=total-sum(calls), pearson_calls=len(calls),
                    axes=len(fig.axes)+sum(len(a.child_axes) for a in fig.axes))
                assert len(output['pearson']) == p
                if args.scenario == 'matrix-tk':
                    measure('tk_first_draw_to_updated', lambda: (fig.canvas.draw(), viewer.main.update()), rep)
                    measure('tk_redraw_to_updated', lambda: (fig.canvas.draw(), viewer.main.update()), rep)
                    viewer.close()
                    root.destroy()
                else:
                    measure('agg_first_draw', fig.canvas.draw, rep)
                    measure('agg_redraw', fig.canvas.draw, rep)
                plt.close(fig)
                fig.clear()
        elif args.scenario in ('table', 'spc', 'excel', 'reports', 'wide'):
            from stat_table import StatTable, export_excel
            headers = ['Sample'] + [f'V{i}' for i in range(1, p)]
            values = [[f'row{i}']+[i+c/7 for c in range(1, p)] for i in range(n)]
            if args.scenario == 'spc':
                from control_chart import _print_spc_report
                for rep in range(4):
                    measure('report_build', lambda: _print_spc_report('I',
                        [('Individual', data, 7., 10., 13.)], 1, 'N', None, [], null), rep)
            elif args.scenario == 'table':
                for rep in range(4):
                    measure('report_build', lambda: StatTable(title='G15', headers=headers, values=values), rep)
            else:
                table = StatTable(title='G15', headers=headers, values=values)
                if args.scenario == 'excel':
                    from zipfile import ZipFile
                    for rep in range(4):
                        measure('export_excel', lambda: export_excel(table, target/'table.xlsx'), rep)
                        with ZipFile(target/'table.xlsx') as book:
                            assert book.read('xl/worksheets/sheet1.xml').count(b'<row ') == n+2
                        measure('txt_write', lambda: (target/'table.txt').write_text(str(table), encoding='utf-8'), rep)
                else:
                    import tkinter as tk
                    from types import SimpleNamespace
                    from MiniJMP import Minijmp
                    from txt_output import txt_viewer
                    root = tk.Tk()
                    root.withdraw()
                    viewer = txt_viewer(SimpleNamespace(tOut=None))
                    app = SimpleNamespace(table=viewer.table, tOut=viewer)
                    tables = [StatTable(title=f'G15 {i+1}', headers=headers, values=values)
                              for i in range(20)] if args.scenario == 'reports' else [table]
                    viewer.main.update()
                    for rep in range(4):
                        viewer.clear()
                        viewer.main.update()

                        def present():
                            for current in tables:
                                Minijmp.print(app, current)
                            viewer.main.update()

                        measure('tk_print_to_updated', present, rep)
                        block = viewer.table_blocks[-1]
                        measure('tk_last_page_to_updated', lambda: (block.show_page(block.page_count), viewer.main.update()), rep)
                        assert block.tree.item(block.tree.get_children()[-1], 'values')[-1] == table.display[-1][-1]
                        measure('gui_txt_save', lambda: viewer.save(target/'table.txt'), rep)
                        assert (target/'table.txt').read_text(encoding='utf-8') == ''.join(str(t)+'\n' for t in tables)
                        measure('tk_clear_to_updated', lambda: (viewer.clear(), viewer.main.update()), rep)
                        assert not viewer.table_blocks
                    viewer.close()
                    root.destroy()
        elif args.scenario in ('series', 'series-tk', 'dialog'):
            from time_series import prepare_time_series, time_series_plot, AXIS_MODES
            df = pd.DataFrame(rng.normal(size=(n, p)), columns=[f'V{i}' for i in range(p)])
            df['Time'] = pd.date_range('2025-01-01', periods=n, freq='s')[::-1]
            cols = list(df.columns[:-1])
            assignments = {c: i+1 for i, c in enumerate(cols)}
            if args.scenario == 'series':
                for rep in range(4):
                    prepared = measure('data_prepare', lambda: prepare_time_series(df, cols, 'Time'), rep)
                    fig = Figure(figsize=(9, 6), dpi=100)
                    FigureCanvasAgg(fig)
                    axes = measure('plot_build_including_prepare', lambda: time_series_plot(
                        fig, df, cols, 'Time', assignments, AXIS_MODES[2]), rep)
                    for ax in axes.values():
                        assert len(ax.lines[0].get_xdata()) == n
                    measure('agg_first_draw', fig.canvas.draw, rep)
                    measure('agg_redraw', fig.canvas.draw, rep)
                    fig.clear()
                    import time_series
                    # 基准中单独提供同一份已验证数据，分离 Axes/Artist 与数据准备。
                    time_series.prepare_time_series = lambda *a: prepared
                    try:
                        axes = measure('artist_build_prepared', lambda: time_series_plot(
                            fig, df, cols, 'Time', assignments, AXIS_MODES[2]), rep)
                        assert sum(len(ax.lines) for ax in axes.values()) == p
                    finally:
                        time_series.prepare_time_series = prepare_time_series
                        fig.clear()
            else:
                import tkinter as tk
                from types import SimpleNamespace
                root = tk.Tk()
                root.withdraw()
                if args.scenario == 'series-tk':
                    from plots import plot_viewer
                    viewer = plot_viewer(SimpleNamespace(pf=None))
                    viewer.main.update()
                    for rep in range(4):
                        def present():
                            time_series_plot(viewer.fig, df, cols, 'Time', assignments, AXIS_MODES[2])
                            viewer.canvas.draw()
                            viewer.main.update()
                        measure('tk_plot_to_updated', present, rep)
                        measure('tk_redraw_to_updated', lambda: (viewer.canvas.draw(), viewer.main.update()), rep)
                    viewer.close()
                else:
                    from MiniJMP import Minijmp
                    from modified_app import Minijmp_pre
                    from time_series_dialog import TimeSeriesDialog
                    parent = tk.Frame(root)
                    parent.pf = None
                    app = SimpleNamespace(table=parent, print=null, addPlot=null,
                        dialog_help_msg=lambda **kw: Minijmp_pre.dialog_help_msg(None, **kw))
                    app.showPlotViewer = lambda **kw: Minijmp.showPlotViewer(app, **kw)
                    dlg = TimeSeriesDialog(parent, df=df, app=app, title='G18 时间序列')
                    dlg.ylist.selection_set(0, 2)
                    dlg.mode.set(AXIS_MODES[2])
                    dlg.update_variables()
                    dlg.assignments = assignments
                    dlg.no_preview = False
                    dlg.main.update()
                    for rep in range(4):
                        measure('tk_dialog_apply_to_updated', lambda: (dlg.apply(), parent.pf.main.update()), rep)
                        assert len(parent.pf.fig.axes) == 3
                    parent.pf.close()
                    dlg.main.destroy()
                    parent.destroy()
                root.destroy()
        else:
            import tkinter as tk
            from modified_table import MTable
            from pandastable_local.plotting import PlotViewer
            df = pd.DataFrame(rng.normal(size=(n, p)), columns=[f'V{i}' for i in range(p)])
            root = tk.Tk()
            root.geometry('1000x650')
            frame = tk.Frame(root)
            frame.pack(fill='both', expand=True)
            table = MTable(frame, dataframe=df, showtoolbar=False, showstatusbar=True)
            table.show()
            root.update()
            for rep in range(4):
                viewer = measure('tk_vendor_viewer_create', lambda: PlotViewer(table=table, showoptions=True), rep)
                root.update()
                for phase, fn in [('replot', lambda: viewer.replot(data=df.copy())),
                                  ('plotCurrent', viewer.plotCurrent), ('plot2D', viewer.plot2D)]:
                    if phase == 'plot2D':
                        viewer._initFigure()
                    measure('tk_vendor_'+phase+'_to_updated', lambda: (fn(), root.update()), rep)
                    assert len(viewer.ax.lines) == p
                    for line, column in zip(viewer.ax.lines, df):
                        np.testing.assert_array_equal(line.get_ydata(), df[column])
                viewer.close()
            root.destroy()
    result['status'] = 'ok'
    save()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-dir', type=Path, default=ROOT/'code')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--scenario', choices=SCENARIOS, action='append')
    parser.add_argument('--worker', action='store_true')
    args = parser.parse_args()
    args.source_dir = args.source_dir.resolve()
    args.output = args.output.resolve()
    if args.worker:
        args.scenario = args.scenario[0]
        if args.scenario == 'vendor' and args.source_dir != (ROOT/'code').resolve():
            parser.error('vendor 场景仅支持当前源码；旧版无有效曲线，见 G15 原始失败记录。')
        worker(args)
        return
    env = dict(os.environ, OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1')
    for scenario in args.scenario or SCENARIOS:
        print(scenario, flush=True)
        subprocess.run([sys.executable, str(Path(__file__).resolve()), '--worker',
            '--source-dir', str(args.source_dir), '--output', str(args.output),
            '--scenario', scenario], env=env, check=True, timeout=240, cwd=ROOT)


if __name__ == '__main__':
    main()
