from pathlib import Path
import ast


ROOT = Path(__file__).resolve().parent / 'fixtures' / 'source_baselines'


def read_source_baseline(revision, path):
    return (ROOT / revision / f'{path}.txt').read_text(encoding='utf-8')


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
