"""Cleanup tab: renders CLEANUP_TASKS as simple cards with a Limpar button."""
from __future__ import annotations

from typing import TYPE_CHECKING

import customtkinter as ctk

from src.features.cleanup import CLEANUP_TASKS, CleanupTask
from src.ui.components.confirm_dialog import ConfirmDialog

if TYPE_CHECKING:
    from src.ui.main_window import MainWindow


class CleanupTab(ctk.CTkScrollableFrame):
    def __init__(self, master, *, main_window: "MainWindow") -> None:
        super().__init__(master, fg_color="transparent")
        self.main_window = main_window
        self._buttons: dict[str, ctk.CTkButton] = {}

        ctk.CTkLabel(
            self,
            text=(
                "Tarefas de limpeza rodam sempre sob confirmação quando envolvem "
                "serviços ou cache persistente. Saída em tempo real vai para o "
                "console abaixo."
            ),
            wraplength=780, justify="left",
            text_color=("#555", "#aaa"),
        ).pack(anchor="w", padx=6, pady=(6, 10))

        for task in CLEANUP_TASKS:
            self._build_card(task)

    def _build_card(self, task: CleanupTask) -> None:
        frame = ctk.CTkFrame(self, corner_radius=6, border_width=1)
        frame.pack(fill="x", padx=6, pady=4)

        header = ctk.CTkFrame(frame, fg_color="transparent")
        header.pack(fill="x", padx=12, pady=(10, 2))
        ctk.CTkLabel(
            header, text=task.label, font=ctk.CTkFont(size=13, weight="bold"),
        ).pack(side="left", anchor="w")
        if task.long_running:
            ctk.CTkLabel(
                header, text="Demora", fg_color="#1f6feb", text_color="white",
                corner_radius=10, padx=8,
                font=ctk.CTkFont(size=10, weight="bold"),
            ).pack(side="right", padx=3)
        if task.needs_confirm:
            ctk.CTkLabel(
                header, text="Confirma", fg_color="#d29922", text_color="white",
                corner_radius=10, padx=8,
                font=ctk.CTkFont(size=10, weight="bold"),
            ).pack(side="right", padx=3)

        ctk.CTkLabel(
            frame, text=task.description, wraplength=720, justify="left",
            anchor="w", font=ctk.CTkFont(size=11),
        ).pack(fill="x", padx=12, pady=(0, 4))

        footer = ctk.CTkFrame(frame, fg_color="transparent")
        footer.pack(fill="x", padx=12, pady=(0, 10))
        btn = ctk.CTkButton(
            footer, text="Limpar", width=100,
            command=lambda t=task: self._run(t),
        )
        btn.pack(side="right")
        self._buttons[task.id] = btn

    def _run(self, task: CleanupTask) -> None:
        if task.needs_confirm:
            ok = ConfirmDialog.ask(
                self.main_window,
                title=f"Confirmar: {task.label}",
                description=task.description,
                actions=[task.label],
                confirm_label="Limpar",
            )
            if not ok:
                self.main_window.console.append_line(f"[limpeza] cancelado: {task.label}")
                return

        btn = self._buttons.get(task.id)
        if btn is not None:
            btn.configure(state="disabled", text="Limpando...")

        self.main_window.console.append_line(f"\n>>> {task.label}")
        self.main_window.executor.run(
            list(task.cmd),
            on_line=self.main_window.console.append_line,
            on_done=lambda _code, tid=task.id: self.after(0, self._reset_button, tid),
        )

    def _reset_button(self, task_id: str) -> None:
        btn = self._buttons.get(task_id)
        if btn is not None:
            btn.configure(state="normal", text="Limpar")
