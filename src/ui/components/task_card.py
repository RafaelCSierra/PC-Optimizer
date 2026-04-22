"""Reusable card showing a single maintenance task with run button and metadata badges."""
from __future__ import annotations

from collections.abc import Callable

import customtkinter as ctk

from src.features.system_tools import SystemTask


class TaskCard(ctk.CTkFrame):
    def __init__(self, master, *, task: SystemTask, on_run: Callable[[SystemTask], None]) -> None:
        super().__init__(master, corner_radius=6, border_width=1)
        self.task = task
        self._on_run = on_run

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=12, pady=(10, 2))
        ctk.CTkLabel(
            header, text=task.label, font=ctk.CTkFont(size=13, weight="bold"),
        ).pack(side="left", anchor="w")

        badge_row = ctk.CTkFrame(header, fg_color="transparent")
        badge_row.pack(side="right")
        self._badge(badge_row, task.risk.label, task.risk.color)
        if task.needs_reboot:
            self._badge(badge_row, "Reboot", "#8957e5")
        if task.long_running:
            self._badge(badge_row, "Demora", "#1f6feb")

        ctk.CTkLabel(
            self, text=task.description, wraplength=620, justify="left",
            anchor="w", font=ctk.CTkFont(size=11),
        ).pack(fill="x", padx=12, pady=(0, 4))

        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.pack(fill="x", padx=12, pady=(0, 10))
        ctk.CTkLabel(
            footer, text=f"$ {task.cmd}", font=("Consolas", 10),
            text_color=("#555", "#888"), anchor="w",
        ).pack(side="left", fill="x", expand=True)
        self._run_btn = ctk.CTkButton(
            footer, text="Executar", width=100, command=self._handle_run,
        )
        self._run_btn.pack(side="right")

    def _badge(self, parent, text: str, color: str) -> None:
        ctk.CTkLabel(
            parent, text=text, fg_color=color, text_color="white",
            corner_radius=10, padx=8, font=ctk.CTkFont(size=10, weight="bold"),
        ).pack(side="left", padx=3)

    def _handle_run(self) -> None:
        self._run_btn.configure(state="disabled", text="Executando…")
        self._on_run(self.task)

    def reset(self) -> None:
        """Called by the tab when the command finishes, to re-enable the button."""
        self._run_btn.configure(state="normal", text="Executar")
