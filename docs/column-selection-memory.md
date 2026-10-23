# 数据列预选与记忆

明确的表格列选区优先；没有可用选区时，恢复同一功能、同一字段角色上次成功执行的有效列名，否则留空。多列选区按工作表列顺序处理；初始化的 `currentcol=0` 不算真实选区。自动填入的不同角色不会重复使用同一列，仍可手动改选。

Windows 保存于当前用户的 `HKCU\Software\MiniJMP\ColumnSelections`；其他平台保存于 `~/.config/MiniJMP/column_selections.json`。仅保存功能标识、字段角色与列名，不保存列数据。按数值角色预选时，保守地只接受 pandas 数值类型；数字文本仍可手动选择。非字符串列名、空列名及重复列名不自动恢复。

取消、关闭、校验提前返回或执行抛错不保存。绘图预览在成功渲染并替换结果后保存；茎叶图在成功输出后保存。汇总样本输入不覆盖未实际使用的数据列角色。对话框继续使用打开时绑定的源工作表。

## 覆盖范围

- 描述性统计、多变量描述性统计、正态性检验、置信区间、分布拟合。
- 线性回归、正交回归、相关分析、残差图、多变量相关分析。
- 单样本 t/Z/标准差检验、双样本 t、配对 t、多样本方差检验、均值比较 t、双因子 ANOVA。
- 交叉及嵌套量具 R&R、过程能力、含子组过程能力、正态公差区间。
- I/MR、I、MR、Xbar/R、Xbar/S、NP、P、C、U 控制图。
- 单列直方图及分布拟合、二维直方图。
- 独立条形图、饼图、区域图、点图、矩阵图、等值线图、三维散点图、曲面图；按图形种类分别记忆。
- 独立气泡图、边际图、经验分布图、个体值图、均值区间图、样本概率图、茎叶图；按图形种类分别记忆。

## 留存特例

单因子 ANOVA、分组/多列直方图、箱线图、分类计数图、分组折线图及分组点图混合了原始列、分类列和多列备选输入模式，暂不自动注入。比例检验、列联表/比例卡方检验、时间序列的轴映射、概率分布参数和通用绘图器也未接入本次记忆。保持这些入口的既有行为。

## 验证边界

专项测试覆盖真实 Tk 控件预选、优先级、无效索引与历史、角色去重、手动改选、取消及失败不保存、实际描述性分析、多列执行、绘图预览提交、源工作表绑定、文件读写及模拟注册表读写。既有图形与工作表测试用于回归。

尚未人工关闭并重启整个 MiniJMP 验收；注册表验证使用模拟后端，不改动用户真实偏好。

2026-10-22 最终验证（项目 Python 3.11.9）：

```powershell
& .venv/Scripts/python.exe -m pytest tests/test_column_selection.py tests/test_sheet_context.py tests/test_table_regressions.py tests/test_phase1_plots.py tests/test_phase2_plots.py tests/test_dialog_translation.py -q --basetemp=.pytest_cache/column-selection-verified
```

结果：407 passed，6 条既有 pandas 绘图警告；其中列选择专项 20 项。`git diff --check` 通过。

额外执行 G12 清单检查时，`test_all_python_files_and_production_sites_are_classified` 失败：HEAD 已跟踪的 `code/icon_resource.py` 不在 HEAD 的清单文件中，属于本次改动前的清单缺项，未修改该清单。
