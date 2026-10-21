import pandas as pd
import numpy as np


def df_combine(df1, df2, ins_x=0, ins_y=0):
    df1h, df1w = df1.shape
    df2h, df2w = df2.shape
    h = max(df1h, ins_y + df2h)
    w = max(df1w, ins_x + df2w)
    # Keep NumPy scalar types so rebuilding columns preserves narrow dtypes too.
    res = np.full((h, w), np.nan, dtype=object)
    for x, (_, values) in enumerate(df1.items()):
        res[:df1h, x] = list(values.array)
    if df2h:
        for x, (_, values) in enumerate(df2.items()):
            res[range(ins_y, ins_y + df2h), ins_x + x] = list(values.array)
    cols = df1.columns.tolist()
    for i in range(w - df1w):
        cols.append("C%d" % (i + 1 + df1w))
    return pd.DataFrame(res.tolist(), columns=cols, index=range(h))


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
