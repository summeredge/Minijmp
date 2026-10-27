# MiniJMP — Open-Source Statistical Analysis Software (Community-Derived Edition)

> This repository is an independent derivative of the open-source [Minijmp project](https://github.com/garrydu/Minijmp) released by G.Du. It is not an official release by the original author.

![Screenshot of the original project's main window](docs/images/main.png)

MiniJMP is a desktop statistical analysis application written in Python. It provides a spreadsheet workspace, statistical tests, regression analysis, process-quality tools, and data visualization. The original project drew on selected features of Minitab Express and JMP. This derivative primarily extends advanced statistics, the Chinese interface, plotting, industrial PI data import, and the Windows user experience.

**Current version label:** `v0.1.0-beta.4`. This README reflects the repository source as of **October 2026**. Some screenshots may come from the original project; the current application is the authoritative reference for the interface.

## Original Projects, Copyright, and License

- **Original project:** [garrydu/Minijmp](https://github.com/garrydu/Minijmp), by **G.Du**. The original attribution `Copyright (C) G.Du 2024-` is retained.
- **Underlying table component:** [PandasTable](https://github.com/dmnfarrell/pandastable) / DataExplore, by **Damien Farrell**. Applicable upstream copyright and license notices are retained; the application's About dialog lists `Copyright (C) Damien Farrell 2014-`.
- **Independent derivative:** [summeredge/Minijmp](https://github.com/summeredge/Minijmp). Since October 2026, this repository has made changes to the interface, statistical modules, data operations, plotting, and industrial data integration. The maintainers of this repository are responsible for those changes; they are not endorsed by the original author.
- **License:** This derivative continues under the **GNU General Public License v3 (GPLv3)**. See [LICENSE](LICENSE) for the full text. Distributions of modified versions must retain applicable original copyright and third-party notices, identify modifications, and comply with GPL requirements for licensing and providing the corresponding source code.

The software is provided “as is,” without express or implied warranties. Minitab and JMP are products or trademarks of their respective owners; this project is not affiliated with their official vendors.

## Features

### Core features of the original project

- Editing multiple worksheets, working with CSV and Excel data, transforming data, and displaying charts.
- Descriptive statistics, distribution fitting, correlation, t- and Z-tests, ANOVA, contingency tables, and chi-square tests.
- Linear and orthogonal regression, gauge R&R, Cpk, and commonly used control charts.

### Major additions and enhancements in this repository

| Area | Implemented features |
| --- | --- |
| Chinese interface and interaction | Chinese menus, searchable offline Chinese help opened with F1, remembered column selections for common analyses and plots, and enhanced table and worksheet context-menu operations. |
| Advanced regression | OLS, WLS, binary logistic regression, nonlinear regression, variable selection, diagnostics, and prediction; plus Poisson, nominal multinomial logistic, ordinal logistic/probit, and single- or multi-response PLS. |
| PCA | Principal-component scores and loadings, explained variance, Hotelling's T², Q/SPE, variable contributions, model saving, and projection of new samples. |
| Time series | ACF/PACF/CCF, trend and seasonal decomposition, ADF/KPSS, and ARIMA/SARIMA modeling and forecasting. |
| Process capability | Normal and non-normal capability analysis, Box-Cox/Johnson transformations, and normal/non-normal Sixpack. |
| Advanced SPC | EWMA, CUSUM, the eight Nelson rules, and multivariate Hotelling's T², alongside the existing I-MR, Xbar-R/S, NP/P/C/U, and other control charts. |
| Quality tools | Pareto charts, run charts, cause-and-effect (fishbone) diagrams, multi-vari charts, and attribute agreement analysis. |
| Plotting | A general-purpose plot builder and standalone plotting entry points; extended bar, area, matrix, contour, 3D scatter/surface, bubble, marginal, ECDF, interval, and probability plots, among others. |
| Industrial data | Querying PI historical data by Tag or Tag Mask through the external PIReader/PI SDK, then importing it into the current worksheet. |
| Data and deployment | Improved CSV/Excel result export and protection against failed overwrites; a Windows 64-bit PyInstaller `onedir` build workflow with an embedded icon. |

Statistical methods, defaults, and applicability conditions can differ across software. These features do not imply that every option or numerical result matches Minitab or JMP. Some methods are approximate or depend on specific assumptions; see the corresponding help for details.

## Installation and Running

### Run from source (recommended for development)

Requires **Windows x64 and Python >= 3.11** (3.11, 3.12, or 3.13); the production pandas version is pinned to `3.0.6`. The repository's focused validation used Python 3.11.9. On newer Python versions, differences from the lock file are recorded only. Although the original project includes Linux/macOS considerations, this derivative has not claimed equivalent cross-platform validation.

Open PowerShell in the project root:

~~~powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe start.py
~~~

If `.venv` already exists, there is no need to recreate it. Dependencies are specified in [requirements.txt](requirements.txt).

### Windows packaged application

The repository provides a [Windows build script](tools/build_windows_release.ps1), [packaging guide](PACKAGING.md), and locked dependency files. It uses PyInstaller **`onedir` mode**. The presence of a build workflow does not mean that every source change has an accepted EXE release package. When using a packaged build, extract the complete archive and keep `MiniJMP.exe`, `_internal`, `PIReader`, and the other dependency folders together.

Enterprise Defender, TsdEncrypt/DLP transparent encryption, and other security policies may affect startup or export. Verify these behaviors separately on the target machine.

## Optional PI Historical Data Import

Choose **File → Import PI Data**. A Windows release package includes a `PIReader` folder beside `MiniJMP.exe`, containing `PIReader.exe` and `config.txt`. The local machine still requires the **PI SDK/PIPC runtime** and permission to access the server; the PI SDK is not distributed with this software. You can also specify paths through environment variables or the Browse button. Enter a Tag or Tag Mask, historical time range, and sampling interval. A successful import replaces the current worksheet, so save any data you need to keep first.

For operating instructions, constraints, and error handling, see the [PI data import guide](docs/PI-data-import.md). Ordinary statistical features do not depend on the PI SDK.

## Help and Technical Documentation

- [Offline Chinese help](help/index.html) (press F1 in the application)
- [Advanced statistical analysis: regression, PCA, time series, and SPC](docs/advanced-statistics.md)
- [Extended regression models and statistical conventions](docs/REGRESSION_EXTENSIONS.md)
- [Comprehensive process capability analysis](docs/capability-analysis.md)
- [Quality tool extensions](docs/quality-tools-extension.md)
- [Column preselection and history](docs/column-selection-memory.md)
- [Original project's online documentation](https://minijmp.readthedocs.io/) (may not cover this derivative)

![Screenshot of the original project's menu, for reference only](docs/images/menu.gif)

## Development Tools and Acknowledgments

The software is written in **Python** and uses Tkinter, pandas, NumPy, SciPy, statsmodels, Matplotlib, Seaborn, and other libraries. **ChatGPT** and **Codex**, among other AI-assisted tools, have been used for some code analysis, implementation, debugging, testing, and documentation work. The project maintainer reviews and integrates changes and decides whether to adopt them.

Thanks to **G.Du** for releasing Minijmp as open source, and to **Damien Farrell** for releasing PandasTable/DataExplore. Copyright in the original project and third-party components belongs to their respective rights holders.

---

**[GNU GPL v3 license](LICENSE)** · **[Original project](https://github.com/garrydu/Minijmp)** · **[Independent derivative repository](https://github.com/summeredge/Minijmp)**
