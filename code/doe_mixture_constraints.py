"""混料比例约束：上下界、线性不等式、可行性与单位换算。"""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
import math
from types import MappingProxyType
from typing import Mapping


TOLERANCE = 1e-9


class MixtureConstraintError(ValueError):
    """混料约束或设计输入无效。"""


def _identifier(value, label):
    if (not isinstance(value, str) or not value or value != value.strip()
            or not value[0].isalpha() or not all(c.isalnum() or c in '_.-' for c in value)
            or len(value) > 64):
        raise MixtureConstraintError(f'{label} 必须是稳定的 ASCII 标识符')
    return value


def _text(value, label):
    if not isinstance(value, str) or not value or value != value.strip():
        raise MixtureConstraintError(f'{label} 必须是非空且无首尾空格的字符串')
    return value


def _number(value, label):
    if isinstance(value, bool) or not isinstance(value, (int, float, Fraction)):
        raise MixtureConstraintError(f'{label} 必须是有限数值')
    if isinstance(value, Fraction):
        value = float(value)
    if not math.isfinite(value):
        raise MixtureConstraintError(f'{label} 必须是有限数值')
    return float(value)


@dataclass(frozen=True)
class ComponentSpec:
    """一个混料组分及其比例上下界；比例以 0–1 表示。"""

    component_id: str
    name: str
    lower: float = 0.0
    upper: float = 1.0
    unit: str | None = None

    def __post_init__(self):
        _identifier(self.component_id, '组分 ID')
        _text(self.name, '组分名称')
        if self.unit is not None:
            _text(self.unit, '组分单位')
        lower = _number(self.lower, '组分下界')
        upper = _number(self.upper, '组分上界')
        if not 0 <= lower <= upper <= 1:
            raise MixtureConstraintError('组分比例必须满足 0 ≤ 下界 ≤ 上界 ≤ 1')
        object.__setattr__(self, 'lower', lower)
        object.__setattr__(self, 'upper', upper)

    def to_dict(self):
        return {'component_id': self.component_id, 'name': self.name,
                'lower': self.lower, 'upper': self.upper, 'unit': self.unit}

    @classmethod
    def from_dict(cls, data):
        if not isinstance(data, dict) or set(data) != {
                'component_id', 'name', 'lower', 'upper', 'unit'}:
            raise MixtureConstraintError('组分字段无效')
        return cls(**data)


@dataclass(frozen=True)
class VariableSpec:
    """工艺变量或总量变量；水平保留实际单位。"""

    variable_id: str
    name: str
    low: float
    high: float
    unit: str | None = None
    role: str = 'process'

    def __post_init__(self):
        _identifier(self.variable_id, '变量 ID')
        _text(self.name, '变量名称')
        if self.unit is not None:
            _text(self.unit, '变量单位')
        low = _number(self.low, '变量低水平')
        high = _number(self.high, '变量高水平')
        if low >= high:
            raise MixtureConstraintError('变量低水平必须小于高水平')
        if self.role not in ('process', 'amount'):
            raise MixtureConstraintError('变量角色必须是 process 或 amount')
        object.__setattr__(self, 'low', low)
        object.__setattr__(self, 'high', high)

    def to_coded(self, value):
        value = _number(value, '变量水平')
        if not self.low - TOLERANCE <= value <= self.high + TOLERANCE:
            raise MixtureConstraintError(f'变量 {self.variable_id} 超出声明范围')
        return 2 * (value - self.low) / (self.high - self.low) - 1

    def to_dict(self):
        return {'variable_id': self.variable_id, 'name': self.name,
                'low': self.low, 'high': self.high, 'unit': self.unit,
                'role': self.role}

    @classmethod
    def from_dict(cls, data):
        if not isinstance(data, dict) or set(data) != {
                'variable_id', 'name', 'low', 'high', 'unit', 'role'}:
            raise MixtureConstraintError('变量字段无效')
        return cls(**data)


@dataclass(frozen=True)
class LinearConstraint:
    """规范化的线性约束 sum(coefficient * x) ≤ bound。"""

    coefficients: Mapping[str, float]
    bound: float

    def __post_init__(self):
        if not isinstance(self.coefficients, Mapping) or not self.coefficients:
            raise MixtureConstraintError('线性约束必须包含组分系数')
        values = {}
        for key, value in self.coefficients.items():
            values[_identifier(key, '约束组分 ID')] = _number(value, '约束系数')
        bound = _number(self.bound, '约束右端')
        object.__setattr__(self, 'coefficients', MappingProxyType(values))
        object.__setattr__(self, 'bound', bound)

    def value(self, proportions):
        return sum(coefficient * proportions[key]
                   for key, coefficient in self.coefficients.items())

    def residual(self, proportions):
        return self.value(proportions) - self.bound

    def to_dict(self):
        return {'coefficients': dict(self.coefficients), 'bound': self.bound}

    @classmethod
    def from_dict(cls, data):
        if not isinstance(data, dict) or set(data) != {'coefficients', 'bound'}:
            raise MixtureConstraintError('线性约束字段无效')
        return cls(data['coefficients'], data['bound'])


def bounds_problem(components, tol=TOLERANCE):
    """返回上下界本身是否可容纳总和 1。"""
    lower = sum(component.lower for component in components)
    upper = sum(component.upper for component in components)
    if lower > 1 + tol:
        return f'组分下界之和 {lower:.12g} 大于 1'
    if upper < 1 - tol:
        return f'组分上界之和 {upper:.12g} 小于 1'
    return None


def check_point(components, constraints, proportions, tol=TOLERANCE):
    """严格核验单点；返回最大约束残差。"""
    if len(proportions) != len(components):
        raise MixtureConstraintError('组分比例数量与组分定义不一致')
    values = [_number(value, '组分比例') for value in proportions]
    if any(value < -tol or value > 1 + tol for value in values):
        raise MixtureConstraintError('组分比例必须在 0 到 1 之间')
    total = sum(values)
    if abs(total - 1) > tol:
        raise MixtureConstraintError(f'组分比例之和必须为 1，实际为 {total:.12g}')
    residual = abs(total - 1)
    for component, value in zip(components, values):
        if value < component.lower - tol or value > component.upper + tol:
            raise MixtureConstraintError(
                f'组分 {component.component_id} 比例 {value:.12g} 超出 '
                f'[{component.lower:.12g}, {component.upper:.12g}]')
        residual = max(residual, component.lower - value, value - component.upper)
    mapping = {component.component_id: value
               for component, value in zip(components, values)}
    for constraint in constraints:
        excess = constraint.residual(mapping)
        if excess > tol:
            raise MixtureConstraintError(
                '线性约束不满足：' + '；'.join(
                    f'{coefficient:g}*{key}' for key, coefficient in
                    constraint.coefficients.items())
                + f' ≤ {constraint.bound:.12g}')
        residual = max(residual, excess)
    return residual


def feasible(components, constraints, proportions, tol=TOLERANCE):
    try:
        check_point(components, constraints, proportions, tol)
    except MixtureConstraintError:
        return False
    return True


def component_slacks(components, proportions):
    """每个组分在当前点上可向 0 和 1 方向调整的余量。"""
    return [(value - component.lower, component.upper - value)
            for component, value in zip(components, proportions)]


def normalize_proportions(components, proportions, tol=TOLERANCE):
    """只修正浮点舍入，不把真实越界点变成合法点。"""
    values = [_number(value, '组分比例') for value in proportions]
    residual = 1 - sum(values)
    if abs(residual) > tol:
        raise MixtureConstraintError(f'组分比例之和必须为 1，实际为 {sum(values):.12g}')
    if residual:
        slacks = component_slacks(components, values)
        index = max(range(len(values)), key=lambda i: slacks[i][1] if residual > 0
                    else slacks[i][0])
        values[index] += residual
    return values


def to_pseudocomponents(components, proportions):
    """实际比例转伪组分：x' = (x - lower) / (1 - sum(lower))。"""
    values = normalize_proportions(components, proportions)
    base = sum(component.lower for component in components)
    if 1 - base <= TOLERANCE:
        raise MixtureConstraintError('下界之和为 1，伪组分变换退化')
    return tuple((value - component.lower) / (1 - base)
                 for component, value in zip(components, values))


def from_pseudocomponents(components, pseudo):
    """伪组分还原实际比例；结果仍必须满足真实约束。"""
    base = sum(component.lower for component in components)
    values = [component.lower + value * (1 - base)
              for component, value in zip(components, pseudo)]
    check_point(components, (), values)
    return values


def actual_amounts(proportions, total, tol=TOLERANCE):
    """实际组分量 = 总量 × 比例。"""
    values = [_number(value, '组分比例') for value in proportions]
    total = _number(total, '总量')
    if abs(sum(values) - 1) > tol:
        raise MixtureConstraintError('组分比例之和必须为 1')
    if total <= 0:
        raise MixtureConstraintError('总量必须大于 0')
    return tuple(total * value for value in values)


def proportions_from_amounts(amounts, tol=TOLERANCE):
    """由实际组分量反算比例和总量。"""
    values = [_number(value, '组分量') for value in amounts]
    if any(value < 0 for value in values):
        raise MixtureConstraintError('组分量不能为负')
    total = sum(values)
    if total <= TOLERANCE:
        raise MixtureConstraintError('组分量之和必须大于 0')
    return tuple(value / total for value in values), total
