import numpy as np
import pandas as pd
##################
from pandastable_local.data_orig import TableModel as TM, _nullable_dtype


class TableModel(TM):
    def deleteColumns(self, cols=None):
        """Remove all cols or list provided"""

        df = self.df
        colnames = df.columns[cols]
        df.drop(colnames, axis=1, inplace=True)
        return

    def deleteCells(self, rows, cols, fills=np.nan):
        frame = self.df
        columns = list(cols) if isinstance(cols, tuple) else cols
        positions = np.atleast_1d(np.arange(frame.shape[1])[columns])
        updated = frame.iloc[:, positions].copy()
        if pd.api.types.is_scalar(fills) and pd.isna(fills):
            for col in range(len(positions)):
                dtype = updated.dtypes.iloc[col]
                nullable_dtype = _nullable_dtype(dtype)
                if nullable_dtype:
                    updated.isetitem(col, updated.iloc[:, col].astype(nullable_dtype))
        updated.iloc[rows, :] = fills
        for position, col in enumerate(positions):
            frame.isetitem(col, updated.iloc[:, position])
        return
