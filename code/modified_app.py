from tkinter import Toplevel, Label, CENTER, LEFT
import tkinter as tk
import pandas as pd
import matplotlib
import scipy
import statsmodels
import prettytable
import seaborn
import platform
##############
from pandastable_local.app import DataExplore
from pandastable_local.dialogs import getParentGeometry
#### Own Modules ####
from help_link import help_link, help_window
from icon_resource import create_icon_image


def get_tkver():
    # Create a root window
    root = tk.Tk()

    # Get the Tcl/Tk version
    tcl_version = root.tk.call("info", "patchlevel")
    tk_version = root.tk.call("info", "patchlevel")

    print(f"Tcl version: {tcl_version}")
    print(f"Tk version: {tk_version}")

    # Destroy the root window
    root.destroy()
    return tk_version


class Minijmp_pre(DataExplore):
    def online_documentation(self, event=None, key=""):
        """Open the online documentation"""
        import webbrowser
        link = help_link(key)
        print("Open help link by browser:", link)
        webbrowser.open(link, autoraise=1)
        return

    def dialog_help_msg(self, event=None, key=""):
        txt = help_window(key)
        #  print("App got txt", txt)
        return txt

    def about(self):
        """显示二次开发信息、原作者署名和开源许可。"""

        abwin = Toplevel(self.main)
        abwin.title('关于 MiniJMP')
        abwin.transient(self.main)
        abwin.resizable(width=False, height=False)
        abwin.configure(background=self.bg)

        content = tk.Frame(abwin, bg=self.bg, padx=22, pady=14)
        content.pack(fill=tk.BOTH, expand=True)

        # 保留原项目图标，并缩小显示以避免“关于”窗口过高。
        logo = create_icon_image(abwin)
        small_logo = logo.subsample(2, 2)
        logo_label = Label(content, image=small_logo, bg=self.bg, anchor=CENTER)
        logo_label.image = small_logo
        logo_label.pack(pady=(0, 6))

        Label(content, text='MiniJMP', font=('Segoe UI', 14, 'bold'),
              bg=self.bg, anchor=CENTER).pack()
        Label(content, text='版本 v0.1.0-beta.3', font=('Segoe UI', 10),
              bg=self.bg, anchor=CENTER).pack(pady=(2, 0))
        Label(content, text='Copyright (C) G.Du 2024-',
              font=('Segoe UI', 10), bg=self.bg, anchor=CENTER).pack(pady=(2, 3))

        def add_section(title, text):
            Label(content, text=title, font=('Segoe UI', 10, 'bold'),
                  bg=self.bg, anchor='w', justify=LEFT).pack(fill=tk.X, pady=(12, 4))
            Label(content, text=text, font=('Segoe UI', 10),
                  bg=self.bg, anchor='w', justify=LEFT,
                  wraplength=520).pack(fill=tk.X)

        add_section('二次开发说明',
                    '本软件基于原作者 G.Du 发布的 Minijmp 开源项目进行二次开发。\n'
                    '本版本包含后续功能修改与改进，与原作者发布的原始版本有所区别。'
                    '更新日期：2026年10月。\n'
                    '基础组件 DataExplore 0.13：Copyright (C) Damien Farrell 2014-')

        add_section('开发工具',
                    '本版本以 Python 为主要开发语言，使用 Tkinter、pandas、NumPy、SciPy、'
                    'Matplotlib 等工具进行界面开发、数据处理、统计分析和绘图。'
                    '部分代码分析、功能实现、调试及文档整理借助 ChatGPT、Codex 等 AI 辅助工具完成。\n'
                    'AI 工具用于辅助开发，相关修改由项目维护者审查、整合并决定是否采用。')

        add_section('开源许可与免责声明',
                    '本软件依据 GNU GPL v3 或更高版本授权。您可以按照该许可证的条款'
                    '使用、复制、修改和再分发本软件。\n'
                    '本软件按“现状”提供，不提供任何明示或默示担保，包括适销性'
                    '或特定用途适用性的担保。\n'
                    '完整许可条款请查看软件根目录中的 LICENSE 文件，或访问以下官方页面。')

        import webbrowser
        license_link = Label(content, text='GNU GPL v3 官方许可文本',
                             font=('Segoe UI', 10, 'underline'),
                             fg='#1764b0', bg=self.bg, cursor='hand2', anchor='w')
        license_link.pack(fill=tk.X, pady=(5, 0))
        license_link.bind('<Button-1>',
                          lambda event: webbrowser.open('https://www.gnu.org/licenses/gpl-3.0.html'))

        tk.Button(content, text='关闭', width=10,
                  command=abwin.destroy).pack(anchor='e', pady=(12, 0))

        abwin.update_idletasks()
        x, y, w, h = getParentGeometry(self.main)
        width = max(560, abwin.winfo_reqwidth())
        height = abwin.winfo_reqheight()
        abwin.geometry('%dx%d+%d+%d' % (
            width, height,
            max(0, int(x + (w - width) / 2)),
            max(0, int(y + (h - height) / 2))))
        abwin.grab_set()
        return
