"""Unit tests for dry-run flag, config persistence, and executor integration."""
from __future__ import annotations

import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

from src.core import dry_run
from src.core.executor import CommandExecutor
from src.utils import config as config_mod


class DryRunWithIsolatedConfig(unittest.TestCase):
    """Swap the config singleton with a tmp-path instance per test."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        tmp_cfg = config_mod.Config(path=Path(self._tmp.name) / "config.json")
        self._cfg_patch = mock.patch.object(config_mod, "_instance", tmp_cfg)
        self._cfg_patch.start()
        self.addCleanup(self._cfg_patch.stop)
        # Reset the in-memory dry_run flag — enter AND exit clean
        dry_run._enabled = False
        self.addCleanup(lambda: setattr(dry_run, "_enabled", False))

    def test_toggle_persists_to_config(self) -> None:
        self.assertFalse(dry_run.is_enabled())
        dry_run.set_enabled(True)
        self.assertTrue(dry_run.is_enabled())
        # Config should have the new value
        self.assertTrue(config_mod.get_config().get("dry_run"))

    def test_init_from_config_loads_value(self) -> None:
        config_mod.get_config().set("dry_run", True)
        dry_run._enabled = False  # force stale
        dry_run.init_from_config()
        self.assertTrue(dry_run.is_enabled())

    def test_executor_skips_real_command_when_dry_run(self) -> None:
        dry_run.set_enabled(True)
        lines: list[str] = []
        done = threading.Event()
        codes: list[int] = []

        def on_line(line: str) -> None:
            lines.append(line)

        def on_done(code: int) -> None:
            codes.append(code)
            done.set()

        ex = CommandExecutor()
        ex.run(
            "cmd /c echo this-should-not-actually-run",
            on_line=on_line,
            on_done=on_done,
        )
        self.assertTrue(done.wait(timeout=5))
        self.assertEqual(codes, [0])
        # Exactly the DRY-RUN message + exit marker — no real echo line ever emitted
        self.assertTrue(any("[DRY-RUN]" in line for line in lines))
        self.assertFalse(
            any(line.strip() == "this-should-not-actually-run" for line in lines),
            "dry-run should not produce the real echo output",
        )


if __name__ == "__main__":
    unittest.main()
