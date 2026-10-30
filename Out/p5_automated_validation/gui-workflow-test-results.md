# P2-5 GUI 工作流测试结果

日期：2026-10-30  
代码基线：main / 512f03a1e4fb8554748633fec086024375e4e4de

## 测试类别与边界

- **单元测试**：纯计算/边界断言；非 _gui.py 批次也包含集成测试，不把整批称为纯单元。
- **集成测试**：真实工作簿、元数据、保存/重开/复制和响应变化。
- **Tk GUI 工作流**：真实 Tk 根窗口和 MiniJMP 控件被创建；测试进程隐藏窗口，程序方式调用控件/回调，覆盖预览、分析、绘图、取消、失效和项目读回。
- **真实桌面 E2E**：没有 OS 鼠标/键盘驱动、可见屏幕检查或真实用户文件对话框；本轮未将隐藏窗口 Tk 测试称为桌面 E2E。

## 自动化结果

| 批次 | 范围 | 结果 |
|---|---|---:|
| DOE 非 _gui.py 文件批次 | 76 个文件，含单元及集成测试 | 1201 passed，12 warnings |
| DOE Tk GUI 文件 | 下表 16 个完整文件 | 139 passed |
| 筛选 GUI 隔离用例 | PB 创建/分析/绘图/保存、DSD mixed preview/persistence 各一项 | 2 passed |
| DOE 菜单与本地化 | tests/test_menu_localization.py | 66 passed |
| **合计** | 上述批次 | **1408 passed，69 warnings，0 failed** |

| 完整 GUI 测试文件 | 结果 |
|---|---:|
| test_doe_bbd_gui.py | 10 passed |
| test_doe_ccd_options_gui.py | 13 passed |
| test_doe_custom_gui.py | 7 passed |
| test_doe_foldover_gui.py | 2 passed |
| test_doe_fractional_gui.py | 15 passed |
| test_doe_general_factorial_gui.py | 3 passed |
| test_doe_gui.py | 5 passed |
| test_doe_mixture_gui.py | 10 passed |
| test_doe_optimal_gui.py | 6 passed |
| test_doe_optimize_gui.py | 9 passed |
| test_doe_overlay_gui.py | 4 passed |
| test_doe_p4a_gui.py | 12 passed |
| test_doe_predict_gui.py | 7 passed |
| test_doe_rsm_gui.py | 12 passed |
| test_doe_splitplot_gui.py | 10 passed |
| test_doe_taguchi_gui.py | 14 passed |
| test_doe_screening_gui.py 指定 PB node | 1 passed |
| test_doe_screening_gui.py 指定 DSD node | 1 passed |

筛选 GUI 全文件历史记录为 318 例规模，曾出现长耗时和解释器级中断。本轮启动后在汇总前停止全套，**不计其部分进度或结果**。随后 PB 和 DSD 两个指定 node 在独立进程通过；其余筛选 GUI 参数化边界/工作流未运行。

非 _gui.py 的 76 文件批次另含 7 个 Tk 集成文件、101 项，均包含在 1201 passed 中：test_doe_efg_workbook_integration.py、test_doe_e_lifecycle.py、test_doe_h_lifecycle.py、test_doe_mixture_persistence.py、test_doe_persistence.py、test_doe_schema_v3.py、test_doe_taguchi_persistence.py。

## 警告与人工抽检

- Matplotlib tight_layout 在绘图流程产生布局提示；没有像素截图复核。
- test_doe_custom_gui.py 的 DejaVu Sans 报告若干中文 glyph 缺失；按 PRESENTATION_DIFFERENCE 记录，不据此认定计算或 GUI 流程失败。
- 本机测试不能证明 event_generate('<KeyRelease>') 会产生真实桌面键盘事件；历史记录中该事件不投递，相关测试直接调用绑定处理函数。

人工抽检项（本轮未执行）：

1. 可见 Windows 桌面启动；真实菜单打开 PB、DSD、CCD/BBD、Taguchi、Mixture、最优设计与预测/分析窗口。
2. 鼠标/键盘执行预览、取消、提交、帮助、窗口关闭和焦点/快捷键；检查高 DPI、小窗口和滚动。
3. 观察响应面、Pareto/效应图、Taguchi/Mixture 图表的中文字体、图例、刻度和布局。
4. 经原生文件选择器保存、关闭、重开 .dexpl；验证当前工作表、响应、分析结果和菜单上下文。
5. 手动触发输入错误、无效区组、空可行域及源数据变化后的提示/失效。

## 可复跑命令

```powershell
$python = (Resolve-Path ".venv\Scripts\python.exe").Path
$files = @(rg --files tests -g 'test_doe*.py' | Where-Object { $_ -notmatch '_gui\.py$' })
& $python -m pytest -q @files
& $python -m pytest -q tests/test_menu_localization.py
```

完整 GUI 文件逐个串行运行；screening 两个 node 独立运行。原始输出保存在 pytest-doe-non-gui.log 和 pytest-doe-gui.log。