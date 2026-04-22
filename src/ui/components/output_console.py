"""Thread-safe streaming output console based on CTkTextbox."""
from __future__ import annotations

import customtkinter as ctk


class OutputConsole(ctk.CTkFrame):
    """Read-only scrolling console for streamed command output.

    append_line() is safe to call from any thread — it defers the UI update to
    the Tk event loop via after(0, ...).
    """

    def __init__(self, master, **kwargs) -> None:
        super().__init__(master, **kwargs)

        header = ctk.CTkFrame(self, height=28, corner_radius=0, fg_color="transparent")
        header.pack(side="top", fill="x")
        ctk.CTkLabel(
            header, text="Console", font=ctk.CTkFont(size=12, weight="bold")
        ).pack(side="left", padx=8, pady=2)
        ctk.CTkButton(
            header, text="Limpar", width=70, height=22, command=self.clear
        ).pack(side="right", padx=8, pady=2)

        self._textbox = ctk.CTkTextbox(
            self, font=("Consolas", 11), wrap="none", state="disabled"
        )
        self._textbox.pack(side="top", fill="both", expand=True)

    def append_line(self, line: str) -> None:
        self.after(0, self._append, line)

    def clear(self) -> None:
        self.after(0, self._clear)

    def _append(self, line: str) -> None:
        self._textbox.configure(state="normal")
        self._textbox.insert("end", line + "\n")
        self._textbox.see("end")
        self._textbox.configure(state="disabled")

    def _clear(self) -> None:
        self._textbox.configure(state="normal")
        self._textbox.delete("1.0", "end")
        self._textbox.configure(state="disabled")
