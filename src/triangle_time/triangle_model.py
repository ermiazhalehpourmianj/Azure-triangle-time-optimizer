"""
Pure math for the triangle time model.

No I/O, no Azure. Just:
- Conversions between times and proportions
- Entropy / mixing calculation
- Time prediction given model parameters
"""

from __future__ import annotations

import math
from typing import Tuple

from .schema import Task, ModelParams


def proportions_from_times(
    T_gov: float,
    T_azure: float,
    T_ds: float,
) -> Tuple[float, float, float]:
    """
    Convert raw times in each dimension into barycentric proportions.

    If total time is zero or negative, all proportions are set to 0.
    """
    total = T_gov + T_azure + T_ds
    if total <= 0.0:
        return 0.0, 0.0, 0.0
    return T_gov / total, T_azure / total, T_ds / total


def update_task_proportions(task: Task) -> Task:
    """
    Ensure T_total and p_* are populated on the Task.

    - If T_total is None, compute as T_gov + T_azure + T_ds.
    - If any of p_* is None, compute from times.
    """
    if task.T_total is None:
        task.T_total = task.T_gov + task.T_azure + task.T_ds

    # Only recompute proportions if any is missing
    if task.p_gov is None or task.p_azure is None or task.p_ds is None:
        p_gov, p_azure, p_ds = proportions_from_times(
            task.T_gov,
            task.T_azure,
            task.T_ds,
        )
        task.p_gov = p_gov
        task.p_azure = p_azure
        task.p_ds = p_ds

    return task


def entropy_from_proportions(
    p_gov: float,
    p_azure: float,
    p_ds: float,
) -> float:
    """
    Compute a Shannon-style entropy H(p) = - sum p_i log p_i.

    Uses natural log. Terms with p_i <= 0 are treated as zero.
    """
    entropy = 0.0
    for p in (p_gov, p_azure, p_ds):
        if p > 0.0:
            entropy -= p * math.log(p)
    return entropy


def predict_time_from_proportions(
    p_gov: float,
    p_azure: float,
    p_ds: float,
    params: ModelParams,
) -> float:
    """
    Predict total time given triangle proportions and model parameters.

    Base model (no entropy):
        T_pred = p_G * T_gov_star + p_A * T_azure_star + p_D * T_ds_star

    If params.use_entropy is True:
        T_pred += eta * H(p)
    """
    base = (
        p_gov * params.T_gov_star
        + p_azure * params.T_azure_star
        + p_ds * params.T_ds_star
    )

    if params.use_entropy:
        H = entropy_from_proportions(p_gov, p_azure, p_ds)
        return base + params.eta * H
    return base


def predict_time_for_task(
    task: Task,
    params: ModelParams,
) -> float:
    """
    Predict total time for a Task.

    This will update the task's T_total and p_* fields if missing.
    """
    task = update_task_proportions(task)

    if task.p_gov is None or task.p_azure is None or task.p_ds is None:
        # Should not happen after update, but guard anyway.
        return 0.0

    return predict_time_from_proportions(
        task.p_gov,
        task.p_azure,
        task.p_ds,
        params,
    )
