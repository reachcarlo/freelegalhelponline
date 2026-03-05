"""Litigation posture (aggressiveness) — platform-level enum.

Controls how aggressively attorney-facing tools generate objections,
arguments, and other adversarial output. Each tool interprets posture
through its own prompt template; this module provides the shared enum
and config loader.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

import yaml

CONFIG_PATH = Path("config/posture.yaml")


class LitigationPosture(str, Enum):
    """How aggressively the tool should object / argue.

    Values are wire-format strings used in API requests and config files.
    """

    AGGRESSIVE = "aggressive"
    BALANCED = "balanced"
    SELECTIVE = "selective"


@dataclass(frozen=True)
class PostureInfo:
    """Display metadata for a single posture level."""

    label: str
    description: str
    tooltip: str


def load_posture_config(path: Path | None = None) -> dict[LitigationPosture, PostureInfo]:
    """Load posture display metadata from YAML config.

    Returns:
        Mapping from posture enum to display info.

    Raises:
        FileNotFoundError: If the config file doesn't exist.
    """
    config_path = path or CONFIG_PATH
    raw: dict[str, Any] = yaml.safe_load(config_path.read_text())

    result: dict[LitigationPosture, PostureInfo] = {}
    for entry in raw.get("postures", []):
        posture = LitigationPosture(entry["id"])
        result[posture] = PostureInfo(
            label=entry["label"],
            description=entry["description"],
            tooltip=entry["tooltip"],
        )
    return result
