# 工作包 C 实施与验收记录（2026-10-28）

> B 四项修复已进入联合工作区；当前联测和 Review 条件见 [B+C 联合收尾](work-package-bc-review-closeout.md)。本文首轮及过程记录均为历史。

状态：**WORK_PACKAGE_C_PARTIAL**。已实现并验证下述限定范围，但尚未取得所有正式验收要求的证据；独立 LRM Review 尚未提交，本地测试不等于协议级 APPROVE。

## 第二轮最终状态（2026-10-28）

HEAD 为 `886a0311164f691aba4c96093013f645107cb128`；保留本任务开始前的 B、C0、C 未提交改动，未提交或推送。下表是当前状态；其后“过程记录”和首轮范围保留历史，不作为当前支持范围。

| 验收 | 状态 | 已支持配置与证据 | 未支持 / 产品一致性阻断项 |
|---|---|---|---|
| ACC-001 | partial | PB 12/20/24/28/32/36/40/44/48；2 至运行数减 1 个连续或两水平文本因子；每重复中心点、分类组合伪中心、完整重复、按重复分区组及组内随机。NIST 原表和 Hadamard 数学构造的平衡、秩、混杂、列前缀、种子和恢复已核验；每个新增运行数的所有连续因子数真实 Tk 工程路径均已测，文本因子组合另有专项。 | 可选产品行为及 Minitab 22 点阵、标准序、随机序尚未导出核对；不能宣称产品全范围一致。 |
| ACC-002 | partial | 2–48 连续因子、1–47 连续加 1 分类因子、4 连续加 2 分类；完整重复均分区组。conference、有限域与反向配对独立核验水平、点数、秩、主效应与二阶项正交；全部新增高因子连续/单分类配置及双分类配置已做真实 Tk 工程路径。 | 其他多分类组合、额外中心点、产品伪中心算法及标准序未覆盖。 |
| ACC-003 | partial | 连续响应、手选主效应/平方/交互、区组调整、秩与零空间、可估系数及指定对比；独立线性模型和伪逆核验系数、残差、自由度和适用推断；真实 Tk 验证指定对比及重开再分析。 | 权重、自动选模等产品选项及产品输出一致性尚未实现或核验；不把所选模型的名义 p 值作为独立确认。 |
| ACC-005 | partial | 有有效残差时标准化 Pareto、正态和半正态效应图；饱和 PB 主效应的 Lenth PSE 与探索性参考线，零/不可辨误差时不伪造常规推断。独立数值、截断边界和图形参考线已测。 | 产品完整图形选项及逐项外观/算法一致性未核验；Lenth 依赖效应稀疏假设。 |
| ACC-006 | partial | PB 部分和完全混杂投影；DSD 主效应与选定平方/交互投影、零空间及可估对比；独立交叉积、秩、伪逆和真实 Tk 已测。 | PB 一般指定对比、其他多分类配置和产品专属 alias 表一致性尚未覆盖。 |

本轮最终代码的实际验证，各组可能重叠，不能相加为去重总数：

```powershell
& .\.venv\Scripts\python.exe -m pytest -p no:cacheprovider tests/test_doe_screening_references.py tests/test_doe_pb.py tests/test_doe_dsd.py tests/test_doe_screening_analysis.py -q --tb=short
# 136 passed；其后仅新增 C0 独立核验器回归，单独 1 passed
& .\.venv\Scripts\python.exe tests\fixtures\doe_screening_reference\dsd\verify.py
# 四个连续原始参考的哈希、整数交叉积与有理数秩通过；混合原始参考由上级 manifest 和 pytest 核验
& .\.venv\Scripts\python.exe -m pytest tests/test_doe_screening_gui.py -q --tb=short
# 118 passed，107 tight-layout warnings
foreach ($runs in @(24, 32, 36, 40, 44, 48)) {
    $cases = @(2..($runs-1) | Where-Object { $_ -ne 3 -and $_ -ne ($runs-1) } |
        ForEach-Object { "tests/test_doe_screening_gui.py::test_pb_new_run_counts_all_factor_counts_gui[$runs-$_]" })
    & .\.venv\Scripts\python.exe -m pytest @cases -q --tb=short
}
# 分别为 20、28、32、36、40、44 passed，各组 warnings 数与案例数相同；合计 200 个互不重叠案例
& .\.venv\Scripts\python.exe -m pytest -p no:cacheprovider tests/test_doe_core.py tests/test_doe_schema_v2.py tests/test_doe_factorial.py tests/test_doe_analysis.py tests/test_doe_fractional.py tests/test_doe_fractional_analysis.py tests/test_doe_ccd.py tests/test_doe_ccd_options.py tests/test_doe_bbd.py tests/test_doe_bbd_minitab_parity.py tests/test_doe_rsm.py tests/test_doe_rsm_categorical.py tests/test_doe_rsm_diagnostics.py tests/test_doe_optimize.py tests/test_doe_predict.py tests/test_doe_overlay.py -q --tb=short
# 316 passed
& .\.venv\Scripts\python.exe -m pytest tests/test_doe_schema_v3.py tests/test_doe_persistence.py tests/test_doe_gui.py tests/test_doe_fractional_gui.py tests/test_doe_rsm_gui.py tests/test_doe_bbd_gui.py tests/test_doe_ccd_options_gui.py tests/test_doe_optimize_gui.py tests/test_doe_predict_gui.py tests/test_doe_overlay_gui.py tests/test_menu_localization.py -q --tb=short
# 164 passed，11 tight-layout warnings
& .\.venv\Scripts\python.exe -m pytest -p no:cacheprovider tests/test_help_center.py tests/test_g12_inventory.py -q --tb=short
# 28 passed
```

GUI 首次完整回归发现旧测试仍将新支持的 5 连续 DSD 视为无效；改为仍不支持的 3 连续加 2 分类后，相关测试 2 passed，并完成上述完整 GUI 重跑。C0 连续参考核验器原先把只存在于上级清单的混合参考误要求在本地清单中；旧脚本实际失败，修复清单范围后新增回归 1 passed，原始八份参考矩阵和 SHA-256 未改。

PB 全部中间因子数的初次 200 案例 Tk 单进程接近结尾时发生 Windows 原生 `0x80000003`，未产生 pytest 汇总，不计为通过。按进度推定的 PB48/43 因子案例单独复跑 1 passed；上述六组独立进程随后全部完成并取得汇总。筛选核心组之后为“有残差自由度但残差方差为零”的既有案例补充不可推断断言，单独复测 1 passed。

可对已实现的限定范围发起独立 Review；五项官方完整范围仍为 partial，尚不能宣称完整验收或 Review APPROVE。所需 Minitab 22 导出配置见 [参考核验](screening-reference-validation.md)。未运行全量 pytest；工作包 B 的 CCD/RSM 专项缺陷未在本轮处理，未进入工作包 D。

## 第二轮过程记录（历史）

第二轮进度：PB24 已接入生成、Schema v3 和 GUI；NIST 原始表逐点核验、重复与 seed、真实 Tk 分析绘图和工程往返已通过。PB 基础运行数现为 12/20/24/28；32/36/40/44/48、中心点与区组及后续 DSD、统计扩展仍待完成。PB24 的 Minitab 标准序尚未核验。第二轮验证：筛选参考、PB 和 schema 39 passed；筛选 GUI 15 passed、5 warnings。以下首轮历史记录中关于 PB24 未支持的表述以本段为准。

随后 PB36 已接入上述路径；筛选参考、PB 和 schema 41 passed；PB36 真实 Tk 工程流程 1 passed、1 warning。当前 PB 基础运行数为 12/20/24/28/36，其余第二轮工作继续进行。产品标准序未验证。

PB32/40/44/48 已以 Hadamard 数学构造接入生成、恢复与 GUI。全部官方基础运行数现均可创建，但这些新增矩阵未证明与 Minitab 点序或混杂结构一致；32 的完全混杂已在分析中明确提示。核心参考/PB/schema 为 45 passed（该次测试后补充了固定投影断言），PB 与分析测试为 24 passed；PB 各运行数 GUI 生命周期 8 passed、6 warnings。中心点、区组、DSD 和后续验收继续进行。

PB 每重复中心点、按重复分区组和区组内随机化已实现。模型含中心点偏差及区组项；整体曲率 F 使用残差均方，纯误差按实际设置与区组组合计算。PB 和筛选分析 26 passed；含中心点/区组的 GUI 工程流程及非法配置不改变工作簿 2 passed、1 warning。旧版 schema 与全部筛选回归仍需在后续集成快照核验。

DSD 扩展至 2–10 连续因子和 1–5 连续加 1 分类因子；以原 C0 conference 矩阵列子集及单分类伪中心构造验证。DSD、schema v3、独立参考 45 passed；各新增连续和单分类配置及原有连续配置真实 Tk 生命周期 13 passed、9 warnings。Minitab 点序与分类伪中心未对标；其余因子数及多分类设计继续处理。

11–48 因子进一步使用 Paley conference、GF(25) 与 16 阶反对称 Hadamard 构造，连续和单分类设置的行数、水平、主效应及平方项秩、二阶正交、重复和恢复参数化测试与筛选分析合并 101 passed；完整二阶秩追加断言后仍需重跑。48 连续因子与 24 连续加 1 分类的 GUI 样本通过，全部高因子 GUI 正在串行测试；Minitab 产品标准序及多分类伪中心仍未对标。

高因子图形调整后，连续和单分类的全部 76 种新增配置真实 Tk 工程流程测试为 **76 passed、76 tight-layout warnings**；绘图展示所选两个因子的主效应和全部效应。未出现此前 48 因子布局无法应用的警告。

饱和 PB 主效应新增 Lenth PSE 和探索性参考线；存在有效残差时 Pareto 使用标准化效应和 t 参考线，两家族均可选择正态及半正态图。独立数值/截断边界与分析测试 11 passed；Lenth 和 DSD 三种图形的 Tk 验证 2 passed、2 tight-layout warnings；PB 标准化 Pareto 的数值与参考线 GUI 1 passed、2 warnings。效应稀疏及常规模型假设会在结果中说明。

DSD 秩亏模型现计算零空间和可估系数，支持指定线性对比并在可用残差自由度下计算推断；模型自由度采用实际秩。选定平方和交互项增加调整截距及所选主效应的投影表。独立参考分析测试 13 passed；秩亏、饱和与 Lenth 图形 GUI 3 passed、3 tight-layout warnings。完整二阶模型通常秩亏；多分类及产品对标仍未完成。

4 连续加 2 分类的数学构造已接入 Schema 与 GUI；独立 C0 矩阵转换、反向配对、秩和二阶正交测试与筛选分析合并 14 passed；双分类及秩亏 GUI 2 passed、2 warnings。其他多分类配置及 Minitab 迭代分配仍未覆盖。

PB 已支持两水平文本因子及按文本水平组合扩展的伪中心，全部文本因子不允许中心点；在分配运行列表前检查扩展后的总运行数。PB 与分析测试 31 passed；文本因子、区组和伪中心 GUI 工程流程 1 passed、1 warning。

DSD 现可把完整重复均分到区组，组内随机化并在模型中调整区组；不可均分的设置拒绝。独立区组模型及筛选分析测试 16 passed，真实 Tk 区组/双分类/秩亏测试 3 passed、3 warnings。PB 新增运行数 24/32/36/40/44 的满容量 GUI 工程流程 5 passed、5 warnings；48 次满容量 1 passed、1 warning。上述修改后的完整筛选及 GUI 回归仍需完成。

## 历史首轮：基线与范围

- Git `main`，基础 HEAD `886a0311164f691aba4c96093013f645107cb128`；工作区含 C0 与 C 本次未提交修改。应用关于窗口标识 `v0.1.0-beta.4`；未创建提交、标签或发布。
- C-A：Schema v3 新增 PB/DSD 类型、点类型和构造身份；工作表摘要先核对旧版原始字典再升级，v1/v2 可读取，旧版软件不承诺读取 v3。矩阵 SHA-256 依标准序、因子编码、点类型、重复及区组计算，随机运行顺序另由原输入摘要保护；响应与实测值可后填。恢复同时核对固定构造，不能仅用重新计算的摘要冒充来源。
- C-B：PB 基础运行数 **12、20、28**；连续因子分别支持 2–11、2–19、2–27 个，选固定参考矩阵前缀列；支持 seed、完整独立重复，单次运行上限 10000。额外中心点、区组及 24/32/36/40/44/48 次构造未支持。PB 主效应分析和交互投影不使用正规分数别名组。
- C-C：DSD 支持 **6/7/8/10 连续因子**与**4 连续加 1 分类因子**，分类因子为最后一列且恰有两个显式水平；连续因子三水平、混合构造使用两个伪中心。支持 seed、无区组完整重复；其他因子数量、多个分类因子、额外中心点和区组未支持。十进制中点沿用受控 binary64 舍入及精度检查。
- C-D：PB 主效应及 DSD 主效应、连续平方项、层级交互项使用实际矩阵进行最小二乘和秩检查；缺失响应或秩亏拒绝。残差自由度和误差方差有效时可提供 t/F 推断，需假设模型充分及误差独立、同方差、正态；饱和或不可辨误差不提供常规推断。未实现 Lenth PSE、自动选模或全体可估对比。两族有主效应、绝对效应 Pareto、残差与拟合值及正态概率图；不可推断时显示不可用。二阶投影是混杂说明，不是因果结论。
- C-E：已有真实 Tk 路径覆盖预览、创建、响应填写、分析、绘图、保存、重开、复制和再次分析；坏元数据不替换现有工作簿，来源切换、删除及设计/响应变化阻止旧图继续使用。完整外部产品对标与独立 Review 仍未进行。

## 历史首轮：逐项验收

| 编号 | 状态 | 本地证据与尚未覆盖 |
| --- | --- | --- |
| ACC-001 | partial | PB12/20/28 点阵逐点、平衡、正交、重复、seed 与三种运行数的 GUI/工程路径已测；其他官方运行数、中心点、区组及产品标准序未覆盖。 |
| ACC-002 | partial | 五种上述 DSD 点阵、实际水平、伪中心、独立参考及各配置的 GUI/工程路径已测；其余连续/分类组合和产品标准序未覆盖。 |
| ACC-003 | partial | 解析线性、平方和交互、多响应、缺失及饱和/秩亏案例已测；尚未证明全部配置或产品专有自动选模等价。 |
| ACC-005 | partial | 两族 GUI 有效应和 Pareto；混合 DSD 图形排序及 PB 正态概率图有真实 Tk 断言。未实现 Lenth PSE、完整产品图形选项及标准化效应线。 |
| ACC-006 | partial | PB12 已核对 −1/3 投影，混合 DSD 核对截距交互投影最大绝对值 1/7；实际模型秩亏拒绝。尚不提供一般可估对比或产品专属 alias 表完整一致性。 |

## 历史首轮：数学参考及验证

NIST PB 12/20/28 固定表、有限域 conference matrix 连续 DSD 和 Jones–Nachtsheim 单分类构造的来源、SHA-256、点集及独立性质见 [参考核验](screening-reference-validation.md)。例如 PB12/20/28 的 F1 对 F2×F3 投影分别为 −1/3、−1/5、−5/7。参考 fixture 不由生产代码计算；它们不是 Minitab 产品导出，不能证明 Minitab 标准序或随机序一致。

本轮实际执行（均为项目 `.venv` Python 3.11.9；测试组有重叠，不能相加为唯一总数）：

```powershell
& .\.venv\Scripts\python.exe -m pytest tests/test_doe_screening_references.py tests/test_doe_schema_v3.py tests/test_doe_pb.py tests/test_doe_dsd.py tests/test_doe_screening_analysis.py -q --tb=short
# 51 passed（含实测/响应后填、输入映射失效和数值不一致拒绝案例）
& .\.venv\Scripts\python.exe -m pytest tests/test_doe_screening_gui.py -q --tb=short
# 14 passed，4 tight-layout warnings
& .\.venv\Scripts\python.exe -m pytest tests/test_doe_core.py tests/test_doe_schema_v2.py tests/test_doe_persistence.py tests/test_doe_fractional.py tests/test_doe_fractional_analysis.py tests/test_doe_ccd.py tests/test_doe_ccd_options.py tests/test_doe_bbd.py tests/test_doe_bbd_minitab_parity.py -q --tb=short
# 187 passed（最终代码快照，80.26 秒）
& .\.venv\Scripts\python.exe -m pytest tests/test_doe_screening_gui.py tests/test_g12_inventory.py tests/test_menu_localization.py tests/test_help_center.py -q --tb=short
# 96 passed，2 tight-layout warnings（运行后筛选 GUI 增加边界测试及预览）
& .\.venv\Scripts\python.exe -m pytest tests/test_g12_inventory.py tests/test_menu_localization.py tests/test_help_center.py -q --tb=short
# 94 passed（最终代码快照）
& .\.venv\Scripts\python.exe -m pytest tests/test_doe_rsm_gui.py tests/test_doe_bbd_gui.py -q --tb=short
# 19 passed，3 tight-layout warnings
& .\.venv\Scripts\python.exe -m pytest tests/test_doe_gui.py tests/test_doe_fractional_gui.py tests/test_doe_rsm_gui.py tests/test_doe_bbd_gui.py tests/test_doe_ccd_options_gui.py -q --tb=short
# 首轮 41 passed、5 failed、6 warnings；上述两文件更新 v3 预期后重跑通过
& .\.venv\Scripts\python.exe -m pytest tests/test_doe_screening_gui.py tests/test_doe_gui.py -q --tb=short
# PB 概率图接入后的相关 GUI：10 passed、5 tight-layout warnings；后续筛选 GUI 又扩充并单独重跑
& .\.venv\Scripts\python.exe -m py_compile code/doe_core.py code/doe_pb.py code/doe_dsd.py code/doe_screening_analysis.py code/doe_screening_matrices.py code/doe_dialog.py code/MiniJMP.py
# 通过
git diff --check
# 通过；Git 提示部分文件的 CRLF 规范化
```

旧 GUI 五文件合并测试首次为 41 passed、5 failed、6 warnings；五项失败均是将新工程版本硬编码为 v2。按 v3 保存合同更新两处版本预期后，受影响 CCD/BBD 两文件重跑 19 passed。筛选 GUI 边界测试编写时两项因测试访问不存在的表名属性失败，修正测试获取工作表名的方式后，完整筛选 GUI 六项通过。

## 历史首轮：剩余工作与外部证据

本地证据覆盖上述限定构造与代表模型，不证明其他未覆盖的模型项组合。收齐 Minitab 确切版本、设计设置和原始工作表后才能比较标准序、随机序和其他分类配置。工作包 B 的已有数学定义未主动修改；其独立 Review 仍须单独确认。可以对当前有限范围开展独立审阅，不能据此声明完整官方范围或最终独立 Review 已通过。
