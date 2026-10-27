"""DOE schema v2：旧 v1 工程照常读取，新类型往返，未知版本拒绝。"""
from dataclasses import replace

import pandas as pd
import pytest

import doe_core
from doe_bbd import create_bbd
from doe_core import (DesignSpec, FactorSpec, design_from_worksheet,
                      restore_design_result, validate_worksheet_metadata,
                      worksheet_metadata)


def v1_frame():
    return pd.DataFrame({
        '运行ID': ['R1', 'R2', 'R3', 'R4'],
        '标准序': [1, 2, 3, 4],
        '运行序': [1, 2, 3, 4],
        '点类型': ['factorial'] * 4,
        '重复': [1, 1, 1, 1],
        'A': [10, 10, 20, 20],
        'B': [2, 6, 2, 6],
        'Y': pd.array([1.0, pd.NA, 3.0, 4.0], dtype='Float64'),
    })


def v1_columns():
    return {'run_id': '运行ID', 'standard_order': '标准序', 'run_order': '运行序',
            'point_type': '点类型', 'replicate': '重复', 'block': None,
            'factors': {'A': 'A', 'B': 'B'}, 'measured_levels': {},
            'responses': {'Y': 'Y'}}


def v1_spec():
    spec = DesignSpec('old-project',
                      (FactorSpec('A', 'A', 10, 20), FactorSpec('B', 'B', 2, 6)),
                      ('Y',), seed=5, design_type='two_level_full',
                      schema_version=1)
    assert spec.schema_version == 1
    return spec


def v1_metadata(frame, spec, columns):
    """按 v1 原样构造：设计字典不含 v2 新字段，摘要按该字典计算。"""
    design = spec.to_dict()
    design.pop('ccd_fraction')
    design.pop('block_count')
    result = design_from_worksheet(frame, spec, columns)
    normalized = doe_core._normalize_column_map(columns, spec)
    labels = [doe_core._column_label(label) for label in frame.columns]
    return {
        'schema_version': 1,
        'design': design,
        'column_map': normalized,
        'worksheet': {
            'schema_version': 1,
            'row_count': len(result.runs),
            'column_fingerprint': doe_core._column_fingerprint(labels),
            'run_rows': [{'run_id': run.run_id, 'row': row}
                         for row, run in enumerate(result.runs)],
            'input_fingerprint': doe_core._fingerprint(design, normalized, result),
        },
    }


def test_v1_project_metadata_still_loads_and_keeps_its_values():
    frame, spec, columns = v1_frame(), v1_spec(), v1_columns()
    metadata = v1_metadata(frame, spec, columns)
    result = restore_design_result(frame, metadata)
    assert result.spec.design_type == 'two_level_full'
    # 读入旧工程即升级为当前版本；设计内容保持原值。
    assert result.spec.schema_version == doe_core.DOE_SCHEMA_VERSION == 2
    assert result.spec.design_id == 'old-project'
    assert result.spec.factors[0].low == 10
    assert result.runs[1].responses['Y'] is None
    assert result.runs[2].responses['Y'] == 3.0


def test_v1_metadata_is_upgraded_on_the_next_validation_not_rejected():
    frame, spec, columns = v1_frame(), v1_spec(), v1_columns()
    upgraded = validate_worksheet_metadata(frame, v1_metadata(frame, spec, columns))
    assert upgraded['schema_version'] == 2
    assert upgraded['design']['schema_version'] == 2
    assert restore_design_result(frame, upgraded).spec.design_type == 'two_level_full'


def test_v1_metadata_with_v2_fields_is_rejected():
    frame, spec, columns = v1_frame(), v1_spec(), v1_columns()
    metadata = v1_metadata(frame, spec, columns)
    metadata['design']['block_count'] = 2
    with pytest.raises(ValueError, match='字段无效'):
        restore_design_result(frame, metadata)


@pytest.mark.parametrize('version', [0, 3, 99, '2', None, 2.0, True])
def test_unknown_or_mistyped_schema_versions_are_rejected(version):
    frame, spec, columns = v1_frame(), v1_spec(), v1_columns()
    metadata = v1_metadata(frame, spec, columns)
    metadata['schema_version'] = version
    with pytest.raises(ValueError, match='schema_version'):
        restore_design_result(frame, metadata)


def test_metadata_and_design_versions_must_agree():
    frame, spec, columns = v1_frame(), v1_spec(), v1_columns()
    metadata = v1_metadata(frame, spec, columns)
    metadata['schema_version'] = 2
    with pytest.raises(ValueError, match='版本不一致'):
        restore_design_result(frame, metadata)


def test_v1_spec_cannot_carry_v2_only_features():
    with pytest.raises(ValueError, match='schema v2'):
        DesignSpec('old', (FactorSpec('A', 'A', 0, 1),), ('Y',),
                   design_type='box_behnken', schema_version=1)
    with pytest.raises(ValueError, match='box_behnken 只适用于 schema v2'):
        DesignSpec('old', (FactorSpec('A', 'A', 0, 1),), ('Y',),
                   design_type='box_behnken', schema_version=1)


def test_bbd_roundtrip_is_v2_and_reports_design_type():
    spec = DesignSpec('bbd-v2', tuple(FactorSpec(c, c, -1, 1) for c in 'ABC'),
                      ('Y',), seed=3, design_type='box_behnken')
    frame, metadata = create_bbd(spec)
    assert metadata['schema_version'] == 2
    assert metadata['design']['design_type'] == 'box_behnken'
    restored = restore_design_result(frame, metadata)
    assert restored.spec.design_type == 'box_behnken'


def test_categorical_levels_persist_as_labels_not_numbers():
    spec = DesignSpec('cat', (FactorSpec('A', 'A', -1, 1),
                              FactorSpec('L', '批次', None, None,
                                         factor_type='categorical',
                                         levels=('甲', '乙'))),
                      ('Y',), seed=1, design_type='box_behnken')
    assert spec.factors[1].levels == ('甲', '乙')
    payload = spec.to_dict()
    assert payload['factors'][1]['levels'] == ['甲', '乙']
    assert DesignSpec.from_dict(payload).factors[1].levels == ('甲', '乙')
