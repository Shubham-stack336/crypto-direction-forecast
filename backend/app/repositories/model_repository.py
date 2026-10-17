"""Model-artifact access. Loads trained model files and their saved metrics from disk."""
import json
import logging
import threading
from pathlib import Path

from app.ml.inference import (
    IncompatibleModelError,
    ModelNotFoundError,
    PredictionEngine,
    PredictionError,
)

logger = logging.getLogger(__name__)


def artifact_stem(symbol: str, timeframe: str) -> str:
    return f"{symbol.replace('/', '_').lower()}_{timeframe}_rf"


class FileModelRepository:
    def __init__(self, model_dir: Path, max_staleness_candles: int | None = 3):
        self._dir = Path(model_dir)
        self._max_staleness = max_staleness_candles
        self._engines: dict[Path, PredictionEngine] = {}
        self._lock = threading.Lock()

    def _model_path(self, symbol: str, timeframe: str) -> Path:
        return self._dir / f"{artifact_stem(symbol, timeframe)}.joblib"

    def _load(self, path: Path) -> PredictionEngine:
        with self._lock:
            engine = self._engines.get(path)
            if engine is None:
                engine = PredictionEngine.load(path, self._max_staleness)
                self._engines[path] = engine
            return engine

    def get_engine(self, symbol: str, timeframe: str) -> PredictionEngine:
        return self._load(self._model_path(symbol, timeframe))

    def get_metrics(self, symbol: str, timeframe: str) -> dict | None:
        path = self._dir / f"{artifact_stem(symbol, timeframe)}.metrics.json"
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            logger.warning("metrics file unreadable: %s", path)
            return None

    def available_models(self) -> list[str]:
        """Labels such as 'BTC/USDT 1h' for every artifact that loads correctly."""
        found = []
        for path in sorted(self._dir.glob("*_rf.joblib")):
            try:
                metadata = self._load(path).metadata
            except PredictionError as err:
                logger.warning("skipping unusable model %s: %s", path.name, err)
                continue
            found.append(f"{metadata['symbol']} {metadata['timeframe']}")
        return found


__all__ = ["FileModelRepository", "ModelNotFoundError", "IncompatibleModelError"]
