"""
Logging Configuration
---------------------
Centralised logger factory for the entire application.
Every module creates its own named logger via setup_logger(__name__),
which makes it easy to trace exactly which module produced a log line.

Log format: 2024-01-15 09:23:11 | INFO     | app.routers.auth | User registered
Log level : DEBUG in development (verbose), INFO in production (clean).

In production, consider replacing the StreamHandler with a file handler
or a logging service like Datadog or Sentry for persistence and alerting.
"""

import logging
import sys
from app.config import settings


def setup_logger(name: str) -> logging.Logger:
    """
    Creates and returns a named logger with consistent formatting.

    Args:
        name: The logger name, typically __name__ from the calling module.
              This makes log lines show exactly which module they came from.

    Returns:
        A configured logging.Logger instance.

    Note:
        Checks for existing handlers before adding new ones to prevent
        duplicate log lines when the function is called multiple times
        for the same logger name (common in FastAPI with hot reload).
    """
    logger = logging.getLogger(name)

    # Guard against duplicate handlers — FastAPI's --reload can call
    # module-level code multiple times, which would add duplicate handlers
    # and cause every log line to print multiple times.
    if logger.handlers:
        return logger

    # Use DEBUG level in development for full visibility into DB queries,
    # request details, and application flow. Use INFO in production to
    # reduce noise and avoid logging potentially sensitive debug data.
    level = logging.DEBUG if settings.DEBUG else logging.INFO
    logger.setLevel(level)

    # StreamHandler writes to stdout, which is the standard for containerised
    # apps — Docker and Kubernetes collect stdout logs automatically.
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(level)

    # Format includes timestamp, padded level name, module name, and message.
    # The padding on levelname (%-8s) keeps columns aligned for readability.
    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    return logger