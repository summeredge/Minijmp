import math

import pytest
from openpyxl import load_workbook

import GRR
from doe_mixture import MixtureSpec, mixture_metadata
from doe_mixture_designs import create_mixture_design
from doe_mixture_optimize import optimize_mixture
from doe_mixture_constraints import ComponentSpec
from stat_table import StatTable, export_excel
from utilities import d2_2D, format_stat


@pytest.mark.parametrize('k', [1, 2, 3, 4])
def test_two_replicate_d2_matches_independent_average_range_moments(k):
    # For R=|X1-X2|, E[R]=2/sqrt(pi), Var[R]=2-4/pi;
    # averaging k independent subgroup ranges divides Var[R] by k.
    expected = math.sqrt(4 / math.pi + (2 - 4 / math.pi) / k)
    assert d2_2D(2, k) == round(expected, 3)


def test_grr_master_three_subgroups_matches_reference_and_report(
        monkeypatch, tmp_path):
    tables = []

    def capture_table(*args, **kwargs):
        table = StatTable(*args, **kwargs)
        tables.append(table)
        return table

    monkeypatch.setattr(GRR, 'StatTable', capture_table)
    lines = []
    result = GRR.grr_master(
        y=[0, 1, 0, 1, 0, 1],
        part=['P1', 'P1', 'P2', 'P2', 'P3', 'P3'],
        op=None, mode='XBAR/R', print_out=True, print_port=lines.append)

    expected_d2 = round(math.sqrt(4 / math.pi + (2 - 4 / math.pi) / 3), 3)
    expected_ev = 1 / expected_d2**2
    assert expected_d2 == 1.231
    assert result['EV'] == pytest.approx(expected_ev)

    table = next(item for item in tables if item.title == '方差分量')
    row = next(i for i, values in enumerate(table.values)
               if values[0] == '重复性 (EV)')
    assert table.values[row][1] == pytest.approx(result['EV'])
    assert table.display[row][1] == format_stat(result['EV'])
    assert str(table) in lines

    path = tmp_path / 'grr.xlsx'
    export_excel(table, path)
    workbook = load_workbook(path, data_only=True)
    try:
        exported = next(values for values in workbook.active.iter_rows(values_only=True)
                        if values[0] == '重复性 (EV)')
        assert exported[1] == pytest.approx(result['EV'])
    finally:
        workbook.close()


def test_grr_master_complete_crossed_design_uses_group_count():
    y, parts, operators = [], [], []
    for operator_index in range(2):
        for part_index in range(3):
            center = 10 * part_index + operator_index
            y.extend([center, center + 1])
            parts.extend([f'P{part_index}'] * 2)
            operators.extend([f'O{operator_index}'] * 2)

    result = GRR.grr_master(y=y, part=parts, op=operators,
                           mode='XBAR/R', print_out=False)
    expected_d2 = round(math.sqrt(4 / math.pi + (2 - 4 / math.pi) / 6), 3)
    assert result['EV'] == pytest.approx(1 / expected_d2**2)


def four_response_mixture():
    responses = ('Y1', 'Y2', 'Y3', 'Y4')
    spec = MixtureSpec(
        'MIX', (ComponentSpec('A', 'A'), ComponentSpec('B', 'B'),
                ComponentSpec('C', 'C')), responses,
        'simplex_lattice', 3, seed=2)
    frame, _ = create_mixture_design(spec)
    a = frame['设定_A']
    for index, offset in enumerate((0.0, 0.1, 0.2, 0.3), 1):
        frame[f'响应_Y{index}'] = a + offset
    return frame, mixture_metadata(frame, spec), responses


@pytest.mark.parametrize('weight', [1, 10])
def test_mixture_multiresponse_log_score_improves_underflow_start(weight):
    frame, metadata, responses = four_response_mixture()
    objectives = [
        {'response': name, 'goal': 'maximize', 'lower': -1,
         'upper': 1e100, 'weight': weight}
        for name in responses
    ]

    start = [0.0, 1 / 3, 2 / 3]
    result = optimize_mixture(frame, metadata, objectives, starts=[start])

    start_log = math.fsum(
        weight * math.log((offset + 1) / (1e100 + 1))
        for offset in (0.0, 0.1, 0.2, 0.3)) / 4
    best_log = math.fsum(
        weight * math.log((1 + offset + 1) / (1e100 + 1))
        for offset in (0.0, 0.1, 0.2, 0.3)) / 4
    assert result['success'] and result['feasible']
    assert result['components']['A'] == pytest.approx(1, abs=1e-6)
    assert -result['solver_objective'] > start_log
    assert result['solver_objective'] == pytest.approx(-best_log, rel=1e-8)
    if weight == 1:
        assert result['aggregate_desirability'] == pytest.approx(
            math.exp(best_log), rel=1e-8, abs=0)
    else:
        assert result['aggregate_desirability'] == 0
        assert '综合期望为正但低于浮点可表示范围' in result['status']


def test_mixture_optimizer_prefers_positive_candidate_over_true_zero():
    frame, metadata, responses = four_response_mixture()
    objectives = [
        {'response': name, 'goal': 'maximize', 'lower': 1e-12,
         'upper': 1e100, 'weight': 10}
        for name in responses
    ]
    result = optimize_mixture(
        frame, metadata, objectives,
        starts=[[0.0, 1 / 3, 2 / 3], [0.25, 0.25, 0.5]])

    assert result['success'] and result['feasible']
    assert result['components']['A'] == pytest.approx(1, abs=1e-6)
    assert result['aggregate_desirability'] == 0
    assert '综合期望为正但低于浮点可表示范围' in result['status']
