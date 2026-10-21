"""第一批独立图形入口；复用 pandas 和 PlotViewer 的已有绘图方法。"""
import tkinter as tk
from tkinter import ttk

import numpy as np
import pandas as pd

from dialog import addListBox
from sbplot_dialog import SBDialog
from chart_style import style_axes


PLOT_TITLES = {'bar': '条形图', 'pie': '饼图', 'area': '区域图',
               'dotplot': '点图', 'scatter_matrix': '矩阵图',
               'contour': '等值线图', 'scatter3d': '三维散点图', 'surface': '三维曲面图'}


class BasicPlotDialog(SBDialog):
    def __init__(self, parent=None, df=None, app=None, kind='bar'):
        self.kind = kind
        super().__init__(parent, df=df, app=app, title=PLOT_TITLES[kind])

    def createWidgets(self, m):
        if self.kind in ('contour', 'scatter3d', 'surface'):
            self.xyz = []
            for label in ('X 数据列', 'Y 数据列', 'Z 数据列'):
                row = ttk.Frame(m)
                row.pack(fill=tk.X, padx=4, pady=2)
                ttk.Label(row, text=label).pack(side=tk.LEFT)
                var = tk.StringVar(self.main)
                ttk.Combobox(row, values=self.cols, textvariable=var,
                             state='readonly').pack(side=tk.LEFT, fill=tk.X, expand=True)
                self.xyz.append(var)
        else:
            frame, self.variables = addListBox(m, values=self.cols, label='数值列（可多选）')
            frame.pack(fill=tk.BOTH, expand=True, padx=4, pady=2)
        if self.kind in ('bar', 'pie', 'area'):
            row = ttk.Frame(m)
            row.pack(fill=tk.X, padx=4, pady=2)
            ttk.Label(row, text='标签列（可选；默认行索引）').pack(side=tk.LEFT)
            self.labels = tk.StringVar(self.main)
            ttk.Combobox(row, values=[''] + self.cols, textvariable=self.labels,
                         state='readonly').pack(side=tk.LEFT, fill=tk.X, expand=True)
        if self.kind == 'bar':
            self.horizontal = tk.BooleanVar(self.main, value=False)
            ttk.Checkbutton(m, text='水平条形', variable=self.horizontal).pack(anchor='w')

    def help(self, event=None):
        from help_link import open_help
        topic = {'bar': 'basic', 'dotplot': 'dot', 'scatter_matrix': 'matrix'}.get(self.kind, self.kind)
        open_help('plots.' + topic, parent=self.main)
        return 'break'

    def apply(self):
        cols = ([v.get() for v in self.xyz] if self.kind in ('contour', 'scatter3d', 'surface')
                else self.variables.getSelectedItem())
        if not cols or any(c not in self.df.columns for c in cols):
            self.error('请选择有效的数值列。')
            return
        if len(set(cols)) != len(cols):
            self.error('X、Y、Z 必须选择不同的列。')
            return
        if self.kind == 'scatter_matrix' and len(cols) < 2:
            self.error('矩阵图至少需要两列数值。')
            return
        if self.kind == 'pie' and len(cols) != 1:
            self.error('饼图请选择一列数值和可选的标签列。')
            return
        try:
            data = self.df.loc[:, cols].apply(pd.to_numeric, errors='raise').astype(float)
            data = data.replace([np.inf, -np.inf], np.nan)
            keep = data.notna().all(axis=1)
            if self.kind == 'dotplot':
                if data.notna().sum().eq(0).any():
                    raise ValueError('每个数值列至少需要一个有限数值。')
            else:
                data = data.loc[keep]
            if data.empty:
                raise ValueError('没有可绘制的完整有限数值行。')
            if self.kind == 'scatter_matrix' and (len(data) < 2 or data.nunique().lt(2).any()):
                raise ValueError('矩阵图每列至少需要两个不同数值。')
            if self.kind == 'pie' and (data.lt(0).any().any() or data.sum().iloc[0] <= 0):
                raise ValueError('饼图数值必须非负，且合计大于零。')
            if self.kind in ('bar', 'pie', 'area') and self.labels.get():
                label = self.labels.get()
                if label not in self.df.columns or label in cols:
                    raise ValueError('标签列必须是所选数值列之外的有效列。')
                # 按行位置取标签，支持重复工作表索引。
                data.index = self.df.loc[keep, label].fillna('').astype(str).to_numpy()
            mesh = None
            if self.kind in ('contour', 'surface'):
                from pandastable_local.plotting import PlotViewer
                mesh = PlotViewer.meshData(self, *data.to_numpy().T)
        except (ValueError, TypeError) as error:
            self.error(str(error))
            return

        pf = self.showPlotViewer()
        pf.ax = ax = pf.fig.add_subplot(111, projection='3d' if self.kind in ('scatter3d', 'surface') else None)
        if self.kind in ('bar', 'area'):
            kind = 'barh' if self.kind == 'bar' and self.horizontal.get() else self.kind
            data.plot(kind=kind, ax=ax, stacked=False)
        elif self.kind == 'pie':
            data.iloc[:, 0].plot.pie(ax=ax, autopct='%1.1f%%')
        elif self.kind == 'scatter_matrix':
            pd.plotting.scatter_matrix(data, ax=ax, diagonal='hist', marker='o')
        elif self.kind == 'dotplot':
            pf.dotplot(data, ax, {'marker': 'o', 'colormap': 'Spectral', 'ms': 5,
                                  'linewidth': 1, 'alpha': .9, 'logy': False})
        elif self.kind == 'scatter3d':
            pf.scatter3D(data, ax, {'linewidth': 1, 'alpha': .9, 'ms': 5,
                                    'marker': 'o', 'by': '', 'legend': True,
                                    'colormap': 'Spectral', 'labelcol': ''})
        else:
            X, Y, Z = mesh
            if self.kind == 'contour':
                artist = ax.contourf(X, Y, Z, 15, cmap='Spectral')
            else:
                artist = ax.plot_surface(X, Y, Z, cmap='Spectral')
                ax.set_zlabel(cols[2])
            pf.fig.colorbar(artist, ax=ax)
            ax.set(xlabel=cols[0], ylabel=cols[1])
        if self.kind == 'scatter3d':
            ax.set(xlabel=cols[0], ylabel=cols[1], zlabel=cols[2])
        for axis in pf.fig.axes:
            style_axes(axis)
        pf.canvas.draw()
