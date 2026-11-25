"""Small key/value store: in memory for one process, Redis when several workers must share it."""
import logging
import threading
import time
from typing import Callable, Protocol

logger = logging.getLogger(__name__)
MAX_MEMORY_KEYS = 5_000


class CacheStore(Protocol):
    def get(self, key: str) -> bytes | None: ...

    def set(self, key: str, value: bytes, ttl_s: float) -> None: ...

    def incr(self, key: str, ttl_s: int) -> int: ...

    def acquire(self, key: str, ttl_s: int) -> bool: ...


class MemoryStore:
    def __init__(self, clock: Callable[[], float] = time.monotonic, max_keys: int = MAX_MEMORY_KEYS):
        self._data: dict[str, tuple[float, bytes]] = {}
        self._lock = threading.Lock()
        self._clock = clock
        self._max_keys = max_keys

    def _live(self, key: str) -> bytes | None:
        entry = self._data.get(key)
        if entry is None:
            return None
        if entry[0] <= self._clock():
            del self._data[key]
            return None
        return entry[1]

    def _put(self, key: str, value: bytes, ttl_s: float) -> None:
        if key not in self._data and len(self._data) >= self._max_keys:
            now = self._clock()
            self._data = {k: v for k, v in self._data.items() if v[0] > now}
            while len(self._data) >= self._max_keys:
                self._data.pop(next(iter(self._data)))
        self._data[key] = (self._clock() + ttl_s, value)

    def get(self, key: str) -> bytes | None:
        with self._lock:
            return self._live(key)

    def set(self, key: str, value: bytes, ttl_s: float) -> None:
        with self._lock:
            self._put(key, value, ttl_s)

    def incr(self, key: str, ttl_s: int) -> int:
        with self._lock:
            current = self._live(key)
            if current is None:
                self._put(key, b"1", ttl_s)
                return 1
            count = int(current) + 1
            self._data[key] = (self._data[key][0], str(count).encode())
            return count

    def acquire(self, key: str, ttl_s: int) -> bool:
        with self._lock:
            if self._live(key) is not None:
                return False
            self._put(key, b"1", ttl_s)
            return True


class RedisStore:
    """Redis is an optimisation: if it fails, answer from a local store instead of failing requests."""

    def __init__(self, client, prefix: str = "cdp:"):
        self._client = client
        self._prefix = prefix
        self._local = MemoryStore()

    @classmethod
    def from_url(cls, url: str) -> "RedisStore":
        import redis

        return cls(redis.Redis.from_url(url, socket_timeout=1, socket_connect_timeout=1))

    def _try(self, action: Callable, fallback: Callable):
        import redis

        try:
            return action()
        except redis.RedisError as err:
            logger.warning("redis unavailable: %s", type(err).__name__)
            return fallback()

    def get(self, key: str) -> bytes | None:
        return self._try(lambda: self._client.get(self._prefix + key), lambda: self._local.get(key))

    def set(self, key: str, value: bytes, ttl_s: float) -> None:
        self._try(
            lambda: self._client.set(self._prefix + key, value, px=max(1, int(ttl_s * 1000))),
            lambda: self._local.set(key, value, ttl_s),
        )

    def incr(self, key: str, ttl_s: int) -> int:
        def action():
            pipe = self._client.pipeline()
            pipe.set(self._prefix + key, 0, ex=ttl_s, nx=True)
            pipe.incr(self._prefix + key)
            return int(pipe.execute()[1])

        return self._try(action, lambda: self._local.incr(key, ttl_s))

    def acquire(self, key: str, ttl_s: int) -> bool:
        return self._try(
            lambda: bool(self._client.set(self._prefix + key, 1, ex=ttl_s, nx=True)),
            lambda: self._local.acquire(key, ttl_s),
        )
