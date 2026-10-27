# DOE 开发合同

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

- **DOE-1**：生成两水平全因子与部分因子设计矩阵；明确定义生成元、定义关系、别名、标准顺序、随机运行顺序、重复和区组。
- **DOE-2**：独立验证效应/回归、残差、纯误差与失拟；区分独立实验重复和同一运行的重复采样。饱和模型 residual_df == 0 时不得输出 t、p、F 推断值。
- **DOE-3**：生成并验证 CCD/响应面设计的 alpha、中心点、轴点与旋转性口径。
- **DOE-4**：基于有验证的模型执行响应优化，并报告可行域、预测值与限制。

ModelResult 和 OptimizationResult 当前只是冻结的数据合同，不含估计、检验或搜索逻辑。饱和模型要求 inference_status="unavailable_saturated"，且 t/p/F 字段为空；独立误差自由度不会使 DOE-0 合同允许在零残差自由度时填入这些推断值。

## 验证资料

tests/fixtures/doe_2x2_reference.json 固定了四个编码组合的解析响应。由 Y=50+3A-2B+4AB 直接代入得到 53、41、51、55；按高水平与低水平响应均值差，以及 AB 符号对比除以 2，独立得到效应 A=6、B=-4、AB=8。该夹具和测试不调用 DOE 生成或分析函数，因此只验证参考资料本身，不能证明 DOE-1 分析器已实现。饱和 2^2 四运行模型的残差自由度为零，不能据此宣称残差 p/F/t 推断通过。

最终执行的命令和实际结果记录在项目工作记忆 .agent-memory/MEMORY.md 及当日日志；测试数量以该记录为准。
