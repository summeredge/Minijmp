# BBD 独立参考数据

ACC-022A 的独立数学参考见 `tests/test_doe_bbd.py`：9 因子由 3×3 模运算重构论文表 4，10 因子按论文因子组独立展开 ±1 组合。ACC-022B 已有用户提供并确认版本为 Minitab 22 的五份参考矩阵；原始 SHA-256、列映射及配置见同目录 `manifest.json`，逐项比较见[参考核验](../../../docs/doe-minitab/bbd-reference-validation.md)。

Git 会按 .gitattributes 将 CSV 行尾规范为 LF；对照测试在内存中还原原始 CRLF 后，核验与 manifest 一致的原始 SHA-256 和字节数，不改动五份 CSV。

五种配置的设计点多重集及区组重编号后的点–区组多重集均与 MiniJMP 数学等价；标准序并非逐行相同，差异行数为 60、116、123、120、163。Minitab 因子 J 映射到 MiniJMP I；10 因子配置的 K 映射到 J。结论仅适用于这五份用户提供的 Minitab 22 配置，不外推至其他版本或设置。生产生成器不充当独立 oracle。
