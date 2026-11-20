# Name: Muhammad Haris
# Roll Number: TRN-2026-000809
# Date: 2026-11-21
"""Read-only raw data audit script for City of Chicago Building Permits (H1 2024)."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_RAW_PATH = (
    PROJECT_ROOT / "data" / "raw" / "chicago_building_permits_2024_h1.csv"
)

CHICAGO_LAT_BOUNDS = (41.6, 42.1)
CHICAGO_LON_BOUNDS = (-88.0, -87.5)
STATE_CODE_RE = re.compile(r"^[A-Z]{2}$")


def summarize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Build a per-column profile with dtype, missing counts, cardinality, and samples."""
    rows: list[dict[str, object]] = []
    total_rows = len(df)
    for col in df.columns:
        series = df[col]
        missing_count = int(series.isna().sum())
        non_null = series.dropna()
        samples = [repr(val)[:45] for val in non_null.head(3).tolist()]
        rows.append(
            {
                "column": col,
                "raw_dtype": str(series.dtype),
                "non_null": int(non_null.shape[0]),
                "missing": missing_count,
                "missing_pct": round((missing_count / total_rows) * 100, 2)
                if total_rows
                else 0.0,
                "nunique": int(series.nunique(dropna=True)),
                "samples": " | ".join(samples),
            }
        )
    return pd.DataFrame(rows)


def inspect_string_quality(series: pd.Series) -> dict[str, int]:
    """Count leading/trailing whitespace and non-uppercase casing issues in text."""
    non_null = series.dropna().astype(str)
    has_whitespace = int((non_null != non_null.str.strip()).sum())
    not_uppercase = int((non_null != non_null.str.upper()).sum())
    return {
        "non_null": len(non_null),
        "leading_or_trailing_ws": has_whitespace,
        "not_uppercase": not_uppercase,
    }


def inspect_state_codes(series: pd.Series) -> dict[str, object]:
    """Identify state values that violate 2-letter uppercase US/territory code format."""
    non_null = series.dropna().astype(str)
    stripped_upper = non_null.str.strip().str.upper()
    invalid_mask = ~stripped_upper.str.match(STATE_CODE_RE)
    format_dirty_mask = non_null != stripped_upper
    return {
        "missing": int(series.isna().sum()),
        "invalid_format_count": int(invalid_mask.sum()),
        "invalid_values": non_null[invalid_mask].value_counts().to_dict(),
        "case_or_ws_dirty_count": int(format_dirty_mask.sum()),
        "case_or_ws_values": non_null[format_dirty_mask].value_counts().to_dict(),
    }


def print_permit_type_check(df: pd.DataFrame) -> None:
    """Report permit_type categories and flag non-ASCII Unicode dash characters."""
    print("\n--- 4A. Category / Unicode Audit: permit_type ---")
    counts = df["permit_type"].value_counts(dropna=False)
    for val, cnt in counts.items():
        text = str(val)
        has_non_ascii = any(ord(ch) > 127 for ch in text)
        tag = " [NON-ASCII CHAR]" if has_non_ascii else ""
        print(f"  {cnt:6d} | {val!r}{tag}")


def print_numeric_and_geo_audit(df: pd.DataFrame) -> None:
    """Report range, outlier, fee consistency, and Chicago coordinate checks."""
    print("\n--- 4B. Text Whitespace & State Code Quality ---")
    state_info = inspect_state_codes(df["contact_1_state"])
    print(f"contact_1_state missing: {state_info['missing']}")
    print(
        f"contact_1_state non-2-letter codes ({state_info['invalid_format_count']}): "
        f"{state_info['invalid_values']}"
    )
    print(
        f"contact_1_state case/whitespace issues ({state_info['case_or_ws_dirty_count']}): "
        f"{state_info['case_or_ws_values']}"
    )
    for col in ["contact_1_city", "street_name", "permit_status", "review_type"]:
        stats = inspect_string_quality(df[col])
        print(f"{col}: {stats}")

    print("\n--- 4C. Numeric Range, Fee & Outlier Audit ---")
    pt = pd.to_numeric(df["processing_time"], errors="coerce")
    print(
        "processing_time (days): "
        f"nulls={int(pt.isna().sum())}, <0={int((pt < 0).sum())}, "
        f"==0={int((pt == 0).sum())}, >30={int((pt > 30).sum())}, "
        f">365={int((pt > 365).sum())}, "
        f"min={pt.min()}, median={pt.median()}, p75={pt.quantile(0.75)}, "
        f"p95={pt.quantile(0.95):.1f}, max={pt.max()}"
    )

    rc = pd.to_numeric(df["reported_cost"], errors="coerce")
    print(
        "reported_cost (USD): "
        f"nulls={int(rc.isna().sum())}, <0={int((rc < 0).sum())}, "
        f"==0={int((rc == 0).sum())}, <=1={int((rc <= 1).sum())}, "
        f">10M={int((rc > 10_000_000).sum())}, "
        f"min={rc.min()}, median={rc.median()}, p95={rc.quantile(0.95):.1f}, max={rc.max()}"
    )

    fee_cols = [
        "building_fee_paid",
        "zoning_fee_paid",
        "other_fee_paid",
        "subtotal_paid",
        "subtotal_unpaid",
        "subtotal_waived",
        "total_fee",
    ]
    for col in fee_cols:
        vals = pd.to_numeric(df[col], errors="coerce")
        print(
            f"  {col}: nulls={int(vals.isna().sum())}, "
            f"<0={int((vals < 0).sum())}, max={vals.max()}"
        )

    fee_sum = df["subtotal_paid"] + df["subtotal_unpaid"] + df["subtotal_waived"]
    fee_mismatch = (fee_sum - df["total_fee"]).abs() > 0.01
    print(f"  total_fee != subtotal_paid+unpaid+waived rows: {int(fee_mismatch.sum())}")

    print("\n--- 4D. Geographic Bounds Audit (Chicago) ---")
    lat = pd.to_numeric(df["latitude"], errors="coerce")
    lon = pd.to_numeric(df["longitude"], errors="coerce")
    lat_oob = (lat < CHICAGO_LAT_BOUNDS[0]) | (lat > CHICAGO_LAT_BOUNDS[1])
    lon_oob = (lon < CHICAGO_LON_BOUNDS[0]) | (lon > CHICAGO_LON_BOUNDS[1])
    print(
        f"latitude nulls={int(lat.isna().sum())}, zeros={int((lat == 0).sum())}, "
        f"out_of_chicago={int(lat_oob.sum())}, min={lat.min()}, max={lat.max()}"
    )
    print(
        f"longitude nulls={int(lon.isna().sum())}, zeros={int((lon == 0).sum())}, "
        f"out_of_chicago={int(lon_oob.sum())}, min={lon.min()}, max={lon.max()}"
    )


def print_target_preview(df: pd.DataFrame) -> None:
    """Preview Part B binary target (is_delayed: processing_time > 30 days)."""
    print("\n--- 5. Part B Target Preview: is_delayed (processing_time > 30 days) ---")
    delayed = df["processing_time"] > 30
    total = len(df)
    pos = int(delayed.sum())
    neg = total - pos
    print(
        f"Delayed (>30d): {pos:,} ({pos / total:.2%}) | "
        f"On-time/Fast (<=30d): {neg:,} ({neg / total:.2%})"
    )

    by_review = (
        df.assign(is_delayed=delayed)
        .groupby("review_type", dropna=False)["is_delayed"]
        .agg(count="count", delayed_rate="mean")
        .sort_values("count", ascending=False)
    )
    by_review["delayed_rate"] = (by_review["delayed_rate"] * 100).round(2)
    print("\nDelayed rate (%) by review_type:")
    print(by_review.to_string())

    app_dates = pd.to_datetime(df["application_start_date"], errors="coerce")
    by_month = (
        df.assign(
            app_month=app_dates.dt.to_period("M").astype(str),
            is_delayed=delayed,
        )
        .groupby("app_month")["is_delayed"]
        .agg(count="count", delayed_rate="mean")
        .sort_index()
    )
    by_month["delayed_rate"] = (by_month["delayed_rate"] * 100).round(2)
    print("\nMonthly counts and delayed rate (%) across H1 2024:")
    print(by_month.to_string())


def inspect_raw_file(raw_path: Path = DEFAULT_RAW_PATH) -> None:
    """Load the raw CSV read-only and print a comprehensive inspection report."""
    if not raw_path.exists():
        raise FileNotFoundError(
            f"Raw dataset not found at '{raw_path}'. "
            "Run 'python src/download_data.py' first."
        )

    size_mb = raw_path.stat().st_size / (1024 * 1024)
    df = pd.read_csv(raw_path, low_memory=False)

    print("=== 1. Dataset Dimensions & File Info ===")
    print(f"File: {raw_path}")
    print(f"Size: {size_mb:.2f} MB ({raw_path.stat().st_size:,} bytes)")
    print(f"Shape: {df.shape[0]:,} rows x {df.shape[1]} columns")

    app_dt = pd.to_datetime(df["application_start_date"], errors="coerce")
    iss_dt = pd.to_datetime(df["issue_date"], errors="coerce")
    print(
        f"application_start_date: min={app_dt.min()}, max={app_dt.max()}, "
        f"unparseable_or_null={int(app_dt.isna().sum())}"
    )
    print(
        f"issue_date:             min={iss_dt.min()}, max={iss_dt.max()}, "
        f"unparseable_or_null={int(iss_dt.isna().sum())}"
    )

    print("\n=== 2. Duplicate Checks ===")
    print(f"Exact full-row duplicates: {int(df.duplicated().sum())}")
    print(f"Duplicate 'id':            {int(df['id'].duplicated().sum())}")
    print(f"Duplicate 'permit_':       {int(df['permit_'].duplicated().sum())}")

    print("\n=== 3. Per-Column Profile ===")
    pd.set_option("display.max_columns", None)
    pd.set_option("display.width", 180)
    pd.set_option("display.max_colwidth", 55)
    print(summarize_columns(df).to_string(index=False))

    print("\n=== 4. Detailed Raw Data Quality Audit ===")
    print_permit_type_check(df)
    print_numeric_and_geo_audit(df)
    print_target_preview(df)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments for raw dataset inspection."""
    parser = argparse.ArgumentParser(
        description="Inspect the raw City of Chicago Building Permits CSV."
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=DEFAULT_RAW_PATH,
        help="Path to raw CSV file.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint for inspecting the raw dataset."""
    args = parse_args(argv)
    inspect_raw_file(args.input)
    return 0


if __name__ == "__main__":
    sys.exit(main())
