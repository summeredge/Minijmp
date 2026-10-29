import re
from types import SimpleNamespace

import pytest
from unittest.mock import Mock

import pandas as pd

from MiniJMP import Minijmp
from modified_table import MTable
from pandastable_local.data import TableModel


CASCADES = ['文件', '工作表', '编辑', '视图', '数据', '工具', '计算', '试验设计（DOE）',
            '统计', '质量', '图形', '调试', '帮助']


@pytest.fixture
def app(tk_root, monkeypatch):
    monkeypatch.setattr(Minijmp, 'start_logging', lambda self: None)
    previous = set(tk_root.winfo_children())
    created = Minijmp(parent=tk_root)
    try:
        yield created
    finally:
        tk_root.configure(menu='')
        for widget in set(tk_root.winfo_children()) - previous:
            widget.destroy()


def read_menu(menu):
    """Every non-tearoff entry as (index, type, label)."""

    last = menu.index('end')
    if last is None:
        return []
    out = []
    for i in range(last + 1):
        kind = menu.type(i)
        if kind in ('separator', 'tearoff'):
            label = ''
        else:
            label = menu.entrycget(i, 'label')
        out.append((i, kind, label))
    return out


def labels(menu):
    return [label for kind, label in
            ((t, l) for _, t, l in read_menu(menu)) if kind == 'command']


def is_chinese_label(text):
    """Fixed menu text must be Chinese, apart from kept abbreviations.

    Latin runs that are part of a shortcut hint (Ctrl+Z, Del) or a kept
    statistical abbreviation (Cpk, I-MR, Xbar-R, R&R, ...) are allowed.
    """

    kept = ('PI', 'CSV', 'Excel', 'PDF', 'SPC', 'DOE', 'Cpk', 'R&R', 'I-MR', 'Del',
            'MR', 'NP', 'Xbar-R', 'Xbar-S', 'hdf5', 'Logistic', 'PLS', 'Box-Cox',
            'Box-Behnken', 'Plackett–Burman', 'DSD', 'Johnson', 'Sixpack',
            'Taguchi')
    single = set('PCUtZVCFDI')
    if not any('一' <= ch <= '鿿' for ch in text):
        return False
    stripped = text
    for token in kept:
        stripped = stripped.replace(token, '')
    stripped = stripped.replace('Ctrl', '')
    for word in re.findall(r'[A-Za-z]+', stripped):
        if word not in single:
            return False
    return True


def pulldown(app, cascade_label):
    menubar = app.menu
    for i, kind, label in read_menu(menubar):
        if kind == 'cascade' and label == cascade_label:
            return menubar.nametowidget(menubar.entrycget(i, 'menu'))
    raise AssertionError('缺少一级菜单 ' + cascade_label)


def test_menu_bar_shows_only_chinese_top_level_menus(app):
    menubar = app.menu
    shown = [label for _, kind, label in read_menu(menubar)
             if kind == 'cascade']
    assert shown == CASCADES
    for label in shown:
        assert any('一' <= ch <= '鿿' for ch in label), label


def test_every_pulldown_entry_is_chinese(app):
    for cascade in CASCADES:
        menu = pulldown(app, cascade)
        for index, kind, label in read_menu(menu):
            if kind != 'command':
                continue
            text = label.strip()
            assert text, (cascade, index)
            assert is_chinese_label(text), (cascade, index, text)


EXPECTED_LAYOUT = {
    '试验设计（DOE）': ['创建两水平全因子设计', '创建两水平部分因子设计', '分析因子设计',
                        '创建中心复合设计', '分析响应面模型', '优化响应面（DOE-4）',
                        '创建 Box-Behnken 设计', '响应面预测', '叠加等高线', '创建 Plackett–Burman 设计',
                        '创建筛选设计（DSD）', '分析筛选设计', '创建一般全因子设计',
                        '折叠两水平部分因子设计', '创建多因子裂区设计', 'sep',
                        '定义自定义因子设计', '定义自定义响应面设计',
                        '定义自定义筛选设计', 'sep',
                        '修改设计', '增加运行', '选择最优设计', '评价设计', 'sep',
                        '创建混料设计', '分析混料设计', '混料预测',
                        '优化混料响应', '混料最优设计', '混料图形', 'sep',
                        '创建 Taguchi 设计（静态）', '创建 Taguchi 设计（动态）',
                        '分析 Taguchi 设计', '因子设计二元响应分析',
                        '筛选设计二元响应分析', '响应面二元响应分析',
                        '因子设计变异性分析'],
    '文件': ['新建项目', '打开项目', '保存', '另存为', 'sep',
            '导入 CSV', '高级导入', '导入 PI 数据', '导入 Excel', '导出 CSV', '导出当前表（单表 / Excel）', 'sep', '退出'],
    '工作表': ['新增工作表', '复制工作表', '重命名工作表', '删除工作表'],
    '编辑': ['撤销 (Ctrl+Z)', '重做', '粘贴（不含表头）(Ctrl+V)', '粘贴（含表头）',
            '复制整表', '复制所选 (Ctrl+C)', '删除所选并上移', '清除所选 (Del)',
            '查找/替换 (Ctrl+F)', 'sep', '首选项'],
    '视图': ['放大', '缩小', '列宽自动换行', 'sep', '深色主题', '浅色主题'],
    '数据': ['创建分类变量', '应用函数', '重抽样/变换', '取值计数', '字符串处理',
            '日期/时间转换', '筛选行', 'sep', '拆分数据列', '堆叠所选列',
            '全部列排序', '所选列排序', 'sep', '首行提升为列名'],
    '工具': ['转换列名', '转换为数值', '清理数据', '查找重复项',
            '表格转换为文本', '表格信息', 'sep', '数值变换', '分组聚合',
            '交叉表', '合并/拼接表', '透视表', '逆透视表', '时间序列重抽样'],
    '计算': ['计算器'],
    '统计': ['描述性统计', '多变量描述性统计', '正态性检验', '置信区间', 'sep',
            '分布拟合', '相关分析', '线性回归', '残差图', '正交回归',
            '相关系数矩阵', '完整回归分析', '泊松回归', '名义多分类 Logistic 回归',
            '有序 Logistic 回归', '偏最小二乘回归（PLS）', '主成分分析', '时间序列分析', 'sep', '单样本均值 t 检验', '单样本均值 Z 检验',
            '单样本标准差检验', '单比率检验', '双样本 t 检验', '配对 t 检验',
            '双比率检验', '多样本标准差检验', 'sep', '单因子方差分析',
            '双因子方差分析', '试验设计功效与样本量', 'sep',
            '列联表与卡方检验', '比率卡方检验'],
    '质量': ['量具 R&R 研究（交叉）', '量具 R&R 研究（嵌套）', 'sep',
            '过程能力分析 (Cpk)', '含子组的 Cpk', '正态过程能力（完整）', '非正态过程能力',
            'Box-Cox / Johnson 变换', '正态能力 Sixpack', '非正态能力 Sixpack', 'sep', '容差区间', 'sep',
            '控制图 I-MR', '控制图 I（单值）', '控制图 MR（移动极差）',
            '控制图 Xbar-R', '控制图 Xbar-S', '高级 SPC 控制图', 'sep',
            '控制图 NP', '控制图 P',
            '控制图 C', '控制图 U', 'sep', '帕累托图', '运行图', '因果图', '多变异图', '属性一致性分析'],
    '图形': ['通用绘图器', 'sep', '直方图与分布拟合', '分组直方图',
            '二维直方图', '多变量箱线图', '分组箱线图', '条形图', '分组计数图', '饼图',
            '线条图', '时间序列图', '散点图', '区域图', '点图', '矩阵图',
            '等值线图', '三维散点图', '三维曲面图', 'sep', '概率图', '概率图对比', '气泡图', '经验累积分布函数图', '单值图', '区间图', '边际图', '茎叶图', '样本概率图', 'sep',
            '保存图形', '清除图形', 'PDF 报告', 'sep'],
    '调试': ['打印数据框', 'sep'],
    '帮助': ['帮助文档', '查看错误日志', '关于'],
}


@pytest.mark.parametrize('cascade', sorted(EXPECTED_LAYOUT))
def test_pulldown_keeps_original_order_separators_and_count(app, cascade):
    menu = pulldown(app, cascade)
    layout = ['sep' if kind == 'separator' else label.strip()
              for _, kind, label in read_menu(menu)]
    assert layout == EXPECTED_LAYOUT[cascade]


# (cascade, label, table method, keyword arguments the table must receive)
COMMANDS = [
    ('文件', '新建项目', 'new_file', {}),
    ('文件', '打开项目', 'load_file', {}),
    ('文件', '导入 CSV', 'import_csv', {}),
    ('文件', '高级导入', 'import_csv', {'advanced': True}),
    ('文件', '导入 Excel', 'load_excel', {}),
    ('文件', '导出 CSV', 'doExport', {}),
    ('编辑', '重做', 'redo', {}),
    ('编辑', '粘贴（含表头）', 'paste_header', {}),
    ('编辑', '清除所选 (Del)', 'clearData', {}),
    ('视图', '放大', 'zoomIn', {}),
    ('视图', '深色主题', 'setTheme', {'name': 'dark'}),
    ('数据', '筛选行', 'queryBar', {}),
    ('工具', '表格信息', 'showInfo', {}),
]


@pytest.mark.parametrize('cascade,label,method,expected', COMMANDS)
def test_translated_item_invokes_its_original_command(
        app, monkeypatch, cascade, label, method, expected):
    sentinel = Mock()
    if method in ('new_file', 'load_file', 'import_csv', 'load_excel'):
        monkeypatch.setattr(app, method, sentinel)
        app.createMenuBar()
    else:
        monkeypatch.setattr(app.table, method, sentinel)
    menu = pulldown(app, cascade)
    index = next(i for i, kind, text in read_menu(menu)
                 if kind == 'command' and text.strip() == label)
    menu.invoke(index)
    sentinel.assert_called_once_with(**expected)


@pytest.mark.parametrize('module,class_name,cascade,label', [
    ('regression_dialog', 'RegressionDialog', '统计', '完整回归分析'),
    ('pca_dialog', 'PCADialog', '统计', '主成分分析'),
    ('advanced_time_series_dialog', 'TimeSeriesAnalysisDialog', '统计', '时间序列分析'),
    ('advanced_spc_dialog', 'AdvancedSPCDialog', '质量', '高级 SPC 控制图'),
])
def test_advanced_analysis_menu_uses_current_sheet_and_lazy_dialog(
        app, monkeypatch, module, class_name, cascade, label):
    import sys

    dialog = Mock()
    monkeypatch.setitem(sys.modules, module, SimpleNamespace(**{class_name: dialog}))
    menu = pulldown(app, cascade)
    for values in ([1, 2], [3, 4]):
        table = app.addSheet(dataframe=pd.DataFrame({'x': values}))
        menu.invoke(next(i for i, kind, text in read_menu(menu)
                         if kind == 'command' and text.strip() == label))
        expected = {'model': 'OLS'} if module == 'regression_dialog' else {}
        dialog.assert_called_once_with(parent=table, df=table.model.df, app=app, **expected)
        dialog.reset_mock()


@pytest.mark.parametrize('label,model', [
    ('泊松回归', 'Poisson'), ('名义多分类 Logistic 回归', 'Nominal'),
    ('有序 Logistic 回归', 'Ordinal'), ('偏最小二乘回归（PLS）', 'PLS'),
])
def test_extended_regression_menu_presets_model_on_current_sheet(app, monkeypatch, label, model):
    import sys

    dialog = Mock()
    monkeypatch.setitem(sys.modules, 'regression_dialog', SimpleNamespace(RegressionDialog=dialog))
    menu = pulldown(app, '统计')
    for values in ([1, 2], [3, 4]):
        table = app.addSheet(dataframe=pd.DataFrame({'Y': values}))
        menu.invoke(next(i for i, kind, text in read_menu(menu)
                         if kind == 'command' and text.strip() == label))
        dialog.assert_called_once_with(parent=table, df=table.model.df, app=app, model=model)
        dialog.reset_mock()


@pytest.mark.parametrize('label,kind', [('帕累托图', 'pareto'), ('运行图', 'run_chart'), ('因果图', 'cause_effect'),
                                      ('多变异图', 'multi_vari'), ('属性一致性分析', 'attribute_agreement')])
def test_quality_tools_menu_uses_current_sheet(app, monkeypatch, label, kind):
    import sys
    dialog = Mock()
    monkeypatch.setitem(sys.modules, 'quality_tools_dialog', SimpleNamespace(QualityToolsDialog=dialog))
    menu = pulldown(app, '质量')
    for values in ([1, 2], [3, 4]):
        table = app.addSheet(dataframe=pd.DataFrame({'x': values}))
        menu.invoke(next(i for i, typ, text in read_menu(menu) if typ == 'command' and text.strip() == label))
        dialog.assert_called_once_with(table, table.model.df, app, kind=kind)
        dialog.reset_mock()


@pytest.fixture
def unposted(monkeypatch):
    """Keep popupMenu from posting a real menu that would block the test."""

    import tkinter as tk
    monkeypatch.setattr(tk.Menu, 'post', lambda self, *args: None)
    monkeypatch.setattr(tk.Menu, 'focus_set', lambda self: None)


def test_cell_popup_menu_is_chinese_and_keeps_submenus(app, unposted):
    table = app.table
    table.model.df = pd.DataFrame({'x': [1, 2, 3], 'y': [4, 5, 6]})
    table.redraw()
    table.prevdf = [table.model.df.copy()]
    table.prevdf_end = 1
    event = SimpleNamespace(x=table.col_positions[0] + 5,
                            y=table.y_start + 5,
                            x_root=0, y_root=0)
    menu = table.popupMenu(event, rows=[0, 1], cols=[0])
    try:
        shown = [text for _, kind, text in read_menu(menu)
                 if kind in ('command', 'cascade')]
        assert shown == ['复制', '粘贴', '撤销', '向下填充', '清除数据',
                         '设置颜色', '全选', '筛选行', '显示为文本',
                         '表格信息', '首选项',
                         '文件', '编辑', '图形', '表格']
        for label in shown:
            assert any('一' <= ch <= '鿿' for ch in label), label
        submenus = {}
        for i, kind, text in read_menu(menu):
            if kind == 'cascade':
                child = menu.nametowidget(menu.entrycget(i, 'menu'))
                submenus[text] = [label for _, k, label in read_menu(child)
                                  if k == 'command']
        assert submenus == {
            '文件': ['打开', '导入文本/CSV', '导入 hdf5', '保存', '另存为', '导出'],
            '编辑': ['撤销上次更改', '复制整表', '查找/替换'],
            '图形': ['绘制所选', '隐藏图形', '显示图形'],
            '表格': ['表格转换为文本', '清理数据', '清除格式'],
        }
    finally:
        menu.destroy()


def test_column_header_popup_menu_is_chinese(app, unposted):
    table = app.table
    table.model.df = pd.DataFrame({'零件': [1, 2], '尺寸': [3, 4]})
    table.redraw()
    table.setSelectedCol(0)
    header = table.colheader
    event = SimpleNamespace(x=20, y=5, x_root=0, y_root=0)
    menu = header.popupMenu(event)
    try:
        shown = [text for _, kind, text in read_menu(menu)
                 if kind == 'command']
        assert shown == ['按 零件 升序排序全表 ↓', '按 零件 降序排序全表 ↑',
                         '复制整列', '粘贴整列', '删除列', '重命名列',
                         '添加列', '设置对齐方式',
                         '填充数据', '设置数据类型']
        menu.invoke(1)
        assert table.model.df['零件'].tolist() == [2, 1]
        menu.invoke(0)
        assert table.model.df['零件'].tolist() == [1, 2]
    finally:
        menu.destroy()


def test_row_header_popup_menu_is_chinese(app, unposted):
    table = app.table
    table.model.df = pd.DataFrame({'x': [1, 2, 3]})
    table.redraw()
    event = SimpleNamespace(x=5, y=table.y_start + 5, x_root=0, y_root=0)
    menu = table.rowheader.popupMenu(event, outside=1)
    try:
        shown = [text for _, kind, text in read_menu(menu)
                 if kind == 'command']
        assert shown == ['按索引排序', '重置索引', '显示/隐藏索引', '重命名索引',
                         '复制索引到列', '在此处插入行', '在末尾添加行',
                         '删除行', '复制行', '复制整行', '粘贴整行']
    finally:
        menu.destroy()


def test_formula_context_submenu_and_calculator_window(app, unposted, monkeypatch):
    from worksheet_formulas import CalculatorDialog

    table = app.table
    table.model.df = pd.DataFrame({'C1': [2.], 'C2': [4.]})
    table.redraw()
    labels = []
    monkeypatch.setattr(CalculatorDialog, '__init__', lambda self, *a, **k: labels.append(a[1:]))
    table.handle_right_click(SimpleNamespace(x=20, y=table.y_start + 5, x_root=0, y_root=0))
    menu = table.rightmenu
    formula_index = next(i for i, kind, text in read_menu(menu)
                         if kind == 'cascade' and text == '公式')
    submenu = menu.nametowidget(menu.entrycget(formula_index, 'menu'))
    assert [text for _, kind, text in read_menu(submenu)
            if kind in ('command', 'checkbutton')] == [
                '向列分配公式', '编辑列公式', '查看列公式', '删除列公式',
                '自动计算所有公式', '立即计算所有公式']
    submenu.invoke(0)
    assert labels == [(0,)]
    menu.destroy()


def test_stored_plot_history_menu_stays_usable(app):
    """Fixed 图形 entries survive adding and clearing the dynamic history."""

    menu = pulldown(app, '图形')
    before = labels(menu)
    app.plots['图一'] = Mock()
    app.plots['图二'] = Mock()
    for name in ('图一', '图二'):
        menu.add_command(label=name, command=lambda: None)
    assert labels(menu) == before + ['图一', '图二']
    app.updatePlotsMenu()
    assert labels(menu) == before
    assert app.plots == {}


def test_dynamic_column_label_uses_chinese_suffix(app, unposted):
    table = app.table
    table.model.df = pd.DataFrame({name: [1] for name in ['a', 'b', 'c', 'd']})
    table.redraw()
    table.multiplecollist = [0, 1, 2, 3]
    header = table.colheader
    event = SimpleNamespace(x=20, y=5, x_root=0, y_root=0)
    menu = header.popupMenu(event)
    try:
        shown = [text for _, kind, text in read_menu(menu) if kind == 'command']
        assert shown[0] == '按 a,b+2 其他列 升序排序全表 ↓'
    finally:
        menu.destroy()


@pytest.mark.parametrize('label,method', [
    ('查看错误日志', 'showErrorLog'), ('关于', 'about'),
])
def test_help_commands_keep_their_callbacks(app, monkeypatch, label, method):
    command = Mock()
    monkeypatch.setattr(app, method, command)
    app.createMenuBar()
    menu = pulldown(app, '帮助')
    menu.invoke(next(i for i, kind, text in read_menu(menu) if text.strip() == label))
    command.assert_called_once_with()


def test_offline_help_menu_and_f1_open_home(app, monkeypatch):
    command = Mock()
    monkeypatch.setattr('MiniJMP.open_help', command)
    menu = pulldown(app, '帮助')
    menu.invoke(0)
    command.assert_called_once_with(parent=app.main)
    command.reset_mock()
    script = app.main.bind('<F1>')
    # Invoke the registered Tcl binding even when the window lacks keyboard focus.
    callback = script.split('[', 1)[1].split()[0]
    app.main.tk.call(callback, *(['0'] * 19))
    command.assert_called_once_with(parent=app.main)



def test_translation_inventory_matches_live_menus(app):
    from collections import Counter
    from pathlib import Path

    inventory = (Path(__file__).resolve().parents[1] / 'docs/MENU_TRANSLATION.md').read_text(encoding='utf-8')
    for cascade in CASCADES:
        section = inventory.split('## ' + cascade + '（', 1)[1].split('\n## ', 1)[0]
        translated = [line.split('|')[2].strip() for line in section.splitlines()
                      if line.startswith('| ') and not line.startswith(('| 英文原文', '| ---'))]
        actual = [label.strip() for label in labels(pulldown(app, cascade))]
        assert Counter(translated) == Counter(actual), cascade
        if cascade == '帮助':
            assert translated == actual


@pytest.mark.parametrize('topic,cascade,label', [
    ('files.csv_import', '文件', '导入 CSV'),
    ('files.csv_advanced_import', '文件', '高级导入'),
    ('files.pi_import', '文件', '导入 PI 数据'),
    ('files.csv_export', '文件', '导出 CSV'),
    ('stats.describe', '统计', '描述性统计'),
    ('stats.advanced_regression', '统计', '完整回归分析'),
    ('stats.pca', '统计', '主成分分析'),
    ('stats.time_series_analysis', '统计', '时间序列分析'),
    ('stats.fit_distribution', '图形', '直方图与分布拟合'),
    ('plots.plot_wizard', '图形', '通用绘图器'),
    ('plots.store_plot', '图形', '保存图形'),
    ('plots.clear_plots', '图形', '清除图形'),
    ('plots.pdf_report', '图形', 'PDF 报告'),
    ('plots.histogram_fit', '统计', '分布拟合'),
])
def test_help_operation_paths_match_live_menu_labels(app, topic, cascade, label):
    import json
    from tools.build_help_index import build_search_index

    index = json.loads(build_search_index().split(' = ', 1)[1].rstrip()[:-1])
    body = next(item['text'] for item in index if item['id'] == topic)
    assert label in [text.strip() for text in labels(pulldown(app, cascade))]
    assert cascade + ' → ' + label in body



def test_graph_help_directory_and_headings_match_live_menu(app):
    from html import unescape
    from pathlib import Path

    page = (Path(__file__).resolve().parents[1] / 'help/pages/graphs.html').read_text(encoding='utf-8')
    actual = [label.strip() for label in labels(pulldown(app, '图形'))]
    directory = [unescape(text) for text in re.findall(r'<a href="#plots\.[^"]+">([^<]+)</a>', page)]
    headings = [unescape(text) for text in re.findall(r'<h2>([^<]+)</h2>', page) if text != '目录']
    assert directory == headings
    assert sorted(directory) == sorted(actual)
