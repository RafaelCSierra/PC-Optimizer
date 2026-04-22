"""Persistent JSON config stored in %LOCALAPPDATA%\\PCOptimizer\\config.json."""
from __future__ import annotations

import json
import logging
import os
import threading
from pathlib import Path
from typing import Any

log = logging.getLogger("pc_optimizer.config")


class Config:
    DEFAULTS: dict[str, Any] = {
        "dry_run": False,
        "theme": "dark",
    }

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or self._default_path()
        self._lock = threading.Lock()
        self._data: dict[str, Any] = self._load()

    @staticmethod
    def _default_path() -> Path:
        base = os.environ.get("LOCALAPPDATA") or str(Path.home())
        return Path(base) / "PCOptimizer" / "config.json"

    def _load(self) -> dict[str, Any]:
        try:
            raw = self.path.read_text(encoding="utf-8")
            data = json.loads(raw)
            if not isinstance(data, dict):
                return dict(self.DEFAULTS)
            merged = dict(self.DEFAULTS)
            merged.update(data)
            return merged
        except FileNotFoundError:
            return dict(self.DEFAULTS)
        except (OSError, json.JSONDecodeError) as e:
            log.warning("config corrompido/ilegível (%s) — usando defaults", e)
            return dict(self.DEFAULTS)

    def _save(self) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(
                json.dumps(self._data, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except OSError:
            log.exception("falha ao gravar config em %s", self.path)

    def get(self, key: str, default: Any = None) -> Any:
        with self._lock:
            if default is None:
                return self._data.get(key, self.DEFAULTS.get(key))
            return self._data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        with self._lock:
            self._data[key] = value
            self._save()


_instance: Config | None = None


def get_config() -> Config:
    global _instance
    if _instance is None:
        _instance = Config()
    return _instance
