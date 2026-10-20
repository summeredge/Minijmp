import sys
from pathlib import Path
import tkinter as tk

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'code'))


@pytest.fixture(scope='session')
def tk_root():
    # Tk widgets share one root interpreter, as they do in the application.
    root = tk.Tk()
    root.withdraw()
    yield root
    root.destroy()
