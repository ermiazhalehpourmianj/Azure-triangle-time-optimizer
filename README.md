# 🔺 Triangle Time Optimizer

### 🖼 Screenshot

![Triangle Time Console UI](screenshots/triangle_console.png)

This repo is a **minimal Python + Azure system** that does one thing relentlessly:

> **Predict how long a task will take based on how much of it is  
> (G) gov inefficiency, (A) Azure integration, and (D) data science stack.**

If you’re tired of “this should only take a day” lies, this is where we start putting receipts on the table.

---

## 🎯 What this actually does

Triangle Time Optimizer lets you:

- **Measure** how time is really spent:
  - Government / approvals / politics (**G**)
  - Azure / infra / identity / integration (**A**)
  - Data science / ETL / ML / analytics (**D**)
- **Encode** each task as a point inside a triangle using barycentric coordinates.
- **Fit a model** from historical tasks that learns:
  - How long pure-G, pure-A, pure-D tasks tend to take.
  - How much extra drag appears when you mix all three.
- **Predict** the time for new tasks *before* you start:
  - `T_pred = triangle(G, A, D)` instead of “manager’s gut feeling”.
- **Expose it** via:
  - A small **Python library** (`triangle_time`).
  - A **FastAPI** endpoint (for tools / agents / dashboards).
  - A simple **CLI** (for Excel power users and shell addicts).

---

## 🔺 The Triangle Time Model (core idea)

We model every task as a point inside a triangle with vertices:

- **G** = Government / policy / approvals / bureaucracy  
- **A** = Azure / infra / identity / integration plumbing  
- **D** = Data science stack / ETL / ML / analytics  

Each task has **time spent** in each dimension:

- \(T_G\) = hours on gov / approvals / compliance  
- \(T_A\) = hours on Azure / infra / CI/CD / identity  
- \(T_D\) = hours on DS / models / data pipelines  

Total time:

\[
T = T_G + T_A + T_D
\]

Triangle coordinates (barycentric):

\[
p_G = T_G / T,\quad p_A = T_A / T,\quad p_D = T_D / T,\quad p_G + p_A + p_D = 1
\]

Now the task is literally a **point inside the G/A/D triangle**, and we learn how time behaves across that space.

### Base-time interpolation

We estimate three **vertex times** from history:

- \(T_G^*\) = typical time for a pure-G task  
- \(T_A^*\) = typical time for a pure-A task  
- \(T_D^*\) = typical time for a pure-D task  

Then the **Triangle Time Formula** is:

\[
T_{\text{pred}}(p_G, p_A, p_D)
= p_G T_G^* + p_A T_A^* + p_D T_D^*
\]

Example: task is 50% gov, 30% Azure, 20% DS:

\[
T_{\text{pred}} = 0.5 T_G^* + 0.3 T_A^* + 0.2 T_D^*
\]

That’s it: **we interpolate time across the triangle** instead of guessing.

### Multi-owner drag (optional)

Reality: the more teams touch a task, the slower it moves.

We model “mixing drag” using entropy:

\[
H(p) = -\left(p_G \log p_G + p_A \log p_A + p_D \log p_D\right)
\]

- If one dimension dominates → low \(H\) (clean ownership).
- If all three are balanced → high \(H\) (handoff city).

Upgraded formula:

\[
T_{\text{pred}}(p_G,p_A,p_D)
= p_G T_G^* + p_A T_A^* + p_D T_D^* + \eta H(p)
\]

- \(\eta > 0\): more mixing ⇒ more time (the usual gov story).

We fit \(T_G^*, T_A^*, T_D^*, \eta\) from historical task data using regression.

---

## 🧠 End-to-end system

### Step 1 – Instrument tasks

For each task or ticket, log:

- `T_gov`   → approvals / legal / policy work (**G**)  
- `T_azure` → Azure config / identity / networking / pipelines (**A**)  
- `T_ds`    → feature engineering / model training / dashboards (**D**)  
- `T_total` = `T_gov + T_azure + T_ds`  

These logs can come from:
- DevOps / Jira / ServiceNow tags  
- Manual timesheets  
- Your own agents

### Step 2 – Encode into the triangle

For each task:

\[
p_G = T_G / T,\quad p_A = T_A / T,\quad p_D = T_D / T
\]

We store both:
- Raw times: `T_gov`, `T_azure`, `T_ds`, `T_total`  
- Triangle coordinates: `p_gov`, `p_azure`, `p_ds`

### Step 3 – Fit model parameters

From historical tasks we estimate:

- \(T_G^*, T_A^*, T_D^*\): base times for pure G/A/D tasks  
- \(\eta\): how much drag mixing adds  

We fit them by minimizing:

\[
T_k \approx p_{G,k} T_G^* + p_{A,k} T_A^* + p_{D,k} T_D^* + \eta H(p_k)
\]

### Step 4 – Predict future tasks

For any new task:

1. Score it with \((p_G,p_A,p_D)\) (via template, rubric, or model).  
2. Plug into:

\[
T_{\text{pred}} = p_G T_G^* + p_A T_A^* + p_D T_D^* + \eta H(p)
\]

3. Use `T_pred`:
   - for planning,  
   - for negotiation,  
   - for “this will not take 2 days, stop lying to yourself” conversations.

---

## 🗂️ Repo structure

```text
triangle-time-optimizer/
├── README.md
├── pyproject.toml          # Minimal Python packaging (library + app)
├── src/
│   └── triangle_time/
│       ├── __init__.py
│       ├── config.py       # Azure + model config
│       ├── schema.py       # Task + model parameter schemas
│       ├── triangle_model.py   # All the time math (triangle + entropy)
│       ├── data_io.py      # Read/write from CSV and Azure
│       └── training.py     # Fit T_G*, T_A*, T_D*, eta from history
├── app/
│   ├── api.py              # FastAPI app: /predict_time, /log_task
│   └── cli.py              # CLI: fit from CSV, predict tasks, export params
├── azure/
│   ├── data_pipeline.md    # How data flows into Azure (DevOps/Jira → SQL/Blob)
│   └── deployment.md       # How to deploy the API to Azure
├── data/
│   └── samples/
│       └── example_tasks.csv   # Small example dataset
└── notebooks/
    └── 01_model_validation.ipynb   # Sanity checks & what-if analysis
