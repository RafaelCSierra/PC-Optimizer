"""Windows 11 debloat: Appx package catalog, presets, privacy/telemetry toggles.

All destructive actions are represented as DebloatAction objects with a ready-to-run
PowerShell command. The UI layer is responsible for:
  1. Creating a restore point before apply
  2. Showing a confirmation dialog listing the actions
  3. Executing each action via the shared CommandExecutor

We never auto-apply — this module just returns data.
"""
from __future__ import annotations

import json
import logging
import subprocess
from dataclasses import dataclass
from enum import Enum

_CREATE_NO_WINDOW = 0x08000000
_log = logging.getLogger("pc_optimizer.debloat")


class Preset(str, Enum):
    MINIMO = "minimo"
    RECOMENDADO = "recomendado"
    AGRESSIVO = "agressivo"

    @property
    def label(self) -> str:
        return {
            Preset.MINIMO: "Mínimo",
            Preset.RECOMENDADO: "Recomendado",
            Preset.AGRESSIVO: "Agressivo",
        }[self]


@dataclass(frozen=True)
class DebloatItem:
    id: str
    label: str
    description: str
    # Appx Name used by Get-AppxPackage / Remove-AppxPackage.
    # None for privacy items that aren't Appx packages.
    appx_name: str | None
    # Which presets include this item.
    presets: frozenset[Preset]
    # Category for UI grouping.
    category: str  # "apps" or "privacy"
    # For privacy items: command to apply (list for argv-style, no shell quoting gotchas).
    apply_cmd: tuple[str, ...] | None = None


def _appx(
    item_id: str,
    label: str,
    description: str,
    appx_name: str,
    presets: set[Preset],
) -> DebloatItem:
    return DebloatItem(
        id=item_id,
        label=label,
        description=description,
        appx_name=appx_name,
        presets=frozenset(presets),
        category="apps",
    )


def _privacy(
    item_id: str,
    label: str,
    description: str,
    apply_cmd: tuple[str, ...],
    presets: set[Preset],
) -> DebloatItem:
    return DebloatItem(
        id=item_id,
        label=label,
        description=description,
        appx_name=None,
        presets=frozenset(presets),
        category="privacy",
        apply_cmd=apply_cmd,
    )


_ALL = {Preset.MINIMO, Preset.RECOMENDADO, Preset.AGRESSIVO}
_REC_AGG = {Preset.RECOMENDADO, Preset.AGRESSIVO}
_AGG = {Preset.AGRESSIVO}


# --- Appx packages (curated, ordered by category) ---

APPS: tuple[DebloatItem, ...] = (
    # Jogos e publicidade pura — todos os presets
    _appx("candy_friends", "Candy Crush Friends Saga",
          "Jogo publicitário pré-instalado pela Microsoft.",
          "king.com.CandyCrushFriends", _ALL),
    _appx("candy_saga", "Candy Crush Saga",
          "Jogo publicitário pré-instalado pela Microsoft.",
          "king.com.CandyCrushSaga", _ALL),
    _appx("solitaire", "Microsoft Solitaire Collection",
          "Pacote de Paciência com anúncios.",
          "Microsoft.MicrosoftSolitaireCollection", _ALL),
    _appx("bingnews", "Microsoft News",
          "Aplicativo de notícias Bing.",
          "Microsoft.BingNews", _ALL),
    _appx("bingweather", "Weather (Bing)",
          "Aplicativo de previsão do tempo Bing.",
          "Microsoft.BingWeather", _ALL),
    _appx("gethelp", "Get Help",
          "Chat de suporte Microsoft — raramente usado.",
          "Microsoft.GetHelp", _ALL),
    _appx("getstarted", "Tips / Get Started",
          "Aplicativo de dicas do Windows.",
          "Microsoft.Getstarted", _ALL),
    _appx("officehub", "Office Hub",
          "Landing page que empurra a compra do Office 365.",
          "Microsoft.MicrosoftOfficeHub", _ALL),
    _appx("clipchamp", "Clipchamp",
          "Editor de vídeo empurrado pela Microsoft.",
          "Clipchamp.Clipchamp", _ALL),

    # Xbox suite — recomendado em diante (quem joga quer manter)
    _appx("xbox_overlay", "Xbox Game Overlay",
          "Overlay do Xbox Game Bar (barra de ferramentas de jogos).",
          "Microsoft.XboxGameOverlay", _REC_AGG),
    _appx("xbox_gaming_overlay", "Xbox Gaming Overlay",
          "Game Bar principal.",
          "Microsoft.XboxGamingOverlay", _REC_AGG),
    _appx("xbox_identity", "Xbox Identity Provider",
          "Login Xbox em jogos e apps.",
          "Microsoft.XboxIdentityProvider", _REC_AGG),
    _appx("xbox_speech", "Xbox Speech To Text Overlay",
          "Overlay de transcrição do Xbox.",
          "Microsoft.XboxSpeechToTextOverlay", _REC_AGG),
    _appx("xbox_tcui", "Xbox TCUI",
          "UI compartilhada do Xbox.",
          "Microsoft.Xbox.TCUI", _REC_AGG),
    _appx("gaming_app", "Xbox App",
          "Aplicativo Xbox para compra/jogos PC Game Pass.",
          "Microsoft.GamingApp", _REC_AGG),

    # Teams Consumer / Your Phone
    _appx("teams_consumer", "Microsoft Teams (consumer)",
          "Teams pessoal (chat/Skype). Diferente do Teams corporativo.",
          "MicrosoftTeams", _REC_AGG),
    _appx("your_phone", "Phone Link / Your Phone",
          "Sincronização com Android; raramente usado.",
          "Microsoft.YourPhone", _REC_AGG),
    _appx("commsapps", "Mail e Calendar",
          "Apps Correio e Calendário nativos — descontinuados pela Microsoft.",
          "microsoft.windowscommunicationsapps", _REC_AGG),

    # Agressivo — utilitários que alguns usuários querem manter
    _appx("paint3d", "Paint 3D",
          "Editor 3D legado (não é o Paint clássico).",
          "Microsoft.MSPaint", _AGG),
    _appx("mixed_reality", "Mixed Reality Portal",
          "Portal VR do Windows — obsoleto.",
          "Microsoft.MixedReality.Portal", _AGG),
    _appx("threeD_viewer", "3D Viewer",
          "Visualizador 3D — quase nunca usado.",
          "Microsoft.Microsoft3DViewer", _AGG),
    _appx("maps", "Maps",
          "Mapas do Bing — quase sempre substituído pelo Google Maps web.",
          "Microsoft.WindowsMaps", _AGG),
    _appx("zune_music", "Groove Music / Windows Media Player moderno",
          "Player de música — streaming descontinuado.",
          "Microsoft.ZuneMusic", _AGG),
    _appx("zune_video", "Movies & TV",
          "Player de vídeo e loja de filmes.",
          "Microsoft.ZuneVideo", _AGG),
    _appx("people", "People",
          "Agenda de contatos antiga.",
          "Microsoft.People", _AGG),
    _appx("sound_recorder", "Gravador de Voz",
          "App de gravação básico.",
          "Microsoft.WindowsSoundRecorder", _AGG),
    _appx("feedback_hub", "Feedback Hub",
          "Canal de feedback da Microsoft.",
          "Microsoft.WindowsFeedbackHub", _AGG),
)


# --- Privacy / telemetry ---
# Keep these reversible — prefer registry tweaks over service deletion.

_PS = ("powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command")

PRIVACY: tuple[DebloatItem, ...] = (
    _privacy(
        "tel_disable",
        "Desabilitar telemetria (AllowTelemetry=0)",
        "Seta a política HKLM\\SOFTWARE\\Policies\\Microsoft\\Windows\\DataCollection"
        "\\AllowTelemetry = 0 (Security). Reduz coleta ao mínimo.",
        apply_cmd=_PS + (
            "New-Item -Path 'HKLM:\\SOFTWARE\\Policies\\Microsoft\\Windows\\DataCollection' "
            "-Force | Out-Null; "
            "Set-ItemProperty -Path 'HKLM:\\SOFTWARE\\Policies\\Microsoft\\Windows\\DataCollection' "
            "-Name 'AllowTelemetry' -Type DWord -Value 0",
        ),
        presets=_ALL,
    ),
    _privacy(
        "consumer_features",
        "Desabilitar Consumer Features (sugestões no Start)",
        "Desliga sugestões de apps/ofertas no menu Iniciar e lockscreen via "
        "HKLM\\...\\CloudContent\\DisableWindowsConsumerFeatures.",
        apply_cmd=_PS + (
            "New-Item -Path 'HKLM:\\SOFTWARE\\Policies\\Microsoft\\Windows\\CloudContent' "
            "-Force | Out-Null; "
            "Set-ItemProperty -Path 'HKLM:\\SOFTWARE\\Policies\\Microsoft\\Windows\\CloudContent' "
            "-Name 'DisableWindowsConsumerFeatures' -Type DWord -Value 1",
        ),
        presets=_ALL,
    ),
    _privacy(
        "ad_id",
        "Desabilitar ID de publicidade",
        "Impede apps de usar o ID de publicidade único do usuário.",
        apply_cmd=_PS + (
            "New-Item -Path 'HKLM:\\SOFTWARE\\Policies\\Microsoft\\Windows\\AdvertisingInfo' "
            "-Force | Out-Null; "
            "Set-ItemProperty -Path 'HKLM:\\SOFTWARE\\Policies\\Microsoft\\Windows\\AdvertisingInfo' "
            "-Name 'DisabledByGroupPolicy' -Type DWord -Value 1",
        ),
        presets=_ALL,
    ),
    _privacy(
        "ceip_tasks",
        "Desabilitar tasks do CEIP (Customer Experience Improvement Program)",
        "Desabilita tasks agendadas de coleta de dados do CEIP.",
        apply_cmd=_PS + (
            "$tasks = @("
            "'\\Microsoft\\Windows\\Customer Experience Improvement Program\\Consolidator',"
            "'\\Microsoft\\Windows\\Customer Experience Improvement Program\\UsbCeip',"
            "'\\Microsoft\\Windows\\Customer Experience Improvement Program\\KernelCeipTask'"
            "); foreach ($t in $tasks) { "
            "schtasks /Change /TN $t /DISABLE 2>&1 | Out-Null; Write-Host \"disabled $t\" }",
        ),
        presets=_REC_AGG,
    ),
    _privacy(
        "cortana_disable",
        "Desabilitar Cortana",
        "Seta HKLM\\...\\Windows Search\\AllowCortana=0 via política.",
        apply_cmd=_PS + (
            "New-Item -Path 'HKLM:\\SOFTWARE\\Policies\\Microsoft\\Windows\\Windows Search' "
            "-Force | Out-Null; "
            "Set-ItemProperty -Path 'HKLM:\\SOFTWARE\\Policies\\Microsoft\\Windows\\Windows Search' "
            "-Name 'AllowCortana' -Type DWord -Value 0",
        ),
        presets=_REC_AGG,
    ),
    _privacy(
        "bing_search_start",
        "Desabilitar Bing no menu Iniciar",
        "Remove resultados web do Bing no Start Menu search.",
        apply_cmd=_PS + (
            "New-Item -Path 'HKCU:\\SOFTWARE\\Policies\\Microsoft\\Windows\\Explorer' "
            "-Force | Out-Null; "
            "Set-ItemProperty -Path 'HKCU:\\SOFTWARE\\Policies\\Microsoft\\Windows\\Explorer' "
            "-Name 'DisableSearchBoxSuggestions' -Type DWord -Value 1",
        ),
        presets=_AGG,
    ),
)


ALL_ITEMS: tuple[DebloatItem, ...] = APPS + PRIVACY


def items_by_preset(preset: Preset) -> list[DebloatItem]:
    return [it for it in ALL_ITEMS if preset in it.presets]


def item_by_id(item_id: str) -> DebloatItem | None:
    return next((it for it in ALL_ITEMS if it.id == item_id), None)


# --- Runtime queries and command builders ---

def list_installed_appx_names(*, timeout: float = 60.0) -> set[str]:
    """Return the set of Appx Names currently installed for all users.

    Empty set on any failure — caller should treat as 'could not detect'.
    """
    script = (
        "Get-AppxPackage -AllUsers | "
        "Select-Object -ExpandProperty Name -Unique | "
        "ConvertTo-Json -Compress"
    )
    cmd = list(_PS) + [script]
    try:
        res = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout,
            creationflags=_CREATE_NO_WINDOW,
        )
    except subprocess.TimeoutExpired:
        _log.error("list_installed_appx_names: timeout")
        return set()
    except FileNotFoundError:
        _log.error("powershell not found")
        return set()

    if res.returncode != 0:
        _log.error("Get-AppxPackage failed: %s", (res.stderr or "").strip())
        return set()

    out = (res.stdout or "").strip()
    if not out:
        return set()
    try:
        data = json.loads(out)
    except json.JSONDecodeError:
        _log.exception("failed to parse Get-AppxPackage output")
        return set()

    if isinstance(data, str):
        return {data}
    if isinstance(data, list):
        return {str(x) for x in data}
    return set()


def remove_appx_cmd(appx_name: str) -> list[str]:
    """Build a CommandExecutor-ready command to remove an Appx for all users."""
    # Quoting: the appx Name is bounded by single quotes in PowerShell. Escape any
    # embedded single quote by doubling it (PowerShell rule).
    safe = appx_name.replace("'", "''")
    script = (
        f"Get-AppxPackage -AllUsers -Name '{safe}' | "
        "Remove-AppxPackage -AllUsers"
    )
    return list(_PS) + [script]
