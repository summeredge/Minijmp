# Minitab 19 最优设计补充对标

## 结果

唯一比较项：18（PASS 18 / FAIL 0 / N/A 0 / UNSUPPORTED 0）。

- OPT-D: PASS 6 / FAIL 0 / N/A 0 / UNSUPPORTED 0。
- OPT-DIST: PASS 5 / FAIL 0 / N/A 0 / UNSUPPORTED 0。
- OPT-AUG: PASS 7 / FAIL 0 / N/A 0 / UNSUPPORTED 0。

- OPT-D：4 个方形四角候选中选 3 个；独立穷举 4 组，最优 det(X'X)=16，4 组并列。
- OPT-DIST：双方在 9 个候选中选 4 个；独立穷举 126 个组合，最大最小平方距离为 4。
- OPT-AUG：父设计固定为 3 个角点；候选为缺失角点与中心点，分别比较增补前后的 det(X'X)。
- OPT-D 使用原生 2² DOE 对象作为四点候选集；Minitab `FACMODEL A B` 与 MiniJMP 两水平分类主效应模型的模型空间一致。MiniJMP 对比值转换到共同的效果编码矩阵 `[1,A,B]`。
- 命令语义实测：`OPTDES K` 配 `FACMODEL` 执行 D-opt；`OPTDES K C...C` 候选列形式执行 Distance-based，分别用于 OPT-D 与 OPT-DIST。

## Minitab 19 实际命令

- OPT-D:

```text
FFDESIGN 2 4; LEVELS -1 1 -1 1; DESIGN.
OPTDES 3; FACMODEL A B; INDICATOR C7; BRIEF 3.
```

- OPT-DIST:

```text
OPTDES 4 C1-C2; INDICATOR C3; BRIEF 3.
```

- OPT-AUG:

```text
OPTDES 4; RESMODEL A B; INUNIT 0; LEVELS -1 1 -1 1; AUGMENT C3; INDICATOR C4; BRIEF 3.
```

Minitab 19 的 `OPTDES K` + 模型子命令（`FACMODEL`/`RESMODEL`）执行 D-optimal；本机 `OPTDES K C...C` 候选列形式实测输出 Distance-based 设计。

## 证据来源

Minitab 列值与 INDICATOR 为 DIRECT；行列式、秩与穷举最优值由选中点 DERIVED。MiniJMP 结果来自现有生产 API。
Minitab 19 Session Commands 手册第 363–365 页记载 `OPTDES`、`AUGMENT`、`INDICATOR` 和 `DESIGN` 语法。

## 限制

- D-opt 最优设计存在并列解，比较以模型秩和信息矩阵行列式为准，不要求选中同一行号。
- Minitab Distance-based 与 MiniJMP 的搜索方法不同；本例最终四角集合相同，最小距离达到穷举上界。
