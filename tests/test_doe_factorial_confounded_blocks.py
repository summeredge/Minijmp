import math
import random
from itertools import product

import pytest

from doe_core import DesignSpec, FactorSpec, restore_design_result
from doe_factorial import (confounded_block_effects, create_factorial,
                           validate_factorial_design)


def spec(generators, factors=("A", "B", "C"), seed=7):
    factor_specs = tuple(FactorSpec(name, name, -1, 1) for name in factors)
    return DesignSpec(
        "confounded", factor_specs, ("Y",), seed=seed,
        design_type="two_level_full", construction_version="v2",
        block_count=1 << len(generators),
        randomization_unit="confounded_block",
        confounded_block_generators=tuple(tuple(term) for term in generators))


def test_2_cubed_abc_confounded_blocks_have_four_runs_and_roundtrip():
    design = spec((("A", "B", "C"),))
    frame, metadata = create_factorial(design)
    restored = validate_factorial_design(frame, metadata)
    assert metadata["schema_version"] == metadata["design"]["schema_version"] == 5
    assert metadata["design"]["confounded_block_generators"] == [["A", "B", "C"]]
    assert len(restored.runs) == 8
    assert {run.block for run in restored.runs} == {"B1", "B2"}
    assert sorted(sum(run.block == block for run in restored.runs)
                  for block in ("B1", "B2")) == [4, 4]

    for run in restored.runs:
        abc = math.prod(
            int(next(f for f in design.factors if f.factor_id == name)
                .to_coded(run.settings[name]))
            for name in ("A", "B", "C"))
        assert run.block == ("B1" if abc == -1 else "B2")
    assert confounded_block_effects(restored.spec) == (("A", "B", "C"),)
    assert DesignSpec.from_dict(metadata["design"]) == design


def test_multiple_block_generators_include_their_product_effect():
    design = spec((("A", "B", "C"), ("A", "B", "D")), factors="ABCD")
    frame, metadata = create_factorial(design)
    restored = validate_factorial_design(frame, metadata)
    assert sorted(sum(run.block == f"B{block}" for run in restored.runs)
                  for block in range(1, 5)) == [4, 4, 4, 4]
    assert confounded_block_effects(restored.spec) == (
        ("C", "D"), ("A", "B", "C"), ("A", "B", "D"))
    for run in restored.runs:
        codes = {factor.factor_id: int(factor.to_coded(run.settings[factor.factor_id]))
                 for factor in restored.spec.factors}
        signature = tuple(math.prod(codes[name] for name in generator)
                          for generator in restored.spec.confounded_block_generators)
        block = 1 + list(product((-1, 1), repeat=2)).index(signature)
        assert run.block == f"B{block}"


def test_confounded_block_order_is_seeded_and_old_schema_v5_is_unchanged():
    current = spec((("A", "B", "C"),))
    frame, metadata = create_factorial(current)
    same, _ = create_factorial(current)
    other, _ = create_factorial(spec((("A", "B", "C"),), seed=8))
    assert frame["运行ID"].tolist() == same["运行ID"].tolist()
    assert frame["运行ID"].tolist() != other["运行ID"].tolist()

    old = DesignSpec(
        "old", tuple(FactorSpec(name, name, -1, 1) for name in "ABC"),
        ("Y",), seed=7, design_type="two_level_full")
    old_data = old.to_dict()
    assert "confounded_block_generators" not in old_data
    assert DesignSpec.from_dict(old_data) == old
    assert restore_design_result(frame, metadata).spec == current


@pytest.mark.parametrize("generators", [
    (("A", "B", "C"), ("A", "B")),
    (("A", "B", "C"), ("A", "B", "C")),
    (("A", "B", "Z"),),
    (("A",),),
])
def test_invalid_block_generator_set_is_rejected(generators):
    with pytest.raises(ValueError):
        spec(generators)


def test_confounded_blocks_reject_replicates_and_center_points():
    design = spec((("A", "B", "C"),))
    with pytest.raises(ValueError, match="单次"):
        create_factorial(design, replicates=2)
    with pytest.raises(ValueError, match="单次"):
        create_factorial(design, center_points=2)


def test_confounded_block_metadata_rejects_invalid_generator_shape():
    data = spec((("A", "B", "C"),)).to_dict()
    data["confounded_block_generators"] = "ABC"
    with pytest.raises(ValueError, match="字段结构"):
        DesignSpec.from_dict(data)
