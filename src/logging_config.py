from __future__ import annotations

import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

_CONFIGURED = False


def _truthy(value: str | None) -> bool:
    if value is None:
        return False
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _parse_level(value: str | int | None) -> int:
    if value is None:
        return logging.INFO
    if isinstance(value, int):
        return value
    name = value.strip().upper()
    return getattr(logging, name, logging.INFO)


def _project_root() -> Path:
    return Path(__file__).parent.parent


def _default_log_path() -> Path:
    rel = os.getenv("LOG_FILE", "logs/app.log").strip()
    return (_project_root() / rel).resolve()


def _root_has_file_handler(root: logging.Logger, path: Path) -> bool:
    for handler in root.handlers:
        if isinstance(handler, logging.FileHandler):
            try:
                if Path(handler.baseFilename).resolve() == path.resolve():
                    return True
            except Exception:
                continue
    return False


def configure_logging(*, level: str | int | None = None, log_file: str | Path | None = None) -> None:
    """Configure application logging once (safe to call multiple times)."""
    global _CONFIGURED
    if _CONFIGURED:
        return

    root = logging.getLogger()
    log_level = _parse_level(level or os.getenv("LOG_LEVEL"))
    root.setLevel(log_level)

    force = _truthy(os.getenv("FORCE_LOG_CONFIG"))

    if force:
        for handler in root.handlers[:]:
            root.removeHandler(handler)

    if not root.handlers:
        console = logging.StreamHandler(sys.stdout)
        console.setLevel(log_level)
        console.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s %(name)s - %(message)s")
        )
        root.addHandler(console)

    path = Path(log_file).resolve() if log_file is not None else _default_log_path()
    if os.getenv("LOG_FILE", "logs/app.log").strip() == "":
        _CONFIGURED = True
        return

    if not _root_has_file_handler(root, path):
        path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            path,
            maxBytes=2 * 1024 * 1024,
            backupCount=3,
            encoding="utf-8",
        )
        file_handler.setLevel(log_level)
        file_handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s %(name)s - %(message)s")
        )
        root.addHandler(file_handler)

    _CONFIGURED = True

