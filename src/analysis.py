# Name: Muhammad Haris
# Roll Number: TRN-2026-000809
# Date: 2026-11-21
"""Pandas grouping/pivot summaries and NumPy vectorized statistical analysis."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

TIER_ORDER: list[str] = [
    "Same-Day (0d)",
    "Fast (1-7d)",
    "Moderate (8-30d)",
    "Delayed (31-90d)",
    "Severely Delayed (>90d)",
]


def compute_pandas_and_numpy_summaries(
    df: pd.DataFrame,
    reports_dir: Path,
) -> dict[str, Any]:
    """Generate and save Pandas summary tables and NumPy vectorized statistics."""
    reports_dir.mkdir(parents=True, exist_ok=True)

    summary_review = (
        df.groupby("review_type", dropna=False)
        .agg(
            permit_count=("id", "count"),
            delayed_count=("is_delayed", "sum"),
            delayed_rate_pct=("is_delayed", lambda s: round(float(s.mean() * 100.0), 2)),
            median_processing_days=("processing_time", "median"),
            mean_processing_days=("processing_time", lambda s: round(float(s.mean()), 2)),
            p90_processing_days=("processing_time", lambda s: round(float(np.percentile(s, 90)), 1)),
            median_reported_cost_usd=("reported_cost", "median"),
            total_fees_usd=("total_fee", lambda s: round(float(s.sum()), 2)),
        )
        .sort_values("permit_count", ascending=False)
        .reset_index()
    )
    summary_review.to_csv(reports_dir / "summary_by_review_type.csv", index=False)

    summary_permit = (
        df.groupby("permit_type", dropna=False)
        .agg(
            permit_count=("id", "count"),
            delayed_rate_pct=("is_delayed", lambda s: round(float(s.mean() * 100.0), 2)),
            median_processing_days=("processing_time", "median"),
            median_reported_cost_usd=("reported_cost", "median"),
            total_fees_usd=("total_fee", lambda s: round(float(s.sum()), 2)),
        )
        .sort_values("permit_count", ascending=False)
        .reset_index()
    )
    summary_permit.to_csv(reports_dir / "summary_by_permit_type.csv", index=False)

    pivot_review_month = pd.pivot_table(
        df,
        values="is_delayed",
        index="review_type",
        columns="application_month",
        aggfunc=lambda s: round(float(s.mean() * 100.0), 2),
    ).reset_index()
    pivot_review_month.to_csv(reports_dir / "pivot_review_by_month.csv", index=False)

    work_type_vc = (
        df["work_type"]
        .value_counts(dropna=False)
        .rename_axis("work_type")
        .reset_index(name="permit_count")
    )
    work_type_vc["share_pct"] = (
        (work_type_vc["permit_count"] / len(df)) * 100.0
    ).round(2)
    work_type_vc.to_csv(reports_dir / "value_counts_work_type.csv", index=False)

    summary_tier = (
        df.groupby("processing_tier", dropna=False)
        .agg(
            permit_count=("id", "count"),
            median_reported_cost_usd=("reported_cost", "median"),
            mean_total_fee_usd=("total_fee", lambda s: round(float(s.mean()), 2)),
        )
        .reindex([t for t in TIER_ORDER if t in set(df["processing_tier"])])
        .reset_index()
    )
    summary_tier["share_pct"] = (
        (summary_tier["permit_count"] / len(df)) * 100.0
    ).round(2)
    summary_tier.to_csv(reports_dir / "summary_by_processing_tier.csv", index=False)

    pt_arr = df["processing_time"].to_numpy(dtype=float)
    cost_arr = df["reported_cost"].to_numpy(dtype=float)
    log_cost_arr = df["log_reported_cost"].to_numpy(dtype=float)
    valid_mask = np.isfinite(cost_arr) & (cost_arr > 1.0) & np.isfinite(pt_arr)

    corr_log_cost_log_pt = (
        round(float(np.corrcoef(log_cost_arr[valid_mask], np.log1p(pt_arr[valid_mask]))[0, 1]), 4)
        if int(valid_mask.sum()) >= 2
        else None
    )

    return {
        "numpy_stats": {
            "processing_time_mean_days": round(float(np.mean(pt_arr)), 2),
            "processing_time_std_days": round(float(np.std(pt_arr)), 2),
            "processing_time_percentiles": {
                f"p{q}": round(float(np.percentile(pt_arr, q)), 2)
                for q in (25, 50, 75, 90, 95, 99)
            },
            "valid_positive_cost_count": int(valid_mask.sum()),
            "corr_log_cost_vs_log_processing_time": corr_log_cost_log_pt,
        },
        "top_review_types": summary_review.head(5).to_dict(orient="records"),
        "processing_tiers": summary_tier.to_dict(orient="records"),
    }
