"""Schema v3 的独立摘要、旧版本迁移和拒绝规则。"""
from copy import deepcopy
from dataclasses import replace
import hashlib
import json
import gzip
import pickle
from pathlib import Path

import pandas as pd
import pytest

from doe_core import DesignSpec, FactorSpec, restore_design_result, validate_worksheet_metadata, worksheet_metadata
from test_doe_schema_v2 import v1_columns, v1_frame, v1_metadata, v1_spec
from test_doe_persistence import workbook, csv_app


def pb_case():
    reference = pd.read_csv(Path(__file__).parent / 'fixtures/doe_screening_reference/pb/pb12.csv')
    rows = [{'levels': [int(row.X1), int(row.X2), int(row.X3)],
             'point_type': 'factorial', 'replicate': 1, 'block': None}
            for row in reference.itertuples()]
    payload = {'design_type': 'plackett_burman', 'factors': ['A', 'B', 'C'], 'runs': rows}
    digest = hashlib.sha256(json.dumps(payload, ensure_ascii=False, allow_nan=False,
                                      sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    identity = {'construction_id': 'pb12.v1', 'source_kind': 'publication',
                'source_id': 'nist.pb12', 'matrix_sha256': digest}
    spec = DesignSpec('pb', tuple(FactorSpec(c, c, -1, 1) for c in 'ABC'), ('Y',),
                      design_type='plackett_burman', screening_matrix=identity)
    frame = pd.DataFrame({'id': range(1, 13), 'std': range(1, 13), 'run': range(1, 13),
                          'type': 'factorial', 'rep': 1,
                          'A': reference.X1, 'B': reference.X2, 'C': reference.X3,
                          'Y': [None] * 12})
    columns = {'run_id': 'id', 'standard_order': 'std', 'run_order': 'run',
               'point_type': 'type', 'replicate': 'rep', 'block': None,
               'factors': {c: c for c in 'ABC'}, 'measured_levels': {}, 'responses': {'Y': 'Y'}}
    return frame, spec, columns


def test_independent_matrix_digest_and_response_update():
    frame, spec, columns = pb_case()
    metadata = worksheet_metadata(frame, spec, columns)
    frame.loc[0, 'Y'] = 42
    assert restore_design_result(frame, metadata).runs[0].responses['Y'] == 42
    frame.loc[0, 'A'] *= -1
    with pytest.raises(ValueError, match='摘要'):
        restore_design_result(frame, metadata)


def test_randomized_row_order_does_not_change_matrix_digest():
    frame, spec, columns = pb_case()
    shuffled = frame.sample(frac=1, random_state=5).reset_index(drop=True)
    shuffled['run'] = range(1, 13)
    assert worksheet_metadata(shuffled, spec, columns)['design']['screening_matrix'] == dict(spec.screening_matrix)


def test_original_v2_fingerprint_is_checked_before_upgrade():
    frame, columns = v1_frame(), v1_columns()
    spec = replace(v1_spec(), schema_version=2)
    metadata = v1_metadata(frame, spec, columns)
    metadata['schema_version'] = 2
    metadata['design'] = spec.to_dict()
    from doe_core import design_from_worksheet, _fingerprint, _normalize_column_map
    metadata['worksheet']['input_fingerprint'] = _fingerprint(
        metadata['design'], _normalize_column_map(columns, spec), design_from_worksheet(frame, spec, columns))
    upgraded = validate_worksheet_metadata(frame, metadata)
    assert upgraded['schema_version'] == 3
    assert upgraded['design']['screening_matrix'] is None
    bad = deepcopy(metadata)
    bad['design']['seed'] = 99
    with pytest.raises(ValueError, match='输入'):
        validate_worksheet_metadata(frame, bad)
    bad = deepcopy(metadata)
    bad['design']['screening_matrix'] = None
    with pytest.raises(ValueError, match='字段'):
        validate_worksheet_metadata(frame, bad)


def test_unknown_source_and_digest_are_rejected():
    frame, spec, columns = pb_case()
    metadata = worksheet_metadata(frame, spec, columns)
    for key, value in [('source_id', 'unknown'), ('matrix_sha256', '0' * 64)]:
        bad = deepcopy(metadata)
        bad['design']['screening_matrix'][key] = value
        with pytest.raises(ValueError):
            restore_design_result(frame, bad)


def test_changed_matrix_is_rejected_even_with_recomputed_digest():
    frame, spec, columns = pb_case()
    frame.loc[0, 'A'] *= -1
    reference = pd.read_csv(Path(__file__).parent / 'fixtures/doe_screening_reference/pb/pb12.csv')
    reference.loc[0, 'X1'] *= -1
    rows = [{'levels': [int(row.X1), int(row.X2), int(row.X3)],
             'point_type': 'factorial', 'replicate': 1, 'block': None}
            for row in reference.itertuples()]
    payload = {'design_type': 'plackett_burman', 'factors': ['A', 'B', 'C'], 'runs': rows}
    identity = dict(spec.screening_matrix)
    identity['matrix_sha256'] = hashlib.sha256(json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    with pytest.raises(ValueError, match='构造矩阵'):
        worksheet_metadata(frame, replace(spec, screening_matrix=identity), columns)


def dsd_case(key, filename, count, mixed):
    reference = pd.read_csv(Path(__file__).parent / 'fixtures/doe_screening_reference/dsd' / filename)
    ids = [f'F{i}' for i in range(1, count + 1)]
    factors = tuple(FactorSpec(name, name, -1, 1) for name in ids[:4 if mixed else count])
    if mixed:
        factors += (FactorSpec(ids[-1], ids[-1], None, None, factor_type='categorical', levels=('低', '高')),)
    rows = []
    data = []
    for index, values in enumerate(reference.iloc[:, 1:].itertuples(index=False, name=None)):
        point = ('pseudo_center' if mixed and index >= len(reference) - 2 else
                 'center' if not mixed and index == len(reference) - 1 else 'screening')
        rows.append({'levels': list(values), 'point_type': point, 'replicate': 1, 'block': None})
        row = {'id': index + 1, 'std': index + 1, 'run': index + 1, 'type': point, 'rep': 1, 'Y': None}
        row.update({name: ('低' if value == -1 else '高') if mixed and i == count - 1 else value
                    for i, (name, value) in enumerate(zip(ids, values))})
        data.append(row)
    payload = {'design_type': 'definitive_screening', 'factors': ids, 'runs': rows}
    digest = hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True,
                                      separators=(',', ':')).encode()).hexdigest()
    identity = {'construction_id': key + '.v1', 'source_kind': 'mathematical_construction',
                'source_id': ('jones.' if mixed else 'conference.') + key, 'matrix_sha256': digest}
    spec = DesignSpec('dsd', factors, ('Y',), design_type='definitive_screening', screening_matrix=identity)
    columns = {'run_id': 'id', 'standard_order': 'std', 'run_order': 'run', 'point_type': 'type',
               'replicate': 'rep', 'block': None, 'factors': {name: name for name in ids},
               'measured_levels': {}, 'responses': {'Y': 'Y'}}
    frame = pd.DataFrame(data)
    return frame, spec, columns


@pytest.mark.parametrize('key,filename,count,mixed', [
    ('dsd6', 'dsd_06_cont_13.csv', 6, False),
    ('dsd7', 'dsd_07_cont_17.csv', 7, False),
    ('dsd8', 'dsd_08_cont_17.csv', 8, False),
    ('dsd10', 'dsd_10_cont_21.csv', 10, False),
    ('dsd4c1', 'dsd_04_cont_01_cat_14.csv', 5, True),
])
def test_dsd_fixture_matrix_identity(key, filename, count, mixed):
    frame, spec, columns = dsd_case(key, filename, count, mixed)
    metadata = worksheet_metadata(frame, spec, columns)
    assert len(restore_design_result(frame, metadata).runs) == len(frame)


@pytest.mark.parametrize('kind', ['pb', 'dsd'])
def test_screening_project_save_reopen_and_copy(workbook, tmp_path, kind):
    app, error = workbook
    frame, spec, columns = (pb_case() if kind == 'pb' else
                            dsd_case('dsd4c1', 'dsd_04_cont_01_cat_14.csv', 5, True))
    metadata = worksheet_metadata(frame, spec, columns)
    app.addSheet('Screening', frame, {'doe': metadata})
    app.nb.select(app.sheetframes['Screening'])
    copied = app.copySheet()
    assert copied.doe_metadata == metadata
    path = tmp_path / 'screening.dexpl'
    assert app._save_project(path)
    assert app.load_file(path)
    table = app.sheets['Screening']
    table.model.df.loc[0, 'Y'] = 12.5
    assert restore_design_result(table.model.df, table.doe_metadata).runs[0].responses['Y'] == 12.5
    assert app._save_project(path)
    assert app.load_file(path)
    assert restore_design_result(app.sheets['Screening'].model.df,
                                 app.sheets['Screening'].doe_metadata).runs[0].responses['Y'] == 12.5
    error.assert_not_called()


def test_bad_screening_identity_does_not_replace_workbook(workbook, tmp_path):
    app, error = workbook
    frame, spec, columns = pb_case()
    metadata = worksheet_metadata(frame, spec, columns)
    metadata['design']['screening_matrix']['matrix_sha256'] = '0' * 64
    path = tmp_path / 'invalid.dexpl'
    data = {'DOE': {'table': frame, 'meta': {'doe': metadata}},
            'meta': {'active': 'DOE', 'minijmp': 1}}
    with gzip.open(path, 'wb') as stream:
        pickle.dump(data, stream)
    original = app.table
    names = list(app.sheets)
    assert not app.load_file(path)
    assert app.table is original and list(app.sheets) == names
    error.assert_called_once()


@pytest.mark.parametrize('change', ['row_order', 'column_order', 'run_order', 'replicate', 'point_type', 'factor_map'])
def test_screening_input_or_mapping_changes_invalidate_identity(change):
    frame, spec, columns = pb_case()
    metadata = worksheet_metadata(frame, spec, columns)
    if change == 'row_order':
        frame = frame.iloc[::-1].reset_index(drop=True)
    elif change == 'column_order':
        frame = frame.iloc[:, ::-1]
    elif change == 'run_order':
        frame.loc[0, 'run'], frame.loc[1, 'run'] = 2, 1
    elif change == 'replicate':
        frame.loc[0, 'rep'] = 2
    elif change == 'point_type':
        frame.loc[0, 'type'] = 'center'
    else:
        metadata['column_map']['factors']['A'], metadata['column_map']['factors']['B'] = 'B', 'A'
    with pytest.raises(ValueError):
        restore_design_result(frame, metadata)
