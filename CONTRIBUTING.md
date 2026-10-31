# How to contribute

## Developers

Any programmers interested in contributing are welcome. Have a look through the code to judge any weaknesses or
if it's amenable to easy changes. There are currently deficencies in error checking and exception handling 
for example which have not yet been addressed due to time.

## End users

Contributions from educators who might want to use this software are sought. This could come in the form of testing and
requesting new features.

## 变更关联检查

在仓库根目录执行检查，先确认 `.venv` 是本项目可用的解释器环境：

```powershell
$python = (Resolve-Path ".venv\Scripts\python.exe").Path
$env:PYTHONIOENCODING = "utf-8"
& $python -c "import sys; print(sys.executable); print(sys.version)"
```

按实际变更选择下表中的既有检查；清单需要人工复核后更新。

记录测试日志时，Python 子进程输出与日志读取均使用 UTF-8；在新的 PowerShell 会话中重新设置上述编码变量。历史原始日志保留原样。

| 变更触发条件 | 关联文件与已有工具 | 对应测试 |
| --- | --- | --- |
| 新增、删除 `code/` 下的 Python 文件，或修改统计报告生产位置 | `tests/fixtures/g12_table_inventory.json`：复核文件集合、`file_reviews`、生产位置及计数 | `tests/test_g12_inventory.py` |
| 新增、调整菜单入口 | `code/MiniJMP.py`、`docs/MENU_TRANSLATION.md`、`tests/test_menu_localization.py` 中的菜单预期；图形菜单还需同步 `help/pages/graphs.html` 的目录与章节 | `tests/test_menu_localization.py` |
| 新增帮助主题、修改主题映射或帮助正文 | `help/help-map.json`、对应 `help/pages/*.html`；执行下方已有工具重新生成 `help/assets/search-index.js` | `tests/test_help_center.py` |

```powershell
# 修改帮助后生成搜索索引
& $python tools/build_help_index.py

# 按上表选择需要的测试文件，也可合并执行以下快检
& $python -m pytest tests/test_g12_inventory.py tests/test_menu_localization.py tests/test_help_center.py -q
```

## Windows Tk 截图

生成 Windows Tk 界面验收截图时，可使用 `ImageGrab.grab(window=window.winfo_id())` 按窗口句柄捕获。
生成后打开图片，确认内容属于目标窗口，再作为验收证据。

模拟 Matplotlib 鼠标拖动时，`motion_notify_event` 的 `MouseEvent` 使用
`buttons={1}` 表示左键持续按下；按下和释放事件使用 `button=1`。
仅给移动事件传 `button=1` 不表示持续按下，标准导航可能取消缩放。
缩放、复位及现有图窗保存入口的验证可复用
[test_real_sheet_fit_plot_export_and_report](tests/test_capability_dialog.py)
（完整测试定位：`tests/test_capability_dialog.py::test_real_sheet_fit_plot_export_and_report`）。
