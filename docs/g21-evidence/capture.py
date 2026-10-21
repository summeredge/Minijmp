"""Capture the real 通用绘图器 Tk window before/after the UI review."""
from pathlib import Path
import sys
import tkinter as tk

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'code'))

import numpy as np
import pandas as pd
from PIL import ImageGrab
from modified_table import MTable
from pandastable_local.plotting import PlotViewer


def capture(window, filename):
    window.update()
    window.lift()
    window.update()
    ImageGrab.grab(window=window.winfo_id()).save(Path(__file__).with_name(filename))


root = tk.Tk()
root.withdraw()
frame = tk.Frame(root)
frame.pack()
x = np.arange(24)
data = pd.DataFrame({'时间': pd.date_range('2026-10-21', periods=24, freq='h'),
                     '温度': 70 + np.sin(x / 3) * 4,
                     '压力': 2.1 + np.cos(x / 4) * .15,
                     '批次': ['A', 'B'] * 12})
table = MTable(frame, dataframe=data, showtoolbar=False, showstatusbar=False)
table.show()
root.update()
table.multiplerowlist = list(range(16))
table.multiplecollist = [1, 2, 3]
viewer = PlotViewer(table=table)
try:
    viewer.main.geometry('1000x750+80+40')
    viewer.replot()
    viewer.main.update_idletasks()
    capture(viewer.main, 'after-1000x750.png')
    viewer.main.geometry('800x700+80+40')
    viewer.main.update()
    root.tk.call('tk', 'scaling', 1.5)
    viewer.main.update()
    capture(viewer.main, 'after-150pct.png')
    root.tk.call('tk', 'scaling', 1.0)
    capture(viewer.main, 'after-800x700.png')
    viewer.main.geometry('640x480+80+40')
    capture(viewer.main, 'after-640x480.png')
    viewer.toggle_options()
    capture(viewer.main, 'after-options-hidden.png')
    print('after captures:', sorted(p.name for p in Path(__file__).parent.glob('after-*.png')))
finally:
    viewer.close()
    table.destroy()
    root.destroy()
