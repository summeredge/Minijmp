"""定位 G14 已有预算下的连续小表成本；profile 不计入正式性能样本。"""
import cProfile
from pathlib import Path
import pstats
import sys
import tkinter as tk
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
sys.path[:0] = [str(OUT/'before'), str(ROOT/'code')]
from MiniJMP import Minijmp
from stat_table import StatTable
from txt_output import txt_viewer


def main():
    root = tk.Tk()
    root.withdraw()
    viewer = txt_viewer(SimpleNamespace(tOut=None))
    app = SimpleNamespace(table=viewer.table, tOut=viewer)
    tables = [StatTable(title=f'G15 {i+1}', headers=['Sample']+[f'V{i}' for i in range(1, 7)],
        values=[[f'row{r}']+[r+c/7 for c in range(1, 7)] for r in range(100)]) for i in range(20)]
    viewer.main.update()
    profile = cProfile.Profile()
    profile.enable()
    for table in tables:
        Minijmp.print(app, table)
    viewer.main.update()
    profile.disable()
    with (OUT/'layout-profile.txt').open('w', encoding='utf-8') as output:
        pstats.Stats(profile, stream=output).strip_dirs().sort_stats('cumulative').print_stats(45)
    viewer.close()
    root.destroy()


if __name__ == '__main__':
    main()
