import copy

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
