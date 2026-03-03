"""Compatibility helpers for the discovery module."""

from __future__ import annotations

import sys

if sys.version_info >= (3, 12):
    from typing import TypeAlias
else:
    from typing_extensions import TypeAlias

__all__ = ["TypeAlias"]
