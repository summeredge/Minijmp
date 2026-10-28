"""Minitab 22 用户参考：原文件独立审计及逐配置多重集对比。"""
from collections import Counter
from itertools import combinations
from pathlib import Path
import hashlib
import json

import numpy as np
import pandas as pd
import pytest

from doe_bbd import create_bbd
from doe_core import DesignSpec, FactorSpec


ROOT = Path(__file__).parent / 'fixtures' / 'doe_bbd_reference'
CASES = [(9, 1, 'unblocked', 60), (9, 5, 'block5', 116),
         (9, 10, 'block10', 123), (10, 1, 'unblocked', 120),
         (10, 2, 'block2', 163)]


def load_reference(k, suffix):
    path = ROOT / 'original' / f'bbd{k}-{suffix}.csv'
    manifest = json.loads((ROOT / 'manifest.json').read_text(encoding='utf-8'))
    entry = manifest['files'][path.name]
    assert hashlib.sha256(path.read_bytes()).hexdigest() == entry['sha256']
    data = pd.read_csv(path, encoding=entry['encoding'])
    assert list(data.columns) == entry['columns']
    aliases = {'standard_order': ('标准序', 'StdOrder'),
               'run_order': ('运行序', 'RunOrder'),
               'point_type': ('点类型', 'PtType'), 'block': ('区组', 'Blocks')}
    mapping = dict(entry['system_column_mapping'])
    assert {'standard_order', 'run_order', 'point_type'} <= mapping.keys()
    assert all(key in aliases and mapping[key] in aliases[key] for key in mapping)
    if 'block' not in mapping:
        data = data.assign(__unblocked=1)
        mapping['block'] = '__unblocked'
    return data, mapping, entry['factor_columns']


def quadratic(x):
    return np.column_stack([np.ones(len(x)), x, x*x] +
                           [x[:, i]*x[:, j] for i, j in combinations(range(x.shape[1]), 2)])


def test_english_headers_and_unblocked_column_absence(tmp_path, monkeypatch):
    original = tmp_path / 'original'
    original.mkdir()
    path = original / 'bbd9-unblocked.csv'
    raw = b'StdOrder,RunOrder,PtType,A,B\n1,1,0,0,0\n'
    path.write_bytes(raw)
    entry = {'sha256': hashlib.sha256(raw).hexdigest(), 'encoding': 'utf-8-sig',
             'columns': ['StdOrder', 'RunOrder', 'PtType', 'A', 'B'],
             'system_column_mapping': {'standard_order': 'StdOrder', 'run_order': 'RunOrder',
                                       'point_type': 'PtType'}, 'factor_columns': ['A', 'B']}
    (tmp_path / 'manifest.json').write_text(json.dumps({'files': {path.name: entry}}), encoding='utf-8')
    monkeypatch.setattr(__import__(__name__), 'ROOT', tmp_path)
    data, columns, factors = load_reference(9, 'unblocked')
    assert data[columns['block']].tolist() == [1]
    assert columns['standard_order'] == 'StdOrder' and factors == ['A', 'B']


@pytest.mark.parametrize(('k', 'blocks', 'suffix', '_'), CASES)
def test_reference_mathematical_audit(k, blocks, suffix, _):
    data, col, factor = load_reference(k, suffix)
    x = data[factor].to_numpy(dtype=float)
    n, p = (130, 55) if k == 9 else (170, 66)
    assert len(data) == n and len(factor) == k
    assert set(np.unique(x)) == {-1, 0, 1}
    assert set(data[col['standard_order']]) == set(range(1, n+1))
    assert set(data[col['run_order']]) == set(range(1, n+1))
    assert (data[col['standard_order']] == data[col['run_order']]).all()
    center = np.all(x == 0, axis=1)
    assert center.sum() == 10
    assert (data[col['point_type']].to_numpy() == 0).tolist() == center.tolist()
    assert np.all(np.count_nonzero(x[~center], axis=1) == (3 if k == 9 else 4))
    support = Counter(tuple(np.flatnonzero(row)) for row in x[~center])
    assert len(support) == (12 if k == 9 else 10)
    assert Counter(support.values()) == (Counter({8: 9, 16: 3}) if k == 9 else Counter({16: 10}))
    for i in range(k):
        assert Counter(x[:, i]) == ({-1: 20, 0: 90, 1: 20} if k == 9 else
                                    {-1: 32, 0: 106, 1: 32})
        for j in range(i+1, k):
            assert np.any(x[:, i]*x[:, j])
    matrix = quadratic(x)
    assert matrix.shape == (n, p) and np.linalg.matrix_rank(matrix) == p
    assert np.linalg.cond(matrix) < 10
    labels = data[col['block']].to_numpy()
    assert Counter(labels) == {i: n//blocks for i in range(1, blocks+1)}
    assert Counter(labels[center]) == {i: 10//blocks for i in range(1, blocks+1)}
    indicators = np.column_stack([labels == i for i in range(1, blocks+1)])
    assert np.linalg.matrix_rank(np.column_stack([matrix, indicators[:, 1:]])) == p+blocks-1
    np.testing.assert_allclose((matrix-matrix.mean(0)).T @
                               (indicators-indicators.mean(0)), 0, atol=1e-12)


@pytest.mark.parametrize(('k', 'blocks', 'suffix', 'sequence_difference'), CASES)
def test_reference_vs_minijmp_points_and_block_assignment(k, blocks, suffix, sequence_difference):
    data, col, factor = load_reference(k, suffix)
    factors = tuple(FactorSpec(chr(65+i), chr(65+i), -1, 1) for i in range(k))
    spec = DesignSpec('parity', factors, ('Y',), seed=1, design_type='box_behnken', block_count=blocks)
    generated, _ = create_bbd(spec)
    generated = generated.sort_values('标准序')
    reference = data.sort_values(col['standard_order'])
    a = reference[factor].to_numpy(dtype=int)
    b = generated[[f'编码_{f.factor_id}' for f in factors]].to_numpy(dtype=int)
    assert Counter(map(tuple, a)) == Counter(map(tuple, b))
    assert sum(not np.array_equal(left, right) for left, right in zip(a, b)) == sequence_difference
    block_map = ({i: i for i in range(1, blocks+1)} if blocks in (1, 5)
                 else {i: i+1 if i % 2 else i-1 for i in range(1, blocks+1)})
    source = Counter((tuple(row), block_map[int(block)])
                     for row, block in zip(a, reference[col['block']]))
    actual = Counter((tuple(row), int(block)) for row, block in zip(b, generated['区组']))
    assert source == actual


@pytest.mark.parametrize(('k', 'suffixes'), [(9, ('unblocked', 'block5', 'block10')),
                                             (10, ('unblocked', 'block2'))])
def test_minitab_block_schemes_preserve_point_multiset(k, suffixes):
    datasets = [load_reference(k, suffix) for suffix in suffixes]
    pointsets = [Counter(map(tuple, data[factors].to_numpy())) for data, _, factors in datasets]
    assert all(points == pointsets[0] for points in pointsets[1:])
