"""Centralized Loguru logging configuration and standard logging interception."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from loguru import logger


class InterceptHandler(logging.Handler):
    """Intercept standard library logging records and redirect them to Loguru."""

    def emit(self, record: logging.LogRecord) -> None:
        # Get corresponding Loguru level if it exists
        try:
            level: str | int = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        # Find caller from where originated the logged message
        frame, depth = sys._getframe(6), 6
        while frame and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back  # type: ignore[assignment]
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(
            level, record.getMessage()
        )


def setup_logging(
    log_level: str = "INFO",
    log_file: str | Path | None = None,
    rotation: str = "10 MB",
    retention: str = "7 days",
    enqueue: bool = False,
) -> None:
    """Configure Loguru sinks and redirect Python stdlib logging through Loguru.

    Args:
        log_level: Minimum logging severity level (DEBUG, INFO, WARNING, ERROR).
        log_file: Optional path to append log files with automatic rotation.
        rotation: File rotation threshold (default: '10 MB').
        retention: Log retention duration (default: '7 days').
        enqueue: Whether to queue logging calls through a background process/thread.
    """
    # Remove default handler
    logger.remove()

    # Add colorized stdout/stderr sink
    log_format = (
        "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
        "<level>{message}</level>"
    )
    logger.add(
        sys.stderr,
        format=log_format,
        level=log_level.upper(),
        colorize=True,
        enqueue=enqueue,
    )

    # Optional file rotation sink
    if log_file:
        file_path = Path(log_file)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        logger.add(
            str(file_path),
            format=log_format,
            level=log_level.upper(),
            rotation=rotation,
            retention=retention,
            compression="zip",
            enqueue=enqueue,
        )

    # Intercept standard library logging (LiteLLM, APScheduler, Crawl4AI, etc.)
    logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)

    # Mute overly noisy third-party libraries if needed
    for noisy_logger in ("httpcore", "httpx", "urllib3", "asyncio"):
        logging.getLogger(noisy_logger).setLevel(logging.WARNING)
