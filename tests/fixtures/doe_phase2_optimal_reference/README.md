# DOE Phase 2 Mixture Optimal 独立参考

本 fixture 为 `P2-ACC-01/02` 建立独立算术参考。`build_reference.py` 与 `verify.py` 各自实现精确分数消元、Scheffé 行构造、D-optimal 穷举与最远点计算；二者均不导入 MiniJMP 生产模块，也不互相导入。`reference.json` 记录精确矩阵、行列式、候选次序和边界；`manifest.json` 固定其 SHA-256、字节数及空 `production_imports`。

覆盖范围：

- 三组分 Simplex 候选的纯组分起点、后续最远点、平方距离和并列输入顺序。
- Scheffé 无截距二次模型的小候选 D-optimal 穷举；受组分上下界及线性约束的合法候选筛选。
- 组分×过程变量模型项与过程变量 `[-1,1]` 编码；实际比例与现有 lower-bound 伪组分换算往返。
- 线性模型有/无放回选点的穷举、重复 multiplicity、重复候选折叠、秩亏和候选耗尽。
- 固定父设计下 D-optimal 增补的精确结果、有放回的新增 multiplicity、父点保留，以及 Distance 增补把父点作为锚点并排除等价点。
- Distance-based 不重复设计点，以及精确/启发式预算状态标记。启发式案例只验证搜索状态合同，不声称获得全局最优。

参考公式：D-optimal 最大化 `det(X'X)`，仅满列秩结果可接受；距离首点最小化到任一纯组分的平方欧氏距离，后续最大化到已选集合的最小平方欧氏距离。过程坐标按 `(value-low)/(high-low)` 归一到 `[0,1]`。伪组分按现有定义 `x'=(x-lower)/(1-sum(lower))`，用于距离前需还原为物理比例。

重建并核验（Windows PowerShell，使用项目环境）：

```powershell
$python = (Resolve-Path ".venv\Scripts\python.exe").Path
& $python tests/fixtures/doe_phase2_optimal_reference/build_reference.py
& $python tests/fixtures/doe_phase2_optimal_reference/verify.py
```

公开 Minitab 方法页用于限定工作流，不是本 fixture 的数值 oracle；本参考不声称 Minitab 22 产品输出 parity。
