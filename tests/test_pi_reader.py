"""Protocol regressions reused from PI-Data-Viewer; no live PI access."""
import json
import logging
import shutil
import subprocess
import traceback
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pandas as pd
import pytest

import pi_reader


def install_fixed_reader(monkeypatch, root):
    """Place PIReader.exe at the fixed <root>/PIReader location."""
    reader_dir = root / "PIReader"
    reader_dir.mkdir(exist_ok=True)
    executable = reader_dir / "PIReader.exe"
    executable.write_bytes(b"test executable")
    monkeypatch.setattr(pi_reader, "application_root", lambda: root)
    return executable


@pytest.mark.parametrize("mode", ["source", "frozen"])
def test_executable_is_fixed_to_application_root(monkeypatch, tmp_path, mode):
    source_root = tmp_path / "repo"
    (source_root / "code").mkdir(parents=True)
    executable = install_fixed_reader(monkeypatch, source_root)
    if mode == "frozen":
        install = tmp_path / "MiniJMP-V1.0"
        install.mkdir()
        frozen_exe = install / "MiniJMP.exe"
        frozen_exe.write_bytes(b"MZ")
        reader = install_fixed_reader(monkeypatch, install)
        monkeypatch.setattr(pi_reader.sys, "frozen", True, raising=False)
        monkeypatch.setattr(pi_reader.sys, "executable", str(frozen_exe))
        executable = reader
    else:
        monkeypatch.delattr(pi_reader.sys, "frozen", raising=False)
        monkeypatch.setattr(pi_reader, "__file__", str(source_root / "code" / "pi_reader.py"))

    assert pi_reader._executable_path() == executable.resolve()


def test_environment_and_config_neighbor_cannot_replace_executable(
        monkeypatch, tmp_path):
    fixed = install_fixed_reader(monkeypatch, tmp_path)
    config = tmp_path / "config.txt"
    config.write_text("Server=1", encoding="utf-8")
    rogue = tmp_path / "PIReader.exe"
    rogue.write_bytes(b"rogue")
    monkeypatch.setenv("PI_READER_EXE", str(rogue))
    response = {"columns": ["Timestamp", "A"], "data": [["2026-01-01", 1]]}
    run = Mock(return_value=subprocess.CompletedProcess([], 0, json.dumps(response), ""))
    monkeypatch.setattr(pi_reader.subprocess, "run", run)

    pi_reader.read_pi_data(["A"], "*-1h", "*", config_path=str(config))

    assert run.call_args.args[0][0] == str(fixed.resolve())
    assert rogue.read_bytes() == b"rogue"


def test_missing_fixed_executable_reports_component_and_never_falls_back(
        monkeypatch, tmp_path):
    monkeypatch.setattr(pi_reader, "application_root", lambda: tmp_path)
    config = tmp_path / "config.txt"
    config.write_text("Server=1", encoding="utf-8")
    # Tempting fallbacks that must never run.
    (tmp_path / "PIReader.exe").write_bytes(b"rogue")
    run = Mock()
    monkeypatch.setattr(pi_reader.subprocess, "run", run)

    with pytest.raises(FileNotFoundError, match="程序组件缺失"):
        pi_reader.search_pi_tags("A*", config_path=str(config))
    run.assert_not_called()


@pytest.mark.parametrize("platform", ["nt", "posix"])
@pytest.mark.parametrize("operation", ["search", "query"])
@pytest.mark.parametrize("outcome", ["success", "failure", "timeout"])
def test_pi_subprocess_flags_and_outcomes(monkeypatch, tmp_path, platform, operation, outcome):
    config = tmp_path / "config.txt"
    config.write_text("test config", encoding="utf-8")
    install_fixed_reader(monkeypatch, tmp_path)
    monkeypatch.setattr(pi_reader, "os", SimpleNamespace(name=platform))
    if platform == "nt":
        monkeypatch.setattr(subprocess, "CREATE_NO_WINDOW", 0x08000000, raising=False)
    else:
        monkeypatch.delattr(subprocess, "CREATE_NO_WINDOW", raising=False)

    def fake_run(command, **kwargs):
        assert kwargs == {
            **({"input": "TAG_A\n"} if operation == "query" else {}),
            "capture_output": True, "text": True, "encoding": "utf-8",
            "errors": "strict", "check": False,
            "timeout": pi_reader.PI_READER_TIMEOUT_SECONDS,
            "creationflags": 0x08000000 if platform == "nt" else 0,
        }
        if outcome == "timeout":
            raise subprocess.TimeoutExpired(command, kwargs["timeout"])
        payload = ({"tags": ["TAG_A"]} if operation == "search" else
                   {"columns": ["Timestamp", "TAG_A"], "data": [["2024-01-01", 1.25]]})
        return subprocess.CompletedProcess(
            command, 1 if outcome == "failure" else 0,
            "reader stdout" if outcome == "failure" else json.dumps(payload),
            "reader stderr" if outcome == "failure" else "",
        )

    monkeypatch.setattr(subprocess, "run", fake_run)

    def invoke():
        paths = {"config_path": config}
        if operation == "search":
            return pi_reader.search_pi_tags("TAG*", **paths)
        return pi_reader.read_pi_data(["TAG_A"], "2024-01-01", "2024-01-02", **paths)

    if outcome == "success":
        result = invoke()
        if operation == "search":
            assert result["tags"] == ["TAG_A"]
        else:
            assert result.iloc[0, 0] == 1.25
    else:
        message = ("搜索超时" if operation == "search" else "查询超时") if outcome == "timeout" else "退出码 1"
        with pytest.raises(RuntimeError, match=message) as error:
            invoke()
        if outcome == "timeout":
            assert error.value.__cause__ is None
            assert error.value.__suppress_context__


@pytest.mark.parametrize('values,expected', [
    (['85.2', None, '1.26'], [85.2, float('nan'), 1.26]),
    ([85.2, None, 1.26], [85.2, float('nan'), 1.26]),
    ([' 1.5 ', '', '-2e2'], [1.5, float('nan'), -200.]),
    ([1, '2', None], [1., 2., float('nan')]),
])
def test_reader_numeric_types(values, expected):
    frame = pi_reader._read_reader_json({
        'columns': ['Timestamp', 'Tag'],
        'data': [[f'2026-10-21 00:0{i}:00', value] for i, value in enumerate(values)]})
    assert pd.api.types.is_numeric_dtype(frame['Tag'])
    pd.testing.assert_series_equal(frame['Tag'].reset_index(drop=True),
                                   pd.Series(expected, name='Tag'))


@pytest.mark.parametrize('values', [
    ['1.5', 'Bad Input', None], ['Shutdown', 'No Data', 'I/O Timeout'],
    ['0.123456789012345678901', '1', None],
    ['9007199254740993', '1.5', None],
    [9007199254740993, None, 1.5],
    ['1e400', '1', None], ['1e-400', '1', None],
    [True, False, None], [None, None, None],
])
def test_reader_preserves_unsafe_columns(values):
    frame = pi_reader._read_reader_json({
        'columns': ['Timestamp', 'Tag'],
        'data': [[f'2026-10-21 00:0{i}:00', value] for i, value in enumerate(values)]})
    assert frame['Tag'].tolist() == values


def test_read_pi_data_uses_pi_reader_json(monkeypatch, tmp_path):
    config_path = tmp_path / "config.txt"
    config_path.write_text("shared PIExport-format config", encoding="utf-8")
    executable = install_fixed_reader(monkeypatch, tmp_path)
    monkeypatch.setenv("PI_CONFIG", str(config_path))

    def fake_run(command, *, input, capture_output, text, encoding, errors, check, timeout, creationflags):
        assert timeout == pi_reader.PI_READER_TIMEOUT_SECONDS
        assert command == [
            str(executable.resolve()),
            "--config",
            str(config_path.resolve()),
            "--tags",
            "-",
            "--start",
            "2024-01-01 00:00:00",
            "--end",
            "2024-01-01 00:02:00",
            "--interval",
            "5m",
        ]
        assert input == "TAG_A\nTAG_B\n"
        assert capture_output is True
        assert text is True
        assert encoding == "utf-8"
        assert errors == "strict"
        return subprocess.CompletedProcess(
            command,
            0,
            json.dumps(
                {
                    "columns": ["Timestamp", "TAG_A", "TAG_B"],
                    "data": [
                        ["2024-01-01 00:00:00", 85.2, 1.25],
                        ["2024-01-01 00:01:00", None, 1.26],
                    ],
                }
            ),
            "",
        )

    monkeypatch.setattr(pi_reader.subprocess, "run", fake_run)

    frame = pi_reader.read_pi_data(
        ["TAG_A", "TAG_A", "TAG_B"],
        datetime(2024, 1, 1),
        "2024-01-01 00:02:00",
        "5m",
    )

    assert isinstance(frame, pd.DataFrame)
    assert isinstance(frame.index, pd.DatetimeIndex)
    assert frame.index.name == "Timestamp"
    assert list(frame.columns) == ["TAG_A", "TAG_B"]
    assert frame.loc[pd.Timestamp("2024-01-01 00:00:00"), "TAG_A"] == 85.2
    assert pd.isna(frame.loc[pd.Timestamp("2024-01-01 00:01:00"), "TAG_A"])


def test_search_pi_tags_returns_matching_names(monkeypatch, tmp_path):
    config_path = tmp_path / "config.txt"
    config_path.write_text("shared PIExport-format config", encoding="utf-8")
    executable = install_fixed_reader(monkeypatch, tmp_path)
    monkeypatch.setenv("PI_CONFIG", str(config_path))

    def fake_run(command, **kwargs):
        assert command == [
            str(executable.resolve()),
            "--config",
            str(config_path.resolve()),
            "--search",
            "--mask",
            "FIC*",
        ]
        assert kwargs["capture_output"] is True
        assert kwargs["text"] is True
        assert kwargs["encoding"] == "utf-8"
        assert kwargs["errors"] == "strict"
        return subprocess.CompletedProcess(
            command,
            0,
            json.dumps({"count": 2, "tags": ["A.PV", "B.PV"]}),
            "",
        )

    monkeypatch.setattr(pi_reader.subprocess, "run", fake_run)

    assert pi_reader.search_pi_tags(" FIC* ") == {
        "tags": ["A.PV", "B.PV"],
        "count": 2,
        "truncated": False,
        "message": "",
    }


def test_search_pi_tags_preserves_truncated_results(monkeypatch, tmp_path):
    config_path = tmp_path / "config.txt"
    config_path.write_text("shared PIExport-format config", encoding="utf-8")
    install_fixed_reader(monkeypatch, tmp_path)
    monkeypatch.setenv("PI_CONFIG", str(config_path))
    tags = [f"TAG_{index}.PV" for index in range(100)]

    monkeypatch.setattr(
        pi_reader.subprocess,
        "run",
        lambda command, **kwargs: subprocess.CompletedProcess(
            command,
            0,
            json.dumps(
                {
                    "count": 100,
                    "tags": tags,
                    "truncated": True,
                    "message": "搜索结果超过限制，请缩小条件",
                }
            ),
            "",
        ),
    )

    result = pi_reader.search_pi_tags("*450*")

    assert result["tags"] == tags
    assert result["count"] == 100
    assert result["truncated"] is True
    assert result["message"] == "搜索结果超过限制，请缩小条件"


def test_search_pi_tags_does_not_turn_truncation_into_an_exception():
    source = Path(pi_reader.__file__).read_text(encoding="utf-8")

    assert 'if payload.get("truncated"):\n        raise RuntimeError' not in source


def test_search_pi_tags_hides_reader_failure(monkeypatch, tmp_path):
    config_path = tmp_path / "config.txt"
    config_path.write_text("shared PIExport-format config", encoding="utf-8")
    install_fixed_reader(monkeypatch, tmp_path)
    monkeypatch.setenv("PI_CONFIG", str(config_path))

    def fake_run(command, **kwargs):
        return subprocess.CompletedProcess(command, 1, "", "PI SDK unavailable")

    monkeypatch.setattr(pi_reader.subprocess, "run", fake_run)

    with pytest.raises(RuntimeError, match="搜索失败（退出码 1）"):
        pi_reader.search_pi_tags("FIC*")


@pytest.mark.parametrize('operation', ['query', 'search'])
@pytest.mark.parametrize('failure', [
    'authentication', 'query', 'timeout', 'json', 'launch', 'encoding', 'timestamp',
])
def test_external_errors_do_not_expose_credentials(
        monkeypatch, tmp_path, caplog, capsys, operation, failure):
    secret = 'Fake-PI-Password-Only-For-Tests!'
    connection = f'UID=test-user;PWD={secret}'
    config = tmp_path / 'config.txt'
    config.write_text('dummy config', encoding='utf-8')
    install_fixed_reader(monkeypatch, tmp_path)

    def fake_run(command, **kwargs):
        assert kwargs['timeout'] == 300
        if failure == 'timeout':
            raise subprocess.TimeoutExpired([connection], 300, output=connection, stderr=secret)
        if failure == 'launch':
            raise OSError(connection)
        if failure == 'encoding':
            raise UnicodeError(connection)
        if failure == 'timestamp':
            payload = {'columns': ['Timestamp', 'A'], 'data': [[connection, 1]]}
            return subprocess.CompletedProcess(command, 0, json.dumps(payload), '')
        if failure == 'json':
            return subprocess.CompletedProcess(command, 0, connection, secret)
        return subprocess.CompletedProcess(command, 1 if failure == 'authentication' else 7,
                                           connection, f'{failure}: {secret}')

    monkeypatch.setattr(pi_reader.subprocess, 'run', fake_run)
    with pytest.raises((RuntimeError, ValueError)) as caught:
        try:
            if operation == 'search':
                pi_reader.search_pi_tags('A*', config_path=config)
            else:
                pi_reader.read_pi_data(['A'], '*-1h', '*', config_path=config)
        except (RuntimeError, ValueError):
            logging.getLogger('pi-test').exception('PI operation failed')
            raise
    diagnostics = ''.join(traceback.format_exception(caught.value))
    output = capsys.readouterr()
    for text in (str(caught.value), repr(caught.value), diagnostics, caplog.text,
                 output.out, output.err):
        assert secret not in text
        assert connection not in text
    if failure in ('authentication', 'query'):
        assert f'退出码 {1 if failure == "authentication" else 7}' in str(caught.value)


def test_pi_reader_top_level_error_output(tmp_path):
    """Compile only a temporary test executable; never touch release artifacts."""
    root = Path(__file__).resolve().parents[1]
    compiler = Path('C:/Windows/Microsoft.NET/Framework/v4.0.30319/csc.exe')
    libraries = [root / 'PIReader' / f'OSIsoft.{name}.dll'
                 for name in ('PISDK', 'PISDKCommon', 'PITimeServer')]
    if not compiler.is_file() or not all(path.is_file() for path in libraries):
        pytest.skip('Requires Windows C# compiler and local PI SDK reference assemblies')
    executable = tmp_path / 'PIReader.exe'
    command = [str(compiler), '/nologo', '/platform:x86', f'/out:{executable}',
               '/reference:System.Web.Extensions.dll',
               *[f'/reference:{path}' for path in libraries],
               str(root / 'PIReader' / 'Program.cs'),
               str(root / 'PIReader' / 'TimeExpressionParser.cs')]
    compiled = subprocess.run(command, capture_output=True, text=True, timeout=60)
    assert compiled.returncode == 0, compiled.stdout + compiled.stderr
    for library in libraries:
        shutil.copyfile(library, tmp_path / library.name)
    secret = 'Fake-CSharp-Password-Only-For-Tests'
    for args in ([f'--UID=test;PWD={secret}', 'value'],
                 ['--search', f'--UID=test;PWD={secret}', 'value']):
        result = subprocess.run([str(executable), *args], capture_output=True,
                                text=True, encoding='utf-8', timeout=30)
        assert result.returncode == 1
        assert result.stdout == ''
        assert 'ArgumentException' in result.stderr
        assert 'HRESULT 0x' in result.stderr
        assert secret not in result.stderr
        assert 'UID=' not in result.stderr


def test_search_pi_tags_rejects_unbounded_mask():
    with pytest.raises(ValueError, match=r"不能为 \*"):
        pi_reader.search_pi_tags("*")


def test_read_pi_data_forwards_pi_time_expressions(monkeypatch, tmp_path):
    config_path = tmp_path / "config.txt"
    config_path.write_text("shared PIExport-format config", encoding="utf-8")
    install_fixed_reader(monkeypatch, tmp_path)
    monkeypatch.setenv("PI_CONFIG", str(config_path))

    def fake_run(command, **kwargs):
        assert command[command.index("--start") + 1] == "*-1h"
        assert command[command.index("--end") + 1] == "*"
        return subprocess.CompletedProcess(
            command,
            0,
            '{"columns": ["Timestamp", "TAG_A"], "data": []}',
            "",
        )

    monkeypatch.setattr(pi_reader.subprocess, "run", fake_run)

    frame = pi_reader.read_pi_data(["TAG_A"], "*-1h", "*")

    assert frame.empty
    assert list(frame.columns) == ["TAG_A"]


def test_pi_reader_production_path_does_not_create_tags_file():
    source = Path(pi_reader.__file__).read_text(encoding="utf-8")

    assert "tags.txt" not in source
    assert "TemporaryDirectory" not in source
    assert "workdir" not in source


def test_read_pi_data_preserves_columns_for_empty_json(monkeypatch, tmp_path):
    config_path = tmp_path / "config.txt"
    config_path.write_text("shared PIExport-format config", encoding="utf-8")
    install_fixed_reader(monkeypatch, tmp_path)
    monkeypatch.setenv("PI_CONFIG", str(config_path))

    def fake_run(command, **kwargs):
        return subprocess.CompletedProcess(
            command,
            0,
            '{"columns": ["Timestamp", "TAG_A", "TAG_B"], "data": []}',
            "",
        )

    monkeypatch.setattr(pi_reader.subprocess, "run", fake_run)

    frame = pi_reader.read_pi_data(
        ["TAG_A", "TAG_B"],
        datetime(2024, 1, 1),
        datetime(2024, 1, 1, 0, 2),
    )

    assert frame.empty
    assert isinstance(frame.index, pd.DatetimeIndex)
    assert list(frame.columns) == ["TAG_A", "TAG_B"]


def test_read_pi_data_rejects_invalid_json(monkeypatch, tmp_path):
    config_path = tmp_path / "config.txt"
    config_path.write_text("shared PIExport-format config", encoding="utf-8")
    install_fixed_reader(monkeypatch, tmp_path)
    monkeypatch.setenv("PI_CONFIG", str(config_path))
    monkeypatch.setattr(
        pi_reader.subprocess,
        "run",
        lambda command, **kwargs: subprocess.CompletedProcess(command, 0, "not-json", ""),
    )

    try:
        pi_reader.read_pi_data(["TAG_A"], datetime(2024, 1, 1), datetime(2024, 1, 1, 0, 1))
    except ValueError as error:
        assert str(error) == "PIReader 返回的 JSON 无效"
    else:
        raise AssertionError("invalid PIReader JSON was accepted")


def test_read_pi_data_rejects_unsupported_interval(monkeypatch, tmp_path):
    config_path = tmp_path / "config.txt"
    config_path.write_text("shared PIExport-format config", encoding="utf-8")
    install_fixed_reader(monkeypatch, tmp_path)
    monkeypatch.setenv("PI_CONFIG", str(config_path))

    with pytest.raises(ValueError, match="采样间隔必须是以下选项之一"):
        pi_reader.read_pi_data(
            ["TAG_A"],
            datetime(2024, 1, 1),
            datetime(2024, 1, 1, 0, 1),
            "2m",
        )


def test_read_pi_data_converts_timeout_to_user_error(monkeypatch, tmp_path):
    config_path = tmp_path / "config.txt"
    config_path.write_text("shared PIExport-format config", encoding="utf-8")
    install_fixed_reader(monkeypatch, tmp_path)
    monkeypatch.setenv("PI_CONFIG", str(config_path))

    def fake_run(command, **kwargs):
        assert kwargs["timeout"] == pi_reader.PI_READER_TIMEOUT_SECONDS
        raise subprocess.TimeoutExpired(command, kwargs["timeout"])

    monkeypatch.setattr(pi_reader.subprocess, "run", fake_run)

    with pytest.raises(RuntimeError, match="PIReader 查询超时"):
        pi_reader.read_pi_data(
            ["TAG_A"],
            datetime(2024, 1, 1),
            datetime(2024, 1, 1, 0, 1),
        )
