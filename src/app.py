"""Application bootstrap: logger, UAC elevation prompt, main window."""
from __future__ import annotations

import tkinter as tk
from tkinter import messagebox

from src.core import dry_run
from src.core.admin import is_admin, relaunch_as_admin
from src.core.logger import setup_logger


def _ask_elevation() -> bool:
    """Show a small Tk dialog asking whether to relaunch elevated. Returns the user's yes/no."""
    root = tk.Tk()
    root.withdraw()
    try:
        return bool(
            messagebox.askyesno(
                "PC Optimizer — Administrador necessário",
                "Este aplicativo precisa de privilégios de Administrador para executar "
                "comandos como CHKDSK, SFC e DISM.\n\n"
                "Deseja reiniciar como Administrador agora?",
            )
        )
    finally:
        root.destroy()


def main() -> int:
    logger = setup_logger()
    logger.info("--- PC Optimizer starting ---")

    dry_run.init_from_config()

    admin = is_admin()
    logger.info("is_admin=%s", admin)

    if not admin and _ask_elevation():
        if relaunch_as_admin():
            logger.info("relaunched elevated; exiting current process")
            return 0
        logger.error("relaunch_as_admin returned False — continuing unelevated")

    from src.ui.main_window import MainWindow

    window = MainWindow(admin=admin, logger=logger)
    # Check for updates 3s after window shows — non-blocking
    window.after(3000, window.check_for_updates_async)
    window.mainloop()
    logger.info("--- PC Optimizer exiting ---")
    return 0
