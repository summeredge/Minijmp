# P2-4A 独立参考

本目录为 DSD Stepwise 与 PB Foldover 的独立数值参考。构建与验证脚本只使用
标准库与 `fractions` / `numpy` 的基础线性代数，**不导入任何 MiniJMP 生产模块**；
`tests/test_doe_dsd_stepwise.py`、`tests/test_doe_pb_foldover.py` 通过
`importlib` 直接加载 `verify_*.py` 与生产实现比对。

| 文件 | 作用 |
|---|---|
| `exact_linear.py` | Fraction 精确线性代数（正交化、秩、SSE、伪逆投影） |
| `build_dsd_reference.py` | 5 条 DSD 选择轨迹（S01–S05） |
| `build_pb_foldover_reference.py` | 9 个 PB 运行数的点集、秩与混杂投影 |
| `dsd_reference.json` | 轨迹参考，SHA-256 见 `manifest.json` |
| `pb_foldover_reference.json` | PB 折叠参考，SHA-256 见 `manifest.json` |
| `verify_dsd_reference.py` / `verify_pb_foldover_reference.py` | 从构建脚本重建并逐值比对落盘 JSON |
| `write_fixtures.py` | 重新生成 JSON 与 `manifest.json`（仅在数学变更确认后运行） |

## 方法合同

见 `docs/doe-minitab/phase2-p4a-method-contract.md`。要点：

- 先移除、后进入；进入用加入后模型的 MSE，移除用完整模型的 MSE。
- 秩按列修正 Gram–Schmidt 判定，与生产端同一容差（1e-10）。
- PB 完全混杂＝交互列落在 `span{截距 + 主效应}` 内，不使用正规 defining relation。

## 局限

- 未使用 Minitab 22 产品输出，不构成版本 parity 证据。
- 参考只覆盖合同所列范围（无中心点、分类因子、重复批次、分区组或二次折叠）。
