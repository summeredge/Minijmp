"""独立于 Tk 的 PCA 计算接口，不修改传入工作表。

fit_pca(df, columns, n_components=None, scaling='autoscale', variance=.95,
        cv_folds=0, missing='error', cancel=None) -> PCAModel。
scaling: autoscale 为中心化并除以样本标准差；center 仅中心化；none 不平移
也不缩放。全部特征值为预处理矩阵 Z'Z/(n-1) 的谱（none 是未中心化二阶矩，
不是协方差），按降序排列，包含零特征值。手动维数不得超过数值秩。

PCAModel: columns(list[str]), n_components, eigenvalues(p,), loadings(p,k),
mean(p,), scale(p,), explained_variance_ratio(p,), training(PCAProjection),
tables(dict: variance/loadings/limits/preprocessing/cv), notes(list[str])。
scores 属性为 training.scores。project(df, missing='error') 使用固定训练参数。
PCAProjection: scores(n,k), t2(n,), q(n,), scaled/residuals/reconstructed(n,p),
data(DataFrame 原变量数值), source(DataFrame source_row/source_index), flags,
tables(dict: scores/monitoring/residuals/reconstructed), phase, notes。
residuals 是预处理空间残差；reconstructed 已还原原单位。
source_row 是传入数据中从 1 起算的位置；删除缺失行后仍保留原位置。
contributions(row0, kind='t2'/'q', projection=None) -> variable/contribution 表；
compare_groups(A0, B0, projection=None) -> 原单位变量 n/mean/std/difference 表。
两接口的行参数均为结果中从 0 起算的位置；A/B 组内部不重复，两组可重叠。

T² 限：phase1=((n-1)^2/n)*Beta(k/2,(n-k-1)/2) 分位数；
phase2=k*(n+1)*(n-1)/(n*(n-k))*F(k,n-k) 分位数。独立正态样本；
估计 PCA 子空间使其为近似。none 不满足中心化假设，T² 限标记不可用。
Q 限：theta1=sum(遗漏特征值)，theta2=sum(遗漏特征值平方)，
g=theta2/theta1，h=theta1²/theta2，Q限=g*chi²_h 分位数。
这以独立正态主成分的前两矩匹配为近似，两阶段同用训练谱，不宣称精确
训练内分布。无遗漏正特征值时限为零，允许投影检测训练零方差方向。
flags 中 T² 限不可用为 pd.NA，不能解释为正常；Q 标记仍有效。
T² 贡献为有符号 z_j*(P Lambda^-1 P'z)_j；Q 贡献为预处理残差平方。

CV 为确定性连续分折，每折独立估计预处理和载荷；报告留出行重构 MSE，
只展示不选维（该误差随维数下降不能用来主张最优）。方差选维不读取 CV。
cancel 支持 threading.Event 或无参布尔回调，在 SVD 前后及各折检查；单次
底层 SVD 不可中断。selection_mask(points, bounds, geometry) 为纯选区接口，
bounds=(xmin,xmax,ymin,ymax)，geometry 为 rectangle/ellipse，边界包含。

save(path)/load_pca(path) 使用版本化 JSON，无 pickle，保存训练原值、来源、
完整谱及预处理参数。普通 JSON 标量索引原样保存；复杂索引保存类型和显示
文本，加载为显示标签，不重建任意 Python 对象。source_row 不受影响。
"""
from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
from tempfile import NamedTemporaryFile

import numpy as np
import pandas as pd
from scipy import stats


def _cancel(cancel):
    if cancel is not None and (cancel.is_set() if hasattr(cancel, 'is_set') else cancel()):
        raise InterruptedError('PCA 分析已取消。')


def _integer(value, name, minimum=1):
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, (int, np.integer)) or value < minimum:
        raise ValueError(f'{name} 必须为不小于 {minimum} 的整数。')
    return int(value)


def t2_limits(n, k, confidence=.95, phase='phase2'):
    """单观测 Hotelling T² 上限；训练内 phase1，新独立样本 phase2。

    不是均值检验、子组均值或已知总体参数的控制限。自由度不满足时抛出异常。
    """
    n, k = _integer(n, '基线样本量', 2), _integer(k, '维数')
    if isinstance(confidence, (bool, complex, np.complexfloating)) or not isinstance(confidence, (int, float, np.number)) or not np.isfinite(confidence) or not 0 < confidence < 1:
        raise ValueError('置信度必须在 0 和 1 之间。')
    if phase not in ('phase1', 'phase2'):
        raise ValueError('监控阶段必须为 phase1 或 phase2。')
    if n <= k or (phase == 'phase1' and n <= k+1):
        raise ValueError('样本量不足以计算该阶段的 T² 控制限。')
    if phase == 'phase1':
        return float((n-1)**2/n * stats.beta.ppf(confidence, k/2, (n-k-1)/2))
    return float(k*(n+1)*(n-1)/(n*(n-k)) * stats.f.ppf(confidence, k, n-k))


def hotelling_statistics(values, mean, covariance):
    """固定基线均值/样本协方差下逐行 (x-mean)'S^-1(x-mean)，不重新估计。

    供独立个体多变量监控复用；拒绝奇异协方差，不静默使用伪逆。
    """
    x, mu, cov = (np.asarray(v, dtype=float) for v in (values, mean, covariance))
    if x.ndim != 2 or mu.shape != (x.shape[1],) or cov.shape != (x.shape[1], x.shape[1]) or not x.shape[1]:
        raise ValueError('观测、均值及协方差的形状不一致。')
    if not all(np.isfinite(v).all() for v in (x, mu, cov)) or not np.allclose(cov, cov.T, rtol=1e-12, atol=0):
        raise ValueError('输入必须有限，协方差必须对称。')
    try:
        chol = np.linalg.cholesky(cov)
        if np.linalg.matrix_rank(cov) != len(mu):
            raise np.linalg.LinAlgError()
        white = np.linalg.solve(chol, (x-mu).T)
    except np.linalg.LinAlgError as exc:
        raise ValueError('协方差须为非奇异正定矩阵。') from exc
    result = np.sum(white**2, axis=0)
    if not np.isfinite(result).all():
        raise ValueError('T² 计算溢出；请检查输入尺度。')
    return result


def selection_mask(points, bounds, geometry='rectangle'):
    """在两个得分坐标中选区；ellipse 为外接矩形所定义的轴对齐椭圆。"""
    xy, box = np.asarray(points, dtype=float), np.asarray(bounds, dtype=float)
    if xy.ndim != 2 or xy.shape[1] != 2 or box.shape != (4,) or not np.isfinite(xy).all() or not np.isfinite(box).all():
        raise ValueError('选区需要有限的二维坐标及四个边界值。')
    xmin, xmax, ymin, ymax = box
    if xmin >= xmax or ymin >= ymax:
        raise ValueError('选区宽度和高度必须为正。')
    if geometry == 'rectangle':
        return (xy[:, 0] >= xmin) & (xy[:, 0] <= xmax) & (xy[:, 1] >= ymin) & (xy[:, 1] <= ymax)
    if geometry == 'ellipse':
        return ((xy[:, 0]-(xmin+xmax)/2)/((xmax-xmin)/2))**2 + ((xy[:, 1]-(ymin+ymax)/2)/((ymax-ymin)/2))**2 <= 1
    raise ValueError('选区类型必须为 rectangle 或 ellipse。')


def _prepare(df, columns, missing):
    if missing not in ('error', 'drop'):
        raise ValueError('缺失值策略必须为 error 或 drop。')
    if not isinstance(df, pd.DataFrame) or not df.columns.is_unique:
        raise ValueError('输入必须为列名唯一的 DataFrame。')
    if any(c not in df.columns for c in columns):
        raise ValueError('输入缺少模型变量。')
    vectors = []
    for c in columns:
        try:
            col = pd.to_numeric(df[c], errors='raise')
            if np.iscomplexobj(col):
                raise ValueError()
            vectors.append(col.to_numpy(dtype=float, na_value=np.nan))
        except (ValueError, TypeError) as exc:
            raise ValueError(f'变量 {c!r} 必须为实数数值。') from exc
    x = np.column_stack(vectors)
    if np.isinf(x).any():
        raise ValueError('变量含无穷值。')
    keep = ~np.isnan(x).any(axis=1)
    if not keep.all() and missing == 'error':
        raise ValueError('变量含缺失值；可明确选择 missing="drop" 删除不完整行。')
    if not keep.any():
        raise ValueError('没有完整样本。')
    positions = np.flatnonzero(keep)
    source = pd.DataFrame({'source_row': positions+1,
                           'source_index': [df.index[i] for i in positions]})
    return pd.DataFrame(x[keep], columns=columns), source, len(x)-len(positions)


def _decompose(x, scaling):
    if len(x) < 2:
        raise ValueError('PCA 至少需要两个完整样本。')
    if np.any(np.ptp(x, axis=0) == 0):
        raise ValueError('变量含常量列；请移除后重新建模。')
    mean = np.zeros(x.shape[1]) if scaling == 'none' else x.mean(axis=0)
    scale = x.std(axis=0, ddof=1) if scaling == 'autoscale' else np.ones(x.shape[1])
    z = (x-mean)/scale
    if not np.isfinite(z).all():
        raise ValueError('预处理溢出；请检查数据尺度。')
    try:
        _, s, vt = np.linalg.svd(z, full_matrices=False)
    except np.linalg.LinAlgError as exc:
        raise ValueError('PCA 奇异值分解未收敛。') from exc
    rank = int(np.count_nonzero(s > s[0]*max(z.shape)*np.finfo(float).eps))
    eigenvalues = np.zeros(x.shape[1])
    eigenvalues[:len(s)] = s**2/(len(x)-1)
    eigenvalues[rank:] = 0
    if not rank or not np.isfinite(eigenvalues).all() or not np.isfinite(eigenvalues.sum()):
        raise ValueError('数据无有效变化或特征值计算溢出。')
    # 固定每个载荷绝对值最大元素的符号，便于保存及图形重现。
    vt *= np.where(vt[np.arange(len(vt)), np.abs(vt).argmax(axis=1)] < 0, -1., 1.)[:, None]
    return mean, scale, z, eigenvalues, vt.T, rank


@dataclass
class PCAProjection:
    scores: np.ndarray
    t2: np.ndarray
    q: np.ndarray
    scaled: np.ndarray
    residuals: np.ndarray
    reconstructed: np.ndarray
    data: pd.DataFrame
    source: pd.DataFrame
    flags: pd.DataFrame
    tables: dict
    phase: str
    notes: list
    _model: object = field(repr=False)


@dataclass
class PCAModel:
    columns: list
    n_components: int
    scaling: str
    mean: np.ndarray
    scale: np.ndarray
    eigenvalues: np.ndarray
    loadings: np.ndarray
    n_samples: int
    variance: float = .95
    cv: pd.DataFrame = field(default_factory=pd.DataFrame)
    notes: list = field(default_factory=list)
    training: PCAProjection = field(init=False, repr=False)
    tables: dict = field(init=False, repr=False)

    @property
    def scores(self):
        return self.training.scores

    @property
    def explained_variance_ratio(self):
        return self.eigenvalues/self.eigenvalues.sum()

    def _tables(self):
        self.notes = [
            'T² 控制限假设独立正态样本；PCA 子空间由样本估计，控制限为近似。',
            'Q 控制限为遗漏特征值前两矩匹配的缩放卡方近似；训练和投影使用同一训练谱，非精确训练内分布。',
            'T² 贡献有正负且加和为 T²；Q 贡献为预处理空间残差平方，加和为 Q。',
            'CV 仅辅助显示留出重构误差，不自动选维，不证明最优维数。',
            '复杂 source_index 在保存后作为带类型的显示标签；真实源行位置由 source_row 保留。',
        ]
        if self.scaling == 'none':
            self.notes.append('不缩放模式也不中心化；谱为未中心化二阶矩，T² 控制限不可用。')
            self.notes.append('不中心化时 Q 限仅供探索；若残差均值非零，中心卡方近似不具有名义覆盖率。')
        if self.n_samples <= self.n_components+1:
            self.notes.append('训练样本量不足以计算 phase1 T² 控制限，相关异常标记为未知。')
        tail = self.eigenvalues[self.n_components:]
        theta1, theta2 = float(tail.sum()), float(tail @ tail)
        if not np.isfinite(theta1) or not np.isfinite(theta2) or theta1 > 0 and theta2 == 0:
            raise ValueError('Q 控制限矩计算溢出或下溢；请调整变量尺度。')
        if theta1 == 0:
            self.notes.append('遗漏方差为零，Q 控制限退化为零；新样本偏离训练子空间仍可触发异常。')
        rows = []
        for phase in ('phase1', 'phase2'):
            for confidence in (.95, .99):
                t2 = np.nan
                if self.scaling != 'none' and self.n_samples > self.n_components+(phase == 'phase1'):
                    t2 = t2_limits(self.n_samples, self.n_components, confidence, phase)
                g = theta2/theta1 if theta1 else 0.
                q = g*stats.chi2.ppf(confidence, theta1/g) if theta1 else 0.
                if not np.isfinite(q):
                    raise ValueError('Q 控制限计算溢出；请调整变量尺度。')
                rows.append(dict(phase=phase, confidence=confidence, t2=t2, q=q,
                                 theta1=theta1, theta2=theta2,
                                 t2_method='Beta 训练内近似' if phase == 'phase1' else 'F 新样本近似',
                                 q_method='前两矩匹配缩放卡方近似' if theta1 else '零残差方差退化'))
        ratios = self.explained_variance_ratio
        self.tables = {
            'variance': pd.DataFrame({'component': np.arange(1, len(ratios)+1),
                                      'eigenvalue': self.eigenvalues, 'explained_variance_ratio': ratios,
                                      'cumulative_variance_ratio': np.cumsum(ratios),
                                      'selected': np.arange(len(ratios)) < self.n_components}),
            'loadings': pd.DataFrame(self.loadings, columns=self._pc_names()).assign(variable=self.columns),
            'limits': pd.DataFrame(rows),
            'preprocessing': pd.DataFrame({'variable': self.columns, 'mean': self.mean, 'scale': self.scale}),
            'cv': self.cv.copy(),
        }

    def _pc_names(self):
        return [f'PC{i+1}' for i in range(self.n_components)]

    def _projection(self, data, source, phase, dropped=0):
        z = (data.to_numpy()-self.mean)/self.scale
        scores = z @ self.loadings
        fitted = scores @ self.loadings.T
        residuals = z-fitted
        reconstructed = fitted*self.scale+self.mean
        t2 = np.sum(scores**2/self.eigenvalues[:self.n_components], axis=1)
        q = np.sum(residuals**2, axis=1)
        if not all(np.isfinite(v).all() for v in (z, scores, residuals, reconstructed, t2, q)):
            raise ValueError('投影计算溢出；请检查样本尺度。')
        monitoring = source.copy()
        monitoring['t2'], monitoring['q'] = t2, q
        flags = pd.DataFrame(index=range(len(data)))
        limits = self.tables['limits'].query('phase == @phase')
        for confidence, tag in ((.95, '95'), (.99, '99')):
            limit = limits.loc[limits.confidence == confidence].iloc[0]
            monitoring[f't2_limit_{tag}'] = limit.t2
            monitoring[f'q_limit_{tag}'] = limit.q
            flags[f't2_flag_{tag}'] = pd.array(t2 > limit.t2 if np.isfinite(limit.t2) else [pd.NA]*len(t2), dtype='boolean')
            # 零限时只容忍矩阵乘法舍入量级，不能把零空间新偏差视为正常。
            roundoff = 16*np.finfo(float).eps**2*max(self.n_samples, len(self.columns))**2*np.sum(z**2, axis=1)
            flags[f'q_flag_{tag}'] = pd.array(q > (roundoff if limit.q == 0 else limit.q), dtype='boolean')
            flags[f'abnormal_{tag}'] = flags[f't2_flag_{tag}'] | flags[f'q_flag_{tag}']
        monitoring = pd.concat([monitoring, flags], axis=1)
        notes = self.notes.copy()
        if dropped:
            notes.append(f'已按明确选择删除 {dropped} 行不完整样本；未填补数据。')
        def table(values, columns):
            return pd.concat([source.reset_index(drop=True), pd.DataFrame(values, columns=columns)], axis=1)
        return PCAProjection(scores, t2, q, z, residuals, reconstructed, data.copy(), source.copy(), flags,
                             {'scores': table(scores, self._pc_names()), 'monitoring': monitoring,
                              'residuals': table(residuals, self.columns),
                              'reconstructed': table(reconstructed, self.columns)}, phase, notes, self)

    def project(self, df, missing='error'):
        data, source, dropped = _prepare(df, self.columns, missing)
        return self._projection(data, source, 'phase2', dropped)

    def _result(self, projection):
        result = self.training if projection is None else projection
        if not isinstance(result, PCAProjection) or result._model is not self:
            raise ValueError('投影结果不属于此 PCA 模型。')
        return result

    def contributions(self, row0, kind='t2', projection=None):
        result = self._result(projection)
        row0 = _integer(row0, '样本位置', 0)
        if row0 >= len(result.data):
            raise ValueError('样本位置超出范围。')
        if kind == 't2':
            values = result.scaled[row0]* (self.loadings @ (result.scores[row0]/self.eigenvalues[:self.n_components]))
        elif kind == 'q':
            values = result.residuals[row0]**2
        else:
            raise ValueError('贡献类型必须为 t2 或 q。')
        return pd.DataFrame({'variable': self.columns, 'contribution': values})

    def compare_groups(self, rowsA, rowsB, projection=None):
        result = self._result(projection)
        groups = []
        for rows in (rowsA, rowsB):
            indices = list(rows)
            for i in indices:
                if _integer(i, '选区样本位置', 0) >= len(result.data):
                    raise ValueError('选区样本位置超出范围。')
            if len(set(indices)) != len(indices):
                raise ValueError('同一选区不能重复包含样本。')
            groups.append(result.data.iloc[indices])
        a, b = groups
        return pd.DataFrame({'variable': self.columns, 'n_a': len(a), 'mean_a': a.mean().to_numpy(),
                             'std_a': a.std(ddof=1).to_numpy(), 'n_b': len(b),
                             'mean_b': b.mean().to_numpy(), 'std_b': b.std(ddof=1).to_numpy(),
                             'difference': (a.mean()-b.mean()).to_numpy()})

    def save(self, path):
        """保存有限数值及训练结果，JSON 编码成功后才打开目标文件。"""
        def label(value):
            if isinstance(value, np.generic):
                value = value.item()
            if value is None or isinstance(value, (str, bool, int)) or isinstance(value, float) and np.isfinite(value):
                return {'type': 'scalar', 'value': value}
            return {'type': type(value).__name__, 'value': str(value)}
        payload = dict(format='MiniJMP-PCA', version=1, columns=self.columns,
                       n_components=self.n_components, scaling=self.scaling, n_samples=self.n_samples,
                       variance=self.variance, mean=self.mean.tolist(), scale=self.scale.tolist(),
                       eigenvalues=self.eigenvalues.tolist(), loadings=self.loadings.tolist(),
                       data=self.training.data.to_numpy().tolist(),
                       source_row=self.training.source.source_row.tolist(),
                       source_index=[label(x) for x in self.training.source.source_index],
                       cv=self.cv.to_dict(orient='records'))
        encoded = json.dumps(payload, ensure_ascii=False, allow_nan=False)
        path = Path(path)
        temporary = None
        try:
            with NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent,
                                    prefix=f'.{path.name}.', suffix='.tmp', delete=False) as stream:
                temporary = Path(stream.name)
                stream.write(encoded)
            temporary.replace(path)
        finally:
            if temporary is not None and temporary.exists():
                temporary.unlink()


def _cv(x, scaling, folds, cancel):
    columns = ['n_components', 'mse', 'n_values']
    if not folds:
        return pd.DataFrame(columns=columns)
    if folds < 2 or folds > len(x) or len(x)-int(np.ceil(len(x)/folds)) < 2:
        raise ValueError('交叉验证需 2 到样本量个折，且每个训练折至少两个样本。')
    errors = np.zeros(x.shape[1])
    counts = np.zeros(x.shape[1], dtype=int)
    for hold in np.array_split(np.arange(len(x)), folds):
        _cancel(cancel)
        train = np.ones(len(x), dtype=bool)
        train[hold] = False
        try:
            mean, scale, _, _, vectors, rank = _decompose(x[train], scaling)
        except ValueError as exc:
            raise ValueError('交叉验证训练折不可建模（如常量列）；请调整折数或数据。') from exc
        z = (x[hold]-mean)/scale
        residual = z.copy()
        scores = z @ vectors[:, :rank]
        for k in range(1, rank+1):
            residual -= scores[:, k-1, None]*vectors[:, k-1]
            errors[k-1] += np.sum(residual**2)
            counts[k-1] += z.size
            _cancel(cancel)
        _cancel(cancel)
    valid = counts == x.size
    mse = errors[valid]/counts[valid]
    if not np.isfinite(mse).all():
        raise ValueError('交叉验证计算溢出。')
    return pd.DataFrame({'n_components': np.flatnonzero(valid)+1, 'mse': mse, 'n_values': counts[valid]})


def fit_pca(df, columns, n_components=None, scaling='autoscale', variance=.95,
            cv_folds=0, missing='error', cancel=None):
    """SVD PCA；自动累计方差选维，CV 仅为辅助报告。"""
    _cancel(cancel)
    if isinstance(columns, str):
        raise ValueError('变量须为列名列表。')
    columns = list(columns)
    if not columns or any(not isinstance(c, str) for c in columns) or len(set(columns)) != len(columns):
        raise ValueError('请选择非空且不重复的字符串列名。')
    if scaling not in ('autoscale', 'center', 'none'):
        raise ValueError('预处理模式必须为 autoscale、center 或 none。')
    if isinstance(variance, (bool, complex, np.complexfloating)) or not isinstance(variance, (int, float, np.number)) or not np.isfinite(variance) or not 0 < variance <= 1:
        raise ValueError('累计解释方差目标须在 0 和 1 之间（可等于 1）。')
    cv_folds = _integer(cv_folds, '交叉验证折数', 0)
    data, source, dropped = _prepare(df, columns, missing)
    mean, scale, _, eigenvalues, vectors, rank = _decompose(data.to_numpy(), scaling)
    _cancel(cancel)
    if n_components is None:
        cumulative = np.cumsum(eigenvalues)/eigenvalues.sum()
        k = min(rank, int(np.searchsorted(cumulative, variance))+1)
    else:
        k = _integer(n_components, '主成分数')
        if k > rank:
            raise ValueError(f'主成分数不得超过数据数值秩 {rank}。')
    cv = _cv(data.to_numpy(), scaling, cv_folds, cancel)
    model = PCAModel(columns, k, scaling, mean, scale, eigenvalues, vectors[:, :k], len(data), float(variance), cv)
    model._tables()
    model.training = model._projection(data, source, 'phase1', dropped)
    _cancel(cancel)
    return model


def load_pca(path):
    """读取版本 1 JSON，校验形状、有限值及谱/预处理与训练原值的一致性。"""
    try:
        payload = json.loads(Path(path).read_text(encoding='utf-8'))
        if not isinstance(payload, dict) or payload.get('format') != 'MiniJMP-PCA' or type(payload.get('version')) is not int or payload['version'] != 1:
            raise ValueError('模型格式或版本不支持。')
        columns = payload['columns']
        if not isinstance(columns, list) or not columns or any(not isinstance(c, str) for c in columns) or len(set(columns)) != len(columns):
            raise ValueError('模型变量无效。')
        n = _integer(payload['n_samples'], '样本量', 2)
        k = _integer(payload['n_components'], '主成分数')
        p = len(columns)
        scaling, variance = payload['scaling'], payload['variance']
        if scaling not in ('autoscale', 'center', 'none') or type(variance) not in (int, float) or not np.isfinite(variance) or not 0 < variance <= 1 or k > min(n, p):
            raise ValueError('模型参数无效。')
        arrays = {}
        for key, shape in [('mean', (p,)), ('scale', (p,)), ('eigenvalues', (p,)), ('loadings', (p, k)), ('data', (n, p))]:
            value = np.asarray(payload[key], dtype=float)
            if value.shape != shape or not np.isfinite(value).all():
                raise ValueError(f'模型 {key} 的形状或有限值无效。')
            arrays[key] = value
        mean, scale, eigen, vectors, data = (arrays[key] for key in ('mean', 'scale', 'eigenvalues', 'loadings', 'data'))
        if np.any(scale <= 0) or np.any(eigen < 0) or np.any(np.diff(eigen) > 0) or eigen[k-1] <= 0:
            raise ValueError('模型尺度或特征值无效。')
        expected_mean, expected_scale, z, expected_eigen, _, rank = _decompose(data, scaling)
        if k > rank or not np.allclose(mean, expected_mean, rtol=1e-10, atol=0) or not np.allclose(scale, expected_scale, rtol=1e-10, atol=0):
            raise ValueError('模型预处理参数与训练原值不一致。')
        if not np.allclose(eigen, expected_eigen, rtol=1e-9, atol=np.finfo(float).eps*expected_eigen[0]*max(n, p)) or not np.allclose(vectors.T @ vectors, np.eye(k), rtol=1e-10, atol=1e-10):
            raise ValueError('模型特征谱或载荷正交性无效。')
        if not np.allclose(z.T @ (z @ vectors)/(n-1), vectors*eigen[:k], rtol=1e-8, atol=eigen[0]*1e-10):
            raise ValueError('载荷与训练特征谱不一致。')
        rows, indices = payload['source_row'], payload['source_index']
        if not isinstance(rows, list) or len(rows) != n or any(type(i) is not int or i < 1 for i in rows) or any(b <= a for a, b in zip(rows, rows[1:])) or not isinstance(indices, list) or len(indices) != n:
            raise ValueError('模型来源行位置无效。')
        labels = []
        for item in indices:
            if not isinstance(item, dict) or not isinstance(item.get('type'), str) or not item['type'] or 'value' not in item:
                raise ValueError('来源索引标签无效。')
            value = item['value']
            if item['type'] == 'scalar':
                if value is not None and not isinstance(value, (str, bool, int, float)) or isinstance(value, float) and not np.isfinite(value):
                    raise ValueError('来源标量索引无效。')
                labels.append(value)
            else:
                if not isinstance(value, str):
                    raise ValueError('复杂来源索引必须为显示文本。')
                labels.append(f"[{item['type']}] {value}")
        records = payload['cv']
        if not isinstance(records, list):
            raise ValueError('CV 报告无效。')
        for record in records:
            if not isinstance(record, dict) or set(record) != {'n_components', 'mse', 'n_values'}:
                raise ValueError('CV 报告字段无效。')
            dim = _integer(record['n_components'], 'CV 维数')
            count = _integer(record['n_values'], 'CV 数据量')
            mse = record['mse']
            if dim > rank or count != n*p or not isinstance(mse, (int, float)) or not np.isfinite(mse) or mse < 0:
                raise ValueError('CV 报告数值无效。')
        if [r['n_components'] for r in records] != list(range(1, len(records)+1)):
            raise ValueError('CV 维数顺序无效。')
        cv = pd.DataFrame(records, columns=['n_components', 'mse', 'n_values'])
        model = PCAModel(columns, k, scaling, mean, scale, eigen, vectors, n, float(variance), cv)
        model._tables()
        model.training = model._projection(pd.DataFrame(data, columns=columns), pd.DataFrame({'source_row': rows, 'source_index': labels}), 'phase1')
        return model
    except (KeyError, TypeError, ValueError, OverflowError, np.linalg.LinAlgError) as exc:
        raise ValueError(f'PCA 模型读取失败：{exc}') from exc
