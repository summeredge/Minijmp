"""独立手工列联表、二项区间、Fleiss 及 Kendall 验证。"""
import numpy as np
import pandas as pd
import pytest
from scipy import stats
from attribute_agreement import attribute_agreement, agreement_interval, kendall_concordance


def long_data(matrix, appraisers=2, trials=1, standard=None):
    matrix = np.asarray(matrix)
    rows = [[i, f'A{a}', t+1, matrix[i, a*trials+t]] for i in range(len(matrix)) for a in range(appraisers) for t in range(trials)]
    frame = pd.DataFrame(rows, columns=['sample', 'appraiser', 'trial', 'response'])
    if standard is not None:
        frame['standard'] = [standard[i] for i in frame['sample']]
    return frame


def analyze(frame, **kwargs):
    return attribute_agreement(frame, 'sample', 'appraiser', 'response', trial='trial', **kwargs)


def test_cohen_manual_contingency_and_test_direction():
    matrix = [[0, 0]]*20+[[0, 1]]*5+[[1, 0]]*10+[[1, 1]]*15
    result = analyze(long_data(matrix))
    table = result['tables']['Kappa'].set_index('方法')
    # Po=.7, Pe=.5; SE0^2=(Pe+Pe^2 - sum p_i*q_i*(p_i+q_i)) / (N*(1-Pe)^2)
    expected_se = np.sqrt((.5+.25-(.5*.6*(.5+.6)+.5*.4*(.5+.4)))/(50*.25))
    assert table.loc['Cohen', 'Kappa'] == pytest.approx(.4)
    assert table.loc['Cohen', 'SE0'] == pytest.approx(expected_se)
    assert table.loc['Cohen', 'Z'] == pytest.approx(.4/expected_se)
    assert table.loc['Cohen', '右尾 p'] == pytest.approx(stats.norm.sf(.4/expected_se))
    matched = result['tables']['完全一致率'].query('范围 == "评价员之间"').iloc[0]
    assert matched['一致样本数'] == 35 and matched['一致率'] == .7


def test_fleiss_independent_pair_enumeration_multicategory():
    from itertools import combinations
    matrix = np.array([[0, 0, 0], [1, 1, 2], [2, 2, 2], [0, 1, 2], [0, 0, 1]])
    result = analyze(long_data(matrix, appraisers=3))
    po = np.mean([np.mean([row[a] == row[b] for a, b in combinations(range(3), 2)]) for row in matrix])
    marginals = [np.mean(matrix == c) for c in range(3)]
    pe = sum(p*p for p in marginals)
    fleiss = result['tables']['Kappa'].iloc[0]
    assert fleiss['Kappa'] == pytest.approx((po-pe)/(1-pe))
    assert pd.isna(fleiss['右尾 p'])  # small N: no invented inference
    assert len(result['tables']['各类别Kappa']) == 3


def test_fleiss_se_balanced_binary_analytic():
    matrix = np.tile([[0, 0, 0], [1, 1, 1], [0, 1, 0], [1, 0, 1]], (10, 1))
    result = analyze(long_data(matrix, appraisers=3))
    row = result['tables']['Kappa'].iloc[0]
    # Equal binary margins: Var0=2/[N*m*(m-1)].
    assert row['SE0'] == pytest.approx(np.sqrt(2/(40*3*2)))
    assert row['右尾 p'] == pytest.approx(stats.norm.sf(row['Kappa']/row['SE0']))


def test_fleiss_se_unequal_margins_independent_multinomial_enumeration():
    from itertools import product, combinations
    probabilities = np.array([.5, .3, .2])
    assignments = list(product(range(3), repeat=3))
    matrix, expected_square = [], 0.
    pe = float(probabilities @ probabilities)
    for assignment in assignments:
        weight = np.prod(probabilities[list(assignment)])
        matrix.extend([assignment]*round(weight*1000))
        pair_agreement = sum(assignment[i] == assignment[j] for i, j in combinations(range(3), 2))/3
        # Delta influence of (Po-Pe)/(1-Pe), enumerating every iid rater assignment.
        influence = (pair_agreement-2*np.mean(probabilities[list(assignment)])+pe)/(1-pe)
        expected_square += weight*influence**2
    result = analyze(long_data(matrix, appraisers=3))
    row = result['tables']['Kappa'].iloc[0]
    assert row['SE0'] == pytest.approx(np.sqrt(expected_square/len(matrix)))


def test_exact_intervals_against_binomial_inversion_and_endpoints():
    assert agreement_interval(50, 50)[0] == pytest.approx(.05**(1/50))
    assert agreement_interval(0, 50)[1] == pytest.approx(1-.05**(1/50))
    low, high = agreement_interval(37, 50)
    assert stats.binom.sf(36, 50, low) == pytest.approx(.025)
    assert stats.binom.cdf(37, 50, high) == pytest.approx(.025)
    assert low == pytest.approx(.59655, abs=.0001)


def test_within_vs_standard_and_correlated_accuracy():
    matrix = [[0, 0, 0, 0], [1, 1, 0, 1], [0, 0, 1, 1], [1, 1, 1, 1]]
    frame = long_data(matrix, trials=2, standard=[1, 1, 0, 0])
    original = frame.copy(deep=True)
    result = analyze(frame, standard='standard')
    table = result['tables']['完全一致率']
    assert table.query('范围 == "评价员内部"')['一致率'].tolist() == [1., .75]
    assert table.query('范围 == "评价员与标准"')['一致率'].tolist() == [.5, 0.]
    assert table.query('范围 == "全部评价员与标准"')['一致样本数'].item() == 0
    accuracy = result['tables']['正确评价比例']
    assert accuracy.query('评价员 == "A0" and 试次 == "所有试次"')['正确率'].item() == .5
    assert '分类不一致' in result['tables']
    pd.testing.assert_frame_equal(frame, original)


@pytest.mark.parametrize('matrix,expected', [([[0, 0], [1, 1]]*20, 1), ([[0, 1], [1, 0]]*20, -1), ([[0, 0], [0, 1], [1, 0], [1, 1]]*10, 0)])
def test_perfect_opposite_random_agreement(matrix, expected):
    result = analyze(long_data(matrix))
    assert result['tables']['Kappa'].set_index('方法').loc['Cohen', 'Kappa'] == pytest.approx(expected)
    assert not result['has_standard'] and '正确评价比例' not in result['tables']


def test_kendall_independent_rank_formula_and_friedman():
    matrix = np.array([[0, 0, 0], [0, 1, 0], [1, 1, 1], [2, 2, 2]]*3)
    w, chi, df, p = kendall_concordance(matrix)
    # Friedman treats rating sequences as blocks and samples as treatments.
    reference = stats.friedmanchisquare(*[matrix[i] for i in range(len(matrix))])
    assert chi == pytest.approx(reference.statistic)
    assert p == pytest.approx(reference.pvalue)
    assert w == pytest.approx(chi/(3*(len(matrix)-1)))
    assert df == len(matrix)-1
    frame = long_data(matrix, appraisers=3, standard=matrix[:, 0])
    result = analyze(frame, standard='standard', order=['0', '1', '2'])
    assert 'Kendall' in result['tables']
    assert result['tables']['Kendall'].query('指标 == "Kendall tau-b"')['系数'].iloc[0] == pytest.approx(1)
    with pytest.raises(ValueError, match='顺序'):
        analyze(frame, order=['0', '2'])


def test_design_validation_and_inferred_trials():
    frame = long_data([[0, 0, 0, 1], [1, 1, 1, 1], [0, 1, 0, 1]], trials=2, standard=[0, 1, 0])
    inferred = attribute_agreement(frame, 'sample', 'appraiser', 'response', standard='standard')
    assert inferred['tables']['设计']['试次数'].item() == 2
    with pytest.raises(ValueError, match='不平衡'):
        analyze(frame.iloc[1:])
    with pytest.raises(ValueError, match='重复记录'):
        analyze(pd.concat([frame, frame.iloc[:1]]))
    bad = frame.copy(); bad.loc[0, 'standard'] = 1
    with pytest.raises(ValueError, match='矛盾'):
        analyze(bad, standard='standard')
    bad = frame.copy(); bad.loc[0, 'response'] = None
    with pytest.raises(ValueError, match='空值'):
        analyze(bad)
    one = long_data([[0], [1], [1]], appraisers=1)
    result = analyze(one)
    assert result['tables']['完全一致率']['一致率'].isna().all()


def test_distinct_appraiser_identifiers_with_same_display_text():
    frame = long_data([[0, 0, 1, 1], [1, 1, 0, 0]]*20, trials=2, standard=[0, 1]*20)
    frame['appraiser'] = frame['appraiser'].map({'A0': 1, 'A1': '1'})
    result = analyze(frame, standard='standard')
    means = result['tables']['Kappa'].query('范围 == "评价员与标准" and 方法 == "Cohen 试次均值"')
    assert means['Kappa'].tolist() == [1., -1.]


def test_kendall_tau_asymptotic_direction_against_pair_count_formula():
    matrix = np.column_stack((np.arange(10), np.arange(9, -1, -1)))
    frame = long_data(matrix, standard=np.arange(10))
    result = analyze(frame, standard='standard', order=[str(i) for i in range(10)])
    tau = result['tables']['Kendall'].query('指标 == "Kendall tau-b"')
    # 无并列：S=±45，Var(S)=N(N−1)(2N+5)/18，右尾正态近似。
    z = 45/np.sqrt(10*9*25/18)
    assert tau['系数'].tolist() == pytest.approx([1., -1.])
    np.testing.assert_allclose(tau['右尾 p'], [stats.norm.sf(z), stats.norm.sf(-z)])
