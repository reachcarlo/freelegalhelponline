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

    # Source-health command (T1-A)
    health_parser = subparsers.add_parser(
        "source-health",
        help="Show freshness and health status for all knowledge sources.",
    )
    health_parser.add_argument(
        "--db",
        type=str,
        default="data/employee_help.db",
        help="Database path (default: data/employee_help.db).",
    )
    health_parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Output as JSON instead of table.",
    )
    health_parser.add_argument(
        "--history",
        type=int,
        default=0,
        help="Show last N refresh runs per source (default: 0).",
    )
    health_parser.add_argument(
        "--check-updates",
        action="store_true",
        dest="check_updates",
        help="Check for new editions of downloadable sources (CACI, DLSE Manual).",
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
    refresh_parser.add_argument(
        "--tier",
        type=str,
        choices=["statutory", "regulatory", "persuasive", "agency", "caselaw"],
        default=None,
        help="Refresh only sources in this tier (e.g., --tier statutory).",
    )
    refresh_parser.add_argument(
        "--auto-embed",
        action="store_true",
        help="Run incremental embedding + FTS rebuild after refreshing.",
    )
    refresh_parser.add_argument(
        "--auto-download",
        action="store_true",
        help="Download PUBINFO archive before refreshing statutory sources.",
    )
    refresh_parser.add_argument(
        "--if-stale",
        action="store_true",
        help="Only refresh sources that exceed their max_age_days threshold.",
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

    # Embed command
    embed_parser = subparsers.add_parser(
        "embed",
        help="Generate vector embeddings for chunks.",
    )
    embed_parser.add_argument(
        "--all",
        action="store_true",
        dest="embed_all",
        help="Embed all un-embedded chunks.",
    )
    embed_parser.add_argument(
        "--source",
        type=str,
        default=None,
        help="Embed chunks for a specific source slug.",
    )
    embed_parser.add_argument(
        "--rebuild",
        action="store_true",
        help="Delete and rebuild entire vector index from scratch.",
    )
    embed_parser.add_argument(
        "--db",
        type=str,
        default="data/employee_help.db",
        help="Database path (default: data/employee_help.db).",
    )

    # Embed-status command
    embed_status_parser = subparsers.add_parser(
        "embed-status",
        help="Show embedding coverage and index stats.",
    )
    embed_status_parser.add_argument(
        "--db",
        type=str,
        default="data/employee_help.db",
        help="Database path (default: data/employee_help.db).",
    )

    # Search command
    search_parser = subparsers.add_parser(
        "search",
        help="Search the knowledge base using hybrid retrieval.",
    )
    search_parser.add_argument(
        "query",
        type=str,
        help="Search query.",
    )
    search_parser.add_argument(
        "--mode",
        type=str,
        choices=["consumer", "attorney"],
        default="consumer",
        help="Search mode (default: consumer).",
    )
    search_parser.add_argument(
        "--top-k",
        type=int,
        default=5,
        help="Number of results to return (default: 5).",
    )
    search_parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show full content and debug info.",
    )
    search_parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Output results as JSON.",
    )
    search_parser.add_argument(
        "--db",
        type=str,
        default="data/employee_help.db",
        help="Database path (default: data/employee_help.db).",
    )

    # Ask command
    ask_parser = subparsers.add_parser(
        "ask",
        help="Ask a question and get a RAG-generated answer.",
    )
    ask_parser.add_argument(
        "query",
        type=str,
        help="Question to ask.",
    )
    ask_parser.add_argument(
        "--mode",
        type=str,
        choices=["consumer", "attorney"],
        default="consumer",
        help="Answer mode (default: consumer).",
    )
    ask_parser.add_argument(
        "--no-stream",
        action="store_true",
        help="Wait for complete response before displaying.",
    )
    ask_parser.add_argument(
        "--debug",
        action="store_true",
        help="Show retrieval results and prompt debug info.",
    )
    ask_parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Output structured answer as JSON.",
    )
    ask_parser.add_argument(
        "--db",
        type=str,
        default="data/employee_help.db",
        help="Database path (default: data/employee_help.db).",
    )

    # Evaluate-retrieval command
    eval_retrieval_parser = subparsers.add_parser(
        "evaluate-retrieval",
        help="Run automated retrieval quality evaluation.",
    )
    eval_retrieval_parser.add_argument(
        "--output",
        type=str,
        default="data/evaluation",
        help="Output directory for evaluation report (default: data/evaluation).",
    )
    eval_retrieval_parser.add_argument(
        "--db",
        type=str,
        default="data/employee_help.db",
        help="Database path (default: data/employee_help.db).",
    )

    # Evaluate-answers command
    eval_answers_parser = subparsers.add_parser(
        "evaluate-answers",
        help="Run automated answer quality evaluation.",
    )
    eval_answers_parser.add_argument(
        "--output",
        type=str,
        default="data/evaluation",
        help="Output directory for evaluation report (default: data/evaluation).",
    )
    eval_answers_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run retrieval only, skip LLM calls.",
    )
    eval_answers_parser.add_argument(
        "--db",
        type=str,
        default="data/employee_help.db",
        help="Database path (default: data/employee_help.db).",
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

    # Feedback dashboard command
    feedback_parser = subparsers.add_parser(
        "feedback",
        help="Show query analytics and feedback dashboard.",
    )
    feedback_parser.add_argument(
        "--days",
        type=int,
        default=30,
        help="Number of days to look back (default: 30).",
    )
    feedback_parser.add_argument(
        "--db",
        type=str,
        default="data/feedback.db",
        help="Feedback database path (default: data/feedback.db).",
    )

    # Citation audit command
    audit_parser = subparsers.add_parser(
        "citation-audit",
        help="Show citation verification audit report.",
    )
    audit_parser.add_argument(
        "--days",
        type=int,
        default=30,
        help="Number of days to look back (default: 30).",
    )
    audit_parser.add_argument(
        "--session",
        type=str,
        default=None,
        help="Show citations for a specific session ID.",
    )
    audit_parser.add_argument(
        "--confidence",
        type=str,
        choices=["verified", "unverified", "suspicious"],
        default=None,
        help="Filter by confidence level.",
    )
    audit_parser.add_argument(
        "--csv",
        type=str,
        default=None,
        metavar="FILE",
        help="Export audit data to CSV file.",
    )
    audit_parser.add_argument(
        "--db",
        type=str,
        default="data/feedback.db",
        help="Feedback database path (default: data/feedback.db).",
    )

    # Ingest-caselaw command
    caselaw_parser = subparsers.add_parser(
        "ingest-caselaw",
        help="Download and ingest California employment case law from CourtListener.",
    )
    caselaw_parser.add_argument(
        "--max-opinions",
        type=int,
        default=None,
        help="Maximum number of opinions to ingest (default: from config).",
    )
    caselaw_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Process opinions without storing to database.",
    )
    caselaw_parser.add_argument(
        "--db",
        type=str,
        default="data/employee_help.db",
        help="Database path (default: data/employee_help.db).",
    )
    caselaw_parser.add_argument(
        "--config",
        type=str,
        default="config/sources/courtlistener.yaml",
        help="Path to courtlistener source config (default: config/sources/courtlistener.yaml).",
    )

    # Spot-check-caselaw command (4C.6)
    spotcheck_parser = subparsers.add_parser(
        "spot-check-caselaw",
        help="Spot-check ingested case law for quality.",
    )
    spotcheck_parser.add_argument(
        "--samples",
        type=int,
        default=20,
        help="Number of opinions to sample (default: 20).",
    )
    spotcheck_parser.add_argument(
        "--db",
        type=str,
        default="data/employee_help.db",
        help="Database path (default: data/employee_help.db).",
    )

    # Dashboard command (T4-D)
    dashboard_parser = subparsers.add_parser(
        "dashboard",
        help="Comprehensive health dashboard for all knowledge sources.",
    )
    dashboard_parser.add_argument(
        "--db",
        type=str,
        default="data/employee_help.db",
        help="Database path (default: data/employee_help.db).",
    )
    dashboard_parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Output as JSON instead of table.",
    )

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 0

    try:
        if args.command == "scrape":
            return _handle_scrape(args)
        elif args.command == "source-health":
            return _handle_source_health(args)
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
        elif args.command == "embed":
            return _handle_embed(args)
        elif args.command == "embed-status":
            return _handle_embed_status(args)
        elif args.command == "search":
            return _handle_search(args)
        elif args.command == "ask":
            return _handle_ask(args)
        elif args.command == "evaluate-retrieval":
            return _handle_evaluate_retrieval(args)
        elif args.command == "evaluate-answers":
            return _handle_evaluate_answers(args)
        elif args.command == "feedback":
            return _handle_feedback(args)
        elif args.command == "citation-audit":
            return _handle_citation_audit(args)
        elif args.command == "ingest-caselaw":
            return _handle_ingest_caselaw(args)
        elif args.command == "spot-check-caselaw":
            return _handle_spot_check_caselaw(args)
        elif args.command == "dashboard":
            return _handle_dashboard(args)
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


# Tier → content_category mapping for --tier filter (T1-B.6)
_TIER_CATEGORIES: dict[str, set[str]] = {
    "statutory": {"statutory_code"},
    "regulatory": {"regulation", "jury_instruction"},
    "persuasive": {"opinion_letter", "enforcement_manual", "federal_guidance"},
    "agency": {"agency_guidance", "fact_sheet", "faq", "legal_aid_resource", "poster"},
    "caselaw": {"case_law"},
}


def _filter_configs_by_tier(configs: list, tier: str | None) -> list:
    """Filter source configs to those matching the given tier's content categories."""
    if tier is None:
        return configs
    categories = _TIER_CATEGORIES.get(tier, set())
    return [c for c in configs if c.extraction.content_category in categories]


def _handle_source_health(args) -> int:
    """Show freshness and health status for all knowledge sources."""
    import json as json_mod

    from employee_help.config import load_all_source_configs
    from employee_help.storage.storage import Storage

    storage = Storage(args.db)

    try:
        freshness = storage.get_source_freshness()
        all_sources = storage.get_all_sources()

        # Build max_age_days lookup from configs
        all_configs = []
        try:
            all_configs = load_all_source_configs("config/sources", enabled_only=False)
            max_age_map = {c.slug: c.refresh.max_age_days for c in all_configs}
        except FileNotFoundError:
            max_age_map = {}

        # Build consecutive failure lookup
        source_id_map = {s.slug: s.id for s in all_sources}

        rows = []
        for f in freshness:
            slug = f["slug"]
            max_age = max_age_map.get(slug, 7)
            age_days = f["age_days"]

            if age_days is None:
                status = "NEVER_RUN"
            elif age_days <= max_age:
                status = "FRESH"
            else:
                status = "STALE"

            sid = source_id_map.get(slug)
            consecutive_failures = storage.get_consecutive_failures(sid) if sid else 0

            rows.append({
                "slug": slug,
                "source_type": f["source_type"],
                "last_refreshed_at": f["last_refreshed_at"].isoformat() if f["last_refreshed_at"] else None,
                "age_days": round(age_days, 1) if age_days is not None else None,
                "max_age_days": max_age,
                "status": status,
                "consecutive_failures": consecutive_failures,
            })

        if args.json_output:
            print(json_mod.dumps(rows, indent=2))
            return 0

        # Table output
        print("\n" + "=" * 85)
        print("SOURCE HEALTH")
        print("=" * 85)
        print(f"{'Slug':<25} {'Type':<15} {'Age (days)':<12} {'Max':<6} {'Status':<12} {'Failures'}")
        print("-" * 85)
        for r in rows:
            age_str = f"{r['age_days']}" if r["age_days"] is not None else "—"
            print(
                f"{r['slug']:<25} {r['source_type']:<15} {age_str:<12} "
                f"{r['max_age_days']:<6} {r['status']:<12} {r['consecutive_failures']}"
            )

        stale_count = sum(1 for r in rows if r["status"] in ("STALE", "NEVER_RUN"))
        print("-" * 85)
        print(f"Total: {len(rows)} sources, {stale_count} stale/never-run")
        print("=" * 85 + "\n")

        # Show run history if requested
        if args.history > 0:
            _print_run_history(storage, all_sources, args.history)

        # Check for new editions (--check-updates)
        if getattr(args, "check_updates", False):
            _check_source_updates(all_configs)

        return 0

    finally:
        storage.close()


def _print_run_history(storage, sources, count: int) -> None:
    """Print last N runs per source."""
    for source in sources:
        if source.id is None:
            continue
        runs = storage.get_recent_runs(source.id, count)
        if not runs:
            continue
        print(f"\n  {source.slug} — Last {len(runs)} runs:")
        for run in runs:
            status = run["status"]
            completed = run["completed_at"] or "—"
            summary = run["summary"]
            docs = summary.get("documents_stored", summary.get("opinions_loaded", "?"))
            duration = summary.get("duration_seconds", "?")
            if isinstance(duration, (int, float)):
                duration = f"{duration:.0f}s"
            print(f"    {completed}  {status:<10}  docs={docs}  duration={duration}")


def _check_source_updates(configs: list) -> None:
    """Check for new editions of downloadable sources via HTTP HEAD.

    Sources with a non-empty ``refresh.check_update_url`` are checked.
    URL templates may contain ``{next_year}`` which is replaced with the
    current year + 1.
    """
    from datetime import datetime

    import httpx

    sources_with_url = [c for c in configs if c.refresh.check_update_url]
    if not sources_with_url:
        return

    current_year = datetime.now().year
    next_year = current_year + 1

    print("\n" + "-" * 85)
    print("UPDATE CHECKS")
    print("-" * 85)

    for config in sources_with_url:
        url = config.refresh.check_update_url.replace("{next_year}", str(next_year))
        try:
            resp = httpx.head(url, timeout=10.0, follow_redirects=True)
            if resp.status_code == 200:
                content_length = resp.headers.get("content-length", "unknown")
                print(f"  {config.slug}: NEW EDITION AVAILABLE at {url} (size: {content_length})")
            elif resp.status_code == 404:
                print(f"  {config.slug}: Current edition (no new edition at {url})")
            else:
                print(f"  {config.slug}: Unknown (HTTP {resp.status_code} at {url})")
        except httpx.TimeoutException:
            print(f"  {config.slug}: Timeout checking {url}")
        except httpx.HTTPError as e:
            print(f"  {config.slug}: Error checking {url}: {e}")

    print("-" * 85 + "\n")


def _handle_dashboard(args) -> int:
    """Show comprehensive health dashboard for all knowledge sources."""
    import json as json_mod

    from employee_help.config import load_all_source_configs
    from employee_help.storage.storage import Storage

    storage = Storage(args.db)

    try:
        dashboard_data = storage.get_source_dashboard_data()

        # Load configs for tier/schedule metadata
        try:
            all_configs = load_all_source_configs("config/sources", enabled_only=False)
            config_map = {c.slug: c for c in all_configs}
        except FileNotFoundError:
            config_map = {}

        # Enrich dashboard data with config metadata
        for entry in dashboard_data:
            cfg = config_map.get(entry["slug"])
            if cfg:
                entry["content_category"] = cfg.extraction.content_category
                entry["max_age_days"] = cfg.refresh.max_age_days
                entry["static"] = cfg.refresh.static
                entry["cron_hint"] = cfg.refresh.cron_hint
                entry["extraction_method"] = cfg.statutory.method if cfg.statutory else "crawler"
                # Determine tier
                for tier_name, cats in _TIER_CATEGORIES.items():
                    if cfg.extraction.content_category in cats:
                        entry["tier"] = tier_name
                        break
                else:
                    entry["tier"] = "unknown"
                # Determine status
                age = entry["age_days"]
                if age is None:
                    entry["status"] = "NEVER_RUN"
                elif age <= cfg.refresh.max_age_days:
                    entry["status"] = "FRESH"
                else:
                    entry["status"] = "STALE"
            else:
                entry["tier"] = "unknown"
                entry["content_category"] = "unknown"
                entry["max_age_days"] = 7
                entry["static"] = False
                entry["cron_hint"] = ""
                entry["extraction_method"] = "unknown"
                entry["status"] = "UNKNOWN"

        if args.json_output:
            # Serialize datetimes for JSON
            for entry in dashboard_data:
                if entry.get("last_refreshed_at"):
                    entry["last_refreshed_at"] = entry["last_refreshed_at"].isoformat()
            print(json_mod.dumps(dashboard_data, indent=2, default=str))
            return 0

        # Table output grouped by tier
        tier_order = ["statutory", "regulatory", "persuasive", "agency", "caselaw", "unknown"]
        tier_labels = {
            "statutory": "STATUTORY (Binding Law)",
            "regulatory": "REGULATORY (Binding Regulations)",
            "persuasive": "PERSUASIVE (Administrative Authority)",
            "agency": "AGENCY (Guidance & Educational)",
            "caselaw": "CASE LAW (Judicial Opinions)",
            "unknown": "UNCATEGORIZED",
        }

        by_tier: dict[str, list] = {t: [] for t in tier_order}
        for entry in dashboard_data:
            tier = entry.get("tier", "unknown")
            if tier in by_tier:
                by_tier[tier].append(entry)
            else:
                by_tier["unknown"].append(entry)

        total_docs = sum(e["document_count"] for e in dashboard_data)
        total_chunks = sum(e["chunk_count"] for e in dashboard_data)
        total_sources = len(dashboard_data)
        fresh = sum(1 for e in dashboard_data if e.get("status") == "FRESH")
        stale = sum(1 for e in dashboard_data if e.get("status") == "STALE")
        never_run = sum(1 for e in dashboard_data if e.get("status") == "NEVER_RUN")

        print()
        print("=" * 100)
        print("KNOWLEDGE BASE HEALTH DASHBOARD")
        print("=" * 100)

        for tier in tier_order:
            entries = by_tier[tier]
            if not entries:
                continue

            print(f"\n  {tier_labels.get(tier, tier)} ({len(entries)} sources)")
            print("  " + "-" * 96)
            print(
                f"  {'Source':<22} {'Docs':>6} {'Chunks':>7} {'Age':>6} {'Max':>5} "
                f"{'Status':<10} {'Last Run':<12} {'Errors':>6} {'Method'}"
            )
            print("  " + "-" * 96)

            for e in entries:
                age_str = f"{e['age_days']}d" if e["age_days"] is not None else "--"
                max_str = f"{e['max_age_days']}d"
                status = e.get("status", "?")

                # Last run info
                last_run_status = e.get("last_run_status", "")
                if last_run_status == "completed":
                    summary = e.get("last_run_summary", {})
                    duration = summary.get("duration_seconds", 0)
                    if isinstance(duration, (int, float)):
                        last_run_str = f"OK {duration:.0f}s"
                    else:
                        last_run_str = "OK"
                elif last_run_status == "failed":
                    last_run_str = "FAILED"
                elif last_run_status == "running":
                    last_run_str = "RUNNING"
                else:
                    last_run_str = "--"

                errors = e.get("last_run_summary", {}).get("errors", 0)
                method = e.get("extraction_method", "?")

                print(
                    f"  {e['slug']:<22} {e['document_count']:>6,} {e['chunk_count']:>7,} "
                    f"{age_str:>6} {max_str:>5} {status:<10} {last_run_str:<12} "
                    f"{errors:>6} {method}"
                )

        # Summary footer
        print()
        print("  " + "=" * 96)
        print(
            f"  TOTAL: {total_sources} sources | {total_docs:,} documents | "
            f"{total_chunks:,} chunks"
        )
        print(
            f"  Fresh: {fresh}/{total_sources} | Stale: {stale}/{total_sources} | "
            f"Never Run: {never_run}/{total_sources}"
        )
        print("  " + "=" * 96)
        print()

        return 0

    finally:
        storage.close()


def _handle_refresh(args) -> int:
    """Execute the refresh command — re-runs pipeline with change detection."""
    if args.source:
        return _refresh_source(args.source, args.dry_run)
    elif args.all_sources:
        return _refresh_all_sources(
            dry_run=args.dry_run,
            tier=getattr(args, "tier", None),
            auto_embed=getattr(args, "auto_embed", False),
            auto_download=getattr(args, "auto_download", False),
            if_stale=getattr(args, "if_stale", False),
        )
    else:
        print("Error: Specify --source <slug> or --all.", file=sys.stderr)
        return 1


def _refresh_source(slug: str, dry_run: bool) -> int:
    """Refresh a single source — re-run pipeline, report changes."""
    result, _stats = _refresh_source_with_stats(slug, dry_run)
    return result


def _refresh_source_with_stats(slug: str, dry_run: bool):
    """Refresh a single source, returning (exit_code, PipelineStats)."""
    from employee_help.pipeline import Pipeline
    from employee_help.storage.storage import Storage

    config_path = Path("config/sources") / f"{slug}.yaml"
    logger.info("refresh_source", slug=slug, dry_run=dry_run)

    try:
        source_config = load_source_config(config_path)
    except FileNotFoundError:
        print(f"Error: No config found for source '{slug}' at {config_path}", file=sys.stderr)
        return 1, None
    except ValueError as e:
        print(f"Error: Invalid config for source '{slug}': {e}", file=sys.stderr)
        return 1, None

    # Static corpus confirmation (T3-A.2) — skip full extraction
    if source_config.refresh.static and not dry_run:
        return _confirm_static_corpus(source_config)

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
    return (0 if stats.errors == 0 else 1), stats


def _confirm_static_corpus(source_config) -> tuple[int, None]:
    """Confirm a static corpus is still accessible without re-extracting.

    For sources with ``refresh.static: true`` (e.g., DLSE opinion letters —
    closed corpus, no new data expected).  Performs:
      (a) HTTP HEAD to ``base_url`` to verify accessibility,
      (b) query stored document count for this source,
      (c) update ``last_refreshed_at`` if confirmed.

    Returns (exit_code, None) — no PipelineStats for static sources.
    """
    from datetime import UTC, datetime

    import httpx

    from employee_help.storage.storage import Storage

    slug = source_config.slug
    base_url = source_config.base_url
    storage = Storage(source_config.database_path)

    try:
        source_record = storage.get_source(slug)
        source_id = source_record.id if source_record else None
        doc_count = storage.get_document_count(source_id=source_id) if source_id else 0

        # HTTP HEAD to verify accessibility
        reachable = False
        try:
            resp = httpx.head(base_url, timeout=10.0, follow_redirects=True)
            reachable = resp.status_code < 400
        except (httpx.TimeoutException, httpx.HTTPError):
            reachable = False

        if reachable:
            print(f"  {slug}: Corpus confirmed ({doc_count} docs, source reachable)")
            if source_id:
                storage.update_source_last_refreshed(source_id, datetime.now(tz=UTC))
            return 0, None
        else:
            print(f"  {slug}: Source unreachable at {base_url} ({doc_count} docs in DB)")
            return 1, None
    finally:
        storage.close()


def _refresh_all_sources(
    dry_run: bool,
    tier: str | None = None,
    auto_embed: bool = False,
    auto_download: bool = False,
    if_stale: bool = False,
) -> int:
    """Refresh all enabled sources with optional tier filter and orchestration."""
    import json as json_mod
    from datetime import UTC, datetime

    from employee_help.storage.storage import Storage

    logger.info(
        "refresh_all_sources",
        dry_run=dry_run, tier=tier, auto_embed=auto_embed,
        auto_download=auto_download, if_stale=if_stale,
    )

    try:
        configs = load_all_source_configs("config/sources", enabled_only=True)
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    # Filter by tier
    configs = _filter_configs_by_tier(configs, tier)

    if not configs:
        print(f"No enabled source configs found{' for tier ' + tier if tier else ''}.")
        return 0

    # Conditional PUBINFO download (--auto-download)
    has_statutory = any(
        c.extraction.content_category == "statutory_code" for c in configs
    )
    if auto_download and has_statutory and not dry_run:
        print("\n--- Auto-downloading PUBINFO archive ---")
        try:
            _auto_download_pubinfo()
        except Exception as e:
            logger.error("auto_download_failed", error=str(e))
            print(f"Warning: PUBINFO download failed: {e}", file=sys.stderr)

    # Staleness check (--if-stale)
    if if_stale:
        storage = Storage(configs[0].database_path)
        freshness = storage.get_source_freshness()
        freshness_map = {f["slug"]: f for f in freshness}
        storage.close()

        fresh_configs = []
        for c in configs:
            entry = freshness_map.get(c.slug)
            if entry and entry["age_days"] is not None and entry["age_days"] <= c.refresh.max_age_days:
                print(f"  Skipping {c.slug}: fresh ({entry['age_days']:.1f} days, max {c.refresh.max_age_days})")
                continue
            fresh_configs.append(c)
        configs = fresh_configs

        if not configs:
            print("All sources are fresh. Nothing to refresh.")
            return 0

    # Track which sources had changes for auto-embed
    total_errors = 0
    failed_sources = []
    sources_with_changes = []
    all_stats = []

    for source_config in configs:
        print(f"\n--- Refreshing source: {source_config.name} ({source_config.slug}) ---")
        try:
            result, stats = _refresh_source_with_stats(source_config.slug, dry_run)
            all_stats.append((source_config.slug, stats))
            if result != 0:
                total_errors += 1
                failed_sources.append(source_config.slug)
            elif stats and stats.has_changes:
                sources_with_changes.append(source_config.slug)
        except Exception as e:
            logger.error("refresh_failed", source=source_config.slug, error=str(e))
            print(f"Error refreshing {source_config.slug}: {e}", file=sys.stderr)
            total_errors += 1
            failed_sources.append(source_config.slug)

    # Retry failed sources once (T1-B.10)
    if failed_sources and not dry_run:
        import time
        print(f"\n--- Retrying {len(failed_sources)} failed sources ---")
        time.sleep(5)
        retry_errors = 0
        for slug in list(failed_sources):
            print(f"  Retrying {slug}...")
            try:
                result, stats = _refresh_source_with_stats(slug, dry_run)
                if result == 0:
                    failed_sources.remove(slug)
                    total_errors -= 1
                    if stats and stats.has_changes:
                        sources_with_changes.append(slug)
                else:
                    retry_errors += 1
            except Exception as e:
                logger.error("retry_failed", source=slug, error=str(e))
                retry_errors += 1

    # Auto-embed (--auto-embed)
    if auto_embed and sources_with_changes and not dry_run:
        print(f"\n--- Auto-embedding {len(sources_with_changes)} changed sources ---")
        try:
            _auto_embed_sources(sources_with_changes, configs[0].database_path)
        except Exception as e:
            logger.error("auto_embed_failed", error=str(e))
            print(f"Warning: Auto-embed failed: {e}", file=sys.stderr)
    elif auto_embed and not sources_with_changes:
        print("\n--- No changes detected; skipping auto-embed ---")

    # Write JSON refresh report (T1-B.9)
    if not dry_run:
        _write_refresh_report_json(all_stats, tier, sources_with_changes, failed_sources)

    return 0 if total_errors == 0 else 1


def _auto_download_pubinfo() -> None:
    """Download PUBINFO archive if a newer version is available."""
    from employee_help.scraper.extractors.pubinfo import download_pubinfo

    pubinfo_dir = Path("data/pubinfo")
    download_pubinfo(pubinfo_dir)
    print("  PUBINFO download complete.")


def _auto_embed_sources(slugs: list[str], db_path: str) -> None:
    """Run incremental embedding + FTS rebuild for changed sources."""
    import yaml

    from employee_help.retrieval.embedder import EmbeddingService
    from employee_help.retrieval.vector_store import VectorStore
    from employee_help.storage.storage import Storage

    rag_config_path = Path("config/rag.yaml")
    rag_config = {}
    if rag_config_path.exists():
        with open(rag_config_path) as f:
            rag_config = yaml.safe_load(f) or {}

    emb_cfg = rag_config.get("embedding", {})
    vs_cfg = rag_config.get("vector_store", {})

    storage = Storage(db_path)
    embedding_service = EmbeddingService(
        model_name=emb_cfg.get("model", "BAAI/bge-base-en-v1.5"),
        device=emb_cfg.get("device", "cpu"),
    )
    vector_store = VectorStore(db_path=vs_cfg.get("path", "data/lancedb"))

    try:
        for slug in slugs:
            result = _embed_source(slug, storage, embedding_service, vector_store)
            if result == 0:
                print(f"  Embedded {slug}")

        # Rebuild FTS index after embedding
        print("  Rebuilding FTS index...")
        vector_store.rebuild_fts_index()
        print("  FTS index rebuilt.")
    finally:
        storage.close()


def _write_refresh_report_json(
    all_stats: list, tier: str | None, changed: list[str], failed: list[str]
) -> None:
    """Write JSON refresh report to data/refresh_reports/."""
    import json as json_mod
    from datetime import UTC, datetime

    report_dir = Path("data/refresh_reports")
    report_dir.mkdir(parents=True, exist_ok=True)

    now = datetime.now(tz=UTC)
    filename = now.strftime("%Y-%m-%d_%H-%M") + ".json"

    report = {
        "timestamp": now.isoformat(),
        "tier": tier,
        "sources": [],
        "sources_with_changes": changed,
        "failed_sources": failed,
    }

    for slug, stats in all_stats:
        if stats:
            report["sources"].append({
                "slug": slug,
                "new_documents": stats.new_documents,
                "updated_documents": stats.updated_documents,
                "unchanged_documents": stats.unchanged_documents,
                "deactivated_sections": len(stats.deactivated_sections),
                "errors": stats.errors,
                "duration_seconds": round(stats.duration_seconds, 1),
            })

    report_path = report_dir / filename
    report_path.write_text(json_mod.dumps(report, indent=2))
    print(f"\nRefresh report saved to {report_path}")


def _print_refresh_report(
    slug: str,
    stats,
    pre_doc: int,
    post_doc: int,
    pre_chunk: int,
    post_chunk: int,
) -> None:
    """Print change detection report for a refresh run."""
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
    print(f"  New documents:     {stats.new_documents}")
    print(f"  Updated documents: {stats.updated_documents}")
    print(f"  Unchanged:         {stats.unchanged_documents}")
    deactivated_count = sum(
        d.get("chunks_deactivated", 0) for d in stats.deactivated_sections
    )
    print(f"  Deactivated:       {deactivated_count} chunks ({len(stats.deactivated_sections)} sections)")
    if stats.has_changes:
        print("  Status:            CONTENT UPDATED")
    else:
        print("  Status:            NO CHANGES DETECTED")
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


def _load_rag_config() -> dict:
    """Load RAG pipeline configuration."""
    import yaml

    config_path = Path("config/rag.yaml")
    if config_path.exists():
        with open(config_path) as f:
            return yaml.safe_load(f)
    return {}


def _build_retrieval_service(db_path: str = "data/employee_help.db"):
    """Build and return a configured RetrievalService."""
    from employee_help.retrieval.embedder import EmbeddingService
    from employee_help.retrieval.query import QueryPreprocessor
    from employee_help.retrieval.reranker import Reranker
    from employee_help.retrieval.service import RetrievalService
    from employee_help.retrieval.vector_store import VectorStore

    rag_config = _load_rag_config()

    emb_cfg = rag_config.get("embedding", {})
    embedding_service = EmbeddingService(
        model_name=emb_cfg.get("model", "BAAI/bge-base-en-v1.5"),
        device=emb_cfg.get("device", "cpu"),
    )

    vs_cfg = rag_config.get("vector_store", {})
    vector_store = VectorStore(
        db_path=vs_cfg.get("path", "data/lancedb"),
    )

    rr_cfg = rag_config.get("reranker", {})
    reranker = None
    if rr_cfg.get("enabled", True):
        reranker = Reranker(
            model_name=rr_cfg.get("model", "mixedbread-ai/mxbai-rerank-base-v2"),
            device=rr_cfg.get("device", "cpu"),
        )

    ret_cfg = rag_config.get("retrieval", {})
    return RetrievalService(
        vector_store=vector_store,
        embedding_service=embedding_service,
        reranker=reranker,
        query_preprocessor=QueryPreprocessor(),
        top_k_search=ret_cfg.get("top_k_search", 50),
        top_k_rerank=ret_cfg.get("top_k_rerank", 10),
        top_k_final=ret_cfg.get("top_k_final", 5),
        citation_boost=ret_cfg.get("citation_boost", 1.5),
        statutory_boost=ret_cfg.get("statutory_boost", 1.2),
        diversity_max_per_doc=ret_cfg.get("diversity_max_per_doc", 3),
    )


def _handle_embed(args) -> int:
    """Generate vector embeddings for chunks."""
    from employee_help.retrieval.embedder import EmbeddingService
    from employee_help.retrieval.vector_store import VectorStore
    from employee_help.storage.storage import Storage

    rag_config = _load_rag_config()
    emb_cfg = rag_config.get("embedding", {})
    vs_cfg = rag_config.get("vector_store", {})

    storage = Storage(args.db)
    embedding_service = EmbeddingService(
        model_name=emb_cfg.get("model", "BAAI/bge-base-en-v1.5"),
        device=emb_cfg.get("device", "cpu"),
    )
    vector_store = VectorStore(
        db_path=vs_cfg.get("path", "data/lancedb"),
    )

    try:
        if args.rebuild:
            print("Rebuilding vector index from scratch...")
            return _embed_all(storage, embedding_service, vector_store, rebuild=True)

        if args.source:
            return _embed_source(
                args.source, storage, embedding_service, vector_store
            )

        if args.embed_all:
            return _embed_all(storage, embedding_service, vector_store)

        print("Error: Specify --all, --source <slug>, or --rebuild.", file=sys.stderr)
        return 1
    finally:
        storage.close()


def _embed_all(storage, embedding_service, vector_store, rebuild=False) -> int:
    """Embed all un-embedded chunks (or all chunks if rebuild=True)."""
    all_chunks = storage.get_all_chunks()
    active_chunks = [c for c in all_chunks if c.is_active]
    inactive_chunks = [c for c in all_chunks if not c.is_active]

    if not rebuild:
        # Incremental: only embed chunks not yet in the vector store
        embedded_hashes = vector_store.get_embedded_content_hashes()
        chunks_to_embed = [
            c for c in active_chunks if c.content_hash not in embedded_hashes
        ]
    else:
        chunks_to_embed = active_chunks

    # Deactivation sync: remove inactive chunks from vector store
    if inactive_chunks and not rebuild:
        inactive_ids = [c.id for c in inactive_chunks if c.id]
        if inactive_ids:
            embedded_ids = vector_store.get_embedded_chunk_ids()
            ids_to_remove = [cid for cid in inactive_ids if cid in embedded_ids]
            if ids_to_remove:
                vector_store.delete_embeddings(ids_to_remove)
                print(f"Deactivated {len(ids_to_remove)} inactive chunks in vector store.")

    if not chunks_to_embed:
        print("All chunks are already embedded. Nothing to do.")
        return 0

    print(f"Embedding {len(chunks_to_embed)} chunks (total active: {len(active_chunks)})...")

    # Build doc URL map and language map for metadata
    all_docs = storage.get_all_documents()
    doc_url_map = {d.id: d.source_url for d in all_docs if d.id}
    doc_language_map = {d.id: d.language for d in all_docs if d.id}

    # Build source_id map from documents
    doc_source_map = {d.id: d.source_id for d in all_docs if d.id}

    # Embed in batches
    embeddings = embedding_service.embed_chunks(
        chunks_to_embed,
        source_id=0,  # Will be overridden per-chunk below
        doc_url_map=doc_url_map,
        doc_language_map=doc_language_map,
    )

    # Fix source_id per embedding
    for emb, chunk in zip(embeddings, chunks_to_embed):
        emb.source_id = doc_source_map.get(chunk.document_id, 0) or 0

    if rebuild:
        vector_store.create_table(embeddings)
    else:
        vector_store.upsert_embeddings(embeddings)

    print(f"Embedded {len(embeddings)} chunks successfully.")
    stats = vector_store.get_stats()
    print(f"Vector index: {stats.get('embedding_count', 0)} total embeddings")
    return 0


def _embed_source(slug, storage, embedding_service, vector_store) -> int:
    """Embed chunks for a specific source."""
    source = storage.get_source(slug)
    if not source:
        print(f"Error: Source '{slug}' not found in database.", file=sys.stderr)
        return 1

    chunks = storage.get_all_chunks(source_id=source.id)
    active_chunks = [c for c in chunks if c.is_active]

    if not active_chunks:
        print(f"No active chunks found for source '{slug}'.")
        return 0

    # Check which need embedding
    embedded_hashes = vector_store.get_embedded_content_hashes()
    chunks_to_embed = [
        c for c in active_chunks if c.content_hash not in embedded_hashes
    ]

    if not chunks_to_embed:
        print(f"All {len(active_chunks)} chunks for '{slug}' are already embedded.")
        return 0

    print(f"Embedding {len(chunks_to_embed)} chunks for source '{slug}'...")

    all_docs = storage.get_all_documents(source_id=source.id)
    doc_url_map = {d.id: d.source_url for d in all_docs if d.id}
    doc_language_map = {d.id: d.language for d in all_docs if d.id}

    embeddings = embedding_service.embed_chunks(
        chunks_to_embed,
        source_id=source.id or 0,
        doc_url_map=doc_url_map,
        doc_language_map=doc_language_map,
    )

    # Batch upserts to avoid OOM on large sources (e.g. 14K+ case law chunks)
    batch_size = 2000
    for i in range(0, len(embeddings), batch_size):
        batch = embeddings[i : i + batch_size]
        vector_store.upsert_embeddings(batch)
        print(f"  Upserted batch {i // batch_size + 1} ({len(batch)} embeddings)")

    print(f"Embedded {len(embeddings)} chunks for '{slug}'.")
    return 0


def _handle_embed_status(args) -> int:
    """Show embedding coverage and index stats."""
    from employee_help.retrieval.vector_store import VectorStore
    from employee_help.storage.storage import Storage

    rag_config = _load_rag_config()
    vs_cfg = rag_config.get("vector_store", {})

    storage = Storage(args.db)
    vector_store = VectorStore(
        db_path=vs_cfg.get("path", "data/lancedb"),
    )

    try:
        # Get total chunk counts per source
        sources = storage.get_all_sources()
        stats = vector_store.get_stats()

        print("\n" + "=" * 60)
        print("EMBEDDING STATUS")
        print("=" * 60)
        print(f"Vector store:  {vs_cfg.get('path', 'data/lancedb')}")
        print(f"Table exists:  {stats.get('table_exists', False)}")
        print(f"Total vectors: {stats.get('embedding_count', 0)}")
        print(f"Active:        {stats.get('active_count', 0)}")

        emb_cfg = rag_config.get("embedding", {})
        print(f"Model:         {emb_cfg.get('model', 'BAAI/bge-base-en-v1.5')}")

        # Per-source breakdown
        total_chunks = 0
        print("\nPer-source coverage:")
        for source in sources:
            source_chunks = storage.get_all_chunks(source_id=source.id)
            active_count = sum(1 for c in source_chunks if c.is_active)
            total_chunks += active_count
            print(f"  {source.slug:30s} {active_count:>6d} active chunks")

        embedded_count = stats.get("embedding_count", 0)
        coverage = (embedded_count / total_chunks * 100) if total_chunks > 0 else 0
        print(f"\nCoverage: {embedded_count}/{total_chunks} ({coverage:.1f}%)")

        if stats.get("content_categories"):
            print("\nBy content category:")
            for cat, count in sorted(stats["content_categories"].items()):
                print(f"  {cat:30s} {count:>6d}")

        print("=" * 60 + "\n")
        return 0
    finally:
        storage.close()


def _handle_search(args) -> int:
    """Run hybrid search and display results."""
    import json as json_module

    retrieval_service = _build_retrieval_service(args.db)

    results = retrieval_service.retrieve(
        query=args.query,
        mode=args.mode,
        top_k=args.top_k,
    )

    if args.json_output:
        output = [
            {
                "rank": i + 1,
                "chunk_id": r.chunk_id,
                "relevance_score": round(r.relevance_score, 4),
                "content_category": r.content_category,
                "citation": r.citation,
                "heading_path": r.heading_path,
                "content": r.content if args.verbose else r.content[:200],
                "source_url": r.source_url,
            }
            for i, r in enumerate(results)
        ]
        print(json_module.dumps(output, indent=2))
        return 0

    if not results:
        print("No results found.")
        return 0

    print(f"\nSearch results for: {args.query}")
    print(f"Mode: {args.mode} | Results: {len(results)}")
    print("-" * 60)

    for i, r in enumerate(results):
        print(f"\n[{i + 1}] Score: {r.relevance_score:.4f} | {r.content_category}")
        if r.citation:
            print(f"    Citation: {r.citation}")
        print(f"    Path: {r.heading_path}")
        if r.source_url:
            print(f"    URL: {r.source_url}")

        if args.verbose:
            print(f"    Content:\n    {r.content}")
        else:
            preview = r.content[:200].replace("\n", " ")
            print(f"    Preview: {preview}...")

    print()
    return 0


def _handle_ask(args) -> int:
    """Generate a RAG answer to a question."""
    import json as json_module

    from employee_help.generation.llm import LLMClient
    from employee_help.generation.prompts import PromptBuilder
    from employee_help.generation.service import AnswerService

    rag_config = _load_rag_config()
    gen_cfg = rag_config.get("generation", {})

    retrieval_service = _build_retrieval_service(args.db)

    try:
        llm_client = LLMClient(
            timeout=gen_cfg.get("timeout_seconds", 30),
            consumer_model=gen_cfg.get("consumer_model"),
            attorney_model=gen_cfg.get("attorney_model"),
        )
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        print(
            "Set your API key with: export ANTHROPIC_API_KEY=your-key-here",
            file=sys.stderr,
        )
        return 1

    prompt_builder = PromptBuilder(
        max_context_tokens=gen_cfg.get("max_context_tokens", 6000),
        rag_config=rag_config,
    )

    # Optionally create citation verifiers for attorney-mode verification
    from employee_help.generation.citation_verifier import (
        CaseCitationVerifier,
        StatuteCitationVerifier,
    )

    case_verifier = CaseCitationVerifier()  # Uses COURTLISTENER_API_TOKEN env var
    statute_verifier = None
    try:
        from employee_help.storage.storage import Storage as _Storage

        statute_verifier = StatuteCitationVerifier(_Storage())
    except Exception:
        pass

    answer_service = AnswerService(
        retrieval_service=retrieval_service,
        llm_client=llm_client,
        prompt_builder=prompt_builder,
        citation_validation=gen_cfg.get("citation_validation", "strict"),
        case_verifier=case_verifier,
        statute_verifier=statute_verifier,
    )

    if not args.no_stream and not args.json_output:
        # Streaming mode
        stream, retrieval_results, stream_metadata = answer_service.generate_stream(
            query=args.query,
            mode=args.mode,
        )

        if args.debug:
            print(f"\n--- Retrieval Results ({len(retrieval_results)} chunks) ---")
            for i, r in enumerate(retrieval_results):
                print(f"  [{i + 1}] {r.citation or r.heading_path} (score: {r.relevance_score:.4f})")
            print()

        print(f"\n{'=' * 60}")
        print(f"Mode: {args.mode}")
        print(f"{'=' * 60}\n")

        for chunk in stream:
            print(chunk, end="", flush=True)

        print("\n")
        print(f"{'=' * 60}")

        # Show token usage and cost from stream metadata
        if stream_metadata:
            meta = stream_metadata[0]
            model = meta.get("model", "")
            in_tok = meta.get("input_tokens", 0)
            out_tok = meta.get("output_tokens", 0)
            if model:
                print(f"Model:  {model}")
            if in_tok or out_tok:
                from employee_help.generation.models import TokenUsage
                usage = TokenUsage(input_tokens=in_tok, output_tokens=out_tok, model=model)
                print(f"Tokens: {in_tok} in / {out_tok} out")
                print(f"Cost:   ${usage.cost_estimate:.4f}")

        print(f"Sources: {len(retrieval_results)} chunks retrieved")
        for r in retrieval_results:
            label = r.citation or r.heading_path
            print(f"  - {label}")
        print(f"{'=' * 60}\n")
    else:
        # Non-streaming or JSON mode
        if args.debug:
            # Show retrieval results without making a separate call
            # (generate() will call retrieve() internally)
            pass

        answer = answer_service.generate(query=args.query, mode=args.mode)

        if args.debug:
            print(f"\n--- Retrieval Results ({len(answer.retrieval_results)} chunks) ---")
            for i, r in enumerate(answer.retrieval_results):
                print(f"  [{i + 1}] {r.citation or r.heading_path} (score: {r.relevance_score:.4f})")
            print()

        if args.json_output:
            output = {
                "text": answer.text,
                "mode": answer.mode,
                "query": answer.query,
                "model": answer.model_used,
                "token_usage": {
                    "input": answer.token_usage.input_tokens,
                    "output": answer.token_usage.output_tokens,
                    "cost_estimate": round(answer.token_usage.cost_estimate, 6),
                },
                "duration_ms": answer.duration_ms,
                "citations": [
                    {
                        "claim": c.claim_text,
                        "citation": c.citation,
                        "source_url": c.source_url,
                        "category": c.content_category,
                    }
                    for c in answer.citations
                ],
                "warnings": answer.warnings,
            }
            print(json_module.dumps(output, indent=2))
        else:
            print(f"\n{'=' * 60}")
            print(f"Mode: {answer.mode} | Model: {answer.model_used}")
            print(f"{'=' * 60}\n")
            print(answer.text)
            print(f"\n{'=' * 60}")
            print(f"Tokens: {answer.token_usage.input_tokens} in / {answer.token_usage.output_tokens} out")
            print(f"Cost:   ${answer.token_usage.cost_estimate:.4f}")
            print(f"Time:   {answer.duration_ms}ms")
            if answer.warnings:
                print(f"Warnings: {', '.join(answer.warnings)}")
            print(f"Sources: {len(answer.retrieval_results)} chunks")
            for r in answer.retrieval_results:
                label = r.citation or r.heading_path
                print(f"  - {label}")
            print(f"{'=' * 60}\n")

    return 0


def _handle_evaluate_retrieval(args) -> int:
    """Run automated retrieval quality evaluation."""
    from employee_help.evaluation.retrieval_metrics import run_retrieval_evaluation

    retrieval_service = _build_retrieval_service(args.db)

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    report = run_retrieval_evaluation(retrieval_service, output_dir)

    pf = report.get("pass_fail", {})
    print(f"\n{'=' * 60}")
    print("RETRIEVAL EVALUATION REPORT")
    print(f"{'=' * 60}")
    print(f"Questions evaluated: {report['total_questions']}")
    print(f"Consumer precision@5: {report['consumer_precision']:.3f} "
          f"[{'PASS' if pf.get('consumer_precision') else 'FAIL'}]")
    print(f"Attorney precision@5: {report['attorney_precision']:.3f} "
          f"[{'PASS' if pf.get('attorney_precision') else 'FAIL'}]")
    print(f"Citation top-1 accuracy: {report['citation_top1_accuracy']:.3f} "
          f"[{'PASS' if pf.get('citation_top1') else 'FAIL'}]")
    print(f"Overall MRR: {report['overall_mrr']:.3f}")
    print(f"Overall: {'PASS' if report.get('overall_pass') else 'FAIL'}")
    print(f"Report saved to: {output_dir}")
    print(f"{'=' * 60}\n")

    return 0


def _handle_evaluate_answers(args) -> int:
    """Run automated answer quality evaluation."""
    from employee_help.evaluation.answer_metrics import run_answer_evaluation
    from employee_help.generation.llm import LLMClient
    from employee_help.generation.prompts import PromptBuilder
    from employee_help.generation.service import AnswerService

    rag_config = _load_rag_config()
    gen_cfg = rag_config.get("generation", {})

    retrieval_service = _build_retrieval_service(args.db)

    if not args.dry_run:
        try:
            llm_client = LLMClient(
                timeout=gen_cfg.get("timeout_seconds", 30),
                consumer_model=gen_cfg.get("consumer_model"),
                attorney_model=gen_cfg.get("attorney_model"),
            )
        except ValueError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1

        prompt_builder = PromptBuilder(
            max_context_tokens=gen_cfg.get("max_context_tokens", 6000),
        )

        answer_service = AnswerService(
            retrieval_service=retrieval_service,
            llm_client=llm_client,
            prompt_builder=prompt_builder,
            citation_validation=gen_cfg.get("citation_validation", "strict"),
        )
    else:
        answer_service = None

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    report = run_answer_evaluation(
        retrieval_service=retrieval_service,
        answer_service=answer_service,
        output_dir=output_dir,
        dry_run=args.dry_run,
    )

    print(f"\n{'=' * 60}")
    print("ANSWER EVALUATION REPORT")
    print(f"{'=' * 60}")
    print(f"Questions evaluated: {report['total_questions']}")
    if not args.dry_run:
        print(f"Disclaimer rate: {report.get('disclaimer_rate', 'N/A')}")
        print(f"Avg reading level: {report.get('avg_reading_level', 'N/A')}")
        print(f"Avg citation completeness: {report.get('avg_citation_completeness', 'N/A')}")
        print(f"Avg cost per query: ${report.get('avg_cost', 0):.4f}")
        if "adversarial_pass_rate" in report:
            print(f"Adversarial pass rate: {report['adversarial_pass_rate']:.1%}")
    print(f"Report saved to: {output_dir}")
    print(f"{'=' * 60}\n")

    return 0


def _handle_feedback(args) -> int:
    """Display query analytics and feedback dashboard."""
    from employee_help.feedback.store import FeedbackStore

    db_path = Path(args.db)
    if not db_path.exists():
        print(f"No feedback database found at {db_path}")
        print("Feedback data is collected automatically when the API serves queries.")
        return 0

    days = args.days
    store = FeedbackStore(db_path)

    try:
        mode_dist = store.get_mode_distribution(days=days)
        total_queries = sum(mode_dist.values())

        if total_queries == 0:
            print(f"No queries recorded in the last {days} days.")
            return 0

        fb_summary = store.get_feedback_summary(days=days)
        daily = store.get_daily_stats(days=days)
        repeated = store.get_top_repeated_queries(days=days, limit=10)

        print(f"\n{'=' * 60}")
        print(f"FEEDBACK DASHBOARD  (last {days} days)")
        print(f"{'=' * 60}")

        # Query volume
        consumer = mode_dist.get("consumer", 0)
        attorney = mode_dist.get("attorney", 0)
        print(f"Total queries:       {total_queries}")
        print(f"  Consumer:          {consumer}  ({consumer / total_queries:.0%})")
        print(f"  Attorney:          {attorney}  ({attorney / total_queries:.0%})")

        # Cost & performance
        if daily:
            avg_cost = sum(d["avg_cost"] for d in daily) / len(daily)
            avg_dur = sum(d["avg_duration_ms"] for d in daily) / len(daily)
            print(f"Avg cost/query:      ${avg_cost:.4f}")
            print(f"Avg duration:        {avg_dur:.0f}ms")

        # Feedback
        print(f"\nFeedback:")
        print(f"  Thumbs up:         {fb_summary['thumbs_up']}")
        print(f"  Thumbs down:       {fb_summary['thumbs_down']}")
        if fb_summary["total_feedback"] > 0:
            print(f"  Approval rate:     {fb_summary['approval_rate']:.0%}")
        print(f"  Feedback rate:     {fb_summary['feedback_rate']:.0%} of queries")

        # Daily volume (ASCII bar chart for last 7 days)
        recent = daily[-7:] if len(daily) > 7 else daily
        if recent:
            max_total = max(d["total"] for d in recent)
            bar_width = 30
            print(f"\nDaily volume (last {len(recent)} days):")
            for d in recent:
                bar_len = int((d["total"] / max_total) * bar_width) if max_total else 0
                bar = "#" * bar_len
                print(f"  {d['day']}  {bar} {d['total']}")

        # Top repeated queries
        if repeated:
            print(f"\nTop repeated query hashes:")
            for r in repeated[:10]:
                print(f"  {r['query_hash'][:12]}...  {r['mode']:>8}  x{r['count']}")

        print(f"{'=' * 60}\n")
        return 0

    finally:
        store.close()


def _handle_citation_audit(args) -> int:
    """Display citation verification audit report."""
    import csv as csv_module

    from employee_help.feedback.store import FeedbackStore

    db_path = Path(args.db)
    if not db_path.exists():
        print(f"No feedback database found at {db_path}")
        return 0

    store = FeedbackStore(db_path)

    try:
        # Session-specific view
        if args.session:
            rows = store.get_citation_audit_by_session(args.session)
            if not rows:
                print(f"No citations found for session {args.session}")
                return 0

            print(f"\n{'=' * 70}")
            print(f"CITATION AUDIT — Session {args.session[:12]}...")
            print(f"{'=' * 70}")
            for row in rows:
                conf = row["confidence"].upper()
                print(
                    f"  [{conf:>10}]  {row['citation_type']:>7}  {row['citation_text']}"
                )
                if row["detail"]:
                    print(f"               {row['detail']}")
            print(f"{'=' * 70}\n")
            return 0

        # CSV export
        if args.csv:
            rows = store.get_citation_audit_rows(
                days=args.days, confidence=args.confidence
            )
            if not rows:
                print(f"No citation audit data in the last {args.days} days.")
                return 0

            csv_path = Path(args.csv)
            csv_path.parent.mkdir(parents=True, exist_ok=True)
            with open(csv_path, "w", newline="") as f:
                writer = csv_module.DictWriter(
                    f,
                    fieldnames=[
                        "query_id",
                        "citation_text",
                        "citation_type",
                        "verification_status",
                        "confidence",
                        "detail",
                        "model_used",
                        "session_id",
                        "created_at",
                    ],
                )
                writer.writeheader()
                writer.writerows(rows)
            print(f"Exported {len(rows)} rows to {csv_path}")
            return 0

        # Summary report (default)
        days = args.days
        stats = store.get_citation_audit_stats(days=days)

        if stats["total"] == 0:
            print(f"No citation audit data in the last {days} days.")
            return 0

        print(f"\n{'=' * 60}")
        print(f"CITATION AUDIT REPORT  (last {days} days)")
        print(f"{'=' * 60}")

        total = stats["total"]
        print(f"Total citations verified: {total}")
        print(
            f"  Verified:    {stats['verified']:>5}  "
            f"({stats['verified'] / total:.0%})"
        )
        print(
            f"  Unverified:  {stats['unverified']:>5}  "
            f"({stats['unverified'] / total:.0%})"
        )
        print(
            f"  Suspicious:  {stats['suspicious']:>5}  "
            f"({stats['suspicious'] / total:.0%})"
        )

        # Breakdown by type
        by_type = store.get_citation_audit_by_type(days=days)
        if by_type:
            print(f"\nBy citation type:")
            for row in by_type:
                print(
                    f"  {row['citation_type']:>7} / {row['confidence']:<12}  "
                    f"{row['count']}"
                )

        print(f"{'=' * 60}\n")
        return 0

    finally:
        store.close()


def _handle_ingest_caselaw(args) -> int:
    """Execute the ingest-caselaw command."""
    from employee_help.pipeline import Pipeline

    config_path = Path(args.config)
    logger.info("ingest_caselaw", config_path=str(config_path), dry_run=args.dry_run)

    try:
        source_config = load_source_config(config_path)
    except FileNotFoundError:
        print(f"Error: Config not found at {config_path}", file=sys.stderr)
        return 1
    except ValueError as e:
        print(f"Error: Invalid config: {e}", file=sys.stderr)
        return 1

    if not source_config.caselaw:
        print("Error: Config has no 'caselaw' section.", file=sys.stderr)
        return 1

    # Override max_opinions from CLI if provided
    if args.max_opinions is not None:
        source_config.caselaw.max_opinions = args.max_opinions

    # Override db path if provided
    if args.db != "data/employee_help.db":
        source_config.database_path = args.db

    pipeline = Pipeline(source_config)
    stats = pipeline.run(dry_run=args.dry_run)

    print("\n" + "=" * 60)
    print("CASE LAW INGESTION REPORT")
    print("=" * 60)
    print(f"Source:              {stats.source_slug}")
    print(f"Opinions processed:  {stats.urls_crawled}")
    print(f"Documents stored:    {stats.documents_stored}")
    print(f"Chunks created:      {stats.chunks_created}")
    print(f"Errors:              {stats.errors}")
    print(f"Duration:            {stats.duration_seconds:.1f}s")
    print("=" * 60 + "\n")

    return 0 if stats.errors == 0 else 1


def _handle_spot_check_caselaw(args) -> int:
    """Spot-check ingested case law for quality (4C.6)."""
    import random

    from employee_help.storage.storage import Storage

    storage = Storage(args.db)
    try:
        source = storage.get_source("courtlistener")
        if not source:
            print("No 'courtlistener' source found in database.")
            print("Run 'employee-help ingest-caselaw' first.")
            return 1

        docs = storage.get_all_documents(source_id=source.id)
        if not docs:
            print("No case law documents found.")
            return 1

        sample_size = min(args.samples, len(docs))
        sampled = random.sample(docs, sample_size)

        print(f"\n{'=' * 70}")
        print(f"CASE LAW SPOT CHECK  ({sample_size} of {len(docs)} opinions)")
        print(f"{'=' * 70}")

        issues = 0
        for i, doc in enumerate(sampled, 1):
            chunks = storage.get_chunks_for_document(doc.id)
            first_chunk = chunks[0] if chunks else None

            # Checks
            checks = []
            has_citation = bool(first_chunk and first_chunk.citation)
            has_content = bool(doc.raw_content and len(doc.raw_content) > 100)
            has_title = bool(doc.title and doc.title != "Unknown")
            is_case_law = doc.content_category.value == "case_law"
            has_chunks = len(chunks) > 0

            if not has_citation:
                checks.append("MISSING citation")
            if not has_content:
                checks.append("EMPTY/SHORT content")
            if not has_title:
                checks.append("MISSING title")
            if not is_case_law:
                checks.append(f"WRONG category ({doc.content_category.value})")
            if not has_chunks:
                checks.append("NO chunks")

            status = "PASS" if not checks else "FAIL"
            if checks:
                issues += 1

            print(f"\n[{i}/{sample_size}] {status}")
            print(f"  Title:      {doc.title[:70]}")
            print(f"  URL:        {doc.source_url}")
            if first_chunk and first_chunk.citation:
                print(f"  Citation:   {first_chunk.citation[:70]}")
            print(f"  Chunks:     {len(chunks)}")
            print(f"  Content:    {len(doc.raw_content)} chars")
            print(f"  Category:   {doc.content_category.value}")
            if checks:
                print(f"  Issues:     {', '.join(checks)}")

        # Citation links summary
        link_count = storage.get_citation_link_count()

        print(f"\n{'=' * 70}")
        print(f"SUMMARY")
        print(f"  Total opinions:    {len(docs)}")
        print(f"  Sampled:           {sample_size}")
        print(f"  Passed:            {sample_size - issues}")
        print(f"  Failed:            {issues}")
        print(f"  Citation links:    {link_count}")
        print(f"  Quality:           {(sample_size - issues) / sample_size:.0%}")
        print(f"{'=' * 70}\n")

        return 0 if issues == 0 else 1

    finally:
        storage.close()


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
