"""Model & Evaluation Service Layer.

Implements strict time-based splits, naive baseline, Logistic Regression,
Random Forest, and Gradient Boosted Trees with honest evaluation and inference.
"""

from datetime import datetime, timezone
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Tuple

import joblib
import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, ClassifierMixin, clone
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    f1_score,
    precision_score,
    recall_score,
)
from sklearn.model_selection import TimeSeriesSplit, cross_val_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from app.services.data_service import DataService
from app.services.feature_service import FEATURE_NAMES, FeatureService

logger = logging.getLogger("app.service.models")
ARTIFACTS_DIR = Path(__file__).resolve().parents[2] / "artifacts"


class NaiveBaselineClassifier(BaseEstimator, ClassifierMixin):
    """Naive Baseline that always predicts the majority class observed in training."""

    def __init__(self):
        self.majority_class_ = 1  # Default to UP
        self.classes_ = np.array([0, 1])

    def fit(self, X, y):
        counts = pd.Series(y).value_counts()
        self.majority_class_ = int(counts.index[0])
        return self

    def predict(self, X):
        n = len(X) if hasattr(X, "__len__") else X.shape[0]
        return np.full(n, self.majority_class_)

    def predict_proba(self, X):
        n = len(X) if hasattr(X, "__len__") else X.shape[0]
        probs = np.zeros((n, 2))
        probs[:, self.majority_class_] = 1.0
        return probs


class ModelService:
    def __init__(
        self,
        data_service: DataService | None = None,
        feature_service: FeatureService | None = None,
        artifacts_dir: Path | None = None,
    ):
        self.data_service = data_service or DataService()
        self.feature_service = feature_service or FeatureService()
        self.artifacts_dir = artifacts_dir or ARTIFACTS_DIR
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)

    def time_based_split(
        self, df: pd.DataFrame, train_ratio: float = 0.8
    ) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """Split dataset strictly chronologically (earlier -> train, recent -> test).

        Zero shuffling to avoid future lookahead leakage.
        """
        n = len(df)
        split_idx = int(n * train_ratio)
        train_df = df.iloc[:split_idx].copy()
        test_df = df.iloc[split_idx:].copy()
        return train_df, test_df

    def evaluate_model(
        self, model: BaseEstimator, X_test: pd.DataFrame, y_test: pd.Series
    ) -> Dict[str, float]:
        """Compute comprehensive performance metrics on unseen test data."""
        y_pred = model.predict(X_test)

        acc = float(accuracy_score(y_test, y_pred))
        bal_acc = float(balanced_accuracy_score(y_test, y_pred))
        macro_f1 = float(f1_score(y_test, y_pred, average="macro", zero_division=0))
        precision = float(precision_score(y_test, y_pred, average="binary", zero_division=0))
        recall = float(recall_score(y_test, y_pred, average="binary", zero_division=0))

        # Direction-specific hit rate
        up_mask = y_test == 1
        down_mask = y_test == 0
        up_acc = float(accuracy_score(y_test[up_mask], y_pred[up_mask])) if up_mask.sum() > 0 else 0.0
        down_acc = float(accuracy_score(y_test[down_mask], y_pred[down_mask])) if down_mask.sum() > 0 else 0.0

        return {
            "accuracy": round(acc, 4),
            "balanced_accuracy": round(bal_acc, 4),
            "macro_f1": round(macro_f1, 4),
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "up_accuracy": round(up_acc, 4),
            "down_accuracy": round(down_acc, 4),
        }

    def train_and_compare_all(
        self, symbol: str, train_ratio: float = 0.8
    ) -> Dict[str, Any]:
        """Train Naive, Logistic Regression, Random Forest, and Gradient Boosting.

        Compare honestly against baseline and save candidate model artifacts.
        """
        raw_df = self.data_service.get_data(symbol)
        dataset = self.feature_service.build_dataset(raw_df)

        train_df, test_df = self.time_based_split(dataset, train_ratio=train_ratio)
        X_train, y_train = train_df[FEATURE_NAMES], train_df["target"]
        X_test, y_test = test_df[FEATURE_NAMES], test_df["target"]

        test_start = str(test_df.index[0].date()) if hasattr(test_df.index[0], "date") else str(test_df.index[0])
        test_end = str(test_df.index[-1].date()) if hasattr(test_df.index[-1], "date") else str(test_df.index[-1])

        # Model Definitions
        models: Dict[str, BaseEstimator] = {
            "naive_baseline": NaiveBaselineClassifier(),
            "logistic_regression": Pipeline([
                ("scaler", StandardScaler()),
                ("clf", LogisticRegression(random_state=42, max_iter=500, C=0.5)),
            ]),
            "random_forest": RandomForestClassifier(
                n_estimators=100, max_depth=4, min_samples_leaf=5, random_state=42, n_jobs=-1
            ),
            "gradient_boosting": HistGradientBoostingClassifier(
                max_iter=100, max_depth=3, random_state=42
            ),
        }

        results = {}
        trained_models = {}

        for name, clf in models.items():
            clf.fit(X_train, y_train)
            metrics = self.evaluate_model(clf, X_test, y_test)
            results[name] = metrics
            trained_models[name] = clf

        # Compare against baseline
        baseline_acc = results["naive_baseline"]["accuracy"]
        baseline_bal = results["naive_baseline"]["balanced_accuracy"]

        # Select the candidate on time-ordered folds of the training data; the test set only reports
        ml_names = ["random_forest", "gradient_boosting", "logistic_regression"]
        folds = TimeSeriesSplit(n_splits=4)
        validation = {
            m: cross_val_score(clone(models[m]), X_train, y_train, cv=folds, scoring="balanced_accuracy").mean()
            for m in ml_names
        }
        best_ml = max(ml_names, key=validation.get)
        candidate_metrics = results[best_ml]

        edge = round(candidate_metrics["accuracy"] - baseline_acc, 4)
        edge_bal = round(candidate_metrics["balanced_accuracy"] - baseline_bal, 4)
        beats_baseline = bool(candidate_metrics["balanced_accuracy"] > baseline_bal)

        # Honest assessment report
        if beats_baseline and edge_bal >= 0.02:
            honest_note = (
                f"Candidate ({best_ml}) beat naive baseline by +{edge_bal * 100:.1f}% balanced accuracy. "
                "However, market noise is significant and execution slippage/fees must be considered."
            )
        elif beats_baseline:
            honest_note = (
                f"Candidate ({best_ml}) slightly beat naive baseline by +{edge_bal * 100:.1f}%. "
                "Edge is narrow; market exhibits heavy random-walk behavior."
            )
        else:
            honest_note = (
                f"Candidate ({best_ml}) did NOT beat naive baseline in balanced accuracy. "
                "Reported honestly: ML could not outperform simple majority class on this period."
            )

        # Persist candidate model
        sanitized = symbol.replace("/", "_").replace("-", "_").lower()
        model_path = self.artifacts_dir / f"{sanitized}_candidate.joblib"
        metrics_path = self.artifacts_dir / f"{sanitized}_metrics.json"

        joblib.dump(trained_models[best_ml], model_path)

        summary = {
            "symbol": symbol,
            "trained_at_utc": datetime.now(timezone.utc).isoformat(),
            "candidate_model": best_ml,
            "beats_baseline": beats_baseline,
            "edge_over_baseline_acc": edge,
            "edge_over_baseline_bal_acc": edge_bal,
            "honest_assessment": honest_note,
            "train_samples": len(train_df),
            "test_samples": len(test_df),
            "test_period": [test_start, test_end],
            "results": results,
            "feature_names": FEATURE_NAMES,
        }

        with open(metrics_path, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2)

        return summary

    def predict_next_day(self, symbol: str) -> Dict[str, Any]:
        """Generate next-day direction forecast using stored or auto-trained candidate."""
        sanitized = symbol.replace("/", "_").replace("-", "_").lower()
        model_path = self.artifacts_dir / f"{sanitized}_candidate.joblib"
        metrics_path = self.artifacts_dir / f"{sanitized}_metrics.json"

        if not model_path.exists() or not metrics_path.exists():
            logger.info(f"No existing candidate model for {symbol}. Training now...")
            self.train_and_compare_all(symbol)

        model = joblib.load(model_path)
        with open(metrics_path, "r", encoding="utf-8") as f:
            metrics_summary = json.load(f)

        raw_df = self.data_service.get_data(symbol)
        latest_features, meta = self.feature_service.get_latest_inference_features(raw_df)

        pred_class = int(model.predict(latest_features)[0])
        pred_label = "UP" if pred_class == 1 else "DOWN"

        probs = model.predict_proba(latest_features)[0]
        prob_dict = {"DOWN": round(float(probs[0]), 4), "UP": round(float(probs[1]), 4)}

        return {
            "symbol": symbol,
            "prediction_time_utc": datetime.now(timezone.utc).isoformat(),
            "forecast_direction": pred_label,
            "probabilities": prob_dict,
            "confidence": round(float(max(probs)), 4),
            "candidate_model": metrics_summary["candidate_model"],
            "model_metrics": metrics_summary["results"].get(metrics_summary["candidate_model"], {}),
            "latest_candle": meta,
            "honest_assessment": metrics_summary["honest_assessment"],
            "disclaimer": "Educational demonstration only. Not financial or trading advice.",
        }
