# Name: Muhammad Haris
# Roll Number: TRN-2026-000809
# Date: 2026-11-21
"""Unit tests for modular cleaning functions in src/cleaning.py."""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.cleaning import (
    clean_permits_data,
    handle_duplicates,
    handle_missing_and_sentinels,
    handle_outliers_and_features,
    parse_permit_dates,
    standardize_categories,
)


def _make_sample_raw_df() -> pd.DataFrame:
    """Create a realistic mini raw permits DataFrame with intentional messiness."""
    return pd.DataFrame(
        [
            {
                "id": "101",
                "permit_": "P101",
                "permit_status": " complete ",
                "permit_milestone": "COMPLETE",
                "permit_type": "PERMIT \u2013 EXPRESS PERMIT PROGRAM",
                "review_type": "express permit program",
                "application_start_date": "2024-02-15T00:00:00.000",
                "issue_date": "2024-02-15T00:00:00.000",
                "processing_time": 0,
                "street_number": 100,
                "street_direction": "n",
                "street_name": "state st ",
                "work_type": np.nan,
                "work_description": "TEST WORK 1",
                "building_fee_paid": 100.0,
                "zoning_fee_paid": 0.0,
                "other_fee_paid": 0.0,
                "subtotal_paid": 100.0,
                "subtotal_unpaid": 0.0,
                "subtotal_waived": 0.0,
                "total_fee": 100.0,
                "reported_cost": 0.0,
                "community_area": 0.0,
                "ward": 0.0,
                "contact_1_type": np.nan,
                "contact_1_city": "chicago",
                "contact_1_state": "ILLINOIS",
                "latitude": 41.88,
                "longitude": -87.63,
            },
            {
                "id": "102",
                "permit_": "P102",
                "permit_status": np.nan,
                "permit_milestone": np.nan,
                "permit_type": "PERMIT - RENOVATION/ALTERATION",
                "review_type": "STANDARD PLAN REVIEW",
                "application_start_date": "2024-03-01T00:00:00.000",
                "issue_date": "2024-04-15T00:00:00.000",
                "processing_time": 45,
                "street_number": 200,
                "street_direction": "W",
                "street_name": "MADISON ST",
                "work_type": "Electrical Work",
                "work_description": "TEST WORK 2",
                "building_fee_paid": 500.0,
                "zoning_fee_paid": 75.0,
                "other_fee_paid": 0.0,
                "subtotal_paid": 575.0,
                "subtotal_unpaid": 0.0,
                "subtotal_waived": 0.0,
                "total_fee": 575.0,
                "reported_cost": 15_000_000.0,
                "community_area": 8.0,
                "ward": 42.0,
                "contact_1_type": "CONTRACTOR",
                "contact_1_city": np.nan,
                "contact_1_state": "IL.",
                "latitude": np.nan,
                "longitude": np.nan,
            },
        ]
    )


def test_parse_permit_dates_creates_calendar_columns() -> None:
    """Verify date columns parse to datetime64 and calendar helpers match."""
    raw = _make_sample_raw_df()
    parsed = parse_permit_dates(raw)

    assert pd.api.types.is_datetime64_any_dtype(parsed["application_start_date"])
    assert pd.api.types.is_datetime64_any_dtype(parsed["issue_date"])
    assert parsed["application_month"].tolist() == ["2024-02", "2024-03"]
    assert parsed.loc[0, "application_day_name"] == "Thursday"


def test_standardize_categories_fixes_unicode_dashes_and_states() -> None:
    """Verify en-dash/em-dash normalization, trimming, and Illinois state standardization."""
    raw = _make_sample_raw_df()
    raw.loc[1, "permit_type"] = "PERMIT \u2014 TEST"
    cleaned = standardize_categories(raw)

    assert cleaned.loc[0, "permit_type"] == "PERMIT - EXPRESS PERMIT PROGRAM"
    assert cleaned.loc[1, "permit_type"] == "PERMIT - TEST"
    assert cleaned.loc[0, "contact_1_state"] == "IL"
    assert cleaned.loc[1, "contact_1_state"] == "IL"
    assert cleaned.loc[0, "permit_status"] == "COMPLETE"
    assert cleaned.loc[0, "street_direction"] == "N"
    assert cleaned.loc[0, "street_name"] == "STATE ST"


def test_handle_duplicates_drops_exact_and_id_dups() -> None:
    """Verify duplicate rows and duplicate IDs are removed with accurate count."""
    raw = _make_sample_raw_df()
    with_dups = pd.concat([raw, raw.iloc[[0]]], ignore_index=True)
    deduped, removed = handle_duplicates(with_dups)

    assert removed == 1
    assert len(deduped) == 2


def test_handle_missing_and_sentinels_preserves_numeric_nulls() -> None:
    """Verify sentinel 0 becomes pd.NA while numeric/geo NaNs stay NaN with flags."""
    raw = _make_sample_raw_df()
    raw.loc[0, "reported_cost"] = np.nan
    handled = handle_missing_and_sentinels(raw)

    assert pd.isna(handled.loc[0, "community_area"])
    assert pd.isna(handled.loc[0, "ward"])
    assert handled.loc[1, "community_area"] == 8
    assert bool(handled.loc[0, "reported_cost_missing"]) is True
    assert bool(handled.loc[1, "coords_missing"]) is True
    assert pd.isna(handled.loc[0, "reported_cost"])
    assert handled.loc[0, "work_type"] == "UNSPECIFIED"
    assert handled.loc[1, "permit_status"] == "UNKNOWN"


def test_handle_outliers_and_features_vectorized_safety() -> None:
    """Verify NumPy flags, safe divide-by-zero ratio, log transform, and winsorization."""
    raw = _make_sample_raw_df()
    featured = handle_outliers_and_features(raw)

    assert featured["is_delayed"].tolist() == [0, 1]
    assert featured["processing_tier"].tolist() == [
        "Same-Day (0d)",
        "Delayed (31-90d)",
    ]
    assert bool(featured.loc[0, "reported_cost_is_placeholder"]) is True
    assert bool(featured.loc[1, "reported_cost_outlier_flag"]) is True
    assert pd.isna(featured.loc[0, "fee_to_cost_ratio"])
    assert np.isclose(featured.loc[1, "fee_to_cost_ratio"], 575.0 / 15_000_000.0)
    assert np.isclose(featured.loc[0, "log_reported_cost"], 0.0)


def test_clean_permits_data_does_not_mutate_input_and_records_stats() -> None:
    """Verify end-to-end cleaning preserves raw input DataFrame and logs action counts."""
    raw = _make_sample_raw_df()
    raw_copy = raw.copy(deep=True)
    cleaned, stats = clean_permits_data(raw)

    pd.testing.assert_frame_equal(raw, raw_copy)
    assert stats["unicode_dashes_fixed"] == 1
    assert stats["state_codes_normalized"] == 2
    assert stats["community_area_sentinels_to_na"] == 1
    assert stats["ward_sentinels_to_na"] == 1
    assert len(cleaned) == 2
