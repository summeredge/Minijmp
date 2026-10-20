"""使用项目解释器从仓库根目录执行，生成可复查的真实表格文件。"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / 'code'), str(ROOT / 'tests')]

from test_g11_quality_tables import report
from stat_table import StatTable, export_excel, export_png


def main():
    destination = Path(__file__).resolve().parent
    cases = [
        ('GRR方差分量', ('grr', 'aiag', True, 'Auto'), 1),
        ('GRR测量系统评价', ('grr', 'aiag', True, 'Auto'), 2),
        ('EMP补充统计', ('direct', 'emp', True, True), 2),
        ('嵌套ANOVA', ('nested', None), 0),
        ('过程能力指数', ('cpk', True, 'unbalanced', True), 1),
        ('U图逐点明细', ('spc', 'U'), 1),
        ('NP图逐点明细', ('spc', 'NP'), 1),
    ]
    for name, case, index in cases:
        _, lines = report(case)
        table = [line for line in lines if isinstance(line, StatTable)][index]
        export_excel(table, destination / (name + '.xlsx'))
        export_png(table, destination / (name + '.png'))
        (destination / (name + '.txt')).write_text('\n'.join(lines) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
