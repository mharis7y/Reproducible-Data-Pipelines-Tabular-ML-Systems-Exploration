# Name: Muhammad Haris
# Roll Number: TRN-2026-000809
# Date: 2026-11-21
"""Matplotlib and Seaborn visualization generators for Part A insights."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
import numpy as np
import pandas as pd
import seaborn as sns

TIER_ORDER: list[str] = [
    "Same-Day (0d)",
    "Fast (1-7d)",
    "Moderate (8-30d)",
    "Delayed (31-90d)",
    "Severely Delayed (>90d)",
]


def _configure_style() -> None:
    """Apply consistent, clean plot styling across all Part A figures."""
    sns.set_theme(style="whitegrid", context="notebook")
    plt.rcParams["axes.spines.top"] = False
    plt.rcParams["axes.spines.right"] = False


def plot_processing_time_by_review_type(df: pd.DataFrame, out_path: Path) -> Path:
    """Plot median processing time (days) and delay rate (%) by permit review type."""
    summary = (
        df.groupby("review_type", dropna=False)
        .agg(
            permit_count=("id", "count"),
            median_days=("processing_time", "median"),
            delayed_rate_pct=("is_delayed", lambda s: float(s.mean() * 100.0)),
        )
        .sort_values("median_days", ascending=True)
        .reset_index()
    )
    labels = [
        f"{row['review_type']} (n={int(row['permit_count']):,})"
        for _, row in summary.iterrows()
    ]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6), sharey=True)
    y_pos = np.arange(len(summary))

    ax1.barh(y_pos, summary["median_days"], color="#2b6cb0")
    ax1.set_yticks(y_pos)
    ax1.set_yticklabels(labels)
    ax1.set_xlabel("Median Processing Time (Days)")
    ax1.set_ylabel("Permit Review Type")
    ax1.set_title("Median Review Duration")
    for idx, val in enumerate(summary["median_days"]):
        ax1.text(val + 1.5, idx, f"{val:.1f}d", va="center", fontsize=9)
    ax1.set_xlim(0, max(summary["median_days"]) * 1.18)

    ax2.barh(y_pos, summary["delayed_rate_pct"], color="#c53030")
    ax2.set_xlabel("Delayed Permits Rate (% > 30 Days)")
    ax2.set_title("Share Delayed Over 30 Days")
    for idx, val in enumerate(summary["delayed_rate_pct"]):
        ax2.text(val + 1.5, idx, f"{val:.1f}%", va="center", fontsize=9)
    ax2.set_xlim(0, 108)

    fig.suptitle(
        "Chicago Building Permits (H1 2024): Processing Speed & Delay Rate by Review Type",
        fontsize=13,
        fontweight="bold",
    )
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    return out_path


def plot_monthly_volume_and_delay_rate(df: pd.DataFrame, out_path: Path) -> Path:
    """Plot monthly application volume (count) and delayed rate (%) across H1 2024."""
    monthly = (
        df.groupby("application_month", dropna=False)
        .agg(
            permit_count=("id", "count"),
            delayed_rate_pct=("is_delayed", lambda s: float(s.mean() * 100.0)),
        )
        .sort_index()
        .reset_index()
    )

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 7), sharex=True)

    bars = ax1.bar(monthly["application_month"], monthly["permit_count"], color="#3182ce")
    ax1.set_ylabel("Applications Filed (Count)")
    ax1.set_title("Monthly Application Volume & Share Delayed (>30 Days), H1 2024")
    ax1.set_ylim(0, max(monthly["permit_count"]) * 1.18)
    for bar, val in zip(bars, monthly["permit_count"], strict=True):
        ax1.text(
            bar.get_x() + bar.get_width() / 2,
            val + 55,
            f"{int(val):,}",
            ha="center",
            fontsize=9,
        )

    ax2.plot(
        monthly["application_month"],
        monthly["delayed_rate_pct"],
        marker="o",
        linewidth=2.5,
        color="#c53030",
    )
    ax2.set_xlabel("Application Start Month (YYYY-MM)")
    ax2.set_ylabel("Delayed Rate (% > 30 Days)")
    ax2.set_ylim(0, max(monthly["delayed_rate_pct"]) * 1.3)
    for idx, val in enumerate(monthly["delayed_rate_pct"]):
        ax2.text(idx, val + 1.0, f"{val:.2f}%", ha="center", fontsize=9)

    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    return out_path


def plot_cost_vs_processing_tier(df: pd.DataFrame, out_path: Path) -> Path:
    """Plot reported construction cost (USD, log scale) across processing duration tiers."""
    valid = df[df["reported_cost"].notna() & (df["reported_cost"] > 1.0)].copy()
    valid["log10_cost"] = np.log10(valid["reported_cost"].to_numpy(dtype=float))
    order = [t for t in TIER_ORDER if t in set(valid["processing_tier"])]

    fig, ax = plt.subplots(figsize=(11, 6))
    sns.boxplot(
        data=valid,
        x="processing_tier",
        y="log10_cost",
        hue="processing_tier",
        order=order,
        palette="Blues",
        legend=False,
        showfliers=False,
        ax=ax,
    )
    ax.set_xlabel("Processing Duration Tier (Days)")
    ax.set_ylabel("Reported Construction Cost (USD, Log10 Scale)")
    ax.set_title(
        "Reported Project Cost Distribution by Processing Tier "
        "(Excludes Missing & <=$1 Placeholders)"
    )

    yticks = [2, 3, 4, 5, 6, 7, 8]
    ax.set_yticks(yticks)
    ax.set_yticklabels(["$100", "$1K", "$10K", "$100K", "$1M", "$10M", "$100M"])
    ax.yaxis.set_minor_formatter(mtick.NullFormatter())

    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    return out_path


def plot_top_community_areas_sql(sql_df: pd.DataFrame, out_path: Path) -> Path:
    """Plot top 15 Chicago community areas by permit count with delay rate annotations."""
    top15 = sql_df.head(15).sort_values("permit_count", ascending=True).copy()

    fig, ax = plt.subplots(figsize=(11, 7))
    bars = ax.barh(top15["area_name"], top15["permit_count"], color="#2f855a")
    ax.set_xlabel("Permits Filed (Count, H1 2024)")
    ax.set_ylabel("Chicago Community Area (Neighborhood)")
    ax.set_title("Top 15 Chicago Community Areas by Permit Volume & Delay Rate (SQLite JOIN)")
    ax.set_xlim(0, max(top15["permit_count"]) * 1.32)

    for bar, (_, row) in zip(bars, top15.iterrows(), strict=True):
        ax.text(
            bar.get_width() + 12,
            bar.get_y() + bar.get_height() / 2,
            f"{int(row['permit_count']):,}  ({row['delayed_rate_pct']:.1f}% delayed, "
            f"avg {row['avg_processing_days']:.1f}d)",
            va="center",
            fontsize=8.5,
        )

    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    return out_path


def generate_all_figures(
    cleaned_df: pd.DataFrame,
    sql_df: pd.DataFrame,
    figures_dir: Path,
) -> list[Path]:
    """Generate and save all four Part A visualizations."""
    figures_dir.mkdir(parents=True, exist_ok=True)
    _configure_style()
    return [
        plot_processing_time_by_review_type(
            cleaned_df, figures_dir / "01_processing_time_by_review_type.png"
        ),
        plot_monthly_volume_and_delay_rate(
            cleaned_df, figures_dir / "02_monthly_volume_and_delay_rate.png"
        ),
        plot_cost_vs_processing_tier(
            cleaned_df, figures_dir / "03_cost_vs_processing_tier.png"
        ),
        plot_top_community_areas_sql(
            sql_df, figures_dir / "04_top_community_areas_sql.png"
        ),
    ]
