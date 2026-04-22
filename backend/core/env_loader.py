"""Lightweight .env loader for local development."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable


def _find_env_files() -> Iterable[Path]:
    """Yield candidate .env files from the repository root and backend folder."""

    root = Path(__file__).resolve().parents[2]
    yield root / ".env"
    yield root / "backend" / ".env"


def _parse_env_line(line: str) -> tuple[str, str] | None:
    stripped = line.strip()
    if not stripped or stripped.startswith("#"):
        return None
    if "=" not in stripped:
        return None

    key, value = stripped.split("=", 1)
    key = key.strip()
    if not key:
        return None

    value = value.strip()
    if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
        value = value[1:-1]

    return key, value


def load_dotenv_files(*, override: bool = False) -> None:
    """Load simple KEY=VALUE pairs into os.environ if present."""

    for path in _find_env_files():
        if not path.exists() or not path.is_file():
            continue

        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError:
            continue

        for line in lines:
            parsed = _parse_env_line(line)
            if parsed is None:
                continue
            key, value = parsed
            if override or key not in os.environ:
                os.environ[key] = value
