"""G14 本机基准；每个场景/阶段在独立进程运行，超时保留已完成指标。

使用项目解释器运行：python tools/benchmark_report_rendering.py --output <目录>
--source-dir 可指向 tests/fixtures/g14_before，重放修改前公共链路。
"""
import argparse
import ctypes
import json
import os
from pathlib import Path
import statistics
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
SCENARIOS = {'small': (100, 7, 1), 'medium': (1000, 7, 1),
             'large': (10000, 7, 1), 'huge': (50000, 7, 1),
             'wide': (100, 100, 1), 'many': (100, 7, 20)}


def memory(pid=None):
    if os.name != 'nt':
        return None
    from ctypes import wintypes

    class Counters(ctypes.Structure):
        _fields_ = [('cb', wintypes.DWORD), ('PageFaultCount', wintypes.DWORD)] + [
            (name, ctypes.c_size_t) for name in (
                'PeakWorkingSetSize', 'WorkingSetSize', 'QuotaPeakPagedPoolUsage',
                'QuotaPagedPoolUsage', 'QuotaPeakNonPagedPoolUsage',
                'QuotaNonPagedPoolUsage', 'PagefileUsage', 'PeakPagefileUsage')]

    counter = Counters()
    counter.cb = ctypes.sizeof(counter)
    kernel = ctypes.windll.kernel32
    kernel.GetCurrentProcess.restype = wintypes.HANDLE
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    handle = kernel.OpenProcess(0x410, False, pid) if pid else kernel.GetCurrentProcess()
    if not handle:
        return None  # 子进程可能已在两次轮询之间退出。
    get_memory = ctypes.windll.psapi.GetProcessMemoryInfo
    get_memory.argtypes = [wintypes.HANDLE, ctypes.POINTER(Counters), wintypes.DWORD]
    get_memory.restype = wintypes.BOOL
    try:
        success = get_memory(handle, ctypes.byref(counter), counter.cb)
        if not success:
            if pid:
                return None
            raise ctypes.WinError()
    finally:
        if pid:
            kernel.CloseHandle(handle)
    return {name: getattr(counter, name) / 1024**2 for name in
            ('WorkingSetSize', 'PeakWorkingSetSize', 'PagefileUsage')}


def worker(args):
    sys.path[:0] = [str(args.source_dir), str(ROOT / 'code')]
    import tkinter as tk
    from tkinter import ttk
    from types import SimpleNamespace
    from MiniJMP import Minijmp
    from stat_table import StatTable, export_excel
    from txt_output import txt_viewer

    rows, columns, count = SCENARIOS[args.scenario]
    result = {'scenario': args.scenario, 'shape': [rows, columns], 'tables': count,
              'phase': args.phase, 'python': sys.executable,
              'worker_pid': os.getpid(),
              'source_dir': str(args.source_dir), 'memory_imported_mib': memory()}

    def record(stage, **metrics):
        result.update(metrics, stage=stage)
        args.result.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')

    record('building')
    headers = ['项目'] + [f'统计{i}' for i in range(1, columns)]
    # 输入准备不计入 StatTable 构建，原值与显示值的创建计入。
    values = [[f'样本{r+1}'] + [r + c / 7 for c in range(1, columns)] for r in range(rows)]
    started = time.perf_counter()
    tables = [StatTable(title=f'性能表 {i+1}', headers=headers, values=values) for i in range(count)]
    record('built', build_seconds=time.perf_counter()-started, memory_built_mib=memory())
    with tempfile.TemporaryDirectory(prefix='minijmp-g14-') as directory:
        target = Path(directory)
        if args.phase == 'exports':
            started = time.perf_counter()
            with (target / 'report.txt').open('w', encoding='utf-8') as output:
                for table in tables:
                    output.write(table)
                    output.write('\n')
            record('txt_written', txt_write_seconds=time.perf_counter()-started)
            started = time.perf_counter()
            for i, table in enumerate(tables):
                export_excel(table, target / f'{i}.xlsx')
            record('complete', excel_seconds=time.perf_counter()-started, memory_export_mib=memory())
            return
        root = tk.Tk()
        root.withdraw()
        viewer = txt_viewer(SimpleNamespace(tOut=None))
        app = SimpleNamespace(table=viewer.table, tOut=viewer)
        viewer.main.update()
        record('rendering', memory_before_gui_mib=memory())
        started = time.perf_counter()
        for table in tables:
            Minijmp.print(app, table)
        viewer.main.update()

        def widgets(widget):
            return 1 + sum(widgets(child) for child in widget.winfo_children())

        trees = [child for block in viewer.table_blocks for body in block.winfo_children()
                 for child in body.winfo_children() if isinstance(child, ttk.Treeview)]
        record('visible', first_visible_seconds=time.perf_counter()-started,
               widgets=widgets(viewer.main), tree_items=sum(len(t.get_children()) for t in trees),
               memory_gui_mib=memory(), tk_text_characters=len(viewer.T.get('1.0', 'end-1c')))
        samples = []
        for i in range(12):
            started = time.perf_counter()
            viewer.T.yview_moveto((i % 3) / 2)
            for tree in trees:
                tree.yview_moveto((i % 3) / 2)
                tree.xview_moveto((i % 3) / 2)
            viewer.main.update()
            samples.append(time.perf_counter()-started)
        record('scrolled', scroll_median_seconds=statistics.median(samples),
               scroll_max_seconds=max(samples))
        # 分页延迟和末行内容另测；旧实现没有分页。
        if viewer.table_blocks and getattr(viewer.table_blocks[-1], 'paged', False):
            block = viewer.table_blocks[-1]
            started = time.perf_counter()
            block.show_page(block.page_count)
            viewer.main.update()
            record('last_page', last_page_seconds=time.perf_counter()-started,
                   last_cell=block.tree.item(block.tree.get_children()[-1], 'values')[-1])
        started = time.perf_counter()
        viewer.save(target / 'viewer.txt')
        record('saved', gui_txt_save_seconds=time.perf_counter()-started)
        expected = ''.join(str(table)+'\n' for table in tables)
        assert (target / 'viewer.txt').read_text(encoding='utf-8') == expected
        viewer.clear()
        viewer.main.update()
        record('complete', widgets_after_clear=widgets(viewer.main), memory_cleared_mib=memory())
        viewer.close()
        root.destroy()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--source-dir', type=Path, default=ROOT / 'code')
    parser.add_argument('--scenario', choices=SCENARIOS)
    parser.add_argument('--phase', choices=('gui', 'exports'))
    parser.add_argument('--result', type=Path)
    parser.add_argument('--gui-timeout', type=float, default=20)
    parser.add_argument('--export-timeout', type=float, default=90)
    args = parser.parse_args()
    if args.result:
        worker(args)
        return
    if args.output is None:
        parser.error('--output is required')
    args.output.mkdir(parents=True, exist_ok=True)
    for scenario in ([args.scenario] if args.scenario else SCENARIOS):
        for phase in ([args.phase] if args.phase else ('exports', 'gui')):
            result = args.output / f'{scenario}-{phase}.json'
            result.unlink(missing_ok=True)
            command = [sys.executable, __file__, '--source-dir', str(args.source_dir.resolve()),
                       '--scenario', scenario, '--phase', phase, '--result', str(result.resolve())]
            timeout = args.gui_timeout if phase == 'gui' else args.export_timeout
            started = time.perf_counter()
            sampled_peak = 0
            with subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                  text=True) as process:
                while process.poll() is None and time.perf_counter()-started < timeout:
                    worker_pid = process.pid
                    if result.exists():
                        try:
                            worker_pid = json.loads(result.read_text(encoding='utf-8')).get(
                                'worker_pid', worker_pid)
                        except json.JSONDecodeError:
                            pass  # 写入阶段指标的瞬间可能读到半个 JSON。
                    counters = memory(worker_pid)
                    if counters:
                        sampled_peak = max(sampled_peak, counters['PeakWorkingSetSize'])
                    time.sleep(.1)
                if process.poll() is None:
                    if os.name == 'nt':
                        # venv 的 python.exe 是重定向器，必须一并终止实际工作进程。
                        subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'],
                                       capture_output=True, timeout=10)
                    else:
                        process.kill()
                    status = 'timeout'
                else:
                    status = 'ok' if process.returncode == 0 else 'error'
                _, stderr = process.communicate()
            error = (f'进程超过 {timeout:g}s，已终止；未完成的指标不作推算。'
                     if status == 'timeout' else stderr[-4000:])
            data = json.loads(result.read_text(encoding='utf-8')) if result.exists() else {}
            data.update(status=status, error=error, process_seconds=time.perf_counter()-started,
                        timeout_seconds=timeout, sampled_process_peak_rss_mib=sampled_peak or None)
            result.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
            print(scenario, phase, status, data.get('stage'), flush=True)


if __name__ == '__main__':
    main()
