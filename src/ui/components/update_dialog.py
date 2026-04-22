"""Update dialog — shown when a newer release is detected on GitHub."""
from __future__ import annotations

import threading
import webbrowser
from pathlib import Path

import customtkinter as ctk

from src.core import updater
from src.core.updater import UpdateInfo
from src.ui import design


class UpdateDialog(ctk.CTkToplevel):
    def __init__(self, master, *, update: UpdateInfo, current_exe: Path) -> None:
        super().__init__(master)
        self.title("Atualização disponível")
        self.geometry("600x480")
        self.minsize(540, 420)

        self.transient(master)
        self.grab_set()

        self._update = update
        self._current_exe = current_exe
        self._downloading = False

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=design.SP_LG, pady=(design.SP_LG, design.SP_SM))
        ctk.CTkLabel(
            header, text="🎉 Nova versão do PC Optimizer",
            font=design.font_h2(), text_color=design.PRIMARY,
        ).pack(anchor="w")
        ctk.CTkLabel(
            header,
            text=f"Atual: v{update.current}   →   Nova: {update.tag}   ·   {update.size_mb:.1f} MB",
            font=design.font_body(), text_color=design.MUTED_TEXT,
        ).pack(anchor="w", pady=(2, 0))

        notes_frame = ctk.CTkFrame(self, fg_color=design.CODE_BG, corner_radius=6)
        notes_frame.pack(fill="both", expand=True, padx=design.SP_LG, pady=design.SP_SM)
        notes = ctk.CTkTextbox(
            notes_frame, wrap="word", font=design.font_body(),
            fg_color="transparent",
        )
        notes.pack(fill="both", expand=True, padx=design.SP_MD, pady=design.SP_MD)
        notes.insert("1.0", update.notes or "(sem release notes)")
        notes.configure(state="disabled")

        self._progress_var = ctk.StringVar(value="")
        ctk.CTkLabel(
            self, textvariable=self._progress_var, font=design.font_caption(),
            text_color=design.MUTED_TEXT,
        ).pack(anchor="w", padx=design.SP_LG)

        self._progress_bar = ctk.CTkProgressBar(self, mode="determinate")
        self._progress_bar.set(0)
        # Hidden until download starts
        self._progress_bar.pack(fill="x", padx=design.SP_LG, pady=(0, design.SP_SM))
        self._progress_bar.pack_forget()

        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.pack(fill="x", padx=design.SP_LG, pady=(0, design.SP_LG))

        ctk.CTkButton(
            footer, text="Abrir no GitHub", width=140,
            fg_color="gray40", hover_color="gray30",
            command=self._open_github,
        ).pack(side="left", padx=design.SP_XS)
        ctk.CTkButton(
            footer, text="Depois", width=120,
            fg_color="gray40", hover_color="gray30",
            command=self._cancel,
        ).pack(side="right", padx=design.SP_XS)
        self._update_btn = ctk.CTkButton(
            footer, text=f"{design.ICON_PLAY}  Atualizar agora", width=180,
            fg_color=design.SUCCESS, hover_color="#24833a",
            command=self._start_update,
        )
        self._update_btn.pack(side="right", padx=design.SP_XS)

        self.protocol("WM_DELETE_WINDOW", self._cancel)

    def _open_github(self) -> None:
        webbrowser.open(self._update.html_url)

    def _cancel(self) -> None:
        if self._downloading:
            return
        self.destroy()

    def _start_update(self) -> None:
        self._downloading = True
        self._update_btn.configure(state="disabled", text="Baixando…")
        self._progress_bar.pack(fill="x", padx=design.SP_LG, pady=(0, design.SP_SM))
        self._progress_var.set("Preparando download…")

        threading.Thread(target=self._do_download, daemon=True, name="updater-download").start()

    def _do_download(self) -> None:
        try:
            def on_progress(done: int, total: int) -> None:
                pct = done / total if total else 0
                self.after(0, self._update_progress, done, total, pct)

            new_path = updater.download_update(self._update, on_progress=on_progress)
        except Exception as e:  # noqa: BLE001
            self.after(0, self._download_failed, str(e))
            return

        self.after(0, self._download_complete, new_path)

    def _update_progress(self, done: int, total: int, pct: float) -> None:
        self._progress_bar.set(pct)
        mb_done = done / (1024 * 1024)
        mb_total = total / (1024 * 1024) if total else 0
        self._progress_var.set(f"Baixando: {mb_done:.1f} / {mb_total:.1f} MB ({pct * 100:.0f}%)")

    def _download_complete(self, new_path: Path) -> None:
        self._progress_var.set("Download concluído. Reiniciando…")
        self._update_btn.configure(text="Reiniciando…")
        # Schedule the relaunch slightly after this tick so the UI can paint
        self.after(400, self._relaunch, new_path)

    def _relaunch(self, new_path: Path) -> None:
        import logging
        log = logging.getLogger("pc_optimizer.update_dialog")
        try:
            log.info("launching updater bat: new=%s current=%s",
                     new_path, self._current_exe)
            updater.install_update_and_relaunch(new_path, self._current_exe)
        except Exception:
            log.exception("install_update_and_relaunch failed")
            self._progress_var.set(
                "Falha ao lançar o updater. Baixe manualmente: ver %TEMP%\\PCOptimizer_update"
            )
            return
        # Give the bat a head start to begin its tasklist-wait loop before we exit.
        self.master.after(400, self.master.destroy)

    def _download_failed(self, msg: str) -> None:
        self._downloading = False
        self._progress_var.set(f"Falha no download: {msg}")
        self._update_btn.configure(state="normal", text=f"{design.ICON_PLAY}  Tentar de novo")
