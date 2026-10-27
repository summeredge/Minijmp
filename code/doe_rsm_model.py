"""响应面模型项、区组与分类因子编码；供拟合、预测、绘图和优化共用。"""
from itertools import combinations

import numpy as np


def _split(term):
    return tuple(part.strip() for part in term.split('*'))


class TermModel:
    """把模型项编译为设计矩阵列；分类因子使用参考水平哑变量。"""

    def __init__(self, factors, terms=None, blocks=0):
        self.factors = tuple(factors)
        self.by_id = {factor.factor_id: factor for factor in self.factors}
        self.blocks = int(blocks)
        self.terms = (tuple(self.default_terms()) if terms is None
                      else self.validate_terms(terms))
        self.columns = self._columns()

    # -- terms ---------------------------------------------------------
    def continuous(self):
        return [f.factor_id for f in self.factors if f.factor_type == 'continuous']

    def categorical(self):
        return [f.factor_id for f in self.factors if f.factor_type == 'categorical']

    def default_terms(self):
        continuous = self.continuous()
        terms = list(continuous) + [f.factor_id for f in self.factors
                                    if f.factor_type == 'categorical']
        terms += [f'{name}²' for name in continuous]
        terms += [f'{a}*{b}' for a, b in combinations(continuous, 2)]
        terms += [f'{name}*{category}' for category in self.categorical()
                  for name in continuous]
        return terms

    def validate_terms(self, terms):
        if not isinstance(terms, (tuple, list)) or not terms:
            raise ValueError('模型项必须是非空列表')
        result, seen = [], set()
        for term in terms:
            if not isinstance(term, str) or not term or term != term.strip():
                raise ValueError('模型项必须是字符串')
            if term in seen:
                raise ValueError(f'模型项重复：{term}')
            seen.add(term)
            parts = _split(term)
            if len(parts) > 2:
                raise ValueError(f'模型项最多两个因子：{term}')
            squared = len(parts) == 1 and term.endswith('²')
            if squared:
                base = term[:-1]
                if base not in self.by_id:
                    raise ValueError(f'模型项含未知因子：{term}')
                if self.by_id[base].factor_type != 'continuous':
                    raise ValueError(f'分类因子没有平方项：{term}')
                result.append(term)
                continue
            for part in parts:
                if part not in self.by_id:
                    raise ValueError(f'模型项含未知因子：{term}')
            if len(parts) == 2:
                kinds = {self.by_id[part].factor_type for part in parts}
                if kinds == {'categorical'}:
                    raise ValueError(f'不支持分类因子间的交互项：{term}')
                if parts[0] == parts[1]:
                    raise ValueError(f'交互项需要两个不同因子：{term}')
            result.append(term)
        self._check_hierarchy(result)
        return tuple(result)

    @staticmethod
    def _check_hierarchy(terms):
        present = set(terms)
        for term in terms:
            parts = _split(term)
            if len(parts) == 1 and term.endswith('²'):
                base = term[:-1]
                if base not in present:
                    raise ValueError(f'平方项 {term} 需要同时包含 {base}')
            elif len(parts) == 2:
                for part in parts:
                    if part not in present:
                        raise ValueError(f'交互项 {term} 需要同时包含 {part}')

    def _columns(self):
        columns = [('截距', None)]
        for term in self.terms:
            parts = _split(term)
            if len(parts) == 1 and not term.endswith('²'):
                factor = self.by_id[parts[0]]
                if factor.factor_type == 'categorical':
                    columns.extend((f'{factor.factor_id}[{level}]',
                                    (term, level))
                                   for level in factor.levels[1:])
                else:
                    columns.append((term, None))
            elif term.endswith('²'):
                columns.append((term, None))
            else:
                first, second = parts
                categories = [p for p in parts
                              if self.by_id[p].factor_type == 'categorical']
                if categories:
                    factor = self.by_id[categories[0]]
                    columns.extend((f'{term}[{level}]', (term, level))
                                   for level in factor.levels[1:])
                else:
                    columns.append((term, None))
        # 与分类因子一致：第 1 个水平为参考，保留其余水平。
        columns.extend((f'区组{b}', ('block', b))
                       for b in range(2, self.blocks + 1))
        return columns

    @property
    def names(self):
        return [name for name, _ in self.columns]

    @property
    def width(self):
        return len(self.columns)

    # -- evaluation ----------------------------------------------------
    def coded(self, settings):
        """连续因子返回编码值，分类因子返回水平字符串。"""
        result = {}
        for factor in self.factors:
            value = settings[factor.factor_id]
            if factor.factor_type == 'categorical':
                if value not in factor.levels:
                    raise ValueError(f'因子 {factor.factor_id} 的水平不在已声明范围内')
                result[factor.factor_id] = value
            else:
                result[factor.factor_id] = float(factor.to_coded(value))
        return result

    def row(self, settings, block=None):
        """按列顺序构造单行模型向量。"""
        values = (settings if isinstance(settings, dict)
                  else self.coded(settings))
        row = [1.0]
        for _name, spec in self.columns[1:]:
            if spec is None:
                term = _name
                if term.endswith('²'):
                    row.append(values[term[:-1]] ** 2)
                elif '*' in term:
                    first, second = term.split('*')
                    row.append(values[first] * values[second])
                else:
                    row.append(values[term])
                continue
            if not isinstance(spec, tuple) or len(spec) != 2:
                raise ValueError(f'模型列定义无效：{_name}')
            if spec[0] == 'block':
                if block is None:
                    raise ValueError('模型含区组项，但未提供区组')
                row.append(1.0 if block == spec[1] else 0.0)
                continue
            term, level = spec
            indicator = 1.0 if values[_category_of(term, self.by_id)] == level else 0.0
            if '*' in term:
                continuous = next(part for part in term.split('*')
                                  if self.by_id[part].factor_type == 'continuous')
                row.append(values[continuous] * indicator)
            else:
                row.append(indicator)
        return np.asarray(row, dtype=float)

    def matrix(self, settings_rows, blocks=None):
        blocks = [None] * len(settings_rows) if blocks is None else blocks
        return np.vstack([self.row(settings, block)
                          for settings, block in zip(settings_rows, blocks)])

    def gradient(self, settings, block=None):
        """对连续因子编码值求解析梯度；分类与区组无导数。"""
        values = settings
        continuous = self.continuous()
        index = {name: i for i, name in enumerate(continuous)}
        gradient = np.zeros(len(continuous))
        for _name, spec in self.columns[1:]:
            if spec is None:
                term = _name
                if term.endswith('²'):
                    gradient[index[term[:-1]]] += 2 * values[term[:-1]]
                elif '*' in term:
                    first, second = term.split('*')
                    gradient[index[first]] += values[second]
                    gradient[index[second]] += values[first]
                else:
                    gradient[index[term]] += 1.0
                continue
            if spec[0] == 'block':
                continue
            term, level = spec
            category = _category_of(term, self.by_id)
            if values[category] != level:
                continue
            if '*' in term:
                gradient[index[next(part for part in term.split('*')
                                    if part != category)]] += 1.0
        return gradient


def _category_of(term, by_id):
    return next(part for part in term.split('*')
                if by_id[part].factor_type == 'categorical')
