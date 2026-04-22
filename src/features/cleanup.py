"""Cleanup catalog: temp files, prefetch, Windows Update cache, component store, recycle bin.

Each CleanupTask carries the ready-to-run argv for CommandExecutor. Scripts are
intentionally verbose (Write-Host at each step) so the shared console shows what
is happening in real time.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field

_PS = ("powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command")


def _ps(script: str) -> tuple[str, ...]:
    """Trim a multi-line script to a single-line PowerShell -Command payload."""
    collapsed = " ".join(line.strip() for line in script.strip().splitlines() if line.strip())
    return _PS + (collapsed,)


@dataclass(frozen=True)
class CleanupTask:
    id: str
    label: str
    description: str
    cmd: tuple[str, ...]
    needs_confirm: bool = False
    long_running: bool = False
    # Filesystem targets whose total size is an upper-bound estimate of what the
    # task will free. Empty = no estimate offered (e.g. component store, recycle bin).
    size_targets: tuple[str, ...] = field(default_factory=tuple)


def estimate_size(task: CleanupTask) -> int:
    """Walk task.size_targets and sum file sizes. Returns 0 on any issue.

    Caller should run this on a background thread — big temp dirs can take a few seconds.
    """
    total = 0
    for target in task.size_targets:
        path = os.path.expandvars(target)
        if not os.path.isdir(path):
            continue
        for dirpath, _dirs, files in os.walk(path):
            for f in files:
                try:
                    total += os.path.getsize(os.path.join(dirpath, f))
                except OSError:
                    continue
    return total


def format_bytes(n: int) -> str:
    if n <= 0:
        return "—"
    size = float(n)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} PB"


_CLEAN_TEMP = _ps(
    """
    $targets = @($env:TEMP, 'C:\\Windows\\Temp')
    $totalBefore = 0; $totalAfter = 0
    foreach ($p in $targets) {
        if (-not (Test-Path $p)) { continue }
        $before = (Get-ChildItem -Path $p -Recurse -Force -ErrorAction SilentlyContinue |
            Measure-Object -Property Length -Sum).Sum
        if (-not $before) { $before = 0 }
        $totalBefore += $before
        Write-Host ('limpando {0} ({1:N1} MB)' -f $p, ($before/1MB))
        Get-ChildItem -Path $p -Recurse -Force -ErrorAction SilentlyContinue |
            Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
        $after = (Get-ChildItem -Path $p -Recurse -Force -ErrorAction SilentlyContinue |
            Measure-Object -Property Length -Sum).Sum
        if (-not $after) { $after = 0 }
        $totalAfter += $after
    }
    $freed = $totalBefore - $totalAfter
    Write-Host ('liberado: {0:N1} MB' -f ($freed/1MB))
    """
)


_CLEAN_PREFETCH = _ps(
    """
    $p = 'C:\\Windows\\Prefetch'
    if (-not (Test-Path $p)) { Write-Host 'Prefetch nao existe'; exit 0 }
    $before = (Get-ChildItem -Path $p -Recurse -Force -ErrorAction SilentlyContinue |
        Measure-Object -Property Length -Sum).Sum
    if (-not $before) { $before = 0 }
    Write-Host ('Prefetch antes: {0:N1} MB' -f ($before/1MB))
    Get-ChildItem -Path $p -Recurse -Force -ErrorAction SilentlyContinue |
        Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
    $after = (Get-ChildItem -Path $p -Recurse -Force -ErrorAction SilentlyContinue |
        Measure-Object -Property Length -Sum).Sum
    if (-not $after) { $after = 0 }
    Write-Host ('liberado: {0:N1} MB' -f (($before - $after)/1MB))
    """
)


_CLEAN_WU_CACHE = _ps(
    """
    Write-Host 'parando servicos Windows Update (wuauserv, bits)...'
    Stop-Service -Name wuauserv -Force -ErrorAction SilentlyContinue
    Stop-Service -Name bits -Force -ErrorAction SilentlyContinue
    $p = 'C:\\Windows\\SoftwareDistribution\\Download'
    $before = (Get-ChildItem -Path $p -Recurse -Force -ErrorAction SilentlyContinue |
        Measure-Object -Property Length -Sum).Sum
    if (-not $before) { $before = 0 }
    Write-Host ('cache antes: {0:N1} MB' -f ($before/1MB))
    Get-ChildItem -Path $p -Recurse -Force -ErrorAction SilentlyContinue |
        Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
    Write-Host 'reiniciando servicos...'
    Start-Service -Name wuauserv -ErrorAction SilentlyContinue
    Start-Service -Name bits -ErrorAction SilentlyContinue
    Write-Host ('liberado: {0:N1} MB' -f ($before/1MB))
    """
)


_CLEAN_COMPONENT_STORE = (
    "DISM.exe", "/Online", "/Cleanup-Image", "/StartComponentCleanup",
)


_EMPTY_RECYCLE = _ps("Clear-RecycleBin -Force -ErrorAction SilentlyContinue; Write-Host 'lixeira esvaziada'")


CLEANUP_TASKS: tuple[CleanupTask, ...] = (
    CleanupTask(
        id="temp",
        label="Arquivos temporários",
        description=(
            "Remove o conteúdo de %TEMP% (usuário atual) e C:\\Windows\\Temp. "
            "Arquivos em uso por processos ativos são ignorados."
        ),
        cmd=_CLEAN_TEMP,
        size_targets=("%TEMP%", r"C:\Windows\Temp"),
    ),
    CleanupTask(
        id="prefetch",
        label="Prefetch",
        description=(
            "Limpa C:\\Windows\\Prefetch. O Windows reconstrói esses arquivos "
            "conforme os apps são usados — a primeira inicialização de cada "
            "programa pode ficar um pouco mais lenta logo após a limpeza."
        ),
        cmd=_CLEAN_PREFETCH,
        needs_confirm=True,
        size_targets=(r"C:\Windows\Prefetch",),
    ),
    CleanupTask(
        id="wu_cache",
        label="Cache do Windows Update",
        description=(
            "Para wuauserv e BITS, limpa C:\\Windows\\SoftwareDistribution\\"
            "Download e reinicia os serviços. Útil quando o Windows Update "
            "está travado ou reclamando de corrupção."
        ),
        cmd=_CLEAN_WU_CACHE,
        needs_confirm=True,
        size_targets=(r"C:\Windows\SoftwareDistribution\Download",),
    ),
    CleanupTask(
        id="component_store",
        label="DISM — Component Store Cleanup",
        description=(
            "Remove pacotes antigos da WinSxS que não são mais necessários após "
            "atualizações. Pode recuperar alguns GB. Processo demorado."
        ),
        cmd=_CLEAN_COMPONENT_STORE,
        long_running=True,
    ),
    CleanupTask(
        id="recycle_bin",
        label="Esvaziar Lixeira",
        description="Esvazia a Lixeira do Windows de forma permanente em todos os drives.",
        cmd=_EMPTY_RECYCLE,
        needs_confirm=True,
    ),
)
