import gzip
import json
import pickle
from types import SimpleNamespace
from unittest.mock import Mock

import pandas as pd

import worksheets
from pandastable_local import core_orig


def app_module(monkeypatch):
    import matplotlib

    monkeypatch.setattr(matplotlib, 'use', lambda *args, **kwargs: None)
    from pandastable_local import app
    return app


def test_legacy_app_options_migrate_to_json_after_consent(tmp_path, monkeypatch):
    module = app_module(monkeypatch)
    legacy = tmp_path / 'app.p'
    legacy.write_bytes(pickle.dumps({'recent': ['C:/trusted/project.dexpl']}))
    ask = Mock(return_value=True)
    monkeypatch.setattr(module.messagebox, 'askyesno', ask)
    instance = SimpleNamespace(configpath=str(tmp_path), main=None)
    instance.saveAppOptions = lambda: module.DataExplore.saveAppOptions(instance)

    module.DataExplore.loadAppOptions(instance)

    config = tmp_path / 'app.json'
    assert instance.appoptions == {'recent': ['C:/trusted/project.dexpl']}
    assert json.loads(config.read_text(encoding='utf-8')) == instance.appoptions
    assert legacy.exists()
    ask.assert_called_once()

    monkeypatch.setattr(module.messagebox, 'askyesno', Mock(side_effect=AssertionError))
    restarted = SimpleNamespace(configpath=str(tmp_path), main=None)
    module.DataExplore.loadAppOptions(restarted)
    assert restarted.appoptions == instance.appoptions


def test_declining_legacy_config_never_unpickles(tmp_path, monkeypatch):
    module = app_module(monkeypatch)
    (tmp_path / 'app.p').write_bytes(b'not a pickle')
    monkeypatch.setattr(module.messagebox, 'askyesno', lambda *a, **k: False)
    monkeypatch.setattr(module.pickle, 'load', Mock(side_effect=AssertionError('unpickled')))
    instance = SimpleNamespace(configpath=str(tmp_path), main=None)

    module.DataExplore.loadAppOptions(instance)

    assert instance.appoptions == {'recent': []}
    assert not (tmp_path / 'app.json').exists()


def test_worksheet_cancel_precedes_pickle_load(tmp_path, monkeypatch):
    path = tmp_path / 'project.dexpl'
    path.write_bytes(b'not a pickle')
    monkeypatch.setattr(worksheets.messagebox, 'askyesno', lambda *a, **k: False)
    monkeypatch.setattr(worksheets.pickle, 'load', Mock(side_effect=AssertionError('unpickled')))
    monkeypatch.setattr(worksheets.pd, 'read_pickle', Mock(side_effect=AssertionError('read pickle')))

    assert not worksheets.Worksheets.load_file(SimpleNamespace(main=None), path)


def test_pandastable_project_cancel_preserves_project_before_unpickle(tmp_path, monkeypatch):
    module = app_module(monkeypatch)
    path = tmp_path / 'project.dexpl'
    with gzip.open(path, 'wb') as stream:
        pickle.dump({'sheet': {'table': pd.DataFrame({'x': [1]})}}, stream)
    instance = SimpleNamespace(defaultsavedir=str(tmp_path), main=Mock(),
                               closeProject=Mock(), newProject=Mock())
    monkeypatch.setattr(module.messagebox, 'askyesno', lambda *a, **k: False)
    monkeypatch.setattr(module.pickle, 'load', Mock(side_effect=AssertionError('unpickled')))

    assert module.DataExplore.loadProject(instance, str(path), asksave=True) is None
    instance.closeProject.assert_not_called()
    instance.newProject.assert_not_called()


def test_table_pickle_cancel_precedes_model_load(tmp_path, monkeypatch):
    path = tmp_path / 'table.pickle'
    path.write_bytes(b'not a pickle')
    monkeypatch.setattr(core_orig.messagebox, 'askyesno', lambda *a, **k: False)
    load_model = Mock(side_effect=AssertionError('unpickled'))
    monkeypatch.setattr(core_orig, 'TableModel', load_model)
    table = SimpleNamespace(master=None, currentdir=str(tmp_path), updateModel=Mock())

    core_orig.Table.load(table, str(path))

    load_model.assert_not_called()
    table.updateModel.assert_not_called()


def test_load_pickle_cancel_precedes_dataframe_read(tmp_path, monkeypatch):
    module = app_module(monkeypatch)
    instance = SimpleNamespace(main=None, load_dataframe=Mock())
    monkeypatch.setattr(module.messagebox, 'askyesno', lambda *a, **k: False)
    read_pickle = Mock(side_effect=AssertionError('unpickled'))
    monkeypatch.setattr(module.pd, 'read_pickle', read_pickle)

    module.DataExplore.load_pickle(instance, tmp_path / 'table.pickle')

    read_pickle.assert_not_called()
    instance.load_dataframe.assert_not_called()


def test_trusted_legacy_pickle_still_opens(tmp_path, monkeypatch):
    module = app_module(monkeypatch)
    path = tmp_path / 'table.pickle'
    expected = pd.DataFrame({'x': [1, 2]})
    expected.to_pickle(path)
    instance = SimpleNamespace(main=None, load_dataframe=Mock())
    monkeypatch.setattr(module.messagebox, 'askyesno', lambda *a, **k: True)

    module.DataExplore.load_pickle(instance, str(path))

    result, name = instance.load_dataframe.call_args.args
    pd.testing.assert_frame_equal(result, expected)
    assert name == 'table'
