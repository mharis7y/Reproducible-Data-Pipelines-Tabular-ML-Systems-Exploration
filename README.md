# Reproducible Data Pipelines, Tabular ML & Systems Exploration

> **Write-ups & Documentation**: [Project Write-ups & Documentation (Google Doc)](https://docs.google.com/document/d/1wccAHNu3aKxX6hXiF19ov8Lx1y56MF_EyiLIqiX162U/edit?usp=sharing)

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
├── screenshots/         # Project screenshots displayed in README
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

Details and justification are documented in [docs/dataset_proposal.md](docs/dataset_proposal.md) and [docs/schema.md](docs/schema.md).

- **Dataset Name**: City of Chicago Building Permits (H1 2024 Operational Extract)
- **Source Portal**: https://data.cityofchicago.org/Buildings/Building-Permits/ydr8-5enu
- **API Endpoint**: `https://data.cityofchicago.org/resource/ydr8-5enu.csv`
- **Licence**: City of Chicago Data Terms of Use — Public Open Data (https://www.chicago.gov/city/en/narr/foia/data_disclaimer.html)
- **Access Date**: `2026-11-21`
- **Rows / Columns**: `16,934` rows × `29` columns (`7.55 MB`)
- **Prediction Target (Part B)**: `is_delayed` (`processing_time > 30` days — binary classification: `21.24%` delayed vs. `78.76%` on-time/fast)

Reproduce the raw download and read-only audit (raw files in `data/raw/` are never edited or overwritten):
```bash
python src/download_data.py
python src/inspect_raw.py
```

## Running Part A (Data Quality & Insights Pipeline)

1. *(Optional if raw files are already present)* Download raw permits & official community area lookup:
   ```bash
   python src/download_data.py
   ```
2. Run all Part A unit & SQLite integration tests:
   ```bash
   pytest -v
   ```
3. Run the reproducible Part A pipeline (cleaning, validation quality gate, Pandas/NumPy summaries, SQLite join, charts, and reports):
   ```bash
   python src/run_part_a.py
   ```
4. Demonstrate the **Bonus Quality Gate** failing loudly on a deliberately corrupted copy and passing on the real dataset:
   ```bash
   python src/run_part_a.py --demo-quality-gate
   ```

## Running Part B (Tabular ML Pipeline)

*To be completed once Part B training and inference scripts are implemented.*

- Train & evaluate models: _TBD_
- Run inference on unseen rows: _TBD_

## Findings & Figures

### Part A: Data Quality & Validation Results

Full before-and-after metrics and tables live in [outputs/reports/data_quality_report.md](outputs/reports/data_quality_report.md) and [outputs/reports/metrics.json](outputs/reports/metrics.json).

- **Raw vs. Cleaned**: Processed **`16,934` rows** (`0` duplicates removed) from `29` raw columns to `41` cleaned/feature columns; normalized **`10,952`** Unicode en-dash values in `permit_type`, fixed **`41`** invalid `contact_1_state` entries (`'ILLINOIS'`/`'IL.'` -> `'IL'`), converted **`3`** `community_area == 0` and **`3`** `ward == 0` sentinels to `pd.NA`, filled **`10,006`** categorical nulls (`"UNSPECIFIED"`/`"UNKNOWN"`), and flagged **`543`** `reported_cost <= $1` placeholders plus **`41`** `> $10M` mega-projects (`99th` percentile cap `$3,083,746.50`) while preserving numeric nulls to prevent Part B leakage.
- **Quality Gate (Bonus Challenge)**: Enforced a `99.00%` minimum row validation pass rate (`src/validation.py`):
  - **Real Dataset**: **PASSED** with **`100.0000%`** row validation pass rate (`16,934 / 16,934` valid rows; `outputs/reports/metrics.json`).
  - **Deliberately Corrupted Copy (`--demo-quality-gate`)**: **FAILED loudly** (`ValidationError`) with **`97.0474%`** pass rate (`500` invalid rows caught across negative `processing_time`, invalid `latitude`, invalid `street_direction`, invalid `contact_1_state`, and `is_delayed` nulls; logged in `outputs/reports/metrics_corrupted_demo.json`) without writing cleaned outputs.
- **NumPy & Pandas Key Insights**: Processing time has a mean of **`27.04` days** (`std = 65.12` days), median **`4.0` days**, and p90 **`72.0` days**. Across `15,195` permits with valid reported cost `> $1.00`, `numpy.corrcoef` shows a positive correlation (`r = 0.3407`) between `log(1 + cost)` and `log(1 + processing_time)`.

### Part A Visualizations (`outputs/figures/`)

1. ![Processing Time and Delay Rate by Review Type](outputs/figures/01_processing_time_by_review_type.png)
   *Shows that `EXPRESS PERMIT PROGRAM` applications clear with a median of 1 day (`6.81%` delayed), whereas `STANDARD PLAN REVIEW` (`68.29%` delayed) and `DIRECT DEVELOPER SERVICES` (`92.59%` delayed) account for the steepest review bottlenecks.*
2. ![Monthly Application Volume and Delay Rate](outputs/figures/02_monthly_volume_and_delay_rate.png)
   *Shows H1 2024 permit applications increasing from January (`2,266`) into spring (`3,005–3,088`/month in April–June) while monthly delay rates remained between `18.31%` and `25.77%`.*
3. ![Reported Cost Distribution by Processing Tier](outputs/figures/03_cost_vs_processing_tier.png)
   *Shows median reported construction cost rises steadily from same-day approvals (`$4,000` median) up to `Severely Delayed (>90d)` projects (`$80,000` median).*
4. ![Top 15 Chicago Community Areas (SQLite JOIN)](outputs/figures/04_top_community_areas_sql.png)
   *Shows neighborhood-level permitting concentration from the SQLite join, led by `Loop` (`1,386`), `Near North Side` (`1,373`), and `Near West Side` (`868`), with `West Town` experiencing a `34.48%` delay rate.*

### Part A SQLite Query & Explanation ([sql/community_area_insights.sql](sql/community_area_insights.sql))

```sql
SELECT
    c.community_area,
    c.area_name,
    COUNT(*) AS permit_count,
    SUM(p.is_delayed) AS delayed_count,
    ROUND(100.0 * AVG(p.is_delayed), 2) AS delayed_rate_pct,
    ROUND(AVG(p.processing_time), 2) AS avg_processing_days,
    ROUND(SUM(COALESCE(p.reported_cost, 0.0)), 2) AS total_reported_cost_usd,
    ROUND(AVG(CASE WHEN p.reported_cost > 1.0 THEN p.reported_cost END), 2) AS avg_reported_cost_usd,
    ROUND(SUM(p.total_fee), 2) AS total_fees_usd
FROM permits AS p
INNER JOIN community_areas AS c
    ON p.community_area = c.community_area
WHERE p.community_area IS NOT NULL
GROUP BY c.community_area, c.area_name
HAVING COUNT(*) >= 100
ORDER BY permit_count DESC;
```

- **Result Explanation**: Joining the `16,934` cleaned permits against the `77` official Chicago community area names (`data/raw/chicago_community_areas.csv`) returned **`57` neighborhoods** with `>= 100` permits (`outputs/reports/sql_community_area_insights.csv`). Downtown/central neighborhoods dominate volume (`Loop`: `1,386` permits at `14.14%` delayed; `Near North Side`: `1,373` permits with `$690.0M` total reported cost), while outer/residential neighborhoods like `South Deering` (`4.76%` delayed) and `Ashburn` (`6.74%` delayed) exhibit much lower delay rates than `West Town` (`34.48%` delayed) or `Bridgeport` (`33.33%` delayed).

## Screenshots

*Checkpoint and output screenshots stored in [screenshots/](screenshots/) will be embedded here as checkpoints are completed.*

## Part C Exploration

See [docs/exploration.md](docs/exploration.md) and the accompanying artifacts in [sql/](sql/) and [.github/workflows/](.github/workflows/).

## Tools & Academic Integrity Disclosure

All code, analysis, and documentation in this repository are understood and explainable line-by-line by the author. Tools used during development:
- Python 3.13 (`pandas`, `numpy`, `matplotlib`, `seaborn`, `scikit-learn`, `joblib`, `scipy`, `requests`, `openpyxl`, `sqlite3`, `pytest`, `ruff`)
- AI coding assistant (used as a learning and scaffolding aid; all decisions verified and explainable by the author)
