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


@pytest.mark.parametrize("design", [
    spec(blocks=1), spec(seed=None),
    spec(blocks=2501),
    spec(factors=(
        FactorSpec("A", "A", -1, 1, randomization_role="hard_to_change"),
        FactorSpec("B", "B", -1, 1, randomization_role="easy_to_change"),
        FactorSpec("C", "C", -1, 1),
    )),
])
def test_rejects_designs_outside_the_supported_scope(design):
    with pytest.raises(ValueError):
        create_split_plot(design)


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
