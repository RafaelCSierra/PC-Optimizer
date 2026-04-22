"""PC Optimizer entry point.

Run with `py pc_optimizer.py` from a terminal. The app will request UAC
elevation on startup if not already running as administrator.
"""
from __future__ import annotations

import sys

from src.app import main

if __name__ == "__main__":
    sys.exit(main())
