# Part C: Systems & Engineering Exploration

## C1. Optimized Query System of a Social Media Algorithm

### Write-up
_To be completed (approx. 1 page in own words): candidate retrieval, indexing, caching, fan-out on write vs. fan-out on read, ranking, and pagination._

### Artifact Reference
- SQLite experiment script & query plan output: _TBD (`sql/...`)_

### Guiding Questions
- **Why is a naive "join every followed user's posts at read time" query slow at scale?** _TBD_
- **What does an index on `(author, created_time)` change?** _TBD_
- **When would you precompute feeds instead?** _TBD_
- **How does your experiment's result support your answer?** _TBD_

### Sources
- _Cite official SQLite query-planner documentation and any other references used._

---

## C2. GitHub Actions, Branch Rules, PR Rules & Code Reviews

### Write-up
_To be completed (approx. 1 page in own words): workflows, triggers, jobs, secrets, caching, branch protection, required status checks, CODEOWNERS, PR templates, and effective code reviews._

### Artifact Reference
- CI workflow: `.github/workflows/ci.yml` (_TBD_)
- PR template & review checklist: `.github/pull_request_template.md` / _TBD_

### Guiding Questions
- **Which events should trigger the workflow?** _TBD_
- **What should block a merge?** _TBD_
- **Who should be required to review which files, and why?** _TBD_

### Sources
- _Cite official GitHub Actions and branch-protection documentation._

---

## C3. Theory of System Design

### Write-up & Trade-off Analysis
_To be completed: one-paragraph explanation of a core trade-off (e.g., consistency vs. availability, SQL vs. NoSQL, or caching staleness vs. latency)._

### Glossary (10 Terms with Concrete Examples)
1. **Requirements (Functional & Non-Functional)**: _TBD_
2. **Capacity Estimation**: _TBD_
3. **Load Balancing**: _TBD_
4. **Caching**: _TBD_
5. **Relational Database (SQL)**: _TBD_
6. **NoSQL Database (e.g., Key-Value / Document)**: _TBD_
7. **Message Queue**: _TBD_
8. **Replication**: _TBD_
9. **Consistency**: _TBD_
10. **Availability**: _TBD_

### Guiding Questions
- **Which requirement would make you pick a relational database over a key-value store, and which the reverse?** _TBD_

### Sources
- _List references used._

---

## C4. A Workflow for System Design

### Write-up: Repeatable System Design Workflow
_To be completed (approx. 1 page in own words): step-by-step sequence from clarifying requirements to reviewed design and communication._

### Artifact Reference: One-Page Design Document
_To be written by following the workflow step by step for a chosen small system._

### Guiding Questions
- **What do you ask before drawing any boxes?** _TBD_
- **Where do you record the assumptions and numbers you used?** _TBD_

### Sources
- _List engineering blogs and design-doc templates cited._
