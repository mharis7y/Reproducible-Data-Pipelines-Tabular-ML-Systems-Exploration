# Name: Muhammad Haris
# Roll Number: TRN-2026-000809
# Date: 2026-11-21
"""SQLite analytical queries joining cleaned permits with Chicago community areas."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd


def run_community_area_sql_analysis(
    cleaned_df: pd.DataFrame,
    community_areas_csv: Path,
    sql_file: Path,
    output_csv: Path,
) -> tuple[pd.DataFrame, str]:
    """Load permits and community areas into SQLite, execute JOIN query, and save CSV."""
    if not community_areas_csv.exists():
        raise FileNotFoundError(
            f"Community areas reference CSV not found at '{community_areas_csv}'. "
            "Run 'python src/download_data.py' first."
        )
    if not sql_file.exists():
        raise FileNotFoundError(f"SQL query file not found at '{sql_file}'.")

    lookup_raw = pd.read_csv(community_areas_csv)
    lookup_df = lookup_raw.rename(
        columns={"area_numbe": "community_area", "community": "area_name"}
    )[["community_area", "area_name"]].copy()
    lookup_df["community_area"] = pd.to_numeric(
        lookup_df["community_area"], errors="raise"
    ).astype(int)
    lookup_df["area_name"] = lookup_df["area_name"].astype(str).str.strip().str.title()

    permits_sql_df = cleaned_df[
        [
            "id",
            "community_area",
            "is_delayed",
            "processing_time",
            "reported_cost",
            "total_fee",
        ]
    ].copy()
    permits_sql_df["community_area"] = permits_sql_df["community_area"].astype("Float64")
    permits_sql_df["is_delayed"] = permits_sql_df["is_delayed"].astype(int)

    sql_text = sql_file.read_text(encoding="utf-8")

    with sqlite3.connect(":memory:") as conn:
        permits_sql_df.to_sql("permits", conn, if_exists="replace", index=False)
        lookup_df.to_sql("community_areas", conn, if_exists="replace", index=False)
        result_df = pd.read_sql_query(sql_text, conn)

    output_csv.parent.mkdir(parents=True, exist_ok=True)
    result_df.to_csv(output_csv, index=False)
    return result_df, sql_text
