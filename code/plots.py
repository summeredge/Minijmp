from pandastable_local.plotting import PlotViewer, addButton, addFigure
from pandastable_local import handlers, images, util
from matplotlib.figure import Figure
from matplotlib import pyplot as plt
#  from tkinter.ttk import Frame
from tkinter import BOTH, Toplevel, VERTICAL, TOP, BOTTOM, LEFT, BooleanVar, Checkbutton, IntVar, Label, X, Entry, Frame
import os
from collections import OrderedDict


def general_plotly_figure(data, kind, *, bins, legend, grid, title, xlabel, ylabel):
    """Render the same role/selection frame used by the general plotter."""
    import numpy as np
    import pandas as pd
    from plotly import graph_objects as go

    numeric = data.select_dtypes(include=['number', 'bool']).astype(float)
    numeric = numeric.where(np.isfinite(numeric))
    fig = go.Figure()
    xaxis = {}
    if kind == 'scatter':
        if len(numeric.columns) < 2:
            raise ValueError('散点图需要一个数值 X 列和至少一个数值 Y 列。')
        x = numeric.iloc[:, 0]
        xlabel = xlabel or str(x.name)
        for name, y in numeric.iloc[:, 1:].items():
            keep = x.notna() & y.notna()
            if keep.any():
                fig.add_scatter(x=x[keep].tolist(), y=y[keep].tolist(), name=str(name), mode='markers')
    elif kind == 'histogram':
        values = [y.dropna().to_numpy() for _, y in numeric.items()]
        if bins < 1:
            raise ValueError('直方图分箱数必须为正整数。')
        if values and any(len(y) for y in values):
            edges = np.histogram_bin_edges(np.concatenate(values), bins=bins)
            centers = edges[:-1] + np.diff(edges) / 2
            bounds = np.column_stack((edges[:-1], edges[1:])).tolist()
            for name, y in zip(numeric.columns, values):
                if len(y):
                    counts, _ = np.histogram(y, bins=edges)
                    fig.add_bar(x=centers.tolist(), y=counts.tolist(), width=np.diff(edges).tolist(),
                                name=str(name), customdata=bounds,
                                hovertemplate='%{customdata[0]} ～ %{customdata[1]}<br>频数：%{y}')
        ylabel = ylabel or '频数'
        fig.update_layout(barmode='overlay')
        fig.update_traces(opacity=.65)
    else:
        xlabel = xlabel or str(data.index.name or '')
        x = data.index.tolist()
        if kind == 'bar':
            labels = [str(value) if pd.notna(value) else '（缺失）' for value in x]
            # Row positions keep duplicate categories as separate bars.
            x = list(range(len(labels)))
            xaxis.update(tickmode='array', tickvals=x, ticktext=labels)
            for name, y in numeric.items():
                if y.notna().any():
                    fig.add_bar(x=x, y=y.fillna(0).tolist(), name=str(name), customdata=labels,
                                hovertemplate='%{customdata}<br>%{y}')
            fig.update_layout(barmode='group')
        else:
            for name, y in numeric.items():
                if y.notna().any():
                    fig.add_scatter(x=x, y=y.tolist(), name=str(name), mode='lines',
                                    connectgaps=False)
    if not fig.data:
        raise ValueError('没有可绘制的有限数值或完整的 X/Y 配对。')
    fig.update_layout(template='plotly_white', title=title, showlegend=legend,
                      xaxis=dict(title=xlabel, showgrid=grid, **xaxis),
                      yaxis=dict(title=ylabel, showgrid=grid))
    return fig


class PlotlyViewer:
    """Tk window for interactive Plotly figures and standalone exports."""

    _config = dict(responsive=True, scrollZoom=True, displaylogo=False,
                   displayModeBar=True, modeBarButtonsToRemove=['toImage'])

    def __init__(self, parent, figure, *, on_ready=None, live=False):
        from pathlib import Path
        from tempfile import TemporaryDirectory
        from tkinter import ttk

        from tkwry import WebView

        self.main = Toplevel(parent)
        self.main.title('Plot Viewer — Plotly（试验）')
        self.main.geometry('1000x750+120+0')
        self.main.minsize(420, 320)
        self.webview = None
        self._webview_job = None
        self._image_export = None
        self.directory = None
        self._live = live
        self._live_ready = False
        self._live_figure = None
        self.main.bind('<Destroy>', self._destroyed, add='+')
        self.main.protocol('WM_DELETE_WINDOW', self.close)
        try:
            post_script = None
            if live:
                post_script = """
                    window.minijmpPlotUpdate = Promise.resolve();
                    window.tkwry?.call('live_plot_ready').catch(console.error);
                """
            self.html = self._figure_html(figure, post_script)
            self.directory = TemporaryDirectory(prefix='minijmp-plotly-')
            Path(self.directory.name, 'index.html').write_text(self.html, encoding='utf-8')
            tools = ttk.Frame(self.main)
            tools.pack(fill=X)
            ttk.Button(tools, text='导出…', command=self.export).pack(side=LEFT, padx=4, pady=3)
            ttk.Label(tools, text='工程和 PDF 报告不包含此图').pack(side=LEFT, padx=4)
            frame = ttk.Frame(self.main)
            # A timer runs after the plot callback and outside Tk's idle layout pass.
            self._webview_job = self.main.after(0, self._create_webview, WebView, frame, on_ready)
        except Exception:
            self.close()
            raise

    @classmethod
    def _figure_html(cls, figure, post_script=None):
        html = figure.to_html(
            include_plotlyjs=True, include_mathjax=False, post_script=post_script,
            config=cls._config,
        )
        return html.replace('<head>', '''<head>
<meta http-equiv="Content-Security-Policy"
 content="default-src 'none'; script-src 'unsafe-inline' 'unsafe-eval';
 style-src 'unsafe-inline'; img-src data: blob:; worker-src blob:">
<style>html, body { height: 100%; margin: 0; overflow: hidden; }
body > div { height: 100%; }</style>''', 1)

    def update_figure(self, figure):
        self._live_figure = figure
        if self._live_ready:
            self._render_live_figure()

    def _live_plot_ready(self):
        self._live_ready = True
        if self._live_figure is not None:
            self._render_live_figure()

    def _render_live_figure(self):
        import json
        spec = self._live_figure.to_json()
        config = json.dumps(self._config)
        self.webview.eval_js(f"""
            window.minijmpPlotUpdate = window.minijmpPlotUpdate.then(() => {{
                const figure = {spec};
                return Plotly.react(document.querySelector('.js-plotly-plot'), figure.data, figure.layout, {config});
            }}).catch(error => window.tkwry.call('live_plot_error', String(error)));
        """, on_error=self._live_plot_error)

    def _live_plot_error(self, error):
        from tkinter import messagebox
        messagebox.showerror('无法更新 Plotly 图形', str(error), parent=self.main)

    def _create_webview(self, webview_type, frame, on_ready):
        self._webview_job = None
        try:
            self.webview = webview_type(frame, app=self.directory.name, csp=False, open_external=False)
            self.webview.when_failed(self.creation_failed)
            self.webview.expose(self._finish_image_export, name='finish_image_export')
            if self._live:
                self.webview.expose(self._live_plot_ready, name='live_plot_ready')
                self.webview.expose(self._live_plot_error, name='live_plot_error')
            if on_ready is not None:
                self.webview.when_ready(on_ready)
            frame.pack(fill=BOTH, expand=True)
            self.webview.pack(fill=BOTH, expand=True)
        except Exception as exc:
            self.creation_failed(exc)

    def export(self):
        from pathlib import Path
        from tkinter import StringVar, filedialog, messagebox

        formats = {'PNG 图片': '.png', 'SVG 矢量图': '.svg', 'Plotly HTML': '.html'}
        selected = StringVar(master=self.main, value=next(iter(formats)))
        filename = filedialog.asksaveasfilename(
            parent=self.main, filetypes=[(name, '*' + suffix) for name, suffix in formats.items()],
            typevariable=selected)
        if not filename or not self.main.winfo_exists():
            return

        path = Path(filename)
        try:
            if not path.suffix:
                path = path.with_suffix(formats.get(selected.get(), '.png'))
                if path.exists() and not messagebox.askyesno(
                        '确认覆盖', f'是否覆盖 {path.name}？', parent=self.main):
                    return
            suffix = path.suffix.lower()
            if suffix == '.html':
                html = (self.html if self._live_figure is None else self._figure_html(self._live_figure))
                path.write_text(html, encoding='utf-8')
            elif suffix in ('.png', '.svg'):
                self._export_image(path, suffix[1:])
            else:
                raise ValueError('请选择 .png、.svg 或 .html 文件。')
        except (OSError, ValueError) as exc:
            self._export_error(exc)

    def _export_image(self, path, format_name):
        if self._image_export is not None:
            raise ValueError('正在导出图片，请稍候。')
        if self.webview is None:
            raise ValueError('图形仍在加载，请稍后重试。')

        import json
        options = json.dumps({'format': format_name, 'scale': 2 if format_name == 'png' else 1})
        job = self.main.after(20000, lambda: self._finish_image_export(
            job, None, '生成图片超时，请重试。'))
        self._image_export = (path, format_name, job)
        try:
            self.webview.eval_js(f"""
                (async () => {{
                    let image;
                    try {{
                        await window.minijmpPlotUpdate;
                        const graph = document.querySelector('.js-plotly-plot');
                        if (!graph || !graph._fullLayout) throw Error('图形仍在加载，请稍后重试。');
                        image = await Plotly.toImage(graph, {{...{options},
                            width: graph.clientWidth, height: graph.clientHeight}});
                    }} catch (error) {{
                        await window.tkwry.call('finish_image_export', {json.dumps(job)}, null, String(error));
                        return;
                    }}
                    await window.tkwry.call('finish_image_export', {json.dumps(job)}, image, null);
                }})().catch(console.error);
            """, on_error=lambda error: self._finish_image_export(job, None, str(error)))
        except Exception as exc:
            self._finish_image_export(job, None, str(exc))

    def _finish_image_export(self, request, data_url, error):
        from base64 import b64decode
        from urllib.parse import unquote_to_bytes

        if self._image_export is None or request != self._image_export[2]:
            return
        path, format_name, job = self._image_export
        self._image_export = None
        self.main.after_cancel(job)
        try:
            if error:
                raise ValueError(error)
            header, _, payload = (data_url or '').partition(',')
            mime = 'image/png' if format_name == 'png' else 'image/svg+xml'
            if header.split(';', 1)[0] != 'data:' + mime or not payload:
                raise ValueError('图形引擎未返回有效图片。')
            content = (b64decode(payload, validate=True) if header.endswith(';base64')
                       else unquote_to_bytes(payload))
            if not content:
                raise ValueError('图形引擎返回了空图片。')
            path.write_bytes(content)
        except (OSError, ValueError) as exc:
            self._export_error(exc)

    def _export_error(self, error):
        from tkinter import messagebox

        messagebox.showerror('无法导出 Plotly 图形', str(error), parent=self.main)

    def creation_failed(self, error):
        from tkinter import messagebox

        messagebox.showerror('无法启动 Plotly',
                             f'请确认已安装 Microsoft Edge WebView2 Runtime。\n{error}',
                             parent=self.main)
        self.close()

    def close(self):
        if self.main.winfo_exists():
            # tkwry releases the native view when its host frame is destroyed.
            self.main.destroy()

    def _destroyed(self, event):
        if event.widget is not self.main:
            return
        if self._webview_job is not None:
            self.main.after_cancel(self._webview_job)
            self._webview_job = None
        if self._image_export is not None:
            self.main.after_cancel(self._image_export[2])
            self._image_export = None
        if self.directory is not None:
            self.directory.cleanup()
            self.directory = None


class plot_viewer(PlotViewer):
    def __init__(self, table, parent=None, showoptions=True, figsize=(10, 7), register=True):

        self.parent = parent
        self.table = table
        if table is not None and register:
            self.table.pf = self  # opaque ref
        #self.mode = '2d'
        self.showoptions = showoptions
        self.multiviews = False
        if self.parent is not None:
            Frame.__init__(self, parent)
            self.main = self.master
        else:
            self.main = Toplevel()
            self.master = self.main
            self.main.title('Plot Viewer')
            self.main.protocol("WM_DELETE_WINDOW", self.close)
            g = '1000x750+120+0'
            self.main.geometry(g)
        self.orient = VERTICAL
        self.style = None
        self.figsize = figsize
        self.setupGUI()
        #  self.updateStyle()
        self.currentdir = os.path.expanduser('~')
        self._cleaned_up = False
        self.main.bind('<Destroy>', self._on_destroy, add='+')
        return

    def setupGUI(self):
        """Add GUI elements"""

        #import tkinter as tk
        #self.m = PanedWindow(self.main, orient=self.orient)
        self.m = Frame(self.main)
        self.m.pack(fill=BOTH, expand=1)
        # frame for figure
        self.plotfr = Frame(self.m)
        #host for chart navigation bars; keeps them off the figure and the options dock
        self.plot_tools = Frame(self.m)
        self.plot_tools.pack(side=TOP, fill=X)
        # add it to the panedwindow
        self.fig, self.canvas = addFigure(
            self.plotfr, figure=Figure(
                figsize=self.figsize, dpi=100, facecolor='white', layout='constrained'))
        #  self.ax = self.fig.add_subplot(111)

        #self.m.add(self.plotfr, weight=12)
        self.plotfr.pack(side=TOP, fill=BOTH, expand=1)

        # frame for controls
        self.ctrlfr = Frame(self.main)
        #self.m.add(self.ctrlfr, weight=4)
        self.ctrlfr.pack(side=BOTTOM, fill=X)

        # button frame
        bf = Frame(self.ctrlfr, padx=2)  # padding=2)
        bf.pack(side=TOP, fill=BOTH)

        side = LEFT
        addButton(bf, 'Save', self.savePlot, images.save(),
                  'save plot', side=side)

        # dicts to store global options, can be saved with projects
        self.globalvars = {}
        self.globalopts = OrderedDict({'dpi': 100})
        # , 'grid layout': False, '3D plot': False})
        from functools import partial
        for n in self.globalopts:
            val = self.globalopts[n]
            if isinstance(val, bool):
                v = self.globalvars[n] = BooleanVar()
                v.set(val)
                b = Checkbutton(
                    bf, text=n, variable=v, command=partial(
                        self.setGlobalOption, n))
            else:
                v = self.globalvars[n] = IntVar()
                v.set(val)
                Label(bf, text=n).pack(side=LEFT, fill=X, padx=2)
                b = Entry(bf, textvariable=v, width=5)
                util.trace_write(v, partial(self.setGlobalOption, n))
            b.pack(side=LEFT, padx=2)
        self._drag_handler = handlers.DragHandler(self)
        self._drag_handler.connect()
        return

    def _on_destroy(self, event):
        if event.widget is self.main:
            self._cleanup()

    def close(self):
        """Close the window, including an already destroyed viewer."""
        try:
            self._cleanup()
        finally:
            if self.main.winfo_exists():
                self.main.destroy()

    def _cleanup(self):
        if self._cleaned_up:
            return
        self._cleaned_up = True
        for table in (self.table, getattr(self.table, 'child', None)):
            if table is not None and getattr(table, 'pf', None) is self:
                table.pf = None
        try:
            if hasattr(self, 'animateopts'):
                self.animateopts.stop()
        finally:
            for variable in self.globalvars.values():
                for mode, callback in variable.trace_info():
                    variable.trace_remove(mode, callback)
            self._drag_handler = None
            plt.close(self.fig)
        return
