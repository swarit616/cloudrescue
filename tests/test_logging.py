"""JSON log format and redaction (standard library only)."""

from __future__ import annotations

import json
import logging

from app.logging_config import JsonFormatter, request_id_var


def render(**context) -> dict:
    logger = logging.getLogger("cloudrescue.test")
    record = logger.makeRecord(
        "cloudrescue.test", logging.INFO, __file__, 1, "x", (), None,
        extra={"event": "demo.event", "context": context},
    )  # fmt: skip
    return json.loads(JsonFormatter().format(record))


def test_log_line_is_structured_json():
    token = request_id_var.set("req-1")
    try:
        line = render(incident_id=3)
    finally:
        request_id_var.reset(token)
    assert line["event"] == "demo.event"
    assert line["level"] == "INFO"
    assert line["request_id"] == "req-1"
    assert line["context"] == {"incident_id": 3}
    assert line["timestamp"].endswith("+00:00")


def test_sensitive_keys_are_redacted():
    line = render(demo_token="abc", Authorization="Bearer x", safe="ok")
    assert line["context"]["demo_token"] == "***REDACTED***"
    assert line["context"]["Authorization"] == "***REDACTED***"
    assert line["context"]["safe"] == "ok"
