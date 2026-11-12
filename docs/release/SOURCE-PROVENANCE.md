# 源码来源与许可证

核对日期：2026-11-04；PIReader 自研身份于 2026-11-11 由项目维护者确认。原项目 [garrydu/Minijmp](https://github.com/garrydu/Minijmp)，原作者 G.Du，Copyright (C) G.Du 2024-；二次开发项目 [summeredge/Minijmp](https://github.com/summeredge/Minijmp)。根 LICENSE 保留 GNU GPLv3，代码中适用的“或更高版本”条款保留。

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
| C | PIReader/ | 项目维护者确认由 MiniJMP 项目自研，适用项目 GPL-3.0-or-later。运行包使用本次源码构建产生的 `PIReader/PIReader.exe`；SBOM 对运行目录中的实际文件计算 SHA-256，不用仓库旧 EXE |
| B，第三方片段 | code/blakerCI.py | 明示由R BlakerCI 1.0-6移植（p-value除外）；Jan Klaschka；CRAN DESCRIPTION为GPL-3，SPDX GPL-3.0-only；源码链接见文件头 |
| B，第三方片段 | code/nonpara_cor.py::phoeffd | 明示由Hmisc R/hoeffd.s移植；Frank E Harrell Jr及贡献者；当前DESCRIPTION GPL (>=2)，SPDX GPL-2.0-or-later；实际移植版本未记载，不能以当前5.3-0冒充版本 |
| B，第三方片段；授权D | code/nonpara_cor.py::hoeffd_example | 文件明确copy-pasted自Dicklesworthstone/hoeffdings_d_explainer README。GitHub仓库未显示许可证，license API为404；作者署名保留，SPDX及分发授权待确认，不推断为GPL/MIT。这是正式合规放行阻断 |
| C，外部图标 | code/icon_resource.py | IBM Carbon @carbon/icons 11.91.0，Apache-2.0；Tabler Icons，Paweł Kuna，MIT；固定上游commit、文件名与完整许可见THIRD-PARTY-NOTICES及packaging/windows/licenses/ |

## 证据与限制

- BlakerCI DESCRIPTION：https://raw.githubusercontent.com/cran/BlakerCI/master/DESCRIPTION （Version 1.0-6，Author Jan Klaschka，License GPL-3）。
- Hmisc DESCRIPTION：https://raw.githubusercontent.com/cran/Hmisc/master/DESCRIPTION；原移植链接 https://rdrr.io/cran/Hmisc/src/R/hoeffd.s 。
- Hoeffding复制来源：https://github.com/Dicklesworthstone/hoeffdings_d_explainer ，核对license API无可用许可证；不把公开可读视作授权。
- PI SDK 属于 OSIsoft/AVEVA 专有第三方软件；三个 DLL 的再分发授权仍未确认。指定构建输入目录不会改变或授予授权。源码 ZIP 排除这些 DLL。
- 源码清单可支持内部审核，不能代替缺失授权。`code/pi_reader.py` 与 Hoeffding 复制片段的授权缺口仍需补充证据，未解决前不宣称正式合规发布完成。

MiniJMP V1.1 Windows 发布包随附三个 PI SDK 相关组件，用于支持 PI 数据访问。PI 数据导入功能须在已取得相应授权、安装并正确配置 PI SDK/PIPC 运行环境，且具有 PI Server 访问权限的企业办公终端上使用。随包组件不构成完整的 PI System 运行环境，也不代表授予额外的软件使用或再分发许可。
