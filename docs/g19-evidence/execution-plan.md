# G19 执行记录

- 日期：2026-10-21，Asia/Shanghai。
- 开始 HEAD：`b430f8c7c4e4870f1dc3a9242e8f2d50ba9ba231`；首次 `git status --short` 输出为空，工作区干净。
- `initial-git-status.txt` 在建立证据目录后留存，因此包含 G19 新目录；不代表开始前已有改动。
- Python：项目 `.venv/Scripts/python.exe`，依赖路径和版本见 environment.json；未安装或升级依赖。

执行顺序：

1. 固定 Git、环境及源码哈希，读取 G12–G18 原始证据。
2. 并行进行只读模块覆盖、历史修复保护和 G15 场景核对；测试和性能只由主任务串行执行。
3. 当前完整 pytest → 真实 Tk/导出验收 → 统计、数据、绘图分阶段性能基准。
4. 有稳定可复现局部缺陷才建立失败测试并最小修复；否则记录 B/C 类事项。
5. 最终完整 pytest、逐文件 diff 审查、五项交付报告和最终结论。

历史结果只作可追溯参照，不作为本轮动态通过证据。模块静态调用关系与测试文件关联不等于分支覆盖；没有 trace/coverage 的入口不推断为已全面动态验证。
不 commit、push、merge，不扩大至 G20。
