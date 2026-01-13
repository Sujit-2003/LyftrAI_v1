"""
Structured JSON logging utilities.
"""
import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from app.config import get_settings


class JSONFormatter(logging.Formatter):
    """Custom JSON formatter for structured logging."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry: Dict[str, Any] = {
            "ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "level": record.levelname,
            "message": record.getMessage(),
        }

        # Add extra fields from the record
        if hasattr(record, "request_id"):
            log_entry["request_id"] = record.request_id
        if hasattr(record, "method"):
            log_entry["method"] = record.method
        if hasattr(record, "path"):
            log_entry["path"] = record.path
        if hasattr(record, "status"):
            log_entry["status"] = record.status
        if hasattr(record, "latency_ms"):
            log_entry["latency_ms"] = record.latency_ms
        if hasattr(record, "message_id"):
            log_entry["message_id"] = record.message_id
        if hasattr(record, "dup"):
            log_entry["dup"] = record.dup
        if hasattr(record, "result"):
            log_entry["result"] = record.result

        # Add exception info if present
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_entry, default=str)


def setup_logging() -> logging.Logger:
    """Set up the application logger with JSON formatting."""
    settings = get_settings()

    # Create logger
    logger = logging.getLogger("app")
    logger.setLevel(getattr(logging, settings.log_level, logging.INFO))

    # Remove existing handlers
    logger.handlers = []

    # Create console handler with JSON formatter
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONFormatter())
    logger.addHandler(handler)

    # Prevent propagation to root logger
    logger.propagate = False

    return logger


def get_logger() -> logging.Logger:
    """Get the application logger."""
    return logging.getLogger("app")


class RequestLogContext:
    """Context holder for request-level logging data."""

    def __init__(
        self,
        request_id: str,
        method: str,
        path: str,
        status: Optional[int] = None,
        latency_ms: Optional[float] = None,
        message_id: Optional[str] = None,
        dup: Optional[bool] = None,
        result: Optional[str] = None,
    ):
        self.request_id = request_id
        self.method = method
        self.path = path
        self.status = status
        self.latency_ms = latency_ms
        self.message_id = message_id
        self.dup = dup
        self.result = result

    def to_dict(self) -> Dict[str, Any]:
        """Convert context to dictionary for logging."""
        data = {
            "request_id": self.request_id,
            "method": self.method,
            "path": self.path,
        }
        if self.status is not None:
            data["status"] = self.status
        if self.latency_ms is not None:
            data["latency_ms"] = self.latency_ms
        if self.message_id is not None:
            data["message_id"] = self.message_id
        if self.dup is not None:
            data["dup"] = self.dup
        if self.result is not None:
            data["result"] = self.result
        return data


def log_request(
    logger: logging.Logger,
    ctx: RequestLogContext,
    level: int = logging.INFO,
    message: str = "Request processed",
) -> None:
    """Log a request with structured context."""
    extra = ctx.to_dict()
    record = logger.makeRecord(
        logger.name,
        level,
        "",
        0,
        message,
        (),
        None,
    )
    for key, value in extra.items():
        setattr(record, key, value)
    logger.handle(record)
