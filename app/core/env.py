from __future__ import annotations

import os
from pathlib import Path


def load_app_env() -> None:
    """Load environment variables from a local .env file if present.

    Uses python-dotenv when available; otherwise falls back to a minimal parser
    that supports simple KEY=VALUE lines.
    """
    try:
        from dotenv import load_dotenv
    except ModuleNotFoundError:
        _load_env_file_manually()
        return

    load_dotenv(override=False)


def _load_env_file_manually() -> None:
    env_path = Path(__file__).resolve().parents[2] / ".env"
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        if "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key or key in os.environ:
            continue

        if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
            value = value[1:-1]

        os.environ[key] = value