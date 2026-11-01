import pandas as pd
import numpy as np


def _nullable_dtype(dtype):
    if pd.api.types.is_extension_array_dtype(dtype):
        return None
    if pd.api.types.is_bool_dtype(dtype):
        return 'boolean'
    if pd.api.types.is_integer_dtype(dtype):
        dtype = np.dtype(dtype)
        return ('UInt' if dtype.kind == 'u' else 'Int') + str(dtype.itemsize * 8)
    return None


def _is_missing(value):
    return value is None or value is pd.NA or value is pd.NaT or (
        pd.api.types.is_scalar(value) and bool(pd.isna(value)))


def _integer_fits(value, dtype):
    limits = np.iinfo(dtype)
    return limits.min <= value <= limits.max


def _infer(values):
    """Infer a new column without turning exact integers into lossy floats."""
    present = [value for value in values if not _is_missing(value)]
    integers = [value for value in present
                if isinstance(value, (int, np.integer))
                and not isinstance(value, (bool, np.bool_))]
    if integers and len(integers) == len(present):
        exact = [int(value) if not _is_missing(value) else value for value in values]
        if len(present) == len(values):
            try:
                return pd.Series(exact)
            except (OverflowError, TypeError, ValueError):
                return pd.Series(exact, dtype=object)
        if all(_integer_fits(value, 'int64') for value in integers):
            return pd.Series(pd.array(exact, dtype='Int64'))
        if all(_integer_fits(value, 'uint64') for value in integers):
            return pd.Series(pd.array(exact, dtype='UInt64'))
        return pd.Series(exact, dtype=object)
    if any(float(int(value)) != int(value) for value in integers):
        # Exact integers cannot share a float column; keep the original digits.
        return pd.Series(values, dtype=object)
    return pd.Series(values)


def _extend(series, height):
    series = series.reset_index(drop=True)
    if height == len(series):
        return series.set_axis(range(height))
    # Padding with NaN would turn int64/uint64 into float64 and round large ints.
    series = series.astype(_nullable_dtype(series.dtype) or series.dtype)
    return series.reindex(range(height)).set_axis(range(height))


def _keeps_dtype(dtype, values):
    """Whether the target dtype holds every value exactly."""
    numbers = [value for value in values if not _is_missing(value)]
    if pd.api.types.is_integer_dtype(dtype):
        return all(isinstance(value, (int, float, np.integer, np.floating))
                   and float(int(value)) == value
                   and _integer_fits(int(value), getattr(dtype, 'numpy_dtype', dtype))
                   for value in numbers)
    if pd.api.types.is_float_dtype(dtype):
        target = np.dtype(getattr(dtype, 'numpy_dtype', dtype)).type
        for value in numbers:
            if not isinstance(value, (int, float, np.integer, np.floating)) \
                    or isinstance(value, (bool, np.bool_)):
                return False
            cast = target(value)
            # Compare integers as ints: casting to float first would hide rounding.
            exact = (int(cast) == int(value) if isinstance(value, (int, np.integer))
                     else float(cast) == float(value))
            if not exact or not np.isfinite(cast):
                return False
        return True
    return True


def _write(series, rows, values):
    """Overwrite rows while keeping the column dtype when the values fit."""
    rows = list(rows)
    values = list(values)
    if _keeps_dtype(series.dtype, values):
        nullable = _nullable_dtype(series.dtype)
        if nullable and any(_is_missing(value) for value in values):
            series = series.astype(nullable)
        updated = series.copy()
        try:
            updated.iloc[rows] = values
            return updated
        except (TypeError, ValueError, OverflowError):
            pass
    # Rows may sit past the column's current end after a vertical expansion.
    result = list(series.array) + [None] * (max(rows) + 1 - len(series))
    for row, value in zip(rows, values):
        result[row] = value
    if pd.api.types.is_float_dtype(series.dtype):
        # Widen to float64, but keep exact integers that float64 cannot hold.
        numbers = [value for value in result if not _is_missing(value)]
        if all(isinstance(value, (float, np.floating)) for value in numbers):
            widened = [pd.NA if _is_missing(value) else float(value) for value in result]
            dtype = 'Float64' if pd.api.types.is_extension_array_dtype(series.dtype) else 'float64'
            return pd.Series(widened, dtype=dtype)
        return pd.Series([float(value) if isinstance(value, (float, np.floating))
                          else value for value in result], dtype=object)
    return _infer(result)


def df_combine(df1, df2, ins_x=0, ins_y=0):
    df1h, df1w = df1.shape
    df2h, df2w = df2.shape
    h = max(df1h, ins_y + df2h)
    w = max(df1w, ins_x + df2w)
    # Rebuild column by column so untouched columns keep their dtype and values.
    blocks = []
    for x, (_, values) in enumerate(df1.items()):
        blocks.append(_extend(values, h))
    # New columns start blank; their values are inferred after the patch is applied.
    blocks.extend(pd.Series([np.nan] * h) for _ in range(df1w, w))
    if df2h:
        for x, (_, values) in enumerate(df2.items()):
            rows = range(ins_y, ins_y + df2h)
            position = ins_x + x
            blocks[position] = _write(blocks[position], rows, values.array)
    cols = df1.columns.tolist()
    for i in range(w - df1w):
        cols.append("C%d" % (i + 1 + df1w))
    if not blocks:
        return pd.DataFrame(index=range(h))
    res = pd.concat(blocks, axis=1)
    res.columns = cols
    return res.set_axis(range(h))


if __name__ == "__main__":
    data = [
        ['Alice', 25, 'New York'],
        ['Bob', 30, 'San Francisco'],
        ['Charlie', 35, 'Los Angeles'],
        ['David', 28, 'Chicago']
    ]

    # Create DataFrame
    df1 = pd.DataFrame(data, columns=['Name', 'Age', 'City'])
    df2 = pd.DataFrame(data, columns=['Name', 'Age', 'City'])
    print(df_combine(df1, df2, ins_x=2, ins_y=2))
