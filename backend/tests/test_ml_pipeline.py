"""Unit tests for Phase 2, 3, and 4: Feature Engineering, Time-Split, Models, and Evaluation."""

import numpy as np
import pandas as pd
import pytest

from app.services.feature_service import FEATURE_NAMES, FeatureService
from app.services.model_service import ModelService, NaiveBaselineClassifier


@pytest.fixture
def synthetic_price_df():
    """Generate 200 days of deterministic price data."""
    dates = pd.date_range(start="2024-01-01", periods=200, freq="D")
    np.random.seed(42)
    # Drift + noise
    returns = np.random.normal(0.001, 0.02, 200)
    prices = 50000.0 * np.exp(np.cumsum(returns))
    volumes = np.random.uniform(1e8, 5e8, 200)
    
    df = pd.DataFrame(
        {
            "open": prices * 0.995,
            "high": prices * 1.015,
            "low": prices * 0.985,
            "close": prices,
            "volume": volumes,
        },
        index=dates,
    )
    df.index.name = "date"
    return df


class TestFeatureService:
    def test_feature_generation_columns(self, synthetic_price_df):
        service = FeatureService()
        feats = service.generate_features(synthetic_price_df)
        assert list(feats.columns) == FEATURE_NAMES
        assert len(feats) == len(synthetic_price_df)

    def test_rsi_bounds(self, synthetic_price_df):
        service = FeatureService()
        rsi = service.calculate_rsi(synthetic_price_df["close"])
        valid_rsi = rsi.dropna()
        assert (valid_rsi >= 0.0).all()
        assert (valid_rsi <= 100.0).all()

    def test_target_has_no_lookahead_leakage(self, synthetic_price_df):
        service = FeatureService()
        dataset = service.build_dataset(synthetic_price_df)
        
        # Verify target definition: target at t == 1 iff close at t+1 > close at t
        raw_close = synthetic_price_df["close"]
        for i in range(len(dataset) - 1):
            date_t = dataset.index[i]
            # Next calendar/business day in raw df
            loc_in_raw = raw_close.index.get_loc(date_t)
            next_close = raw_close.iloc[loc_in_raw + 1]
            curr_close = raw_close.iloc[loc_in_raw]
            expected_target = 1 if next_close > curr_close else 0
            assert dataset["target"].iloc[i] == expected_target

    def test_inference_features_single_row(self, synthetic_price_df):
        service = FeatureService()
        latest_feats, meta = service.get_latest_inference_features(synthetic_price_df)
        assert len(latest_feats) == 1
        assert list(latest_feats.columns) == FEATURE_NAMES
        assert "rsi_14" in meta
        assert "close" in meta


class TestModelService:
    def test_time_based_split_chronological(self, synthetic_price_df):
        service = FeatureService()
        dataset = service.build_dataset(synthetic_price_df)
        
        model_svc = ModelService()
        train_df, test_df = model_svc.time_based_split(dataset, train_ratio=0.8)
        
        assert len(train_df) + len(test_df) == len(dataset)
        # Strict temporal order: max train date < min test date
        assert train_df.index.max() < test_df.index.min()
        # No overlapping dates
        assert set(train_df.index).isdisjoint(set(test_df.index))

    def test_naive_baseline_majority_prediction(self):
        clf = NaiveBaselineClassifier()
        # Train with 80% UP (1) and 20% DOWN (0)
        y_train = np.array([1, 1, 1, 1, 0])
        clf.fit(np.zeros((5, 2)), y_train)
        
        preds = clf.predict(np.zeros((3, 2)))
        assert (preds == 1).all()
        
        probs = clf.predict_proba(np.zeros((2, 2)))
        assert probs[0, 1] == 1.0
        assert probs[0, 0] == 0.0

    def test_train_and_compare_all_models(self, tmp_path):
        model_svc = ModelService(artifacts_dir=tmp_path)
        summary = model_svc.train_and_compare_all("BTC-USD", train_ratio=0.8)
        
        assert "candidate_model" in summary
        assert "naive_baseline" in summary["results"]
        assert "logistic_regression" in summary["results"]
        assert "random_forest" in summary["results"]
        assert "gradient_boosting" in summary["results"]
        assert "honest_assessment" in summary
        assert summary["test_samples"] > 0
        
        # Verify artifact was saved
        saved_files = list(tmp_path.glob("*.joblib"))
        assert len(saved_files) >= 1

    def test_predict_next_day(self, tmp_path):
        model_svc = ModelService(artifacts_dir=tmp_path)
        forecast = model_svc.predict_next_day("BTC-USD")
        
        assert forecast["forecast_direction"] in ["UP", "DOWN"]
        assert "probabilities" in forecast
        assert "UP" in forecast["probabilities"]
        assert "DOWN" in forecast["probabilities"]
        assert 0.0 <= forecast["confidence"] <= 1.0
        assert "honest_assessment" in forecast
