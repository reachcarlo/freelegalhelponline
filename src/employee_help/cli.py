"""Command-line interface for the Employee Help scraper."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import structlog

from employee_help.config import load_config, load_source_config, load_all_source_configs

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
        "--source",
        type=str,
        default=None,
        help="Source slug to scrape (e.g., 'crd'). Looks for config/sources/<slug>.yaml.",
    )
    scrape_parser.add_argument(
        "--all",
        action="store_true",
        dest="all_sources",
        help="Scrape all enabled sources in config/sources/.",
    )
    scrape_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Perform crawling and extraction without storing to database.",
    )
    scrape_parser.add_argument(
        "--method",
        type=str,
        choices=["pubinfo", "web"],
        default=None,
        help="Statutory extraction method override: 'pubinfo' (default) or 'web'.",
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
    status_parser.add_argument(
        "--source",
        type=str,
        default=None,
        help="Show status for a specific source slug.",
    )

    # Refresh command
    refresh_parser = subparsers.add_parser(
        "refresh",
        help="Re-run pipeline for a source, skipping unchanged content.",
    )
    refresh_parser.add_argument(
        "--source",
        type=str,
        default=None,
        help="Source slug to refresh (e.g., 'crd').",
    )
    refresh_parser.add_argument(
        "--all",
        action="store_true",
        dest="all_sources",
        help="Refresh all enabled sources.",
    )
    refresh_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report what would change without modifying the database.",
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

    # Cross-validate command
    cross_validate_parser = subparsers.add_parser(
        "cross-validate",
        help="Run cross-source validation across all ingested sources.",
    )
    cross_validate_parser.add_argument(
        "--db",
        type=str,
        default="data/employee_help.db",
        help="Database path (default: data/employee_help.db).",
    )
    cross_validate_parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Output directory for JSON and Markdown reports.",
    )
    cross_validate_parser.add_argument(
        "--samples",
        type=int,
        default=30,
        help="Number of statutory citations to sample (default: 30).",
    )

    # Pubinfo-download command
    pubinfo_parser = subparsers.add_parser(
        "pubinfo-download",
        help="Download the PUBINFO ZIP archive from leginfo.",
    )
    pubinfo_parser.add_argument(
        "--year",
        type=int,
        default=None,
        help="Year of the full archive (e.g., 2025). Defaults to current year.",
    )
    pubinfo_parser.add_argument(
        "--dest",
        type=str,
        default="data/pubinfo",
        help="Destination directory (default: data/pubinfo).",
    )
    pubinfo_parser.add_argument(
        "--force",
        action="store_true",
        help="Re-download even if file exists (for weekly refresh).",
    )

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 0

    try:
        if args.command == "scrape":
            return _handle_scrape(args)
        elif args.command == "refresh":
            return _handle_refresh(args)
        elif args.command == "status":
            return _handle_status(args)
        elif args.command == "validate":
            return _handle_validate(args.config, args.output, args.markdown, args.samples)
        elif args.command == "cross-validate":
            return _handle_cross_validate(args)
        elif args.command == "pubinfo-download":
            return _handle_pubinfo_download(args)
        else:
            parser.print_help()
            return 1

    except KeyboardInterrupt:
        logger.warning("Interrupted by user")
        return 130
    except Exception as e:
        logger.error("fatal_error", error=str(e), exc_info=True)
        return 1


def _handle_scrape(args) -> int:
    """Execute the scrape command."""
    from employee_help.pipeline import Pipeline

    method = getattr(args, "method", None)

    # Determine mode: --source, --all, or legacy --config
    if args.source:
        return _scrape_source(args.source, args.dry_run, method=method)
    elif args.all_sources:
        return _scrape_all_sources(args.dry_run, method=method)
    else:
        return _scrape_legacy(args.config, args.dry_run)


def _scrape_source(slug: str, dry_run: bool, method: str | None = None) -> int:
    """Scrape a single source by slug."""
    from employee_help.pipeline import Pipeline

    config_path = Path("config/sources") / f"{slug}.yaml"
    logger.info("scrape_source", slug=slug, config_path=str(config_path), dry_run=dry_run, method=method)

    try:
        source_config = load_source_config(config_path)
    except FileNotFoundError:
        print(f"Error: No config found for source '{slug}' at {config_path}", file=sys.stderr)
        return 1
    except ValueError as e:
        print(f"Error: Invalid config for source '{slug}': {e}", file=sys.stderr)
        return 1

    pipeline = Pipeline(source_config)
    if method:
        pipeline._method_override = method
    stats = pipeline.run(dry_run=dry_run)
    _print_stats(stats)
    return 0 if stats.errors == 0 else 1


def _scrape_all_sources(dry_run: bool, method: str | None = None) -> int:
    """Scrape all enabled sources."""
    from employee_help.pipeline import Pipeline

    logger.info("scrape_all_sources", dry_run=dry_run)

    try:
        configs = load_all_source_configs("config/sources", enabled_only=True)
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    if not configs:
        print("No enabled source configs found in config/sources/.")
        return 0

    total_errors = 0
    for source_config in configs:
        print(f"\n--- Scraping source: {source_config.name} ({source_config.slug}) ---")
        try:
            pipeline = Pipeline(source_config)
            if method:
                pipeline._method_override = method
            stats = pipeline.run(dry_run=dry_run)
            _print_stats(stats)
            total_errors += stats.errors
        except Exception as e:
            logger.error("source_failed", source=source_config.slug, error=str(e))
            print(f"Error scraping {source_config.slug}: {e}", file=sys.stderr)
            total_errors += 1

    return 0 if total_errors == 0 else 1


def _scrape_legacy(config_path: str, dry_run: bool) -> int:
    """Scrape using legacy single-config mode."""
    from employee_help.pipeline import Pipeline

    logger.info("scrape_started", config_path=config_path, dry_run=dry_run)

    try:
        config = load_config(config_path)
    except FileNotFoundError as e:
        print(f"Error: Configuration file not found: {config_path}", file=sys.stderr)
        return 1
    except ValueError as e:
        print(f"Error: Invalid configuration: {e}", file=sys.stderr)
        return 1

    pipeline = Pipeline(config)
    stats = pipeline.run(dry_run=dry_run)
    _print_stats(stats)
    return 0 if stats.errors == 0 else 1


def _handle_refresh(args) -> int:
    """Execute the refresh command — re-runs pipeline with change detection."""
    if args.source:
        return _refresh_source(args.source, args.dry_run)
    elif args.all_sources:
        return _refresh_all_sources(args.dry_run)
    else:
        print("Error: Specify --source <slug> or --all.", file=sys.stderr)
        return 1


def _refresh_source(slug: str, dry_run: bool) -> int:
    """Refresh a single source — re-run pipeline, report changes."""
    from employee_help.pipeline import Pipeline
    from employee_help.storage.storage import Storage

    config_path = Path("config/sources") / f"{slug}.yaml"
    logger.info("refresh_source", slug=slug, dry_run=dry_run)

    try:
        source_config = load_source_config(config_path)
    except FileNotFoundError:
        print(f"Error: No config found for source '{slug}' at {config_path}", file=sys.stderr)
        return 1
    except ValueError as e:
        print(f"Error: Invalid config for source '{slug}': {e}", file=sys.stderr)
        return 1

    # Get pre-refresh counts
    storage = Storage(source_config.database_path)
    source_record = storage.get_source(slug)
    source_id = source_record.id if source_record else None

    pre_doc_count = storage.get_document_count(source_id=source_id) if source_id else 0
    pre_chunk_count = storage.get_chunk_count(source_id=source_id) if source_id else 0
    storage.close()

    # Run the pipeline (upsert_document handles change detection)
    pipeline = Pipeline(source_config)
    stats = pipeline.run(dry_run=dry_run)

    # Get post-refresh counts
    storage = Storage(source_config.database_path)
    source_record = storage.get_source(slug)
    source_id = source_record.id if source_record else None

    post_doc_count = storage.get_document_count(source_id=source_id) if source_id else 0
    post_chunk_count = storage.get_chunk_count(source_id=source_id) if source_id else 0
    storage.close()

    _print_refresh_report(slug, stats, pre_doc_count, post_doc_count, pre_chunk_count, post_chunk_count)
    return 0 if stats.errors == 0 else 1


def _refresh_all_sources(dry_run: bool) -> int:
    """Refresh all enabled sources."""
    logger.info("refresh_all_sources", dry_run=dry_run)

    try:
        configs = load_all_source_configs("config/sources", enabled_only=True)
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    if not configs:
        print("No enabled source configs found in config/sources/.")
        return 0

    total_errors = 0
    for source_config in configs:
        print(f"\n--- Refreshing source: {source_config.name} ({source_config.slug}) ---")
        try:
            result = _refresh_source(source_config.slug, dry_run)
            if result != 0:
                total_errors += 1
        except Exception as e:
            logger.error("refresh_failed", source=source_config.slug, error=str(e))
            print(f"Error refreshing {source_config.slug}: {e}", file=sys.stderr)
            total_errors += 1

    return 0 if total_errors == 0 else 1


def _print_refresh_report(
    slug: str,
    stats,
    pre_doc: int,
    post_doc: int,
    pre_chunk: int,
    post_chunk: int,
) -> None:
    """Print change detection report for a refresh run."""
    new_docs = post_doc - pre_doc
    new_chunks = post_chunk - pre_chunk

    print("\n" + "=" * 60)
    print("REFRESH REPORT")
    print("=" * 60)
    print(f"Source:              {slug}")
    print(f"URLs crawled:        {stats.urls_crawled}")
    print(f"Documents processed: {stats.documents_stored}")
    print(f"Chunks created:      {stats.chunks_created}")
    print(f"Errors:              {stats.errors}")
    print(f"Duration:            {stats.duration_seconds:.2f}s")
    print("-" * 60)
    print("Change Detection:")
    print(f"  Documents before:  {pre_doc}")
    print(f"  Documents after:   {post_doc}")
    print(f"  New/updated docs:  {max(0, new_docs)}")
    print(f"  Chunks before:     {pre_chunk}")
    print(f"  Chunks after:      {post_chunk}")
    print(f"  New/updated chunks:{max(0, new_chunks)}")
    if new_docs == 0 and new_chunks == 0:
        print("  Status:            NO CHANGES DETECTED")
    else:
        print(f"  Status:            CONTENT UPDATED ({new_docs} docs, {new_chunks} chunks)")
    print("=" * 60 + "\n")


def _print_stats(stats) -> None:
    """Print pipeline run statistics."""
    print("\n" + "=" * 60)
    print("SCRAPE COMPLETED")
    print("=" * 60)
    if stats.source_slug:
        print(f"Source:              {stats.source_slug}")
    print(f"URLs crawled:        {stats.urls_crawled}")
    print(f"Documents stored:    {stats.documents_stored}")
    print(f"Chunks created:      {stats.chunks_created}")
    print(f"Errors encountered:  {stats.errors}")
    print(f"Duration:            {stats.duration_seconds:.2f}s")
    if stats.run_id > 0:
        print(f"Run ID:              {stats.run_id}")
    print("=" * 60 + "\n")


def _handle_cross_validate(args) -> int:
    """Run cross-source validation across all ingested sources."""
    from employee_help.storage.storage import Storage
    from employee_help.validation_report import run_cross_source_validation

    db_path = args.db
    storage = Storage(db_path)

    try:
        report = run_cross_source_validation(
            storage, citation_sample_size=args.samples,
        )

        # Print summary to terminal
        status = "PASS" if report.passed else "FAIL"
        print("\n" + "=" * 70)
        print("CROSS-SOURCE VALIDATION REPORT")
        print("=" * 70)
        print(f"Generated:       {report.generated_at}")
        print(f"Status:          {status}")
        print(f"Checks:          {report.checks_passed}/{len(report.checks)} passed")
        print(f"Sources:         {report.total_sources}")
        print(f"Documents:       {report.total_documents}")
        print(f"Chunks:          {report.total_chunks} ({report.total_active_chunks} active)")
        print(f"Cross-src dupes: {report.cross_source_duplicates}")

        if report.checks_failed > 0:
            print("\nFailed Checks:")
            for c in report.checks:
                if not c.passed:
                    print(f"  [FAIL] {c.name}: {c.message}")

        print("=" * 70)

        # Save reports
        if args.output:
            output_dir = Path(args.output)
            output_dir.mkdir(parents=True, exist_ok=True)

            json_path = output_dir / "cross_source_validation.json"
            json_path.write_text(report.to_json())
            print(f"\nJSON report: {json_path}")

            md_path = output_dir / "cross_source_validation.md"
            md_path.write_text(report.to_markdown())
            print(f"Markdown report: {md_path}")

        return 0 if report.passed else 1

    finally:
        storage.close()


def _handle_pubinfo_download(args) -> int:
    """Download the PUBINFO ZIP archive."""
    from employee_help.scraper.extractors.pubinfo import download_pubinfo

    dest_dir = Path(args.dest)
    year = args.year

    try:
        path = download_pubinfo(dest_dir, year=year, force=getattr(args, "force", False))
        print(f"PUBINFO archive downloaded to: {path}")
        print(f"Size: {path.stat().st_size / 1024 / 1024:.1f} MB")
        return 0
    except Exception as e:
        print(f"Error downloading PUBINFO: {e}", file=sys.stderr)
        return 1


def _handle_status(args) -> int:
    """Display status of the latest crawl run."""
    try:
        config = load_config(args.config)
        from employee_help.storage.storage import Storage
        storage = Storage(config.database_path)

        source_id = None
        if args.source:
            source = storage.get_source(args.source)
            if not source:
                print(f"Source '{args.source}' not found in database.")
                storage.close()
                return 0
            source_id = source.id

        run_info = storage.get_latest_run(source_id=source_id)
        if not run_info:
            if args.source:
                print(f"No crawl runs found for source '{args.source}'.")
            else:
                print("No crawl runs found in the database.")
            storage.close()
            return 0

        doc_count = storage.get_document_count(source_id=source_id)
        chunk_count = storage.get_chunk_count(source_id=source_id)

        print("\n" + "=" * 60)
        print("LATEST CRAWL RUN")
        print("=" * 60)
        if args.source:
            print(f"Source:              {args.source}")
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
        print(f"Error: Configuration file not found: {args.config}", file=sys.stderr)
        return 1
    except ValueError as e:
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
    """Execute the validation command (Phase 1G)."""
    try:
        from employee_help.validation import Validator

        logger.info("validation_started", config_path=config_path)

        with Validator(config_path) as validator:
            logger.info("running_validation_suite")
            report = validator.run_validation(sample_size=sample_size)

        output_path_obj = Path(output_path)
        output_path_obj.parent.mkdir(parents=True, exist_ok=True)
        output_path_obj.write_text(report.to_json())

        if markdown_output:
            markdown_path = output_path_obj.with_suffix(".md")
            markdown_path.write_text(report.to_markdown())

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
        print(f"Error: Configuration file not found: {config_path}", file=sys.stderr)
        return 1
    except ValueError as e:
        print(f"Error: Invalid configuration: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        logger.error("validation_error", error=str(e))
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
