# Part C: Systems & Engineering Exploration

---

## C1. Optimized Query System of a Social Media Algorithm (+ Bonus Feed Ranker)

### Write-Up: How Social Feeds Serve Fast at Scale
Loading a user's home feed appears simple ("show me recent posts from people I follow"), yet running a naive SQL join across millions of rows on every page refresh quickly collapses database CPU and I/O. Production feed architectures combine six key techniques:

1. **Candidate Retrieval**: Instead of scoring every post on the platform, the service narrows the pool first—typically fetching only recent posts (e.g., the last 7 days) authored by accounts the viewer follows (`follows` -> `posts`).
2. **Composite B-Tree Indexing `(author_id, created_at DESC)`**: A composite B-tree groups all posts by `author_id` and stores each author's timestamps already ordered descending. Rather than scanning the entire `posts` table (`O(N)` rows), SQLite performs a logarithmic B-tree seek per followed author (`O(k log N)`), bounding reads to the viewer's follow graph and time window.
3. **Fan-Out on Write vs. Fan-Out on Read (and Hybrid Model)**:
   - *Fan-out on Read (Pull)*: Computes the join at read time (`follows JOIN posts`). Writes are cheap (`O(1)` insert into `posts`), which fits high-follower "celebrity" accounts (millions of followers), though read latency grows with how many accounts a user follows.
   - *Fan-out on Write (Push)*: When a normal user publishes a post, background workers immediately push the `post_id` into each follower's precomputed inbox list (e.g., Redis sorted set). Reads become instant `O(1)` lookups, while writes cost `O(followers)`.
   - *Hybrid*: Push posts for typical users (`<10K` followers), pull posts for celebrities at read time, and merge in memory.
4. **Caching**: Pre-ranked top-K feeds (per `user_id`) cached in memory (Redis/Memcached) with short TTLs (30–120 seconds) absorb repeat refreshes in sub-millisecond time while shielding relational storage from read storms.
5. **Ranking & Pagination**: Candidate posts are scored by combining freshness decay with engagement (e.g., `(likes + 1.0) / (age_hours + 2.0)^2`) and paginated via **cursor/keyset pagination** (`WHERE (score, post_id) < (:last_score, :last_id)`) instead of `OFFSET`, avoiding skipped/duplicated items as new posts arrive and preventing deep-offset scan degradation.

### Artifact & Measured SQLite Experiment (`sql/c1_feed_schema.sql` & `src/c1_feed_experiment.py`)
We benchmarked a seeded SQLite social graph of **`1,000` users** and **`150,000` posts**, querying the home feed of `user_id = 1` following **`80` authors** (`outputs/reports/c1_feed_experiment_results.json`):

#### Benchmark A — Chronological Top-20 Feed Query

| Mode | Mean Latency (ms) | Relative Speedup |
| --- | ---: | ---: |
| Unindexed (`posts` full table scan) | `56.2248 ms` | `1.00×` |
| Indexed (`idx_follows_follower` + `idx_posts_author_created(author_id, created_at DESC)`) | `2.4218 ms` | **`23.22×` faster** |

- **Unindexed `EXPLAIN QUERY PLAN`**:
  ```text
  id=5 parent=0 detail=SCAN p
  id=7 parent=0 detail=SEARCH f USING COVERING INDEX sqlite_autoindex_follows_1 (follower_id=? AND followee_id=?)
  id=26 parent=0 detail=USE TEMP B-TREE FOR ORDER BY
  ```
- **Indexed `EXPLAIN QUERY PLAN`**:
  ```text
  id=6 parent=0 detail=SEARCH f USING COVERING INDEX idx_follows_follower (follower_id=?)
  id=12 parent=0 detail=SEARCH p USING INDEX idx_posts_author_created (author_id=?)
  id=31 parent=0 detail=USE TEMP B-TREE FOR ORDER BY
  ```

#### Benchmark B (Bonus +2) — Tiny Feed Ranker (Top 10 by Recency & Likes over 7-Day Window)
Using `rank_score = (likes + 1.0) / (age_hours + 2.0)^2`, all three modes returned the exact same Top-10 posts (led by `post_id=87550` with `255` likes and score `13.865020`):

| Implementation | Mean Latency (ms) | Speedup vs. Unindexed | Indexed `EXPLAIN QUERY PLAN` Detail |
| --- | ---: | ---: | --- |
| Unindexed SQLite Ranker | `25.4721 ms` | `1.00×` | `SCAN p` across all `150,000` rows |
| Indexed SQLite Candidate Ranker | `3.9829 ms` | **`6.40×` faster** | `SEARCH p USING INDEX idx_posts_author_created (author_id=? AND created_at>?)` |
| In-Memory Feed Cache Hit | `0.000123 ms` | **`207,090.2×` faster** | Direct O(1) dictionary lookup |

### Guiding Questions Answered
- **Why is a naive "join every followed user's posts at read time" query slow at scale?** Without an index on `posts(author_id, created_at)`, SQLite performs `SCAN p`—visiting every row in `posts` (`150,000` here, billions in production) and sorting matches in a temporary B-tree on every request.
- **What does an index on `(author_id, created_at)` change?** It flips the outer-to-inner execution order: SQLite finds the viewer's `80` followed authors via `idx_follows_follower` and executes targeted B-tree seeks (`SEARCH p USING INDEX idx_posts_author_created (author_id=? AND created_at>?)`), skipping irrelevant authors and expired posts.
- **When would you precompute feeds instead?** When read-to-write ratio is high, users follow hundreds of authors (increasing pull fan-out cost), or ML ranking becomes too expensive to compute synchronously per page load—while reserving pull/hybrid merges for high-fan-out celebrity accounts.
- **How does your experiment's result support your answer?** Indexing cut chronological feed latency `23.22×` (`56.22 ms -> 2.42 ms`) and candidate ranking `6.40×` (`25.47 ms -> 3.98 ms`), while serving a precomputed/cached top-10 feed dropped latency to `0.000123 ms` (`~207,090×` faster than unindexed SQLite).

### Sources
- SQLite Query Planning & Indexing: https://www.sqlite.org/queryplanner.html
- SQLite `EXPLAIN QUERY PLAN`: https://www.sqlite.org/eqp.html

---

## C2. GitHub Actions, Branch Rules, PR Rules & Code Reviews

### Write-Up: Automated Quality Gates & Team Review Workflow
Modern engineering teams protect production code using automated continuous integration (CI) paired with repository governance rules so broken or unreviewed code never lands on `main`:

1. **GitHub Actions Workflows, Triggers, Jobs, Caching & Secrets**:
   - A workflow YAML file under `.github/workflows/` defines **triggers** (`on: pull_request`, `push`, `workflow_dispatch`), **jobs** running on isolated VMs (`ubuntu-latest`), **concurrency groups** to cancel outdated runs on new pushes, and **pip caching** (`actions/setup-python@v5` with `cache: 'pip'` keyed to `requirements.txt`) to keep CI fast.
   - Sensitive credentials (API keys, deploy tokens) are never hardcoded in `.yml` files or committed code; they live in encrypted GitHub Repository/Environment **Secrets** (`${{ secrets.NAME }}`) masked automatically in logs and restricted from untrusted fork PRs.
2. **Branch Protection Rules / Repository Rulesets & Required Status Checks**:
   - Rulesets lock `main` against direct pushes and force-pushes, requiring all changes via Pull Requests (PRs), requiring passing **status checks** (e.g., `Ruff Lint & Pytest Suite`), and optionally requiring up-to-date branches before merge.
3. **`CODEOWNERS`, PR Templates & Effective Code Reviews**:
   - `.github/CODEOWNERS` automatically assigns required reviewers for critical directories (`/src/`, `/tests/`, `/sql/`, `/.github/workflows/`).
   - `.github/pull_request_template.md` standardizes PR descriptions (what changed, why, verification commands run, and self-checks).
   - A strong code review checks correctness, edge cases/error handling, test coverage, data-leakage/security risks, readability, and concise rationale ("why", not line-by-line nitpicks).

### Artifacts Submitted
- CI Workflow: [`.github/workflows/ci.yml`](../.github/workflows/ci.yml) — triggers on `pull_request` and `push` to `main`, caches pip dependencies against `requirements.txt`, and runs `ruff check src/ tests/` and `pytest -v`.
- PR Template & Review Checklist: [`.github/pull_request_template.md`](../.github/pull_request_template.md)
- Code Ownership Rules: [`.github/CODEOWNERS`](../.github/CODEOWNERS)

### Guiding Questions Answered
- **Which events should trigger the workflow?** `pull_request` targeting `main` (validates every proposed change before merge), `push` to `main` (verifies post-merge health), and `workflow_dispatch` (allows manual re-runs).
- **What should block a merge?** Any failure in required status checks (`ruff check src/ tests/` or `pytest -v`), missing required reviewer/code-owner approvals, unresolved review conversations, or outdated branches when strict status checks are enabled.
- **Who should be required to review which files, and why?** Core pipeline maintainers (`@mharis` in `CODEOWNERS`) should review `/src/` (leakage/correctness), `/tests/` (test integrity), `/sql/` (query safety), and especially `/.github/workflows/` (preventing contributors from weakening CI checks or leaking secrets).

### Sources
- GitHub Actions Documentation: https://docs.github.com/en/actions
- GitHub Managing Protected Branches & Rulesets: https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches
- GitHub `CODEOWNERS` Documentation: https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-code-owners
- Google Engineering Practices — Code Review Guide: https://google.github.io/eng-practices/review/

---

## C3. Theory of System Design

### Glossary (10 Core Terms with Concrete Examples)

1. **Requirements (Functional & Non-Functional)**: *Functional requirements* define what the system does (e.g., "a user can submit a permit and receive a delay risk band"); *non-functional requirements* define how well it operates (e.g., "99.9% uptime, p95 API latency `< 200 ms`, zero data loss").
2. **Capacity Estimation**: Back-of-the-envelope calculations for traffic (QPS), storage, memory, and bandwidth before building—e.g., `100K` daily active users making `20` feed reads/day = `2M reads/day` (`~23 avg QPS`, `~70–100 peak QPS`) and `500 bytes/post` × `1M posts/day` = `~500 MB/day` raw text storage.
3. **Load Balancing**: Distributing incoming requests across multiple stateless backend servers using algorithms like round-robin or least-connections (plus health checks)—e.g., NGINX or AWS Application Load Balancer routing Chicago portal API traffic across 3 Gunicorn instances so one crashed worker does not drop requests.
4. **Caching**: Storing frequently read, slow-to-compute results in fast RAM (e.g., Redis) ahead of the database—e.g., caching a user's ranked top-10 feed for 60 seconds reduced latency from `3.98 ms` (indexed SQLite) to `0.000123 ms` in our C1 experiment.
5. **Relational Database (SQL)**: ACID-compliant tabular database enforcing schemas, foreign keys, and complex joins/aggregations—e.g., PostgreSQL or SQLite storing building permits and official `community_areas` lookup tables for transactional consistency and `GROUP BY` reporting.
6. **NoSQL Database**: Non-relational stores (key-value, wide-column, document) optimized for horizontal partitioning and simple access patterns—e.g., Redis or DynamoDB storing precomputed user feed lists keyed by `user_id` (`O(1)` lookup without relational joins).
7. **Message Queue**: Asynchronous durable buffer decoupling producers from slower downstream consumers—e.g., RabbitMQ or Kafka queuing new permit submissions so ML batch scoring and email notifications retry safely without slowing down the web intake form.
8. **Replication**: Copying data across multiple database nodes (primary-replica or multi-leader) for high availability and read scaling—e.g., directing dashboard SQL queries to read replicas while writes go to a single primary node.
9. **Consistency**: Guaranteeing every read sees the most recent committed write (strong/linearizable consistency) vs. converging after brief propagation delay (eventual consistency)—e.g., a bank ledger requiring strong consistency so two withdrawals cannot spend the same balance twice.
10. **Availability**: Ensuring every non-failing node returns a non-error response—e.g., a social feed remaining readable with slightly stale likes (`5` seconds behind) during a cross-datacenter network split rather than returning `503 Service Unavailable`.

### Trade-Off Analysis: Consistency vs. Availability (CAP Theorem)
Under normal network operation, distributed data stores provide both consistency and availability; however, when a **network partition (`P`)** splits nodes so replicas cannot synchronize in real time, a system must choose between **Consistency (`CP`)** and **Availability (`AP`)**. Choosing `CP` means rejecting or blocking requests on the partitioned side until synchronization recovers, preventing stale reads or split-brain writes—essential for financial ledgers, inventory reservations, and permit ID uniqueness constraints. Choosing `AP` allows every reachable replica to keep serving reads and accepting writes using local state, reconciling conflicts asynchronously later—ideal for social media feeds, view counters, or advisory ML risk caches where serving a 30-second-old prediction beats showing an error page. Real-world platforms rarely apply one setting globally: they isolate strict `CP` relational transactions for core identity/billing records and use `AP` caches and async queues for feeds and analytics.

### Guiding Question Answered
- **Which requirement would make you pick a relational database over a key-value store, and which the reverse?** Pick a **relational database (SQL)** when you need multi-table joins (`permits JOIN community_areas`), ad-hoc aggregations (`GROUP BY` / `HAVING`), strict foreign-key integrity, and multi-row ACID transactions (e.g., financial transfers). Pick a **key-value store (NoSQL)** when access is strictly by primary key (`GET feed:{user_id}`), latency must stay sub-millisecond at high read/write QPS, schema flexibility matters, and you need effortless horizontal sharding across nodes without cross-shard joins.

### Sources
- Martin Kleppmann, *Designing Data-Intensive Applications* (O'Reilly, Chapters 1, 5, 7, 9)
- AWS Architecture Center — Caching & Database Best Practices: https://docs.aws.amazon.com/whitepapers/latest/database-caching-strategies-using-redis/welcome.html

---

## C4. A Workflow for System Design

### Write-Up: Repeatable 7-Step System Design Workflow
Rather than jumping straight to drawing boxes and picking trendy tools, reliable system design follows a disciplined sequence:
1. **Clarify Requirements & Scope (Goals vs. Non-Goals)**: Interview stakeholders to lock down exact user workflows, constraints, non-goals, and measurable non-functional SLOs (latency, availability, consistency, data retention).
2. **Back-of-the-Envelope Capacity Estimation**: Quantify read/write QPS (average & peak), payload sizes, 1-year/5-year storage, and RAM needed for hot caches; record every assumption explicitly so reviewers can challenge numbers.
3. **Define API Contracts & Core Data Model**: Specify public endpoints/events and database tables/indexes before choosing middleware.
4. **Propose High-Level Architecture**: Connect client -> load balancer -> stateless services -> database/cache/queues cleanly to satisfy the core happy path.
5. **Deep Dive & Analyze Trade-Offs**: Identify bottlenecks (hot partitions, synchronous ML inference latency, fan-out amplification), justify data-store/caching choices, and document rejected alternatives.
6. **Plan Reliability, Failure Modes & Observability**: Add idempotency keys, retries with backoff + dead-letter queues, circuit breakers, structured logs, latency/error alerts, and model-drift checks.
7. **Write & Review the Design Doc**: Circulate a concise 1–2 page RFC with open questions before coding begins.

### Artifact: One-Page Design Document — Chicago Permit Delay Triage & Notification Service

- **Context & Goal**: Surface real-time Part B `Random Forest` delay risk predictions (`Low` / `Medium` / `High`) to City of Chicago Department of Buildings intake planners and applicants upon permit submission, without slowing down the intake portal.
- **Non-Goals**: Automated permit approval/rejection decisions or replacing architectural plan review.

#### 1. Requirements & Assumptions
- **Functional**: (`1`) Accept 14 intake fields (`POST /v1/permits/triage`), return `predicted_is_delayed`, `delay_probability`, and `delay_risk_band`; (`2`) Store triage history for planner dashboards (`GET /v1/triage/summary?community_area=24`); (`3`) Recompute batch daily metrics and flag validation failures via Part A's quality gate.
- **Non-Functional**: `p95 <= 150 ms` for synchronous intake triage; `99.9%` availability; graceful degradation (`202 Accepted` async fallback or cached rule-of-thumb tier if ML worker saturates); zero raw intake data loss.
- **Capacity Numbers (Assumed & Recorded)**: Chicago H1 2024 had `16,934` permits (`~93 permits/day`, peak ~`500/hour` -> `< 1 write QPS`, plus `~20 read QPS` for planner dashboards). Scaling `100×` for multi-city usage gives `~100 peak write QPS` and `~2,000 read QPS`; at `2 KB/record`, `10M` records/year require `~20 GB/year` storage (fits comfortably on one primary PostgreSQL instance + read replica).

#### 2. API & Data Model
- `POST /v1/permits/triage` (body: 14 `INPUT_FEATURE_COLUMNS`, header: `Idempotency-Key`) -> returns `{ "prediction_id", "predicted_is_delayed", "delay_probability", "delay_risk_band", "model_version" }`.
- Relational tables (`PostgreSQL`): `triage_requests(prediction_id PK, idempotency_key UNIQUE, created_at, community_area, review_type, payload_json, delay_probability, model_version)` with composite index `(community_area, created_at DESC)` for fast neighborhood dashboards.

#### 3. High-Level Architecture & Trade-Offs
```text
Client / Portal ---> Load Balancer ---> FastAPI Triage Service ---> Redis Cache (dashboard summaries, 60s TTL)
                                             |        \
                                             v         +---> PostgreSQL (Primary + Read Replica)
                                    In-Process Joblib RF
                                    (or Queue -> Async Worker for batch CSV uploads)
```
- **Key Trade-Off (In-Process Scoring vs. Async Queue)**: For single real-time submissions (`10–25 ms` inference with preloaded `best_delay_pipeline.joblib`), running inference synchronously inside stateless API workers avoids network hops and satisfies `p95 <= 150 ms`. For bulk batch CSV uploads (`1,000+` rows like `src/predict.py`), requests enqueue onto a **Message Queue** (`202 Accepted`) so worker pools process batches asynchronously without blocking single-row API threads.
- **Failure Modes & Observability**: Duplicate retries guarded by `UNIQUE(idempotency_key)`; if Redis fails, API falls back cleanly to the PostgreSQL read replica; track p95 inference latency, 5xx error rate, daily input-schema validation pass rate (Part A Quality Gate), and weekly predicted-delay rate drift alerts.

### Guiding Questions Answered
- **What do you ask before drawing any boxes?** Who the users are, exact functional scope and explicit non-goals, expected read/write QPS and growth rate, acceptable latency (`p95`/`p99`), consistency requirements (can reads tolerate stale caches?), and failure tolerance / budget constraints.
- **Where do you record the assumptions and numbers you used?** Directly at the top of the written **Design Document** (in a dedicated *Requirements, Capacity Estimates & Assumptions* section—versioned in Git alongside `docs/`) so every teammate and reviewer can verify the math before implementation starts.

### Sources
- Malte Ubl, *Design Docs at Google*: https://www.industrialempathy.com/posts/design-docs-at-google/
- GitHub & System Design Engineering Templates (Architecture Decision Records & RFC practice): https://adr.github.io/
