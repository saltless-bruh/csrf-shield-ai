"""ML training pipeline for CSRF vulnerability classifier.

Trains Random Forest (primary) and XGBoost (secondary) classifiers
on the prepared training data.  Evaluates against FR-304 targets
and serializes the best model.

Ref:
    - docs/proposal/PROPOSAL.md §9.4, §9.5
    - spec/Tasks.md T-311 through T-316
    - spec/Requirements.md FR-303, FR-304, FR-308

Usage:
    python -m src.ml.trainer
    python -m src.ml.trainer --train data/training/train.csv
"""

from __future__ import annotations

import argparse
import json
import logging
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    accuracy_score,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from xgboost import XGBClassifier

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

# Default paths.
DEFAULT_TRAIN = _PROJECT_ROOT / "data" / "training" / "train.csv"
DEFAULT_VAL = _PROJECT_ROOT / "data" / "training" / "val.csv"
DEFAULT_TEST = _PROJECT_ROOT / "data" / "training" / "test.csv"
DEFAULT_MODEL_DIR = _PROJECT_ROOT / "models"

LABEL_COLUMN = "is_vulnerable"

# Categorical columns requiring one-hot encoding.
CATEGORICAL_COLUMNS = [
    "has_samesite_cookie",
    "http_method",
    "content_type",
    "auth_mechanism",
]

# FR-304 performance targets.
TARGETS = {
    "accuracy": 0.80,
    "precision": 0.75,
    "recall": 0.85,
    "f1": 0.80,
    "auc_roc": 0.85,
}


# ------------------------------------------------------------------
# Data structures
# ------------------------------------------------------------------


@dataclass
class ModelMetrics:
    """Evaluation metrics for a trained model."""

    model_name: str
    accuracy: float
    precision: float
    recall: float
    f1: float
    auc_roc: float

    def meets_targets(self) -> bool:
        """Check if all FR-304 targets are met."""
        return (
            self.accuracy >= TARGETS["accuracy"]
            and self.precision >= TARGETS["precision"]
            and self.recall >= TARGETS["recall"]
            and self.f1 >= TARGETS["f1"]
            and self.auc_roc >= TARGETS["auc_roc"]
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict for JSON serialization."""
        return asdict(self)


@dataclass
class TrainingResult:
    """Result of the full training pipeline."""

    best_model_name: str
    best_model_path: str
    metrics: List[ModelMetrics]


# ------------------------------------------------------------------
# Preprocessing
# ------------------------------------------------------------------


def load_csv(path: Path) -> pd.DataFrame:
    """Load a CSV dataset."""
    return pd.read_csv(path)


def preprocess(df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.Series]:
    """Preprocess a DataFrame: one-hot encode categoricals.

    Args:
        df: Raw DataFrame with 14 features + label.

    Returns:
        Tuple of (X feature matrix, y label series).
    """
    y = df[LABEL_COLUMN].astype(int)
    X = df.drop(columns=[LABEL_COLUMN])

    # One-hot encode categorical columns.
    X = pd.get_dummies(X, columns=CATEGORICAL_COLUMNS, dtype=int)

    return X, y


def align_columns(
    X_train: pd.DataFrame,
    X_other: pd.DataFrame,
) -> pd.DataFrame:
    """Align columns of X_other to match X_train.

    Adds missing columns as 0, removes extra columns, reorders.
    """
    missing = set(X_train.columns) - set(X_other.columns)
    for col in missing:
        X_other[col] = 0

    return X_other[X_train.columns]


# ------------------------------------------------------------------
# Training
# ------------------------------------------------------------------


def train_random_forest(
    X_train: pd.DataFrame,
    y_train: pd.Series,
    n_estimators: int = 200,
    seed: int = 42,
) -> RandomForestClassifier:
    """Train a Random Forest classifier (T-312).

    Args:
        X_train: Feature matrix.
        y_train: Labels.
        n_estimators: Number of trees.
        seed: Random seed.

    Returns:
        Trained RandomForestClassifier.
    """
    model = RandomForestClassifier(
        n_estimators=n_estimators,
        random_state=seed,
        n_jobs=-1,
        class_weight="balanced",
    )
    model.fit(X_train, y_train)
    logger.info(
        "Trained Random Forest (%d trees)", n_estimators
    )
    return model


def train_xgboost(
    X_train: pd.DataFrame,
    y_train: pd.Series,
    n_estimators: int = 200,
    seed: int = 42,
) -> XGBClassifier:
    """Train an XGBoost classifier (T-313, FR-308).

    Args:
        X_train: Feature matrix.
        y_train: Labels.
        n_estimators: Number of boosting rounds.
        seed: Random seed.

    Returns:
        Trained XGBClassifier.
    """
    model = XGBClassifier(
        n_estimators=n_estimators,
        random_state=seed,
        eval_metric="logloss",
        use_label_encoder=False,
        verbosity=0,
    )
    model.fit(X_train, y_train)
    logger.info(
        "Trained XGBoost (%d rounds)", n_estimators
    )
    return model


# ------------------------------------------------------------------
# Evaluation (T-314)
# ------------------------------------------------------------------


def evaluate(
    model: Any,
    X_test: pd.DataFrame,
    y_test: pd.Series,
    model_name: str,
) -> ModelMetrics:
    """Evaluate a model against FR-304 targets.

    Args:
        model: Trained classifier with predict/predict_proba.
        X_test: Test feature matrix.
        y_test: Test labels.
        model_name: Name for the metrics report.

    Returns:
        ModelMetrics with all 5 evaluation metrics.
    """
    y_pred = model.predict(X_test)
    y_prob = model.predict_proba(X_test)[:, 1]

    metrics = ModelMetrics(
        model_name=model_name,
        accuracy=round(accuracy_score(y_test, y_pred), 4),
        precision=round(
            precision_score(y_test, y_pred, zero_division=0), 4
        ),
        recall=round(
            recall_score(y_test, y_pred, zero_division=0), 4
        ),
        f1=round(f1_score(y_test, y_pred, zero_division=0), 4),
        auc_roc=round(roc_auc_score(y_test, y_prob), 4),
    )

    logger.info(
        "%s — acc=%.2f prec=%.2f rec=%.2f f1=%.2f auc=%.2f",
        model_name,
        metrics.accuracy,
        metrics.precision,
        metrics.recall,
        metrics.f1,
        metrics.auc_roc,
    )
    return metrics


# ------------------------------------------------------------------
# Serialization (T-315)
# ------------------------------------------------------------------


def save_model(model: Any, path: Path) -> None:
    """Serialize model to disk via joblib."""
    path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, path)
    logger.info("Saved model to %s", path)


def load_model(path: Path) -> Any:
    """Load a serialized model from disk."""
    return joblib.load(path)


# ------------------------------------------------------------------
# Full Pipeline
# ------------------------------------------------------------------


class CsrfTrainer:
    """Orchestrates the full ML training pipeline.

    Usage::

        trainer = CsrfTrainer()
        result = trainer.run()
        print(result.best_model_name)
    """

    def __init__(
        self,
        train_path: Path = DEFAULT_TRAIN,
        val_path: Path = DEFAULT_VAL,
        test_path: Path = DEFAULT_TEST,
        model_dir: Path = DEFAULT_MODEL_DIR,
    ) -> None:
        self.train_path = train_path
        self.val_path = val_path
        self.test_path = test_path
        self.model_dir = model_dir

    def run(self) -> TrainingResult:
        """Execute the full training pipeline.

        1. Load and preprocess data
        2. Train Random Forest + XGBoost
        3. Evaluate both on test set
        4. Save best model
        5. Return results

        Returns:
            TrainingResult with best model info and all metrics.
        """
        # Load data
        train_df = load_csv(self.train_path)
        val_df = load_csv(self.val_path)
        test_df = load_csv(self.test_path)

        # Preprocess
        X_train, y_train = preprocess(train_df)
        X_val, y_val = preprocess(val_df)
        X_test, y_test = preprocess(test_df)

        # Align columns
        X_val = align_columns(X_train, X_val)
        X_test = align_columns(X_train, X_test)

        # Train models
        rf_model = train_random_forest(X_train, y_train)
        xgb_model = train_xgboost(X_train, y_train)

        # Evaluate on test set
        rf_metrics = evaluate(
            rf_model, X_test, y_test, "Random Forest"
        )
        xgb_metrics = evaluate(
            xgb_model, X_test, y_test, "XGBoost"
        )

        all_metrics = [rf_metrics, xgb_metrics]

        # Select best model by F1
        best = max(all_metrics, key=lambda m: m.f1)
        best_model = (
            rf_model if best.model_name == "Random Forest"
            else xgb_model
        )

        # Save best model + feature columns
        model_path = self.model_dir / "csrf_model.pkl"
        save_model(best_model, model_path)

        # Save feature column names for inference alignment
        columns_path = self.model_dir / "feature_columns.json"
        columns_path.parent.mkdir(parents=True, exist_ok=True)
        with open(columns_path, "w") as f:
            json.dump(list(X_train.columns), f)

        # Print summary
        self._print_summary(all_metrics, best)

        return TrainingResult(
            best_model_name=best.model_name,
            best_model_path=str(model_path),
            metrics=all_metrics,
        )

    def _print_summary(
        self,
        metrics: List[ModelMetrics],
        best: ModelMetrics,
    ) -> None:
        """Print training summary."""
        print(f"\n{'=' * 55}")
        print("MODEL TRAINING RESULTS")
        print(f"{'=' * 55}")
        print(
            f"{'Model':<16} {'Acc':>6} {'Prec':>6} "
            f"{'Rec':>6} {'F1':>6} {'AUC':>6} {'Target':>8}"
        )
        print("-" * 55)
        for m in metrics:
            status = "✓ PASS" if m.meets_targets() else "✗ FAIL"
            print(
                f"{m.model_name:<16} "
                f"{m.accuracy:>6.2%} {m.precision:>6.2%} "
                f"{m.recall:>6.2%} {m.f1:>6.2%} "
                f"{m.auc_roc:>6.2%} {status:>8}"
            )
        print("-" * 55)
        print(f"Best model: {best.model_name} (by F1)")
        print(f"{'=' * 55}")


# ------------------------------------------------------------------
# CLI
# ------------------------------------------------------------------


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Train CSRF vulnerability classifier",
    )
    parser.add_argument(
        "--train", type=Path, default=DEFAULT_TRAIN,
    )
    parser.add_argument(
        "--val", type=Path, default=DEFAULT_VAL,
    )
    parser.add_argument(
        "--test", type=Path, default=DEFAULT_TEST,
    )
    parser.add_argument(
        "--model-dir", type=Path, default=DEFAULT_MODEL_DIR,
    )
    args = parser.parse_args()

    trainer = CsrfTrainer(
        train_path=args.train,
        val_path=args.val,
        test_path=args.test,
        model_dir=args.model_dir,
    )
    result = trainer.run()

    # Generate metrics report (T-316)
    report_path = (
        _PROJECT_ROOT / "docs" / "reports" / "model_performance.md"
    )
    _write_metrics_report(result, report_path)


def _write_metrics_report(
    result: TrainingResult, path: Path
) -> None:
    """Generate markdown metrics report (T-316)."""
    path.parent.mkdir(parents=True, exist_ok=True)

    lines = [
        "# Model Performance Report\n",
        "",
        f"> Best model: **{result.best_model_name}**\n",
        "",
        "## Metrics Comparison\n",
        "",
        "| Metric | Target | "
        + " | ".join(m.model_name for m in result.metrics)
        + " |",
        "| --- | --- | "
        + " | ".join("---" for _ in result.metrics)
        + " |",
    ]

    for metric_name, target in TARGETS.items():
        row = f"| {metric_name.replace('_', ' ').title()} | ≥{target:.0%} |"
        for m in result.metrics:
            val = getattr(m, metric_name)
            status = "✅" if val >= target else "❌"
            row += f" {val:.2%} {status} |"
        lines.append(row)

    lines.extend([
        "",
        "## Verdict\n",
        "",
    ])

    for m in result.metrics:
        status = "**PASS** ✅" if m.meets_targets() else "**FAIL** ❌"
        lines.append(f"- {m.model_name}: {status}")

    lines.extend([
        "",
        f"\nSerialized to: `{result.best_model_path}`",
    ])

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"\n✓ Metrics report written to {path}")


if __name__ == "__main__":
    main()
