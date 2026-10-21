"""G16: reproduce G15 inputs; one warmup and three serial timed calls per case.

Run each hotspot in a fresh process, with PYTHONHASHSEED=0 and BLAS threads=1.
--code-dir can point to the verified G15 source-snapshot/code for the baseline.
"""
import argparse
import gc
import hashlib
import json
from pathlib import Path
import statistics
import sys
import time

ROOT = Path(__file__).resolve().parents[1]


def cases(hotspot):
    if hotspot == 'F01':
        return [('linear_fit', n, 1) for n in (1000, 3000, 10000)]
    if hotspot == 'F11':
        return [('multi_var', n, 3) for n in (100, 1000)]
    if hotspot == 'F02':
        return ([('hoeffding', n, 1) for n in (100, 1000, 3000)]
                + [('matrix_hoeffding', n, p) for n, p in ((100, 5), (100, 10), (1000, 5))])
    if hotspot == 'F04':
        return [(name, n, 1) for name in ('binomial', 'p_blaker', 'p_sterne',
                'p_likelihood_ratio', 'prop_test_1sample') for n in (1000, 10000, 50000)]
    if hotspot == 'F06':
        return ([('fit_norm', n, 1) for n in (1000, 10000, 50000)]
                + [('compare_dist', n, 1) for n in (1000, 5000, 10000)])
    if hotspot == 'F08':
        return ([('two_way', n, 5) for n in (150, 1500, 15000)]
                + [('grr', n, 10) for n in (300, 3000, 30000)])
    raise ValueError(hotspot)


def make_case(name, n, p):
    import numpy as np
    rng = np.random.default_rng(20261021)
    data = rng.normal(10, 1, n).tolist()  # Also consumed by G15 before all cases.
    if name == 'linear_fit':
        from linear_fit import linear_fit
        x = (np.arange(n) % max(5, n // 5)).astype(float).tolist()
        y = (2 * np.array(x) + rng.normal(size=n)).tolist()
        return lambda: linear_fit(x, y, print_out=False)
    if name == 'multi_var':
        from chi_sq import multi_pop_var_test
        groups = [rng.normal(i, .8 + i * .1, n).tolist() for i in range(3)]
        return lambda: multi_pop_var_test(groups, ['A', 'B', 'C'])
    if name == 'hoeffding':
        from nonpara_cor import hoeffding
        other = rng.normal(size=n).tolist()
        return lambda: hoeffding(data, other)
    if name == 'matrix_hoeffding':
        from fit_dialog import print_multi_col_tables
        from nonpara_cor import hoeffding
        values = rng.normal(size=(p, n)).tolist()
        labels = [f'V{i}' for i in range(p)]
        return lambda: print_multi_col_tables(values, labels, hoeffding,
                                             print_port=lambda *a: None, name=name)
    if name == 'binomial':
        from binomial import binomial
        # G15's valid noncentral scenario; central failures are correctness tests.
        return lambda: binomial(n, .5, x=int(n * .49))
    if name in ('p_blaker', 'p_sterne', 'p_likelihood_ratio', 'prop_test_1sample'):
        import proportion_test as mod
        if name == 'prop_test_1sample':
            return lambda: mod.prop_test_1sample(events=int(n * .49), N=n, p0=.5)
        return lambda: getattr(mod, name)(n, .5, n // 2)
    if name == 'fit_norm':
        from dist_fit import fit_norm
        return lambda: fit_norm(data, print_out=False)
    if name == 'compare_dist':
        from dist_fit import compare_dist
        positive = rng.lognormal(1, .25, n).tolist()
        def compare():
            result = compare_dist(positive, print_out=False)
            assert len(result) == 6, 'Six-model benchmark requires six successful fits'
            return result
        return compare
    if name in ('two_way', 'grr'):
        a = (np.arange(n) % p).astype(str).tolist()
        b = ((np.arange(n) // p) % 3).astype(str).tolist()
        if name == 'two_way':
            from two_way_anova import two_way_anova
            return lambda: two_way_anova(data, factor_listA=a, factor_listB=b)
        from GRR import grr_master
        return lambda: grr_master(y=data, part=a, op=b)
    raise ValueError(name)


def measure(fn):
    fn()
    samples = []
    for _ in range(3):
        gc.collect()
        start = time.perf_counter()
        fn()
        samples.append(time.perf_counter() - start)
    assert len(samples) == 3 and min(samples) > 0
    return samples


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('hotspot', choices=['F01', 'F11', 'F02', 'F04', 'F06', 'F08'])
    parser.add_argument('--code-dir', type=Path, default=ROOT / 'code')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    sys.path.insert(0, str(args.code_dir.resolve()))
    rows = []
    for name, n, p in cases(args.hotspot):
        samples = measure(make_case(name, n, p))
        row = dict(name=name, n=n, p=p, samples=samples, median=statistics.median(samples))
        rows.append(row)
        print(f'{name} n={n} p={p}: {row["median"]:.6f}s', flush=True)
        args.output.write_text(json.dumps(dict(
            python=sys.executable, code_dir=str(args.code_dir.resolve()), seed=20261021,
            source_hashes={f.name: hashlib.sha256(f.read_bytes()).hexdigest()
                           for f in args.code_dir.glob('*.py')}, rows=rows), indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
