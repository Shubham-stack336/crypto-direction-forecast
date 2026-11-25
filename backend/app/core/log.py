"""Logging setup: readable text in development, one JSON object per line in production."""
import json
import logging
from datetime import datetime, timezone

EXTRA_FIELDS = ("request_id", "method", "path", "status", "duration_ms")


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        entry = {
            "ts": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for field in EXTRA_FIELDS:
            if hasattr(record, field):
                entry[field] = getattr(record, field)
        if record.exc_info:
            entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(entry)


class TextFormatter(logging.Formatter):
    """Readable lines that also show which request a log entry is about."""

    def formatMessage(self, record: logging.LogRecord) -> str:
        line = super().formatMessage(record)
        details = [f"{f}={getattr(record, f)}" for f in EXTRA_FIELDS[1:] if hasattr(record, f)]
        return " ".join([line, *details])


def configure_logging(json_logs: bool) -> None:
    handler = logging.StreamHandler()
    if json_logs:
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(TextFormatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    handler._app_handler = True  # lets us replace only our own handler on repeated setup
    root = logging.getLogger()
    for existing in list(root.handlers):
        if getattr(existing, "_app_handler", False):
            root.removeHandler(existing)
    root.addHandler(handler)
    root.setLevel(logging.INFO)
