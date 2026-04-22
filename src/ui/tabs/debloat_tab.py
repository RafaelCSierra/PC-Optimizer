"""Debloat Windows 11 tab: Appx removal + privacy toggles, with safety flow."""
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
from src.ui.components.confirm_dialog import ConfirmDialog

if TYPE_CHECKING:
    from src.ui.main_window import MainWindow


class DebloatTab(ctk.CTkFrame):
    def __init__(self, master, *, main_window: "MainWindow") -> None:
        super().__init__(master, fg_color="transparent")
        self.main_window = main_window
        self._vars: dict[str, ctk.BooleanVar] = {}
        self._row_widgets: dict[str, ctk.CTkCheckBox] = {}
        self._installed: set[str] = set()
        self._applying = False

        self._build_header()
        self._build_body()
        self._build_footer()

        self.after(200, self.refresh_installed)

    # ---------------- layout ----------------

    def _build_header(self) -> None:
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(side="top", fill="x", padx=6, pady=(6, 2))

        self._refresh_btn = ctk.CTkButton(
            header, text="Atualizar lista", width=130, command=self.refresh_installed,
        )
        self._refresh_btn.pack(side="left", padx=2)

        ctk.CTkLabel(header, text="   Preset:").pack(side="left", padx=(12, 2))
        for preset in Preset:
            ctk.CTkButton(
                header, text=preset.label, width=110,
                command=lambda p=preset: self._apply_preset(p),
            ).pack(side="left", padx=2)

        ctk.CTkButton(
            header, text="Desmarcar todos", width=130, fg_color="gray30",
            hover_color="gray25", command=self._clear_selection,
        ).pack(side="left", padx=(12, 2))

        self._status_var = ctk.StringVar(value="Carregando pacotes instalados...")
        ctk.CTkLabel(header, textvariable=self._status_var, anchor="e").pack(
            side="right", padx=8,
        )

    def _build_body(self) -> None:
        scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        scroll.pack(side="top", fill="both", expand=True, padx=6, pady=4)

        self._section(scroll, "Apps pré-instalados", APPS)
        self._section(scroll, "Privacidade e telemetria", PRIVACY)

    def _section(self, parent, title: str, items: tuple[DebloatItem, ...]) -> None:
        ctk.CTkLabel(
            parent, text=title, font=ctk.CTkFont(size=14, weight="bold"),
        ).pack(anchor="w", padx=4, pady=(10, 4))

        for item in items:
            row = ctk.CTkFrame(parent, corner_radius=4)
            row.pack(fill="x", padx=4, pady=2)

            var = ctk.BooleanVar(value=False)
            self._vars[item.id] = var

            checkbox = ctk.CTkCheckBox(
                row, text=item.label, variable=var,
                command=self._update_footer,
                font=ctk.CTkFont(size=12, weight="bold"),
            )
            checkbox.pack(anchor="w", padx=10, pady=(6, 0))
            self._row_widgets[item.id] = checkbox

            ctk.CTkLabel(
                row, text=item.description, wraplength=700, justify="left",
                anchor="w", font=ctk.CTkFont(size=10),
                text_color=("#444", "#aaa"),
            ).pack(anchor="w", padx=32, pady=(0, 6))

    def _build_footer(self) -> None:
        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.pack(side="bottom", fill="x", padx=6, pady=6)

        self._apply_btn = ctk.CTkButton(
            footer, text="Aplicar seleção (0)", height=36,
            fg_color="#d13438", hover_color="#a32b2e",
            command=self._on_apply, state="disabled",
        )
        self._apply_btn.pack(side="right", padx=4)

    # ---------------- data flow ----------------

    def refresh_installed(self) -> None:
        self._status_var.set("Consultando pacotes Appx...")
        self._refresh_btn.configure(state="disabled")

        def worker() -> None:
            names = list_installed_appx_names()
            self.after(0, self._apply_installed, names)

        threading.Thread(target=worker, daemon=True, name="appx-list").start()

    def _apply_installed(self, names: set[str]) -> None:
        self._installed = names
        missing = 0
        for item in ALL_ITEMS:
            cb = self._row_widgets.get(item.id)
            if cb is None:
                continue
            if item.category != "apps":
                continue
            if item.appx_name and item.appx_name not in names:
                cb.configure(state="disabled", text=f"{item.label}  —  (não instalado)")
                missing += 1
            else:
                cb.configure(state="normal", text=item.label)

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
            should_select = preset in item.presets
            var = self._vars.get(item.id)
            cb = self._row_widgets.get(item.id)
            if var is None or cb is None:
                continue
            if cb.cget("state") == "disabled":
                var.set(False)
                continue
            var.set(should_select)
            if should_select:
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
            cb = self._row_widgets.get(item.id)
            if var is None or cb is None:
                continue
            if cb.cget("state") == "disabled":
                continue
            if var.get():
                out.append(item)
        return out

    def _update_footer(self) -> None:
        count = sum(
            1 for item in ALL_ITEMS
            if (var := self._vars.get(item.id)) is not None
            and var.get()
            and (cb := self._row_widgets.get(item.id)) is not None
            and cb.cget("state") != "disabled"
        )
        self._apply_btn.configure(
            text=f"Aplicar seleção ({count})",
            state="normal" if count > 0 and not self._applying else "disabled",
        )

    # ---------------- apply flow ----------------

    def _on_apply(self) -> None:
        items = self._collect_selected()
        if not items:
            return

        console = self.main_window.console

        # 1) Restore point
        console.append_line("\n[debloat] criando ponto de restauração...")
        threading.Thread(
            target=self._apply_after_restore_point,
            args=(items,),
            daemon=True, name="debloat-apply",
        ).start()

    def _apply_after_restore_point(self, items: list[DebloatItem]) -> None:
        console = self.main_window.console
        rp = restore_point.create("PC Optimizer — antes de debloat")
        console.append_line(f"[restore point] {rp.message}")
        if not rp.success:
            console.append_line(
                "[debloat] continuando mesmo sem restore point — confirmação requer atenção"
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
        self._apply_btn.configure(state="disabled", text="Aplicando...")
        self._run_sequential(items, 0)

    def _run_sequential(self, items: list[DebloatItem], index: int) -> None:
        console = self.main_window.console
        if index >= len(items):
            console.append_line(f"\n[debloat] concluído — {len(items)} itens processados")
            self._applying = False
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
