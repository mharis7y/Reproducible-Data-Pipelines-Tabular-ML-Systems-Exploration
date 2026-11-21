# Name: Muhammad Haris
# Roll Number: TRN-2026-000809
# Date: 2026-11-21
"""Reproducible end-to-end Part A pipeline entrypoint with Quality Gate & metrics.json."""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path
from typing import Any

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.analysis import compute_pandas_and_numpy_summaries
from src.cleaning import clean_permits_data
from src.sql_queries import run_community_area_sql_analysis
from src.validation import ValidationError, validate_dataset
from src.visualize import generate_all_figures

DEFAULT_RAW_PATH = (
    PROJECT_ROOT / "data" / "raw" / "chicago_building_permits_2024_h1.csv"
)
DEFAULT_COMMUNITY_PATH = PROJECT_ROOT / "data" / "raw" / "chicago_community_areas.csv"
DEFAULT_CLEANED_PATH = (
    PROJECT_ROOT / "data" / "cleaned" / "chicago_building_permits_cleaned.csv"
)
DEFAULT_SQL_FILE = PROJECT_ROOT / "sql" / "community_area_insights.sql"
DEFAULT_REPORTS_DIR = PROJECT_ROOT / "outputs" / "reports"
DEFAULT_FIGURES_DIR = PROJECT_ROOT / "outputs" / "figures"
DEFAULT_METRICS_PATH = DEFAULT_REPORTS_DIR / "metrics.json"
DEFAULT_REPORT_MD_PATH = DEFAULT_REPORTS_DIR / "data_quality_report.md"


def measure_raw_quality(raw_df: pd.DataFrame) -> dict[str, Any]:
    """Compute pre-cleaning data quality metrics directly on the raw DataFrame."""
    total_rows, total_cols = raw_df.shape
    total_cells = total_rows * total_cols
    missing_cells = int(raw_df.isna().sum().sum())

    non_ascii_permit_type = (
        int(
            raw_df["permit_type"]
            .dropna()
            .astype(str)
            .map(lambda s: not s.isascii())
            .sum()
        )
        if "permit_type" in raw_df.columns
        else 0
    )
    invalid_state_codes = (
        int(
            (~raw_df["contact_1_state"].dropna().astype(str).str.match(r"^[A-Z]{2}$")).sum()
        )
        if "contact_1_state" in raw_df.columns
        else 0
    )
    ca_num = pd.to_numeric(raw_df["community_area"], errors="coerce")
    ward_num = pd.to_numeric(raw_df["ward"], errors="coerce")
    cost_num = pd.to_numeric(raw_df["reported_cost"], errors="coerce")

    return {
        "rows": total_rows,
        "columns": total_cols,
        "total_cells": total_cells,
        "missing_cells": missing_cells,
        "missing_pct": round((missing_cells / total_cells) * 100.0, 2)
        if total_cells
        else 0.0,
        "exact_duplicate_rows": int(raw_df.duplicated().sum()),
        "duplicate_ids": int(raw_df["id"].duplicated().sum()),
        "non_ascii_permit_type_rows": non_ascii_permit_type,
        "invalid_state_code_rows": invalid_state_codes,
        "community_area_zero_sentinels": int((ca_num == 0).sum()),
        "ward_zero_sentinels": int((ward_num == 0).sum()),
        "reported_cost_placeholders_le_1": int((cost_num <= 1.0).sum()),
        "reported_cost_outliers_gt_10m": int((cost_num > 10_000_000.0).sum()),
    }


def measure_cleaned_quality(cleaned_df: pd.DataFrame) -> dict[str, Any]:
    """Compute post-cleaning data quality metrics on the cleaned DataFrame."""
    total_rows, total_cols = cleaned_df.shape
    total_cells = total_rows * total_cols
    missing_cells = int(cleaned_df.isna().sum().sum())

    non_ascii_permit_type = int(
        cleaned_df["permit_type"]
        .dropna()
        .astype(str)
        .map(lambda s: not s.isascii())
        .sum()
    )
    invalid_state_codes = int(
        (
            ~(
                cleaned_df["contact_1_state"].astype(str).str.match(r"^[A-Z]{2}$")
                | (cleaned_df["contact_1_state"].astype(str) == "UNKNOWN")
            )
        ).sum()
    )

    return {
        "rows": total_rows,
        "columns": total_cols,
        "total_cells": total_cells,
        "missing_cells": missing_cells,
        "missing_pct": round((missing_cells / total_cells) * 100.0, 2)
        if total_cells
        else 0.0,
        "exact_duplicate_rows": int(cleaned_df.duplicated().sum()),
        "duplicate_ids": int(cleaned_df["id"].duplicated().sum()),
        "non_ascii_permit_type_rows": non_ascii_permit_type,
        "invalid_state_code_rows": invalid_state_codes,
        "community_area_zero_sentinels": int((cleaned_df["community_area"] == 0).sum()),
        "ward_zero_sentinels": int((cleaned_df["ward"] == 0).sum()),
    }


def _df_to_markdown(df: pd.DataFrame) -> str:
    """Format a small summary DataFrame as a GitHub-flavored Markdown table."""
    headers = [str(col) for col in df.columns]
    header_line = "| " + " | ".join(headers) + " |"
    sep_line = "| " + " | ".join("---" for _ in headers) + " |"
    rows = []
    for _, row in df.iterrows():
        cells = [str(val).replace("|", "\\|") for val in row.tolist()]
        rows.append("| " + " | ".join(cells) + " |")
    return "\n".join([header_line, sep_line, *rows])


def write_data_quality_report(
    report_path: Path,
    metrics: dict[str, Any],
    analysis_highlights: dict[str, Any],
    sql_df: pd.DataFrame,
    sql_text: str,
) -> None:
    """Write the Markdown Part A before-and-after data quality & insights report."""
    raw_q = metrics["raw_quality"]
    clean_q = metrics["cleaned_quality"]
    actions = metrics["cleaning_actions"]
    val = metrics["validation"]
    np_stats = analysis_highlights["numpy_stats"]

    top_areas_md = _df_to_markdown(sql_df.head(10))
    review_md = _df_to_markdown(pd.DataFrame(analysis_highlights["top_review_types"]))

    top3_areas = ", ".join(
        f"`{row['area_name']}` ({int(row['permit_count']):,} permits)"
        for _, row in sql_df.head(3).iterrows()
    )
    highest_delay_row = sql_df.sort_values("delayed_rate_pct", ascending=False).iloc[0]

    content = f"""# Part A: Data Quality & Insights Report

## 1. Before-and-After Data Quality Metrics

| Metric | Raw Dataset (Before) | Cleaned Dataset (After) | Change / Action |
| --- | ---: | ---: | --- |
| Rows | {raw_q['rows']:,} | {clean_q['rows']:,} | {actions['duplicates_removed']:,} duplicates removed |
| Columns | {raw_q['columns']} | {clean_q['columns']} | +{clean_q['columns'] - raw_q['columns']} engineered/flag cols |
| Total Missing Cells | {raw_q['missing_cells']:,} ({raw_q['missing_pct']:.2f}%) | {clean_q['missing_cells']:,} ({clean_q['missing_pct']:.2f}%) | {actions['total_categorical_nulls_filled']:,} categorical nulls filled; numeric/geo nulls preserved with flags |
| Non-ASCII `permit_type` Rows (`\\u2013`) | {raw_q['non_ascii_permit_type_rows']:,} | {clean_q['non_ascii_permit_type_rows']:,} | {actions['unicode_dashes_fixed']:,} Unicode dashes normalized to `-` |
| Invalid `contact_1_state` Formats | {raw_q['invalid_state_code_rows']:,} | {clean_q['invalid_state_code_rows']:,} | {actions['state_codes_normalized']:,} normalized (`ILLINOIS`/`IL.` -> `IL`) |
| `community_area == 0` Sentinels | {raw_q['community_area_zero_sentinels']:,} | {clean_q['community_area_zero_sentinels']:,} | Converted {actions['community_area_sentinels_to_na']} sentinels to `pd.NA` |
| `ward == 0` Sentinels | {raw_q['ward_zero_sentinels']:,} | {clean_q['ward_zero_sentinels']:,} | Converted {actions['ward_sentinels_to_na']} sentinels to `pd.NA` |
| Placeholder `reported_cost <= $1` | {raw_q['reported_cost_placeholders_le_1']:,} | Flagged (`reported_cost_is_placeholder`) | Kept raw value + boolean flag |
| Extreme `reported_cost > $10M` | {raw_q['reported_cost_outliers_gt_10m']:,} | Flagged + Winsorized (`p99=${actions['reported_cost_p99_cap']:,.2f}`) | Preserved raw value + added clipped/log views |
| **Validation Row Pass Rate** | — | **{val['row_pass_rate']:.4%}** | Quality gate threshold: `{val['min_pass_rate']:.2%}` (**{'PASSED' if val['passed'] else 'FAILED'}**) |

## 2. NumPy & Pandas Analytical Highlights

- **Vectorized Processing Time Distribution (`numpy`)**: Mean = **{np_stats['processing_time_mean_days']} days**, Std = **{np_stats['processing_time_std_days']} days**, p25 = `{np_stats['processing_time_percentiles']['p25']}`, Median (p50) = `{np_stats['processing_time_percentiles']['p50']}`, p75 = `{np_stats['processing_time_percentiles']['p75']}`, p90 = `{np_stats['processing_time_percentiles']['p90']}`, p95 = `{np_stats['processing_time_percentiles']['p95']}`, p99 = `{np_stats['processing_time_percentiles']['p99']}`.
- **Vectorized Log Cost vs. Log Processing Time Correlation (`numpy.corrcoef`)**: `r = {np_stats['corr_log_cost_vs_log_processing_time']}` across `{np_stats['valid_positive_cost_count']:,}` permits with valid cost `> $1.00`, confirming larger/higher-cost construction projects undergo longer review durations.

### Top Review Types (`summary_by_review_type.csv`)

{review_md}

## 3. SQLite Query & Geographic Insights (`sql/community_area_insights.sql`)

```sql
{sql_text.strip()}
```

### Top 10 Chicago Community Areas by H1 2024 Permit Volume (`>= 100` Permits)

{top_areas_md}

## 4. Saved Visualizations (`outputs/figures/`)

1. `01_processing_time_by_review_type.png`: Shows that `EXPRESS PERMIT PROGRAM` permits clear with a median of 1 day (6.81% delayed), whereas `STANDARD PLAN REVIEW` (68.29% delayed) and `DIRECT DEVELOPER SERVICES` (92.59% delayed) account for the steepest review bottlenecks.
2. `02_monthly_volume_and_delay_rate.png`: Shows monthly H1 2024 permit volume rising from January (`2,266`) into spring (`3,005–3,088`/month in April–June) while delay rates stayed between `18.31%` and `25.77%`.
3. `03_cost_vs_processing_tier.png`: Shows median reported construction cost rises steadily from same-day/fast tiers (`$4,000` same-day median) up to `Severely Delayed (>90d)` permits (`$80,000` median).
4. `04_top_community_areas_sql.png`: Highlights neighborhood-level disparities from the SQLite join, led in permit volume by {top3_areas}, while `{highest_delay_row['area_name']}` exhibits the highest delay share (`{highest_delay_row['delayed_rate_pct']:.2f}%`) among neighborhoods with `>= 100` permits.
"""
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(content, encoding="utf-8")


def run_part_a_pipeline(
    input_csv: Path = DEFAULT_RAW_PATH,
    community_csv: Path = DEFAULT_COMMUNITY_PATH,
    output_cleaned_csv: Path = DEFAULT_CLEANED_PATH,
    metrics_path: Path = DEFAULT_METRICS_PATH,
    reports_dir: Path = DEFAULT_REPORTS_DIR,
    figures_dir: Path = DEFAULT_FIGURES_DIR,
    sql_file: Path = DEFAULT_SQL_FILE,
    min_pass_rate: float = 0.99,
    write_outputs: bool = True,
) -> dict[str, Any]:
    """Execute cleaning, loud validation/quality gate, analysis, SQLite join, and charts."""
    if not input_csv.exists():
        raise FileNotFoundError(
            f"Input CSV not found at '{input_csv}'. Run 'python src/download_data.py' first."
        )

    raw_df = pd.read_csv(input_csv, low_memory=False)
    raw_quality = measure_raw_quality(raw_df)

    cleaned_df, cleaning_actions = clean_permits_data(raw_df)
    cleaned_quality = measure_cleaned_quality(cleaned_df)
    validation_report = validate_dataset(
        cleaned_df, min_pass_rate=min_pass_rate, raise_on_failure=False
    )

    metrics: dict[str, Any] = {
        "input_file": str(input_csv),
        "raw_quality": raw_quality,
        "cleaning_actions": cleaning_actions,
        "cleaned_quality": cleaned_quality,
        "validation": validation_report,
    }
    metrics_path.parent.mkdir(parents=True, exist_ok=True)
    metrics_path.write_text(json.dumps(metrics, indent=2) + "\n", encoding="utf-8")

    if not validation_report["passed"]:
        # Trigger standard loud ValidationError message without overwriting cleaned outputs
        validate_dataset(cleaned_df, min_pass_rate=min_pass_rate, raise_on_failure=True)

    if write_outputs:
        output_cleaned_csv.parent.mkdir(parents=True, exist_ok=True)
        cleaned_df.to_csv(output_cleaned_csv, index=False)

        analysis_highlights = compute_pandas_and_numpy_summaries(cleaned_df, reports_dir)
        sql_df, sql_text = run_community_area_sql_analysis(
            cleaned_df=cleaned_df,
            community_areas_csv=community_csv,
            sql_file=sql_file,
            output_csv=reports_dir / "sql_community_area_insights.csv",
        )
        figure_paths = generate_all_figures(cleaned_df, sql_df, figures_dir)
        write_data_quality_report(
            report_path=reports_dir / "data_quality_report.md",
            metrics=metrics,
            analysis_highlights=analysis_highlights,
            sql_df=sql_df,
            sql_text=sql_text,
        )
        print(
            f"Quality gate PASSED ({validation_report['row_pass_rate']:.4%} >= "
            f"{min_pass_rate:.2%}). Cleaned CSV ({len(cleaned_df):,} rows) and "
            f"{len(figure_paths)} figures written."
        )

    return metrics


def run_quality_gate_demo(
    raw_csv: Path = DEFAULT_RAW_PATH,
    reports_dir: Path = DEFAULT_REPORTS_DIR,
    min_pass_rate: float = 0.99,
) -> bool:
    """Demonstrate the quality gate FAILING on a corrupted temp copy and PASSING on real data."""
    print("=== Quality Gate Demo (Bonus Challenge) ===")
    raw_df = pd.read_csv(raw_csv, low_memory=False)
    corrupted_df = raw_df.copy()
    corrupt_rows = min(500, len(corrupted_df))
    corrupted_df.loc[: corrupt_rows - 1, "processing_time"] = -10
    corrupted_df.loc[: corrupt_rows - 1, "latitude"] = 0.0
    corrupted_df.loc[: corrupt_rows - 1, "street_direction"] = "INVALID"
    corrupted_df.loc[: corrupt_rows - 1, "contact_1_state"] = "BADSTATE"

    corrupted_metrics_path = reports_dir / "metrics_corrupted_demo.json"
    gate_blocked_corrupted = False

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        corrupted_csv = tmp_path / "corrupted_permits.csv"
        corrupted_df.to_csv(corrupted_csv, index=False)

        try:
            run_part_a_pipeline(
                input_csv=corrupted_csv,
                output_cleaned_csv=tmp_path / "should_not_exist.csv",
                metrics_path=corrupted_metrics_path,
                min_pass_rate=min_pass_rate,
                write_outputs=True,
            )
        except ValidationError as exc:
            gate_blocked_corrupted = True
            print(f"[EXPECTED FAIL on corrupted copy]: {exc}")

    if not gate_blocked_corrupted:
        raise RuntimeError("Quality gate failed to reject the corrupted copy!")

    print("\nNow running full Part A pipeline on real raw dataset:")
    run_part_a_pipeline(input_csv=raw_csv, min_pass_rate=min_pass_rate, write_outputs=True)
    return True


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments for Part A pipeline execution."""
    parser = argparse.ArgumentParser(
        description="Run Part A reproducible data cleaning, validation, and analysis pipeline."
    )
    parser.add_argument("--input", type=Path, default=DEFAULT_RAW_PATH)
    parser.add_argument("--community-areas", type=Path, default=DEFAULT_COMMUNITY_PATH)
    parser.add_argument("--output-cleaned", type=Path, default=DEFAULT_CLEANED_PATH)
    parser.add_argument("--metrics-out", type=Path, default=DEFAULT_METRICS_PATH)
    parser.add_argument("--min-pass-rate", type=float, default=0.99)
    parser.add_argument(
        "--demo-quality-gate",
        action="store_true",
        help="Demonstrate quality gate failing on a corrupted copy before passing on real data.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint for the Part A pipeline."""
    args = parse_args(argv)
    try:
        if args.demo_quality_gate:
            run_quality_gate_demo(
                raw_csv=args.input,
                reports_dir=args.metrics_out.parent,
                min_pass_rate=args.min_pass_rate,
            )
        else:
            run_part_a_pipeline(
                input_csv=args.input,
                community_csv=args.community_areas,
                output_cleaned_csv=args.output_cleaned,
                metrics_path=args.metrics_out,
                reports_dir=args.metrics_out.parent,
                figures_dir=DEFAULT_FIGURES_DIR,
                sql_file=DEFAULT_SQL_FILE,
                min_pass_rate=args.min_pass_rate,
                write_outputs=True,
            )
    except (ValidationError, FileNotFoundError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
