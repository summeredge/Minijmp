"""混料专属数据合同及其在 DOE schema v4 工作表上的最小适配。"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
from numbers import Integral

from doe_core import DesignSpec, FactorSpec
from doe_mixture_constraints import (
    ComponentSpec, LinearConstraint, MixtureConstraintError, TOLERANCE,
    VariableSpec, check_point, normalize_proportions,
)


MIXTURE_SCHEMA_VERSION = 1
MIXTURE_TYPES = ('simplex_lattice', 'simplex_centroid', 'extreme_vertices')
_SPEC_KEYS = {
    'schema_version', 'design_id', 'design_type', 'degree', 'components',
    'process_variables', 'amount_variables', 'amount_settings',
    'linear_constraints', 'response_names', 'seed', 'construction_version',
}
_META_KEYS = {'schema_version', 'spec', 'worksheet'}
_MODEL_KEYS = {'response', 'degree', 'terms', 'input_fingerprint'}


def _string_tuple(values, label):
    if not isinstance(values, (tuple, list)) or not values:
        raise MixtureConstraintError(f'{label} 必须是非空列表')
    result = tuple(str(value) for value in values)
    if any(not value or value != value.strip() for value in result):
        raise MixtureConstraintError(f'{label} 必须是非空且无首尾空格的字符串')
    if len(set(result)) != len(result):
        raise MixtureConstraintError(f'{label} 不得重复')
    return result


@dataclass(frozen=True)
class MixtureSpec:
    """混料组分、过程/总量变量、约束与设计构造的稳定定义。"""

    design_id: str
    components: tuple[ComponentSpec, ...]
    response_names: tuple[str, ...]
    design_type: str = 'simplex_lattice'
    degree: int | None = 2
    process_variables: tuple[VariableSpec, ...] = ()
    amount_variables: tuple[VariableSpec, ...] = ()
    amount_settings: tuple[tuple[str, float], ...] = ()
    linear_constraints: tuple[LinearConstraint, ...] = ()
    seed: int = 1
    schema_version: int = MIXTURE_SCHEMA_VERSION
    construction_version: str = 'v1'

    def __post_init__(self):
        if self.schema_version != MIXTURE_SCHEMA_VERSION:
            raise MixtureConstraintError('未知混料 schema_version')
        if self.construction_version != 'v1':
            raise MixtureConstraintError('未知混料构造版本')
        if not isinstance(self.design_id, str) or not self.design_id:
            raise MixtureConstraintError('design_id 必须是非空字符串')
        components = tuple(self.components) if isinstance(
            self.components, (tuple, list)) else ()
        if not 2 <= len(components) <= 12:
            raise MixtureConstraintError('混料设计需要 2–12 个组分')
        if not all(isinstance(item, ComponentSpec) for item in components):
            raise MixtureConstraintError('components 必须包含 ComponentSpec')
        if len({item.component_id for item in components}) != len(components):
            raise MixtureConstraintError('组分 ID 不得重复')
        if len({item.name for item in components}) != len(components):
            raise MixtureConstraintError('组分名称不得重复')
        object.__setattr__(self, 'components', components)
        object.__setattr__(self, 'response_names',
                           _string_tuple(self.response_names, '响应名称'))
        if self.design_type not in MIXTURE_TYPES:
            raise MixtureConstraintError('design_type 必须是三类混料设计之一')
        if self.design_type == 'simplex_lattice':
            if isinstance(self.degree, bool) or not isinstance(self.degree, Integral) \
                    or not 1 <= int(self.degree) <= 10:
                raise MixtureConstraintError('Simplex Lattice 阶数必须为 1–10')
            object.__setattr__(self, 'degree', int(self.degree))
        elif self.degree is not None:
            raise MixtureConstraintError('该设计类型不接受阶数')
        if self.design_type == 'simplex_centroid' and len(components) > 13:
            raise MixtureConstraintError('Simplex Centroid 最多支持 13 个组分')
        if self.design_type == 'extreme_vertices' and len(components) > 8:
            raise MixtureConstraintError('Extreme Vertices 当前支持 2–8 个组分')
        process = tuple(self.process_variables) if isinstance(
            self.process_variables, (tuple, list)) else ()
        amount = tuple(self.amount_variables) if isinstance(
            self.amount_variables, (tuple, list)) else ()
        if any(not isinstance(item, VariableSpec) or item.role != 'process'
               for item in process):
            raise MixtureConstraintError('过程变量定义无效')
        if any(not isinstance(item, VariableSpec) or item.role != 'amount'
               for item in amount):
            raise MixtureConstraintError('总量变量定义无效')
        if len(amount) > 1:
            raise MixtureConstraintError('当前仅支持一个总量变量')
        if len(process) > 6:
            raise MixtureConstraintError('过程变量最多支持 6 个')
        ids = [item.component_id for item in components]
        ids += [item.variable_id for item in (*process, *amount)]
        if len(set(ids)) != len(ids):
            raise MixtureConstraintError('组分与变量 ID 不得重复')
        names = [item.name for item in components]
        names += [item.name for item in (*process, *amount)]
        if len(set(names)) != len(names):
            raise MixtureConstraintError('组分与变量名称不得重复')
        object.__setattr__(self, 'process_variables', process)
        object.__setattr__(self, 'amount_variables', amount)
        settings = dict(self.amount_settings)
        if set(settings) != {item.variable_id for item in amount}:
            raise MixtureConstraintError('总量设定必须覆盖且仅覆盖全部总量变量')
        for variable in amount:
            value = settings[variable.variable_id]
            if isinstance(value, bool) or not isinstance(value, (int, float)) \
                    or not math.isfinite(value) or not variable.low <= value <= variable.high:
                raise MixtureConstraintError(f'总量 {variable.variable_id} 设定超出声明范围')
        object.__setattr__(self, 'amount_settings',
                           tuple((variable.variable_id, float(settings[variable.variable_id]))
                                 for variable in amount))
        constraints = tuple(self.linear_constraints) if isinstance(
            self.linear_constraints, (tuple, list)) else ()
        component_ids = {item.component_id for item in components}
        for constraint in constraints:
            if not isinstance(constraint, LinearConstraint):
                raise MixtureConstraintError('线性约束定义无效')
            if not set(constraint.coefficients) <= component_ids:
                raise MixtureConstraintError('线性约束含未知组分')
        object.__setattr__(self, 'linear_constraints', constraints)
        if isinstance(self.seed, bool) or not isinstance(self.seed, Integral):
            raise MixtureConstraintError('随机 seed 必须是整数')
        object.__setattr__(self, 'seed', int(self.seed))
        lower = sum(item.lower for item in components)
        upper = sum(item.upper for item in components)
        if lower > 1 + TOLERANCE:
            raise MixtureConstraintError(f'组分下界之和 {lower:.12g} 大于 1，区域不可行')
        if upper < 1 - TOLERANCE:
            raise MixtureConstraintError(f'组分上界之和 {upper:.12g} 小于 1，区域不可行')

    @property
    def component_ids(self):
        return tuple(item.component_id for item in self.components)

    @property
    def variable_ids(self):
        return tuple(item.variable_id
                     for item in (*self.process_variables, *self.amount_variables))

    def component(self, component_id):
        return next(item for item in self.components
                    if item.component_id == component_id)

    def variable(self, variable_id):
        return next(item for item in (*self.process_variables, *self.amount_variables)
                    if item.variable_id == variable_id)

    def to_dict(self):
        return {
            'schema_version': self.schema_version, 'design_id': self.design_id,
            'design_type': self.design_type, 'degree': self.degree,
            'components': [item.to_dict() for item in self.components],
            'process_variables': [item.to_dict() for item in self.process_variables],
            'amount_variables': [item.to_dict() for item in self.amount_variables],
            'amount_settings': {key: value for key, value in self.amount_settings},
            'linear_constraints': [item.to_dict() for item in self.linear_constraints],
            'response_names': list(self.response_names), 'seed': self.seed,
            'construction_version': self.construction_version,
        }

    @classmethod
    def from_dict(cls, data):
        if not isinstance(data, dict) or set(data) != _SPEC_KEYS:
            raise MixtureConstraintError('混料设计字段无效')
        for key in ('components', 'process_variables', 'amount_variables',
                    'linear_constraints', 'response_names'):
            if not isinstance(data[key], list):
                raise MixtureConstraintError('混料设计列表字段结构无效')
        return cls(
            design_id=data['design_id'],
            components=tuple(ComponentSpec.from_dict(item) for item in data['components']),
            response_names=tuple(data['response_names']),
            design_type=data['design_type'], degree=data['degree'],
            process_variables=tuple(VariableSpec.from_dict(item)
                                    for item in data['process_variables']),
            amount_variables=tuple(VariableSpec.from_dict(item)
                                   for item in data['amount_variables']),
            amount_settings=tuple(sorted(data['amount_settings'].items())),
            linear_constraints=tuple(LinearConstraint.from_dict(item)
                                     for item in data['linear_constraints']),
            seed=data['seed'], schema_version=data['schema_version'],
            construction_version=data['construction_version'])

    def doe_design_spec(self):
        """映射为现有 v4 设计合同；混料语义由本模块单独保存。"""
        factors = []
        for component in self.components:
            factors.append(FactorSpec(component.component_id, component.name,
                                      0.0, 1.0, component.unit))
        for variable in (*self.process_variables, *self.amount_variables):
            factors.append(FactorSpec(variable.variable_id, variable.name,
                                      variable.low, variable.high, variable.unit))
        return DesignSpec(self.design_id, tuple(factors), self.response_names,
                          seed=self.seed, design_type='mixture',
                          construction_version=self.construction_version)

    def column_map(self, *, measured=False):
        return {
            'run_id': '运行ID', 'standard_order': '标准序', 'run_order': '运行序',
            'point_type': '点类型', 'replicate': '重复', 'block': None,
            'factors': {factor_id: f'设定_{factor_id}'
                        for factor_id in (*self.component_ids, *self.variable_ids)},
            'measured_levels': {}, 'responses': 
                {name: f'响应_{name}' for name in self.response_names},
        }


def mixture_rows(frame, spec):
    """按混料合同读取并核验工作表行；响应列只需存在。"""
    if not isinstance(spec, MixtureSpec):
        raise MixtureConstraintError('spec 必须是 MixtureSpec')
    columns = spec.column_map()
    required = ['运行ID', '标准序', '运行序', '点类型', '重复']
    required += list(columns['factors'].values())
    required += list(columns['responses'].values())
    for name in required:
        if name not in frame.columns or list(frame.columns).count(name) != 1:
            raise MixtureConstraintError(f'混料工作表缺少列 {name} 或列名重复')
    if len(frame) < 1:
        raise MixtureConstraintError('混料工作表没有运行')
    rows, seen = [], set()
    for position, (_, row) in enumerate(frame.iterrows()):
        run_id = row['运行ID']
        if isinstance(run_id, bool) or not isinstance(run_id, (str, Integral)):
            raise MixtureConstraintError('运行ID 必须是字符串或整数')
        key = (type(run_id).__name__, run_id)
        if key in seen:
            raise MixtureConstraintError('运行ID 不得重复')
        seen.add(key)
        proportions = []
        for component in spec.components:
            value = row[f'设定_{component.component_id}']
            if isinstance(value, bool) or not isinstance(value, (int, float)) \
                    or not math.isfinite(value):
                raise MixtureConstraintError('组分比例必须是有限数值')
            proportions.append(float(value))
        proportions = normalize_proportions(spec.components, proportions)
        check_point(spec.components, spec.linear_constraints, proportions)
        settings = {component.component_id: value
                    for component, value in zip(spec.components, proportions)}
        for variable in (*spec.process_variables, *spec.amount_variables):
            value = row[f'设定_{variable.variable_id}']
            if isinstance(value, bool) or not isinstance(value, (int, float)) \
                    or not math.isfinite(value):
                raise MixtureConstraintError(f'变量 {variable.variable_id} 必须是有限数值')
            if not variable.low - TOLERANCE <= value <= variable.high + TOLERANCE:
                raise MixtureConstraintError(
                    f'变量 {variable.variable_id} 超出声明范围')
            settings[variable.variable_id] = float(value)
        rows.append({'position': position, 'run_id': run_id,
                     'settings': settings, 'proportions': proportions, 'row': row})
    return rows


def input_fingerprint(frame, spec):
    """设计输入摘要：行、组分量、过程/总量与约束变化都会使旧模型失效。"""
    rows = mixture_rows(frame, spec)
    payload = {
        'spec': spec.to_dict(),
        'columns': [str(name) for name in frame.columns],
        'runs': [{'run_id': str(item['run_id']),
                  'settings': {key: item['settings'][key] for key in sorted(item['settings'])}}
                 for item in rows],
    }
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True,
                                     separators=(',', ':')).encode('utf-8')).hexdigest()


def mixture_metadata(frame, spec):
    return {'schema_version': MIXTURE_SCHEMA_VERSION, 'spec': spec.to_dict(),
            'worksheet': {'row_count': len(frame),
                          'input_fingerprint': input_fingerprint(frame, spec)}}


def restore_mixture(frame, metadata):
    """严格验证混料元数据、行映射与设计输入摘要。"""
    if not isinstance(metadata, dict) or set(metadata) != _META_KEYS:
        raise MixtureConstraintError('混料元数据结构无效')
    if metadata['schema_version'] != MIXTURE_SCHEMA_VERSION:
        raise MixtureConstraintError('未知混料元数据 schema_version')
    spec = MixtureSpec.from_dict(metadata['spec'])
    worksheet = metadata['worksheet']
    if not isinstance(worksheet, dict) or set(worksheet) != {
            'row_count', 'input_fingerprint'}:
        raise MixtureConstraintError('混料工作表映射结构无效')
    if worksheet['row_count'] != len(frame):
        raise MixtureConstraintError('混料工作表行数已变化')
    fingerprint = worksheet['input_fingerprint']
    if not isinstance(fingerprint, str) or len(fingerprint) != 64:
        raise MixtureConstraintError('混料输入摘要无效')
    if input_fingerprint(frame, spec) != fingerprint:
        raise MixtureConstraintError('混料设计输入、组分约束或运行映射已变化')
    return spec, mixture_rows(frame, spec)


def validate_mixture_metadata(frame, metadata):
    spec, _ = restore_mixture(frame, metadata)
    return mixture_metadata(frame, spec)


def mixture_model_config(frame, metadata, response, degree, terms):
    """保存最近一次混料分析模型，供重开/复制后恢复。"""
    spec, _ = restore_mixture(frame, metadata)
    from doe_mixture_model import MixtureTermModel
    model = MixtureTermModel(spec, terms, degree)
    if response not in spec.response_names:
        raise MixtureConstraintError('模型响应不属于该混料设计')
    return {'response': response, 'degree': int(model.degree),
            'terms': list(model.terms),
            'input_fingerprint': input_fingerprint(frame, spec)}


def restore_mixture_model(frame, metadata, config):
    """验证最近模型仍对应当前混料输入；返回 response/degree/terms。"""
    spec, _ = restore_mixture(frame, metadata)
    if not isinstance(config, dict) or set(config) != _MODEL_KEYS:
        raise MixtureConstraintError('混料模型配置结构无效')
    if config['input_fingerprint'] != input_fingerprint(frame, spec):
        raise MixtureConstraintError('混料设计输入已变化，旧模型配置失效')
    from doe_mixture_model import MixtureTermModel
    degree = config['degree']
    if isinstance(degree, bool) or not isinstance(degree, int) or not 1 <= degree <= 3:
        raise MixtureConstraintError('混料模型阶次无效')
    terms = config['terms']
    if not isinstance(terms, list):
        raise MixtureConstraintError('混料模型项字段无效')
    model = MixtureTermModel(spec, tuple(terms), degree)
    if config['response'] not in spec.response_names:
        raise MixtureConstraintError('混料模型响应无效')
    return config['response'], degree, model.terms
