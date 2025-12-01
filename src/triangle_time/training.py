"""
Model training and evaluation for the triangle time system.

Responsibilities:
- Fit ModelParams (T_gov_star, T_azure_star, T_ds_star, eta)
  from historical tasks.
- Evaluate model quality on a dataset (MAE, RMSE, etc.).
"""

from __future__ import annotations

from typing import Dict, Iterable, List, Sequence

import numpy as np

from .schema import Task, ModelParams
from .triangle_model import (
    proportions_from_times,
    entropy_from_proportions,
    predict_time_for_task,
)


def _prepare_training_matrices(
    tasks: Sequence[Task],
    use_entropy: bool,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Build design matrix X and target vector y for least squares.

    X columns:
    - p_gov
    - p_azure
    - p_ds
    - (optional) H(p) if use_entropy is True

    y: T_total
    """
    X_rows: List[List[float]] = []
    y_vals: List[float] = []

    for t in tasks:
        # Compute total if missing
        if t.T_total is None or t.T_total <= 0.0:
            total = t.T_gov + t.T_azure + t.T_ds
        else:
            total = t.T_total

        if total <= 0.0:
            # Skip degenerate tasks
            continue

        p_gov, p_azure, p_ds = (
            (t.p_gov, t.p_azure, t.p_ds)
            if t.p_gov is not None and t.p_azure is not None and t.p_ds is not None
            else proportions_from_times(t.T_gov, t.T_azure, t.T_ds)
        )

        row = [p_gov, p_azure, p_ds]

        if use_entropy:
            H = entropy_from_proportions(p_gov, p_azure, p_ds)
            row.append(H)

        X_rows.append(row)
        y_vals.append(total)

    if not X_rows:
        raise ValueError("No valid tasks for training (all had zero or missing time).")

    X = np.asarray(X_rows, dtype=float)
    y = np.asarray(y_vals, dtype=float)
    return X, y


def fit_model(
    tasks: Sequence[Task],
    *,
    use_entropy: bool = True,
) -> ModelParams:
    """
    Fit the triangle time model parameters from historical tasks.

    Uses ordinary least squares:

        T_k ≈ p_Gk * T_gov_star
             + p_Ak * T_azure_star
             + p_Dk * T_ds_star
             + eta * H(p_k)  (if use_entropy is True)

    Returns:
        ModelParams with fitted T_*_star and eta.
    """
    X, y = _prepare_training_matrices(tasks, use_entropy=use_entropy)

    # Solve least squares: minimize ||X * beta - y||_2
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)

    if use_entropy:
        if beta.shape[0] != 4:
            raise RuntimeError(
                f"Unexpected parameter vector size for entropy model: {beta.shape[0]}"
            )
        T_gov_star, T_azure_star, T_ds_star, eta = beta.tolist()
    else:
        if beta.shape[0] != 3:
            raise RuntimeError(
                f"Unexpected parameter vector size for base model: {beta.shape[0]}"
            )
        T_gov_star, T_azure_star, T_ds_star = beta.tolist()
        eta = 0.0

    return ModelParams(
        T_gov_star=float(T_gov_star),
        T_azure_star=float(T_azure_star),
        T_ds_star=float(T_ds_star),
        eta=float(eta),
        use_entropy=use_entropy,
    )


def evaluate_model(
    tasks: Iterable[Task],
    params: ModelParams,
) -> Dict[str, float]:
    """
    Evaluate the model on a dataset of tasks.

    Returns a dict with:
    - n:         number of tasks used
    - mae:       mean absolute error
    - mse:       mean squared error
    - rmse:      root mean squared error
    - mape:      mean absolute percentage error (0 if any true value is 0)
    """
    y_true: List[float] = []
    y_pred: List[float] = []

    for t in tasks:
        # Determine ground truth total time
        if t.T_total is None or t.T_total <= 0.0:
            total = t.T_gov + t.T_azure + t.T_ds
        else:
            total = t.T_total

        if total <= 0.0:
            # Skip degenerate tasks
            continue

        y_true.append(total)
        y_pred.append(predict_time_for_task(t, params))

    if not y_true:
        raise ValueError("No valid tasks for evaluation (all had zero or missing time).")

    y_true_arr = np.asarray(y_true, dtype=float)
    y_pred_arr = np.asarray(y_pred, dtype=float)

    errors = y_pred_arr - y_true_arr
    abs_errors = np.abs(errors)
    sq_errors = errors**2

    mae = float(abs_errors.mean())
    mse = float(sq_errors.mean())
    rmse = float(np.sqrt(mse))

    # MAPE: be careful with zeros
    with np.errstate(divide="ignore", invalid="ignore"):
        perc_errors = abs_errors / y_true_arr
        perc_errors = perc_errors[~np.isnan(perc_errors) & ~np.isinf(perc_errors)]
        mape = float(perc_errors.mean()) if perc_errors.size > 0 else 0.0

    return {
        "n": float(len(y_true)),
        "mae": mae,
        "mse": mse,
        "rmse": rmse,
        "mape": mape,
    }
