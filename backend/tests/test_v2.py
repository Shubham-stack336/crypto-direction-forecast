"""Feature pipeline v2, confidence, record summary and auto forecasts. All data is synthetic."""
import numpy as np
import pandas as pd
import pytest
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from app.background import BackgroundWorker
from app.core.cache import MemoryStore
from app.ml import features_v2
from app.ml.inference import InsufficientHistoryError, PredictionEngine
from app.repositories.model_repository import FileModelRepository
from app.services.prediction_service import PredictionService
from tests.conftest import LAST_CLOSED, FakeMarketRepository, build_market, make_prediction


def test_features_do_not_look_ahead():
    market = build_market(400)
    full = features_v2.make_features(market)
    part = features_v2.make_features(market.iloc[:300])
    pd.testing.assert_frame_equal(full.loc[part.index], part)
    assert list(full.columns) == ["timestamp", *features_v2.FEATURE_COLUMNS]


def test_flat_candles_give_finite_features():
    market = build_market(300)
    market[["open", "high", "low", "close"]] = 100.0
    market["volume"] = 0.0
    rows = features_v2.make_features(market)[features_v2.FEATURE_COLUMNS]
    assert len(rows) > 0 and np.isfinite(rows.to_numpy()).all()


@pytest.fixture
def engine_v2():
    frame = features_v2.make_features(build_market(600))
    labels = np.random.default_rng(1).choice(["DOWN", "SIDEWAYS", "UP"], size=len(frame))
    model = make_pipeline(StandardScaler(), LogisticRegression(max_iter=500)).fit(
        frame[features_v2.FEATURE_COLUMNS], labels
    )
    return PredictionEngine(model, {
        "symbol": "ALL/USDT", "timeframe": "1h", "horizon_candles": 3, "threshold": 0.003, "feature_version": "v2",
        "feature_columns": features_v2.FEATURE_COLUMNS, "trained_at_utc": "2026-01-01T00:00:00+00:00",
        "reliability": {"clear_threshold": 0.45, "bins": [{"from": 0.0, "to": 0.45, "rows": 300, "accuracy": 0.4},
                                                          {"from": 0.45, "to": 1.0, "rows": 200, "accuracy": 0.6}]},
    })


def test_engine_predicts_with_v2_and_reports_confidence(engine_v2):
    result = engine_v2.predict(build_market(), now=LAST_CLOSED + pd.Timedelta(hours=1, minutes=5))
    top = max(result.probabilities.values())
    assert result.confidence["level"] == ("clear" if top >= 0.45 else "weak")
    assert result.confidence["historical_accuracy"] == (0.6 if top >= 0.45 else 0.4)


def test_v2_needs_more_history(engine_v2):
    with pytest.raises(InsufficientHistoryError):
        engine_v2.predict(build_market(150), now=LAST_CLOSED + pd.Timedelta(hours=1, minutes=5))


def test_confidence_is_absent_for_models_without_it(make_client, live_market):
    body = make_client(FakeMarketRepository(live_market)).post("/api/v1/predictions/BTC-USDT").json()
    assert body["confidence"] is None


def test_record_summary(make_client, live_market, history_repo):
    client = make_client(FakeMarketRepository(live_market), history_repo=history_repo)
    empty = client.get("/api/v1/predictions").json()
    assert empty["checked"] == 0 and empty["baseline_correct"] == 0
    ids = [history_repo.add(make_prediction(label, at=f"2026-01-20T1{i}:00:00+00:00"))
           for i, label in enumerate(["UP", "UP", "DOWN", "UP"])]
    history_repo.save_outcomes({ids[0]: ("UP", 0.01), ids[1]: ("DOWN", -0.01), ids[2]: ("DOWN", -0.01)})
    body = client.get("/api/v1/predictions").json()
    assert (body["checked"], body["correct"], body["open"], body["baseline_correct"]) == (3, 2, 1, 2)
    assert body["by_label"][0] == {"name": "UP", "checked": 2, "correct": 1}


def test_record_summary_without_database_is_503(make_client, live_market):
    assert make_client(FakeMarketRepository(live_market)).get("/api/v1/predictions").status_code == 503


def test_market_hours(make_client, live_market):
    client = make_client(FakeMarketRepository(live_market))
    assert len(client.get("/api/v1/market/BTC-USDT?hours=168").json()["candles"]) == 168
    assert len(client.get("/api/v1/market/BTC-USDT").json()["candles"]) == 24
    assert client.get("/api/v1/market/BTC-USDT?hours=9999").status_code == 422


def test_auto_forecast_saves_and_skips_unknown_coins(model_dir, live_market, history_repo):
    service = PredictionService(FakeMarketRepository(live_market), FileModelRepository(model_dir), 500, 3,
                                history_repo=history_repo)
    worker = BackgroundWorker(MemoryStore(), lambda: None,
                              auto_forecast=lambda: service.auto_forecast(["NOPE/USDT", "BTC/USDT"]))
    worker.tick()
    worker.tick()
    assert history_repo.list("BTC/USDT", "1h", 10, 0)[1] == 1


def test_shadow_forecasts_are_recorded_but_never_shown(model_dir, tmp_path, live_market, history_repo, market):
    from tests.conftest import write_artifact

    folder = tmp_path / "challenger"
    folder.mkdir()
    write_artifact(folder, market, name="all_usdt_1h_rf", symbol="ALL/USDT", model_name="next")
    challenger = FileModelRepository(folder)
    service = PredictionService(FakeMarketRepository(live_market), FileModelRepository(model_dir, 3, challenger), 500, 3,
                                history_repo=history_repo)
    shown = service.predict("BTC/USDT", "1h").prediction
    assert not shown.model_version.startswith("next")
    assert history_repo.list("BTC/USDT", "1h", 10, 0)[1] == 1
    rows, total = history_repo.list("BTC/USDT", "1h", 10, 0, include_shadow=True)
    assert total == 2 and any(r.model_version.startswith("shadow-next") for r in rows)
    history_repo.save_outcomes({r.id: ("UP", 0.01) for r in rows})
    summary = history_repo.outcome_summary()
    assert summary["checked"] == 1 and len(summary["by_model"]) == 2
    assert service.track_record("BTC/USDT", "1h").checked == 1

    serving = FileModelRepository(model_dir, 3, challenger, serve_challenger=True)
    assert serving.get_engine("BTC/USDT", "1h").model_version.startswith("next")
    assert serving.get_challenger("BTC/USDT", "1h") is None


def test_reliability_file_of_another_model_is_ignored(model_dir):
    import json

    side = model_dir / "btc_usdt_1h_rf.reliability.json"
    side.write_text(json.dumps({"model_sha256": "other", "clear_threshold": 0.1, "bins": []}))
    assert FileModelRepository(model_dir).get_engine("BTC/USDT", "1h").reliability is None
    sha = FileModelRepository(model_dir).get_engine("BTC/USDT", "1h").sha256
    side.write_text(json.dumps({"model_sha256": sha, "clear_threshold": 0.1, "bins": []}))
    assert FileModelRepository(model_dir).get_engine("BTC/USDT", "1h").reliability["clear_threshold"] == 0.1
