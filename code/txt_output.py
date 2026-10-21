from tkinter import BOTH, Toplevel, VERTICAL, LEFT, TOP, END, BOTTOM, filedialog
from tkinter import ttk, font, messagebox
import tkinter as tk
import os
#####################################
from pandastable_local.plotting import addButton
from pandastable_local import images
from pandastable_local.dialogs import (
    apply_dialog_theme, dialog_style, text_widget_colors)
############# Own Modules ###########
from plots import plot_viewer
from stat_table import RESULT_BACKGROUND, LABEL_CELL_LIMIT, configure_result_styles


class txt_viewer(plot_viewer):
    def __init__(self, table, parent=None):

        self.parent = parent
        self.table = table
        if table is not None:
            self.table.tOut = self  # opaque ref

        if self.parent is not None:
            ttk.Frame.__init__(self, parent)
            self.main = self.master
        else:
            self.main = Toplevel()
            self.master = self.main
            self.main.title('Minijmp - 统计结果')
            self.main.protocol("WM_DELETE_WINDOW", self.close)
            g = '720x700'
            self.main.geometry(g)
            self.main.minsize(480, 320)
        self.orient = VERTICAL
        self.ui_style = dialog_style(self.main)
        self._scroll_job = None
        self.setupGUI()
        self._apply_theme()
        self.table_blocks = []
        self.currentdir = os.path.expanduser('~')
        return

    def _apply_theme(self):
        """Keep result backgrounds white and retain theme text/selection colors."""

        apply_dialog_theme(self.main)
        self._apply_result_colors()
        return

    def _apply_result_colors(self):
        configure_result_styles(self.ui_style)
        colors = text_widget_colors(self.ui_style)
        colors['background'] = RESULT_BACKGROUND
        self.T.configure(**colors)

    def setupGUI(self):
        """Add GUI elements"""

        self.m = ttk.Frame(self.main, style='Result.TFrame')
        self.plotfr = ttk.Frame(self.m, style='Result.TFrame')
        # shortcut: 无中文等宽字体时沿用 TkFixedFont；需严格对齐时安装下列字体。
        self.output_font = font.nametofont('TkFixedFont', root=self.main).copy()
        # 中文需占两个西文字符宽，才能与 PrettyTable 的显示宽度一致。
        families = set(font.families(self.main))
        for family in ('Sarasa Mono SC', '新宋体', 'NSimSun',
                       'Noto Sans Mono CJK SC', 'WenQuanYi Zen Hei Mono'):
            if family in families:
                self.output_font.configure(family=family)
                # 偶数像素字号避免高 DPI 下半角宽度取整后错位。
                self.output_font.configure(size=-2 * round(self.output_font.measure('中') / 2))
                break
        self.T = tk.Text(self.plotfr, wrap='none', font=self.output_font,
                         tabs=(self.output_font.measure('0') * 8,))
        self.vsb = ttk.Scrollbar(
            self.plotfr,
            orient="vertical",
            command=self.T.yview)
        self.hsb = ttk.Scrollbar(self.plotfr, orient='horizontal', command=self.T.xview)
        self.T.configure(yscrollcommand=self.vsb.set, xscrollcommand=self.hsb.set)
        self.T.grid(row=0, column=0, sticky='nsew')
        self.vsb.grid(row=0, column=1, sticky='ns')
        self.hsb.grid(row=1, column=0, sticky='ew')
        self.plotfr.rowconfigure(0, weight=1)
        self.plotfr.columnconfigure(0, weight=1)
        self.T.bind('<Configure>', self._resize_table_titles)
        self.T.bind('<Control-a>', self.select_all)
        self.T.bind('<<Copy>>', self.copy)
        self.T.bind('<<ThemeChanged>>', lambda event: self._apply_result_colors())
        self.plotfr.pack(side=TOP, fill=BOTH, expand=1)

        self.ctrlfr = ttk.Frame(self.main)
        self.ctrlfr.pack(side=BOTTOM, fill=BOTH)

        bf = ttk.Frame(self.ctrlfr, padding=2)
        bf.pack(side=TOP, fill=BOTH)
        side = LEFT
        addButton(bf, '清空', self.clear, images.plot_clear(),
                  '清空结果', side=side)
        addButton(bf, '保存', self.save, images.save(),
                  '保存为文本文件', side=side)
        ttk.Button(bf, text='复制', command=lambda: self.T.event_generate('<<Copy>>')).pack(side=side)
        ttk.Button(bf, text='全选', command=self.select_all).pack(side=side)
        self.m.pack(fill=BOTH, expand=1)

        return

    def _resize_table_titles(self, event):
        for block in self.table_blocks:
            block.fit_titlebar(event.width)

    def add_txt(self, txt):
        self.T.insert(END, txt, ())
        return

    def add_table(self, table, end='\n'):
        from stat_table import TableBlock
        start = self.T.index('end-1c')
        stop = start
        line = self.T.index(f'{stop} linestart')
        while (self.T.compare(line, '>', '1.0') and not self.T.get(line, stop).strip()
               and not self.T.dump(line, stop, window=True)):
            stop = self.T.index(f'{line}-1c')
            line = self.T.index(f'{stop} linestart')
        heading = self.T.get(line, stop).strip()
        if (table.title and heading in (table.title, f'---- {table.title} ----')
                and not self.T.dump(line, stop, window=True)):
            # 仅隐藏紧邻的重复标题，保存和复制仍包含原报告的全部字符。
            self.T.tag_add('table_heading', line, f'{stop}+1c')
            self.T.tag_configure('table_heading', elide=True)
        # 累计预算避免多张小表耗尽 Windows 控件句柄；不额外缓存数据或计数。
        cells = (len(table.display)+1)*len(table.headers)
        labels = sum((len(b.table.display)+1)*len(b.table.headers)
                     for b in self.table_blocks if b.table is not None and not b.paged)
        block = TableBlock(self.T, table, paginate=labels+cells > 2*LABEL_CELL_LIMIT)
        if block.paged:
            block.tree.bind('<Control-a>', self.select_all)
            block.tree.bind('<<Copy>>', self.copy)
        if not block.paged:
            self.T.insert(END, table, 'table_ascii')
        self.T.insert(END, end, ())
        self.T.tag_configure('table_ascii', elide=True)
        self.table_blocks.append(block)
        self.T.window_create(start, window=block)

    def _text_chunks(self, start='1.0', stop='end-1c'):
        """按 Text 中的实际顺序重建报告，分页窗口代表整张原始文本表。"""
        for kind, value, index in self.T.dump(start, stop, text=True, window=True):
            if kind == 'text':
                yield value
            elif value:
                block = self.T.nametowidget(value)
                if block.paged:
                    yield block.table

    def copy(self, event=None):
        ranges = self.T.tag_ranges('sel')
        if ranges:
            text = ''.join(self._text_chunks(*ranges))
            self.T.clipboard_clear()
            self.T.clipboard_append(text)
        return 'break'

    def select_all(self, event=None):
        self.T.tag_add('sel', '1.0', 'end-1c')
        self.T.focus_set()
        return 'break'

    def save(self, filename=None):
        """Save output as UTF-8 text."""

        ftypes = [('txt', '*.txt')]
        if filename is None:
            filename = filedialog.asksaveasfilename(parent=self.master,
                                                    initialdir=self.currentdir,
                                                    defaultextension='.txt',
                                                    filetypes=ftypes)
        if filename:
            self.currentdir = os.path.dirname(os.path.abspath(filename))
            try:
                with open(filename, 'w', encoding='utf-8') as file:
                    file.writelines(self._text_chunks())
            except OSError as error:
                messagebox.showerror('保存失败', str(error), parent=self.master)
        return

    def clear(self):
        if self._scroll_job is not None:
            self.T.after_cancel(self._scroll_job)
            self._scroll_job = None
        for block in self.table_blocks:
            block.destroy()
        self.table_blocks.clear()
        self.T.delete('1.0', END)
        return

    def close(self):
        self.clear()
        try:
            self.table.tOut = None
        except BaseException:
            pass
        self.main.destroy()
        return

    def to_end(self, defer=False):
        if defer:
            if self._scroll_job is None:
                self._scroll_job = self.T.after_idle(self.to_end)
            return
        if self._scroll_job is not None:
            self.T.after_cancel(self._scroll_job)
            self._scroll_job = None
        self.T.see("end")
