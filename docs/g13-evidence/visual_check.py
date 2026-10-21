"""Reproduce the G13 native dialog/viewer screenshots with the project Python."""
from pathlib import Path
import sys
import tkinter as tk
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'code'))
import numpy as np
import pandas as pd
from PIL import ImageGrab
from MiniJMP import Minijmp
from modified_app import Minijmp_pre
from time_series_dialog import TimeSeriesDialog
from time_series import AXIS_MODES


def capture(window, filename):
    window.lift()
    window.update()
    ImageGrab.grab(window=window.winfo_id()).save(
        Path(__file__).with_name(filename))


root = tk.Tk()
root.geometry('1x1+0+0')
parent = tk.Frame(root)
parent.pf = None
app = SimpleNamespace(table=parent, print=print, addPlot=lambda: None,
                      dialog_help_msg=lambda **kw: Minijmp_pre.dialog_help_msg(None, **kw))
app.showPlotViewer = lambda **kw: Minijmp.showPlotViewer(app, **kw)
x = np.arange(80)
data = pd.DataFrame({'采样时间': pd.date_range('2026-10-21', periods=80, freq='min'),
                     'TIC330003.PV': 100 + np.sin(x / 8) * 5,
                     'PI330004.PV': 2 + np.cos(x / 12) * .2,
                     'FI330506_S': 500 + x * 2})
data.loc[35:38, 'TIC330003.PV'] = np.nan
dialog = TimeSeriesDialog(parent, df=data, app=app, title='时间序列图')
try:
    dialog.main.geometry('+60+60')
    dialog.ylist.selection_set(0, 2)
    dialog.mode.set(AXIS_MODES[2])
    dialog.update_variables()
    dialog.assignments = dict(zip(dialog.selected_columns(), [1, 2, 3]))
    dialog.update_variables()
    dialog.titlevar.set('连续采样原始趋势')
    dialog.ylabels = {1: '温度（℃）', 2: '压力（MPa）', 3: '流量（m³/h）'}
    dialog.select_axis_title()
    capture(dialog.main, 'dialog.png')
    dialog.apply()
    viewer = parent.pf
    viewer.main.geometry('1000x750+60+60')
    capture(viewer.main, 'viewer.png')
    viewer.savePlot(str(Path(__file__).with_name('three-axes.png')))
    viewer.main.geometry('760x560+60+60')
    capture(viewer.main, 'viewer-small.png')
    # Native widget geometry checks at normal and larger Tk font scaling.
    for scaling in (1.0, 2.0):
        root.tk.call('tk', 'scaling', scaling)
        dialog.main.update()
        assert dialog.main.winfo_reqheight() < root.winfo_screenheight()
        for widget in (dialog.time_combo, dialog.axis_table, dialog.mode_combo, dialog.ylabel_entry):
            assert widget.winfo_width() > 20 and widget.winfo_height() > 10
    print('Native dialog, 1000x750 and 760x560 viewer screenshots and PNG export generated.')
finally:
    if parent.pf is not None:
        parent.pf.close()
    dialog.main.destroy()
    root.destroy()
