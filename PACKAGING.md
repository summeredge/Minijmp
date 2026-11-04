# MiniJMP V1.0 Windows 发布

唯一构建入口 `tools/build_windows_release.ps1`。版本：显示 V1.0，产品/Tag v1.0.0，Windows文件版本1.0.0.0。保留Beta标签和历史构建，禁止覆盖已有目标。

## 前置检查与冻结

使用项目 `.venv\Scripts\python.exe`（Windows x64 Python3.11.9），锁文件 `packaging/windows/requirements-py311.lock`，PyInstaller6.22.3。不得使用Codex运行时替代项目环境。

```powershell
& .venv/Scripts/python.exe tools/release_env.py
& .venv/Scripts/python.exe tools/release_metadata.py
powershell -NoProfile -ExecutionPolicy Bypass -File tools/check_windows_release_ready.ps1
```

发布工作区必须在main、干净，且origin/main为HEAD祖先；允许本地快进领先，不自动推送、不修改同步规则。先提交全部版本源码、发布工具及审核模板，创建本地annotated `v1.0.0`，记录完整SHA，然后构建。源码ZIP没有.git时可按SOURCE-BUNDLE-INFO复现基础构建；正式审核包最终化需Git冻结和对应Tag。

## 构建与产物

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File tools/build_windows_release.ps1
```

Windows x64 PyInstaller onedir/windowed/noupx，运行时在_internal；解压即用，无额外Python安装和管理员权限要求。仅排错可使用-SkipSmoke，正式审核必须执行冒烟。

- `dist/MiniJMP-V1.0/`：实际运行目录。
- `dist/MiniJMP-V1.0-Release/`：审核目录，包含MiniJMP-V1.0-Windows-x64.zip、MiniJMP-V1.0-Source.zip、VERSION-INFO.md、INSTALL-USAGE.md、SOURCE-PROVENANCE.md/.csv、BUILD-INFO.txt、SBOM.cdx.json/.csv、THIRD-PARTY-NOTICES.txt、完整LICENSE目录及SHA256SUMS.txt。
- `docs/release/pyinstaller-build-V1.0.txt`、`build-inputs-V1.0.txt`：构建记录。

工具保留旧产物；新版本目标存在即阻断，不能擅自删除或覆盖。PyInstaller进度写stderr，以退出码判断。

## PI组件与许可证边界

本版不分发授权未确认的PIReader.exe与OSIsoft三个DLL，源码包也排除这些二进制、本机config.txt/tags.txt及缓存。保留PI业务接口、PIReader源码、干净配置模板。启用时自行提供合法授权的x86 PIReader/.NET Framework4.8、匹配PI SDK/PIPC及PI访问权限；不会安装或注册SDK。

SOURCE-PROVENANCE列出源码继承/修改/新增/待确认分类。Hoeffding复制片段与PI来源许可仍待补充；即使构建通过也不得宣称合规已放行。SBOM记录实际依赖、二进制、未知版本/许可与排除组件，不以requirements清单代替实际打包核对。

## 一致性与冒烟

工具复用make_zip的DLP文件头扫描、CRC、全文件hash与EXE条目hash比较。ZIP落盘后等待120秒沉降，间隔读取一致才写hash，之后再等待90秒复核；不调整Defender/DLP策略。构建目录与新解压目录分别启动冒烟，90秒内识别真实MiniJMP窗口，裸tk标题不算通过。工具写SHA256SUMS时不计算其自身，BUILD-INFO不自包含其自身摘要。

```powershell
& .venv/Scripts/python.exe tools/make_zip.py inspect dist/MiniJMP-V1.0-Release/MiniJMP-V1.0-Windows-x64.zip --entry MiniJMP-V1.0/MiniJMP.exe
& .venv/Scripts/python.exe tools/smoke_launch.py dist/MiniJMP-V1.0/MiniJMP.exe 90
```

对应源码保留GPL、原始署名、构建说明；SOURCE-MANIFEST记录源码包逐项摘要。检查SOURCE-BUNDLE-INFO的Commit与BUILD-INFO及annotated tag一致。审核材料中的Commit/hash由release_metadata.py --finalize从冻结源码及实际ZIP填写。

企业目标机Defender/DLP、普通权限、离线帮助实屏和PI连接仍待现场验收；本机启动冒烟不能替代这些验收。不启动额外统计回归或Minitab对标。
