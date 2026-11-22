## Summary

<!-- Describe what this PR changes and why it is needed. -->

## Type of Change

- [ ] Part A — Data cleaning / validation / SQL / visualization
- [ ] Part B — Feature engineering / model training / inference
- [ ] Tests or CI configuration
- [ ] Documentation update

## Verification Commands Run

```bash
ruff check src/ tests/
pytest -v
```

<!-- Paste key test/pipeline output or attach relevant metrics below. -->

## Author Self-Check

- [ ] Every new `.py` file starts with the required comment header (name, roll number, date).
- [ ] Raw data in `data/raw/` has not been modified or overwritten.
- [ ] No data leakage (split happens before fitting transformers; post-intake columns excluded from Part B features).
- [ ] All functions include clear docstrings and corresponding unit tests.
- [ ] Documentation (`README.md`, `docs/schema.md`, `docs/assumptions.md`) is updated if behavior changed.

## Code Review Checklist (For Reviewer)

- [ ] **Correctness & Edge Cases**: Are nulls, empty inputs, and malformed formats handled cleanly and loudly?
- [ ] **Reproducibility**: Can the changes run end-to-end from a fresh clone without hidden notebook state?
- [ ] **Readability**: Are names descriptive, helpers modular, and non-obvious decisions commented ("why", not "what")?
- [ ] **CI Status**: Did the `Ruff Lint & Pytest Suite` GitHub Actions check pass on this PR?
