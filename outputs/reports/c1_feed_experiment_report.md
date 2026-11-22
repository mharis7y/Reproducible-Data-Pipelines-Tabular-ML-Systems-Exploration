# Part C1: SQLite Feed Query & Bonus Ranker Benchmark Report

- **Synthetic Graph**: `1,000` users, `150,000` posts, target user follows `80` authors (`15` timed repeats).

## 1. Chronological Top-20 Feed Timings & Query Plans

| Mode | Mean Latency (ms) | Relative Speedup |
| --- | ---: | ---: |
| Unindexed (`posts` full scan) | 56.2248 | 1.00× |
| Indexed (`idx_posts_author_created(author_id, created_at DESC)`) | 2.4218 | **23.22×** |

**Unindexed `EXPLAIN QUERY PLAN`**:
```text
id=5 parent=0 detail=SCAN p
id=7 parent=0 detail=SEARCH f USING COVERING INDEX sqlite_autoindex_follows_1 (follower_id=? AND followee_id=?)
id=26 parent=0 detail=USE TEMP B-TREE FOR ORDER BY
```

**Indexed `EXPLAIN QUERY PLAN`**:
```text
id=6 parent=0 detail=SEARCH f USING COVERING INDEX idx_follows_follower (follower_id=?)
id=12 parent=0 detail=SEARCH p USING INDEX idx_posts_author_created (author_id=?)
id=31 parent=0 detail=USE TEMP B-TREE FOR ORDER BY
```

## 2. Bonus (+2) Tiny Feed Ranker (Top 10 by Recency & Likes)

- **Formula**: `(likes + 1.0) / (age_hours + 2.0)^2 over 7-day candidate window`

| Implementation | Mean Latency (ms) | Speedup vs. Unindexed |
| --- | ---: | ---: |
| Unindexed SQLite Ranker | 25.4721 | 1.00× |
| Indexed SQLite Candidate Ranker | 3.9829 | **6.40×** |
| In-Memory Feed Cache Hit | 0.000123 | **207,090.2×** |

### Sample Top-10 Ranked Posts Returned for `user_id=1`

| Rank | Post ID | Author | Created At | Likes | Rank Score |
| ---: | ---: | --- | --- | ---: | ---: |
| 1 | 87550 | user_0097 | 2026-11-22 09:42:11 | 255 | 13.865020 |
| 2 | 17811 | user_0346 | 2026-11-22 10:28:08 | 165 | 13.313288 |
| 3 | 42384 | user_0946 | 2026-11-22 11:26:10 | 57 | 8.823270 |
| 4 | 140202 | user_0008 | 2026-11-22 10:51:53 | 63 | 6.510704 |
| 5 | 69128 | user_0008 | 2026-11-22 08:58:47 | 151 | 6.030983 |
| 6 | 70041 | user_0096 | 2026-11-22 11:46:20 | 27 | 5.641756 |
| 7 | 126647 | user_0908 | 2026-11-22 10:38:47 | 61 | 5.512725 |
| 8 | 19195 | user_0225 | 2026-11-22 09:43:35 | 95 | 5.256313 |
| 9 | 96794 | user_0129 | 2026-11-22 09:41:06 | 94 | 5.102253 |
| 10 | 131957 | user_0576 | 2026-11-22 11:05:34 | 41 | 4.969273 |
