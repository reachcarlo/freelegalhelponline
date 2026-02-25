"""Command-line interface for the Employee Help scraper."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import structlog

from employee_help.config import load_config
from employee_help.pipeline import Pipeline

logger = structlog.get_logger()


def main() -> int:
    """Main entry point for the CLI."""
    parser = argparse.ArgumentParser(
        prog="employee-help",
        description="Employee Help knowledge acquisition and indexing tool.",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Scrape command
    scrape_parser = subparsers.add_parser(
        "scrape",
        help="Run the web crawler and processing pipeline.",
    )
    scrape_parser.add_argument(
        "--config",
        type=str,
        default="config/scraper.yaml",
        help="Path to the scraper configuration file (default: config/scraper.yaml).",
    )
    scrape_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Perform crawling and extraction without storing to database.",
    )

    # Status command
    status_parser = subparsers.add_parser(
        "status",
        help="Display status of the latest crawl run.",
    )
    status_parser.add_argument(
        "--config",
        type=str,
        default="config/scraper.yaml",
        help="Path to the scraper configuration file (default: config/scraper.yaml).",
    )

    # Validate command (Phase 1G)
    validate_parser = subparsers.add_parser(
        "validate",
        help="Run Phase 1G validation and acceptance tests.",
    )
    validate_parser.add_argument(
        "--config",
        type=str,
        default="config/scraper.yaml",
        help="Path to the scraper configuration file (default: config/scraper.yaml).",
    )
    validate_parser.add_argument(
        "--output",
        type=str,
        default="validation_report.json",
        help="Output path for validation report (default: validation_report.json).",
    )
    validate_parser.add_argument(
        "--markdown",
        action="store_true",
        help="Also output report in Markdown format.",
    )
    validate_parser.add_argument(
        "--samples",
        type=int,
        default=10,
        help="Number of chunks to sample for manual review (default: 10).",
    )

    args = parser.parse_args()

    # If no command specified, show help
    if not args.command:
        parser.print_help()
        return 0

    try:
        if args.command == "scrape":
            return _handle_scrape(args.config, args.dry_run)
        elif args.command == "status":
            return _handle_status(args.config)
        elif args.command == "validate":
            return _handle_validate(args.config, args.output, args.markdown, args.samples)
        else:
            parser.print_help()
            return 1

    except KeyboardInterrupt:
        logger.warning("Interrupted by user")
        return 130
    except Exception as e:
        logger.error("fatal_error", error=str(e), exc_info=True)
        return 1


def _handle_scrape(config_path: str, dry_run: bool) -> int:
    """Execute the scrape command.

    Args:
        config_path: Path to the configuration file.
        dry_run: Whether to skip storage operations.

    Returns:
        Exit code (0 for success, 1 for failure).
    """
    logger.info("scrape_started", config_path=config_path, dry_run=dry_run)

    try:
        # Load configuration
        config = load_config(config_path)
        logger.info(
            "config_loaded",
            seed_urls=len(config.seed_urls),
            max_pages=config.max_pages,
        )

        # Create and run pipeline
        pipeline = Pipeline(config)
        stats = pipeline.run(dry_run=dry_run)

        # Log results
        logger.info(
            "scrape_completed",
            urls_crawled=stats.urls_crawled,
            documents_stored=stats.documents_stored,
            chunks_created=stats.chunks_created,
            errors=stats.errors,
            duration_seconds=stats.duration_seconds,
        )

        # Print summary to stdout
        print("\n" + "=" * 60)
        print("SCRAPE COMPLETED")
        print("=" * 60)
        print(f"URLs crawled:        {stats.urls_crawled}")
        print(f"Documents stored:    {stats.documents_stored}")
        print(f"Chunks created:      {stats.chunks_created}")
        print(f"Errors encountered:  {stats.errors}")
        print(f"Duration:            {stats.duration_seconds:.2f}s")
        if stats.run_id > 0:
            print(f"Run ID:              {stats.run_id}")
        print("=" * 60 + "\n")

        return 0 if stats.errors == 0 else 1

    except FileNotFoundError as e:
        logger.error("config_not_found", path=config_path, error=str(e))
        print(f"Error: Configuration file not found: {config_path}", file=sys.stderr)
        return 1
    except ValueError as e:
        logger.error("config_validation_error", error=str(e))
        print(f"Error: Invalid configuration: {e}", file=sys.stderr)
        return 1


def _handle_status(config_path: str) -> int:
    """Display status of the latest crawl run.

    Args:
        config_path: Path to the configuration file.

    Returns:
        Exit code (0 for success, 1 for failure).
    """
    try:
        # Load configuration to get database path
        config = load_config(config_path)

        # Import Storage here to avoid circular imports
        from employee_help.storage.storage import Storage

        storage = Storage(config.database_path)

        # Get latest run
        run_info = storage.get_latest_run()
        if not run_info:
            print("No crawl runs found in the database.")
            return 0

        # Get stats
        doc_count = storage.get_document_count()
        chunk_count = storage.get_chunk_count()

        # Print status
        print("\n" + "=" * 60)
        print("LATEST CRAWL RUN")
        print("=" * 60)
        print(f"Run ID:              {run_info['id']}")
        print(f"Started at:          {run_info['started_at']}")
        if run_info["completed_at"]:
            print(f"Completed at:        {run_info['completed_at']}")
        print(f"Status:              {run_info['status']}")
        print(f"Total documents:     {doc_count}")
        print(f"Total chunks:        {chunk_count}")
        if run_info.get("summary"):
            summary = run_info["summary"]
            print("\nSummary:")
            for key, value in summary.items():
                print(f"  {key}: {value}")
        print("=" * 60 + "\n")

        storage.close()
        return 0

    except FileNotFoundError as e:
        logger.error("config_not_found", path=config_path, error=str(e))
        print(f"Error: Configuration file not found: {config_path}", file=sys.stderr)
        return 1
    except ValueError as e:
        logger.error("config_validation_error", error=str(e))
        print(f"Error: Invalid configuration: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        logger.error("status_error", error=str(e))
        print(f"Error: {e}", file=sys.stderr)
        return 1


def _handle_validate(
    config_path: str,
    output_path: str,
    markdown_output: bool,
    sample_size: int,
) -> int:
    """Execute the validation command (Phase 1G).

    Args:
        config_path: Path to the configuration file.
        output_path: Path to save the validation report (JSON).
        markdown_output: Whether to also output Markdown report.
        sample_size: Number of chunks to sample for review.

    Returns:
        Exit code (0 for success, 1 for failure).
    """
    try:
        from employee_help.validation import Validator

        logger.info("validation_started", config_path=config_path)

        with Validator(config_path) as validator:
            logger.info("running_validation_suite")
            report = validator.run_validation(sample_size=sample_size)

        # Save JSON report
        output_path_obj = Path(output_path)
        output_path_obj.parent.mkdir(parents=True, exist_ok=True)
        output_path_obj.write_text(report.to_json())
        logger.info("json_report_saved", path=output_path)

        # Optionally save Markdown report
        if markdown_output:
            markdown_path = output_path_obj.with_suffix(".md")
            markdown_path.write_text(report.to_markdown())
            logger.info("markdown_report_saved", path=markdown_path)

        # Print summary to stdout
        print("\n" + "=" * 70)
        print("PHASE 1G VALIDATION REPORT")
        print("=" * 70)
        print(f"Timestamp:     {report.timestamp}")
        print(f"Status:        {report.validation_status}")
        print(f"Coverage:      {report.coverage_percent:.2f}%")
        print()
        print("Run 1 (Initial Crawl):")
        for key, value in report.run1_stats.items():
            print(f"  {key}: {value}")
        print()
        print("Run 2 (Idempotency Check):")
        for key, value in report.run2_stats.items():
            print(f"  {key}: {value}")
        print()
        print("Idempotency:")
        for key, value in report.idempotency_check.items():
            print(f"  {key}: {value}")
        print()
        print("Data Quality:")
        for key, value in report.data_quality_metrics.items():
            if isinstance(value, dict):
                print(f"  {key}:")
                for subkey, subval in value.items():
                    print(f"    {subkey}: {subval}")
            else:
                print(f"  {key}: {value}")
        print()

        if report.notes:
            print("Notes:")
            for note in report.notes:
                print(f"  {note}")
            print()

        print(f"Reports saved to: {output_path}")
        if markdown_output:
            print(f"Markdown report: {output_path_obj.with_suffix('.md')}")

        print("=" * 70 + "\n")

        return 0 if report.validation_status == "PASS" else 1

    except FileNotFoundError as e:
        logger.error("config_not_found", path=config_path, error=str(e))
        print(f"Error: Configuration file not found: {config_path}", file=sys.stderr)
        return 1
    except ValueError as e:
        logger.error("config_validation_error", error=str(e))
        print(f"Error: Invalid configuration: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        logger.error("validation_error", error=str(e))
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
