"""
Data I/O utilities.

Provides thin helpers to:
- Load tasks from a local CSV (Excel-style usage)
- Load/save tasks to Azure Blob Storage as CSV
- Sync a local CSV to Azure Blob

Dependencies:
- Standard library only for local CSV.
- For Azure Blob: `azure-storage-blob` package is required.
"""

from __future__ import annotations

import csv
from dataclasses import asdict
from io import StringIO
from typing import Iterable, List, Optional

from .config import Config, get_config
from .schema import Task

try:
    from azure.storage.blob import BlobServiceClient  # type: ignore[import]
except ImportError:  # pragma: no cover - optional dependency
    BlobServiceClient = None  # type: ignore[assignment]


# --- Local CSV helpers -----------------------------------------------------


def load_tasks_from_csv(path: str) -> List[Task]:
    """
    Load tasks from a CSV file.

    Expected columns (case-sensitive):
    - Optional: task_id
    - Required: T_gov, T_azure, T_ds
    - Optional: T_total, p_gov, p_azure, p_ds

    Extra columns are ignored.
    """
    tasks: List[Task] = []
    with open(path, mode="r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if not row:
                continue

            def _f(key: str, default: float = 0.0) -> float:
                val = row.get(key)
                if val in (None, ""):
                    return default
                try:
                    return float(val)
                except ValueError:
                    return default

            task = Task(
                task_id=row.get("task_id") or None,
                T_gov=_f("T_gov"),
                T_azure=_f("T_azure"),
                T_ds=_f("T_ds"),
                T_total=_f("T_total", default=0.0)
                if row.get("T_total") not in (None, "")
                else None,
                p_gov=_f("p_gov", default=0.0)
                if row.get("p_gov") not in (None, "")
                else None,
                p_azure=_f("p_azure", default=0.0)
                if row.get("p_azure") not in (None, "")
                else None,
                p_ds=_f("p_ds", default=0.0)
                if row.get("p_ds") not in (None, "")
                else None,
            )
            tasks.append(task)
    return tasks


def save_tasks_to_csv(tasks: Iterable[Task], path: str) -> None:
    """
    Save tasks to a CSV file.

    Columns:
    task_id, T_gov, T_azure, T_ds, T_total, p_gov, p_azure, p_ds
    """
    fieldnames = [
        "task_id",
        "T_gov",
        "T_azure",
        "T_ds",
        "T_total",
        "p_gov",
        "p_azure",
        "p_ds",
    ]

    with open(path, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for task in tasks:
            row = asdict(task)
            # Ensure all expected keys exist
            out = {key: row.get(key) for key in fieldnames}
            writer.writerow(out)


# --- Azure Blob helpers ----------------------------------------------------


def _get_blob_service(config: Optional[Config] = None):
    if BlobServiceClient is None:
        raise ImportError(
            "azure-storage-blob is required for Azure Blob operations. "
            "Install via `pip install azure-storage-blob`."
        )
    cfg = config or get_config()
    if not cfg.azure_blob_connection_string:
        raise ValueError(
            "Azure blob connection string is not configured. "
            "Set TT_AZURE_BLOB_CONNECTION_STRING or pass Config explicitly."
        )
    return BlobServiceClient.from_connection_string(
        cfg.azure_blob_connection_string
    ), cfg


def load_tasks_from_azure_blob(
    blob_name: str,
    *,
    container_name: Optional[str] = None,
    config: Optional[Config] = None,
) -> List[Task]:
    """
    Load tasks from a CSV stored in Azure Blob Storage.

    - blob_name: name of the blob (e.g., 'triangle/tasks.csv')
    - container_name: overrides Config.azure_blob_container_name if provided
    """
    service_client, cfg = _get_blob_service(config)
    container = container_name or cfg.azure_blob_container_name
    if not container:
        raise ValueError(
            "Azure blob container name is not configured. "
            "Set TT_AZURE_BLOB_CONTAINER_NAME or pass container_name."
        )

    blob_client = service_client.get_blob_client(container=container, blob=blob_name)
    download_stream = blob_client.download_blob()
    csv_text = download_stream.readall().decode("utf-8")

    # Reuse our local CSV loader on an in-memory string
    tasks: List[Task] = []
    reader = csv.DictReader(StringIO(csv_text))
    for row in reader:
        if not row:
            continue

        def _f(key: str, default: float = 0.0) -> float:
            val = row.get(key)
            if val in (None, ""):
                return default
            try:
                return float(val)
            except ValueError:
                return default

        task = Task(
            task_id=row.get("task_id") or None,
            T_gov=_f("T_gov"),
            T_azure=_f("T_azure"),
            T_ds=_f("T_ds"),
            T_total=_f("T_total", default=0.0)
            if row.get("T_total") not in (None, "")
            else None,
            p_gov=_f("p_gov", default=0.0)
            if row.get("p_gov") not in (None, "")
            else None,
            p_azure=_f("p_azure", default=0.0)
            if row.get("p_azure") not in (None, "")
            else None,
            p_ds=_f("p_ds", default=0.0)
            if row.get("p_ds") not in (None, "")
            else None,
        )
        tasks.append(task)
    return tasks


def save_tasks_to_azure_blob(
    tasks: Iterable[Task],
    blob_name: str,
    *,
    container_name: Optional[str] = None,
    config: Optional[Config] = None,
) -> None:
    """
    Save tasks as CSV into an Azure Blob.

    Overwrites the target blob.
    """
    service_client, cfg = _get_blob_service(config)
    container = container_name or cfg.azure_blob_container_name
    if not container:
        raise ValueError(
            "Azure blob container name is not configured. "
            "Set TT_AZURE_BLOB_CONTAINER_NAME or pass container_name."
        )

    # Serialize to in-memory CSV
    fieldnames = [
        "task_id",
        "T_gov",
        "T_azure",
        "T_ds",
        "T_total",
        "p_gov",
        "p_azure",
        "p_ds",
    ]
    buffer = StringIO()
    writer = csv.DictWriter(buffer, fieldnames=fieldnames)
    writer.writeheader()
    for task in tasks:
        row = asdict(task)
        out = {key: row.get(key) for key in fieldnames}
        writer.writerow(out)

    csv_bytes = buffer.getvalue().encode("utf-8")

    blob_client = service_client.get_blob_client(container=container, blob=blob_name)
    blob_client.upload_blob(csv_bytes, overwrite=True)


def sync_csv_to_azure_blob(
    local_csv_path: str,
    blob_name: str,
    *,
    container_name: Optional[str] = None,
    config: Optional[Config] = None,
) -> None:
    """
    Convenience function:

    1) Load tasks from a local CSV.
    2) Push them to Azure Blob Storage as CSV.
    """
    tasks = load_tasks_from_csv(local_csv_path)
    save_tasks_to_azure_blob(
        tasks,
        blob_name=blob_name,
        container_name=container_name,
        config=config,
    )
