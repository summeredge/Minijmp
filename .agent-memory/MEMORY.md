# MiniJMP 工作记忆

## 工作包 F 混料设计（2026-10-28，隔离 worktree）

- 状态 `WORK_PACKAGE_F_READY_FOR_REVIEW`；BASE `c3720d2`，worktree `C:\Users\shaoy\.codex\worktrees\e9e5\Minijmp`（detached HEAD），未提交/推送/合并，未启动 G/H。E 最终 Schema 合并、跨 E 联合回归和独立 Review 未完成。
- 新增 `code/doe_mixture*.py` 九个模块：约束、专属合同、三类设计、Scheffé 模型/ANOVA、预测、优化、图形、GUI。菜单新增创建/分析/预测/优化/图形五项；帮助新增 `doe.mixture*` 并重建索引。
- 混料语义存 `table.mixture_metadata`（schema 1），最近分析模型存 `table.mixture_model`（响应/阶次/模型项/输入摘要），DOE v4 仅新增 `design_type='mixture'`，不改 v4 字段集；`worksheets.saveMeta/loadMeta` 先验证后赋值。总量目前固定一个设计设定，MIX-005/ACC-036 为 partial。
- 独立参考 `tests/fixtures/doe_mixture_reference/`（Fraction + 自写高斯消元），`reference.json` SHA-256 `8ae2c0712fdb423a0570336ebf96cca0dd8366e56c7dddf1be007ad36099c913`；覆盖格点/重心/5 顶点/ANOVA/优化网格/Trace/叠加 11 点。
- 独立 Review ITERATE 五项已修复：默认 Mixture×Process 去掉过程主项 `P`（保留 `xi*P` 与秩检查）、模型 F/df 改用增量秩（校正/未校正平方和分流）、可估计性改判行空间、组分主项只报删除项条件平方和、双组分图形改为拒绝二维并提示 Trace。closeout 文档含“Review ITERATE 修正”段。
- 验证快照（最终状态）：混料 12 文件 64 passed（24.01s）；DOE 非 GUI 427 passed（348.77s）；既有 DOE GUI 15/11/9/13/10 passed；菜单/帮助/G12/工作表/文件/工程 173（菜单单项 66）。测试组重叠，全量 pytest 未运行。
- ACC-032/033/034/035/037/038/039/040/041/042/043/044 implemented（限定范围），ACC-036 partial；Minitab 标准序、XVERT/CONAEV 顺序、图形布局与预测区间未核实。详见 `docs/doe-minitab/work-package-f-closeout.md` 与 `work-package-f-integration-plan.md`。

## 工作包 D D0–D5（2026-10-28，本地收尾）

- 独立 Review 遗留两项已修复：General Full Factorial 创建与恢复统一限制 2–10 因子（1/11 拒绝，10 因子仍受 10,000 行上限）；Split-Plot 预览显示运行/区组/整区数，仅插入前 100 行并提示总数，增加水平滚动，实际创建保持完整。专项八文件 42 passed、D 非 GUI 182、B/C 非 GUI 358、Factorial Tk 22、菜单帮助/G12 94 passed；测试组重叠，全量 pytest 未运行。ACC 状态未变，工作区仍未提交。
- 状态 `WORK_PACKAGE_D_READY_FOR_REVIEW`；BASE/HEAD `e7a46737612cf5b56cd7d02911c4d13ec4753087`，分支 `main`，开始时工作区干净。D0–D5 限定范围已完成；独立网页端 LRM Review 尚未执行，未提交/推送，不启动 E/F/G/H。
- D0 独立参考位于 `tests/fixtures/doe_factorial_reference/`，`reference.json` SHA-256 `0c3e379a6962efe224695ba79a21d101319d4298d1ed6962c9a8a9b6dfef37ba`；包含一般全因子、正负定义关系、Foldover 完整别名/精确秩、完整区组和 3-block 2×2 Split-Plot SS/df/F/p。核验器不导入生产模块。
- DOE Schema 当前 v4；v1/v2/v3 按旧字段与原输入摘要校验后迁移。D1 一般全因子范围为 2–10 分类因子、文本/数值标签、完整笛卡尔积和完整重复区组；分析密集矩阵上限 10,000,000 个单元。旧版 MiniJMP 不保证读取 v4 工程。
- D2 正规分数支持 signed generators、中心点和每个完整重复一区组；Foldover 只支持未分区组正规分数的全因子或单因子单批次，保留响应并存 parent/run map/batch 和原始/当前矩阵 SHA-256。PB、Split-Plot、重复折叠和 Minitab 输出/标准序未覆盖；FAC-012 维持 partial。
- D3 区组仅按完整重复分配，适用于两水平全因子、正规部分因子和 General Full Factorial；中心点须平均分配。Split-Plot 限两个连续两水平因子、一个 hard-to-change 与一个 easy-to-change、至少两个平衡区组；A 用整区误差，B/AB 用子区误差。自定义区组分割、更大/不平衡裂区和 REML 未覆盖，FAC-008/010/019 为 partial。
- D3 验证快照：数学/Schema/区组/Split-Plot 专项 140 passed；Foldover+独立参考 13 passed；普通 DOE GUI 5 passed（2 warnings）、Fractional GUI 15 passed（1 warning）、Split-Plot GUI 2 passed（1 warning）、Foldover GUI 2 passed、menu 66 passed、help/G12 28 passed；帮助索引成功重建。测试组有重叠，未运行全量 pytest。
- D4 统一三类 factorial 分析器的 pure-error/区组误差分解；无独立纯误差时不输出 LOF F/p。中心曲率使用独立纯误差；分层 ANOVA 与真实水平诊断图有独立参考验证。ACC-007/011/013/015/017/018/066 及未核实产品范围维持 partial。
- 验证快照：factorial 分析/误差分解 45 passed；D 非 GUI 设计/Schema/分析组 176 passed；B/C 非 GUI 回归 358 passed（310.15 秒）。GUI 分组、帮助、菜单、工作表和文件测试明细见 `docs/doe-minitab/work-package-d-closeout.md`；各组重叠，不相加，全量 pytest 未运行。
- D5 的创建、预览、响应填写、分析、图形、保存/重开/复制/再分析和旧 Schema 回归已覆盖。帮助索引重建成功；Help/G12 28 passed、menu 66 passed；独立 factorial verifier 通过。
- 筛选 Tk 大文件本轮未完整执行：约 22% 时停止长进程；D4 影响的 PB 绘图和代表性 DSD 工程用例分组复跑通过，但该整文件未在最终快照重跑。独立网页端 LRM Review 尚未执行，未提交/推送。

## 工作包 B+C 联合 Review 收尾（2026-10-28）

- 状态 **BC_READY_FOR_INDEPENDENT_REVIEW**：HEAD `886a0311164f691aba4c96093013f645107cb128`，B 四项阻断修复已在联合工作区本地验证；C 的 ACC-001/002/003/005/006 仍 partial，独立 LRM Review 尚未通过。完整范围、未提交文件清单、测试与外部参考缺口见 `docs/doe-minitab/work-package-bc-review-closeout.md`。
- 官方确认 SCR-005 自定义筛选定义；MiniJMP missing，追加 ACC-067 并规划后续 E，本轮未实现。DSD 4 连续加 2 分类的主效应不两两正交，与二阶项交叉积为零；新增独立交叉积回归。
- 联合快照：B 核心/对标/旧工程 274 passed，DOE-1/2 52 passed，C 核心/schema 156 passed，双分类交叉积专项 1 passed；B Tk 69 passed、11 warnings，C Tk 118 passed、200 deselected、107 warnings；帮助/菜单/G12/工程基础 163 passed。历史 PB 中间因子数 200 项未在本次重跑，不能当作联合快照新测试。测试组重叠，不相加；全量 pytest 未运行。
- 已重建帮助索引；八份 C0 矩阵与五份用户提供的 Minitab 22 BBD 参考按清单校验。未提交、未推送、未启动 D；下一步针对限定范围独立 Review，产品标准序和其他设置仍需外部导出。

## 工作包 C 第二轮收尾（2026-10-28）

- 最终审计补齐 PB 新增六种运行数的全部连续因子数真实 Tk 工程流程：原 200 案例单进程接近尾声时触发 Windows Tk 原生 `0x80000003`，无汇总，不计通过；按进度推定 PB48/43 单独 1 passed。按运行数拆分独立进程重跑，PB24/32/36/40/44/48 分别 **20/28/32/36/40/44 passed**，共 200 个互不重叠案例，各组 warnings 数与案例数相同；前述 118 项已覆盖各运行数的 3 因子及满容量。

- 状态 **WORK_PACKAGE_C_PARTIAL**：PB 全部官方基础运行数、文本因子与伪中心、重复区组；DSD 2–48 连续、1–47 连续加 1 分类、4 连续加 2 分类及完整重复均分区组；Lenth PSE、标准化效应图、DSD 零空间和对比已实现。ACC-001/002/003/005/006 均仍 partial，产品标准序、多分类及其他产品选项未齐；可对限定范围发起独立 Review，尚无 APPROVE。构造、验收与 Minitab 22 导出需求见 `docs/doe-minitab/work-package-c-closeout.md` 和 `docs/doe-minitab/screening-reference-validation.md`。
- Schema v3 对 PB/DSD 的矩阵来源、编码、标准序、重复和区组做摘要及固定构造复核；v1/v2 可读并升级，响应/实测可后填。原八份 C0 数学参考与 SHA-256 未改；不能将数学构造与产品逐点一致混为一谈。
- 最终代码验证：筛选参考/PB/DSD/分析非 Tk **136 passed**，核验器新增回归 **1 passed**；筛选 Tk GUI **118 passed、107 tight-layout warnings**；DOE-0～4 非 Tk 与 schema v2 **316 passed**；schema v3、工程持久化、DOE GUI 与菜单 **164 passed、11 warnings**；帮助/G12 **28 passed**。测试组重叠，不相加；全量 pytest 未执行。
- 修复 C0 的 DSD 独立核验脚本清单范围不一致：本地 manifest 仅有四个连续参考，混合参考由上级 manifest 测试；旧脚本失败，修复后四项精确审计和新增回归通过。自动检查缺失的过程细节见 `logs/2026-10-28.md` 与 C 收尾报告。
- 未提交、未推送、未启动工作包 D；B 的 CCD/RSM 图形缺陷另行处理。工作包 C 首轮及第二轮阶段过程详见上述收尾报告和当日日志。

## 工作包 C0 技术准备（2026-10-28）

- HEAD `886a0311164f691aba4c96093013f645107cb128`；C0 结论为 C0_READY_FOR_REVIEW，等待网页端独立 Review。未实现 PB/DSD 生产功能，B 的独立 Review 也未完成。SCR-001/002/003 保持 missing、SCR-006/007 保持 partial。
- 已建立 NIST PB 12/20/28、独立 conference matrix DSD 6/7/8/10 全连续及 4 连续加 1 分类 DSD 矩阵与 SHA-256、可执行数学核验；Schema v3 迁移方案与 ACC-001/002/003/005/006 的 STD/EDGE/GUI/PERSIST 合同见 `docs/doe-minitab/work-package-c0-closeout.md`。
- 本轮旧 Schema/持久化/分数设计回归 52 passed；筛选矩阵审计 9 passed，DSD 精确构造审计 4 个通过。Minitab 产品标准序及其他分类组合、规模、区组和 seed 的逐点一致性仍未验证；后续先 Review，再冻结 Schema，未核实配置取得参考前暂缓。

## 工作包 B Review ITERATE（2026-10-28）

- 用户提供并确认 Minitab 22 五份原始 CSV：9 因子无区组/5/10 组和 10 因子无区组/2 组。独立数学与多重集审计均通过；点集及区组重编号后逐点分配一致，标准序不同。ACC-022B 在这五份指定设置下数学等价通过，独立 Review 仍未提交；详情及哈希见 `docs/doe-minitab/bbd-reference-validation.md` 和 fixture manifest。

- 用户批准 ACC-022 分层：022A 数学和工程为功能 Review 必需，022B Minitab 精确一致性 pending_external_reference 不阻断。现已按 Box–Behnken (1960) 表 4 实现 9/10 因子及正交区组，并修复显式中心点与重复/分类组合合同；022A 本地验证通过，RSM-002 implemented，独立 Review 待网页端发起。证据与命令见 `docs/doe-minitab/work-package-b-closeout.md`；不进入 C。
- 公共 DOE 合同修复后补跑 DOE-1～4 及响应面相关核心回归 187 passed；两种 computer-use 初始化入口均因 kernel assets 路径错误不可用，网页 Review 请求尚未提交。

- 后续补全：6/8/9/10 因子 CCD 真实 Tk 工程关闭、重开、复制及二次分析通过；本轮核心 181、GUI 30（3 warnings）、菜单/帮助/工作表 163 项通过，测试组不可相加。原始 Box–Behnken 论文与 Crosier 10 因子表均不足以证明 Minitab 逐点等价；五种导出需求见 `docs/doe-minitab/bbd-reference-validation.md`，ACC-022 仍 partial，工作包 B 未完成。

- 第二轮已修复 CCD 6/8/9/10 因子 GUI 入口和分类预览/CCC 确认，响应优化高维起点有界；核心 241、GUI 51（10 warnings）、菜单/帮助/G12/工作表 163 项通过；帮助更新后 94 项通过，新增 GUI 文件 11、优化文件 50 项通过（各组有重叠）。9/10 BBD 官方点阵及区组仍无证据，工作包 B 未完成，见 `docs/doe-minitab/work-package-b-closeout.md`。

- 已修复分类水平被混入纯误差与带区组优化等高线，独立参考及真实 Tk 已验证；带区组曲率未调整区组，F/p 不提供。详见 `docs/doe-minitab/work-package-b-closeout.md` 与 `logs/2026-10-28.md`。
- 9、10 因子 BBD 标准矩阵及官方区组方案尚未完成，RSM-002 partial、ACC-022 未完整通过；等待网页端最终 Review，不进入工作包 C。

## 工作包 B（2026-10-27，收尾）

- 已完成 B1–B4 代码：schema v2（box_behnken、edge、ccd_fraction、block_count；v1 可读并升级）、doe_bbd.py、doe_rsm_model.py、doe_predict.py/doe_predict_dialog.py、doe_overlay.py/doe_overlay_dialog.py；CCD 分数/区组/分类因子、模型项选择、CCD+BBD 优化、项平方和与诊断可用性页。
- 菜单新增 07 创建 Box-Behnken 设计、08 响应面预测、09 叠加等高线；帮助新增 doe.bbd、doe.predict、doe.ccd.overlay 并重建索引（94 主题）。
- 验证基线（.venv）：核心 DOE 16 文件 263 passed；GUI 22 + 21 passed（仅既有 tight-layout 警告）；菜单 66、帮助 13、G12 15、工作表/工程 69 passed；合计 469 passed。全量 pytest 未运行。
- 收尾报告 docs/doe-minitab/work-package-b-closeout.md；矩阵 RSM 13 implemented、RSM-005/016 missing、RSM-009 unknown。
- 未提交、未推送、未打标签；不进入工作包 C。

## 当前状态（2026-10-27）

DOE-3 已实现 CCD 和二次响应面：支持 2–5 因子 CCF/旋转 CCC、越界预览确认、编码与设定矩阵校验、纯误差/失拟/曲率和图形，工程可保存、重开、复制。DOE-1 含中心点时禁用模型 t/F 推断的前置修复已完成。CCD 允许十进制/指数文本按最近 binary64 保存；纯整数文本保持精确整数，无法无损转 binary64 的端点拒绝；中心和 CCC 轴点采用有界舍入，轴点必须仍在 low/high 外且反算编码误差不超过 1e-8。DOE schema v1 与 DOE-0/1/2 语义未变。DOE-4 已实现：完整 CCD 上单响应最大化/最小化/逼近目标，多响应期望函数权重优化；默认编码 bounds 为 [-1,1]，可收紧或固定。GUI 每次从当前表快照重拟合，候选含编码/实际水平、预测、期望、可行与 solver 状态；确定性多起点 L-BFGS-B 不保证全局最优，零期望/数值下溢/评价上限会明示。优化不写回响应、设定或 `.dexpl` schema v1。当前验收按范围合计 456 passed、14 warnings、0 failed、0 skipped；全量 pytest 未运行，DOE-3 之前的全量历史曾两次于 Tk `Menu.add` 原生 `0x80000003` 中断且无 summary。见 `docs/doe-development.md`、`docs/doe3-closeout-report.md` 与 `logs/2026-10-27.md`。

DOE-4 最小修复（2026-10-27）：目标型多响应在目标高侧改用 `power_high`；GUI 按各响应分别计算目标差值，保留单响应显示语义。独立解析最优点、左右侧期望/有限差分和真实 Tk 多响应显示均覆盖。指定四文件回归 64 passed、2 个既有 tight-layout warnings；py_compile 与 diff check 通过。详见 `logs/2026-10-27.md`。

DOE-2 正规部分因子支持 3–6 连续因子、正生成元、独立重复、定义字及别名组、DOE 元数据保存恢复；拒绝中心点、负生成元和派生因子循环。模型按别名组解释，只有独立重复且纯误差可辨时才在模型充分等假设下提供 OLS 推断。历史关联测试中的两项 DOE-1 失败已在 DOE-3 修复；历史证据见 `logs/2026-10-27.md`。

beta.4 已固化：beta.3 基线 `d21a924abf6f437f82e2736ac09c5a38dc636d5f`；pandas 迁移提交 `d321c59806230572bc6d7ba2c752ad8c80a62891`；版本提交 `e770bb9b22bca9aad2de3e167f77407a5608dff5`；本地 annotated 标签 `v0.1.0-beta.4` 指向实际构建基线 `0d9f5730029905745856d6bda1f4e7a24fc97b50`，标签未推送。产品/包/EXE 版本分别为 `v0.1.0-beta.4`、`V0.1-beta4`、`0.1.0.4`。迁移全量历史结果 3810 passed、0 failed、0 skipped；发布工具 25 passed、启动测试 17 passed。干净基线 Windows EXE/ZIP 构建、哈希和按进程 ID 的运行目录与解压版窗口冒烟通过。原冒烟脚本此前曾误识别 Edge，办公终端与实际 PI Server 未验收。详见当日日志。

beta.3 已冻结在提交 `d21a924abf6f437f82e2736ac09c5a38dc636d5f`；迁移开始时 `main`、`origin/main` 相同且工作区干净，未创建标签。pandas 3.0.6 迁移已完成并由提交 `d321c59806230572bc6d7ba2c752ad8c80a62891` 固化，正式依赖 `requirements.txt` 与 Windows Python 3.11 锁文件一致。数据安全写入、CSV/Excel 精度、旧 API、类别/日期时间绘图、分组语义及绘图 DPI 全局状态已修复；统计计算定义未改。

验证：`.venv` Python 3.11.9、pandas 3.0.6 及锁依赖检查通过，`tools/release_env.py` 五项 PASS；第一层 473、第二层 70、第三层 202、绘图 DPI/图片导出专项 180 项通过。收尾后全量 `pytest -q --tb=short` 为 **3,810 passed、0 failed、0 skipped、120 warnings**（978.26 秒）。历史 AST 守卫已修：`CorrelationDialog.apply` 的 `pearson=self.cor_p.get()` 按严格形态断言归一化后仍完整比较快照；同一函数内 `CpkSubDialog.apply` 的 REVIEW-018/019 差异复用整函数 SHA256 守卫还原。快照未改、测试未跳过；新增 Pearson 开/关运行时测试。详见 `docs/release/pandas3-migration-report.md` 与 `logs/2026-10-27.md`。限制：`.xls` 超精度原始 token 不可恢复；未接实际 PI Server；该迁移阶段未做 EXE/ZIP 构建与办公终端安全策略验收，后续构建状态见上文。

通用绘图器事件绑定最终验收已完成：`PlotViewer.setupGUI()` 创建并保留唯一 `self._drag_handler`，移除 `_flow_panelhead()` 中不可达绑定，`close()` 释放引用；专用 `code/plots.py` 未在本任务修改。普通查看器真实 Tk 覆盖四类事件各一次、GC 后存活、标注选择/拖动/释放/Delete、参数显隐/重绘/缩放/调整大小后不重复监听、关闭后监听消失及重开。指定三组测试分别 16/54/39 项通过（`PythonEnvs/minijmp`），普通查看器额外真实 Tk 交互及 900×720 窗口截图复核通过；画布 576×663。截图：`docs/gui-evidence/plotter/event-fix-900x720-{visible,hidden}.png`，导出图 `event-fix-saved-line.png`。本次未重做多 DPI/全页面布局矩阵，未跑全量测试。详见当日日志。

通用绘图器界面已重排为“顶部动作栏 + 右侧参数坞 + 画布主区”：参数页改为可滚动、按分组自适应列数的紧凑行式布局，绘图数据摘要移到画布下方，图形类型只在数据配置页出现一次；时间序列与过程能力的导航工具条改挂画布顶部。900×720 下画布高度 204→664 像素，640×480 至 1600×1000、125%/200% 缩放均逐页测量无裁切。见 2026-10-26 日志。

pandas 3 兼容性定向修复已完成：`core_orig.py` 的 `getRowsFromMask()`（按标签对齐布尔掩码，整数按行位置）与 `transform()`（按列重建 + `isetitem` 写回、`df.map` 替换 `applymap`），以及 `handlers.py` 散点拾取的 `df.iloc[ind]`；`plotting.py` 两处 `drop(columns=...)` 已是新写法，未改动。见 2026-10-26 日志。

通用绘图器新增“数据配置”页：X/Y/分组列显式配置、数据范围选择，折线/散点/条形/面积图按角色取数，不再依赖工作表列顺序；选区绘图、PLOT 高级选项与专用 PlotViewer 调用保持原行为。角色绘图的空分组跳过但按 Y 整体校验、序列按源列位置区分（`1` 与 `"1"` 不合并）、切到其他类型或三维必须退出角色模式，见 2026-10-26 日志。

工作表列公式功能已实现并验证：计算器、一次性/关联计算、依赖重算、循环检测、只读编辑规则、工程持久化、右键“公式”子菜单与计算菜单。

工作表、剪贴板、公式与绘图器集成验收（2026-10-26）完成：清除/上移单元格会同步公式状态；Ctrl+C/V 复用 TSV 列表解析和最终范围保护，行头选区不沿用旧列；列粘贴后恢复列头选中标记；验证公式结果经手动/自动重算后绘图、多表公式工程往返、行增删与公式只读保护。5 个相关测试文件 246 项通过，pandas 3.0.6 移位专项另 3 项通过。真实 Tk 窗口由自动化测试驱动，未做人工鼠标逐项验收。详见 2026-10-26 日志。

改善前后过程能力对比已并入原能力分析窗口（默认不勾选“启用阶段对比”）：复用 `analyze_capability` 分阶段估计，输出 6 张对比表、对比图与统一报告；原单阶段分析与 Sixpack 流程不变。

阶段对比已并入 I-MR/Xbar-R/Xbar-S 原窗口（默认关闭，勾选后展开设置），不再有独立菜单；阶段列/时间分界划分、独立控制限与改善前固定基线、改善指标、自相关适用性检查、统一报告与阶段图。普通 I/I-MR/Xbar 图同步启用 Nelson 判异，MR/R/S 只判越限。

## 关键实现

- `code/worksheet_formulas.py`：AST 白名单表达式求值、列引用解析、依赖排序、循环检测、`CalculatorDialog`；列引用按列名稳定关联，C 序号只在展示与新建公式时解析。
- `code/modified_table.py:MTable`：公式状态（`items`/`auto`）随工作表对象存放；`define_formula` 负责一次性/关联写入，`refresh_formulas` 由 `tableChanged` 触发；拒绝手工编辑、粘贴和清除关联结果列。
- `code/pandastable_local/headers.py`：关联结果列头追加 `[公式]`，待更新追加 `*`；重命名同步公式目标与来源。
- `code/worksheets.py`：`saveMeta`/`loadMeta` 保存并恢复公式定义和自动计算开关，旧工程无公式字段时保持原行为。
- 菜单：`code/MiniJMP.py` 顶层“计算”→“计算器”；单元格右键“公式”子菜单（分配/编辑/查看/删除/自动切换/立即计算）。
- `code/improvement_chart.py`：阶段划分、指标、Ljung-Box/Welch/Levene、统一报告、`phase_control_plot`；结果表含 `limits`（常量限标量，变化时标注“逐子组变化”）与 `limit_details`（逐子组 LCL/CL/UCL）；`code/stage_compare.py` 在三种变量图原窗口添加折叠设置并调用 `analyze_improvement`；`code/improvement_dialog.py` 仅展示结果（StatTable、TableBlock、PlotViewer、SheetApp）。
- 异常统计：`alarms` 按 stage 内 point 去重（两面板同一子组只计一次），分母 `points` 为实际绘制点数（I-MR 观测数、Xbar 子组数）；`records` 保留逐规则记录。指标行按图型显示“异常观测比例”或“异常子组比例”。
- Xbar 阶段数据：`_subgroups` 返回阶段内下标，`_chart` 只接收该阶段有效观测；阶段图横轴 I-MR 用观测序号、Xbar 用子组序号，分界取实际点位数。
- `code/control_chart.py`：`_panel_events`/`_mark_events`/`_x_plot_anomalies` 复用 `advanced_spc.nelson_events`；`x_plot` 仅在 `detect_rules=True` 时判定并标记；普通控制图对话框已启用。

## 改善前后能力对比（2026-10-26）

- `code/capability_compare.py`：`analyze_capability_comparison()` 复用 `improvement_chart.split_phases` 划分阶段、每阶段独立调用 `capability.analyze_capability`；输出「数据与规格摘要 / 能力指数对比 / 波动与超规对比 / 稳定性与分布诊断 / 统计检验 / 分析结论」6 张表与 `print_report`；`source_row` 映射回整张工作表，跨阶段重复子组 ID 直接拒绝。
- 指标列名跟随实际阶段标签（`_columns(names)`）；非正态只输出 Pp/Ppl/Ppu/Ppk 与等价 Z；`_row()` 两侧都有限才给差值，否则“不适用”及原因。
- 稳定性复用 `capability_plots._charts` + `control_chart._panel_events`（主图 Nelson、极差类图越限）；自相关/Welch/Levene 复用 `improvement_chart._differences`，阶段名替换为实际标签；有限制时不输出显著改善结论。
- `code/capability_plots.py:plot_capability_comparison()`：两阶段直方图共用横轴与规格、能力指数柱状图、实测/预计 PPM 对数面板；`plot_capability` 与原 Sixpack 未改动。
- `code/capability_dialog.py`：`compare_frame` 构造后仅在勾选时 pack；`comparison()` 拦截变换组合与缺规格；`publish_comparison`/`sync_tabs` 复用表格页、导出、写工作表；`report()`/`plot()` 以 `result_settings[1] == '阶段对比'` 分支。
- 帮助 `help/pages/capability-analysis.html#improvement` 与重建的 `help/assets/search-index.js`；`docs/capability-analysis.md` 增方法合同与证据矩阵；`docs/CHANGELOG_DEV.md` 已记 2026-10-26。
- `tests/fixtures/g12_table_inventory.json` 增 `capability_compare.py` 与说明（不新增 StatTable 生产位置）。

（该项为收尾前基线，已被下方 2026-10-26 最终验收记录取代）验证基线：`.venv` 下 `test_capability_compare.py` 9 项、`test_capability_dialog.py` 13 项（含真实 Tk 阶段对比）、`test_capability.py`+`test_capability_plots.py` 合计 93 项通过；`test_g12_inventory.py`+`test_g12_tables.py` 24 项、`test_help_center.py` 13 项、`test_improvement_chart.py`+`test_review_p2_legacy.py`+`test_review_data_safety.py` 69 项、`test_menu_localization.py`+`test_plot_window_lifecycle.py` 104 项通过。

未实现：两阶段分别 Box-Cox/Johnson 后比较能力指数（窗口明确提示，单阶段变换仍可用）；能力指数差值区间/检验。


## 验证基线

- 通用绘图器布局：`tests/test_g21_plotter.py`+`test_plotter_roles.py` 14 项、`test_dialog_translation.py -k 'plot or legacy'` 10 项、`test_phase1_plots.py` 63 项、`test_g6_chart_presentation.py` 54 项、`test_plot_window_lifecycle.py` 39 项通过（`PythonEnvs/minijmp`）。几何测量脚本 `tools/_plot_shot.py`；证据图在 `docs/gui-evidence/plotter/`。`test_g13_time_series.py::test_real_viewer_replot_navigation_and_save` 因测试用 `MouseEvent(buttons=...)` 与本环境 matplotlib 3.9 签名不符而失败，与本次布局改动无关。

### 2026-10-26 改善前后能力对比收尾修复

- `code/capability_dialog.py`：阶段划分下拉框原用 `list(SPLITS)` 填入内部键 `stage`/`time`，与按“阶段列”判断的启用逻辑不匹配。现改为 `SPLIT_LABELS`（显示“阶段列”/“时间分界点” → 内部 `stage`/`time`），默认“阶段列”，未知选项由 `split_mode()` 明确报错，不再隐式当作时间模式。
- `code/capability_plots.py:_ppm_panel()`：原 `rows` 为 (标签, 键)，解包写成 `for key, _ in rows` 后用中文标签查 `ppm`，导致全部被判定缺失；现严格用 `observed`/`overall`/`within` 取值，统一换算为 PPM，实测行标为“实测超规 PPM”，0 只标注不画条形、缺失显示 NA，`set_yticks` 也改用真实行标签。
- `code/capability_compare.py:_special_causes()`：原对非正态 I 图也用 `(UCL-CL)/3` 作公共尺度跑全部 Nelson 规则。现正态主图仍跑 Nelson，非正态主图只判拟合分位限越界，并在诊断表/对比图标注“未执行 Nelson 连续模式”。

验证（最终验收，`.venv` Python 3.11.9）：`test_capability_compare.py` 收集 14 项、14 项通过；`test_capability_dialog.py` 14 项通过；`test_capability.py`+`test_capability_plots.py` 71 项通过。合计 99 项。

重复测试名已修复：原第 279/304 行为同名 `test_nonnormal_asymmetric_limits_flag_both_sides`，前者从未被收集；现分别为 `test_nonnormal_in_limit_sequence_does_not_trigger_nelson`（限内连续点不触发 Nelson，旧做法命中 Nelson 2/3/7、新做法 0 异常，断言改为命中规则集合而非固定 `== 9` 条）与 `test_nonnormal_two_sided_limit_crossings`（上下越界预期数按重拟合后的实际分位限计算，`below>=1 and above>=1`，`alarms == below + above`）。

此前方案：`test_improvement_chart.py`/帮助/清单/旧 Cpk 守卫等共 176 项通过。Tk 套件合并运行仍偶发 `tcl_findLibrary` / `tk.tcl` 环境错误，单独运行通过（既有问题）。

遗留：非正态主图未实现经统计验证的连续点判异规则，目前只报告越界。

- pandas 3 兼容：`.venv`（Python 3.11.9、pandas 3.0.6）下 `test_table_regressions.py`、`test_g17_data_processing.py`、`test_g6_chart_presentation.py`、`test_phase1_plots.py` 合并 387 项通过。既有无关失败：paste 4 项、工程保存 3 项（沙箱临时目录权限）、便携存储 1 项、绘图器 `toggle_options` 3 项（并行 GUI 任务）。

- 通用绘图器列角色：`tests/test_plotter_roles.py` 8 项（真实 Tk，`PythonEnvs/minijmp`）与 `test_g21_plotter.py`、`test_phase1_plots.py` 合并 74 项通过；`test_dialog_translation.py` 相关 48 项、`test_g12_*`+`test_menu_localization.py` 89 项、`test_help_center.py` 13 项通过。`test_dialog_translation.py::test_original_analysis_code_is_unchanged` 仍因既有 `fit_dialog.py` 差异失败；`test_g18_performance.py` 的 `int64` 用例为 pandas 3.0 兼容问题、Excel 用例受沙箱临时目录权限限制，均与本次绘图改动无关。

- `tests/test_worksheet_formulas.py` 20 项通过；`tests/test_worksheet_context_menu.py`、`tests/test_sheet_context.py`、`tests/test_file_io.py`、`tests/test_table_regressions.py` 相关用例通过；计算器真实 Tk 交互验证 25→50 自动更新。
- `tests/test_g12_inventory.py` 仅`python_files`计数与本任务新增文件相关；当前工作区另有并行任务文件（`improvement_*`）未纳入本任务清单。
- 阶段对比：`tests/test_improvement_chart.py` 33 项、`test_g5_spc_reports.py` 74 项（`-s`，与前者合并 107 项通过）。结果窗口在后端 `limit_details` 为空时不建标签页，有明细时显示并支持导出当前页；两个方向均有真实 Tk 断言。多套 Tk 测试合并偶发 Tcl 初始化错误，单独运行均通过；`test_dialog_translation.py::test_original_analysis_code_is_unchanged` 因已提交的 `fit_dialog.py` 差异失败，与本次改动无关。

## DOE-0 工程基础（2026-10-27）

- DOE-1 推断及交互图修复：无独立重复的简化全因子模型禁用推断；独立重复按相同组合计算纯误差 SSE/df，无中心点时拆分失拟 SSE/df，但不检验失拟显著性。OLS 推断使用模型残差均方，明确要求模型充分、误差独立同方差且正态；中心点推断仍禁用。交互图可选择任意两个因子并标示上次分析快照。真实 Tk 已覆盖三因子各因子对、多响应、非法创建、两个独立工作表、删除和重开后旧来源失效。`.venv` DOE 专项 26 passed、2 warnings；关联 DOE-0/工作表/工程/公式/G12/菜单/帮助/绘图生命周期 278 passed、9 warnings。见当日日志。

- DOE-1 基础：`doe_factorial.py` 生成 2–6 因子的完整组合、独立重复和中心点；`doe_analysis.py` 验证 DOE-0 摘要及组合并拟合层级模型；`doe_dialog.py` 和菜单支持创建、响应后填、分析、StatTable 与基础图。饱和模型不推断；中心点单独建模且推断暂不可用。先前 19 项专项和 278 项回归为历史结果，当前修复及验证见上条；未做 LRM 评审。

- 基于 beta.4 后的当前 HEAD e61d43c0bc21 增加纯数据模块 code/doe_core.py；beta.4 tag、版本文件和发布产物未修改。
- 公共类型/API：FactorSpec、DesignSpec（含受控 design_type）、RunRecord、DesignResult、ModelResult、OptimizationResult、randomized_run_order()、design_from_worksheet()、worksheet_metadata()、restore_design_result()。design_type 区分 two_level_full、two_level_fractional、central_composite 与明确的 unspecified，进入 schema v1 序列化和输入摘要；缺失/未知值拒绝。连续因子编码保持精确，必要时返回 Fraction；分类因子仅有结构占位，不允许混合水平设计或设计生成。
- Worksheets.saveMeta/loadMeta 增加可选每表 doe schema；列名保留原类型，run_id 映射到 iloc 行，不用 DataFrame.index。列顺序用 SHA-256 指纹校验，未映射列名不重复进入元数据；设计定义、映射、行 ID 和输入摘要仍保留，不复制 X/Y 原值。实测水平与响应是观察字段，可晚填/修正；设计设定或行映射变化会让保存/恢复失败。摘要不是匿名化；映射列名和 run_id 必须使用非敏感值，通用代码不具备 PII 语义检测；.dexpl 仍是原有可信 pickle 边界。
- 记录合同区分 standard/run order、点类型、重复、区组、设定与实测水平及可空多响应；轴点必须匹配 CCD alpha/轴点数声明。residual_df == 0 的 ModelResult 禁止 t/p/F 字段。独立 2² 解析参考得到 Y=(53,41,51,55)、效应 A=6、B=-4、AB=8；未实现 DOE-1 分析器。
- 最终验证：项目 .venv Python 3.11.9、pandas 3.0.6；py_compile 通过；DOE 核心/持久化、worksheets、sheet context、file I/O、公式及 G12 inventory 合并 160 passed、0 failed、0 skipped。G12 已核对 103 个 code/**/*.py 文件。
- 下一步继续 DOE-1 验收与缺口处理；部分因子、生成元和别名不在当前范围内。

## 当前限制

- 只支持工作表内 C 列引用，不支持跨表、Excel 语法、宏或完整 Minitab 函数库。
- 公式结果为浮点列；部分溢出或除零写为空值并提示。
- 环境状态（2026-10-27）：旧 `C:\Users\shaoy\Documents\PythonEnvs\minijmp`（Python 3.11.9、pandas 2.2.3）已停用并列入退役；递归删除被执行策略拒绝，目录目前仍存在。后续 MiniJMP 仅使用项目 `.venv`（Python 3.11.9、pandas 3.0.6）。此前 Tk 测试改用旧环境的记录及 beta.3 基线均保留为历史事实；若 `.venv` 的 Tcl/Tk 运行时脚本问题影响后续测试，应在 `.venv` 内处理，不复用旧环境。
- 改善前后分析未实现 P/NP/C/U 图、复杂时间序列模型、规则 1～8 以外的判异规则；固定基线模式的 Xbar-S 为获得可绘制 S 限，保留原算法对 bar2 的已知口径差异并单独校正（子组大小取改善后各组的 n）。

## 公式收尾修复（2026-10-25）

- 粘贴保护改为在最终 `target_rows`/`target_cols` 解析后校验；单元格扩展或整行粘贴覆盖公式列时整次拒绝，无部分写入与撤销记录。
- `load_formulas` 恢复保存的 `stale`，手动模式重开后仍显示 `*`；`export_formulas` 原样保存该状态；自动模式仍重算。
- `row1ToHeader` 使用 `formula_columns_renamed()` 按列位置成批改名；`sortSelected` 走 `tableChanged()` 刷新公式，并拒绝单独排序公式结果列。
- 撤销历史中每个 `prevdf` 快照并列保存公式定义（`_formula_history`），`delete_column_formula` 也先记录快照。
- 验证基线：`tests/test_worksheet_formulas.py` 26 项，加上下文剪贴板、表格、工作表、数据安全、CSV 与工程相关共 324 项通过。

## 数值列名公式持久化（2026-10-25）

- `row1ToHeader()` 可产生数值列名；公式目标与来源必须保持 DataFrame 实际列名类型。
- `load_formulas()` 不再要求目标是 `str`，也不对所有来源执行 `str()`；`_match_column_name()` 仅对非字符串列名按当前 DataFrame 列匹配，字符串保持原样以兼容旧工程。
- `export_formulas()` 返回原类型，pickle 工程往返后可正常重算。`C1`、`C2` 表达式语法未变。
- 验证：`tests/test_worksheet_formulas.py` 27 项（新增数值列名保存/加载/重算）及上下文剪贴板、表格、工作表、工作表右键菜单共 207 项通过。

## DOE Minitab 功能对标工作包 A（2026-10-27）

- 基线：main HEAD fd76b69b59f98d11751074a2d68e1b396f11773a；开始时工作区干净。DOE-0～DOE-4 APPROVE 未变。
- 只读调查 Minitab Statistical Software 官方在线帮助及 MiniJMP 源码/测试；产品版本未由官方页面注明。已新增 docs/doe-minitab/README.md、feature-matrix.csv、acceptance.md、roadmap.md、sources.md。
- Review 修正后矩阵 80 项（10 implemented、13 partial、52 missing、4 unknown、1 excluded），66 个唯一验收号；原 001–063 稳定，新增 TAG-010/011、FAC-019 与 ACC-064–066。P0 与 Level 1 完全一致；已实现 P0 项复用 DOE-0～4 基线，不重复安排开发，FAC-009 的 ACC-012 保留为回归验收。
- Review 修正官方定义：General Full Factorial 的数值水平仍是分类水平；Taguchi 覆盖 4/5/mixed-level 与四类静态 S/N、adjusted 公式及独立数值参考；D-optimality 与 distance-based 按设计家族限定；不要求无官方承诺的全局最优保证。B/D/E 完成 Level 1 ANOVA、诊断和 schema 前置验收，H 保留最终跨类别验收。
- 最终自动检查：项目 .venv Python 3.11.9 下验证 CSV 80×20 结构、状态计数、66 个连续且一一映射的验收编号、P0/Level 1、A–H 路线映射、UTF-8/Markdown 本地链接/尾随空白；`git diff --check` 通过。未跑 pytest、未改产品代码/schema/菜单/测试/CHANGELOG_DEV；待用户最终审查。详见当日日志。
