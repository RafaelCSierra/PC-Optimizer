"""Global dry-run flag consulted by the executor.

When enabled, CommandExecutor logs the command and completes with exit 0
without actually spawning a subprocess — useful for previewing debloat
and cleanup actions.
"""
from __future__ import annotations

import logging
import threading

_log = logging.getLogger("pc_optimizer.dry_run")
_lock = threading.Lock()
_enabled: bool = False


def is_enabled() -> bool:
    with _lock:
        return _enabled


def set_enabled(value: bool) -> None:
    """Update the flag and persist it to config.json."""
    global _enabled
    with _lock:
        _enabled = bool(value)
    _log.info("dry_run=%s", _enabled)
    from src.utils.config import get_config
    get_config().set("dry_run", _enabled)


def init_from_config() -> None:
    """Load the persisted value at startup. Call once from app.main()."""
    global _enabled
    from src.utils.config import get_config
    with _lock:
        _enabled = bool(get_config().get("dry_run"))
    _log.info("dry_run loaded from config: %s", _enabled)
