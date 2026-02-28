"""Tests for the ML training pipeline.

Covers preprocessing, model training, evaluation, and serialization.

Ref:
    - src/ml/trainer.py
    - spec/Tasks.md T-311 through T-316
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from src.ml.trainer import (
    ModelMetrics,
    TARGETS,
    align_columns,
    evaluate,
    load_model,
    preprocess,
    save_model,
    train_random_forest,
    train_xgboost,
)


# ===========================================================================
# Fixtures
# ===========================================================================

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_TRAIN = _PROJECT_ROOT / "data" / "training" / "train.csv"
_VAL = _PROJECT_ROOT / "data" / "training" / "val.csv"
_TEST = _PROJECT_ROOT / "data" / "training" / "test.csv"


@pytest.fixture(scope="module")
def train_data() -> tuple:
    """Load and preprocess training data (cached per module)."""
    df = pd.read_csv(_TRAIN)
    return preprocess(df)


@pytest.fixture(scope="module")
def test_data(train_data: tuple) -> tuple:
    """Load and preprocess test data, aligned to train columns."""
    X_train, _ = train_data
    df = pd.read_csv(_TEST)
    X_test, y_test = preprocess(df)
    X_test = align_columns(X_train, X_test)
    return X_test, y_test


@pytest.fixture(scope="module")
def rf_model(train_data: tuple):
    """Trained Random Forest model (cached per module)."""
    X_train, y_train = train_data
    return train_random_forest(X_train, y_train)


@pytest.fixture(scope="module")
def xgb_model(train_data: tuple):
    """Trained XGBoost model (cached per module)."""
    X_train, y_train = train_data
    return train_xgboost(X_train, y_train)


# ===========================================================================
# Preprocessing
# ===========================================================================


class TestPreprocess:
    """Data preprocessing tests."""

    def test_preprocess_shape(self, train_data: tuple) -> None:
        """Feature matrix has expected shape after one-hot encoding."""
        X, y = train_data
        # 14 raw features - 4 categorical + one-hot expansions
        # At least 14 columns (some one-hot expansions)
        assert X.shape[0] > 0
        assert X.shape[1] >= 14  # expanded from 14 raw features

    def test_preprocess_no_label_leak(
        self, train_data: tuple
    ) -> None:
        """Label column not present in features."""
        X, _ = train_data
        assert "is_vulnerable" not in X.columns

    def test_labels_binary(self, train_data: tuple) -> None:
        """Labels are 0 or 1."""
        _, y = train_data
        assert set(y.unique()).issubset({0, 1})

    def test_align_columns_adds_missing(self) -> None:
        """align_columns adds missing columns as zeros."""
        X_train = pd.DataFrame({"a": [1], "b": [2], "c": [3]})
        X_other = pd.DataFrame({"a": [4], "b": [5]})
        aligned = align_columns(X_train, X_other)
        assert list(aligned.columns) == ["a", "b", "c"]
        assert aligned["c"].iloc[0] == 0


# ===========================================================================
# T-312: Random Forest
# ===========================================================================


class TestRandomForest:
    """Random Forest training and evaluation."""

    def test_model_trains(self, rf_model) -> None:
        """RF model is fitted."""
        assert hasattr(rf_model, "predict")
        assert hasattr(rf_model, "predict_proba")

    def test_model_predicts(
        self, rf_model, test_data: tuple
    ) -> None:
        """RF produces predictions on test set."""
        X_test, _ = test_data
        preds = rf_model.predict(X_test)
        assert len(preds) == len(X_test)

    def test_metrics_returned(
        self, rf_model, test_data: tuple
    ) -> None:
        """evaluate() returns all 5 metrics."""
        X_test, y_test = test_data
        metrics = evaluate(rf_model, X_test, y_test, "RF")
        assert isinstance(metrics, ModelMetrics)
        assert metrics.accuracy > 0
        assert metrics.precision > 0
        assert metrics.recall > 0
        assert metrics.f1 > 0
        assert metrics.auc_roc > 0


# ===========================================================================
# T-313: XGBoost
# ===========================================================================


class TestXGBoost:
    """XGBoost training and evaluation."""

    def test_model_trains(self, xgb_model) -> None:
        """XGBoost model is fitted."""
        assert hasattr(xgb_model, "predict")

    def test_model_predicts(
        self, xgb_model, test_data: tuple
    ) -> None:
        """XGBoost produces predictions on test set."""
        X_test, _ = test_data
        preds = xgb_model.predict(X_test)
        assert len(preds) == len(X_test)


# ===========================================================================
# T-314: Accuracy Targets
# ===========================================================================


class TestAccuracyTargets:
    """Verify models meet FR-304 targets."""

    def test_rf_meets_accuracy(
        self, rf_model, test_data: tuple
    ) -> None:
        X_test, y_test = test_data
        m = evaluate(rf_model, X_test, y_test, "RF")
        assert m.accuracy >= TARGETS["accuracy"], (
            f"RF accuracy {m.accuracy:.2%} < {TARGETS['accuracy']:.0%}"
        )

    def test_rf_meets_recall(
        self, rf_model, test_data: tuple
    ) -> None:
        X_test, y_test = test_data
        m = evaluate(rf_model, X_test, y_test, "RF")
        assert m.recall >= TARGETS["recall"], (
            f"RF recall {m.recall:.2%} < {TARGETS['recall']:.0%}"
        )

    def test_rf_meets_auc(
        self, rf_model, test_data: tuple
    ) -> None:
        X_test, y_test = test_data
        m = evaluate(rf_model, X_test, y_test, "RF")
        assert m.auc_roc >= TARGETS["auc_roc"], (
            f"RF AUC {m.auc_roc:.2%} < {TARGETS['auc_roc']:.0%}"
        )


# ===========================================================================
# T-315: Serialization
# ===========================================================================


class TestSerialization:
    """Model save/load round-trip."""

    def test_save_and_load(
        self, rf_model, test_data: tuple, tmp_path: Path
    ) -> None:
        """Saved model loads and produces same predictions."""
        X_test, _ = test_data
        model_path = tmp_path / "test_model.pkl"

        save_model(rf_model, model_path)
        assert model_path.exists()

        loaded = load_model(model_path)
        original_preds = rf_model.predict(X_test)
        loaded_preds = loaded.predict(X_test)

        assert list(original_preds) == list(loaded_preds)


# ===========================================================================
# ModelMetrics
# ===========================================================================


class TestModelMetrics:
    """ModelMetrics utility tests."""

    def test_meets_targets_pass(self) -> None:
        m = ModelMetrics(
            "test", 0.90, 0.85, 0.90, 0.87, 0.92
        )
        assert m.meets_targets() is True

    def test_meets_targets_fail(self) -> None:
        m = ModelMetrics(
            "test", 0.70, 0.60, 0.70, 0.65, 0.70
        )
        assert m.meets_targets() is False
