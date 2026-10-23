from types import SimpleNamespace

from matplotlib.backend_bases import MouseEvent
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure
import numpy as np
import pandas as pd
import pytest
from PIL import Image

from regression_plots import regression_plot


@pytest.fixture
def model():
    return SimpleNamespace(tables={
        'observations': pd.DataFrame({'actual': [2., 3., 5., 6.], 'fitted': [2.1, 3.2, 4.8, 5.9],
            'residual': [-.1, -.2, .2, .1], 'source_row': [1, 3, 5, 6],
            'leverage': [.1, .2, .3, .4], 'cooks_distance': [.1, .3, .2, .4],
            'mean_ci_lower': [1.9, 3., 4.6, 5.7], 'mean_ci_upper': [2.3, 3.4, 5., 6.1]}),
        'coefficients': pd.DataFrame({'term': ['Intercept', 'X'], 'estimate': [1., 2.],
                                      'ci_lower': [.8, 1.7], 'ci_upper': [1.2, 2.3]}),
        'comparison': pd.DataFrame({'score': [10., 8., 9.]}),
        'roc': pd.DataFrame({'fpr': [0., 0., .5, 1.], 'tpr': [0., .5, 1., 1.]})})


@pytest.mark.parametrize('kind', ['observed', 'residual', 'sequence', 'qq', 'influence',
                                  'coefficients', 'comparison', 'prediction', 'roc'])
def test_plots_render_and_reopen(model, kind, tmp_path):
    fig = Figure(figsize=(8, 5))
    FigureCanvasAgg(fig)
    axis = regression_plot(model, kind, fig)
    fig.canvas.draw()
    filename = tmp_path/(kind+'.png')
    fig.savefig(filename)
    with Image.open(filename) as image:
        assert image.width == 800 and image.height == 500
        image.verify()
    if kind == 'residual':
        np.testing.assert_allclose(axis.collections[0].get_offsets()[:, 1], [-.1, -.2, .2, .1])


def test_click_recovers_original_positional_row(model):
    fig = Figure(figsize=(8, 5))
    FigureCanvasAgg(fig)
    rows = []
    axis = regression_plot(model, 'observed', fig, on_pick=rows.append)
    fig.canvas.draw()
    x, y = axis.transData.transform([3.2, 3.])
    event = MouseEvent('button_press_event', fig.canvas, x, y, button=1)
    fig.canvas.callbacks.process('button_press_event', event)
    assert rows == [3]


def test_unavailable_model_specific_plot_errors(model):
    del model.tables['roc']
    with pytest.raises(ValueError, match='Logistic'):
        regression_plot(model, 'roc', Figure())
