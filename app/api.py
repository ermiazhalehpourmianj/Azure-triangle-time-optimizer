"""
FastAPI app for the triangle-time system.

Endpoints:
- POST /predict_time
- POST /log_task

This is what you deploy to Azure App Service / Container Apps.
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Optional

# --- Make src/ importable ----------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = REPO_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from triangle_time.schema import Task, ModelParams
from triangle_time.triangle_model import (
    predict_time_for_task,
    update_task_proportions,
)
from triangle_time.data_io import (
    load_tasks_from_csv,
    save_tasks_to_csv,
)

# --- Config-ish constants ----------------------------------------------------

DEFAULT_PARAMS_PATH = REPO_ROOT / "model_params.json"
DEFAULT_TASK_LOG_CSV = REPO_ROOT / "data" / "tasks_logged.csv"

MODEL_PARAMS_PATH = Path(
    os.getenv("TT_MODEL_PARAMS_PATH", str(DEFAULT_PARAMS_PATH))
)

TASK_LOG_CSV_PATH = Path(
    os.getenv("TT_TASK_LOG_CSV_PATH", str(DEFAULT_TASK_LOG_CSV))
)

app = FastAPI(title="Triangle Time API")


# --- Helpers -----------------------------------------------------------------


def load_model_params(path: Path = MODEL_PARAMS_PATH) -> ModelParams:
    """
    Load ModelParams from a JSON file.

    Expected keys: T_gov_star, T_azure_star, T_ds_star, eta, use_entropy.
    """
    if not path.exists():
        raise FileNotFoundError(
            f"Model params file not found at {path}. "
            "Run `python -m app.cli fit data/samples/example_tasks.csv` first."
        )
    data = json.loads(path.read_text(encoding="utf-8"))
    return ModelParams(**data)


def append_task_to_csv(task: Task, path: Path = TASK_LOG_CSV_PATH) -> None:
    """
    Append a single task to the task log CSV.

    This is intentionally simple: load existing, append, overwrite.
    Good enough for low-volume / demo. Replace with DB/Azure in prod.
    """
    path.parent.mkdir(parents=True, exist_ok=True)

    existing_tasks = []
    if path.exists():
        existing_tasks = load_tasks_from_csv(str(path))

    existing_tasks.append(update_task_proportions(task))
    save_tasks_to_csv(existing_tasks, str(path))


# --- Request / Response schemas ----------------------------------------------


class TaskPayload(BaseModel):
    """
    Input payload for both /predict_time and /log_task.

    You can supply:
    - Raw times: T_gov, T_azure, T_ds, (optional) T_total
    - Optionally p_gov, p_azure, p_ds if you already have proportions.

    If proportions are missing, they will be computed from times.
    """

    task_id: Optional[str] = None

    T_gov: float = 0.0
    T_azure: float = 0.0
    T_ds: float = 0.0
    T_total: Optional[float] = None

    p_gov: Optional[float] = None
    p_azure: Optional[float] = None
    p_ds: Optional[float] = None


class PredictResponse(BaseModel):
    task_id: Optional[str]
    T_pred: float
    model_params: dict


class LogTaskResponse(BaseModel):
    status: str
    task: dict


# --- Endpoints ---------------------------------------------------------------


@app.post("/predict_time", response_model=PredictResponse)
def predict_time(payload: TaskPayload) -> PredictResponse:
    """
    Predict the total time for a task.

    Body example (raw times):
    {
      "task_id": "TASK-123",
      "T_gov": 2.0,
      "T_azure": 3.0,
      "T_ds": 1.0
    }

    Or using proportions (if you already know triangle coords):
    {
      "task_id": "TASK-123",
      "p_gov": 0.5,
      "p_azure": 0.3,
      "p_ds": 0.2
    }
    """
    try:
        params = load_model_params()
    except FileNotFoundError as e:
        raise HTTPException(status_code=500, detail=str(e))

    task = Task(
        task_id=payload.task_id,
        T_gov=payload.T_gov,
        T_azure=payload.T_azure,
        T_ds=payload.T_ds,
        T_total=payload.T_total,
        p_gov=payload.p_gov,
        p_azure=payload.p_azure,
        p_ds=payload.p_ds,
    )

    T_pred = predict_time_for_task(task, params)

    return PredictResponse(
        task_id=task.task_id,
        T_pred=T_pred,
        model_params=asdict(params),
    )


@app.post("/log_task", response_model=LogTaskResponse)
def log_task(payload: TaskPayload) -> LogTaskResponse:
    """
    Log a completed task with actual time into a CSV log.

    This is a simple "append to CSV" implementation.

    Example:
    {
      "task_id": "TASK-123",
      "T_gov": 2.0,
      "T_azure": 3.0,
      "T_ds": 1.0,
      "T_total": 6.0
    }
    """
    task = Task(
        task_id=payload.task_id,
        T_gov=payload.T_gov,
        T_azure=payload.T_azure,
        T_ds=payload.T_ds,
        T_total=payload.T_total,
        p_gov=payload.p_gov,
        p_azure=payload.p_azure,
        p_ds=payload.p_ds,
    )

    # Normalize proportions & total
    task = update_task_proportions(task)
    append_task_to_csv(task)

    return LogTaskResponse(
        status="ok",
        task=asdict(task),
    )


# Convenience for local dev:
# uvicorn app.api:app --reload
if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.api:app", host="0.0.0.0", port=8000, reload=True)
