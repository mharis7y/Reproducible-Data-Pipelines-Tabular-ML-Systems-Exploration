# Name: Muhammad Haris
# Roll Number: TRN-2026-000809
# Date: 2026-11-22
"""Part C1 SQLite feed query optimization & Bonus (+2) recency+likes feed ranker benchmark."""

from __future__ import annotations

import argparse
import json
import random
import sqlite3
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_RESULTS_JSON = (
    PROJECT_ROOT / "outputs" / "reports" / "c1_feed_experiment_results.json"
)
DEFAULT_REPORT_MD = (
    PROJECT_ROOT / "outputs" / "reports" / "c1_feed_experiment_report.md"
)

CHRONOLOGICAL_FEED_SQL = """
SELECT
    p.post_id,
    p.author_id,
    p.created_at,
    p.likes
FROM follows AS f
INNER JOIN posts AS p
    ON p.author_id = f.followee_id
WHERE f.follower_id = ?
ORDER BY p.created_at DESC, p.post_id DESC
LIMIT 20;
"""

RANKED_FEED_SQL = """
SELECT
    p.post_id,
    p.author_id,
    p.created_at,
    p.likes,
    ROUND(
        (p.likes + 1.0) / (
            ((julianday(?) - julianday(p.created_at)) * 24.0 + 2.0)
            * ((julianday(?) - julianday(p.created_at)) * 24.0 + 2.0)
        ),
        6
    ) AS rank_score
FROM follows AS f
INNER JOIN posts AS p
    ON p.author_id = f.followee_id
WHERE f.follower_id = ?
  AND p.created_at >= ?
ORDER BY rank_score DESC, p.post_id DESC
LIMIT 10;
"""


def _build_demo_database(
    conn: sqlite3.Connection,
    n_users: int,
    n_posts: int,
    n_following: int,
    seed: int = 42,
) -> tuple[str, str]:
    """Populate synthetic users, follow edges, and posts in SQLite with fixed seed."""
    rng = random.Random(seed)
    ref_time = datetime(2026, 11, 22, 12, 0, 0)
    window_start = ref_time - timedelta(days=7)

    conn.execute("CREATE TABLE users (user_id INTEGER PRIMARY KEY, username TEXT NOT NULL);")
    conn.execute(
        "CREATE TABLE follows ("
        "follower_id INTEGER NOT NULL, "
        "followee_id INTEGER NOT NULL, "
        "PRIMARY KEY (follower_id, followee_id)"
        ");"
    )
    conn.execute(
        "CREATE TABLE posts ("
        "post_id INTEGER PRIMARY KEY, "
        "author_id INTEGER NOT NULL, "
        "created_at TEXT NOT NULL, "
        "likes INTEGER NOT NULL, "
        "body TEXT NOT NULL"
        ");"
    )

    users = [(uid, f"user_{uid:04d}") for uid in range(1, n_users + 1)]
    conn.executemany("INSERT INTO users (user_id, username) VALUES (?, ?);", users)

    # Target user 1 follows n_following authors; other users also create realistic graph density
    target_followees = rng.sample(range(2, n_users + 1), min(n_following, n_users - 1))
    follow_rows: list[tuple[int, int]] = [(1, fid) for fid in target_followees]
    for uid in range(2, n_users + 1):
        sample_size = min(15, n_users - 1)
        peers = rng.sample([u for u in range(1, n_users + 1) if u != uid], sample_size)
        for fid in peers:
            follow_rows.append((uid, fid))
    conn.executemany(
        "INSERT INTO follows (follower_id, followee_id) VALUES (?, ?);", follow_rows
    )

    post_rows: list[tuple[int, int, str, int, str]] = []
    max_seconds = 30 * 24 * 3600
    for pid in range(1, n_posts + 1):
        author_id = rng.randint(1, n_users)
        age_sec = rng.randint(60, max_seconds)
        created_iso = (ref_time - timedelta(seconds=age_sec)).strftime("%Y-%m-%d %H:%M:%S")
        # Heavy-tailed realistic engagement counts
        likes = int(rng.expovariate(1 / 25.0)) + (
            rng.randint(80, 600) if pid % 50 == 0 else 0
        )
        post_rows.append((pid, author_id, created_iso, likes, f"Post #{pid} by user {author_id}"))

    conn.executemany(
        "INSERT INTO posts (post_id, author_id, created_at, likes, body) VALUES (?, ?, ?, ?, ?);",
        post_rows,
    )
    conn.commit()
    return (
        ref_time.strftime("%Y-%m-%d %H:%M:%S"),
        window_start.strftime("%Y-%m-%d %H:%M:%S"),
    )


def _explain_query_plan(
    conn: sqlite3.Connection,
    sql: str,
    params: tuple[Any, ...],
) -> list[str]:
    """Return formatted EXPLAIN QUERY PLAN lines for a SQLite query."""
    rows = conn.execute(f"EXPLAIN QUERY PLAN {sql}", params).fetchall()
    return [f"id={r[0]} parent={r[1]} detail={r[3]}" for r in rows]


def _benchmark_query(
    conn: sqlite3.Connection,
    sql: str,
    params: tuple[Any, ...],
    n_repeats: int,
) -> tuple[list[tuple[Any, ...]], float]:
    """Time repeated SQLite query execution and return rows + mean latency in ms."""
    rows = conn.execute(sql, params).fetchall()
    start = time.perf_counter()
    for _ in range(n_repeats):
        rows = conn.execute(sql, params).fetchall()
    elapsed_ms = ((time.perf_counter() - start) / max(n_repeats, 1)) * 1000.0
    return rows, round(elapsed_ms, 4)


def run_feed_experiment(
    n_users: int = 1000,
    n_posts: int = 150_000,
    n_following: int = 80,
    n_repeats: int = 15,
    seed: int = 42,
) -> dict[str, Any]:
    """Run unindexed vs. indexed chronological and ranked feed benchmarks in SQLite."""
    with sqlite3.connect(":memory:") as conn:
        ref_iso, window_start_iso = _build_demo_database(
            conn,
            n_users=n_users,
            n_posts=n_posts,
            n_following=n_following,
            seed=seed,
        )
        target_user_id = 1
        chrono_params = (target_user_id,)
        rank_params = (ref_iso, ref_iso, target_user_id, window_start_iso)

        # 1. Unindexed phase
        unindexed_chrono_plan = _explain_query_plan(conn, CHRONOLOGICAL_FEED_SQL, chrono_params)
        unindexed_chrono_rows, unindexed_chrono_ms = _benchmark_query(
            conn, CHRONOLOGICAL_FEED_SQL, chrono_params, n_repeats=n_repeats
        )

        unindexed_rank_plan = _explain_query_plan(conn, RANKED_FEED_SQL, rank_params)
        unindexed_rank_rows, unindexed_rank_ms = _benchmark_query(
            conn, RANKED_FEED_SQL, rank_params, n_repeats=n_repeats
        )

        # 2. Add composite indexes and update query planner statistics
        conn.execute("CREATE INDEX idx_follows_follower ON follows(follower_id, followee_id);")
        conn.execute("CREATE INDEX idx_posts_author_created ON posts(author_id, created_at DESC);")
        conn.execute("ANALYZE;")

        indexed_chrono_plan = _explain_query_plan(conn, CHRONOLOGICAL_FEED_SQL, chrono_params)
        indexed_chrono_rows, indexed_chrono_ms = _benchmark_query(
            conn, CHRONOLOGICAL_FEED_SQL, chrono_params, n_repeats=n_repeats
        )

        indexed_rank_plan = _explain_query_plan(conn, RANKED_FEED_SQL, rank_params)
        indexed_rank_rows, indexed_rank_ms = _benchmark_query(
            conn, RANKED_FEED_SQL, rank_params, n_repeats=n_repeats
        )

    # Verify identical query results before and after indexing
    unindexed_chrono_ids = [r[0] for r in unindexed_chrono_rows]
    indexed_chrono_ids = [r[0] for r in indexed_chrono_rows]
    if unindexed_chrono_ids != indexed_chrono_ids:
        raise RuntimeError("Chronological feed results differed between unindexed and indexed!")

    unindexed_rank_ids = [r[0] for r in unindexed_rank_rows]
    indexed_rank_ids = [r[0] for r in indexed_rank_rows]
    if unindexed_rank_ids != indexed_rank_ids:
        raise RuntimeError("Ranked top-10 results differed between unindexed and indexed!")

    # 3. In-memory Cache Hit benchmark for ranked feed
    feed_cache: dict[tuple[int, str], list[tuple[Any, ...]]] = {
        (target_user_id, window_start_iso): indexed_rank_rows
    }
    cache_start = time.perf_counter()
    cached_rows: list[tuple[Any, ...]] = []
    for _ in range(max(n_repeats * 100, 100)):
        cached_rows = feed_cache[(target_user_id, window_start_iso)]
    cached_ms = ((time.perf_counter() - cache_start) / max(n_repeats * 100, 100)) * 1000.0
    cached_ms = round(cached_ms, 6)

    if [r[0] for r in cached_rows] != indexed_rank_ids:
        raise RuntimeError("Cached feed results did not match SQLite top-10 output!")

    chrono_speedup = round(unindexed_chrono_ms / max(indexed_chrono_ms, 1e-6), 2)
    rank_index_speedup = round(unindexed_rank_ms / max(indexed_rank_ms, 1e-6), 2)
    rank_cache_speedup = round(unindexed_rank_ms / max(cached_ms, 1e-9), 1)

    top_10_ranked = [
        {
            "rank": idx + 1,
            "post_id": int(r[0]),
            "author_id": int(r[1]),
            "created_at": str(r[2]),
            "likes": int(r[3]),
            "rank_score": float(r[4]),
        }
        for idx, r in enumerate(indexed_rank_rows)
    ]

    return {
        "setup": {
            "n_users": n_users,
            "n_posts": n_posts,
            "target_user_id": target_user_id,
            "followed_authors": min(n_following, n_users - 1),
            "n_repeats": n_repeats,
            "reference_time": ref_iso,
            "candidate_window_start": window_start_iso,
        },
        "chronological_feed": {
            "unindexed_mean_ms": unindexed_chrono_ms,
            "indexed_mean_ms": indexed_chrono_ms,
            "speedup_factor": chrono_speedup,
            "unindexed_query_plan": unindexed_chrono_plan,
            "indexed_query_plan": indexed_chrono_plan,
            "top_20_post_ids": indexed_chrono_ids,
        },
        "bonus_ranked_feed_top10": {
            "formula": "(likes + 1.0) / (age_hours + 2.0)^2 over 7-day candidate window",
            "unindexed_mean_ms": unindexed_rank_ms,
            "indexed_mean_ms": indexed_rank_ms,
            "cached_mean_ms": cached_ms,
            "index_speedup_factor": rank_index_speedup,
            "cache_speedup_factor": rank_cache_speedup,
            "unindexed_query_plan": unindexed_rank_plan,
            "indexed_query_plan": indexed_rank_plan,
            "top_10_posts": top_10_ranked,
        },
    }


def write_c1_report(
    results: dict[str, Any],
    json_path: Path = DEFAULT_RESULTS_JSON,
    md_path: Path = DEFAULT_REPORT_MD,
) -> None:
    """Persist C1 benchmark metrics and Markdown summary report."""
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")

    setup = results["setup"]
    chrono = results["chronological_feed"]
    ranked = results["bonus_ranked_feed_top10"]

    top_rows_md = "\n".join(
        f"| {p['rank']} | {p['post_id']} | user_{p['author_id']:04d} | "
        f"{p['created_at']} | {p['likes']} | {p['rank_score']:.6f} |"
        for p in ranked["top_10_posts"]
    )
    unidx_plan = "\n".join(chrono["unindexed_query_plan"])
    idx_plan = "\n".join(chrono["indexed_query_plan"])

    md = f"""# Part C1: SQLite Feed Query & Bonus Ranker Benchmark Report

- **Synthetic Graph**: `{setup['n_users']:,}` users, `{setup['n_posts']:,}` posts, target user follows `{setup['followed_authors']}` authors (`{setup['n_repeats']}` timed repeats).

## 1. Chronological Top-20 Feed Timings & Query Plans

| Mode | Mean Latency (ms) | Relative Speedup |
| --- | ---: | ---: |
| Unindexed (`posts` full scan) | {chrono['unindexed_mean_ms']:.4f} | 1.00× |
| Indexed (`idx_posts_author_created(author_id, created_at DESC)`) | {chrono['indexed_mean_ms']:.4f} | **{chrono['speedup_factor']:.2f}×** |

**Unindexed `EXPLAIN QUERY PLAN`**:
```text
{unidx_plan}
```

**Indexed `EXPLAIN QUERY PLAN`**:
```text
{idx_plan}
```

## 2. Bonus (+2) Tiny Feed Ranker (Top 10 by Recency & Likes)

- **Formula**: `{ranked['formula']}`

| Implementation | Mean Latency (ms) | Speedup vs. Unindexed |
| --- | ---: | ---: |
| Unindexed SQLite Ranker | {ranked['unindexed_mean_ms']:.4f} | 1.00× |
| Indexed SQLite Candidate Ranker | {ranked['indexed_mean_ms']:.4f} | **{ranked['index_speedup_factor']:.2f}×** |
| In-Memory Feed Cache Hit | {ranked['cached_mean_ms']:.6f} | **{ranked['cache_speedup_factor']:,.1f}×** |

### Sample Top-10 Ranked Posts Returned for `user_id=1`

| Rank | Post ID | Author | Created At | Likes | Rank Score |
| ---: | ---: | --- | --- | ---: | ---: |
{top_rows_md}
"""
    md_path.write_text(md, encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments for the Part C1 feed benchmark."""
    parser = argparse.ArgumentParser(description="Run Part C1 SQLite feed benchmark.")
    parser.add_argument("--n-users", type=int, default=1000)
    parser.add_argument("--n-posts", type=int, default=150_000)
    parser.add_argument("--n-following", type=int, default=80)
    parser.add_argument("--n-repeats", type=int, default=15)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint for running and saving the Part C1 SQLite feed experiment."""
    args = parse_args(argv)
    results = run_feed_experiment(
        n_users=args.n_users,
        n_posts=args.n_posts,
        n_following=args.n_following,
        n_repeats=args.n_repeats,
    )
    write_c1_report(results)

    chrono = results["chronological_feed"]
    ranked = results["bonus_ranked_feed_top10"]
    print(
        f"Part C1 SQLite Benchmark ({args.n_posts:,} posts, {args.n_following} followed authors):"
    )
    print(
        f"  Chronological Top-20 -> Unindexed: {chrono['unindexed_mean_ms']:.4f} ms | "
        f"Indexed: {chrono['indexed_mean_ms']:.4f} ms ({chrono['speedup_factor']:.2f}x faster)"
    )
    print(
        f"  Bonus Ranked Top-10  -> Unindexed: {ranked['unindexed_mean_ms']:.4f} ms | "
        f"Indexed: {ranked['indexed_mean_ms']:.4f} ms ({ranked['index_speedup_factor']:.2f}x) | "
        f"Cache Hit: {ranked['cached_mean_ms']:.6f} ms ({ranked['cache_speedup_factor']:,.1f}x)"
    )
    print("Indexed EXPLAIN QUERY PLAN:")
    for line in chrono["indexed_query_plan"]:
        print(f"  {line}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
