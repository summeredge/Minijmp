from dialog import option_combobox
from tkinter import ttk, messagebox
import tkinter as tk
from tkinter import TOP, LEFT, X, BOTH, Frame, Button
from pandas import DataFrame as DF
import numpy as np
import seaborn as sb
########### Own Modules ###########
from dialog import Dialogs
from utilities import get_number, is_void, is_number, grouping_by_labels, transpose_2D_list, number_list


class SBDialog(Dialogs):
    def buttonsFrame(self):
        #  self.palette = 'pastel'
        bf = Frame(self.main)
        bf.pack(side=TOP, fill=BOTH)
        b = Button(bf, text='绘图', command=self.preview)
        b.pack(side=LEFT, fill=X, expand=1, pady=2)
        #  b = Button(bf, text="Done", command=self.done)
        #  b.pack(side=LEFT, fill=X, expand=1, pady=2)
        b = Button(bf, text='关闭', command=self.quit)
        b.pack(side=LEFT, fill=X, expand=1, pady=2)
        b = Button(bf, text='帮助', command=self.help)
        b.pack(side=LEFT, fill=X, expand=1, pady=2)
        self.no_preview = True
        return

    def prepare_preview(self):
        """Collect subclass selections before drawing."""
        pass

    def preview(self):
        if not self.main.winfo_exists():
            return
        self._previewing = True
        self._preview_viewer = None
        self._preview_failed = False
        try:
            self.app.getCurrentTable()
            self.prepare_preview()
            self.apply()
            viewer = self._preview_viewer
            if self._preview_failed or viewer is None or not viewer.main.winfo_exists():
                return
            # Render before replacing the old figure, including deferred draw errors.
            viewer.canvas.draw()
            self.app.replacePlotViewer(viewer, save_last=self.no_preview)
            self.no_preview = False
            if self.main.grab_current() is self.main:
                self.main.grab_release()
            viewer.main.deiconify()
            viewer.main.update_idletasks()
            viewer.main.lift()
            viewer.canvas.get_tk_widget().focus_force()
        except RuntimeError as exc:
            messagebox.showerror('无法绘图', str(exc), parent=self.main)
        except Exception as exc:
            self.error('绘图失败：' + str(exc))
        finally:
            viewer = self._preview_viewer
            self._preview_viewer = None
            self._previewing = False
            if viewer is not None and viewer is not getattr(viewer.table, 'pf', None):
                viewer.close()

    def error(self, msg=None, *, preview_failed=True):
        if (msg is not None and preview_failed
                and getattr(self, '_previewing', False)):
            self._preview_failed = True
        super().error(msg)

    def done(self):
        self.quit()
        self.apply()
        return

    def showPlotViewer(self):
        if getattr(self, '_previewing', False):
            self._preview_viewer = self.app.showPlotViewer(deferred=True)
            return self._preview_viewer
        return self.app.showPlotViewer(save_last=self.no_preview)

    def make_working_df(self, cols=None, numcols=[]):
        def voids2nan(data):
            return [np.nan if is_void(i) else i
                    for i in data]
        d = dict()
        if cols is None:
            cols = self.cols
        for key in cols:
            d[key] = voids2nan(self.df[key])
        for key in numcols:
            d[key] = [float(i) if is_number(i) else np.nan for i in self.df[key]]
        self.working_df = DF(d)
        return

    def make_working_df_1col(self,
                             data=None, label=None):
        data, keys = grouping_by_labels(
            self.df[data], self.df[label],
            return_keys=True)
        maxLen = max(len(i) for i in data)
        for i in data:
            i.extend([np.nan] * (maxLen - len(i)))
        self.working_df = DF(
            transpose_2D_list(data),
            columns=keys)
        return

    def get_x_plot_settings(self):
        self.x_max_v = get_number(self.x_max)
        self.x_min_v = get_number(self.x_min)
        self.xlabel_v = None if self.xlabel.get() == "" else self.xlabel.get()
        return

    def get_y_plot_settings(self):
        self.y_max_v = get_number(self.y_max)
        self.y_min_v = get_number(self.y_min)
        self.ylabel_v = None if self.ylabel.get() == "" else self.ylabel.get()
        return

    def get_misc_plot_settings(self):
        self.ax_margin_v = self.ax_margin.get()
        self.show_legend_v = self.show_legend.get()
        self.grid_v = self.grid.get()
        return

    def add_y_refs(self, m):
        master = tk.LabelFrame(m, text='水平参考线（可选）')
        master.pack(side=TOP, fill=BOTH, padx=2)
        self.yref = tk.StringVar(value="")

        w = tk.Label(master, text='Y 轴位置（逗号分隔）')
        w.pack(side=LEFT, fill=X, padx=2)
        w = tk.Entry(master, textvariable=self.yref,
                     bg='white', width=15)
        w.pack(side=LEFT, padx=2, pady=2)
        self.yref_label = tk.BooleanVar(value=False)
        w = tk.Checkbutton(master, text='显示标签',
                           variable=self.yref_label)
        w.pack(side=LEFT, padx=2, pady=2)

        return

    def add_palette_selection(self, m):
        # List of Seaborn palettes
        palettes = [
            "deep", "muted", "pastel", "bright", "dark", "colorblind",
            "Blues", "BuGn", "BuPu", "GnBu", "Greens", "Greys", "Oranges",
            "Purples", "Reds", "YlGn", "YlGnBu", "YlOrBr", "YlOrRd",
            "BrBG", "PiYG", "PRGn", "PuOr", "RdBu", "RdGy", "RdYlBu",
            "RdYlGn", "Spectral"
        ]

        f = tk.LabelFrame(m, text='配色方案')
        f.pack(side=TOP, fill=BOTH, padx=2)
        w = tk.Label(f, text='配色')
        w.pack(side=LEFT, fill=X, padx=2)
        # Dropdown menu to select a palette
        self.palette = tk.StringVar(value=palettes[0])
        dropdown = option_combobox(
            f, width=10,
            textvariable=self.palette,
            values=palettes)
        dropdown.pack(side=LEFT, fill=X, expand=1, pady=2)
        #  dropdown.grid(row=0, column=0, padx=10, pady=10, sticky="ns")
        dropdown.bind("<<ComboboxSelected>>", self.show_palette)

        # Canvas to display the palette colors
        self.canvas = tk.Canvas(f, width=120, height=20)
        self.canvas.pack(side=LEFT, fill=X, expand=1, pady=2, padx=20)
        #  grid(row=0, column=1, padx=10, pady=10)

        # Display initial palette
        self.show_palette()
        return

    def show_palette(self, event=None):
        # Clear the canvas
        self.canvas.delete("all")

        # Get the selected palette
        palette_name = self.palette.get()
        colors = sb.color_palette(palette_name, n_colors=6)

        # Display the colors as rectangles on the canvas
        for i, color in enumerate(colors):
            x0 = i * 20
            x1 = x0 + 20
            self.canvas.create_rectangle(
                x0, 0, x1, 20, fill=self.rgb_to_hex(color), outline="")
        return

    def rgb_to_hex(self, rgb):
        # Convert RGB tuple to hex color
        return '#%02x%02x%02x' % tuple(int(c * 255) for c in rgb)

    def rgb_to_hex_darker(self, rgb):
        # Convert RGB tuple to hex color
        return '#%02x%02x%02x' % tuple(int(c * c * 255) for c in rgb)
