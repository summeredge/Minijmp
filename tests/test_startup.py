import ast
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock

import pytest


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def startup(monkeypatch):
    spec = importlib.util.spec_from_file_location('minijmp_start', ROOT / 'start.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    popup = Mock()
    monkeypatch.setattr(module, 'ctypes', SimpleNamespace(
        windll=SimpleNamespace(user32=SimpleNamespace(MessageBoxW=popup))))
    return module, popup


def test_launch_uses_current_interpreter_without_changing_parent_cwd(startup, monkeypatch, tmp_path):
    module, popup = startup
    launch = Mock(return_value=SimpleNamespace(returncode=0, stderr=''))
    monkeypatch.setattr(module.subprocess, 'run', launch)
    monkeypatch.chdir(tmp_path)
    assert module.main() == 0
    launch.assert_called_once_with(
        [sys.executable, str(ROOT / 'code' / 'MiniJMP.py')],
        cwd=ROOT / 'code', stderr=subprocess.PIPE, text=True, errors='replace')
    assert Path.cwd() == tmp_path
    popup.assert_not_called()


@pytest.mark.parametrize('stderr', ['Traceback: missing dependency\n', ''])
def test_child_failure_returns_code_and_reports_error(startup, monkeypatch, capsys, stderr):
    module, popup = startup
    monkeypatch.setattr(module, 'os', SimpleNamespace(name='nt'))
    launch = Mock(return_value=SimpleNamespace(returncode=7, stderr=stderr))
    monkeypatch.setattr(module.subprocess, 'run', launch)
    assert module.main() == 7
    launch.assert_called_once()
    message = popup.call_args.args[1]
    assert 'code 7' in message
    assert sys.executable in message
    assert stderr in message
    assert stderr in capsys.readouterr().err


def test_os_error_is_visible_and_does_not_retry_another_interpreter(startup, monkeypatch, capsys):
    module, popup = startup
    monkeypatch.setattr(module, 'os', SimpleNamespace(name='nt'))
    launch = Mock(side_effect=FileNotFoundError('missing executable'))
    monkeypatch.setattr(module.subprocess, 'run', launch)
    assert module.main() == 1
    launch.assert_called_once()
    assert 'missing executable' in capsys.readouterr().err
    assert 'missing executable' in popup.call_args.args[1]


def test_failure_without_console_still_has_popup(startup, monkeypatch):
    module, popup = startup
    monkeypatch.setattr(module, 'os', SimpleNamespace(name='nt'))
    monkeypatch.setattr(module.sys, 'stderr', None)
    monkeypatch.setattr(module.subprocess, 'run', Mock(
        return_value=SimpleNamespace(returncode=1, stderr='startup traceback')))
    assert module.main() == 1
    assert 'startup traceback' in popup.call_args.args[1]


@pytest.mark.parametrize('returncode', [0, 7, 1])
def test_real_launcher_with_chinese_path_and_unrelated_cwd(tmp_path, returncode):
    project = tmp_path / '中文 project'
    code_dir = project / 'code'
    code_dir.mkdir(parents=True)
    shutil.copyfile(ROOT / 'start.py', project / 'start.py')
    (code_dir / 'MiniJMP.py').write_text(
        'import os, sys\n'
        'print(sys.executable)\n'
        'print(os.getcwd())\n'
        + ('import minijmp_missing_test_dependency\n' if returncode == 1 else '')
        + f'sys.exit({returncode})\n', encoding='utf-8')
    # Keep the native error dialog noninteractive while exercising the real child process.
    wrapper = (
        'import runpy, sys, types; '
        'sys.modules["ctypes"] = types.SimpleNamespace(windll=types.SimpleNamespace('
        'user32=types.SimpleNamespace(MessageBoxW=lambda *args: print("ERROR_DIALOG", args[1])))); '
        'runpy.run_path(sys.argv[1], run_name="__main__")')
    env = dict(os.environ, PYTHONUTF8='1')
    result = subprocess.run(
        [sys.executable, '-c', wrapper, str(project / 'start.py')],
        cwd=tmp_path, env=env, capture_output=True, encoding='utf-8', timeout=20)
    assert result.returncode == returncode, result.stderr
    assert sys.executable in result.stdout
    assert str(code_dir) in result.stdout
    assert ('ERROR_DIALOG' in result.stdout) == (returncode != 0 and os.name == 'nt')
    if returncode == 1:
        assert 'ModuleNotFoundError' in result.stderr
        if os.name == 'nt':
            assert 'ModuleNotFoundError' in result.stdout


@pytest.mark.skipif(os.name != 'nt', reason='Windows launchers')
@pytest.mark.parametrize('launcher', ['win_start.bat', 'win_start_no_cmd_win.vbs'])
@pytest.mark.parametrize('returncode', [0, 7])
def test_windows_launchers_resolve_their_directory_and_propagate_exit_code(tmp_path, launcher, returncode, request):
    project = tmp_path / '中文 project'
    project.mkdir()
    for name in ['win_start.bat', 'win_start_no_cmd_win.vbs']:
        shutil.copyfile(ROOT / name, project / name)
    (project / 'start.py').write_text(f'import sys\nsys.exit({returncode})\n', encoding='utf-8')
    # The BAT resolves .venv beside itself, independently of PATH.
    environment = project / '.venv'
    subprocess.run(
        ['cmd.exe', '/d', '/c', 'mklink', '/J', str(environment), sys.prefix],
        capture_output=True, check=True, timeout=20)
    request.addfinalizer(environment.rmdir)
    if launcher.endswith('.vbs'):
        command = ['cscript.exe', '//nologo', str(project / launcher)]
    else:
        command = ['cmd.exe', '/d', '/c', str(project / launcher)]
    result = subprocess.run(command, cwd=tmp_path, capture_output=True, timeout=20)
    assert result.returncode == returncode, result.stderr


def test_windows_launchers_do_not_update_code_or_request_elevation():
    text = '\n'.join((ROOT / name).read_text().lower() for name in [
        'start.py', 'win_start.bat', 'win_start_no_cmd_win.vbs'])
    assert 'git pull' not in text
    assert 'runas' not in text


def test_main_icon_uses_embedded_resource(monkeypatch, tmp_path):
    path = ROOT / 'code' / 'MiniJMP.py'
    tree = ast.parse(path.read_text(encoding='utf-8'))
    main = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'main')
    root = Mock()
    icon = Mock()
    create_icon = Mock(return_value=icon)
    namespace = dict(__file__=str(path), Tk=Mock(return_value=root), Minijmp=Mock(),
                     create_icon_image=create_icon)
    monkeypatch.chdir(tmp_path)
    exec(compile(ast.Module(body=[main], type_ignores=[]), str(path), 'exec'), namespace)
    namespace['main']()
    create_icon.assert_called_once_with(root)
    root.iconphoto.assert_called_once_with(True, icon)


def test_about_icon_uses_embedded_resource():
    path = ROOT / 'code' / 'modified_app.py'
    tree = ast.parse(path.read_text(encoding='utf-8'))
    about = next(node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name == 'about')
    image = next(node for node in ast.walk(about) if isinstance(node, ast.Call)
                 and isinstance(node.func, ast.Name) and node.func.id == 'create_icon_image')
    assert len(image.args) == 1
    assert isinstance(image.args[0], ast.Name) and image.args[0].id == 'abwin'


def test_help_resource_uses_module_directory_and_preserves_unknown_key_behavior(monkeypatch, tmp_path):
    import help_link

    monkeypatch.chdir(tmp_path)
    (tmp_path / 'help.json').write_text('{}', encoding='utf-8')
    data = json.loads((ROOT / 'code' / 'help.json').read_text(encoding='utf-8'))
    assert help_link.help_link('Main Help Menu') == data['Main Help Menu']['link']
    key = 'Stats Summary Multi Datasets'
    assert help_link.help_window(key) == data[key]['window']
    assert help_link.help_link('unknown key') == help_link.DEFAULT_LINK
    assert help_link.help_window('unknown key') == ''


def test_help_resource_reads_utf8_from_chinese_module_path(monkeypatch, tmp_path):
    project = tmp_path / '中文 module'
    project.mkdir()
    source = project / 'help_link.py'
    shutil.copyfile(ROOT / 'code' / 'help_link.py', source)
    data = {'中文帮助': {'link': '中文链接', 'window': '统计说明：均值与标准差'}}
    (project / 'help.json').write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
    monkeypatch.chdir(tmp_path)
    spec = importlib.util.spec_from_file_location('minijmp_help_resource', source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.help_link('中文帮助') == '中文链接'
    assert module.help_window('中文帮助') == '统计说明：均值与标准差'
