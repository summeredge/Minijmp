"""Minitab 官方 Taguchi 正交表目录：固定标准矩阵，不现场构造。

矩阵逐点取自 Minitab 在线帮助 "Catalogue of Taguchi designs"（2026-10-28 访问），
标准行序即该页顺序；内部编码 1..L 只用于定位列水平。
"""
from dataclasses import dataclass
import hashlib
from itertools import combinations
import json


CATALOG_URL = ("https://support.minitab.com/en-us/minitab/help-and-how-to/"
               "statistical-modeling/doe/supporting-topics/taguchi-designs/"
               "catalogue-of-taguchi-designs/")

_L4 = (
    (1, 1, 1), (1, 2, 2), (2, 1, 2), (2, 2, 1),
)
_L8 = (
    (1, 1, 1, 1, 1, 1, 1), (1, 1, 1, 2, 2, 2, 2), (1, 2, 2, 1, 1, 2, 2),
    (1, 2, 2, 2, 2, 1, 1), (2, 1, 2, 1, 2, 1, 2), (2, 1, 2, 2, 1, 2, 1),
    (2, 2, 1, 1, 2, 2, 1), (2, 2, 1, 2, 1, 1, 2),
)
_L9 = (
    (1, 1, 1, 1), (1, 2, 2, 2), (1, 3, 3, 3), (2, 1, 2, 3), (2, 2, 3, 1),
    (2, 3, 1, 2), (3, 1, 3, 2), (3, 2, 1, 3), (3, 3, 2, 1),
)
_L16 = (
    (1, 1, 1, 1, 1), (1, 2, 2, 2, 2), (1, 3, 3, 3, 3), (1, 4, 4, 4, 4),
    (2, 1, 2, 3, 4), (2, 2, 1, 4, 3), (2, 3, 4, 1, 2), (2, 4, 3, 2, 1),
    (3, 1, 3, 4, 2), (3, 2, 4, 3, 1), (3, 3, 1, 2, 4), (3, 4, 2, 1, 3),
    (4, 1, 4, 2, 3), (4, 2, 3, 1, 4), (4, 3, 2, 4, 1), (4, 4, 1, 3, 2),
)
# 官方页该表列标题为 1..7、9（无 8）；末列与第 3..7 列的组合频数并非全相等。
_L18 = (
    (1, 1, 1, 1, 1, 1, 1, 1), (1, 1, 2, 2, 2, 2, 2, 2),
    (1, 1, 3, 3, 3, 3, 3, 3), (1, 2, 1, 1, 2, 2, 3, 2),
    (1, 2, 2, 2, 3, 3, 1, 3), (1, 2, 3, 3, 1, 1, 2, 1),
    (1, 3, 1, 2, 1, 3, 2, 3), (1, 3, 2, 3, 2, 1, 3, 1),
    (1, 3, 3, 1, 3, 2, 1, 2), (2, 1, 1, 3, 3, 2, 2, 1),
    (2, 1, 2, 1, 1, 3, 3, 2), (2, 1, 3, 2, 2, 1, 1, 3),
    (2, 2, 1, 2, 3, 1, 3, 2), (2, 2, 2, 3, 1, 2, 1, 3),
    (2, 2, 3, 1, 2, 3, 2, 1), (2, 3, 1, 3, 2, 3, 1, 2),
    (2, 3, 2, 1, 3, 1, 2, 3), (2, 3, 3, 2, 1, 2, 3, 1),
)
_L25 = (
    (1, 1, 1, 1, 1, 1), (1, 2, 2, 2, 2, 2), (1, 3, 3, 3, 3, 3),
    (1, 4, 4, 4, 4, 4), (1, 5, 5, 5, 5, 5), (2, 1, 2, 3, 4, 5),
    (2, 2, 3, 4, 5, 1), (2, 3, 4, 5, 1, 2), (2, 4, 5, 1, 2, 3),
    (2, 5, 1, 2, 3, 4), (3, 1, 3, 5, 2, 4), (3, 2, 4, 1, 3, 5),
    (3, 3, 5, 2, 4, 1), (3, 4, 1, 3, 5, 2), (3, 5, 2, 4, 1, 3),
    (4, 1, 4, 2, 5, 3), (4, 2, 5, 3, 1, 4), (4, 3, 1, 4, 2, 5),
    (4, 4, 2, 5, 3, 1), (4, 5, 3, 1, 4, 2), (5, 1, 5, 4, 3, 2),
    (5, 2, 1, 5, 4, 3), (5, 3, 2, 1, 5, 4), (5, 4, 3, 2, 1, 5),
    (5, 5, 4, 3, 2, 1),
)


@dataclass(frozen=True)
class TaguchiArray:
    """一个已核验的固定数组；matrix 行序即官方标准序。"""

    array_id: str
    levels: tuple[int, ...]
    matrix: tuple[tuple[int, ...], ...]
    documented_unbalanced_pairs: tuple[tuple[int, int], ...] = ()

    def __post_init__(self):
        if not self.matrix or len(self.matrix) != self.run_count:
            raise ValueError("数组运行数无效")
        if any(len(row) != len(self.levels) for row in self.matrix):
            raise ValueError("数组列数与水平声明不一致")
        for column, count in enumerate(self.levels):
            values = {row[column] for row in self.matrix}
            if values != set(range(1, count + 1)):
                raise ValueError("数组列水平编码超出声明范围")

    @property
    def run_count(self):
        return len(self.matrix)

    @property
    def factor_capacity(self):
        return len(self.levels)

    @property
    def sha256(self):
        payload = {"array_id": self.array_id, "levels": list(self.levels),
                   "matrix": [list(row) for row in self.matrix]}
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"),
                             ensure_ascii=False).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def columns_for(self, level_count):
        """返回可容纳给定水平数的列号（1 起）。"""
        return tuple(index + 1 for index, value in enumerate(self.levels)
                     if value == level_count)


ARRAYS = {array.array_id: array for array in (
    TaguchiArray("L4(2^3)", (2, 2, 2), _L4),
    TaguchiArray("L8(2^7)", (2,) * 7, _L8),
    TaguchiArray("L9(3^4)", (3,) * 4, _L9),
    TaguchiArray("L16(4^5)", (4,) * 5, _L16),
    TaguchiArray("L18(2^1 3^7)", (2,) + (3,) * 7, _L18,
                 documented_unbalanced_pairs=((3, 8), (4, 8), (5, 8), (6, 8), (7, 8))),
    TaguchiArray("L25(5^6)", (5,) * 6, _L25),
)}
ARRAY_IDS = tuple(ARRAYS)


def get_array(array_id):
    try:
        return ARRAYS[array_id]
    except (KeyError, TypeError):
        raise ValueError(f"未知 Taguchi 数组：{array_id!r}") from None


def column_counts(array):
    """每列各水平出现次数，例如 {1: {1: 4, 2: 4}}。"""
    result = {}
    for column, count in enumerate(array.levels, 1):
        values = [row[column - 1] for row in array.matrix]
        result[column] = {level: values.count(level) for level in range(1, count + 1)}
    return result


def pair_counts(array, first, second):
    """两列水平组合频数；列号为 1 起。"""
    if not (1 <= first <= array.factor_capacity and 1 <= second <= array.factor_capacity):
        raise ValueError("列号超出数组范围")
    if first == second:
        raise ValueError("两列必须不同")
    result = {}
    for row in array.matrix:
        key = (row[first - 1], row[second - 1])
        result[key] = result.get(key, 0) + 1
    return result


def pair_is_balanced(array, first, second):
    counts = pair_counts(array, first, second)
    expected = array.run_count // (array.levels[first - 1] * array.levels[second - 1])
    return (len(counts) == array.levels[first - 1] * array.levels[second - 1]
            and set(counts.values()) == {expected})


def validate_independent_columns(array, columns, role):
    """Reject assigned column pairs whose observed combinations are not balanced."""
    assigned = sorted(columns.values())
    unbalanced = [pair for pair in combinations(assigned, 2)
                  if not pair_is_balanced(array, *pair)]
    if unbalanced:
        pairs = ", ".join(f"{first}/{second}" for first, second in unbalanced)
        raise ValueError(
            f"{array.array_id} 的{role}列组合 {pairs} 不满足两两正交，不能独立解释主效应")


def validate_array(array):
    """核验水平平衡与两两组合频数；返回审计字典。"""
    if not isinstance(array, TaguchiArray):
        raise ValueError("需要 TaguchiArray")
    balance = column_counts(array)
    for column, counts in balance.items():
        expected = array.run_count // array.levels[column - 1]
        if set(counts.values()) != {expected}:
            raise ValueError(f"{array.array_id} 第 {column} 列水平不平衡")
    unbalanced = []
    for first in range(1, array.factor_capacity + 1):
        for second in range(first + 1, array.factor_capacity + 1):
            if not pair_is_balanced(array, first, second):
                unbalanced.append((first, second))
    if tuple(unbalanced) != tuple(array.documented_unbalanced_pairs):
        raise ValueError(f"{array.array_id} 两两正交性与记录的构造事实不一致")
    return {"array_id": array.array_id, "run_count": array.run_count,
            "levels": list(array.levels), "balance": balance,
            "unbalanced_pairs": unbalanced, "sha256": array.sha256}
