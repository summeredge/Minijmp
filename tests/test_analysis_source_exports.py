"""跨分析界面的来源标识导出回归：直接导出、表内导出及报告载体。"""
import importlib
from types import SimpleNamespace
from unittest.mock import Mock

import pandas as pd
import pytest

from stat_table import TableBlock, StatTable, export_excel
from test_regression_dialog import dispose


@pytest.mark.parametrize('module_name,fixture_name,maker,key', [
    ('regression_dialog','test_regression_dialog','make_dialog','observations'),
    ('pca_dialog','test_pca_dialog','make_pca','monitoring'),
    ('advanced_time_series_dialog','test_time_series_analysis_dialog','make_dialog','data'),
])
def test_all_export_paths_keep_source_labels(tk_root, monkeypatch, tmp_path, module_name, fixture_name, maker, key):
    module=importlib.import_module(module_name)
    dialog,app,source,_=getattr(importlib.import_module(fixture_name),maker)(tk_root,monkeypatch)
    frame=pd.DataFrame({'source_row':[1,2,3], 'source_index':[9007199254740993,'000001',None],
                        'statistic':[1.123456789012345,2.5,3.]})
    original=frame.copy(deep=True)
    try:
        dialog.show_table(key,frame)
        dialog.notebook.select(dialog.tabs[key])
        direct=tmp_path/'direct.xlsx'
        monkeypatch.setattr(module.filedialog,'asksaveasfilename',lambda **kw:str(direct))
        dialog.export()
        dialog.error.assert_not_called()
        actual=pd.read_excel(direct,dtype={'来源索引':str})
        assert actual['来源索引'].iloc[:2].tolist()==['9007199254740993','000001']
        assert pd.isna(actual['来源索引'].iloc[2])
        block=next(child for child in dialog.tabs[key].winfo_children() if isinstance(child,TableBlock))
        inner=tmp_path/'inner.xlsx'
        export_excel(block.table,inner)
        actual=pd.read_excel(inner,header=1,dtype={'来源索引':str})
        assert actual['来源索引'].iloc[:2].tolist()==['9007199254740993','000001']
        assert abs(actual[module.HEADERS.get('statistic','statistic')].iloc[0]-frame.statistic.iloc[0])<1e-15
        if module_name=='pca_dialog':
            dialog.model=SimpleNamespace(training=SimpleNamespace(notes=[]))
        else:
            dialog.result=SimpleNamespace(equation='Y=1',notes=[],tables={key:frame})
        app.print=Mock()
        dialog.report()
        carrier=next(call.args[0] for call in app.print.call_args_list if isinstance(call.args[0],StatTable))
        index=carrier.headers.index('来源索引')
        assert [row[index] for row in carrier.values[:2]]==['9007199254740993','000001']
        pd.testing.assert_frame_equal(frame,original)
    finally:
        dialog.close();dispose(app)
