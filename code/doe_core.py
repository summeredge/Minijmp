"""版本化 DOE 数据合同与工作表映射；不生成设计矩阵或执行拟合/优化。"""
from __future__ import annotations

from dataclasses import dataclass, field
from fractions import Fraction
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


DOE_SCHEMA_VERSION = 1
WORKSHEET_SCHEMA_VERSION = 1
_ID = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]{0,63}$")
_RUN_ID = re.compile(r"^[A-Za-z0-9_.-]{1,128}$")
_RELATION = re.compile(r"^[A-Za-z][A-Za-z0-9]*(?:=[A-Za-z][A-Za-z0-9]*)+$")
_DESIGN_TYPES = frozenset({
    "unspecified", "two_level_full", "two_level_fractional", "central_composite",
})
_POINT_TYPES = frozenset({"factorial", "center", "axial"})
_DESIGN_KEYS = {
    "schema_version", "design_id", "factors", "response_names", "seed",
    "generators", "defining_relations", "aliases", "ccd_alpha",
    "ccd_center_points", "ccd_axial_points", "design_type",
}
_MAP_KEYS = {
    "run_id", "standard_order", "run_order", "point_type", "replicate",
    "block", "factors", "measured_levels", "responses",
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


@dataclass(frozen=True)
class FactorSpec:
    """连续因子的稳定 ID、展示名、单位及实际低/高水平。"""

    factor_id: str
    name: str
    low: int | float | None
    high: int | float | None
    unit: str | None = None
    factor_type: str = "continuous"
    levels: tuple[str, ...] = ()
    schema_version: int = DOE_SCHEMA_VERSION

    def __post_init__(self):
        _text(self.factor_id, "factor_id", identifier=True)
        _text(self.name, "因子名称")
        if self.unit is not None:
            _text(self.unit, "因子单位")
        if type(self.schema_version) is not int or self.schema_version != DOE_SCHEMA_VERSION:
            raise ValueError("未知因子 schema_version")
        if self.factor_type not in ("continuous", "categorical"):
            raise ValueError("factor_type 必须是 continuous 或 categorical")
        levels = _string_tuple(self.levels, "分类因子水平")
        object.__setattr__(self, "levels", levels)
        if self.factor_type == "categorical":
            if self.low is not None or self.high is not None or len(levels) < 2:
                raise ValueError("分类因子仅保留至少两个显式字符串水平；DOE-0 不对其编码")
            return
        if levels or self.low is None or self.high is None:
            raise ValueError("连续因子必须提供实际 low/high，且不能提供分类水平")
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
        return {
            "schema_version": self.schema_version, "factor_id": self.factor_id,
            "name": self.name, "unit": self.unit, "factor_type": self.factor_type,
            "low": self.low, "high": self.high, "levels": list(self.levels),
        }

    @classmethod
    def from_dict(cls, data):
        keys = {"schema_version", "factor_id", "name", "unit", "factor_type",
                "low", "high", "levels"}
        if (not isinstance(data, dict) or set(data) != keys
                or not isinstance(data["levels"], list)):
            raise ValueError("因子元数据字段无效")
        return cls(**{**data, "levels": tuple(data["levels"])})


@dataclass(frozen=True)
class DesignSpec:
    """设计定义；预留的生成元和 CCD 字段只存储，不执行设计生成。"""

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

    def __post_init__(self):
        _text(self.design_id, "design_id", identifier=True)
        if type(self.schema_version) is not int or self.schema_version != DOE_SCHEMA_VERSION:
            raise ValueError("未知设计 schema_version")
        if not isinstance(self.design_type, str) or self.design_type not in _DESIGN_TYPES:
            raise ValueError(
                "design_type 必须是 unspecified、two_level_full、"
                "two_level_fractional 或 central_composite")
        factors = tuple(self.factors) if isinstance(self.factors, (tuple, list)) else ()
        if not factors or not all(isinstance(item, FactorSpec) for item in factors):
            raise ValueError("设计必须包含 FactorSpec")
        if any(item.factor_type != "continuous" for item in factors):
            raise NotImplementedError("DOE-0 不实现分类或混合水平设计")
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

    def to_dict(self):
        return {
            "schema_version": self.schema_version, "design_id": self.design_id,
            "factors": [factor.to_dict() for factor in self.factors],
            "response_names": list(self.response_names), "seed": self.seed,
            "generators": list(self.generators),
            "defining_relations": list(self.defining_relations),
            "aliases": list(self.aliases), "ccd_alpha": self.ccd_alpha,
            "ccd_center_points": self.ccd_center_points,
            "ccd_axial_points": self.ccd_axial_points,
            "design_type": self.design_type,
        }

    @classmethod
    def from_dict(cls, data):
        if not isinstance(data, dict):
            raise ValueError("设计元数据字段无效")
        if "design_type" not in data:
            raise ValueError("设计元数据缺少 design_type")
        if set(data) != _DESIGN_KEYS:
            raise ValueError("设计元数据字段无效")
        version = data.get("schema_version")
        if type(version) is not int or version != DOE_SCHEMA_VERSION:
            raise ValueError(f"未知 DOE schema_version: {version!r}")
        if any(not isinstance(data[key], list) for key in (
                "factors", "response_names", "generators",
                "defining_relations", "aliases")):
            raise ValueError("设计列表字段结构无效")
        return cls(
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
        )


@dataclass(frozen=True)
class RunRecord:
    """一行实验记录；设定水平、实测水平和响应值分别保存。"""

    run_id: str | int
    standard_order: int
    run_order: int
    point_type: str
    settings: Mapping[str, int | float]
    replicate: int = 1
    block: str | int | None = None
    measured_levels: Mapping[str, int | float | None] = field(default_factory=dict)
    responses: Mapping[str, int | float | None] = field(default_factory=dict)
    schema_version: int = DOE_SCHEMA_VERSION

    def __post_init__(self):
        if type(self.schema_version) is not int or self.schema_version != DOE_SCHEMA_VERSION:
            raise ValueError("未知运行记录 schema_version")
        object.__setattr__(self, "run_id", _run_id(self.run_id))
        object.__setattr__(self, "standard_order",
                           _positive_int(self.standard_order, "standard_order"))
        object.__setattr__(self, "run_order",
                           _positive_int(self.run_order, "run_order"))
        object.__setattr__(self, "replicate", _positive_int(self.replicate, "replicate"))
        if self.point_type not in _POINT_TYPES:
            raise ValueError("point_type 必须是 factorial、center 或 axial")
        if self.block is not None:
            if isinstance(self.block, Integral) and not isinstance(self.block, bool):
                object.__setattr__(self, "block", int(self.block))
            elif isinstance(self.block, str) and _RUN_ID.fullmatch(self.block):
                pass
            else:
                raise ValueError("block 必须是安全字符串、整数或 None")
        object.__setattr__(self, "settings",
                           _freeze_numeric_map(self.settings, "设定水平"))
        object.__setattr__(self, "measured_levels",
                           _freeze_numeric_map(self.measured_levels, "实测水平",
                                               nullable=True))
        object.__setattr__(self, "responses",
                           _freeze_numeric_map(self.responses, "响应值", nullable=True))


@dataclass(frozen=True)
class DesignResult:
    """按工作表行顺序保存的运行记录，顺序字段仍独立表示标准/实际顺序。"""

    spec: DesignSpec
    runs: tuple[RunRecord, ...]
    schema_version: int = DOE_SCHEMA_VERSION

    def __post_init__(self):
        if type(self.schema_version) is not int or self.schema_version != DOE_SCHEMA_VERSION:
            raise ValueError("未知设计结果 schema_version")
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
            if set(run.settings) != factor_ids:
                raise ValueError("每个运行的设定水平必须覆盖全部因子")
            if not set(run.measured_levels) <= factor_ids:
                raise ValueError("实测水平包含未知因子")
            if set(run.responses) != response_names:
                raise ValueError("每个运行的响应字段必须与设计定义一致")
            if run.point_type != "axial":
                for factor in self.spec.factors:
                    factor.to_coded(run.settings[factor.factor_id])
        axial_count = sum(run.point_type == "axial" for run in runs)
        center_count = sum(run.point_type == "center" for run in runs)
        if axial_count and (
                self.spec.ccd_alpha is None or self.spec.ccd_axial_points != axial_count):
            raise ValueError("轴点记录必须匹配已声明的 CCD alpha 和轴点数")
        if not axial_count and self.spec.ccd_axial_points not in (None, 0):
            raise ValueError("CCD 轴点数与运行记录不一致")
        if (self.spec.ccd_center_points is not None
                and self.spec.ccd_center_points != center_count):
            raise ValueError("CCD 中心点数与运行记录不一致")
        object.__setattr__(self, "runs", runs)


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
        if type(self.schema_version) is not int or self.schema_version != DOE_SCHEMA_VERSION:
            raise ValueError("未知模型结果 schema_version")
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
        if type(self.schema_version) is not int or self.schema_version != DOE_SCHEMA_VERSION:
            raise ValueError("未知优化结果 schema_version")
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
    labels = [
        result[key] for key in ("run_id", "standard_order", "run_order",
                                "point_type", "replicate")
    ]
    if result["block"] is not None:
        labels.append(result["block"])
    for group in ("factors", "measured_levels", "responses"):
        labels.extend(result[group].values())
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
        settings = {
            factor_id: _number(_cell(frame, row, pos("factors", factor_id)),
                               f"因子 {factor_id} 实际设定水平")
            for factor_id in normalized["factors"]
        }
        measured = {}
        for factor_id in normalized["measured_levels"]:
            value = _cell(frame, row, pos("measured_levels", factor_id))
            measured[factor_id] = None if _missing(value) else _number(
                value, f"因子 {factor_id} 实测水平")
        responses = {}
        for name in normalized["responses"]:
            value = _cell(frame, row, pos("responses", name))
            responses[name] = None if _missing(value) else _number(value, f"响应 {name}")
        runs.append(RunRecord(
            run_id=run_id, standard_order=standard_order, run_order=run_order,
            point_type=point_type, settings=settings, replicate=replicate,
            block=block, measured_levels=measured, responses=responses))
    result = DesignResult(spec, tuple(runs))
    if spec.design_type == "central_composite" and spec.ccd_alpha is not None:
        from doe_ccd import validate_ccd
        coded = validate_ccd(result)
        for i, factor in enumerate(spec.factors):
            label = f"编码_{factor.factor_id}"
            if label not in frame.columns or list(frame.columns).count(label) != 1:
                raise ValueError("CCD 编码水平列缺失或重复")
            for row, values in enumerate(coded):
                if _number(frame.iloc[row][label], "CCD 编码水平") != values[i]:
                    raise ValueError("CCD 编码水平与实际设定不一致")
    return result


def _fingerprint(spec, column_map, result):
    payload = {
        "design": spec.to_dict(),
        "column_map": column_map,
        "runs": [{
            "run_id": run.run_id, "standard_order": run.standard_order,
            "run_order": run.run_order, "point_type": run.point_type,
            "replicate": run.replicate, "block": run.block,
            "settings": dict(run.settings),
        } for run in result.runs],
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
        fingerprint = _fingerprint(spec, column_map, result)
    return {
        "schema_version": DOE_SCHEMA_VERSION,
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
    if type(version) is not int or version != DOE_SCHEMA_VERSION:
        raise ValueError(f"未知 DOE schema_version: {version!r}")
    spec = DesignSpec.from_dict(metadata["design"])
    column_map = _normalize_column_map(metadata["column_map"], spec)
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
    labels = [_column_label(label) for label in frame.columns.tolist()]
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
    if _fingerprint(spec, column_map, result) != fingerprint:
        raise ValueError("DOE 设计输入或运行映射已变化")
    return result, column_map, labels, fingerprint


def restore_design_result(frame, metadata):
    """验证工作表版本、列/行映射和输入摘要后恢复结构化设计。"""
    return _restore(frame, metadata)[0]


def validate_worksheet_metadata(frame, metadata):
    """验证后返回脱离调用者对象的规范化元数据副本。"""
    result, column_map, labels, fingerprint = _restore(frame, metadata)
    return _metadata_payload(result.spec, column_map, labels, result, fingerprint)

