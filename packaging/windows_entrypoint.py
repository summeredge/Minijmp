from pathlib import Path
import sys

APP_ROOT = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(APP_ROOT / 'code'))

from MiniJMP import main

main()
