"""Debloat Windows 11 tab: Appx removal + privacy toggles, grouped and styled."""
from __future__ import annotations

import threading
from typing import TYPE_CHECKING

import customtkinter as ctk

from src.core import restore_point
from src.features.debloat import (
    ALL_ITEMS,
    APPS,
    PRIVACY,
    DebloatItem,
    Preset,
    list_installed_appx_names,
    remove_appx_cmd,
)
from src.ui import design
from src.ui.components.collapsible import CollapsibleSection
from src.ui.components.confirm_dialog import ConfirmDialog

if TYPE_CHECKING:
    from src.ui.main_window import MainWindow


_PRESET_COLOR = {
    Preset.MINIMO: design.SUCCESS,
    Preset.RECOMENDADO: design.WARNING,
    Preset.AGRESSIVO: design.DANGER,
}


class DebloatTab(ctk.CTkFrame):
    def __init__(self, master, *, main_window: "MainWindow") -> None:
        super().__init__(master, fg_color="transparent")
        self.main_window = main_window
        self._vars: dict[str, ctk.BooleanVar] = {}
        self._checkboxes: dict[str, ctk.CTkCheckBox] = {}
        self._desc_labels: dict[str, ctk.CTkLabel] = {}
        self._installed: set[str] = set()
        self._applying = False
        self._apps_section: CollapsibleSection | None = None
        self._privacy_section: CollapsibleSection | None = None

        self._build_header()
        self._build_body()
        self._build_footer()

        self.after(200, self.refresh_installed)

    # ---------- layout ----------

    def _build_header(self) -> None:
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(side="top", fill="x", padx=design.SP_MD, pady=(design.SP_MD, design.SP_XS))

        row1 = ctk.CTkFrame(header, fg_color="transparent")
        row1.pack(fill="x")
        self._refresh_btn = ctk.CTkButton(
            row1, text="🔄  Atualizar lista", width=160, command=self.refresh_installed,
        )
        self._refresh_btn.pack(side="left")
        self._status_var = ctk.StringVar(value="Carregando pacotes instalados…")
        ctk.CTkLabel(
            row1, textvariable=self._status_var,
            font=design.font_body(), text_color=design.MUTED_TEXT, anchor="e",
        ).pack(side="right", padx=design.SP_SM)

        row2 = ctk.CTkFrame(header, fg_color="transparent")
        row2.pack(fill="x", pady=(design.SP_SM, 0))
        ctk.CTkLabel(
            row2, text="Aplicar preset:", font=design.font_body("bold"),
        ).pack(side="left", padx=(0, design.SP_SM))
        for preset in Preset:
            ctk.CTkButton(
                row2, text=preset.label, width=130,
                fg_color=_PRESET_COLOR[preset],
                hover_color=_PRESET_COLOR[preset],
                command=lambda p=preset: self._apply_preset(p),
            ).pack(side="left", padx=design.SP_XS)
        ctk.CTkButton(
            row2, text="Desmarcar todos", width=140,
            fg_color="gray40", hover_color="gray30",
            command=self._clear_selection,
        ).pack(side="left", padx=(design.SP_LG, 0))

    def _build_body(self) -> None:
        scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        scroll.pack(side="top", fill="both", expand=True, padx=design.SP_MD, pady=design.SP_XS)

        self._apps_section = CollapsibleSection(
            scroll, title="Apps pré-instalados", icon=design.ICON_APP,
            initially_open=True, count=len(APPS),
        )
        self._apps_section.pack(fill="x")
        for item in APPS:
            self._build_row(self._apps_section.body, item, design.ICON_APP)

        self._privacy_section = CollapsibleSection(
            scroll, title="Privacidade e telemetria", icon=design.ICON_PRIVACY,
            initially_open=True, count=len(PRIVACY),
        )
        self._privacy_section.pack(fill="x")
        for item in PRIVACY:
            self._build_row(self._privacy_section.body, item, design.ICON_PRIVACY)

    def _build_row(self, parent, item: DebloatItem, icon: str) -> None:
        row = ctk.CTkFrame(
            parent, corner_radius=6, border_width=1, border_color=design.CARD_BORDER,
            fg_color=design.CARD_BG,
        )
        row.pack(fill="x", padx=design.SP_XS, pady=2)

        top = ctk.CTkFrame(row, fg_color="transparent")
        top.pack(fill="x", padx=design.SP_LG, pady=(design.SP_SM, 0))

        ctk.CTkLabel(
            top, text=icon, font=design.font_icon(18), width=28,
        ).pack(side="left", padx=(0, design.SP_SM))

        var = ctk.BooleanVar(value=False)
        self._vars[item.id] = var
        cb = ctk.CTkCheckBox(
            top, text=item.label, variable=var,
            command=self._update_footer,
            font=design.font_body("bold"),
        )
        cb.pack(side="left", anchor="w")
        self._checkboxes[item.id] = cb

        desc = ctk.CTkLabel(
            row, text=item.description, wraplength=700, justify="left", anchor="w",
            font=design.font_caption(), text_color=design.MUTED_TEXT,
        )
        desc.pack(fill="x", padx=(design.SP_LG + 28 + design.SP_SM, design.SP_LG), pady=(0, design.SP_SM))
        self._desc_labels[item.id] = desc

    def _build_footer(self) -> None:
        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.pack(side="bottom", fill="x", padx=design.SP_MD, pady=design.SP_MD)

        self._selected_var = ctk.StringVar(value="0 itens selecionados")
        ctk.CTkLabel(
            footer, textvariable=self._selected_var,
            font=design.font_body(), text_color=design.MUTED_TEXT,
        ).pack(side="left")

        self._apply_btn = ctk.CTkButton(
            footer, text=f"{design.ICON_PLAY}  Aplicar seleção", height=38, width=180,
            fg_color=design.DANGER, hover_color=design.DANGER_HOVER,
            font=design.font_body("bold"),
            command=self._on_apply, state="disabled",
        )
        self._apply_btn.pack(side="right")

    # ---------- data flow ----------

    def refresh_installed(self) -> None:
        self._status_var.set("Consultando pacotes Appx…")
        self._refresh_btn.configure(state="disabled")

        def worker() -> None:
            names = list_installed_appx_names()
            self.after(0, self._apply_installed, names)

        threading.Thread(target=worker, daemon=True, name="appx-list").start()

    def _apply_installed(self, names: set[str]) -> None:
        self._installed = names
        missing = 0
        for item in APPS:
            cb = self._checkboxes.get(item.id)
            desc = self._desc_labels.get(item.id)
            if cb is None or desc is None:
                continue
            if item.appx_name and item.appx_name not in names:
                cb.configure(
                    state="disabled",
                    text=f"{item.label}  —  não instalado",
                    text_color=design.SUBTLE_TEXT,
                )
                missing += 1
            else:
                cb.configure(state="normal", text=item.label, text_color=None)

        self._refresh_btn.configure(state="normal")
        if names:
            self._status_var.set(
                f"{len(names)} pacotes detectados · {missing} itens já ausentes"
            )
        else:
            self._status_var.set("Falha ao listar pacotes — ver console")
            self.main_window.console.append_line(
                "[debloat] Get-AppxPackage não retornou dados — veja logs."
            )
        self._update_footer()

    def _apply_preset(self, preset: Preset) -> None:
        selected = 0
        for item in ALL_ITEMS:
            var = self._vars.get(item.id)
            cb = self._checkboxes.get(item.id)
            if var is None or cb is None:
                continue
            if cb.cget("state") == "disabled":
                var.set(False)
                continue
            should = preset in item.presets
            var.set(should)
            if should:
                selected += 1
        self._update_footer()
        self.main_window.console.append_line(
            f"[debloat] preset '{preset.label}' selecionou {selected} itens"
        )

    def _clear_selection(self) -> None:
        for var in self._vars.values():
            var.set(False)
        self._update_footer()

    def _collect_selected(self) -> list[DebloatItem]:
        out: list[DebloatItem] = []
        for item in ALL_ITEMS:
            var = self._vars.get(item.id)
            cb = self._checkboxes.get(item.id)
            if var is None or cb is None:
                continue
            if cb.cget("state") == "disabled":
                continue
            if var.get():
                out.append(item)
        return out

    def _update_footer(self) -> None:
        count = len(self._collect_selected())
        self._selected_var.set(
            f"{count} item selecionado" if count == 1 else f"{count} itens selecionados"
        )
        self._apply_btn.configure(
            state="normal" if count > 0 and not self._applying else "disabled",
        )

    # ---------- apply flow ----------

    def _on_apply(self) -> None:
        items = self._collect_selected()
        if not items:
            return
        self.main_window.console.append_line("\n[debloat] criando ponto de restauração…")
        threading.Thread(
            target=self._apply_after_restore_point, args=(items,),
            daemon=True, name="debloat-apply",
        ).start()

    def _apply_after_restore_point(self, items: list[DebloatItem]) -> None:
        rp = restore_point.create("PC Optimizer — antes de debloat")
        self.main_window.console.append_line(f"[restore point] {rp.message}")
        if not rp.success:
            self.main_window.console.append_line(
                "[debloat] prosseguindo sem restore point — confirmação requer atenção"
            )
        self.after(0, self._confirm_and_execute, items, rp.success)

    def _confirm_and_execute(self, items: list[DebloatItem], rp_ok: bool) -> None:
        summary = [f"• {it.label}" for it in items]
        warn = (
            f"{len(items)} itens serão aplicados."
            + ("" if rp_ok else " ATENÇÃO: ponto de restauração NÃO foi criado — o rollback manual será mais trabalhoso.")
        )
        confirmed = ConfirmDialog.ask(
            self.main_window,
            title="Confirmar debloat",
            description=warn,
            actions=summary,
            confirm_label="Aplicar agora",
        )
        if not confirmed:
            self.main_window.console.append_line("[debloat] cancelado pelo usuário")
            return

        self._applying = True
        self._apply_btn.configure(state="disabled", text="Aplicando…")
        self._run_sequential(items, 0)

    def _run_sequential(self, items: list[DebloatItem], index: int) -> None:
        console = self.main_window.console
        if index >= len(items):
            console.append_line(f"\n[debloat] concluído — {len(items)} itens processados")
            self._applying = False
            self._apply_btn.configure(text=f"{design.ICON_PLAY}  Aplicar seleção")
            self._update_footer()
            return

        item = items[index]
        console.append_line(f"\n>>> ({index + 1}/{len(items)}) {item.label}")

        if item.category == "apps" and item.appx_name:
            cmd = remove_appx_cmd(item.appx_name)
        elif item.apply_cmd is not None:
            cmd = list(item.apply_cmd)
        else:
            console.append_line(f"[debloat] {item.id}: nada a executar (item sem cmd)")
            self.after(0, self._run_sequential, items, index + 1)
            return

        self.main_window.executor.run(
            cmd,
            on_line=console.append_line,
            on_done=lambda _code, i=index: self.after(
                0, self._run_sequential, items, i + 1
            ),
        )
