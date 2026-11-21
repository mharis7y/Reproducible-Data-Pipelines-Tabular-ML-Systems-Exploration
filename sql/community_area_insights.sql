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
