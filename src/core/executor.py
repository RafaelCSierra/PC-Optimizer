"""Async command executor: runs shell commands in a thread, streaming output."""
from __future__ import annotations

import locale
import logging
import subprocess
import threading
from collections.abc import Callable, Sequence
from dataclasses import dataclass

LineCallback = Callable[[str], None]
DoneCallback = Callable[[int], None]

_CREATE_NO_WINDOW = 0x08000000


@dataclass
class RunHandle:
    """Handle returned by CommandExecutor.run — allows cancellation and status checks."""

    thread: threading.Thread | None = None
    process: subprocess.Popen | None = None
    cancelled: bool = False

    def cancel(self) -> None:
        self.cancelled = True
        if self.process and self.process.poll() is None:
            try:
                self.process.terminate()
            except Exception:
                pass

    def is_running(self) -> bool:
        return bool(self.thread and self.thread.is_alive())


class CommandExecutor:
    """Executes commands asynchronously, streaming stdout+stderr line by line.

    Callbacks fire from the executor thread. UI callers must marshal to the GUI
    thread themselves (OutputConsole does this via Tk's after(0, ...)).
    """

    def __init__(self, logger: logging.Logger | None = None) -> None:
        self._log = logger or logging.getLogger("pc_optimizer.executor")

    def run(
        self,
        cmd: str | Sequence[str],
        on_line: LineCallback,
        on_done: DoneCallback | None = None,
        *,
        shell: bool | None = None,
        cwd: str | None = None,
    ) -> RunHandle:
        """Start cmd in a background thread. Returns a handle immediately."""
        if shell is None:
            shell = isinstance(cmd, str)

        handle = RunHandle()
        pretty = cmd if isinstance(cmd, str) else " ".join(cmd)

        def worker() -> None:
            from src.core import dry_run

            if dry_run.is_enabled():
                self._log.info("[DRY-RUN] would exec: %s", pretty)
                on_line(f"[DRY-RUN] would execute: {pretty}")
                on_line("[exit code 0 (dry-run)]")
                if on_done:
                    on_done(0)
                return

            self._log.info("exec: %s", pretty)
            on_line(f"$ {pretty}")
            try:
                handle.process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    shell=shell,
                    cwd=cwd,
                    text=True,
                    bufsize=1,
                    encoding=locale.getpreferredencoding(False),
                    errors="replace",
                    creationflags=_CREATE_NO_WINDOW,
                )
                assert handle.process.stdout is not None
                try:
                    for line in handle.process.stdout:
                        if handle.cancelled:
                            break
                        on_line(line.rstrip("\r\n"))
                finally:
                    handle.process.stdout.close()
                exit_code = handle.process.wait()
                self._log.info("exit: %d (%s)", exit_code, pretty)
                on_line(f"[exit code {exit_code}]")
                if on_done:
                    on_done(exit_code)
            except FileNotFoundError as e:
                msg = f"[erro] comando não encontrado: {e}"
                self._log.error(msg)
                on_line(msg)
                if on_done:
                    on_done(-1)
            except Exception as e:
                msg = f"[erro] {type(e).__name__}: {e}"
                self._log.exception("executor failed for: %s", pretty)
                on_line(msg)
                if on_done:
                    on_done(-1)

        thread = threading.Thread(target=worker, daemon=True, name="cmd-executor")
        handle.thread = thread
        thread.start()
        return handle
