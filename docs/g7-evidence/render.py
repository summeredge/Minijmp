import sys
sys.path.insert(0,'code')
import tkinter as tk
from types import SimpleNamespace
from describe import describe
from txt_output import txt_viewer
from stat_table import StatTable,export_excel,export_png
from PIL import ImageGrab
root=tk.Tk();root.withdraw()
v=txt_viewer(SimpleNamespace(tOut=None))
lines=[]
describe([-5,None,-2,4,7], print_out=True,print_port=lines.append)
for line in lines:
    if isinstance(line,StatTable):
        v.add_table(line)
        export_excel(line,'docs/g7-evidence/'+line.title+'.xlsx')
        export_png(line,'docs/g7-evidence/'+line.title+'.png')
    else:v.add_txt(line+'\n')
v.main.geometry('1100x800+30+30');v.main.update()
v.main.attributes('-topmost',True);v.main.lift();v.main.update();v.main.after(500);v.main.update()
ImageGrab.grab(bbox=(v.main.winfo_rootx(),v.main.winfo_rooty(),v.main.winfo_rootx()+v.main.winfo_width(),v.main.winfo_rooty()+v.main.winfo_height())).save('docs/g7-evidence/window.png')
v.close();root.destroy()
