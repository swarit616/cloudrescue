"""Structured JSON logging (one JSON object per line)."""

from __future__ import annotations

import json
import logging
import sys
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any

LOGGER_NAME = "cloudrescue"
request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)

_SENSITIVE = ("token", "secret", "password", "authorization", "key")


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, UTC).isoformat(
                timespec="milliseconds"
            ),
            "level": record.levelname,
            "event": getattr(record, "event", None) or record.getMessage(),
            "logger": record.name,
        }
        request_id = request_id_var.get()
        if request_id:
            payload["request_id"] = request_id
        context = getattr(record, "context", None)
        if context:
            payload["context"] = {
                k: "***REDACTED***" if any(s in k.lower() for s in _SENSITIVE) else v
                for k, v in context.items()
            }
        if record.exc_info and record.exc_info[0] is not None:
            payload["error_type"] = record.exc_info[0].__name__
        return json.dumps(payload, default=str, separators=(",", ":"))


def configure_logging(level: str = "INFO") -> logging.Logger:
    logger = logging.getLogger(LOGGER_NAME)
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    logger.addHandler(handler)
    logger.setLevel(level)
    logger.propagate = False
    return logger


def log_event(logger: logging.Logger, level: int, event: str, **context: Any) -> None:
    logger.log(level, event, extra={"event": event, "context": context})
