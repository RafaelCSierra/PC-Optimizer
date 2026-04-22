"""Create a Windows System Restore Point via PowerShell's Checkpoint-Computer."""
from __future__ import annotations

import logging
import subprocess
from dataclasses import dataclass

_CREATE_NO_WINDOW = 0x08000000
_log = logging.getLogger("pc_optimizer.restore_point")


@dataclass(frozen=True)
class RestorePointResult:
    success: bool
    message: str


def create(description: str, *, timeout: float = 180.0) -> RestorePointResult:
    """Create a System Restore Point with the given description.

    Requirements:
      - Process must be elevated (Admin).
      - System Protection must be enabled on C: (System > About > Advanced system
        settings > System Protection).

    Known quirks:
      - Windows rate-limits restore points to 1 per 24h by default. If another one
        was created recently, Checkpoint-Computer succeeds silently without making
        a new point. We return success in that case — caller should still proceed.
    """
    # -%% is the stop-parsing token in PowerShell — avoids accidental interpolation.
    ps_script = (
        f'Checkpoint-Computer -Description "{description}" '
        '-RestorePointType "MODIFY_SETTINGS"'
    )
    cmd = [
        "powershell",
        "-NoProfile",
        "-ExecutionPolicy", "Bypass",
        "-Command", ps_script,
    ]

    _log.info("creating restore point: %s", description)
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            creationflags=_CREATE_NO_WINDOW,
        )
    except subprocess.TimeoutExpired:
        msg = f"Timeout após {int(timeout)}s ao criar ponto de restauração."
        _log.error(msg)
        return RestorePointResult(False, msg)
    except FileNotFoundError:
        msg = "PowerShell não encontrado no PATH."
        _log.error(msg)
        return RestorePointResult(False, msg)

    if result.returncode == 0:
        _log.info("restore point criado com sucesso")
        return RestorePointResult(True, "Ponto de restauração criado.")

    stderr = (result.stderr or "").strip()
    stdout = (result.stdout or "").strip()
    tail = stderr or stdout or f"exit code {result.returncode}"
    _log.error("checkpoint-computer falhou: %s", tail)
    return RestorePointResult(False, f"Falha ao criar ponto de restauração: {tail}")
