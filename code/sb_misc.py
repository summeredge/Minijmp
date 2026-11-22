import seaborn as sb
#  import numpy as np
from matplotlib import pyplot as plt
from chart_style import style_axes
########## Own Modules ###########
from utilities import add_Y_refs, hash_combined


def interval_plot(xlabel=None, y_max=None, y_min=None,
                  CIs=None,  # customize intervals
                  ax_margin=0.1, ax=None, ylabel=None,
                  grid=False, title=None,
                  show_y_ref_label=False,
                  y_ref=None, errorbar=('ci', 95), **kwargs):

    def custom_error(x):
        return CIs[hash_combined(x)]

    if ax is None:
        fig, ax = plt.subplots(layout="constrained")

    sb.pointplot(ax=ax, zorder=3, capsize=.1,
                 errorbar=custom_error if CIs is not None else errorbar,
                 **kwargs)
    if y_max is not None:
        ax.set_ylim(top=y_max)
    if y_min is not None:
        ax.set_ylim(bottom=y_min)
    if xlabel is not None:
        ax.set_xlabel(xlabel)
    if ylabel is not None:
        ax.set_ylabel(ylabel)
    if title is not None:
        ax.set_title(title)
    if grid:
        ax.grid(grid, zorder=1)
    add_Y_refs(ax, y_values=y_ref, label=show_y_ref_label)
    style_axes(ax)
    return


def count_plot(xlabel=None, y_max=None, y_min=None, grid=False,
               palette=None,
               ax_margin=0.1, ax=None, ylabel=None,
               show_y_ref_label=False,
               y_ref=None, **kwargs):

    if ax is None:
        fig, ax = plt.subplots(layout="constrained")

    sb.countplot(ax=ax, zorder=3,
                 palette=palette, **kwargs)
    if y_max is not None:
        ax.set_ylim(top=y_max)
    if y_min is not None:
        ax.set_ylim(bottom=y_min)
    if xlabel is not None:
        ax.set_xlabel(xlabel)
    if ylabel is not None:
        ax.set_ylabel(ylabel)
    if grid:
        ax.grid(grid, zorder=1)
    add_Y_refs(ax, y_values=y_ref, label=show_y_ref_label)
    style_axes(ax)
    return


def dot_plot(xlabel=None, y_max=None, y_min=None, grid=False,
             palette=None,
             ax_margin=0.1, ax=None, ylabel=None,
             show_y_ref_label=False,
             y_ref=None, **kwargs):

    if ax is None:
        fig, ax = plt.subplots(layout="constrained")

    sb.scatterplot(ax=ax, zorder=3,
                   palette=palette, **kwargs)
    if y_max is not None:
        ax.set_ylim(top=y_max)
    if y_min is not None:
        ax.set_ylim(bottom=y_min)
    if xlabel is not None:
        ax.set_xlabel(xlabel)
    if ylabel is not None:
        ax.set_ylabel(ylabel)
    if grid:
        ax.grid(grid, zorder=1)
    add_Y_refs(ax, y_values=y_ref, label=show_y_ref_label)
    style_axes(ax)
    return


def plotly_scatter(data, x, y, *, labels=None, area=None, palette=None,
                   xlabel=None, ylabel=None, title=None, grid=False, legend=True,
                   y_min=None, y_max=None, refs=(), label_refs=False):
    """Render prepared observations as markers, optionally sized by area."""
    import pandas as pd
    from matplotlib.colors import to_hex
    from plotly import graph_objects as go

    groups = list(pd.unique(labels)) if labels is not None else [None]
    colors = sb.color_palette(palette, len(groups))
    maximum = data[area].max() if area is not None else None
    fig = go.Figure()
    for group, color in zip(groups, colors):
        subset = data if labels is None else data.loc[labels.eq(group)]
        marker = dict(color=to_hex(color))
        hover = '%{x}<br>%{y}'
        custom = None
        if area is not None:
            subset = subset.loc[subset[area].gt(0)]
            custom = subset[area].tolist()
            marker.update(size=(subset[area] / maximum).tolist(), sizemode='area',
                          sizeref=2 / 24**2, opacity=.6)
            hover += '<br>面积：%{customdata}'
        fig.add_scatter(x=subset[x].tolist(), y=subset[y].tolist(), mode='markers',
                        marker=marker, name=str(group if labels is not None else area or y),
                        customdata=custom, hovertemplate=hover + '<extra>%{fullData.name}</extra>')
    fig.update_layout(template='plotly_white', title=title, showlegend=legend,
                      xaxis=dict(title=xlabel or x, showgrid=grid),
                      yaxis=dict(title=ylabel or y, showgrid=grid))
    if y_min is not None or y_max is not None:
        fig.update_yaxes(range=[y_min, y_max])
    for ref in refs:
        options = dict(annotation_text=str(ref), annotation_position='right') if label_refs else {}
        fig.add_hline(y=ref, line_color='gray', line_dash='dash', **options)
    return fig


def line_plot(xlabel=None, y_max=None, y_min=None, grid=False,
              palette=None,
              ax_margin=0.1, ax=None, ylabel=None,
              show_y_ref_label=False,
              y_ref=None, **kwargs):

    if ax is None:
        fig, ax = plt.subplots(layout="constrained")

    sb.lineplot(ax=ax, zorder=3,
                palette=palette, **kwargs)
    if y_max is not None:
        ax.set_ylim(top=y_max)
    if y_min is not None:
        ax.set_ylim(bottom=y_min)
    if xlabel is not None:
        ax.set_xlabel(xlabel)
    if ylabel is not None:
        ax.set_ylabel(ylabel)
    if grid:
        ax.grid(grid, zorder=1)
    add_Y_refs(ax, y_values=y_ref, label=show_y_ref_label)
    style_axes(ax)
    return
