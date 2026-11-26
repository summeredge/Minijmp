# 源码来源与许可证

本次核对日期：2026-11-26；PIReader 自研身份于 2026-11-11 由项目维护者确认。原项目 [garrydu/Minijmp](https://github.com/garrydu/Minijmp)，原作者 G.Du，Copyright (C) G.Du 2024-；二次开发项目 [summeredge/Minijmp](https://github.com/summeredge/Minijmp)。根 LICENSE 保留 GNU GPLv3，代码中适用的“或更高版本”条款保留。

## 分类口径

对照固定上游 `c684c7d919294119a563c099eb854c2a841197f9` 与冻结源码 `7a709598b002f7454af24ed07d33993ae39563a2` 的 Git 路径和 blob。A=同路径同blob；B=同路径不同blob；C=当前项目新增路径；D=存在来源或授权证据缺口。详见 SOURCE-PROVENANCE.csv。清单覆盖 code/、PIReader/、packaging/，不计算自研比例，不是逐行归属审计。PIReader 自研身份按项目维护者 2026-11-11 确认；这不是逐行原创性审计。新增路径、AI辅助开发与完全原创不是同一概念。

## 主要模块

| 分类 | 路径与模块 | 来源、署名和适用许可 |
|---|---|---|
| A/B，详见CSV | code/dist_fit.py、GRR.py、control_chart.py、cpk.py、linear_fit.py、modified_app.py、modified_table.py等基础统计、GUI | 继承G.Du项目；修改版仍保留GPLv3声明，B含本仓库后续修改 |
| A/B，详见CSV | code/pandastable_local/：app.py、core_orig.py、data_orig.py、dialogs.py、plotting.py等 | 内嵌PandasTable/DataExplore；Damien Farrell，Copyright (C) Damien Farrell 2014-，文件头GPL-3.0-or-later；界面称DataExplore 0.13，精确独立pandastable发布版本未确认，不当作pip安装包 |
| C | code/advanced_regression.py、generalized_regression.py、pls_regression.py、pca_analysis.py等 | 相对固定上游新增的高级回归、PLS、PCA；按项目GPL许可，未逐行排除外部片段 |
| C | code/doe_*.py、advanced_spc*.py、time_series_analysis.py等 | 新增DOE、高级SPC与时间序列；依赖SciPy/statsmodels等计算，具体第三方依赖另列SBOM；方法参考文献不自动等于复制源码 |
| D | code/pi_reader.py | 文件头注明复用 PI-Data-Viewer/backend/pi_reader.py；独立许可证据仍待核实。此 Python adapter 与 PIReader/ C# 程序分别登记 |
| C | PIReader/ | 项目维护者确认由 MiniJMP 项目自研，适用项目 GPL-3.0-or-later。公开候选运行包复用固定 PIReader 1.0.0.0，SBOM 对实际随包文件计算 SHA-256。固定文件的源码及构建关联待证实 |
| B，第三方片段 | code/blakerCI.py | 明示由R BlakerCI 1.0-6移植（p-value除外）；Jan Klaschka；CRAN DESCRIPTION为GPL-3，SPDX GPL-3.0-only；源码链接见文件头 |
| B，第三方片段 | code/nonpara_cor.py::phoeffd | Frank E Harrell Jr 及贡献者，GPL-2.0-or-later。Python 移植最迟见于 MiniJMP 提交 1253526（2024-10-26）。查表、插值区间与尾部近似均和 [Hmisc 5.1-3 的 R/hoeffd.s](https://github.com/cran/Hmisc/blob/1dd1751850d080156ac8152ec6de54f049dff659/R/hoeffd.s) 一致。原移植所取版本未记录 |
| B，本项目实现 | code/nonpara_cor.py::hoeffd_example | 依据 [Hoeffding（1948）](https://doi.org/10.1214/aoms/1177730150) 的统计定义及有许可的 Hmisc 参考独立实现。生产源码和随源码包分发的旧测试快照均已替换 README 复制片段 |
| C，外部图标 | code/icon_resource.py | IBM Carbon @carbon/icons 11.91.0，Apache-2.0；Tabler Icons，Paweł Kuna，MIT；固定上游commit、文件名与完整许可见THIRD-PARTY-NOTICES及packaging/windows/licenses/ |

## 证据与限制

- BlakerCI DESCRIPTION：https://raw.githubusercontent.com/cran/BlakerCI/master/DESCRIPTION （Version 1.0-6，Author Jan Klaschka，License GPL-3）。
- Hmisc 许可与署名见 [固定版本 DESCRIPTION](https://github.com/cran/Hmisc/blob/1dd1751850d080156ac8152ec6de54f049dff659/DESCRIPTION)，随包保留该版本元数据。现有标量接口与 p 值计算保持原行为。
- PI-Data-Viewer 适配器首次引入见 MiniJMP 提交 e072596ba51743b65c81b9446c92033a67774a57。公开来源 URL 本次返回 404。待维护者提供原文件与提交、作者及外部贡献情况，以及依据 GPLv3 或更高版本修改和公开分发的授权。
- 固定 PIReader SHA-256 为 3EEEA2BB6D747BD2731C2F405F2A1FECBDB6C0FAC672F659F1C26ECD2DDF23D0，Git blob 0eb622e9b9dbcd83d6e957e8aee10624269c34dc。固定路径见提交 785636091bd2bb4c1853f28d6ce283c0237421ed，同一 blob 也见于 ca0571dcf9b322212624fbde9207a74bf33b995b 的旧路径 PIReader/PIReader.exe。该线索证实字节相同，尚无记录将其绑定到构建输入、编译器和 SDK 版本、或带日期及摘要的现场验证。
- PIReader 源码树提供 .NET Framework 4.8 x86 工程和单独的旧构建批处理。公开候选包及对应源码包均排除三个 OSIsoft/AVEVA 专有 SDK DLL。含 SDK 的内部构建需要组织确认软件授权和分发范围。
