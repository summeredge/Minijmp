"""Shared presentation defaults; leave data, scales and statistical colors alone."""

from matplotlib import font_manager
from matplotlib.text import Text
from matplotlib.category import StrCategoryLocator
from matplotlib.ticker import FixedLocator


# Use installed fonts only. DejaVu supplies minus/Greek/math; CJK falls back per glyph.
CJK_FONTS = [name for name in (
    "Microsoft YaHei", "SimHei", "Noto Sans CJK SC", "WenQuanYi Micro Hei",
    "PingFang SC", "Heiti SC", "SimSun",
) if name in font_manager.get_font_names()]


def font_families(preferred):
    """Keep the selected font first and add installed Chinese glyph coverage."""
    families = [preferred] if isinstance(preferred, str) else list(preferred)
    return list(dict.fromkeys(families + ["DejaVu Sans"] + CJK_FONTS))


def style_axes(ax):
    """Apply the same compact typography and quiet frame to finished axes."""
    ax.set_facecolor("white")
    ax.set_axisbelow(True)
    for spine in ax.spines.values():
        spine.set_color("#8c969f")
        spine.set_linewidth(0.7)
    ax.tick_params(axis="both", labelsize=9, colors="#303841")
    for line in ax.get_xgridlines() + ax.get_ygridlines():
        line.set_color("#b8c0c8")
        line.set_linewidth(0.6)
        line.set_alpha(0.4)
    ax.xaxis.label.set_size(10)
    ax.yaxis.label.set_size(10)
    ax.title.set_size(12)
    labels = ax.get_xticklabels()
    if (isinstance(ax.xaxis.get_major_locator(), (StrCategoryLocator, FixedLocator))
            and labels and all(label.get_rotation() == 0 for label in labels)
            and (len(labels) > 8 or any(len(label.get_text()) > 10 for label in labels))):
        ax.tick_params(axis="x", labelrotation=60)
        for label in labels:
            label.set_ha("right")
    for text in ax.findobj(match=Text):
        text.set_fontfamily(font_families(text.get_fontfamily()))
