"""Win32 uninstaller: lista e desinstala apps a partir das chaves Uninstall do registry.

Lê o mesmo conjunto de lugares que a janela "Programs and Features" do Windows:
  HKLM\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Uninstall
  HKLM\\SOFTWARE\\WOW6432Node\\Microsoft\\Windows\\CurrentVersion\\Uninstall
  HKCU\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Uninstall

Respeita as flags `SystemComponent` e `ParentKeyName` (updates/patches) para não
listar componentes internos e KBs do Windows.
"""
from __future__ import annotations

import logging
import winreg
from dataclasses import dataclass

_log = logging.getLogger("pc_optimizer.uninstaller")


_BASES: tuple[tuple[int, str, str], ...] = (
    (winreg.HKEY_LOCAL_MACHINE,
     r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall", "HKLM"),
    (winreg.HKEY_LOCAL_MACHINE,
     r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall", "HKLM (32-bit)"),
    (winreg.HKEY_CURRENT_USER,
     r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall", "HKCU"),
)


@dataclass(frozen=True)
class InstalledApp:
    key_path: str              # registry subkey — unique id
    name: str
    version: str
    publisher: str
    install_date: str          # DD/MM/YYYY or ""
    uninstall_string: str
    quiet_uninstall_string: str
    install_location: str
    estimated_size_kb: int     # 0 if unknown
    source: str                # "HKLM" / "HKLM (32-bit)" / "HKCU"

    @property
    def is_microsoft(self) -> bool:
        p = self.publisher.lower()
        n = self.name.lower()
        return any(s in p for s in ("microsoft", "microsoft corporation")) or n.startswith("microsoft ")

    @property
    def size_mb(self) -> float:
        return self.estimated_size_kb / 1024 if self.estimated_size_kb else 0.0


def _read_value(key, name: str, default=None):
    try:
        v, _ = winreg.QueryValueEx(key, name)
        return v
    except FileNotFoundError:
        return default
    except OSError:
        return default


def _parse_install_date(s) -> str:
    if not s:
        return ""
    s = str(s)
    if len(s) == 8 and s.isdigit():
        return f"{s[6:8]}/{s[4:6]}/{s[:4]}"
    return s


def _read_app(hive: int, base: str, source_label: str, subkey_name: str) -> InstalledApp | None:
    try:
        with winreg.OpenKey(hive, rf"{base}\{subkey_name}", 0, winreg.KEY_READ) as k:
            name = _read_value(k, "DisplayName")
            if not name:
                return None
            # Filter out system components and updates to match Programs & Features behavior.
            if _read_value(k, "SystemComponent", 0) == 1:
                return None
            if _read_value(k, "ParentKeyName") or _read_value(k, "ParentDisplayName"):
                return None

            uninstall = _read_value(k, "UninstallString") or ""
            if not uninstall.strip():
                return None

            return InstalledApp(
                key_path=f"{source_label}:{subkey_name}",
                name=str(name).strip(),
                version=str(_read_value(k, "DisplayVersion") or "").strip(),
                publisher=str(_read_value(k, "Publisher") or "").strip(),
                install_date=_parse_install_date(_read_value(k, "InstallDate")),
                uninstall_string=str(uninstall).strip(),
                quiet_uninstall_string=str(_read_value(k, "QuietUninstallString") or "").strip(),
                install_location=str(_read_value(k, "InstallLocation") or "").strip(),
                estimated_size_kb=int(_read_value(k, "EstimatedSize") or 0),
                source=source_label,
            )
    except (FileNotFoundError, OSError):
        return None


def list_installed_apps() -> list[InstalledApp]:
    """Read all Uninstall hives and return the deduped list of apps."""
    apps: list[InstalledApp] = []
    seen_names: set[tuple[str, str]] = set()

    for hive, base, label in _BASES:
        try:
            with winreg.OpenKey(hive, base, 0, winreg.KEY_READ) as root:
                i = 0
                while True:
                    try:
                        sub = winreg.EnumKey(root, i)
                    except OSError:
                        break
                    i += 1
                    app = _read_app(hive, base, label, sub)
                    if app is None:
                        continue
                    # dedupe on (name, version) — apps often appear twice across 32/64 hives
                    key = (app.name.lower(), app.version)
                    if key in seen_names:
                        continue
                    seen_names.add(key)
                    apps.append(app)
        except FileNotFoundError:
            continue
        except OSError:
            _log.exception("falha ao enumerar %s", base)

    apps.sort(key=lambda a: a.name.lower())
    return apps


def uninstall_command(app: InstalledApp) -> str:
    """Pick the best command to run for uninstalling.

    Prefer QuietUninstallString (silent) when available. Otherwise return
    UninstallString as-is (may prompt the user via the vendor uninstaller).
    """
    return app.quiet_uninstall_string or app.uninstall_string
