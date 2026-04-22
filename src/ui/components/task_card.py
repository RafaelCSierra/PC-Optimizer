"""Reusable card showing a maintenance task with icon, risk border, badges and status."""
from __future__ import annotations

import time
from collections.abc import Callable

import customtkinter as ctk

from src.features.system_tools import SystemTask
from src.ui import design


class TaskCard(ctk.CTkFrame):
    """One card per SystemTask.

    Lifecycle:
      1. idle → user clicks "Executar" → on_run(task) fires
      2. the tab decides whether to actually run (may cancel via ConfirmDialog)
      3. if running, the tab calls card.begin(); the card shows the running state
         with a live-updating elapsed-seconds label
      4. on done the tab calls card.finish(exit_code) → success or failure state
    """

    def __init__(
        self,
        master,
        *,
        task: SystemTask,
        on_run: Callable[[SystemTask], None],
    ) -> None:
        super().__init__(
            master,
            corner_radius=8,
            border_width=2,
            border_color=design.risk_color(task.risk.value),
            fg_color=design.CARD_BG,
        )
        self.task = task
        self._on_run = on_run
        self._start_time: float = 0.0
        self._tick_job: str | None = None

        self._build()

    # ---------- layout ----------

    def _build(self) -> None:
        pad_x = design.SP_LG
        pad_y = design.SP_MD

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=pad_x, pady=(pad_y, 0))

        ctk.CTkLabel(
            header,
            text=design.icon_for_system_task(self.task.id),
            font=design.font_icon(22),
            width=32,
        ).pack(side="left", padx=(0, design.SP_MD))

        ctk.CTkLabel(
            header,
            text=self.task.label,
            font=design.font_h3(),
            anchor="w",
        ).pack(side="left")

        # Right side: status label + badges (pack right-to-left)
        self._status_label = ctk.CTkLabel(
            header, text="", font=design.font_caption(),
        )
        self._status_label.pack(side="right", padx=design.SP_SM)

        badge_row = ctk.CTkFrame(header, fg_color="transparent")
        badge_row.pack(side="right")
        self._badge(badge_row, self.task.risk.label, design.risk_color(self.task.risk.value))
        if self.task.needs_reboot:
            self._badge(badge_row, "Reboot", "#8957e5", icon=design.ICON_REBOOT)
        if self.task.long_running:
            self._badge(badge_row, "Demora", design.INFO, icon=design.ICON_SLOW)

        ctk.CTkLabel(
            self,
            text=self.task.description,
            wraplength=700,
            justify="left",
            anchor="w",
            font=design.font_body(),
        ).pack(fill="x", padx=pad_x + 32, pady=(design.SP_XS, 0))

        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.pack(fill="x", padx=pad_x, pady=(design.SP_SM, pad_y))

        ctk.CTkLabel(
            footer,
            text=f"$ {self.task.cmd}",
            font=design.font_mono(10),
            text_color=design.SUBTLE_TEXT,
            anchor="w",
        ).pack(side="left", fill="x", expand=True)

        self._run_btn = ctk.CTkButton(
            footer,
            text=f"{design.ICON_PLAY}  Executar",
            width=130,
            command=self._handle_click,
        )
        self._run_btn.pack(side="right")

    def _badge(self, parent, text: str, color: str, *, icon: str = "") -> None:
        content = f"{icon} {text}".strip() if icon else text
        ctk.CTkLabel(
            parent,
            text=content,
            fg_color=color,
            text_color="white",
            corner_radius=12,
            padx=10,
            font=design.font_caption(),
        ).pack(side="left", padx=2)

    # ---------- state transitions ----------

    def _handle_click(self) -> None:
        self._on_run(self.task)

    def begin(self) -> None:
        """Called by the tab when execution is actually starting."""
        self._run_btn.configure(state="disabled", text="Executando...")
        self._start_time = time.monotonic()
        self._set_status(design.Status.RUNNING, "executando 0s...")
        self._schedule_tick()

    def finish(self, exit_code: int) -> None:
        self._cancel_tick()
        elapsed = time.monotonic() - self._start_time if self._start_time else 0.0
        if exit_code == 0:
            self._set_status(design.Status.OK, f"concluído em {elapsed:.0f}s")
        else:
            self._set_status(design.Status.FAIL, f"falhou (exit {exit_code})")
        self._run_btn.configure(state="normal", text=f"{design.ICON_PLAY}  Executar")

    def cancel(self, reason: str = "cancelado") -> None:
        self._cancel_tick()
        self._set_status(design.Status.CANCELLED, reason)
        self._run_btn.configure(state="normal", text=f"{design.ICON_PLAY}  Executar")

    def reset(self) -> None:
        """Back to idle. Used when the tab's flow aborts before begin()."""
        self._cancel_tick()
        self._set_status(design.Status.IDLE, "")
        self._run_btn.configure(state="normal", text=f"{design.ICON_PLAY}  Executar")

    # ---------- internals ----------

    def _set_status(self, status: str, text: str) -> None:
        icon = design.STATUS_ICONS.get(status, "")
        color = design.STATUS_COLORS.get(status, design.MUTED_TEXT)
        label = f"{icon} {text}".strip() if icon else text
        self._status_label.configure(text=label, text_color=color)

    def _schedule_tick(self) -> None:
        self._tick_job = self.after(500, self._tick)

    def _tick(self) -> None:
        if self._start_time:
            elapsed = time.monotonic() - self._start_time
            self._set_status(design.Status.RUNNING, f"executando {elapsed:.0f}s...")
        self._tick_job = self.after(500, self._tick)

    def _cancel_tick(self) -> None:
        if self._tick_job is not None:
            try:
                self.after_cancel(self._tick_job)
            except Exception:
                pass
            self._tick_job = None
