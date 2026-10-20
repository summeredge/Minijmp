import seaborn as sb
import numpy as np
from matplotlib import pyplot as plt
from chart_style import style_axes, font_families


def add_fig_legend_best_loc(ax, fig):
    fig.legend(loc='outside upper right',
               prop={'family': font_families(['DejaVu Sans'])})
    return


def histo_xy(xlabel=None, x_max=None, x_min=None, grid=False,
             ylabel=None, y_max=None, y_min=None,
             ax_margin=0.1, ax=None, **kwargs):

    if ax is None:
        fig, ax = plt.subplots(layout="constrained")
    sb.histplot(ax=ax, zorder=2, **kwargs)
    if y_max is not None:
        ax.set_ylim(top=y_max)
    if y_min is not None:
        ax.set_ylim(bottom=y_min)
    if x_max is not None:
        ax.set_xlim(right=x_max)
    if x_min is not None:
        ax.set_xlim(left=x_min)
    if ylabel is not None:
        ax.set_ylabel(ylabel)
    if xlabel is not None:
        ax.set_xlabel(xlabel)
    if grid:
        ax.grid(grid, zorder=1)
    style_axes(ax)
    return


def histo_full(xlabel=None, x_max=None, x_min=None, grid=False,
               ax_margin=0.1, ax=None, **kwargs):

    if ax is None:
        fig, ax = plt.subplots(layout="constrained")
    sb.histplot(ax=ax, zorder=2, **kwargs)
    if x_max is not None:
        ax.set_xlim(right=x_max)
    if x_min is not None:
        ax.set_xlim(left=x_min)
    if xlabel is not None:
        ax.set_xlabel(xlabel)
    if grid:
        ax.grid(grid, zorder=1)
    style_axes(ax)
    return


def histo_n_fit(df=None, xkey=None,
                xlabel=None, x_max=None, x_min=None,
                bins='auto', binwidth=None,
                stat='count', rv=None, ax=None, fig=None,
                ax_margin=0.1, legend=False, grid=False,
                fill_color='lightblue', edge_color='k',
                fit_color='k'
                ):
    if df is None or xkey is None:
        return

    if ax is None:
        fig, ax = plt.subplots(layout="constrained")

    fig = ax.figure
    x = list(df[xkey].dropna())
    if x_min is None:
        x_min = min(x) - (max(x) - min(x)) * ax_margin
    if x_max is None:
        x_max = max(x) + (max(x) - min(x)) * ax_margin
    ax.set_xlim(left=x_min, right=x_max)
    if grid:
        ax.grid(grid, zorder=1)

    sb.histplot(data=df, x=xkey, ax=ax, zorder=2,
                color=fill_color, edgecolor=edge_color, linewidth=1,
                stat=stat, bins=bins, binwidth=binwidth,
                legend=False,
                label=xkey if xlabel is None else xlabel)
    if rv is not None:
        ax2 = ax.twinx()
        sb.histplot(data=df, x=xkey, ax=ax2, alpha=0, edgecolor=None,
                    #  color='lightblue', edgecolor='k', linewidth=1,
                    stat='density', bins=bins, binwidth=binwidth,
                    legend=False)
        rvx = np.linspace(x_min, x_max, 100)
        rvy = rv.pdf(rvx)
        ax2.plot(rvx, rvy, color=fit_color, linewidth=2, label=f"拟合分布 ({rv.dist.name})",
                 zorder=3)

    if xlabel is not None:
        ax.set_xlabel(xlabel)
    if rv is not None:
        ax2.set_ylabel("Density")
        style_axes(ax2)

    if legend:
        add_fig_legend_best_loc(ax=ax, fig=fig)

    style_axes(ax)
    return
