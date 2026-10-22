# 2026-10-22 项目资料归档

本目录保留 Beta 1 清理前未引用的历史输出和旧 Windows 依赖清单。归档不代表这些测试日志是本次发布测试结果。

- `logs/pytest_before.txt`：此前位于仓库根目录的未引用 pytest 输出。
- `logs/g7-test-results-duplicate.txt`：根目录副本；与 `docs/g7-evidence/full-tests.txt` 字节相同。
- `logs/multisheet-*.txt`：此前位于 `log/` 的六份多工作表回归输出。
- `dependencies/requirements.txt.old`、`dependencies/winreq.txt`：未被当前启动/环境脚本引用的旧依赖清单。当前开发环境继续由根目录 `requirements.txt` 和 `setup_env.bat` 管理。

根目录 `log/error.log` 是应用当前运行日志，保留原位并继续写入；它不随 Windows 测试包分发。
