"""Administrator privilege detection and UAC elevation for Windows."""
from __future__ import annotations

import ctypes
import logging
import sys
from pathlib import Path

log = logging.getLogger(__name__)


def is_admin() -> bool:
    """Return True if the current process has administrator privileges."""
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        log.exception("IsUserAnAdmin failed")
        return False


def relaunch_as_admin() -> bool:
    """Relaunch the current script elevated via UAC.

    Returns True if the elevation request was dispatched (caller should exit).
    Returns False if already admin or the relaunch could not be initiated.
    """
    if is_admin():
        return False

    python_exe = sys.executable
    script = str(Path(sys.argv[0]).resolve())
    params = " ".join(f'"{arg}"' for arg in [script, *sys.argv[1:]])

    try:
        rc = ctypes.windll.shell32.ShellExecuteW(
            None, "runas", python_exe, params, None, 1
        )
    except Exception:
        log.exception("ShellExecuteW runas failed")
        return False

    # ShellExecute returns > 32 on success
    return int(rc) > 32
