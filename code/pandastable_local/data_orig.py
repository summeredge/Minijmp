#!/usr/bin/env python
"""
    Module implementing the Data class that manages data for
    it's associated PandasTable.

    Created Jan 2014
    Copyright (C) Damien Farrell

    This program is free software; you can redistribute it and/or
    modify it under the terms of the GNU General Public License
    as published by the Free Software Foundation; either version 2
    of the License, or (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program; if not, write to the Free Software
    Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
"""

from types import *
import operator
import os, string, types, copy
import pickle
from decimal import Decimal, InvalidOperation
import numpy as np
import pandas as pd
from . import util


def _nullable_dtype(dtype):
    if pd.api.types.is_extension_array_dtype(dtype):
        return None
    if pd.api.types.is_bool_dtype(dtype):
        return 'boolean'
    if pd.api.types.is_integer_dtype(dtype):
        dtype = np.dtype(dtype)
        return ('UInt' if dtype.kind == 'u' else 'Int') + str(dtype.itemsize * 8)
    return None


def _missing_cell_value(dtype):
    if (pd.api.types.is_datetime64_any_dtype(dtype)
            or pd.api.types.is_timedelta64_dtype(dtype)):
        return pd.NaT
    if (pd.api.types.is_extension_array_dtype(dtype)
            or pd.api.types.is_integer_dtype(dtype)
            or pd.api.types.is_bool_dtype(dtype)):
        return pd.NA
    return np.nan


def _is_missing_cell_value(value):
    if value is None or value is pd.NA or value is pd.NaT:
        return True
    return pd.api.types.is_scalar(value) and bool(pd.isna(value))


def _coerce_cell_value(value, dtype):
    if isinstance(value, str) and value == '':
        value = pd.NA
    if _is_missing_cell_value(value):
        return _missing_cell_value(dtype)

    if isinstance(dtype, pd.CategoricalDtype):
        if value not in dtype.categories:
            raise ValueError(f'“{value}”不属于该分类列的现有类别。')
        return value
    if pd.api.types.is_bool_dtype(dtype):
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in ('true', '1'):
                return True
            if normalized in ('false', '0'):
                return False
            raise ValueError(f'“{value}”不是有效的布尔值。')
        if isinstance(value, (bool, np.bool_)):
            return bool(value)
        if isinstance(value, (int, np.integer)) and value in (0, 1):
            return bool(value)
        raise ValueError(f'“{value}”不是有效的布尔值。')
    if pd.api.types.is_integer_dtype(dtype):
        if isinstance(value, (bool, np.bool_)):
            raise ValueError('布尔值不能写入整数列。')
        try:
            number = Decimal(str(value).strip())
        except (InvalidOperation, ValueError) as error:
            raise ValueError(f'“{value}”不是有效的整数。') from error
        if not number.is_finite() or number != number.to_integral_value():
            raise ValueError(f'“{value}”不是有效的整数。')
        number = int(number)
        limits = np.iinfo(getattr(dtype, 'numpy_dtype', dtype))
        if number < limits.min or number > limits.max:
            raise ValueError(f'“{value}”超出当前整数列可表示范围。')
        return number
    if pd.api.types.is_float_dtype(dtype):
        if isinstance(value, (bool, np.bool_)):
            raise ValueError('布尔值不能写入数值列。')
        if isinstance(value, (str, Decimal, int, np.integer)):
            try:
                number = Decimal(str(value).strip())
            except (InvalidOperation, ValueError) as error:
                raise ValueError(f'“{value}”不是有效的数值。') from error
            if number.is_nan():
                return _missing_cell_value(dtype)
            converted = float(number)
            if number.is_finite() and (
                    not np.isfinite(converted) or Decimal(str(converted)) != number):
                raise ValueError(f'“{value}”超出浮点列可保留的精度。')
            return converted
        return float(value)
    if pd.api.types.is_datetime64_any_dtype(dtype):
        try:
            value = pd.Timestamp(value)
            timezone = getattr(dtype, 'tz', None)
            if timezone is None and value.tz is not None:
                raise ValueError('时区时间不能写入无时区日期列。')
            if timezone is not None:
                value = value.tz_localize(timezone) if value.tz is None else value.tz_convert(timezone)
            unit = getattr(dtype, 'unit', None)
            if unit:
                value = value.as_unit(unit, round_ok=False)
        except (TypeError, ValueError, OverflowError) as error:
            raise ValueError(f'“{value}”不能在不损失精度的情况下写入日期时间列。') from error
        return value
    if pd.api.types.is_timedelta64_dtype(dtype):
        try:
            return pd.to_timedelta(value)
        except (TypeError, ValueError, OverflowError) as error:
            raise ValueError(f'“{value}”不是有效的时间间隔。') from error
    if pd.api.types.is_string_dtype(dtype) and not pd.api.types.is_object_dtype(dtype):
        return str(value)
    return value


def _prepare_cell_updates(frame, updates):
    """Build typed positional column replacements without mutating the frame."""
    prepared = {}
    for col, (rows, values) in updates.items():
        rows = [rows] if pd.api.types.is_scalar(rows) else list(rows)
        values = ([values] * len(rows) if pd.api.types.is_scalar(values)
                  else list(values))
        if len(rows) != len(values):
            raise ValueError('单元格更新行数与数据数量不一致。')
        if not rows:
            continue
        series = frame.iloc[:, col].copy()
        dtype = series.dtype
        values = [_coerce_cell_value(value, dtype) for value in values]
        nullable = _nullable_dtype(dtype)
        if nullable and any(_is_missing_cell_value(value) for value in values):
            series = series.astype(nullable)
        try:
            for row, value in zip(rows, values):
                series.iloc[row] = value
        except (TypeError, ValueError, OverflowError) as error:
            raise ValueError(f'单元格数据无法安全写入：{error}') from error
        prepared[col] = series
    return prepared


def _commit_cell_updates(frame, prepared):
    for col, series in prepared.items():
        frame.isetitem(col, series)


class TableModel(object):
    """A data model for the Table class that uses pandas

    Args:
        dataframe: pandas dataframe
        rows: number of rows if empty table
        columns: number of columns if empty table
    """

    keywords = {'colors':'colors'}

    def __init__(self, dataframe=None, rows=20, columns=5):
        """Constructor for table model. """
        self.initialiseFields()
        self.setup(dataframe, rows, columns)
        return

    def setup(self, dataframe, rows=20, columns=5):
        """Create table model"""

        if not dataframe is None:
            self.df = dataframe
        else:
            colnames = [string.ascii_lowercase[i] if i < 26 else "col%d" % (i + 1)
                        for i in range(columns)]
            self.df = pd.DataFrame(index=range(rows),columns=colnames)
            #self.df = self.getSampleData()
        #self.reclist = self.df.index # not needed now?
        return

    @classmethod
    def getSampleData(self, rows=400, cols=5, n=2):
        """Generate sample data
        Args:
            rows: no. of rows
            cols: columns
            n: length of column names
        """

        import random
        s = string.ascii_lowercase
        def genstr(n=2):
            return ''.join(random.choice(s) for i in range(n))
        maxrows = 5e6
        if rows>maxrows:
            rows=maxrows
        if cols>1e5:
            cols=int(1e5)
        n=2
        if cols>100: n=3
        colnames = [genstr(n) for i in range(cols)]
        coldata = [np.random.normal(x,1,rows) for x in np.random.normal(5,3,cols)]
        n = np.array(coldata).T
        df = pd.DataFrame(n, columns=colnames)
        col1 = colnames[0]
        col2 = colnames[1]
        df[col2] = df[col1]*np.random.normal(.8, .2, len(df))
        df = np.round(df, 3)
        cats = ['low','medium','high','very high']
        df['label'] = pd.cut(df[col1], bins=4, labels=cats).astype(str)
        #df['label'] = df.label.cat.as_ordered()
        #don't add date if rows too large
        if rows<2e6:
            df['date'] = pd.date_range('1/1/2016', periods=rows, freq='H')
        return df

    @classmethod
    def getIrisData(self):
        """Get iris dataset"""

        path = os.path.dirname(__file__)
        cols = ['sepal length','sepal width','petal length','petal width','class']
        df = pd.read_csv(os.path.join(path,'datasets','iris.data'),names=cols)
        return df

    @classmethod
    def getStackedData(self):
        """Get a dataframe to pivot test"""

        import pandas.util.testing as tm; tm.N = 4
        frame = tm.makeTimeDataFrame()
        N, K = frame.shape
        data = {'value' : frame.values.ravel('F'),
                'variable' : np.asarray(frame.columns).repeat(N),
                'date' : np.tile(np.asarray(frame.index), K)}
        return pd.DataFrame(data, columns=['date', 'variable', 'value'])

    def initialiseFields(self):
        """Create meta data fields"""
        self.meta = {}
        #self.columnwidths = {} #used to store col widths
        return

    def save(self, filename):
        """Save dataframe"""

        ftype = os.path.splitext(filename)[1].lower()
        if ftype not in ('.pickle', '.xls', '.xlsx', '.csv'):
            raise ValueError('Unsupported file extension: %s' % ftype)
        with util.atomic_output(filename) as temporary:
            if ftype == '.pickle':
                self.df.to_pickle(temporary)
            elif ftype in ('.xls', '.xlsx'):
                self.df.to_excel(temporary)
            else:
                self.df.to_csv(temporary)
        return

    def load(self, filename, filetype=None):
        """Load file, if no filetype given assume it's pickle format"""

        if filetype == '.mpk':
            self.df = pd.read_msgpack(filename)
        else:
            self.df = pd.read_pickle(filename)
            #print (len(self.df))
        return

    def getlongestEntry(self, colindex, n=500):
        """Get the longest string in the column for determining width. Just uses the first
         n rows for speed"""

        df = self.df
        col = df.columns[colindex]
        try:
            if df.dtypes[col] == 'float64':
                c = df[col][:n].round(3)
            else:
                c = df[col][:n]
        except:
            return 1
        longest = c.astype('object').astype('str').str.len().max()
        if np.isnan(longest):
            return 1
        return int(longest)

    def getRecordAtRow(self, rowindex):
        """Get the entire record at the specifed row"""

        record = self.df.iloc[rowindex]
        return record

    def moveColumn(self, oldindex, newindex):
        """Changes the order of columns"""

        df = self.df
        cols = list(df.columns)
        name = cols[oldindex]
        del cols[oldindex]
        cols.insert(newindex, name)
        self.df = df[cols]
        return

    def autoAddRows(self, num):
        """Add n rows to end of dataframe. Will create rows with index starting
           from highest previous row count"""

        df = self.df
        if len(df) == 0:
            self.df = df.reindex(range(num))
            return
        try:
            ind = self.df.index.max()+1
        except:
            ind = len(df)+1
        new = pd.DataFrame(np.nan, index=range(ind,ind+num), columns=df.columns)
        self.df = pd.concat([df, new])
        return

    def insertRow(self, row):
        """Inserts a row at the required index by append/concat"""

        df = self.df
        a, b = df[:row], df[row:]
        idx = len(df)+1
        new = pd.DataFrame(np.nan,index=[idx],columns=df.columns)
        a = pd.concat([a,new])
        self.df = pd.concat([a,b])
        return idx

    def deleteRow(self, row, unique=True):
        """Delete a row"""

        self.deleteRows([row], unique)
        return

    def deleteRows(self, rowlist=None, unique=True):
        """Delete multiple or all rows"""

        df = self.df
        if unique == True:
            rows = list(set(range(len(df))) - set(rowlist))
            self.df = df.iloc[rows]
        else:
            df.drop(df.index[rowlist],inplace=True)
        return

    def addColumn(self, colname=None, dtype=None, data=None):
        """Add a column"""

        if data is None:
            data = pd.Series(dtype=dtype)
        self.df[colname] = data
        return

    def deleteColumn(self, colindex):
        """delete a column"""

        df = self.df
        colname = df.columns[colindex]
        df.drop([colname], axis=1, inplace=True)
        return

    def deleteColumns(self, cols=None):
        """Remove all cols or list provided"""

        df = self.df
        colnames = df.columns[cols]
        df.drop(colnames, axis=1, inplace=True)
        return

    def deleteCells(self, rows, cols):
        self.df.iloc[rows,cols] = np.nan
        return

    def resetIndex(self, drop=False):
        """Reset index behaviour"""

        df = self.df
        df.reset_index(drop=drop,inplace=True)
        return

    def setindex(self, colindex):
        """Index setting behaviour"""

        df = self.df
        colnames = list(df.columns[colindex])
        indnames = df.index.names
        if indnames[0] != None:
            df.reset_index(inplace=True)
        df.set_index(colnames, inplace=True)
        return

    def copyIndex(self):
        """Copy index to a column"""

        df = self.df
        name = df.index.name
        if name == None: name='index'
        df[name] = df.index#.astype('object')
        return

    def groupby(self, cols):
        """Group by cols"""

        df = self.df
        colnames = df.columns[cols]
        grps = df.groupby(colnames, observed=False)
        return grps

    def getColumnType(self, columnIndex):
        """Get the column type"""
        coltype = self.df.dtypes.iloc[columnIndex]
        return coltype

    def getColumnCount(self):
         """Returns the number of columns in the data model"""
         return len(self.df.columns)

    def getColumnName(self, columnIndex):
        """Returns the name of the given column by columnIndex"""
        try:
            return str(self.df.columns[columnIndex])
        except:
            return self.df.columns[columnIndex].encode('ascii', 'ignore')

    def getRowCount(self):
         """Returns the number of rows in the table model."""
         return len(self.df)

    def getValueAt(self, row, col):
         """Returns the cell value at location specified
             by columnIndex and rowIndex."""

         df = self.df
         value = self.df.iloc[row,col]
         if type(value) is float and np.isnan(value):
             return ''
         return value

    def setValueAt(self, value, row, col, df=None):
        """Change dataframe according to row/col numbers. You can
        also pass an arbitrary dataframe here."""

        if df is None:
            df = self.df
        target_row = row
        target_col = col
        if df is not self.df:
            if not df.index.is_unique:
                raise ValueError('Cannot edit filtered data with a non-unique source index')
            if not df.columns.is_unique:
                raise ValueError('Cannot edit filtered data with non-unique source columns')
            target_row = df.index.get_loc(self.df.index[row])
            target_col = df.columns.get_loc(self.df.columns[col])
        updated = _prepare_cell_updates(
            df, {target_col: ([target_row], [value])})
        source_updated = (_prepare_cell_updates(
            self.df, {col: ([row], [value])}) if df is not self.df else None)
        _commit_cell_updates(df, updated)
        if source_updated is not None:
            _commit_cell_updates(self.df, source_updated)
        return

    def transpose(self):
        """Transpose dataframe"""

        df = self.df
        rows = df.index
        df = df.transpose()
        df.reset_index()
        if util.check_multiindex(df.columns) != 1:
            try:
                df.columns = df.columns.astype(str)
            except:
                pass
        self.df = df.infer_objects()
        #self.columnwidths = {}
        return

    def query(self):

        return

    def filterby(self):
        import filtering
        funcs = filtering.operatornames
        floatops = ['=','>','<']
        func = funcs[op]

        return

    def __repr__(self):
        return 'Table Model with %s rows' %len(self.df)
