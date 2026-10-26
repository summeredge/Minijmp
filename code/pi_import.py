"""Modal PI import: workers perform I/O; only the Tk thread touches widgets."""
import json
import ntpath
import os
import queue
import re
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import ttk, filedialog, messagebox
from tkinter.scrolledtext import ScrolledText

import pandas as pd

import pi_reader


# The current Windows user owns these preferences; no administrator access is needed.
# Registry values are unaffected by the transparent file-encryption client.
_PI_SETTINGS_KEY = r'Software\MiniJMP\PIImport'
_PI_SETTING_NAMES = ('executable_path', 'config_path')


def normalize_pi_path(value):
    """Accept either Windows slash style, and display native separators."""
    value = str(value or '').strip().strip('"')
    if not value:
        return ''
    return ntpath.normpath(value) if os.name == 'nt' else os.path.normpath(value)


def application_root():
    """Return the folder that holds PIReader/ beside the packaged EXE.

    Frozen onedir modules live in _internal, so __file__ must not be used there.
    """
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def _pi_settings_file():
    return Path.home() / '.config' / 'MiniJMP' / 'pi_import_paths.json'


def load_pi_paths():
    """Read path-only preferences, without accessing PI credentials."""
    if os.name == 'nt':
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _PI_SETTINGS_KEY) as key:
                values = {}
                for name in _PI_SETTING_NAMES:
                    try:
                        value, _ = winreg.QueryValueEx(key, name)
                        if isinstance(value, str) and value.strip():
                            values[name] = normalize_pi_path(value)
                    except FileNotFoundError:
                        pass
                return values
        except FileNotFoundError:
            return {}
    try:
        data = json.loads(_pi_settings_file().read_text(encoding='utf-8'))
        return {key: normalize_pi_path(data[key]) for key in _PI_SETTING_NAMES
                if isinstance(data, dict) and isinstance(data.get(key), str)
                and data[key].strip()}
    except (FileNotFoundError, ValueError):
        return {}


def save_pi_paths(values):
    """Persist path-only preferences for the current user."""
    values = {key: normalize_pi_path(values.get(key)) for key in _PI_SETTING_NAMES
              if values.get(key)}
    if os.name == 'nt':
        import winreg
        with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, _PI_SETTINGS_KEY, 0,
                                winreg.KEY_SET_VALUE) as key:
            for name, value in values.items():
                winreg.SetValueEx(key, name, 0, winreg.REG_SZ, value)
        return
    dest = _pi_settings_file()
    dest.parent.mkdir(parents=True, exist_ok=True)
    temp = dest.with_name(dest.name + '.tmp')
    try:
        temp.write_text(json.dumps(values, ensure_ascii=False, indent=2), encoding='utf-8')
        os.replace(temp, dest)
    finally:
        temp.unlink(missing_ok=True)


def query_size(tags, start, end, interval):
    """Estimate common PI expressions without changing the reader's time semantics."""
    now = pd.Timestamp.now()

    def timestamp(value):
        match = re.fullmatch(r'\*(?:-([0-9]+)([smhd]))?', value)
        if match:
            unit = 'D' if match[2] == 'd' else match[2]
            return now - (pd.Timedelta(int(match[1]), unit=unit) if match[1]
                          else pd.Timedelta(0))
        if value.startswith('*'):
            return None
        return pd.Timestamp(value)

    first, last = timestamp(start), timestamp(end)
    if first is None or last is None:
        return None
    if last <= first:
        raise ValueError('结束时间必须晚于开始时间')
    return (int((last - first) / pd.Timedelta(interval)) + 1) * len(tags)


class PIImportDialog(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title('导入 PI 数据')
        self.transient(parent)
        self.df = None
        self.pending = None
        self.busy = False
        self.protocol('WM_DELETE_WINDOW', self.cancel)
        self.bind('<Escape>', lambda event: self.cancel())
        body = ttk.Frame(self, padding=12)
        body.grid(sticky='nsew')
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        body.columnconfigure(1, weight=1)
        body.rowconfigure(3, weight=1)
        root = application_root()
        # Both layouts are supported; discover the two files independently.
        default_exe = (root / 'PIReader.exe' if (root / 'PIReader.exe').is_file()
                       else root / 'PIReader' / 'PIReader.exe')
        default_config = (root / 'config.txt' if (root / 'config.txt').is_file()
                          else root / 'PIReader' / 'config.txt')
        try:
            self._saved_paths = load_pi_paths()
            self._settings_error = None
        except OSError as exc:
            self._saved_paths = {}
            self._settings_error = f'PI 路径设置读取失败：{exc}'
        self._save_after = None
        self.exe = tk.StringVar(value=normalize_pi_path(
            self._saved_paths.get('executable_path') or os.environ.get('PI_READER_EXE')
            or str(default_exe)))
        self.config = tk.StringVar(value=normalize_pi_path(
            self._saved_paths.get('config_path') or os.environ.get('PI_CONFIG')
            or str(default_config)))
        self.start = tk.StringVar(value='*-1d')
        self.end = tk.StringVar(value='*')
        self.interval = tk.StringVar(value='5m')
        self.mask = tk.StringVar()
        for row, (label, variable, pattern) in enumerate([
                ('PIReader.exe', self.exe, '*.exe'), ('config.txt', self.config, '*.txt')]):
            ttk.Label(body, text=label).grid(row=row, column=0, sticky='w', padx=(0, 8))
            entry = ttk.Entry(body, textvariable=variable, width=55)
            entry.grid(row=row, column=1, sticky='ew')
            entry.bind('<FocusOut>', lambda event: self.save_current_paths())
            entry.bind('<Return>', lambda event: self.save_current_paths())
            ttk.Button(body, text='浏览…', command=lambda v=variable, p=pattern: self.browse(v, p)).grid(row=row, column=2)
        ttk.Label(body, text='PI Tag（每行一个，最多 20 个）').grid(row=2, column=0, columnspan=3, sticky='w', pady=(10, 0))
        self.tags = tk.Text(body, height=5, width=65, wrap='none')
        self.tags.grid(row=3, column=0, columnspan=3, sticky='nsew')
        ttk.Label(body, text='Tag 搜索模式').grid(row=4, column=0, sticky='w')
        ttk.Entry(body, textvariable=self.mask).grid(row=4, column=1, sticky='ew')
        self.search_button = ttk.Button(body, text='搜索', command=self.search)
        self.search_button.grid(row=4, column=2)
        results = ttk.Frame(body)
        results.grid(row=5, column=0, columnspan=3, sticky='ew')
        self.results = ttk.Treeview(results, columns=('selected', 'tag'), show='headings', height=4, selectmode='none')
        self.results.heading('selected', text='勾选')
        self.results.heading('tag', text='Tag')
        self.results.column('selected', width=48, stretch=False)
        self.results.column('tag', width=400)
        self.results.pack(side='left', fill='both', expand=True)
        scrollbar = ttk.Scrollbar(results, orient='vertical', command=self.results.yview)
        scrollbar.pack(side='right', fill='y')
        self.results.configure(yscrollcommand=scrollbar.set)
        self.results.bind('<Button-1>', self.toggle_tag)
        self.results.bind('<space>', self.toggle_tag)
        ttk.Button(body, text='添加勾选 Tag', command=self.add_tags).grid(row=6, column=2)
        for row, label, variable in [(7, '开始时间', self.start), (8, '结束时间', self.end)]:
            ttk.Label(body, text=label).grid(row=row, column=0, sticky='w')
            ttk.Entry(body, textvariable=variable).grid(row=row, column=1, columnspan=2, sticky='ew')
        ttk.Label(body, text='采样间隔').grid(row=9, column=0, sticky='w')
        ttk.Combobox(body, textvariable=self.interval, values=pi_reader.INTERVAL_OPTIONS, state='readonly', width=10).grid(row=9, column=1, sticky='w')
        self.status_view = ScrolledText(body, height=3, width=60, wrap='word', state='disabled')
        self.status_view.grid(row=10, column=0, columnspan=3, sticky='ew', pady=8)
        self.import_button = ttk.Button(body, text='查询并导入', command=self.query)
        self.import_button.grid(row=11, column=1, sticky='e')
        ttk.Button(body, text='取消', command=self.cancel).grid(row=11, column=2)
        self.update_idletasks()
        self.minsize(self.winfo_reqwidth(), self.winfo_reqheight())
        self.grab_set()
        self.tags.focus_set()
        self._path_traces = [
            (variable, variable.trace_add('write', self.schedule_save))
            for variable in (self.exe, self.config)]
        self.bind('<Destroy>', self._cancel_pending_save, add='+')
        if self._settings_error:
            self.set_status(self._settings_error)

    def set_status(self, message):
        self.status_view.configure(state='normal')
        self.status_view.delete('1.0', 'end')
        self.status_view.insert('1.0', message)
        self.status_view.configure(state='disabled')
        self.status_view.yview_moveto(0)

    def schedule_save(self, *_):
        """Debounce manual edits; browsing and leaving a field save immediately."""
        if self._save_after is not None:
            self.after_cancel(self._save_after)
        self._save_after = self.after(650, self.save_current_paths)

    def _cancel_pending_save(self, event):
        if event.widget is self:
            if self._save_after is not None:
                self.after_cancel(self._save_after)
                self._save_after = None
            for variable, trace in self._path_traces:
                variable.trace_remove('write', trace)
            self._path_traces.clear()

    def save_current_paths(self):
        if self._save_after is not None:
            self.after_cancel(self._save_after)
            self._save_after = None
        candidates = {
            'executable_path': normalize_pi_path(self.exe.get()),
            'config_path': normalize_pi_path(self.config.get()),
        }
        for name, variable in (('executable_path', self.exe),
                               ('config_path', self.config)):
            if variable.get() != candidates[name]:
                variable.set(candidates[name])
        # Store independently selected valid files, not incomplete typing or guesses.
        updates = {key: value for key, value in candidates.items()
                   if value and Path(value).is_file()}
        # Normalization may have scheduled another callback through StringVar traces.
        if self._save_after is not None:
            self.after_cancel(self._save_after)
            self._save_after = None
        next_values = {**self._saved_paths, **updates}
        if next_values != self._saved_paths:
            try:
                save_pi_paths(next_values)
            except OSError as exc:
                self.set_status(f'PI 路径自动保存失败：{exc}')
            else:
                self._saved_paths = next_values
                self.set_status('PI 路径已自动保存。')

    def browse(self, variable, pattern):
        filename = filedialog.askopenfilename(parent=self, filetypes=[('PI 文件', pattern), ('所有文件', '*.*')])
        if filename:
            variable.set(normalize_pi_path(filename))
            self.save_current_paths()

    def paths(self):
        self.save_current_paths()
        return dict(config_path=normalize_pi_path(self.config.get()),
                    executable_path=normalize_pi_path(self.exe.get()))

    def toggle_tag(self, event):
        item = self.results.identify_row(event.y) if event.type != tk.EventType.KeyPress else self.results.focus()
        if item:
            checked, tag = self.results.item(item, 'values')
            self.results.item(item, values=('☐' if checked == '☑' else '☑', tag))
            self.results.focus(item)

    def add_tags(self):
        try:
            values = self.tags.get('1.0', 'end').splitlines()
            values += [self.results.item(item, 'values')[1] for item in self.results.get_children()
                       if self.results.item(item, 'values')[0] == '☑']
            values = pi_reader.normalize_tags(values)
            self.tags.delete('1.0', 'end')
            self.tags.insert('1.0', '\n'.join(values))
        except (ValueError, TypeError) as error:
            self.set_status(str(error))

    def search(self):
        if not self.busy:
            mask, paths = self.mask.get(), self.paths()
            self.run('search', lambda: pi_reader.search_pi_tags(mask, **paths))

    def query(self):
        if self.busy:
            return
        try:
            tags = pi_reader.normalize_tags(self.tags.get('1.0', 'end').splitlines())
            start = pi_reader._format_time(self.start.get(), '开始时间')
            end = pi_reader._format_time(self.end.get(), '结束时间')
            interval, paths = self.interval.get(), self.paths()
            size = query_size(tags, start, end, interval)
            if size is None or size > 1_000_000:
                text = ('无法估算该 PI 时间表达式的数据量。' if size is None else f'预计约 {size:,} 个数据点。')
                if not messagebox.askokcancel('查询数据量', text + '\n大查询可能耗时且占用较多内存，是否继续？', parent=self):
                    return
            self.tags.delete('1.0', 'end')
            self.tags.insert('1.0', '\n'.join(tags))
            self.run('query', lambda: pi_reader.read_pi_data(tags, start, end, interval, **paths))
        except (ValueError, TypeError) as error:
            self.set_status(str(error))

    def run(self, kind, operation):
        self.busy = True
        self.search_button.configure(state='disabled')
        self.import_button.configure(state='disabled')
        self.set_status('正在查询…（最多等待 300 秒）')
        mailbox = queue.Queue()

        def worker():
            try:
                mailbox.put((True, operation()))
            except Exception as error:
                mailbox.put((False, str(error)))

        threading.Thread(target=worker, daemon=True).start()
        self.poll(kind, mailbox)

    def poll(self, kind, mailbox):
        self.pending = None
        try:
            success, result = mailbox.get_nowait()
        except queue.Empty:
            self.pending = self.after(50, self.poll, kind, mailbox)
            return
        self.busy = False
        self.search_button.configure(state='normal')
        self.import_button.configure(state='normal')
        if not success:
            self.set_status('查询失败：' + result)
        elif kind == 'search':
            self.results.delete(*self.results.get_children())
            for tag in result['tags']:
                self.results.insert('', 'end', values=('☐', tag))
            self.set_status(f"找到 {result['count']} 个 Tag。" + (result['message'] or ('结果已截断，请缩小 Mask。' if result['truncated'] else '')))
        elif result.empty:
            self.set_status('查询结果为空，请检查 Tag 和时间范围。')
        else:
            try:
                time_column = 'Timestamp'
                suffix = 1
                while time_column in result.columns:
                    time_column = f'Timestamp (time {suffix})'
                    suffix += 1
                self.df = result.reset_index(names=time_column)
            except (ValueError, TypeError) as error:
                self.set_status('数据转换失败：' + str(error))
                return
            self.cancel()

    def cancel(self):
        self.save_current_paths()
        if self.pending is not None:
            self.after_cancel(self.pending)
            self.pending = None
        # A canceled reader may finish within its timeout; its isolated result is discarded.
        self.destroy()
