"""PC Optimizer entry point.

Run with `py pc_optimizer.py` from a terminal. The app will request UAC
elevation on startup if not already running as administrator.
"""
from __future__ import annotations

import sys
import traceback
from pathlib import Path

# Ensure `src/` is importable even when launched from a different CWD
# (e.g. elevated via Start-Process -Verb RunAs sets CWD to System32).
_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def _write_crash_log(exc: BaseException) -> None:
    """Last-resort crash dump so we never lose a startup error, even if the logger
    module itself failed to load."""
    import os

    base = os.environ.get("LOCALAPPDATA") or str(Path.home())
    crash_dir = Path(base) / "PCOptimizer" / "logs"
    try:
        crash_dir.mkdir(parents=True, exist_ok=True)
        (crash_dir / "crash.log").write_text(
            "".join(traceback.format_exception(exc)), encoding="utf-8"
        )
    except Exception:
        pass


if __name__ == "__main__":
    try:
        from src.app import main

        sys.exit(main())
    except BaseException as e:
        _write_crash_log(e)
        raise
