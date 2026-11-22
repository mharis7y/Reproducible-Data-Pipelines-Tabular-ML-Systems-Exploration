# Name: Muhammad Haris
# Roll Number: TRN-2026-000809
# Date: 2026-11-22
"""Inference CLI for scoring unseen building permit CSV rows with the saved Part B pipeline."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.features import INPUT_FEATURE_COLUMNS, prepare_feature_frame

DEFAULT_MODEL_PATH = PROJECT_ROOT / "models" / "best_delay_pipeline.joblib"
DEFAULT_METADATA_PATH = PROJECT_ROOT / "models" / "model_metadata.json"
DEFAULT_OUTPUT_PATH = PROJECT_ROOT / "outputs" / "reports" / "predictions.csv"


def _risk_band(prob: float) -> str:
    """Map predicted delay probability into an operational risk tier."""
    if prob >= 0.60:
        return "High (>=0.60)"
    if prob >= 0.30:
        return "Medium (0.30-0.60)"
    return "Low (<0.30)"


def predict_from_csv(
    input_csv: Path,
    output_csv: Path = DEFAULT_OUTPUT_PATH,
    model_path: Path = DEFAULT_MODEL_PATH,
    metadata_path: Path = DEFAULT_METADATA_PATH,
) -> pd.DataFrame:
    """Load saved pipeline, validate input CSV schema, score rows, and save predictions."""
    if not input_csv.exists():
        raise FileNotFoundError(f"Input CSV not found at '{input_csv}'.")

    raw_df = pd.read_csv(input_csv, low_memory=False)
    if raw_df.empty:
        raise ValueError(f"Input CSV '{input_csv}' contains 0 rows.")

    X_input = prepare_feature_frame(raw_df)

    if not model_path.exists():
        raise FileNotFoundError(
            f"Saved pipeline not found at '{model_path}'. Run 'python src/train_part_b.py' first."
        )
    pipeline = joblib.load(model_path)

    preds = pipeline.predict(X_input).astype(int)
    probs = pipeline.predict_proba(X_input)[:, 1]

    scored_df = raw_df.copy()
    scored_df["predicted_is_delayed"] = preds
    scored_df["delay_probability"] = np.round(probs, 4)
    scored_df["delay_risk_band"] = [_risk_band(float(p)) for p in probs]

    output_csv.parent.mkdir(parents=True, exist_ok=True)
    scored_df.to_csv(output_csv, index=False)

    delayed_n = int(preds.sum())
    print(
        f"Scored {len(scored_df):,} unseen rows -> {delayed_n:,} predicted delayed "
        f"({delayed_n / len(scored_df):.1%}). Saved predictions to '{output_csv}'."
    )

    if metadata_path.exists():
        meta = json.loads(metadata_path.read_text(encoding="utf-8"))
        top_feats = meta.get("top_permutation_features", [])[:3]
        if top_feats:
            top_names = ", ".join(
                f"{item['feature']} (+{item['importance_mean']:.4f})"
                for item in top_feats
            )
            print(
                f"Top permutation importance drivers ({meta.get('winning_model')}): {top_names}."
            )
            print(
                "Interpretation: Review workflow, work type, project scope description, and "
                "permit type drive delay predictions, matching Chicago's real distinction between "
                "automated express permits and multi-step plan reviews."
            )

    return scored_df


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments for scoring unseen permit applications."""
    parser = argparse.ArgumentParser(
        description="Run batch delay prediction on unseen building permit CSV rows."
    )
    parser.add_argument("input_csv", type=Path, help="Path to CSV of unseen permit applications.")
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_PATH,
        help="Destination path for predictions CSV.",
    )
    parser.add_argument(
        "--model",
        type=Path,
        default=DEFAULT_MODEL_PATH,
        help="Path to saved joblib ML pipeline.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint for unseen permit delay inference."""
    args = parse_args(argv)
    try:
        predict_from_csv(
            input_csv=args.input_csv,
            output_csv=args.output,
            model_path=args.model,
        )
    except (FileNotFoundError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        print(f"Required columns: {INPUT_FEATURE_COLUMNS}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
