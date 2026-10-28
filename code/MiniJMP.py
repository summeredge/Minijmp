from tkinter import Frame, Menu, BOTH, Toplevel, END, Tk
import pickle
import os
import platform
import time
###############################
from pandastable_local import config, plotting
# ####### Own Module ###########
from worksheets import Worksheets
from modified_app import Minijmp_pre
from icon_resource import create_icon_image, create_plot_icon_images
from modified_table import MTable as Table
from plots import plot_viewer
from txt_output import txt_viewer
from fit_dialog import LinearFitDialog, CorrelationDialog, OrthoFitDialog, ResidDialog, MCorDialog
from basic_dialogs import DescribeDialog, NormTestDialog, CIDialog, MultiDescribeDialog, FitDistDialog
from sample_test_dialog import Mean1SampleDialog, Mean1SampleZDialog, Var1SampleDialog, Mean2SampleDialog, PairedTDialog, MultiVarDialog, Prop1SDialog, Prop2SDialog
from anova_dialog import Anova1WayDialog, TtestDialog, Anova2WayDialog
from chi2_dialog import Chi2TableDialog, Chi2PropDialog
from qc_dialog import GRRDialog, CpkDialog, CpkSubDialog, TIDialog, GRR_Nested_Dialog
from ctrlchart_dialog import IMRDialog, IDialog, MRDialog, XBRDialog, XBSDialog, NPDialog, PDialog, CDialog, UDialog
from sb_hist_dialog import singleHistoDialog, multiHistoDialog, xyHistoDialog
from sb_box_dialog import singleBoxDialog, multiBoxDialog
from sb_misc_dialog import countPlotDialog, linePlotDialog, dotPlotDialog
from dist_plot_dialog import displayProbDialog, displayProb2xDialog
from help_link import open_help


class Minijmp(Worksheets, Minijmp_pre):
    """Basic test frame for the table"""

    def __init__(self, parent=None):
        self.parent = parent
        Frame.__init__(self)
        self.main = self.master
        self.main.geometry('600x400+50+100')
        #  self.main.title('Untitled - Minijmp')

        # Get platform into a variable
        self.currplatform = platform.system()
        self.setConfigDir()
        if not hasattr(self, 'defaultsavedir'):
            self.defaultsavedir = os.path.join(os.path.expanduser('~'))
        self.loadAppOptions()
        # start logging
        self.start_logging()

        self.init_worksheets()
        self.createMenuBar()
        self.setStyles()
        self.clipboarddf = None
        self.projopen = False
        self.plots = dict()
        self.table.tOut = None

        self.main.protocol('WM_DELETE_WINDOW', self.quit)
        self.main.lift()
        self.pickle_fname = None
        self.update_title()
        return

    def createMenuBar(self):
        """Create the menu bar for the application. """

        self.menu = Menu(self.main)
        file_menu = Menu(self.menu, tearoff=0)
        # add recent first
        #  self.createRecentMenu(file_menu)
        filemenuitems = {'01新建项目': {'cmd': self.new_file},
                         '02打开项目': {'cmd': self.load_file},
                         '04保存': {'cmd': self.save_file},
                         '05另存为': {'cmd': self.save_as_file},
                         '06sep': '',
                         '07导入 CSV': {'cmd': self.import_csv},
                         '08高级导入': {'cmd': lambda: self.import_csv(advanced=True)},
                         '09导入 PI 数据': {'cmd': self.import_pi_data},
                         '10导入 Excel': {'cmd': self.load_excel},
                         '10导出 CSV': {'cmd': lambda: self._call('doExport')},
                         '10导出当前表（单表 / Excel）': {'cmd': self.export_sheet},
                         '11sep': '',
                         '12退出': {'cmd': self.quit}}

        self.file_menu = self.createPulldown(
            self.menu, filemenuitems, var=file_menu)
        self.menu.add_cascade(label='文件', menu=self.file_menu['var'])

        sheetmenu = {'01新增工作表': {'cmd': self.addSheet},
                     '02复制工作表': {'cmd': self.copySheet},
                     '03重命名工作表': {'cmd': self.renameSheet},
                     '04删除工作表': {'cmd': self.deleteSheet}}
        self.sheet_menu = self.createPulldown(self.menu, sheetmenu)
        self.menu.add_cascade(label='工作表', menu=self.sheet_menu['var'])

        editmenuitems = {'01撤销 (Ctrl+Z)': {'cmd': self.undo},
                         '02重做': {'cmd': lambda: self._call('redo')},
                         '03粘贴（不含表头）(Ctrl+V)': {'cmd': lambda: self._call('paste')},
                         '04粘贴（含表头）': {'cmd': lambda: self._call('paste_header')},
                         '05复制整表': {'cmd': self.copyTable},
                         '06复制所选 (Ctrl+C)': {'cmd': lambda: self._call('copy')},
                         '07删除所选并上移': {'cmd': lambda: self._call('clearDataUp')},
                         '08清除所选 (Del)': {'cmd': lambda: self._call('clearData')},
                         '13查找/替换 (Ctrl+F)': {'cmd': self.findText},
                         '20sep': 'ddddd',
                         '24首选项': {'cmd': self.currentTablePrefs}}
        self.edit_menu = self.createPulldown(self.menu, editmenuitems)
        self.menu.add_cascade(label='编辑', menu=self.edit_menu['var'])

        self.view_menu = {
            '01放大': {
                'cmd': lambda: self._call('zoomIn')}, '02缩小': {
                'cmd': lambda: self._call('zoomOut')}, '03列宽自动换行': {
                'cmd': lambda: self._call('setWrap')}, '04sep': '', '05深色主题': {
                    'cmd': lambda: self._call(
                        'setTheme', name='dark')}, 
                        # '06Bold Theme': {'cmd': lambda: self._call(
                        #         'setTheme', name='bold')}, 
                                '07浅色主题': {
                                    'cmd': lambda: self._call(
                                        'setTheme', name='default')}, }
        self.view_menu = self.createPulldown(self.menu, self.view_menu)
        self.menu.add_cascade(label='视图', menu=self.view_menu['var'])

        self.data_menu = {
            '01创建分类变量': {'cmd': lambda: self._call('createCategorical')},
            '02应用函数': {'cmd': lambda: self._call('applyColumnFunction')},
            '03重抽样/变换': {'cmd': lambda: self._call('applyTransformFunction')},
            '04取值计数': {'cmd': lambda: self._call('valueCounts')},
            '05字符串处理': {'cmd': lambda: self._call('applyStringMethod')},
            '06日期/时间转换': {'cmd': lambda: self._call('convertDates')},
            '22筛选行': {'cmd': lambda: self._call('queryBar')},
            '32拆分数据列': {'cmd': lambda: self._call('splitColumn')},
            '33堆叠所选列': {'cmd': lambda: self._call('stackColumn')},
            '34全部列排序': {'cmd': lambda: self._call('sortAll')},
            '35所选列排序': {'cmd': lambda: self._call('sortSelected')},
            '42首行提升为列名': {'cmd': lambda: self._call('row1ToHeader')},
            '30sep': '', '40sep': ''}
        self.data_menu = self.createPulldown(self.menu, self.data_menu)
        self.menu.add_cascade(label='数据', menu=self.data_menu['var'])

        self.table_menu = {
            #  '01Describe Table': {'cmd': self.describe},
            '02转换列名': {'cmd': lambda: self._call('convertColumnNames')},
            '03转换为数值': {'cmd': lambda: self._call('convertNumeric')},
            '04清理数据': {'cmd': lambda: self._call('cleanData')},
            '05查找重复项': {'cmd': lambda: self._call('findDuplicates')},
            #  '06Correlation Matrix': {'cmd': lambda: self._call('corrMatrix')},
            #  '07Concatenate Tables': {'cmd': self.concat},
            '08表格转换为文本': {'cmd': lambda: self._call('showasText')},
            '09表格信息': {'cmd': lambda: self._call('showInfo')},
            '10sep': '',
            '11数值变换': {'cmd': lambda: self._call('transform')},
            '12分组聚合': {'cmd': lambda: self._call('aggregate')},
            '13交叉表': {'cmd': lambda: self._call('crosstab')},
            '14合并/拼接表': {'cmd': lambda: self._call('doCombine')},
            '15透视表': {'cmd': lambda: self._call('pivot')},
            '16逆透视表': {'cmd': lambda: self._call('melt')},
            '17时间序列重抽样': {'cmd': lambda: self._call('resample')}
        }
        self.table_menu = self.createPulldown(self.menu, self.table_menu)
        self.menu.add_cascade(label='工具', menu=self.table_menu['var'])

        self.calc_menu = {'01计算器': {'cmd': lambda: self._call('calculator')}}
        self.calc_menu = self.createPulldown(self.menu, self.calc_menu)
        self.menu.add_cascade(label='计算', menu=self.calc_menu['var'])

        from doe_dialog import CreateDOE, CreateGeneralFactorial, AnalyzeDOE
        from doe_foldover_dialog import FoldoverDOE
        from doe_splitplot_dialog import CreateSplitPlot
        from doe_optimize_dialog import OptimizeRSM
        from doe_predict_dialog import PredictRSM
        from doe_overlay_dialog import OverlayContours
        from doe_taguchi_dialog import CreateTaguchi
        from doe_taguchi_analysis_dialog import AnalyzeTaguchi
        self.doe_menu = self.createPulldown(self.menu, {
            '01创建两水平全因子设计': {'cmd': lambda: CreateDOE(self)},
            '02创建两水平部分因子设计': {
                'cmd': lambda: CreateDOE(self, fractional=True)},
            '03分析因子设计': {'cmd': lambda: AnalyzeDOE(self)},
            '04创建中心复合设计': {'cmd': lambda: CreateDOE(self, ccd=True)},
            '05分析响应面模型': {'cmd': lambda: AnalyzeDOE(self)},
            '06优化响应面（DOE-4）': {'cmd': lambda: OptimizeRSM(self)},
            '07创建 Box-Behnken 设计': {'cmd': lambda: CreateDOE(self, bbd=True)},
            '08响应面预测': {'cmd': lambda: PredictRSM(self)},
            '09叠加等高线': {'cmd': lambda: OverlayContours(self)},
            '10创建 Plackett–Burman 设计': {'cmd': lambda: CreateDOE(self, pb=True)},
            '11创建筛选设计（DSD）': {'cmd': lambda: CreateDOE(self, dsd=True)},
            '12分析筛选设计': {'cmd': lambda: AnalyzeDOE(self, screening=True)},
            '13创建一般全因子设计': {'cmd': lambda: CreateGeneralFactorial(self)},
            '14折叠两水平部分因子设计': {'cmd': lambda: FoldoverDOE(self)},
            '15创建两水平裂区设计': {'cmd': lambda: CreateSplitPlot(self)},
            '16创建 Taguchi 设计（静态）': {'cmd': lambda: CreateTaguchi(self)},
            '17创建 Taguchi 设计（动态）': {
                'cmd': lambda: CreateTaguchi(self, dynamic=True)},
            '18分析 Taguchi 设计': {'cmd': lambda: AnalyzeTaguchi(self)},
        })
        self.menu.add_cascade(label='试验设计（DOE）', menu=self.doe_menu['var'])

        self.stats_menu = {
            '01描述性统计': {'cmd': self.describe},
            '02多变量描述性统计': {'cmd': self.multi_describe},
            '04正态性检验': {'cmd': self.norm_test},
            '05置信区间': {'cmd': self.confidence_interval},
            '06分布拟合': {'cmd': self.fit_dist},
            '13相关分析': {'cmd': self.correlation},
            '16正交回归': {'cmd': self.ortho_fit},
            '14线性回归': {'cmd': self.linear_fit},
            '15残差图': {'cmd': self.resid},
            '17相关系数矩阵': {'cmd': self.multi_cor},
            '18完整回归分析': {'cmd': self.advanced_regression},
            '19泊松回归': {'cmd': lambda: self.advanced_regression(model='Poisson')},
            '20名义多分类 Logistic 回归': {'cmd': lambda: self.advanced_regression(model='Nominal')},
            '21有序 Logistic 回归': {'cmd': lambda: self.advanced_regression(model='Ordinal')},
            '22偏最小二乘回归（PLS）': {'cmd': lambda: self.advanced_regression(model='PLS')},
            '23主成分分析': {'cmd': self.pca_analysis},
            '23时间序列分析': {'cmd': self.time_series_analysis},
            '25单样本均值 t 检验': {'cmd': self.mean_1sample},
            '26单样本均值 Z 检验': {'cmd': self.mean_1sampleZ},
            '27单样本标准差检验': {'cmd': self.var_1sample},
            '28单比率检验': {'cmd': self.prop_1sample},
            '29双样本 t 检验': {'cmd': self.mean_2samples},
            '30配对 t 检验': {'cmd': self.paired_t},
            '31双比率检验': {'cmd': self.prop_2samples},
            '32多样本标准差检验': {'cmd': self.multi_var},
            '34单因子方差分析': {'cmd': self.anova_1way},
            #  '33Mean Comparison t': {'cmd': self.JMP_t_test},
            '35双因子方差分析': {'cmd': self.anova_2way},
            '42列联表与卡方检验': {'cmd': self.chi2table},
            '43比率卡方检验': {'cmd': self.chi2prop},
            '06sep': '', '24sep': '', '33sep': '', '40sep': ''}
        self.stats_menu = self.createPulldown(self.menu, self.stats_menu)
        self.menu.add_cascade(label='统计', menu=self.stats_menu['var'])

        self.quality_menu = {
            '50帕累托图': {'cmd': self.pareto_chart},
            '51运行图': {'cmd': self.run_chart},
            '52因果图': {'cmd': self.cause_effect},
            '53多变异图': {'cmd': self.multi_vari},
            '54属性一致性分析': {'cmd': self.attribute_agreement},
            '49sep': '',
            '01量具 R&R 研究（交叉）': {'cmd': self.grr},
            '02量具 R&R 研究（嵌套）': {'cmd': self.grr_nst},
            '07过程能力分析 (Cpk)': {'cmd': self.cpk},
            '08含子组的 Cpk': {'cmd': self.cpksub},
            '09正态过程能力（完整）': {'cmd': lambda: self.capability_analysis('正态能力')},
            '10非正态过程能力': {'cmd': lambda: self.capability_analysis('非正态能力')},
            '11Box-Cox / Johnson 变换': {'cmd': lambda: self.capability_analysis('变换诊断')},
            '12正态能力 Sixpack': {'cmd': lambda: self.capability_analysis('正态 Sixpack')},
            '13非正态能力 Sixpack': {'cmd': lambda: self.capability_analysis('非正态 Sixpack')},
            '22容差区间': {'cmd': self.ti_norm},
            '32控制图 I-MR': {'cmd': self.cChartIMR},
            '33控制图 I（单值）': {'cmd': self.cChartI},
            '34控制图 MR（移动极差）': {'cmd': self.cChartMR},
            '35控制图 Xbar-R': {'cmd': self.cChartXBR},
            '36控制图 Xbar-S': {'cmd': self.cChartXBS},
            '37高级 SPC 控制图': {'cmd': self.advanced_spc},
            '42控制图 NP': {'cmd': self.cChartNP},
            '43控制图 P': {'cmd': self.cChartP},
            '44控制图 C': {'cmd': self.cChartC},
            '45控制图 U': {'cmd': self.cChartU},
            '06sep': '', '20sep': '', '30sep': '', '40sep': ''}
        self.quality_menu = self.createPulldown(self.menu, self.quality_menu)
        self.menu.add_cascade(label='质量', menu=self.quality_menu['var'])

        plot_icons = create_plot_icon_images(self)
        self.plots_menu = {
            '01通用绘图器': {'cmd': self.plot_selected, 'img': plot_icons['carbon-chart--custom']},
            '53保存图形': {'cmd': self.addPlot},
            '54清除图形': {'cmd': self.updatePlotsMenu},
            '55PDF 报告': {'cmd': self.pdfReport},
            '12直方图与分布拟合': {'cmd': self.singleHisto, 'img': plot_icons['carbon-chart--histogram']},
            '13分组直方图': {'cmd': self.multiHisto, 'img': plot_icons['carbon-chart--cluster-bar']},
            '14二维直方图': {'cmd': self.xyHisto, 'img': plot_icons['carbon-chart--treemap']},
            '15多变量箱线图': {'cmd': self.singleBox, 'img': plot_icons['carbon-chart--candlestick']},
            '16分组箱线图': {'cmd': self.multiBox, 'img': plot_icons['carbon-chart--violin-plot']},
            '18分组计数图': {'cmd': self.countPlot, 'img': plot_icons['carbon-chart--cluster-bar']},
            '17条形图': {'cmd': lambda: self.basicPlot('bar'), 'img': plot_icons['carbon-chart--bar']},
            '19饼图': {'cmd': lambda: self.basicPlot('pie'), 'img': plot_icons['carbon-chart--pie']},
            '20线条图': {'cmd': self.linePlot, 'img': plot_icons['carbon-chart--line']},
            '21时间序列图': {'cmd': self.timeSeriesPlot, 'img': plot_icons['carbon-chart--line--data']},
            '22散点图': {'cmd': self.dotPlot, 'img': plot_icons['carbon-chart--scatter']},
            '23区域图': {'cmd': lambda: self.basicPlot('area'), 'img': plot_icons['carbon-chart--area-smooth']},
            '24点图': {'cmd': lambda: self.basicPlot('dotplot'), 'img': plot_icons['carbon-chart--lollipop']},
            '25矩阵图': {'cmd': lambda: self.basicPlot('scatter_matrix'), 'img': plot_icons['tabler-grid-dots']},
            '26等值线图': {'cmd': lambda: self.basicPlot('contour'), 'img': plot_icons['tabler-chart-arcs-3']},
            '27三维散点图': {'cmd': lambda: self.basicPlot('scatter3d'), 'img': plot_icons['tabler-chart-scatter-3d']},
            '28三维曲面图': {'cmd': lambda: self.basicPlot('surface'), 'img': plot_icons['carbon-chart--3D']},
            '30sep': '',
            '34气泡图': {'cmd': lambda: self.statPlot('bubble'), 'img': plot_icons['carbon-chart--bubble']},
            '35经验累积分布函数图': {'cmd': lambda: self.statPlot('ecdf'), 'img': plot_icons['tabler-chart-area-line']},
            '36单值图': {'cmd': lambda: self.statPlot('individual'), 'img': plot_icons['carbon-chart--point']},
            '37区间图': {'cmd': lambda: self.statPlot('interval'), 'img': plot_icons['carbon-chart--error-bar']},
            '38边际图': {'cmd': lambda: self.statPlot('marginal'), 'img': plot_icons['carbon-chart--multitype']},
            '39茎叶图': {'cmd': lambda: self.statPlot('stem'), 'img': plot_icons['tabler-chart-dots-3']},
            '40样本概率图': {'cmd': lambda: self.statPlot('probability'), 'img': plot_icons['carbon-chart--line--data']},
            '32概率图': {'cmd': self.distDPPlot, 'img': plot_icons['carbon-chart--logistic-regression']},
            '33概率图对比': {'cmd': self.dist2XPlot, 'img': plot_icons['carbon-chart--multi-line']},
            '02sep': '', '50sep': '', '60sep': ''}
        self.plots_menu = self.createPulldown(self.menu, self.plots_menu)
        self.menu.add_cascade(label='图形', menu=self.plots_menu['var'])
        self.plot_menu_orig_len = len(self.plots_menu)

        self.debug_menu = {
            '01打印数据框': {'cmd': self.printDF},
            '06sep': ''}
        self.debug_menu = self.createPulldown(self.menu, self.debug_menu)
        self.menu.add_cascade(label='调试', menu=self.debug_menu['var'])

        self.help_menu = {'01帮助文档': {'cmd': lambda: open_help(parent=self.main)},
                          '03查看错误日志': {'cmd': self.showErrorLog},
                          '04关于': {'cmd': self.about}}
        self.help_menu = self.createPulldown(self.menu, self.help_menu)
        self.menu.add_cascade(label='帮助', menu=self.help_menu['var'])

        self.main.config(menu=self.menu)
        self.main.bind('<F1>', lambda event: open_help(parent=self.main))
        return

    def printDF(self):
        print(self.table.model.df)
        return

    def addPlot(self, table=None):
        """Store the current plot so it can be re-loaded"""

        table = table if table is not None else self.table
        if getattr(table, 'pf', None) is None:
            from tkinter import messagebox
            messagebox.showinfo('保存图形', '当前工作表还没有图形。', parent=self.main)
            return
        fig = table.pf.fig
        t = time.strftime("%H:%M:%S")
        source = next(name for name, item in self.sheets.items() if item is table)
        label = f'{source} {t} ({len(self.plots) + 1})'
        # dump and reload the figure to get a new object
        p = pickle.dumps(fig)
        fig = pickle.loads(p)
        self.plots[label] = fig

        def func(label):
            fig = self.plots[label]
            win = Toplevel()
            win.title(label)
            plotting.addFigure(win, fig)

        menu = self.plots_menu['var']
        menu.add_command(label=label, command=lambda: func(label))
        return

    def updatePlotsMenu(self, clear=True):
        """Clear stored plots"""

        if clear:
            self.plots = {}
        menu = self.plots_menu['var']
        menu.delete(self.plot_menu_orig_len - 1, menu.index(END))
        return

    def plot_selected(self):
        if hasattr(self.table, 'pf') and self.table.pf is not None:
            self.addPlot()
            self.table.pf.close()
        self._call('plotSelected')
        return

    def showPlotViewer(self, parent=None, figsize=(10, 7), save_last=True, table=None,
                       deferred=False):
        table = table if table is not None else self.table
        viewer = plot_viewer(table=table, parent=parent, figsize=figsize,
                             register=False)
        if deferred:
            viewer.main.withdraw()
            return viewer
        self.replacePlotViewer(viewer, save_last=save_last)
        return viewer

    def replacePlotViewer(self, viewer, save_last=True):
        """Publish a completed plot only to its source worksheet."""
        table = viewer.table
        previous = getattr(table, 'pf', None)
        child = getattr(table, 'child', None)
        child_previous = getattr(child, 'pf', None)
        if previous is not None and previous.main.winfo_exists():
            if save_last:
                self.addPlot(table=table)
            previous.close()
        table.pf = viewer
        if child is not None and (child_previous is None or child_previous is previous):
            child.pf = viewer

    def print(self, txt, end="\n", table=None):
        table = table if table is not None else self.table
        if table.tOut is None:
            table.tOut = txt_viewer(table=table)
        self.tOut = table.tOut
        from stat_table import StatTable
        if isinstance(txt, StatTable):
            table.tOut.add_table(txt, end)
        else:
            table.tOut.add_txt(txt + end)
        table.tOut.to_end(defer=True)

    def linear_fit(self):

        _ = LinearFitDialog(
            self.table, app=self,
            df=self.table.model.df,
            title='Linear Regression')
        return

    def advanced_regression(self, model='OLS'):
        from regression_dialog import RegressionDialog
        RegressionDialog(parent=self.table, df=self.table.model.df, app=self, model=model)

    def pca_analysis(self):
        from pca_dialog import PCADialog
        PCADialog(parent=self.table, df=self.table.model.df, app=self)

    def time_series_analysis(self):
        from advanced_time_series_dialog import TimeSeriesAnalysisDialog
        TimeSeriesAnalysisDialog(parent=self.table, df=self.table.model.df, app=self)

    def advanced_spc(self):
        from advanced_spc_dialog import AdvancedSPCDialog
        AdvancedSPCDialog(parent=self.table, df=self.table.model.df, app=self)

    def correlation(self):

        _ = CorrelationDialog(
            self.table, app=self,
            df=self.table.model.df,
            title='Correlation')
        return

    def ortho_fit(self):

        _ = OrthoFitDialog(
            self.table, app=self,
            df=self.table.model.df,
            title='Orthogonal Regression')
        return

    def describe(self):
        _ = DescribeDialog(
            self.table, app=self,
            df=self.table.model.df,
            title='Stats Summary')
        return

    def multi_describe(self):
        _ = MultiDescribeDialog(
            self.table, app=self,
            df=self.table.model.df,
            title='Stats Summary Multi Datasets')
        return

    def norm_test(self):
        _ = NormTestDialog(
            self.table, app=self,
            df=self.table.model.df,
            title='Normality Test')
        return

    def resid(self):
        _ = ResidDialog(
            self.table, app=self,
            df=self.table.model.df,
            title='Residual Plots')
        return

    def confidence_interval(self):
        _ = CIDialog(
            self.table, app=self,
            df=self.table.model.df,
            title='Confidence Intervals')
        return

    def multi_cor(self):
        _ = MCorDialog(
            self.table, app=self,
            df=self.table.model.df,
            title='Multi Column Correlation')
        return

    def mean_1sample(self):
        _ = Mean1SampleDialog(
            self.table, app=self,
            df=self.table.model.df,
            title='One sample mean t-test')
        return

    def mean_1sampleZ(self):
        _ = Mean1SampleZDialog(
            self.table, app=self,
            df=self.table.model.df,
            title='One sample mean Z-test')
        return

    def var_1sample(self):
        _ = Var1SampleDialog(
            self.table, app=self,
            df=self.table.model.df,
            title='One sample Std Dev test')
        return

    def mean_2samples(self):
        _ = Mean2SampleDialog(
            self.table, app=self,
            df=self.table.model.df,
            title='Two samples t-test')
        return

    def paired_t(self):
        _ = PairedTDialog(
            self.table, app=self,
            df=self.table.model.df,
            title='Paired t-test')
        return

    def multi_var(self):
        _ = MultiVarDialog(
            self.table, app=self,
            df=self.table.model.df,
            title='Mutli-sample Std Dev Test')
        return

    def prop_1sample(self):
        _ = Prop1SDialog(
            self.table, app=self,
            df=self.table.model.df,
            title='One Proportion Test')
        return

    def prop_2samples(self):
        _ = Prop2SDialog(
            self.table, app=self,
            df=self.table.model.df,
            title='Two Proportions Test')
        return

    def anova_1way(self):
        _ = Anova1WayDialog(
            self.table, app=self,
            df=self.table.model.df,
            title='One-Way ANOVA')
        return

    def JMP_t_test(self):
        _ = TtestDialog(
            self.table, app=self,
            df=self.table.model.df,
            title="Mean Comparison Student's t")
        return

    def anova_2way(self):
        _ = Anova2WayDialog(
            self.table, app=self,
            df=self.table.model.df,
            title='Two-Way ANOVA')
        return

    def chi2table(self):
        _ = Chi2TableDialog(
            self.table, app=self,
            df=self.table.model.df,
            title='Contingency Table and Chi SQ Test')
        return

    def chi2prop(self):
        _ = Chi2PropDialog(
            self.table, app=self,
            df=self.table.model.df,
            title='Propabilities Chi SQ Test')
        return

    def grr(self):
        _ = GRRDialog(
            self.table, app=self,
            df=self.table.model.df,
            title='Crossed Gage R&R')
        return

    def grr_nst(self):
        _ = GRR_Nested_Dialog(
            self.table, app=self,
            df=self.table.model.df,
            title='Nested Gage R&R')
        return

    def cpk(self):
        _ = CpkDialog(
            self.table, app=self,
            df=self.table.model.df,
            title='Process Capability')
        return

    def pareto_chart(self):
        from quality_tools_dialog import QualityToolsDialog
        return QualityToolsDialog(self.table, self.table.model.df, self, kind='pareto')

    def run_chart(self):
        from quality_tools_dialog import QualityToolsDialog
        return QualityToolsDialog(self.table, self.table.model.df, self, kind='run_chart')

    def cause_effect(self):
        from quality_tools_dialog import QualityToolsDialog
        return QualityToolsDialog(self.table, self.table.model.df, self, kind='cause_effect')

    def multi_vari(self):
        from quality_tools_dialog import QualityToolsDialog
        return QualityToolsDialog(self.table, self.table.model.df, self, kind='multi_vari')

    def attribute_agreement(self):
        from quality_tools_dialog import QualityToolsDialog
        return QualityToolsDialog(self.table, self.table.model.df, self, kind='attribute_agreement')

    def capability_analysis(self, mode):
        from capability_dialog import CapabilityDialog
        return CapabilityDialog(parent=self.table, df=self.table.model.df, app=self, mode=mode)

    def cpksub(self):
        _ = CpkSubDialog(
            self.table, app=self,
            df=self.table.model.df,
            title='Process Capability with Subgroups')
        return

    def ti_norm(self):
        _ = TIDialog(
            self.table, app=self,
            df=self.table.model.df,
            title='Normal Dist TI')
        return

    def cChartIMR(self):
        _ = IMRDialog(
            self.table, app=self,
            df=self.table.model.df,
            title='Control Chart I/MR')
        return

    def cChartI(self):
        _ = IDialog(
            self.table, app=self,
            df=self.table.model.df,
            title='Control Chart I')
        return

    def cChartMR(self):
        _ = MRDialog(
            self.table, app=self,
            df=self.table.model.df,
            title='Control Chart MR')
        return

    def cChartXBR(self):
        _ = XBRDialog(
            self.table, app=self,
            df=self.table.model.df,
            title='Control Chart X Bar/R')
        return

    def cChartXBS(self):
        _ = XBSDialog(
            self.table, app=self,
            df=self.table.model.df,
            title='Control Chart X Bar/S')
        return

    def cChartNP(self):
        _ = NPDialog(
            self.table, app=self,
            df=self.table.model.df,
            title='Control Chart NP')
        return

    def cChartP(self):
        _ = PDialog(
            self.table, app=self,
            df=self.table.model.df,
            title='Control Chart P')
        return

    def cChartC(self):
        _ = CDialog(
            self.table, app=self,
            df=self.table.model.df,
            title='Control Chart C')
        return

    def cChartU(self):
        _ = UDialog(
            self.table, app=self,
            df=self.table.model.df,
            title='Control Chart U')
        return

    def fit_dist(self):
        _ = FitDistDialog(
            self.table, app=self,
            df=self.table.model.df,
            title='Fit Distributions')
        return

    def singleHisto(self):
        _ = singleHistoDialog(
            self.table, app=self,
            df=self.table.model.df,
            title='Histogram + Distribution Fit')
        return

    def multiHisto(self):
        _ = multiHistoDialog(
            self.table, app=self,
            df=self.table.model.df,
            title='Histogram with Groups')
        return

    def xyHisto(self):
        _ = xyHistoDialog(
            self.table, app=self,
            df=self.table.model.df,
            title='2D Histogram')
        return

    def singleBox(self):
        _ = singleBoxDialog(
            self.table, app=self,
            df=self.table.model.df,
            title='Box Plot')
        return

    def multiBox(self):
        _ = multiBoxDialog(
            self.table, app=self,
            df=self.table.model.df,
            title='Box Plot with Groups')
        return

    def countPlot(self):
        _ = countPlotDialog(
            self.table, app=self,
            df=self.table.model.df,
            title='Count Plot with Groups')
        return

    def statPlot(self, kind):
        from stat_plot_dialog import StatPlotDialog
        StatPlotDialog(self.table, app=self, df=self.table.model.df, kind=kind)

    def basicPlot(self, kind):
        from basic_plot_dialog import BasicPlotDialog
        BasicPlotDialog(self.table, app=self, df=self.table.model.df, kind=kind)

    def linePlot(self):
        _ = linePlotDialog(
            self.table, app=self,
            df=self.table.model.df,
            title='Line Plot with Groups')
        return

    def timeSeriesPlot(self):
        from time_series_dialog import TimeSeriesDialog
        _ = TimeSeriesDialog(
            self.table, app=self,
            df=self.table.model.df,
            title='时间序列图')
        return

    def dotPlot(self):
        _ = dotPlotDialog(
            self.table, app=self,
            df=self.table.model.df,
            title='Dot Plot with Groups')
        return

    def distDPPlot(self):
        _ = displayProbDialog(
            self.table, app=self,
            df=self.table.model.df,
            title='Distribution Plot')
        return

    def dist2XPlot(self):
        _ = displayProb2xDialog(
            self.table, app=self,
            df=self.table.model.df,
            title='Distribution Plot Compare')
        return


def main():
    # Create the main window
    root = Tk()
    icon = create_icon_image(root)
    root.iconphoto(True, icon)

    # Create an instance of the custom frame
    _ = Minijmp(root)

    # Run the application
    root.mainloop()
    return


if __name__ == "__main__":
    main()

#  if __name__ == "__main__":
#      app = Minijmp()
#      # launch the app
#      app.mainloop()
