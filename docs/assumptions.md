# Assumptions, Limitations & Model Card

## Part A: Data Quality & Cleaning Assumptions

1. **Non-Destructive Raw Data Preservation**: Raw extracts in `data/raw/` (`chicago_building_permits_2024_h1.csv` and `chicago_community_areas.csv`) are strictly read-only. Re-running `python src/download_data.py` skips overwriting existing raw files unless `--force` is passed. All cleaned output is written separately to `data/cleaned/chicago_building_permits_cleaned.csv`.
2. **Unicode & State Code Standardization**:
   - In `permit_type`, Unicode en-dash (`\u2013`) and em-dash (`\u2014`) characters are normalized to ASCII hyphens (`-`), resolving the `10,952` (`64.67%`) formatting discrepancies in `'PERMIT - EXPRESS PERMIT PROGRAM'`.
   - In `contact_1_state`, whitespace and trailing periods are stripped, text is uppercased, and `'ILLINOIS'` is mapped to `'IL'` (fixing all `41` non-2-letter entries: `39` `'ILLINOIS'` and `2` `'IL.'`).
3. **Sentinel Geo ID Handling (`community_area` & `ward`)**:
   - The `3` records with `community_area == 0` and `3` records with `ward == 0` represent unmapped/citywide sentinel entries (outside Chicago's official `1..77` areas and `1..50` wards). These `0` sentinels are converted to `pd.NA` (`Int64`), whereas any non-zero out-of-range values are intentionally left untouched so `src/validation.py` catches data corruption loudly.
4. **Leakage-Safe Missing Value Strategy**:
   - Missing categorical attributes are explicitly labelled (`work_type` -> `"UNSPECIFIED"` for `5,982` rows; `permit_status`, `permit_milestone`, `contact_1_type`, `contact_1_city`, `contact_1_state` -> `"UNKNOWN"`).
   - Missing numeric/coordinate values (`reported_cost` in `1,196` rows, `latitude`/`longitude` in `333` rows) are **not** globally imputed in Part A; instead, explicit boolean missingness indicator columns (`reported_cost_missing`, `coords_missing`) are added so Part B can fit imputers strictly inside the training split.
5. **Derived Vectorized Features & Winsorized Views**:
   - `is_delayed` (`processing_time > 30` days) and `processing_tier` categorize review durations via NumPy vectorized rules (`np.where`, `np.select`).
   - `reported_cost_winsorized` (clipped at the `99th` percentile `$3,083,746.50` via `np.clip`) and `log_reported_cost` (`np.log1p`) support visualizations and skewed-cost analysis without altering raw `reported_cost`.

## Part A: Limitations & What Was Intentionally Not Fixed

1. **Placeholder `$0` / `<= $1` Reported Costs (`543` rows)**: Entries such as `$0.00` (`160` rows) or `$1.00` frequently correspond to administrative updates, sign permits, or fee-only permits where construction valuation is not applicable. Rather than deleting or guessing costs, they are retained with `reported_cost_is_placeholder = True` and excluded from cost-ratio (`fee_to_cost_ratio = NaN` when `cost <= $1.00`) and cost boxplot summaries.
2. **Extreme `$10M+` Construction Costs (`41` rows, max `$259M`)**: Verified commercial/institutional mega-developments genuinely exist in Chicago permitting. They are preserved in `reported_cost` and flagged (`reported_cost_outlier_flag = True`) rather than dropped.
3. **Long-Tail Processing Delays `> 365` Days (`137` rows, max `1,034` days)**: Cross-checking confirms `processing_time == (issue_date - application_start_date).days` for `100%` of records (`0` discrepancies). Multi-year review durations reflect real zoning/developer-service delays and are preserved.
4. **Free-Text `work_description` (`14,467` unique descriptions)**: Left unparsed/un-normalized beyond whitespace trimming to avoid distorting original applicant scope text; optional keyword extraction belongs to feature engineering in Part B.
5. **Unmapped Geographic Records (`244` missing `community_area`/`ward`, `333` missing `latitude`/`longitude`)**: Not geocoded externally so Part A remains 100% offline-reproducible from the saved raw CSV; excluded cleanly via `WHERE p.community_area IS NOT NULL` in the SQLite join.

---

## Part B: Model Card

### Problem Framing & Target
- **Prediction Target**: `is_delayed` (`1` if `processing_time > 30` days else `0`).
- **Problem Type**: Binary tabular classification on imbalanced operational intake records (`21.24%` delayed overall; `21.41%` in Jan–May training split, `20.47%` in June holdout test split).
- **Intended Users & Decision Supported**: City of Chicago Department of Buildings intake planners (early bottleneck triage and staffing) and contractors/applicants (realistic permit turnaround expectations at submission time).

### Leakage Exclusions
All post-application, target-derived, and full-dataset-scaled columns are strictly excluded from `INPUT_FEATURE_COLUMNS`:
- **Direct Target / Outcome Timing**: `issue_date`, `processing_time`, `processing_tier` (only exist after review finishes; directly define `is_delayed`).
- **Post-Application Lifecycle Status**: `permit_status`, `permit_milestone` (updated after submission, e.g., `COMPLETE`, `EXPIRED`).
- **Post-Review Fee Fields**: `building_fee_paid`, `zoning_fee_paid`, `other_fee_paid`, `subtotal_paid`, `subtotal_unpaid`, `subtotal_waived`, `total_fee`, `fee_to_cost_ratio` (assessed/settled during review or issuance).
- **Full-Dataset-Computed Columns**: `reported_cost_winsorized` (its 99th-percentile cap was computed across all H1 2024 rows in Part A), plus redundant pre-derived flags/log cost which are recomputed strictly row-wise inside `PermitIntakeFeatureBuilder`.

### Split Strategy & Preprocessing
- **Chronological Train/Test Split (`application_start_date < 2024-06-01`)**: Splits `13,929` Jan–May 2024 permits into training/cross-validation and reserves `3,005` June 2024 permits (`17.7%`) as a strict future holdout test set evaluated **once** at the end. Time-based splitting matches real deployment (predicting future permits from historical records) and prevents temporal leakage across overlapping monthly review queues.
- **Cross-Validation (`TimeSeriesSplit(n_splits=5)`)**: All model comparison and hyperparameter tuning (`GridSearchCV`) run chronologically inside the training set only.
- **Unified Single Pipeline (`src/features.py`)**: `PermitIntakeFeatureBuilder` -> `ColumnTransformer` (`SimpleImputer(median)` + `StandardScaler` for 12 numeric intake features; `SimpleImputer(constant="MISSING")` + `OneHotEncoder(handle_unknown="ignore", min_frequency=20)` for 7 categorical features) -> estimator inside a single `sklearn.pipeline.Pipeline` saved via `joblib`.

### Model Comparison, Metric Justification & Feature Importance
- **Why PR-AUC, ROC-AUC, F1, Precision & Recall Over Accuracy**: With `~79.5%` on-time permits in training CV, `DummyClassifier(most_frequent)` achieves `0.7941` accuracy with `0.0000` recall and `0.0000` F1. Therefore, **PR-AUC (`average_precision`)** is the primary selection metric (focusing on minority-class delay ranking), supported by ROC-AUC, F1, Precision, Recall, and Confusion Matrix analysis.
- **5-Fold CV Winner**: `Random Forest (Tuned)` (`max_depth=12, min_samples_leaf=5`) achieved the highest mean CV PR-AUC (**`0.7330 ± 0.0249`**, ROC-AUC `0.8868`, F1 `0.6662`, Recall `0.8347`), narrowly ahead of `HistGradientBoosting (Tuned)` (`0.7327`) and clearly outperforming `Logistic Regression (Balanced)` (`0.6868`), `KNN (k=25)` (`0.6761`), and `Dummy` (`0.2059`).
- **Final Holdout Test Set (`n=3,005`)**: PR-AUC **`0.7757`** (vs `0.2047` prevalence), ROC-AUC **`0.9026`**, F1 **`0.6923`**, Precision **`0.5983`**, Recall **`0.8211`**, Accuracy **`0.8506`** (`TN=2,051`, `FP=339`, `FN=110`, `TP=505`).
- **Permutation Importance**: Top drivers of test PR-AUC were `review_type` (`+0.1137`), `work_type` (`+0.0851`), `work_description` (`+0.0794`), `permit_type` (`+0.0744`), `contact_1_type` (`+0.0325`), and `reported_cost` (`+0.0297`), which directly reflects Chicago's operational split between fast automated express workflows and multi-reviewer standard plan reviews.

### Assumptions, Limitations & Error Analysis
- **Boundary-Threshold Ambiguity (False Positives, `339` rows)**: Many high-confidence false positives are `STANDARD PLAN REVIEW` projects cleared in `19–30` days right near the binary `>30` day cutoff (e.g., ID `3379835` at `30d`, prob `0.9245`; `3382552` at `29d`, prob `0.9230`; `3382837` at `27d`, prob `0.9461`) or `SELF CERT` permits (`Precision=0.4184, Recall=1.0000`), where `class_weight="balanced_subsample"` favors catching delays over minimizing false alarms.
- **Unobserved Post-Intake Holds (False Negatives, `110` rows)**: Concentrated in `EXPRESS PERMIT PROGRAM` (`Recall=0.2986`, `F1=0.3839`)—especially `Small-Scale Solar PV System` (`N2135589`: 38d, prob `0.0684`) and `Administrative Change` permits with missing cost (`N2139640`: 100d, prob `0.1173`). Delays caused by post-submission corrections or external utility holds are invisible from intake fields alone.
- **No Full-Text NLP Embedding**: `work_description` contributes only via character length and word count (`work_desc_len`, `work_desc_words`); specific structural keywords are not tokenized.

### Intended Use & Risks
- **Intended Use**: Early risk-triage indicator (`Low` / `Medium` / `High` delay probability bands) to help planners and applicants flag potential review queues before formal plan check begins.
- **Out-of-Scope / Misuse Risks**: Must **not** be used to deny permits, enforce punitive SLAs, or replace human architectural/zoning review. Because precision is `59.83%` at the default `0.50` threshold, flagged permits should trigger advisory review rather than automatic escalation.
- **Bias / Subgroup Risks**: Performance varies substantially across `review_type` (`DIRECT DEVELOPER SERVICES` F1 `0.9825` vs `EXPRESS` F1 `0.3839`) and cost availability (`>$100K` F1 `0.8135` vs `Missing` cost `0.0000`, `Placeholder <=$1` F1 `0.4000`). Historical processing delays also reflect City staffing/queue backlogs during H1 2024 rather than intrinsic applicant merit.
