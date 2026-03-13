"""Configuration loader for CSRF Shield AI."""

import logging
from pathlib import Path
from typing import Any, Dict

import yaml

logger = logging.getLogger(__name__)

_DEFAULT_SETTINGS_PATH = (
    Path(__file__).resolve().parent.parent / "config" / "settings.yaml"
)


def load_settings(path: Path = _DEFAULT_SETTINGS_PATH) -> Dict[str, Any]:
    """Load application settings from settings.yaml."""
    if not path.exists():
        logger.warning("Settings file not found: %s", path)
        return {}

    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


SETTINGS = load_settings()
