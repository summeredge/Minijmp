"""使用项目解释器生成真实 Windows Tk 窗口截图；不操作其他应用。"""
from pathlib import Path
import sys
import tkinter as tk
from types import SimpleNamespace

from PIL import ImageGrab

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / 'code')]
from MiniJMP import Minijmp
from stat_table import StatTable
from txt_output import txt_viewer

OUT = Path(__file__).resolve().parent


def capture(viewer, filename, geometry='720x700+80+70'):
    viewer.main.geometry(geometry)
    viewer.main.lift()
    viewer.main.update()
    viewer.to_end()
    viewer.main.update()
    viewer.main.after(300)
    image = ImageGrab.grab(window=viewer.main.winfo_id())
    image.save(OUT / filename)
    image.close()


def main():
    root = tk.Tk()
    root.withdraw()
    viewer = txt_viewer(SimpleNamespace(tOut=None))
    app = SimpleNamespace(table=viewer.table, tOut=viewer)
    try:
        Minijmp.print(app, StatTable(title='小表：保留原有外观', headers=['变量', '均值', 'N'],
                                   values=[[f'测量 {i}', i/7, 100] for i in range(8)]))
        viewer.main.update()
        capture(viewer, 'small-window.png')
        viewer.clear()
        values = [[f'样本 {i+1}']+[i+j/7 for j in range(1, 7)] for i in range(50000)]
        Minijmp.print(app, StatTable(title='大表：50,000 行 × 7 列',
                                   headers=['变量']+[f'统计 {i}' for i in range(1, 7)], values=values))
        viewer.main.update()
        capture(viewer, 'large-first-page.png')
        block = viewer.table_blocks[-1]
        block.show_page(block.page_count)
        block.tree.yview_moveto(1)
        block.tree.xview_moveto(1)
        viewer.main.update()
        capture(viewer, 'large-last-page.png')
        capture(viewer, 'large-small-window.png', '480x320+80+70')
        viewer.clear()
        for i in range(20):
            Minijmp.print(app, StatTable(title=f'连续输出 {i+1}/20', headers=['变量', '均值', 'N'],
                                       values=[[f'测量 {j}', j/7, 100] for j in range(100)]))
        viewer.main.update()
        capture(viewer, 'many-window.png')
    finally:
        viewer.close()
        root.destroy()


if __name__ == '__main__':
    main()
