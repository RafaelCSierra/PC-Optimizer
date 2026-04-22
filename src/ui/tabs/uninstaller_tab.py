"""Uninstaller tab: lista os apps Win32 instalados e dispara o uninstall string.

Design:
  - Rows são construídas UMA VEZ em `_rebuild_rows`, ordenadas por nome.
  - Filtros (search + hide MS) não destroem rows: apenas `pack_forget`/`pack`
    (mantendo `before=` para preservar ordem). Isso evita um bug conhecido do
    CTkScrollableFrame em que destroir/recriar muitas rows deixa o scroll em
    estado inconsistente.
  - Ordenação alternativa (tamanho/data) não destrói: ela re-`pack(before=)`
    os widgets existentes na nova ordem.
"""
from __future__ import annotations

import threading
from typing import TYPE_CHECKING

import customtkinter as ctk

from src.features.uninstaller import InstalledApp, list_installed_apps, uninstall_command
from src.ui import design
from src.ui.components.confirm_dialog import ConfirmDialog

if TYPE_CHECKING:
    from src.ui.main_window import MainWindow


SORT_OPTIONS = (
    "Nome (A-Z)",
    "Tamanho (maior primeiro)",
    "Data de instalação (recente primeiro)",
)


def _sort_key(option: str):
    if option == "Tamanho (maior primeiro)":
        return lambda a: (-a.estimated_size_kb, a.name.lower())
    if option == "Data de instalação (recente primeiro)":
        def key(a: InstalledApp):
            if a.install_date and len(a.install_date) >= 10:
                # install_date comes as DD/MM/YYYY
                y, m, d = a.install_date[6:10], a.install_date[3:5], a.install_date[:2]
                return (0, f"{y}{m}{d}", a.name.lower())
            return (1, "", a.name.lower())  # undated apps sink to bottom
        return key
    return lambda a: a.name.lower()


class UninstallerTab(ctk.CTkFrame):
    def __init__(self, master, *, main_window: "MainWindow") -> None:
        super().__init__(master, fg_color="transparent")
        self.main_window = main_window
        self._all_apps: list[InstalledApp] = []
        # Persistent row widgets, keyed by app.key_path so we can dedupe/update.
        self._rows_by_key: dict[str, ctk.CTkFrame] = {}
        self._apps_by_key: dict[str, InstalledApp] = {}

        self._hide_ms_var = ctk.BooleanVar(value=True)
        self._search_var = ctk.StringVar(value="")
        self._sort_var = ctk.StringVar(value=SORT_OPTIONS[0])

        self._build_header()
        self._scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self._scroll.pack(side="top", fill="both", expand=True,
                          padx=design.SP_MD, pady=design.SP_XS)

        self._empty_label = ctk.CTkLabel(
            self._scroll,
            text="Carregando lista de aplicativos…",
            text_color=design.MUTED_TEXT,
        )
        self._empty_label.pack(pady=design.SP_XL)

        self.after(200, self.refresh)

    def _build_header(self) -> None:
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(side="top", fill="x", padx=design.SP_MD, pady=(design.SP_MD, design.SP_XS))

        row1 = ctk.CTkFrame(header, fg_color="transparent")
        row1.pack(fill="x")
        self._refresh_btn = ctk.CTkButton(
            row1, text="🔄  Atualizar lista", width=160, command=self.refresh,
        )
        self._refresh_btn.pack(side="left", padx=design.SP_XS)

        ctk.CTkEntry(
            row1, textvariable=self._search_var, width=280,
            placeholder_text="Buscar por nome ou publisher…",
        ).pack(side="left", padx=design.SP_MD, fill="x", expand=True)
        self._search_var.trace_add("write", lambda *_: self._apply_filter_sort())

        self._count_var = ctk.StringVar(value="")
        ctk.CTkLabel(
            row1, textvariable=self._count_var,
            font=design.font_caption(), text_color=design.MUTED_TEXT,
        ).pack(side="right", padx=design.SP_MD)

        row2 = ctk.CTkFrame(header, fg_color="transparent")
        row2.pack(fill="x", pady=(design.SP_SM, 0))

        ctk.CTkCheckBox(
            row2, text="Ocultar apps da Microsoft",
            variable=self._hide_ms_var, command=self._apply_filter_sort,
        ).pack(side="left", padx=design.SP_XS)

        ctk.CTkLabel(
            row2, text="   Ordenar por:", font=design.font_caption(),
        ).pack(side="left", padx=(design.SP_LG, design.SP_XS))
        ctk.CTkOptionMenu(
            row2, variable=self._sort_var, values=list(SORT_OPTIONS),
            width=260, command=lambda _: self._apply_filter_sort(),
        ).pack(side="left")

    # ---------- data lifecycle ----------

    def refresh(self) -> None:
        """Re-fetch the installed apps list. Rebuilds all rows from scratch."""
        self._refresh_btn.configure(state="disabled")
        self._count_var.set("Lendo registry…")

        def worker() -> None:
            apps = list_installed_apps()
            self.after(0, self._on_loaded, apps)

        threading.Thread(target=worker, daemon=True, name="uninstall-list").start()

    def _on_loaded(self, apps: list[InstalledApp]) -> None:
        self._all_apps = apps
        self._apps_by_key = {a.key_path: a for a in apps}
        self._rebuild_rows()
        self._refresh_btn.configure(state="normal")

    def _rebuild_rows(self) -> None:
        """Fully destroy + recreate all rows. Called only on refresh()."""
        for row in self._rows_by_key.values():
            row.pack_forget()
            row.destroy()
        self._rows_by_key.clear()
        self._empty_label.pack_forget()

        if not self._all_apps:
            self._empty_label.configure(text="Nenhum app listado pelo registry.")
            self._empty_label.pack(pady=design.SP_XL)
            return

        import logging
        log = logging.getLogger("pc_optimizer.uninstaller_tab")
        failed = 0
        for app in sorted(self._all_apps, key=lambda a: a.name.lower()):
            try:
                row = self._build_row(app)
                self._rows_by_key[app.key_path] = row
            except Exception:
                log.exception("_build_row failed for %s", app.name)
                failed += 1
        if failed:
            self.main_window.console.append_line(
                f"[uninstaller] {failed} rows falharam ao construir — ver app.log"
            )
        self._apply_filter_sort()

    def _apply_filter_sort(self) -> None:
        """Show/hide rows based on filter+search, and reorder per sort option."""
        term = self._search_var.get().strip().lower()
        hide_ms = self._hide_ms_var.get()
        key_fn = _sort_key(self._sort_var.get())

        visible_apps: list[InstalledApp] = []
        for app in self._all_apps:
            if hide_ms and app.is_microsoft:
                continue
            if term and term not in app.name.lower() and term not in app.publisher.lower():
                continue
            visible_apps.append(app)
        visible_apps.sort(key=key_fn)

        for row in self._rows_by_key.values():
            row.pack_forget()
        for app in visible_apps:
            row = self._rows_by_key.get(app.key_path)
            if row is not None:
                row.pack(fill="x", padx=design.SP_XS, pady=2)

        total_mb = sum(a.size_mb for a in visible_apps)
        self._count_var.set(
            f"{len(visible_apps)} apps · {total_mb:.0f} MB estimados"
            if total_mb else f"{len(visible_apps)} apps"
        )

        if not visible_apps and self._all_apps:
            self._empty_label.configure(
                text="Nenhum app corresponde aos filtros atuais.",
            )
            self._empty_label.pack(pady=design.SP_XL)
        else:
            self._empty_label.pack_forget()

    # ---------- row factory ----------

    def _build_row(self, app: InstalledApp) -> ctk.CTkFrame:
        """Minimal single-line row with a fixed height.

        Keeping the structure flat (no nested frames) sidesteps CustomTkinter
        ScrollableFrame layout quirks we hit with multi-level packing.
        """
        row = ctk.CTkFrame(
            self._scroll, corner_radius=6, border_width=1,
            border_color=design.CARD_BORDER, fg_color=design.CARD_BG,
            height=44,
        )
        row.pack_propagate(False)

        ctk.CTkLabel(
            row, text=design.ICON_APP, font=design.font_icon(16), width=24,
        ).pack(side="left", padx=(design.SP_LG, design.SP_SM))

        title = app.name if not app.version else f"{app.name}  ·  {app.version}"
        ctk.CTkLabel(
            row, text=title, font=design.font_body("bold"), anchor="w",
        ).pack(side="left", padx=(0, design.SP_SM))

        ctk.CTkButton(
            row, text=f"{design.ICON_RECYCLE}  Desinstalar", width=130, height=28,
            fg_color=design.DANGER, hover_color=design.DANGER_HOVER,
            command=lambda a=app: self._on_uninstall(a),
        ).pack(side="right", padx=(design.SP_SM, design.SP_LG))

        if app.estimated_size_kb:
            ctk.CTkLabel(
                row, text=f"{app.size_mb:.0f} MB",
                fg_color=design.CODE_BG, text_color=design.MUTED_TEXT,
                corner_radius=12, padx=10, font=design.font_caption(),
            ).pack(side="right", padx=design.SP_XS)

        # Publisher in the middle, muted
        if app.publisher:
            ctk.CTkLabel(
                row, text=app.publisher, anchor="w",
                font=design.font_caption(), text_color=design.MUTED_TEXT,
            ).pack(side="right", padx=design.SP_SM)

        return row

    # ---------- action ----------

    def _on_uninstall(self, app: InstalledApp) -> None:
        cmd = uninstall_command(app)
        quiet = bool(app.quiet_uninstall_string)
        confirmed = ConfirmDialog.ask(
            self.main_window,
            title=f"Desinstalar {app.name}?",
            description=(
                "O app será removido via o desinstalador do próprio fornecedor. "
                + ("Este uninstaller suporta modo silencioso (sem prompts)."
                   if quiet else
                   "O uninstaller pode abrir uma janela pedindo confirmação — interaja com ela normalmente.")
            ),
            actions=[
                f"Nome: {app.name}",
                f"Versão: {app.version or '—'}",
                f"Publisher: {app.publisher or '—'}",
                f"Comando: {cmd[:140]}{'…' if len(cmd) > 140 else ''}",
            ],
            confirm_label="Desinstalar",
        )
        if not confirmed:
            self.main_window.console.append_line(f"[uninstaller] cancelado: {app.name}")
            return

        self.main_window.console.append_line(f"\n>>> Desinstalando {app.name}")
        self.main_window.run_cmd(
            cmd,
            on_done=lambda code, n=app.name: self.after(0, self._on_done, n, code),
        )

    def _on_done(self, app_name: str, code: int) -> None:
        status = "concluído" if code == 0 else f"terminou com exit code {code}"
        self.main_window.console.append_line(f"[uninstaller] {app_name}: {status}")
        self.after(500, self.refresh)
