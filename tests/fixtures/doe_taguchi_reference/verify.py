"""运行独立 Taguchi 参考核验；不导入生产模块。"""
from pathlib import Path

import pytest


if __name__ == "__main__":
    raise SystemExit(pytest.main([str(Path(__file__).resolve().parents[2] /
                                      "test_doe_taguchi_references.py"), "-q"]))
