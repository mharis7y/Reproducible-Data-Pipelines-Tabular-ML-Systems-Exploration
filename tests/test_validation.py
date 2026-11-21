# Name: Muhammad Haris
# Roll Number: TRN-2026-000809
# Date: 2026-11-21
"""Unit tests for src/validation.py and SQLite query integration in src/sql_queries.py."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.cleaning import clean_permits_data
from src.sql_queries import run_community_area_sql_analysis
from src.validation import (
    ValidationError,
    check_nulls,
    check_ranges_and_formats,
    check_required_columns,
    check_types,
    check_uniqueness,
    validate_dataset,
)


def _make_valid_cleaned_df(n_rows: int = 10) -> pd.DataFrame:
    """Create a valid cleaned permits DataFrame passing all schema and domain checks."""
    rows = []
    for idx in range(n_rows):
        rows.append(
            {
                "id": f"ID_{idx}",
                "permit_": f"P_{idx}",
                "permit_status": "COMPLETE",
                "permit_milestone": "COMPLETE",
                "permit_type": "PERMIT \u2013 EXPRESS PERMIT PROGRAM",
                "review_type": "EXPRESS PERMIT PROGRAM",
                "application_start_date": "2024-03-01T00:00:00.000",
                "issue_date": "2024-03-05T00:00:00.000",
                "processing_time": 4,
                "street_number": 100 + idx,
                "street_direction": "N",
                "street_name": "CLARK ST",
                "work_type": "Electrical Work",
                "work_description": "TEST",
                "building_fee_paid": 100.0,
                "zoning_fee_paid": 0.0,
                "other_fee_paid": 0.0,
                "subtotal_paid": 100.0,
                "subtotal_unpaid": 0.0,
                "subtotal_waived": 0.0,
                "total_fee": 100.0,
                "reported_cost": 5000.0,
                "community_area": 8.0,
                "ward": 42.0,
                "contact_1_type": "CONTRACTOR",
                "contact_1_city": "CHICAGO",
                "contact_1_state": "IL",
                "latitude": 41.89,
                "longitude": -87.63,
            }
        )
    cleaned, _ = clean_permits_data(pd.DataFrame(rows))
    return cleaned


def test_check_required_columns_detects_missing() -> None:
    """Verify check_required_columns flags missing columns accurately."""
    df = _make_valid_cleaned_df()
    assert check_required_columns(df)["passed"] is True

    dropped = df.drop(columns=["permit_type"])
    res = check_required_columns(dropped)
    assert res["passed"] is False
    assert "permit_type" in res["missing_columns"]


def test_check_types_catches_non_datetime_or_non_numeric() -> None:
    """Verify check_types catches invalid column dtypes."""
    df = _make_valid_cleaned_df()
    assert check_types(df)["passed"] is True

    bad = df.copy()
    bad["issue_date"] = bad["issue_date"].astype(str)
    bad["processing_time"] = bad["processing_time"].astype(str)
    res = check_types(bad)
    assert res["passed"] is False
    assert "issue_date" in res["mismatches"]
    assert "processing_time" in res["mismatches"]


def test_check_uniqueness_catches_duplicate_keys() -> None:
    """Verify check_uniqueness catches duplicate id or permit_ keys."""
    df = _make_valid_cleaned_df()
    assert check_uniqueness(df)["passed"] is True

    dup = df.copy()
    dup.loc[1, "permit_"] = dup.loc[0, "permit_"]
    res = check_uniqueness(dup)
    assert res["passed"] is False
    assert res["duplicate_counts"]["permit_"] == 1


def test_check_nulls_catches_critical_missing_values() -> None:
    """Verify check_nulls catches null entries in non-nullable columns."""
    df = _make_valid_cleaned_df()
    assert check_nulls(df)["passed"] is True

    bad = df.copy()
    bad.loc[0, "review_type"] = np.nan
    res = check_nulls(bad)
    assert res["passed"] is False
    assert res["null_counts"]["review_type"] == 1


def test_check_ranges_and_formats_catches_domain_violations() -> None:
    """Verify range, bounds, ASCII, state regex, and empty DataFrame handling."""
    empty_res = check_ranges_and_formats(_make_valid_cleaned_df().iloc[0:0])
    assert empty_res["passed"] is False
    assert empty_res["row_pass_rate"] == 0.0

    df = _make_valid_cleaned_df(n_rows=10)
    df.loc[0, "processing_time"] = -5
    df.loc[1, "latitude"] = 10.0
    df.loc[2, "community_area"] = 99
    df.loc[3, "contact_1_state"] = "BADSTATE"
    res = check_ranges_and_formats(df)

    assert res["passed"] is False
    assert res["valid_rows"] == 6
    assert res["row_pass_rate"] == pytest.approx(0.6)
    assert res["rule_failures"]["processing_time_non_negative"] == 1
    assert res["rule_failures"]["chicago_geo_bounds"] == 1
    assert res["rule_failures"]["community_area_range"] == 1
    assert res["rule_failures"]["contact_1_state_format"] == 1


def test_validate_dataset_quality_gate_passes_and_fails_loudly() -> None:
    """Verify validate_dataset passes on clean data and raises ValidationError on bad data."""
    valid_df = _make_valid_cleaned_df(n_rows=10)
    report = validate_dataset(valid_df, min_pass_rate=0.99, raise_on_failure=True)
    assert report["passed"] is True
    assert report["row_pass_rate"] == 1.0

    corrupted = valid_df.copy()
    corrupted.loc[0, "street_direction"] = "NORTH"
    with pytest.raises(ValidationError, match="Quality gate FAILED"):
        validate_dataset(corrupted, min_pass_rate=0.99, raise_on_failure=True)


def test_sqlite_community_area_join_executes(tmp_path: Path) -> None:
    """Verify the SQLite JOIN query executes cleanly and aggregates counts by area."""
    df = _make_valid_cleaned_df(n_rows=120)
    lookup_csv = tmp_path / "community_areas.csv"
    pd.DataFrame([{"area_numbe": 8, "community": "NEAR NORTH SIDE"}]).to_csv(
        lookup_csv, index=False
    )
    out_csv = tmp_path / "sql_out.csv"
    sql_path = Path(__file__).resolve().parent.parent / "sql" / "community_area_insights.sql"

    result_df, _ = run_community_area_sql_analysis(
        cleaned_df=df,
        community_areas_csv=lookup_csv,
        sql_file=sql_path,
        output_csv=out_csv,
    )
    assert out_csv.exists()
    assert len(result_df) == 1
    assert result_df.loc[0, "area_name"] == "Near North Side"
    assert int(result_df.loc[0, "permit_count"]) == 120
