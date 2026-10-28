# 工作包 G 收尾记录

**状态：`WORK_PACKAGE_G_PARTIAL_READY_FOR_REVIEW`**

G0–G6 的限定范围已实现并通过本地独立数学、真实 Tk 与工程闭环验证；ACC-049、052、053 保持 `partial`，独立 Review 尚未提交。本记录不是 Review APPROVE。

## 独立 Review ITERATE 定向修复

- 静态单次观测：Smaller/Larger 的公式不需要样本方差；L4、replicates=1、无噪声时 Y=[2] 分别得到 −6.020599913279624 与 6.020599913279624。Mean 保持 2，SD/ln(SD) 为 unavailable；Nominal I/II 和 adjusted 仍拒绝 n<2。两类 S/N 均由真实 Tk 工程保存、重开并重新分析。
- 目标组合：目标均值/斜率按全部控制水平组合做加性预测并精确枚举；预算 20,000，大于当前最大候选数 15,625。L4 手算边际 A/B={14,26}、grand=20 的预测是 8、20、20、32；目标 20 并列 A1B2/A2B1，稳定选择 A1B2，且完整 L4 中该组合已观测。超预算时明确拒绝返回全局最优。负的加性 SD 预测显示不可用。
- L18：仍保留官方矩阵和原 SHA-256。内部列 8 对应官方表头列 9；实际分配到控制表或噪声表的列对若不平衡则分别拒绝。内部列 {1,2,8} 仍可正常创建；包含 {3,8} 的分配在 GUI、核心创建、工程恢复和分析入口均被阻止。

## Git 与边界

- 项目：`C:\Users\shaoy\.codex\worktrees\7256\Minijmp`
- G 开发基线：`c3720d2737f44ad130d8b61cd07ae31073073c2d`；合并前 `main` 已含 E/F，HEAD 为 `9e46bf3ac64ab76cf29598381e162d848cf6d997`。
- 本轮将 G 与 E/F 合并到本地 `main`；不推送。保留 E/F 独立工作树，不启动工作包 H。

## 阶段完成情况

| 阶段 | 实际完成 |
|---|---|
| G0 | 读取 AGENTS/MEMORY 与 DOE 文档；确认 schema v4 基线；从 Minitab 官方目录逐点抄录六个数组，取得四类静态 S/N、adjusted 与动态公式及选项页；建立 tests/fixtures/doe_taguchi_reference/（矩阵 CSV、manifest、手算 cases）与不导入生产模块的核验器。 |
| G1 | doe_taguchi_arrays.py 固定目录：L4、L8、L9、L16、L18、L25；每列平衡、实际分配列对频数、列子集重复行、水平数匹配、重复列与容量超限均校验；L18 控制表与噪声表分别拒绝不平衡列对，原矩阵 SHA-256 保持不变。 |
| G2 | doe_taguchi_sn.py 四类静态 S/N 与 adjusted nominal (I)、样本方差、定义域错误（含极值溢出/下溢与负值域）；Smaller/Larger 支持 n=1，SD/ln(SD) 为不可用而非零；响应表保留 Mean、可空 SD、S/N、效应、Delta、Rank、最优水平及可选 ln(s)。 |
| G3 | doe_taguchi_analysis.py 动态回归（自由截距、固定参考点）、斜率/截距/拟合/残差/SSE/MSE/df、动态 S/N 与 adjusted（r=Σ(signal−ref)²）。官方选项页的“按平均响应设参考点”未实现。 |
| G4 | 噪声稳健性按控制设定比较噪声条件间 Mean/SD/S/N，并输出控制因子水平响应表与 Delta/Rank；最大 S/N/最小 SD 保持逐因子选择，目标均值/斜率在 20,000 预算内精确枚举完整加性组合，稳定列出全部并列组合；负的加性 SD 标为不可用，未实测组合提示确认且不写回原始运行。 |
| G5 | Schema v5 增加 Taguchi 身份（kind/array_id/matrix_sha256/columns/noise_*/signal_factor）与 control_run_id/noise_condition_id；创建、分析、最佳设置界面；菜单三项；帮助主题；保存、重开、复制、再分析覆盖。 |
| G6 | 新增 6 个核心测试文件与 1 个 Tk 文件；更新 feature-matrix、acceptance、roadmap、sources、README、CHANGELOG、MENU_TRANSLATION、help/pages/doe.html 与帮助索引；G12 清单重新分类。 |

## 支持的数组与 SHA-256

| 数组 | 运行数 | 列水平 | SHA-256 |
|---|---:|---|---|
| L4(2³) | 4 | 2,2,2 | 36e38b04086c1cca2ff46858c444191aed0201aff98957c459cbf34b6ddb931e |
| L8(2⁷) | 8 | 2×7 | 3f2bcff42339aaa4ae214b46b95b1cc496158f5e1ef2b386189a9020185a51b6 |
| L9(3⁴) | 9 | 3×4 | 69b67312f67be4e18dd1e628975f4542ad12a5bd1ff137c833c495e7b6568da9 |
| L16(4⁵) | 16 | 4×5 | 1ff77c0da051f1b8158acfb9fc2dcbad7e2b85e064e8203bd47fa4553637dcb0 |
| L18(2¹3⁷) | 18 | 2,3×7 | 767f1ad05d8f96ba082346c8bd4c06bad848e7e82a88438d1756f6d6c3b99a76 |
| L25(5⁶) | 25 | 5×6 | 86845223d1e019205ad36faa592b62b7d87b546d34054d07ffb1374affd85ea2 |

静态与动态设计均可使用上述数组（动态需另有信号因子列）；L18 是唯一混合水平数组。未实现 L12、L27、L32、L36、L54 等目录条目，也不做自定义构造。

## 独立数值结果

静态 Y=[1,2]：smaller −3.979400086720376、larger 2.041199826559248、nominal (I) 6.532125137753438、nominal (II) 3.010299956639812、adjusted nominal (I) 6.020599913279624。

动态 signal=[1,2,3]、response=[2.0,4.5,6.0]：

- 自由截距：slope 2.0、intercept 0.16666666666666696、SSE 0.16666666666666666、df 1、MSE 0.16666666666666666、S/N 13.80211241711606。
- 过参考点 (2, 4.5)：slope 2.0、intercept 0.5、SSE 0.5、df 2、MSE 0.25、S/N 12.041199826559248；r=2，adjusted 11.903316981702915。

## 稳健性与预测范围

- 噪声稳健性：使用显式噪声正交表构成内外表；按控制设定与信号水平比较噪声条件间 Mean/SD/S/N，并给出控制因子水平的 Mean/SD/S/N 响应表与 Delta/Rank（专用 Tk 窗口）。未实现经独立验证的控制×噪声交互估计或稳健性优化，TAG-008 保持 partial。
- 最佳设置：支持最大 S/N、目标均值、最小 SD 与动态目标斜率四种依据；并列水平全部列出并确定性取第一个；预测同时给出 Mean/S/N/SD/斜率。确认实验可填写实测值与判定容差并在窗口内计算差值，不写回原表。交互修正最优与置信/预测区间未实现，TAG-009 保持 partial。
- 确认实验建议表独立展示，不写回正交表；未观测组合明确标记需要确认试验。

## Schema

- DOE_SCHEMA_VERSION = 5；v1–v4 仍按原字段与输入摘要校验后升级。
- 合并后的 v5 同时包含 E 的模型项/最优与增补谱系、G 的 Taguchi 身份及 control_run_id/noise_condition_id 映射；保留 E/F-only、G-only 与合并后 v5 工程读取形状，并规范化为并集字段。
- Taguchi 的控制运行/噪声条件 ID 纳入新输入摘要；旧 G-only v5 摘要继续按原格式校验，再规范化保存。
- 设计身份、数组矩阵摘要、列分配、角色、内外表与信号水平写入元数据；原始观测逐条保存，不保存聚合均值。
- 执行分析后，S/N 类型、adjusted、ln(s) 与动态参考形式（自由截距或固定参考点）作为可选 analysis 字段随工程保存，重开与复制时恢复；该字段只允许出现在 Taguchi 设计上，并按其静态/动态形状校验。
- 旧版 MiniJMP 不保证读取 v5 工程。

## 验证快照

| 组 | 命令 | 结果 |
|---|---|---|
| Taguchi 全组 | pytest tests/test_doe_taguchi_arrays.py tests/test_doe_taguchi_sn.py tests/test_doe_taguchi_dynamic.py tests/test_doe_taguchi_noise.py tests/test_doe_taguchi_persistence.py tests/test_doe_taguchi_references.py tests/test_doe_taguchi_gui.py -q | 138 passed、2 tight_layout warnings |
| Schema v1–v5 / 工作表工程 | pytest tests/test_doe_core.py tests/test_doe_factorial_schema.py tests/test_doe_schema_v2.py tests/test_doe_schema_v3.py tests/test_doe_persistence.py tests/test_worksheets.py tests/test_sheet_context.py tests/test_doe_taguchi_persistence.py -q | 121 passed |
| 菜单 | pytest tests/test_menu_localization.py -q | 66 passed |
| 帮助/G12 | pytest tests/test_help_center.py tests/test_g12_inventory.py tests/test_g12_tables.py -q | 37 passed |
| 基础 DOE / Split-Plot Tk | pytest tests/test_doe_gui.py tests/test_doe_splitplot_gui.py -q | 11 passed、4 warnings |
| Fractional / General Factorial / RSM / BBD Tk | pytest tests/test_doe_fractional_gui.py tests/test_doe_general_factorial_gui.py tests/test_doe_rsm_gui.py tests/test_doe_bbd_gui.py -q | 39 passed、6 warnings |
| 帮助索引 | python tools/build_help_index.py | 完成 |
| 静态检查 | python -m py_compile ...；git diff --check | 通过 |

各组存在重叠，不相加为唯一总数；未运行全量 pytest。

表内测试结果来自 G 提交合并前的快照。用户要求本次合并不执行测试，因此 E/F+G 合并后的工作树未运行 pytest。

## 未支持与集成待办

- Minitab 产品标准序、随机种子与未列数组配置未逐点核对；无产品导出证据。
- 动态 ANOVA F/p、平均响应参考点、预测/置信区间、控制×噪声交互与稳健性优化未实现。
- L18 官方页面自身 5 对列组合频数不均，已记录为构造事实；ACC-049 保持 partial。
- E/F 已在本次目标 `main` 中；其与 G 的共享 Schema v5 合并尚未在合并后运行测试验证。
- 独立技术 Review 尚未提交。
