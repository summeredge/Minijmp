import sys
from pathlib import Path
import tkinter as tk
import gc

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'code'))


@pytest.fixture(autouse=True)
def isolated_column_preferences(monkeypatch):
    # Analysis tests must not read or overwrite the user's saved column choices.
    import dialog
    history = {}
    monkeypatch.setattr(dialog, '_read_column_history', lambda key: history.get(key, {}))
    monkeypatch.setattr(dialog, '_write_column_history',
                        lambda key, values: history.update({key: values}))


@pytest.fixture(scope='session')
def tk_root():
    # Tk widgets share one root interpreter, as they do in the application.
    root = tk.Tk()
    root.withdraw()
    yield root
    root.destroy()


@pytest.fixture(autouse=True)
def collect_closed_tk_objects(request):
    yield
    if 'tk_root' in request.fixturenames:
        # 关闭窗口后的循环引用应在主线程释放，避免后续数值线程析构 Tk 对象。
        gc.collect()
