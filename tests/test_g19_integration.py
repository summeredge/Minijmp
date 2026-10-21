"""G19：Fisher 浮点下溢时的有界搜索及报告原值。"""
from types import SimpleNamespace

import pytest
from scipy.stats import fisher_exact, hypergeom

import proportion_test
from stat_table import StatTable


@pytest.mark.parametrize('events', [1, 9999])
def test_fisher_underflow_search_stays_in_support(monkeypatch, events):
    rv = hypergeom(20000, 10000, 10000)
    lower, upper = rv.support()
    assert rv.pmf(events) == 0
    calls = []

    def checked_pmf(value):
        # 在越界的第一次调用直接失败，旧实现不会使测试进程无限循环。
        assert lower <= value <= upper, 'Fisher search left its finite support'
        calls.append(value)
        return rv.pmf(value)

    monkeypatch.setattr(proportion_test, 'hypergeom', lambda *args: SimpleNamespace(
        pmf=checked_pmf, cdf=rv.cdf, sf=rv.sf, support=rv.support))
    lines = []
    result = proportion_test.prop_2sample(
        n1=10000, n2=10000, e1=events, e2=10000-events,
        print_out=True, print_port=lines.append)
    expected = fisher_exact([[events, 10000-events], [10000-events, events]]).pvalue
    assert result['p Fisher'] == expected == 0
    assert len(calls) <= upper-lower+2
    table = next(table for table in lines if isinstance(table, StatTable) and table.title == '检验结果')
    assert table.values[0][2:] == [result['p Fisher'], result['p p1<p2 Fisher'], result['p p1>p2 Fisher']]
