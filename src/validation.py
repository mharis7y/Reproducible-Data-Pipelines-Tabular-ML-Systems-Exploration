# Name: Muhammad Haris
# Roll Number: TRN-2026-000809
# Date: 2026-11-21
"""Loud schema, range, uniqueness, null, and quality-gate validation checks."""

from __future__ import annotations

from typing import Any

import pandas as pd

REQUIRED_COLUMNS: list[str] = [
    "id",
    "permit_",
    "permit_status",
    "permit_milestone",
    "permit_type",
    "review_type",
    "application_start_date",
    "issue_date",
    "processing_time",
    "street_number",
    "street_direction",
    "street_name",
    "work_type",
    "work_description",
    "building_fee_paid",
    "zoning_fee_paid",
    "other_fee_paid",
    "subtotal_paid",
    "subtotal_unpaid",
    "subtotal_waived",
    "total_fee",
    "reported_cost",
    "community_area",
    "ward",
    "contact_1_type",
    "contact_1_city",
    "contact_1_state",
    "latitude",
    "longitude",
    "application_month",
    "application_dayofweek",
    "application_day_name",
    "reported_cost_missing",
    "coords_missing",
    "is_delayed",
    "processing_tier",
    "reported_cost_is_placeholder",
    "reported_cost_outlier_flag",
    "reported_cost_winsorized",
    "log_reported_cost",
    "fee_to_cost_ratio",
]

NON_NULL_COLUMNS: list[str] = [
    "id",
    "permit_",
    "permit_type",
    "review_type",
    "application_start_date",
    "issue_date",
    "processing_time",
    "street_direction",
    "total_fee",
    "is_delayed",
]

ALLOWED_STREET_DIRECTIONS: set[str] = {"N", "S", "E", "W"}
CHICAGO_LAT_BOUNDS = (41.6, 42.1)
CHICAGO_LON_BOUNDS = (-88.0, -87.5)


class ValidationError(ValueError):
    """Raised when structural validation checks or the quality gate threshold fail."""


def check_required_columns(
    df: pd.DataFrame,
    required_columns: list[str] | None = None,
) -> dict[str, Any]:
    """Verify that all expected columns are present in the DataFrame."""
    expected = REQUIRED_COLUMNS if required_columns is None else required_columns
    missing = [col for col in expected if col not in df.columns]
    return {
        "passed": len(missing) == 0,
        "expected_count": len(expected),
        "missing_columns": missing,
    }


def check_types(df: pd.DataFrame) -> dict[str, Any]:
    """Verify datetime and numeric column types match the expected schema."""
    datetime_cols = ("application_start_date", "issue_date")
    numeric_cols = (
        "processing_time",
        "reported_cost",
        "total_fee",
        "subtotal_paid",
        "subtotal_unpaid",
        "subtotal_waived",
        "latitude",
        "longitude",
        "community_area",
        "ward",
    )

    mismatches: dict[str, str] = {}
    for col in datetime_cols:
        if col in df.columns and not pd.api.types.is_datetime64_any_dtype(df[col]):
            mismatches[col] = f"expected datetime64, got {df[col].dtype}"

    for col in numeric_cols:
        if col in df.columns and not pd.api.types.is_numeric_dtype(df[col]):
            mismatches[col] = f"expected numeric dtype, got {df[col].dtype}"

    return {
        "passed": len(mismatches) == 0,
        "mismatches": mismatches,
    }


def check_uniqueness(
    df: pd.DataFrame,
    key_columns: tuple[str, ...] = ("id", "permit_"),
) -> dict[str, Any]:
    """Verify key identifier columns contain no duplicate values."""
    duplicate_counts: dict[str, int] = {}
    for col in key_columns:
        if col in df.columns:
            dups = int(df[col].duplicated().sum())
            if dups > 0:
                duplicate_counts[col] = dups

    return {
        "passed": len(duplicate_counts) == 0,
        "duplicate_counts": duplicate_counts,
    }


def check_nulls(
    df: pd.DataFrame,
    non_null_columns: list[str] | None = None,
) -> dict[str, Any]:
    """Verify critical non-nullable columns contain zero missing values."""
    cols = NON_NULL_COLUMNS if non_null_columns is None else non_null_columns
    null_counts: dict[str, int] = {}
    for col in cols:
        if col in df.columns:
            count = int(df[col].isna().sum())
            if count > 0:
                null_counts[col] = count

    return {
        "passed": len(null_counts) == 0,
        "null_counts": null_counts,
    }


def check_ranges_and_formats(df: pd.DataFrame) -> dict[str, Any]:
    """Evaluate row-level domain rules and compute overall row pass rate."""
    total_rows = len(df)
    if total_rows == 0:
        return {
            "passed": False,
            "total_rows": 0,
            "valid_rows": 0,
            "invalid_rows": 0,
            "row_pass_rate": 0.0,
            "rule_failures": {"empty_dataset": 1},
        }

    pt = pd.to_numeric(df["processing_time"], errors="coerce")
    app_dt = pd.to_datetime(df["application_start_date"], errors="coerce")
    iss_dt = pd.to_datetime(df["issue_date"], errors="coerce")
    diff_days = (iss_dt - app_dt).dt.days

    total_fee = pd.to_numeric(df["total_fee"], errors="coerce")
    sub_paid = pd.to_numeric(df["subtotal_paid"], errors="coerce")
    sub_unpaid = pd.to_numeric(df["subtotal_unpaid"], errors="coerce")
    sub_waived = pd.to_numeric(df["subtotal_waived"], errors="coerce")

    cost = pd.to_numeric(df["reported_cost"], errors="coerce")
    ca = pd.to_numeric(df["community_area"], errors="coerce")
    ward = pd.to_numeric(df["ward"], errors="coerce")
    lat = pd.to_numeric(df["latitude"], errors="coerce")
    lon = pd.to_numeric(df["longitude"], errors="coerce")

    permit_type_str = df["permit_type"].astype(str)
    state_str = df["contact_1_state"].astype(str)

    rules: dict[str, pd.Series] = {
        "processing_time_non_negative": pt.notna() & (pt >= 0),
        "issue_date_consistent": (
            app_dt.notna()
            & iss_dt.notna()
            & (iss_dt >= app_dt)
            & pt.notna()
            & (pt == diff_days)
        ),
        "fees_non_negative_and_reconciled": (
            total_fee.notna()
            & (total_fee >= 0)
            & (sub_paid >= 0)
            & (sub_unpaid >= 0)
            & (sub_waived >= 0)
            & (((sub_paid + sub_unpaid + sub_waived) - total_fee).abs() <= 0.01)
        ),
        "reported_cost_non_negative": cost.isna() | (cost >= 0),
        "community_area_range": ca.isna() | ((ca >= 1) & (ca <= 77)),
        "ward_range": ward.isna() | ((ward >= 1) & (ward <= 50)),
        "chicago_geo_bounds": (
            (lat.isna() | lat.between(*CHICAGO_LAT_BOUNDS))
            & (lon.isna() | lon.between(*CHICAGO_LON_BOUNDS))
        ),
        "permit_type_ascii": df["permit_type"].notna() & permit_type_str.map(str.isascii),
        "contact_1_state_format": (
            df["contact_1_state"].notna()
            & (state_str.str.match(r"^[A-Z]{2}$") | (state_str == "UNKNOWN"))
        ),
        "street_direction_allowed": df["street_direction"].isin(ALLOWED_STREET_DIRECTIONS),
    }

    valid_mask = pd.Series(True, index=df.index)
    rule_failures: dict[str, int] = {}
    for name, mask in rules.items():
        clean_mask = mask.fillna(False).astype(bool)
        rule_failures[name] = int((~clean_mask).sum())
        valid_mask = valid_mask & clean_mask

    valid_rows = int(valid_mask.sum())
    invalid_rows = total_rows - valid_rows
    row_pass_rate = valid_rows / total_rows

    return {
        "passed": invalid_rows == 0,
        "total_rows": total_rows,
        "valid_rows": valid_rows,
        "invalid_rows": invalid_rows,
        "row_pass_rate": round(row_pass_rate, 6),
        "rule_failures": rule_failures,
    }


def validate_dataset(
    df: pd.DataFrame,
    min_pass_rate: float = 0.99,
    raise_on_failure: bool = True,
) -> dict[str, Any]:
    """Run all schema/domain checks and enforce the Part A quality gate threshold."""
    req_check = check_required_columns(df)
    type_check = check_types(df)
    uniq_check = check_uniqueness(df)
    null_check = check_nulls(df)

    if req_check["passed"]:
        range_check = check_ranges_and_formats(df)
    else:
        range_check = {
            "passed": False,
            "total_rows": len(df),
            "valid_rows": 0,
            "invalid_rows": len(df),
            "row_pass_rate": 0.0,
            "rule_failures": {"skipped_due_to_missing_columns": len(df)},
        }

    row_pass_rate = float(range_check["row_pass_rate"])
    structural_ok = (
        req_check["passed"]
        and type_check["passed"]
        and uniq_check["passed"]
        and null_check["passed"]
    )
    gate_passed = structural_ok and (row_pass_rate >= min_pass_rate)

    report: dict[str, Any] = {
        "passed": gate_passed,
        "row_pass_rate": row_pass_rate,
        "min_pass_rate": min_pass_rate,
        "structural_passed": structural_ok,
        "checks": {
            "required_columns": req_check,
            "types": type_check,
            "uniqueness": uniq_check,
            "nulls": null_check,
            "ranges_and_formats": range_check,
        },
    }

    if not gate_passed and raise_on_failure:
        failed_rules = {
            k: v
            for k, v in range_check["rule_failures"].items()
            if v > 0
        }
        raise ValidationError(
            "Quality gate FAILED! "
            f"row_pass_rate={row_pass_rate:.4%} < min_pass_rate={min_pass_rate:.4%}; "
            f"missing_cols={req_check['missing_columns']}; "
            f"type_mismatches={type_check['mismatches']}; "
            f"duplicates={uniq_check['duplicate_counts']}; "
            f"nulls={null_check['null_counts']}; "
            f"failed_rules={failed_rules}"
        )

    return report
