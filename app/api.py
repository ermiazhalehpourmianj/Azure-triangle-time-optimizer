"""
FastAPI app for the triangle-time system.

Endpoints:
- POST /predict_time
- POST /log_task
- GET  /health
- GET  /self-test
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


# --- Simple health + self-test -----------------------------------------------


@app.get("/health")
def health() -> dict:
    """Basic health check for Azure / load balancers."""
    return {"status": "ok"}


@app.get("/self-test")
def self_test() -> dict:
    """
    End-to-end smoke test:

    1. Load example tasks from data/samples/example_tasks.csv
    2. Load model params from model_params.json
    3. Predict time for the first task
    4. Append that task into the task log CSV

    If this works on Azure, the whole pipeline is wired.
    """
    # 1) load a sample file
    sample_csv = REPO_ROOT / "data" / "samples" / "example_tasks.csv"
    if not sample_csv.exists():
        raise HTTPException(
            status_code=500,
            detail=f"Sample CSV not found at {sample_csv}",
        )

    tasks = load_tasks_from_csv(str(sample_csv))
    if not tasks:
        raise HTTPException(
            status_code=500,
            detail="No tasks found in example_tasks.csv",
        )

    task = tasks[0]

    # 2) load model params
    try:
        params = load_model_params()
    except FileNotFoundError as e:
        raise HTTPException(status_code=500, detail=str(e))

    # 3) predict time
    T_pred = predict_time_for_task(task, params)

    # 4) log that task into the main CSV
    append_task_to_csv(task)

    return {
        "ok": True,
        "sample_task": asdict(task),
        "T_pred": T_pred,
        "model_params": asdict(params),
        "task_log_csv": str(TASK_LOG_CSV_PATH),
    }


# --- Main endpoints ----------------------------------------------------------


@app.post("/predict_time", response_model=PredictResponse)
def predict_time(payload: TaskPayload) -> PredictResponse:
    ...
    # (leave your existing implementation as-is)
    ...


@app.post("/log_task", response_model=LogTaskResponse)
def log_task(payload: TaskPayload) -> LogTaskResponse:
    ...
    # (leave your existing implementation as-is)
    ...


# Convenience for local dev:
# uvicorn app.api:app --reload
if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.api:app", host="0.0.0.0", port=8000, reload=True)

