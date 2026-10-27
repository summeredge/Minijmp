# DOE-3 收尾报告

日期：2026-10-27  
项目：`C:\Users\shaoy\Documents\Minijmp`  
基线：`main` / `origin/main`，HEAD `618a19203f9e77d7b37ecdf637707a02c456fd15`；开始时工作区干净。

## CCD 数值政策

CCD 的纯整数文本保留为 Python 整数；包含小数点或指数的文本先验证为有限 Decimal，再由 Python 转为 binary64 最近值（ties-to-even，输入表示误差不超过 0.5 ULP）。原始输入文本不进入工作表或 `.dexpl`。例如：

| 输入 | CCF | CCC，2 因子 alpha=√2 | 判据 |
| --- | --- | --- | --- |
| `0.1` / `0.2` | 接受；中心 `0.15000000000000002`，轴点 `0.1` / `0.2` | 接受；轴点约 `0.07928932188134524` / `0.22071067811865477` | 十进制转最近 binary64；中心和轴点保留可分辨 |
| `1.1` / `2.3` | 接受；中心 `1.7` | 接受；轴点约 `0.851471862576143` / `2.548528137423857` | 普通十进制水平 |
| `65.3` / `68.3` | 接受；中心 `66.8`，轴点保持端点 | 接受；轴点约 `64.67867965644035` / `68.92132034355964` | 实际值和响应面矩阵完成往返核对 |
| `65.5` / `68.3` | 接受；中心 `66.9` | 接受；轴点约 `64.92010101267766` / `68.87989898732233` | 可精确表示和近似表示的混合输入 |
| `-0.1` / `0.3` | 接受；中心约 `0.09999999999999999` | 接受；轴点约 `-0.18284271247461903` / `0.38284271247461904` | 负值与跨零范围 |
| `1e-300` / `2e-300` | 接受；中心 `1.5e-300` | 接受；轴点约 `7.928932188134525e-301` / `2.2071067811865475e-300` | 极小但仍可分辨的值 |
| `1e300` / `1.1e300` | 接受；中点保留为精确整数值 | 接受；轴点约 `9.792893218813452e299` / `1.1207106781186549e300` | 极大有限值；中点可精确保存为整数 |
| `NaN`、`Infinity`、`1e309`、`1e-999` | 拒绝 | 拒绝 | 非有限、溢出或非零下溢 |
| `1.0` / `1.0000000000000001` | 拒绝 | 拒绝 | 转 binary64 后端点重合 |
| `1.0` / `1.0000000000000002` | 拒绝 | 拒绝 | 中心舍入到端点 |
| `1.0` / `1.0000000000000007` | 拒绝 | 拒绝 | 中点虽然可区分，但反算编码误差超过 `1e-8` |
| `1.0` / `1.0000000000000004` | 接受 | 拒绝 | CCC 轴点舍入后落回端点，不能仍标作 `±alpha` |
| `2^60+1` / `2^60+1025`（纯整数文本） | 拒绝 | 拒绝 | 输入整数本身精确保留，但 CCD 端点不能无损转 binary64 |

纯整数文本 `9007199254740993` 保留为精确整数；写成 `9007199254740993.0` 时属于小数格式，按 binary64 最近值成为 `9007199254740992.0`。需要保留大整数原值时应使用纯整数文本，CCD 会在不能无损转为 binary64 时拒绝。浮点表示误差不代表工艺公差或设备分辨率。

中心点按存储端点的精确中点计算；整数中点保留为整数，精确 binary64 中点保留为浮点数，其他中点舍入到最近 binary64。CCF 轴点直接取转换后的 low/high。CCC 轴点以存储端点和 binary64 alpha 的精确有理数值计算，再舍入到最近 binary64；舍入后须保持在端点之外，中心及轴点必须有限、可区分，且按实际设定值反算编码与声明编码相差不超过 `1e-8`。`.dexpl` 的 schema v1 未变，保存并恢复转换后的 int/float；不保存原始输入文本。DOE-0/1/2 的编码、生成元、别名与统计语义未修改。

## 实现与独立验证

- `code/doe_dialog.py`：将 CCD 专用解析与 DOE-0/1/2 的通用解析分开；保留纯整数，拒绝非有限、溢出和非零下溢。
- `code/doe_ccd.py`：中心舍入规则在创建和恢复校验间共用；CCF 轴点保留端点；CCC 以精确有理值计算轴点并舍入一次，拒绝轴点与端点重合或编码误差超限。
- `tests/test_doe_ccd.py`：覆盖 8 组十进制/指数范围的 CCF/CCC 输入、编码反算、极大/极小值、非有限值、下溢、整数写法区别、端点/中心坍缩与 CCC 轴点回落端点。
- `tests/test_doe_rsm.py`：用独立 Fraction 公式从实际设定值重建编码，以 `Y=40+3A−2B+4AB+5A²−1.5B²` 验证完整二次模型恢复。
- `tests/test_doe_rsm_gui.py`：真实 Tk 下使用 `0.1/0.2`、`65.3/68.3` 创建 CCC，检查取消/确认、分析与图形，以及 `.dexpl` 保存、关闭重开和复制后的数值不变。
- 复杂度审查发现近 ULP CCC 轴点可能舍入回端点，已增加明确拒绝条件与复现测试；保留 CCD 专用 helper 和 Fraction 计算，因为它们分别统一中心策略、避免 DOE-0 合同变化，并保证最终只舍入一次。

## 环境与验证结果

- 解释器：`.venv\Scripts\python.exe`，Python 3.11.9 x64。
- 依赖：pandas 3.0.6、NumPy 2.4.6、SciPy 1.15.3、Matplotlib 3.11.2、pytest 9.1.1；`pip check` 报告无损坏依赖。
- Windows Python 3.11 锁文件 SHA-256：`6EAA711EFEA51BB277F3B7C99F865EFDD2A21F3557A91CC3C5F7B11F7039B50D`。
- 当前改动后的收集数：`3974 tests collected in 3.07s`。该命令只收集测试，不执行测试。
- 最终相关回归命令在项目根目录执行：

```powershell
& .\.venv\Scripts\python.exe -m pytest tests/test_doe_core.py tests/test_doe_persistence.py tests/test_doe_ccd.py tests/test_doe_rsm.py tests/test_doe_rsm_gui.py tests/test_doe_factorial.py tests/test_doe_analysis.py tests/test_doe_gui.py tests/test_doe_fractional.py tests/test_doe_fractional_analysis.py tests/test_doe_fractional_gui.py tests/test_worksheets.py tests/test_sheet_context.py tests/test_file_io.py tests/test_worksheet_formulas.py tests/test_plot_window_lifecycle.py tests/test_help_center.py tests/test_menu_localization.py tests/test_g12_inventory.py -q --tb=short
```

结果：**403 passed，14 warnings**，83.78 秒；无失败或跳过。14 条警告是既有绘图提示：5 条 `PlotViewer.tight_layout()`、Seaborn palette/hue 提示、Matplotlib 箱线图 `vert` 弃用，以及 `scatter_matrix` 清理传入 axes 的提示；未涉及 CCD 数值或 DOE 统计计算。

随后补充了 `9007199254740993.0 → 9007199254740992.0` 的文本形式断言，并将被修改的边界测试单独复跑：`tests/test_doe_ccd.py::test_ccd_number_preserves_large_integer_and_rejects_float_collisions`，结果 `1 passed`。这是 403 项回归中的同一测试，不另行累加总数。

帮助索引由 `& .\.venv\Scripts\python.exe -m tools.build_help_index` 生成；核对后共 91 个主题，只有 `doe.ccd` 文本变化。帮助、菜单和 G12 测试均包含在上述回归命令中。`git diff --check` 通过。

## 全量 pytest 与剩余限制

当前 HEAD 没有完整全量通过记录。唯一历史 `3,810 passed` 来自 DOE-3 之前的 pandas 迁移基线，不作为本轮结果。干净 HEAD `618a19203f9e77d7b37ecdf637707a02c456fd15` 上曾两次实际运行用户要求的完整命令：

```powershell
& .\.venv\Scripts\python.exe -m pytest -q --tb=short
```

两次均约在进度 98% 时以退出码 `1` 结束，Python/Tk 报 `Windows fatal exception: code 0x80000003`，栈位于 `tkinter.Menu.add` → 通用 `createPulldown` → 绘图菜单创建。pytest 未产生终端 summary，因此这两次的 passed/failed/skipped/warnings 计数和运行时长均不可用。末段工作表 GUI 用例单独运行 `1 passed`；`docs/capability-validation.md` 还记录了 DOE-3 之前一次相同原生异常。没有证据把该问题归因于 CCD 改动，当前也没有在修改后的代码上执行全量套件；完整单进程全量结果仍未验证。

最终基线仍是 `main`/`origin/main` 的 HEAD `618a19203f9e77d7b37ecdf637707a02c456fd15`。本地 `v0.1.0-beta.4` 标签仍指向 `1f94aac97c1af09abfdaefa6c75cb3bb6a22740d`。未提交、推送、发布或改动标签。工作区保留本报告、代码、测试及对应文档改动，待用户审阅提交。
