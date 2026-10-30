import copy
from dataclasses import replace
import gzip
import pickle

import pandas as pd
import pytest
from pandas.testing import assert_frame_equal

from doe_mixture import (MixtureSpec, mixture_metadata, restore_mixture,
                         mixture_model_config, restore_mixture_model,
                         validate_mixture_metadata)
from doe_mixture_constraints import ComponentSpec, VariableSpec
from doe_mixture_designs import create_mixture_design
from test_csv_import import csv_app


def full_spec():
    return MixtureSpec('MIX', (ComponentSpec('A', 'A'), ComponentSpec('B', 'B'),
                               ComponentSpec('C', 'C')), ('Y1', 'Y2'),
                       'simplex_centroid', None,
                       process_variables=(VariableSpec('P1', '温度', 20, 40, 'C'),),
                       amount_variables=(VariableSpec('T', '总量', 100, 300, 'g', 'amount'),),
                       amount_settings=(('T', 200),), seed=9)


def test_roles_amount_and_run_ids_survive_roundtrip():
    spec = full_spec()
    frame, meta = create_mixture_design(spec, 2)
    frame['响应_Y1'] = 1.0
    restored, rows = restore_mixture(frame, meta['mixture'])
    assert restored.process_variables[0].role == 'process'
    assert restored.amount_variables[0].role == 'amount'
    assert restored.amount_settings == (('T', 200),)
    assert restored.seed == spec.seed
    assert [item['run_id'] for item in rows] == list(frame['运行ID'])
    assert validate_mixture_metadata(frame, meta['mixture']) == meta['mixture']


def test_tampered_design_inputs_and_bad_metadata_are_rejected():
    spec = full_spec()
    frame, meta = create_mixture_design(spec)
    changed = frame.copy()
    changed.loc[0, '设定_T'] = 250
    with pytest.raises(ValueError):
        restore_mixture(changed, meta['mixture'])
    bad = copy.deepcopy(meta['mixture'])
    bad['schema_version'] = 99
    with pytest.raises(ValueError, match='schema'):
        restore_mixture(frame, bad)
    bad = copy.deepcopy(meta['mixture'])
    bad['spec']['components'][0]['lower'] = 0.9
    with pytest.raises(ValueError):
        restore_mixture(frame, bad)
    bad = copy.deepcopy(meta['mixture'])
    bad['improvement_lineage'] = {}
    with pytest.raises(ValueError, match='结构'):
        restore_mixture(frame, bad)
    bad = copy.deepcopy(meta['mixture'])
    bad['schema_version'] = True
    with pytest.raises(ValueError, match='schema'):
        restore_mixture(frame, bad)


def test_bad_metadata_does_not_overwrite_current_workbook(csv_app, monkeypatch):
    app, error = csv_app
    monkeypatch.setattr('doe_mixture_dialog.messagebox.showerror', error)
    from doe_mixture_dialog import CreateMixtureDesign
    create = CreateMixtureDesign(app)
    create.create()
    table = app.getCurrentTable()
    original = table.mixture_metadata
    bad = copy.deepcopy(original)
    bad['spec']['components'][0]['lower'] = 0.9
    with pytest.raises(ValueError):
        app.loadMeta(table, {'mixture': bad})
    assert table.mixture_metadata == original
    error.assert_not_called()


def test_v2_bad_amount_contract_does_not_replace_live_workbook(csv_app):
    app, error = csv_app
    spec = MixtureSpec(
        'MIX-V2', (ComponentSpec('A', 'A'), ComponentSpec('B', 'B')), ('Y',),
        'simplex_lattice', 1,
        amount_variables=(VariableSpec('T', '总量', 100, 200, role='amount'),),
        amount_settings=(('T', 100),), construction_version='v2')
    frame, metadata = create_mixture_design(spec, amount_levels=(100, 200))
    table = app.addSheet('Mixture v2', frame, metadata)
    original = table.mixture_metadata
    bad_spec = replace(spec, amount_settings=(('T', 150),))
    bad_metadata = mixture_metadata(frame, bad_spec)
    with pytest.raises(ValueError, match='默认总量设定必须是一个实际总量水平'):
        app.loadMeta(table, {'mixture': bad_metadata})
    assert table.mixture_metadata == original
    error.assert_not_called()


def test_model_terms_config_roundtrip_and_stale_rejection():
    spec = full_spec()
    frame, meta = create_mixture_design(spec)
    config = mixture_model_config(frame, meta['mixture'], 'Y1', 2,
                                  ('A', 'B', 'C', 'A*B'))
    response, degree, terms = restore_mixture_model(frame, meta['mixture'], config)
    assert (response, degree) == ('Y1', 2)
    assert terms == ('A', 'B', 'C', 'A*B')
    changed = frame.copy()
    changed.loc[0, '设定_T'] = 250
    with pytest.raises(ValueError, match='失效|已变化'):
        restore_mixture_model(changed, meta['mixture'], config)


def test_schema2_survives_save_load_and_single_sheet_copy_without_parent_sheet(
        csv_app):
    from test_doe_mixture_improve import _improve

    app, _ = csv_app
    _, _, _, (frame, doe, mixture, model, _) = _improve()
    table = app.addSheet('Mixture Improve', frame,
                         {'doe': doe, 'mixture': mixture,
                          'mixture_model': model})
    saved = app.saveMeta(table)
    assert saved['mixture']['schema_version'] == 2
    assert saved['mixture']['improvement_lineage'] == mixture['improvement_lineage']
    app.loadMeta(table, saved)
    assert table.mixture_metadata == mixture

    copied = app.copySheet()
    assert copied.mixture_metadata == table.mixture_metadata
    assert copied.mixture_metadata is not table.mixture_metadata
    assert copied.mixture_metadata['improvement_lineage'] is not \
        table.mixture_metadata['improvement_lineage']
    restored, rows = restore_mixture(
        copied.model.df, copied.mixture_metadata, copied.doe_metadata)
    assert restored.design_id == mixture['spec']['design_id']
    assert [row['run_id'] for row in rows] == copied.model.df['运行ID'].tolist()


def test_bad_schema2_dexpl_does_not_replace_a_healthy_workbook(
        csv_app, monkeypatch, tmp_path):
    from test_doe_mixture_improve import _improve

    app, error = csv_app
    monkeypatch.setattr('worksheets.messagebox.showerror', error)
    monkeypatch.setattr('worksheets.messagebox.askyesno', lambda *a, **k: True)
    _, _, _, (frame, doe, mixture, model, _) = _improve()
    bad = copy.deepcopy(mixture)
    bad['improvement_lineage']['current_logdet'] += 1
    path = tmp_path / 'bad-schema2.dexpl'
    data = {
        '健康工作表': {'table': pd.DataFrame({'x': [1]})},
        '坏改善设计': {'table': frame,
                       'meta': {'doe': doe, 'mixture': bad,
                                'mixture_model': model}},
        'meta': {'active': '健康工作表', 'minijmp': 1},
    }
    with gzip.open(path, 'wb') as stream:
        pickle.dump(data, stream)

    original_table = app.table
    original_names = list(app.sheets)
    original_frame = original_table.model.df.copy(deep=True)
    assert not app.load_file(path)
    assert app.table is original_table
    assert list(app.sheets) == original_names
    assert_frame_equal(app.table.model.df, original_frame)
    error.assert_called_once()
