from itertools import combinations, product
from math import comb

import numpy as np
import pandas as pd
import pytest
from scipy.stats import chi2

from nonparametric_tests import (
    friedman_test, grouped_rank_test, mann_whitney_test, runs_test,
    sign_test, signed_rank_test,
)


def test_sign_drops_zero_and_missing_with_exact_interval():
    result = sign_test([0, 1, 2, 3, 4, -1, -2, np.nan])
    assert (result["positive"], result["negative"], result["zero"]) == (4, 2, 1)
    assert result["pvalue"] == 2 * sum(comb(6, k) for k in range(3)) / 64
    assert result["estimate"] == 1
    assert result["interval"] == (-2, 4, 1-2/128)


def test_signed_rank_exact_by_enumeration_and_tied_ranks():
    result = signed_rank_test([0, 1, 3, -5, 8], alternative="greater")
    totals = [sum(r for r, b in enumerate(bits, 1) if b)
              for bits in product((0, 1), repeat=4)]
    assert result["statistic"] == 7
    assert result["pvalue"] == sum(t >= 7 for t in totals) / len(totals)
    tied = signed_rank_test([0, 1, 1, -2, 4])
    assert (tied["positive"], tied["negative"]) == (7, 3)
    assert tied["interval"] is None
    assert signed_rank_test([0, 0])["pvalue"] == 1


def test_mann_whitney_rank_subsets_and_shift():
    x, y = [1, 2, 8], [3, 4, 5, 7]
    result = mann_whitney_test(x, y, alternative="less", alpha=.2)
    totals = [sum(ranks)-6 for ranks in combinations(range(1, 8), 3)]
    assert result["statistic"] == 4
    assert result["pvalue"] == pytest.approx(sum(t <= 4 for t in totals)/35)
    assert result["estimate"] == -2
    assert result["interval"] == pytest.approx((-5, 4, 1-2*sum(t <= 1 for t in totals)/35))
    assert mann_whitney_test([1, 2], [2, 3])["statistic"] == .5


def test_kruskal_and_mood_hand_calculated():
    kw = grouped_rank_test([[1, 2, 3], [3, 4, 5]])
    h = (12 / 42 * (6.5**2 / 3 + 14.5**2 / 3) - 21) / (1 - 6 / 210)
    assert kw["statistic"] == pytest.approx(h)
    assert kw["pvalue"] == pytest.approx(chi2.sf(h, 1))
    mood = grouped_rank_test([[1, 2, 3], [3, 4, 5]], mood=True)
    assert [row[2:4] for row in mood["groups"]] == [(0, 3), (2, 1)]
    assert mood["pvalue"] == pytest.approx(chi2.sf(3, 1))


def test_friedman_hand_calculated_and_rejects_invalid_blocks():
    frame = pd.DataFrame(dict(y=[1, 1, 2, 3, 2, 4, 4, 3, 5],
                              t=list("abc")*3, b=np.repeat(range(3), 3)))
    result = friedman_test(frame, "y", "t", "b")
    assert [group[1] for group in result["groups"]] == [5.5, 3.5, 9]
    q = (12 / 36 * (5.5**2 + 3.5**2 + 9**2) - 36) / (1 - 6/72)
    assert result["pvalue"] == pytest.approx(chi2.sf(q, 2))
    with pytest.raises(ValueError):
        friedman_test(frame.iloc[:-1], "y", "t", "b")
    with pytest.raises(ValueError):
        friedman_test(pd.concat([frame, frame.iloc[:1]]), "y", "t", "b")


def test_runs_exact_by_enumerating_ordered_sequences():
    result = runs_test([1, 0, np.nan, 1, -1, -1], threshold=0)
    sequences = [tuple(i in picks for i in range(4))
                 for picks in combinations(range(4), 2)]
    counts = [1 + sum(x != y for x, y in zip(seq, seq[1:])) for seq in sequences]
    assert result["statistic"] == 2
    assert result["pvalue"] == 2 * sum(r <= 2 for r in counts) / len(counts)
    assert runs_test([1, -1, 1, -1])["statistic"] == 4


def test_f3_1_native_input_cases():
    from scipy.stats import binom, friedmanchisquare, kruskal, mannwhitneyu

    x = np.arange(1, 13)
    y = np.array([2, 4, 4, 6, 8, 8, 9, 12, 12, 15, 15, 18])
    groups = x.reshape(4, 3)
    assert sign_test(x, 4)["pvalue"] == pytest.approx(2*binom.cdf(3, 11, .5))
    rank = signed_rank_test(x, 4)
    assert (rank["positive"], rank["negative"], rank["estimate"]) == (55.5, 10.5, 6.5)
    assert mann_whitney_test(x, y)["pvalue"] == pytest.approx(
        mannwhitneyu(x, y, method="asymptotic").pvalue)
    assert grouped_rank_test(groups)["pvalue"] == pytest.approx(kruskal(*groups).pvalue)
    assert grouped_rank_test(groups, mood=True)["statistic"] == 12
    assert runs_test(x)["pvalue"] == pytest.approx(4/comb(12, 6))
    values = np.array([1, 2, 4, 3, 5, 7, 2, 6, 8, 4, 7, 9])
    frame = pd.DataFrame(dict(y=values, t=[1, 2, 3]*4, b=np.repeat(range(4), 3)))
    assert friedman_test(frame, "y", "t", "b")["pvalue"] == pytest.approx(
        friedmanchisquare(*values.reshape(4, 3).T).pvalue)
