"""Configuration loading and validation for the Employee Help scraper.

Supports two config formats:
- Legacy: single scraper.yaml (Phase 1 backward compatibility)
- Source: per-source YAML in config/sources/ (Phase 1.5+)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from employee_help.storage.models import SourceType


# ── Shared chunking config ────────────────────────────────────


@dataclass
class ChunkingConfig:
    """Chunking parameters for document segmentation."""

    min_tokens: int = 200
    max_tokens: int = 1500
    overlap_tokens: int = 100
    strategy: str = "heading_based"

    def __post_init__(self) -> None:
        if self.min_tokens < 1:
            raise ValueError("min_tokens must be >= 1")
        if self.max_tokens < self.min_tokens:
            raise ValueError("max_tokens must be >= min_tokens")
        if self.overlap_tokens < 0:
            raise ValueError("overlap_tokens must be >= 0")
        if self.overlap_tokens >= self.max_tokens:
            raise ValueError("overlap_tokens must be < max_tokens")
        if self.strategy not in ("heading_based", "section_boundary"):
            raise ValueError(f"Unknown chunking strategy: {self.strategy}")


# ── Legacy CrawlConfig (Phase 1 backward compat) ─────────────


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
        _validate_patterns(self.allowlist_patterns, "allowlist")
        _validate_patterns(self.blocklist_patterns, "blocklist")


# ── SourceConfig (Phase 1.5+) ────────────────────────────────


@dataclass
class ExtractionConfig:
    """Source-specific extraction parameters."""

    content_selector: str | None = None
    boilerplate_patterns: list[str] = field(default_factory=list)
    content_category: str = "agency_guidance"


@dataclass
class StatutoryConfig:
    """Configuration for statutory code extraction."""

    code_abbreviation: str  # e.g., "LAB", "GOV"
    code_name: str  # e.g., "Labor Code"
    citation_prefix: str  # e.g., "Cal. Lab. Code"
    target_divisions: list[str] = field(default_factory=list)  # Empty = all divisions
    method: str = "pubinfo"  # "pubinfo" (default) or "web"


@dataclass
class CaselawConfig:
    """Configuration for case law ingestion from CourtListener."""

    courts: list[str] = field(default_factory=lambda: ["cal", "calctapp"])
    filed_after: str | None = None
    filed_before: str | None = None
    max_opinions: int = 5000
    search_queries: list[str] = field(default_factory=list)


@dataclass
class SourceConfig:
    """Configuration for a single data source (agency or statutory code)."""

    name: str
    slug: str
    source_type: SourceType
    base_url: str
    enabled: bool = True

    # Crawl settings
    seed_urls: list[str] = field(default_factory=list)
    allowlist_patterns: list[str] = field(default_factory=list)
    blocklist_patterns: list[str] = field(default_factory=list)
    rate_limit_seconds: float = 2.0
    max_pages: int = 100

    # Extraction
    extraction: ExtractionConfig = field(default_factory=ExtractionConfig)

    # Chunking
    chunking: ChunkingConfig = field(default_factory=ChunkingConfig)

    # Statutory code settings (only for source_type == statutory_code)
    statutory: StatutoryConfig | None = None

    # Case law settings (only for CourtListener source)
    caselaw: CaselawConfig | None = None

    # Storage
    database_path: str = "data/employee_help.db"

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("Source name is required")
        if not self.slug:
            raise ValueError("Source slug is required")
        if not self.base_url:
            raise ValueError("Source base_url is required")
        if self.rate_limit_seconds < 0:
            raise ValueError("rate_limit_seconds must be >= 0")
        if self.max_pages < 1:
            raise ValueError("max_pages must be >= 1")
        _validate_patterns(self.allowlist_patterns, "allowlist")
        _validate_patterns(self.blocklist_patterns, "blocklist")

    def to_crawl_config(self) -> CrawlConfig:
        """Convert to a CrawlConfig for backward compatibility with existing pipeline."""
        return CrawlConfig(
            seed_urls=self.seed_urls,
            allowlist_patterns=self.allowlist_patterns,
            blocklist_patterns=self.blocklist_patterns,
            rate_limit_seconds=self.rate_limit_seconds,
            max_pages=self.max_pages,
            chunking=self.chunking,
            database_path=self.database_path,
        )


# ── Loaders ───────────────────────────────────────────────────


def load_config(config_path: str | Path = "config/scraper.yaml") -> CrawlConfig:
    """Load legacy crawler configuration from YAML file.

    Kept for Phase 1 backward compatibility. New code should use
    load_source_config() or load_all_source_configs().
    """
    config_path = Path(config_path)

    if not config_path.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")

    with open(config_path, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if not isinstance(data, dict):
        raise ValueError("Configuration file must contain a YAML dictionary")

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


def load_source_config(config_path: str | Path) -> SourceConfig:
    """Load a per-source configuration from YAML.

    Args:
        config_path: Path to the source config YAML file.

    Returns:
        Validated SourceConfig.
    """
    config_path = Path(config_path)

    if not config_path.exists():
        raise FileNotFoundError(f"Source config not found: {config_path}")

    with open(config_path, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if not isinstance(data, dict):
        raise ValueError(f"Source config must be a YAML dictionary: {config_path}")

    # Parse source identity
    source_data = data.get("source", {})
    if not isinstance(source_data, dict):
        raise ValueError("Missing or invalid 'source' section")

    name = source_data.get("name")
    if not name:
        raise ValueError("Missing required field: source.name")

    slug = source_data.get("slug")
    if not slug:
        raise ValueError("Missing required field: source.slug")

    source_type_str = source_data.get("source_type", "agency")
    try:
        source_type = SourceType(source_type_str)
    except ValueError:
        raise ValueError(f"Invalid source_type: {source_type_str}")

    base_url = source_data.get("base_url")
    if not base_url:
        raise ValueError("Missing required field: source.base_url")

    enabled = source_data.get("enabled", True)

    # Parse crawl settings
    crawl_data = data.get("crawl", {})
    seed_urls = crawl_data.get("seed_urls", [])
    allowlist_patterns = crawl_data.get("allowlist_patterns", [])
    blocklist_patterns = crawl_data.get("blocklist_patterns", [])
    rate_limit_seconds = float(crawl_data.get("rate_limit_seconds", 2.0))
    max_pages = int(crawl_data.get("max_pages", 100))

    # Parse extraction settings
    extraction_data = data.get("extraction", {})
    extraction = ExtractionConfig(
        content_selector=extraction_data.get("content_selector"),
        boilerplate_patterns=extraction_data.get("boilerplate_patterns", []),
        content_category=extraction_data.get("content_category", "agency_guidance"),
    )

    # Parse chunking settings
    chunking_data = data.get("chunking", {})
    chunking = ChunkingConfig(
        min_tokens=int(chunking_data.get("min_tokens", 200)),
        max_tokens=int(chunking_data.get("max_tokens", 1500)),
        overlap_tokens=int(chunking_data.get("overlap_tokens", 100)),
        strategy=chunking_data.get("strategy", "heading_based"),
    )

    # Parse statutory configuration (optional, for statutory_code sources)
    statutory: StatutoryConfig | None = None
    statutory_data = data.get("statutory")
    if statutory_data and isinstance(statutory_data, dict):
        code_abbr = statutory_data.get("code_abbreviation")
        code_name_val = statutory_data.get("code_name")
        citation_pfx = statutory_data.get("citation_prefix")
        if code_abbr and code_name_val and citation_pfx:
            method = statutory_data.get("method", "pubinfo")
            if method not in ("pubinfo", "web", "caci_pdf", "dlse_opinions", "dlse_manual"):
                raise ValueError(f"Invalid statutory method: {method}. Must be 'pubinfo', 'web', 'caci_pdf', 'dlse_opinions', or 'dlse_manual'.")
            statutory = StatutoryConfig(
                code_abbreviation=code_abbr,
                code_name=code_name_val,
                citation_prefix=citation_pfx,
                target_divisions=statutory_data.get("target_divisions", []),
                method=method,
            )

    # Parse case law configuration (optional, for CourtListener source)
    caselaw: CaselawConfig | None = None
    caselaw_data = data.get("caselaw")
    if caselaw_data and isinstance(caselaw_data, dict):
        caselaw = CaselawConfig(
            courts=caselaw_data.get("courts", ["cal", "calctapp"]),
            filed_after=caselaw_data.get("filed_after"),
            filed_before=caselaw_data.get("filed_before"),
            max_opinions=int(caselaw_data.get("max_opinions", 5000)),
            search_queries=caselaw_data.get("search_queries", []),
        )

    # Parse database path
    database_path = data.get("database_path", "data/employee_help.db")

    return SourceConfig(
        name=name,
        slug=slug,
        source_type=source_type,
        base_url=base_url,
        enabled=enabled,
        seed_urls=seed_urls,
        allowlist_patterns=allowlist_patterns,
        blocklist_patterns=blocklist_patterns,
        rate_limit_seconds=rate_limit_seconds,
        max_pages=max_pages,
        extraction=extraction,
        chunking=chunking,
        statutory=statutory,
        caselaw=caselaw,
        database_path=database_path,
    )


def load_all_source_configs(
    config_dir: str | Path = "config/sources",
    enabled_only: bool = True,
) -> list[SourceConfig]:
    """Load all source configurations from a directory.

    Args:
        config_dir: Directory containing per-source YAML files.
        enabled_only: If True, skip sources with enabled=false.

    Returns:
        List of validated SourceConfig objects.
    """
    config_dir = Path(config_dir)

    if not config_dir.exists():
        raise FileNotFoundError(f"Source config directory not found: {config_dir}")

    configs = []
    for yaml_file in sorted(config_dir.glob("*.yaml")):
        source_config = load_source_config(yaml_file)
        if enabled_only and not source_config.enabled:
            continue
        configs.append(source_config)

    return configs


# ── Helpers ───────────────────────────────────────────────────


def _validate_patterns(patterns: list[str], label: str) -> None:
    for pattern in patterns:
        try:
            re.compile(pattern)
        except re.error as e:
            raise ValueError(f"Invalid {label} pattern '{pattern}': {e}")
