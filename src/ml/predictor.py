"""CSRF vulnerability predictor — inference engine.

Loads a trained model and produces vulnerability probabilities
for raw feature dictionaries extracted by the feature extractor.

Ref:
    - docs/proposal/PROPOSAL.md §9.4, §9.5
    - spec/Tasks.md T-321
    - spec/Requirements.md FR-303
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List

import joblib
import pandas as pd

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_MODEL_PATH = _PROJECT_ROOT / "models" / "csrf_model.pkl"
DEFAULT_COLUMNS_PATH = (
    _PROJECT_ROOT / "models" / "feature_columns.json"
)

# Categorical columns requiring one-hot encoding (must match trainer).
CATEGORICAL_COLUMNS = [
    "has_samesite_cookie",
    "http_method",
    "content_type",
    "auth_mechanism",
]


class CsrfPredictor:
    """Load a trained model and predict CSRF vulnerability.

    Usage::

        predictor = CsrfPredictor()
        prob = predictor.predict(raw_features_dict)
        # prob ∈ [0.0, 1.0] — P(vulnerable)

    Ref: T-321, FR-303
    """

    def __init__(
        self,
        model_path: Path = DEFAULT_MODEL_PATH,
        columns_path: Path = DEFAULT_COLUMNS_PATH,
    ) -> None:
        """Load model and training column order.

        Args:
            model_path: Path to the serialized `.pkl` model.
            columns_path: Path to the JSON feature columns list.
        """
        self.model = joblib.load(model_path)
        with open(columns_path, "r", encoding="utf-8") as f:
            self.columns: List[str] = json.load(f)
        logger.info(
            "Loaded model from %s (%d features)",
            model_path,
            len(self.columns),
        )

    def predict(self, features: Dict[str, Any]) -> float:
        """Predict vulnerability probability for a single exchange.

        Args:
            features: Raw feature dict from ``extract_features()``.

        Returns:
            Float in [0.0, 1.0] — probability of being vulnerable.
        """
        X = self._prepare(features)
        proba = self.model.predict_proba(X)[0, 1]
        return float(proba)

    def predict_batch(
        self, features_list: List[Dict[str, Any]]
    ) -> List[float]:
        """Predict vulnerability probabilities for many exchanges.

        Args:
            features_list: List of raw feature dicts.

        Returns:
            List of floats — one probability per feature dict.
        """
        if not features_list:
            return []

        frames = [self._prepare(f) for f in features_list]
        X = pd.concat(frames, ignore_index=True)
        probas = self.model.predict_proba(X)[:, 1]
        return [float(p) for p in probas]

    def _prepare(self, features: Dict[str, Any]) -> pd.DataFrame:
        """One-hot encode and align to training columns.

        Drops the label column if present, one-hot encodes
        categoricals, then aligns to the stored training columns.
        """
        df = pd.DataFrame([features])

        # Drop label if accidentally included.
        if "is_vulnerable" in df.columns:
            df = df.drop(columns=["is_vulnerable"])

        # One-hot encode categoricals.
        cols_present = [
            c for c in CATEGORICAL_COLUMNS if c in df.columns
        ]
        df = pd.get_dummies(df, columns=cols_present, dtype=int)

        # Align: add missing columns, remove extras, reorder.
        for col in self.columns:
            if col not in df.columns:
                df[col] = 0
        df = df[self.columns]

        return df
