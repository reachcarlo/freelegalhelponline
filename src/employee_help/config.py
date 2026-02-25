"""Configuration loading and validation for the Employee Help scraper.

Loads and validates scraper.yaml configuration, providing typed dataclass
access to crawler parameters, chunking settings, and storage configuration.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass
class ChunkingConfig:
    """Chunking parameters for document segmentation."""

    min_tokens: int
    max_tokens: int
    overlap_tokens: int

    def __post_init__(self) -> None:
        """Validate chunking parameters."""
        if self.min_tokens < 1:
            raise ValueError("min_tokens must be >= 1")
        if self.max_tokens < self.min_tokens:
            raise ValueError("max_tokens must be >= min_tokens")
        if self.overlap_tokens < 0:
            raise ValueError("overlap_tokens must be >= 0")
        if self.overlap_tokens >= self.max_tokens:
            raise ValueError("overlap_tokens must be < max_tokens")


@dataclass
class CrawlConfig:
    """Complete configuration for the web crawler and processing pipeline."""

    seed_urls: list[str]
    allowlist_patterns: list[str]
    blocklist_patterns: list[str]
    rate_limit_seconds: float
    max_pages: int
    chunking: ChunkingConfig
    database_path: str

    def __post_init__(self) -> None:
        """Validate configuration after initialization."""
        if not self.seed_urls:
            raise ValueError("At least one seed URL is required")
        if not self.allowlist_patterns:
            raise ValueError("At least one allowlist pattern is required")
        if self.rate_limit_seconds < 0:
            raise ValueError("rate_limit_seconds must be >= 0")
        if self.max_pages < 1:
            raise ValueError("max_pages must be >= 1")
        if not self.database_path:
            raise ValueError("database_path must be specified")

        # Validate that all patterns are valid regexes
        for pattern in self.allowlist_patterns:
            try:
                re.compile(pattern)
            except re.error as e:
                raise ValueError(f"Invalid allowlist pattern '{pattern}': {e}")

        for pattern in self.blocklist_patterns:
            try:
                re.compile(pattern)
            except re.error as e:
                raise ValueError(f"Invalid blocklist pattern '{pattern}': {e}")


def load_config(config_path: str | Path = "config/scraper.yaml") -> CrawlConfig:
    """Load and validate crawler configuration from YAML file.

    Args:
        config_path: Path to the scraper.yaml configuration file.
            Defaults to "config/scraper.yaml" relative to current directory.

    Returns:
        Validated CrawlConfig dataclass instance.

    Raises:
        FileNotFoundError: If the configuration file does not exist.
        ValueError: If the configuration is invalid or required fields are missing.
        yaml.YAMLError: If the YAML file is malformed.
    """
    config_path = Path(config_path)

    if not config_path.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")

    with open(config_path, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if not isinstance(data, dict):
        raise ValueError("Configuration file must contain a YAML dictionary")

    # Extract and validate required top-level fields
    seed_urls = data.get("seed_urls")
    if not seed_urls:
        raise ValueError("Missing required field: seed_urls")
    if not isinstance(seed_urls, list):
        raise ValueError("seed_urls must be a list")

    allowlist_patterns = data.get("allowlist_patterns")
    if not allowlist_patterns:
        raise ValueError("Missing required field: allowlist_patterns")
    if not isinstance(allowlist_patterns, list):
        raise ValueError("allowlist_patterns must be a list")

    blocklist_patterns = data.get("blocklist_patterns", [])
    if not isinstance(blocklist_patterns, list):
        raise ValueError("blocklist_patterns must be a list")

    rate_limit_seconds = data.get("rate_limit_seconds")
    if rate_limit_seconds is None:
        raise ValueError("Missing required field: rate_limit_seconds")
    try:
        rate_limit_seconds = float(rate_limit_seconds)
    except (TypeError, ValueError):
        raise ValueError("rate_limit_seconds must be a number")

    max_pages = data.get("max_pages")
    if max_pages is None:
        raise ValueError("Missing required field: max_pages")
    try:
        max_pages = int(max_pages)
    except (TypeError, ValueError):
        raise ValueError("max_pages must be an integer")

    database_path = data.get("database_path")
    if not database_path:
        raise ValueError("Missing required field: database_path")

    # Extract chunking configuration
    if "chunking" not in data:
        raise ValueError("Missing required field: chunking")
    chunking_data = data.get("chunking")
    if not isinstance(chunking_data, dict):
        raise ValueError("chunking must be a dictionary")

    try:
        chunking = ChunkingConfig(
            min_tokens=int(chunking_data.get("min_tokens", 200)),
            max_tokens=int(chunking_data.get("max_tokens", 1500)),
            overlap_tokens=int(chunking_data.get("overlap_tokens", 100)),
        )
    except (TypeError, ValueError) as e:
        raise ValueError(f"Invalid chunking configuration: {e}")

    return CrawlConfig(
        seed_urls=seed_urls,
        allowlist_patterns=allowlist_patterns,
        blocklist_patterns=blocklist_patterns,
        rate_limit_seconds=rate_limit_seconds,
        max_pages=max_pages,
        chunking=chunking,
        database_path=database_path,
    )
