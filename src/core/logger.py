"""Application-wide logger with rotating file output in %LOCALAPPDATA%."""
from __future__ import annotations

import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

_LOGGER_NAME = "pc_optimizer"


def log_dir() -> Path:
    """Return the directory where app logs live, creating it if needed."""
    base = os.environ.get("LOCALAPPDATA") or str(Path.home())
    d = Path(base) / "PCOptimizer" / "logs"
    d.mkdir(parents=True, exist_ok=True)
    return d


def setup_logger(level: int = logging.INFO) -> logging.Logger:
    """Configure and return the app logger. Idempotent — safe to call twice."""
    logger = logging.getLogger(_LOGGER_NAME)
    if logger.handlers:
        return logger

    logger.setLevel(level)
    logger.propagate = False

    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    fh = RotatingFileHandler(
        log_dir() / "app.log",
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    fh.setFormatter(fmt)
    logger.addHandler(fh)

    sh = logging.StreamHandler(sys.stderr)
    sh.setFormatter(fmt)
    logger.addHandler(sh)

    return logger


def get_logger(name: str | None = None) -> logging.Logger:
    """Return a child logger under the app namespace."""
    root = logging.getLogger(_LOGGER_NAME)
    return root.getChild(name) if name else root
