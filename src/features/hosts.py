"""Hosts file editor backend: ler, salvar, backup, restaurar, templates.

O arquivo `C:\\Windows\\System32\\drivers\\etc\\hosts` requer privilégios de
Administrador para escrita. Toda operação é atômica: a gente grava num arquivo
temporário ao lado e faz rename por cima, evitando corromper em caso de erro.
"""
from __future__ import annotations

import logging
import os
import shutil
import tempfile
from pathlib import Path

_log = logging.getLogger("pc_optimizer.hosts")

HOSTS_PATH = Path(r"C:\Windows\System32\drivers\etc\hosts")
HOSTS_BACKUP_PATH = HOSTS_PATH.with_suffix(".pc-optimizer.bak")

DEFAULT_HOSTS = (
    "# Copyright (c) 1993-2009 Microsoft Corp.\n"
    "#\n"
    "# This is a sample HOSTS file used by Microsoft TCP/IP for Windows.\n"
    "#\n"
    "# localhost name resolution is handled within DNS itself.\n"
    "#\t127.0.0.1       localhost\n"
    "#\t::1             localhost\n"
)


# Curated template blocks. Each is a list of host entries that will be appended
# to the file wrapped in a clear comment banner. Safe defaults — only hostnames
# widely considered pure telemetry/ads endpoints.

TEMPLATE_TELEMETRY = [
    "vortex.data.microsoft.com",
    "vortex-win.data.microsoft.com",
    "telecommand.telemetry.microsoft.com",
    "telemetry.microsoft.com",
    "settings-win.data.microsoft.com",
    "watson.telemetry.microsoft.com",
    "diagnostics.support.microsoft.com",
    "oca.telemetry.microsoft.com",
    "sqm.telemetry.microsoft.com",
    "ceuswatcab01.blob.core.windows.net",
    "ceuswatcab02.blob.core.windows.net",
]

TEMPLATE_ADS = [
    "ads.msn.com",
    "rad.msn.com",
    "srtb.msn.com",
    "static.ads-twitter.com",
    "doubleclick.net",
    "googleads.g.doubleclick.net",
]

TEMPLATES: dict[str, list[str]] = {
    "Telemetria Microsoft": TEMPLATE_TELEMETRY,
    "Propaganda/Ads": TEMPLATE_ADS,
}


def read_hosts() -> str:
    """Return the full content of the hosts file. Empty string if missing."""
    try:
        return HOSTS_PATH.read_text(encoding="utf-8", errors="replace")
    except FileNotFoundError:
        return ""
    except OSError as e:
        _log.exception("read_hosts failed: %s", e)
        return ""


def write_hosts(content: str) -> tuple[bool, str]:
    """Atomic write: tempfile beside hosts + os.replace. Requires admin."""
    try:
        # Write in same directory so os.replace is atomic (cross-device would fail)
        fd, tmp_path = tempfile.mkstemp(
            prefix="hosts.", suffix=".tmp", dir=HOSTS_PATH.parent,
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
                f.write(content)
            os.replace(tmp_path, HOSTS_PATH)
        except OSError:
            # Clean up tmpfile if replace failed
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass
            raise
        return True, f"hosts gravado ({len(content)} bytes)"
    except PermissionError:
        return False, "permissão negada — rodar como Administrador"
    except OSError as e:
        _log.exception("write_hosts failed: %s", e)
        return False, f"erro: {e}"


def backup_hosts() -> tuple[bool, str]:
    try:
        shutil.copy2(HOSTS_PATH, HOSTS_BACKUP_PATH)
        return True, f"backup salvo em {HOSTS_BACKUP_PATH.name}"
    except FileNotFoundError:
        return False, "arquivo hosts não encontrado"
    except PermissionError:
        return False, "permissão negada"
    except OSError as e:
        _log.exception("backup_hosts failed: %s", e)
        return False, f"erro: {e}"


def restore_backup() -> tuple[bool, str]:
    if not HOSTS_BACKUP_PATH.exists():
        return False, "nenhum backup do PC Optimizer encontrado"
    try:
        shutil.copy2(HOSTS_BACKUP_PATH, HOSTS_PATH)
        return True, f"restaurado de {HOSTS_BACKUP_PATH.name}"
    except PermissionError:
        return False, "permissão negada"
    except OSError as e:
        _log.exception("restore_backup failed: %s", e)
        return False, f"erro: {e}"


def has_backup() -> bool:
    return HOSTS_BACKUP_PATH.exists()


def render_template(title: str, entries: list[str]) -> str:
    """Return a newline-delimited block that can be appended to hosts."""
    lines = [f"", f"# --- PC Optimizer: {title} ---"]
    lines.extend(f"0.0.0.0 {host}" for host in entries)
    lines.append(f"# --- end: {title} ---")
    return "\n".join(lines) + "\n"
