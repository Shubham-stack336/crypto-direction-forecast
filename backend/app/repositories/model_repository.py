"""Model-artifact access. Loads trained model files and their saved metrics from disk."""
import json
import logging
import threading
from pathlib import Path

from app.core.symbols import UNIVERSAL_SYMBOL, is_forecastable
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
    def __init__(
        self, model_dir: Path, max_staleness_candles: int | None = 3,
        challenger: "FileModelRepository | None" = None, serve_challenger: bool = False,
    ):
        self._challenger = challenger
        self._serve_challenger = serve_challenger and challenger is not None
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
                engine = PredictionEngine.load(
                    path, self._max_staleness, expected_sha256=self._expected(path)
                )
                self._attach_reliability(engine, path)
                self._engines[path] = engine
            return engine

    def _attach_reliability(self, engine: PredictionEngine, path: Path) -> None:
        """Measured accuracy per confidence level, ignored when it belongs to another model file."""
        sidecar = path.with_suffix(".reliability.json")
        if not sidecar.exists():
            return
        try:
            report = json.loads(sidecar.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            logger.warning("reliability file unreadable: %s", sidecar)
            return
        if report.get("model_sha256") == engine.sha256:
            engine.reliability = report

    def get_challenger(self, symbol: str, timeframe: str) -> PredictionEngine | None:
        """The candidate that forecasts in the background until live results decide. None when it is served."""
        if self._challenger is None or self._serve_challenger or not is_forecastable(symbol):
            return None
        try:
            return self._challenger.get_engine(UNIVERSAL_SYMBOL, timeframe)
        except PredictionError as err:
            logger.warning("challenger unavailable: %s", err)
            return None

    def _expected(self, path: Path) -> str | None:
        """The checksum from manifest.json. A folder with a manifest only serves files listed in it."""
        manifest = self._dir / "manifest.json"
        if not manifest.exists():
            return None
        try:
            checksums = json.loads(manifest.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as err:
            raise IncompatibleModelError("manifest.json is unreadable") from err
        return checksums.get(path.name, "not in manifest")

    def get_engine(self, symbol: str, timeframe: str) -> PredictionEngine:
        if self._serve_challenger and is_forecastable(symbol):
            return self._challenger.get_engine(UNIVERSAL_SYMBOL, timeframe)
        return self._load(self._model_path(self.model_symbol(symbol, timeframe), timeframe))

    def model_symbol(self, symbol: str, timeframe: str) -> str:
        """The symbol whose artifact serves this coin: its own model, or the universal one."""
        if self._serve_challenger and is_forecastable(symbol):
            return UNIVERSAL_SYMBOL
        if self._model_path(symbol, timeframe).exists() or not is_forecastable(symbol):
            return symbol
        if self._model_path(UNIVERSAL_SYMBOL, timeframe).exists():
            return UNIVERSAL_SYMBOL
        return symbol

    def get_metrics(self, symbol: str, timeframe: str) -> dict | None:
        if self._serve_challenger and is_forecastable(symbol):
            return self._challenger.get_metrics(UNIVERSAL_SYMBOL, timeframe)
        stem = artifact_stem(self.model_symbol(symbol, timeframe), timeframe)
        path = self._dir / f"{stem}.metrics.json"
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
