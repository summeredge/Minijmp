# 筛选设计独立参考核验

本目录的证据用于 C0 研究，不等于 PB/DSD 生产实现验收，也不是 Minitab 导出或标准序一致性证明。统一索引及 SHA-256 见 [manifest](../../tests/fixtures/doe_screening_reference/manifest.json)。测试不导入任何 MiniJMP 生产 DOE 生成器。

## PB

2026-10-28 第二轮新增 [NIST PB24 原始表](https://www.itl.nist.gov/div898/software/dataplot/dex/PB24.DAT)，原始 SHA-256 为 `4f7984fdafff362782a7b79bcd4c14880ea4b3d959c40e571b157176c905a731`，转换 CSV 的 SHA-256 为 `e10e4014c68e4a1e5a0a33503913c7a6a241f58a3baf969f35ab007062284aa1`。24×23 矩阵满足列平衡和 `XᵀX=24I`；不含目标主效应的两因子交互投影中，绝对交叉积 0 有 3036 个、8 有 2277 个。产品标准序尚无导出证据。

[NIST PB36 原始表](https://www.itl.nist.gov/div898/software/dataplot/dex/PB36.DAT) SHA-256 为 `e10c10dc5ed37d36415b4122b50fcb794c25940425a5560d147a52802df3f7ed`，按原表将 1/2 转为 +1/−1 的 CSV SHA-256 为 `d8d84eddab02b4b6f72b90f39d7413e580065be1e698b3821730de0207325d32`。36×35 列平衡且 `XᵀX=36I`；不含目标主效应的二因子交互绝对交叉积 4、12、28 分别为 16320、3264、51 个。

PB 的文本因子伪中心按 [Minitab 中心点说明](https://support.minitab.com/en-us/minitab/help-and-how-to/statistical-modeling/doe/supporting-topics/factorial-and-screening-designs/how-minitab-adds-center-points/) 覆盖每个分类水平组合；全部为文本因子时不增加中心点。独立线性模型测试两文本因子、两重复、两区组和每重复两个中心点，核对 40 行、每组四种分类组合各两次、区组调整后的中心偏差及按区组与实际设置分组的纯误差。

PB32/40/44/48 采用可验证数学构造：32 为 Sylvester 阶 32 Hadamard 矩阵；40 为阶 2 Hadamard 与上面 NIST PB20 加截距后的阶 20 矩阵的 Kronecker 积；44/48 为 Paley I 型，分别取素数 q=43、47，令 `Q[i,j]=χ(i-j)`，`χ(0)=0`，其余为二次剩余特征，构造 `H=[[1,1ᵀ],[1,Q-I]]`。删去全 1 截距列并按前缀选取因子，得到平衡正交矩阵；构造依据见 [Paley 矩阵研究论文](https://doi.org/10.1007/s10801-021-01033-x)，独立测试用 SciPy Hadamard、Kronecker 积及 Euler 判据核对。32/40/44/48 某组已选主效应与交互的投影依次为 1、−1/5、3/11、1/6；32 可产生完全混杂，不应描述为仅有部分混杂。以上是数学支持，未经 Minitab 点序或别名结构逐项对标。

独立参考来自美国 NIST Dataplot 的 [12](https://www.itl.nist.gov/div898/software/dataplot/dex/PB12.DAT)、[20](https://www.itl.nist.gov/div898/software/dataplot/dex/PB20.DAT)、[28](https://www.itl.nist.gov/div898/software/dataplot/dex/PB28.DAT) 次矩阵；28 次按原表完整 27 列读取，并将 1/2 映射为 +1/−1。来源、原始和转换后哈希、NIST 读取示例的列数笔误、参考解释见 [PB README](../../tests/fixtures/doe_screening_reference/pb/README.md)。Minitab 官方明示 28 次采用特殊构造，不能套用单列循环法。

三份矩阵依次为 12×11、20×19、28×27，列平衡、`XᵀX=nI`，带截距的主效应矩阵满秩。对于 `x1` 与 `x2*x3`，投影系数依次为 −1/3、−1/5、−5/7；这些是部分混杂，不是完全别名。运行和因子列置换、因子单列反号不影响正交性质，但会改变投影符号及列名，比较时必须同步变换。满容量主效应模型饱和，没有残差自由度。

## 全连续 DSD

C0 独立 `dsd/verify.py` 原先同时要求本地连续清单包含上级清单中的混合参考，因清单边界不一致而失败；现按本地清单核验四个连续参考，混合参考继续由上级 manifest 的独立测试核验。原始 CSV 与 SHA-256 未改；原脚本失败、修复后四项精确有理数审计及新增回归均通过。

第二轮的 2–5 连续因子取原 6 阶 conference 构造前缀列、9 连续因子取原 10 阶构造前 9 列；分别保持 13、21 次运行。独立读取原有 C0 CSV 后截取列，逐项验证主效应秩为 k+1、主效应及平方模型秩为 2k+1，以及主效应与所有二阶项的整数交叉积为零。折叠设计的成对反号使三次乘积抵消；平方列对应不同零点且整体中心行区分截距，故前缀列仍保持所述秩。

单分类扩展使用 C6 的前 m+1 列（m=1–5）：将最后一列的两个零改为 +1/−1，用两个实际分类水平的伪中心替换整体中心。14 行成对反号，主效应与二阶项的奇次交叉积为零；独立计算的主效应加连续平方项秩依 m 为 4、6、8、10、12。m=4 原 C0 矩阵保持不变；其他配置是一般数学构造，未声称 Minitab 矩阵或伪中心选取一致。

11–48 因子连续 DSD 使用相应官方基础运行数的 conference 阶数：素数 q=11、13、17、19、23、29、31、37、41、43、47 使用 Paley 二次剩余构造；q=25 使用 GF(5)[u]/(u²−2)，2 在 GF(5) 中为非平方；16 阶矩阵使用 [反对称 Hadamard 的倍阶构造](https://citeseerx.ist.psu.edu/document?doi=cfb7cf3e914336819b8d39359af58d66f4e448bf&repid=rep1&type=pdf)，令 `C=H−I`。每个阶数均直接验证 `CᵀC=(N−1)I`，取列后与负值折叠及一个零中心点构成设计。单分类方案按同样的零点替换和两个伪中心扩展至 1–47 个连续因子；成对反号使线性效应与二阶项的交叉积为零。逐配置测试核对实际水平、官方运行数、重复/恢复、一阶秩、主效应加平方秩及二阶正交性；全二阶模型秩另按 `1+N+k` 核验，不将秩亏模型的全部系数视为可估计。它们不是 Minitab 产品矩阵或标准序证据。

4 连续加 2 分类采用 6 阶 C0 参考的六列，将两分类列各自的零点对替换为 `(+1,−1)`，另加入 `(0,0,0,0,+1,+1)` 和它的反向点。12 个原始点及两个伪中心均成反向对，因此主效应与二阶项的三次乘积在配对行相消；主效应之间并非两两正交：连续与分类列交叉积为 ±2，两个分类列交叉积为 6。直接整数审计得到一阶模型秩 7、加四个连续平方项后的秩 11。该方案是可核验的数学构造，不声称模拟 Minitab 的多分类伪中心迭代算法或标准序。

[DSD README](../../tests/fixtures/doe_screening_reference/dsd/README.md) 和 [独立构造](../../tests/fixtures/doe_screening_reference/dsd/verify.py) 给出来源及有限域 conference matrix 构造。6、7、8、10 因子分别为 13、17、17、21 次；每列低、高水平平衡，主效应与全部平方项和两因子交互正交，主效应加全部平方项满列秩。全部二阶模型的参数数/秩分别为 28/13、36/16、45/17、66/21；秩亏不能解读为所有系数可估计。231 个三因子投影的完整二次模型均为 10 列满秩。数学参考与 Minitab 逐点顺序的等价关系尚未验证。

混合分类参考为 4 连续加 1 分类、14 次运行，按 [Jones 与 Nachtsheim (2013)](https://www.jmp.com/content/dam/jmp/documents/en/white-papers/dsd-with-added-two-level-categorical-factors.pdf) 第 2 节独立构造：取 6 阶连续参考的前五列及其反向配对，分类列的两个零按 `z,-z` 填入，再添加分类水平 `b,-b` 的两个伪中心。`z,b` 均取 ±1，四种组合的一阶信息矩阵行列式均为 1736000；本例取 `z=b=1`。测试检查水平、成对反号、秩、四种选择与主效应对交互的投影，以及论文报告的截距交互混杂最大绝对值 1/7。它是数学构造，不代表 Minitab 导出或产品逐点等价；其他分类数及伪中心分配仍须配置级证据。

## 独立验收与产品导出

第二轮产品逐点核对需要 Minitab 22 原始工作表、确切版本和创建选项：

- PB：12、20、24、28、32、36、40、44、48 次各导出满容量、无中心点、单重复、标准序；再选择 24 和 40 次各导出含两个文本因子、每重复两个中心点、两重复且按重复分区组的设计，另附相同 seed 的随机序。
- 连续 DSD：各 conference 阶数至少导出 6、8、10、12、14、16、18、20、24、26、30、32、38、42、44、48 因子单重复标准序，并导出 2、7、9、21、33、45 因子的列子集案例。
- 混合 DSD：导出 1、4、5、9、23、47 个连续因子加 1 个两水平分类因子，以及 4 连续加 2 分类；另导出 4 连续加 3 分类等产品可创建配置，用于核对尚未实现的多分类伪中心。对 6 连续及 4 连续加 2 分类各另导出 4 重复、2 区组和固定 seed 的设计。
- 连续水平统一使用 0 和 10，文本因子的两个水平使用可区分的文本；随机序样例固定 seed=1234。每份保留 `StdOrder`、`RunOrder`、`PtType`、`Blocks`、所有因子列、真实水平及类型；若某选项不受支持，记录实际界面与错误。产品导出缺口只影响对应产品一致性结论，不改变数学审计结果。

饱和 PB 主效应的 Lenth PSE：`s0=1.5·median(|effect|)`，保留严格满足 `|effect|<2.5·s0` 的效应，再取 `PSE=1.5·median(保留值)`；探索性参考线 `t(.975,m/3)·PSE`。公式见 [Minitab 效应图方法](https://support.minitab.com/en-us/minitab/help-and-how-to/statistical-modeling/doe/how-to/factorial/analyze-factorial-design/methods-and-formulas/effects-plots/) 与 [Waterloo 独立研究报告](https://uwaterloo.ca/business-and-industrial-statistics-research-group/sites/default/files/uploads/documents/rr-94-12.pdf)。11 个效应 10 个为 2、1 个为 50 时，PSE 为 3、参考线为 8.636634489208934；测试还覆盖严格截断及零中位数。PSE 依赖效应稀疏假设，不能当作常规残差标准误。

DSD 指定模型 `X` 的数值零空间由 SVD 求得；对比 `cᵀβ` 可估计当且仅当 `c` 与 `null(X)` 正交。秩亏时仅显示满足该条件的单个系数；可估对比可用最小范数解计算，推断的方差由 `cᵀX⁺(X⁺)ᵀc·MSE` 计算，残差自由度为 `n−rank(X)`。独立测试从 C0 原始 6 因子矩阵构建 13×14 秩亏模型，核对零空间、可估主效应、不可估交互项及预测对比；重复数据以独立伪逆核对标准误和 p 值。F1² 对 F2×F3 在调整截距及全部主效应后的投影系数独立计算为 −13/15。名义 p 值不代表独立确认。

DSD 区组按 [Minitab 指定设计说明](https://support.minitab.com/en-us/minitab/help-and-how-to/statistical-modeling/doe/how-to/screening/create-definitive-screening-design/create-the-design/specify-the-design/) 将相同数量的完整重复分配至每个区组；不能均分时拒绝。独立模型参考使用 C0 6 因子矩阵、4 重复及 2 区组，核对实际区组列、参考区组、系数、残差平方和和自由度。随机顺序及分配标准序不声明与 Minitab 一致。

对于每个 fixture 固定列顺序和编码；先核查 SHA-256、尺寸、水平、截距和主效应秩，再用交叉积、投影和独立模型矩阵计算混杂及可估计性。连续 DSD 的主效应正交性不能推及未经证明的分类配置。参考矩阵的数学等价和 Minitab 的产品标准序是不同验收层次。

建议以 Minitab 22 或实际使用版本分别导出：PB 12/20/28 次满容量，DSD 6/7/8/10 连续因子，以及 6 因子中分别 1 个和 3 个分类因子的混合设计；另给混合设计两个重复、两个区组案例。设置为标准序、单重复、无额外中心点（区组案例除外），每列使用可区分水平；另外固定随机种子导出随机序。提供软件确切版本和菜单设置，列至少为 `StdOrder`、`RunOrder`、`PtType`、`Blocks`、所有因子和类型/实际水平。产品不提供某选项时记录实际可选项及错误，不推测矩阵。产品标准序和多分类伪中心构造在收到并核验前保持未验证。
