"""System Tools tab: renders SYSTEM_TASKS as cards. Risky tasks hit a confirm dialog."""
from __future__ import annotations

from typing import TYPE_CHECKING

import customtkinter as ctk

from src.features.system_tools import SYSTEM_TASKS, RiskLevel, SystemTask
from src.ui.components.confirm_dialog import ConfirmDialog
from src.ui.components.task_card import TaskCard

if TYPE_CHECKING:
    from src.ui.main_window import MainWindow


_RISKY = {RiskLevel.MEDIUM, RiskLevel.HIGH}


class SystemToolsTab(ctk.CTkScrollableFrame):
    def __init__(self, master, *, main_window: "MainWindow") -> None:
        super().__init__(master, fg_color="transparent")
        self.main_window = main_window
        self._cards: dict[str, TaskCard] = {}

        for task in SYSTEM_TASKS:
            card = TaskCard(self, task=task, on_run=self._on_run)
            card.pack(fill="x", padx=6, pady=4)
            self._cards[task.id] = card

    def _on_run(self, task: SystemTask) -> None:
        if task.risk in _RISKY:
            confirmed = ConfirmDialog.ask(
                self.main_window,
                title=f"Confirmar: {task.label}",
                description=(
                    f"{task.description}\n\n"
                    f"Nível de risco: {task.risk.label}."
                    + ("\nSerá necessário REINICIAR o computador." if task.needs_reboot else "")
                ),
                actions=[f"Executar: {task.cmd}"],
                confirm_label="Executar",
            )
            if not confirmed:
                self._cards[task.id].reset()
                self.main_window.console.append_line(
                    f"[cancelado] {task.label}"
                )
                return

        self.main_window.console.append_line(f"\n>>> {task.label}")
        self.main_window.run_cmd(
            task.cmd,
            on_done=lambda _code, tid=task.id: self._on_done(tid),
        )

    def _on_done(self, task_id: str) -> None:
        card = self._cards.get(task_id)
        if card is not None:
            self.after(0, card.reset)
