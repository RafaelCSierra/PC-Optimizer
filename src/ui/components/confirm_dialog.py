"""Modal double-confirmation dialog listing actions before a destructive operation."""
from __future__ import annotations

from collections.abc import Sequence

import customtkinter as ctk

_DANGER_RED = "#d13438"


class ConfirmDialog(ctk.CTkToplevel):
    """Modal dialog: shows a list of actions + 'Entendo os riscos' checkbox.

    Use via classmethod ConfirmDialog.ask(master, ...). Returns True if the user
    checked the box and clicked Confirmar; False on Cancelar or window close.
    """

    def __init__(
        self,
        master,
        *,
        title: str,
        description: str,
        actions: Sequence[str],
        confirm_label: str = "Confirmar",
    ) -> None:
        super().__init__(master)
        self.title(title)
        self.geometry("620x480")
        self.minsize(520, 400)
        self.result: bool = False

        self.transient(master)
        self.grab_set()
        self._center_over(master)

        ctk.CTkLabel(
            self, text=title, font=ctk.CTkFont(size=16, weight="bold"),
            text_color=_DANGER_RED,
        ).pack(padx=16, pady=(14, 6), anchor="w")

        ctk.CTkLabel(
            self, text=description, wraplength=560, justify="left",
        ).pack(padx=16, pady=(0, 8), anchor="w")

        list_label = f"As seguintes ações serão executadas ({len(actions)}):"
        ctk.CTkLabel(
            self, text=list_label, font=ctk.CTkFont(size=12, weight="bold"),
        ).pack(padx=16, pady=(6, 4), anchor="w")

        list_frame = ctk.CTkScrollableFrame(self, fg_color=("#f0f0f0", "#2b2b2b"))
        list_frame.pack(fill="both", expand=True, padx=16, pady=4)
        for action in actions:
            ctk.CTkLabel(
                list_frame, text=f"•  {action}", anchor="w", justify="left",
                wraplength=520,
            ).pack(fill="x", padx=8, pady=2)

        self._ack_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(
            self,
            text="Entendo os riscos e quero prosseguir",
            variable=self._ack_var,
            command=self._on_ack_toggle,
        ).pack(padx=16, pady=(10, 4), anchor="w")

        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(pady=(4, 14))
        ctk.CTkButton(
            btn_frame, text="Cancelar", width=130, command=self._cancel,
        ).pack(side="left", padx=8)
        self._confirm_btn = ctk.CTkButton(
            btn_frame,
            text=confirm_label,
            width=130,
            state="disabled",
            fg_color=_DANGER_RED,
            hover_color="#a32b2e",
            command=self._confirm,
        )
        self._confirm_btn.pack(side="left", padx=8)

        self.protocol("WM_DELETE_WINDOW", self._cancel)
        self.bind("<Escape>", lambda _e: self._cancel())

    def _center_over(self, master) -> None:
        try:
            master.update_idletasks()
            mx, my = master.winfo_x(), master.winfo_y()
            mw, mh = master.winfo_width(), master.winfo_height()
            x = mx + (mw - 620) // 2
            y = my + (mh - 480) // 2
            self.geometry(f"620x480+{max(0, x)}+{max(0, y)}")
        except Exception:
            pass

    def _on_ack_toggle(self) -> None:
        state = "normal" if self._ack_var.get() else "disabled"
        self._confirm_btn.configure(state=state)

    def _confirm(self) -> None:
        self.result = True
        self.destroy()

    def _cancel(self) -> None:
        self.result = False
        self.destroy()

    @classmethod
    def ask(
        cls,
        master,
        *,
        title: str,
        description: str,
        actions: Sequence[str],
        confirm_label: str = "Confirmar",
    ) -> bool:
        dlg = cls(
            master,
            title=title,
            description=description,
            actions=actions,
            confirm_label=confirm_label,
        )
        master.wait_window(dlg)
        return dlg.result
