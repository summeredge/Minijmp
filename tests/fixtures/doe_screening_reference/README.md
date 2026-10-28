# 筛选设计独立参考

PB 参考来自 NIST 设计数据；DSD 参考是依公开文献构造的数学矩阵。均不来自 MiniJMP 生产生成器，也不是 Minitab 软件导出。矩阵来源、设置、哈希及许可的数学等价变换见 [manifest.json](manifest.json) 和各子目录 README；Minitab 精确标准序、种子和未列配置均未验证。

从仓库根目录运行 `& .\.venv\Scripts\python.exe -m pytest tests/test_doe_screening_references.py -q` 进行矩阵与哈希审计；其他独立构造和结果见 DSD 子目录说明。工作包 C 的正式验收仍需相应生产实现、界面、工程持久化以及独立 Review。
