"""Performance tab — v2.0a: power plan selector + Ultimate Performance unlock."""
from __future__ import annotations

import threading
from typing import TYPE_CHECKING

import customtkinter as ctk

import os
import subprocess

from src.features.performance import (
    QUICK_TOGGLES,
    PowerPlan,
    QuickToggle,
    StartupEntry,
    _startup_approved_target,
    get_startup_state,
    list_plans,
    list_startup_entries,
    read_toggle,
    set_active,
    set_startup_state,
    unlock_ultimate_performance,
    write_toggle,
)
from src.ui import design
from src.ui.components.collapsible import CollapsibleSection

if TYPE_CHECKING:
    from src.ui.main_window import MainWindow


def _plan_color(name: str) -> str:
    """Pick a color that hints at the plan's flavor (green = save, red = max)."""
    n = name.lower()
    if "economia" in n or "saver" in n:
        return design.SUCCESS
    if "ultimate" in n or "m\u00e1ximo" in n or "maximo" in n or "melhor" in n:
        return design.DANGER
    if "alto" in n or "high" in n:
        return design.WARNING
    if "equilibrado" in n or "balanced" in n:
        return design.INFO
    return design.PRIMARY


class PerformanceTab(ctk.CTkFrame):
    def __init__(self, master, *, main_window: "MainWindow") -> None:
        super().__init__(master, fg_color="transparent")
        self.main_window = main_window
        self._plan_rows: list[ctk.CTkFrame] = []

        ctk.CTkLabel(
            self,
            text=(
                "Perfis de energia do Windows e, em breve, toggles rápidos "
                "(Game Mode, efeitos visuais) e programas de inicialização."
            ),
            wraplength=900, justify="left",
            font=design.font_body(), text_color=design.MUTED_TEXT,
        ).pack(anchor="w", padx=design.SP_LG, pady=(design.SP_MD, design.SP_SM))

        scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        scroll.pack(side="top", fill="both", expand=True, padx=design.SP_MD, pady=design.SP_XS)

        self._power_section = CollapsibleSection(
            scroll,
            title="Plano de energia",
            icon=design.ICON_PERFORMANCE,
            initially_open=True,
        )
        self._power_section.pack(fill="x")

        self._power_body = ctk.CTkFrame(self._power_section.body, fg_color="transparent")
        self._power_body.pack(fill="x")

        # --- Ajustes rápidos section ---
        self._toggle_vars: dict[str, ctk.BooleanVar] = {}
        toggles_section = CollapsibleSection(
            scroll, title="Ajustes rápidos", icon="🎛",
            initially_open=True, count=len(QUICK_TOGGLES),
        )
        toggles_section.pack(fill="x")
        for toggle in QUICK_TOGGLES:
            self._build_toggle_row(toggles_section.body, toggle)

        # --- Startup entries section ---
        self._startup_rows: list[ctk.CTkFrame] = []
        self._startup_section = CollapsibleSection(
            scroll, title="Programas de inicialização", icon="🚀",
            initially_open=False,
        )
        self._startup_section.pack(fill="x")

        intro = ctk.CTkLabel(
            self._startup_section.body,
            text=(
                "Programas que rodam no login. Esta listagem é informativa — "
                "para habilitar/desabilitar, abra as Configurações ou o Task Manager."
            ),
            wraplength=880, justify="left",
            font=design.font_caption(), text_color=design.MUTED_TEXT,
        )
        intro.pack(anchor="w", padx=design.SP_LG, pady=(design.SP_SM, design.SP_XS))

        startup_header = ctk.CTkFrame(self._startup_section.body, fg_color="transparent")
        startup_header.pack(fill="x", padx=design.SP_MD, pady=(0, design.SP_XS))
        self._startup_refresh_btn = ctk.CTkButton(
            startup_header, text="🔄  Atualizar", width=130,
            command=self._refresh_startup,
        )
        self._startup_refresh_btn.pack(side="left", padx=design.SP_XS)
        ctk.CTkButton(
            startup_header, text="⚙  Abrir Configurações", width=180,
            command=self._open_settings_startup,
        ).pack(side="left", padx=design.SP_XS)
        ctk.CTkButton(
            startup_header, text="🧰  Task Manager", width=150,
            command=self._open_task_manager,
        ).pack(side="left", padx=design.SP_XS)

        self._startup_body = ctk.CTkFrame(
            self._startup_section.body, fg_color="transparent"
        )
        self._startup_body.pack(fill="x", padx=design.SP_MD)

        self.after(600, self._refresh_startup)

        footer = ctk.CTkFrame(self._power_section.body, fg_color="transparent")
        footer.pack(fill="x", pady=(design.SP_SM, 0))

        self._refresh_btn = ctk.CTkButton(
            footer, text="🔄  Atualizar", width=130, command=self.refresh,
        )
        self._refresh_btn.pack(side="left", padx=design.SP_XS)

        self._unlock_btn = ctk.CTkButton(
            footer, text="🔓  Desbloquear Ultimate Performance", width=260,
            fg_color=design.DANGER, hover_color=design.DANGER_HOVER,
            command=self._on_unlock_ultimate,
        )
        # packed only if Ultimate is absent; see _render

        self._status_var = ctk.StringVar(value="Carregando…")
        ctk.CTkLabel(
            footer, textvariable=self._status_var,
            font=design.font_caption(), text_color=design.MUTED_TEXT,
        ).pack(side="right", padx=design.SP_MD)

        self.after(200, self.refresh)

    # ---------- data ----------

    def refresh(self) -> None:
        self._status_var.set("Consultando powercfg…")
        self._refresh_btn.configure(state="disabled")

        def worker() -> None:
            plans = list_plans()
            self.after(0, self._render, plans)

        threading.Thread(target=worker, daemon=True, name="powercfg-list").start()

    def _render(self, plans: list[PowerPlan]) -> None:
        for row in self._plan_rows:
            row.destroy()
        self._plan_rows.clear()

        if not plans:
            ctk.CTkLabel(
                self._power_body,
                text="Nenhum plano detectado — powercfg falhou.",
                text_color=design.DANGER,
            ).pack(padx=design.SP_LG, pady=design.SP_MD)
            self._refresh_btn.configure(state="normal")
            self._status_var.set("Falha ao listar planos")
            return

        for plan in plans:
            self._plan_rows.append(self._build_plan_row(plan))

        has_ultimate = any(
            "ultimate" in p.name.lower() or "m\u00e1ximo" in p.name.lower()
            for p in plans
        )
        if has_ultimate:
            self._unlock_btn.pack_forget()
        else:
            self._unlock_btn.pack(side="left", padx=design.SP_MD)

        self._refresh_btn.configure(state="normal")
        self._status_var.set(f"{len(plans)} planos detectados")

    def _build_plan_row(self, plan: PowerPlan) -> ctk.CTkFrame:
        row = ctk.CTkFrame(
            self._power_body,
            corner_radius=8,
            border_width=2,
            border_color=_plan_color(plan.name) if plan.is_active else design.CARD_BORDER,
            fg_color=design.CARD_BG,
        )
        row.pack(fill="x", padx=2, pady=3)

        top = ctk.CTkFrame(row, fg_color="transparent")
        top.pack(fill="x", padx=design.SP_LG, pady=(design.SP_MD, 0))

        ctk.CTkLabel(
            top, text=design.ICON_PERFORMANCE, font=design.font_icon(22), width=32,
            text_color=_plan_color(plan.name),
        ).pack(side="left", padx=(0, design.SP_MD))

        ctk.CTkLabel(
            top, text=plan.name, font=design.font_h3(), anchor="w",
        ).pack(side="left")

        if plan.is_active:
            ctk.CTkLabel(
                top, text="✓ Ativo", fg_color=design.SUCCESS, text_color="white",
                corner_radius=12, padx=10, font=design.font_caption(),
            ).pack(side="right")

        ctk.CTkLabel(
            row, text=plan.guid, font=design.font_mono(10),
            text_color=design.SUBTLE_TEXT, anchor="w",
        ).pack(fill="x", padx=design.SP_LG + 32 + design.SP_SM, pady=(design.SP_XS, 0))

        footer = ctk.CTkFrame(row, fg_color="transparent")
        footer.pack(fill="x", padx=design.SP_LG, pady=(design.SP_SM, design.SP_MD))
        activate_btn = ctk.CTkButton(
            footer,
            text="Plano ativo" if plan.is_active else f"{design.ICON_PLAY}  Ativar",
            width=130,
            state="disabled" if plan.is_active else "normal",
            command=lambda g=plan.guid, n=plan.name: self._on_activate(g, n),
        )
        activate_btn.pack(side="right")
        return row

    # ---------- actions ----------

    def _on_activate(self, guid: str, name: str) -> None:
        console = self.main_window.console
        console.append_line(f"\n[performance] ativando plano: {name}")

        def worker() -> None:
            ok, msg = set_active(guid)
            console.append_line(f"[performance] {msg}")
            self.after(0, self.refresh)

        threading.Thread(target=worker, daemon=True, name="powercfg-setactive").start()

    def _on_unlock_ultimate(self) -> None:
        console = self.main_window.console
        console.append_line("\n[performance] desbloqueando Ultimate Performance…")
        self._unlock_btn.configure(state="disabled", text="Desbloqueando…")

        def worker() -> None:
            ok, msg = unlock_ultimate_performance()
            console.append_line(f"[performance] {msg}")
            self.after(0, self.refresh)
            self.after(0, lambda: self._unlock_btn.configure(
                state="normal", text="🔓  Desbloquear Ultimate Performance",
            ))

        threading.Thread(target=worker, daemon=True, name="powercfg-unlock").start()

    # ---------- Quick toggles ----------

    def _build_toggle_row(self, parent, toggle: QuickToggle) -> None:
        row = ctk.CTkFrame(
            parent, corner_radius=6, border_width=1,
            border_color=design.CARD_BORDER, fg_color=design.CARD_BG,
        )
        row.pack(fill="x", padx=design.SP_XS, pady=2)

        top = ctk.CTkFrame(row, fg_color="transparent")
        top.pack(fill="x", padx=design.SP_LG, pady=(design.SP_SM, 0))

        ctk.CTkLabel(
            top, text="🎛", font=design.font_icon(18), width=28,
        ).pack(side="left", padx=(0, design.SP_SM))

        ctk.CTkLabel(
            top, text=toggle.label, font=design.font_body("bold"), anchor="w",
        ).pack(side="left")

        var = ctk.BooleanVar(value=read_toggle(toggle))
        self._toggle_vars[toggle.id] = var
        switch = ctk.CTkSwitch(
            top, text="", variable=var,
            command=lambda t=toggle: self._on_toggle(t),
        )
        switch.pack(side="right", padx=design.SP_SM)

        ctk.CTkLabel(
            row, text=toggle.description, wraplength=700, justify="left",
            anchor="w", font=design.font_caption(), text_color=design.MUTED_TEXT,
        ).pack(fill="x", padx=(design.SP_LG + 28 + design.SP_SM, design.SP_LG),
                pady=(0, design.SP_SM))

    def _on_toggle(self, toggle: QuickToggle) -> None:
        var = self._toggle_vars.get(toggle.id)
        if var is None:
            return
        desired = bool(var.get())
        console = self.main_window.console

        def worker() -> None:
            ok, msg = write_toggle(toggle, desired)
            console.append_line(f"[performance] {msg}")
            if not ok:
                actual = read_toggle(toggle)
                self.after(0, var.set, actual)

        threading.Thread(target=worker, daemon=True, name="quick-toggle").start()

    # ---------- Startup listing ----------

    def _refresh_startup(self) -> None:
        self._startup_refresh_btn.configure(state="disabled")

        def worker() -> None:
            entries = list_startup_entries()
            self.after(0, self._render_startup, entries)

        threading.Thread(target=worker, daemon=True, name="startup-list").start()

    def _render_startup(self, entries: list[StartupEntry]) -> None:
        for row in self._startup_rows:
            row.destroy()
        self._startup_rows.clear()

        if not entries:
            lbl = ctk.CTkLabel(
                self._startup_body,
                text="Nenhuma entrada de startup detectada (ou falha ao consultar).",
                text_color=design.MUTED_TEXT,
            )
            lbl.pack(padx=design.SP_LG, pady=design.SP_MD)
            self._startup_rows.append(lbl)
        else:
            self._startup_section.set_count(len(entries))
            for entry in entries:
                self._startup_rows.append(self._build_startup_row(entry))

        self._startup_refresh_btn.configure(state="normal")

    def _build_startup_row(self, entry: StartupEntry) -> ctk.CTkFrame:
        row = ctk.CTkFrame(
            self._startup_body, corner_radius=6, border_width=1,
            border_color=design.CARD_BORDER, fg_color=design.CARD_BG,
        )
        row.pack(fill="x", padx=design.SP_XS, pady=2)

        top = ctk.CTkFrame(row, fg_color="transparent")
        top.pack(fill="x", padx=design.SP_LG, pady=(design.SP_SM, 0))

        ctk.CTkLabel(
            top, text="🚀", font=design.font_icon(16), width=24,
        ).pack(side="left", padx=(0, design.SP_SM))
        ctk.CTkLabel(
            top, text=entry.name, font=design.font_body("bold"), anchor="w",
        ).pack(side="left")

        togglable = _startup_approved_target(entry) is not None

        if togglable:
            var = ctk.BooleanVar(value=get_startup_state(entry))
            switch = ctk.CTkSwitch(
                top, text="", variable=var,
                command=lambda e=entry, v=var: self._on_startup_toggle(e, v),
            )
            switch.pack(side="right", padx=design.SP_SM)
        else:
            ctk.CTkLabel(
                top, text="sistema (não togglável)", fg_color=design.MUTED_TEXT,
                text_color="white", corner_radius=12, padx=10,
                font=design.font_caption(),
            ).pack(side="right", padx=design.SP_SM)

        short_loc = entry.location.rsplit("\\", 1)[-1] or entry.location
        ctk.CTkLabel(
            top, text=short_loc, font=design.font_caption(),
            text_color=design.SUBTLE_TEXT,
        ).pack(side="right", padx=design.SP_SM)

        cmd_text = entry.command if len(entry.command) <= 140 else entry.command[:137] + "…"
        ctk.CTkLabel(
            row, text=cmd_text, font=design.font_mono(10),
            text_color=design.MUTED_TEXT, anchor="w", justify="left",
            wraplength=820,
        ).pack(fill="x", padx=(design.SP_LG + 24 + design.SP_SM, design.SP_LG),
                pady=(0, design.SP_SM))
        return row

    def _on_startup_toggle(self, entry: StartupEntry, var: ctk.BooleanVar) -> None:
        desired = bool(var.get())
        console = self.main_window.console

        def worker() -> None:
            ok, msg = set_startup_state(entry, desired)
            console.append_line(f"[startup] {msg}")
            if not ok:
                # Revert switch
                actual = get_startup_state(entry)
                self.after(0, var.set, actual)

        threading.Thread(target=worker, daemon=True, name="startup-toggle").start()

    def _open_settings_startup(self) -> None:
        try:
            os.startfile("ms-settings:startupapps")
        except OSError:
            subprocess.Popen(["cmd", "/c", "start", "ms-settings:startupapps"], shell=False)
        self.main_window.console.append_line("[performance] Configurações > Startup apps aberta")

    def _open_task_manager(self) -> None:
        try:
            subprocess.Popen(["taskmgr"])
        except OSError:
            self.main_window.console.append_line("[performance] falha ao abrir Task Manager")
            return
        self.main_window.console.append_line("[performance] Task Manager aberto")
