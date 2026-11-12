from pathlib import Path
import sys

if getattr(sys, 'frozen', False) and len(str(Path(sys.executable).parent)) > 80:
    from tkinter import Tk, messagebox
    root = Tk()
    root.withdraw()
    messagebox.showerror('安装路径过长',
                         '请完整解压到不超过 80 个字符的本地受控目录（例如 C:\\Apps\\MiniJMP-V1.2），再启动。',
                         parent=root)
    root.destroy()
    raise SystemExit(1)

APP_ROOT = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(APP_ROOT / 'code'))

from MiniJMP import main

main()
