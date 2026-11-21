# Part A: Data Quality & Insights Report

## 1. Before-and-After Data Quality Metrics

| Metric | Raw Dataset (Before) | Cleaned Dataset (After) | Change / Action |
| --- | ---: | ---: | --- |
| Rows | 16,934 | 16,934 | 0 duplicates removed |
| Columns | 29 | 41 | +12 engineered/flag cols |
| Total Missing Cells | 12,356 (2.52%) | 6,487 (0.93%) | 10,006 categorical nulls filled; numeric/geo nulls preserved with flags |
| Non-ASCII `permit_type` Rows (`\u2013`) | 10,952 | 0 | 10,952 Unicode dashes normalized to `-` |
| Invalid `contact_1_state` Formats | 41 | 0 | 41 normalized (`ILLINOIS`/`IL.` -> `IL`) |
| `community_area == 0` Sentinels | 3 | 0 | Converted 3 sentinels to `pd.NA` |
| `ward == 0` Sentinels | 3 | 0 | Converted 3 sentinels to `pd.NA` |
| Placeholder `reported_cost <= $1` | 543 | Flagged (`reported_cost_is_placeholder`) | Kept raw value + boolean flag |
| Extreme `reported_cost > $10M` | 41 | Flagged + Winsorized (`p99=$3,083,746.50`) | Preserved raw value + added clipped/log views |
| **Validation Row Pass Rate** | — | **100.0000%** | Quality gate threshold: `99.00%` (**PASSED**) |

## 2. NumPy & Pandas Analytical Highlights

- **Vectorized Processing Time Distribution (`numpy`)**: Mean = **27.04 days**, Std = **65.12 days**, p25 = `0.0`, Median (p50) = `4.0`, p75 = `24.0`, p90 = `72.0`, p95 = `131.0`, p99 = `333.0`.
- **Vectorized Log Cost vs. Log Processing Time Correlation (`numpy.corrcoef`)**: `r = 0.3407` across `15,195` permits with valid cost `> $1.00`, confirming larger/higher-cost construction projects undergo longer review durations.

### Top Review Types (`summary_by_review_type.csv`)

| review_type | permit_count | delayed_count | delayed_rate_pct | median_processing_days | mean_processing_days | p90_processing_days | median_reported_cost_usd | total_fees_usd |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| EXPRESS PERMIT PROGRAM | 10952 | 746 | 6.81 | 1.0 | 8.03 | 22.0 | 6000.0 | 3365153.45 |
| STANDARD PLAN REVIEW | 2173 | 1484 | 68.29 | 60.0 | 99.77 | 244.8 | 48000.0 | 4920723.43 |
| SELF CERT | 1418 | 637 | 44.92 | 26.0 | 47.24 | 110.0 | 175000.0 | 3706028.83 |
| SIGN PERMIT | 1174 | 571 | 48.64 | 29.0 | 52.13 | 126.7 | 3000.0 | 353095.0 |
| CONVEYANCE DEVICE PERMIT | 632 | 1 | 0.16 | 0.0 | 1.51 | 6.0 | 28669.370000000003 | 491079.07 |

## 3. SQLite Query & Geographic Insights (`sql/community_area_insights.sql`)

```sql
-- Name: Muhammad Haris | Roll Number: TRN-2026-000809 | Date: 2026-11-21
-- Purpose: Part A SQLite JOIN comparing H1 2024 building permit volume, delay rates,
--          processing duration, and reported construction costs across official
--          Chicago Community Areas (excluding unmapped areas and small areas < 100 permits).

SELECT
    c.community_area,
    c.area_name,
    COUNT(*) AS permit_count,
    SUM(p.is_delayed) AS delayed_count,
    ROUND(100.0 * AVG(p.is_delayed), 2) AS delayed_rate_pct,
    ROUND(AVG(p.processing_time), 2) AS avg_processing_days,
    ROUND(SUM(COALESCE(p.reported_cost, 0.0)), 2) AS total_reported_cost_usd,
    ROUND(AVG(CASE WHEN p.reported_cost > 1.0 THEN p.reported_cost END), 2) AS avg_reported_cost_usd,
    ROUND(SUM(p.total_fee), 2) AS total_fees_usd
FROM permits AS p
INNER JOIN community_areas AS c
    ON p.community_area = c.community_area
WHERE p.community_area IS NOT NULL
GROUP BY c.community_area, c.area_name
HAVING COUNT(*) >= 100
ORDER BY permit_count DESC;
```

### Top 10 Chicago Community Areas by H1 2024 Permit Volume (`>= 100` Permits)

| community_area | area_name | permit_count | delayed_count | delayed_rate_pct | avg_processing_days | total_reported_cost_usd | avg_reported_cost_usd | total_fees_usd |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 32 | Loop | 1386 | 196 | 14.14 | 15.68 | 410503864.5 | 332391.77 | 1410750.91 |
| 8 | Near North Side | 1373 | 332 | 24.18 | 24.9 | 689998772.0 | 560063.93 | 2250797.75 |
| 28 | Near West Side | 868 | 216 | 24.88 | 27.93 | 645716559.61 | 833182.64 | 1906347.67 |
| 7 | Lincoln Park | 682 | 199 | 29.18 | 32.06 | 208373278.0 | 415085.94 | 794666.24 |
| 24 | West Town | 638 | 220 | 34.48 | 47.35 | 119318184.0 | 208963.54 | 868106.74 |
| 6 | Lake View | 602 | 117 | 19.44 | 24.21 | 79787337.05 | 148303.59 | 546507.45 |
| 25 | Austin | 469 | 99 | 21.11 | 27.92 | 61796482.2 | 147485.62 | 526664.65 |
| 22 | Logan Square | 405 | 108 | 26.67 | 36.71 | 61389090.4 | 172927.0 | 511121.68 |
| 49 | Roseland | 291 | 35 | 12.03 | 18.09 | 8251757.76 | 31375.46 | 114873.96 |
| 15 | Portage Park | 274 | 42 | 15.33 | 20.32 | 17184147.0 | 65839.64 | 179445.32 |

## 4. Saved Visualizations (`outputs/figures/`)

1. `01_processing_time_by_review_type.png`: Shows that `EXPRESS PERMIT PROGRAM` permits clear with a median of 1 day (6.81% delayed), whereas `STANDARD PLAN REVIEW` (68.29% delayed) and `DIRECT DEVELOPER SERVICES` (92.59% delayed) account for the steepest review bottlenecks.
2. `02_monthly_volume_and_delay_rate.png`: Shows monthly H1 2024 permit volume rising from January (`2,266`) into spring (`3,005–3,088`/month in April–June) while delay rates stayed between `18.31%` and `25.77%`.
3. `03_cost_vs_processing_tier.png`: Shows median reported construction cost rises steadily from same-day/fast tiers (`$4,000` same-day median) up to `Severely Delayed (>90d)` permits (`$80,000` median).
4. `04_top_community_areas_sql.png`: Highlights neighborhood-level disparities from the SQLite join, led in permit volume by `Loop` (1,386 permits), `Near North Side` (1,373 permits), `Near West Side` (868 permits), while `West Town` exhibits the highest delay share (`34.48%`) among neighborhoods with `>= 100` permits.
