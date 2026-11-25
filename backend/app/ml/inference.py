"""Reusable inference engine. Independent of FastAPI and any database."""
import hashlib
import io
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from app.ml import features, features_v2
from app.ml.validation import validate

FEATURE_PIPELINES = {"v1": features, "v2": features_v2}
MIN_HISTORY_CANDLES = {"v1": 100, "v2": 200}
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
    threshold: float | None = None
    confidence: dict | None = None


class PredictionEngine:
    def __init__(self, model, metadata: dict, max_staleness_candles: int | None = 3, artifact_id: str = ""):
        self.model = model
        self.sha256 = ""
        self.metadata = metadata
        self.max_staleness_candles = max_staleness_candles
        self.artifact_id = artifact_id
        self.reliability = metadata.get("reliability")

    @classmethod
    def load(
        cls, path, max_staleness_candles: int | None = 3, expected_sha256: str | None = None
    ) -> "PredictionEngine":
        path = Path(path)
        if not path.exists():
            raise ModelNotFoundError(f"Model file not found: {path}")

        try:
            data = path.read_bytes()
        except OSError as err:
            raise IncompatibleModelError(f"Could not read model file: {err}") from err
        digest = hashlib.sha256(data).hexdigest()
        # joblib files can run code when loaded, so check the file before opening it.
        if expected_sha256 is not None and digest != expected_sha256:
            raise IncompatibleModelError(f"Checksum mismatch for {path.name}")

        try:
            artifact = joblib.load(io.BytesIO(data))
        except Exception as err:
            raise IncompatibleModelError(f"Could not read model file: {err}") from err

        if not isinstance(artifact, dict) or "model" not in artifact or "metadata" not in artifact:
            raise IncompatibleModelError("Model file has an unexpected structure")

        model, metadata = artifact["model"], artifact["metadata"]
        if not hasattr(model, "predict_proba"):
            raise IncompatibleModelError("Model cannot produce probabilities")
        if metadata.get("feature_version") not in FEATURE_PIPELINES:
            raise IncompatibleModelError(f"Unknown feature version: {metadata.get('feature_version')}")
        if metadata.get("feature_columns") != FEATURE_PIPELINES[metadata["feature_version"]].FEATURE_COLUMNS:
            raise IncompatibleModelError("Model feature names/order differ from the current pipeline")

        engine = cls(model, metadata, max_staleness_candles, digest[:8])
        engine.sha256 = digest
        return engine

    @property
    def model_version(self) -> str:
        trained_day = self.metadata["trained_at_utc"][:10]
        version = f"{self.metadata['feature_version']}-{trained_day}"
        name = self.metadata.get("model_name")
        return "-".join(part for part in (name, version, self.artifact_id) if part)

    def _confidence(self, top: float) -> dict | None:
        """How often forecasts with a similar top probability were right on data the model never saw."""
        info = self.reliability
        if not info:
            return None
        match = next((b for b in info["bins"] if b["from"] <= top < b["to"]), None)
        return {
            "level": "clear" if top >= info["clear_threshold"] else "weak",
            "historical_accuracy": round(match["accuracy"], 4) if match else None,
            "historical_rows": match["rows"] if match else 0,
        }

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

        needed = MIN_HISTORY_CANDLES[self.metadata["feature_version"]]
        if len(df) < needed:
            raise InsufficientHistoryError(
                f"Need at least {needed} closed candles, got {len(df)}"
            )

        latest_ts = df["timestamp"].iloc[-1]
        age = now - (latest_ts + candle_length)
        if self.max_staleness_candles is not None and age > self.max_staleness_candles * candle_length:
            raise StaleDataError(f"Latest closed candle is {age} old")

        frame = FEATURE_PIPELINES[self.metadata["feature_version"]].make_features(df)
        if frame.empty or frame["timestamp"].iloc[-1] != latest_ts:
            raise InsufficientHistoryError("Could not compute features for the latest candle")

        columns = self.metadata["feature_columns"]
        X = frame[columns].iloc[[-1]]
        if not np.isfinite(X.to_numpy(dtype=float)).all():
            raise InvalidInputError("Features contain non-finite values")

        named = hasattr(self.model, "feature_names_in_")
        proba = self.model.predict_proba(X if named else X.to_numpy())[0]
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
            threshold=self.metadata["threshold"],
            confidence=self._confidence(float(np.max(proba))),
        )
