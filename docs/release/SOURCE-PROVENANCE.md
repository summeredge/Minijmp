# 源码来源与许可证

核对日期：2026-11-04。原项目 [garrydu/Minijmp](https://github.com/garrydu/Minijmp)，原作者 G.Du，Copyright (C) G.Du 2024-；二次开发项目 [summeredge/Minijmp](https://github.com/summeredge/Minijmp)。根 LICENSE 保留 GNU GPLv3，代码中适用的“或更高版本”条款保留。

## 分类口径

对照固定上游 `c684c7d919294119a563c099eb854c2a841197f9` 与本次冻结前源码 `7a709598b002f7454af24ed07d33993ae39563a2` 的 Git 路径和 blob。A=同路径同blob；B=同路径不同blob；C=当前项目新增路径；D=存在来源或授权证据缺口。详见 SOURCE-PROVENANCE.csv。清单覆盖 code/、PIReader/、packaging/，不计算自研比例，不是逐行归属审计。新增路径、AI辅助开发与完全原创不是同一概念。本次发布改动仅版本及打包材料，统计代码保留上述基线。

## 主要模块

| 分类 | 路径与模块 | 来源、署名和适用许可 |
|---|---|---|
| A/B，详见CSV | code/dist_fit.py、GRR.py、control_chart.py、cpk.py、linear_fit.py、modified_app.py、modified_table.py等基础统计、GUI | 继承G.Du项目；修改版仍保留GPLv3声明，B含本仓库后续修改 |
| A/B，详见CSV | code/pandastable_local/：app.py、core_orig.py、data_orig.py、dialogs.py、plotting.py等 | 内嵌PandasTable/DataExplore；Damien Farrell，Copyright (C) Damien Farrell 2014-，文件头GPL-3.0-or-later；界面称DataExplore 0.13，精确独立pandastable发布版本未确认，不当作pip安装包 |
| C | code/advanced_regression.py、generalized_regression.py、pls_regression.py、pca_analysis.py等 | 相对固定上游新增的高级回归、PLS、PCA；按项目GPL许可，未逐行排除外部片段 |
| C | code/doe_*.py、advanced_spc*.py、time_series_analysis.py等 | 新增DOE、高级SPC与时间序列；依赖SciPy/statsmodels等计算，具体第三方依赖另列SBOM；方法参考文献不自动等于复制源码 |
| D | code/pi_reader.py、PIReader/ | 明示复用PI-Data-Viewer/backend/pi_reader.py，来源仓库 https://github.com/summeredge/PI-Data-Viewer；本地来源仓库未找到独立LICENSE，授权待确认。PIReader源码保留，已有exe及专有DLL不进入可交付运行包 |
| B，第三方片段 | code/blakerCI.py | 明示由R BlakerCI 1.0-6移植（p-value除外）；Jan Klaschka；CRAN DESCRIPTION为GPL-3，SPDX GPL-3.0-only；源码链接见文件头 |
| B，第三方片段 | code/nonpara_cor.py::phoeffd | 明示由Hmisc R/hoeffd.s移植；Frank E Harrell Jr及贡献者；当前DESCRIPTION GPL (>=2)，SPDX GPL-2.0-or-later；实际移植版本未记载，不能以当前5.3-0冒充版本 |
| B，第三方片段；授权D | code/nonpara_cor.py::hoeffd_example | 文件明确copy-pasted自Dicklesworthstone/hoeffdings_d_explainer README。GitHub仓库未显示许可证，license API为404；作者署名保留，SPDX及分发授权待确认，不推断为GPL/MIT。这是正式合规放行阻断 |
| C，外部图标 | code/icon_resource.py | IBM Carbon @carbon/icons 11.91.0，Apache-2.0；Tabler Icons，Paweł Kuna，MIT；固定上游commit、文件名与完整许可见THIRD-PARTY-NOTICES及packaging/windows/licenses/ |

## 证据与限制

- BlakerCI DESCRIPTION：https://raw.githubusercontent.com/cran/BlakerCI/master/DESCRIPTION （Version 1.0-6，Author Jan Klaschka，License GPL-3）。
- Hmisc DESCRIPTION：https://raw.githubusercontent.com/cran/Hmisc/master/DESCRIPTION；原移植链接 https://rdrr.io/cran/Hmisc/src/R/hoeffd.s 。
- Hoeffding复制来源：https://github.com/Dicklesworthstone/hoeffdings_d_explainer ，核对license API无可用许可证；不把公开可读视作授权。
- PI SDK属于OSIsoft/AVEVA专有软件；再分发授权未确认，三个DLL不在本次运行/源码ZIP中。PIReader.exe也排除，源码与业务接口保留。
- 源码清单可支持内部审核，不能代替缺失授权。上述Hoeffding与PI来源授权应由维护者/权利人补充证据，未解决前不宣称正式合规发布完成。
