"""Performance feature module: power plans, quick toggles, startup entries."""
from __future__ import annotations

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
