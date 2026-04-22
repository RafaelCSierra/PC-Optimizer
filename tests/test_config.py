"""Unit tests for JSON config persistence."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from src.utils.config import Config


class ConfigTest(unittest.TestCase):
    def test_defaults_when_file_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cfg = Config(path=Path(tmp) / "nope.json")
            self.assertFalse(cfg.get("dry_run"))
            self.assertEqual(cfg.get("theme"), "dark")

    def test_set_persists_across_instances(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "cfg.json"
            Config(path=path).set("dry_run", True)
            cfg2 = Config(path=path)
            self.assertTrue(cfg2.get("dry_run"))

    def test_corrupt_file_falls_back_to_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "broken.json"
            path.write_text("{ not valid json", encoding="utf-8")
            cfg = Config(path=path)
            self.assertFalse(cfg.get("dry_run"))

    def test_unknown_keys_use_provided_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cfg = Config(path=Path(tmp) / "x.json")
            self.assertEqual(cfg.get("does_not_exist", "fallback"), "fallback")


if __name__ == "__main__":
    unittest.main()
