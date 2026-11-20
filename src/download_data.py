# Name: Muhammad Haris
# Roll Number: TRN-2026-000809
# Date: 2026-11-21
"""Reproducible downloader for the City of Chicago Building Permits (H1 2024) raw dataset."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import sys
import time
from pathlib import Path

import requests

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = PROJECT_ROOT / "data" / "raw"
RAW_CSV_PATH = RAW_DIR / "chicago_building_permits_2024_h1.csv"
METADATA_PATH = RAW_DIR / "dataset_metadata.json"

DATASET_NAME = "City of Chicago Building Permits (H1 2024 Extract)"
PORTAL_URL = "https://data.cityofchicago.org/Buildings/Building-Permits/ydr8-5enu"
API_ENDPOINT = "https://data.cityofchicago.org/resource/ydr8-5enu.csv"
LICENCE_NAME = "City of Chicago Data Terms of Use (Public Open Data)"
LICENCE_URL = "https://www.chicago.gov/city/en/narr/foia/data_disclaimer.html"
ACCESS_DATE = "2026-11-21"

QUERY_WHERE = (
    "application_start_date >= '2024-01-01T00:00:00' "
    "AND application_start_date < '2024-07-01T00:00:00'"
)
QUERY_ORDER = "application_start_date ASC, id ASC"
SELECTED_COLUMNS = [
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
]

DEFAULT_PAGE_SIZE = 5000
REQUEST_TIMEOUT_SEC = 60
MAX_RETRIES = 3


def fetch_csv_page(
    session: requests.Session,
    offset: int,
    limit: int = DEFAULT_PAGE_SIZE,
) -> str:
    """Fetch one paginated CSV chunk from the Chicago Data Portal Socrata API."""
    params = {
        "$select": ",".join(SELECTED_COLUMNS),
        "$where": QUERY_WHERE,
        "$order": QUERY_ORDER,
        "$limit": limit,
        "$offset": offset,
    }
    headers = {"User-Agent": "chicago-permits-reproducible-pipeline/1.0"}

    last_error: Exception | None = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = session.get(
                API_ENDPOINT,
                params=params,
                headers=headers,
                timeout=REQUEST_TIMEOUT_SEC,
            )
            if response.status_code >= 500:
                raise requests.HTTPError(
                    f"Server error {response.status_code} at offset={offset}",
                    response=response,
                )
            response.raise_for_status()
            return response.content.decode("utf-8")
        except (requests.RequestException, UnicodeDecodeError) as exc:
            last_error = exc
            if attempt < MAX_RETRIES:
                time.sleep(2 * attempt)
    raise RuntimeError(
        f"Failed to fetch offset={offset} after {MAX_RETRIES} attempts"
    ) from last_error


def count_csv_data_rows(csv_text: str) -> int:
    """Count exact data records in a CSV string (excluding its header row)."""
    if not csv_text.strip():
        return 0
    reader = csv.reader(io.StringIO(csv_text))
    next(reader, None)
    return sum(1 for _ in reader)


def strip_csv_header(csv_text: str) -> str:
    """Remove only the first header line while keeping quoted embedded newlines intact."""
    parts = csv_text.split("\n", 1)
    return parts[1] if len(parts) > 1 else ""


def compute_sha256(file_path: Path) -> str:
    """Return the hexadecimal SHA-256 checksum of a file."""
    digest = hashlib.sha256()
    with file_path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_csv_dimensions(csv_path: Path) -> tuple[int, int]:
    """Count data rows and header columns directly from the saved CSV file."""
    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle)
        header = next(reader, [])
        row_count = sum(1 for _ in reader)
    return row_count, len(header)


def download_raw_dataset(
    output_csv: Path = RAW_CSV_PATH,
    metadata_path: Path = METADATA_PATH,
    force: bool = False,
    page_size: int = DEFAULT_PAGE_SIZE,
) -> Path:
    """Download the raw CSV via paginated Socrata calls and save provenance metadata."""
    if output_csv.exists() and not force:
        print(
            f"Raw dataset already exists at '{output_csv}'. "
            "Preserving raw file (pass --force to re-download)."
        )
        return output_csv

    output_csv.parent.mkdir(parents=True, exist_ok=True)
    temp_csv = output_csv.with_suffix(".csv.tmp")

    offset = 0
    total_pages = 0
    with requests.Session() as session, temp_csv.open(
        "w", encoding="utf-8", newline=""
    ) as out_file:
        while True:
            page_text = fetch_csv_page(session, offset=offset, limit=page_size)
            page_rows = count_csv_data_rows(page_text)
            if page_rows == 0:
                break

            chunk = page_text if offset == 0 else strip_csv_header(page_text)
            if chunk and not chunk.endswith("\n"):
                chunk += "\n"
            out_file.write(chunk)

            total_pages += 1
            print(f"Downloaded page {total_pages}: offset={offset}, rows={page_rows}")
            if page_rows < page_size:
                break
            offset += page_size

    temp_csv.replace(output_csv)

    row_count, column_count = verify_csv_dimensions(output_csv)
    file_size_bytes = output_csv.stat().st_size
    sha256_hex = compute_sha256(output_csv)

    metadata = {
        "dataset_name": DATASET_NAME,
        "portal_url": PORTAL_URL,
        "api_endpoint": API_ENDPOINT,
        "licence": LICENCE_NAME,
        "licence_url": LICENCE_URL,
        "access_date": ACCESS_DATE,
        "query_where": QUERY_WHERE,
        "query_order": QUERY_ORDER,
        "selected_columns": SELECTED_COLUMNS,
        "row_count": row_count,
        "column_count": column_count,
        "file_size_bytes": file_size_bytes,
        "sha256": sha256_hex,
    }
    metadata_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")

    print(
        f"Saved raw dataset to '{output_csv}' "
        f"({row_count:,} rows x {column_count} cols, "
        f"{file_size_bytes / (1024 * 1024):.2f} MB)."
    )
    print(f"Saved provenance metadata to '{metadata_path}' (SHA-256: {sha256_hex}).")
    return output_csv


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments for raw dataset download."""
    parser = argparse.ArgumentParser(
        description="Download raw City of Chicago Building Permits (H1 2024) CSV."
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-download and overwrite existing raw file in data/raw/.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint for downloading the raw dataset."""
    args = parse_args(argv)
    download_raw_dataset(force=args.force)
    return 0


if __name__ == "__main__":
    sys.exit(main())
