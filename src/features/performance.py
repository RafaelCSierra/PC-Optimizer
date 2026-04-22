"""Performance feature module: power plans, quick toggles, startup entries."""
from __future__ import annotations

import json
import logging
import re
import subprocess
import winreg
from dataclasses import dataclass

_CREATE_NO_WINDOW = 0x08000000
_log = logging.getLogger("pc_optimizer.performance")


# GUID of Microsoft's built-in "Ultimate Performance" scheme template.
# Running `powercfg -duplicatescheme <this>` creates a new plan from it.
ULTIMATE_PERFORMANCE_TEMPLATE = "e9a42b02-d5df-448d-aa00-03f14749eb61"


@dataclass(frozen=True)
class PowerPlan:
    guid: str
    name: str
    is_active: bool


_PLAN_LINE = re.compile(
    r"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})\s+\(([^)]+)\)(\s*\*)?",
    re.IGNORECASE,
)


def _run_powercfg(args: list[str], *, timeout: float = 15.0) -> tuple[int, str, str]:
    try:
        r = subprocess.run(
            ["powercfg", *args],
            capture_output=True, text=True, timeout=timeout,
            creationflags=_CREATE_NO_WINDOW,
        )
    except subprocess.TimeoutExpired:
        return 1, "", "timeout"
    except FileNotFoundError:
        return 1, "", "powercfg não encontrado"
    return r.returncode, r.stdout or "", r.stderr or ""


def list_plans() -> list[PowerPlan]:
    """Return all installed power schemes. Empty list on failure."""
    code, out, err = _run_powercfg(["/list"])
    if code != 0:
        _log.error("powercfg /list failed: %s", err.strip() or out.strip())
        return []

    plans: list[PowerPlan] = []
    for line in out.splitlines():
        m = _PLAN_LINE.search(line)
        if not m:
            continue
        guid, name, active = m.group(1).lower(), m.group(2).strip(), m.group(3)
        plans.append(PowerPlan(guid=guid, name=name, is_active=bool(active)))
    return plans


def get_active_guid() -> str | None:
    code, out, _ = _run_powercfg(["/getactivescheme"])
    if code != 0:
        return None
    m = _PLAN_LINE.search(out)
    return m.group(1).lower() if m else None


def set_active(guid: str) -> tuple[bool, str]:
    code, out, err = _run_powercfg(["/setactive", guid])
    if code == 0:
        return True, f"Plano ativado: {guid}"
    return False, (err or out).strip() or f"exit code {code}"


def unlock_ultimate_performance() -> tuple[bool, str]:
    """Duplicate the Ultimate Performance template so it appears in the plan list.

    Returns (success, message). On success, the message includes the new plan's GUID.
    No-op (but reported as success) if the plan is already present.
    """
    existing = list_plans()
    for p in existing:
        if "ultimate" in p.name.lower() or "desempenho m" in p.name.lower():
            return True, f"Ultimate Performance já existe: {p.guid}"

    code, out, err = _run_powercfg(["-duplicatescheme", ULTIMATE_PERFORMANCE_TEMPLATE])
    if code != 0:
        return False, (err or out).strip() or f"exit code {code}"
    # duplicatescheme echoes the new GUID
    m = _PLAN_LINE.search(out)
    new_guid = m.group(1) if m else "?"
    return True, f"Ultimate Performance criado: {new_guid}"


# =============================================================================
# Quick registry toggles
# =============================================================================

@dataclass(frozen=True)
class QuickToggle:
    id: str
    label: str
    description: str
    # Full registry path relative to the hive.
    reg_path: str
    reg_name: str
    # Values that the DWORD should have for the semantic on/off.
    # on_value may be less than off_value (e.g. when the registry name is a
    # "disable" flag inverted in our UI label).
    on_value: int
    off_value: int
    # If the key/name doesn't exist, what the effective default is.
    default_when_missing: int
    # Hive: "HKCU" or "HKLM".
    hive: str = "HKCU"


QUICK_TOGGLES: tuple[QuickToggle, ...] = (
    QuickToggle(
        id="game_mode",
        label="Game Mode",
        description=(
            "Otimiza o desempenho em jogos priorizando o processo ativo e pausando "
            "atualizações/notificações."
        ),
        reg_path=r"Software\Microsoft\GameBar",
        reg_name="AutoGameModeEnabled",
        on_value=1, off_value=0, default_when_missing=1,
    ),
    QuickToggle(
        id="transparency",
        label="Efeitos de transparência",
        description=(
            "Acrílico e blur no Start, barra de tarefas e janelas. Desligar "
            "reduz uso de GPU em máquinas modestas."
        ),
        reg_path=r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
        reg_name="EnableTransparency",
        on_value=1, off_value=0, default_when_missing=1,
    ),
    QuickToggle(
        id="start_recent",
        label="Mostrar arquivos/itens recentes no Iniciar",
        description=(
            "Lista de arquivos usados recentemente no menu Iniciar e no Explorer. "
            "Desligar aumenta privacidade."
        ),
        reg_path=r"Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced",
        reg_name="Start_TrackDocs",
        on_value=1, off_value=0, default_when_missing=1,
    ),
    QuickToggle(
        id="bg_apps",
        label="Permitir apps rodando em background",
        description=(
            "Controla se apps da Microsoft Store podem rodar quando você não "
            "está usando. Desligar economiza bateria/RAM."
        ),
        reg_path=r"Software\Microsoft\Windows\CurrentVersion\BackgroundAccessApplications",
        reg_name="GlobalUserDisabled",
        # The registry flag is "GlobalUserDisabled" — on=0 means background apps allowed.
        on_value=0, off_value=1, default_when_missing=0,
    ),
    QuickToggle(
        id="visual_fx_perf",
        label="Priorizar performance sobre efeitos visuais",
        description=(
            "Reduz animações e sombras do Windows (mesmo que 'Melhor desempenho' "
            "em Propriedades do Sistema → Desempenho)."
        ),
        reg_path=r"Software\Microsoft\Windows\CurrentVersion\Explorer\VisualEffects",
        reg_name="VisualFXSetting",
        # 2 = best performance; 0 = let Windows choose (our 'off' default)
        on_value=2, off_value=0, default_when_missing=0,
    ),
    QuickToggle(
        id="tb_widgets",
        label="Widgets na barra de tarefas",
        description=(
            "Botão de Widgets (clima, notícias, feed) à esquerda da barra. "
            "Desligar libera espaço e reduz uso de rede passivo."
        ),
        reg_path=r"Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced",
        reg_name="TaskbarDa",
        on_value=1, off_value=0, default_when_missing=1,
    ),
    QuickToggle(
        id="tb_copilot",
        label="Botão Copilot na barra de tarefas",
        description=(
            "Ícone de atalho do Copilot. Desligar apenas oculta o botão — não "
            "desabilita o serviço em si."
        ),
        reg_path=r"Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced",
        reg_name="ShowCopilotButton",
        on_value=1, off_value=0, default_when_missing=1,
    ),
    QuickToggle(
        id="tb_chat",
        label="Botão Chat (Teams consumer) na barra",
        description="Atalho do Microsoft Teams consumer na barra de tarefas.",
        reg_path=r"Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced",
        reg_name="TaskbarMn",
        on_value=1, off_value=0, default_when_missing=1,
    ),
    QuickToggle(
        id="search_highlights",
        label="Highlights / sugestões na busca",
        description=(
            "Banner colorido com 'dia de X' e sugestões no campo de busca do "
            "menu Iniciar. Desligar limpa a UI da busca."
        ),
        reg_path=r"Software\Microsoft\Windows\CurrentVersion\Feeds\DSB",
        reg_name="ShowDynamicContent",
        on_value=1, off_value=0, default_when_missing=1,
    ),
)


def _hive(name: str) -> int:
    return winreg.HKEY_LOCAL_MACHINE if name.upper() == "HKLM" else winreg.HKEY_CURRENT_USER


def toggle_by_id(toggle_id: str) -> QuickToggle | None:
    return next((t for t in QUICK_TOGGLES if t.id == toggle_id), None)


def read_toggle(toggle: QuickToggle) -> bool:
    """Return True if the toggle is currently enabled (per its semantic on_value)."""
    try:
        with winreg.OpenKey(_hive(toggle.hive), toggle.reg_path, 0, winreg.KEY_READ) as key:
            value, _type = winreg.QueryValueEx(key, toggle.reg_name)
            return int(value) == toggle.on_value
    except (FileNotFoundError, OSError):
        return toggle.default_when_missing == toggle.on_value


def write_toggle(toggle: QuickToggle, enable: bool) -> tuple[bool, str]:
    """Set the registry DWORD to on_value or off_value. Returns (ok, message)."""
    target = toggle.on_value if enable else toggle.off_value
    try:
        with winreg.CreateKeyEx(_hive(toggle.hive), toggle.reg_path, 0, winreg.KEY_SET_VALUE) as key:
            winreg.SetValueEx(key, toggle.reg_name, 0, winreg.REG_DWORD, target)
        return True, f"{toggle.label}: {'ligado' if enable else 'desligado'}"
    except OSError as e:
        _log.exception("write_toggle failed for %s", toggle.id)
        return False, f"erro ao gravar registry: {e}"


# =============================================================================
# Startup programs (read-only listing)
# =============================================================================

@dataclass(frozen=True)
class StartupEntry:
    name: str
    command: str
    location: str  # e.g. "HKLM\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Run"
    user: str


def list_startup_entries(*, timeout: float = 20.0) -> list[StartupEntry]:
    """Return the merged list of Run-key entries + Startup-folder shortcuts.

    Empty on any failure (logs the error).
    """
    script = (
        "Get-CimInstance Win32_StartupCommand | "
        "Select-Object Name, Command, Location, User | "
        "ConvertTo-Json -Compress"
    )
    cmd = [
        "powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
        "-Command", script,
    ]
    try:
        r = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout,
            creationflags=_CREATE_NO_WINDOW,
        )
    except subprocess.TimeoutExpired:
        _log.error("list_startup_entries: timeout")
        return []
    except FileNotFoundError:
        _log.error("powershell not found")
        return []

    if r.returncode != 0:
        _log.error("Win32_StartupCommand failed: %s", (r.stderr or "").strip())
        return []
    out = (r.stdout or "").strip()
    if not out:
        return []
    try:
        raw = json.loads(out)
    except json.JSONDecodeError:
        _log.exception("failed to parse startup JSON")
        return []

    if isinstance(raw, dict):
        raw = [raw]
    entries: list[StartupEntry] = []
    for item in raw:
        entries.append(StartupEntry(
            name=str(item.get("Name") or "—"),
            command=str(item.get("Command") or ""),
            location=str(item.get("Location") or "—"),
            user=str(item.get("User") or "—"),
        ))
    # Sort by location then name for stable display.
    entries.sort(key=lambda e: (e.location.lower(), e.name.lower()))
    return entries


# --- Startup enable/disable via StartupApproved ---
# The StartupApproved subkey mirrors the Task Manager "Startup apps" toggle.
# Each value is a binary blob: first DWORD is state (0x02/0x06 enabled, 0x03
# disabled), followed by 8-byte FILETIME. Missing value → Windows treats as
# enabled by default.

_STATE_ENABLED = 0x02
_STATE_DISABLED = 0x03


def _filetime_now_bytes() -> bytes:
    """Current UTC time as 8-byte little-endian FILETIME (100-ns since 1601)."""
    import datetime
    epoch = datetime.datetime(1601, 1, 1, tzinfo=datetime.timezone.utc)
    now = datetime.datetime.now(tz=datetime.timezone.utc)
    intervals = int((now - epoch).total_seconds() * 10_000_000)
    return intervals.to_bytes(8, byteorder="little", signed=False)


def _startup_approved_target(entry: StartupEntry) -> tuple[int, str, str] | None:
    """Return (hive, subkey, value_name) for the StartupApproved entry matching
    this StartupEntry, or None if the location isn't togglable.
    """
    loc = entry.location.strip().upper()
    name = entry.name
    approved_base = r"Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved"

    if loc == "STARTUP":
        return (
            winreg.HKEY_CURRENT_USER,
            rf"{approved_base}\StartupFolder",
            name if name.lower().endswith(".lnk") else f"{name}.lnk",
        )
    if loc == "COMMON STARTUP":
        return (
            winreg.HKEY_LOCAL_MACHINE,
            rf"{approved_base}\StartupFolder",
            name if name.lower().endswith(".lnk") else f"{name}.lnk",
        )
    if loc.startswith("HKLM"):
        run_key = "Run32" if "WOW6432NODE" in loc else "Run"
        return (
            winreg.HKEY_LOCAL_MACHINE,
            rf"{approved_base}\{run_key}",
            name,
        )
    # Current user entries can come as HKCU\… or HKU\S-1-5-21-…\ (Win32_StartupCommand
    # reports the per-user hive via its SID). Both map to HKCU StartupApproved.
    if loc.startswith("HKCU") or loc.startswith("HKEY_CURRENT_USER"):
        return (winreg.HKEY_CURRENT_USER, rf"{approved_base}\Run", name)
    if loc.startswith("HKU\\S-1-5-21"):
        return (winreg.HKEY_CURRENT_USER, rf"{approved_base}\Run", name)
    # System profiles (HKU\.DEFAULT, HKU\S-1-5-18/19/20) — don't expose a toggle
    return None


def get_startup_state(entry: StartupEntry) -> bool:
    """True if the entry is currently enabled (no StartupApproved record =
    default enabled; 0x03 in the state byte = disabled)."""
    target = _startup_approved_target(entry)
    if target is None:
        return True  # unknown location — assume enabled, toggling will be a no-op
    hive, subkey, value_name = target
    try:
        with winreg.OpenKey(hive, subkey, 0, winreg.KEY_READ) as key:
            data, _type = winreg.QueryValueEx(key, value_name)
    except (FileNotFoundError, OSError):
        return True
    if not data:
        return True
    return data[0] != _STATE_DISABLED


def set_startup_state(entry: StartupEntry, enabled: bool) -> tuple[bool, str]:
    """Write to StartupApproved. Returns (ok, message)."""
    target = _startup_approved_target(entry)
    if target is None:
        return False, f"localização não suportada: {entry.location}"
    hive, subkey, value_name = target

    state = _STATE_ENABLED if enabled else _STATE_DISABLED
    payload = state.to_bytes(4, byteorder="little") + _filetime_now_bytes()
    try:
        with winreg.CreateKeyEx(hive, subkey, 0, winreg.KEY_SET_VALUE) as key:
            winreg.SetValueEx(key, value_name, 0, winreg.REG_BINARY, payload)
        return True, f"{entry.name}: {'habilitado' if enabled else 'desabilitado'}"
    except OSError as e:
        _log.exception("set_startup_state failed")
        return False, f"erro registry: {e}"
