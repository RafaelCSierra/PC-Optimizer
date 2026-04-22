"""Main application window with tabbed layout and shared output console."""
from __future__ import annotations

import logging

import customtkinter as ctk

from src.core.executor import CommandExecutor
from src.ui.components.output_console import OutputConsole

TAB_NAMES: tuple[str, ...] = (
    "System Tools",
    "Debloat Windows 11",
    "Limpeza",
    "Info do Sistema",
)


class MainWindow(ctk.CTk):
    def __init__(self, admin: bool, logger: logging.Logger) -> None:
        super().__init__()
        self.title("PC Optimizer")
        self.geometry("1100x720")
        self.minsize(900, 600)

        self.logger = logger
        self.executor = CommandExecutor(logger=logger)
        self.admin = admin

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("dark-blue")

        self._build_topbar()
        self._build_console()
        self._build_tabs()

        self.console.append_line("PC Optimizer iniciado.")
        self.console.append_line(
            f"Administrador: {'sim' if admin else 'NÃO — comandos elevados vão falhar'}"
        )

    def _build_topbar(self) -> None:
        bar = ctk.CTkFrame(self, height=44, corner_radius=0)
        bar.pack(side="top", fill="x")
        ctk.CTkLabel(
            bar, text="PC Optimizer", font=ctk.CTkFont(size=16, weight="bold")
        ).pack(side="left", padx=14, pady=8)

        status_text = "Admin: OK" if self.admin else "Admin: FALTA"
        status_color = "#2ea043" if self.admin else "#f85149"
        ctk.CTkLabel(bar, text=status_text, text_color=status_color).pack(
            side="right", padx=14
        )

    def _build_tabs(self) -> None:
        self.tabview = ctk.CTkTabview(self)
        self.tabview.pack(side="top", fill="both", expand=True, padx=12, pady=(8, 4))
        for name in TAB_NAMES:
            self.tabview.add(name)
            ctk.CTkLabel(
                self.tabview.tab(name),
                text=f"[{name}] — em implementação",
                font=ctk.CTkFont(size=14),
            ).pack(pady=40)

    def _build_console(self) -> None:
        self.console = OutputConsole(self, height=200)
        self.console.pack(side="bottom", fill="x", padx=12, pady=(4, 12))
