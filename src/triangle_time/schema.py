"""
Data schemas for the triangle-time system.

Defines:
- Task: a single work item with time breakdown + triangle proportions
- ModelParams: parameters of the triangle time model
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class Task:
    """
    Represents a single task / ticket / project instance.

    Times are in arbitrary but consistent units (e.g., hours).
    Proportions are barycentric coordinates inside the triangle.
    """

    task_id: Optional[str] = None

    # Raw time spent in each dimension
    T_gov: float = 0.0
    T_azure: float = 0.0
    T_ds: float = 0.0

    # Total time; if not provided, can be computed as T_gov + T_azure + T_ds
    T_total: Optional[float] = None

    # Proportions inside the triangle (barycentric coords)
    p_gov: Optional[float] = None
    p_azure: Optional[float] = None
    p_ds: Optional[float] = None

    def __post_init__(self) -> None:
        # Normalization can be handled centrally in triangle_model,
        # but we ensure numeric types here.
        self.T_gov = float(self.T_gov)
        self.T_azure = float(self.T_azure)
        self.T_ds = float(self.T_ds)
        if self.T_total is not None:
            self.T_total = float(self.T_total)


@dataclass
class ModelParams:
    """
    Parameters of the triangle time model.

    T_*_star represent the expected time for a "pure" task located at
    each vertex (p=1 at that vertex, 0 at others).

    eta is the coefficient for the entropy-based "mixing" term. If
    use_entropy is False, eta is typically 0.0 and H(p) is ignored.
    """

    T_gov_star: float
    T_azure_star: float
    T_ds_star: float
    eta: float = 0.0
    use_entropy: bool = False
