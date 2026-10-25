from pathlib import Path
import ast
import copy
import hashlib
import json


ROOT = Path(__file__).resolve().parent / 'fixtures' / 'source_baselines'


def read_source_baseline(revision, path):
    return (ROOT / revision / f'{path}.txt').read_text(encoding='utf-8')


def normalize_p2_legacy(tree, module, baseline):
    """仅接管 REVIEW-018/019 的精确函数；含报告在内的任何后续变动均拒绝。"""
    name = {'cpk.py': 'cpk', 'qc_dialog.py': 'CpkSubDialog.apply'}[module]
    owner, original = tree, baseline
    if '.' in name:
        cls, name = name.split('.')
        owner, original = [next(n for n in t.body if isinstance(n, ast.ClassDef)
                                and n.name == cls) for t in (tree, baseline)]
    node = next(n for n in owner.body if isinstance(n, ast.FunctionDef) and n.name == name)
    hashes = json.loads((ROOT.parent / 'p2_guard_nodes.json').read_text())
    key = f'{module}:{"CpkSubDialog.apply" if module == "qc_dialog.py" else name}'
    assert hashlib.sha256(ast.dump(node).encode()).hexdigest() == hashes[key], key
    before = next(n for n in original.body if isinstance(n, ast.FunctionDef) and n.name == name)
    owner.body[owner.body.index(node)] = copy.deepcopy(before)
    return tree


def normalize_p1_numeric(tree, module, baseline):
    """校验已审查的完整函数后还原旧节点；其他 AST 仍由原守卫比较。"""
    names = {'utilities.py': ('pearson_correlation', 'c4_values'),
             'cpk.py': ('cpl_cpu_95',)}[module]
    hashes = json.loads((ROOT.parent / 'p1_numeric_nodes.json').read_text())
    for name in names:
        nodes = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name]
        assert len(nodes) == 1, name
        node = nodes[0]
        assert hashlib.sha256(ast.dump(node).encode()).hexdigest() == hashes[f'{module}:{name}'], name
        original = next(n for n in baseline.body if isinstance(n, ast.FunctionDef) and n.name == name)
        tree.body[tree.body.index(node)] = copy.deepcopy(original)
    if module == 'utilities.py':
        current = ast.parse('from scipy.special import gammaln').body[0]
        matches = [i for i, n in enumerate(tree.body) if ast.dump(n) == ast.dump(current)]
        assert len(matches) == 1
        tree.body[matches[0]] = ast.parse('from scipy.special import gamma').body[0]
    return tree


def normalize_column_memory(tree, module):
    """仅还原逐项审查的列记忆增量；旧计算、验证和输出继续冻结。"""
    def remove_exact(owner, source):
        expected = ast.dump(ast.parse(source).body[0])
        matches = [n for n in ast.walk(owner) if ast.dump(n) == expected]
        assert len(matches) == 1, source
        target = matches[0]
        for parent in ast.walk(owner):
            for _, value in ast.iter_fields(parent):
                if isinstance(value, list) and target in value:
                    value.remove(target)
                    return

    classes = {n.name: n for n in tree.body if isinstance(n, ast.ClassDef)}
    if module == 'dialog.py':
        for source in ('import json', 'import os', 'from pathlib import Path',
                       'from numbers import Integral', 'import warnings',
                       'from pandas.api.types import is_numeric_dtype, is_bool_dtype'):
            remove_exact(tree, source)
        remove_exact(tree, r"_COLUMN_SETTINGS_KEY = r'Software\MiniJMP\ColumnSelections'")
        hashes = json.loads((ROOT.parent / 'review015_column_memory_nodes.json').read_text())
        for key, expected in hashes.items():
            owner = classes['Dialogs'] if key.startswith('Dialogs.') else tree
            node = next(n for n in owner.body if isinstance(n, ast.FunctionDef)
                        and n.name == key.split('.')[-1])
            assert hashlib.sha256(ast.dump(node).encode()).hexdigest() == expected, key
            owner.body.remove(node)
        remove_exact(classes['Dialogs'], 'column_roles = ()')
        remove_exact(classes['Dialogs'], 'self._init_column_selection(parent)')
        return tree
    roles = {
        'qc_dialog.py': {
            'GRR_Nested_Dialog': "(('xvar', True), ('yvar', False), ('ovar', False))",
            'GRRDialog': "(('xvar', True), ('yvar', False), ('ovar', False))",
            'CpkDialog': "(('xvar', True),)",
            'CpkSubDialog': "(('xvar', True), ('subid', False))",
            'TIDialog': "(('xvar', True),)"},
        'ctrlchart_dialog.py': {
            'IMRDialog': "(('xvar', True), ('xlabelID', False))",
            'XBRDialog': "(('xvar', True), ('gid', False), ('xlabelID', False))",
            'NPDialog': "(('xvar', True), ('xlabelID', False))",
            'PDialog': "(('xvar', True), ('N', True), ('xlabelID', False))",
            'CDialog': "(('xvar', True), ('xlabelID', False))",
            'UDialog': "(('xvar', True), ('N', True), ('xlabelID', False))"}}
    for name, value in roles[module].items():
        remove_exact(classes[name], 'column_roles = ' + value)
    if module == 'ctrlchart_dialog.py':
        # 改善前后对比复用普通控制图窗口的判异入口，只新增该关键字。
        function = next(n for n in classes['IMRDialog'].body
                        if isinstance(n, ast.FunctionDef) and n.name == 'apply')
        calls = [n for n in ast.walk(function) if isinstance(n, ast.Call)
                 and ast.unparse(n.func) == 'x_plot']
        assert len(calls) == 1
        keywords = [n for n in calls[0].keywords if n.arg == 'detect_rules']
        assert len(keywords) == 1 and ast.unparse(keywords[0].value) == 'True'
        calls[0].keywords.remove(keywords[0])
        # 阶段对比只在三个变量图窗口追加可选设置，移除后应与原窗口一致。
        remove_exact(tree, 'import stage_compare')
        remove_exact(tree, "STAGE_CHARTS = {'IMRDialog': 'I-MR', "
                           "'XBRDialog': 'Xbar-R', 'XBSDialog': 'Xbar-S'}")
        create = next(n for n in classes['IMRDialog'].body
                      if isinstance(n, ast.FunctionDef) and n.name == 'createWidgets')
        remove_exact(create, 'if type(self).__name__ in STAGE_CHARTS:\n'
                             '    stage_compare.settings(self, m)')
        remove_exact(function, 'if getattr(self, \'stage_compare\', None) is not None '
                               'and self.stage_compare.get():\n'
                               '    try:\n'
                               '        stage_compare.run(self, STAGE_CHARTS[type(self).__name__])\n'
                               '    except Exception as exc:\n'
                               '        self.error(str(exc))\n'
                               '    return')
    names = ('GRR_Nested_Dialog', 'GRRDialog', 'CpkDialog', 'CpkSubDialog') if module == 'qc_dialog.py' else ('IMRDialog', 'NPDialog', 'CDialog')
    for name in names:
        function = next(n for n in classes[name].body if isinstance(n, ast.FunctionDef) and n.name == 'apply')
        remove_exact(function, 'self.remember_columns(roles=None if "ID" in m else ("xvar",))'
                     if name == 'CpkSubDialog' else 'self.remember_columns()')
    if module == 'qc_dialog.py':
        function = next(n for n in classes['TIDialog'].body if isinstance(n, ast.FunctionDef) and n.name == 'apply')
        remove_exact(function, 'if result is not None and None in [mean, n, std]:\n    self.remember_columns()')
        assignment = next(n for n in function.body if isinstance(n, ast.Assign)
                          and ast.unparse(n.targets[0]) == 'result')
        assert isinstance(assignment.value, ast.Call) and ast.unparse(assignment.value.func) == 'ti_norm'
        function.body[function.body.index(assignment)] = ast.Expr(value=assignment.value)
    return tree


def normalize_review003(tree):
    """只还原 REVIEW-003 的已验差异；其余 AST 冻结继续生效。

    新数值及秩亏边界由 test_review003_anova 的独立矩阵检验保护。
    """
    rank_guard = ("if full_model.model.rank < full_model.model.exog.shape[1]:\n"
                  "    raise ValueError('双因素方差分析模型秩亏，无法独立估计所选效应。')")
    for function in ast.walk(tree):
        if not isinstance(function, ast.FunctionDef):
            continue
        if function.name in ('SSA_SSB', 'SSA_SSB_simple'):
            function.body = [node for node in function.body
                             if ast.dump(node) != ast.dump(ast.parse(rank_guard).body[0])]
        if function.name == 'SSA_SSB_simple':
            for node in function.body:
                if isinstance(node, ast.Return) and ast.unparse(node.value) == (
                        '(anova_table.sum_sq.iloc[1], anova_table.sum_sq.iloc[2], full_model.ssr)'):
                    node.value.elts.pop()
        if function.name == 'two_way_anova':
            for node in function.body:
                if isinstance(node, ast.If) and ast.unparse(node.test) == 'interaction':
                    if [ast.unparse(n) for n in node.orelse] == [
                            'SSA, SSB, SSE = SSA_SSB_simple(d)', 'SSAB = 0']:
                        node.orelse = ast.parse(
                            'SSA, SSB = SSA_SSB_simple(d)\nSSAB = 0\nSSE = SST - SSB - SSA - SSAB').body
    return tree
