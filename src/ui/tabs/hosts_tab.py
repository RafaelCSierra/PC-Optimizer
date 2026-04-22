"""Hosts editor tab: editar C:\\Windows\\System32\\drivers\\etc\\hosts com segurança."""
from __future__ import annotations

from typing import TYPE_CHECKING

import customtkinter as ctk

from src.features import hosts
from src.ui import design
from src.ui.components.confirm_dialog import ConfirmDialog

if TYPE_CHECKING:
    from src.ui.main_window import MainWindow


class HostsTab(ctk.CTkFrame):
    def __init__(self, master, *, main_window: "MainWindow") -> None:
        super().__init__(master, fg_color="transparent")
        self.main_window = main_window
        self._original_content: str = ""

        self._build_header()
        self._build_editor()
        self._build_templates_bar()

        self.after(100, self.reload)

    # ---------- layout ----------

    def _build_header(self) -> None:
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(side="top", fill="x", padx=design.SP_MD, pady=(design.SP_MD, design.SP_XS))

        ctk.CTkLabel(
            header, text="🗒  Arquivo hosts", font=design.font_h2(),
        ).pack(side="left", padx=design.SP_XS)
        ctk.CTkLabel(
            header, text=str(hosts.HOSTS_PATH), font=design.font_mono(10),
            text_color=design.SUBTLE_TEXT,
        ).pack(side="left", padx=design.SP_MD)

        self._modified_var = ctk.StringVar(value="")
        ctk.CTkLabel(
            header, textvariable=self._modified_var,
            font=design.font_caption(), text_color=design.WARNING,
        ).pack(side="right", padx=design.SP_MD)

        actions = ctk.CTkFrame(self, fg_color="transparent")
        actions.pack(side="top", fill="x", padx=design.SP_MD, pady=design.SP_XS)

        ctk.CTkButton(
            actions, text="🔄  Recarregar", width=130, command=self.reload,
        ).pack(side="left", padx=design.SP_XS)
        ctk.CTkButton(
            actions, text="💾  Salvar", width=120,
            fg_color=design.SUCCESS, hover_color="#24833a",
            command=self._on_save,
        ).pack(side="left", padx=design.SP_XS)
        ctk.CTkButton(
            actions, text="📋  Backup", width=120, command=self._on_backup,
        ).pack(side="left", padx=design.SP_XS)
        self._restore_btn = ctk.CTkButton(
            actions, text="↩  Restaurar backup", width=170,
            fg_color="gray40", hover_color="gray30",
            command=self._on_restore,
        )
        self._restore_btn.pack(side="left", padx=design.SP_XS)
        ctk.CTkButton(
            actions, text="🔁  Restaurar padrão", width=170,
            fg_color=design.DANGER, hover_color=design.DANGER_HOVER,
            command=self._on_restore_default,
        ).pack(side="right", padx=design.SP_XS)

    def _build_editor(self) -> None:
        self._editor = ctk.CTkTextbox(
            self, wrap="none", font=design.font_mono(12),
        )
        self._editor.pack(
            side="top", fill="both", expand=True,
            padx=design.SP_MD, pady=design.SP_XS,
        )
        self._editor.bind("<<Modified>>", self._on_editor_modified)

    def _build_templates_bar(self) -> None:
        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.pack(side="bottom", fill="x", padx=design.SP_MD, pady=design.SP_MD)
        ctk.CTkLabel(
            bar, text="Inserir bloco:", font=design.font_body("bold"),
        ).pack(side="left", padx=(0, design.SP_SM))
        for name in hosts.TEMPLATES:
            ctk.CTkButton(
                bar, text=f"+  {name}", width=220,
                command=lambda n=name: self._on_insert_template(n),
            ).pack(side="left", padx=design.SP_XS)

    # ---------- state ----------

    def reload(self) -> None:
        content = hosts.read_hosts()
        self._original_content = content
        self._editor.configure(state="normal")
        self._editor.delete("1.0", "end")
        self._editor.insert("1.0", content)
        self._editor.edit_modified(False)
        self._update_modified_indicator()
        self._update_restore_btn()

    def _current_content(self) -> str:
        return self._editor.get("1.0", "end-1c")

    def _on_editor_modified(self, _event=None) -> None:
        # <<Modified>> fires once until we reset edit_modified
        self._editor.edit_modified(False)
        self._update_modified_indicator()

    def _update_modified_indicator(self) -> None:
        if self._current_content() != self._original_content:
            self._modified_var.set("• modificado (não salvo)")
        else:
            self._modified_var.set("")

    def _update_restore_btn(self) -> None:
        state = "normal" if hosts.has_backup() else "disabled"
        self._restore_btn.configure(state=state)

    # ---------- actions ----------

    def _on_save(self) -> None:
        content = self._current_content()
        if content == self._original_content:
            self.main_window.console.append_line("[hosts] sem alterações para salvar")
            return

        confirmed = ConfirmDialog.ask(
            self.main_window,
            title="Salvar alterações no hosts?",
            description=(
                "Esta operação vai sobrescrever o arquivo hosts do Windows. "
                "Um backup atual NÃO é criado automaticamente — use o botão Backup antes se quiser reverter."
            ),
            actions=[
                f"Arquivo: {hosts.HOSTS_PATH}",
                f"Tamanho novo: {len(content)} bytes",
                f"Tamanho anterior: {len(self._original_content)} bytes",
            ],
            confirm_label="Salvar",
        )
        if not confirmed:
            self.main_window.console.append_line("[hosts] save cancelado")
            return

        ok, msg = hosts.write_hosts(content)
        self.main_window.console.append_line(f"[hosts] {msg}")
        if ok:
            self._original_content = content
            self._update_modified_indicator()

    def _on_backup(self) -> None:
        ok, msg = hosts.backup_hosts()
        self.main_window.console.append_line(f"[hosts] {msg}")
        self._update_restore_btn()

    def _on_restore(self) -> None:
        if not hosts.has_backup():
            self.main_window.console.append_line("[hosts] nenhum backup para restaurar")
            return
        confirmed = ConfirmDialog.ask(
            self.main_window,
            title="Restaurar backup do hosts?",
            description="O conteúdo atual será sobrescrito pelo backup mais recente criado pelo PC Optimizer.",
            actions=[f"Backup: {hosts.HOSTS_BACKUP_PATH.name}"],
            confirm_label="Restaurar",
        )
        if not confirmed:
            return
        ok, msg = hosts.restore_backup()
        self.main_window.console.append_line(f"[hosts] {msg}")
        if ok:
            self.reload()

    def _on_restore_default(self) -> None:
        confirmed = ConfirmDialog.ask(
            self.main_window,
            title="Restaurar hosts padrão?",
            description=(
                "Vai escrever o conteúdo padrão do hosts (praticamente só um header de comentários). "
                "Todas as entradas atuais serão perdidas."
            ),
            actions=["Conteúdo: template padrão do Windows"],
            confirm_label="Restaurar padrão",
        )
        if not confirmed:
            return
        ok, msg = hosts.write_hosts(hosts.DEFAULT_HOSTS)
        self.main_window.console.append_line(f"[hosts] {msg}")
        if ok:
            self._original_content = hosts.DEFAULT_HOSTS
            self.reload()

    def _on_insert_template(self, name: str) -> None:
        entries = hosts.TEMPLATES.get(name)
        if not entries:
            return
        block = hosts.render_template(name, entries)
        self._editor.insert("end", block)
        self._update_modified_indicator()
        self.main_window.console.append_line(
            f"[hosts] bloco '{name}' inserido ({len(entries)} entradas) — revise e salve"
        )
