"""Tests for the command-line interface."""

import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
import yaml

from employee_help.cli import main, _handle_scrape, _handle_status


@pytest.fixture
def temp_config() -> tuple[str, dict]:
    """Create a temporary configuration file for testing."""
    config_data = {
        "seed_urls": ["https://example.com"],
        "allowlist_patterns": ["example\\.com"],
        "blocklist_patterns": [],
        "rate_limit_seconds": 0.1,
        "max_pages": 10,
        "chunking": {
            "min_tokens": 100,
            "max_tokens": 1000,
            "overlap_tokens": 50,
        },
        "database_path": ":memory:",
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        yaml.dump(config_data, f)
        return f.name, config_data


@pytest.fixture
def temp_config_with_db() -> tuple[str, dict, str]:
    """Create a temporary configuration with a file-based database."""
    import shutil
    tmpdir = tempfile.mkdtemp()
    db_path = str(Path(tmpdir) / "test.db")

    config_data = {
        "seed_urls": ["https://example.com"],
        "allowlist_patterns": ["example\\.com"],
        "blocklist_patterns": [],
        "rate_limit_seconds": 0.1,
        "max_pages": 10,
        "chunking": {
            "min_tokens": 100,
            "max_tokens": 1000,
            "overlap_tokens": 50,
        },
        "database_path": db_path,
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        yaml.dump(config_data, f)
        config_path = f.name

    yield config_path, config_data, tmpdir

    # Cleanup
    Path(config_path).unlink()
    shutil.rmtree(tmpdir, ignore_errors=True)


class TestCLIMainCommand:
    """Tests for the main CLI entry point."""

    def test_main_with_no_args_shows_help(self, capsys) -> None:
        """CLI with no arguments should show help."""
        with patch("sys.argv", ["employee-help"]):
            result = main()
            assert result == 0
            captured = capsys.readouterr()
            assert "usage" in captured.out or "usage" in captured.err

    def test_main_with_help_flag(self, capsys) -> None:
        """CLI with --help flag should show help."""
        with patch("sys.argv", ["employee-help", "--help"]):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 0

    def test_main_with_invalid_command(self) -> None:
        """CLI with invalid command should fail."""
        with patch("sys.argv", ["employee-help", "invalid"]):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 2  # argparse uses exit code 2 for usage errors

    def test_main_handles_keyboard_interrupt(self) -> None:
        """CLI should handle keyboard interrupt gracefully."""
        with patch("sys.argv", ["employee-help", "scrape"]):
            with patch("employee_help.cli._handle_scrape") as mock_scrape:
                mock_scrape.side_effect = KeyboardInterrupt()
                result = main()
                assert result == 130


class TestScrapeCommand:
    """Tests for the scrape command."""

    def test_scrape_with_missing_config(self) -> None:
        """Scrape should fail if config file doesn't exist."""
        result = _handle_scrape("/nonexistent/config.yaml", dry_run=False)
        assert result == 1

    def test_scrape_dry_run(self, temp_config: tuple[str, dict], capsys) -> None:
        """Scrape with --dry-run should not store to database."""
        config_path, _ = temp_config

        with patch("employee_help.cli.Pipeline") as mock_pipeline_class:
            mock_pipeline = MagicMock()
            mock_pipeline_class.return_value = mock_pipeline

            from employee_help.pipeline import PipelineStats
            from datetime import datetime, timezone

            now = datetime.now(tz=timezone.utc)
            mock_pipeline.run.return_value = PipelineStats(
                run_id=-1,
                urls_crawled=0,
                documents_stored=0,
                chunks_created=0,
                errors=0,
                start_time=now,
                end_time=now,
            )

            result = _handle_scrape(config_path, dry_run=True)
            assert result == 0
            mock_pipeline.run.assert_called_with(dry_run=True)

    def test_scrape_with_invalid_config(self) -> None:
        """Scrape should fail if config is invalid."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False
        ) as f:
            # Write invalid YAML that will be caught as ValueError
            yaml.dump({"invalid": "config"}, f)
            config_path = f.name

        try:
            # The config is missing required fields, so it will raise ValueError
            result = _handle_scrape(config_path, dry_run=False)
            assert result == 1
        finally:
            Path(config_path).unlink()


class TestStatusCommand:
    """Tests for the status command."""

    def test_status_with_missing_config(self) -> None:
        """Status should fail if config file doesn't exist."""
        result = _handle_status("/nonexistent/config.yaml")
        assert result == 1

    def test_status_with_no_runs(self, temp_config: tuple[str, dict], capsys) -> None:
        """Status should handle database with no runs."""
        config_path, _ = temp_config

        result = _handle_status(config_path)
        assert result == 0
        captured = capsys.readouterr()
        assert "No crawl runs found" in captured.out

    def test_status_displays_latest_run(self, temp_config_with_db: tuple[str, dict, str], capsys) -> None:
        """Status should display the latest run information."""
        import shutil
        from employee_help.config import load_config
        from employee_help.storage.storage import Storage

        config_path, _, tmpdir = temp_config_with_db

        config = load_config(config_path)
        storage = Storage(config.database_path)

        # Create a test run
        run = storage.create_run()
        storage.complete_run(
            run.id,
            run.status,
            {"urls_crawled": 5, "documents_stored": 3, "chunks_created": 30},
        )
        storage.close()

        result = _handle_status(config_path)
        assert result == 0
        captured = capsys.readouterr()
        assert "LATEST CRAWL RUN" in captured.out
        assert str(run.id) in captured.out


class TestCLIIntegration:
    """Integration tests for the CLI."""

    def test_scrape_command_via_main(self, temp_config: tuple[str, dict]) -> None:
        """Test scrape command through main() function."""
        config_path, _ = temp_config

        with patch("sys.argv", ["employee-help", "scrape", "--config", config_path, "--dry-run"]):
            with patch("employee_help.cli.Pipeline") as mock_pipeline_class:
                mock_pipeline = MagicMock()
                mock_pipeline_class.return_value = mock_pipeline

                from employee_help.pipeline import PipelineStats
                from datetime import datetime, timezone

                now = datetime.now(tz=timezone.utc)
                mock_pipeline.run.return_value = PipelineStats(
                    run_id=-1,
                    urls_crawled=0,
                    documents_stored=0,
                    chunks_created=0,
                    errors=0,
                    start_time=now,
                    end_time=now,
                )

                result = main()
                assert result == 0

    def test_status_command_via_main(self, temp_config: tuple[str, dict]) -> None:
        """Test status command through main() function."""
        config_path, _ = temp_config

        with patch("sys.argv", ["employee-help", "status", "--config", config_path]):
            result = main()
            assert result == 0
