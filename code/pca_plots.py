"""PCA 图形与选区；不拟合模型，不修改来源数据。

GUI 应保存整个返回 dict，尤其是 selectors 的强引用；重绘前对 selectors
调用 disconnect_events()，并用 canvas.mpl_disconnect 断开 connections。
points 为 (PathCollection, 有效样本位置数组) 列表，所有回调使用从 0 开始的位置。
labels 是与 projection 行顺序一致的类别，groups 是 A/B 到样本位置序列的映射。
single_variable 显示指定变量的 Q 贡献；compare_contribution 默认比较 Q，
variable='t2' 时比较 T²。组内单个位置即为指定样本对比。

后端 limits 使用 phase/confidence/t2/q 和 t2_method/q_method；
monitoring 使用 t2_flag_95/q_flag_95/t2_flag_99/q_flag_99，可为 nullable boolean。
统计控制限由后端提供；得分椭圆独立使用训练得分样本协方差和 χ²(2) 分位数，
是二元正态假设下的近似覆盖轮廓，不是均值得分置信区间或 T² 控制限。
"""

import numpy as np
import pandas as pd
from matplotlib.patches import Ellipse, Rectangle
from matplotlib.widgets import EllipseSelector, RectangleSelector
from scipy.stats import chi2

from chart_style import style_axes, font_families
from pca_analysis import selection_mask


_KINDS = ('scree', 'cumulative', 'score', 'loading', 'biplot', 't2', 'q',
          'contribution_t2', 'contribution_q', 'single_variable', 'compare_contribution')
_GROUP_COLORS = {'A': '#0072b2', 'B': '#e69f00'}


def _positions(values, size):
    rows = np.asarray(list(values))
    if rows.size == 0:
        return np.array([], dtype=int)
    if rows.ndim != 1 or rows.dtype.kind not in 'iu' or np.any((rows < 0) | (rows >= size)):
        raise ValueError('样本位置必须为有效数据中从 0 开始的整数位置。')
    return np.unique(rows.astype(int))


def _ellipse(axis, scores, components, confidence):
    xy = np.asarray(scores, dtype=float)[:, components]
    if len(xy) < 3:
        axis.text(.01, .01, '训练样本不足 3 个，无法估计得分覆盖椭圆', transform=axis.transAxes)
        return
    covariance = np.cov(xy, rowvar=False, ddof=1)
    values, vectors = np.linalg.eigh(covariance)
    if values[0] <= 0:
        axis.text(.01, .01, '训练得分协方差奇异，无法绘制覆盖椭圆', transform=axis.transAxes)
        return
    radii = np.sqrt(values * chi2.ppf(confidence, 2))
    angle = np.degrees(np.arctan2(vectors[1, 1], vectors[0, 1]))
    axis.add_patch(Ellipse(xy.mean(axis=0), 2*radii[1], 2*radii[0], angle=angle,
                           fill=False, edgecolor='#606060', linestyle='--',
                           label=f'{confidence:.0%} 得分覆盖轮廓'))


def pca_plot(model, kind, figure, projection=None, components=(1, 2), labels=None,
             groups=None, on_pick=None, on_select=None, selection_shape='rectangle',
             active_group='A', confidence=.95, contribution_row=0, variable=None):
    """在空 Figure 上绘制一种 PCA 图；PC 编号从 1 开始。

    返回 axes/selectors/points/groups/connections。每次完成选区会更新返回 groups，
    并调用 on_select(indices0, active_group)；A/B 的高亮和轮廓互不覆盖。
    更换 active_group/selection_shape 时由 GUI 断开旧连接并重绘，传回 groups。
    """
    if kind not in _KINDS:
        raise ValueError('未知 PCA 图形。')
    if confidence not in (.95, .99):
        raise ValueError('置信水平请选择 0.95 或 0.99，与后端监控标记一致。')
    if active_group not in _GROUP_COLORS:
        raise ValueError('活动选区必须为 A 或 B。')
    if selection_shape not in ('rectangle', 'ellipse'):
        raise ValueError('选区形状必须为 rectangle 或 ellipse。')
    projection = model.training if projection is None else projection
    scores = np.asarray(projection.scores, dtype=float)
    n = len(scores)
    if n == 0:
        raise ValueError('没有可绘制的有效样本。')
    pc = None
    if kind in ('score', 'loading', 'biplot'):
        if model.n_components < 2:
            raise ValueError('二维 PCA 图至少需要保留 2 个主成分。')
        if (len(components) != 2 or any(isinstance(c, (bool, np.bool_)) or
                not isinstance(c, (int, np.integer)) or c < 1 or c > model.n_components
                for c in components)):
            raise ValueError('主成分编号必须为保留范围内的两个整数（从 1 开始）。')
        if components[0] == components[1]:
            raise ValueError('二维图的两个主成分必须不同。')
        pc = np.asarray(components, dtype=int)-1
    if labels is not None and (np.ndim(labels) != 1 or len(labels) != n):
        raise ValueError('类别标签数必须与有效样本数一致。')
    selected = {key: _positions((groups or {}).get(key, []), n) for key in _GROUP_COLORS}
    row = None
    if kind in ('contribution_t2', 'contribution_q'):
        row = _positions([contribution_row], n)[0]
    if kind == 'single_variable' and variable not in model.columns:
        raise ValueError('请选择模型中的有效变量。')
    if kind == 'compare_contribution':
        if variable not in (None, 't2', 'q'):
            raise ValueError('贡献对比类型必须为 t2 或 q。')
        if any(len(rows) == 0 for rows in selected.values()):
            raise ValueError('贡献对比需要 A、B 两组各至少一个样本。')

    axis = figure.add_subplot(111)
    result = {'axes': [axis], 'selectors': [], 'points': [], 'groups': selected,
              'connections': []}

    def scatter(xy, rows, **kwargs):
        artist = axis.scatter(xy[:, 0], xy[:, 1], s=28, alpha=.85, **kwargs)
        result['points'].append((artist, np.asarray(rows, dtype=int)))
        return artist

    def contributions(position, statistic):
        table = model.contributions(int(position), kind=statistic, projection=projection)
        return table.set_index('variable').loc[list(model.columns), 'contribution'].to_numpy(dtype=float)

    if kind in ('scree', 'cumulative'):
        eigenvalues = np.asarray(model.eigenvalues, dtype=float)
        if not np.all(np.isfinite(eigenvalues)) or np.any(eigenvalues < 0) or eigenvalues.sum() <= 0:
            raise ValueError('特征值必须非负、有限且总和大于 0。')
        values = eigenvalues if kind == 'scree' else np.cumsum(eigenvalues)/eigenvalues.sum()*100
        axis.plot(np.arange(1, len(values)+1), values, 'o-')
        axis.axvline(model.n_components, linestyle='--', color='gray', label='保留主成分数')
        axis.set(xlabel='主成分', ylabel='特征值' if kind == 'scree' else '累计解释方差 (%)',
                 title='碎石图' if kind == 'scree' else '累计解释方差')
        axis.legend()
    elif kind in ('score', 'loading', 'biplot'):
        if kind != 'loading':
            xy = scores[:, pc]
            if labels is None:
                scatter(xy, np.arange(n), color='#0072b2', label='样本')
            else:
                # factorize keeps mixed labels and missing categories in positional order.
                codes, categories = pd.factorize(np.asarray(labels, dtype=object), sort=False,
                                                  use_na_sentinel=False)
                for code, category in enumerate(categories):
                    rows = np.flatnonzero(codes == code)
                    scatter(xy[rows], rows, label='缺失类别' if pd.isna(category) else str(category))
            _ellipse(axis, model.training.scores, pc, confidence)
        if kind != 'score':
            loading = np.asarray(model.loadings)[:, pc]
            if kind == 'biplot':
                # shortcut: arrows use a visual scale, use raw Loading Plot for numeric loadings.
                score_span = np.max(np.abs(scores[:, pc]))
                loading_span = np.max(np.abs(loading))
                scale = .8*score_span/loading_span if loading_span else 1.
                loading = loading*scale
                axis.text(.01, .01, f'载荷箭头视觉缩放 ×{scale:.3g}；非原始载荷坐标',
                          transform=axis.transAxes, fontsize=8)
            for name, (x, y) in zip(model.columns, loading):
                axis.annotate('', xy=(x, y), xytext=(0, 0),
                              arrowprops={'arrowstyle': '->', 'color': '#a63603'})
                axis.text(x, y, str(name), fontsize=9)
            axis.update_datalim(loading)
            axis.autoscale_view()
        axis.axhline(0, color='gray', linewidth=.6)
        axis.axvline(0, color='gray', linewidth=.6)
        axis.set(xlabel=f'PC{components[0]}', ylabel=f'PC{components[1]}',
                 title={'score': 'PCA 得分图', 'loading': 'PCA 载荷图', 'biplot': 'PCA 双标图'}[kind])
    elif kind in ('t2', 'q'):
        values = np.asarray(getattr(projection, kind), dtype=float)
        xy = np.column_stack([projection.source['source_row'], values])
        axis.plot(xy[:, 0], xy[:, 1], color='#0072b2', linewidth=.8)
        scatter(xy, np.arange(n), color='#0072b2', label='样本')
        limits = model.tables['limits']
        for level in (.95, .99):
            matching = limits.loc[(limits['phase'] == projection.phase) &
                                  (limits['confidence'] == level)]
            if len(matching) != 1:
                raise ValueError(f'缺少唯一的 {level:.0%} {kind} 控制限。')
            limit = float(matching.iloc[0][kind])
            method = matching.iloc[0][kind+'_method']
            if np.isfinite(limit):
                axis.axhline(limit, color='#d55e00' if level == .99 else '#e69f00',
                             linestyle='--', label=f'{level:.0%} {method}')
        axis.set(xlabel='来源工作表行号（从 1 开始）', ylabel='T²' if kind == 't2' else 'Q / SPE',
                 title=('建模数据' if projection.phase == 'phase1' else '新样本投影')+' '+kind.upper()+' 监控')
    elif kind.startswith('contribution_'):
        statistic = kind.split('_')[1]
        axis.bar(np.arange(len(model.columns)), contributions(row, statistic))
        axis.set_xticks(np.arange(len(model.columns)), model.columns)
        axis.set(ylabel='T² 贡献' if statistic == 't2' else 'Q 贡献',
                 title=f'来源行 {projection.source.iloc[row]["source_row"]} 的 '
                       + ('T²' if statistic == 't2' else 'Q')+' 贡献')
    elif kind == 'single_variable':
        column = list(model.columns).index(variable)
        values = np.asarray(projection.residuals)[:, column]**2
        xy = np.column_stack([projection.source['source_row'], values])
        axis.plot(xy[:, 0], xy[:, 1], linewidth=.8)
        scatter(xy, np.arange(n), color='#0072b2')
        axis.set(xlabel='来源工作表行号（从 1 开始）', ylabel='Q 贡献', title=f'{variable} 单变量残差贡献')
    elif kind == 'compare_contribution':
        statistic = variable or 'q'
        x = np.arange(len(model.columns))
        for i, (group, rows) in enumerate(selected.items()):
            if statistic == 'q':
                mean = np.mean(np.asarray(projection.residuals)[rows]**2, axis=0)
            else:
                weighted_scores = scores[rows]/np.asarray(model.eigenvalues)[:model.n_components]
                mean = np.mean(np.asarray(projection.scaled)[rows] *
                               (weighted_scores @ np.asarray(model.loadings).T), axis=0)
            axis.bar(x+(i-.5)*.36, mean, width=.36, color=_GROUP_COLORS[group],
                     label=f'{group}（n={len(rows)}）')
        axis.set_xticks(x, model.columns)
        axis.set(ylabel='T² 平均贡献' if statistic == 't2' else 'Q 平均贡献', title='A/B 样本贡献对比')
        axis.legend()

    if kind in ('score', 'biplot', 't2', 'q'):
        monitoring = projection.tables['monitoring']
        flags = np.zeros(n, dtype=bool)
        unknown = np.zeros(n, dtype=bool)
        unavailable = []
        statistics = ('t2', 'q') if kind in ('score', 'biplot') else (kind,)
        for statistic in statistics:
            flag = pd.array(monitoring[f'{statistic}_flag_{confidence*100:.0f}'], dtype='boolean')
            flags |= flag.fillna(False).to_numpy(dtype=bool)
            missing = pd.isna(flag)
            unknown |= missing
            if np.any(missing):
                unavailable.append('T²' if statistic == 't2' else 'Q')
        if np.any(unknown):
            axis.scatter(xy[unknown, 0], xy[unknown, 1], s=75, marker='s', facecolors='none',
                         edgecolors='gray', label='判异不可用')
            axis.text(.01, .98, '/'.join(unavailable)+' 判异不可用，不能视为统计正常',
                      transform=axis.transAxes, va='top', fontsize=9, color='#606060')
        if np.any(flags):
            axis.scatter(xy[flags, 0], xy[flags, 1], s=65, marker='x', color='#d62728',
                         label=f'{confidence:.0%} 监控异常')

    if kind in ('score', 'biplot'):
        highlights = {}
        contours = {}
        for group, rows in selected.items():
            highlights[group] = axis.scatter(xy[rows, 0], xy[rows, 1], s=100, facecolors='none',
                                             edgecolors=_GROUP_COLORS[group], linewidths=1.6,
                                             marker='o' if group == 'A' else 's', label=f'选区 {group}')
            if len(rows) > 1:
                low, high = xy[rows].min(axis=0), xy[rows].max(axis=0)
                # GUI 重绘仅传回成员；虚线表示成员包围框，不重建原选区几何。
                contours[group] = Rectangle(low, *(high-low), fill=False, linestyle=':',
                                             edgecolor=_GROUP_COLORS[group])
                axis.add_patch(contours[group])

        if on_select is not None:
            def select(start, end):
                if any(v is None for v in (start.xdata, start.ydata, end.xdata, end.ydata)):
                    return
                low = np.minimum([start.xdata, start.ydata], [end.xdata, end.ydata])
                high = np.maximum([start.xdata, start.ydata], [end.xdata, end.ydata])
                inside = (selection_mask(xy, (low[0], high[0], low[1], high[1]), selection_shape)
                          if np.all(high > low) else np.zeros(n, dtype=bool))
                if selection_shape == 'rectangle':
                    outline = Rectangle(low, *(high-low), fill=False, edgecolor=_GROUP_COLORS[active_group])
                else:
                    outline = Ellipse((low+high)/2, *(high-low), fill=False,
                                      edgecolor=_GROUP_COLORS[active_group])
                rows = np.flatnonzero(inside)
                selected[active_group] = rows
                highlights[active_group].set_offsets(xy[rows])
                if active_group in contours:
                    contours[active_group].remove()
                contours[active_group] = outline
                axis.add_patch(outline)
                on_select(rows.copy(), active_group)
                figure.canvas.draw_idle()

            selector_class = RectangleSelector if selection_shape == 'rectangle' else EllipseSelector
            selector = selector_class(axis, select, useblit=False, button=[1],
                                      minspanx=3, minspany=3, spancoords='pixels',
                                      props={'edgecolor': _GROUP_COLORS[active_group],
                                             'facecolor': 'none', 'linewidth': 1.4})
            result['selectors'].append(selector)

    if on_pick is not None and result['points']:
        annotation = axis.annotate('', (0, 0), xytext=(8, 8), textcoords='offset points',
                                   bbox={'boxstyle': 'round', 'fc': 'white', 'alpha': .9},
                                   fontfamily=font_families('DejaVu Sans'))
        annotation.set_visible(False)

        def click(event):
            if event.inaxes is not axis or event.button != 1 or axis.get_navigate_mode() is not None:
                return
            nearest = None
            for artist, rows in result['points']:
                if not len(rows):
                    continue
                offsets = np.asarray(artist.get_offsets())
                distances = np.linalg.norm(axis.transData.transform(offsets)-[event.x, event.y], axis=1)
                index = int(np.argmin(distances))
                if distances[index] <= 10 and (nearest is None or distances[index] < nearest[0]):
                    nearest = (distances[index], int(rows[index]), offsets[index])
            if nearest is not None:
                _, position, point = nearest
                annotation.xy = point
                annotation.set_text(f'来源行：{projection.source.iloc[position]["source_row"]}')
                annotation.set_visible(True)
                on_pick(position)
                figure.canvas.draw_idle()

        result['connections'].append(figure.canvas.mpl_connect('button_press_event', click))

    if kind in ('score', 'biplot', 't2', 'q'):
        axis.legend(fontsize=8)
    axis.grid(alpha=.3)
    style_axes(axis)
    figure.set_layout_engine('constrained')
    return result
