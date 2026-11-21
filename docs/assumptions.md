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
- **Prediction Target**: _TBD_
- **Problem Type**: _Classification / Regression (TBD)_
- **Intended Users & Decision Supported**: _TBD_

### Leakage Exclusions
- _List columns excluded before splitting/training and explain why each leaks target information._

### Split Strategy & Preprocessing
- _Explain why random, stratified, or time-based splitting was chosen and confirm fitting occurred on training data only._

### Assumptions & Limitations
- _Key assumptions made by the baseline and candidate models, and known failure modes from error analysis._

### Intended Use & Risks
- **Intended Use**: _TBD_
- **Out-of-Scope / Misuse Risks**: _TBD_
- **Bias / Subgroup Risks**: _TBD_
