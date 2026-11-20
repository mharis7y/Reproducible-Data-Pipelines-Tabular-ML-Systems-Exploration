# Reproducible Data Pipelines, Tabular ML & Systems Exploration

An end-to-end reproducible data engineering and tabular machine learning project built on a real-world dataset, accompanied by systems engineering exploration artifacts.

## Overview

- **Part A — Reproducible Data Quality & Insights Pipeline (35%)**: Inspect raw data, document its schema, write testable cleaning and validation functions, compute Pandas/NumPy summaries, run SQLite queries, generate visual insights, and produce a before-and-after data-quality report.
- **Part B — End-to-End Tabular ML Baseline (40%)**: Frame a prediction task, perform a justified leakage-free train/test split, build a unified `scikit-learn` `Pipeline` + `ColumnTransformer`, compare a baseline against candidate models, run error analysis, and save the fitted pipeline for unseen inference.
- **Part C — Exploration Homework (15%)**: Explore four core systems and software engineering topics (feed query optimization in SQLite, GitHub Actions CI & PR workflows, system design theory, and a repeatable system design workflow) with written reports and working artifacts.

## Repository Structure

```text
.
├── .github/
│   └── workflows/       # Part C2 GitHub Actions CI workflow
├── data/
│   ├── raw/             # Original raw data (never edited or overwritten)
│   └── cleaned/         # Reproducible cleaned dataset output
├── docs/
│   ├── assumptions.md   # Cleaning assumptions, limitations, and Part B model card
│   ├── exploration.md   # Part C write-ups and references
│   └── schema.md        # Raw data schema and validation rules
├── models/              # Saved ML pipeline artifacts (.joblib)
├── notebooks/           # Exploration notebooks only (outputs also saved as files)
├── outputs/
│   ├── figures/         # Saved visualizations (referenced below)
│   └── reports/         # Data-quality report, model comparison table, metrics
├── sql/                 # SQLite queries and experiments
├── src/                 # Cleaning, validation, features, training, and inference code
├── tests/               # Pytest unit tests for cleaning and validation functions
├── README.md
└── requirements.txt     # Pinned Python dependencies
```

## Setup Instructions

**Prerequisites**: Python 3.13+ (tested on Python 3.13.15).

1. Clone the repository:
   ```bash
   git clone <REPOSITORY_URL>
   cd "<REPOSITORY_FOLDER>"
   ```

2. (Optional, recommended) Create and activate a virtual environment:
   ```bash
   python -m venv .venv
   # Windows PowerShell:
   .\.venv\Scripts\Activate.ps1
   # Linux/macOS:
   source .venv/bin/activate
   ```

3. Install pinned dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Dataset

*To be completed at Checkpoint 0.*

- **Dataset Name**: _TBD_
- **Source URL**: _TBD_
- **Licence**: _TBD_
- **Access Date**: _TBD_
- **Rows / Columns**: _TBD_
- **Prediction Target (Part B)**: _TBD_

## Running Part A (Data Quality & Insights Pipeline)

*To be completed once Part A pipeline scripts are implemented.*

- Run tests: `pytest`
- Run pipeline: _TBD_

## Running Part B (Tabular ML Pipeline)

*To be completed once Part B training and inference scripts are implemented.*

- Train & evaluate models: _TBD_
- Run inference on unseen rows: _TBD_

## Findings & Figures

*To be completed after Part A and Part B outputs are generated.*

## Part C Exploration

See [docs/exploration.md](docs/exploration.md) and the accompanying artifacts in [sql/](sql/) and [.github/workflows/](.github/workflows/).

## Tools & Academic Integrity Disclosure

All code, analysis, and documentation in this repository are understood and explainable line-by-line by the author. Tools used during development:
- Python 3.13 (`pandas`, `numpy`, `matplotlib`, `seaborn`, `scikit-learn`, `joblib`, `scipy`, `requests`, `openpyxl`, `sqlite3`, `pytest`, `ruff`)
- AI coding assistant (used as a learning and scaffolding aid; all decisions verified and explainable by the author)
