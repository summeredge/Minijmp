"""普通控制图窗口中的可选阶段对比；计算与图形复用 improvement_chart。"""
import tkinter as tk
from tkinter import BOTH, LEFT, TOP, ttk

from improvement_chart import LIMIT_MODES, SPLITS, analyze_improvement
from utilities import get_number


LABEL = '启用阶段对比（改善前/改善后）'


def settings(dialog, master):
    """只加一个勾选项；设置区在首次勾选时才创建。"""
    dialog.stage_compare = tk.BooleanVar(dialog.main, False)
    dialog.sc_master = master
    ttk.Checkbutton(master, text=LABEL, variable=dialog.stage_compare,
                    command=lambda: toggle(dialog)).pack(side=TOP, anchor='w', padx=2)


def toggle(dialog):
    if not dialog.stage_compare.get():
        frame = getattr(dialog, 'sc_frame', None)
        if frame is not None:
            frame.pack_forget()
        return
    if not hasattr(dialog, 'sc_frame'):
        _build(dialog)
    dialog.sc_frame.pack(side=TOP, fill=BOTH, padx=2)


def _build(dialog):
    master = dialog.sc_master
    frame = tk.LabelFrame(master, text='阶段对比设置')
    dialog.sc_frame = frame
    dialog.sc_split = tk.StringVar(dialog.main, list(SPLITS.values())[0])
    dialog.sc_stage = tk.StringVar(dialog.main, '')
    dialog.sc_time = tk.StringVar(dialog.main, '')
    dialog.sc_cutoff = tk.StringVar(dialog.main, '')
    dialog.sc_mode = tk.StringVar(dialog.main, list(LIMIT_MODES.values())[0])
    dialog.sc_alpha = tk.StringVar(dialog.main, '0.05')

    row = tk.Frame(frame)
    row.pack(side=TOP, fill=BOTH, padx=2)
    tk.Label(row, text='阶段划分方式').pack(side=LEFT, padx=2)
    ttk.Combobox(row, values=list(SPLITS.values()), textvariable=dialog.sc_split,
                 state='readonly', width=10).pack(side=LEFT, padx=2, pady=2)
    tk.Label(row, text='控制限模式').pack(side=LEFT, padx=2)
    ttk.Combobox(row, values=list(LIMIT_MODES.values()), textvariable=dialog.sc_mode,
                 state='readonly', width=16).pack(side=LEFT, padx=2, pady=2)
    tk.Label(row, text='显著性水平').pack(side=LEFT, padx=2)
    tk.Entry(row, textvariable=dialog.sc_alpha, bg='white', width=6).pack(
        side=LEFT, padx=2, pady=2)

    row = tk.Frame(frame)
    row.pack(side=TOP, fill=BOTH, padx=2)
    tk.Label(row, text='阶段标识列').pack(side=LEFT, padx=2)
    dialog.sc_stage_box = ttk.Combobox(row, values=dialog.cols,
                                       textvariable=dialog.sc_stage, width=14)
    dialog.sc_stage_box.pack(side=LEFT, padx=2, pady=2)
    tk.Label(row, text='时间列').pack(side=LEFT, padx=2)
    dialog.sc_time_box = ttk.Combobox(row, values=dialog.cols,
                                      textvariable=dialog.sc_time, width=14)
    dialog.sc_time_box.pack(side=LEFT, padx=2, pady=2)
    tk.Label(row, text='分界时间').pack(side=LEFT, padx=2)
    dialog.sc_cutoff_entry = tk.Entry(row, textvariable=dialog.sc_cutoff,
                                      bg='white', width=14)
    dialog.sc_cutoff_entry.pack(side=LEFT, padx=2, pady=2)

    dialog.sc_split.trace_add('write', lambda *_: _mode_state(dialog))
    _mode_state(dialog)


def _mode_state(dialog):
    by_stage = dialog.sc_split.get() == list(SPLITS.values())[0]
    dialog.sc_stage_box.configure(state='readonly' if by_stage else 'disabled')
    for widget in (dialog.sc_time_box, dialog.sc_cutoff_entry):
        widget.configure(state='disabled' if by_stage else 'normal')


def run(dialog, chart):
    """执行阶段分析并打开结果窗口。"""
    value = dialog.xvar.get()
    if not value:
        raise ValueError('请选择观测值列。')
    split = next(key for key, label in SPLITS.items() if label == dialog.sc_split.get())
    mode = next(key for key, label in LIMIT_MODES.items() if label == dialog.sc_mode.get())
    try:
        alpha = float(dialog.sc_alpha.get())
    except ValueError as exc:
        raise ValueError('显著性水平须为数字。') from exc
    result = analyze_improvement(
        dialog.df, value, chart=chart, split=split,
        stage=dialog.sc_stage.get() or None,
        time=dialog.sc_time.get() or None,
        cutoff=dialog.sc_cutoff.get().strip() or None,
        limit_mode=mode, alpha=alpha,
        subgroup_size=get_number(dialog.gsize) if hasattr(dialog, 'gsize') else None,
        subgroup_id=(dialog.gid.get() or None) if hasattr(dialog, 'gid') else None)
    from improvement_dialog import ImprovementChartDialog
    ImprovementChartDialog(dialog.parent, dialog.app, result)
    dialog.remember_columns()
    return True
