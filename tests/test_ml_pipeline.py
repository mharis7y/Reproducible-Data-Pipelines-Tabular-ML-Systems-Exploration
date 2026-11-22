# Name: Muhammad Haris
# Roll Number: TRN-2026-000809
# Date: 2026-11-22
"""Unit and integration tests for Part B ML pipeline, leakage prevention, and inference CLI."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from sklearn.linear_model import LogisticRegression

from src.features import (
    INPUT_FEATURE_COLUMNS,
    LEAKAGE_COLUMNS,
    PermitIntakeFeatureBuilder,
    build_model_pipeline,
    chronological_train_test_split,
    prepare_feature_frame,
)
from src.predict import main as predict_main
from src.predict import predict_from_csv


def _make_mini_cleaned_permits(n_rows: int = 40) -> pd.DataFrame:
    """Create a realistic mini cleaned permits dataset spanning May and June 2024."""
    rng = np.random.default_rng(42)
    dates = pd.date_range("2024-05-01", periods=n_rows, freq="D")
    rows = []
    for idx, dt in enumerate(dates):
        is_std = idx % 2 == 0
        rows.append(
            {
                "id": f"ID_{idx}",
                "permit_": f"P_{idx}",
                "application_start_date": dt.strftime("%Y-%m-%d"),
                "permit_type": "PERMIT \u2013 EXPRESS PERMIT PROGRAM"
                if not is_std
                else "PERMIT - RENOVATION/ALTERATION",
                "review_type": "STANDARD PLAN REVIEW"
                if is_std
                else "EXPRESS PERMIT PROGRAM",
                "work_type": "Electrical Work" if idx % 3 else np.nan,
                "reported_cost": float(50_000 if is_std else 3_000)
                if idx % 5 != 0
                else np.nan,
                "community_area": 8.0 if idx % 4 else np.nan,
                "street_direction": ["N", "S", "E", "W"][idx % 4],
                "street_number": 100 + idx * 10,
                "latitude": 41.88 + float(rng.uniform(-0.02, 0.02))
                if idx % 7 != 0
                else np.nan,
                "longitude": -87.63 + float(rng.uniform(-0.02, 0.02))
                if idx % 7 != 0
                else np.nan,
                "contact_1_type": "GENERAL CONTRACTOR",
                "contact_1_city": "chicago " if idx % 2 == 0 else "LOMBARD",
                "contact_1_state": "ILLINOIS" if idx % 6 == 0 else "IL",
                "application_dayofweek": int(dt.day_of_week),
                "work_description": "INTERIOR RENOVATION" if is_std else "PANEL UPGRADE",
                "is_delayed": 1 if is_std else 0,
            }
        )
    return pd.DataFrame(rows)


def test_no_leakage_columns_in_input_features() -> None:
    """Verify strict separation between pre-application features and leakage columns."""
    overlap = set(INPUT_FEATURE_COLUMNS).intersection(set(LEAKAGE_COLUMNS))
    assert overlap == set()
    assert "is_delayed" not in INPUT_FEATURE_COLUMNS


def test_chronological_split_enforces_strict_time_order() -> None:
    """Verify chronological split separates Jan-May train from June test with no overlap."""
    df = _make_mini_cleaned_permits(n_rows=45)
    train_df, test_df = chronological_train_test_split(df, cutoff_date="2024-06-01")

    assert len(train_df) + len(test_df) == len(df)
    assert len(train_df) == 31
    assert len(test_df) == 14
    assert train_df["application_start_date"].max() < pd.Timestamp("2024-06-01")
    assert test_df["application_start_date"].min() >= pd.Timestamp("2024-06-01")


def test_intake_feature_builder_handles_messy_and_missing_inputs() -> None:
    """Verify feature builder normalizes Unicode dashes/states and preserves input DF."""
    df = _make_mini_cleaned_permits(n_rows=10)
    raw_in = prepare_feature_frame(df)
    snapshot = raw_in.copy(deep=True)

    builder = PermitIntakeFeatureBuilder()
    out = builder.fit_transform(raw_in)

    pd.testing.assert_frame_equal(raw_in, snapshot)
    assert "PERMIT - EXPRESS PERMIT PROGRAM" in set(out["permit_type"])
    assert "IL" in set(out["contact_1_state"])
    assert "ILLINOIS" not in set(out["contact_1_state"])
    assert out.loc[0, "reported_cost_missing"] == 1.0
    assert out.loc[0, "coords_missing"] == 1.0


def test_single_pipeline_object_fits_and_scores_unseen_categories() -> None:
    """Verify unified Pipeline fits on train only and scores unseen categories + NaNs."""
    df = _make_mini_cleaned_permits(n_rows=40)
    train_df, test_df = chronological_train_test_split(df, cutoff_date="2024-06-01")

    pipe = build_model_pipeline(
        LogisticRegression(max_iter=500, class_weight="balanced", random_state=42),
        min_frequency=1,
    )
    X_train = prepare_feature_frame(train_df)
    y_train = train_df["is_delayed"].astype(int)
    pipe.fit(X_train, y_train)

    X_unseen = prepare_feature_frame(test_df).copy()
    X_unseen.loc[0, "work_type"] = "Brand New Unseen Work Type"
    X_unseen.loc[0, "reported_cost"] = np.nan

    preds = pipe.predict(X_unseen)
    probs = pipe.predict_proba(X_unseen)[:, 1]
    assert len(preds) == len(X_unseen)
    assert set(np.unique(preds)).issubset({0, 1})
    assert np.all((probs >= 0.0) & (probs <= 1.0))


def test_predict_cli_validates_missing_columns_loudly(tmp_path: Path) -> None:
    """Verify predict.py fails loudly on missing required columns or empty CSV."""
    bad_csv = tmp_path / "missing_cols.csv"
    pd.DataFrame([{"permit_type": "PERMIT - SIGNS"}]).to_csv(bad_csv, index=False)

    with pytest.raises(ValueError, match="Missing required input feature columns"):
        predict_from_csv(bad_csv, output_csv=tmp_path / "out.csv")

    assert predict_main([str(bad_csv), "--output", str(tmp_path / "out.csv")]) == 1


def test_saved_pipeline_scores_sample_unseen_csv(tmp_path: Path) -> None:
    """Verify the saved joblib pipeline loads cleanly and scores sample_unseen_permits.csv."""
    repo_root = Path(__file__).resolve().parent.parent
    model_path = repo_root / "models" / "best_delay_pipeline.joblib"
    sample_csv = repo_root / "data" / "sample_unseen_permits.csv"
    if not model_path.exists():
        pytest.skip("Saved model not trained yet; run python src/train_part_b.py first.")

    out_csv = tmp_path / "scored.csv"
    scored = predict_from_csv(
        input_csv=sample_csv,
        output_csv=out_csv,
        model_path=model_path,
        metadata_path=repo_root / "models" / "model_metadata.json",
    )
    assert out_csv.exists()
    assert len(scored) == 10
    assert {"predicted_is_delayed", "delay_probability", "delay_risk_band"}.issubset(
        scored.columns
    )
    assert scored["delay_probability"].between(0.0, 1.0).all()
