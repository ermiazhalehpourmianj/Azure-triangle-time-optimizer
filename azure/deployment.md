````markdown
# Deployment Guide – `triangle-time-optimizer`

This document is the playbook for running and deploying the Triangle Time system.

It covers:

- Local development (uvicorn, with and without Docker)
- Containerizing the app
- Deploying to **Azure App Service** or **Azure Container Apps**
- Required environment variables

The goal is to keep the stack **minimal**: Python + FastAPI + optional Azure Blob.

---

## 0. Repo Layout (Assumed)

This guide assumes the repo looks like this:

```text
triangle-time-optimizer/
├── app/
│   ├── api.py            # FastAPI app (entrypoint for HTTP)
│   └── cli.py            # CLI for fitting model, predicting, exporting params
├── src/
│   └── triangle_time/    # Core Python package (model, data_io, training)
├── data/
│   ├── samples/
│   │   └── example_tasks.csv
│   └── tasks_logged.csv  # (created at runtime, optional)
├── model_params.json     # (created by CLI, used by API)
└── azure/
    └── deployment.md     # This file
````

If your structure differs slightly, adjust paths accordingly.

---

## 1. Environment Variables

The system is configured via environment variables (all optional but recommended in Azure):

| Variable                          | Description                                                    | Example                        |
| --------------------------------- | -------------------------------------------------------------- | ------------------------------ |
| `TT_AZURE_BLOB_CONNECTION_STRING` | Azure Storage connection string (for Blob I/O in `data_io.py`) | `DefaultEndpointsProtocol=...` |
| `TT_AZURE_BLOB_CONTAINER_NAME`    | Container where CSVs are stored (e.g., for tasks, history)     | `triangle-time`                |
| `TT_AZURE_SQL_CONNECTION_STRING`  | (Optional) For future SQL usage (not required currently)       | `Server=tcp:...`               |
| `TT_USE_ENTROPY`                  | `"true"` / `"false"` – Whether to use entropy term by default  | `true`                         |
| `TT_DEFAULT_ETA`                  | Float – default η value if none is learned or used             | `0.0`                          |
| `TT_MODEL_PARAMS_PATH`            | Path to the model params JSON used by the API                  | `/app/model_params.json`       |
| `TT_TASK_LOG_CSV_PATH`            | Path to the task log CSV used by `/log_task`                   | `/app/data/tasks_logged.csv`   |

For local dev, defaults are:

* `TT_MODEL_PARAMS_PATH` → `./model_params.json` at repo root
* `TT_TASK_LOG_CSV_PATH` → `./data/tasks_logged.csv`

In Azure, it is recommended to **set `TT_MODEL_PARAMS_PATH` and `TT_TASK_LOG_CSV_PATH` to paths inside the container or mounted storage**.

---

## 2. Local Development (no Docker)

### 2.1. Create virtual environment & install dependencies

From repo root:

```bash
python -m venv .venv
source .venv/bin/activate  # on Windows: .venv\Scripts\activate

pip install --upgrade pip
pip install -r requirements.txt
# or, if using pyproject.toml: pip install .
```

Make sure `fastapi`, `uvicorn`, `numpy`, and (optionally) `azure-storage-blob` are installed.

### 2.2. Fit the model locally

Before the API can serve predictions, create `model_params.json`:

```bash
python -m app.cli fit data/samples/example_tasks.csv
```

This will:

* Read sample tasks from `data/samples/example_tasks.csv`
* Fit model parameters (T_gov*, T_azure*, T_ds*, η)
* Save them to `model_params.json` in the repo root

You can override the output path:

```bash
python -m app.cli fit data/samples/example_tasks.csv --params-path model_params.json
```

### 2.3. Run the API with uvicorn

From repo root (with the venv active):

```bash
uvicorn app.api:app --reload --host 0.0.0.0 --port 8000
```

The service will be available at:

* `http://localhost:8000/docs` – interactive Swagger UI
* `POST /predict_time`
* `POST /log_task`

---

## 3. Dockerized Deployment (Local & Azure)

### 3.1. Example `Dockerfile`

Create a `Dockerfile` at the repo root:

```dockerfile
FROM python:3.11-slim

# Set workdir
WORKDIR /app

# Install system dependencies (if needed)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
 && rm -rf /var/lib/apt/lists/*

# Copy dependency definitions
COPY pyproject.toml poetry.lock* requirements.txt* ./

# Install Python dependencies
# Option 1: using requirements.txt
RUN if [ -f "requirements.txt" ]; then \
      pip install --no-cache-dir --upgrade pip && \
      pip install --no-cache-dir -r requirements.txt; \
    fi

# Option 2 (comment out Option 1) for pyproject.toml + poetry:
# RUN pip install --no-cache-dir poetry && \
#     poetry config virtualenvs.create false && \
#     poetry install --no-root --no-interaction --no-ansi

# Copy only the necessary app files
COPY app/ ./app/
COPY src/ ./src/
COPY data/ ./data/

# Copy model params if you want to bake in a default version
# (For real CI/CD, you'd usually mount or overwrite this)
COPY model_params.json ./model_params.json

ENV PYTHONPATH=/app/src

# Expose port
EXPOSE 8000

# Default command: run the FastAPI app with uvicorn
CMD ["uvicorn", "app.api:app", "--host", "0.0.0.0", "--port", "8000"]
```

Adjust the dependencies/install section according to your actual setup.

### 3.2. Build & run the container locally

From repo root:

```bash
# Build
docker build -t triangle-time-api .

# Run
docker run -it --rm -p 8000:8000 \
  -e TT_MODEL_PARAMS_PATH=/app/model_params.json \
  -e TT_TASK_LOG_CSV_PATH=/app/data/tasks_logged.csv \
  triangle-time-api
```

Check:

* `http://localhost:8000/docs`

---

## 4. Deploy to Azure App Service (Container)

### 4.1. Push image to Azure Container Registry (ACR)

1. Create an ACR (once):

   ```bash
   az acr create \
     --resource-group <RESOURCE_GROUP> \
     --name <ACR_NAME> \
     --sku Basic
   ```

2. Log in and tag/push image:

   ```bash
   az acr login --name <ACR_NAME>

   docker tag triangle-time-api <ACR_NAME>.azurecr.io/triangle-time-api:latest

   docker push <ACR_NAME>.azurecr.io/triangle-time-api:latest
   ```

### 4.2. Create Azure App Service using the container

```bash
az appservice plan create \
  --name triangle-time-plan \
  --resource-group <RESOURCE_GROUP> \
  --sku B1 \
  --is-linux

az webapp create \
  --resource-group <RESOURCE_GROUP> \
  --plan triangle-time-plan \
  --name <WEBAPP_NAME> \
  --deployment-container-image-name <ACR_NAME>.azurecr.io/triangle-time-api:latest
```

Grant App Service access to ACR if needed:

```bash
az webapp config container set \
  --name <WEBAPP_NAME> \
  --resource-group <RESOURCE_GROUP> \
  --docker-custom-image-name <ACR_NAME>.azurecr.io/triangle-time-api:latest \
  --docker-registry-server-url https://<ACR_NAME>.azurecr.io
```

### 4.3. Configure environment variables in App Service

Set env vars via Azure Portal or CLI. Example:

```bash
az webapp config appsettings set \
  --resource-group <RESOURCE_GROUP> \
  --name <WEBAPP_NAME> \
  --settings \
    TT_MODEL_PARAMS_PATH=/app/model_params.json \
    TT_TASK_LOG_CSV_PATH=/app/data/tasks_logged.csv \
    TT_USE_ENTROPY=true \
    TT_DEFAULT_ETA=0.0 \
    TT_AZURE_BLOB_CONNECTION_STRING="<your-blob-connection-string>" \
    TT_AZURE_BLOB_CONTAINER_NAME="triangle-time"
```

Once deployed, your API will be reachable at:

* `https://<WEBAPP_NAME>.azurewebsites.net/docs`

---

## 5. Deploy to Azure Container Apps (Optional)

If you prefer **Azure Container Apps**:

### 5.1. Create Container Apps environment

```bash
az containerapp env create \
  --name triangle-time-env \
  --resource-group <RESOURCE_GROUP> \
  --location <LOCATION>
```

### 5.2. Deploy Container App

```bash
az containerapp create \
  --name triangle-time-api \
  --resource-group <RESOURCE_GROUP> \
  --environment triangle-time-env \
  --image <ACR_NAME>.azurecr.io/triangle-time-api:latest \
  --ingress external \
  --target-port 8000 \
  --env-vars \
    TT_MODEL_PARAMS_PATH=/app/model_params.json \
    TT_TASK_LOG_CSV_PATH=/app/data/tasks_logged.csv \
    TT_USE_ENTROPY=true \
    TT_DEFAULT_ETA=0.0 \
    TT_AZURE_BLOB_CONNECTION_STRING="<your-blob-connection-string>" \
    TT_AZURE_BLOB_CONTAINER_NAME="triangle-time"
```

Get the FQDN of the app:

```bash
az containerapp show \
  --name triangle-time-api \
  --resource-group <RESOURCE_GROUP> \
  --query properties.configuration.ingress.fqdn \
  --output tsv
```

Your API will be at:

* `https://<FQDN>/docs`

---

## 6. Updating the Model in Production

The production API reads parameters from `TT_MODEL_PARAMS_PATH` (`model_params.json`).

Baseline flow:

1. Pull latest tasks from logs / Blob / CSV.

2. Run the CLI locally or in a pipeline:

   ```bash
   python -m app.cli fit data/samples/example_tasks.csv --params-path model_params.json
   ```

3. Replace `model_params.json` in:

   * The repo (and rebuild image), or
   * A mounted volume / storage location used by the container.

4. Redeploy the container (if params are baked in the image), or simply restart the app if it reads from a mounted file updated externally.

---

## 7. Health & Smoke Testing

After deployment (App Service or Container Apps):

* Hit the docs:
  `GET /docs`
* Test prediction with `curl`:

```bash
curl -X POST "https://<HOST>/predict_time" \
  -H "Content-Type: application/json" \
  -d '{
    "task_id": "SMOKE-TEST",
    "T_gov": 2.0,
    "T_azure": 3.0,
    "T_ds": 1.0
  }'
```

You should receive:

* `200 OK`
* JSON containing `T_pred` and `model_params`.

If this works, the app, model, and env vars are wired correctly.

---

```
```
