"""Info do Sistema tab: read-only system snapshot + helper buttons."""
from __future__ import annotations

import os
import subprocess
import threading
import webbrowser
from typing import TYPE_CHECKING

import customtkinter as ctk

from src.features.system_info import DiskInfo, SystemInfo, collect, log_dir_path

if TYPE_CHECKING:
    from src.ui.main_window import MainWindow


REPO_URL = "https://github.com/RafaelCSierra/PC-Optimizer"


class InfoTab(ctk.CTkFrame):
    def __init__(self, master, *, main_window: "MainWindow") -> None:
        super().__init__(master, fg_color="transparent")
        self.main_window = main_window

        self._build_header()
        self._body = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self._body.pack(side="top", fill="both", expand=True, padx=6, pady=4)
        self._build_footer()

        self._set_loading()
        self.after(100, self.refresh)

    def _build_header(self) -> None:
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(side="top", fill="x", padx=6, pady=(6, 2))
        ctk.CTkLabel(
            header, text="Informações do sistema",
            font=ctk.CTkFont(size=14, weight="bold"),
        ).pack(side="left", padx=4)
        self._refresh_btn = ctk.CTkButton(
            header, text="Atualizar", width=100, command=self.refresh,
        )
        self._refresh_btn.pack(side="right", padx=4)

    def _build_footer(self) -> None:
        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.pack(side="bottom", fill="x", padx=6, pady=6)
        ctk.CTkButton(
            footer, text="Abrir pasta de logs", command=self._open_logs,
        ).pack(side="left", padx=4)
        ctk.CTkButton(
            footer, text="Abrir repositório no GitHub", command=self._open_repo,
        ).pack(side="left", padx=4)

    # ---------- data ----------

    def refresh(self) -> None:
        self._set_loading()
        self._refresh_btn.configure(state="disabled")

        def worker() -> None:
            try:
                info = collect()
                self.after(0, self._render, info)
            except Exception as e:
                self.after(0, self._render_error, str(e))

        threading.Thread(target=worker, daemon=True, name="sysinfo").start()

    def _set_loading(self) -> None:
        for w in self._body.winfo_children():
            w.destroy()
        ctk.CTkLabel(self._body, text="Coletando informações...").pack(pady=20)

    def _render_error(self, msg: str) -> None:
        for w in self._body.winfo_children():
            w.destroy()
        ctk.CTkLabel(
            self._body, text=f"Falha ao coletar: {msg}", text_color="#f85149",
        ).pack(pady=20)
        self._refresh_btn.configure(state="normal")

    def _render(self, info: SystemInfo) -> None:
        for w in self._body.winfo_children():
            w.destroy()

        self._section("Sistema", [
            ("Hostname", info.hostname),
            ("Usuário", info.user),
            ("SO", info.os_caption),
            ("Build", info.os_build),
            ("Uptime", info.format_uptime()),
            ("Versão do PC Optimizer", info.app_version),
        ])

        self._section("Hardware", [
            ("CPU", info.cpu_name),
            ("Cores / Threads", f"{info.cpu_physical_cores} cores · {info.cpu_logical_cores} threads"),
            ("Uso de CPU (instantâneo)", f"{info.cpu_percent:.1f}%"),
            ("RAM", f"{info.ram_total_gb:.1f} GB total · {info.ram_available_gb:.1f} GB livre"),
            ("Uso de RAM", f"{info.ram_percent:.1f}%"),
            ("GPU", "\n".join(info.gpu_names) if info.gpu_names else "não detectada"),
        ])

        disk_rows = [self._disk_row(d) for d in info.disks]
        self._section("Discos", disk_rows or [("—", "nenhum disco fixo detectado")])

        self._refresh_btn.configure(state="normal")

    def _disk_row(self, d: DiskInfo) -> tuple[str, str]:
        return (
            d.mountpoint,
            f"{d.fstype} · {d.total_gb:.1f} GB total · {d.free_gb:.1f} GB livre "
            f"({d.percent:.1f}% usado)",
        )

    def _section(self, title: str, rows: list[tuple[str, str]]) -> None:
        ctk.CTkLabel(
            self._body, text=title, font=ctk.CTkFont(size=13, weight="bold"),
        ).pack(anchor="w", padx=4, pady=(10, 4))
        frame = ctk.CTkFrame(self._body, corner_radius=4)
        frame.pack(fill="x", padx=4)
        for label, value in rows:
            row = ctk.CTkFrame(frame, fg_color="transparent")
            row.pack(fill="x", padx=10, pady=2)
            ctk.CTkLabel(
                row, text=label, width=200, anchor="w",
                font=ctk.CTkFont(size=11, weight="bold"),
                text_color=("#333", "#ccc"),
            ).pack(side="left")
            ctk.CTkLabel(
                row, text=value, anchor="w", justify="left",
                font=ctk.CTkFont(size=11), wraplength=520,
            ).pack(side="left", fill="x", expand=True)

    # ---------- actions ----------

    def _open_logs(self) -> None:
        path = log_dir_path()
        try:
            os.startfile(path)  # noqa: SIM115 — Windows built-in launcher
        except OSError:
            subprocess.Popen(["explorer", path])

    def _open_repo(self) -> None:
        webbrowser.open(REPO_URL)
