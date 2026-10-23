"""回归结果图；只消费已拟合结果，不重新估计模型。"""
import numpy as np
from scipy import stats

from chart_style import style_axes, font_families


def regression_plot(result, kind, figure, *, prediction=None, on_pick=None):
    tables = result.tables
    observations = tables['observations']
    model = getattr(result, 'model', 'OLS')
    residual_column = ('standardized_residual' if model == 'Logistic' else
                       'whitened_residual' if model == 'WLS' else 'residual')
    residual_label = ('标准化 Pearson 残差' if model == 'Logistic' else
                      '白化残差' if model == 'WLS' else '残差')
    axis = figure.add_subplot(111)
    row_artists = []

    def scatter(x, y, rows, **kwargs):
        artist = axis.scatter(x, y, s=25, alpha=.8, **kwargs)
        row_artists.append((artist, np.asarray(rows)))
        return artist

    if kind == 'observed':
        scatter(observations['fitted'], observations['actual'], observations['source_row'])
        low = min(observations['fitted'].min(), observations['actual'].min())
        high = max(observations['fitted'].max(), observations['actual'].max())
        axis.plot([low, high], [low, high], '--', color='gray')
        axis.set(xlabel='预测值 / 概率', ylabel='实测值', title='实测值与预测值')
    elif kind in ('residual', 'sequence'):
        x = observations['fitted'] if kind == 'residual' else observations['source_row']
        scatter(x, observations[residual_column], observations['source_row'])
        axis.axhline(0, color='gray', linestyle='--')
        axis.set(xlabel='拟合值' if kind == 'residual' else '来源工作表行号（从 1 开始）',
                 ylabel=residual_label, title='残差与拟合值' if kind == 'residual' else '残差序列')
    elif kind == 'qq':
        if model == 'Logistic':
            raise ValueError('二元 Logistic 不假设正态残差；请查看 Pearson 残差与 ROC。')
        residual = observations[residual_column].to_numpy()
        order = np.argsort(residual)
        (quantiles, ordered), (slope, intercept, _) = stats.probplot(residual)
        scatter(quantiles, ordered, observations['source_row'].to_numpy()[order])
        axis.plot(quantiles, intercept+slope*quantiles, '--', color='gray')
        axis.set(xlabel='正态理论分位数', ylabel=residual_label+'分位数', title='残差正态 QQ 图')
    elif kind == 'influence':
        if 'leverage' not in observations or 'cooks_distance' not in observations:
            raise ValueError('此模型不提供杠杆值 / Cook 距离。')
        scatter(observations['leverage'], observations['cooks_distance'], observations['source_row'])
        axis.axhline(4/len(observations), color='red', linestyle='--', label='Cook 距离 4/N 筛查线')
        axis.set(xlabel='杠杆值', ylabel="Cook's Distance", title='影响点诊断（筛查标记不是删除依据）')
        axis.legend()
    elif kind == 'coefficients':
        coef = tables['coefficients']
        y = np.arange(len(coef))
        axis.errorbar(coef['estimate'], y,
                      xerr=np.array([coef['estimate']-coef['ci_lower'], coef['ci_upper']-coef['estimate']]),
                      fmt='o', capsize=3)
        axis.set_yticks(y, coef['term'])
        axis.axvline(0, color='gray', linestyle='--')
        axis.set(xlabel='系数及置信区间', title='回归系数')
    elif kind == 'comparison':
        comparison = tables.get('comparison')
        if comparison is None or comparison.empty:
            raise ValueError('请选择变量筛选方法后查看模型比较。')
        axis.plot(np.arange(1, len(comparison)+1), comparison['score'], 'o-')
        axis.set(xlabel='候选模型序号', ylabel='所选评价指标', title='模型比较（同一训练样本）')
    elif kind == 'prediction':
        if prediction is None:
            prediction = observations.rename(columns={'fitted': 'predicted'})
        x = prediction['source_row']
        axis.plot(x, prediction['predicted'], 'o-', label='预测值 / 概率')
        if {'mean_ci_lower', 'mean_ci_upper'} <= set(prediction):
            axis.fill_between(x, prediction['mean_ci_lower'], prediction['mean_ci_upper'], alpha=.25, label='均值置信区间')
        if {'pi_lower', 'pi_upper'} <= set(prediction):
            axis.fill_between(x, prediction['pi_lower'], prediction['pi_upper'], alpha=.15, label='观测预测区间')
        axis.set(xlabel='数据工作表行号（从 1 开始）', ylabel='响应 / 概率', title='模型预测')
        axis.legend()
    elif kind == 'roc':
        roc = tables.get('roc')
        if roc is None or roc.empty:
            raise ValueError('ROC 曲线仅适用于二元 Logistic 回归。')
        axis.plot(roc['fpr'], roc['tpr'], label='训练集 ROC')
        axis.plot([0, 1], [0, 1], '--', color='gray')
        axis.set(xlabel='假阳性率', ylabel='真阳性率', title='ROC 曲线（训练集评估）', xlim=(0, 1), ylim=(0, 1))
        axis.legend()
    else:
        raise ValueError('未知回归图形。')
    axis.grid(alpha=.3)
    style_axes(axis)
    figure.set_layout_engine('constrained')
    if on_pick is not None and row_artists:
        annotation = axis.annotate('', (0, 0), xytext=(10, 10), textcoords='offset points',
                                   bbox={'boxstyle': 'round', 'fc': 'white', 'alpha': .9},
                                   fontfamily=font_families('DejaVu Sans'))
        annotation.set_visible(False)

        def click(event):
            if event.inaxes is not axis or event.button != 1:
                return
            for artist, rows in row_artists:
                offsets = artist.get_offsets()
                points = axis.transData.transform(offsets)
                distances = np.linalg.norm(points-[event.x, event.y], axis=1)
                i = int(np.argmin(distances))
                if distances[i] <= 10:
                    annotation.xy = offsets[i]
                    annotation.set_text(f'来源行：{rows[i]}')
                    annotation.set_visible(True)
                    on_pick(int(rows[i]))
                    figure.canvas.draw_idle()
                    return

        figure.canvas.mpl_connect('button_press_event', click)
    return axis
