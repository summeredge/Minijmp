"""Scheffé 混料模型项与模型矩阵；不引入普通回归截距。"""
from __future__ import annotations

from itertools import combinations

import numpy as np

from doe_mixture import MixtureSpec
from doe_mixture_constraints import MixtureConstraintError, TOLERANCE


def _parts(term):
    return tuple(part.strip() for part in term.split('*'))


class MixtureTermModel:
    """混料组分单项/交互项，加过程与总量变量；无截距列。"""

    def __init__(self, spec, terms=None, degree=2):
        if not isinstance(spec, MixtureSpec):
            raise MixtureConstraintError('spec 必须是 MixtureSpec')
        if isinstance(degree, bool) or not isinstance(degree, int) or not 1 <= degree <= 3:
            raise MixtureConstraintError('Scheffé 模型阶次必须为 1–3')
        self.spec = spec
        self.degree = degree
        self.component_ids = spec.component_ids
        self.variable_ids = spec.variable_ids
        self.by_id = {item.component_id: item for item in spec.components}
        self.variables = {item.variable_id: item
                          for item in (*spec.process_variables, *spec.amount_variables)}
        self.terms = (tuple(self.default_terms()) if terms is None
                      else self.validate_terms(terms))

    def default_terms(self):
        terms = list(self.component_ids)
        if self.degree >= 2:
            terms += ['*'.join(pair) for pair in combinations(self.component_ids, 2)]
        if self.degree >= 3:
            terms += ['*'.join(triple) for triple in combinations(self.component_ids, 3)]
        process_ids = [item.variable_id for item in self.spec.process_variables]
        # 完整 xi*P 已张成 P（Σxi=1）；再加入 P 会造成结构性完全共线。
        terms += [f'{component}*{variable}'
                  for variable in process_ids for component in self.component_ids]
        if self.spec.construction_version == 'v2':
            amount_ids = [item.variable_id for item in self.spec.amount_variables]
            terms += [f'{component}*{variable}'
                      for variable in amount_ids for component in self.component_ids]
        return terms

    def validate_terms(self, terms):
        if not isinstance(terms, (tuple, list)) or not terms:
            raise MixtureConstraintError('模型项必须是非空列表')
        result, seen = [], set()
        for term in terms:
            if not isinstance(term, str) or not term or term != term.strip():
                raise MixtureConstraintError('模型项必须是非空字符串')
            if term in seen:
                raise MixtureConstraintError(f'模型项重复：{term}')
            seen.add(term)
            parts = _parts(term)
            if len(parts) > 3 or len(set(parts)) != len(parts):
                raise MixtureConstraintError(f'模型项不受支持：{term}')
            unknown = [part for part in parts
                       if part not in self.by_id and part not in self.variables]
            if unknown:
                raise MixtureConstraintError('模型项含未知因子：' + '、'.join(unknown))
            components = [part for part in parts if part in self.by_id]
            variables = [part for part in parts if part in self.variables]
            if len(components) > 3:
                raise MixtureConstraintError(f'混料项最多三个组分：{term}')
            if len(variables) > 1:
                raise MixtureConstraintError(f'当前仅支持一个变量参与模型项：{term}')
            if sum(self.variables[part].role == 'amount' for part in variables) > 1:
                raise MixtureConstraintError(f'总量变量不能与自身或第二个总量组合：{term}')
            if components and variables:
                if len(components) != 1:
                    raise MixtureConstraintError(f'混料×变量项只支持单个组分：{term}')
            result.append(term)
        return tuple(result)

    @property
    def names(self):
        return list(self.terms)

    @property
    def width(self):
        return len(self.terms)

    def encoded(self, settings):
        """组分保留实际比例，过程/总量使用 [-1, 1] 编码。"""
        values = {}
        for component_id in self.component_ids:
            if component_id not in settings:
                raise MixtureConstraintError(f'缺少组分比例：{component_id}')
            value = settings[component_id]
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise MixtureConstraintError('组分比例必须是数值')
            values[component_id] = float(value)
        for variable_id in self.variable_ids:
            if variable_id not in settings:
                raise MixtureConstraintError(f'缺少变量设定：{variable_id}')
            values[variable_id] = self.variables[variable_id].to_coded(
                settings[variable_id])
        return values

    def row(self, settings):
        values = self.encoded(settings)
        return np.asarray([np.prod([values[part] for part in _parts(term)])
                           for term in self.terms], dtype=float)

    def matrix(self, rows):
        return np.vstack([self.row(row) for row in rows])


def predict_row(model, coefficients, settings):
    value = float(np.asarray(model.row(settings), dtype=float)
                  @ np.asarray(coefficients, dtype=float))
    if not np.isfinite(value):
        raise MixtureConstraintError('预测值超出有限范围')
    return value


def is_component_main(term, model):
    return term in model.by_id
