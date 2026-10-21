# G20：二项似然比精确检验修复

## 统计定义

对 H0: p=p0 与 H1: p∈[0,1]，每个支持点 y=0,…,n 的非约束 MLE 为 y/n。

λ(y)=L(p0;y)/L(y/n;y)。组合数在比值中消去。精确双侧 p 值为
Σ P_p0(Y=y) · 1{λ(y)≤λ(x)}，包含并列支持点。

实现等价地比较 D(y)=log L(y/n;y)−log L(p0;y)=n·KL(y/n || p0)，
选择 D(y)≥D(x)。用 SciPy `rel_entr` 处理零计数和对数计算，避免直接乘幂的溢出。
并列比较容差为 `32*eps*max(1,abs(D(x)))`；这是浮点排序约定，不改变备择估计。
最终概率使用一次向量化二项 PMF 求和，限制上界为 1，保持 O(n) 支持集遍历。

边界：x=0 或 n 使用相同定义；p0=0/1 时，观测为退化分布唯一可能点则返回 1，
否则返回 0；n=0,x=0 返回 1。非法计数或概率拒绝为 ValueError。
函数签名不变，返回标量 float。极小到不能由 double 表示的概率允许下溢到 0。

## 独立参考与旧错误约束

`tests/test_g20_likelihood_ratio.py::reference` 使用 100 位 Decimal 直接计算
各点的 L(p0)/L(y/n)，通过标准库 comb 计算精确二项概率并枚举求和；不调用生产函数、
SciPy PMF 或 KL。参考容差是 LR 的相对 `1e-13`，独立于生产对数排序实现。
输入浮点 .8 等可能使数学并列值分裂；首轮过严参考比较的三个失败保存在
`initial-oracle-pytest.txt`，未修改生产实现来迎合这些失败。
`p0=.5±1e-10` 测试明确要求区分非并列候选点。

网格覆盖 8 个 n（0,1,2,3,7,10,25,60）、8 个 p0（包括 0、1 和极小尾概率），
逐个检查全部 x，共 928 组输入，另有极端尾、对称并列、近并列与非法域测试。
概率比较使用相对误差且 abs=0，防止把可表示的微小概率误当成零。

| n | p0 | x | 独立参考 | 修复结果 |
|---|---|---|---|---|
| 10 | .5 | 8 | .109375 | .1093750000000001 |
| 7 | .3 | 0 | .1111498 | .11114979999999998 |
| 7 | .3 | 7 | .0002187 | .00021869999999999998 |
| 25 | .1 | 4 | .5076145489081944 | .5076145489081944 |
| 60 | .8 | 40 | .02277446758961043 | .0227744675896104 |
| 1000 | .5 | 0 | 1.8665272370064378e-301 | 1.8665272370063673e-301 |

完整选中支持点及更多边界结果见 `reference-results.json`。
B-01 的选中集合明确断言为 {0,1,2,8,9,10}，并明确排除旧值 .978515625。
从当前 HEAD 提取旧函数，在内存中执行新 B-01 回归，确认 AssertionError；
证据见 `old-implementation-rejection.txt`。未刷新任何旧错误数值基线。

## 修改范围与调用者

- `code/proportion_test.py`：增加 rel_entr 导入，替换 p_likelihood_ratio 实现。
- `tests/test_g16_statistics.py`：仅从历史数值对照中排除错误 LR；Blaker、Sterne、
  单比例报告对照及 LR 一次 PMF 工作量检查均保留。
- `tests/test_g9_tables.py`：模块冻结检查仅对 LR 函数恢复不可变提交的 AST，
  并移除精确匹配的 rel_entr 导入后计算历史 hash；其他计算与数值/报告 fixture 不变。
- `tests/test_g20_likelihood_ratio.py`：独立参考与专项回归。
- `docs/g20-evidence/`：本轮结果、回归日志和审查证据。

限定 code/tests/tools 中 Python 文件检索：生产代码只有一个定义，没有活动 GUI 调用。
GUI 的 `sample_test_dialog.py` 调用 prop_test_1sample/prop_2sample，未改接到 LR。
直接消费者为 G16 测试、G20 测试和 tools/benchmark_statistics.py 的 F04 动态调用；
生产模块末尾只有两个注释示例。进一步检索全仓 Python，另核对了
`docs/g19-evidence/supplemental/benchmark.py` 的相同动态调用，以及
`docs/g19-evidence/summarize_performance.py` 对历史 LR 性能行的 B-01 标注。
这些脚本没有复制生产 LR 公式；不重写 G19 历史性能结论。历史 docs 快照与
G16 从不可变提交加载的旧函数作为历史证据保留，不修改重复旧公式。

开始时已有 `code/proportion_test.py` Fisher 修复、`tests/test_g9_tables.py` 修改、
`tests/test_g19_integration.py` 和整个 G19 证据目录；全部保留。
git diff 相对 HEAD 中的 Fisher hunk 属于进入任务前的修改，不归因于 G20。

## 实际 Patch Review 与复杂度 Audit

逐 hunk 检查生产差异、G16 调整及新增测试，未发现本轮阻断项：

1. 候选 MLE 由 support/n 逐点生成，移除了观测 MLE 固定化和 min(y,n-y) 折叠。
2. null/alternative 的比值方向与极端性方向一致；不是 Sterne 概率排序，也不是等尾替代。
3. rel_entr 的 0·log(0/q)=0 处理支持集端点；退化 null 单独处理，避免 inf−inf 并列。
4. float 并列容差有独立参考和近并列反例保护；未使用 np.isclose 默认的大容差。
5. PMF 仍为一次向量计算，G16 一次调用断言仍生效；无缓存、fallback、配置、抽象层或新依赖。
6. Fisher 支持集边界修复未动，其他比例函数和报告数据未改。
7. G9 继续核对原 fixture hash，LR 的历史 AST 只用于此检查，不参与生产运行；
   没有把新统计结果写成旧基线，也没有豁免整个比例模块。

按 no-stop-gpt Audit 检查新防御：公开辅助入口没有统一上游校验，保留局部域校验；
零样本与退化概率分支是定义域和数值边界所需；并列容差与求和上界用于浮点误差。
未发现有证据应删除的机制，未扩大到其他统计函数或架构。

## 验证环境与结果

项目解释器 `C:\Users\shaoy\Documents\Minijmp\.venv\Scripts\python.exe`，
Python 3.11.9、NumPy 2.4.6、SciPy 1.15.3；已核对实际导入均来自项目 .venv。
未安装、升级依赖，也未使用 Codex bundled Python。

专项命令：`<python> -m pytest -q tests/test_g20_likelihood_ratio.py tests/test_g16_statistics.py tests/test_g19_integration.py --tb=short`。
结果：206 passed，59 warnings，8.14 秒，见 `targeted-pytest.txt`。
其中 G20 新增 87 项测试；网格内部逐点断言不另计 pytest 项数。

完整命令：`<python> -m pytest -q --junitxml=docs/g20-evidence/final-pytest.xml`。
最终结果：**2185 passed，112 warnings，504.92 秒（8:24）**，
见 `final-pytest.txt` 和 `final-pytest.xml`。警告数量与 G19 最终回归相同。
`git diff --check` 通过；实际 Patch Review 未发现本轮阻断项。

首轮完整回归：2184 passed、1 failed、112 warnings，355.66 秒，
唯一失败为 G9 模块冻结检查仍要求旧 LR AST，见 `initial-full-pytest.txt/xml`。
补齐该检查的精确授权豁免后，7 项模块冻结检查全部通过（104 deselected），
见 `g9-guard-pytest.txt`，然后重新执行完整回归。

复用已有 G19 完整基线 2098 passed（`docs/g19-evidence/final-pytest.txt`）；
该基线不是统计正确性的依据，统计正确性由独立参考与旧实现拒绝试验确定。
未 commit、push、merge。未重跑 GUI 人工交互或性能基准；这些不属于本次数值修复的验收要求。

## 结论

**G19 B-01 已解除。** 标准逐支持点 MLE 的二项 LR 定义、精确双侧排序与边界已落实；
独立参考、旧错误拒绝试验、专项与完整回归均通过。
G19 B-02/B-03 的历史限制不在本次修复范围，本结论不替代其人工或外部环境验收。
