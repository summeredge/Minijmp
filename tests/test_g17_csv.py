"""CSV compatibility and per-call work bounds; no timing thresholds."""
import codecs
import csv
from collections import Counter
from unittest.mock import Mock

import pandas as pd
import pytest

from pandastable_local import csv_import


@pytest.mark.parametrize('encoding,bom,detected,confirm', [
    ('utf-8', b'', 'utf-8-sig', False),
    ('utf-8-sig', b'', 'utf-8-sig', False),
    ('utf-16-le', codecs.BOM_UTF16_LE, 'utf-16', False),
    ('utf-16-be', codecs.BOM_UTF16_BE, 'utf-16', False),
    ('gb18030', b'', 'gb18030', True),
    ('cp1252', b'', 'cp1252', True),
])
def test_encodings_decode_each_attempt_once(tmp_path, monkeypatch, encoding, bom,
                                          detected, confirm):
    text = 'name,value\n' + ('\u20ac' if encoding == 'cp1252' else '中文') + ',1\n'
    calls = []

    class Payload(bytes):
        def decode(self, encoding, *args, **kwargs):
            calls.append(encoding)
            return super().decode(encoding, *args, **kwargs)

    path = tmp_path / 'encoded.csv'
    path.write_bytes(bom + text.encode(encoding))
    raw = Payload(path.read_bytes())
    monkeypatch.setattr(csv_import.Path, 'read_bytes', lambda self: raw)
    options = csv_import.detect_csv(path)
    assert options == dict(encoding=detected, delimiter=',', header=True, confirm=confirm)
    assert calls == (['utf-16'] if detected == 'utf-16' else
                     ['utf-8-sig', 'gb18030', 'cp1252'] if detected == 'cp1252' else
                     ['utf-8-sig', 'gb18030'] if detected == 'gb18030' else ['utf-8-sig'])
    calls.clear()
    frame = csv_import.read_csv(path, detected, ',', True)
    assert calls == [detected]
    assert frame.iloc[0].tolist() == [text.splitlines()[1].split(',')[0], 1]


@pytest.mark.parametrize('text,delimiter,header,confirm', [
    ('a,b\n1,2\n', ',', True, False),
    ('a\tb\n1\t2\n', '\t', True, False),
    ('a;b\n1;2\n', ';', True, False),
    ('a|b\n1|2\n', '|', True, False),
    ('a,b;c|d\te\n1,2;3|4\t5\n', ',', True, True),
    ('a\tb;c|d\n1\t2;3|4\n', '\t', True, True),
    ('a;b|c\n1;2|3\n', ';', True, True),
    ('name\nAlice\nBob\n', ',', None, True),
    ('1,2\n3,4\n', ',', False, False),
    ('1,2\n3,\n', ',', None, True),
    ('a,b\nx,\ny,\n', ',', None, True),
    ('a,b\nx,\ny,2\n', ',', True, False),
    ('a,a\n1,2\n', ',', None, True),
    (',b\n1,2\n', ',', None, True),
    ('a,1\n2,3\n', ',', None, True),
    ('001,2\n3,4\n', ',', None, True),
    ('a,b\n', ',', None, True),
    ('a,b;c\n1,2;3\nx;4\n', ';', True, False),
])
def test_detection_contract_and_no_selected_reparse(tmp_path, monkeypatch, text,
                                                  delimiter, header, confirm):
    path = tmp_path / 'detect.csv'
    path.write_text(text, encoding='utf-8')
    parse = Mock(wraps=csv_import.read_records)
    monkeypatch.setattr(csv_import, 'read_records', parse)
    assert csv_import.detect_csv(path) == dict(encoding='utf-8-sig', delimiter=delimiter,
                                              header=header, confirm=confirm)
    assert [call.args[1] for call in parse.call_args_list] == list(csv_import.DELIMITERS.values())


@pytest.mark.parametrize('value,numeric', [
    ('123456789012345', True), ('1234567890123456', False),
    ('-123456789012345', True), ('+1234567890123456', False),
    ('001', False), ('+01', False), ('-01', False), ('00.5', False),
    ('0.5', True), ('-0', True), ('+2', True), ('1e3', True), ('1E-3', True),
    ('0.1234567890123456789', True), ('1234567890123456789.0', True),
    ('1e309', False), ('NaN', False), ('inf', False),
    ('1,25', False), (' 1', False), ('1 ', False), ('1.', False),
    ('.5', False), ('１', False), ('NA', False), ('2026-10-21', False),
])
def test_numeric_precision_and_identifier_contract(tmp_path, value, numeric):
    path = tmp_path / 'values.csv'
    with path.open('w', encoding='utf-8', newline='') as stream:
        csv.writer(stream).writerows([['label', 'value'], ['a', value], ['b', ''], ['c', value]])
    frame = csv_import.read_csv(path, 'utf-8', ',', True)
    assert pd.isna(frame.loc[1, 'value'])
    if numeric:
        assert pd.api.types.is_numeric_dtype(frame['value'])
        assert frame.loc[0, 'value'] == pytest.approx(float(value), rel=1e-15)
        assert frame.loc[2, 'value'] == frame.loc[0, 'value']
    else:
        assert frame.loc[[0, 2], 'value'].tolist() == [value, value]


@pytest.mark.parametrize('header', [False, True])
def test_numeric_checks_scale_with_distinct_values_per_column(tmp_path, monkeypatch, header):
    path = tmp_path / 'repeated.csv'
    path.write_text(('a,b\n' if header else '1,2\n') + '1,2\n' * 2000, encoding='utf-8')
    number = Mock(wraps=csv_import.NUMBER)
    monkeypatch.setattr(csv_import, 'NUMBER', number)
    assert csv_import.detect_csv(path)['header'] is header
    counts = Counter(call.args[0] for call in number.fullmatch.call_args_list)
    assert sum(counts.values()) <= 4
    number.reset_mock()
    frame = csv_import.read_csv(path, 'utf-8', ',', header)
    assert len(frame) == (2000 if header else 2001)
    assert Counter(call.args[0] for call in number.fullmatch.call_args_list) == {'1': 2, '2': 2}


@pytest.mark.parametrize('tail', ['3', '3,4,5', '"unterminated,3', '3,\x00'])
@pytest.mark.parametrize('operation', ['detect', 'read'])
def test_strict_validation_reaches_file_tail(tmp_path, tail, operation):
    path = tmp_path / 'damaged.csv'
    path.write_text('a,b\n' + '1,2\n' * 12000 + tail, encoding='utf-8')
    with pytest.raises((ValueError, csv.Error)):
        if operation == 'detect':
            csv_import.detect_csv(path)
        else:
            csv_import.read_csv(path, 'utf-8', ',', True)


@pytest.mark.parametrize('raw', [b'', b'\xef\xbb\xbf', b'\xff\xfea', b'a,b\n\x81'])
@pytest.mark.parametrize('operation', ['detect', 'read'])
def test_empty_and_invalid_encoding_rejected(tmp_path, raw, operation):
    path = tmp_path / 'invalid.csv'
    path.write_bytes(raw)
    with pytest.raises((ValueError, csv.Error)):
        if operation == 'detect':
            csv_import.detect_csv(path)
        else:
            encoding = 'utf-16' if raw.startswith(codecs.BOM_UTF16_LE) else 'utf-8-sig'
            csv_import.read_csv(path, encoding, ',', True)


@pytest.mark.parametrize('names', ['a,a', ',b'])
def test_invalid_confirmed_headers_still_rejected(tmp_path, names):
    path = tmp_path / 'header.csv'
    path.write_text(names + '\n1,2\n', encoding='utf-8')
    with pytest.raises(ValueError, match='表头'):
        csv_import.read_csv(path, 'utf-8', ',', True)
    row = csv_import.read_csv(path, 'utf-8', ',', False).iloc[0]
    assert row.iloc[1] == names.split(',')[1]
    assert row.iloc[0] == 'a' if names.startswith('a') else pd.isna(row.iloc[0])


def test_calls_reread_changed_files_and_choices(tmp_path):
    path = tmp_path / 'changing.csv'
    path.write_text('name,value\na,1\n', encoding='utf-8')
    options = csv_import.detect_csv(path)
    options.pop('confirm')
    path.write_text('name,value\nb,2\n', encoding='utf-8')
    assert csv_import.read_csv(path, **options).iloc[0].tolist() == ['b', 2]
    assert len(csv_import.read_csv(path, 'utf-8', ',', False)) == 2
    path.write_text('name;value\nc;3\n', encoding='utf-8')
    assert csv_import.detect_csv(path)['delimiter'] == ';'
    assert csv_import.read_csv(path, 'utf-8', ';', True).iloc[0].tolist() == ['c', 3]
    path.write_text('name,value\nb,2\nbad\n', encoding='utf-8')
    with pytest.raises(ValueError):
        csv_import.read_csv(path, **options)
