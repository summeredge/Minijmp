import numpy as np
import matplotlib.pyplot as plt
from scipy.stats import norm
from cpk import cpk
import statistics as stat
from chart_style import style_axes


def cpk_plot(data, usl, target, lsl, print_out=False,
             use_range=False, alpha=0.05, show_plot=False,
             filename=None, xlabel=None, print_port=print,
             transparent=None, ax=None, show_legend=True,
             show_within=True, show_spec=True):

    if ax is None:
        fig, ax1 = plt.subplots(layout='constrained')
    else:
        ax1 = ax
    # Add y axis on the right side
    ax2 = ax1.twinx()

    res = cpk(data, target, usl, lsl, print_out=print_out, within=show_within,
              use_range=use_range, alpha=alpha, print_port=print_port)
    # Use density=True when creating the histogram to ensure
    # the y-axis represents probability density, which is
    # necessary for a proper comparison with the normal distribution curve
    d = res["Flat List"]
    #  print(d)
    ax2.hist(d, density=False, alpha=0.2, color='g', edgecolor='k')
    ax1.hist(d, density=True, alpha=0, color='b')

    std = res["Overall Sigma"]
    mean = res["mean"]
    std_within = res["Within Sigma"]
    target = res["Target"]
    usl = res["USL"]
    lsl = res["LSL"]

    # Create x and y values for the normal distribution curve
    #  xmin, xmax = plt.xlim()
    xmin = min(d) - (max(d) - min(d)) * 0.05
    xmax = max(d) + (max(d) - min(d)) * 0.05
    x = np.linspace(xmin, xmax, 100)

    # Plot the normal distribution curve for overall
    y = norm.pdf(x, mean, std)
    ax1.plot(x, y, 'k', linewidth=2, linestyle="dashed", label="Overall")
    #  print(x, y)
    if show_within:
        # Plot the normal distribution curve for within
        y = norm.pdf(x, mean, std_within)
        ax1.plot(x, y, 'b', linewidth=1, label="Within")

    # Add labels and title
    ax2.set_ylabel("Counts")
    ax1.set_ylabel('Density')
    if xlabel is not None:
        ax1.set_xlabel(xlabel)
    # ax1.set_title(f'Histogram with Normal Distribution Fit (μ={mu:.2f}, σ={std:.2f})')

    if show_spec:
        for value, name, color, linestyle in (
                (target, "Target", 'g', ':'),
                (usl, "USL", 'r', '-.'), (lsl, "LSL", 'r', '-.')):
            ax1.axvline(value, color=color, linewidth=2, linestyle=linestyle)
            ax1.annotate(name, xy=(value, 1), xycoords=ax1.get_xaxis_transform(),
                         xytext=(0, 4), textcoords="offset points",
                         ha="center", va="bottom", rotation=90)
    if show_legend:
        ax1.legend(loc='best', frameon=False)

    style_axes(ax1)
    style_axes(ax2)

    if show_plot:
        plt.show()

    if filename is not None:
        fname = str(filename) + '.png'
        ax1.figure.savefig(
            fname,
            transparent=transparent,
            dpi=200,
            format='png', bbox_inches='tight')

    return res


def hist_norm(data, ax=None, show_plot=False,
              filename=None, xlabel=None):

    if ax is not None:
        ax1 = ax
    else:
        fig, ax1 = plt.subplots(layout='constrained')
    # Add y axis on the right side
    ax2 = ax1.twinx()

    # Use density=True when creating the histogram to ensure
    # the y-axis represents probability density, which is
    # necessary for a proper comparison with the normal distribution curve
    d = data
    ax2.hist(d, density=False, alpha=0.2, color='g', edgecolor='k')
    ax1.hist(d, density=True, alpha=0, color='b')

    std = stat.stdev(data)
    mean = stat.mean(data)

    # Create x and y values for the normal distribution curve
    xmin, xmax = min(data), max(data)
    x = np.linspace(xmin, xmax, 100)

    # Plot the normal distribution curve for overall
    y = norm.pdf(x, mean, std)
    ax1.plot(x, y, 'k', linewidth=2, linestyle="dashed", label="Overall")

    # Add labels and title
    ax2.set_ylabel("Counts")
    ax1.set_xlabel(xlabel)
    ax1.set_ylabel('Density')
    # ax1.set_title(f'Histogram with Normal Distribution Fit (μ={mu:.2f}, σ={std:.2f})')

    style_axes(ax1)
    style_axes(ax2)

    if show_plot:
        plt.show()

    if filename is not None:
        fname = str(filename) + '.png'
        ax1.figure.savefig(
            fname,
            dpi=200,
            format='png', bbox_inches='tight')

    return


if __name__ == "__main__":
    group = [1, 1, 1, 1, 2, 2, 2, 2, 3, 3, 3, 3, 4, 4, 4,
             4, 5, 5, 5, 5, 6, 6, 6, 6, 7, 7, 7, 7, 8, 8, 8, 8]
    data = [18.5, 21.2, 19.4, 16.5, 17.9, 19.0, 20.3, 21.2, 19.6, 19.8,
            20.4, 20.5, 22.2, 21.5, 20.8, 20.3, 19.1, 20.6, 20.8, 21.6,
            22.8, 22.2, 23.2, 23.0, 19.0, 20.5, 20.3, 19.2, 20.7, 21.0,
            20.5, 19.1]
    target = 20
    usl = 22
    lsl = 18

    cpk_plot(data, target, usl, lsl, print_out=False, filename="ddd")
    #  cpk(data, target, usl, lsl, alpha=0.1)
