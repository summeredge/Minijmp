"""Capability diagnostics on the analysis scale; no fitting or data mutation.

Sixpack order follows Minitab: I/Xbar, histogram; MR/R/S, probability;
recent subgroups, capability comparison. SPC limits always use 3 sigma,
independently of the capability spread K. Only beyond-limit tests are marked.
"""

import numpy as np
import pandas as pd
from matplotlib.figure import Figure
from matplotlib.patches import Patch
from scipy import special, stats

from chart_style import font_families, style_axes
from control_chart import x_mR, xBar_R


def _specs(ax, result, vertical=True):
    for key, label, color in (("lsl", "LSL", "#c62728"),
                              ("usl", "USL", "#c62728"),
                              ("target", "Target", "#258248")):
        value = result.get(key)
        if value is not None:
            draw = ax.axvline if vertical else ax.axhline
            draw(value, color=color, linestyle="-.", label=label)


def _histogram(ax, data, model, result=None):
    ax.hist(data, bins="auto", density=True, color="#c9dbe8", edgecolor="white")
    low, high = np.quantile(data, [0, 1])
    pad = (high - low) * .1
    xs = np.linspace(low - pad, high + pad, 400)
    ax.plot(xs, model.pdf(xs), color="black", linestyle="--", label="整体拟合")
    if result is not None:
        if _normal(result) and (result.get("transform") or {}).get("method") != "johnson":
            ax.plot(xs, stats.norm.pdf(xs, result["mean"], result["within_sigma"]),
                    color="#286ca2", label="组内正态")
        _specs(ax, result)
    ax.set_ylabel("密度")
    ax.legend(fontsize=8)


def _normal(result):
    return result["model"].dist.name == "norm"


def _probability(ax, data, model, fit=None):
    # Median ranks are plotting positions, not confidence bounds or a GOF test.
    ranks = (np.arange(1, len(data) + 1) - .3) / (len(data) + .4)
    theoretical = model.ppf(ranks)
    ax.plot(theoretical, np.sort(data), ".", label="观测值")
    ax.plot(theoretical, theoretical, "k--", label="拟合分位数")
    ax.set_xlabel("模型理论分位数（Q-Q；无置信带）")
    ax.set_ylabel("样本分位数")
    if fit:
        summary = "; ".join(f"{label}={fit[key]:.4g}" for key, label in
                            (("AD", "AD"), ("KS", "KS"), ("p_value", "p（参数自举）"))
                            if isinstance(fit.get(key), (int, float)) and np.isfinite(fit[key]))
        if summary:
            ax.text(.02, .98, summary, transform=ax.transAxes, va="top", fontsize=8,
                    wrap=True)


def _control(ax, values, center, lower, upper, title):
    values = np.asarray(values)
    xs = np.arange(1, len(values) + 1)
    ax.plot(xs, values, ".-", color="#444444", label="观测值")
    for limit, label in ((lower, "LCL"), (center, "CL"), (upper, "UCL")):
        ax.plot(xs, np.broadcast_to(limit, values.shape), color="#286ca2",
                linestyle="--" if label != "CL" else ":", label=label)
    outside = (values < lower) | (values > upper)
    ax.plot(xs[outside], values[outside], "ro", label="超控制限")
    ax.set_title(title)
    ax.set_xlabel("子组 / 观测顺序")
    ax.legend(fontsize=7, ncol=3)


def _charts(result, groups):
    mean, sigma = result["mean"], result["within_sigma"]
    sizes = np.array([len(group) for group in groups])
    if np.all(sizes == 1):
        chart = x_mR(result["data"], 2, sigma=sigma, mean=mean)
        if not _normal(result):
            chart["lcl1"], chart["ucl1"] = result["model"].ppf([.00135, .99865])
        return chart, "I 单值图", "MR 移动极差图"
    if np.any(sizes < 2):
        raise ValueError("子组图要求每个子组至少含两个观测值")
    if np.max(sizes) <= 8:
        return xBar_R(groups, mean=mean, sigma=sigma), "Xbar 均值图", "R 极差图"
    # E(S)=c4(n)*sigma; SD(S)=sigma*sqrt(1-c4(n)^2).
    c4 = np.sqrt(2 / (sizes - 1)) * np.exp(
        special.gammaln(sizes / 2) - special.gammaln((sizes - 1) / 2))
    center = c4 * sigma
    spread = 3 * sigma * np.sqrt(1 - c4 ** 2)
    chart = {"Y1": [np.mean(g) for g in groups],
             "Y2": [np.std(g, ddof=1) for g in groups],
             "bar1": mean, "lcl1": mean - 3 * sigma / np.sqrt(sizes),
             "ucl1": mean + 3 * sigma / np.sqrt(sizes),
             "bar2": center, "lcl2": np.maximum(0, center - spread),
             "ucl2": center + spread}
    return chart, "Xbar 均值图", "S 标准差图"


def _comparison(ax, result):
    model = result["model"]
    k = result.get("k", 6)
    if _normal(result):
        intervals = [("整体", result["mean"] - k / 2 * result["overall_sigma"],
                      result["mean"] + k / 2 * result["overall_sigma"])]
        if (result.get("transform") or {}).get("method") != "johnson":
            intervals.insert(0, ("组内", result["mean"] - k / 2 * result["within_sigma"],
                                result["mean"] + k / 2 * result["within_sigma"]))
        if result.get("lsl") is not None and result.get("usl") is not None:
            intervals.append(("规格", result["lsl"], result["usl"]))
    else:
        intervals = [("整体（Z 尺度）", -k / 2, k / 2)]
    for y, (label, lower, upper) in enumerate(intervals):
        ax.plot([lower, upper], [y, y], "o-", label=label)
        center = ((lower+upper)/2 if label == "规格" else result["mean"]) if _normal(result) else 0
        ax.plot(center, y, "|", color="#444444", markersize=12)
    ax.set_yticks(range(len(intervals)), [item[0] for item in intervals])
    if _normal(result):
        _specs(ax, result)
    else:
        for key, label in (("lsl", "LSL"), ("usl", "USL"), ("target", "Target")):
            value = result.get(key)
            if value is None:
                continue
            z = stats.norm.ppf(model.cdf(value))
            if np.isfinite(z):
                ax.axvline(z, color="#258248" if key == "target" else "#c62728",
                           linestyle="-.", label=label + "（Z）")
            else:
                ax.text(.02, .9 if key == "lsl" else .75, f"{label}：Z={z}（支持域边界）",
                        transform=ax.transAxes, fontsize=8)
    ax.set_ylim(-.6, len(intervals) - .4)
    indices = result.get("indices", {})
    summary = "  ".join(f"{key}={indices[key]:.4g}" if isinstance(indices[key],
                        (int, float)) and np.isfinite(indices[key]) else f"{key}=NA"
                        for key in ("Cp", "Cpk", "Pp", "Ppk") if key in indices)
    ax.set_xlabel(("Z=Φ⁻¹(F(x))；" if not _normal(result) else "") +
                  (summary or "分析尺度上的过程区间与规格限"))
    ax.legend(fontsize=8)


def control_diagnostics(result):
    """Return control statistics without mutating result; subgroup is 1-based.

    The first moving range is undefined and its outside flag is NA.
    """
    groups = [np.asarray(group, dtype=float) for group in result["groups"]]
    chart, title1, title2 = _charts(result, groups)
    rows = []
    for suffix, title in (("1", title1), ("2", title2)):
        values = np.asarray(chart["Y" + suffix], dtype=float)
        center, lower, upper = [np.broadcast_to(chart[key + suffix], values.shape)
                                for key in ("bar", "lcl", "ucl")]
        method = "正态 3σ 控制限；仅检验超控制限点"
        if not _normal(result):
            if title.startswith("I "):
                method = "拟合分布 0.135% / 99.865% 分位控制限"
            elif title.startswith("MR "):
                method = "正态 MR(2) 极差常数近似；非正态数据下并非精确概率限"
            else:
                method = "非正态子组使用正态 3σ 近似；不保证实际误报概率"
        for i, value in enumerate(values):
            rows.append({"chart": title, "subgroup": i + 1,
                         "size": len(groups[i]), "statistic": value,
                         "center": center[i], "lcl": lower[i], "ucl": upper[i],
                         "outside": bool(value < lower[i] or value > upper[i])
                         if np.isfinite(value) else pd.NA,
                         "method": method})
    table = pd.DataFrame(rows)
    table["outside"] = table["outside"].astype("boolean")
    return table


def plot_capability(result, figure=None, sixpack=True, recent=25):
    """Return a Figure using the validated core result (data/specs on one scale).

    sixpack=False shows histogram/Q-Q; transformed results additionally show
    the original-data histogram/Q-Q. The caller owns GUI display and saving.
    """
    if isinstance(recent, bool) or not isinstance(recent, (int, np.integer)) or recent < 1:
        raise ValueError("最近子组数必须为正整数")
    data = np.asarray(result["data"], dtype=float)
    if data.ndim != 1 or len(data) < 2 or not np.isfinite(data).all() or np.ptp(data) == 0:
        raise ValueError("绘图要求至少两个有限且不全相同的观测值")
    groups = [np.asarray(g, dtype=float) for g in result["groups"]]
    if not groups or any(g.ndim != 1 or not len(g) or not np.isfinite(g).all() for g in groups):
        raise ValueError("子组不能为空且必须包含有限观测值")
    fig = figure if figure is not None else Figure(figsize=(12, 10), layout="constrained")
    fig.clear()
    if sixpack:
        axes = fig.subplots(3, 2).ravel()
        chart, title1, title2 = _charts(result, groups)
        for ax, suffix, title in ((axes[0], "1", title1), (axes[2], "2", title2)):
            _control(ax, chart["Y" + suffix], chart["bar" + suffix],
                     chart["lcl" + suffix], chart["ucl" + suffix], title)
        _histogram(axes[1], data, result["model"], result)
        axes[1].set_title("能力直方图")
        _probability(axes[3], data, result["model"], result.get("fit"))
        axes[3].set_title("概率图（Q-Q）")
        start = max(0, len(groups) - recent)
        for i, group in enumerate(groups[start:], start + 1):
            axes[4].plot(np.full(len(group), i), group, ".", color="#444444")
        axes[4].axhline(result["mean"], color="#286ca2", linestyle=":", label="整体均值")
        axes[4].set_title(f"最近 {min(recent, len(groups))} 个子组")
        axes[4].set_xlabel("子组 / 观测顺序")
        _comparison(axes[5], result)
        axes[5].set_title("能力比较（过程区间 / 规格）")
    else:
        transformed = result.get("transform") is not None
        axes = np.atleast_1d(fig.subplots(2 if transformed else 1, 2)).ravel()
        if transformed:
            original = result["original"]
            raw = np.asarray(original["data"] if isinstance(original, dict) else original)
            raw_model = stats.norm(np.mean(raw), np.std(raw, ddof=1))
            _histogram(axes[0], raw, raw_model)
            _probability(axes[1], raw, raw_model, result.get("fit", {}).get("original_normality"))
            axes[0].set_title("原始数据直方图（正态参考）")
            axes[1].set_title("原始数据正态 Q-Q")
        _histogram(axes[-2], data, result["model"], result)
        _probability(axes[-1], data, result["model"], result.get("fit"))
        axes[-2].set_title("变换后直方图" if transformed else "能力直方图")
        axes[-1].set_title("变换后正态 Q-Q" if transformed else "概率图（Q-Q）")
    for ax in axes:
        style_axes(ax)
    scale = "变换尺度" if result.get("transform") is not None else "原始尺度"
    approximation = " · 非正态子组限为正态近似" if not _normal(result) and any(
        len(group) > 1 for group in groups) else ""
    fig.suptitle(f"过程能力诊断 · {scale} · 控制限≠规格限；仅标记超控制限点{approximation}",
                 fontfamily=axes[0].title.get_fontfamily(), fontsize=12)
    return fig


def _shared_range(stages):
    """两阶段与规格共用同一横轴范围，避免视觉上夸大差异。"""
    low = min(np.min(np.asarray(stage["data"], dtype=float)) for stage in stages)
    high = max(np.max(np.asarray(stage["data"], dtype=float)) for stage in stages)
    specs = [value for stage in stages
             for value in (stage.get("lsl"), stage.get("usl"), stage.get("target"))
             if value is not None]
    if specs:
        low, high = min([low] + specs), max([high] + specs)
    pad = (high - low) * .05 or 1.
    return low - pad, high + pad


def _diagnostics_text(result, index):
    stage = result.plot["diagnostics"][index]
    fit = result.plot["results"][index]["fit"]
    lines = ["%s %d/%d；%s 超限 %d" % (
        "异常" if stage["rules"] else "越限",
        stage["alarms"], stage["points"], stage["secondary"], stage["beyond"]),
             "非正态仅判越限，未判连续模式" if not stage["rules"] else "",
             "分布失配，预计 PPM 不可靠" if fit["mismatch"] else "分布未拒绝"]
    if stage["alarms"] or stage["beyond"]:
        lines.append("能力仅描述样本期，不宜预测稳定运行")
    return "\n".join(line for line in lines if line)


def _ppm_panel(ax, result):
    """实测与预计统一换算为 PPM；0 不画条形，缺失显示 NA。"""
    rows = [("实测超规 PPM", "observed"), ("预计 PPM（整体）", "overall")]
    if "within" in result["results"][0]["ppm"]:
        rows.append(("预计 PPM（组内）", "within"))
    values = [[None if item["ppm"].get(key, {}).get("total") is None
               else float(item["ppm"][key]["total"]) for item in result["results"]]
              for _, key in rows]
    known = [value for pair in values for value in pair if value and value > 0]
    floor = min([1.] + [value / 10 for value in known])
    height, colors = .36, ["#4a7fa7", "#2f7d5f"]
    for row, (_, key) in enumerate(rows):
        for index in range(len(result["names"])):
            value = values[row][index]
            y = row + (index - .5) * height
            # 对数轴上任何可见长度都会把 0 画成非零，因此只标注文字。
            if value:
                ax.barh(y, max(value, floor), .9 * height, color=colors[index])
            ax.text(max(value or 0., floor) * 1.25, y,
                    "NA" if value is None else "%.4g" % value, va="center", fontsize=8)
    ax.set_yticks(range(len(rows)), [label for label, _ in rows])
    ax.set_xscale("log")
    ax.set_xlim(left=floor / 2, right=max(known + [1.]) * 10)
    ax.set_xlabel("PPM（对数轴，条形下限 %.3g；0 不画条形）" % floor)
    ax.invert_yaxis()
    ax.legend(handles=[Patch(color=color, label=name) for color, name
                       in zip(colors, result["names"])], fontsize=8, loc="lower right")


def plot_capability_comparison(result, figure=None):
    """两阶段能力对比图：统一原始尺度与同一规格，复用现有直方图样式。"""
    stages = result.plot["results"]
    if len(stages) != 2:
        raise ValueError("对比图需要恰好两个阶段")
    pairs = [stage for stage in stages if np.ptp(np.asarray(stage["data"], dtype=float)) > 0]
    if len(pairs) != 2:
        raise ValueError("对比图要求每阶段至少两个不全相同的观测值")
    figure = figure if figure is not None else Figure(figsize=(12, 9))
    figure.clear()
    axes = figure.subplots(2, 2).ravel()
    low, high = _shared_range(stages)
    xs = np.linspace(low, high, 400)
    indices = [stage["indices"] for stage in stages]
    keys = [key for key in ("Cp", "Cpk", "Pp", "Ppk")
            if any(isinstance(item.get(key), (int, float)) and np.isfinite(item.get(key))
                   for item in indices)]
    for position, (name, stage) in enumerate(zip(result.plot["names"], stages)):
        ax = axes[position]
        _histogram(ax, stage["data"], stage["model"], stage)
        ax.set_xlim(low, high)
        ax.set_title(name + "能力直方图")
        ax.set_xlabel("原始测量值")
        ax.set_ylabel("密度")
        ax.text(.02, .96, "  ".join("%s=%.3g" % (key, indices[position][key])
                                   for key in keys) or "无可用能力指数",
                transform=ax.transAxes, va="top", fontsize=8)
        ax.text(.02, .04, _diagnostics_text(result, position), transform=ax.transAxes,
                va="bottom", fontsize=7.5, color="#a03c1c")
    if keys:
        bar_width = .8 / len(keys)
        for position, index in enumerate(indices):
            positions = np.arange(len(keys)) + (position - .5) * bar_width
            values = [index.get(key) if isinstance(index.get(key), (int, float))
                      and np.isfinite(index.get(key)) else np.nan for key in keys]
            axes[2].bar(positions, values, bar_width, label=result.plot["names"][position])
            for x, value in zip(positions, values):
                if np.isfinite(value):
                    axes[2].text(x, value, "%.3g" % value, ha="center", fontsize=7,
                                 va="bottom" if value >= 0 else "top")
        axes[2].set_xticks(range(len(keys)), keys)
        axes[2].axhline(0, color="#444444", linewidth=.8)
        axes[2].set_ylabel("指数值")
        axes[2].legend(fontsize=8)
        axes[2].set_title("能力指数对比")
    else:
        axes[2].text(.5, .5, "非正态百分位法不定义 Cp/Cpk，见 PPM 面板",
                     transform=axes[2].transAxes, ha="center", va="center", fontsize=9)
        axes[2].set_axis_off()
    _ppm_panel(axes[3], result.plot)
    axes[3].set_title("实测超规率与预计 PPM（口径不同）")
    for ax in axes:
        style_axes(ax)
    figure.suptitle("改善前后过程能力对比 · 原始尺度 · 规格与 K 两阶段一致",
                    fontsize=12, fontfamily=font_families("Microsoft YaHei")[:2])
    return figure

