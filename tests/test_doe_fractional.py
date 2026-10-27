from itertools import product
import random

import numpy as np
import pytest

from doe_core import DesignSpec, FactorSpec, worksheet_metadata
from doe_fractional import create_fractional, validate_fractional_design


def spec(factors="ABCD", generators=("D=AB",), seed=23, **kwargs):
    return DesignSpec(
        "fractional-test",
        tuple(FactorSpec(factor_id, f"因子{factor_id}", i * 10, i * 10 + 2)
              for i, factor_id in enumerate(factors)),
        ("Y",), seed=seed, generators=generators,
        design_type="two_level_fractional", **kwargs,
    )


def test_two_level_runs_match_independent_generator_formula_and_schema():
    design = spec()
    frame, metadata = create_fractional(design, replicates=2, measured=True)
    restored = validate_fractional_design(frame, metadata)

    expected = {
        (a, b, c, a * b)
        for a, b, c in product((-1, 1), repeat=3)
    }
    for replicate in (1, 2):
        actual = {
            tuple(int(design.factors[i].to_coded(run.settings[factor_id]))
                  for i, factor_id in enumerate("ABCD"))
            for run in restored.runs
            if run.point_type == "factorial" and run.replicate == replicate
        }
        assert actual == expected

    assert set(frame["运行序"]) == set(range(1, len(frame) + 1))
    assert set(metadata["design"]["generators"]) == {"D=AB"}
    assert metadata["design"]["defining_relations"] == ["I=ABD"]
    assert metadata["design"]["aliases"] == [
        "A=BD", "B=AD", "C=ABCD", "D=AB", "AC=BCD", "BC=ACD", "CD=ABC",
    ]
    assert list(metadata) == ["schema_version", "design", "column_map", "worksheet"]
    assert all(f"实测_{factor_id}" in frame for factor_id in "ABCD")


def test_multiple_generators_return_complete_defining_and_alias_groups():
    design = spec("ABCDE", ("D=AB", "E=AC"))
    frame, metadata = create_fractional(design)
    relations = metadata["design"]

    assert len(frame) == 8
    assert relations["defining_relations"] == ["I=ABD", "I=ACE", "I=BCDE"]
    assert len(relations["aliases"]) == 21
    assert {"A=BD", "A=CE", "A=ABCDE", "B=AD", "B=ABCE", "B=CDE"} <= set(
        relations["aliases"])
    assert validate_fractional_design(frame, metadata).spec.generators == (
        "D=AB", "E=AC")


def test_re_signed_factor_tampering_fails_strict_validation():
    frame, metadata = create_fractional(spec())
    row = frame.index[frame["运行ID"] == "R00001"][0]
    factor = DesignSpec.from_dict(metadata["design"]).factors[-1]
    current = frame.at[row, "设定_D"]
    frame.at[row, "设定_D"] = factor.high if current == factor.low else factor.low

    # Recompute the normal DOE fingerprint to prove structural validation is separate.
    signed_again = worksheet_metadata(
        frame, DesignSpec.from_dict(metadata["design"]), metadata["column_map"])
    with pytest.raises(ValueError, match="生成元"):
        validate_fractional_design(frame, signed_again)


@pytest.mark.parametrize("generators", [
    ("D=AB", "D=AC"),
    ("D=AB", "E=AD"),
    ("D=AB", "E=AB"),
    ("D=AA",),
    ("I=ABD=ACE",),
    ("E=AC", "D=AB"),
])
def test_invalid_generator_systems_are_rejected(generators):
    with pytest.raises(ValueError):
        create_fractional(spec("ABCDE", generators))


def test_design_definition_and_run_limits_are_checked():
    with pytest.raises(ValueError, match="defining_relations"):
        create_fractional(spec(defining_relations=("I=ABC",)))
    with pytest.raises(ValueError, match="运行总数"):
        create_fractional(spec(), replicates=10001)
    with pytest.raises(ValueError, match="seed"):
        create_fractional(spec(seed=None))
    with pytest.raises(ValueError, match="中心点"):
        create_fractional(spec(), center_points=1)
    with pytest.raises(ValueError, match="A、B、C"):
        create_fractional(spec("BACD", ("D=AB",)))
    with pytest.raises(ValueError, match="右侧"):
        create_fractional(spec("ABCD", ("D=BA",)))
    with pytest.raises(ValueError):
        create_fractional(spec("ABCD", ("d=AB",)))
    with pytest.raises(ValueError):
        spec("ABCD", ("D=A B",))
    with pytest.raises(ValueError, match="3 至 6 个因子"):
        create_fractional(spec("ABCDEFG", ("G=AB",)))


@pytest.mark.parametrize(("factors", "generators", "expected_runs"), [
    ("ABC", ("C=AB",), 4),
    ("ABCDEF", ("E=AB", "F=CD"), 16),
])
def test_supported_factor_count_edges(factors, generators, expected_runs):
    frame, metadata = create_fractional(spec(factors, generators))
    assert len(frame) == expected_runs
    assert len(validate_fractional_design(frame, metadata).spec.factors) == len(factors)


def test_seed_is_local_and_large_integer_levels_stay_exact():
    state = random.getstate()
    base = 2**60 + 1
    design = DesignSpec(
        "large-levels",
        tuple(FactorSpec(factor_id, factor_id, base + i * 4, base + i * 4 + 2)
              for i, factor_id in enumerate("ABCD")),
        ("Y",), seed=31, generators=("D=AB",),
        design_type="two_level_fractional",
    )
    frame, metadata = create_fractional(design)
    same, _ = create_fractional(design)
    assert random.getstate() == state
    assert frame["运行ID"].tolist() == same["运行ID"].tolist()
    assert {run.settings["A"] for run in validate_fractional_design(frame, metadata).runs} == {
        base, base + 2}


@pytest.mark.parametrize(('factors', 'generators', 'relations', 'resolution'), [
    ('ABC', ('C=AB',), {'I=ABC'}, 3),
    ('ABCD', ('D=ABC',), {'I=ABCD'}, 4),
    ('ABCDE', ('E=ABCD',), {'I=ABCDE'}, 5),
    ('ABCDE', ('D=AB', 'E=AC'), {'I=ABD', 'I=ACE', 'I=BCDE'}, 3),
])
def test_independent_matrix_proves_defining_words_and_aliases(factors, generators, relations, resolution):
    design = spec(factors, generators)
    frame, metadata = create_fractional(design)
    columns = {f.factor_id: np.asarray([float(f.to_coded(x)) for x in frame[f'设定_{f.factor_id}']])
               for f in design.factors}
    assert set(metadata['design']['defining_relations']) == relations
    assert min(len(word.split('=')[1]) for word in relations) == resolution
    assert len(relations) + 1 == 2 ** len(generators)
    for relation in relations:
        np.testing.assert_array_equal(np.prod([columns[c] for c in relation[2:]], axis=0), 1)
    for relation in metadata['design']['aliases']:
        left, right = relation.split('=')
        np.testing.assert_array_equal(np.prod([columns[c] for c in left], axis=0),
                                      np.prod([columns[c] for c in right], axis=0))
    matrix = np.column_stack([np.ones(len(frame)), *columns.values()])
    np.testing.assert_allclose(matrix.T @ matrix, np.eye(len(factors) + 1) * len(frame))
    if generators == ('D=ABC',):
        assert {'A=BCD', 'AB=CD'} <= set(metadata['design']['aliases'])
