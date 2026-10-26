"""Exercise real Tk dialogs reached by application menu callbacks."""
import ast
import json
from pathlib import Path
import re
import sys
from types import SimpleNamespace
import tkinter as tk

import pandas as pd
import pytest

import MiniJMP
from modified_app import Minijmp_pre
from dialog import Dialogs

ROOT = Path(__file__).resolve().parents[1]
TREE = ast.parse((ROOT / 'code/MiniJMP.py').read_text(encoding='utf-8'))
CALLS = []
for method in next(n for n in TREE.body if isinstance(n, ast.ClassDef)).body:
    if not isinstance(method, ast.FunctionDef):
        continue
    for n in ast.walk(method):
        if (isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                and isinstance(getattr(MiniJMP, n.func.id, None), type)
                and issubclass(getattr(MiniJMP, n.func.id), Dialogs)):
            title = next(k.value.value for k in n.keywords if k.arg == 'title')
            CALLS.append((method.name, n.func.id, title))


def widgets(parent):
    for child in parent.winfo_children():
        yield child
        yield from widgets(child)


def app_for(root):
    output = []
    frame = tk.Frame(root)
    frame.model = SimpleNamespace(df=pd.DataFrame({'测量': [1., 2., 4., 5.], '分组': ['甲', '甲', '乙', '乙']}))
    return SimpleNamespace(table=frame, print=lambda *args, **kw: output.append(args),
        dialog_help_msg=lambda **kw: Minijmp_pre.dialog_help_msg(None, **kw), output=output,
        online_documentation=lambda **kw: None)


def construct(root, callback):
    root.deiconify()
    root.update()
    app = app_for(root)
    before = set(root.winfo_children())
    getattr(MiniJMP.Minijmp, callback)(app)
    top = next(w for w in set(root.winfo_children()) - before if isinstance(w, tk.Toplevel))
    return app, top


@pytest.mark.parametrize('callback,cls,title', CALLS, ids=[c[1] for c in CALLS])
def test_menu_dialog_lifecycle_and_translation(tk_root, callback, cls, title):
    errors = []
    original = tk_root.report_callback_exception
    tk_root.report_callback_exception = lambda *e: errors.append(e)
    app, top = construct(tk_root, callback)
    try:
        top.deiconify()
        tk_root.update()
        assert top.winfo_viewable()
        assert re.search('[\u4e00-\u9fff]', top.title()), top.title()
        for w in widgets(top):
            if 'text' in w.keys():
                text = str(w.cget('text'))
                assert not re.search('[A-Za-z]{2}', text) or re.search('[\u4e00-\u9fff]', text) or text in {'USL - LSL'}, (cls, text)
            if w.winfo_class() == 'TCombobox':
                values = tuple(w.cget('values'))
                if values != tuple(app.table.model.df.columns):
                    for value in values:
                        assert re.search('[\u4e00-\u9fff]', value) or value in {'AIAG（ANOVA）', 'EMP（ANOVA）'}, (cls, value)
                    for i in range(len(values)):
                        w.current(i)
                        w.event_generate('<<ComboboxSelected>>')
                        tk_root.update()
        for button in widgets(top):
            if button.winfo_class() in ('TButton', 'Button'):
                label = str(button.cget('text'))
                expected = {'确定': 'ok', '取消': 'quit', '关闭': 'quit', '绘图': 'preview', '帮助': 'help'}[label]
                assert str(button.cget('command')).endswith(expected)
        close = next(w for w in widgets(top) if 'text' in w.keys() and w.cget('text') in ('取消', '关闭'))
        close.invoke()
        assert not top.winfo_exists()
        assert app.output == []
        assert errors == []
    finally:
        if top.winfo_exists(): top.destroy()
        app.table.destroy()
        tk_root.report_callback_exception = original


@pytest.mark.parametrize('values', [
    ['Normal', "Student's t", 'Gamma', 'Lognormal', 'Exponential', 'Weibull'],
    ['Normal', 'Chi Square', 'F', 'LogNormal', 't', 'Binomial', 'Poisson'],
    ['Auto', 'On', 'Off'], ['Use Subgrp ID Col.', 'Use Subgrp Size'],
    ['Unbiased Std Dev', 'Ranges'], ['count','frequency','proportion','percent','density'],
    ['layer','dodge','stack','fill'], ['bars','step','poly'], ['Half','Full','1/4']])
def test_display_option_preserves_internal_values(tk_root, values):
    from dialog import option_combobox, display_text
    internal = tk.StringVar(tk_root, value=values[0])
    box = option_combobox(tk_root, values=values, textvariable=internal)
    try:
        assert internal.get() == values[0]
        for index, value in enumerate(values):
            box.current(index)
            box.event_generate('<<ComboboxSelected>>')
            assert internal.get() == value
            assert box.get() == display_text(value)
            other = values[(index + 1) % len(values)]
            internal.set(other)
            assert box.get() == display_text(other)
            internal.set(value)
            assert box.get() == display_text(value)
    finally:
        box.destroy()


def test_distribution_dynamic_labels_and_original_argument_keys(tk_root):
    from dist_plot_dialog import comboNEntries
    top = tk.Toplevel(tk_root)
    try:
        control = comboNEntries('Distribution', ['Normal','F'],
            [['Mean','Standard deviation'], ['Numerator degrees of freedom','Denominator degrees of freedom']], top)
        control.combo.current(1)
        control.combo.event_generate('<<ComboboxSelected>>')
        tk_root.update()
        assert [e['label'].cget('text') for e in control.entries] == ['分子自由度','分母自由度']
        control.entries[0]['input'].set('4')
        control.entries[1]['input'].set('8')
        assert control.get_values() == ({'Numerator degrees of freedom': 4, 'Denominator degrees of freedom': 8}, 'F')
    finally:
        top.destroy()



BASELINE = json.loads((ROOT / 'tests/fixtures/dialog_baseline.json').read_text(encoding='utf-8'))

# Bind expectations to the original analysis variables, independently of widget bindings.
OPTION_VARIABLES = {
    'GRRDialog': ('mvar', 'inter'),
    'CpkSubDialog': ('mvar', 'subm'),
    'singleHistoDialog': ('stat', 'dist'),
    'multiHistoDialog': ('multiple', 'element', 'stat', 'palette'),
    'xyHistoDialog': ('palette',),
    'singleBoxDialog': ('stat',),
    'multiBoxDialog': ('stat', 'palette'),
    'countPlotDialog': ('stat', 'palette'),
    'linePlotDialog': ('palette',),
    'dotPlotDialog': ('palette',),
    'displayProbDialog': ('dist.combo_select',),
    'displayProb2xDialog': ('dist1.combo_select', 'dist2.combo_select'),
}


def variable_values(value):
    if isinstance(value, tk.Variable):
        return value.get()
    if isinstance(value, dict):
        result = {str(k): variable_values(v) for k, v in value.items() if isinstance(v, (tk.Variable, dict))}
        return result or None
    return None


@pytest.mark.parametrize('callback,cls,title', CALLS, ids=[c[1] for c in CALLS])
def test_original_defaults_structure_and_english_removed(tk_root, callback, cls, title):
    app = app_for(tk_root)
    dialog = getattr(MiniJMP, cls)(app.table, df=app.table.model.df, app=app, title=title)
    try:
        expected = BASELINE[cls]
        actual = {k: variable_values(v) for k, v in dialog.__dict__.items() if isinstance(v, (tk.Variable, dict))}
        # 阶段对比的展开区在勾选时才创建，默认窗口结构保持原样。
        actual = {k: v for k, v in actual.items() if k != 'stage_compare'}
        assert actual == expected['variables']
        # 新增的只是一个勾选项，不进入原窗口控件序列比较。
        stage_toggle = '启用阶段对比（改善前/改善后）'
        shown = [w for w in widgets(dialog.main)
                 if 'text' not in w.keys() or str(w.cget('text')) != stage_toggle]
        assert [w.winfo_class() for w in shown] == expected['classes']
        old = {text for text in expected['texts'] if re.search('[A-Za-z]{2}', text)}
        for widget in shown:
            if 'text' in widget.keys():
                assert str(widget.cget('text')) not in old
        # Every displayed fixed option maps back to that exact original spelling.
        boxes = [w for w in shown if 'values' in w.keys()]
        assert len(boxes) == len(expected['options'])
        fixed_boxes = []
        for box, values in zip(boxes, expected['options']):
            if values == list(app.table.model.df.columns):
                assert list(box.cget('values')) == values
            else:
                fixed_boxes.append((box, values))
        variable_paths = OPTION_VARIABLES.get(cls, ())
        assert len(fixed_boxes) == len(variable_paths)
        for (box, values), path in zip(fixed_boxes, variable_paths):
            assert hasattr(box, 'display_variable'), (cls, path)
            assert len(box.cget('values')) == len(values)
            variable = dialog
            for attribute in path.split('.'):
                variable = getattr(variable, attribute)
            for index, value in enumerate(values):
                box.current(index)
                box.event_generate('<<ComboboxSelected>>')
                tk_root.update()
                assert variable.get() == value, (cls, path, value, variable.get())
    finally:
        dialog.quit()
        app.table.destroy()


def test_probability_secondary_dialog_real_confirm_and_cancel(tk_root):
    # Use the same original modal dialog, overriding only its button labels locally.
    from chi2_dialog import ProbabilityDialog
    for confirm in (False, True):
        def finish():
            top = next(w for w in tk_root.winfo_children() if isinstance(w, tk.Toplevel))
            button = next(w for w in widgets(top) if 'text' in w.keys() and w.cget('text') == ('确定' if confirm else '取消'))
            button.invoke()
        tk_root.after(30, finish)
        dialog = ProbabilityDialog(tk_root, title='假设概率（总和须为 1）', labels=['甲','乙'], initialvalues=[0,0], types=['float','float'])
        assert bool(dialog.result) == confirm


def test_real_confirm_calls_statistics_and_invalid_input_is_chinese(tk_root):
    from basic_dialogs import DescribeDialog
    app = app_for(tk_root)
    dialog = DescribeDialog(app.table, df=app.table.model.df, app=app, title='Stats Summary')
    dialog.xvar.set('测量')
    next(w for w in widgets(dialog.main) if 'text' in w.keys() and w.cget('text') == '确定').invoke()
    assert not dialog.main.winfo_exists()
    assert any('均值' in str(row) for row in app.output)
    app.output.clear()
    from sample_test_dialog import Mean1SampleDialog
    dialog = Mean1SampleDialog(app.table, df=app.table.model.df, app=app, title='One sample mean t-test')
    dialog.xvar.set('测量')
    dialog.u0.set('3')
    dialog.alpha.set('2')
    next(w for w in widgets(dialog.main) if 'text' in w.keys() and w.cget('text') == '确定').invoke()
    assert any('检验要求' in str(row) for row in app.output)
    app.table.destroy()


def test_legacy_plot_options_and_all_original_values(tk_root):
    from pandastable_local import plotting
    app = app_for(tk_root)
    parent = SimpleNamespace(table=app.table)
    top = tk.Toplevel(tk_root)
    errors = []
    original = tk_root.report_callback_exception
    tk_root.report_callback_exception = lambda *e: errors.append(e)
    try:
        for cls in (plotting.MPLBaseOptions, plotting.MPL3DOptions, plotting.AnnotationOptions, plotting.ExtraOptions, plotting.AnimateOptions):
            options = cls(parent=parent)
            frame = options.showDialog(top)
            tk_root.update()
            for key, config in options.opts.items():
                if key not in options.tkvars or config['type'] in ('scrolledtext', 'listbox'): continue
                if config['type'] in ('entry', 'combobox') and not isinstance(config['default'], int):
                    assert str(options.tkvars[key].get()) == str(config['default'])
                elif config['type'] == 'checkbutton':
                    assert options.tkvars[key].get() == config['default']
                elif config['type'] == 'scale':
                    assert float(options.tkvars[key].get()) == config['default']
                widget = options.widgets[key]
                if hasattr(widget, 'display_variable'):
                    for i, value in enumerate(config['items']):
                        widget.current(i)
                        widget.event_generate('<<ComboboxSelected>>')
                        assert options.tkvars[key].get() == value
                        options.tkvars[key].set(config['default'])
            for widget in widgets(frame):
                for key in ('text', 'label'):
                    if key in widget.keys():
                        assert str(widget.cget(key)) not in plotting.PLOT_LABELS
            frame.destroy()
        assert not errors
    finally:
        top.destroy()
        app.table.destroy()
        tk_root.report_callback_exception = original


def test_display_traces_are_released_when_dialog_closes(tk_root):
    from dialog import option_combobox
    parent = tk.Frame(tk_root)
    variable = tk.StringVar(tk_root, value='Auto')
    before = variable.trace_info()
    option_combobox(parent, values=['Auto','On','Off'], textvariable=variable)
    assert len(variable.trace_info()) == len(before) + 1
    parent.destroy()
    assert variable.trace_info() == before


def test_actual_menu_commands_open_original_dialogs(tk_root):
    app = MiniJMP.Minijmp.__new__(MiniJMP.Minijmp)
    tk.Frame.__init__(app, tk_root)
    app.main = tk_root
    stub = app_for(tk_root)
    app.table = stub.table
    app.print = stub.print
    errors = []
    original = tk_root.report_callback_exception
    tk_root.report_callback_exception = lambda *e: errors.append(e)
    try:
        app.createMenuBar()
        reached = set()
        for name in ('stats_menu', 'quality_menu', 'plots_menu'):
            entries = getattr(app, name)
            menu = entries['var']
            index = 0
            for key in sorted(k for k in entries if k != 'var'):
                if key.endswith('sep'):
                    index += 1
                    continue
                callback = entries[key]['cmd'].__name__
                if callback in {c[0] for c in CALLS}:
                    before = set(tk_root.winfo_children())
                    menu.invoke(index)
                    top = next(w for w in set(tk_root.winfo_children()) - before if isinstance(w, tk.Toplevel))
                    assert re.search('[\u4e00-\u9fff]', top.title())
                    close = next(w for w in widgets(top) if 'text' in w.keys() and w.cget('text') in ('取消','关闭'))
                    close.invoke()
                    reached.add(callback)
                index += 1
        assert reached == {c[0] for c in CALLS} - {'JMP_t_test'}
        assert not errors
    finally:
        app.menu.destroy()
        app.destroy()
        app.table.destroy()
        tk_root.report_callback_exception = original


def test_original_analysis_code_is_unchanged():
    """除 G2/G3 明确接管并单独保护的报告 apply 外，保留原分析方法的完整 AST 守卫。"""
    from source_baselines import read_source_baseline
    class ColumnMemoryHooks(ast.NodeTransformer):
        """Remove only the successful-selection UI hook, retaining analysis AST."""
        def visit_Expr(self, node):
            call = node.value
            if (isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute)
                    and isinstance(call.func.value, ast.Name)
                    and call.func.value.id == 'self' and call.func.attr == 'remember_columns'):
                return None
            return self.generic_visit(node)

        def visit_If(self, node):
            node = self.generic_visit(node)
            return node if node.body or node.orelse else None

        def visit_Assign(self, node):
            # Capturing these return values controls only whether memory is saved.
            if (len(node.targets) == 1 and isinstance(node.targets[0], ast.Name)
                    and node.targets[0].id == 'result' and isinstance(node.value, ast.Call)
                    and isinstance(node.value.func, ast.Name)
                    and node.value.func.id in ('compare_dist', 'ti_norm', 'norm_test')):
                return ast.Expr(value=node.value)
            return self.generic_visit(node)

    class StageCompareHook(ast.NodeTransformer):
        """Remove only the optional stage-comparison branch."""
        def visit_If(self, node):
            calls = {ast.unparse(n.func) for n in ast.walk(node) if isinstance(n, ast.Call)}
            if 'stage_compare.run' in calls:
                return None
            return self.generic_visit(node)

        def visit_Call(self, node):
            node.keywords = [kw for kw in node.keywords if kw.arg != 'detect_rules']
            return self.generic_visit(node)

    class ErrorsToMarker(ast.NodeTransformer):
        def visit_Call(self, node):
            if isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name) and node.func.value.id == 'self' and node.func.attr == 'error':
                return ast.copy_location(ast.Call(func=node.func, args=[ast.Constant('error message')], keywords=[]), node)
            # The local probability dialog keeps the inherited implementation.
            if isinstance(node.func, ast.Name) and node.func.id == 'ProbabilityDialog':
                node.func.id = 'MultipleValDialog'
            for kw in node.keywords:
                if kw.arg == 'title' and isinstance(node.func, ast.Name) and node.func.id == 'MultipleValDialog':
                    kw.value = ast.Constant('probability dialog title')
            return self.generic_visit(node)

    class PearsonSwitchHook(ast.NodeTransformer):
        """Remove only CorrelationDialog's explicit pearson switch from fit_plot."""
        removed = 0

        def visit_ClassDef(self, node):
            if node.name != 'CorrelationDialog':
                return node
            method = next(m for m in node.body
                          if isinstance(m, ast.FunctionDef) and m.name == 'apply')
            calls = [n for n in ast.walk(method) if isinstance(n, ast.Call)
                     and isinstance(n.func, ast.Name) and n.func.id == 'fit_plot']
            assert len(calls) == 1
            call = calls[0]
            assert [ast.unparse(arg) for arg in call.args] == ['x', 'y']
            names = [kw.arg for kw in call.keywords]
            assert names.count('pearson') == 1
            index = names.index('pearson')
            assert names[index - 1] == 'alpha' and names[index + 1] == 'ellipse'
            switch = call.keywords[index]
            assert ast.dump(switch.value) == ast.dump(ast.parse('self.cor_p.get()', mode='eval').body)
            call.keywords.remove(switch)
            self.removed += 1
            return node

    class ReportOnly(ast.NodeTransformer):
        """Remove only G4 added report lines and translated texts."""
        texts = {'Received %d valid data pairs for group ID and measurement.':
                     '子组标识与测量值的有效配对数 = %d。',
                 'WARNING: Unbalanced subgrouping.': '警告：子组大小不相等。'}

        def visit_Expr(self, node):
            call = node.value
            if (isinstance(call, ast.Call) and ast.unparse(call.func) == 'self.app.print'
                    and call.args and isinstance(call.args[0], ast.JoinedStr)
                    and isinstance(call.args[0].values[0], ast.Constant)
                    and call.args[0].values[0].value == '分析变量：'):
                return None
            return self.generic_visit(node)

        def visit_Constant(self, node):
            if isinstance(node.value, str):
                node.value = self.texts.get(node.value, node.value)
            return node

    paths = sorted({Path(getattr(MiniJMP, cls).__module__.replace('.', '/')) for _, cls, _ in CALLS})
    for path in paths:
        file = 'code/' + str(path).replace('\\','/') + '.py'
        baseline = read_source_baseline('87281643b7fd0caaedb50ff561720b221c489a07', file)
        debug_lines = {
            'code/basic_dialogs.py': ('        print(x)\n', 1),
            'code/ctrlchart_dialog.py': ('        print(NP)\n', 1),
            'code/fit_dialog.py': ('        print("xlabel", xlabel, "y", ylabel)\n', 2),
        }
        if file in debug_lines:
            statement, count = debug_lines[file]
            assert baseline.count(statement) == count, file
            baseline = baseline.replace(statement, '')
        current = (ROOT / file).read_text(encoding='utf-8')
        expected_hooks = {'basic_dialogs': 5, 'fit_dialog': 4, 'sample_test_dialog': 6,
                          'qc_dialog': 5, 'ctrlchart_dialog': 3, 'anova_dialog': 2,
                          'sb_hist_dialog': 2}
        hooks = [n for n in ast.walk(ast.parse(current)) if isinstance(n, ast.Call)
                 and isinstance(n.func, ast.Attribute) and isinstance(n.func.value, ast.Name)
                 and n.func.value.id == 'self' and n.func.attr == 'remember_columns']
        assert len(hooks) == expected_hooks.get(path.name, 0), file
        if file == 'code/dist_plot_dialog.py':
            # SheetApp routes plot creation through the source worksheet proxy.
            assert current.count('self.showPlotViewer()') == 2
            current = current.replace('self.showPlotViewer()', 'self.app.showPlotViewer()')
        if file == 'code/sb_box_dialog.py':
            message = "self.error('缺少输入数据。')"
            assert current.count(message) == 2
            current = current.replace(message, "self.error('Missing input data.')")
        if file == 'code/sb_hist_dialog.py':
            display_changes = {
                "self.error('没有可供绘图的数值观测值。')": "self.error('No numeric observations to plot.')",
                "self.error('无法使用所选分布进行拟合。', preview_failed=False)":
                    'self.error("Can\'t perform fit with the dist..")',
                "self.error('缺少输入数据。')": "self.error('Missing input data.')",
                "self.error('缺少 X 或 Y 数据列。')": "self.error('Missing X or Y data col.')",
            }
            for current_text, baseline_text in display_changes.items():
                assert current.count(current_text) == 1
                current = current.replace(current_text, baseline_text)
        if file == 'code/sb_misc_dialog.py':
            display_changes = {
                "self.error('缺少输入数据。')": "self.error('Missing input data.')",
                "self.error('缺少 X 输入数据。')": "self.error('Missing input X data.')",
                "self.error('缺少 Y 输入数据。')": "self.error('Missing input Y data.')",
            }
            for current_text, baseline_text in display_changes.items():
                count = 2 if ' X ' in current_text or ' Y ' in current_text else 1
                assert current.count(current_text) == count
                current = current.replace(current_text, baseline_text)
        if file == 'code/basic_dialogs.py':
            # G6 仅更改正态 Q-Q 图的变量标签及字体；仍完整保护统计调用。
            old_plot = "            pf.ax.set_ylabel('Observed Values')"
            new_plot = "            pf.ax.set_ylabel(self.xvar.get())\n            style_axes(pf.ax)"
            assert current.count(new_plot) == 1
            current = current.replace(new_plot, old_plot)
        pearson_switch = PearsonSwitchHook()
        if file == 'code/fit_dialog.py':
            # REVIEW-017：Pearson 报告独立于椭圆显示，当前已由运行时测试保护。
            current = ast.unparse(pearson_switch.visit(ast.parse(current)))
            assert pearson_switch.removed == 1
        def methods(source, legacy=False):
            tree = ast.parse(source)
            if file == 'code/qc_dialog.py':
                if legacy:
                    # 列记忆与 REVIEW-018/019 均按整函数哈希冻结后再还原。
                    from source_baselines import normalize_column_memory, normalize_p2_legacy
                    tree = normalize_p2_legacy(normalize_column_memory(tree, 'qc_dialog.py'),
                                               'qc_dialog.py', ast.parse(baseline))
                # G4 新增标签与翻译由 ReportOnly 还原。
                tree = ReportOnly().visit(tree)
            if file == 'code/ctrlchart_dialog.py':
                # 阶段对比分支由 SPC 测试覆盖；其余 apply AST 仍完整比较。
                tree = StageCompareHook().visit(tree)
            tree = ErrorsToMarker().visit(ColumnMemoryHooks().visit(tree))
            return {c.name + '.' + m.name: ast.dump(m, include_attributes=False) for c in tree.body if isinstance(c, ast.ClassDef)
                    for m in c.body if isinstance(m, ast.FunctionDef) and m.name in ('apply','ok','preview','get_values','get_box_settings','get_histo_setting')}
        actual, original = methods(current, True), methods(baseline)
        if file == 'code/sb_box_dialog.py':
            # Preview lifecycle moved to SBDialog; runtime coverage is in test_plot_window_lifecycle.py.
            for method in ('singleBoxDialog.preview', 'multiBoxDialog.preview'):
                assert method in original and method not in actual
                original.pop(method)
        if file == 'code/sb_hist_dialog.py':
            # Histogram preview now shares SBDialog.preview; runtime tests cover success and fit failure.
            method = 'multiHistoDialog.preview'
            assert method in original and method not in actual
            original.pop(method)
        if file == 'code/sb_misc_dialog.py':
            # Count, line, and dot plots now use the shared SBDialog preview lifecycle.
            for method in ('countPlotDialog.preview', 'linePlotDialog.preview', 'dotPlotDialog.preview'):
                assert method in original and method not in actual
                original.pop(method)
        if file == 'code/basic_dialogs.py':
            # 两个输出编排由 G2 逐入口数据、清洗及百分位数测试保护。
            for method in ('DescribeDialog.apply', 'MultiDescribeDialog.apply'):
                assert method in actual and method in original
                actual.pop(method)
                original.pop(method)
        if file == 'code/chi2_dialog.py':
            # G3 的分类概率报告由专项路由测试及冻结计算 AST 保护。
            method = 'Chi2PropDialog.apply'
            assert method in actual and method in original
            actual.pop(method)
            original.pop(method)
        assert actual == original, file


@pytest.mark.skipif(sys.platform != 'win32', reason='验证 Windows Tk 中文字体回退')
def test_chinese_font_fallback_and_translated_option_width(tk_root):
    import tkinter.font as font
    tk_root.deiconify()
    family = str(tk_root.tk.call('font', 'actual', 'TkDefaultFont', '-family', '--', '中'))
    assert family in font.families(tk_root)
    # Confirm the resolved CJK font actually has each required Chinese glyph.
    from fontTools.ttLib import TTFont
    import winreg
    key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r'SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts')
    paths = []
    try:
        index = 0
        while True:
            try:
                name, path, _ = winreg.EnumValue(key, index)
            except OSError:
                break
            index += 1
            if family.lower() in name.lower(): paths.append(path)
    finally:
        winreg.CloseKey(key)
    assert paths, family
    import os
    path = Path(paths[0])
    if not path.is_absolute(): path = Path(os.environ['WINDIR']) / 'Fonts' / path
    with TTFont(path, fontNumber=0) as chinese_font:
        cmap = chinese_font.getBestCmap()
        assert all(ord(c) in cmap for c in '确定取消置信区间显著性水平预测响应子组规格')
    for callback, cls, title in CALLS:
        app = app_for(tk_root)
        dialog = getattr(MiniJMP, cls)(app.table, df=app.table.model.df, app=app, title=title)
        try:
            tk_root.update()
            for widget in widgets(dialog.main):
                if hasattr(widget, 'display_variable'):
                    face = font.Font(root=tk_root, font=widget.cget('font') or 'TkDefaultFont')
                    assert max(face.measure(str(value)) for value in widget.cget('values')) <= widget.winfo_width() - 22, cls
        finally:
            dialog.quit()
            app.table.destroy()


def test_legacy_plot_title_uses_real_modal_buttons(tk_root):
    from pandastable_local.plotting import PlotTitleDialog
    for confirm in (False, True):
        def finish():
            top = next(w for w in tk_root.winfo_children() if isinstance(w, tk.Toplevel))
            button = next(w for w in widgets(top) if 'text' in w.keys() and w.cget('text') == ('确定' if confirm else '取消'))
            button.invoke()
        tk_root.after(30, finish)
        dialog = PlotTitleDialog('子图标题', '标题：', parent=tk_root, initialvalue='用户标题')
        assert dialog.result == ('用户标题' if confirm else None)


def test_legacy_grid_radiobuttons_and_plot_kind_mapping(tk_root):
    from pandastable_local import plotting
    parent = SimpleNamespace(gridaxes={}, removeSubplot=lambda: None, setSubplotTitle=lambda: None)
    top = tk.Toplevel(tk_root)
    try:
        options = plotting.PlotLayoutOptions(parent)
        frame = options.showDialog(top)
        assert options.rowsvar.get() == options.colsvar.get() == 2
        assert options.modevar.get() == 'normal'
        radios = [w for w in widgets(frame) if w.winfo_class() in ('Radiobutton', 'TRadiobutton')]
        assert [str(w.cget('text')) for w in radios] == ['常规','拆分数据','多视图']
        for radio, expected in zip(radios, ('normal','splitdata','multiviews')):
            radio.invoke()
            assert options.modevar.get() == expected
        options.plottypeslistbox.selection_set(0, 2)
        display = plotting.getListBoxSelection(options.plottypeslistbox)
        reverse = {v: k for k, v in plotting.PLOT_OPTIONS.items()}
        assert [reverse[v] for v in display] == ['histogram','line','scatter']
    finally:
        top.destroy()


def test_real_legacy_menu_entry_opens_all_six_panels(tk_root):
    from modified_table import MTable
    from pandastable_local.data import TableModel
    frame = tk.Frame(tk_root)
    table = MTable(frame)
    table.show()
    table.updateModel(TableModel(dataframe=pd.DataFrame({'X': [1.,2.,3.], 'Y': [4.,5.,6.]})))
    table.setSelectedCol(0)
    errors = []
    original = tk_root.report_callback_exception
    tk_root.report_callback_exception = lambda *e: errors.append(e)
    app = SimpleNamespace(table=table, _call=lambda method: getattr(table, method)())
    try:
        MiniJMP.Minijmp.plot_selected(app)
        tk_root.update()
        assert table.pf.main.title() == '通用绘图器'
        assert [table.pf.nb.tab(tab, 'text') for tab in table.pf.nb.tabs()] == ['数据配置','基本选项','注释','网格布局','其他选项','三维选项','动画']
        table.pf.close()
        assert table.pf is None
        assert not errors
    finally:
        if getattr(table, 'pf', None) is not None: table.pf.close()
        frame.destroy()
        tk_root.report_callback_exception = original


def test_auto_placeholder_preserves_original_numeric_input(tk_root):
    from dialog import display_variable
    from utilities import get_number
    parent = tk.Frame(tk_root)
    value = tk.StringVar(tk_root, value='Auto')
    shown = display_variable(value, owner=parent)
    entry = tk.Entry(parent, textvariable=shown)
    assert entry.get() == '自动'
    assert value.get() == 'Auto'
    assert get_number(value) is None
    entry.delete(0, tk.END)
    entry.insert(0, '1.25')
    assert value.get() == '1.25'
    assert get_number(value) == 1.25
    value.set('Auto')
    assert entry.get() == '自动'
    parent.destroy()
    assert value.trace_info() == []


@pytest.mark.parametrize('callback,expected_label', [
    ('cChartNP', '不合格品数（Y）'),
    ('cChartP', '不合格品数（Y）'),
    ('cChartC', '缺陷数（Y）'),
    ('cChartU', '缺陷数（Y）'),
])
def test_control_chart_count_labels_match_analysis(tk_root, callback, expected_label):
    app, top = construct(tk_root, callback)
    try:
        labels = [str(w.cget('text')) for w in widgets(top) if 'text' in w.keys()]
        assert expected_label in labels
        other = '缺陷数（Y）' if expected_label == '不合格品数（Y）' else '不合格品数（Y）'
        assert other not in labels
    finally:
        top.destroy()
        app.table.destroy()
