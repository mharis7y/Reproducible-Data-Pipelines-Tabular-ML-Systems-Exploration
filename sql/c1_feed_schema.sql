-- Name: Muhammad Haris | Roll Number: TRN-2026-000809 | Date: 2026-11-22
-- Purpose: Part C1 SQLite schema, composite index, chronological feed query,
--          and Bonus (+2) recency-and-likes top-10 feed ranker query.

CREATE TABLE users (
    user_id INTEGER PRIMARY KEY,
    username TEXT NOT NULL
);

CREATE TABLE follows (
    follower_id INTEGER NOT NULL,
    followee_id INTEGER NOT NULL,
    PRIMARY KEY (follower_id, followee_id)
);

CREATE TABLE posts (
    post_id INTEGER PRIMARY KEY,
    author_id INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    likes INTEGER NOT NULL,
    body TEXT NOT NULL
);

-- Benchmark A: Chronological Top-20 Feed Query (Fan-out on Read)
-- Params: (follower_id)
SELECT
    p.post_id,
    p.author_id,
    p.created_at,
    p.likes
FROM follows AS f
INNER JOIN posts AS p
    ON p.author_id = f.followee_id
WHERE f.follower_id = ?
ORDER BY p.created_at DESC
LIMIT 20;

-- Composite Index to accelerate per-author recent post lookups and range scans
CREATE INDEX idx_follows_follower ON follows(follower_id, followee_id);
CREATE INDEX idx_posts_author_created ON posts(author_id, created_at DESC);

-- Benchmark B (Bonus): Top-10 Ranked Feed Query (Recency + Likes over candidate window)
-- Uses pure SQLite math so it runs cleanly without extensions:
--   rank_score = (likes + 1.0) / (age_hours + 2.0)^2
-- Params: (reference_iso_ts, reference_iso_ts, follower_id, window_start_iso_ts)
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
