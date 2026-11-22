# Name: Muhammad Haris
# Roll Number: TRN-2026-000809
# Date: 2026-11-22
"""Leakage-free intake feature engineering, chronological splitting, and unified ML pipeline."""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

TARGET_COLUMN = "is_delayed"
SPLIT_DATE_COLUMN = "application_start_date"
TEST_CUTOFF_DATE = "2024-06-01"

INPUT_FEATURE_COLUMNS: list[str] = [
    "permit_type",
    "review_type",
    "work_type",
    "reported_cost",
    "community_area",
    "street_direction",
    "street_number",
    "latitude",
    "longitude",
    "contact_1_type",
    "contact_1_city",
    "contact_1_state",
    "application_dayofweek",
    "work_description",
]

LEAKAGE_COLUMNS: list[str] = [
    "issue_date",
    "processing_time",
    "processing_tier",
    "permit_status",
    "permit_milestone",
    "building_fee_paid",
    "zoning_fee_paid",
    "other_fee_paid",
    "subtotal_paid",
    "subtotal_unpaid",
    "subtotal_waived",
    "total_fee",
    "fee_to_cost_ratio",
    "reported_cost_winsorized",
]

EXCLUDED_IDENTIFIER_COLUMNS: list[str] = [
    "id",
    "permit_",
    "street_name",
    "ward",
    "application_start_date",
    "application_month",
    "application_day_name",
    "reported_cost_missing",
    "coords_missing",
    "reported_cost_is_placeholder",
    "reported_cost_outlier_flag",
    "log_reported_cost",
]

NUMERIC_INPUT_COLS: tuple[str, ...] = (
    "reported_cost",
    "community_area",
    "street_number",
    "latitude",
    "longitude",
    "application_dayofweek",
)

STRING_INPUT_COLS: tuple[str, ...] = (
    "permit_type",
    "review_type",
    "work_type",
    "street_direction",
    "contact_1_type",
    "contact_1_city",
    "contact_1_state",
    "work_description",
)

NUMERIC_PIPELINE_COLS: list[str] = [
    "log_reported_cost",
    "latitude",
    "longitude",
    "street_number",
    "application_dayofweek",
    "work_desc_len",
    "work_desc_words",
    "reported_cost_missing",
    "reported_cost_is_placeholder",
    "coords_missing",
    "contact_is_chicago",
    "contact_is_il",
]

CATEGORICAL_PIPELINE_COLS: list[str] = [
    "permit_type",
    "review_type",
    "work_type",
    "street_direction",
    "contact_1_type",
    "contact_1_state",
    "community_area_str",
]


def prepare_feature_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Validate intake columns and normalize dtypes for scikit-learn compatibility."""
    missing = [col for col in INPUT_FEATURE_COLUMNS if col not in df.columns]
    if missing:
        raise ValueError(f"Missing required input feature columns: {missing}")

    out = df[INPUT_FEATURE_COLUMNS].copy()
    for col in NUMERIC_INPUT_COLS:
        out[col] = pd.to_numeric(out[col], errors="coerce").astype(float)
    for col in STRING_INPUT_COLS:
        series = out[col]
        out[col] = series.where(series.notna(), np.nan).astype(object)
    return out


def chronological_train_test_split(
    df: pd.DataFrame,
    cutoff_date: str = TEST_CUTOFF_DATE,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Split permits chronologically before any transformation to prevent temporal leakage."""
    working = df.copy()
    working[SPLIT_DATE_COLUMN] = pd.to_datetime(
        working[SPLIT_DATE_COLUMN], errors="coerce"
    )
    if working[SPLIT_DATE_COLUMN].isna().any():
        raise ValueError(f"Null or invalid dates found in '{SPLIT_DATE_COLUMN}'.")

    sort_cols = [SPLIT_DATE_COLUMN, "id"] if "id" in working.columns else [SPLIT_DATE_COLUMN]
    working = working.sort_values(sort_cols, kind="mergesort").reset_index(drop=True)

    cutoff_ts = pd.Timestamp(cutoff_date)
    train_df = working[working[SPLIT_DATE_COLUMN] < cutoff_ts].reset_index(drop=True)
    test_df = working[working[SPLIT_DATE_COLUMN] >= cutoff_ts].reset_index(drop=True)

    if train_df.empty or test_df.empty:
        raise ValueError(
            f"Chronological split at '{cutoff_date}' produced an empty split "
            f"(train={len(train_df)}, test={len(test_df)})."
        )
    if train_df[SPLIT_DATE_COLUMN].max() >= test_df[SPLIT_DATE_COLUMN].min():
        raise ValueError("Train dates overlap or exceed test dates after splitting.")

    return train_df, test_df


def _clean_text_series(series: pd.Series, uppercase: bool = True) -> pd.Series:
    """Strip whitespace and optionally uppercase non-null string values."""
    cleaned = pd.Series(np.nan, index=series.index, dtype=object)
    mask = series.notna()
    if mask.any():
        vals = series.loc[mask].astype(str).str.strip()
        vals = vals.replace({"": np.nan, "nan": np.nan, "None": np.nan, "<NA>": np.nan})
        valid = vals.notna()
        if valid.any():
            text = vals.loc[valid].str.upper() if uppercase else vals.loc[valid]
            cleaned.loc[text.index] = text
    return cleaned


class PermitIntakeFeatureBuilder(BaseEstimator, TransformerMixin):
    """Stateless row-wise intake feature builder matching raw and cleaned schemas."""

    def fit(self, X: pd.DataFrame, y: pd.Series | None = None) -> PermitIntakeFeatureBuilder:
        """Validate required intake columns without learning any dataset statistics."""
        missing = [col for col in INPUT_FEATURE_COLUMNS if col not in X.columns]
        if missing:
            raise ValueError(f"Missing required input columns: {missing}")
        return self

    def transform(self, X: pd.DataFrame) -> pd.DataFrame:
        """Build numeric and normalized categorical features from raw intake columns."""
        missing = [col for col in INPUT_FEATURE_COLUMNS if col not in X.columns]
        if missing:
            raise ValueError(f"Missing required input columns: {missing}")

        cost = pd.to_numeric(X["reported_cost"], errors="coerce").to_numpy(dtype=float)
        lat = pd.to_numeric(X["latitude"], errors="coerce").to_numpy(dtype=float)
        lon = pd.to_numeric(X["longitude"], errors="coerce").to_numpy(dtype=float)
        street_num = pd.to_numeric(X["street_number"], errors="coerce").to_numpy(dtype=float)
        dow = pd.to_numeric(X["application_dayofweek"], errors="coerce").to_numpy(dtype=float)

        desc = X["work_description"].fillna("").astype(str)
        work_desc_len = desc.str.len().to_numpy(dtype=float)
        work_desc_words = desc.str.split().str.len().to_numpy(dtype=float)

        permit_type = _clean_text_series(X["permit_type"], uppercase=True)
        permit_mask = permit_type.notna()
        if permit_mask.any():
            permit_type.loc[permit_mask] = (
                permit_type.loc[permit_mask]
                .astype(str)
                .str.replace("\u2013", "-", regex=False)
                .str.replace("\u2014", "-", regex=False)
            )

        review_type = _clean_text_series(X["review_type"], uppercase=True)
        work_type = _clean_text_series(X["work_type"], uppercase=False)
        street_direction = _clean_text_series(X["street_direction"], uppercase=True)
        contact_1_type = _clean_text_series(X["contact_1_type"], uppercase=True)
        contact_1_city = _clean_text_series(X["contact_1_city"], uppercase=True)

        contact_1_state = _clean_text_series(X["contact_1_state"], uppercase=True)
        st_mask = contact_1_state.notna()
        if st_mask.any():
            contact_1_state.loc[st_mask] = (
                contact_1_state.loc[st_mask]
                .astype(str)
                .str.rstrip(".")
                .replace({"ILLINOIS": "IL"})
            )

        ca_num = pd.to_numeric(X["community_area"], errors="coerce")
        ca_str = pd.Series("MISSING", index=X.index, dtype=object)
        valid_ca = ca_num.notna() & (ca_num > 0)
        if valid_ca.any():
            ca_str.loc[valid_ca] = ca_num.loc[valid_ca].round().astype(int).astype(str)

        log_cost = np.where(np.isfinite(cost) & (cost >= 0.0), np.log1p(cost), np.nan)
        cost_missing = np.where(np.isfinite(cost), 0.0, 1.0)
        cost_placeholder = np.where(np.isfinite(cost) & (cost <= 1.0), 1.0, 0.0)
        coords_missing = np.where(np.isfinite(lat) & np.isfinite(lon), 0.0, 1.0)
        contact_is_chicago = (contact_1_city == "CHICAGO").fillna(False).to_numpy(dtype=float)
        contact_is_il = (contact_1_state == "IL").fillna(False).to_numpy(dtype=float)

        features = pd.DataFrame(
            {
                "log_reported_cost": log_cost,
                "latitude": lat,
                "longitude": lon,
                "street_number": street_num,
                "application_dayofweek": dow,
                "work_desc_len": work_desc_len,
                "work_desc_words": work_desc_words,
                "reported_cost_missing": cost_missing,
                "reported_cost_is_placeholder": cost_placeholder,
                "coords_missing": coords_missing,
                "contact_is_chicago": contact_is_chicago,
                "contact_is_il": contact_is_il,
                "permit_type": permit_type,
                "review_type": review_type,
                "work_type": work_type,
                "street_direction": street_direction,
                "contact_1_type": contact_1_type,
                "contact_1_state": contact_1_state,
                "community_area_str": ca_str,
            },
            index=X.index,
        )
        return features


def build_model_pipeline(estimator: BaseEstimator, min_frequency: int = 20) -> Pipeline:
    """Create one unified preprocessing + estimator Pipeline fitted on training data only."""
    numeric_transformer = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
        ]
    )
    categorical_transformer = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="constant", fill_value="MISSING")),
            (
                "encoder",
                OneHotEncoder(
                    handle_unknown="ignore",
                    min_frequency=min_frequency,
                    sparse_output=False,
                ),
            ),
        ]
    )
    preprocessor = ColumnTransformer(
        transformers=[
            ("num", numeric_transformer, NUMERIC_PIPELINE_COLS),
            ("cat", categorical_transformer, CATEGORICAL_PIPELINE_COLS),
        ],
        remainder="drop",
    )
    return Pipeline(
        steps=[
            ("intake_features", PermitIntakeFeatureBuilder()),
            ("preprocess", preprocessor),
            ("model", estimator),
        ]
    )
