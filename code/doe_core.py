"""版本化 DOE 数据合同与工作表映射；不生成设计矩阵或执行拟合/优化。"""
from __future__ import annotations

from dataclasses import dataclass, field
from fractions import Fraction
from itertools import product
import hashlib
import json
import math
from numbers import Integral, Real
import random
import re
from pathlib import PurePosixPath, PureWindowsPath
from types import MappingProxyType
from typing import Mapping

import pandas as pd


DOE_SCHEMA_VERSION = 5
_READ_VERSIONS = frozenset({1, 2, 3, 4, 5})
WORKSHEET_SCHEMA_VERSION = 1
_ID = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]{0,63}$")
_RUN_ID = re.compile(r"^[A-Za-z0-9_.-]{1,128}$")
_RELATION = re.compile(r"^[A-Za-z][A-Za-z0-9]*(?:=-?[A-Za-z][A-Za-z0-9]*)+$")
_DESIGN_TYPES = frozenset({
    "unspecified", "two_level_full", "two_level_fractional", "central_composite",
    "box_behnken", "plackett_burman", "definitive_screening",
    "general_full_factorial", "split_plot", "mixture",
    "custom_factorial", "custom_rsm", "custom_screening",
})
_SCREENING_TYPES = frozenset({"plackett_burman", "definitive_screening"})
_CUSTOM_TYPES = frozenset({"custom_factorial", "custom_rsm", "custom_screening"})
_SCREENING_POINTS = _SCREENING_TYPES | {"custom_screening"}
_SCREENING_SOURCES = {
    ("plackett_burman", f"pb{n}.v1", "publication", f"nist.pb{n}")
    for n in (12, 20, 24, 28, 36)
} | {
    ("plackett_burman", f"pb{n}.v1", "mathematical_construction", f"hadamard.pb{n}")
    for n in (32, 40, 44, 48)
} | {
    ("definitive_screening", f"dsd{n}.v1", "mathematical_construction", f"conference.dsd{n}")
    for n in range(2, 49)
} | {
    ("definitive_screening", f"dsd{n}c1.v1", "mathematical_construction", f"jones.dsd{n}c1")
    for n in range(1, 48)
} | {("definitive_screening", "dsd4c2.v1", "mathematical_construction", "foldover.dsd4c2")}
_POINT_TYPES = frozenset({"factorial", "center", "axial", "edge", "screening", "pseudo_center"})
_DESIGN_KEYS = {
    "schema_version", "design_id", "factors", "response_names", "seed",
    "generators", "defining_relations", "aliases", "ccd_alpha",
    "ccd_center_points", "ccd_axial_points", "design_type", "ccd_fraction",
    "block_count",
}
_DESIGN_KEYS_V1 = _DESIGN_KEYS - {"ccd_fraction", "block_count"}
_DESIGN_KEYS_V3 = _DESIGN_KEYS | {"screening_matrix"}
_DESIGN_KEYS_V4 = _DESIGN_KEYS_V3 | {
    "construction_version", "randomization_unit", "error_structure",
    "foldover_lineage", "center_point_count",
}
_DESIGN_KEYS_V5 = _DESIGN_KEYS_V4 | {
    "model_terms", "optimal_lineage", "augmentation_lineage",
}
_FACTOR_KEYS = {"schema_version", "factor_id", "name", "unit", "factor_type",
                "low", "high", "levels"}
_FACTOR_KEYS_V4 = _FACTOR_KEYS | {"level_type", "randomization_role"}
_MAP_KEYS = {
    "run_id", "standard_order", "run_order", "point_type", "replicate",
    "block", "factors", "measured_levels", "responses", "whole_plot_id",
    "subplot_id", "whole_plot_order", "subplot_order", "batch_id",
    "source_run_id",
}
_MAP_KEYS_V3 = _MAP_KEYS - {
    "whole_plot_id", "subplot_id", "whole_plot_order", "subplot_order",
    "batch_id", "source_run_id",
}
_META_KEYS = {"schema_version", "design", "column_map", "worksheet"}


def _text(value, field_name, *, identifier=False):
    if not isinstance(value, str) or not value or value != value.strip():
        raise ValueError(f"{field_name} 必须是非空且无首尾空格的字符串")
    if len(value) > 256 or any(ord(char) < 32 for char in value):
        raise ValueError(f"{field_name} 含非法字符或过长")
    if PurePosixPath(value).is_absolute() or PureWindowsPath(value).is_absolute():
        raise ValueError(f"{field_name} 不得包含绝对路径")
    if identifier and not _ID.fullmatch(value):
        raise ValueError(f"{field_name} 必须是稳定 ASCII 标识符")
    return value


def _number(value, field_name):
    if isinstance(value, bool):
        raise ValueError(f"{field_name} 必须是有限的整数或浮点数")
    if isinstance(value, Fraction):
        if value.denominator == 1:
            return value.numerator
        try:
            result = float(value)
        except (OverflowError, ValueError) as error:
            raise ValueError(f"{field_name} 超出支持范围") from error
        if math.isfinite(result) and Fraction.from_float(result) == value:
            return result
        raise ValueError(f"{field_name} 不能无损表示为整数或浮点数")
    if isinstance(value, Integral):
        return int(value)
    if isinstance(value, Real):
        try:
            result = float(value)
        except (OverflowError, TypeError, ValueError) as error:
            raise ValueError(f"{field_name} 超出支持范围") from error
        if not math.isfinite(result) or value != result:
            raise ValueError(f"{field_name} 必须是可精确表示的有限浮点数")
        return result
    raise ValueError(f"{field_name} 必须是有限的整数或浮点数")


def _fraction(value, field_name):
    if isinstance(value, bool):
        raise ValueError(f"{field_name} 必须是有限数值")
    if isinstance(value, Fraction):
        return value
    value = _number(value, field_name)
    return Fraction(value) if isinstance(value, int) else Fraction.from_float(value)


def _positive_int(value, field_name, *, minimum=1):
    if isinstance(value, bool) or not isinstance(value, Integral):
        raise ValueError(f"{field_name} 必须是整数")
    result = int(value)
    if result < minimum:
        raise ValueError(f"{field_name} 必须不小于 {minimum}")
    return result


def _run_id(value, field_name="run_id"):
    if isinstance(value, bool):
        raise ValueError(f"{field_name} 必须是字符串或整数")
    if isinstance(value, Integral):
        return int(value)
    if isinstance(value, str) and _RUN_ID.fullmatch(value):
        return value
    raise ValueError(f"{field_name} 必须是安全的字符串标识符或整数")


def _run_id_key(value):
    return (type(value), value)


def _column_label(value, field_name="列名"):
    if isinstance(value, bool):
        raise ValueError(f"{field_name} 必须是字符串、整数或有限浮点数")
    if isinstance(value, str):
        return _text(value, field_name)
    if isinstance(value, Integral):
        return int(value)
    if isinstance(value, Real):
        return _number(value, field_name)
    raise ValueError(f"{field_name} 必须是字符串、整数或有限浮点数")


def _label_key(value):
    value = _column_label(value)
    return (type(value).__name__, value)


def _string_tuple(values, field_name):
    if not isinstance(values, (tuple, list)):
        raise ValueError(f"{field_name} 必须是字符串列表")
    result = tuple(_text(item, field_name) for item in values)
    if len(set(result)) != len(result):
        raise ValueError(f"{field_name} 不得重复")
    return result


def _freeze_foldover_lineage(value):
    if value is None:
        return None
    keys = {"parent_design_id", "batch_id", "folded_factors", "run_map",
            "source_matrix_sha256", "current_matrix_sha256"}
    if not isinstance(value, Mapping) or set(value) != keys:
        raise ValueError("Foldover 谱系字段无效")
    parent = _text(value["parent_design_id"], "parent_design_id", identifier=True)
    batch = _text(value["batch_id"], "batch_id", identifier=True)
    factors = _string_tuple(value["folded_factors"], "folded_factors")
    pairs = value["run_map"]
    if not factors or not isinstance(pairs, (list, tuple)) or not pairs:
        raise ValueError("Foldover 谱系必须包含因子和运行映射")
    run_map, sources, additions = [], set(), set()
    for pair in pairs:
        if not isinstance(pair, (list, tuple)) or len(pair) != 2:
            raise ValueError("Foldover 运行映射必须是来源/新增 ID 对")
        source, addition = (_run_id(pair[0], "Foldover 来源 run_id"),
                            _run_id(pair[1], "Foldover 新 run_id"))
        source_key, addition_key = _run_id_key(source), _run_id_key(addition)
        if source_key == addition_key or source_key in sources or addition_key in additions:
            raise ValueError("Foldover 运行映射必须一一对应且 ID 不同")
        sources.add(source_key)
        additions.add(addition_key)
        run_map.append((source, addition))
    hashes = {}
    for key in ("source_matrix_sha256", "current_matrix_sha256"):
        digest = value[key]
        if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise ValueError(f"Foldover {key} 无效")
        hashes[key] = digest
    return MappingProxyType({"parent_design_id": parent, "batch_id": batch,
                             "folded_factors": factors, "run_map": tuple(run_map),
                             **hashes})


def _freeze_numeric_map(values, field_name, *, nullable=False, probability=False):
    if not isinstance(values, Mapping):
        raise ValueError(f"{field_name} 必须是映射")
    result = {}
    for key, value in values.items():
        key = _text(key, f"{field_name} 键")
        if value is None and nullable:
            result[key] = None
            continue
        number = _number(value, f"{field_name}[{key}]")
        if probability and not 0 <= number <= 1:
            raise ValueError(f"{field_name}[{key}] 必须在 0 到 1 之间")
        result[key] = number
    return MappingProxyType(result)


def _sha256_text(value, field_name):
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
        raise ValueError(f"{field_name} 必须是 SHA-256 十六进制摘要")
    return value


def _freeze_optimal_lineage(value):
    """D-optimal/distance 选点的父候选集、准则与选点顺序身份。"""
    if value is None:
        return None
    keys = {"parent_design_id", "criterion", "candidate_sha256",
            "selection_order", "batch_id"}
    if not isinstance(value, Mapping) or set(value) != keys:
        raise ValueError("最优设计谱系字段无效")
    criterion = value["criterion"]
    if criterion not in ("d_optimal", "distance"):
        raise ValueError("最优设计准则必须是 d_optimal 或 distance")
    order = value["selection_order"]
    if not isinstance(order, (list, tuple)) or not order:
        raise ValueError("最优设计谱系必须记录选点顺序")
    run_ids = [_run_id(item, "selection_order") for item in order]
    if len({_run_id_key(item) for item in run_ids}) != len(run_ids):
        raise ValueError("选点顺序中的 run_id 不得重复")
    return MappingProxyType({
        "parent_design_id": _text(value["parent_design_id"], "parent_design_id",
                                   identifier=True),
        "criterion": criterion,
        "candidate_sha256": _sha256_text(value["candidate_sha256"], "candidate_sha256"),
        "selection_order": tuple(run_ids),
        "batch_id": _text(value["batch_id"], "batch_id", identifier=True),
    })


def _freeze_augmentation_lineage(value):
    """通用增补谱系：父设计、批次、新增映射与前后矩阵摘要。"""
    if value is None:
        return None
    keys = {"parent_design_id", "batch_id", "criterion", "run_map",
            "source_matrix_sha256", "current_matrix_sha256"}
    if not isinstance(value, Mapping) or set(value) != keys:
        raise ValueError("增补谱系字段无效")
    criterion = value["criterion"]
    if criterion not in ("manual", "d_optimal", "distance"):
        raise ValueError("增补准则必须是 manual、d_optimal 或 distance")
    pairs = value["run_map"]
    if not isinstance(pairs, (list, tuple)) or not pairs:
        raise ValueError("增补谱系必须包含新增运行映射")
    run_map, additions = [], set()
    for pair in pairs:
        if not isinstance(pair, (list, tuple)) or len(pair) != 2:
            raise ValueError("增补映射必须是来源/新增 ID 对")
        source = None if pair[0] is None else _run_id(pair[0], "增补来源 run_id")
        addition = _run_id(pair[1], "增补新 run_id")
        key = _run_id_key(addition)
        if key in additions:
            raise ValueError("增补 run_id 不得重复")
        additions.add(key)
        run_map.append((source, addition))
    return MappingProxyType({
        "parent_design_id": _text(value["parent_design_id"], "parent_design_id",
                                   identifier=True),
        "batch_id": _text(value["batch_id"], "batch_id", identifier=True),
        "criterion": criterion,
        "run_map": tuple(run_map),
        "source_matrix_sha256": _sha256_text(value["source_matrix_sha256"],
                                              "source_matrix_sha256"),
        "current_matrix_sha256": _sha256_text(value["current_matrix_sha256"],
                                               "current_matrix_sha256"),
    })


def _freeze_settings(values, *, nullable=False):
    """保留数值或文本因子水平的原始类型。"""
    if not isinstance(values, Mapping):
        raise ValueError("设定水平必须是映射")
    result = {}
    for key, value in values.items():
        key = _text(key, "设定水平键")
        if value is None and nullable:
            result[key] = None
            continue
        if isinstance(value, str) and value == value.strip() and value:
            result[key] = _text(value, f"设定水平[{key}]")
        else:
            result[key] = _number(value, f"设定水平[{key}]")
    return MappingProxyType(result)


@dataclass(frozen=True)
class FactorSpec:
    """连续因子或有序分类水平的稳定定义。"""

    factor_id: str
    name: str
    low: int | float | None
    high: int | float | None
    unit: str | None = None
    factor_type: str = "continuous"
    levels: tuple[str | int | float, ...] = ()
    schema_version: int = DOE_SCHEMA_VERSION
    level_type: str | None = None
    randomization_role: str | None = None

    def __post_init__(self):
        _text(self.factor_id, "factor_id", identifier=True)
        _text(self.name, "因子名称")
        if self.unit is not None:
            _text(self.unit, "因子单位")
        if type(self.schema_version) is not int or self.schema_version not in _READ_VERSIONS:
            raise ValueError("未知因子 schema_version")
        if self.factor_type not in ("continuous", "categorical"):
            raise ValueError("factor_type 必须是 continuous 或 categorical")
        if self.schema_version < 4:
            if self.level_type is not None or self.randomization_role is not None:
                raise ValueError("分类标签类型与随机化角色只适用于 schema v4")
            levels = _string_tuple(self.levels, "分类因子水平")
        elif self.factor_type == "categorical":
            level_type = self.level_type
            raw_levels = tuple(self.levels) if isinstance(self.levels, (tuple, list)) else ()
            if level_type is None:
                level_type = ("text" if all(isinstance(value, str) for value in raw_levels)
                              else "numeric" if all(isinstance(value, Real) and not isinstance(value, bool)
                                                    for value in raw_levels)
                              else None)
            if level_type == "text":
                levels = _string_tuple(raw_levels, "分类因子水平")
            elif level_type == "numeric":
                levels = tuple(_number(value, "分类因子数值水平") for value in raw_levels)
                if len(set(levels)) != len(levels):
                    raise ValueError("分类因子水平不得重复")
            else:
                raise ValueError("分类因子 level_type 必须是 text 或 numeric")
            object.__setattr__(self, "level_type", level_type)
        else:
            levels = tuple(self.levels) if isinstance(self.levels, (tuple, list)) else ()
            if self.level_type is not None:
                raise ValueError("连续因子不得设置 level_type")
        object.__setattr__(self, "levels", levels)
        if self.factor_type == "categorical":
            if (self.low is not None or self.high is not None or len(levels) < 2
                    or self.schema_version < 4 and any(not isinstance(v, str) for v in levels)):
                raise ValueError("分类因子需有至少两个合法水平，且不得设置 low/high")
            if self.randomization_role not in (None, "hard_to_change", "easy_to_change"):
                raise ValueError("随机化角色必须是 hard_to_change 或 easy_to_change")
            return
        if levels or self.low is None or self.high is None:
            raise ValueError("连续因子必须提供实际 low/high，且不能提供分类水平")
        if self.randomization_role not in (None, "hard_to_change", "easy_to_change"):
            raise ValueError("随机化角色必须是 hard_to_change 或 easy_to_change")
        low = _number(self.low, "因子 low")
        high = _number(self.high, "因子 high")
        if _fraction(low, "因子 low") >= _fraction(high, "因子 high"):
            raise ValueError("因子 low 必须小于 high")
        object.__setattr__(self, "low", low)
        object.__setattr__(self, "high", high)

    def to_coded(self, actual):
        """精确编码范围内实际值；无法用 float 表示时返回 Fraction。"""
        if self.factor_type != "continuous":
            raise TypeError("分类因子没有 DOE-0 编码转换")
        value = _fraction(actual, "实际因子水平")
        low = _fraction(self.low, "因子 low")
        high = _fraction(self.high, "因子 high")
        if not low <= value <= high:
            raise ValueError("实际因子水平超出 low/high 范围")
        if value == low:
            return -1.0
        if value == high:
            return 1.0
        exact = 2 * (value - low) / (high - low) - 1
        coded = float(exact)
        if not math.isfinite(coded):
            raise ValueError("编码结果超出有限范围")
        return coded if Fraction.from_float(coded) == exact else exact

    def from_coded(self, coded):
        """将 [-1, +1] 编码值映射回实际水平；不可无损表示时返回 Fraction。"""
        if self.factor_type != "continuous":
            raise TypeError("分类因子没有 DOE-0 编码转换")
        value = _fraction(coded, "编码因子水平")
        if not -1 <= value <= 1:
            raise ValueError("编码因子水平必须在 -1 到 +1 之间")
        if value == -1:
            return self.low
        if value == 1:
            return self.high
        low = _fraction(self.low, "因子 low")
        high = _fraction(self.high, "因子 high")
        actual = low + (value + 1) * (high - low) / 2
        if actual.denominator == 1:
            return actual.numerator
        result = float(actual)
        if math.isfinite(result) and Fraction.from_float(result) == actual:
            return result
        if not math.isfinite(result):
            raise ValueError("实际水平超出有限范围")
        return actual

    def to_dict(self):
        result = {
            "schema_version": self.schema_version, "factor_id": self.factor_id,
            "name": self.name, "unit": self.unit, "factor_type": self.factor_type,
            "low": self.low, "high": self.high, "levels": list(self.levels),
        }
        if self.schema_version >= 4:
            result["level_type"] = self.level_type
            result["randomization_role"] = self.randomization_role
        return result

    @classmethod
    def from_dict(cls, data):
        if not isinstance(data, dict):
            raise ValueError("因子元数据字段无效")
        version = data.get("schema_version")
        keys = _FACTOR_KEYS_V4 if version >= 4 else _FACTOR_KEYS
        if (not isinstance(data, dict) or set(data) != keys
                or not isinstance(data["levels"], list)):
            raise ValueError("因子元数据字段无效")
        return cls(**{**data, "levels": tuple(data["levels"])})


@dataclass(frozen=True)
class DesignSpec:
    """版本化设计定义及其构造、随机化和误差结构身份。"""

    design_id: str
    factors: tuple[FactorSpec, ...]
    response_names: tuple[str, ...]
    seed: int | None = None
    schema_version: int = DOE_SCHEMA_VERSION
    generators: tuple[str, ...] = ()
    defining_relations: tuple[str, ...] = ()
    aliases: tuple[str, ...] = ()
    ccd_alpha: int | float | None = None
    ccd_center_points: int | None = None
    ccd_axial_points: int | None = None
    design_type: str = "unspecified"
    ccd_fraction: str | None = None
    block_count: int | None = None
    screening_matrix: Mapping | None = None
    construction_version: str = "v1"
    randomization_unit: str = "run"
    error_structure: str = "fixed"
    foldover_lineage: Mapping | None = None
    center_point_count: int | None = None
    model_terms: tuple[str, ...] = ()
    optimal_lineage: Mapping | None = None
    augmentation_lineage: Mapping | None = None

    def __post_init__(self):
        _text(self.design_id, "design_id", identifier=True)
        if type(self.schema_version) is not int or self.schema_version not in _READ_VERSIONS:
            raise ValueError("未知设计 schema_version")
        if not isinstance(self.design_type, str) or self.design_type not in _DESIGN_TYPES:
            raise ValueError("design_type 必须是受支持的 DOE 设计类型")
        factors = tuple(self.factors) if isinstance(self.factors, (tuple, list)) else ()
        if not factors or not all(isinstance(item, FactorSpec) for item in factors):
            raise ValueError("设计必须包含 FactorSpec")
        categorical_types = ("central_composite", "box_behnken", "plackett_burman",
                             "definitive_screening", "general_full_factorial",
                             "custom_factorial", "custom_rsm", "custom_screening")
        if self.design_type not in categorical_types:
            if any(item.factor_type != "continuous" for item in factors):
                raise NotImplementedError("分类或混合水平设计仅用于中心复合或 Box-Behnken")
        if self.design_type == "general_full_factorial" and any(
                item.factor_type != "categorical" for item in factors):
            raise ValueError("General Full Factorial 的所有因子必须是分类因子")
        if self.design_type in _CUSTOM_TYPES and self.schema_version < 5:
            raise ValueError("自定义设计需要 schema v5")
        if self.design_type == "custom_factorial" and any(
                item.factor_type == "categorical" and len(item.levels) != 2
                for item in factors):
            raise ValueError("自定义两水平因子设计只接受两水平分类因子")
        if self.design_type == "custom_screening" and any(
                item.factor_type == "categorical" and len(item.levels) != 2
                for item in factors):
            raise ValueError("自定义筛选设计只接受两水平分类因子")
        ids = [item.factor_id for item in factors]
        names = [item.name for item in factors]
        if len(set(ids)) != len(ids):
            raise ValueError("factor_id 不得重复")
        if len(set(names)) != len(names):
            raise ValueError("因子展示名称不得重复")
        object.__setattr__(self, "factors", factors)
        responses = _string_tuple(self.response_names, "响应名称")
        if not responses:
            raise ValueError("设计至少需要一个响应名称")
        object.__setattr__(self, "response_names", responses)
        if self.seed is not None:
            if isinstance(self.seed, bool) or not isinstance(self.seed, Integral):
                raise ValueError("随机化 seed 必须是整数或 None")
            object.__setattr__(self, "seed", int(self.seed))
        for key in ("generators", "defining_relations", "aliases"):
            relations = _string_tuple(getattr(self, key), key)
            if any(not _RELATION.fullmatch(item) for item in relations):
                raise ValueError(f"{key} 必须使用受控关系格式，例如 D=AB")
            object.__setattr__(self, key, relations)
        if self.ccd_alpha is not None:
            alpha = _number(self.ccd_alpha, "CCD alpha")
            if alpha <= 0:
                raise ValueError("CCD alpha 必须大于 0")
            object.__setattr__(self, "ccd_alpha", alpha)
        for key in ("ccd_center_points", "ccd_axial_points"):
            value = getattr(self, key)
            if value is not None:
                object.__setattr__(self, key, _positive_int(value, key, minimum=0))
        if self.ccd_fraction is not None:
            if self.ccd_fraction not in ("full", "half", "quarter", "eighth"):
                raise ValueError("ccd_fraction 必须是 full、half、quarter 或 eighth")
            if self.schema_version < 2 or self.design_type != "central_composite":
                raise ValueError("ccd_fraction 只适用于 schema v2 的中心复合设计")
        if self.block_count is not None:
            object.__setattr__(self, "block_count",
                               _positive_int(self.block_count, "block_count", minimum=1))
        if self.center_point_count is not None:
            if self.schema_version < 4 or self.design_type != "two_level_fractional":
                raise ValueError("center_point_count 只适用于 schema v4 正规部分因子设计")
            object.__setattr__(self, "center_point_count",
                               _positive_int(self.center_point_count, "center_point_count", minimum=0))
        if self.schema_version < 2:
            if self.block_count is not None:
                raise ValueError("block_count 只适用于 schema v2")
            if self.design_type == "box_behnken":
                raise ValueError("box_behnken 只适用于 schema v2")
            if any(item.factor_type == "categorical" for item in factors):
                raise ValueError("schema v1 不支持分类因子")
        if self.schema_version < 4:
            if (self.construction_version != "v1" or self.randomization_unit != "run"
                    or self.error_structure != "fixed" or self.foldover_lineage is not None
                    or self.center_point_count is not None
                    or self.model_terms or self.optimal_lineage is not None
                    or self.augmentation_lineage is not None
                    or any(item.randomization_role is not None for item in factors)
                    or any(item.factor_type == "categorical" and item.level_type == "numeric"
                           for item in factors)):
                raise ValueError("新设计身份字段只适用于 schema v4")
        else:
            construction = _text(self.construction_version, "construction_version", identifier=True)
            if not re.fullmatch(r"v[1-9][0-9]*", construction):
                raise ValueError("construction_version 必须使用 vN 格式")
            object.__setattr__(self, "construction_version", construction)
            if self.randomization_unit not in ("run", "block", "whole_plot"):
                raise ValueError("randomization_unit 无效")
            if self.error_structure not in ("fixed", "split_plot"):
                raise ValueError("error_structure 无效")
            if self.design_type == "split_plot":
                roles = [factor.randomization_role for factor in factors]
                if (self.randomization_unit != "whole_plot"
                        or self.error_structure != "split_plot"
                        or roles.count("hard_to_change") != 1
                        or roles.count("easy_to_change") < 1
                        or any(factor.factor_type != "continuous" for factor in factors)):
                    raise ValueError("Split-Plot 需一个 hard-to-change 和至少一个 easy-to-change 连续因子")
            elif (self.randomization_unit == "whole_plot" or self.error_structure == "split_plot"
                  or any(factor.randomization_role is not None for factor in factors)):
                raise ValueError("只有 Split-Plot 才能声明裂区随机化角色或误差层")
            lineage = _freeze_foldover_lineage(self.foldover_lineage)
            if lineage is not None and self.design_type != "two_level_fractional":
                raise ValueError("当前 Foldover 谱系只支持正规两水平部分因子")
            if lineage is not None and any(factor.factor_type != "continuous" for factor in factors):
                raise ValueError("正规部分因子 Foldover 不支持分类因子")
            if lineage is not None and (
                    lineage["parent_design_id"] == self.design_id
                    or not set(lineage["folded_factors"]) <= set(ids)
                    or len(lineage["folded_factors"]) not in (1, len(ids))):
                raise ValueError("Foldover 因子或父设计身份无效")
            object.__setattr__(self, "foldover_lineage", lineage)
        if self.design_type == "split_plot" and self.schema_version < 4:
            raise ValueError("Split-Plot 需要 schema v4")
        if self.design_type in _SCREENING_TYPES:
            if self.schema_version < 3 or not isinstance(self.screening_matrix, Mapping):
                raise ValueError("筛选设计需要 schema v3 和矩阵身份")
            identity = dict(self.screening_matrix)
            if set(identity) != {"construction_id", "source_kind", "source_id", "matrix_sha256"}:
                raise ValueError("筛选矩阵身份字段无效")
            _text(identity["construction_id"], "construction_id", identifier=True)
            _text(identity["source_id"], "source_id", identifier=True)
            if identity["source_kind"] not in ("mathematical_construction", "publication", "minitab_export"):
                raise ValueError("筛选矩阵来源类型无效")
            if (self.design_type, identity["construction_id"], identity["source_kind"],
                    identity["source_id"]) not in _SCREENING_SOURCES:
                raise ValueError("未知筛选矩阵构造或来源")
            if not isinstance(identity["matrix_sha256"], str) or not re.fullmatch(r"[0-9a-f]{64}", identity["matrix_sha256"]):
                raise ValueError("筛选矩阵摘要无效")
            object.__setattr__(self, "screening_matrix", MappingProxyType(identity))
        elif self.screening_matrix is not None:
            raise ValueError("非筛选设计不得声明筛选矩阵身份")
        if self.schema_version < 5:
            if (self.model_terms or self.optimal_lineage is not None
                    or self.augmentation_lineage is not None):
                raise ValueError("模型项与最优/增补谱系只适用于 schema v5")
        else:
            terms = _string_tuple(self.model_terms, "model_terms")
            object.__setattr__(self, "model_terms", terms)
            if terms and self.design_type not in (
                    "custom_rsm", "custom_factorial", "custom_screening"):
                raise ValueError("model_terms 只适用于自定义设计")
            optimal = _freeze_optimal_lineage(self.optimal_lineage)
            augmentation = _freeze_augmentation_lineage(self.augmentation_lineage)
            if optimal is not None and augmentation is not None:
                raise ValueError("最优选点谱系与增补谱系不能同时存在")
            for name, lineage in (("optimal", optimal), ("augmentation", augmentation)):
                if lineage is not None and lineage["parent_design_id"] == self.design_id:
                    raise ValueError(f"{name} 父设计不能与当前设计相同")
            if optimal is not None and self.design_type not in (
                    "custom_factorial", "custom_rsm", "general_full_factorial"):
                raise ValueError("最优设计谱系只适用于自定义/一般全因子设计")
            object.__setattr__(self, "optimal_lineage", optimal)
            object.__setattr__(self, "augmentation_lineage", augmentation)

    def to_dict(self):
        result = {
            "schema_version": self.schema_version, "design_id": self.design_id,
            "factors": [],
            "response_names": list(self.response_names), "seed": self.seed,
            "generators": list(self.generators),
            "defining_relations": list(self.defining_relations),
            "aliases": list(self.aliases), "ccd_alpha": self.ccd_alpha,
            "ccd_center_points": self.ccd_center_points,
            "ccd_axial_points": self.ccd_axial_points,
            "design_type": self.design_type,
            "ccd_fraction": self.ccd_fraction, "block_count": self.block_count,
        }
        for factor in self.factors:
            item = factor.to_dict()
            item["schema_version"] = self.schema_version
            if self.schema_version < 4:
                item.pop("level_type", None)
                item.pop("randomization_role", None)
            result["factors"].append(item)
        if self.schema_version >= 3:
            result["screening_matrix"] = (dict(self.screening_matrix)
                                          if self.screening_matrix is not None else None)
        if self.schema_version >= 4:
            result.update({
                "construction_version": self.construction_version,
                "randomization_unit": self.randomization_unit,
                "error_structure": self.error_structure,
                "foldover_lineage": (None if self.foldover_lineage is None else {
                    "parent_design_id": self.foldover_lineage["parent_design_id"],
                    "batch_id": self.foldover_lineage["batch_id"],
                    "folded_factors": list(self.foldover_lineage["folded_factors"]),
                    "run_map": [list(pair) for pair in self.foldover_lineage["run_map"]],
                    "source_matrix_sha256": self.foldover_lineage["source_matrix_sha256"],
                    "current_matrix_sha256": self.foldover_lineage["current_matrix_sha256"],
                }),
                "center_point_count": self.center_point_count,
            })
        if self.schema_version >= 5:
            result.update({
                "model_terms": list(self.model_terms),
                "optimal_lineage": (None if self.optimal_lineage is None else {
                    "parent_design_id": self.optimal_lineage["parent_design_id"],
                    "criterion": self.optimal_lineage["criterion"],
                    "candidate_sha256": self.optimal_lineage["candidate_sha256"],
                    "selection_order": list(self.optimal_lineage["selection_order"]),
                    "batch_id": self.optimal_lineage["batch_id"],
                }),
                "augmentation_lineage": (
                    None if self.augmentation_lineage is None else {
                        "parent_design_id": self.augmentation_lineage["parent_design_id"],
                        "batch_id": self.augmentation_lineage["batch_id"],
                        "criterion": self.augmentation_lineage["criterion"],
                        "run_map": [list(pair) for pair in
                                    self.augmentation_lineage["run_map"]],
                        "source_matrix_sha256":
                            self.augmentation_lineage["source_matrix_sha256"],
                        "current_matrix_sha256":
                            self.augmentation_lineage["current_matrix_sha256"],
                    }),
            })
        return result

    @classmethod
    def from_dict(cls, data):
        if not isinstance(data, dict):
            raise ValueError("设计元数据字段无效")
        if "design_type" not in data:
            raise ValueError("设计元数据缺少 design_type")
        version = data.get("schema_version")
        if type(version) is not int or version not in _READ_VERSIONS:
            raise ValueError(f"未知 DOE schema_version: {version!r}")
        keys = {1: _DESIGN_KEYS_V1, 2: _DESIGN_KEYS, 3: _DESIGN_KEYS_V3,
                4: _DESIGN_KEYS_V4, 5: _DESIGN_KEYS_V5}[version]
        if set(data) != keys:
            raise ValueError("设计元数据字段无效")
        missing = object()
        fraction = data.get("ccd_fraction", missing)
        blocks = data.get("block_count", missing)
        if any(not isinstance(data[key], list) for key in (
                "factors", "response_names", "generators",
                "defining_relations", "aliases")):
            raise ValueError("设计列表字段结构无效")
        if any(not isinstance(item, dict) or item.get("schema_version") != version
               for item in data["factors"]):
            raise ValueError("因子与设计 schema_version 不一致")
        result = cls(
            design_id=data["design_id"],
            factors=tuple(FactorSpec.from_dict(item) for item in data["factors"]),
            response_names=tuple(data["response_names"]),
            seed=data["seed"], schema_version=version,
            generators=tuple(data["generators"]),
            defining_relations=tuple(data["defining_relations"]),
            aliases=tuple(data["aliases"]), ccd_alpha=data["ccd_alpha"],
            ccd_center_points=data["ccd_center_points"],
            ccd_axial_points=data["ccd_axial_points"],
            design_type=data["design_type"],
            ccd_fraction=None if fraction is missing else fraction,
            block_count=None if blocks is missing else blocks,
            screening_matrix=data.get("screening_matrix"),
            construction_version=data.get("construction_version", "v1"),
            randomization_unit=data.get("randomization_unit", "run"),
            error_structure=data.get("error_structure", "fixed"),
            foldover_lineage=data.get("foldover_lineage"),
            center_point_count=data.get("center_point_count"),
            model_terms=tuple(data.get("model_terms") or ()),
            optimal_lineage=data.get("optimal_lineage"),
            augmentation_lineage=data.get("augmentation_lineage"),
        )
        from dataclasses import replace
        return replace(result,
                       factors=tuple(replace(factor, schema_version=DOE_SCHEMA_VERSION)
                                     for factor in result.factors),
                       schema_version=DOE_SCHEMA_VERSION)


@dataclass(frozen=True)
class RunRecord:
    """一行实验记录；设定水平、实测水平和响应值分别保存。"""

    run_id: str | int
    standard_order: int
    run_order: int
    point_type: str
    settings: Mapping[str, str | int | float]
    replicate: int = 1
    block: str | int | None = None
    measured_levels: Mapping[str, str | int | float | None] = field(default_factory=dict)
    responses: Mapping[str, int | float | None] = field(default_factory=dict)
    schema_version: int = DOE_SCHEMA_VERSION
    whole_plot_id: str | None = None
    subplot_id: str | None = None
    whole_plot_order: int | None = None
    subplot_order: int | None = None
    batch_id: str | None = None
    source_run_id: str | int | None = None

    def __post_init__(self):
        version = self.schema_version
        if type(version) is not int or version not in _READ_VERSIONS:
            raise ValueError("未知运行记录 schema_version")
        object.__setattr__(self, "schema_version", DOE_SCHEMA_VERSION)
        object.__setattr__(self, "run_id", _run_id(self.run_id))
        object.__setattr__(self, "standard_order",
                           _positive_int(self.standard_order, "standard_order"))
        object.__setattr__(self, "run_order",
                           _positive_int(self.run_order, "run_order"))
        object.__setattr__(self, "replicate", _positive_int(self.replicate, "replicate"))
        if self.point_type not in _POINT_TYPES:
            raise ValueError("point_type 必须是 factorial、center、axial 或 edge")
        if self.block is not None:
            if isinstance(self.block, Integral) and not isinstance(self.block, bool):
                object.__setattr__(self, "block", int(self.block))
            elif isinstance(self.block, str) and _RUN_ID.fullmatch(self.block):
                pass
            else:
                raise ValueError("block 必须是安全字符串、整数或 None")
        if version < 4 and any(value is not None for value in (
                self.whole_plot_id, self.subplot_id, self.whole_plot_order,
                self.subplot_order, self.batch_id, self.source_run_id)):
            raise ValueError("裂区与 Foldover 运行字段只适用于 schema v4")
        for key in ("whole_plot_id", "subplot_id", "batch_id"):
            value = getattr(self, key)
            if value is not None:
                object.__setattr__(self, key, _text(value, key, identifier=True))
        for key in ("whole_plot_order", "subplot_order"):
            value = getattr(self, key)
            if value is not None:
                object.__setattr__(self, key, _positive_int(value, key))
        if self.source_run_id is not None:
            object.__setattr__(self, "source_run_id", _run_id(self.source_run_id, "source_run_id"))
        object.__setattr__(self, "settings", _freeze_settings(self.settings))
        object.__setattr__(self, "measured_levels",
                           _freeze_settings(self.measured_levels, nullable=True))
        object.__setattr__(self, "responses",
                           _freeze_numeric_map(self.responses, "响应值", nullable=True))


@dataclass(frozen=True)
class DesignResult:
    """按工作表行顺序保存的运行记录，顺序字段仍独立表示标准/实际顺序。"""

    spec: DesignSpec
    runs: tuple[RunRecord, ...]
    schema_version: int = DOE_SCHEMA_VERSION

    def __post_init__(self):
        if type(self.schema_version) is not int or self.schema_version not in _READ_VERSIONS:
            raise ValueError("未知设计结果 schema_version")
        object.__setattr__(self, "schema_version", DOE_SCHEMA_VERSION)
        if not isinstance(self.spec, DesignSpec):
            raise ValueError("DesignResult.spec 必须是 DesignSpec")
        runs = tuple(self.runs) if isinstance(self.runs, (tuple, list)) else ()
        if not runs or not all(isinstance(run, RunRecord) for run in runs):
            raise ValueError("DesignResult 必须包含 RunRecord")
        run_ids = [_run_id_key(run.run_id) for run in runs]
        if len(set(run_ids)) != len(run_ids):
            raise ValueError("run_id 必须唯一")
        expected_order = set(range(1, len(runs) + 1))
        if {run.standard_order for run in runs} != expected_order:
            raise ValueError("standard_order 必须是 1 到运行数的排列")
        if {run.run_order for run in runs} != expected_order:
            raise ValueError("run_order 必须是 1 到运行数的排列")
        factor_ids = {factor.factor_id for factor in self.spec.factors}
        response_names = set(self.spec.response_names)
        for run in runs:
            if self.spec.design_type not in _SCREENING_POINTS and run.point_type in ("screening", "pseudo_center"):
                raise ValueError("筛选点类型只适用于筛选设计")
            if set(run.settings) != factor_ids:
                raise ValueError("每个运行的设定水平必须覆盖全部因子")
            if not set(run.measured_levels) <= factor_ids:
                raise ValueError("实测水平包含未知因子")
            for factor in self.spec.factors:
                if factor.factor_id in run.measured_levels:
                    value = run.measured_levels[factor.factor_id]
                    if value is not None and _factor_level(
                            value, factor, f"因子 {factor.factor_id} 实测水平") != value:
                        raise ValueError("实测水平与因子类型不一致")
            if set(run.responses) != response_names:
                raise ValueError("每个运行的响应字段必须与设计定义一致")
            if run.point_type != "axial":
                for factor in self.spec.factors:
                    value = run.settings[factor.factor_id]
                    if factor.factor_type == "categorical":
                        if value not in factor.levels:
                            raise ValueError("分类因子设定不在已声明的水平内")
                    elif run.point_type == "axial":
                        # 轴点位于 low/high 之外；范围与距离由设计模块核验。
                        _number(value, "设定水平")
                    else:
                        factor.to_coded(value)
        if self.spec.design_type in ("two_level_full", "two_level_fractional",
                                     "general_full_factorial", "split_plot",
                                     "custom_factorial"):
            if self.spec.block_count is not None:
                blocks = {run.block for run in runs}
                if None in blocks or len(blocks) != self.spec.block_count:
                    raise ValueError("实际区组数量与设计声明不一致")
        if self.spec.design_type == "split_plot":
            hard = [f for f in self.spec.factors if f.randomization_role == "hard_to_change"]
            easy = [f for f in self.spec.factors if f.randomization_role == "easy_to_change"]
            whole_plots = {}
            for run in runs:
                if (run.block is None or run.whole_plot_id is None or run.subplot_id is None
                        or run.whole_plot_order is None or run.subplot_order is None):
                    raise ValueError("每个裂区运行都必须保留 block/whole-plot/subplot 身份和顺序")
                whole_plots.setdefault(run.whole_plot_id, []).append(run)
            if not whole_plots:
                raise ValueError("Split-Plot 缺少 whole plots")
            block_orders, subplot_ids = {}, {}
            for whole_plot_id, group in whole_plots.items():
                blocks = {run.block for run in group}
                orders = {run.whole_plot_order for run in group}
                if len(blocks) != 1 or len(orders) != 1:
                    raise ValueError("whole plot 不得跨区组或有多个顺序")
                block = next(iter(blocks))
                order = next(iter(orders))
                block_orders.setdefault(block, {})[order] = whole_plot_id
                if any(any(run.settings[f.factor_id] != group[0].settings[f.factor_id]
                           for f in hard) for run in group):
                    raise ValueError("同一 whole plot 内 hard-to-change 因子水平必须固定")
                if len(group) != 1 << len(easy):
                    raise ValueError("每个 whole plot 必须包含完整 easy-to-change 全因子组合")
                expected_subplots = set(product((-1, 1), repeat=len(easy)))
                observed_subplots, local_orders = set(), set()
                for run in group:
                    coded = tuple(next(f for f in easy if f.factor_id == factor_id).to_coded(
                        run.settings[factor_id]) for factor_id in [f.factor_id for f in easy])
                    if coded in observed_subplots:
                        raise ValueError("whole plot 内 subplot 因子组合不得重复")
                    observed_subplots.add(coded)
                    local_orders.add(run.subplot_order)
                if observed_subplots != expected_subplots or local_orders != set(range(1, len(group)+1)):
                    raise ValueError("whole plot 的 subplot 组合或顺序不完整")
                sorted_runs = sorted(group, key=lambda run: run.subplot_order)
                if [run.run_order for run in sorted_runs] != list(range(
                        sorted_runs[0].run_order, sorted_runs[0].run_order + len(group))):
                    raise ValueError("同一 whole plot 的 subplot 运行必须连续")
                subplot_ids[whole_plot_id] = {run.subplot_id for run in group}
            for block, orders in block_orders.items():
                if set(orders) != set(range(1, len(orders)+1)):
                    raise ValueError("区组内 whole-plot 顺序必须连续")
            expected_hard = set(product((-1, 1), repeat=len(hard)))
            for block in block_orders:
                observed_hard = {
                    tuple(f.to_coded(whole_plots[whole_plot_id][0].settings[f.factor_id])
                          for f in hard)
                    for whole_plot_id in block_orders[block].values()
                }
                if observed_hard != expected_hard:
                    raise ValueError("每个区组都必须包含全部 hard-to-change 组合")
            by_order = sorted(runs, key=lambda run: run.run_order)
            current_block, current_wp = None, None
            seen_blocks, seen_whole_plots = [], []
            for run in by_order:
                if run.block != current_block:
                    if run.block in seen_blocks:
                        raise ValueError("区组内运行必须连续")
                    seen_blocks.append(run.block)
                    current_block, current_wp = run.block, None
                if run.whole_plot_id != current_wp:
                    if run.whole_plot_id in seen_whole_plots:
                        raise ValueError("whole plot 运行必须连续")
                    seen_whole_plots.append(run.whole_plot_id)
                    current_wp = run.whole_plot_id
        if self.spec.design_type in _CUSTOM_TYPES:
            # 自定义设计的点集与模型项由 doe_custom 按实际矩阵核验。
            pass
        elif self.spec.design_type == "box_behnken":
            expected_centers = self.spec.ccd_center_points
            if expected_centers is not None:
                expected_centers *= (len({run.replicate for run in runs}) *
                                     len(category_combinations(self.spec.factors)))
            if (expected_centers is not None
                    and expected_centers != sum(run.point_type == "center"
                                                for run in runs)):
                raise ValueError("Box-Behnken 中心点数与运行记录不一致")
        else:
            axial_count = sum(run.point_type == "axial" for run in runs)
            center_count = sum(run.point_type == "center" for run in runs)
            # 扩展 CCD（分数/区组/分类）由 validate_ccd 统一核验。
            extended = (self.spec.design_type == "central_composite"
                        and (self.spec.ccd_fraction is not None
                             or self.spec.block_count is not None
                             or any(f.factor_type == "categorical"
                                    for f in self.spec.factors)))
            if axial_count and (
                    self.spec.ccd_alpha is None
                    or self.spec.ccd_axial_points != axial_count) and not extended:
                raise ValueError("轴点记录必须匹配已声明的 CCD alpha 和轴点数")
            if not axial_count and self.spec.ccd_axial_points not in (None, 0):
                raise ValueError("CCD 轴点数与运行记录不一致")
            if (self.spec.ccd_center_points is not None
                    and self.spec.ccd_center_points != center_count and not extended):
                raise ValueError("CCD 中心点数与运行记录不一致")
        object.__setattr__(self, "runs", runs)


def _screening_level(factor, value):
    if factor.factor_type == 'categorical':
        if len(factor.levels) != 2 or value not in factor.levels:
            raise ValueError('筛选分类因子必须恰有两个水平')
        return -1 if value == factor.levels[0] else 1
    if value == factor.low:
        return -1
    if value == factor.high:
        return 1
    from doe_ccd import _center_level
    if value == _center_level(factor):
        return 0
    raise ValueError('筛选因子必须位于低、中或高水平')


def screening_matrix_sha256(result):
    """按标准序计算筛选设计身份，不包含响应和随机运行序。"""
    factors = result.spec.factors
    rows = []
    for run in sorted(result.runs, key=lambda item: item.standard_order):
        levels = []
        for factor in factors:
            value = run.settings[factor.factor_id]
            levels.append(_screening_level(factor, value))
        rows.append({"levels": levels, "point_type": run.point_type,
                     "replicate": run.replicate, "block": run.block})
    payload = {"design_type": result.spec.design_type,
               "factors": [factor.factor_id for factor in factors], "runs": rows}
    encoded = json.dumps(payload, ensure_ascii=False, allow_nan=False,
                         sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _validate_screening_construction(result):
    """逐标准序核对已固定构造，不能只相信可重新计算的摘要。"""
    from doe_screening_matrices import MATRICES

    spec = result.spec
    key = spec.screening_matrix['construction_id'].removesuffix('.v1')
    matrix = MATRICES[key]
    factor_count = len(spec.factors)
    if spec.design_type == 'plackett_burman':
        if not 2 <= factor_count <= len(matrix[0]):
            raise ValueError('PB 因子数与构造不匹配')
    elif key.endswith(('c1', 'c2')):
        categorical_count = 2 if key.endswith('c2') else 1
        if (factor_count != len(matrix[0]) or
                [f.factor_type for f in spec.factors] != ['continuous'] * (factor_count - categorical_count) + ['categorical'] * categorical_count):
            raise ValueError('混合 DSD 的连续及分类因子与构造不匹配')
    elif factor_count != len(matrix[0]) or any(f.factor_type != 'continuous' for f in spec.factors):
        raise ValueError('DSD 因子数或类型与构造不匹配')
    if (spec.generators or spec.defining_relations or spec.aliases
            or any(value is not None for value in (spec.ccd_alpha, spec.ccd_center_points,
                                                    spec.ccd_axial_points, spec.ccd_fraction))):
        raise ValueError('筛选设计包含不支持的设计选项')
    runs = sorted(result.runs, key=lambda run: run.standard_order)
    size = len(matrix)
    if spec.design_type == 'plackett_burman':
        repetitions = {run.replicate for run in runs}
        count = len(repetitions)
        if repetitions != set(range(1, count + 1)) or len(runs) > 10000 or len(runs) % count:
            raise ValueError('PB 重复或运行数与构造不匹配')
        per_rep = len(runs) // count
        if per_rep < size or (spec.block_count is not None and spec.block_count != count):
            raise ValueError('PB 中心点或区组数与构造不匹配')
        categorical = [f for f in spec.factors if f.factor_type == 'categorical']
        combinations_count = 1 << len(categorical)
        center_total = per_rep - size
        if center_total and (center_total % combinations_count or len(categorical) == factor_count):
            raise ValueError('PB 伪中心组合或中心点数与构造不匹配')
        center_combinations = list(product((-1, 1), repeat=len(categorical))) if center_total else []
        for index, run in enumerate(runs):
            rep, position = divmod(index, per_rep)
            center = position >= size
            if center:
                category_levels = iter(center_combinations[(position - size) % combinations_count])
                expected = tuple(next(category_levels) if f.factor_type == 'categorical' else 0 for f in spec.factors)
            else:
                expected = matrix[position][:factor_count]
            if (run.replicate != rep + 1 or run.block != (rep + 1 if spec.block_count is not None else None)
                    or run.point_type != ('pseudo_center' if center and categorical else 'center' if center else 'factorial')):
                raise ValueError('PB 重复、区组或点类型与构造不匹配')
            for factor, value in zip(spec.factors, expected):
                if _screening_level(factor, run.settings[factor.factor_id]) != value:
                    raise ValueError('PB 设定与构造矩阵不匹配')
        return
    if len(runs) > 10000 or len(runs) % size:
        raise ValueError('筛选设计运行数与构造不匹配')
    repetitions = len(runs) // size
    blocks = spec.block_count or 1
    if blocks > repetitions or repetitions % blocks:
        raise ValueError('DSD 区组必须均分完整重复')
    for index, run in enumerate(runs):
        base = matrix[index % size][:factor_count]
        expected_type = ('factorial' if spec.design_type == 'plackett_burman' else
                         'pseudo_center' if key.endswith(('c1', 'c2')) and index % size >= size - 2 else
                         'center' if not key.endswith(('c1', 'c2')) and index % size == size - 1 else 'screening')
        expected_block = (index // size) // (repetitions // blocks) + 1 if blocks > 1 else None
        if run.replicate != index // size + 1 or run.block != expected_block or run.point_type != expected_type:
            raise ValueError('筛选设计重复、区组或点类型与构造不匹配')
        for factor, expected in zip(spec.factors, base):
            value = run.settings[factor.factor_id]
            actual = _screening_level(factor, value)
            if actual != expected:
                raise ValueError('筛选设计设定与构造矩阵不匹配')


@dataclass(frozen=True)
class ModelResult:
    """拟合结果合同；DOE-0 不拟合，饱和模型禁止携带推断统计量。"""

    design_id: str
    response_name: str
    coefficients: Mapping[str, int | float]
    residual_df: int
    independent_error_df: int | None = None
    saturated: bool = False
    inference_status: str = "not_evaluated"
    term_t_statistics: Mapping[str, int | float | None] = field(default_factory=dict)
    term_p_values: Mapping[str, int | float | None] = field(default_factory=dict)
    f_statistic: int | float | None = None
    model_p_value: int | float | None = None
    schema_version: int = DOE_SCHEMA_VERSION

    def __post_init__(self):
        if type(self.schema_version) is not int or self.schema_version not in _READ_VERSIONS:
            raise ValueError("未知模型结果 schema_version")
        object.__setattr__(self, "schema_version", DOE_SCHEMA_VERSION)
        _text(self.design_id, "design_id", identifier=True)
        _text(self.response_name, "响应名称")
        if not isinstance(self.coefficients, Mapping):
            raise ValueError("系数必须是映射")
        coefficients = _freeze_numeric_map(self.coefficients, "系数")
        object.__setattr__(self, "coefficients", coefficients)
        residual_df = _positive_int(self.residual_df, "residual_df", minimum=0)
        object.__setattr__(self, "residual_df", residual_df)
        if self.independent_error_df is not None:
            object.__setattr__(
                self, "independent_error_df",
                _positive_int(self.independent_error_df, "independent_error_df", minimum=0))
        if type(self.saturated) is not bool or self.saturated != (residual_df == 0):
            raise ValueError("saturated 必须与 residual_df == 0 一致")
        if self.inference_status not in (
                "not_evaluated", "evaluated", "unavailable_saturated"):
            raise ValueError("未知推断状态")
        t_values = _freeze_numeric_map(self.term_t_statistics, "t 统计量", nullable=True)
        p_values = _freeze_numeric_map(self.term_p_values, "p 值",
                                       nullable=True, probability=True)
        f_value = None if self.f_statistic is None else _number(self.f_statistic, "F 统计量")
        model_p = None if self.model_p_value is None else _number(self.model_p_value, "模型 p 值")
        if f_value is not None and f_value < 0:
            raise ValueError("F 统计量不能小于 0")
        if model_p is not None and not 0 <= model_p <= 1:
            raise ValueError("模型 p 值必须在 0 到 1 之间")
        if self.saturated:
            if (self.inference_status != "unavailable_saturated" or t_values
                    or p_values or f_value is not None or model_p is not None):
                raise ValueError("residual_df 为 0 时不得提供 t/p/F 推断值")
        elif self.inference_status == "unavailable_saturated":
            raise ValueError("非饱和模型不能标为饱和推断不可用")
        if self.inference_status == "not_evaluated" and (
                t_values or p_values or f_value is not None or model_p is not None):
            raise ValueError("not_evaluated 状态不得携带推断统计量")
        object.__setattr__(self, "term_t_statistics", t_values)
        object.__setattr__(self, "term_p_values", p_values)
        object.__setattr__(self, "f_statistic", f_value)
        object.__setattr__(self, "model_p_value", model_p)


@dataclass(frozen=True)
class OptimizationResult:
    """优化结果的只读输出合同；DOE-0 不搜索、评分或推荐条件。"""

    design_id: str
    factor_levels: Mapping[str, int | float]
    predicted_responses: Mapping[str, int | float]
    schema_version: int = DOE_SCHEMA_VERSION

    def __post_init__(self):
        if type(self.schema_version) is not int or self.schema_version not in _READ_VERSIONS:
            raise ValueError("未知优化结果 schema_version")
        object.__setattr__(self, "schema_version", DOE_SCHEMA_VERSION)
        _text(self.design_id, "design_id", identifier=True)
        object.__setattr__(self, "factor_levels",
                           _freeze_numeric_map(self.factor_levels, "推荐因子水平"))
        object.__setattr__(self, "predicted_responses",
                           _freeze_numeric_map(self.predicted_responses, "预测响应"))


def randomized_run_order(run_ids, seed):
    """用局部 random.Random 重现运行 ID 顺序，不改变全局随机状态。"""
    if isinstance(seed, bool) or not isinstance(seed, Integral):
        raise ValueError("随机化 seed 必须是整数")
    if not isinstance(run_ids, (tuple, list)):
        raise ValueError("run_ids 必须是字符串或整数列表")
    result = [_run_id(value) for value in run_ids]
    if not result or len({_run_id_key(value) for value in result}) != len(result):
        raise ValueError("运行 ID 必须非空且唯一")
    random.Random(int(seed)).shuffle(result)
    return tuple(result)


def _normalize_column_map(value, spec):
    if not isinstance(value, Mapping) or set(value) - _MAP_KEYS:
        raise ValueError("DOE 列映射字段无效")
    required = {"run_id", "standard_order", "run_order", "point_type",
                "replicate", "factors", "responses"}
    if not required <= set(value):
        raise ValueError("DOE 列映射缺少必需字段")
    factors = value["factors"]
    measured = value.get("measured_levels", {})
    responses = value["responses"]
    if not all(isinstance(item, Mapping) for item in (factors, measured, responses)):
        raise ValueError("因子、实测水平和响应列映射必须是映射")
    factor_ids = {factor.factor_id for factor in spec.factors}
    response_names = set(spec.response_names)
    if set(factors) != factor_ids or not set(measured) <= factor_ids:
        raise ValueError("因子列映射与设计定义不一致")
    if set(responses) != response_names:
        raise ValueError("响应列映射与设计定义不一致")
    if spec.design_type == "split_plot" and not {
            "whole_plot_id", "subplot_id", "whole_plot_order", "subplot_order"} <= set(value):
        raise ValueError("Split-Plot 列映射缺少 whole-plot/subplot 随机化字段")
    if spec.foldover_lineage is not None and not {"batch_id", "source_run_id"} <= set(value):
        raise ValueError("Foldover 列映射缺少批次或来源运行字段")
    result = {
        "run_id": _column_label(value["run_id"]),
        "standard_order": _column_label(value["standard_order"]),
        "run_order": _column_label(value["run_order"]),
        "point_type": _column_label(value["point_type"]),
        "replicate": _column_label(value["replicate"]),
        "block": None if value.get("block") is None else _column_label(value["block"]),
        "factors": {key: _column_label(factors[key]) for key in sorted(factors)},
        "measured_levels": {
            key: _column_label(measured[key]) for key in sorted(measured)},
        "responses": {key: _column_label(responses[key]) for key in sorted(responses)},
    }
    for key in ("whole_plot_id", "subplot_id", "batch_id", "source_run_id"):
        if key in value:
            result[key] = _column_label(value[key])
    for key in ("whole_plot_order", "subplot_order"):
        if key in value:
            result[key] = _column_label(value[key])
    labels = [
        result[key] for key in ("run_id", "standard_order", "run_order",
                                "point_type", "replicate")
    ]
    if result["block"] is not None:
        labels.append(result["block"])
    for group in ("factors", "measured_levels", "responses"):
        labels.extend(result[group].values())
    labels.extend(result[key] for key in (
        "whole_plot_id", "subplot_id", "whole_plot_order", "subplot_order",
        "batch_id", "source_run_id") if key in result)
    keys = [_label_key(label) for label in labels]
    if len(set(keys)) != len(keys):
        raise ValueError("DOE 列映射不能将多个字段指向同一列")
    return result


def _column_positions(frame, column_map):
    if not isinstance(frame, pd.DataFrame):
        raise ValueError("DOE 数据源必须是 pandas DataFrame")
    if not frame.columns.is_unique:
        raise ValueError("DOE 数据源存在重复列名")
    labels = [_column_label(value) for value in frame.columns.tolist()]
    positions = {_label_key(label): index for index, label in enumerate(labels)}
    mapped = [column_map[key] for key in
              ("run_id", "standard_order", "run_order", "point_type", "replicate")]
    if column_map["block"] is not None:
        mapped.append(column_map["block"])
    for group in ("factors", "measured_levels", "responses"):
        mapped.extend(column_map[group].values())
    mapped.extend(column_map[key] for key in (
        "whole_plot_id", "subplot_id", "whole_plot_order", "subplot_order",
        "batch_id", "source_run_id") if key in column_map)
    result = {}
    for label in mapped:
        key = _label_key(label)
        if key not in positions:
            raise ValueError(f"DOE 映射列不存在或已重命名：{label!r}")
        result[key] = positions[key]
    return labels, positions


def _cell(frame, row, position):
    return frame.iloc[row, position]


def _missing(value):
    if value is None:
        return True
    try:
        return bool(pd.isna(value))
    except (TypeError, ValueError):
        return False


def _block_value(value):
    if _missing(value):
        return None
    if isinstance(value, Integral) and not isinstance(value, bool):
        return int(value)
    if isinstance(value, Real) and not isinstance(value, bool):
        number = _number(value, "block")
        if isinstance(number, float) and number.is_integer() and abs(number) <= 2**53:
            return int(number)
    if isinstance(value, str) and _RUN_ID.fullmatch(value):
        return value
    raise ValueError("block 值必须是安全字符串、整数或可精确恢复的整数")


def _factor_level(value, factor, field_name):
    if factor.factor_type != "categorical":
        return _number(value, field_name)
    if factor.level_type == "text":
        if isinstance(value, str) and value == value.strip():
            return _text(value, field_name)
        raise ValueError(f"{field_name}必须是文本分类水平")
    return _number(value, field_name)


def foldover_matrix_fingerprint(runs, factors):
    factor_ids = tuple(factor.factor_id for factor in factors)
    factor_map = {factor.factor_id: factor for factor in factors}
    rows = []
    for run in sorted((item for item in runs if item.point_type == "factorial"),
                      key=lambda item: item.standard_order):
        coded = [int(factor_map[key].to_coded(run.settings[key])) for key in factor_ids]
        if any(value not in (-1, 1) for value in coded):
            raise ValueError("Foldover 因子点必须是低或高水平")
        rows.append([run.run_id, run.standard_order, run.replicate, coded])
    encoded = json.dumps({"factors": factor_ids, "runs": rows}, ensure_ascii=False,
                         allow_nan=False, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def category_combinations(factors):
    """分类因子的水平组合；无分类因子时返回单个空组合。"""
    categorical = [factor for factor in factors if factor.factor_type == "categorical"]
    if not categorical:
        return [{}]
    return [{factor.factor_id: level for factor, level in zip(categorical, values)}
            for values in product(*(factor.levels for factor in categorical))]


def design_from_worksheet(frame, spec, column_map):
    """按显式列名和 iloc 行位置读取运行记录，不使用或修改 DataFrame.index。"""
    if not isinstance(spec, DesignSpec):
        raise ValueError("spec 必须是 DesignSpec")
    normalized = _normalize_column_map(column_map, spec)
    _, positions = _column_positions(frame, normalized)
    pos = lambda group, key=None: positions[_label_key(
        normalized[group] if key is None else normalized[group][key])]
    runs = []
    for row in range(len(frame)):
        run_id = _run_id(_cell(frame, row, pos("run_id")), "run_id 列")
        standard_order = _positive_int(
            _cell(frame, row, pos("standard_order")), "standard_order 列")
        run_order = _positive_int(_cell(frame, row, pos("run_order")), "run_order 列")
        point_type = _cell(frame, row, pos("point_type"))
        replicate = _positive_int(_cell(frame, row, pos("replicate")), "replicate 列")
        block = None if normalized["block"] is None else _block_value(
            _cell(frame, row, pos("block")))
        settings = {}
        for factor_id in normalized["factors"]:
            raw = _cell(frame, row, pos("factors", factor_id))
            factor = next(item for item in spec.factors if item.factor_id == factor_id)
            settings[factor_id] = _factor_level(raw, factor, f"因子 {factor_id} 设定水平")
        measured = {}
        for factor_id in normalized["measured_levels"]:
            value = _cell(frame, row, pos("measured_levels", factor_id))
            factor = next(item for item in spec.factors if item.factor_id == factor_id)
            measured[factor_id] = (None if _missing(value) else
                                    _factor_level(value, factor, f"因子 {factor_id} 实测水平"))
        responses = {}
        for name in normalized["responses"]:
            value = _cell(frame, row, pos("responses", name))
            responses[name] = None if _missing(value) else _number(value, f"响应 {name}")
        def optional(field, convert):
            if field not in normalized:
                return None
            value = _cell(frame, row, pos(field))
            return None if _missing(value) else convert(value)
        runs.append(RunRecord(
            run_id=run_id, standard_order=standard_order, run_order=run_order,
            point_type=point_type, settings=settings, replicate=replicate,
            block=block, measured_levels=measured, responses=responses,
            whole_plot_id=optional("whole_plot_id", lambda v: _text(v, "whole_plot_id", identifier=True)),
            subplot_id=optional("subplot_id", lambda v: _text(v, "subplot_id", identifier=True)),
            whole_plot_order=optional("whole_plot_order", lambda v: _positive_int(v, "whole_plot_order")),
            subplot_order=optional("subplot_order", lambda v: _positive_int(v, "subplot_order")),
            batch_id=optional("batch_id", lambda v: _text(v, "batch_id", identifier=True)),
            source_run_id=optional("source_run_id", lambda v: _run_id(v, "source_run_id"))))
    result = DesignResult(spec, tuple(runs))
    if spec.design_type in _SCREENING_TYPES:
        if screening_matrix_sha256(result) != spec.screening_matrix["matrix_sha256"]:
            raise ValueError("筛选矩阵摘要与设计不一致")
        _validate_screening_construction(result)
    if spec.foldover_lineage is not None:
        run_by_id = {_run_id_key(run.run_id): run for run in result.runs}
        lineage = spec.foldover_lineage
        base_runs = [run for run in result.runs if run.batch_id == "BASE"]
        added_runs = [run for run in result.runs if run.batch_id == lineage["batch_id"]]
        sources, additions = set(), set()
        for source_id, addition_id in lineage["run_map"]:
            sources.add(_run_id_key(source_id))
            additions.add(_run_id_key(addition_id))
        if (len(base_runs) + len(added_runs) != len(result.runs)
                or sources != {_run_id_key(run.run_id) for run in base_runs
                               if run.point_type == "factorial"}
                or additions != {_run_id_key(run.run_id) for run in added_runs}
                or any(run.source_run_id is not None for run in base_runs)
                or foldover_matrix_fingerprint(base_runs, spec.factors)
                != lineage["source_matrix_sha256"]
                or foldover_matrix_fingerprint((*base_runs, *added_runs), spec.factors)
                != lineage["current_matrix_sha256"]):
            raise ValueError("Foldover 批次映射或原始/当前模型矩阵摘要不匹配")
        for source_id, addition_id in spec.foldover_lineage["run_map"]:
            source = run_by_id.get(_run_id_key(source_id))
            addition = run_by_id.get(_run_id_key(addition_id))
            if (source is None or addition is None or source.batch_id != "BASE"
                    or addition.source_run_id != source_id
                    or addition.batch_id != lineage["batch_id"]):
                raise ValueError("Foldover 谱系与运行批次映射不一致")
    if spec.design_type == "central_composite" and spec.ccd_alpha is not None:
        from doe_ccd import validate_ccd
        coded = validate_ccd(result)
        continuous = [f for f in spec.factors if f.factor_type == "continuous"]
        for i, factor in enumerate(continuous):
            label = f"编码_{factor.factor_id}"
            if label not in frame.columns or list(frame.columns).count(label) != 1:
                raise ValueError("CCD 编码水平列缺失或重复")
            for row, values in enumerate(coded):
                if _number(frame.iloc[row][label], "CCD 编码水平") != values[i]:
                    raise ValueError("CCD 编码水平与实际设定不一致")
    elif spec.design_type == "box_behnken":
        from doe_bbd import validate_bbd
        coded = validate_bbd(result, frame)
        continuous = [f for f in spec.factors if f.factor_type == "continuous"]
        for i, factor in enumerate(continuous):
            for row, values in enumerate(coded):
                label = f"编码_{factor.factor_id}"
                if _number(frame.iloc[row][label], "编码水平") != values[i]:
                    raise ValueError("编码水平与实际设定不一致")
    if spec.design_type in _CUSTOM_TYPES:
        from doe_custom import validate_custom
        # 欠秩的自定义响应面允许保存为候选集，分析时仍会明确拒绝。
        validate_custom(result, require_estimable=False)
    if spec.optimal_lineage is not None:
        from doe_optimal import candidate_digest
        selected = [run.run_id for run in result.runs
                    if run.run_id in spec.optimal_lineage["selection_order"]]
        if tuple(selected) != spec.optimal_lineage["selection_order"]:
            raise ValueError("最优选点顺序与当前运行不一致")
    if spec.augmentation_lineage is not None:
        from doe_custom import matrix_sha256
        lineage = spec.augmentation_lineage
        base = [run for run in result.runs if run.batch_id != lineage["batch_id"]]
        added = [run for run in result.runs if run.batch_id == lineage["batch_id"]]
        if (len(base) + len(added) != len(result.runs) or not added
                or {_run_id_key(run.run_id) for run in added}
                != {_run_id_key(pair[1]) for pair in lineage["run_map"]}
                or any(run.batch_id not in (None, "BASE") for run in base)):
            raise ValueError("增补批次映射与运行记录不一致")
        from dataclasses import replace as _replace
        parent = _replace(result, spec=_replace(
            spec, design_id=lineage["parent_design_id"],
            augmentation_lineage=None), runs=tuple(base))
        if matrix_sha256(parent) != lineage["source_matrix_sha256"]:
            raise ValueError("增补前模型矩阵摘要与父设计不一致")
        if matrix_sha256(result) != lineage["current_matrix_sha256"]:
            raise ValueError("增补后模型矩阵摘要与设计不一致")
    return result


def _fingerprint(design, column_map, result):
    """摘要使用“实际存储的设计字典”，使 v1 旧工程按原样复核。"""
    rows = [{
        "run_id": run.run_id, "standard_order": run.standard_order,
        "run_order": run.run_order, "point_type": run.point_type,
        "replicate": run.replicate, "block": run.block,
        "settings": dict(run.settings),
    } for run in result.runs]
    if design.get("schema_version", 0) >= 4:
        for row, run in zip(rows, result.runs):
            row.update({
                "whole_plot_id": run.whole_plot_id, "subplot_id": run.subplot_id,
                "whole_plot_order": run.whole_plot_order,
                "subplot_order": run.subplot_order, "batch_id": run.batch_id,
                "source_run_id": run.source_run_id,
            })
    payload = {
        "design": design,
        "column_map": column_map,
        "runs": rows,
    }
    encoded = json.dumps(payload, ensure_ascii=False, allow_nan=False,
                         sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _column_fingerprint(labels):
    encoded = json.dumps([_label_key(label) for label in labels],
                         ensure_ascii=False, allow_nan=False,
                         separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def worksheet_metadata(frame, spec, column_map):
    """创建仅含定义、列映射、行映射和输入摘要的可序列化 DOE 元数据。"""
    normalized = _normalize_column_map(column_map, spec)
    result = design_from_worksheet(frame, spec, normalized)
    labels = [_column_label(label) for label in frame.columns.tolist()]
    return _metadata_payload(spec, normalized, labels, result)


def _metadata_payload(spec, column_map, labels, result, fingerprint=None):
    if fingerprint is None:
        fingerprint = _fingerprint(spec.to_dict(), column_map, result)
    return {
        "schema_version": spec.schema_version,
        "design": spec.to_dict(),
        "column_map": column_map,
        "worksheet": {
            "schema_version": WORKSHEET_SCHEMA_VERSION,
            "row_count": len(result.runs),
            "column_fingerprint": _column_fingerprint(labels),
            "run_rows": [
                {"run_id": run.run_id, "row": row}
                for row, run in enumerate(result.runs)
            ],
            "input_fingerprint": fingerprint,
        },
    }


def _restore(frame, metadata):
    if not isinstance(frame, pd.DataFrame):
        raise ValueError("DOE 数据源必须是 pandas DataFrame")
    if not isinstance(metadata, dict) or set(metadata) != _META_KEYS:
        raise ValueError("DOE 元数据结构无效")
    version = metadata.get("schema_version")
    if type(version) is not int or version not in _READ_VERSIONS:
        raise ValueError(f"未知 DOE schema_version: {version!r}")
    design = metadata["design"]
    if version < 4 and isinstance(metadata.get("column_map"), Mapping):
        if set(metadata["column_map"]) - _MAP_KEYS_V3:
            raise ValueError("旧版 DOE 列映射包含 schema v4 字段")
    if isinstance(design, dict) and design.get("schema_version") != version:
        raise ValueError("DOE schema_version 与设计版本不一致")
    spec = DesignSpec.from_dict(design)
    column_map = _normalize_column_map(metadata["column_map"], spec)
    labels = [_column_label(label) for label in frame.columns.tolist()]
    worksheet = metadata["worksheet"]
    worksheet_keys = {"schema_version", "row_count", "column_fingerprint",
                      "run_rows", "input_fingerprint"}
    if not isinstance(worksheet, dict) or set(worksheet) != worksheet_keys:
        raise ValueError("DOE 工作表映射结构无效")
    if (type(worksheet["schema_version"]) is not int
            or worksheet["schema_version"] != WORKSHEET_SCHEMA_VERSION):
        raise ValueError("未知 DOE 工作表 schema_version")
    row_count = worksheet["row_count"]
    if isinstance(row_count, bool) or not isinstance(row_count, int) or row_count != len(frame):
        raise ValueError("DOE 工作表行数已变化")
    result = design_from_worksheet(frame, spec, column_map)
    column_fingerprint = worksheet["column_fingerprint"]
    if (not isinstance(column_fingerprint, str)
            or not re.fullmatch(r"[0-9a-f]{64}", column_fingerprint)
            or _column_fingerprint(labels) != column_fingerprint):
        raise ValueError("DOE 工作表列名或列顺序已变化")
    rows = worksheet["run_rows"]
    expected_rows = [
        {"run_id": run.run_id, "row": row}
        for row, run in enumerate(result.runs)
    ]
    if not isinstance(rows, list) or len(rows) != len(expected_rows):
        raise ValueError("DOE run_id 到行位置的映射已失效")
    for saved, expected in zip(rows, expected_rows):
        if not isinstance(saved, dict) or set(saved) != {"run_id", "row"}:
            raise ValueError("DOE run_id 到行位置的映射结构无效")
        try:
            saved_id = _run_id(saved["run_id"])
        except ValueError as error:
            raise ValueError("DOE run_id 到行位置的映射含无效 ID") from error
        if (type(saved["row"]) is not int or
                _run_id_key(saved_id) != _run_id_key(expected["run_id"]) or
                saved["row"] != expected["row"]):
            raise ValueError("DOE run_id 到行位置的映射已失效")
    fingerprint = worksheet["input_fingerprint"]
    if not isinstance(fingerprint, str) or not re.fullmatch(r"[0-9a-f]{64}", fingerprint):
        raise ValueError("DOE 输入摘要无效")
    if _fingerprint(metadata["design"], column_map, result) != fingerprint:
        raise ValueError("DOE 设计输入或运行映射已变化")
    return result, column_map, labels, fingerprint


def restore_design_result(frame, metadata):
    """验证工作表版本、列/行映射和输入摘要后恢复结构化设计。"""
    return _restore(frame, metadata)[0]


def validate_worksheet_metadata(frame, metadata):
    """验证后返回脱离调用者对象的规范化元数据副本。"""
    result, column_map, labels, fingerprint = _restore(frame, metadata)
    # 读取旧 v1 后升级为当前版本，摘要按升级后的设计重新计算。
    return _metadata_payload(result.spec, column_map, labels, result)

