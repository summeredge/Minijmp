from pathlib import Path
import runpy


def test_independent_factorial_reference_contracts():
    verifier = Path(__file__).parent / "fixtures" / "doe_factorial_reference" / "verify.py"
    assert runpy.run_path(str(verifier))["verify"]()
