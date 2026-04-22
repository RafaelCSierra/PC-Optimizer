"""CollapsibleSection: a header that expands/collapses a body on click."""
from __future__ import annotations

import customtkinter as ctk

from src.ui import design


class CollapsibleSection(ctk.CTkFrame):
    """Section with a clickable header that toggles a body.

    Use the `body` property as the parent for your content widgets.
    """

    def __init__(
        self,
        master,
        *,
        title: str,
        icon: str | None = None,
        initially_open: bool = True,
        count: int | None = None,
    ) -> None:
        super().__init__(master, fg_color="transparent")

        self._open = initially_open

        self._header = ctk.CTkFrame(
            self,
            corner_radius=6,
            fg_color=design.SECTION_HEADER_BG,
            height=38,
            cursor="hand2",
        )
        self._header.pack(fill="x", pady=(design.SP_SM, design.SP_XS))

        self._chevron = ctk.CTkLabel(
            self._header,
            text="▾" if initially_open else "▸",
            width=20,
            font=design.font_body("bold"),
        )
        self._chevron.pack(side="left", padx=(design.SP_MD, 0), pady=design.SP_SM)

        if icon:
            ctk.CTkLabel(
                self._header, text=icon, font=design.font_icon(16),
            ).pack(side="left", padx=(design.SP_SM, 0))

        ctk.CTkLabel(
            self._header,
            text=title,
            font=design.font_h3(),
            anchor="w",
        ).pack(side="left", padx=design.SP_SM)

        if count is not None:
            self._count_label = ctk.CTkLabel(
                self._header,
                text=f"{count} itens",
                font=design.font_caption(),
                text_color=design.SUBTLE_TEXT,
            )
            self._count_label.pack(side="right", padx=design.SP_LG)
        else:
            self._count_label = None

        self._body = ctk.CTkFrame(self, fg_color="transparent")
        if initially_open:
            self._body.pack(fill="x", pady=(design.SP_XS, design.SP_SM))

        self._bind_clicks(self._header)

    @property
    def body(self) -> ctk.CTkFrame:
        return self._body

    def set_count(self, count: int | None) -> None:
        if self._count_label is None:
            return
        self._count_label.configure(text="" if count is None else f"{count} itens")

    def set_open(self, value: bool) -> None:
        if bool(value) == self._open:
            return
        self._toggle()

    def _bind_clicks(self, widget) -> None:
        widget.bind("<Button-1>", self._toggle)
        for child in widget.winfo_children():
            self._bind_clicks(child)

    def _toggle(self, _event=None) -> None:
        self._open = not self._open
        if self._open:
            self._body.pack(fill="x", pady=(design.SP_XS, design.SP_SM))
            self._chevron.configure(text="▾")
        else:
            self._body.pack_forget()
            self._chevron.configure(text="▸")
