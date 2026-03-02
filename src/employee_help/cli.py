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

    vector_store.upsert_embeddings(embeddings)
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
