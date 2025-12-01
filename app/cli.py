"""
CLI for the triangle-time system.

Usage examples:

    # Fit model from a CSV of historical tasks
    python -m app.cli fit data/samples/example_tasks.csv

    # Predict time for a single task JSON
    python -m app.cli predict single-task.json

    # Export the model parameters to another path
    python -m app.cli export-params params.json
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

# --- Make src/ importable ----------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = REPO_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from triangle_time.data_io import load_tasks_from_csv
from triangle_time.schema import Task, ModelParams
from triangle_time.training import fit_model
from triangle_time.triangle_model import predict_time_for_task

DEFAULT_PARAMS_PATH = REPO_ROOT / "model_params.json"


# --- Commands ----------------------------------------------------------------


def cmd_fit(args: argparse.Namespace) -> None:
    """
    Fit model from a CSV of historical tasks and save params as JSON.
    """
    csv_path = Path(args.csv_path).resolve()
    params_path = Path(args.params_path).resolve()

    if not csv_path.exists():
        raise SystemExit(f"[fit] CSV file not found: {csv_path}")

    print(f"[fit] Loading tasks from {csv_path} ...")
    tasks = load_tasks_from_csv(str(csv_path))
    print(f"[fit] Loaded {len(tasks)} tasks.")

    print("[fit] Fitting model (with entropy)...")
    params = fit_model(tasks, use_entropy=True)

    params_path.parent.mkdir(parents=True, exist_ok=True)
    params_json = asdict(params)
    params_path.write_text(json.dumps(params_json, indent=2), encoding="utf-8")

    print(f"[fit] Saved model params to {params_path}")
    print("[fit] Done.")


def cmd_predict(args: argparse.Namespace) -> None:
    """
    Predict time for one task described in a JSON file.
    """
    task_json_path = Path(args.task_json_path).resolve()
    params_path = Path(args.params_path).resolve()

    if not task_json_path.exists():
        raise SystemExit(f"[predict] Task JSON file not found: {task_json_path}")
    if not params_path.exists():
        raise SystemExit(
            f"[predict] Model params file not found: {params_path}. "
            "Run `python -m app.cli fit ...` first."
        )

    task_data = json.loads(task_json_path.read_text(encoding="utf-8"))
    task = Task(**task_data)

    params_data = json.loads(params_path.read_text(encoding="utf-8"))
    params = ModelParams(**params_data)

    T_pred = predict_time_for_task(task, params)

    print("[predict] Input task:")
    print(json.dumps(task_data, indent=2))
    print()
    print(f"[predict] Predicted total time: {T_pred:.4f}")


def cmd_export_params(args: argparse.Namespace) -> None:
    """
    Copy model params JSON to a new destination path.
    """
    source_path = Path(args.source_path).resolve()
    dest_path = Path(args.dest_path).resolve()

    if not source_path.exists():
        raise SystemExit(
            f"[export-params] Source params file not found: {source_path}"
        )

    dest_path.parent.mkdir(parents=True, exist_ok=True)
    dest_path.write_bytes(source_path.read_bytes())

    print(f"[export-params] Copied {source_path} -> {dest_path}")


# --- Main --------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Triangle Time CLI – fit model, predict, export params."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # fit
    fit_p = subparsers.add_parser(
        "fit",
        help="Fit model from a CSV of historical tasks.",
    )
    fit_p.add_argument(
        "csv_path",
        help="Path to CSV with historical tasks (e.g., data/samples/example_tasks.csv).",
    )
    fit_p.add_argument(
        "--params-path",
        default=str(DEFAULT_PARAMS_PATH),
        help=f"Where to save model params JSON (default: {DEFAULT_PARAMS_PATH}).",
    )
    fit_p.set_defaults(func=cmd_fit)

    # predict
    pred_p = subparsers.add_parser(
        "predict",
        help="Predict time for a single task defined in a JSON file.",
    )
    pred_p.add_argument(
        "task_json_path",
        help="Path to JSON file describing a Task (fields match triangle_time.schema.Task).",
    )
    pred_p.add_argument(
        "--params-path",
        default=str(DEFAULT_PARAMS_PATH),
        help=f"Path to model params JSON (default: {DEFAULT_PARAMS_PATH}).",
    )
    pred_p.set_defaults(func=cmd_predict)

    # export-params
    exp_p = subparsers.add_parser(
        "export-params",
        help="Copy model params JSON to another location.",
    )
    exp_p.add_argument(
        "dest_path",
        help="Destination path for the copied params JSON.",
    )
    exp_p.add_argument(
        "--source-path",
        default=str(DEFAULT_PARAMS_PATH),
        help=f"Source params JSON path (default: {DEFAULT_PARAMS_PATH}).",
    )
    exp_p.set_defaults(func=cmd_export_params)

    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
