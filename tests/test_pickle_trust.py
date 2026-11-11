import gzip
import io
import json
import pickle
import zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from pandas.testing import assert_frame_equal

import worksheets
from pandastable_local import core_orig
from pandastable_local.data import TableModel
from pandastable_local.data_orig import TableModel as OriginalTableModel


def app_module(monkeypatch):
    import matplotlib

    monkeypatch.setattr(matplotlib, 'use', lambda *args, **kwargs: None)
    from pandastable_local import app
    return app


def _create_marker(filename):
    Path(filename).write_text('pickle executed', encoding='utf-8')


class _MarkerPayload:
    def __init__(self, marker):
        self.marker = marker

    def __reduce__(self):
        return _create_marker, (str(self.marker),)


def _legacy_bytes(marker, compressed=False):
    payload = pickle.dumps(_MarkerPayload(marker))
    return gzip.compress(payload) if compressed else payload


@pytest.mark.parametrize(('surface', 'suffix', 'compressed'), [
    ('worksheets', '.dexpl', True),
    ('worksheets', '.pickle', False),
    ('project', '.dexpl', True),
    ('project_pickle', '.pickle', False),
    ('load_pickle', '.pickle', False),
    ('table', '.pickle', False),
])
def test_legacy_pickle_entrypoints_never_execute_or_replace_current_data(
        tmp_path, monkeypatch, surface, suffix, compressed):
    marker = tmp_path / 'executed.txt'
    path = tmp_path / ('legacy' + suffix)
    path.write_bytes(_legacy_bytes(marker, compressed))
    original_file = path.read_bytes()
    current = pd.DataFrame({'keep': [42]})
    current_state = SimpleNamespace(model=SimpleNamespace(df=current),
                                    filename='current.csv', prevdf=current.copy())

    monkeypatch.setattr(worksheets.messagebox, 'askyesno', lambda *a, **k: True)
    monkeypatch.setattr(worksheets.messagebox, 'showerror', Mock())
    if surface == 'worksheets':
        app = SimpleNamespace(
            main=None, defaultsavedir='C:/previous', filename='current.dexpl',
            table=current_state,
            _confirm_discard=Mock(return_value=True), _replace=Mock())
        assert not worksheets.Worksheets.load_file(app, path)
        app._confirm_discard.assert_not_called()
        app._replace.assert_not_called()
        assert app.table is current_state
        assert app.filename == 'current.dexpl'
    else:
        module = app_module(monkeypatch)
        monkeypatch.setattr(module.messagebox, 'askyesno', lambda *a, **k: True)
        monkeypatch.setattr(module.messagebox, 'showerror', Mock())
        if surface in ('project', 'project_pickle'):
            app = SimpleNamespace(
                main=Mock(), defaultsavedir='C:/previous', filename='current.dexpl',
                table=current_state, closeProject=Mock(return_value=True),
                newProject=Mock(), addRecent=Mock(), removeRecent=Mock())
            module.DataExplore.loadProject(app, str(path), asksave=True)
            app.closeProject.assert_not_called()
            app.newProject.assert_not_called()
            assert app.filename == 'current.dexpl'
            assert app.defaultsavedir == 'C:/previous'
        elif surface == 'load_pickle':
            app = SimpleNamespace(main=None, table=current_state, load_dataframe=Mock())
            module.DataExplore.load_pickle(app, str(path))
            app.load_dataframe.assert_not_called()
        else:
            model = SimpleNamespace(df=current)
            table = SimpleNamespace(
                master=None, currentdir=str(tmp_path), model=model,
                filename='current.csv', prevdf=current.copy(), updateModel=Mock(),
                adjustColumnWidths=Mock(), redraw=Mock())
            core_orig.Table.load(table, str(path))
            table.updateModel.assert_not_called()
            assert table.filename == 'current.csv'
            assert_frame_equal(table.prevdf, current)
            assert model.df is current

    assert not marker.exists()
    assert path.read_bytes() == original_file
    assert current_state.model.df is current
    assert_frame_equal(current_state.model.df, current)


@pytest.mark.parametrize('model_type', [OriginalTableModel, TableModel])
def test_table_model_load_rejects_pickle_without_execution_or_mutation(
        tmp_path, model_type):
    marker = tmp_path / 'executed.txt'
    path = tmp_path / 'legacy.pickle'
    path.write_bytes(_legacy_bytes(marker))
    original_file = path.read_bytes()
    current = pd.DataFrame({'keep': [42]})
    model = model_type(current.copy())

    with pytest.raises(ValueError):
        model.load(path)

    assert not marker.exists()
    assert path.read_bytes() == original_file
    assert_frame_equal(model.df, current)


def test_legacy_app_config_is_ignored_and_json_config_remains_readable(tmp_path, monkeypatch):
    module = app_module(monkeypatch)
    marker = tmp_path / 'executed.txt'
    legacy = tmp_path / 'app.p'
    legacy.write_bytes(_legacy_bytes(marker))
    original_file = legacy.read_bytes()
    monkeypatch.setattr(module.messagebox, 'askyesno', Mock(side_effect=AssertionError))
    instance = SimpleNamespace(configpath=str(tmp_path), main=None)

    module.DataExplore.loadAppOptions(instance)

    assert instance.appoptions == {'recent': []}
    assert not marker.exists()
    assert legacy.read_bytes() == original_file
    module.messagebox.askyesno.assert_not_called()

    configured = {'recent': ['C:/trusted/project.dexpl']}
    (tmp_path / 'app.json').write_text(json.dumps(configured), encoding='utf-8')
    restarted = SimpleNamespace(configpath=str(tmp_path), main=None)
    module.DataExplore.loadAppOptions(restarted)
    assert restarted.appoptions == configured
    assert not marker.exists()


def test_embedded_arrow_extension_is_rejected_before_deserialization(tmp_path):
    marker = tmp_path / 'arrow-executed.txt'

    class ProbeType(pa.ExtensionType):
        def __init__(self):
            super().__init__(pa.int64(), 'minijmp-test-probe')

        def __arrow_ext_serialize__(self):
            return b'probe'

        @classmethod
        def __arrow_ext_deserialize__(cls, storage_type, serialized):
            marker.write_text('executed', encoding='utf-8')
            return cls()

    extension = ProbeType()
    pa.register_extension_type(extension)
    try:
        path = tmp_path / 'project.dexpl'
        worksheets.write_project_file(path, {'sheet': {'table': pd.DataFrame({'x': [1]})}})
        with zipfile.ZipFile(path) as archive:
            members = {name: archive.read(name) for name in archive.namelist()}
        array = pa.ExtensionArray.from_storage(extension, pa.array([1]))
        payload = io.BytesIO()
        pq.write_table(pa.table({'column_000000': array}), payload)
        members['worksheets/sheet_001.parquet'] = payload.getvalue()
        with zipfile.ZipFile(path, 'w') as archive:
            for name, content in members.items():
                archive.writestr(name, content)
        assert not marker.exists()

        with pytest.raises(ValueError, match='Arrow'):
            worksheets.read_project_file(path)

        assert not marker.exists()
    finally:
        pa.unregister_extension_type('minijmp-test-probe')


def test_untrusted_column_index_dtype_is_rejected(tmp_path):
    path = tmp_path / 'project.dexpl'
    worksheets.write_project_file(path, {'sheet': {'table': pd.DataFrame({'x': [1]})}})
    with zipfile.ZipFile(path) as archive:
        members = {name: archive.read(name) for name in archive.namelist()}
    manifest = json.loads(members['manifest.json'])
    manifest['sheets'][0]['pandas']['column_indexes'][0]['numpy_type'] = 'untrusted-extension'
    members['manifest.json'] = json.dumps(manifest).encode('utf-8')
    with zipfile.ZipFile(path, 'w') as archive:
        for name, content in members.items():
            archive.writestr(name, content)
    with pytest.raises(ValueError, match='不支持'):
        worksheets.read_project_file(path)


def test_hdf_import_never_calls_pandas_deserializer(tmp_path, monkeypatch):
    marker = tmp_path / 'executed.txt'
    path = tmp_path / 'legacy.hdf5'
    path.write_bytes(_legacy_bytes(marker))
    read = Mock(side_effect=lambda *a, **k: _create_marker(marker))
    monkeypatch.setattr(core_orig.pd, 'read_hdf', read)
    error = Mock()
    monkeypatch.setattr(core_orig.messagebox, 'showerror', error)
    current = pd.DataFrame({'keep': [42]})
    table = SimpleNamespace(master=None, model=SimpleNamespace(df=current), updateModel=Mock())

    assert core_orig.Table.importHDF(table, filename=str(path)) is False

    read.assert_not_called()
    table.updateModel.assert_not_called()
    error.assert_called_once()
    assert table.model.df is current and not marker.exists()


def test_legacy_msgpack_entrypoints_do_not_deserialize(tmp_path, monkeypatch):
    module = app_module(monkeypatch)
    read = Mock(side_effect=AssertionError('unexpected deserialization'))
    monkeypatch.setattr(pd, 'read_msgpack', read, raising=False)
    monkeypatch.setattr(module.messagebox, 'showerror', Mock())
    instance = SimpleNamespace(main=None, load_dataframe=Mock())
    assert module.DataExplore.load_msgpack(instance, str(tmp_path / 'old.mpk')) is False
    instance.load_dataframe.assert_not_called()
    with pytest.raises(ValueError, match='MessagePack'):
        TableModel(pd.DataFrame({'x': [1]})).load(tmp_path / 'old.mpk')
    read.assert_not_called()
