"""Protocol regressions reused from PI-Data-Viewer; no live PI access."""
import json
import subprocess
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest

import pi_reader


@pytest.mark.parametrize("platform", ["nt", "posix"])
@pytest.mark.parametrize("operation", ["search", "query"])
@pytest.mark.parametrize("outcome", ["success", "failure", "timeout"])
def test_pi_subprocess_flags_and_outcomes(monkeypatch, tmp_path, platform, operation, outcome):
    config = tmp_path / "config.txt"
    config.write_text("test config", encoding="utf-8")
    executable = tmp_path / "PIReader.exe"
    executable.touch()
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
        paths = {"config_path": config, "executable_path": executable}
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
        message = ("搜索超时" if operation == "search" else "查询超时") if outcome == "timeout" else "reader stdout\nreader stderr"
        with pytest.raises(RuntimeError, match=message) as error:
            invoke()
        if outcome == "timeout":
            assert isinstance(error.value.__cause__, subprocess.TimeoutExpired)


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
    executable = tmp_path / "PIReader.exe"
    executable.write_bytes(b"test executable")
    monkeypatch.setenv("PI_CONFIG", str(config_path))
    monkeypatch.setenv("PI_READER_EXE", str(executable))

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
    executable = tmp_path / "PIReader.exe"
    executable.write_bytes(b"test executable")
    monkeypatch.setenv("PI_CONFIG", str(config_path))
    monkeypatch.setenv("PI_READER_EXE", str(executable))

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
    executable = tmp_path / "PIReader.exe"
    executable.write_bytes(b"test executable")
    monkeypatch.setenv("PI_CONFIG", str(config_path))
    monkeypatch.setenv("PI_READER_EXE", str(executable))
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


def test_search_pi_tags_forwards_reader_failure(monkeypatch, tmp_path):
    config_path = tmp_path / "config.txt"
    config_path.write_text("shared PIExport-format config", encoding="utf-8")
    executable = tmp_path / "PIReader.exe"
    executable.write_bytes(b"test executable")
    monkeypatch.setenv("PI_CONFIG", str(config_path))
    monkeypatch.setenv("PI_READER_EXE", str(executable))

    def fake_run(command, **kwargs):
        return subprocess.CompletedProcess(command, 1, "", "PI SDK unavailable")

    monkeypatch.setattr(pi_reader.subprocess, "run", fake_run)

    with pytest.raises(RuntimeError, match="PI SDK unavailable"):
        pi_reader.search_pi_tags("FIC*")


def test_search_pi_tags_rejects_unbounded_mask():
    with pytest.raises(ValueError, match=r"不能为 \*"):
        pi_reader.search_pi_tags("*")


def test_read_pi_data_forwards_pi_time_expressions(monkeypatch, tmp_path):
    config_path = tmp_path / "config.txt"
    config_path.write_text("shared PIExport-format config", encoding="utf-8")
    executable = tmp_path / "PIReader.exe"
    executable.write_bytes(b"test executable")
    monkeypatch.setenv("PI_CONFIG", str(config_path))
    monkeypatch.setenv("PI_READER_EXE", str(executable))

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
    executable = tmp_path / "PIReader.exe"
    executable.write_bytes(b"test executable")
    monkeypatch.setenv("PI_CONFIG", str(config_path))
    monkeypatch.setenv("PI_READER_EXE", str(executable))

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
    executable = tmp_path / "PIReader.exe"
    executable.write_bytes(b"test executable")
    monkeypatch.setenv("PI_CONFIG", str(config_path))
    monkeypatch.setenv("PI_READER_EXE", str(executable))
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
    executable = tmp_path / "PIReader.exe"
    executable.write_bytes(b"test executable")
    monkeypatch.setenv("PI_CONFIG", str(config_path))
    monkeypatch.setenv("PI_READER_EXE", str(executable))

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
    executable = tmp_path / "PIReader.exe"
    executable.write_bytes(b"test executable")
    monkeypatch.setenv("PI_CONFIG", str(config_path))
    monkeypatch.setenv("PI_READER_EXE", str(executable))

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
