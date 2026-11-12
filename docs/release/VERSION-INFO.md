# MiniJMP V1.2 版本与审核说明

> 本资料供内部审核。当前源码存在未核实的第三方代码许可，正式分发及合规放行受阻；本文不是企业验收或合规放行结论。

许可状态核对日期：2026-11-04。

## 软件概况

MiniJMP 是独立的 Windows 桌面统计分析软件，提供表格数据导入、统计检验与回归、质量工具、DOE、图形和可选 PI 历史数据导入。它不隶属于、不是由 Minitab 或 JMP 发布或认可的产品。功能和统计结果可能与 Minitab/JMP 不同，本项目不宣称功能、算法或数值等效。

| 标识 | 值 |
|---|---|
| 发布名 | `V1.2` |
| 产品版本 | `v1.2.0` |
| Windows 文件版本 | `1.2.0.0` |
| Git tag | `{{TAG}}`|
| 对应 Git commit | `{{COMMIT}}` |

完整 Git SHA、Tag 与本次实际文件 SHA-256 由构建流程填写。附件校验值见 `SHA256SUMS.txt`，源码Commit见源码包 `SOURCE-BUNDLE-INFO.txt`，包内 `SOURCE-MANIFEST.txt` 提供逐文件摘要。

```text
{{SHA256}}
```

## 仓库、许可与分发状态

- 本仓库为 [summeredge/Minijmp](https://github.com/summeredge/Minijmp)，基于原项目 [garrydu/Minijmp](https://github.com/garrydu/Minijmp) 二次开发。本仓库 `LICENSE` 声明 GNU GPL v3。该声明本身不能证明下列外部代码的授权或许可兼容性。
- `code/nonpara_cor.py::hoeffd_example` 明确标记为复制自 [Dicklesworthstone/hoeffdings_d_explainer](https://github.com/Dicklesworthstone/hoeffdings_d_explainer) 的 README。审核时未找到该仓库的独立 `LICENSE`，GitHub license API 返回 HTTP 404：[许可查询](https://api.github.com/repos/Dicklesworthstone/hoeffdings_d_explainer/license)。
- `PIReader/` 是 MiniJMP 项目自研源码（项目维护者确认），按项目 GPL-3.0-or-later 许可；运行包使用本次源码构建产生的 `PIReader/PIReader.exe`。`code/pi_reader.py` 的文件头注明复用 [PI-Data-Viewer/backend/pi_reader.py](https://github.com/summeredge/PI-Data-Viewer)，该来源的独立许可仍未核实。

上述许可缺口尚无独立授权文件或兼容性结论。该构建资料和包可用于内部审核；正式分发及合规放行须先补足授权依据或移除/替换相关代码，并重新审核。不得据此宣称整个交付物已获合规放行。

## 运行环境与组件

- 发布目标：Windows x64，PyInstaller `onedir`。需保留整个运行目录；终端用户无需另装 Python。当前发布资料没有声明最低 Windows 版本。
- 从源码运行或构建需要 Windows x64 与 Python 3.11 或更高版本；具体版本以构建记录为准。
- 主要运行依赖：Python/Tkinter、NumPy、pandas、SciPy、Matplotlib、Seaborn、statsmodels；Excel 文件读写使用 `openpyxl`、`xlrd`。实际版本和组件许可应以该次 `BUILD-INFO.txt`、`THIRD-PARTY-NOTICES.txt` 与 `THIRD-PARTY-LICENSES/` 为准。
- MiniJMP 不安装 Windows 服务、不要求管理员权限启动。应用配置、表格默认配置、日志、PI 路径及用户数据分别存放，详见 [安装与使用说明](INSTALL-USAGE.md)。

## PI 发布边界

- 当前 Windows 构建将源码编译的 `PIReader.exe` 放在运行包 `PIReader/PIReader.exe`；SBOM 记录该运行文件的版本与实际 SHA-256，不取仓库中的旧 EXE。源码包不含 PIReader.exe 或 PI SDK DLL。
MiniJMP V1.2 Windows 发布包随附三个 PI SDK 相关组件，用于支持 PI 数据访问。PI 数据导入功能须在已取得相应授权、安装并正确配置 PI SDK/PIPC 运行环境，且具有 PI Server 访问权限的企业办公终端上使用。随包组件不构成完整的 PI System 运行环境，也不代表授予额外的软件使用或再分发许可。 三个 DLL 保持专有第三方身份，再分发授权待企业确认；公开 Git 与源码 ZIP 不含 SDK DLL，不自动安装或注册组件。

## 数据与企业验证边界

普通文件分析在本机执行，无需外部应用服务器；未配置PI时可离线使用统计分析和随包帮助。在线链接由用户点击打开。本轮仅构建/一致性/启动冒烟，不代表所有统计场景与Minitab或JMP等效。企业目标机的普通权限、Windows版本兼容性、Defender/EDR、DLP、帮助显示与PI连接仍需现场验收；已知许可缺口未解除。
