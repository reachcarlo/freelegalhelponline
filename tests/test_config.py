"""Tests for configuration loading and validation."""

import tempfile
from pathlib import Path

import pytest
import yaml

from employee_help.config import ChunkingConfig, CrawlConfig, load_config


class TestChunkingConfig:
    """Tests for ChunkingConfig dataclass validation."""

    def test_valid_configuration(self) -> None:
        """Valid chunking configuration should create instance."""
        config = ChunkingConfig(min_tokens=200, max_tokens=1500, overlap_tokens=100)
        assert config.min_tokens == 200
        assert config.max_tokens == 1500
        assert config.overlap_tokens == 100

    def test_min_tokens_must_be_positive(self) -> None:
        """min_tokens must be >= 1."""
        with pytest.raises(ValueError, match="min_tokens must be >= 1"):
            ChunkingConfig(min_tokens=0, max_tokens=1500, overlap_tokens=100)

    def test_max_tokens_must_be_at_least_min_tokens(self) -> None:
        """max_tokens must be >= min_tokens."""
        with pytest.raises(ValueError, match="max_tokens must be >= min_tokens"):
            ChunkingConfig(min_tokens=1500, max_tokens=200, overlap_tokens=100)

    def test_overlap_tokens_must_be_non_negative(self) -> None:
        """overlap_tokens must be >= 0."""
        with pytest.raises(ValueError, match="overlap_tokens must be >= 0"):
            ChunkingConfig(min_tokens=200, max_tokens=1500, overlap_tokens=-1)

    def test_overlap_tokens_must_be_less_than_max_tokens(self) -> None:
        """overlap_tokens must be < max_tokens."""
        with pytest.raises(ValueError, match="overlap_tokens must be < max_tokens"):
            ChunkingConfig(min_tokens=200, max_tokens=1500, overlap_tokens=1500)


class TestCrawlConfig:
    """Tests for CrawlConfig dataclass validation."""

    def test_valid_configuration(self) -> None:
        """Valid crawl configuration should create instance."""
        config = CrawlConfig(
            seed_urls=["https://example.com"],
            allowlist_patterns=["example\\.com"],
            blocklist_patterns=["example\\.com/admin"],
            rate_limit_seconds=1.0,
            max_pages=100,
            chunking=ChunkingConfig(min_tokens=200, max_tokens=1500, overlap_tokens=100),
            database_path="data/test.db",
        )
        assert config.seed_urls == ["https://example.com"]
        assert config.max_pages == 100

    def test_seed_urls_required(self) -> None:
        """seed_urls cannot be empty."""
        with pytest.raises(ValueError, match="At least one seed URL"):
            CrawlConfig(
                seed_urls=[],
                allowlist_patterns=["example\\.com"],
                blocklist_patterns=[],
                rate_limit_seconds=1.0,
                max_pages=100,
                chunking=ChunkingConfig(min_tokens=200, max_tokens=1500, overlap_tokens=100),
                database_path="data/test.db",
            )

    def test_allowlist_patterns_required(self) -> None:
        """allowlist_patterns cannot be empty."""
        with pytest.raises(ValueError, match="At least one allowlist pattern"):
            CrawlConfig(
                seed_urls=["https://example.com"],
                allowlist_patterns=[],
                blocklist_patterns=[],
                rate_limit_seconds=1.0,
                max_pages=100,
                chunking=ChunkingConfig(min_tokens=200, max_tokens=1500, overlap_tokens=100),
                database_path="data/test.db",
            )

    def test_rate_limit_must_be_non_negative(self) -> None:
        """rate_limit_seconds must be >= 0."""
        with pytest.raises(ValueError, match="rate_limit_seconds must be >= 0"):
            CrawlConfig(
                seed_urls=["https://example.com"],
                allowlist_patterns=["example\\.com"],
                blocklist_patterns=[],
                rate_limit_seconds=-1.0,
                max_pages=100,
                chunking=ChunkingConfig(min_tokens=200, max_tokens=1500, overlap_tokens=100),
                database_path="data/test.db",
            )

    def test_max_pages_must_be_positive(self) -> None:
        """max_pages must be >= 1."""
        with pytest.raises(ValueError, match="max_pages must be >= 1"):
            CrawlConfig(
                seed_urls=["https://example.com"],
                allowlist_patterns=["example\\.com"],
                blocklist_patterns=[],
                rate_limit_seconds=1.0,
                max_pages=0,
                chunking=ChunkingConfig(min_tokens=200, max_tokens=1500, overlap_tokens=100),
                database_path="data/test.db",
            )

    def test_database_path_required(self) -> None:
        """database_path cannot be empty."""
        with pytest.raises(ValueError, match="database_path must be specified"):
            CrawlConfig(
                seed_urls=["https://example.com"],
                allowlist_patterns=["example\\.com"],
                blocklist_patterns=[],
                rate_limit_seconds=1.0,
                max_pages=100,
                chunking=ChunkingConfig(min_tokens=200, max_tokens=1500, overlap_tokens=100),
                database_path="",
            )

    def test_invalid_allowlist_regex(self) -> None:
        """Invalid regex in allowlist_patterns should raise ValueError."""
        with pytest.raises(ValueError, match="Invalid allowlist pattern"):
            CrawlConfig(
                seed_urls=["https://example.com"],
                allowlist_patterns=["[invalid(regex"],
                blocklist_patterns=[],
                rate_limit_seconds=1.0,
                max_pages=100,
                chunking=ChunkingConfig(min_tokens=200, max_tokens=1500, overlap_tokens=100),
                database_path="data/test.db",
            )

    def test_invalid_blocklist_regex(self) -> None:
        """Invalid regex in blocklist_patterns should raise ValueError."""
        with pytest.raises(ValueError, match="Invalid blocklist pattern"):
            CrawlConfig(
                seed_urls=["https://example.com"],
                allowlist_patterns=["example\\.com"],
                blocklist_patterns=["[invalid(regex"],
                rate_limit_seconds=1.0,
                max_pages=100,
                chunking=ChunkingConfig(min_tokens=200, max_tokens=1500, overlap_tokens=100),
                database_path="data/test.db",
            )


class TestLoadConfig:
    """Tests for the load_config function."""

    def test_load_valid_config(self) -> None:
        """Loading valid YAML config should return CrawlConfig."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(
                {
                    "seed_urls": ["https://example.com"],
                    "allowlist_patterns": ["example\\.com"],
                    "blocklist_patterns": ["example\\.com/admin"],
                    "rate_limit_seconds": 1.5,
                    "max_pages": 50,
                    "chunking": {
                        "min_tokens": 150,
                        "max_tokens": 2000,
                        "overlap_tokens": 80,
                    },
                    "database_path": "data/example.db",
                },
                f,
            )
            config_path = f.name

        try:
            config = load_config(config_path)
            assert config.seed_urls == ["https://example.com"]
            assert config.allowlist_patterns == ["example\\.com"]
            assert config.rate_limit_seconds == 1.5
            assert config.max_pages == 50
            assert config.chunking.min_tokens == 150
            assert config.database_path == "data/example.db"
        finally:
            Path(config_path).unlink()

    def test_load_config_file_not_found(self) -> None:
        """Loading non-existent config file should raise FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            load_config("/nonexistent/path/config.yaml")

    def test_load_config_invalid_yaml(self) -> None:
        """Loading malformed YAML should raise yaml.YAMLError."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("invalid: yaml: content: [")
            config_path = f.name

        try:
            with pytest.raises(yaml.YAMLError):
                load_config(config_path)
        finally:
            Path(config_path).unlink()

    def test_load_config_not_dict(self) -> None:
        """YAML file must contain a dictionary."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(["list", "instead", "of", "dict"], f)
            config_path = f.name

        try:
            with pytest.raises(ValueError, match="must contain a YAML dictionary"):
                load_config(config_path)
        finally:
            Path(config_path).unlink()

    def test_load_config_missing_seed_urls(self) -> None:
        """Missing seed_urls should raise ValueError."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(
                {
                    "allowlist_patterns": ["example\\.com"],
                    "blocklist_patterns": [],
                    "rate_limit_seconds": 1.0,
                    "max_pages": 100,
                    "chunking": {"min_tokens": 200, "max_tokens": 1500, "overlap_tokens": 100},
                    "database_path": "data/test.db",
                },
                f,
            )
            config_path = f.name

        try:
            with pytest.raises(ValueError, match="Missing required field: seed_urls"):
                load_config(config_path)
        finally:
            Path(config_path).unlink()

    def test_load_config_missing_allowlist_patterns(self) -> None:
        """Missing allowlist_patterns should raise ValueError."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(
                {
                    "seed_urls": ["https://example.com"],
                    "blocklist_patterns": [],
                    "rate_limit_seconds": 1.0,
                    "max_pages": 100,
                    "chunking": {"min_tokens": 200, "max_tokens": 1500, "overlap_tokens": 100},
                    "database_path": "data/test.db",
                },
                f,
            )
            config_path = f.name

        try:
            with pytest.raises(ValueError, match="Missing required field: allowlist_patterns"):
                load_config(config_path)
        finally:
            Path(config_path).unlink()

    def test_load_config_missing_rate_limit(self) -> None:
        """Missing rate_limit_seconds should raise ValueError."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(
                {
                    "seed_urls": ["https://example.com"],
                    "allowlist_patterns": ["example\\.com"],
                    "blocklist_patterns": [],
                    "max_pages": 100,
                    "chunking": {"min_tokens": 200, "max_tokens": 1500, "overlap_tokens": 100},
                    "database_path": "data/test.db",
                },
                f,
            )
            config_path = f.name

        try:
            with pytest.raises(ValueError, match="Missing required field: rate_limit_seconds"):
                load_config(config_path)
        finally:
            Path(config_path).unlink()

    def test_load_config_missing_max_pages(self) -> None:
        """Missing max_pages should raise ValueError."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(
                {
                    "seed_urls": ["https://example.com"],
                    "allowlist_patterns": ["example\\.com"],
                    "blocklist_patterns": [],
                    "rate_limit_seconds": 1.0,
                    "chunking": {"min_tokens": 200, "max_tokens": 1500, "overlap_tokens": 100},
                    "database_path": "data/test.db",
                },
                f,
            )
            config_path = f.name

        try:
            with pytest.raises(ValueError, match="Missing required field: max_pages"):
                load_config(config_path)
        finally:
            Path(config_path).unlink()

    def test_load_config_missing_database_path(self) -> None:
        """Missing database_path should raise ValueError."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(
                {
                    "seed_urls": ["https://example.com"],
                    "allowlist_patterns": ["example\\.com"],
                    "blocklist_patterns": [],
                    "rate_limit_seconds": 1.0,
                    "max_pages": 100,
                    "chunking": {"min_tokens": 200, "max_tokens": 1500, "overlap_tokens": 100},
                },
                f,
            )
            config_path = f.name

        try:
            with pytest.raises(ValueError, match="Missing required field: database_path"):
                load_config(config_path)
        finally:
            Path(config_path).unlink()

    def test_load_config_missing_chunking(self) -> None:
        """Missing chunking configuration should raise ValueError."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(
                {
                    "seed_urls": ["https://example.com"],
                    "allowlist_patterns": ["example\\.com"],
                    "blocklist_patterns": [],
                    "rate_limit_seconds": 1.0,
                    "max_pages": 100,
                    "database_path": "data/test.db",
                },
                f,
            )
            config_path = f.name

        try:
            with pytest.raises(ValueError, match="Missing required field: chunking"):
                load_config(config_path)
        finally:
            Path(config_path).unlink()

    def test_load_config_chunking_uses_defaults(self) -> None:
        """Chunking defaults should be applied if not specified."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(
                {
                    "seed_urls": ["https://example.com"],
                    "allowlist_patterns": ["example\\.com"],
                    "blocklist_patterns": [],
                    "rate_limit_seconds": 1.0,
                    "max_pages": 100,
                    "chunking": {},
                    "database_path": "data/test.db",
                },
                f,
            )
            config_path = f.name

        try:
            config = load_config(config_path)
            assert config.chunking.min_tokens == 200
            assert config.chunking.max_tokens == 1500
            assert config.chunking.overlap_tokens == 100
        finally:
            Path(config_path).unlink()

    def test_load_config_blocklist_optional(self) -> None:
        """blocklist_patterns should be optional (default empty list)."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(
                {
                    "seed_urls": ["https://example.com"],
                    "allowlist_patterns": ["example\\.com"],
                    "rate_limit_seconds": 1.0,
                    "max_pages": 100,
                    "chunking": {"min_tokens": 200, "max_tokens": 1500, "overlap_tokens": 100},
                    "database_path": "data/test.db",
                },
                f,
            )
            config_path = f.name

        try:
            config = load_config(config_path)
            assert config.blocklist_patterns == []
        finally:
            Path(config_path).unlink()

    def test_load_config_with_path_object(self) -> None:
        """load_config should accept Path objects."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(
                {
                    "seed_urls": ["https://example.com"],
                    "allowlist_patterns": ["example\\.com"],
                    "blocklist_patterns": [],
                    "rate_limit_seconds": 1.0,
                    "max_pages": 100,
                    "chunking": {"min_tokens": 200, "max_tokens": 1500, "overlap_tokens": 100},
                    "database_path": "data/test.db",
                },
                f,
            )
            config_path = Path(f.name)

        try:
            config = load_config(config_path)
            assert config.seed_urls == ["https://example.com"]
        finally:
            config_path.unlink()

    def test_load_config_multiple_seed_urls(self) -> None:
        """Config should support multiple seed URLs."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(
                {
                    "seed_urls": [
                        "https://example1.com",
                        "https://example2.com",
                        "https://example3.com",
                    ],
                    "allowlist_patterns": ["example"],
                    "blocklist_patterns": [],
                    "rate_limit_seconds": 1.0,
                    "max_pages": 100,
                    "chunking": {"min_tokens": 200, "max_tokens": 1500, "overlap_tokens": 100},
                    "database_path": "data/test.db",
                },
                f,
            )
            config_path = f.name

        try:
            config = load_config(config_path)
            assert len(config.seed_urls) == 3
            assert config.seed_urls[0] == "https://example1.com"
        finally:
            Path(config_path).unlink()

    def test_load_config_invalid_rate_limit_type(self) -> None:
        """Invalid rate_limit_seconds type should raise ValueError."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(
                {
                    "seed_urls": ["https://example.com"],
                    "allowlist_patterns": ["example\\.com"],
                    "blocklist_patterns": [],
                    "rate_limit_seconds": "invalid",  # Should be a number
                    "max_pages": 100,
                    "chunking": {"min_tokens": 200, "max_tokens": 1500, "overlap_tokens": 100},
                    "database_path": "data/test.db",
                },
                f,
            )
            config_path = f.name

        try:
            with pytest.raises(ValueError, match="rate_limit_seconds must be a number"):
                load_config(config_path)
        finally:
            Path(config_path).unlink()

    def test_load_config_invalid_max_pages_type(self) -> None:
        """Invalid max_pages type should raise ValueError."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(
                {
                    "seed_urls": ["https://example.com"],
                    "allowlist_patterns": ["example\\.com"],
                    "blocklist_patterns": [],
                    "rate_limit_seconds": 1.0,
                    "max_pages": "invalid",  # Should be an integer
                    "chunking": {"min_tokens": 200, "max_tokens": 1500, "overlap_tokens": 100},
                    "database_path": "data/test.db",
                },
                f,
            )
            config_path = f.name

        try:
            with pytest.raises(ValueError, match="max_pages must be an integer"):
                load_config(config_path)
        finally:
            Path(config_path).unlink()
