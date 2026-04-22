"""Cleanup tab: redesigned cards with icons, async size estimates and status."""
from __future__ import annotations

import threading
import time
from collections.abc import Callable
from typing import TYPE_CHECKING

import customtkinter as ctk

from src.features.cleanup import CLEANUP_TASKS, CleanupTask, estimate_size, format_bytes
from src.ui import design
from src.ui.components.confirm_dialog import ConfirmDialog

if TYPE_CHECKING:
    from src.ui.main_window import MainWindow


class _CleanupCard(ctk.CTkFrame):
    """Card mirroring TaskCard layout but tailored to CleanupTask (with size badge)."""

    def __init__(
        self,
        master,
        *,
        task: CleanupTask,
        on_run: Callable[[CleanupTask], None],
    ) -> None:
        super().__init__(
            master,
            corner_radius=8,
            border_width=2,
            border_color=design.INFO,
            fg_color=design.CARD_BG,
        )
        self.task = task
        self._on_run = on_run
        self._start_time: float = 0.0
        self._tick_job: str | None = None

        pad_x = design.SP_LG
        pad_y = design.SP_MD

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=pad_x, pady=(pad_y, 0))

        icon = design.CLEANUP_ICONS.get(task.id, design.ICON_RECYCLE)
        ctk.CTkLabel(
            header, text=icon, font=design.font_icon(22), width=32,
        ).pack(side="left", padx=(0, design.SP_MD))

        ctk.CTkLabel(
            header, text=task.label, font=design.font_h3(), anchor="w",
        ).pack(side="left")

        self._status_label = ctk.CTkLabel(
            header, text="", font=design.font_caption(),
        )
        self._status_label.pack(side="right", padx=design.SP_SM)

        badge_row = ctk.CTkFrame(header, fg_color="transparent")
        badge_row.pack(side="right")

        self._size_label = ctk.CTkLabel(
            badge_row,
            text="—" if task.size_targets else "sem estimativa",
            fg_color=design.CODE_BG, text_color=design.MUTED_TEXT,
            corner_radius=12, padx=10,
            font=design.font_caption(),
        )
        if task.size_targets:
            self._size_label.pack(side="left", padx=2)
        else:
            self._size_label = None  # type: ignore[assignment]

        if task.long_running:
            self._badge(badge_row, "Demora", design.INFO, icon=design.ICON_SLOW)
        if task.needs_confirm:
            self._badge(badge_row, "Confirma", design.WARNING, icon="⚠")

        ctk.CTkLabel(
            self, text=task.description, wraplength=700, justify="left",
            anchor="w", font=design.font_body(),
        ).pack(fill="x", padx=pad_x + 32, pady=(design.SP_XS, 0))

        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.pack(fill="x", padx=pad_x, pady=(design.SP_SM, pad_y))
        ctk.CTkLabel(
            footer,
            text=f"$ {' '.join(task.cmd[4:5]) if len(task.cmd) > 4 else task.cmd[0]}"[:100] + ("…" if len(' '.join(task.cmd)) > 100 else ""),
            font=design.font_mono(10), text_color=design.SUBTLE_TEXT, anchor="w",
        ).pack(side="left", fill="x", expand=True)
        self._run_btn = ctk.CTkButton(
            footer,
            text=f"{design.ICON_PLAY}  Limpar",
            width=130, command=self._handle_click,
        )
        self._run_btn.pack(side="right")

    def _badge(self, parent, text: str, color: str, *, icon: str = "") -> None:
        content = f"{icon} {text}".strip() if icon else text
        ctk.CTkLabel(
            parent, text=content, fg_color=color, text_color="white",
            corner_radius=12, padx=10, font=design.font_caption(),
        ).pack(side="left", padx=2)

    def _handle_click(self) -> None:
        self._on_run(self.task)

    def set_size(self, size_bytes: int) -> None:
        if self._size_label is None:
            return
        text = format_bytes(size_bytes)
        self._size_label.configure(text=text)

    def begin(self) -> None:
        self._run_btn.configure(state="disabled", text="Limpando…")
        self._start_time = time.monotonic()
        self._set_status(design.Status.RUNNING, "executando 0s…")
        self._schedule_tick()

    def finish(self, exit_code: int) -> None:
        self._cancel_tick()
        elapsed = time.monotonic() - self._start_time if self._start_time else 0.0
        if exit_code == 0:
            self._set_status(design.Status.OK, f"concluído em {elapsed:.0f}s")
        else:
            self._set_status(design.Status.FAIL, f"falhou (exit {exit_code})")
        self._run_btn.configure(state="normal", text=f"{design.ICON_PLAY}  Limpar")

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
            self._set_status(design.Status.RUNNING, f"executando {elapsed:.0f}s…")
        self._tick_job = self.after(500, self._tick)

    def _cancel_tick(self) -> None:
        if self._tick_job is not None:
            try:
                self.after_cancel(self._tick_job)
            except Exception:
                pass
            self._tick_job = None


class CleanupTab(ctk.CTkFrame):
    def __init__(self, master, *, main_window: "MainWindow") -> None:
        super().__init__(master, fg_color="transparent")
        self.main_window = main_window
        self._cards: dict[str, _CleanupCard] = {}

        ctk.CTkLabel(
            self,
            text=(
                "Tarefas de limpeza rodam sob confirmação quando mexem em serviços ou "
                "cache persistente. Estimativas de tamanho são calculadas no fundo ao "
                "abrir a aba. Saída em tempo real vai para o console."
            ),
            wraplength=900, justify="left",
            font=design.font_body(), text_color=design.MUTED_TEXT,
        ).pack(anchor="w", padx=design.SP_LG, pady=(design.SP_MD, design.SP_SM))

        scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        scroll.pack(side="top", fill="both", expand=True, padx=design.SP_MD, pady=design.SP_XS)

        for task in CLEANUP_TASKS:
            card = _CleanupCard(scroll, task=task, on_run=self._on_run)
            card.pack(fill="x", padx=2, pady=4)
            self._cards[task.id] = card

        self.after(200, self._start_estimates)

    def _start_estimates(self) -> None:
        threading.Thread(target=self._do_estimates, daemon=True, name="cleanup-estimate").start()

    def _do_estimates(self) -> None:
        for task in CLEANUP_TASKS:
            if not task.size_targets:
                continue
            size = estimate_size(task)
            self.after(0, self._update_size, task.id, size)

    def _update_size(self, task_id: str, size_bytes: int) -> None:
        card = self._cards.get(task_id)
        if card is not None:
            card.set_size(size_bytes)

    def _on_run(self, task: CleanupTask) -> None:
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

        card = self._cards.get(task.id)
        if card is not None:
            card.begin()

        self.main_window.console.append_line(f"\n>>> {task.label}")
        self.main_window.executor.run(
            list(task.cmd),
            on_line=self.main_window.console.append_line,
            on_done=lambda code, tid=task.id: self.after(0, self._finish, tid, code),
        )

    def _finish(self, task_id: str, code: int) -> None:
        card = self._cards.get(task_id)
        if card is not None:
            card.finish(code)
