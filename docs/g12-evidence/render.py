"""使用项目解释器生成 G12 混合报告、真实窗口及边界导出证据。"""
import sys
from pathlib import Path
from types import SimpleNamespace
import tkinter as tk

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT/'code'), str(ROOT/'tests')]

from PIL import ImageGrab
from MiniJMP import Minijmp
from stat_table import StatTable, export_excel, export_png
from test_g12_tables import DATA, mixed_reports
from txt_output import txt_viewer
from utilities import mean_std_CIs


def main():
    folder = Path(__file__).resolve().parent
    root = tk.Tk()
    root.withdraw()
    viewer = txt_viewer(SimpleNamespace(tOut=None))
    app = SimpleNamespace(table=viewer.table, tOut=viewer)
    try:
        lines = []
        mean_std_CIs(DATA, print_out=True, print_port=lines.append)
        lines.extend(mixed_reports())
        for line in lines:
            Minijmp.print(app, line)
        viewer.save(folder/'混合报告.txt')
        assert (folder/'混合报告.txt').read_text(encoding='utf-8') == ''.join(str(x)+'\n' for x in lines)
        viewer.main.geometry('1100x800+30+30')
        viewer.T.yview_moveto(0)
        viewer.main.attributes('-topmost', True)
        viewer.main.update()
        viewer.main.after(300)
        ImageGrab.grab(window=viewer.main.winfo_id()).save(folder/'mixed-window.png')
        interval = viewer.table_blocks[0].table
        edge = StatTable(title='中文 μ、ρ、α：精度与缺失', headers=['变量', '极小 p 值', '估计值', 'N'],
            values=[['=中文 & <标签>', 1.234567890123456e-100, -1.23456789, 12],
                    ['缺失与无穷', None, float('inf'), 0]],
            display=[['=中文 & <标签>', '1.235e-100', '-1.235', '12'],
                     ['缺失与无穷', '*', '*', '0']],
            number_formats=['General', '0.000E+00', '0.000', '0'])
        for name, table in [('置信区间', interval), ('导出边界', edge)]:
            export_excel(table, folder/(name+'.xlsx'))
            export_png(table, folder/(name+'.png'))
        viewer.main.geometry('480x320+30+30')
        viewer.T.yview_moveto(0)
        viewer.main.update()
        ImageGrab.grab(window=viewer.main.winfo_id()).save(folder/'mixed-narrow.png')
        indices = {entry[1]: entry[2] for entry in viewer.T.dump('1.0', 'end', window=True)}
        positions = []
        for block in viewer.table_blocks:
            viewer.T.see(indices[str(block)])
            viewer.T.xview_moveto(0)
            viewer.main.update()
            positions.append(block.menu_button.winfo_rootx())
        assert len(set(positions)) == 1
        print('实际混合表格数：', len(viewer.table_blocks))
        print('逐表映射后的菜单 x 坐标：', sorted(set(positions)))
    finally:
        viewer.close()
        root.destroy()


if __name__ == '__main__':
    main()
