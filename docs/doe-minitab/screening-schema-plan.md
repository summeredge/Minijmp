# 筛选设计 Schema 方案（v2 审计与 v3 提议）

## 2026-10-28：v3 实施中的矩阵规范化

当前实现对 `design_type`、按设计因子顺序排列的 `factors`（稳定 ID），以及按 `standard_order` 排列的 `runs` 建立 JSON 对象；每行包含整数编码 `levels`、`point_type`、`replicate` 和 `block`。JSON 使用 UTF-8、排序键、无额外空白后计算 SHA-256。它不包含响应、实测值、工作表行索引或运行序；实际运行序由原有输入摘要校验。恢复时还按固定构造逐点校验，防止重算摘要后把错误矩阵冒充既有来源。

当前校验范围为 NIST PB12/20/24/28/36 和数学构造 PB32/40/44/48 的指定列前缀，以及 2–48 连续 DSD、1–47 连续加 1 分类 DSD、4 连续加 2 分类 DSD。PB 可按重复追加相同数量的中心点，并可将每重复分为一个区组；DSD 可将完整重复均分至区组。恢复时依标准序逐点核对重复、中心点及区组映射。代码固定矩阵与独立测试参考分别保存；它们不是 Minitab 产品导出。验收状态见 [工作包 C 收尾记录](work-package-c-closeout.md)。

PB 允许两水平文本因子。若含连续和分类因子，每个指定中心点按全部文本水平组合展开为 `pseudo_center`；全部因子均为分类时不允许添加中心点。重复、区组、点类型和实际分类水平参与矩阵身份与构造校验。

> 状态：实施前合同草案。本文只定义 PB/DSD 的设计元数据、持久化、指纹和 GUI/测试边界；不代表筛选功能已实现或通过验收。

## 结论摘要

- 当前 DOE Schema v2 是严格的封闭合同：版本、字段集合和设计类型均显式校验。PB/DSD 不只是增加两个枚举，还需要设计族专属点类型、构造来源/矩阵身份及恢复时的矩阵校验，建议升级到 v3。
- 现有保存恢复链路可复用：DOE 元数据随工作表进入 .dexpl，保存、加载和复制时重验；坏工程在替换工作簿前失败，过期设计不会覆盖已有工程。
- 当前指纹允许后填响应和实测水平；设计输入、运行映射、区组、列名或列序改变会使设计失效。SHA-256 是一致性/过期检查，不是文件认证。
- 当前菜单、创建对话框和分析分发没有 PB/DSD 路径。正规部分因子别名分析、CCD/BBD 响应面分析不能直接充当两类筛选设计的生产实现。
- 本方案不改变工作包 B 统计定义、现有 v1/v2 文件内容或当前 feature 状态。

## 1. 审计范围与基线

本次只读检查了：

- code/doe_core.py：FactorSpec、DesignSpec、RunRecord、DesignResult、列映射、指纹和恢复入口。
- code/worksheets.py：saveMeta、loadMeta、copySheet、工程暂存/替换、.dexpl 保存。
- code/MiniJMP.py、code/doe_dialog.py 及 DOE 分析分发。
- tests/test_doe_core.py、tests/test_doe_schema_v2.py、tests/test_doe_persistence.py 和现有 DOE GUI 生命周期测试。
- 对照 docs/doe-minitab/README.md、roadmap.md、feature-matrix.csv、acceptance.md、sources.md、work-package-b-closeout.md。

审计时基线：分支 main，HEAD 886a0311164f691aba4c96093013f645107cb128，起始工作区干净。未执行测试；此文记录的是源码与测试断言审查，不把历史测试结果当成本次运行结果。

## 2. 当前 Schema 与工作表合同

### 2.1 Schema v2 数据形状

code/doe_core.py 当前定义：

- DOE_SCHEMA_VERSION = 2，读取版本为 {1, 2}；元数据顶层版本与 design.schema_version 必须相同。
- DesignSpec.design_type 只接受 unspecified、two_level_full、two_level_fractional、central_composite、box_behnken。
- v2 DesignSpec 使用精确字段集合；v1 的精确字段集合仅缺少 ccd_fraction、block_count。缺字段、额外字段、错误版本或未知类型均拒绝。
- FactorSpec 已有连续 low/high 和显式分类 levels。但 DesignSpec 只允许 CCD/BBD 使用分类因子；分类字段存在不等于 DSD 混合因子已受支持。
- RunRecord 保存 run_id、standard_order、run_order、point_type、replicate、block、设定、实测水平和响应。设定可为连续数值或显式分类标签；实测水平和响应为可空数值。
- 当前 point_type 只接受 factorial、center、axial、edge。generators、defining_relations、aliases 是现有正规分数设计语义，不能改作 PB 部分混杂或 DSD 投影的存储位置。
- DesignSpec.block_count 是设计定义字段，具体每行区组在 RunRecord.block 中。PB/DSD 是否可分区、区组如何分配仍须按各自官方和数学合同验证，不能仅凭字段存在放行。

DOE 工作表元数据结构为：

~~~text
{
  schema_version,
  design,
  column_map,
  worksheet: {
    schema_version, row_count, column_fingerprint,
    run_rows, input_fingerprint
  }
}
~~~

当前 WORKSHEET_SCHEMA_VERSION 为 1。DesignResult 强制运行 ID 唯一、标准序与运行序分别构成完整排列，并验证设定因子集合；CCD/BBD 再调用各自验证器。PB/DSD 尚无相应生产验证器。

### 2.2 保存、加载、复制与失败处理

- 创建入口生成 frame + metadata，再以 app.addSheet(..., {'doe': metadata}) 绑定到工作表。
- saveMeta() 在正常保存时调用 validate_worksheet_metadata()；.dexpl 保存表数据与每表元数据。临时文件写入完成后才用 os.replace 替换目标文件。
- .dexpl 加载会先逐表创建并校验暂存工作表，全部成功后再替换当前工作簿；DOE 元数据无效时保留现有工作表。
- copySheet() 深复制表数据，并通过保存/加载元数据路径生成独立的 DOE 元数据副本。
- _state() 使用不校验 DOE 的快照以允许用户在编辑后继续撤销/离开；真正保存仍执行校验。设计输入已改变时，保存失败且不覆盖既有文件。
- renameSheet() 只改工作表标签，不改变 DOE 设计身份。
- .dexpl 是 gzip 压缩的 pickle。现有打开流程提示只打开可信文件；Schema 校验不改变 pickle 的信任边界。

### 2.3 指纹覆盖与边界

worksheet_metadata() 和 _restore() 当前分开校验三类信息：

1. column_fingerprint：按类型编码的所有列名及其顺序。重命名、重排、增加或删除任何列都会失效；DataFrame 行索引不参与映射。
2. row_count 与 run_rows：行数以及 run_id → iloc 行位置。不依赖、也不改写 DataFrame.index。
3. input_fingerprint：SHA-256 的规范 JSON，覆盖存储的完整设计字典、规范化 column_map，以及逐行 run_id、标准/实际运行序、点类型、重复、区组和设定值。

响应值与 measured_levels 值不进入 input_fingerprint，因此可在创建后填写或修正；改变响应列映射仍会失效。column_map 中任何因子/响应映射变化、设计字段变化或运行结构变化都会失效。

这是无密钥的摘要。它可检测正常编辑造成的不一致，不证明文件来源，也不抵御能同时改写数据与元数据并重算摘要的恶意修改。新版本应保持此语义：响应与实测数据可变，设计身份和设计输入不可静默漂移。

## 3. PB/DSD 代码与测试现状

### 3.1 GUI 与分析路由

- code/MiniJMP.py 现有 DOE 菜单编号为 01–09：全因子、正规部分因子、因子分析、CCD、响应面分析、优化、BBD、预测、叠加等高线。
- CreateDOE 通过 fractional/ccd/bbd 模式选择已有生成器；没有 PB/DSD 创建模式。
- AnalyzeDOE 只接受全因子、正规部分因子、CCD、BBD。PB/DSD 若只扩展 design_type 而不扩展分析分发，会被拒绝或误走现有分析路径。
- PB 的菜单/产品语义属于 Factorial 分析；其分析实现仍须按实际 PB 矩阵计算部分混杂，不能调用正规分数的完整 alias group 输出代替。
- DSD 应有独立 Screening 分析路径；不能作为 CCD/BBD 完整二次响应面直接送入 doe_rsm.py。
- 预测、优化、叠加等高线入口目前也只处理 CCD/BBD。PB/DSD 不应因新增类型而自动出现在这些入口。

### 3.2 相关现有测试

源码审查确认以下覆盖已存在：

- tests/test_doe_schema_v2.py：v1 元数据读取及升级、未知/错误版本拒绝、版本一致性、v2 BBD 往返、分类水平标签往返。
- tests/test_doe_core.py：类型化列名、重复 DataFrame.index、响应/实测值后填、列重排/改名、设定变化、设计类型/响应映射篡改及安全恢复。
- tests/test_doe_persistence.py：多工作表 .dexpl 往返、响应后填再保存、复制隔离、坏元数据不替换现有工作簿、过期 DOE 保存不覆盖原文件。
- tests/test_doe_gui.py、test_doe_rsm_gui.py、test_doe_bbd_gui.py、test_doe_ccd_options_gui.py：真实 Tk 创建/分析、来源切换或删除、CCD/BBD 保存—重开—复制—再分析等现有路径。

当前 feature matrix 仍标记 SCR-001/002/003 为 missing、SCR-006/007 为 partial。现有测试没有 PB/DSD 元数据、矩阵身份、族专属恢复验证或筛选 GUI 路由覆盖；DOE-2 的测试不能替代这些验收。

## 4. 版本决策：新增 Schema v3

PB/DSD 应使用 Schema v3，而不是在 v2 中静默加入新语义。

原因：

- v2 对设计字段集合和枚举严格拒绝未知值。
- PB/DSD 需要新的设计类型与至少一个 DSD 点类；若混合分类设计经证据确认需要区分伪中心点，还需明确表示该点类。
- 新设计必须保存可追溯的构造/参考身份，并在加载、保存和复制时对实际工作表矩阵执行家族专属验证。
- v3 为以上结构提供显式拒绝与迁移边界；现有旧版本来就不承诺读取 v2，新版文件不应承诺可被旧版读取。

保持工作表包装结构不变，因此 WORKSHEET_SCHEMA_VERSION 仍为 1；Schema v3 仅扩展 DOE design 合同及 point_type 可用值。若后续改变 column_map 或 worksheet 的结构，再独立评估工作表 schema 版本。

## 5. 建议的 v3 数据合同

### 5.1 公共字段复用

保留现有字段和含义：

- design_type：新增稳定枚举 plackett_burman、definitive_screening。
- factors：连续因子用 low/high；DSD 连续三水平中的中点由其编码定义导出并校验，不重复存一个可冲突的中点值。分类因子使用显式字符串 levels，不转成数值编码来持久化。
- response_names、seed：原样保留。run_order 是实际顺序的持久事实；恢复时不重新随机化。
- block_count、每行 block、replicate：复用现有字段，但各设计族验证允许组合、数量及完整分配。
- worksheet.row_count、standard_order 和 run_rows 已表达总运行数、标准顺序与行位置；不再加重复的 run_count / run_order 数组字段。

### 5.2 筛选矩阵身份

v3 DesignSpec 增加一个严格校验的 screening_matrix 字段。非 PB/DSD 设计为 null；PB/DSD 必须提供完整对象：

| 字段 | 含义 |
|---|---|
| construction_id | 稳定构造/设计目录 ID，含设计族与构造修订；不得用自由文本猜测算法版本。 |
| source_kind | mathematical_construction、publication 或 minitab_export，明确矩阵证据类别。 |
| source_id | 指向 fixture manifest、出版物条目或用户导出记录的稳定 ID；Minitab 导出须标软件版本和设置。 |
| matrix_sha256 | 64 位小写十六进制摘要，核对规范化的标准序设计矩阵。 |

matrix_sha256 的规范输入固定为：设计族、按 factor_id 顺序排列的因子标识、按 standard_order 排列的编码水平、点类型、重复和区组分配。它不含响应值、实测水平、DataFrame.index 或随机化后的 run_order。随机运行顺序仍由现有 input_fingerprint 覆盖。

示意结构（尖括号内容为占位符）：

~~~json
{
  "schema_version": 3,
  "design": {
    "schema_version": 3,
    "design_type": "definitive_screening",
    "screening_matrix": {
      "construction_id": "<DSD 构造 ID>",
      "source_kind": "mathematical_construction",
      "source_id": "<fixture manifest 条目 ID>",
      "matrix_sha256": "<64 位小写十六进制 SHA-256>"
    }
  },
  "column_map": "<沿用现有映射结构>",
  "worksheet": {
    "schema_version": 1,
    "row_count": "<实际行数>",
    "column_fingerprint": "<现有列指纹>",
    "run_rows": "<现有 run_id 到 iloc 行映射>",
    "input_fingerprint": "<现有输入摘要>"
  }
}
~~~

以上仅展示新增字段位置；生产对象仍要求现有 DesignSpec 的全部必需字段及严格字段集合。

### 5.3 点类型与可推导统计量

- 保留既有 factorial、center、axial、edge 语义。
- v3 为 DSD 普通设计点新增 screening 点类型。若经验证的混合因子构造确有可区分的伪中心点，再增加 pseudo_center；不得把它映射成 axial 或 edge。
- PB 基本两水平运行沿用 factorial；可选中心点仅在来源核实且构造验证通过后使用 center。
- 因子编码、区组结构、秩、别名/部分混杂、模型可估计性、效应和诊断由已验证矩阵及当前模型项重新计算；不把其缓存值写入设计元数据。
- generators、defining_relations、aliases 保持 DOE-2 语义，不储存 PB 投影系数或 DSD 别名结果。

DesignResult 保持通用运行记录合同；新增 PB/DSD 类型验证器须检查设计矩阵、运行数、点类型、因子水平、重复、区组、顺序和保存的矩阵摘要。_restore() 在恢复新类型时必须调用相应验证器，使保存、加载、复制及分析入口使用同一检查。

## 6. v1/v2 迁移与拒绝规则

1. 新读取器接受 v1、v2、v3；v1/v2 只按原字段集合解析，不把缺失的 design_type 猜成某种设计。
2. 先用文件内原始 v1/v2 design 字典校验旧 input_fingerprint，避免先升级字段后误判旧摘要。
3. 完成旧版列/行映射校验后，内存对象规范化为当前合同。下一次正常保存时写 v3，并对规范化设计重新计算 input_fingerprint。
4. 旧设计族的值、运行表、响应、v2 BBD/CCD 配置必须保留；迁移不重排运行、不重新生成矩阵、不重算响应。
5. PB/DSD 必须为 v3；Schema 版本与 design.schema_version 不一致、未知字段/枚举、缺失矩阵身份、未知来源 ID、摘要不匹配、非法分类水平或家族验证失败，一律拒绝。
6. 坏 DOE 元数据仍须在 _replace() 交换工作簿前失败；过期 DOE 保存仍不得替换目标 .dexpl。
7. v3 .dexpl 不承诺旧版 MiniJMP 可读取；不提供降级导出或删字段式“兼容”。

此策略与现有读取路径一致：restore_design_result() 校验而不改调用者元数据；validate_worksheet_metadata() 返回规范化副本，当前工程加载/保存通过该路径完成验证与升级。

## 7. GUI、模块及验收责任

现有 DOE 菜单 01–09 不重排。建议后续按既有菜单增加入口并明确家族路由：

| 阶段 / 验收 | 菜单与生产路由 | Schema / 持久化责任 | 关键 PERSIST 验收 |
|---|---|---|---|
| C1 / ACC-001、相关 ACC-005/006 | PB 创建归入因子设计；现有“03分析因子设计”识别 PB 后调用 PB 专属矩阵分析，不调用正规部分因子 alias-group 分析。 | plackett_burman、构造来源、标准矩阵身份与 PB validator；不改变 DOE-2 旧类型语义。 | 预览/取消/创建；保存、关闭、重开、复制后矩阵身份一致；填写响应后经 Factorial 语义重新分析。 |
| C2 / ACC-002 | 增加 DSD 创建入口，单独支持连续/经证据确认的分类因子配置与预览。 | definitive_screening、三水平/分类映射、伪中心（如适用）、区组/重复及 DSD validator。 | 保存、重开、复制后各因子水平、伪中心/区组分配和实际运行顺序保持；不支持的组合拒绝创建。 |
| C3 / ACC-003、ACC-005/006 | 增加 DSD 专用“分析筛选设计”入口；PB 仍走 Factorial 路径，不能落入 RSM、CCD/BBD 预测或优化入口。 | 消费 v3 恢复的 DesignResult；模型秩与效应由矩阵重算，不写入设计元数据。 | 重开/复制后重新分析；响应改变可重新拟合，设计输入或映射变化使旧分析失效。 |

真实窗口应验证预览不写表、取消不留下半成品、错误配置不改变已有工作表、来源切换/删除时旧对话框拒绝继续、窄窗口下按钮可达。DSD 动态因子配置按现有可滚动 CCD/BBD 对话框模式处理；不做整个 DOE 菜单或 GUI 架构重排。

## 8. 后续测试合同

保留现有 v1/v2 测试作为迁移回归，不刷新或删除旧基线。建议在对应生产实现中新增/扩展：

| 测试层 | 建议文件 | 必须覆盖 |
|---|---|---|
| Schema | tests/test_doe_schema_v3.py | v1/v2 精确读取与升级；v3 PB/DSD 往返；版本/字段/枚举不匹配拒绝；旧 BBD/CCD 字段和值不变。 |
| 独立矩阵 | tests/test_doe_pb.py、tests/test_doe_dsd.py 及 tests/fixtures/doe_screening_reference/ | fixture 来源和 SHA-256；独立秩、水平平衡、主效应与二阶项投影；混杂系数方向；模型可估计性。生产生成器不得用作自己的 oracle。 |
| 指纹/持久化 | 扩展 tests/test_doe_core.py、tests/test_doe_persistence.py | 改设定/顺序/区组/构造 ID/矩阵摘要必失效；后填响应和实测值仍有效；保存重开及复制不丢 source identity；坏摘要不替换工作簿、不覆盖旧文件。 |
| GUI | tests/test_doe_screening_gui.py | PB Factorial 路由与 DSD Screening 路由；创建/取消/预览、错误提示、响应分析、来源切换/删除、保存—重开—复制—再分析。 |
| 旧功能回归 | 现有 DOE 核心、GUI、工作表和文件测试 | v1/v2、DOE-1/2、CCD/BBD 行为无回归；尤其现有 .dexpl、响应后填、分类水平和区组合同。 |

矩阵摘要测试必须用测试内独立规范化过程对 fixture 重算；不能只断言“生产生成结果的 hash 等于生产生成时写入的 hash”。结构指纹的逐项变更测试应包括：factor/column 映射变化、列重排、行插入/删除/重排、运行 ID/标准序/实际运行序、重复/区组、点类型、编码设定变化。响应/实测数据值变化及 DataFrame.index 改变应保持可恢复。

## 9. 范围与限制

- 本文不新增生产代码、测试、fixture、帮助主题、菜单或变更日志；本轮也未运行 pytest。
- PB 官方创建选项、28-run 特殊构造、中心点/区组边界，以及 DSD 各因子数、混合分类伪中心和具体矩阵均以 docs/doe-minitab/sources.md 与独立参考 fixture 核定为准。未核实的配置不应写入 v3 合同作为支持项。
- 工作包 B 的独立 Review 状态与本文无关；本文不宣称 B 已 APPROVE，也不宣布 C0_READY。
- 在矩阵参考、独立测试及其他 C0 交付完成之前，本文只可作为 Schema 子方案供后续实现审查。
