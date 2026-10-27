# DOE 开发合同

## DOE-3 中心复合设计与响应面

`doe_ccd.create_ccd` 支持 2–5 个连续因子的面心 CCF（α=1）和旋转外接 CCC（α=(2^k)^(1/4)）。每次独立重复包含全部因子点和轴点；中心点数是整个设计的独立运行数。标准序、随机序、点类型、重复号、编码及实际设定值随工作表保存，DOE-0 指纹和 CCD 完整矩阵校验共同保护输入；实测与响应可后填。历史仅占位的 central_composite 元数据继续可加载，但不能作为完整 CCD 分析。

编码变换为 X=(低+高)/2+x(高−低)/2。输入及中心值须可无损表示，CCC 轴点由有限精度浮点运算计算，创建前展示实际值并要求确认越界工艺安全。轴点和编码列修改都会被校验拒绝。没有实现内接设计、区组或响应优化。

`doe_rsm.analyze_rsm` 用 SVD 拟合完整二次模型，检查秩与条件数；使用相同设定的独立实验估计纯误差。模型推断使用残差均方，要求误差独立、同方差、正态及模型充分；纯误差方差不可辨时不提供推断。失拟检验要求有效纯误差和失拟自由度。曲率使用中心点与全因子点的均值对比，并以纯误差为分母。图形使用同一分析快照；斜线及红色表示因子点超立方体之外，轴点存在于其中部分位置，不能将整片区域误认为已实验。

| 生产入口 | 独立参考和边界 | 验证 |
| --- | --- | --- |
| create_ccd、validate_ccd | 2–5 因子点计数、轴点、矩阵秩及等半径预测方差；篡改和精度边界 | tests/test_doe_ccd.py |
| analyze_rsm | 独立解析多项式、独立矩阵和 SciPy 分布参考 | tests/test_doe_rsm.py |
| 创建、分析、绘图、保存及恢复 | 真实 Tk 和工程往返、复制、来源失效 | tests/test_doe_rsm_gui.py |

DOE-4 可基于返回的系数和 `model_matrix` 计算预测，但优化可行域、约束和目标函数尚未定义或实现。

## DOE-2 正规两水平部分因子

`doe_fractional.create_fractional` 支持 3–6 个按 A 至 F 连续编号的连续因子、正生成元及独立重复。生成元左侧为末尾派生因子，右侧仅能按因子顺序引用至少两个不同的基础因子，例如 `D=ABC`、`D=AB;E=AC`；不接受负号、循环、派生因子参与右侧、重复列或分辨度低于 III 的设计。生成的全部定义字与别名组保存在 DOE-0 元数据中，分析时重新验证它们、运行组合、生成关系和运行顺序。中心点、区组、foldover 与非正规分数设计不支持。

界面提供常见半实施、四分之一实施和自定义生成元，预览运行数、分辨度和别名。`doe_fractional_analysis.analyze_fractional` 从实际设计矩阵确定完整别名组，每组只选择一个代表列；效应为编码系数的两倍，代表整个别名组，不能视为单个物理效应。无独立重复、饱和模型或纯误差方差不可辨时不推断；有独立重复时经典 OLS 使用模型残差均方，假设模型充分且误差独立、同方差和正态。报告分别列示纯误差与失拟平方和和自由度，不将混杂效应单独宣称显著。

图形使用分析快照，主效应与交互条件均值可能混杂；效应图明确标为别名组效应。随机 seed 只生成可重现的运行顺序，不能取代实验现场的随机化、独立重复、区组安排及物理可行域判断。部分因子设计不支持曲率分析；Plackett–Burman 和响应优化尚未实现。

| 生产入口 | 独立参考和边界 | 本轮证据 |
| --- | --- | --- |
| create_fractional、validate_fractional_design | 手算定义字与 NumPy 列乘；III/IV/V、两生成元及重新签名的错误运行 | `tests/test_doe_fractional.py` |
| analyze_fractional | 手算 ±1 编码系数与纯误差，SciPy t/F 分布；独立重复、无重复及饱和模型 | `tests/test_doe_fractional_analysis.py` |
| 创建、分析及保存恢复 | Tk 工作表输入、图形和 `.dexpl` 往返 | `tests/test_doe_fractional_gui.py`；尚未覆盖全部交互边界 |

## DOE-1 当前实现

`code/doe_factorial.py:create_factorial` 接受 `two_level_full` 的
`DesignSpec`，生成 2–6 个连续因子的运行表及 DOE-0 元数据。每个独立重复
按照二进制顺序列出全部组合，第一个因子变化最快；中心点排列在所有因子点
之后。每行具有唯一标准序和 ID，再用指定的整数 seed 局部随机化全部行，
运行序独立记录。总运行数限制为 10000，中心水平不能无损表示时拒绝生成。
设定水平、可选实测列和可空响应列分别映射；不自动填补响应。

菜单“试验设计（DOE）”可创建工作表，并从来源表选择响应和模型阶次进行分析。
`doe_analysis.analyze_factorial` 对完整、平衡的因子点使用编码 −1/+1 和
`numpy.linalg.lstsq`；从截距到所选阶次依次加入完整层级项，非截距效应为
2β。含中心点时加入单独中心点偏移，按原合同禁用模型系数及整体模型的 t/F 推断。因子点纯误差平方和为每个因子组合内的
Σ(y−组合均值)²，自由度为因子点运行数减去不同组合数；重复必须是独立
实验。无中心点时，失拟平方和为模型残差平方和减纯误差平方和，自由度为
残差自由度减纯误差自由度；当前代码还输出失拟检验，该检验尚未在本次独立验证。单次全因子即使简化
模型有残差自由度，残差也可能是遗漏交互，默认不提供 t/F 推断。有独立
重复且纯误差方差可辨时，仍以模型残差均方进行经典 OLS 推断，因此需要
模型充分、误差独立同方差且正态的假设，不能据此断言失拟不存在。饱和或
数值上无法辨认纯误差方差时推断不可用。区组字段非空或响应缺失时拒绝分析。

结果表及图形使用同一分析快照；图形提供主效应、可选任意两个不同因子的
交互、效应绝对值 Pareto 及可推断时的残差图。图窗标明响应和快照，切换或
删除来源表时不会把图形绑定到另一张表。响应优化尚不支持。

| 生产入口 | 独立参考 | 定义和边界 | 本轮测试 |
| --- | --- | --- | --- |
| create_factorial | itertools 组合及矩阵乘积 | 2、3、6 因子；重复与中心点 | tests/test_doe_factorial.py |
| analyze_factorial | 手工代入 2²、2³ 多项式 | ±1 编码；饱和模型无推断 | tests/test_doe_analysis.py |
| analyze_factorial | 重复观测误差 ±1：SSE=8、df=4、SE=0.5，t/F 分布用 SciPy | 独立同方差正态误差；无中心点 | tests/test_doe_analysis.py |
| analyze_factorial | 手算遗漏 AB 和 ABC：SSE 分别为 64 和 392 | 无重复，纯误差自由度为零，禁止推断 | tests/test_doe_analysis.py |
| analyze_factorial | 2² 两次重复、遗漏 AB：纯误差 SSE=8/df=4，失拟 SSE=128/df=1，残差 SSE=136/df=5 | 经典残差均方推断依赖模型充分假设；未检验失拟 | tests/test_doe_analysis.py |

## DOE-0 范围

DOE-0 提供可导入的纯数据合同、因子编码、工作表关联和工程元数据往返。它不创建 DOE 界面或一级菜单，不生成全因子/部分因子/CCD 设计矩阵，不拟合模型，也不执行响应优化。

公共入口位于 code/doe_core.py：FactorSpec、DesignSpec、RunRecord、DesignResult、ModelResult、OptimizationResult、randomized_run_order()、design_from_worksheet()、worksheet_metadata()、restore_design_result()。模块不导入 Tkinter。因子展示名和列名保留原类型；稳定因子 ID 使用 ASCII 标识符。连续因子编码以实际 low、high 定义；结果可由二进制浮点无损表示时返回 float 或 int，否则返回 Fraction，不会把不同的大整数水平悄悄编码为同一个浮点数。Fraction 可继续参与编码换算；只有能无损转为 JSON 数值的 Fraction 才能作为工作表运行值保存。

典型调用先声明定义和列映射，再从 DataFrame 读取记录；持久化时把返回的普通字典放在当前表的 doe_metadata 属性中：

    spec = DesignSpec("trial-1", (FactorSpec("A", "温度", 10, 20, "°C"),),
                      ("收率",), seed=7, design_type="two_level_full")
    columns = {
        "run_id": "运行ID", "standard_order": "标准序",
        "run_order": "运行序", "point_type": "点类型", "replicate": "重复",
        "block": None, "factors": {"A": "温度设定"},
        "measured_levels": {}, "responses": {"收率": "实测收率"},
    }
    records = design_from_worksheet(frame, spec, columns)
    table.doe_metadata = worksheet_metadata(frame, spec, columns)
    restored = restore_design_result(frame, table.doe_metadata)

DesignResult.runs 按 DataFrame 行位置排列；每条记录再分别携带 standard_order 与 run_order。dataframe 索引不会进入映射。

分类因子仅保留 factor_type="categorical" 和显式字符串水平的结构；DesignSpec 在 DOE-0 明确拒绝分类/混合水平设计。今后需单独定义类别编码、混合水平模型矩阵及其别名规则，不得把类别水平强制转成连续数值。

## 数据合同

所有版本字段当前均为 1。元数据是受控的普通字典、列表、字符串、整数、有限浮点数和空值，可用 JSON 序列化器的 allow_nan=False 检查。未知字段或版本拒绝加载。schema 没有外部命令、认证或连接串字段，并拒绝绝对路径及非安全 run_id 格式；由于因子/响应名称、映射列名和 run_id 必须参与关联，调用方必须使用非敏感标签和不含个人信息的 opaque ID，通用代码无法判定任意用户字符串是否为 PII。原始 X/Y 值和未映射列名不写入 DOE 元数据。现存 .dexpl 的 pickle 信任边界没有扩大。

    FactorSpec (schema_version=1)
      factor_id, name, unit, factor_type
      continuous: low, high
      categorical: levels (仅预留，不可用于 DOE-0 DesignSpec)

    DesignSpec (schema_version=1)
      schema_version, design_id, design_type, factors, response_names, seed
      design_type: two_level_full | two_level_fractional
                   | central_composite | unspecified
      generators, defining_relations, aliases (仅接受 D=AB 形式的关系标识)
      ccd_alpha, ccd_center_points, ccd_axial_points

    RunRecord (schema_version=1)
      run_id, standard_order, run_order, point_type
      replicate, block, settings, measured_levels, responses

    DesignResult / ModelResult / OptimizationResult (schema_version=1)

    DOE worksheet metadata
      schema_version, design
      column_map: run_id/order/type/replicate/block/factor/measured/response 列标签
      worksheet: schema_version, row_count, column_fingerprint, run_id -> iloc 行映射
                 设计输入摘要（不保存 X、Y 原值）

point_type 目前只接受 factorial、center、axial。轴点记录必须声明 ccd_alpha，且 ccd_axial_points 与轴点行数相同；若声明 ccd_center_points，也须与中心点行数一致。轴点的实际设定值可超出 low/high，但 DOE-0 不根据 CCD alpha 计算它们；FactorSpec 的编码换算只覆盖 [-1, +1]。standard_order 和 run_order 必须分别为 1 到运行数的排列；randomized_run_order(ids, seed) 使用局部随机数生成器，可按同一 Python 运行时重现顺序，保存的运行顺序仍以工作表列为准。run_id 必须唯一且为安全字符串标识符或整数；replicate 表示独立安排的实验重复，不能把同一行的重复测量或连续在线采样自动视为独立重复。block、设定水平、可选实测水平和一个或多个可空响应分别保存。设定值不会替代实测值，响应不会自动填补。

DesignSpec.design_type 是设计级受控字段，取值为 two_level_full、two_level_fractional、central_composite 或 unspecified；Python 构造时默认明确为 unspecified。它与 RunRecord.point_type 的单行类型标记彼此独立。DOE-0 不从生成元、点类型或运行数推断 design_type；缺失或未知 design_type 的 DOE schema v1 元数据拒绝加载。该字段由 DesignSpec.to_dict/from_dict 往返，并进入输入 SHA-256 摘要，修改已保存类型会使元数据验证失败。

工作表通过 iloc 行位置和独立 run_id 列关联，不使用 DataFrame 索引作为主键；因此非连续索引和重复索引不影响映射。列名按原类型显式映射，列顺序/列数由 column_fingerprint 校验，映射列标签及运行 ID、顺序、区组和设定水平纳入输入摘要。重命名、删除、重排列或修改这些设计字段都会使映射失效并明确报错。实测水平和响应是观察值，不进入摘要，可在实验后填入或修正；目标设定值不会替代实测值。SHA-256 摘要只用于发现数据或映射变化，不是匿名化机制；低基数设定可能被枚举还原，不应把摘要当作隐私保护。

DOE 结构经 Worksheets.saveMeta/loadMeta 写入每张表既有的可选 doe 元数据段；.dexpl 外层格式及非 DOE 工作表不变。旧工程缺少 doe 时沿用原加载行为。坏元数据或未知版本导致工程加载失败时，现有工作簿保持不变；不会静默丢弃 DOE 映射。copySheet() 会复制并重新验证该表的 DOE 元数据。

## 后续阶段边界

- **DOE-1**：两水平全因子生成和分析；不包含部分因子或区组控制。继续完善独立参考、界面和异常路径验收。
- **后续阶段**：另行定义部分因子与别名、独立纯误差和失拟；区分独立实验重复和同一次运行的重复采样。
- **DOE-3**：生成并验证 CCD/响应面设计的 alpha、中心点、轴点与旋转性口径。
- **DOE-4**：基于有验证的模型执行响应优化，并报告可行域、预测值与限制。

ModelResult 和 OptimizationResult 当前只是冻结的数据合同，不含估计、检验或搜索逻辑。饱和模型要求 inference_status="unavailable_saturated"，且 t/p/F 字段为空；独立误差自由度不会使 DOE-0 合同允许在零残差自由度时填入这些推断值。

## 验证资料

tests/fixtures/doe_2x2_reference.json 固定了四个编码组合的解析响应。由 Y=50+3A-2B+4AB 直接代入得到 53、41、51、55；按高水平与低水平响应均值差，以及 AB 符号对比除以 2，独立得到效应 A=6、B=-4、AB=8。该夹具和测试不调用 DOE 生成或分析函数，因此只验证参考资料本身，不能证明 DOE-1 分析器已实现。饱和 2^2 四运行模型的残差自由度为零，不能据此宣称残差 p/F/t 推断通过。

最终执行的命令和实际结果记录在项目工作记忆 .agent-memory/MEMORY.md 及当日日志；测试数量以该记录为准。
