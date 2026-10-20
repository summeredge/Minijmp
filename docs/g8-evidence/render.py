"""从项目根目录用项目解释器生成 G8 实际 GUI、TXT 与导出证据。"""
import sys
from pathlib import Path
from types import SimpleNamespace
import tkinter as tk

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'code'))
from PIL import ImageGrab
from MiniJMP import Minijmp
from describe import describe
from stat_table import StatTable, export_excel, export_png
from txt_output import txt_viewer


def screenshot(viewer, target):
    viewer.main.attributes('-topmost', True)
    viewer.main.lift()
    viewer.main.update()
    viewer.main.after(300)
    viewer.main.update()
    # 原生窗口捕获使用物理像素，避免 Windows DPI 虚拟坐标裁掉滚动条和底栏。
    ImageGrab.grab(window=viewer.main.winfo_id()).save(target)


def main():
    folder = Path(__file__).resolve().parent
    root = tk.Tk()
    root.withdraw()
    viewer = txt_viewer(SimpleNamespace(tOut=None))
    app = SimpleNamespace(table=viewer.table, tOut=viewer)
    try:
        lines = []
        describe([-5, None, -2, 4, 7], print_out=True, print_port=lines.append)
        for line in lines:
            Minijmp.print(app, line)
            if isinstance(line, StatTable):
                export_excel(line, folder / (line.title + '.xlsx'))
                export_png(line, folder / (line.title + '.png'))
        viewer.main.geometry('1100x800+30+30')
        viewer.T.yview_moveto(0)
        screenshot(viewer, folder / 'window.png')
        viewer.save(folder / '原报告.txt')
        assert (folder / '原报告.txt').read_text(encoding='utf-8') == ''.join(str(x) + '\n' for x in lines)
        positions = [block.menu_button.winfo_rootx() for block in viewer.table_blocks]
        assert len(set(positions)) == 1
        viewer.clear()
        for count in (2, 10, 31):
            viewer.add_table(StatTable(title=f'{count} 列表格', headers=[f'中文列{i}' for i in range(count)],
                values=[list(range(count)) for _ in range(2)]))
        viewer.main.geometry('480x600+30+30')
        viewer.T.yview_moveto(0)
        screenshot(viewer, folder / 'menus-narrow.png')
        positions = [block.menu_button.winfo_rootx() for block in viewer.table_blocks]
        assert len(set(positions)) == 1
        print('GUI、TXT、Excel、PNG 已生成；2/10/31 列菜单坐标：', positions)
    finally:
        viewer.close()
        root.destroy()


if __name__ == '__main__':
    main()
