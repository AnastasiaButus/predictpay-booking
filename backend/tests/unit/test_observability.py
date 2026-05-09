import json
import logging

from app.core.logging import JsonFormatter, sanitize_headers


def test_json_formatter_does_not_fail() -> None:
    record = logging.LogRecord(
        name="test.logger",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="hello",
        args=(),
        exc_info=None,
    )
    payload = json.loads(JsonFormatter().format(record))

    assert payload["level"] == "INFO"
    assert payload["logger"] == "test.logger"
    assert payload["message"] == "hello"
    assert payload["service"] == "predictpay-bookingguard"
    assert "timestamp" in payload
    assert "environment" in payload


def test_sensitive_headers_not_logged() -> None:
    headers = sanitize_headers(
        {
            "Authorization": "Bearer raw.jwt.token",
            "X-Request-ID": "request-id",
            "refresh-token": "secret-refresh",
        }
    )

    assert headers["Authorization"] == "[redacted]"
    assert headers["refresh-token"] == "[redacted]"
    assert headers["X-Request-ID"] == "request-id"
