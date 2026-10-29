import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VERIFY = ROOT / "tests" / "fixtures" / "doe_phase2_splitplot_reference" / "verify.py"


def test_p2_3_splitplot_reference_fixture_verifies_independently():
    result = subprocess.run([sys.executable, str(VERIFY)], cwd=ROOT,
                            capture_output=True, text=True, check=True)
    assert "Cases 1" in result.stdout
    assert "8c4ccc639a44954582290a3e49cb85695b25a46f29a5fd0c575b8efb74e3f32f" in result.stdout
