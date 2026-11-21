# Name: Muhammad Haris
# Roll Number: TRN-2026-000809
# Date: 2026-11-21
"""Modular, non-mutating cleaning functions for City of Chicago Building Permits."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

STATE_NORMALIZATION_MAP: dict[str, str] = {
    "ILLINOIS": "IL",
}

CATEGORICAL_UNKNOWN_COLS: tuple[str, ...] = (
    "permit_status",
    "permit_milestone",
    "contact_1_type",
    "contact_1_city",
    "contact_1_state",
)

UPPERCASE_COLS: tuple[str, ...] = (
    "street_direction",
    "permit_status",
    "permit_milestone",
    "review_type",
    "contact_1_city",
    "street_name",
)


def parse_permit_dates(df: pd.DataFrame) -> pd.DataFrame:
    """Parse application/issue dates and derive application calendar fields."""
    out = df.copy()
    out["application_start_date"] = pd.to_datetime(
        out["application_start_date"], errors="coerce"
    )
    out["issue_date"] = pd.to_datetime(out["issue_date"], errors="coerce")
    out["application_month"] = out["application_start_date"].dt.strftime("%Y-%m")
    out["application_dayofweek"] = (
        out["application_start_date"].dt.day_of_week.astype("Int64")
    )
    out["application_day_name"] = out["application_start_date"].dt.day_name()
    return out


def standardize_categories(df: pd.DataFrame) -> pd.DataFrame:
    """Trim whitespace, normalize Unicode dashes, and standardize state/category text."""
    out = df.copy()

    string_cols = out.select_dtypes(include=["object", "string"]).columns
    for col in string_cols:
        series = out[col]
        stripped = series.where(series.isna(), series.astype(str).str.strip())
        out[col] = stripped.replace("", pd.NA)

    if "permit_type" in out.columns:
        pt = out["permit_type"]
        out["permit_type"] = pt.where(
            pt.isna(),
            pt.astype(str)
            .str.replace("\u2013", "-", regex=False)
            .str.replace("\u2014", "-", regex=False),
        )

    if "contact_1_state" in out.columns:
        st = out["contact_1_state"]
        normalized_st = (
            st.astype(str).str.strip().str.rstrip(".").str.upper().replace(STATE_NORMALIZATION_MAP)
        )
        out["contact_1_state"] = st.where(st.isna(), normalized_st).replace("", pd.NA)

    for col in UPPERCASE_COLS:
        if col in out.columns:
            series = out[col]
            out[col] = series.where(series.isna(), series.astype(str).str.upper())

    return out


def handle_duplicates(df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    """Remove exact duplicate rows and duplicate permit application IDs."""
    out = df.copy()
    initial_rows = len(out)
    out = out.drop_duplicates(keep="first")
    if "id" in out.columns:
        out = out.drop_duplicates(subset=["id"], keep="first")
    out = out.reset_index(drop=True)
    duplicates_removed = initial_rows - len(out)
    return out, duplicates_removed


def _clean_sentinel_int_column(series: pd.Series) -> tuple[pd.Series, int]:
    """Convert sentinel zero values to pd.NA and cast whole numbers to nullable Int64."""
    numeric = pd.to_numeric(series, errors="coerce")
    sentinel_count = int((numeric == 0).sum())
    cleaned = numeric.mask(numeric == 0)
    return cleaned.astype("Int64"), sentinel_count


def handle_missing_and_sentinels(df: pd.DataFrame) -> pd.DataFrame:
    """Replace geo sentinels with NA, preserve numeric nulls with flags, and fill categories."""
    out = df.copy()

    for geo_col in ("community_area", "ward"):
        if geo_col in out.columns:
            cleaned_col, _ = _clean_sentinel_int_column(out[geo_col])
            out[geo_col] = cleaned_col

    if "reported_cost" in out.columns:
        out["reported_cost"] = pd.to_numeric(out["reported_cost"], errors="coerce")
        out["reported_cost_missing"] = out["reported_cost"].isna().astype(bool)

    if "latitude" in out.columns and "longitude" in out.columns:
        out["latitude"] = pd.to_numeric(out["latitude"], errors="coerce")
        out["longitude"] = pd.to_numeric(out["longitude"], errors="coerce")
        out["coords_missing"] = (
            out["latitude"].isna() | out["longitude"].isna()
        ).astype(bool)

    if "work_type" in out.columns:
        out["work_type"] = out["work_type"].fillna("UNSPECIFIED")

    for col in CATEGORICAL_UNKNOWN_COLS:
        if col in out.columns:
            out[col] = out[col].fillna("UNKNOWN")

    return out


def handle_outliers_and_features(df: pd.DataFrame) -> pd.DataFrame:
    """Compute vectorized NumPy flags, winsorized/log costs, and delay classifications."""
    out = df.copy()

    pt = pd.to_numeric(out["processing_time"], errors="coerce").to_numpy(dtype=float)
    valid_pt = np.isfinite(pt) & (pt >= 0.0)
    is_delayed_arr = np.where(pt > 30.0, 1, 0)
    out["is_delayed"] = (
        pd.Series(is_delayed_arr, index=out.index)
        .where(valid_pt, pd.NA)
        .astype("Int64")
    )

    tier_conditions = [
        np.isfinite(pt) & (pt == 0.0),
        np.isfinite(pt) & (pt >= 1.0) & (pt <= 7.0),
        np.isfinite(pt) & (pt >= 8.0) & (pt <= 30.0),
        np.isfinite(pt) & (pt >= 31.0) & (pt <= 90.0),
        np.isfinite(pt) & (pt > 90.0),
    ]
    tier_choices = [
        "Same-Day (0d)",
        "Fast (1-7d)",
        "Moderate (8-30d)",
        "Delayed (31-90d)",
        "Severely Delayed (>90d)",
    ]
    out["processing_tier"] = np.select(
        tier_conditions, tier_choices, default="Invalid/Missing"
    )

    cost = pd.to_numeric(out["reported_cost"], errors="coerce").to_numpy(dtype=float)
    out["reported_cost_is_placeholder"] = np.where(
        np.isfinite(cost) & (cost <= 1.0), True, False
    )
    out["reported_cost_outlier_flag"] = np.where(
        np.isfinite(cost) & (cost > 10_000_000.0), True, False
    )

    valid_non_neg_cost = cost[np.isfinite(cost) & (cost >= 0.0)]
    if valid_non_neg_cost.size > 0:
        p99 = float(np.nanpercentile(valid_non_neg_cost, 99))
        out["reported_cost_winsorized"] = np.where(
            np.isfinite(cost) & (cost >= 0.0),
            np.clip(cost, 0.0, p99),
            np.nan,
        )
    else:
        out["reported_cost_winsorized"] = np.full(len(out), np.nan)

    safe_cost_for_log = np.where(np.isfinite(cost) & (cost >= 0.0), cost, np.nan)
    out["log_reported_cost"] = np.log1p(safe_cost_for_log)

    total_fee = pd.to_numeric(out["total_fee"], errors="coerce").to_numpy(dtype=float)
    with np.errstate(divide="ignore", invalid="ignore"):
        out["fee_to_cost_ratio"] = np.where(
            np.isfinite(cost) & (cost > 1.0) & np.isfinite(total_fee),
            total_fee / cost,
            np.nan,
        )

    return out


def clean_permits_data(raw_df: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Run the full deterministic Part A cleaning pipeline on a raw permits DataFrame."""
    working = raw_df.copy()

    unicode_dashes_fixed = (
        int(
            working["permit_type"]
            .dropna()
            .astype(str)
            .str.contains("[\u2013\u2014]", regex=True)
            .sum()
        )
        if "permit_type" in working.columns
        else 0
    )

    if "contact_1_state" in working.columns:
        raw_st = working["contact_1_state"].dropna().astype(str)
        norm_st = (
            raw_st.str.strip()
            .str.rstrip(".")
            .str.upper()
            .replace(STATE_NORMALIZATION_MAP)
        )
        state_codes_normalized = int((raw_st != norm_st).sum())
    else:
        state_codes_normalized = 0

    ca_sentinels = (
        int((pd.to_numeric(working["community_area"], errors="coerce") == 0).sum())
        if "community_area" in working.columns
        else 0
    )
    ward_sentinels = (
        int((pd.to_numeric(working["ward"], errors="coerce") == 0).sum())
        if "ward" in working.columns
        else 0
    )

    nulls_before_cat = {
        col: int(working[col].isna().sum())
        for col in ("work_type", *CATEGORICAL_UNKNOWN_COLS)
        if col in working.columns
    }

    working = parse_permit_dates(working)
    working = standardize_categories(working)
    working, duplicates_removed = handle_duplicates(working)
    working = handle_missing_and_sentinels(working)
    working = handle_outliers_and_features(working)

    valid_non_neg_cost = working["reported_cost"].dropna()
    valid_non_neg_cost = valid_non_neg_cost[valid_non_neg_cost >= 0.0]
    p99_cap = (
        round(float(np.nanpercentile(valid_non_neg_cost.to_numpy(dtype=float), 99)), 2)
        if not valid_non_neg_cost.empty
        else None
    )

    stats: dict[str, Any] = {
        "raw_rows": len(raw_df),
        "raw_cols": len(raw_df.columns),
        "cleaned_rows": len(working),
        "cleaned_cols": len(working.columns),
        "unicode_dashes_fixed": unicode_dashes_fixed,
        "state_codes_normalized": state_codes_normalized,
        "duplicates_removed": duplicates_removed,
        "community_area_sentinels_to_na": ca_sentinels,
        "ward_sentinels_to_na": ward_sentinels,
        "categorical_nulls_filled": nulls_before_cat,
        "total_categorical_nulls_filled": sum(nulls_before_cat.values()),
        "reported_cost_placeholders_flagged": int(
            working["reported_cost_is_placeholder"].sum()
        ),
        "reported_cost_outliers_flagged": int(
            working["reported_cost_outlier_flag"].sum()
        ),
        "reported_cost_p99_cap": p99_cap,
    }
    return working, stats
