"""Self-update via GitHub Releases.

Flow:
  1. check_for_updates(current) → fetch latest release from GitHub API
  2. if UpdateInfo returned, UI shows a dialog
  3. download_update(update, on_progress) → writes new exe to %TEMP%
  4. install_update_and_relaunch(new_exe, current_exe) → writes a .bat
     that waits for the current process to exit, swaps files, relaunches,
     then the current process exits.
"""
from __future__ import annotations

import json
import logging
import os
import re
import subprocess
import sys
import tempfile
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

_log = logging.getLogger("pc_optimizer.updater")

REPO = "RafaelCSierra/PC-Optimizer"
API_URL = f"https://api.github.com/repos/{REPO}/releases/latest"
USER_AGENT = "PC-Optimizer-Updater"

_CREATE_NO_WINDOW = 0x08000000
_DETACHED_PROCESS = 0x00000008


@dataclass(frozen=True)
class UpdateInfo:
    current: str
    version: str
    tag: str
    download_url: str
    notes: str
    size_bytes: int
    html_url: str

    @property
    def size_mb(self) -> float:
        return self.size_bytes / (1024 * 1024)


def parse_version(v: str) -> tuple[int, ...]:
    v = (v or "").strip().lstrip("vV")
    parts = re.split(r"[.\-+]", v)
    out: list[int] = []
    for p in parts:
        try:
            out.append(int(p))
        except ValueError:
            break
    return tuple(out)


def check_for_updates(current_version: str, *, timeout: float = 10.0) -> UpdateInfo | None:
    """Fetch the latest release and return UpdateInfo if it's newer than current.

    Returns None on any failure or when already up to date.
    """
    try:
        req = urllib.request.Request(API_URL, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.load(resp)
    except Exception as e:
        _log.warning("update check failed: %s", e)
        return None

    tag = data.get("tag_name", "")
    latest = parse_version(tag)
    current = parse_version(current_version)
    if not latest or latest <= current:
        return None

    asset = next(
        (a for a in data.get("assets", []) if a.get("name", "").lower().endswith(".exe")),
        None,
    )
    if not asset or not asset.get("browser_download_url"):
        _log.info("newer release %s has no .exe asset", tag)
        return None

    return UpdateInfo(
        current=current_version,
        version=".".join(str(x) for x in latest),
        tag=tag,
        download_url=asset["browser_download_url"],
        notes=(data.get("body") or "").strip(),
        size_bytes=int(asset.get("size", 0)),
        html_url=data.get("html_url", f"https://github.com/{REPO}/releases/tag/{tag}"),
    )


def download_update(
    update: UpdateInfo,
    *,
    on_progress: Callable[[int, int], None] | None = None,
    timeout: float = 120.0,
) -> Path:
    """Download the exe into %TEMP%\\PCOptimizer_update. Returns the local path."""
    tmp_dir = Path(tempfile.gettempdir()) / "PCOptimizer_update"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    out_path = tmp_dir / f"PCOptimizer_{update.tag}.exe"

    req = urllib.request.Request(update.download_url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        total_header = resp.headers.get("Content-Length") or str(update.size_bytes or 0)
        total = int(total_header or 0)
        downloaded = 0
        chunk = 64 * 1024
        with open(out_path, "wb") as f:
            while True:
                buf = resp.read(chunk)
                if not buf:
                    break
                f.write(buf)
                downloaded += len(buf)
                if on_progress and total > 0:
                    on_progress(downloaded, total)

    return out_path


def install_update_and_relaunch(new_exe: Path, current_exe: Path) -> None:
    """Spawn a small batch that waits for the current exe to exit, swaps it
    with the new one, and relaunches. Caller must exit the process right after.

    The batch writes its progress to %TEMP%\\PCOptimizer_update.log so we can
    inspect post-mortem if something goes wrong.
    """
    bat_path = Path(tempfile.gettempdir()) / "PCOptimizer_update.bat"
    log_path = Path(tempfile.gettempdir()) / "PCOptimizer_update.log"
    target_name = current_exe.name

    script = (
        "@echo off\r\n"
        "chcp 65001 > nul\r\n"
        f'set LOG={log_path}\r\n'
        'echo [%DATE% %TIME%] bat start > "%LOG%"\r\n'
        f'echo new_exe={new_exe} >> "%LOG%"\r\n'
        f'echo current_exe={current_exe} >> "%LOG%"\r\n'
        'set /a WAIT_COUNT=0\r\n'
        ':wait\r\n'
        f'tasklist /FI "IMAGENAME eq {target_name}" 2>nul | find /I "{target_name}" >nul\r\n'
        'if errorlevel 1 goto ready\r\n'
        'set /a WAIT_COUNT+=1\r\n'
        'if %WAIT_COUNT% GEQ 60 (\r\n'
        '    echo [%DATE% %TIME%] timeout esperando exe sair >> "%LOG%"\r\n'
        '    exit /b 1\r\n'
        ')\r\n'
        'timeout /t 1 /nobreak > nul\r\n'
        'goto wait\r\n'
        ':ready\r\n'
        'echo [%DATE% %TIME%] exe saiu, movendo arquivo >> "%LOG%"\r\n'
        f'move /Y "{new_exe}" "{current_exe}" >> "%LOG%" 2>&1\r\n'
        'if errorlevel 1 (\r\n'
        '    echo [%DATE% %TIME%] move falhou >> "%LOG%"\r\n'
        '    exit /b 1\r\n'
        ')\r\n'
        'echo [%DATE% %TIME%] lancando nova versao >> "%LOG%"\r\n'
        f'start "" "{current_exe}"\r\n'
        'echo [%DATE% %TIME%] concluido >> "%LOG%"\r\n'
    )
    bat_path.write_text(script, encoding="utf-8")

    # Launch detached via `start` — cmd.exe spawns the bat in its own window
    # (minimized) and exits, so we don't hold a process handle.
    subprocess.Popen(
        f'start "" /min cmd /c "{bat_path}"',
        shell=True,
        creationflags=_CREATE_NO_WINDOW,
    )


def current_exe_path() -> Path | None:
    """Return the path to the running .exe when frozen by PyInstaller; else None."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve()
    return None
