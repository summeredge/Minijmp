"""固定计算和返回 AST；G6 展示及 G18 绘图性能变更由专项数值/协议测试保护。"""
import ast
import hashlib
import json
from pathlib import Path

import pytest
from source_baselines import normalize_review003

ROOT = Path(__file__).resolve().parents[1]
BASELINE = json.loads((ROOT / 'tests/fixtures/g3_computation_baseline.json').read_text(encoding='utf-8'))


class WithoutReports(ast.NodeTransformer):
    def visit_If(self, node):
        names = {n.id for n in ast.walk(node.test) if isinstance(n, ast.Name)}
        if names & {'print_out', 'print_residual'}:
            assert not node.orelse
            return None
        return self.generic_visit(node)

    def visit_Expr(self, node):
        if isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Name):
            if node.value.func.id in {'print', 'print_port'}:
                return None
        if (isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Attribute)
                and ast.unparse(node.value.func) == 'self.app.print'):
            return None
        return self.generic_visit(node)

    def visit_Assign(self, node):
        if len(node.targets) == 1 and isinstance(node.targets[0], ast.Name) and node.targets[0].id == 'print':
            return None
        return self.generic_visit(node)


def computation_dump(source, function):
    tree = ast.parse(source)
    if '.' in function:
        owner, function = function.split('.')
        tree = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == owner)
    node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == function)
    if isinstance(tree, ast.ClassDef) and tree.name == 'Chi2PropDialog':
        body = []
        calls = 0
        for statement in node.body:
            # values 是 G9 新增的报告原值；清洗、概率校验和参考行计算全部保留。
            if isinstance(statement, ast.Assign):
                target = statement.targets[0]
                if isinstance(statement.value, ast.Call) and isinstance(statement.value.func, ast.Name) and statement.value.func.id == 'chi_square':
                    call = statement.value
                    calls += 1
                    for keyword in call.keywords:
                        if keyword.arg == 'print_out':
                            keyword.value = ast.Constant(False)
                    body.append(ast.Expr(call))
                    continue
                if (isinstance(target, ast.Name) and target.id in {'t', 'rows', 'table', 'values'}
                        or isinstance(target, (ast.Attribute, ast.Subscript)) and ast.unparse(target).startswith(('t.', 'table.'))):
                    continue
            if isinstance(statement, ast.Expr) and isinstance(statement.value, ast.Call):
                call = statement.value
                if isinstance(call.func, ast.Name) and call.func.id == 'chi_square':
                    calls += 1
                    for keyword in call.keywords:
                        if keyword.arg == 'print_out':
                            keyword.value = ast.Constant(False)
                elif isinstance(call.func, ast.Attribute) and ast.unparse(call.func).startswith(('t.', 'table.')):
                    continue
            if isinstance(statement, ast.For) and isinstance(statement.target, ast.Name) and statement.target.id == 'i':
                assert ast.unparse(statement.iter) == 'range(len(cnts))'
                assert all(isinstance(s, ast.Expr) and isinstance(s.value, ast.Call)
                           and ast.unparse(s.value.func) in {'t.add_row', 'rows.append', 'values.append'} for s in statement.body)
                continue
            body.append(statement)
        assert calls == 1
        node.body = body
    if function == 'two_way_anova':
        normalize_review003(node)
    return ast.dump(WithoutReports().visit(node), include_attributes=False)


@pytest.mark.parametrize('entry', BASELINE, ids=lambda x: x['file'] + '::' + x['function'])
def test_computation_return_and_plot_ast_matches_g3_start(entry):
    source = (ROOT / 'code' / entry['file']).read_text(encoding='utf-8')
    actual = hashlib.sha256(computation_dump(source, entry['function']).encode('utf-8')).hexdigest()
    assert actual == entry['sha256']
