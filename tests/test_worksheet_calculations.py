import numpy as np
import pandas as pd
import pytest
from scipy import stats

from MiniJMP import Minijmp
from worksheet_calculations import (WorksheetCalculationDialog, distribution_parameters,
                                    distribution_values, random_values, sample_rows, unstack_columns)
from test_regression_dialog import dispose


def test_unstack_keeps_group_order_missing_and_exact_identifiers():
    y = pd.Series([2**60+1, pd.NA, 5, 7, 11, 13, 17], dtype='Int64')
    g = pd.Series([1, None, 1, '1', None, 1, '（缺失）'])
    actual = unstack_columns(y, g)
    expected = pd.concat([y.iloc[rows].reset_index(drop=True) for rows in
                          [[0, 2, 5], [1, 4], [3], [6]]], axis=1)
    expected.columns = ['1', '（缺失）', '1 (2)', '（缺失） (2)']
    pd.testing.assert_frame_equal(actual, expected)


def test_sampling_is_repeatable_and_preserves_row_correspondence():
    data = pd.DataFrame({'a': range(10), 'b': [i*i for i in range(10)]})
    for replace, count in [(False, 10), (True, 20)]:
        result = sample_rows(data, count, seed=123, replace=replace)
        pd.testing.assert_frame_equal(result, sample_rows(data, count, seed=123, replace=replace))
        assert result.b.equals(result.a**2)
        assert result.a.is_unique is not replace
    with pytest.raises(ValueError, match='无放回'):
        sample_rows(data, 11, seed=123)


@pytest.mark.parametrize(('name', 'fields', 'scipy', 'pars'), [
    ('normal', ('3', '2'), stats.norm, (3, 2)),
    ('binomial', ('6', '.4'), stats.binom, (6, .4)),
    ('poisson', ('2.5',), stats.poisson, (2.5,)),
    ('poisson', ('0',), stats.poisson, (0,)),
])
def test_distribution_operations_match_scipy(name, fields, scipy, pars):
    parameters = distribution_parameters(name, fields)
    for op, values in [('density', [-1, 0, 2.3, 99, np.nan]),
                       ('cdf', [-1, 0, 2.3, np.inf, np.nan]),
                       ('ppf', [0, .001, .5, .99, 1, np.nan])]:
        function = (scipy.pdf if name == 'normal' else scipy.pmf) if op == 'density' else getattr(scipy, op)
        np.testing.assert_allclose(distribution_values(name, parameters, op, values),
                                   function(values, *pars))
    with pytest.raises(ValueError, match='0 至 1'):
        distribution_values(name, parameters, 'ppf', [-.01, 1.01])


@pytest.mark.parametrize(('name', 'fields', 'expected_bounds'), [
    ('normal', ('0', '1'), (-np.inf, np.inf)),
    ('uniform', ('4', '9'), (4, 9)),
    ('binomial', ('6', '1'), (6, 6)),
    ('poisson', ('0', ''), (0, 0)),
])
def test_seeded_generation(name, fields, expected_bounds):
    pars = distribution_parameters(name, fields)
    values = random_values(name, pars, 100, 451)
    np.testing.assert_array_equal(values, random_values(name, pars, 100, 451))
    assert (values >= expected_bounds[0]).all() and (values <= expected_bounds[1]).all()
    assert len(values) == 100


def test_menu_creates_worksheet_outputs_and_appends_probability_column(tk_root, monkeypatch):
    monkeypatch.setattr(Minijmp, 'start_logging', lambda self: None)
    app = Minijmp(parent=tk_root)
    original = pd.DataFrame({'x': [0., 1., np.nan], 'g': ['a', 'b', 'a']})
    source = app.addSheet('源数据', original.copy())
    opened = []

    def record_dialog(self, *args):
        original_init(self, *args)
        opened.append(self)

    original_init = WorksheetCalculationDialog.__init__
    monkeypatch.setattr(WorksheetCalculationDialog, '__init__', record_dialog)

    def run(menu, label, settings, selection=()):
        app.nb.select(app.sheetframes['源数据'])
        app._sheet_changed()
        entry = next(i for i in range(menu.index('end') + 1)
                     if menu.type(i) == 'command' and menu.entrycget(i, 'label').strip() == label)
        menu.invoke(entry)
        dialog = opened[-1]
        for key, value in settings.items():
            dialog.fields[key].set(value)
        for index in selection:
            dialog.selection.selection_set(index)
        dialog.apply()
        assert not dialog.main.winfo_exists()

    try:
        run(app.data_menu['var'], '逆堆叠列', {'data': 'C1  x', 'group': 'C2  g'})
        pd.testing.assert_frame_equal(app.getCurrentTable().model.df,
                                      pd.DataFrame({'a': [0., np.nan], 'b': [1., np.nan]}))
        run(app.table_menu['var'], '从列随机抽样', {'count': '3', 'seed': '77'}, (0, 1))
        assert len(app.getCurrentTable().model.df) == 3
        run(app.table_menu['var'], '生成随机数据', {'count': '7', 'seed': '77'})
        assert len(app.getCurrentTable().model.df) == 7
        run(app.table_menu['var'], '概率分布', {'input': 'C1  x', 'name': '新表结果'})
        np.testing.assert_allclose(app.getCurrentTable().model.df['新表结果'], stats.norm.pdf(original.x))
        pd.testing.assert_frame_equal(source.model.df, original)
        run(app.table_menu['var'], '概率分布', {'input': 'C1  x', 'output': '当前工作表新列'})
        assert app.getCurrentTable() is source
        np.testing.assert_allclose(source.model.df['概率分布结果'], stats.norm.pdf(original.x))
        pd.testing.assert_frame_equal(source.model.df.iloc[:, :2], original)
    finally:
        dispose(app)
