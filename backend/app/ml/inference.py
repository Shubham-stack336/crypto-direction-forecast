"""Reusable inference engine. Independent of FastAPI and any database."""
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from app.ml.features import FEATURE_COLUMNS, make_features
from app.ml.validation import validate

FEATURE_BUILDERS = {"v1": make_features}
MIN_HISTORY_CANDLES = 100
REQUIRED_COLUMNS = {"timestamp", "open", "high", "low", "close", "volume"}
DISCLAIMER = (
    "Probabilities are model estimates, not guarantees. "
    "This is not financial advice."
)


class PredictionError(Exception):
    pass


class ModelNotFoundError(PredictionError):
    pass


class IncompatibleModelError(PredictionError):
    pass


class InvalidInputError(PredictionError):
    pass


class InsufficientHistoryError(PredictionError):
    pass


class StaleDataError(PredictionError):
    pass


@dataclass(frozen=True)
class Prediction:
    label: str
    probabilities: dict
    symbol: str
    timeframe: str
    horizon_candles: int
    prediction_time_utc: str
    latest_candle_utc: str
    model_version: str
    feature_version: str
    status: str
    data_quality: dict
    disclaimer: str


class PredictionEngine:
    def __init__(self, model, metadata: dict, max_staleness_candles: int | None = 3):
        self.model = model
        self.metadata = metadata
        self.max_staleness_candles = max_staleness_candles

    @classmethod
    def load(cls, path, max_staleness_candles: int | None = 3) -> "PredictionEngine":
        path = Path(path)
        if not path.exists():
            raise ModelNotFoundError(f"Model file not found: {path}")

        try:
            artifact = joblib.load(path)
        except Exception as err:
            raise IncompatibleModelError(f"Could not read model file: {err}") from err

        if not isinstance(artifact, dict) or "model" not in artifact or "metadata" not in artifact:
            raise IncompatibleModelError("Model file has an unexpected structure")

        model, metadata = artifact["model"], artifact["metadata"]
        if not hasattr(model, "predict_proba"):
            raise IncompatibleModelError("Model cannot produce probabilities")
        if metadata.get("feature_version") not in FEATURE_BUILDERS:
            raise IncompatibleModelError(f"Unknown feature version: {metadata.get('feature_version')}")
        if metadata.get("feature_columns") != FEATURE_COLUMNS:
            raise IncompatibleModelError("Model feature names/order differ from the current pipeline")

        return cls(model, metadata, max_staleness_candles)

    @property
    def model_version(self) -> str:
        trained_day = self.metadata["trained_at_utc"][:10]
        return f"{self.metadata['feature_version']}-{trained_day}"

    def predict(self, candles, now=None) -> Prediction:
        now = now or datetime.now(timezone.utc)

        if not isinstance(candles, pd.DataFrame) or not REQUIRED_COLUMNS.issubset(candles.columns):
            raise InvalidInputError(f"Input must be a DataFrame with columns {sorted(REQUIRED_COLUMNS)}")

        df = candles.copy()
        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
        df, problems = validate(df, min_rows=1)
        if problems:
            raise InvalidInputError("; ".join(problems))

        candle_length = pd.Timedelta(self.metadata["timeframe"])
        dropped_incomplete = False
        if df["timestamp"].iloc[-1] + candle_length > now:
            df = df.iloc[:-1].reset_index(drop=True)
            dropped_incomplete = True

        if len(df) < MIN_HISTORY_CANDLES:
            raise InsufficientHistoryError(
                f"Need at least {MIN_HISTORY_CANDLES} closed candles, got {len(df)}"
            )

        latest_ts = df["timestamp"].iloc[-1]
        age = now - (latest_ts + candle_length)
        if self.max_staleness_candles is not None and age > self.max_staleness_candles * candle_length:
            raise StaleDataError(f"Latest closed candle is {age} old")

        builder = FEATURE_BUILDERS[self.metadata["feature_version"]]
        features = builder(df)
        if features.empty or features["timestamp"].iloc[-1] != latest_ts:
            raise InsufficientHistoryError("Could not compute features for the latest candle")

        columns = self.metadata["feature_columns"]
        X = features[columns].iloc[[-1]]
        if not np.isfinite(X.to_numpy(dtype=float)).all():
            raise InvalidInputError("Features contain non-finite values")

        proba = self.model.predict_proba(X)[0]
        classes = [str(c) for c in self.model.classes_]

        return Prediction(
            label=classes[int(np.argmax(proba))],
            probabilities={c: round(float(p), 4) for c, p in zip(classes, proba)},
            symbol=self.metadata["symbol"],
            timeframe=self.metadata["timeframe"],
            horizon_candles=self.metadata["horizon_candles"],
            prediction_time_utc=now.isoformat(),
            latest_candle_utc=latest_ts.isoformat(),
            model_version=self.model_version,
            feature_version=self.metadata["feature_version"],
            status="ok",
            data_quality={
                "rows_used": len(df),
                "dropped_incomplete_candle": dropped_incomplete,
                "data_age_minutes": round(age.total_seconds() / 60, 1),
            },
            disclaimer=DISCLAIMER,
        )
