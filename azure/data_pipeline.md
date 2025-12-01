# Triangle Time – Data Pipeline Design

This document describes how historical tasks move from work systems into Azure,
and how the `triangle-time-optimizer` app reads and writes them.

The goal: keep it **simple and Excel-like**, but on Azure.

---

## 1. Source systems (where tasks come from)

Typical upstream systems:

- **Azure DevOps** – work items, bugs, tasks
- **Jira** – issues / tickets
- **ServiceNow** – incidents / requests
- **Manual spreadsheets** – CSV logs curated by PMs / leads

Each system should eventually produce a **flat table** (or CSV export) with at least:

- `task_id` – unique ID from the source system (e.g., ADO ID, Jira key)
- `T_gov` – time spent on government / policy / approval / compliance work
- `T_azure` – time spent on Azure / infra / CI/CD / identity / networking
- `T_ds` – time spent on data science / analytics / ML / ETL
- `T_total` – (optional) total time; if missing, app computes `T_gov + T_azure + T_ds`
- `p_gov`, `p_azure`, `p_ds` – (optional) precomputed triangle proportions; if missing, they are computed from time.

Everything else (assignee, status, description, tags) is optional and can live in the source system or in a separate analytics store.

---

## 2. Staging in Azure

We use **Azure Blob Storage** as the canonical “Excel-in-the-cloud” store.

### 2.1 Containers and blobs

Recommended structure:

- **Container**: `triangle-time-data`  
  (Set this as `TT_AZURE_BLOB_CONTAINER_NAME`)

Inside the container:

- `raw/` – direct exports from DevOps/Jira/ServiceNow (optional)
- `processed/` – unified CSVs in the app’s schema

Key blobs:

- `processed/historical_tasks.csv`  
  - Input for model training (`fit_model`)  
  - Contains all completed, labeled tasks.

- `processed/tasks_logged.csv` (optional)  
  - Output log of tasks received via the `/log_task` API.  
  - In small deployments, the app may also write to local disk instead of Blob.

---

## 3. Ingestion flow

### Option A – Manual (MVP / small teams)

1. **Export from source systems**  
   - PM / analyst exports CSV from Azure DevOps / Jira / ServiceNow.
   - Map / clean the columns in Excel / Power BI or a simple Python script so they match:
     - `task_id, T_gov, T_azure, T_ds, T_total (optional), p_gov (optional), p_azure (optional), p_ds (optional)`

2. **Upload to Blob**  
   - Upload the cleaned CSV as:
     - `processed/historical_tasks.csv` in the `triangle-time-data` container.

3. **Train model**  
   - In a dev box or pipeline:
     - `python -m app.cli fit data/samples/example_tasks.csv` (for sample)
     - Later: replace the path to point to a downloaded version of `processed/historical_tasks.csv`.

This is enough to bootstrap the model with no heavy infra.

---

### Option B – Automated (Data Factory / Synapse)

For a more scalable setup:

1. **Data Factory pipelines**
   - Create a pipeline per source system:
     - **Copy activity** from:
       - Azure DevOps REST API / Jira REST / ServiceNow REST
     - To:
       - `triangle-time-data/raw/<system_name>/YYYYMMDD_<export>.csv`

2. **Mapping / transformation**
   - Use a **Data Flow** or a small **Databricks / Synapse notebook** to:
     - Map source columns to canonical:
       - Example:  
         - `ado_field_government_hours` → `T_gov`  
         - `ado_field_infra_hours` → `T_azure`  
         - `ado_field_ds_hours` → `T_ds`
     - Compute `T_total` if missing.
     - Optionally compute `p_gov`, `p_azure`, `p_ds` on the ETL side.

   - Output to:
     - `triangle-time-data/processed/historical_tasks.csv`  
       (overwrite or partition by date and union later).

3. **Downstream consumption**
   - The Python training script can read directly from Blob (see below) or
     a scheduled job can download `historical_tasks.csv` to a build agent
     and run `fit_model`.

---

## 4. How the Python app reads/writes

The `triangle_time.data_io` module handles CSV I/O from Azure Blob.

### 4.1 Configuration

Set environment variables (in Azure or locally):

- `TT_AZURE_BLOB_CONNECTION_STRING` – connection string to your storage account
- `TT_AZURE_BLOB_CONTAINER_NAME` – e.g., `triangle-time-data`

These are read via `triangle_time.config.get_config()`.

### 4.2 Reading historical tasks

Code path:

- `triangle_time.data_io.load_tasks_from_azure_blob(blob_name=...)`

Default expectation:

- `blob_name="processed/historical_tasks.csv"`

You can then call:

```python
from triangle_time.data_io import load_tasks_from_azure_blob
tasks = load_tasks_from_azure_blob("processed/historical_tasks.csv")
