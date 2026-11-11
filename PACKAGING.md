# MiniJMP V1.0 Windows 发布

唯一构建入口 `tools/build_windows_release.ps1`。版本：显示 V1.0，产品/Tag v1.0.0，Windows文件版本1.0.0.0。保留Beta标签和历史构建，禁止覆盖已有目标。

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

发布工作区必须在main、干净，且origin/main为HEAD祖先；允许本地快进领先，不自动推送、不修改同步规则。先提交全部版本源码、发布工具及审核模板，创建本地annotated `v1.0.0`，记录完整SHA，然后构建。源码ZIP没有.git时可按SOURCE-BUNDLE-INFO复现基础构建；正式审核包最终化需Git冻结和对应Tag。

## 构建与产物

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File tools/build_windows_release.ps1 -CertificateThumbprint '<证书指纹>'
```

`-CertificateThumbprint` 指定用于签名的代码签名证书，也可通过 `MINIJMP_SIGNING_THUMBPRINT` 环境变量提供；`-CertificateStore` 可选 `CurrentUser` 或 `LocalMachine`，默认 `CurrentUser`。`-PiSdkDirectory` 指定三个合法 PI SDK 编译引用的目录，默认项目 `PIReader` 目录。`-FrameworkReferenceDirectory` 指定 .NET Framework 4.8 参考程序集目录，默认系统 Developer Pack 目录；没有 Developer Pack 时可使用 [Microsoft 官方 net48 参考程序集](https://www.nuget.org/packages/Microsoft.NETFramework.ReferenceAssemblies.net48/1.0.3)解压后的 `build/.NETFramework/v4.8` 目录。`-SignToolPath` 可选，用于指定 `signtool.exe` 路径。

本机测试可只在 `CurrentUser\My` 创建自签名代码签名证书，再把指纹传给构建入口：

```powershell
$cert = New-SelfSignedCertificate `
    -Type CodeSigningCert `
    -Subject 'CN=MiniJMP Local Test Signing' `
    -CertStoreLocation 'Cert:\CurrentUser\My' `
    -HashAlgorithm SHA256 `
    -NotAfter (Get-Date).AddYears(1)

powershell -NoProfile -ExecutionPolicy Bypass -File tools/build_windows_release.ps1 `
    -CertificateThumbprint $cert.Thumbprint `
    -CertificateStore CurrentUser
```

该自签证书仅用于测试签名流程，默认不受 Windows 或其他计算机信任。不要将其导入 `Root` 或 `TrustedPublisher`；签名存在不代表发布者可信。[New-SelfSignedCertificate 官方说明](https://learn.microsoft.com/en-us/powershell/module/pki/new-selfsignedcertificate)。

Windows x64 PyInstaller onedir/windowed/noupx，运行时在_internal；解压即用，无额外Python安装和管理员权限要求。仅排错可使用-SkipSmoke，正式审核必须执行冒烟。

- `dist/MiniJMP-V1.0/`：实际运行目录。
- `dist/MiniJMP-V1.0-Release/`：审核目录，包含MiniJMP-V1.0-Windows-x64.zip、MiniJMP-V1.0-Source.zip、VERSION-INFO.md、INSTALL-USAGE.md、SOURCE-PROVENANCE.md/.csv、BUILD-INFO.txt、SBOM.cdx.json/.csv、THIRD-PARTY-NOTICES.txt、完整LICENSE目录及SHA256SUMS.txt。
- `docs/release/pyinstaller-build-V1.0.txt`、`build-inputs-V1.0.txt`：构建记录。

工具保留旧产物；新版本目标存在即阻断，不能擅自删除或覆盖。PyInstaller进度写stderr，以退出码判断。

## PI组件与许可证边界

PIReader/ 源码由 MiniJMP 项目自研，按项目 GPL-3.0-or-later 许可；Windows 运行包内的签名程序位于 `PIReader/PIReader.exe`。SBOM 从实际运行目录读取该签名后文件的版本和 SHA-256，不使用仓库内的旧 EXE。源码包仍排除 PIReader.exe、SDK DLL、本机 config.txt/tags.txt 和缓存。

三个 OSIsoft/AVEVA DLL 仍是专有第三方组件，不属于 MiniJMP 自研代码或 GPL 许可，其再分发授权仍未确认。构建仅将 `-PiSdkDirectory` 指定位置的文件用作编译引用，不复制或安装这些 DLL；目标机须自行具备合法的匹配 PI SDK/PIPC 运行环境。

SOURCE-PROVENANCE列出源码继承/修改/新增/待确认分类。`code/pi_reader.py` 仍保留其文件头所列 PI-Data-Viewer 来源及许可待核实状态；Hoeffding 复制片段的许可也待补充。即使构建通过也不得宣称整体合规已放行。SBOM记录实际依赖、二进制、未知版本/许可与排除组件，不以requirements清单代替实际打包核对。

## 一致性与冒烟

工具复用make_zip的DLP文件头扫描、CRC、全文件hash与EXE条目hash比较。ZIP落盘后等待120秒沉降，间隔读取一致才写hash，之后再等待90秒复核；不调整Defender/DLP策略。构建目录与新解压目录分别启动冒烟，90秒内识别真实MiniJMP窗口，裸tk标题不算通过。工具写SHA256SUMS时不计算其自身，BUILD-INFO不自包含其自身摘要。

```powershell
& .venv/Scripts/python.exe tools/make_zip.py inspect dist/MiniJMP-V1.0-Release/MiniJMP-V1.0-Windows-x64.zip --entry MiniJMP-V1.0/MiniJMP.exe
& .venv/Scripts/python.exe tools/smoke_launch.py dist/MiniJMP-V1.0/MiniJMP.exe 90
```

对应源码保留GPL、原始署名、构建说明；SOURCE-MANIFEST记录源码包逐项摘要。检查SOURCE-BUNDLE-INFO的Commit与BUILD-INFO及annotated tag一致。审核材料中的Commit/hash由release_metadata.py --finalize从冻结源码及实际ZIP填写。

企业目标机Defender/DLP、普通权限、离线帮助实屏和PI连接仍待现场验收；本机启动冒烟不能替代这些验收。不启动额外统计回归或Minitab对标。
