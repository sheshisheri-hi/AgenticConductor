"""Structured JSON logging for Conductor.

Promoted from Coding-Agent's logging_config.py — now a conductor-core primitive.
All log output is structured via structlog. No print() or unstructured logging.

Log output goes to:
  - stdout (always)
  - CONDUCTOR_LOG_FILE path (when set in .env)
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import structlog


def configure_logging(
    log_level: str = "INFO",
    json_output: bool = True,
    log_file: str | None = None,
) -> None:
    """Configure structured logging for the entire application.

    Call once at application startup (in main.py). Never call from agents.

    Args:
        log_level: Minimum log level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
        json_output: True = JSON lines (prod), False = colored console (dev).
        log_file: Optional path to write logs to file in addition to stdout.
    """
    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
    ]

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    renderer = structlog.processors.JSONRenderer() if json_output else structlog.dev.ConsoleRenderer()
    formatter = structlog.stdlib.ProcessorFormatter(
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )

    root_logger = logging.getLogger()
    root_logger.handlers.clear()

    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setFormatter(formatter)
    root_logger.addHandler(stdout_handler)

    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_path, encoding="utf-8")
        file_formatter = structlog.stdlib.ProcessorFormatter(
            processors=[
                structlog.stdlib.ProcessorFormatter.remove_processors_meta,
                structlog.processors.JSONRenderer(),
            ],
        )
        file_handler.setFormatter(file_formatter)
        root_logger.addHandler(file_handler)

    root_logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Get a named structured logger.

    Args:
        name: Logger name, typically __name__ or agent name.
    """
    return structlog.get_logger(name)
