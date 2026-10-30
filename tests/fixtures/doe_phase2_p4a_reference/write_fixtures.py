"""重新生成参考数据与 manifest（仅在确认数学变更后运行）。"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from build_dsd_reference import build as build_dsd
from build_pb_foldover_reference import build as build_pb


ROOT = Path(__file__).resolve().parent


def _write(name, payload):
    path = ROOT / name
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=1) + "\n",
                    encoding="utf-8", newline="\n")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    dsd = build_dsd()
    pb = build_pb()
    digests = {
        "dsd_reference.json": _write("dsd_reference.json", {"schema": 1, "cases": dsd}),
        "pb_foldover_reference.json": _write("pb_foldover_reference.json",
                                            {"schema": 1, "cases": pb}),
    }
    manifest = {
        "schema": 1,
        "method_contract": "docs/doe-minitab/phase2-p4a-method-contract.md",
        "sources": [
            {
                "id": "minitab-stepwise-formulas",
                "url": "https://support.minitab.com/en-us/minitab/help-and-how-to/statistical-modeling/doe/how-to/screening/analyze-screening-design/methods-and-formulas/stepwise/",
                "claim": "移除优先：Alpha to remove 超限先删除最大 p；不能再删除才尝试进入；F 使用加入/删除项后的 MSE。",
                "product_version": "页面未标注产品版本",
            },
            {
                "id": "minitab-folding",
                "url": "https://support.minitab.com/en-us/minitab/help-and-how-to/statistical-modeling/doe/supporting-topics/factorial-and-screening-designs/what-is-folding/",
                "claim": "折叠复制数据追加到原表下方，并翻转指定因子的符号；PB 与分数因子均可折叠。",
                "product_version": "页面未标注产品版本",
            },
        ],
        "files": {"dsd_reference.json": digests["dsd_reference.json"],
                  "pb_foldover_reference.json": digests["pb_foldover_reference.json"]},
        "dsd_matrices": ["tests/fixtures/doe_screening_reference/dsd/dsd_06_cont_13.csv",
                         "tests/fixtures/doe_screening_reference/dsd/dsd_04_cont_01_cat_14.csv"],
        "pb_matrices": {"publication": "tests/fixtures/doe_screening_reference/pb/pb{N}.csv",
                        "mathematical_construction": "Sylvester(32)/doubled PB20(40)/Paley I(q=43,47)"},
        "limits": ["未使用 Minitab 22 产品输出",
                   "PB 不使用正规 defining relation；完全的别名来自逐个整数列的相等比较",
                   "numpy 奇异值秩仅用于 24 行以上的联合模型规模检查"],
    }
    _write("manifest.json", manifest)
    print(json.dumps(digests, indent=1))


if __name__ == "__main__":
    main()
