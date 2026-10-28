"""Factorial ANOVA error partition for replicated cells and complete blocks."""
from collections import defaultdict

import numpy as np


def partition_factorial_error(response, cells, blocks):
    """Split saturated cell/block residuals from within-cell pure error.

    Blocked DOE callers validate complete, balanced blocks before using this
    partition; block-by-cell residuals are not pure error.
    """
    # shortcut: only complete balanced blocks are supported; use weighted projections if expanded.
    groups = defaultdict(list)
    cell_groups = defaultdict(list)
    block_groups = defaultdict(list)
    use_blocks = blocks is not None and len(set(blocks)) > 1
    for index, cell in enumerate(cells):
        value = float(response[index])
        key = (blocks[index], cell) if use_blocks else cell
        groups[key].append(value)
        cell_groups[cell].append(value)
        if use_blocks:
            block_groups[blocks[index]].append(value)

    pure_error_df = sum(len(values) - 1 for values in groups.values())
    pure_error_ss = sum(float(np.sum((values - np.mean(values)) ** 2))
                        for values in (np.asarray(group) for group in groups.values()))
    block_error_ss = 0.0
    block_error_df = 0
    if use_blocks:
        grand = float(np.mean(response))
        block_means = {block: float(np.mean(values))
                       for block, values in block_groups.items()}
        cell_means = {cell: float(np.mean(values)) for cell, values in cell_groups.items()}
        block_error_ss = sum(
            len(values) * (float(np.mean(values)) - block_means[block]
                           - cell_means[cell] + grand) ** 2
            for (block, cell), values in groups.items())
        block_error_df = len(response) - (len(cell_groups) + len(block_groups) - 1) - pure_error_df

    return {
        "pure_error_ss": pure_error_ss,
        "pure_error_df": pure_error_df,
        "block_error_ss": block_error_ss,
        "block_error_df": block_error_df,
    }
