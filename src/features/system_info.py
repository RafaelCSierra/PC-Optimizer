"""Gather read-only system info: OS, CPU, RAM, GPU, disks, uptime."""
from __future__ import annotations

import getpass
import json
import logging
import os
import platform
import socket
import subprocess
import time
from dataclasses import dataclass, field

import psutil

_CREATE_NO_WINDOW = 0x08000000
_log = logging.getLogger("pc_optimizer.system_info")


@dataclass(frozen=True)
class DiskInfo:
    mountpoint: str
    fstype: str
    total_gb: float
    used_gb: float
    free_gb: float
    percent: float


@dataclass(frozen=True)
class SystemInfo:
    hostname: str
    user: str
    os_caption: str
    os_build: str
    uptime_seconds: int
    cpu_name: str
    cpu_physical_cores: int
    cpu_logical_cores: int
    cpu_percent: float
    ram_total_gb: float
    ram_available_gb: float
    ram_percent: float
    gpu_names: tuple[str, ...]
    disks: tuple[DiskInfo, ...]
    app_version: str

    def format_uptime(self) -> str:
        s = int(self.uptime_seconds)
        days, rem = divmod(s, 86400)
        hours, rem = divmod(rem, 3600)
        minutes, _ = divmod(rem, 60)
        parts: list[str] = []
        if days:
            parts.append(f"{days}d")
        if hours or days:
            parts.append(f"{hours}h")
        parts.append(f"{minutes}m")
        return " ".join(parts)


def _powershell_system_info() -> dict:
    """Query WMI via a single PowerShell call. Returns {} on failure."""
    script = (
        "$cpu = Get-CimInstance Win32_Processor | Select-Object -First 1; "
        "$os = Get-CimInstance Win32_OperatingSystem; "
        "$gpus = @(Get-CimInstance Win32_VideoController | "
        "Select-Object -ExpandProperty Name); "
        "@{ "
        "cpu_name = $cpu.Name.Trim(); "
        "cpu_cores = [int]$cpu.NumberOfCores; "
        "cpu_threads = [int]$cpu.NumberOfLogicalProcessors; "
        "os_caption = $os.Caption; "
        "os_build = $os.BuildNumber; "
        "gpu_names = $gpus "
        "} | ConvertTo-Json -Compress"
    )
    cmd = [
        "powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
        "-Command", script,
    ]
    try:
        res = subprocess.run(
            cmd, capture_output=True, text=True, timeout=20,
            creationflags=_CREATE_NO_WINDOW,
        )
    except subprocess.TimeoutExpired:
        _log.error("powershell system info: timeout")
        return {}
    except FileNotFoundError:
        _log.error("powershell not found")
        return {}
    if res.returncode != 0:
        _log.error("powershell system info failed: %s", (res.stderr or "").strip())
        return {}
    try:
        return json.loads(res.stdout or "{}")
    except json.JSONDecodeError:
        _log.exception("failed to parse system info JSON")
        return {}


def collect() -> SystemInfo:
    """Collect a snapshot. Safe to call repeatedly; takes ~300-1500ms per call."""
    ps = _powershell_system_info()

    vm = psutil.virtual_memory()
    uptime = int(time.time() - psutil.boot_time())

    disks: list[DiskInfo] = []
    for part in psutil.disk_partitions(all=False):
        try:
            usage = psutil.disk_usage(part.mountpoint)
        except (PermissionError, OSError):
            continue
        disks.append(DiskInfo(
            mountpoint=part.mountpoint,
            fstype=part.fstype or "—",
            total_gb=usage.total / (1024 ** 3),
            used_gb=usage.used / (1024 ** 3),
            free_gb=usage.free / (1024 ** 3),
            percent=usage.percent,
        ))

    try:
        from src import __version__ as app_version
    except ImportError:
        app_version = "?"

    gpus = ps.get("gpu_names") or []
    if isinstance(gpus, str):
        gpus = [gpus]

    return SystemInfo(
        hostname=socket.gethostname(),
        user=getpass.getuser(),
        os_caption=ps.get("os_caption") or platform.platform(),
        os_build=str(ps.get("os_build") or platform.version()),
        uptime_seconds=uptime,
        cpu_name=(ps.get("cpu_name") or platform.processor() or "desconhecido").strip(),
        cpu_physical_cores=int(ps.get("cpu_cores") or psutil.cpu_count(logical=False) or 0),
        cpu_logical_cores=int(ps.get("cpu_threads") or psutil.cpu_count(logical=True) or 0),
        cpu_percent=psutil.cpu_percent(interval=0.1),
        ram_total_gb=vm.total / (1024 ** 3),
        ram_available_gb=vm.available / (1024 ** 3),
        ram_percent=vm.percent,
        gpu_names=tuple(str(g) for g in gpus),
        disks=tuple(disks),
        app_version=app_version,
    )


def log_dir_path() -> str:
    base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    return os.path.join(base, "PCOptimizer", "logs")
