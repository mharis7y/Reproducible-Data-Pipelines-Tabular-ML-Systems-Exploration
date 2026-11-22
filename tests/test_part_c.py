# Name: Muhammad Haris
# Roll Number: TRN-2026-000809
# Date: 2026-11-22
"""Tests for Part C1 SQLite feed experiment and Part C2 GitHub CI/PR artifacts."""

from __future__ import annotations

from pathlib import Path

import yaml

from src.c1_feed_experiment import run_feed_experiment

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_c1_feed_experiment_indexing_and_bonus_ranker() -> None:
    """Verify indexed feed matches unindexed results, uses index, and returns ranked top 10."""
    results = run_feed_experiment(n_users=60, n_posts=3000, n_following=15, n_repeats=3)

    chrono = results["chronological_feed"]
    assert len(chrono["top_20_post_ids"]) == 20
    assert any("USING INDEX" in line for line in chrono["indexed_query_plan"])

    ranked = results["bonus_ranked_feed_top10"]
    top_10 = ranked["top_10_posts"]
    assert len(top_10) == 10
    scores = [row["rank_score"] for row in top_10]
    assert scores == sorted(scores, reverse=True)
    assert ranked["cached_mean_ms"] >= 0.0


def test_c2_github_actions_ci_workflow_valid() -> None:
    """Verify .github/workflows/ci.yml is valid YAML triggered on PRs with ruff & pytest."""
    ci_path = REPO_ROOT / ".github" / "workflows" / "ci.yml"
    assert ci_path.exists()
    workflow = yaml.safe_load(ci_path.read_text(encoding="utf-8"))

    # Note: PyYAML parses bare YAML `on:` key as boolean True unless quoted
    triggers = workflow.get("on") or workflow.get(True)
    assert isinstance(triggers, dict)
    assert "pull_request" in triggers

    job_steps = workflow["jobs"]["lint-and-test"]["steps"]
    run_cmds = "\n".join(str(step.get("run", "")) for step in job_steps)
    assert "ruff check" in run_cmds
    assert "pytest" in run_cmds


def test_c2_pr_template_and_codeowners_exist() -> None:
    """Verify PR template, review checklist, and CODEOWNERS exist and are populated."""
    pr_tpl = REPO_ROOT / ".github" / "pull_request_template.md"
    codeowners = REPO_ROOT / ".github" / "CODEOWNERS"

    assert pr_tpl.exists()
    pr_text = pr_tpl.read_text(encoding="utf-8")
    assert "Code Review Checklist" in pr_text

    assert codeowners.exists()
    owners_text = codeowners.read_text(encoding="utf-8")
    assert "@mharis" in owners_text
