import ast
import json
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock


def _load_minijmp_pre(monkeypatch):
    import matplotlib

    monkeypatch.setattr(matplotlib, 'use', lambda *args, **kwargs: None)
    from modified_app import Minijmp_pre
    return Minijmp_pre


def test_minijmp_config_migrates_legacy_recent_paths(tmp_path, monkeypatch):
    minijmp_pre = _load_minijmp_pre(monkeypatch)
    config = tmp_path / 'app.json'
    config.write_text(json.dumps({
        'recent': [r'C:\Users\Alice\private.dexpl'],
        'other_option': 'keep',
    }), encoding='utf-8')
    app = object.__new__(minijmp_pre)
    app.configpath = str(tmp_path)

    minijmp_pre.loadAppOptions(app)

    saved = json.loads(config.read_text(encoding='utf-8'))
    assert saved == {'recent': [], 'other_option': 'keep'}


def test_minijmp_config_never_saves_recent_paths(tmp_path, monkeypatch):
    minijmp_pre = _load_minijmp_pre(monkeypatch)
    app = object.__new__(minijmp_pre)
    app.configpath = str(tmp_path)
    app.appoptions = {'recent': [r'C:\Users\Alice\private.dexpl'], 'other_option': 'keep'}

    minijmp_pre.saveAppOptions(app)

    saved = json.loads((tmp_path / 'app.json').read_text(encoding='utf-8'))
    assert saved == {'recent': [], 'other_option': 'keep'}


def test_minijmp_error_log_redacts_paths_and_rotates(tmp_path, monkeypatch):
    minijmp_pre = _load_minijmp_pre(monkeypatch)
    from pandastable_local import app as app_module
    from pandastable_local import core

    logger = logging.Logger('minijmp-p2-test')
    monkeypatch.setattr(app_module.logging, 'getLogger', lambda *args: logger)
    # start_logging imports the path from core, matching the production call.
    monkeypatch.setattr(core, 'logfile', str(tmp_path / 'error.log'))

    minijmp_pre.start_logging(SimpleNamespace())

    handler = logger.handlers[0]
    assert isinstance(handler, RotatingFileHandler)
    assert handler.maxBytes == 1024 * 1024
    assert handler.backupCount == 3
    minijmp_pre.start_logging(SimpleNamespace())
    assert len(logger.handlers) == 1
    record = logging.LogRecord(
        'minijmp-p2-test', logging.ERROR, __file__, 1,
        "open 'C:\\Users\\Alice Smith\\private.csv' and '/home/Alice/private.csv' failed; "
        'password=hunter2; server=pi.internal; user=alice; '
        'endpoint=https://alice:secret@pi.example/data',
        (), None)
    handler.emit(record)
    handler.flush()
    redacted = (tmp_path / 'error.log').read_text(encoding='utf-8')
    assert '[path]' in redacted
    assert '[redacted]' in redacted
    handler.maxBytes = 220
    for index in range(8):
        handler.emit(logging.LogRecord(
            'minijmp-p2-test', logging.ERROR, __file__, 1,
            f'error {index}: ' + 'x' * 80, (), None))
    handler.close()

    logs = list(tmp_path.glob('error.log*'))
    contents = '\n'.join(path.read_text(encoding='utf-8') for path in logs)
    assert len(logs) <= 4
    assert 'C:\\Users\\Alice Smith' not in contents
    assert '/home/Alice/private.csv' not in contents
    assert 'hunter2' not in contents
    assert 'pi.internal' not in contents
    assert 'user=alice' not in contents
    assert 'alice:secret@' not in contents


def test_minijmp_plugin_hooks_do_not_scan_install_or_load(monkeypatch):
    minijmp_pre = _load_minijmp_pre(monkeypatch)
    from pandastable_local import app as app_module
    from pandastable_local import plugin

    app = object.__new__(minijmp_pre)
    scan = Mock(side_effect=AssertionError('plugin scan called'))
    picker = Mock(side_effect=AssertionError('plugin picker called'))
    monkeypatch.setattr(plugin, 'init_plugin_system', scan)
    monkeypatch.setattr(app_module.filedialog, 'askopenfilename', picker)

    class ExternalPlugin:
        def __init__(self):
            raise AssertionError('external plugin instantiated')

    minijmp_pre.discoverPlugins(app)
    minijmp_pre.installPlugin(app)
    minijmp_pre.loadPlugin(app, ExternalPlugin)

    scan.assert_not_called()
    picker.assert_not_called()


def test_windows_entry_has_no_legacy_plugin_menu():
    source = Path(__file__).resolve().parents[1] / 'code' / 'MiniJMP.py'
    tree = ast.parse(source.read_text(encoding='utf-8'))
    app_class = next(node for node in tree.body
                     if isinstance(node, ast.ClassDef) and node.name == 'Minijmp')
    menu = next(node for node in app_class.body
                if isinstance(node, ast.FunctionDef) and node.name == 'createMenuBar')

    assert 'Plugins' not in ast.get_source_segment(source.read_text(encoding='utf-8'), menu)
