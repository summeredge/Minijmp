"""P1 5.5：用户导出的文本不得被电子表格当作公式执行。"""
import csv
import io
from types import SimpleNamespace

import pandas as pd
import pytest
from openpyxl import load_workbook

import stat_table
from pandastable_local.data import TableModel
from pandastable_local.util import escape_text, protected_frame, save_frame
from stat_table import StatTable, TableBlock

QUOTE = chr(39)


@pytest.fixture
def hostile():
    return pd.DataFrame({
        "文本": pd.array(['=1+1', '+SUM(A1:A2)', '-SUM(A1:A2)', '@SUM(A1:A2)',
                            '  =1+1', '\t=1+1', '\n=1+1', '-12.5', '中文', None],
                            dtype='string'),
        "数值": [-12.5, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, None],
        "日期": pd.to_datetime(['2024-01-01'] * 10),
    })


def test_escape_text_blocks_triggers_and_keeps_plain_text():
    for value in ('=1+1', '+SUM(A1:A2)', '-SUM(A1:A2)', '@SUM(A1:A2)',
                  '  =1+1', '\t=1+1', '\n=1+1', '-12.5'):
        assert escape_text(value) == QUOTE + value
    assert escape_text('中文') == '中文'
    assert escape_text('2024-01-01') == '2024-01-01'
    assert escape_text(-12.5) == -12.5 and escape_text(None) is None


def test_csv_keeps_field_boundaries_and_leaves_source_frame(hostile):
    original = hostile.copy(deep=True)
    rows = list(csv.reader(io.StringIO(protected_frame(hostile).to_csv(index=False),
                                      newline='')))
    assert len(rows) == len(hostile) + 1 and all(len(row) == 3 for row in rows)
    assert rows[1][0] == QUOTE + '=1+1' and rows[1][1] == '-12.5'
    assert rows[5][0] == QUOTE + '  =1+1' and rows[6][0] == QUOTE + '\t=1+1'
    assert rows[7][0] == QUOTE + '\n=1+1' and rows[8][0] == QUOTE + '-12.5'
    assert rows[9][0] == '中文' and rows[10][0] == ''
    pd.testing.assert_frame_equal(hostile, original)


@pytest.mark.parametrize('labels', [[1, 2], pd.date_range('2024-01-01', periods=2)])
def test_csv_protects_index_name_independently(tmp_path, labels):
    frame = pd.DataFrame({'值': [1, 2]}, index=pd.Index(labels, name='=1+1'))
    original = frame.copy(deep=True)
    path = tmp_path / 'index.csv'
    save_frame(frame, path, index=True)
    with path.open(encoding='utf-8-sig', newline='') as stream:
        assert next(csv.reader(stream)) == [QUOTE + '=1+1', '值']
    pd.testing.assert_index_equal(protected_frame(frame, index=True).index,
                                  frame.index.rename(QUOTE + '=1+1'))
    pd.testing.assert_index_equal(protected_frame(frame, index=False).index, frame.index)
    pd.testing.assert_frame_equal(frame, original)


@pytest.mark.parametrize('axis', ['index', 'columns'])
def test_multiindex_csv_and_xlsx_preserve_structure_and_block_formulas(tmp_path, axis):
    rows = pd.MultiIndex.from_tuples([('甲', 1), ('甲', 2), ('乙', 1)],
                                     names=['组', '序号'])
    columns = pd.MultiIndex.from_tuples([('测量', '值'), ('测量', '备注')],
                                        names=['类别', '字段'])
    frame = pd.DataFrame([[1, '中文'], [2, None], [3, '正常']],
                         index=rows, columns=columns)
    labels = getattr(frame, axis)
    setattr(frame, axis, pd.MultiIndex.from_tuples(
        [('=1+1', label[1]) if position == 0 else label
         for position, label in enumerate(labels)], names=['=2+2', labels.names[1]]))
    original = frame.copy(deep=True)
    safe = protected_frame(frame, index=True)
    expected_rows = pd.MultiIndex.from_tuples(
        [tuple(escape_text(value) for value in label) for label in frame.index],
        names=[escape_text(name) for name in frame.index.names])
    expected_columns = pd.MultiIndex.from_tuples(
        [tuple(escape_text(value) for value in label) for label in frame.columns],
        names=[escape_text(name) for name in frame.columns.names])
    pd.testing.assert_index_equal(safe.index, expected_rows)
    pd.testing.assert_index_equal(safe.columns, expected_columns)
    csv_path, xlsx_path = tmp_path / 'multi.csv', tmp_path / 'multi.xlsx'
    save_frame(frame, csv_path, index=True)
    with csv_path.open(encoding='utf-8-sig', newline='') as stream:
        output = list(csv.reader(stream))
    assert len(output) == frame.columns.nlevels + 1 + len(frame)
    assert all(len(row) == frame.index.nlevels + len(frame.columns) for row in output)
    assert output[0] == [safe.columns.names[0], '', *safe.columns.get_level_values(0)]
    assert output[1] == [safe.columns.names[1], '', *safe.columns.get_level_values(1)]
    assert output[2] == [*safe.index.names, '', '']
    assert output[3][:2] == list(map(str, safe.index[0]))
    save_frame(frame, xlsx_path, index=True)
    book = load_workbook(xlsx_path)
    try:
        sheet = book.active
        cells = [cell for row in sheet for cell in row]
        assert not any(cell.data_type == 'f' for cell in cells)
        assert any(cell.value == '=1+1' and cell.data_type == 's' for cell in cells)
        assert any(cell.value == '=2+2' and cell.data_type == 's' for cell in cells)
        assert sheet.cell(4, 3).value == 1 and sheet.cell(4, 3).data_type == 'n'
        assert sheet.cell(4, 4).value == '中文'
        assert sheet.cell(5, 4).value is None
        assert sheet.max_row == 6 and sheet.max_column == 4
        assert ('C1:D1' if axis == 'index' else 'A4:A5') in sheet.merged_cells
    finally:
        book.close()
    pd.testing.assert_frame_equal(frame, original)


@pytest.mark.parametrize('index', [False, True])
def test_excel_writes_hostile_text_as_text_cells(tmp_path, hostile, index):
    path = tmp_path / '导出.xlsx'
    save_frame(hostile, path, index=index)
    book = load_workbook(path)
    try:
        sheet = book.active
        first, column = 2 if index else 1, 1 + int(index)
        cells = [cell for (cell,) in sheet.iter_rows(
            min_row=first, min_col=column, max_col=column)]
        # 文本单元格不得为公式类型 'f'；空值仍为空值。
        assert not any(cell.data_type == 'f' for cell in cells)
        start = 0 if index else 1  # 第一行在无索引时是表头。
        assert [cell.value for cell in cells[start:]][:4] == [
            '=1+1', '+SUM(A1:A2)', '-SUM(A1:A2)', '@SUM(A1:A2)']
        number = sheet.cell(first + (0 if index else 1), column + 1)
        assert (number.value, number.data_type) == (-12.5, 'n')
        assert sheet.cell(first + (0 if index else 1), column + 2).value.date().isoformat() == '2024-01-01'
    finally:
        book.close()


def test_worksheet_export_keeps_numeric_types_and_escapes_text(tmp_path, hostile):
    model = TableModel(hostile.copy())
    csv_path, xlsx_path = tmp_path / 'a.csv', tmp_path / 'a.xlsx'
    model.save(csv_path)
    model.save(xlsx_path)
    assert pd.read_csv(csv_path, index_col=0)['数值'].iloc[:2].tolist() == [-12.5, 2.0]
    assert pd.read_csv(csv_path, index_col=0)['文本'].iloc[0] == QUOTE + '=1+1'
    book = load_workbook(xlsx_path)
    try:
        # XLSX 用文本单元格保存原文，不添加 CSV 的引导前缀。
        assert (book.active.cell(2, 2).value, book.active.cell(2, 2).data_type) == ('=1+1', 's')
        assert (book.active.cell(2, 3).value, book.active.cell(2, 3).data_type) == (-12.5, 'n')
    finally:
        book.close()
    pd.testing.assert_frame_equal(model.df, hostile)


def test_stat_table_clipboard_escapes_text_and_keeps_number_display(tk_root):
    table = StatTable(title='=1+1', headers=['=1+1', 'N'],
                      values=[['=1+1', -12.5]],
                      display=[['=1+1', '-12.500']], number_formats=['General', '0.000'])
    block = TableBlock(tk_root, table)
    written = []
    block.clipboard_clear = lambda: None
    block.clipboard_append = written.append
    try:
        block.copy_to_excel()
        rows = list(csv.reader(io.StringIO(written[0], newline=''), delimiter='\t'))
        assert rows == [[QUOTE + '=1+1', 'N'], [QUOTE + '=1+1', '-12.500']]
    finally:
        block.destroy()
