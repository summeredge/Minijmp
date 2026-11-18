# MiniJMP Windows 发布

唯一构建入口 `tools/build_windows_release.ps1`。版本由元数据统一声明：`packaging/windows/version_info.txt` 给出产品版本与文件版本，脚本中的 `$releaseVersion`/`$productVersion` 必须与之相同。保留Beta标签和历史构建，禁止覆盖已有目标。

## 公开候选包（GitHub Actions）

`.github/workflows/release.yml` 是公开发布入口。推送符合 `v*` 规则的新版本 Tag 后，Actions 自动构建、校验、上传候选包并创建 GitHub Release。手动运行可指定已有 Tag，仅生成候选包。

- 触发后先校验 Tag 格式、Tag 指向的提交、`version_info.txt` 与其他版本标识一致，以及检出目录干净。
- 运行环境为 Windows + Python 3.11（默认 `windows-2022`），依赖来自 `packaging/windows/requirements-py311.lock`；PyInstaller 参数、onedir/windowed、Splash、图标、依赖收集与 pyarrow 裁剪与内部构建共用同一份脚本参数（`-Public` 模式）。
- `-Public` 重新构建 MiniJMP 主程序，并复用通过固定输入校验的原版 PIReader。公开候选包通过 CRC/SHA256 复核后才可发布。
- 产物：`MiniJMP-<版本>-Windows-x64-portable.zip`、`MiniJMP-<版本>-Source.zip`、`SHA256SUMS-<版本>.txt`，以及 `SBOM.cdx.json`、`SBOM.csv`、`RUNTIME-CONTENTS.csv`、`BUILD-INFO.txt`、`SOURCE-CODE.txt` 和构建/测试记录。
- 自动校验 Tag/版本/Commit 一致、ZIP CRC 与 SHA256、包内 EXE 与本次构建产物一致、包含 PIReader.exe、干净的 PIReader/config.txt 和 tags.txt 模板，不含三个 OSIsoft DLL、真实账号、密码或企业配置，并核对 PIReader 文件版本、x86 架构、产物摘要和 SBOM、Splash 与图标已嵌入、SBOM 版本一致；任一项失败即中止，不会上传正式 Release。

GitHub 托管 Windows Runner 重新构建 MiniJMP 主程序，直接复用 `packaging/windows/pireader/PIReader.exe`，无需安装 PI SDK、MSBuild 或 .NET Framework 4.8 开发引用。PIReader 当前独立版本为 `1.0.0.0`。构建按相邻 `manifest.json` 校验文件版本和 SHA256，并要求产品名为 `PIReader` 或 `MiniJMP PI Reader`、架构为 I386 / Required32Bit。缺少 EXE 或校验不符时中止构建。

只有 PIReader 自身功能变更时才重新编译、现场验证，并更新固定 EXE 和清单中的版本与 SHA256。MiniJMP 升级无需修改 PIReader 的 `AssemblyInfo.cs`。清单可选记录 `source_commit`、`source_sha256` 和 `field_validation`，按实际掌握的信息填写。公开分发权确认后，将固定 EXE 与清单一并纳入发布 Tag。目标电脑使用 PI 数据功能时须合法安装兼容的 PI SDK/PIPC。

公开运行目录为 `MiniJMP.exe`、`_internal/`、`PIReader/PIReader.exe`、`PIReader/config.txt`、`PIReader/tags.txt`。三个禁入文件为 `OSIsoft.PISDK.dll`、`OSIsoft.PISDKCommon.dll`、`OSIsoft.PITimeServer.dll`。默认配置始终为程序根目录下的 `PIReader/config.txt`，不选择根目录或当前工作目录的 config.txt；手动输入、已保存路径和 `PI_CONFIG` 沿用现有优先级。模板仅在新构建目录中生成，不覆盖安装目录的用户配置。

公开版与企业内部版的区别：

| 项目 | 公开候选包（GitHub Actions） | 企业内部构建（本机） |
| --- | --- | --- |
| PIReader / PI SDK | 复用固定 PIReader；排除三个专有 SDK DLL | 从源码构建 PIReader 并随包三个专有 DLL |
| 代码签名 | 不签名 | `-InternalReview` 不签名；正式模式要求双 EXE 可信签名 |
| 等待与复核 | 无沉降等待，单次 CRC/SHA256 复核 | 120 秒沉降 + 写入后 90 秒复核 |
| 产物位置 | Actions Artifacts 候选包 | `dist/` 审核包及 `--finalize` 发布材料 |

## 标准发布流程

1. 更新 MiniJMP 版本信息（`version_info.txt`、脚本中的 `$releaseVersion`/`$productVersion`、关于窗口、README、CHANGES、USAGE），检查发布条件并提交。
2. 推送对应的 annotated Tag（`v<版本>`）。
3. GitHub Actions 校验 Tag 与版本，构建并上传 Artifacts。发布任务复核下载的摘要后自动创建 GitHub Release。

仓库变量 `MINIJMP_ENABLE_PUBLISH=true` 启用自动发布，`release` Environment 无需配置必需审批人。需要暂停自动发布时，将变量设为 `false`，Tag 推送仍会生成候选包。构建任务使用 `contents: read`，发布任务单独使用 `contents: write`，只发布本次验证通过的资产。已有 Release 受保护，重复发布会失败。

构建失败时在 Actions 运行页面按步骤查看日志：`Check the tag…` 报告 Tag/版本/Commit 问题，`Run the … tests` 报告测试失败，`Build the public candidate` 的 PyInstaller 输出同时作为 artifact 上传，`Verify the candidate…` 列出包内容或校验不一致的具体项。

## 前置检查与冻结

使用项目 `.venv\Scripts\python.exe`（Windows x64 Python3.11.9），锁文件 `packaging/windows/requirements-py311.lock`，PyInstaller6.22.3。不得使用Codex运行时替代项目环境。

```powershell
& .venv/Scripts/python.exe tools/release_env.py
& .venv/Scripts/python.exe tools/release_metadata.py
powershell -NoProfile -ExecutionPolicy Bypass -File tools/check_windows_release_ready.ps1 -CertificateThumbprint '<证书指纹>'
```

`requirements-py311.lock` 保留精确版本；配对的 `requirements-py311-hashed.lock` 为同一组版本固定 Windows x64 / CPython 3.11 wheel 的 SHA-256。发布预检逐项核对两份锁文件，缺包、版本不一致或哈希格式错误会阻断。哈希取自 PyPI 官方索引下载的真实 wheel 文件；不匹配时应从可信发行文件重新核验，不得手工推算。

创建 wheelhouse 并由 pip 原生校验下载哈希：

```powershell
& .venv/Scripts/python.exe tools/release_env.py --download-wheelhouse dist/release-wheelhouse
```

若要让当前环境也留下哈希安装证据，从该 wheelhouse 强制重装所有锁定 wheel：

```powershell
& .venv/Scripts/python.exe tools/release_env.py --install-wheelhouse dist/release-wheelhouse
```

该命令使用 `pip install --require-hashes --force-reinstall --no-index`，只安装 wheel，并在 `.venv` 记录 pip 安装报告；预检仅在报告中的包名、版本和 SHA-256 均与锁文件一致时报告“已哈希验证安装”。当前 `.venv` 没有此报告时，版本匹配仍只证明版本，不证明原安装文件经过哈希校验。

发布工作区必须在main、干净，且origin/main为HEAD祖先；允许本地快进领先，不自动推送、不修改同步规则。先提交全部版本源码、发布工具及审核模板，创建本地annotated `v<版本>`（与 `version_info.txt` 的产品版本一致），记录完整SHA，然后构建。源码ZIP没有.git时可按SOURCE-BUNDLE-INFO复现基础构建；正式审核包最终化需Git冻结和对应Tag。

## 构建与产物

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File tools/build_windows_release.ps1 -CertificateThumbprint '<证书指纹>'
```

`-CertificateThumbprint` 指定用于签名的代码签名证书，也可通过 `MINIJMP_SIGNING_THUMBPRINT` 环境变量提供；`-CertificateStore` 可选 `CurrentUser` 或 `LocalMachine`，默认 `CurrentUser`。`-PiSdkDirectory` 指定三个合法 PI SDK 编译引用的目录，默认项目 `PIReader` 目录。`-FrameworkReferenceDirectory` 指定 .NET Framework 4.8 参考程序集目录，默认系统 Developer Pack 目录；没有 Developer Pack 时可使用 [Microsoft 官方 net48 参考程序集](https://www.nuget.org/packages/Microsoft.NETFramework.ReferenceAssemblies.net48/1.0.3)解压后的 `build/.NETFramework/v4.8` 目录。`-SignToolPath` 可选，用于指定 `signtool.exe` 路径。

内部送审使用 `-InternalReview`，可在没有企业证书时跳过签名；正式模式保持双 EXE 可信验签要求。不要使用测试自签名冒充企业签名。

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File tools/check_windows_release_ready.ps1 -InternalReview -FrameworkReferenceDirectory '<官方net48目录>/build/.NETFramework/v4.8'
powershell -NoProfile -ExecutionPolicy Bypass -File tools/build_windows_release.ps1 -InternalReview -FrameworkReferenceDirectory '<官方net48目录>/build/.NETFramework/v4.8' -PiSdkDirectory '<已有SDK目录>'
```

代码签名状态：暂未实施，企业审批及替代控制说明由申请人另行提供。内部送审技术构建成功不代表批准部署，其他完整性、版本、DLP 和启动检查仍执行。

## PI组件与许可证边界

PIReader/ 源码由 MiniJMP 项目自研，按项目 GPL-3.0-or-later 许可。公开包的 BUILD-INFO 和 SBOM 标明复用来源，记录实际文件版本和 SHA256。源码包保留原始版权、项目源码和固定输入记录，排除 EXE、SDK DLL、本机配置和缓存。

三个 OSIsoft/AVEVA DLL 仍是专有第三方组件，不属于 MiniJMP 自研代码或 GPL 许可，其再分发授权仍未确认。内部构建使用 `-PiSdkDirectory` 指定的三个 DLL 作为编译引用；公开模式不复制这些 DLL，企业内部模式仍只复制这三个文件到运行目录 PIReader/，不安装或注册这些 DLL；目标机须自行具备合法的匹配 PI SDK/PIPC 运行环境。

SOURCE-PROVENANCE列出源码继承/修改/新增/待确认分类。`code/pi_reader.py` 仍保留其文件头所列 PI-Data-Viewer 来源及许可待核实状态；Hoeffding 复制片段的许可也待补充。即使构建通过也不得宣称整体合规已放行。SBOM记录实际依赖、二进制、未知版本/许可与排除组件，不以requirements清单代替实际打包核对。

## 一致性与冒烟

工具复用make_zip的DLP文件头扫描、CRC、全文件hash与EXE条目hash比较。ZIP落盘后等待120秒沉降，间隔读取一致才写hash，之后再等待90秒复核；不调整Defender/DLP策略。构建目录与新解压目录分别启动冒烟，90秒内识别真实MiniJMP窗口，裸tk标题不算通过。工具写SHA256SUMS时不计算其自身，BUILD-INFO不自包含其自身摘要。

```powershell
& .venv/Scripts/python.exe tools/make_zip.py inspect dist/MiniJMP-V<版本>-Release/MiniJMP-V<版本>-Windows-x64.zip --entry MiniJMP-V<版本>/MiniJMP.exe
& .venv/Scripts/python.exe tools/smoke_launch.py dist/MiniJMP-V<版本>/MiniJMP.exe 90
```

对应源码保留GPL、原始署名、构建说明；SOURCE-MANIFEST记录源码包逐项摘要。检查SOURCE-BUNDLE-INFO的Commit与BUILD-INFO及annotated tag一致。审核材料中的Commit/hash由release_metadata.py --finalize从冻结源码及实际ZIP填写。

企业目标机Defender/DLP、普通权限、离线帮助实屏和PI连接仍待现场验收；本机启动冒烟不能替代这些验收。不启动额外统计回归或Minitab对标。


V1.2 导入资源与路径要求

- 文件不超过 256 MiB；单表不超过 200 万行、16384 列，各表总计不超过 1000 万单元格。多表文件最多 256 张表；ZIP 容器最多 4096 项、解压后总计 512 MiB；工程 manifest 最大 16 MiB。解析后的表格数据总内存上限 1 GiB。这些上限不是全部进程内存承诺；导入有额外解析开销。超限请按行/表拆分，不会替换当前工作表。
- 完整解压到不超过 80 个字符的本地受控运行目录，例如 C:\Apps\MiniJMP-V1.2；构建仓库路径同样不超过 80 个字符。程序会提示过长的运行目录。正式运行包检查各文件路径与 80 字符安装目录的合计不超过 240 字符；不依赖系统长路径开关，解压前由 IT 确认目标路径。
- 安装目录须由 IT 设置为普通用户只读，禁止从下载目录或多人可写共享盘运行。PIReader 固定路径并不防止文件被替换；部署方须在首次运行及更新前核验全包 SHA256SUMS，并使用 EDR 持续监控 EXE/DLL/PYD 的基线完整性。启动前的完整性替代控制须由 IT 审批及留存证据，当前应用没有签名/哈希自校验。

增量 CSV、Excel XML 预检及 Parquet 批次解析设 60 秒协作式时间预算；在下一记录/批次检查并拒绝。底层 pandas、xlrd、Arrow 的单次调用无法在同步入口中强制中断，不保证严格的 60 秒进程级超时；文件/展开尺寸和批次资源限制用于减少大文件阻塞。

MiniJMP V1.2 Windows 发布包随附三个 PI SDK 相关组件，用于支持 PI 数据访问。PI 数据导入功能须在已取得相应授权、安装并正确配置 PI SDK/PIPC 运行环境，且具有 PI Server 访问权限的企业办公终端上使用。随包组件不构成完整的 PI System 运行环境，也不代表授予额外的软件使用或再分发许可。
