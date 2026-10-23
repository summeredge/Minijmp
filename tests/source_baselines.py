from pathlib import Path
import ast
import hashlib
import json


ROOT = Path(__file__).resolve().parent / 'fixtures' / 'source_baselines'


def read_source_baseline(revision, path):
    return (ROOT / revision / f'{path}.txt').read_text(encoding='utf-8')


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
