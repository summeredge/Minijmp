import pandas as pd
import pytest

from worksheet_merge import merge_worksheets


@pytest.mark.parametrize("how,counts", [
    ("inner", (4, 0, 0)), ("left", (4, 2, 0)),
    ("right", (4, 0, 2)), ("outer", (4, 2, 2)),
])
def test_composite_join_against_pandas(how, counts):
    left = pd.DataFrame({"key": pd.array([1, 1, 1, None], dtype="Int64"),
                         "date": pd.to_datetime(["2020-01-01"]*2 + ["2020-01-02"]*2),
                         "id": [2**54+1, 2**54+3, 7, 8]})
    right = pd.DataFrame({"batch": pd.array([1, 1, 1, None], dtype="Int64"),
                          "when": pd.to_datetime(["2020-01-01"]*2 + ["2020-01-03", "2020-01-02"]),
                          "id": ["a", "b", "c", None]})
    frame, actual = merge_worksheets(left, right, [0, 1, 2], [0, 1, 2],
                                     keys=([0, 1], [0, 1]), how=how)
    ref = pd.merge(left.astype({"id": "Int64"}), right, left_on=["key", "date"],
                   right_on=["batch", "when"], suffixes=("", "（右）"), how=how,
                   indicator=True)
    both = ref["_merge"].eq("both") & ref["key"].notna()
    pd.testing.assert_frame_equal(frame.loc[frame.key.notna() & frame.batch.notna()].reset_index(drop=True),
                                  ref.loc[both, frame.columns].reset_index(drop=True),
                                  check_dtype=False)
    assert frame.id.dropna().iloc[0] == 2**54+1
    assert actual == counts and len(frame) == sum(counts)
    assert list(frame.columns) == ["key", "date", "id", "batch", "when", "id（右）"]


def test_native_fixed_case_and_side_by_side_values():
    left = pd.DataFrame({"key": [1, 1, 2], "value": [10, 11, 12]})
    right = pd.DataFrame({"key": [1, 1, 3], "value": [21, 22, 23]})
    joined, counts = merge_worksheets(left, right, [0, 1], [0, 1], keys=([0], [0]))
    assert counts == (4, 1, 1) and joined.shape == (6, 4)
    assert list(zip(joined.value.iloc[:4], joined["value（右）"].iloc[:4])) == [
        (10, 21), (10, 22), (11, 21), (11, 22)]
    frame, counts = merge_worksheets(left, right, [0, 1], [0, 1])
    pd.testing.assert_frame_equal(frame, pd.concat([left, right.add_suffix("（右）")], axis=1))
    assert counts == (3, 0, 0)
    frame, counts = merge_worksheets(left, right.iloc[:1], [1], [1])
    assert counts == (1, 2, 0)
    assert frame["value（右）"].isna().tolist() == [False, True, True]


def test_mixed_numeric_keys_do_not_match_rounded_identifiers():
    left = pd.DataFrame({"k": [2**54, 2**54 + 1]})
    right = pd.DataFrame({"k": [float(2**54)]})
    result, counts = merge_worksheets(left, right, [0], [0], keys=([0], [0]))
    assert counts == (1, 1, 0)
    assert result.loc[result["k（右）"].notna(), "k"].tolist() == [2**54]
