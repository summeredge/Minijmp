import pytest

from doe_core import DesignSpec, FactorSpec
from doe_splitplot import create_split_plot, validate_split_plot_design


def spec(blocks=3, seed=42, factors=None):
    factors = factors or (
        FactorSpec("A", "A", -1, 1, randomization_role="hard_to_change"),
        FactorSpec("B", "B", -1, 1, randomization_role="easy_to_change"),
    )
    return DesignSpec(
        "split", factors, ("Y",), seed=seed, design_type="split_plot",
        block_count=blocks, randomization_unit="whole_plot", error_structure="split_plot",
    )


def v2_spec(hard=2, easy=2, blocks=3, seed=42, schema_version=5):
    factors = tuple(
        FactorSpec(chr(ord("A") + index), chr(ord("A") + index), -1, 1,
                   randomization_role=("hard_to_change" if index < hard
                                       else "easy_to_change"))
        for index in range(hard + easy))
    return DesignSpec(
        "split-v2", factors, ("Y",), seed=seed, design_type="split_plot",
        schema_version=schema_version, block_count=blocks, construction_version="v2",
        randomization_unit="whole_plot", error_structure="split_plot",
    )


def test_standard_order_and_nested_seed_randomization():
    design = spec()
    frame, metadata = create_split_plot(design)
    assert len(frame) == 12
    standard = frame.sort_values("标准序")
    factor_columns = metadata["column_map"]["factors"]
    coded = [
        (int(design.factors[0].to_coded(row[factor_columns["A"]])),
         int(design.factors[1].to_coded(row[factor_columns["B"]])))
        for _, row in standard.iterrows()
    ]
    assert coded == [(-1, -1), (-1, 1), (1, -1), (1, 1)] * 3

    actual = frame.sort_values("运行序")
    assert actual["运行ID"].tolist() == [
        "R00007", "R00008", "R00006", "R00005", "R00004", "R00003",
        "R00002", "R00001", "R00011", "R00012", "R00010", "R00009",
    ]
    block_order = actual["区组"].iloc[::4].tolist()
    assert len(block_order) == len(set(block_order)) == 3
    assert set(block_order) == {1, 2, 3}
    assert all(actual["区组"].iloc[start:start + 4].tolist() == [block] * 4
               for start, block in zip(range(0, 12, 4), block_order))
    for _, block in actual.groupby("区组", sort=True):
        whole_plots = block.groupby("整区ID", sort=False)
        assert len(whole_plots) == 2
        assert [group["整区序"].iloc[0] for _, group in whole_plots] == [1, 2]
        for _, subplot in whole_plots:
            assert len(subplot) == 2
            assert subplot["子区序"].tolist() == [1, 2]

    repeated, _ = create_split_plot(spec(seed=42))
    different, _ = create_split_plot(spec(seed=91))
    assert frame["运行ID"].tolist() == repeated["运行ID"].tolist()
    assert frame["运行ID"].tolist() != different["运行ID"].tolist()
    validate_split_plot_design(frame, metadata)


@pytest.mark.parametrize("build_design", [
    lambda: spec(blocks=1), lambda: spec(seed=None),
    lambda: spec(blocks=2501),
    lambda: spec(factors=(
        FactorSpec("A", "A", -1, 1, randomization_role="hard_to_change"),
        FactorSpec("B", "B", -1, 1, randomization_role="easy_to_change"),
        FactorSpec("C", "C", -1, 1),
    )),
])
def test_rejects_designs_outside_the_supported_scope(build_design):
    with pytest.raises(ValueError):
        create_split_plot(build_design())


def test_rejects_corrupted_whole_plot_identity():
    frame, metadata = create_split_plot(spec())
    frame.loc[0, "整区ID"] = "WP99999H1"
    with pytest.raises(ValueError):
        validate_split_plot_design(frame, metadata)


def test_run_limit_is_checked_before_layout_or_randomization(monkeypatch):
    monkeypatch.setattr("doe_splitplot.random.Random",
                        lambda *_: pytest.fail("layout allocated before run-limit rejection"))
    with pytest.raises(ValueError, match="10000"):
        create_split_plot(spec(blocks=2501))


@pytest.mark.parametrize(("hard", "easy", "blocks", "runs", "whole_plots"), [
    (1, 2, 3, 24, 6),
    (2, 2, 3, 48, 12),
    (3, 1, 2, 32, 16),
    (3, 3, 2, 128, 16),
])
def test_v2_design_has_complete_nested_experimental_units(
        hard, easy, blocks, runs, whole_plots):
    design = v2_spec(hard, easy, blocks)
    frame, metadata = create_split_plot(design)
    columns = metadata["column_map"]
    hard_columns = [columns["factors"][factor.factor_id]
                    for factor in design.factors[:hard]]
    easy_columns = [columns["factors"][factor.factor_id]
                    for factor in design.factors[hard:]]
    assert len(frame) == runs == blocks * (1 << (hard + easy))
    assert frame[columns["whole_plot_id"]].nunique() == whole_plots
    assert frame[columns["subplot_id"]].nunique() == runs
    assert all(count == 1 << easy for count in
               frame.groupby(columns["whole_plot_id"]).size())

    actual = frame.sort_values(columns["run_order"])
    block_groups = list(actual.groupby(columns["block"], sort=False))
    assert len(block_groups) == blocks
    assert all(len(group) == runs // blocks for _, group in block_groups)
    for _, block in block_groups:
        plots = list(block.groupby(columns["whole_plot_id"], sort=False))
        assert len(plots) == (1 << hard)
        assert [plot[columns["whole_plot_order"]].iloc[0] for _, plot in plots] == list(
            range(1, (1 << hard) + 1))
        assert all(plot[columns["whole_plot_order"]].nunique() == 1
                   and plot[columns["subplot_order"]].tolist() == list(range(1, (1 << easy) + 1))
                   and plot[hard_columns].nunique().max() == 1
                   and len(plot[columns["subplot_id"]].unique()) == 1 << easy
                   and len(plot[easy_columns].drop_duplicates()) == 1 << easy
                   for _, plot in plots)
    validate_split_plot_design(frame, metadata)


def test_v2_randomization_changes_order_not_design_or_units():
    first, first_meta = create_split_plot(v2_spec(seed=42))
    repeated, _ = create_split_plot(v2_spec(seed=42))
    different, _ = create_split_plot(v2_spec(seed=91))
    columns = first_meta["column_map"]
    assert first.equals(repeated)
    assert first[columns["run_id"]].tolist() != different[columns["run_id"]].tolist()
    point_columns = [columns["block"], *columns["factors"].values(),
                     columns["whole_plot_id"], columns["subplot_id"]]
    assert sorted(map(tuple, first[point_columns].to_numpy().tolist())) == sorted(
        map(tuple, different[point_columns].to_numpy().tolist()))


def test_v2_run_limit_is_rejected_before_factorial_expansion(monkeypatch):
    monkeypatch.setattr("doe_splitplot.product",
                        lambda *_args, **_kwargs: pytest.fail("expanded before budget check"))
    with pytest.raises(ValueError, match="10000"):
        create_split_plot(v2_spec(hard=3, easy=3, blocks=157))


@pytest.mark.parametrize("build_design", [
    lambda: v2_spec(hard=0, easy=2),
    lambda: v2_spec(hard=4, easy=1),
    lambda: v2_spec(hard=1, easy=0),
    lambda: v2_spec(hard=1, easy=6),
    lambda: v2_spec(schema_version=4),
    lambda: v2_spec(seed=None),
    lambda: v2_spec(seed=True),
    lambda: v2_spec(seed=1.5),
    lambda: v2_spec(blocks=1),
    lambda: v2_spec(blocks=2.5),
])
def test_v2_rejects_invalid_version_factor_seed_and_block_settings(build_design):
    with pytest.raises(ValueError):
        create_split_plot(build_design())
