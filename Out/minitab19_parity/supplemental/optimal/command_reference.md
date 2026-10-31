# Minitab 19 Session Command 依据

来源：Minitab 官方 Session Commands PDF，`OPTDES`，第 363–365 页；官方入口：
https://support.minitab.com/zh-cn/minitab/media/pdfs/notranslate/session_commands.pdf

- `OPTDES K` 的文档用途是选择 D-optimal 设计，需用 `FACMODEL`、`MIXMODEL` 或 `RESMODEL` 指定模型。
- `OPTDES K C...C` 接收等长数值候选列；此命令形式不允许 `FACMODEL`、`RESMODEL` 等模型子命令。
- `AUGMENT C` 使用与设计列等长的整数标记列识别增补设计；`INDICATOR C` 可存储所选行标记。
- 本机 Minitab 19.1.0.1 实测 `OPTDES 4 C1-C2` 的输出标题为 Distance-based 选点；四角被选中，显示最小欧氏距离 2.0000。`comparison.csv` 将其平方后与 MiniJMP 的最小平方距离 4 比较。
- D-opt 使用原生 `FFDESIGN` 建立四角 DOE 对象，再执行 `OPTDES 3; FACMODEL A B`；输出确认模型项 A、B，候选 4 行、选中 3 行、`det(X'X)=16`。
- 增补命令以标记 `[1,1,1,0,0]` 固定前三行，并从缺失角点/中心点中选择一行；实测选择缺失角点，`det(X'X)` 从 16 增至 64。

完整命令和原始 COM 输出见 `session_commands.txt` 与 `minitab_raw.txt`。
