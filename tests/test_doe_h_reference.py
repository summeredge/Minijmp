from pathlib import Path
import runpy


def test_doe_h_independent_reference_is_intact():
    root = Path(__file__).parent / "fixtures" / "doe_h_reference"
    runpy.run_path(str(root / "verify.py"))["verify"]()
