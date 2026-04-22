"""Design system: color tokens, typography, spacing, icons.

Everything visual should flow through this module so the look is consistent and
themable from one place. CustomTkinter handles dark/light mode automatically
when tuples (light, dark) are provided to widget colors.
"""
from __future__ import annotations

import customtkinter as ctk

# =============================================================================
# Colors
# =============================================================================

# Risk levels (match src.features.system_tools.RiskLevel.color but defined here
# so the UI layer doesn't depend on features. Kept in sync by convention.)
RISK_SAFE = "#2ea043"
RISK_LOW = "#3fb950"
RISK_MEDIUM = "#d29922"
RISK_HIGH = "#f85149"

# Semantic colors
PRIMARY = "#1f6feb"
PRIMARY_HOVER = "#1a5fd3"
SUCCESS = "#2ea043"
WARNING = "#d29922"
DANGER = "#d13438"
DANGER_HOVER = "#a32b2e"
INFO = "#3b82f6"

# Neutral palettes (tuples = (light mode, dark mode))
MUTED_TEXT = ("#555555", "#9a9a9a")
SUBTLE_TEXT = ("#777777", "#777777")
CARD_BG = ("#fafafa", "#242424")
CARD_BORDER = ("#e0e0e0", "#3a3a3a")
SECTION_HEADER_BG = ("#f5f5f5", "#1e1e1e")
CODE_BG = ("#f0f0f0", "#1a1a1a")


def risk_color(level: str) -> str:
    return {
        "safe": RISK_SAFE,
        "low": RISK_LOW,
        "medium": RISK_MEDIUM,
        "high": RISK_HIGH,
    }.get(level, MUTED_TEXT[0])


# =============================================================================
# Typography
# =============================================================================

def font_h1() -> ctk.CTkFont:
    return ctk.CTkFont(size=20, weight="bold")


def font_h2() -> ctk.CTkFont:
    return ctk.CTkFont(size=15, weight="bold")


def font_h3() -> ctk.CTkFont:
    return ctk.CTkFont(size=13, weight="bold")


def font_body(weight: str = "normal") -> ctk.CTkFont:
    return ctk.CTkFont(size=12, weight=weight)


def font_caption() -> ctk.CTkFont:
    return ctk.CTkFont(size=10)


def font_mono(size: int = 10) -> tuple[str, int]:
    return ("Consolas", size)


def font_icon(size: int = 18) -> tuple[str, int]:
    """Segoe UI Emoji supports the color-emoji glyphs we use across the app."""
    return ("Segoe UI Emoji", size)


# =============================================================================
# Spacing (pixels)
# =============================================================================
SP_XS = 2
SP_SM = 4
SP_MD = 8
SP_LG = 12
SP_XL = 16
SP_XXL = 24


# =============================================================================
# Icons (Unicode symbols)
# =============================================================================
# Using Unicode symbols lets us avoid shipping an icon font. On Windows 11 the
# Segoe UI Emoji font renders these as clean color glyphs. Keep labels text-based
# (no emoji) so Fluent design fonts render the text crisp while emoji handles icons.

# System Tools families
ICON_CHKDSK = "💽"
ICON_SFC = "🛡️"
ICON_DISM = "🧬"
ICON_NETWORK = "🌐"

# Debloat
ICON_APP = "📦"
ICON_APP_REMOVED = "🚫"
ICON_PRIVACY = "🔒"
ICON_TELEMETRY = "📡"

# Cleanup
ICON_TEMP = "🗂️"
ICON_PREFETCH = "⚡"
ICON_WU_CACHE = "🔄"
ICON_COMPONENT = "🗃️"
ICON_RECYCLE = "🗑️"

# Generic
ICON_INFO = "ℹ️"
ICON_PERFORMANCE = "⚡"
ICON_SUCCESS = "✅"
ICON_ERROR = "❌"
ICON_WARNING = "⚠️"
ICON_RUNNING = "⏳"
ICON_REBOOT = "🔁"
ICON_SLOW = "🐢"
ICON_PLAY = "▶"
ICON_DRY_RUN = "👁"


# =============================================================================
# Status descriptors (used by TaskCard to show last-run result)
# =============================================================================

class Status:
    IDLE = "idle"
    RUNNING = "running"
    OK = "ok"
    FAIL = "fail"
    CANCELLED = "cancelled"


STATUS_ICONS = {
    Status.IDLE: "",
    Status.RUNNING: ICON_RUNNING,
    Status.OK: ICON_SUCCESS,
    Status.FAIL: ICON_ERROR,
    Status.CANCELLED: "⏹",
}

STATUS_COLORS = {
    Status.IDLE: MUTED_TEXT,
    Status.RUNNING: (PRIMARY, PRIMARY),
    Status.OK: (SUCCESS, SUCCESS),
    Status.FAIL: (DANGER, DANGER),
    Status.CANCELLED: MUTED_TEXT,
}


# =============================================================================
# Mappings task_id → icon / family (UI-only concern — derived from id prefix)
# =============================================================================

def icon_for_system_task(task_id: str) -> str:
    if task_id.startswith("chkdsk"):
        return ICON_CHKDSK
    if task_id.startswith("sfc"):
        return ICON_SFC
    if task_id.startswith("dism"):
        return ICON_DISM
    if task_id.startswith("net_"):
        return ICON_NETWORK
    return "•"


def family_for_system_task(task_id: str) -> str:
    if task_id.startswith("chkdsk"):
        return "CHKDSK — Verificação de disco"
    if task_id.startswith("sfc"):
        return "SFC — System File Checker"
    if task_id.startswith("dism"):
        return "DISM — Integridade da imagem"
    if task_id.startswith("net_"):
        return "Rede — Resets e flush"
    return "Outros"


# Ordered list of families for rendering.
SYSTEM_FAMILIES_ORDER = (
    "CHKDSK — Verificação de disco",
    "SFC — System File Checker",
    "DISM — Integridade da imagem",
    "Rede — Resets e flush",
)


CLEANUP_ICONS = {
    "temp": ICON_TEMP,
    "prefetch": ICON_PREFETCH,
    "wu_cache": ICON_WU_CACHE,
    "component_store": ICON_COMPONENT,
    "recycle_bin": ICON_RECYCLE,
}


DEBLOAT_CATEGORY_ICONS = {
    "apps": ICON_APP,
    "privacy": ICON_PRIVACY,
}
