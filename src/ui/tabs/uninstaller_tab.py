"""Uninstaller tab: lista os apps Win32 instalados e dispara o uninstall string."""
from __future__ import annotations

import threading
from typing import TYPE_CHECKING

import customtkinter as ctk

from src.features.uninstaller import InstalledApp, list_installed_apps, uninstall_command
from src.ui import design
from src.ui.components.confirm_dialog import ConfirmDialog

if TYPE_CHECKING:
    from src.ui.main_window import MainWindow


SORTS = {
    "Nome (A-Z)": lambda a: a.name.lower(),
    "Tamanho (maior primeiro)": lambda a: -a.estimated_size_kb,
    "Data de instalação (recente primeiro)": lambda a: a.install_date[-4:] + a.install_date[3:5] + a.install_date[:2] if a.install_date else "",
}


class UninstallerTab(ctk.CTkFrame):
    def __init__(self, master, *, main_window: "MainWindow") -> None:
        super().__init__(master, fg_color="transparent")
        self.main_window = main_window
        self._all_apps: list[InstalledApp] = []
        self._rows: list[ctk.CTkFrame] = []

        self._hide_ms_var = ctk.BooleanVar(value=True)
        self._search_var = ctk.StringVar(value="")
        self._sort_var = ctk.StringVar(value="Nome (A-Z)")

        self._build_header()
        self._scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self._scroll.pack(side="top", fill="both", expand=True, padx=design.SP_MD, pady=design.SP_XS)

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

        search = ctk.CTkEntry(
            row1, textvariable=self._search_var, width=280,
            placeholder_text="Buscar por nome ou publisher…",
        )
        search.pack(side="left", padx=design.SP_MD, fill="x", expand=True)
        self._search_var.trace_add("write", lambda *_: self._render())

        self._count_var = ctk.StringVar(value="")
        ctk.CTkLabel(
            row1, textvariable=self._count_var,
            font=design.font_caption(), text_color=design.MUTED_TEXT,
        ).pack(side="right", padx=design.SP_MD)

        row2 = ctk.CTkFrame(header, fg_color="transparent")
        row2.pack(fill="x", pady=(design.SP_SM, 0))

        ctk.CTkCheckBox(
            row2, text="Ocultar apps da Microsoft",
            variable=self._hide_ms_var, command=self._render,
        ).pack(side="left", padx=design.SP_XS)

        ctk.CTkLabel(
            row2, text="   Ordenar por:", font=design.font_caption(),
        ).pack(side="left", padx=(design.SP_LG, design.SP_XS))
        ctk.CTkOptionMenu(
            row2, variable=self._sort_var, values=list(SORTS.keys()),
            width=260, command=lambda _: self._render(),
        ).pack(side="left")

    # ---------- data ----------

    def refresh(self) -> None:
        self._refresh_btn.configure(state="disabled")
        self._count_var.set("Lendo registry…")

        def worker() -> None:
            apps = list_installed_apps()
            self.after(0, self._on_loaded, apps)

        threading.Thread(target=worker, daemon=True, name="uninstall-list").start()

    def _on_loaded(self, apps: list[InstalledApp]) -> None:
        self._all_apps = apps
        self._refresh_btn.configure(state="normal")
        self._render()

    def _filter_sort(self) -> list[InstalledApp]:
        term = self._search_var.get().strip().lower()
        apps = self._all_apps
        if self._hide_ms_var.get():
            apps = [a for a in apps if not a.is_microsoft]
        if term:
            apps = [
                a for a in apps
                if term in a.name.lower() or term in a.publisher.lower()
            ]
        key = SORTS.get(self._sort_var.get(), SORTS["Nome (A-Z)"])
        try:
            apps = sorted(apps, key=key)
        except TypeError:
            pass
        return apps

    def _render(self) -> None:
        for row in self._rows:
            row.destroy()
        self._rows.clear()
        self._empty_label.pack_forget()

        apps = self._filter_sort()
        total_mb = sum(a.size_mb for a in apps)
        self._count_var.set(
            f"{len(apps)} apps · {total_mb:.0f} MB estimados"
            if total_mb else f"{len(apps)} apps"
        )

        if not apps:
            self._empty_label.configure(
                text="Nenhum app corresponde aos filtros atuais.",
            )
            self._empty_label.pack(pady=design.SP_XL)
            return

        for app in apps:
            self._rows.append(self._build_row(app))

    def _build_row(self, app: InstalledApp) -> ctk.CTkFrame:
        row = ctk.CTkFrame(
            self._scroll, corner_radius=6, border_width=1,
            border_color=design.CARD_BORDER, fg_color=design.CARD_BG,
        )
        row.pack(fill="x", padx=design.SP_XS, pady=2)

        top = ctk.CTkFrame(row, fg_color="transparent")
        top.pack(fill="x", padx=design.SP_LG, pady=(design.SP_SM, 0))

        ctk.CTkLabel(
            top, text=design.ICON_APP, font=design.font_icon(18), width=28,
        ).pack(side="left", padx=(0, design.SP_SM))

        title = app.name if not app.version else f"{app.name}  ·  {app.version}"
        ctk.CTkLabel(
            top, text=title, font=design.font_body("bold"), anchor="w",
        ).pack(side="left")

        btn = ctk.CTkButton(
            top, text=f"{design.ICON_TRASH}  Desinstalar", width=140,
            fg_color=design.DANGER, hover_color=design.DANGER_HOVER,
            command=lambda a=app: self._on_uninstall(a),
        )
        btn.pack(side="right", padx=design.SP_SM)

        if app.estimated_size_kb:
            ctk.CTkLabel(
                top, text=f"{app.size_mb:.0f} MB",
                fg_color=design.CODE_BG, text_color=design.MUTED_TEXT,
                corner_radius=12, padx=10, font=design.font_caption(),
            ).pack(side="right", padx=design.SP_XS)

        meta_parts = []
        if app.publisher:
            meta_parts.append(app.publisher)
        if app.install_date:
            meta_parts.append(f"instalado {app.install_date}")
        meta_parts.append(f"fonte: {app.source}")
        if app.quiet_uninstall_string:
            meta_parts.append("silent disponível")

        ctk.CTkLabel(
            row, text=" · ".join(meta_parts), wraplength=900, justify="left",
            anchor="w", font=design.font_caption(), text_color=design.MUTED_TEXT,
        ).pack(fill="x",
               padx=(design.SP_LG + 28 + design.SP_SM, design.SP_LG),
               pady=(0, design.SP_SM))
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
        # Refresh the list — the app may have been removed
        self.after(500, self.refresh)
