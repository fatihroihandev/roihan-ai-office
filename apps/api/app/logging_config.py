import json
import logging
import uuid
from contextvars import ContextVar
from datetime import datetime, timezone

correlation_id: ContextVar[str] = ContextVar("correlation_id", default="-")

_RESERVED = set(logging.makeLogRecord({}).__dict__) | {"message", "asctime"}
_SENSITIVE_KEYS = ("token", "key", "secret", "password", "authorization")


def new_correlation_id() -> str:
    return uuid.uuid4().hex


class JsonFormatter(logging.Formatter):
    def __init__(self, secrets: list[str] | None = None, redact: bool = True):
        super().__init__()
        self._secrets = secrets or []
        self._redact = redact

    def _clean(self, text: str) -> str:
        if self._redact:
            for s in self._secrets:
                text = text.replace(s, "[REDACTED]")
        return text

    def format(self, record: logging.LogRecord) -> str:
        data = {
            "ts": datetime.fromtimestamp(record.created, timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "correlation_id": correlation_id.get(),
            "message": record.getMessage(),
        }
        for k, v in record.__dict__.items():
            if k in _RESERVED:
                continue
            if self._redact and any(s in k.lower() for s in _SENSITIVE_KEYS):
                v = "[REDACTED]"
            data[k] = v
        if record.exc_info:
            data["exception"] = self.formatException(record.exc_info)
        return self._clean(json.dumps(data, ensure_ascii=False, default=str))


def setup_logging(secrets: list[str] | None = None, redact: bool = True, level: int = logging.INFO) -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter(secrets, redact))
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)
