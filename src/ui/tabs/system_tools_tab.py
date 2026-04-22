"""System Tools tab: tasks grouped by family in collapsible sections."""
from __future__ import annotations

from typing import TYPE_CHECKING

import customtkinter as ctk

from src.features.system_tools import SYSTEM_TASKS, RiskLevel, SystemTask
from src.ui import design
from src.ui.components.collapsible import CollapsibleSection
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

        # Bucket tasks by family
        buckets: dict[str, list[SystemTask]] = {}
        for task in SYSTEM_TASKS:
            family = design.family_for_system_task(task.id)
            buckets.setdefault(family, []).append(task)

        for family in design.SYSTEM_FAMILIES_ORDER:
            tasks_in_family = buckets.get(family, [])
            if not tasks_in_family:
                continue
            section = CollapsibleSection(
                self,
                title=family,
                icon=design.icon_for_system_task(tasks_in_family[0].id),
                initially_open=True,
                count=len(tasks_in_family),
            )
            section.pack(fill="x")
            for task in tasks_in_family:
                card = TaskCard(section.body, task=task, on_run=self._on_run)
                card.pack(fill="x", padx=2, pady=3)
                self._cards[task.id] = card

    # ---------- actions ----------

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
                self.main_window.console.append_line(f"[cancelado] {task.label}")
                return

        card = self._cards.get(task.id)
        if card is not None:
            card.begin()

        self.main_window.console.append_line(f"\n>>> {task.label}")
        self.main_window.run_cmd(
            task.cmd,
            on_done=lambda code, tid=task.id: self.after(0, self._finish, tid, code),
        )

    def _finish(self, task_id: str, code: int) -> None:
        card = self._cards.get(task_id)
        if card is not None:
            card.finish(code)
