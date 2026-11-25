"""Keeps the scan warm and applies data retention, so users do not wait for slow work."""
import logging
import threading

from app.core.cache import CacheStore

logger = logging.getLogger(__name__)


class BackgroundWorker:
    def __init__(self, store: CacheStore, refresh_scan, purge=None, interval_s: int = 120, auto_forecast=None):
        self._store = store
        self._refresh_scan = refresh_scan
        self._purge = purge
        self._auto_forecast = auto_forecast
        self._interval = interval_s
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, name="background", daemon=True)

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._thread.join(timeout=5)

    def tick(self) -> None:
        # With Redis the lock is shared, so only one worker process does the job per interval.
        if self._store.acquire("job:scan", max(1, self._interval - 5)):
            self._guard(self._refresh_scan)
        if self._auto_forecast and self._store.acquire("job:forecast", 1_800):
            self._guard(self._auto_forecast)
        if self._purge and self._store.acquire("job:purge", 86_400):
            self._guard(self._purge)

    @staticmethod
    def _guard(job) -> None:
        try:
            job()
        except Exception:
            logger.exception("background job failed")

    def _run(self) -> None:
        while True:
            self.tick()
            if self._stop.wait(self._interval):
                return
