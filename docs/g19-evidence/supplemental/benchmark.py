"""G15 isolated sequential benchmarks; only output directory is writable."""
import argparse
import ctypes
from ctypes import wintypes as wt
import gc
import json
import os
from pathlib import Path
import subprocess
import sys
import time

OUT = Path(__file__).resolve().parent
ROOT = Path(r'C:\Users\shaoy\Documents\Minijmp')

class Counters(ctypes.Structure):
    _fields_ = [('cb', wt.DWORD), ('PageFaultCount', wt.DWORD)] + [(n, ctypes.c_size_t) for n in (
        'PeakWorkingSetSize', 'WorkingSetSize', 'QuotaPeakPagedPoolUsage', 'QuotaPagedPoolUsage',
        'QuotaPeakNonPagedPoolUsage', 'QuotaNonPagedPoolUsage', 'PagefileUsage', 'PeakPagefileUsage')]

def memory():
    c = Counters(); c.cb = ctypes.sizeof(c)
    kernel = ctypes.windll.kernel32
    kernel.GetCurrentProcess.restype = wt.HANDLE
    fn = ctypes.windll.psapi.GetProcessMemoryInfo
    fn.argtypes = [wt.HANDLE, ctypes.POINTER(Counters), wt.DWORD]
    if not fn(kernel.GetCurrentProcess(), ctypes.byref(c), c.cb):
        raise ctypes.WinError()
    return {n: getattr(c, n)/1024**2 for n in ('WorkingSetSize','PeakWorkingSetSize','PagefileUsage')}

def job_limit(process, mib):
    class Basic(ctypes.Structure):
        _fields_ = [('ProcessTime',ctypes.c_int64),('JobTime',ctypes.c_int64),('Flags',wt.DWORD),
                    ('MinWS',ctypes.c_size_t),('MaxWS',ctypes.c_size_t),('Active',wt.DWORD),
                    ('Affinity',ctypes.c_size_t),('Priority',wt.DWORD),('Scheduling',wt.DWORD)]
    class IO(ctypes.Structure):
        _fields_ = [(n,ctypes.c_uint64) for n in ('ReadOp','WriteOp','OtherOp','ReadBytes','WriteBytes','OtherBytes')]
    class Extended(ctypes.Structure):
        _fields_ = [('Basic',Basic),('IO',IO),('ProcessMemory',ctypes.c_size_t),
                    ('JobMemory',ctypes.c_size_t),('PeakProcess',ctypes.c_size_t),('PeakJob',ctypes.c_size_t)]
    k = ctypes.windll.kernel32
    k.CreateJobObjectW.argtypes = [ctypes.c_void_p, wt.LPCWSTR]; k.CreateJobObjectW.restype = wt.HANDLE
    k.SetInformationJobObject.argtypes = [wt.HANDLE,ctypes.c_int,ctypes.c_void_p,wt.DWORD]
    k.AssignProcessToJobObject.argtypes = [wt.HANDLE,wt.HANDLE]
    k.CloseHandle.argtypes = [wt.HANDLE]
    handle = k.CreateJobObjectW(None,None)
    info = Extended(); info.Basic.Flags = 0x2000 | 0x200; info.JobMemory = mib*1024**2
    if not handle or not k.SetInformationJobObject(handle,9,ctypes.byref(info),ctypes.sizeof(info)) or not k.AssignProcessToJobObject(handle,wt.HANDLE(process._handle)):
        process.kill()
        raise ctypes.WinError()
    return handle

def worker(s):
    sys.stdout.reconfigure(encoding='utf-8');sys.stderr.reconfigure(encoding='utf-8')
    sys.path.insert(0,str(ROOT/'code'))
    import numpy as np
    import pandas as pd
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    import cProfile
    import pstats
    import io
    rng = np.random.default_rng(20261021)
    n = s.get('n',1000); p = s.get('p',5)
    name = s['name']; sid = s['id']
    rows = []
    state = {'scenario':s, 'pid':os.getpid(), 'rows':rows, 'stage':'prepare', 'memory_scope':'cumulative_process_peak_including_imports_warmup_inputs'}
    target = OUT/'raw'/f'{sid}.json'
    def save():
        tmp = target.with_suffix('.partial'); tmp.write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding='utf-8'); tmp.replace(target)
    save()
    if name in ('report_gui','text_gui','time_series_tk','time_series_dialog','table_gui','vendor_plot'):
        import tkinter as tk
        def callback_error(root,exc,value,tb):
            state.setdefault('callback_errors',[]).append(f'{exc.__name__}: {value}');save()
        tk.Tk.report_callback_exception=callback_error
    def measure(phase,fn,rep):
        state['stage']=phase; state['repeat']=rep; save()
        gc.collect(); before=memory(); start=time.perf_counter(); cpu=time.process_time()
        result=fn()
        elapsed=time.perf_counter()-start; used=time.process_time()-cpu; after=memory()
        if state.get('callback_errors'):raise RuntimeError(state['callback_errors'])
        rows.append({'phase':phase,'repeat':rep,'wall_seconds':elapsed,'cpu_seconds':used,
                     'rss_before_mib':before['WorkingSetSize'],'rss_after_mib':after['WorkingSetSize'],
                     'process_peak_rss_mib':after['PeakWorkingSetSize'],'private_commit_mib':after['PagefileUsage'],
                     'status':'ok','warmup':rep==0})
        save(); return result
    def null(*a,**k): pass
    data = rng.normal(10,1,n).tolist()
    fn = None
    if name=='linear_fit':
        from linear_fit import linear_fit
        x=(np.arange(n)%max(5,n//5)).astype(float).tolist(); y=(2*np.array(x)+rng.normal(size=n)).tolist()
        fn=lambda:linear_fit(x,y,print_out=False)
    elif name=='df_combine':
        from df_combine import df_combine
        a=pd.DataFrame(rng.normal(size=(n,p))); b=a.iloc[:max(1,n//10)].copy()
        fn=lambda:df_combine(a,b,ins_x=0,ins_y=n//2)
    elif name=='binomial':
        from binomial import binomial
        fn=lambda:binomial(n,.5,x=int(n*s.get('event_fraction',.5)))
    elif name in ('p_blaker','p_sterne','p_likelihood_ratio','prop_test_1sample'):
        import proportion_test as mod
        if name=='prop_test_1sample': fn=lambda:mod.prop_test_1sample(events=int(n*s.get('event_fraction',.5)),N=n,p0=.5)
        else: fn=lambda:getattr(mod,name)(n,.5,n//2)
    elif name=='anova_pairs':
        from one_way_ANOVA import JMP_ANOVA_t_test
        groups=[data[i::p] for i in range(p)];labels=[f'G{i}' for i in range(p)]
        assert len(groups)==len(labels) and sum(map(len,groups))==n
        fn=lambda:JMP_ANOVA_t_test(groups,labels,print_out=False)
    elif name in ('describe','cpk','fit_norm','hoeffding','x_mR'):
        if name=='describe':
            from describe import describe
            fn=lambda:describe(data,print_out=False)
        elif name=='cpk':
            from cpk import cpk
            fn=lambda:cpk(data,10,14,6,print_out=False)
        elif name=='fit_norm':
            from dist_fit import fit_norm
            fn=lambda:fit_norm(data,print_out=False)
        elif name=='x_mR':
            from control_chart import x_mR
            fn=lambda:x_mR(data,2)
        else:
            from nonpara_cor import hoeffding
            other=rng.normal(size=n).tolist()
            fn=lambda:hoeffding(data,other)
    elif name=='spc_report':
        from control_chart import _print_spc_report
        charts=[('Individual',data,7.,10.,13.)]
        fn=lambda:_print_spc_report('I',charts,1,'N',None,[],null)
    elif name in ('matrix_spearman','matrix_kendall','matrix_hoeffding'):
        from fit_dialog import print_multi_col_tables
        import nonpara_cor
        values=rng.normal(size=(p,n)).tolist(); labels=[f'V{i}' for i in range(p)]
        cor=getattr(nonpara_cor,name.split('_')[1])
        fn=lambda:print_multi_col_tables(values,labels,cor,print_port=null,name=name)
    elif name in ('multi_fit','multi_fit_orig'):
        import linear_plot
        values=rng.normal(size=(p,n)).tolist(); labels=[f'V{i}' for i in range(p)]
        for rep in range(4):
            if name=='multi_fit':
                fig=Figure(figsize=(8,7),dpi=100,layout='constrained'); FigureCanvasAgg(fig)
                kw={'ax':fig.add_subplot(111),'fig':fig}
            else: kw={}
            def build():
                result=getattr(linear_plot,name)(values,labels,print_out=False,**kw)
                if name=='multi_fit_orig': return plt.gcf(),result
                return fig,result
            built=measure('matrix_and_artists',build,rep); realfig=built[0]
            state['artist_axes']=len(realfig.axes)+sum(len(a.child_axes) for a in realfig.axes)
            measure('agg_first_draw',realfig.canvas.draw,rep)
            measure('agg_redraw',realfig.canvas.draw,rep)
            plt.close(realfig); realfig.clear()
        if s.get('profile'):
            state['stage']='profile';save()
            prof=cProfile.Profile();prof.enable()
            getattr(linear_plot,name)(values,labels,print_out=False)
            prof.disable();plt.close('all')
            stats=pstats.Stats(prof)
            counts=[v[1] for k,v in stats.stats.items() if k[2]=='pearson_correlation' and k[0].endswith('utilities.py')]
            assert counts==[p*p+p*(p-1)//2],counts
            state['profile_pearson_calls']=counts[0]
            prof.dump_stats(OUT/'profiles'/f'{sid}.prof')
            text=io.StringIO();pstats.Stats(prof,stream=text).strip_dirs().sort_stats('cumulative').print_stats(40)
            (OUT/'profiles'/f'{sid}.txt').write_text(text.getvalue(),encoding='utf-8')
    elif name in ('stat_table','exports','report_gui'):
        from stat_table import StatTable,export_excel,export_png
        headers=['Sample']+[f'V{i}' for i in range(1,p)]
        values=[[f'row{i}']+[i+c/7 for c in range(1,p)] for i in range(n)]
        if name=='stat_table': fn=lambda:StatTable(title='G15',headers=headers,values=values)
        else:
            table=StatTable(title='G15',headers=headers,values=values)
            if name=='exports':
                for rep in range(4):
                    measure('export_excel',lambda:export_excel(table,OUT/'exports'/f'{sid}.xlsx'),rep)
                    measure('txt_write',lambda:(OUT/'exports'/f'{sid}.txt').write_text(str(table),encoding='utf-8'),rep)
            else:
                import tkinter as tk
                from types import SimpleNamespace
                from txt_output import txt_viewer
                from MiniJMP import Minijmp
                root=tk.Tk(); root.withdraw()
                viewer=txt_viewer(SimpleNamespace(tOut=None)); viewer.main.update()
                app=SimpleNamespace(table=viewer.table,tOut=viewer)
                tables=[table] if s.get('count',1)==1 else [StatTable(title=f'G15 {i+1}',headers=headers,values=values) for i in range(s['count'])]
                for rep in range(4):
                    viewer.clear(); viewer.main.update()
                    def present():
                        for current in tables: Minijmp.print(app,current)
                        viewer.main.update()
                    measure('tk_print_to_updated',present,rep)
                    block=viewer.table_blocks[-1]
                    state['paged']=block.paged
                    if block.paged:
                        def page(): block.show_page(block.page_count); viewer.main.update()
                        measure('tk_last_page_to_updated',page,rep)
                        assert len(block.tree.get_children()) <= block.page_size
                        assert block.tree.item(block.tree.get_children()[-1],'values')[-1]==table.display[-1][-1]
                    measure('gui_txt_save',lambda:viewer.save(OUT/'exports'/f'{sid}.txt'),rep)
                    assert (OUT/'exports'/f'{sid}.txt').read_text(encoding='utf-8')==''.join(str(t)+'\n' for t in tables)
                    measure('tk_clear_to_updated',lambda:(viewer.clear(),viewer.main.update()),rep)
                    assert not viewer.table_blocks
                viewer.close(); root.destroy()
    elif name=='text_gui':
        import tkinter as tk
        from types import SimpleNamespace
        from txt_output import txt_viewer
        root=tk.Tk(); root.withdraw(); viewer=txt_viewer(SimpleNamespace(tOut=None)); viewer.main.update()
        chunks=['普通结果 %d: 1.23456\n'%i for i in range(n)]
        for rep in range(4):
            viewer.clear(); viewer.main.update()
            def text():
                for chunk in chunks: viewer.add_txt(chunk); viewer.to_end(defer=True)
                viewer.main.update()
            measure('tk_add_txt_to_updated',text,rep)
            assert viewer.T.get('1.0','end-1c')==''.join(chunks)
        viewer.close(); root.destroy()
    elif name in ('time_series','time_series_tk'):
        from time_series import prepare_time_series,time_series_plot,AXIS_MODES
        df=pd.DataFrame(rng.normal(size=(n,p)),columns=[f'V{i}' for i in range(p)])
        df['Time']=pd.date_range('2025-01-01',periods=n,freq='s')[::-1]
        cols=list(df.columns[:-1]); assignments={c:i%3+1 for i,c in enumerate(cols)}
        if name=='time_series_tk':
            import tkinter as tk
            from plots import plot_viewer
            from types import SimpleNamespace
            root=tk.Tk();root.withdraw(); viewer=plot_viewer(SimpleNamespace(pf=None)); viewer.main.update()
        for rep in range(4):
            if name=='time_series':
                measure('data_prepare',lambda:prepare_time_series(df,cols,'Time'),rep)
                fig=Figure(figsize=(9,6),dpi=100); FigureCanvasAgg(fig)
                measure('plot_build_including_prepare',lambda:time_series_plot(fig,df,cols,'Time',assignments,AXIS_MODES[2]),rep)
                measure('agg_first_draw',fig.canvas.draw,rep); measure('agg_redraw',fig.canvas.draw,rep)
                fig.clear()
            else:
                def present():
                    time_series_plot(viewer.fig,df,cols,'Time',assignments,AXIS_MODES[2])
                    viewer.canvas.draw(); viewer.main.update()
                measure('tk_plot_to_updated',present,rep)
                measure('tk_redraw_to_updated',lambda:(viewer.canvas.draw(),viewer.main.update()),rep)
        if name=='time_series_tk': viewer.close();root.destroy()
    elif name=='table_gui':
        import tkinter as tk
        from modified_table import MTable as Table
        state['table_mro']=[f'{c.__module__}.{c.__name__}' for c in Table.__mro__]
        df=pd.DataFrame(rng.normal(size=(n,p)))
        root=tk.Tk();root.geometry('1000x650'); frame=tk.Frame(root);frame.pack(fill='both',expand=True)
        # config.load_options is read-only with the existing user_config directory.
        for rep in range(4):
            def present():
                table=Table(frame,dataframe=df,showtoolbar=False,showstatusbar=True)
                table.show();root.update_idletasks();table.redraw();root.update();return table
            table=measure('tk_table_first_to_updated',present,rep)
            assert table.visiblerows and table.visiblecols
            measure('tk_table_redraw_to_updated',lambda:(table.redrawVisible(),root.update()),rep)
            measure('tk_table_full_redraw_to_updated',lambda:(table.redraw(),root.update()),rep)
            measure('tk_table_scroll_to_updated',lambda:(table.yview_moveto(.9),table.redrawVisible(),root.update()),rep)
            state['canvas_items']=len(table.find_all()); table.destroy()
            for child in frame.winfo_children():child.destroy()
            root.update()
        root.destroy()
    elif name=='pi_decode':
        import pi_reader
        # Same offline protocol fixture shape used by test_pi_reader.py, generated locally.
        stamps=pd.date_range('2025-01-01',periods=n,freq='s').strftime('%Y-%m-%d %H:%M:%S')
        payload={'columns':['Timestamp']+[f'TAG_{i}' for i in range(p)],
                 'data':[[t]+[float(i) for i in range(p)] for t in stamps]}
        text=json.dumps(payload)
        for rep in range(4):
            decoded=measure('pi_json_decode',lambda:json.loads(text),rep)
            frame=measure('pi_frame_validate',lambda:pi_reader._read_reader_json(decoded),rep)
            assert frame.shape==(n,p) and frame.index.name=='Timestamp'
    elif name=='csv_import':
        from pandastable_local.csv_import import detect_csv,read_csv
        path=OUT/'exports'/f'{sid}.csv'
        pd.DataFrame(rng.normal(size=(n,p)),columns=[f'V{i}' for i in range(p)]).to_csv(path,index=False)
        for rep in range(4):
            opts=measure('csv_detect',lambda:detect_csv(path),rep)
            frame=measure('csv_read',lambda:read_csv(path,opts['encoding'],opts['delimiter'],opts['header']),rep)
            assert frame.shape==(n,p)
    elif name=='vendor_plot':
        import tkinter as tk
        from modified_table import MTable
        from pandastable_local.plotting import PlotViewer
        frame_data=pd.DataFrame(rng.normal(size=(n,p)),columns=[f'V{i}' for i in range(p)])
        root=tk.Tk();root.geometry('1000x650');frame=tk.Frame(root);frame.pack(fill='both',expand=True)
        table=MTable(frame,dataframe=frame_data,showtoolbar=False,showstatusbar=True)
        table.show();root.update()
        for rep in range(4):
            viewer=measure('tk_vendor_viewer_create',lambda:PlotViewer(table=table,parent=None,showoptions=True),rep)
            root.update()
            prepared=frame_data.copy()
            measure('tk_vendor_replot_to_updated',lambda:(viewer.replot(data=prepared),root.update()),rep)
            assert len(viewer.ax.lines)==p and not state.get('callback_errors')
            measure('tk_vendor_plotCurrent_to_updated',lambda:(viewer.plotCurrent(),root.update()),rep)
            assert len(viewer.ax.lines)==p
            viewer._initFigure()
            measure('tk_vendor_plot2D_to_updated',lambda:(viewer.plot2D(redraw=True),root.update()),rep)
            assert len(viewer.ax.lines)==p
            viewer.close()
        root.destroy()
    elif name=='compare_dist':
        from dist_fit import compare_dist
        positive=rng.lognormal(1,.25,n).tolist()
        def compare():
            result=compare_dist(positive,print_out=False)
            assert len(result)==6, 'A failed fit is not a completed six-model benchmark'
            return result
        fn=compare
    elif name=='calculate_d3':
        from utilities import calculate_d3
        assert calculate_d3.cache_info().currsize==0
        measure('cold_integral',lambda:calculate_d3(n),1)
        for rep in range(1,4):measure('warm_cached_integral',lambda:calculate_d3(n),rep)
        state['cache_info']=str(calculate_d3.cache_info())
    elif name=='multi_var':
        from chi_sq import multi_pop_var_test
        groups=[rng.normal(i,.8+i*.1,n).tolist() for i in range(3)]
        fn=lambda:multi_pop_var_test(groups,['A','B','C'],print_out=False)
    elif name=='number_2Dlist':
        from utilities import number_2Dlist
        frame=pd.DataFrame(rng.normal(size=(n,p)),columns=[f'V{i}' for i in range(p)])
        fn=lambda:number_2Dlist(df=frame,cols=list(frame),print_out=False)
    elif name in ('ti_norm','two_way','grr','xbar_s_pooled','find_text'):
        if name=='ti_norm':
            from ti import ti_norm
            fn=lambda:ti_norm(data,print_out=False)
        elif name=='two_way':
            from two_way_anova import two_way_anova
            a=(np.arange(n)%p).astype(str).tolist();b=((np.arange(n)//p)%3).astype(str).tolist()
            fn=lambda:two_way_anova(data,factor_listA=a,factor_listB=b,print_out=False)
        elif name=='grr':
            from GRR import grr_master
            parts=(np.arange(n)%p).astype(str).tolist();ops=((np.arange(n)//p)%3).astype(str).tolist()
            fn=lambda:grr_master(y=data,part=parts,op=ops,print_out=False)
        elif name=='xbar_s_pooled':
            from control_chart import xBar_S
            groups=np.array(data).reshape(-1,p).tolist()
            fn=lambda:xBar_S(groups,pooled=True)
        else:
            from dialog import findRepDialog
            from types import SimpleNamespace
            df=pd.DataFrame(rng.integers(0,100,size=(n,p)))
            obj=SimpleNamespace(table=SimpleNamespace(model=SimpleNamespace(df=df)),
                searchvar=SimpleNamespace(get=lambda:'42'),casevar=SimpleNamespace(get=lambda:True),clear=null)
            fn=lambda:findRepDialog.find(obj)
    elif name=='time_series_dialog':
        import tkinter as tk
        from types import SimpleNamespace
        from MiniJMP import Minijmp
        from modified_app import Minijmp_pre
        from time_series_dialog import TimeSeriesDialog
        from time_series import AXIS_MODES
        df=pd.DataFrame(rng.normal(size=(n,3)),columns=['A','B','C'])
        df['Time']=pd.date_range('2025-01-01',periods=n,freq='s')[::-1]
        root=tk.Tk();root.withdraw();parent=tk.Frame(root);parent.pf=None
        app=SimpleNamespace(table=parent,print=null,dialog_help_msg=lambda **kw:Minijmp_pre.dialog_help_msg(None,**kw),addPlot=null)
        app.showPlotViewer=lambda **kw:Minijmp.showPlotViewer(app,**kw)
        dlg=TimeSeriesDialog(parent,df=df,app=app,title='G15 时间序列')
        dlg.ylist.selection_set(0,2);dlg.mode.set(AXIS_MODES[2]);dlg.update_variables()
        dlg.assignments={'A':1,'B':2,'C':3};dlg.no_preview=False;dlg.main.update()
        for rep in range(4):
            def show():dlg.apply();parent.pf.main.update()
            measure('tk_dialog_apply_to_updated',show,rep)
            assert len(parent.pf.fig.axes)==3
        parent.pf.close();dlg.main.destroy();parent.destroy();root.destroy()
    else: raise ValueError(name)
    if fn:
        for rep in range(4):
            result=measure('compute' if name not in ('spc_report','stat_table') else 'report_build',fn,rep)
            if name=='binomial': assert len(result['pmf'])==n+1
            if name=='df_combine': assert result.shape==(n,p)
            del result
        if s.get('profile') and n <= 10000:
            state['stage']='profile';save()
            prof=cProfile.Profile();prof.enable();result=fn();prof.disable();del result
            prof.dump_stats(OUT/'profiles'/f'{sid}.prof')
            text=io.StringIO();pstats.Stats(prof,stream=text).strip_dirs().sort_stats('cumulative').print_stats(40)
            (OUT/'profiles'/f'{sid}.txt').write_text(text.getvalue(),encoding='utf-8')
    if state.get('callback_errors'):raise RuntimeError(state['callback_errors'])
    state['stage']='complete';state['status']='ok';save()

def main():
    global ROOT
    parser=argparse.ArgumentParser();parser.add_argument('--worker');parser.add_argument('--filter',default='');parser.add_argument('--resume',action='store_true')
    parser.add_argument('--scenarios',type=Path,default=OUT/'scenarios.json')
    parser.add_argument('--repo',type=Path,default=ROOT)
    args=parser.parse_args()
    ROOT=args.repo.resolve()
    if args.worker:
        worker(json.loads(args.worker));return
    for folder in ('raw','logs','exports','profiles','mplconfig'): (OUT/folder).mkdir(exist_ok=True)
    scenarios=json.loads(args.scenarios.read_text())
    env=os.environ.copy();env.update(PYTHONDONTWRITEBYTECODE='1',MPLCONFIGDIR=str(OUT/'mplconfig'),PYTHONHASHSEED='0',OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1',NUMEXPR_NUM_THREADS='1')
    for s in scenarios:
        if args.filter and args.filter not in (s['id'],s['name']):continue
        target=OUT/'raw'/f"{s['id']}.json"
        if args.resume and target.exists():continue
        started=time.perf_counter()
        with (OUT/'logs'/f"{s['id']}.log").open('w',encoding='utf-8') as log:
            process=subprocess.Popen([sys.executable,'-B',str(Path(__file__).resolve()),'--repo',str(ROOT),'--worker',json.dumps(s)],cwd=OUT,env=env,stdout=log,stderr=log)
            handle=job_limit(process,1536)
            try:
                process.wait(timeout=s.get('timeout',60));status='ok' if process.returncode==0 else 'error'
            except subprocess.TimeoutExpired:
                ctypes.windll.kernel32.CloseHandle(handle);handle=None;process.wait(timeout=10);status='timeout'
            finally:
                if handle:ctypes.windll.kernel32.CloseHandle(handle)
        result=json.loads(target.read_text(encoding='utf-8')) if target.exists() else {'scenario':s,'rows':[]}
        if status=='ok' and result.get('stage')!='complete':status='worker_incomplete'
        result.update(status=status,exit_code=process.returncode,process_seconds=time.perf_counter()-started,timeout_seconds=s.get('timeout',60),job_memory_limit_mib=1536)
        target.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
        print(s['id'],status,result.get('stage'),len(result['rows']),flush=True)

if __name__=='__main__':main()
