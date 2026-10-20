"""G12 有界源码清单：静态生产位置不是运行次数，也不是逻辑表张数。

只解析 code/**/*.py，不导入应用、不执行统计或 GUI。位置使用限定函数名及
同类事件序号；行号仅用于失败诊断。清单必须人工分类，测试不自动更新夹具。
"""
import ast
from collections import Counter
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = Path(__file__).with_name('fixtures') / 'g12_table_inventory.json'
CONSTRUCTORS = {'gen_table', 'PrettyTable', 'PT', 'StatTable'}
TEXT_METHODS = {'to_string', 'as_text', 'get_string', 'tabulate', 'SimpleTable'}


def scopes(tree, prefix=''):
    """每个节点只属于最近的函数/类，避免外层重复计算嵌套 tTest。"""
    local = []
    children = []

    def collect(node):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            children.append(node)
            return
        local.append(node)
        for child in ast.iter_child_nodes(node):
            collect(child)

    for node in tree.body:
        collect(node)
    yield prefix or '<module>', local
    for child in children:
        name = f'{prefix}.{child.name}' if prefix else child.name
        yield from scopes(child, name)


def scan_source(source):
    tree = ast.parse(source)
    aliases = {name: name for name in CONSTRUCTORS | TEXT_METHODS}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            for item in node.names:
                aliases[item.asname or item.name] = item.name
        elif isinstance(node, ast.Import):
            for item in node.names:
                aliases[item.asname or item.name] = item.name

    def call_name(node):
        name = ast.unparse(node)
        head, dot, tail = name.partition('.')
        return (aliases.get(head, head) + dot + tail).split('.')[-1]

    imports = aliases.copy()
    result, outputs = {}, {}
    for scope, nodes in scopes(tree):
        aliases = imports.copy()
        calls = sorted((n for n in nodes if isinstance(n, ast.Call)),
                       key=lambda n: (n.lineno, n.col_offset))
        assignments = [n for n in nodes if isinstance(n, (ast.Assign, ast.AnnAssign))]
        # 只追踪本函数显式构造的表及其文本别名，不按 table/t 等变量名猜测。
        kinds = {}

        def kind(node):
            if node is None:
                return ''
            if isinstance(node, ast.Name):
                return kinds.get(node.id, '')
            if isinstance(node, ast.Constant):
                return 'legacy' if is_table_literal(node) else ''
            if isinstance(node, ast.Call):
                name = call_name(node.func)
                if name == 'StatTable' or name == 'model_summary_tables':
                    return 'structured'
                if name in CONSTRUCTORS or name in TEXT_METHODS:
                    return 'legacy'
                if name == 'pred_table':
                    return 'matrix'
                if name == 'summary' and ast.unparse(node.func) != 'self.summary':
                    return 'native'
                if name in ('enumerate', 'iter', 'list', 'tuple') and node.args:
                    return kind(node.args[0])
                if name in ('str', 'format', 'join', 'get_string', 'as_text'):
                    if any(kind(arg) for arg in node.args) or (
                            isinstance(node.func, ast.Attribute) and kind(node.func.value)):
                        return 'legacy'
            if isinstance(node, (ast.BinOp, ast.JoinedStr, ast.FormattedValue)):
                return 'legacy' if is_table_literal(node) or any(
                    kind(c) for c in ast.iter_child_nodes(node)) else ''
            return ''

        # 固定点只处理局部赋值/导入别名；不声称解析任意跨函数动态数据流。
        changed = True
        while changed:
            changed = False
            for node in assignments:
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                for target in targets:
                    if not isinstance(target, ast.Name):
                        continue
                    value = kind(node.value)
                    if value and target.id not in kinds:
                        kinds[target.id] = value
                        changed = True
                    if isinstance(node.value, (ast.Name, ast.Attribute)):
                        name = call_name(node.value)
                        if name in CONSTRUCTORS | {'print', 'print_port'} and aliases.get(target.id) != name:
                            aliases[target.id] = name
                            changed = True
            for node in nodes:
                if isinstance(node, (ast.For, ast.AsyncFor)) and kind(node.iter) == 'structured':
                    target = node.target.elts[-1] if isinstance(node.target, ast.Tuple) else node.target
                    if isinstance(target, ast.Name) and target.id not in kinds:
                        kinds[target.id] = 'structured'
                        changed = True

        events, ports = [], Counter()
        counts = Counter()

        def record(label, node):
            counts[label] += 1
            events.append({'site': f'{label}#{counts[label]}', 'line': node.lineno})

        for node in calls:
            name = call_name(node.func)
            if name in CONSTRUCTORS:
                record('construct:' + ('PrettyTable' if name == 'PT' else name), node)
            elif name in TEXT_METHODS or name == 'pred_table' or (
                    name == 'summary' and ast.unparse(node.func) != 'self.summary'):
                record('table_text:' + name, node)
            sink = ast.unparse(node.func)
            is_port = name in ('print', 'print_port')
            is_text_sink = name in ('insert', 'add_txt', 'add_table', 'write')
            if is_port or is_text_sink:
                values = [kind(arg) for arg in node.args]
                tabular = next((v for v in values if v), '')
                if tabular:
                    record(f'emit:{tabular}:{name}', node)
                elif any(is_table_literal(arg) for arg in node.args):
                    record('emit:literal:' + name, node)
                if is_port:
                    ports[sink] += 1
            for keyword in node.keywords:
                if keyword.arg == 'print_port':
                    ports['forward:' + ast.unparse(keyword.value)] += 1
        if events:
            result[scope] = events
        if ports:
            outputs[scope] = dict(sorted(ports.items()))
    return result, outputs


def is_table_literal(node):
    """只标记多行 ASCII 框/多行制表符；章节、解释和单行 tab 不是表。"""
    strings = [n.value for n in ast.walk(node)
               if isinstance(n, ast.Constant) and isinstance(n.value, str)]
    return any(sum('|' in line for line in text.splitlines()) >= 2 or
               sum('\t' in line for line in text.splitlines()) >= 2
               for text in strings + [''.join(strings)])


def inventory():
    return json.loads(FIXTURE.read_text(encoding='utf-8'))


def test_all_python_files_and_production_sites_are_classified():
    expected = inventory()
    paths = sorted(p.relative_to(ROOT / 'code').as_posix()
                   for p in (ROOT / 'code').rglob('*.py'))
    assert paths == expected['files'], 'code/ 文件集合变化：请审计新增/移除文件'
    actual = {}
    locations = {}
    for path in paths:
        found, _ = scan_source((ROOT / 'code' / path).read_bytes())
        for scope, events in found.items():
            key = f'{path}::{scope}'
            actual[key] = [event['site'] for event in events]
            locations[key] = events
    reviewed = {key: row['sites'] for key, row in expected['producers'].items()}
    differences = {key: {'expected': reviewed.get(key), 'actual': actual.get(key),
                         'locations': locations.get(key)}
                   for key in actual.keys() | reviewed.keys()
                   if actual.get(key) != reviewed.get(key)}
    assert not differences, f'未分类或已变化的表格生产/输出位置：{differences}'


def test_inventory_metadata_and_real_test_references():
    data = inventory()
    for key, row in data['producers'].items():
        assert row['classification'] in ('statistical', 'compatibility', 'data_matrix',
                                          'error_box')
        assert row['entry_points'] and row['titles'] and row['status']
        if row['classification'] == 'statistical':
            assert not row['exception_reason']
            assert row['logical_tables'] == len(row['titles'])
            assert not any(site.startswith(('emit:legacy:', 'emit:native:', 'emit:literal:'))
                           for site in row['sites']), key
        else:
            assert row['exception_reason']
            assert row['logical_tables'] == 0
        assert row['tests'], key
        for reference in row['tests']:
            path, _, function = reference.partition('::')
            tree = ast.parse((ROOT / path).read_bytes())
            assert any(isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == function
                       for n in ast.walk(tree)), reference
    assert data['counting_rules']['source_positions']
    assert data['counting_rules']['logical_tables']


@pytest.mark.parametrize('source,labels', [
    ('from utilities import gen_table as build\ndef f():\n t=build([["x"],[1]])\n print(str(t))',
     ['construct:gen_table#1', 'emit:legacy:print#1']),
    ('import prettytable as pt\ndef f():\n t=pt.PrettyTable()\n alias=t\n print("\\n"+str(alias))',
     ['construct:PrettyTable#1', 'emit:legacy:print#1']),
    ('from stat_table import StatTable as S\ndef f():\n print_port(S(title="x",headers=["x"],values=[[1]]))',
     ['emit:structured:print_port#1', 'construct:StatTable#1']),
    ('def f():\n t=gen_table([["x"],[1]])\n app.print(t)\n app.print(f"{t}")',
     ['construct:gen_table#1', 'emit:legacy:print#1', 'emit:legacy:print#2']),
    ('def f():\n p=gen_table\n t=p([])\n app.print(t.get_string())',
     ['construct:gen_table#1', 'emit:legacy:print#1', 'table_text:get_string#1']),
    ('def f():\n print(df.to_string())',
     ['emit:legacy:print#1', 'table_text:to_string#1']),
    ('def f():\n print("a\\tb\\n1\\t2")', ['emit:legacy:print#1']),
    ('def f():\n print("| A | B |\\n| 1 | 2 |")', ['emit:legacy:print#1']),
    ('def f():\n report="| A |\\n"+"| 1 |"\n emit=app.print\n emit(report)',
     ['emit:legacy:print#1']),
    ('def f():\n print("---- 标题 ----")\n print(str(3))\n print("mean=1\\tSD=2")', []),
    ('def f():\n table="普通字符串"\n print(table)\n print("p 值是在 H0 下的概率")', []),
])
def test_scanner_detects_new_constructors_and_legacy_emits_without_string_false_positives(source, labels):
    found, _ = scan_source(source)
    assert [n['site'] for n in found.get('f', [])] == labels


def test_nested_scopes_and_whitespace_are_not_source_identity():
    source = 'def outer():\n def inner():\n  t=PT()\n  print(str(t))\n'
    before, _ = scan_source(source)
    after, _ = scan_source('\n# 无关说明\n' + source.replace('PT()', 'PT(  )'))
    assert set(before) == {'outer.inner'}
    assert {key: [e['site'] for e in value] for key, value in before.items()} == {
        key: [e['site'] for e in value] for key, value in after.items()}


def test_adding_a_constructor_or_a_legacy_emit_changes_the_inventory():
    before, _ = scan_source('def f():\n t=gen_table([])\n print(StatTable(t,"x",["x"],[]))')
    for extra in ('\n t2=gen_table([])', '\n print(str(t))'):
        after, _ = scan_source('def f():\n t=gen_table([])\n print(StatTable(t,"x",["x"],[]))' + extra)
        assert [e['site'] for e in before['f']] != [e['site'] for e in after['f']]
