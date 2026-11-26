# MiniJMP V1.3.0 版本与审核说明

> 本说明记录 MiniJMP V1.3.0 的产品、许可与运行环境。发布候选及实际验收结果见发布验收报告。

许可状态核对日期：2026-11-26。

## 软件概况

MiniJMP 是独立的 Windows 桌面统计分析软件，提供表格数据导入、统计检验与回归、质量工具、DOE、图形和可选 PI 历史数据导入。它不隶属于、不是由 Minitab 或 JMP 发布或认可的产品。功能和统计结果可能与 Minitab/JMP 不同，本项目不宣称功能、算法或数值等效。

| 标识 | 值 |
|---|---|
| 发布名 | `V1.3.0` |
| 产品版本 | `v1.3.0` |
| Windows 文件版本 | `1.3.0.0` |
| Git tag | `{{TAG}}`|
| 对应 Git commit | `{{COMMIT}}` |

完整 Git SHA、Tag 与本次实际文件 SHA-256 由构建流程填写。附件校验值见 `SHA256SUMS.txt`，源码Commit见源码包 `SOURCE-BUNDLE-INFO.txt`，包内 `SOURCE-MANIFEST.txt` 提供逐文件摘要。

```text
{{SHA256}}
```

## 仓库、许可与分发状态

- 本仓库为 [summeredge/Minijmp](https://github.com/summeredge/Minijmp)，基于原项目 [garrydu/Minijmp](https://github.com/garrydu/Minijmp) 二次开发。本仓库 `LICENSE` 声明 GNU GPL v3。该声明本身不能证明下列外部代码的授权或许可兼容性。
- Hoeffding D 已替换原 README 片段。Hmisc p 值移植的署名、许可和对照版本记录见 [源码来源](SOURCE-PROVENANCE.md)。
- PI-Data-Viewer、跨项目复用的 Python PI 适配器、PIReader C# 程序及其编译产物均为项目维护者确认的自研代码，纳入 MiniJMP GPL v3。公开构建复用固定 PIReader，历史构建记录缺口不影响本次发布。

## 运行环境与组件

- 发布目标：Windows x64，PyInstaller `onedir`。需保留整个运行目录；终端用户无需另装 Python。当前发布资料没有声明最低 Windows 版本。
- 从源码运行或构建需要 Windows x64 与 Python 3.11 或更高版本；具体版本以构建记录为准。
- 主要运行依赖：Python/Tkinter、NumPy、pandas、SciPy、Matplotlib、Seaborn、statsmodels；Excel 文件读写使用 `openpyxl`、`xlrd`。实际版本和组件许可应以该次 `BUILD-INFO.txt`、`THIRD-PARTY-NOTICES.txt` 与 `THIRD-PARTY-LICENSES/` 为准。
- MiniJMP 不安装 Windows 服务、不要求管理员权限启动。应用配置、表格默认配置、日志、PI 路径及用户数据分别存放，详见 [安装与使用说明](INSTALL-USAGE.md)。

## PI 发布边界

- 公开候选运行包使用固定 PIReader 1.0.0.0。随包 SBOM 和构建信息记录实际文件的 SHA-256。运行包排除三个 OSIsoft 专有 SDK DLL，源码包排除 SDK DLL 和 PIReader.exe。
- 使用 PI 导入需要取得相应授权，在目标电脑安装并配置 PI SDK/PIPC，并具备 PI Server 访问权限。

## 数据与企业验证边界

普通文件分析在本机执行，无需外部应用服务器；未配置PI时可离线使用统计分析和随包帮助。在线链接由用户点击打开。本轮仅构建/一致性/启动冒烟，不代表所有统计场景与Minitab或JMP等效。企业目标机的普通权限、Windows版本兼容性、Defender/EDR、DLP、帮助显示与PI连接仍需现场验收；公开包排除 OSIsoft/AVEVA 的三个专有 SDK DLL。
