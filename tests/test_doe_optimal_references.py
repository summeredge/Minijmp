from pathlib import Path
import runpy


def test_independent_optimal_reference_contracts():
    verifier = (Path(__file__).parent / "fixtures" / "doe_optimal_reference"
                / "verify.py")
    assert runpy.run_path(str(verifier))["verify"]()
