"""G1：检验方向、统计解释及公共表格的回归保护。"""
from pathlib import Path
from unittest.mock import Mock

import numpy as np
import pytest
from prettytable import PrettyTable
from scipy import stats
from statsmodels.stats.diagnostic import normal_ad
from wcwidth import wcswidth

from chi_sq import chi2_test_stdev, chi2_var_1sample, var_1sample
from linear_fit import linear_fit
from nonpara_cor import spearman, kendall
from proportion_test import prop_2sample, prop_test_1sample
from t_test import t_test_1sample, z_test_1sample, paired_t_test, t_test_2samples
from utilities import gen_table, mean_std_CIs, norm_test, pearson_correlation, add_Y_refs


DATA = [1, 2, 4, 5, 7, 8]
OTHER = [2, 4, 3, 8, 6, 10]
P_EXPLANATION = 'p 值是在原假设及检验模型成立时，得到当前或更极端检验统计量的概率。'


def report(function, *args, **kwargs):
    lines = []
    result = function(*args, print_out=True, print_port=lines.append, **kwargs)
    return result, '\n'.join(lines)


def table_row(text, label):
    return next([cell.strip() for cell in line.split('|')[1:-1]]
                for line in text.splitlines() if line.startswith('|')
                and line.split('|')[1].strip() == label)


@pytest.mark.parametrize('alpha', [.05, .1])
@pytest.mark.parametrize('null', [0, 10])
@pytest.mark.parametrize('kind', ['t', 'z', 'paired'])
def test_mean_tests_match_tail_directions_and_confidence_bounds(kind, null, alpha):
    if kind == 'paired':
        sample = np.array(DATA) - np.array(OTHER)
        result, text = report(paired_t_test, DATA, OTHER, u0=null, alpha=alpha)
        parameter = 'μd'
    else:
        sample = np.array(DATA)
        function = t_test_1sample if kind == 't' else z_test_1sample
        extra = {} if kind == 't' else {'s0': 2}
        result, text = report(function, DATA, null, alpha=alpha, **extra)
        parameter = 'μ'
        assert P_EXPLANATION in text
    se = (2 if kind == 'z' else np.std(sample, ddof=1)) / np.sqrt(len(sample))
    statistic = (np.mean(sample) - null) / se
    distribution = stats.norm if kind == 'z' else stats.t(df=len(sample) - 1)
    assert result['p lt'] == pytest.approx(distribution.cdf(statistic))
    assert result['p gt'] == pytest.approx(distribution.sf(statistic))
    assert result['p'] == pytest.approx(2 * distribution.sf(abs(statistic)))
    assert result['u0_95range'] == pytest.approx(np.mean(sample) + se * distribution.ppf([alpha/2, 1-alpha/2]))
    assert result['u0 lower'] == pytest.approx(np.mean(sample) + se * distribution.ppf(alpha))
    assert result['u0 upper'] == pytest.approx(np.mean(sample) + se * distribution.ppf(1-alpha))
    assert f'H0: {parameter} = μ0' in text
    for label, symbol, key in [('左尾', '<', 'p lt'), ('右尾', '>', 'p gt'), ('双侧', '≠', 'p')]:
        row = table_row(text, label)
        assert row[1] == f'{"mu_d" if kind == "paired" else "mu"} {"!=" if symbol == "≠" else symbol} mu0'
        assert row[-1] == f'{result[key]:.3f}'
    assert table_row(text, '单侧置信下限')[1:] == [f'{result["u0 lower"]:.3f}', '*']
    assert table_row(text, '单侧置信上限')[1:] == ['*', f'{result["u0 upper"]:.3f}']


@pytest.mark.parametrize('pooled', [False, True])
@pytest.mark.parametrize('d0', [-2, 3])
def test_two_sample_t_preserves_second_minus_first_direction(pooled, d0):
    result, text = report(t_test_2samples, DATA, OTHER, pooled=pooled, d0=d0)
    assert result['p lower'] == pytest.approx(stats.t.cdf(result['t'], result['df']))
    assert result['p upper'] == pytest.approx(stats.t.sf(result['t'], result['df']))
    assert result['t'] > 0 if d0 < 0 else result['t'] < 0
    for label, symbol, key in [('左尾', '<', 'p lower'), ('右尾', '>', 'p upper'), ('双侧', '≠', 'p')]:
        row = table_row(text, label)
        assert row[1] == f'mu2 - mu1 {"!=" if symbol == "≠" else symbol} d0'
        assert row[-1] == f'{result[key]:.3f}'
    assert result['CI'][0] < np.mean(OTHER) - np.mean(DATA) < result['CI'][1]
    if d0 == -2:
        expected = stats.ttest_ind(np.array(OTHER) - d0, DATA, equal_var=pooled)
        assert result['p'] == pytest.approx(expected.pvalue)


@pytest.mark.parametrize('alpha', [.05, .1])
@pytest.mark.parametrize('s0', [.5, 5])
def test_standard_deviation_tests_match_tails_and_bounds(s0, alpha):
    result, text = report(chi2_var_1sample, DATA, s0=s0, alpha=alpha)
    distribution = stats.chi2(df=len(DATA)-1)
    statistic = (len(DATA)-1) * np.var(DATA, ddof=1) / s0**2
    assert result['p lt'] == pytest.approx(distribution.cdf(statistic))
    assert result['p gt'] == pytest.approx(distribution.sf(statistic))
    assert table_row(text, '左尾')[1:] == ['sigma < sigma0', f'{statistic:.3f}', str(len(DATA)-1), f'{result["p lt"]:.3f}']
    assert table_row(text, '右尾')[1:] == ['sigma > sigma0', f'{statistic:.3f}', str(len(DATA)-1), f'{result["p gt"]:.3f}']
    assert table_row(text, '单侧置信上限')[1:] == ['*', f'{result["CI upper"]:.3f}']
    assert table_row(text, '单侧置信下限')[1:] == [f'{result["CI lower"]:.3f}', '*']
    numerator = np.sqrt((len(DATA)-1) * np.var(DATA, ddof=1))
    assert result['CI 95'] == pytest.approx(numerator / np.sqrt(distribution.ppf([1-alpha/2, alpha/2])))
    assert result['CI lower'] == pytest.approx(numerator / np.sqrt(distribution.ppf(1-alpha)))
    assert result['CI upper'] == pytest.approx(numerator / np.sqrt(distribution.ppf(alpha)))
    legacy, legacy_text = report(chi2_test_stdev, DATA, s0, alpha=alpha)
    assert legacy['p'] == pytest.approx(result['p gt'])
    assert table_row(legacy_text, '右尾')[1] == 'sigma > sigma0'
    assert table_row(legacy_text, '右尾')[-1] == f'{legacy["p"]:.3f}'
    assert '样本标准差的抽样分布中央区间' in legacy_text
    assert '总体标准差的置信区间' in legacy_text
    assert '双侧置信区间' in legacy_text and '单侧置信上限' in legacy_text


def test_bonett_assumptions_are_not_an_unconditional_guarantee():
    result, text = report(var_1sample, DATA, s0=2)
    assert '近似推断' in text and '重尾分布需谨慎' in text
    assert '卡方方法假定总体服从正态分布' in text
    assert result['p'] == chi2_var_1sample(DATA, s0=2)['p']


@pytest.mark.parametrize('alpha', [.05, .1])
def test_mean_sd_intervals_are_confidence_limits_not_parameter_probabilities(alpha):
    result, text = report(mean_std_CIs, DATA, alpha=alpha)
    for key, label in [('mean', '均值'), ('std', '标准差')]:
        lower, upper = result[f'{key} 1side']
        row = next(line for line in text.splitlines() if line.startswith('| 总体'+label)).split('|')
        assert float(row[-3]) == pytest.approx(lower, abs=.0005)
        assert float(row[-2]) == pytest.approx(upper, abs=.0005)
    assert '单侧置信下限' in text and '单侧置信上限' in text
    assert '长期比例' in text
    assert result['mean 2side'] == pytest.approx(stats.t.interval(1-alpha, len(DATA)-1, loc=np.mean(DATA), scale=stats.sem(DATA)))
    assert result['std 2side'] == pytest.approx(chi2_var_1sample(DATA, s0=1, alpha=alpha)['CI 95'])


def test_correlation_normality_and_regression_explanations_and_values():
    correlation, text = report(pearson_correlation, DATA, OTHER)
    assert P_EXPLANATION in text and 'H0：总体 Pearson 相关系数 ρ = 0' in text
    assert correlation['p'] == pytest.approx(stats.pearsonr(DATA, OTHER).pvalue)
    normal, text = report(norm_test, DATA)
    assert P_EXPLANATION in text and '备择假设 H1：总体不服从正态分布' in text
    assert normal['shapiro p'] == stats.shapiro(DATA).pvalue
    assert normal['AD p'] == normal_ad(np.array(DATA))[1]
    fit, text = report(linear_fit, DATA, OTHER)
    assert P_EXPLANATION in text and '该总体回归系数 = 0' in text
    assert '总体斜率 = 0' in text and '误差服从正态分布' in text
    assert fit['p slope'] == pytest.approx(stats.linregress(DATA, OTHER).pvalue)
    _, lack_text = report(linear_fit, [1, 1, 2, 2, 3, 3], OTHER)
    assert '总体均值与自变量呈线性关系' in lack_text and '存在失拟' in lack_text


@pytest.mark.parametrize('function, reference', [(spearman, stats.spearmanr), (kendall, stats.kendalltau)])
def test_rank_correlation_null_is_zero_coefficient(function, reference):
    result, text = report(function, DATA, OTHER)
    assert '秩相关系数' in text and '不等同于变量独立' in text
    assert '备择假设 H1' in text
    assert result['cor'] == reference(DATA, OTHER).statistic
    assert result['p'] == reference(DATA, OTHER).pvalue


@pytest.mark.parametrize('events', [3, 14])
def test_one_proportion_exact_and_normal_tail_labels(events):
    result, text = report(prop_test_1sample, events=events, N=20, p0=.4)
    for column, symbol, alternative, normal_p in [(2, '<', 'less', result['Z p less']), (3, '>', 'greater', 1-result['Z p less'])]:
        assert f'p {symbol} p0' in text
        assert table_row(text, '正态近似')[column] == f'{normal_p:.3f}'
        assert table_row(text, '二项精确')[column] == '%.3f' % stats.binomtest(events, 20, .4, alternative=alternative).pvalue
    assert '单侧置信上限' in text and '单侧置信下限' in text
    assert 'Clopper-Pearson Exact p-value' not in text
    assert result['CI norm']['CI low'] <= events/20 <= result['CI norm']['CI high']
    assert result['CI exact']['CI low'] <= events/20 <= result['CI exact']['CI high']
    interval_text = text.split('总体比例的置信区间')[1]
    for method, key in [('正态近似', 'CI norm'), ('Clopper-Pearson', 'CI exact')]:
        row = table_row(interval_text, method)
        assert float(row[-2]) == pytest.approx(result[key]['CI low'], abs=.0005)
        assert float(row[-1]) == pytest.approx(result[key]['CI high'], abs=.0005)
    estimate = events/20
    se = np.sqrt(estimate*(1-estimate)/20)
    assert result['CI norm']['CI low'] == pytest.approx(estimate + stats.norm.ppf(.05)*se)
    assert result['CI norm']['CI high'] == pytest.approx(estimate + stats.norm.ppf(.95)*se)
    assert result['CI exact']['CI low'] == pytest.approx(stats.beta.ppf(.05, events, 21-events))
    assert result['CI exact']['CI high'] == pytest.approx(stats.beta.ppf(.95, events+1, 20-events))


@pytest.mark.parametrize('e1,e2', [(3, 14), (14, 3)])
def test_two_proportion_table_columns_match_alternatives(e1, e2):
    result, text = report(prop_2sample, n1=20, n2=20, e1=e1, e2=e2)
    assert all(f'p1 - p2 {sign} 0' in text for sign in ['≠', '<', '>'])
    for method, suffix in [('Fisher 精确', ' Fisher'), ('正态近似（非合并）', ''), ('正态近似（合并）', ' Pooled')]:
        row = table_row(text, method)
        assert float(row[-2]) == pytest.approx(result['p p1<p2'+suffix], abs=.0005)
        assert float(row[-1]) == pytest.approx(result['p p1>p2'+suffix], abs=.0005)
    for symbol, alternative in [('<', 'less'), ('>', 'greater')]:
        assert result[f'p p1{symbol}p2 Fisher'] == pytest.approx(stats.fisher_exact([[e1, 20-e1], [e2, 20-e2]], alternative=alternative).pvalue)
    difference = (e1-e2)/20
    se = np.sqrt((e1/20)*(1-e1/20)/20 + (e2/20)*(1-e2/20)/20)
    assert float(table_row(text, '单侧置信上限')[-1]) == pytest.approx(difference + stats.norm.ppf(.95)*se, abs=.0005)
    assert float(table_row(text, '单侧置信下限')[1]) == pytest.approx(difference + stats.norm.ppf(.05)*se, abs=.0005)


def test_prettytable_cjk_multiline_widths_and_original_values():
    data = [['项目 Item', '估计值', '备注'], ['均值\nMean', '1.230', '中文 ABC'], ['SD', '-0.012', '测试']]
    table = gen_table(data)
    assert isinstance(table, PrettyTable)
    assert table.rows == data[1:]
    lines = str(table).splitlines()
    assert len({wcswidth(line) for line in lines}) == 1
    separators = [[wcswidth(line[:i]) for i, char in enumerate(line) if char == '|'] for line in lines if '|' in line]
    assert all(positions == separators[0] for positions in separators)
    table.align['估计值'] = 'r'
    assert table.align['估计值'] == 'r'


def test_reference_labels_do_not_print_debug_data(capsys):
    ax = Mock()
    ax.get_xlim.return_value = (0, 10)
    add_Y_refs(ax, [2], label=True)
    ax.axhline.assert_called_once()
    ax.text.assert_called_once()
    assert capsys.readouterr().out == ''


def test_confirmed_wrong_explanations_removed_from_sources():
    root = Path(__file__).resolve().parents[1] / 'code'
    banned = {
        't_test.py': ['P-value is the prob of that population mean', 'for one tailed test 1/2', 'H0: u == u0, H1: ud'],
        'utilities.py': ['Prob that mean', 'Prob that SD', 'probability of there is no linear relationship', 'probability of sampling from a normal'],
        'linear_fit.py': ['probabilities of each term == 0', 'probability of slope == 0', 'probabilities of true dist is normal', 'probability of the true relationship'],
        'chi_sq.py': ['H0 s==s0, H1 s>s0', 'valid for any continuous distribution', 'confidence the population SD lower'],
        'proportion_test.py': ['Clopper-Pearson Exact p-value'],
        'nonpara_cor.py': ['which means no monotonic relationship', 'which means no monotonic association'],
        'plots.py': ["print(self.figsize)", "print('plot close')"],
        'txt_output.py': ["print('txt win close')"],
    }
    for name, snippets in banned.items():
        source = (root / name).read_text(encoding='utf-8')
        for snippet in snippets:
            assert snippet not in source, (name, snippet)
