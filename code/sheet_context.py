"""Keep a dialog's data and output attached to its source worksheet."""

from tkinter import TclError


class SheetApp:
    def __init__(self, app, table):
        self._app = app
        self.table = table

    def getCurrentTable(self):
        self._check_table()
        return self.table

    def _check_table(self):
        exists = getattr(self.table, 'winfo_exists', None)
        if exists is None:
            return
        try:
            if exists():
                return
        except TclError:
            pass
        raise RuntimeError('来源工作表已关闭，无法继续分析或输出。')

    def print(self, txt, end="\n"):
        self._check_table()
        return self._app.print(txt, end=end, table=self.table)

    def showPlotViewer(self, parent=None, figsize=(10, 7), save_last=True):
        self._check_table()
        return self._app.showPlotViewer(
            parent=parent, figsize=figsize, save_last=save_last,
            table=self.table)

    def __getattr__(self, name):
        return getattr(self._app, name)
