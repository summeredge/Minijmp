"""在 G1 文本窗口实际字体中验证 G3 表格对齐。"""
import importlib

import pytest

from test_g1_text_output import viewer

DATA = [1., 2., 4., 5., 7., 8.]
OTHER = [2., 4., 3., 8., 6., 10.]


@pytest.mark.parametrize('module,name,args,options', [
    ('linear_fit', 'linear_fit', [DATA, OTHER], {}),
    ('linear_fit', 'linear_fit', [[1, 1, 2, 2, 3, 3], OTHER], {}),
    ('ortho_fit', 'orthogonal_fit', [DATA, OTHER], {'print_residual': True}),
    ('one_way_ANOVA', 'one_way_anova', [[DATA, OTHER], ['中文组甲', 'Long mixed 变量乙']], {}),
    ('one_way_ANOVA', 'JMP_ANOVA_t_test', [[DATA, OTHER], ['中文组甲', 'Long mixed 变量乙']], {}),
    ('two_way_anova', 'two_way_anova', [[[[1, 2], [3, 4]], [[2, 4], [5, 8]]]],
        {'name_a': '温度 Temperature', 'name_b': '压力 Pressure'}),
    ('two_way_anova', 'two_way_anova', [[[[1, 2], [3, 4]], [[2, 4], [5, 8]]]],
        {'interaction': False}),
    ('chi_sq', 'chi_square', [[[2, 1], [0, 2], [1, 0]]],
        {'print_table': True, 'rKeys': ['中文类别一', 'Long mixed 变量乙', '类别三'], 'cKeys': ['成功', '失败']}),
    *[('dist_fit', name, [DATA], {}) for name in
        ['fit_norm', 'fit_t', 'fit_gamma', 'fit_weibull', 'fit_lognorm', 'fit_expon']],
    ('dist_fit', 'compare_dist', [DATA], {}),
    ('GRR', 'grr_nested', [], {'y': [1, 2, 3, 4, 5, 7, 8, 10],
        'op': ['甲'] * 4 + ['乙'] * 4, 'part': ['A', 'A', 'B', 'B', 'C', 'C', 'D', 'D']}),
])
def test_g3_tables_have_same_pixel_separator_positions(viewer, module, name, args, options):
    lines = []
    getattr(importlib.import_module(module), name)(*args, print_out=True,
        print_port=lines.append, **options)
    viewer.add_txt('\n'.join(lines))
    viewer.main.update()
    count = 0
    for chunk in lines:
        positions = [[viewer.output_font.measure(line[:index])
                      for index, char in enumerate(line) if char == '|']
                     for line in chunk.splitlines() if line.startswith('|')]
        if positions:
            assert all(row == positions[0] for row in positions), (module, name, chunk)
            count += 1
    assert count > 0
