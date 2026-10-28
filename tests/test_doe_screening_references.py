"""独立审计固定参考数据；不导入任何生产 DOE 生成器。"""
import csv
import hashlib
import json
from itertools import combinations
from pathlib import Path

import numpy as np
import pytest


ROOT = Path(__file__).parent / 'fixtures' / 'doe_screening_reference'
MANIFEST = json.loads((ROOT / 'manifest.json').read_text(encoding='utf-8'))


def test_continuous_reference_verifier_matches_its_local_manifest():
    import importlib.util
    spec = importlib.util.spec_from_file_location('dsd_reference_verifier', ROOT / 'dsd' / 'verify.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert set(module.verify()) == {'dsd-06-continuous', 'dsd-07-continuous',
                                    'dsd-08-continuous', 'dsd-10-continuous'}


def test_manifest_complete_and_unique():
    cases = MANIFEST['fixtures']
    assert cases
    assert len({case['id'] for case in cases}) == len(cases)
    assert len({case['path'] for case in cases}) == len(cases)
    required = {'id', 'path', 'family', 'factors', 'runs', 'factor_types',
                'encoding', 'replicates', 'blocks', 'source', 'source_url',
                'source_version', 'equivalence', 'sha256', 'independent_validation'}
    for case in cases:
        assert required <= case.keys(), case['id']
        assert case['source_url'].startswith('https://'), case['id']


@pytest.mark.parametrize('case', MANIFEST['fixtures'], ids=lambda x: x['id'])
def test_reference_matrix(case):
    path = ROOT / case['path']
    assert hashlib.sha256(path.read_bytes()).hexdigest() == case['sha256']
    with path.open(encoding='utf-8', newline='') as stream:
        rows = list(csv.reader(stream))
    offset = 1
    assert rows[0][offset:] == [f'X{i}' for i in range(1, case['factors'] + 1)]
    if offset:
        assert rows[0][0] == 'standard_order'
        assert [int(row[0]) for row in rows[1:]] == list(range(1, case['runs'] + 1))
    x = np.asarray([[int(v) for v in row[offset:]] for row in rows[1:]], dtype=int)
    n, k = x.shape
    assert (n, k) == (case['runs'], case['factors'])
    assert np.linalg.matrix_rank(np.column_stack((np.ones(n), x))) == k + 1
    duplicate_model = np.column_stack((np.ones(n), x[:, 0], x[:, 0]))
    assert np.linalg.matrix_rank(duplicate_model) == 2
    assert np.array_equal(x.sum(axis=0), np.zeros(k))
    gram = x.T @ x
    if case['family'] != 'dsd_mixed':
        assert np.array_equal(gram, np.diag(np.diag(gram)))
    permuted = x[::-1, ::-1].copy()
    permuted[:, 0] *= -1
    expected_gram = gram[::-1, ::-1].copy()
    expected_gram[0, :] *= -1
    expected_gram[:, 0] *= -1
    assert np.array_equal(permuted.T @ permuted, expected_gram)
    if case['family'] == 'pb':
        assert set(np.unique(x)) == {-1, 1}
        assert k < n and n % 4 == 0
        assert np.array_equal(gram, n * np.eye(k, dtype=int))
        projection = [abs(int(x[:, i] @ (x[:, j] * x[:, h])))
                      for i in range(k) for j, h in combinations(range(k), 2)
                      if i not in (j, h)]
        expected = {12: {4: 495}, 20: {4: 2736, 12: 171}, 24: {0: 3036, 8: 2277},
                    28: {4: 7800, 12: 936, 20: 39}, 36: {4: 16320, 12: 3264, 28: 51}}[n]
        assert {v: projection.count(v) for v in set(projection)} == expected
        assert max(projection) < n
        assert int(x[:, 0] @ (x[:, 1] * x[:, 2])) == {12: -4, 20: -4, 24: 0, 28: -20, 36: -28}[n]
    elif case['family'] == 'dsd':
        assert set(np.unique(x)) == {-1, 0, 1}
        assert np.count_nonzero(np.all(x == 0, axis=1)) == 1
        for i, j in combinations(range(k), 2):
            assert np.array_equal(x.T @ (x[:, i] * x[:, j]), np.zeros(k))
        for i in range(k):
            assert np.array_equal(x.T @ (x[:, i] ** 2), np.zeros(k))
        quadratic = np.column_stack((np.ones(n), x, x * x))
        assert np.linalg.matrix_rank(quadratic) == 1 + 2 * k
        model = np.column_stack((np.ones(n), x[:, 0], x[:, 1], x[:, 0] ** 2))
        assert np.linalg.matrix_rank(model) == 4
        beta = np.array([3., 2., -1., 4.])
        y = model @ beta
        fitted, _, rank, _ = np.linalg.lstsq(model, y, rcond=None)
        assert rank == 4 and np.allclose(fitted, beta, atol=1e-10, rtol=0)
        assert np.allclose(model @ fitted, y, atol=1e-10, rtol=0)
    elif case['family'] == 'dsd_mixed':
        assert all(set(x[:, i]) == {-1, 0, 1} for i in range(4))
        assert set(x[:, 4]) == {-1, 1}
        assert np.count_nonzero(np.all(x[:, :4] == 0, axis=1)) == 2
        assert np.array_equal(x[6:12], -x[:6])
        assert np.array_equal(x[13], -x[12])
        main = np.column_stack((np.ones(n), x))
        assert round(np.linalg.det(main.T @ main)) == 1736000
        with (ROOT / 'dsd' / 'dsd_06_cont_13.csv').open(encoding='utf-8', newline='') as stream:
            base = np.asarray([[int(v) for v in row[1:6]] for row in list(csv.reader(stream))[1:13]])
        zeros = np.flatnonzero(base[:, 4] == 0)
        assert len(zeros) == 2
        assert np.array_equal(x[:12, :4], base[:, :4])
        assert np.array_equal(np.delete(x[:12, 4], zeros), np.delete(base[:, 4], zeros))
        for z in (-1, 1):
            for b in (-1, 1):
                candidate = x.copy()
                candidate[zeros, 4] = (z, -z)
                candidate[-2:, 4] = (b, -b)
                design = np.column_stack((np.ones(n), candidate))
                assert round(np.linalg.det(design.T @ design)) == 1736000
        interactions = np.column_stack([x[:, i] * x[:, j] for i, j in combinations(range(k), 2)])
        projection = np.linalg.lstsq(main, interactions, rcond=None)[0]
        assert np.allclose(projection[1:], 0, atol=1e-12)
        assert np.isclose(np.max(np.abs(projection[0])), 1 / 7)
    else:
        pytest.fail(f"unknown reference family: {case['family']}")
