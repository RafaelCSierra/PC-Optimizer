"""Unit tests for CommandExecutor. No GUI required."""
from __future__ import annotations

import threading
import unittest

from src.core import dry_run
from src.core.executor import CommandExecutor


class ExecutorTest(unittest.TestCase):
    def setUp(self) -> None:
        # Executor tests assume dry-run is OFF — isolate from other test files
        # that may have flipped the module-level flag.
        dry_run._enabled = False
    def _run_and_wait(self, cmd: str, timeout: float = 10.0) -> tuple[list[str], int]:
        lines: list[str] = []
        exit_codes: list[int] = []
        done = threading.Event()

        def on_line(line: str) -> None:
            lines.append(line)

        def on_done(code: int) -> None:
            exit_codes.append(code)
            done.set()

        ex = CommandExecutor()
        ex.run(cmd, on_line=on_line, on_done=on_done)
        self.assertTrue(done.wait(timeout=timeout), f"timeout waiting for: {cmd}")
        self.assertEqual(len(exit_codes), 1)
        return lines, exit_codes[0]

    def test_echo_streams_output(self) -> None:
        lines, code = self._run_and_wait("cmd /c echo pc-optimizer-test")
        self.assertEqual(code, 0)
        self.assertTrue(any("pc-optimizer-test" in line for line in lines))

    def test_nonzero_exit_code_is_reported(self) -> None:
        _, code = self._run_and_wait("cmd /c exit 7")
        self.assertEqual(code, 7)

    def test_missing_command_reports_error(self) -> None:
        lines, code = self._run_and_wait("definitely-not-a-real-binary-xyz")
        # Shell returns nonzero when command is not found
        self.assertNotEqual(code, 0)
        self.assertTrue(len(lines) >= 1)


if __name__ == "__main__":
    unittest.main()
