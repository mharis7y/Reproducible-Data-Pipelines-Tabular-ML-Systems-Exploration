# Checkpoint 0: Dataset Proposal

## 1. Dataset Selection & Provenance

- **Dataset Title**: City of Chicago Building Permits (H1 2024 Operational Extract)
- **Operational Source**: City of Chicago — Department of Buildings (via Chicago Data Portal Socrata Open Data API)
- **Portal URL**: https://data.cityofchicago.org/Buildings/Building-Permits/ydr8-5enu
- **API Endpoint**: `https://data.cityofchicago.org/resource/ydr8-5enu.csv`
- **Licence**: City of Chicago Data Terms of Use — Public Open Government Data, permitted for public, educational, and analytical use (https://www.chicago.gov/city/en/narr/foia/data_disclaimer.html)
- **Access Date**: `2026-11-21`
- **Extract Scope**: All building permit applications with `application_start_date` in H1 2024 (`2024-01-01` through `2024-06-30`), deterministically ordered by `application_start_date ASC, id ASC`.
- **Dimensions & File Size**: **16,934 rows × 29 columns** (`7.55 MB` / `7,916,452 bytes`), SHA-256 `73ce902450df764ea5cb235a0e0ea49e1159ba6c5ad2026cd15ffaf26dd23805`.

## 2. Schema Mix & Qualification Check

The extract comfortably exceeds the minimum requirements (`>= 5,000` rows, `>= 8` columns) and combines three data modalities:
- **Date/Time (2 columns)**: `application_start_date`, `issue_date`.
- **Numeric (14 columns)**: `processing_time`, `street_number`, 7 fee columns (`building_fee_paid`, `zoning_fee_paid`, `other_fee_paid`, `subtotal_paid`, `subtotal_unpaid`, `subtotal_waived`, `total_fee`), `reported_cost`, 2 nullable integer-coded geographic columns (`community_area`, `ward`), plus `latitude` and `longitude`.
- **Categorical / Text / Identifiers (13 columns)**: `id`, `permit_`, `permit_status`, `permit_milestone`, `permit_type`, `review_type`, `street_direction`, `street_name`, `work_type`, `work_description`, `contact_1_type`, `contact_1_city`, `contact_1_state`.

## 3. Measured Raw Data Quality Problems

Auditing the raw extract with `src/inspect_raw.py` (without modifying the raw file) revealed concrete, real-world quality issues suited for Part A cleaning and validation:
1. **Unicode / Formatting Inconsistency**: In `permit_type`, **10,952 rows (64.67%)** contain an en-dash (`'\u2013'`) in `'PERMIT – EXPRESS PERMIT PROGRAM'`, whereas the remaining 7 permit types use an ASCII hyphen (`'-'`).
2. **Invalid & Inconsistent State Codes**: In `contact_1_state`, **41 rows** contain non-standard entries (`'ILLINOIS'`: 39, `'IL.'`: 2) instead of 2-letter uppercase codes, plus **69 missing rows (0.41%)**.
3. **Substantial Missingness Across Operational Fields**: `work_type` is missing in **5,982 rows (35.33%)**; `permit_status` and `permit_milestone` are each missing in **1,946 rows (11.49%)**; `reported_cost` is missing in **1,196 rows (7.06%)**; `latitude`/`longitude` in **333 rows (1.97%)**; `community_area`/`ward` in **244 rows (1.44%)**; `contact_1_city` in **58 rows (0.34%)**; and `contact_1_type` in **5 rows (0.03%)**.
4. **Placeholder Zeros & Extreme Skew in `reported_cost`**: **160 rows** report `$0.00`, **543 rows** report `<= $1.00`, and **41 rows** exceed `$10,000,000` (max `$259,000,000.00`, median `$10,640.00`).
5. **Heavy Right-Tail Skew in `processing_time`**: While `5,466` permits are approved same-day (`0` days, median `4.0` days), **137 rows** exceed `365` days (max `1,034` days).
6. **Geographic Code Anomalies**: `community_area` contains **78** unique values (Chicago has 77 official community areas) and `ward` contains **51** unique values (Chicago has 50 official wards), indicating sentinel/invalid area codes that Part A validation rules will inspect and handle explicitly.

## 4. Suitability for Both Part A & Part B

Using a single operational dataset allows the cleaned output of Part A (`data/cleaned/`) to flow directly into Part B:

- **Part A (Data Quality & Insights Pipeline)**: Supports testable normalization (Unicode dash & state-code standardization), numeric range & geographic bounds validation, NumPy vectorized transformations (e.g., log-scaled cost and processing-time indicators), Pandas `groupby`/`pivot_table` summaries across `review_type`, `permit_type`, and `community_area`, at least 3 charts, and a meaningful SQLite join against a Chicago community-area lookup table.
- **Part B (End-to-End Tabular ML Baseline)**:
  - **Target (`is_delayed`)**: Binary classification predicting whether a permit application takes longer than 30 days to be issued (`processing_time > 30`).
  - **Real-World Utility**: Helps contractors, property owners, and city permitting managers anticipate long review queues at application submission time and allocate plan-review capacity proactively.
  - **Observed Class Balance**: **3,597 delayed (`21.24%`)** vs. **13,337 on-time/fast (`78.76%`)** — moderately imbalanced, making accuracy insufficient and motivating precision, recall, F1, ROC-AUC, and PR-AUC.
  - **Why H1 2024 Avoids Right-Censoring**: Applications submitted between Jan–Jun 2024 have had over two years (through `2026-11-16`) to complete processing, avoiding bias from recently filed permits still awaiting review.
  - **Identified Leakage Columns (Excluded in Part B)**: `issue_date` and `processing_time` (directly define the target), `permit_status` and `permit_milestone` (reflect post-application lifecycle outcomes), and post-issuance fee payment/waiver columns (`building_fee_paid`, `zoning_fee_paid`, `other_fee_paid`, `subtotal_paid`, `subtotal_unpaid`, `subtotal_waived`, `total_fee`) which are finalized during or after review.
  - **Planned Split Strategy**: Chronological (time-based) train/test split (e.g., Jan–Apr 2024 for training/cross-validation and May–Jun 2024 as the final holdout test set), justified because operational permit predictors must generalize forward in time.
