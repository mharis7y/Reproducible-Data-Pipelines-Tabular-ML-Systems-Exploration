# Name: Muhammad Haris
# Roll Number: TRN-2026-000809
# Date: 2026-11-22
"""End-to-end Part B training, CV model comparison, error analysis, and pipeline saving."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import joblib
import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.inspection import permutation_importance
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    confusion_matrix,
    f1_score,
    make_scorer,
    precision_recall_curve,
    precision_score,
    recall_score,
    roc_auc_score,
    roc_curve,
)
from sklearn.model_selection import GridSearchCV, TimeSeriesSplit, cross_validate
from sklearn.neighbors import KNeighborsClassifier

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.features import (
    EXCLUDED_IDENTIFIER_COLUMNS,
    INPUT_FEATURE_COLUMNS,
    LEAKAGE_COLUMNS,
    TARGET_COLUMN,
    TEST_CUTOFF_DATE,
    build_model_pipeline,
    chronological_train_test_split,
    prepare_feature_frame,
)

DEFAULT_CLEANED_PATH = (
    PROJECT_ROOT / "data" / "cleaned" / "chicago_building_permits_cleaned.csv"
)
DEFAULT_MODELS_DIR = PROJECT_ROOT / "models"
DEFAULT_REPORTS_DIR = PROJECT_ROOT / "outputs" / "reports"
DEFAULT_FIGURES_DIR = PROJECT_ROOT / "outputs" / "figures"


def _configure_plot_style() -> None:
    """Apply consistent visual styling across all Part B figures."""
    sns.set_theme(style="whitegrid", context="notebook")
    plt.rcParams["axes.spines.top"] = False
    plt.rcParams["axes.spines.right"] = False


def _df_to_markdown(df: pd.DataFrame) -> str:
    """Format a summary DataFrame cleanly as a Markdown table without optional deps."""
    headers = [str(col) for col in df.columns]
    header_line = "| " + " | ".join(headers) + " |"
    sep_line = "| " + " | ".join("---" for _ in headers) + " |"
    rows = []
    for _, row in df.iterrows():
        cells = [str(val).replace("|", "\\|") for val in row.tolist()]
        rows.append("| " + " | ".join(cells) + " |")
    return "\n".join([header_line, sep_line, *rows])


def _cv_scoring() -> dict[str, Any]:
    """Return zero-division-safe multi-metric scoring dictionary for imbalanced CV."""
    return {
        "pr_auc": "average_precision",
        "roc_auc": "roc_auc",
        "f1": make_scorer(f1_score, zero_division=0),
        "precision": make_scorer(precision_score, zero_division=0),
        "recall": make_scorer(recall_score, zero_division=0),
        "accuracy": "accuracy",
    }


def _evaluate_cv_pipeline(
    name: str,
    pipeline: Any,
    X_train: pd.DataFrame,
    y_train: pd.Series,
    cv: TimeSeriesSplit,
    best_params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Run TimeSeriesSplit cross-validation on training data and summarize metrics."""
    scores = cross_validate(
        pipeline,
        X_train,
        y_train,
        cv=cv,
        scoring=_cv_scoring(),
        n_jobs=-1,
        error_score="raise",
    )
    return {
        "model": name,
        "cv_pr_auc_mean": round(float(np.mean(scores["test_pr_auc"])), 4),
        "cv_pr_auc_std": round(float(np.std(scores["test_pr_auc"])), 4),
        "cv_roc_auc_mean": round(float(np.mean(scores["test_roc_auc"])), 4),
        "cv_roc_auc_std": round(float(np.std(scores["test_roc_auc"])), 4),
        "cv_f1_mean": round(float(np.mean(scores["test_f1"])), 4),
        "cv_precision_mean": round(float(np.mean(scores["test_precision"])), 4),
        "cv_recall_mean": round(float(np.mean(scores["test_recall"])), 4),
        "cv_accuracy_mean": round(float(np.mean(scores["test_accuracy"])), 4),
        "best_params": json.dumps(best_params) if best_params else "default",
    }


def _assign_cost_bucket(cost_series: pd.Series) -> pd.Series:
    """Bucket reported construction cost into interpretable dollar brackets."""
    cost = pd.to_numeric(cost_series, errors="coerce")
    buckets = np.select(
        [
            cost.isna(),
            cost <= 1.0,
            (cost > 1.0) & (cost <= 10_000.0),
            (cost > 10_000.0) & (cost <= 100_000.0),
            cost > 100_000.0,
        ],
        [
            "Missing",
            "Placeholder (<=$1)",
            "$2 - $10K",
            "$10K - $100K",
            ">$100K",
        ],
        default="Other",
    )
    return pd.Series(buckets, index=cost_series.index)


def _compute_subgroup_metrics(
    df_eval: pd.DataFrame,
    group_col: str,
    min_count: int = 1,
) -> pd.DataFrame:
    """Compute F1, Precision, Recall, Accuracy, and positive rate per subgroup."""
    rows: list[dict[str, Any]] = []
    for group_val, grp in df_eval.groupby(group_col, dropna=False):
        if len(grp) < min_count:
            continue
        y_true = grp["actual_is_delayed"].to_numpy(dtype=int)
        y_pred = grp["predicted_is_delayed"].to_numpy(dtype=int)
        rows.append(
            {
                group_col: str(group_val),
                "count": len(grp),
                "actual_delayed_rate_pct": round(float(y_true.mean() * 100.0), 2),
                "predicted_delayed_rate_pct": round(float(y_pred.mean() * 100.0), 2),
                "precision": round(float(precision_score(y_true, y_pred, zero_division=0)), 4),
                "recall": round(float(recall_score(y_true, y_pred, zero_division=0)), 4),
                "f1": round(float(f1_score(y_true, y_pred, zero_division=0)), 4),
                "accuracy": round(float(accuracy_score(y_true, y_pred)), 4),
            }
        )
    return pd.DataFrame(rows).sort_values("count", ascending=False).reset_index(drop=True)


def _plot_model_comparison(comparison_df: pd.DataFrame, out_path: Path) -> Path:
    """Save grouped bar chart comparing CV PR-AUC, ROC-AUC, and F1 across models."""
    ordered = comparison_df.sort_values("cv_pr_auc_mean", ascending=True).reset_index(drop=True)
    y = np.arange(len(ordered))
    height = 0.25

    fig, ax = plt.subplots(figsize=(11, 6))
    bars_pr = ax.barh(y + height, ordered["cv_pr_auc_mean"], height, label="PR-AUC (Primary)", color="#2b6cb0")
    bars_roc = ax.barh(y, ordered["cv_roc_auc_mean"], height, label="ROC-AUC", color="#2f855a")
    bars_f1 = ax.barh(y - height, ordered["cv_f1_mean"], height, label="F1 Score", color="#c05621")

    ax.set_yticks(y)
    ax.set_yticklabels(ordered["model"])
    ax.set_xlabel("5-Fold TimeSeriesSplit Cross-Validation Score (0 to 1)")
    ax.set_ylabel("Candidate Model")
    ax.set_title("Part B Model Comparison on Training CV (Sorted by Primary Metric PR-AUC)")
    ax.set_xlim(0, 1.05)
    ax.legend(loc="lower right")

    for bars in (bars_pr, bars_roc, bars_f1):
        for bar in bars:
            w = bar.get_width()
            ax.text(w + 0.01, bar.get_y() + bar.get_height() / 2, f"{w:.3f}", va="center", fontsize=8)

    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    return out_path


def _plot_confusion_and_curves(
    y_test: np.ndarray,
    y_pred: np.ndarray,
    y_prob: np.ndarray,
    model_name: str,
    out_path: Path,
) -> Path:
    """Save 3-panel plot: Confusion Matrix, ROC Curve, and Precision-Recall Curve."""
    cm = confusion_matrix(y_test, y_pred)
    cm_pct = cm / cm.sum(axis=1, keepdims=True) * 100.0
    annot = np.array(
        [
            [f"{cm[r, c]:,}\n({cm_pct[r, c]:.1f}%)" for c in range(2)]
            for r in range(2)
        ]
    )

    fpr, tpr, _ = roc_curve(y_test, y_prob)
    roc_auc = roc_auc_score(y_test, y_prob)
    precision_pts, recall_pts, _ = precision_recall_curve(y_test, y_prob)
    pr_auc = average_precision_score(y_test, y_prob)
    prevalence = float(np.mean(y_test))

    fig, (ax1, ax2, ax3) = plt.subplots(1, 3, figsize=(16, 5))

    sns.heatmap(
        cm,
        annot=annot,
        fmt="",
        cmap="Blues",
        cbar=False,
        xticklabels=["Pred On-Time (0)", "Pred Delayed (1)"],
        yticklabels=["Actual On-Time (0)", "Actual Delayed (1)"],
        ax=ax1,
    )
    ax1.set_title(f"Confusion Matrix (n={len(y_test):,})")
    ax1.set_xlabel("Predicted Label")
    ax1.set_ylabel("True Label")

    ax2.plot(fpr, tpr, color="#2b6cb0", linewidth=2.2, label=f"ROC-AUC = {roc_auc:.3f}")
    ax2.plot([0, 1], [0, 1], linestyle="--", color="gray", label="Random (0.500)")
    ax2.set_title("ROC Curve (June 2024 Test Set)")
    ax2.set_xlabel("False Positive Rate (1 - Specificity)")
    ax2.set_ylabel("True Positive Rate (Recall)")
    ax2.legend(loc="lower right")

    ax3.plot(recall_pts, precision_pts, color="#c53030", linewidth=2.2, label=f"PR-AUC = {pr_auc:.3f}")
    ax3.axhline(prevalence, linestyle="--", color="gray", label=f"Baseline Prevalence ({prevalence:.3f})")
    ax3.set_title("Precision-Recall Curve (June 2024 Test Set)")
    ax3.set_xlabel("Recall (Delayed Permits Caught)")
    ax3.set_ylabel("Precision (True Delayed Share)")
    ax3.set_xlim(0, 1.02)
    ax3.set_ylim(0, 1.02)
    ax3.legend(loc="upper right")

    fig.suptitle(
        f"Holdout Test Evaluation (June 2024): {model_name}",
        fontsize=13,
        fontweight="bold",
    )
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    return out_path


def _plot_permutation_importance(perm_df: pd.DataFrame, out_path: Path) -> Path:
    """Save horizontal bar chart of top intake features by PR-AUC permutation drop."""
    top = perm_df.head(12).sort_values("importance_mean", ascending=True)
    y_pos = np.arange(len(top))

    fig, ax = plt.subplots(figsize=(10, 6))
    bars = ax.barh(
        y_pos,
        top["importance_mean"],
        xerr=top["importance_std"],
        color="#2f855a",
        ecolor="#1a202c",
        capsize=3,
    )
    ax.set_yticks(y_pos)
    ax.set_yticklabels(top["feature"])
    ax.set_xlabel("Mean Drop in Test PR-AUC When Feature Shuffled (10 Repeats)")
    ax.set_ylabel("Raw Intake Feature")
    ax.set_title("Permutation Feature Importance on June 2024 Holdout Set")
    max_x = max((top["importance_mean"] + top["importance_std"]).max(), 0.01)
    ax.set_xlim(0, max_x * 1.24)

    for bar, val, err in zip(
        bars, top["importance_mean"], top["importance_std"], strict=True
    ):
        ax.text(
            max(val + err, 0.0) + max_x * 0.018,
            bar.get_y() + bar.get_height() / 2,
            f"{val:.4f}",
            va="center",
            fontsize=8.5,
        )

    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    return out_path


def _plot_subgroup_errors(
    rev_sub_df: pd.DataFrame,
    cost_sub_df: pd.DataFrame,
    out_path: Path,
) -> Path:
    """Save 2-panel subgroup Recall & F1 comparison by review type and cost bracket."""
    rev_plot = rev_sub_df[rev_sub_df["count"] >= 20].sort_values("f1", ascending=True)
    cost_order = ["Missing", "Placeholder (<=$1)", "$2 - $10K", "$10K - $100K", ">$100K"]
    cost_plot = cost_sub_df.set_index("cost_bracket").reindex(
        [c for c in cost_order if c in set(cost_sub_df["cost_bracket"])]
    ).reset_index()

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 5.5))

    y1 = np.arange(len(rev_plot))
    h = 0.35
    ax1.barh(y1 + h / 2, rev_plot["f1"], h, label="F1 Score", color="#2b6cb0")
    ax1.barh(y1 - h / 2, rev_plot["recall"], h, label="Recall", color="#c53030")
    ax1.set_yticks(y1)
    ax1.set_yticklabels([f"{r['review_type']} (n={int(r['count'])})" for _, r in rev_plot.iterrows()])
    ax1.set_xlabel("Holdout Test Score (0 to 1)")
    ax1.set_ylabel("Review Type Subgroup (n >= 20)")
    ax1.set_title("Subgroup Error Check by Review Type")
    ax1.set_xlim(0, 1.08)
    ax1.legend(loc="lower right")

    x2 = np.arange(len(cost_plot))
    w = 0.35
    ax2.bar(x2 - w / 2, cost_plot["f1"], w, label="F1 Score", color="#2b6cb0")
    ax2.bar(x2 + w / 2, cost_plot["recall"], w, label="Recall", color="#c53030")
    ax2.set_xticks(x2)
    ax2.set_xticklabels(
        [f"{r['cost_bracket']}\n(n={int(r['count'])})" for _, r in cost_plot.iterrows()],
        rotation=20,
        ha="right",
        fontsize=9,
        parse_math=False,
    )
    ax2.set_xlabel("Reported Construction Cost Bracket")
    ax2.set_ylabel("Holdout Test Score (0 to 1)")
    ax2.set_title("Subgroup Error Check by Reported Cost Bracket")
    ax2.set_ylim(0, 1.08)
    ax2.legend(loc="upper left")

    fig.suptitle("Part B Error Analysis Across Subgroups (June 2024 Holdout Set)", fontsize=13, fontweight="bold")
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    return out_path


def _write_evaluation_report(
    report_path: Path,
    metadata: dict[str, Any],
    comparison_df: pd.DataFrame,
    perm_df: pd.DataFrame,
    rev_sub_df: pd.DataFrame,
    cost_sub_df: pd.DataFrame,
    misclassified_df: pd.DataFrame,
) -> None:
    """Write comprehensive Part B Markdown evaluation and error analysis report."""
    test_m = metadata["test_metrics"]
    cm = metadata["confusion_matrix"]
    fp_examples = misclassified_df[misclassified_df["error_type"] == "False Positive"].head(5)
    fn_examples = misclassified_df[misclassified_df["error_type"] == "False Negative"].head(5)

    cols_show = [
        "id",
        "review_type",
        "permit_type",
        "reported_cost",
        "processing_time",
        "delay_probability",
        "error_type",
    ]
    fp_md = _df_to_markdown(fp_examples[cols_show]) if not fp_examples.empty else "_None_"
    fn_md = _df_to_markdown(fn_examples[cols_show]) if not fn_examples.empty else "_None_"

    content = f"""# Part B: End-to-End Tabular ML Evaluation & Error Analysis Report

## 1. Problem Framing, Target & Leakage Control

- **Target (`{TARGET_COLUMN}`)**: Binary classification predicting at application intake whether a permit will take `> 30` days (`1`) vs. `<= 30` days (`0`).
- **Chronological Split (`application_start_date < {TEST_CUTOFF_DATE}`)**:
  - Training / 5-Fold `TimeSeriesSplit` CV (Jan–May 2024): **`{metadata['train_rows']:,}` rows** (`{metadata['train_positive_rate_pct']:.2f}%` delayed)
  - Final Holdout Test Set (June 2024, evaluated once): **`{metadata['test_rows']:,}` rows** (`{metadata['test_positive_rate_pct']:.2f}%` delayed)
- **Strict Input Features (`{len(INPUT_FEATURE_COLUMNS)}` columns)**: `{", ".join(INPUT_FEATURE_COLUMNS)}`
- **Excluded Leakage Columns (`{len(LEAKAGE_COLUMNS)}` columns)**: `{", ".join(LEAKAGE_COLUMNS)}`

## 2. Model Comparison Table (5-Fold `TimeSeriesSplit` CV on Training Data)

{_df_to_markdown(comparison_df)}

- **Selected Winner (Highest CV PR-AUC)**: **`{metadata['winning_model']}`** (best params: `{json.dumps(metadata['best_params'])}`)

## 3. Final Holdout Test Performance (June 2024, `n={metadata['test_rows']:,}`)

- **PR-AUC (Average Precision)**: **`{test_m['pr_auc']:.4f}`** (baseline prevalence = `{metadata['test_positive_rate_pct'] / 100.0:.4f}`)
- **ROC-AUC**: **`{test_m['roc_auc']:.4f}`**
- **F1 Score**: **`{test_m['f1']:.4f}`** | **Precision**: **`{test_m['precision']:.4f}`** | **Recall**: **`{test_m['recall']:.4f}`** | **Accuracy**: **`{test_m['accuracy']:.4f}`**
- **Confusion Matrix**: `TN={cm['tn']:,}`, `FP={cm['fp']:,}`, `FN={cm['fn']:,}`, `TP={cm['tp']:,}`

## 4. Permutation Feature Importance (June 2024 Holdout Set)

{_df_to_markdown(perm_df.head(10))}

## 5. Error Analysis & Subgroup Performance

### Performance by `review_type`

{_df_to_markdown(rev_sub_df)}

### Performance by `reported_cost` Bracket

{_df_to_markdown(cost_sub_df)}

### Highest-Confidence False Positives (Predicted Delayed, Actually Fast `<=30d`)

{fp_md}

### Highest-Confidence False Negatives (Predicted Fast, Actually Delayed `>30d`)

{fn_md}
"""
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(content, encoding="utf-8")


def run_part_b_training(
    cleaned_csv: Path = DEFAULT_CLEANED_PATH,
    models_dir: Path = DEFAULT_MODELS_DIR,
    reports_dir: Path = DEFAULT_REPORTS_DIR,
    figures_dir: Path = DEFAULT_FIGURES_DIR,
) -> dict[str, Any]:
    """Train, cross-validate, compare, inspect errors, plot, and save Part B ML pipeline."""
    if not cleaned_csv.exists():
        raise FileNotFoundError(
            f"Cleaned dataset not found at '{cleaned_csv}'. Run 'python src/run_part_a.py' first."
        )

    df = pd.read_csv(cleaned_csv, low_memory=False)
    train_df, test_df = chronological_train_test_split(df, cutoff_date=TEST_CUTOFF_DATE)

    X_train = prepare_feature_frame(train_df)
    y_train = train_df[TARGET_COLUMN].astype(int)
    X_test = prepare_feature_frame(test_df)
    y_test = test_df[TARGET_COLUMN].astype(int)

    cv = TimeSeriesSplit(n_splits=5)
    comparison_rows: list[dict[str, Any]] = []
    candidate_pipelines: dict[str, tuple[Any, dict[str, Any]]] = {}

    # 1. Baseline: DummyClassifier
    dummy_pipe = build_model_pipeline(DummyClassifier(strategy="most_frequent"))
    comparison_rows.append(
        _evaluate_cv_pipeline("Dummy (Most Frequent)", dummy_pipe, X_train, y_train, cv)
    )
    candidate_pipelines["Dummy (Most Frequent)"] = (dummy_pipe, {})

    # 2. Linear Baseline: Balanced Logistic Regression
    lr_pipe = build_model_pipeline(
        LogisticRegression(max_iter=1000, class_weight="balanced", random_state=42)
    )
    comparison_rows.append(
        _evaluate_cv_pipeline("Logistic Regression (Balanced)", lr_pipe, X_train, y_train, cv)
    )
    candidate_pipelines["Logistic Regression (Balanced)"] = (lr_pipe, {})

    # 3. Distance-based Candidate: KNN
    knn_pipe = build_model_pipeline(
        KNeighborsClassifier(n_neighbors=25, weights="distance", n_jobs=-1)
    )
    comparison_rows.append(
        _evaluate_cv_pipeline("KNN (k=25, Distance)", knn_pipe, X_train, y_train, cv)
    )
    candidate_pipelines["KNN (k=25, Distance)"] = (knn_pipe, {"n_neighbors": 25, "weights": "distance"})

    # 4. Random Forest (Tuned strictly on training data via TimeSeriesSplit)
    rf_base = build_model_pipeline(
        RandomForestClassifier(
            n_estimators=150,
            class_weight="balanced_subsample",
            random_state=42,
            n_jobs=-1,
        )
    )
    rf_search = GridSearchCV(
        rf_base,
        param_grid={
            "model__max_depth": [12, 20],
            "model__min_samples_leaf": [5, 15],
        },
        cv=cv,
        scoring="average_precision",
        n_jobs=-1,
        refit=True,
    )
    rf_search.fit(X_train, y_train)
    comparison_rows.append(
        _evaluate_cv_pipeline(
            "Random Forest (Tuned)",
            rf_search.best_estimator_,
            X_train,
            y_train,
            cv,
            best_params=rf_search.best_params_,
        )
    )
    candidate_pipelines["Random Forest (Tuned)"] = (
        rf_search.best_estimator_,
        rf_search.best_params_,
    )

    # 5. HistGradientBoosting (Tuned strictly on training data via TimeSeriesSplit)
    hgb_base = build_model_pipeline(
        HistGradientBoostingClassifier(
            class_weight="balanced",
            max_iter=200,
            random_state=42,
        )
    )
    hgb_search = GridSearchCV(
        hgb_base,
        param_grid={
            "model__max_depth": [4, 6],
            "model__learning_rate": [0.05, 0.1],
            "model__min_samples_leaf": [20, 50],
        },
        cv=cv,
        scoring="average_precision",
        n_jobs=-1,
        refit=True,
    )
    hgb_search.fit(X_train, y_train)
    comparison_rows.append(
        _evaluate_cv_pipeline(
            "HistGradientBoosting (Tuned)",
            hgb_search.best_estimator_,
            X_train,
            y_train,
            cv,
            best_params=hgb_search.best_params_,
        )
    )
    candidate_pipelines["HistGradientBoosting (Tuned)"] = (
        hgb_search.best_estimator_,
        hgb_search.best_params_,
    )

    comparison_df = (
        pd.DataFrame(comparison_rows)
        .sort_values("cv_pr_auc_mean", ascending=False)
        .reset_index(drop=True)
    )
    reports_dir.mkdir(parents=True, exist_ok=True)
    comparison_df.to_csv(reports_dir / "model_comparison.csv", index=False)

    winning_name = str(comparison_df.loc[0, "model"])
    winning_pipeline, winning_params = candidate_pipelines[winning_name]
    winning_pipeline.fit(X_train, y_train)

    # Final single evaluation on June 2024 holdout test set
    y_test_arr = y_test.to_numpy(dtype=int)
    y_pred = winning_pipeline.predict(X_test)
    y_prob = winning_pipeline.predict_proba(X_test)[:, 1]
    tn, fp, fn, tp = (int(v) for v in confusion_matrix(y_test_arr, y_pred).ravel())

    test_metrics = {
        "pr_auc": round(float(average_precision_score(y_test_arr, y_prob)), 4),
        "roc_auc": round(float(roc_auc_score(y_test_arr, y_prob)), 4),
        "f1": round(float(f1_score(y_test_arr, y_pred, zero_division=0)), 4),
        "precision": round(float(precision_score(y_test_arr, y_pred, zero_division=0)), 4),
        "recall": round(float(recall_score(y_test_arr, y_pred, zero_division=0)), 4),
        "accuracy": round(float(accuracy_score(y_test_arr, y_pred)), 4),
    }

    # Permutation importance across raw input features
    perm = permutation_importance(
        winning_pipeline,
        X_test,
        y_test_arr,
        scoring="average_precision",
        n_repeats=10,
        random_state=42,
        n_jobs=-1,
    )
    perm_df = (
        pd.DataFrame(
            {
                "feature": INPUT_FEATURE_COLUMNS,
                "importance_mean": np.round(perm.importances_mean, 5),
                "importance_std": np.round(perm.importances_std, 5),
            }
        )
        .sort_values("importance_mean", ascending=False)
        .reset_index(drop=True)
    )
    perm_df.to_csv(reports_dir / "permutation_importance.csv", index=False)

    # Concrete Error Analysis & Subgroup Metrics
    eval_df = test_df[
        [
            "id",
            "application_start_date",
            "review_type",
            "permit_type",
            "work_type",
            "reported_cost",
            "processing_time",
            "community_area",
        ]
    ].copy()
    eval_df["actual_is_delayed"] = y_test_arr
    eval_df["predicted_is_delayed"] = y_pred.astype(int)
    eval_df["delay_probability"] = np.round(y_prob, 4)
    eval_df["cost_bracket"] = _assign_cost_bucket(eval_df["reported_cost"])

    fp_rows = (
        eval_df[(eval_df["actual_is_delayed"] == 0) & (eval_df["predicted_is_delayed"] == 1)]
        .sort_values("delay_probability", ascending=False)
        .head(15)
        .assign(error_type="False Positive")
    )
    fn_rows = (
        eval_df[(eval_df["actual_is_delayed"] == 1) & (eval_df["predicted_is_delayed"] == 0)]
        .sort_values("delay_probability", ascending=True)
        .head(15)
        .assign(error_type="False Negative")
    )
    misclassified_df = pd.concat([fp_rows, fn_rows], ignore_index=True)
    misclassified_df.to_csv(reports_dir / "misclassified_examples.csv", index=False)

    rev_sub_df = _compute_subgroup_metrics(eval_df, "review_type", min_count=1)
    rev_sub_df.to_csv(reports_dir / "subgroup_performance_review_type.csv", index=False)

    cost_sub_df = _compute_subgroup_metrics(eval_df, "cost_bracket", min_count=1)
    cost_sub_df.to_csv(reports_dir / "subgroup_performance_cost_bucket.csv", index=False)

    # Visualizations
    figures_dir.mkdir(parents=True, exist_ok=True)
    _configure_plot_style()
    _plot_model_comparison(comparison_df, figures_dir / "05_model_comparison_cv.png")
    _plot_confusion_and_curves(
        y_test_arr,
        y_pred,
        y_prob,
        winning_name,
        figures_dir / "06_confusion_matrix_and_curves.png",
    )
    _plot_permutation_importance(perm_df, figures_dir / "07_permutation_importance.png")
    _plot_subgroup_errors(rev_sub_df, cost_sub_df, figures_dir / "08_error_analysis_subgroups.png")

    # Save unified fitted pipeline and metadata
    models_dir.mkdir(parents=True, exist_ok=True)
    pipeline_path = models_dir / "best_delay_pipeline.joblib"
    joblib.dump(winning_pipeline, pipeline_path)

    metadata: dict[str, Any] = {
        "target_column": TARGET_COLUMN,
        "split_date_column": "application_start_date",
        "test_cutoff_date": TEST_CUTOFF_DATE,
        "train_rows": len(train_df),
        "test_rows": len(test_df),
        "train_positive_rate_pct": round(float(y_train.mean() * 100.0), 2),
        "test_positive_rate_pct": round(float(y_test.mean() * 100.0), 2),
        "input_feature_columns": INPUT_FEATURE_COLUMNS,
        "leakage_columns_excluded": LEAKAGE_COLUMNS,
        "identifier_columns_excluded": EXCLUDED_IDENTIFIER_COLUMNS,
        "winning_model": winning_name,
        "best_params": winning_params,
        "cv_results": comparison_df.to_dict(orient="records"),
        "test_metrics": test_metrics,
        "confusion_matrix": {"tn": tn, "fp": fp, "fn": fn, "tp": tp},
        "top_permutation_features": perm_df.head(5).to_dict(orient="records"),
        "pipeline_path": str(pipeline_path),
    }
    metadata_path = models_dir / "model_metadata.json"
    metadata_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")

    _write_evaluation_report(
        report_path=reports_dir / "part_b_evaluation_report.md",
        metadata=metadata,
        comparison_df=comparison_df,
        perm_df=perm_df,
        rev_sub_df=rev_sub_df,
        cost_sub_df=cost_sub_df,
        misclassified_df=misclassified_df,
    )

    print(
        f"Part B complete! Winner: {winning_name} | "
        f"Test PR-AUC={test_metrics['pr_auc']:.4f}, ROC-AUC={test_metrics['roc_auc']:.4f}, "
        f"F1={test_metrics['f1']:.4f}, Recall={test_metrics['recall']:.4f}"
    )
    print(f"Saved unified pipeline to '{pipeline_path}'")
    return metadata


def main() -> int:
    """CLI entrypoint for Part B model training and evaluation."""
    run_part_b_training()
    return 0


if __name__ == "__main__":
    sys.exit(main())
