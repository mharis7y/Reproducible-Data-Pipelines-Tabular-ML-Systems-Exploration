# Raw Data Schema

## Dataset Metadata

- **Dataset Name**: City of Chicago Building Permits (H1 2024 Extract)
- **Source Portal URL**: https://data.cityofchicago.org/Buildings/Building-Permits/ydr8-5enu
- **API Endpoint**: `https://data.cityofchicago.org/resource/ydr8-5enu.csv`
- **Licence**: City of Chicago Data Terms of Use (Public Open Data) — https://www.chicago.gov/city/en/narr/foia/data_disclaimer.html
- **Access Date**: `2026-11-21`
- **Raw File Path**: `data/raw/chicago_building_permits_2024_h1.csv` (never modified or overwritten)
- **Provenance Metadata**: `data/raw/dataset_metadata.json`
- **SHA-256 Checksum**: `73ce902450df764ea5cb235a0e0ea49e1159ba6c5ad2026cd15ffaf26dd23805`
- **Raw Dimensions**: `16,934 rows × 29 columns` (`7.55 MB` / `7,916,452 bytes`)
- **Date Range**: `application_start_date` from `2024-01-01` to `2024-06-30`; `issue_date` from `2024-01-01` to `2026-11-16`
- **Duplicates**: `0` exact full-row duplicates; `0` duplicate `id`; `0` duplicate `permit_`

## Column Schema (All 29 Raw Columns)

| # | Column | Raw Dtype | Target Type | Units | Allowed Values / Validation Rules | Missing Count (%) | Observed Notes / Quality Issues |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | `id` | `str` | `string` (ID) | `N/A` | Non-null, unique primary key (`16,934` unique) | `0 (0.00%)` | All unique; samples: `'3354066'`, `'3359529'` |
| 2 | `permit_` | `str` | `string` (ID) | `N/A` | Non-null, unique permit identifier (`16,934` unique) | `0 (0.00%)` | Alphanumeric codes (e.g., `'101038117'`, `'B101041197'`) |
| 3 | `permit_status` | `str` | `category` | `N/A` | Known status labels (`COMPLETE`, `EXPIRED`, etc.) or `"UNKNOWN"` | `1,946 (11.49%)` | `7` non-null categories; uppercase; `11.49%` missing |
| 4 | `permit_milestone` | `str` | `category` | `N/A` | Known milestone labels (`COMPLETE`, `INSPECTIONS`, etc.) or `"UNKNOWN"` | `1,946 (11.49%)` | `11` non-null categories; missing on exact same count as `permit_status` |
| 5 | `permit_type` | `str` | `category` | `N/A` | Standardized ASCII uppercase categories (`8` unique) | `0 (0.00%)` | **Quality issue**: `10,952` rows (`64.67%`) use Unicode en-dash `\u2013` in `'PERMIT – EXPRESS PERMIT PROGRAM'` |
| 6 | `review_type` | `str` | `category` | `N/A` | Standardized uppercase review process (`9` unique) | `0 (0.00%)` | Clean uppercase strings (e.g., `'SELF CERT'`, `'STANDARD PLAN REVIEW'`) |
| 7 | `application_start_date` | `str` | `datetime64[ns]` | ISO timestamp | Valid date in `[2024-01-01, 2024-07-01)` | `0 (0.00%)` | `182` distinct dates; `0` unparseable |
| 8 | `issue_date` | `str` | `datetime64[ns]` | ISO timestamp | Valid date `>= application_start_date` | `0 (0.00%)` | `484` distinct dates up to `2026-11-16`; `0` unparseable |
| 9 | `processing_time` | `int64` | `int64` | `days` | Integer `>= 0` (consistent with `issue_date - application_start_date`) | `0 (0.00%)` | Min `0` (`5,466` rows), median `4.0`, p75 `24.0`, p95 `131.0`, max `1,034`; `137` rows `> 365` days |
| 10 | `street_number` | `int64` | `int64` | `address #` | Positive integer `> 0` | `0 (0.00%)` | `5,170` distinct values |
| 11 | `street_direction` | `str` | `category` | `N/A` | One of `{'N', 'S', 'E', 'W'}` | `0 (0.00%)` | `4` distinct values (`'N'`, `'S'`, `'E'`, `'W'`) |
| 12 | `street_name` | `str` | `string` | `N/A` | Non-empty uppercase street name | `0 (0.00%)` | `1,045` distinct names; no whitespace/casing issues |
| 13 | `work_type` | `str` | `category` | `N/A` | Standardized work category or `"UNSPECIFIED"` | `5,982 (35.33%)` | `18` non-null categories (e.g., `'Electrical Work'`); highest missingness (`35.33%`) |
| 14 | `work_description` | `str` | `string` (text) | `N/A` | Non-empty free-text project description | `0 (0.00%)` | `14,467` unique descriptions; free text |
| 15 | `building_fee_paid` | `float64` | `float64` | `USD` | Float `>= 0.0` | `0 (0.00%)` | Max `$636,073.64`; `0` negatives |
| 16 | `zoning_fee_paid` | `float64` | `float64` | `USD` | Float `>= 0.0` | `0 (0.00%)` | Max `$16,307.00`; `0` negatives |
| 17 | `other_fee_paid` | `float64` | `float64` | `USD` | Float `>= 0.0` | `0 (0.00%)` | Max `$109,456.00`; `0` negatives |
| 18 | `subtotal_paid` | `float64` | `float64` | `USD` | Float `>= 0.0` | `0 (0.00%)` | Max `$758,952.64`; `0` negatives |
| 19 | `subtotal_unpaid` | `float64` | `float64` | `USD` | Float `>= 0.0` | `0 (0.00%)` | Max `$29,430.53`; `0` negatives |
| 20 | `subtotal_waived` | `float64` | `float64` | `USD` | Float `>= 0.0` | `0 (0.00%)` | Max `$110,700.00`; `0` negatives |
| 21 | `total_fee` | `float64` | `float64` | `USD` | Float `>= 0.0` and equals `subtotal_paid + subtotal_unpaid + subtotal_waived` | `0 (0.00%)` | Max `$758,952.64`; `0` rows fail subtotal reconciliation |
| 22 | `reported_cost` | `float64` | `float64` | `USD` | Non-negative float (flag `$0` / `<= $1` placeholder costs and extreme outliers) | `1,196 (7.06%)` | **Quality issues**: `1,196` missing; `160` rows `== 0.0`; `543` rows `<= 1.0`; `41` rows `> $10M` (max `$259M`, median `$10,640`) |
| 23 | `community_area` | `float64` | `Int64` | `area ID` | Integer in `1..77` (or `NA` if unmapped/invalid sentinel) | `244 (1.44%)` | **Quality issue**: `78` unique raw values — `3` rows contain sentinel `0` (converted to `pd.NA` in cleaning); valid range `1..77` |
| 24 | `ward` | `float64` | `Int64` | `ward ID` | Integer in `1..50` (or `NA` if unmapped/invalid sentinel) | `244 (1.44%)` | **Quality issue**: `51` unique raw values — `3` rows contain sentinel `0` (converted to `pd.NA` in cleaning); valid range `1..50` |
| 25 | `contact_1_type` | `str` | `category` | `N/A` | Standardized contact role (`19` unique) or `"UNKNOWN"` | `5 (0.03%)` | e.g., `'SELF CERT ARCHITECT'`, `'OWNER OCCUPIED'` |
| 26 | `contact_1_city` | `str` | `string` | `N/A` | Standardized uppercase city string or `"UNKNOWN"` | `58 (0.34%)` | `462` unique cities; `0` leading/trailing whitespace issues |
| 27 | `contact_1_state` | `str` | `category` | `N/A` | 2-letter uppercase US/territory code (`^[A-Z]{2}$`) or `"UNKNOWN"` | `69 (0.41%)` | **Quality issue**: `41` malformed entries (`'ILLINOIS'`: 39, `'IL.'`: 2); `39` raw unique values |
| 28 | `latitude` | `float64` | `float64` | `degrees (WGS84)` | Within Chicago bounds `[41.6, 42.1]` when non-null | `333 (1.97%)` | Observed range `[41.6447, 42.0226]`; `0` zeros or out-of-bounds |
| 29 | `longitude` | `float64` | `float64` | `degrees (WGS84)` | Within Chicago bounds `[-88.0, -87.5]` when non-null | `333 (1.97%)` | Observed range `[-87.9144, -87.5260]`; `0` zeros or out-of-bounds |

## Summary of Measured Raw Data Quality Issues

1. **Unicode dash mismatch (`permit_type`)**: `10,952 / 16,934` rows (`64.67%`) use Unicode en-dash `\u2013` instead of ASCII `-`.
2. **Non-standard state codes (`contact_1_state`)**: `41` rows fail the 2-letter code rule (`'ILLINOIS'`: 39, `'IL.'`: 2), alongside `69` missing values (`0.41%`).
3. **Missing values across key columns**: `work_type` (`5,982`, `35.33%`), `permit_status` (`1,946`, `11.49%`), `permit_milestone` (`1,946`, `11.49%`), `reported_cost` (`1,196`, `7.06%`), `latitude`/`longitude` (`333`, `1.97%`), `community_area`/`ward` (`244`, `1.44%`), `contact_1_city` (`58`, `0.34%`), `contact_1_type` (`5`, `0.03%`).
4. **Placeholder & extreme cost outliers (`reported_cost`)**: `160` zero values, `543` values `<= $1.00`, and `41` extreme values `> $10M` up to `$259,000,000.00`.
5. **Extreme right-skew (`processing_time`)**: Ranges from `0` (`5,466` rows) to `1,034` days (`137` rows `> 365` days; median `4.0` days).
6. **Out-of-domain geographic IDs (`community_area`, `ward`)**: `78` distinct `community_area` values vs. 77 official areas (`3` rows have sentinel `0`) and `51` distinct `ward` values vs. 50 official wards (`3` rows have sentinel `0`).

## Auxiliary Reference Table (`data/raw/chicago_community_areas.csv`)

Used in `sql/community_area_insights.sql` (`src/sql_queries.py`) to map integer `community_area` IDs (`1..77`) to official Chicago neighborhood names:
- **Source API**: `https://data.cityofchicago.org/resource/igwz-8jzy.csv?$select=area_numbe,community&$order=area_numbe ASC`
- **Dimensions**: `77` rows × `2` columns (`area_numbe` integer `1..77`, `community` uppercase neighborhood name).

## Derived Columns Produced in Cleaned Output (`data/cleaned/chicago_building_permits_cleaned.csv`)

In addition to the 29 raw columns, `src/cleaning.py` appends 12 deterministic columns (`41` total columns):
- Calendar fields: `application_month` (`YYYY-MM`), `application_dayofweek` (`Int64`, `0=Mon..6=Sun`), `application_day_name` (`str`)
- Missingness indicators: `reported_cost_missing` (`bool`), `coords_missing` (`bool`)
- Vectorized target & tier fields: `is_delayed` (`Int64`, `1` if `processing_time > 30` else `0`), `processing_tier` (`str` bucket)
- Cost outlier flags & transforms: `reported_cost_is_placeholder` (`bool`, `<= $1`), `reported_cost_outlier_flag` (`bool`, `> $10M`), `reported_cost_winsorized` (`float64`, clipped at 99th percentile `$3,083,746.50`), `log_reported_cost` (`float64`, `np.log1p`), `fee_to_cost_ratio` (`float64`, `total_fee / reported_cost` when `cost > $1`, else `NaN`).
