"""平衡长格式属性一致性分析；样本为独立单位，重复试次不冒充独立样本。"""
import numpy as np
import pandas as pd
from scipy import stats
from statsmodels.stats.inter_rater import cohens_kappa, fleiss_kappa


def agreement_interval(matched, n, confidence=.95):
    """Minitab 精确二项区间：端点使用单侧 alpha，内部等尾 alpha/2。"""
    alpha = 1-confidence
    low = 0. if matched == 0 else float(stats.beta.ppf(alpha if matched == n else alpha/2, matched, n-matched+1))
    high = 1. if matched == n else float(stats.beta.isf(alpha if matched == 0 else alpha/2, matched+1, n-matched))
    return low, high


def _kappa(matrix, categories, method):
    n, raters = matrix.shape
    if raters < 2:
        return np.nan, np.nan, np.nan, np.nan, '至少需要两个评价序列'
    counts = np.column_stack([(matrix == c).sum(axis=1) for c in range(categories)])
    p = counts.sum(axis=0)/(n*raters)
    if np.count_nonzero(p) < 2:
        return np.nan, np.nan, np.nan, np.nan, '只有一个有效类别，偶然一致率为 1'
    if method == 'Cohen':
        cross = np.zeros((categories, categories), dtype=int)
        np.add.at(cross, (matrix[:, 0], matrix[:, 1]), 1)
        value = float(cohens_kappa(cross, return_results=False))
        row, col = cross.sum(axis=1)/n, cross.sum(axis=0)/n
        pe = float(row @ col)
        variance = (pe+pe**2-np.sum(row*col*(row+col)))/(n*(1-pe)**2)
        se = float(np.sqrt(max(0, variance)))
        expected = np.outer(cross.sum(axis=1), cross.sum(axis=0))/n
        reason = 'N<30 或期望列联频数<5，不报告渐近检验' if n < 30 or (expected < 5).any() else ''
    else:
        value = float(fleiss_kappa(counts))
        pe = np.sum(p*p)
        # 多项独立评分零假设的 delta 方差，含估计边际的协方差项。
        variance = 2*(pe+pe**2-2*np.sum(p**3))/(n*raters*(raters-1)*(1-pe)**2)
        se = float(np.sqrt(max(0, variance)))
        reason = 'N<30 或类别期望频数<5，不报告渐近检验' if n < 30 or (n*raters*p < 5).any() else ''
    if reason or not se > 0:
        return value, np.nan, np.nan, np.nan, reason or '零假设标准误为零'
    z = value/se
    return value, se, z, float(stats.norm.sf(z)), ''


def kendall_concordance(matrix):
    n, k = matrix.shape
    if n < 2 or k < 2:
        return np.nan, np.nan, n-1, np.nan
    ranks = np.apply_along_axis(stats.rankdata, 0, matrix)
    tie_sum = 0
    for col in matrix.T:
        _, counts = np.unique(col, return_counts=True)
        tie_sum += sum(int(t)**3-int(t) for t in counts)
    denominator = k*k*(n**3-n)-k*tie_sum
    if denominator == 0:
        return np.nan, np.nan, n-1, np.nan
    w = float(12*np.sum((ranks.sum(axis=1)-k*(n+1)/2)**2)/denominator)
    chi = k*(n-1)*w
    return w, chi, n-1, float(stats.chi2.sf(chi, n-1)) if n >= 10 else np.nan


def attribute_agreement(data, sample, appraiser, response, trial=None, standard=None,
                        order=None, confidence=.95, cancel_event=None):
    if not np.isfinite(confidence) or not 0 < confidence < 1:
        raise ValueError('置信水平必须在 0 与 100% 之间。')
    roles = [sample, appraiser, response]+([trial] if trial else [])+([standard] if standard else [])
    if len(set(roles)) != len(roles):
        raise ValueError('样本、评价员、评价结果、试次和标准必须选择不同列。')
    frame = data[roles].copy()
    if frame.empty or frame.isna().any().any() or any(frame[c].astype(str).str.strip().eq('').any() for c in roles):
        raise ValueError('属性分析输入不能含空值或缺失类别。')
    if any(isinstance(v, (int, float, np.number)) and not np.isfinite(v) for c in roles for v in frame[c]):
        raise ValueError('属性分析输入不能含非有限数值。')
    samples, appraisers = list(pd.unique(frame[sample])), list(pd.unique(frame[appraiser]))
    if len(samples) < 2:
        raise ValueError('至少需要两个样本。')
    inferred = not trial
    if inferred:
        trial = '_inferred_trial'
        while trial in frame:
            trial += '_'
        frame[trial] = frame.groupby([sample, appraiser], sort=False).cumcount()+1
    trials = list(pd.unique(frame[trial]))
    keys = [sample, appraiser, trial]
    if frame.duplicated(keys).any():
        raise ValueError('样本 × 评价员 × 试次存在重复记录。')
    if len(frame) != len(samples)*len(appraisers)*len(trials):
        raise ValueError('设计不平衡：每个样本必须由所有评价员在相同试次集合中评价。')
    index = pd.MultiIndex.from_product([samples, appraisers, trials], names=keys)
    series = frame.set_index(keys)[response].reindex(index)
    if series.isna().any():
        raise ValueError('设计不平衡或试次不能识别。')
    standards = None
    if standard:
        if frame.groupby(sample, sort=False)[standard].nunique().ne(1).any():
            raise ValueError('同一样本的标准答案自相矛盾。')
        standards = frame.groupby(sample, sort=False)[standard].first().reindex(samples).to_numpy()
    labels = list(pd.unique(frame[response]))
    if standards is not None:
        labels = list(dict.fromkeys(labels+list(standards)))
    if len(labels) < 2:
        # 全局单类别不可识别；局部单类别 Kappa 则显示 NA。
        raise ValueError('至少需要两个有效评价类别；单类别 Kappa 不可识别。')
    if order is not None:
        label_map = {str(v): v for v in labels}
        if len(label_map) != len(labels) or len(order) != len(set(order)) or set(order) != set(label_map):
            raise ValueError('有序类别顺序必须恰好包含所有有效类别且不能重复。')
        labels = [label_map[v] for v in order]
    codes = {v: i for i, v in enumerate(labels)}
    cube = np.array([codes[v] for v in series], dtype=int).reshape(len(samples), len(appraisers), len(trials))
    standard_codes = np.array([codes[v] for v in standards]) if standards is not None else None
    n, a, t = cube.shape
    agreements, kappas, category_kappas, kendalls, accuracy, confusion = [], [], [], [], [], []
    warnings = ['试次按每个样本/评价员的原始行序推断。'] if inferred else []

    def check_cancel():
        if cancel_event is not None and cancel_event.is_set():
            raise ValueError('分析已取消。')

    def agreement(scope, who, matched):
        if matched is None:
            agreements.append([scope, who, n, np.nan, np.nan, np.nan, np.nan, confidence])
        else:
            m = int(np.count_nonzero(matched))
            low, high = agreement_interval(m, n, confidence)
            agreements.append([scope, who, n, m, m/n, low, high, confidence])

    def kappas_for(scope, who, matrix, methods):
        check_cancel()
        for method in methods:
            value = _kappa(matrix, len(labels), method)
            kappas.append([scope, who, method, *value])
            for c, label in enumerate(labels):
                v = _kappa((matrix == c).astype(int), 2, method)
                category_kappas.append([scope, who, method, label, *v])
        if order is not None and len(labels) >= 3 and matrix.shape[1] >= 2:
            kendalls.append([scope, who, 'Kendall W', *kendall_concordance(matrix)])

    for j, who in enumerate(appraisers):
        matrix = cube[:, j, :]
        agreement('评价员内部', who, np.all(matrix == matrix[:, :1], axis=1) if t > 1 else None)
        if t > 1:
            kappas_for('评价员内部', who, matrix, ['Fleiss']+(['Cohen'] if t == 2 else []))
    agreement('评价员之间', '全部', np.all(cube.reshape(n, -1) == cube[:, :1, :1].reshape(n, 1), axis=1) if a > 1 else None)
    if a > 1:
        kappas_for('评价员之间', '全部', cube.reshape(n, -1), ['Fleiss']+(['Cohen'] if a == 2 and t == 1 else []))
    if t == 1:
        warnings.append('单试次无法评估评价员内部重复一致性。')
    if a == 1:
        warnings.append('单评价员无法评估评价员之间一致性。')
    if standard_codes is not None:
        correct = cube == standard_codes[:, None, None]
        for j, who in enumerate(appraisers):
            agreement('评价员与标准', who, np.all(correct[:, j, :], axis=1))
            first_kappa = len(kappas)
            for h, trial_label in enumerate(trials):
                matched = int(correct[:, j, h].sum())
                low, high = agreement_interval(matched, n, confidence)
                accuracy.append([who, trial_label, n, matched, matched/n, low, high, '独立样本精确二项'])
                kappas_for('逐试次与标准', f'{who} / {trial_label}', np.column_stack((cube[:, j, h], standard_codes)), ['Cohen', 'Fleiss'])
                if order is not None and len(labels) >= 3:
                    tau = stats.kendalltau(cube[:, j, h], standard_codes, method='asymptotic', alternative='greater')
                    kendalls.append(['逐试次与标准', f'{who} / {trial_label}', 'Kendall tau-b', float(tau.statistic), np.nan, np.nan, float(tau.pvalue) if n >= 10 else np.nan])
            # 重复试次与同一标准相关，均值 Kappa 不套独立方差公式。
            for method in ['Cohen', 'Fleiss']:
                selected = [row for row in kappas[first_kappa:] if row[0] == '逐试次与标准' and row[2] == method]
                mean = float(np.mean([row[3] for row in selected]))
                kappas.append(['评价员与标准', who, method+' 试次均值', mean, np.nan, np.nan, np.nan, '重复试次相关，均值不作渐近检验'])
            for c, label in enumerate(labels):
                for d, predicted in enumerate(labels):
                    count = int(((standard_codes[:, None] == c) & (cube[:, j, :] == d)).sum())
                    confusion.append([who, label, predicted, count, c != d])
        agreement('全部评价员与标准', '全部', np.all(correct, axis=(1, 2)))
        # 同一样本的评价相关：对 E[样本内正确比例] 使用严格保守的样本簇界。
        for who, unit in [(appraisers[j], correct[:, j, :]) for j in range(a)]+[('全部', correct.reshape(n, -1))]:
            all_correct = int(np.all(unit, axis=1).sum())
            all_wrong = int(np.all(~unit, axis=1).sum())
            tail = (1-confidence)/2
            lower = float(stats.beta.ppf(tail, all_correct, n-all_correct+1)) if all_correct else 0.
            upper = 1-float(stats.beta.ppf(tail, all_wrong, n-all_wrong+1)) if all_wrong else 1.
            accuracy.append([who, '所有试次', unit.size, int(unit.sum()), float(unit.mean()), lower, upper, '样本簇保守界（非独立二项）'])
        for method in ['Cohen', 'Fleiss']:
            selected = [row[3] for row in kappas if row[0] == '逐试次与标准' and row[2] == method]
            kappas.append(['全部评价员与标准', '全部', method+' 序列均值', float(np.mean(selected)), np.nan, np.nan, np.nan, '相关评价序列，均值不作渐近检验'])
    tables = {
        '设计': pd.DataFrame([[n, a, t, len(labels), '有序' if order else '名义', confidence, ' → '.join(map(str, labels))]], columns=['样本数', '评价员数', '试次数', '类别数', '尺度', '置信水平', '类别顺序']),
        '完全一致率': pd.DataFrame(agreements, columns=['范围', '评价员', '样本数', '一致样本数', '一致率', 'CI下限', 'CI上限', '置信水平']),
        'Kappa': pd.DataFrame(kappas, columns=['范围', '评价员', '方法', 'Kappa', 'SE0', 'Z', '右尾 p', '适用性']),
        '各类别Kappa': pd.DataFrame(category_kappas, columns=['范围', '评价员', '方法', '类别', 'Kappa', 'SE0', 'Z', '右尾 p', '适用性'])}
    if standard:
        tables['正确评价比例'] = pd.DataFrame(accuracy, columns=['评价员', '试次', '评价数', '正确数', '正确率', 'CI下限', 'CI上限', 'CI方法'])
        tables['分类不一致'] = pd.DataFrame(confusion, columns=['评价员', '标准类别', '评价类别', '频数', '不一致'])
    if order is not None:
        tables['Kendall'] = pd.DataFrame(kendalls, columns=['范围', '评价员', '指标', '系数', 'Chi2', 'df', '右尾 p'])
        warnings.append('有序类别 Kappa 仍为未加权绝对一致；Kendall 衡量关联，不能代替正确率。Kendall W 的卡方检验要求 N≥10。')
    warnings.append('Kappa 检验为 H0:κ=0，H1:κ>0；SE0 为零假设标准误。Fleiss 检验假定独立评分共享类别概率。小样本/稀疏类别仅报告点估计。')
    return {'kind': 'attribute_agreement', 'tables': tables, 'has_standard': bool(standard), 'warnings': warnings}
