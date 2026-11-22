# Part B: End-to-End Tabular ML Evaluation & Error Analysis Report

## 1. Problem Framing, Target & Leakage Control

- **Target (`is_delayed`)**: Binary classification predicting at application intake whether a permit will take `> 30` days (`1`) vs. `<= 30` days (`0`).
- **Chronological Split (`application_start_date < 2024-06-01`)**:
  - Training / 5-Fold `TimeSeriesSplit` CV (Jan–May 2024): **`13,929` rows** (`21.41%` delayed)
  - Final Holdout Test Set (June 2024, evaluated once): **`3,005` rows** (`20.47%` delayed)
- **Strict Input Features (`14` columns)**: `permit_type, review_type, work_type, reported_cost, community_area, street_direction, street_number, latitude, longitude, contact_1_type, contact_1_city, contact_1_state, application_dayofweek, work_description`
- **Excluded Leakage Columns (`14` columns)**: `issue_date, processing_time, processing_tier, permit_status, permit_milestone, building_fee_paid, zoning_fee_paid, other_fee_paid, subtotal_paid, subtotal_unpaid, subtotal_waived, total_fee, fee_to_cost_ratio, reported_cost_winsorized`

## 2. Model Comparison Table (5-Fold `TimeSeriesSplit` CV on Training Data)

| model | cv_pr_auc_mean | cv_pr_auc_std | cv_roc_auc_mean | cv_roc_auc_std | cv_f1_mean | cv_precision_mean | cv_recall_mean | cv_accuracy_mean | best_params |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Random Forest (Tuned) | 0.733 | 0.0249 | 0.8868 | 0.0204 | 0.6662 | 0.5546 | 0.8347 | 0.8277 | {"model__max_depth": 12, "model__min_samples_leaf": 5} |
| HistGradientBoosting (Tuned) | 0.7327 | 0.0319 | 0.8868 | 0.0221 | 0.6743 | 0.5695 | 0.827 | 0.8354 | {"model__learning_rate": 0.05, "model__max_depth": 4, "model__min_samples_leaf": 20} |
| Logistic Regression (Balanced) | 0.6868 | 0.0403 | 0.8755 | 0.0206 | 0.6618 | 0.5458 | 0.8415 | 0.8228 | default |
| KNN (k=25, Distance) | 0.6761 | 0.0278 | 0.8728 | 0.0156 | 0.636 | 0.6622 | 0.6134 | 0.8555 | default |
| Dummy (Most Frequent) | 0.2059 | 0.0085 | 0.5 | 0.0 | 0.0 | 0.0 | 0.0 | 0.7941 | default |

- **Selected Winner (Highest CV PR-AUC)**: **`Random Forest (Tuned)`** (best params: `{"model__max_depth": 12, "model__min_samples_leaf": 5}`)

## 3. Final Holdout Test Performance (June 2024, `n=3,005`)

- **PR-AUC (Average Precision)**: **`0.7757`** (baseline prevalence = `0.2047`)
- **ROC-AUC**: **`0.9026`**
- **F1 Score**: **`0.6923`** | **Precision**: **`0.5983`** | **Recall**: **`0.8211`** | **Accuracy**: **`0.8506`**
- **Confusion Matrix**: `TN=2,051`, `FP=339`, `FN=110`, `TP=505`

## 4. Permutation Feature Importance (June 2024 Holdout Set)

| feature | importance_mean | importance_std |
| --- | --- | --- |
| review_type | 0.11368 | 0.01328 |
| work_type | 0.08509 | 0.0149 |
| work_description | 0.07943 | 0.00599 |
| permit_type | 0.07444 | 0.01265 |
| contact_1_type | 0.03246 | 0.00442 |
| reported_cost | 0.02974 | 0.0041 |
| longitude | 0.00648 | 0.00127 |
| community_area | 0.00441 | 0.00208 |
| latitude | 0.00418 | 0.00099 |
| street_number | 0.003 | 0.00137 |

## 5. Error Analysis & Subgroup Performance

### Performance by `review_type`

| review_type | count | actual_delayed_rate_pct | predicted_delayed_rate_pct | precision | recall | f1 | accuracy |
| --- | --- | --- | --- | --- | --- | --- | --- |
| EXPRESS PERMIT PROGRAM | 2018 | 7.14 | 3.96 | 0.5375 | 0.2986 | 0.3839 | 0.9316 |
| STANDARD PLAN REVIEW | 392 | 66.58 | 88.52 | 0.7522 | 1.0 | 0.8586 | 0.7806 |
| SELF CERT | 248 | 40.32 | 96.37 | 0.4184 | 1.0 | 0.59 | 0.4395 |
| SIGN PERMIT | 145 | 50.34 | 99.31 | 0.5069 | 1.0 | 0.6728 | 0.5103 |
| CONVEYANCE DEVICE PERMIT | 88 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 1.0 |
| DEMOLITION PERMIT | 66 | 13.64 | 6.06 | 0.0 | 0.0 | 0.0 | 0.803 |
| DIRECT DEVELOPER SERVICES | 29 | 96.55 | 100.0 | 0.9655 | 1.0 | 0.9825 | 0.9655 |
| EASY PERMIT | 18 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 1.0 |
| TRADITIONAL DEVELOPER SERVICES | 1 | 0.0 | 100.0 | 0.0 | 0.0 | 0.0 | 0.0 |

### Performance by `reported_cost` Bracket

| cost_bracket | count | actual_delayed_rate_pct | predicted_delayed_rate_pct | precision | recall | f1 | accuracy |
| --- | --- | --- | --- | --- | --- | --- | --- |
| $2 - $10K | 1187 | 13.14 | 18.62 | 0.5249 | 0.7436 | 0.6154 | 0.8778 |
| $10K - $100K | 1039 | 19.73 | 31.67 | 0.535 | 0.8585 | 0.6592 | 0.8248 |
| >$100K | 439 | 49.89 | 64.92 | 0.7193 | 0.9361 | 0.8135 | 0.7859 |
| Missing | 231 | 1.73 | 0.0 | 0.0 | 0.0 | 0.0 | 0.9827 |
| Placeholder (<=$1) | 109 | 28.44 | 8.26 | 0.8889 | 0.2581 | 0.4 | 0.7798 |

### Highest-Confidence False Positives (Predicted Delayed, Actually Fast `<=30d`)

| id | review_type | permit_type | reported_cost | processing_time | delay_probability | error_type |
| --- | --- | --- | --- | --- | --- | --- |
| 3382837 | STANDARD PLAN REVIEW | PERMIT - RENOVATION/ALTERATION | 80000.0 | 27 | 0.9461 | False Positive |
| 3379272 | STANDARD PLAN REVIEW | PERMIT - RENOVATION/ALTERATION | 64500.0 | 26 | 0.9437 | False Positive |
| 3379835 | STANDARD PLAN REVIEW | PERMIT - RENOVATION/ALTERATION | 100000.0 | 30 | 0.9245 | False Positive |
| 3382552 | STANDARD PLAN REVIEW | PERMIT - RENOVATION/ALTERATION | 350000.0 | 29 | 0.923 | False Positive |
| 3380669 | STANDARD PLAN REVIEW | PERMIT - RENOVATION/ALTERATION | 138000.0 | 19 | 0.9199 | False Positive |

### Highest-Confidence False Negatives (Predicted Fast, Actually Delayed `>30d`)

| id | review_type | permit_type | reported_cost | processing_time | delay_probability | error_type |
| --- | --- | --- | --- | --- | --- | --- |
| N2135589 | EXPRESS PERMIT PROGRAM | PERMIT - EXPRESS PERMIT PROGRAM | 24000.0 | 38 | 0.0684 | False Negative |
| N2137495 | EXPRESS PERMIT PROGRAM | PERMIT - EXPRESS PERMIT PROGRAM | 12000.0 | 31 | 0.0712 | False Negative |
| N2093532 | EXPRESS PERMIT PROGRAM | PERMIT - EXPRESS PERMIT PROGRAM | 20000.0 | 48 | 0.074 | False Negative |
| N2147760 | EXPRESS PERMIT PROGRAM | PERMIT - EXPRESS PERMIT PROGRAM | 40000.0 | 39 | 0.0812 | False Negative |
| N2130372 | EXPRESS PERMIT PROGRAM | PERMIT - EXPRESS PERMIT PROGRAM | 6000.0 | 91 | 0.0825 | False Negative |
