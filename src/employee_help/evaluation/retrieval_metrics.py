"""Retrieval quality metrics: precision, recall, MRR, and evaluation runner.

Supports consumer, attorney, and adversarial evaluation datasets with
configurable pass/fail thresholds.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import structlog
import yaml

from employee_help.retrieval.service import RetrievalResult, RetrievalService

logger = structlog.get_logger()

# Default quality thresholds
THRESHOLDS = {
    "consumer_precision_at_5": 0.6,
    "attorney_precision_at_5": 0.7,
    "citation_top1_accuracy": 0.9,
}


def precision_at_k(
    retrieved: list[RetrievalResult],
    relevant_categories: set[str],
    k: int = 5,
) -> float:
    """Fraction of top-k results whose content_category is in the expected set."""
    top_k = retrieved[:k]
    if not top_k:
        return 0.0
    hits = sum(1 for r in top_k if r.content_category in relevant_categories)
    return hits / len(top_k)


def recall_at_k(
    retrieved: list[RetrievalResult],
    expected_citations: list[str],
    k: int = 5,
) -> float:
    """Fraction of expected citations found in top-k results."""
    if not expected_citations:
        return 1.0  # Nothing expected, so recall is trivially 1
    top_k = retrieved[:k]
    retrieved_citations = {r.citation for r in top_k if r.citation}
    hits = sum(
        1 for ec in expected_citations if any(ec in rc for rc in retrieved_citations)
    )
    return hits / len(expected_citations)


def mean_reciprocal_rank(
    retrieved: list[RetrievalResult],
    relevant_categories: set[str],
) -> float:
    """1/rank of the first relevant result."""
    for i, r in enumerate(retrieved):
        if r.content_category in relevant_categories:
            return 1.0 / (i + 1)
    return 0.0


def citation_hit_at_k(
    retrieved: list[RetrievalResult],
    expected_section: str,
    k: int = 1,
) -> bool:
    """Check if the expected citation section appears in top-k results."""
    top_k = retrieved[:k]
    for r in top_k:
        if r.citation and expected_section in r.citation:
            return True
    return False


def run_retrieval_evaluation(
    retrieval_service: RetrievalService,
    output_dir: Path,
    eval_dir: Path | None = None,
) -> dict[str, Any]:
    """Run retrieval evaluation against the evaluation datasets.

    Loads consumer, attorney, and adversarial question sets, runs retrieval
    for each, and computes aggregate metrics with pass/fail assessment.

    Args:
        retrieval_service: Configured retrieval service.
        output_dir: Where to save evaluation reports.
        eval_dir: Directory containing evaluation YAML files.

    Returns:
        Dict with evaluation metrics and per-question results.
    """
    if eval_dir is None:
        eval_dir = Path("tests/evaluation")

    results: dict[str, Any] = {
        "total_questions": 0,
        "consumer_precision": 0.0,
        "attorney_precision": 0.0,
        "overall_mrr": 0.0,
        "citation_top1_accuracy": 0.0,
        "per_question": [],
        "thresholds": THRESHOLDS,
        "pass_fail": {},
    }

    consumer_metrics = _evaluate_mode(
        retrieval_service, eval_dir / "consumer_questions.yaml", "consumer"
    )
    attorney_metrics = _evaluate_mode(
        retrieval_service, eval_dir / "attorney_questions.yaml", "attorney"
    )
    adversarial_metrics = _evaluate_adversarial(
        retrieval_service, eval_dir / "adversarial_questions.yaml"
    )

    all_metrics = consumer_metrics + attorney_metrics
    results["total_questions"] = len(all_metrics) + len(adversarial_metrics)

    if consumer_metrics:
        results["consumer_precision"] = sum(
            m["precision_at_5"] for m in consumer_metrics
        ) / len(consumer_metrics)

    if attorney_metrics:
        results["attorney_precision"] = sum(
            m["precision_at_5"] for m in attorney_metrics
        ) / len(attorney_metrics)

    if all_metrics:
        results["overall_mrr"] = sum(m["mrr"] for m in all_metrics) / len(all_metrics)

    # Citation-specific lookup queries (pure citation queries, not concept queries)
    citation_lookups = [m for m in attorney_metrics if m.get("is_citation_lookup")]
    if citation_lookups:
        hits = sum(1 for m in citation_lookups if m.get("citation_hit_top1"))
        results["citation_top1_accuracy"] = hits / len(citation_lookups)

    # Also report broader citation recall across all attorney questions with expected citations
    all_citation_qs = [m for m in attorney_metrics if m.get("has_citation_query")]
    if all_citation_qs:
        hits = sum(1 for m in all_citation_qs if m.get("citation_hit_top1"))
        results["citation_top1_all_queries"] = hits / len(all_citation_qs)

    results["per_question"] = all_metrics + adversarial_metrics
    results["adversarial_count"] = len(adversarial_metrics)

    # Assess pass/fail against thresholds
    results["pass_fail"] = {
        "consumer_precision": results["consumer_precision"] >= THRESHOLDS["consumer_precision_at_5"],
        "attorney_precision": results["attorney_precision"] >= THRESHOLDS["attorney_precision_at_5"],
        "citation_top1": results["citation_top1_accuracy"] >= THRESHOLDS["citation_top1_accuracy"],
    }
    results["overall_pass"] = all(results["pass_fail"].values())

    # Save report
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / "retrieval_evaluation.json"
    report_path.write_text(json.dumps(results, indent=2))

    md_path = output_dir / "retrieval_evaluation.md"
    md_path.write_text(_format_markdown_report(results))

    return results


def _evaluate_mode(
    retrieval_service: RetrievalService,
    questions_path: Path,
    mode: str,
) -> list[dict[str, Any]]:
    """Evaluate retrieval for a set of questions in a given mode."""
    if not questions_path.exists():
        logger.warning("evaluation_dataset_not_found", path=str(questions_path))
        return []

    with open(questions_path) as f:
        dataset = yaml.safe_load(f)

    questions = dataset.get("questions", [])
    metrics_list = []

    for q in questions:
        question_text = q["question"]
        expected_categories = set(q.get("expected_categories", []))
        expected_citations = q.get("expected_citations", [])

        retrieved = retrieval_service.retrieve(question_text, mode=mode)

        prec = precision_at_k(retrieved, expected_categories, k=5)
        rec = recall_at_k(retrieved, expected_citations, k=5)
        mrr = mean_reciprocal_rank(retrieved, expected_categories)

        is_citation_lookup = q.get("citation_lookup", False)

        metric: dict[str, Any] = {
            "question": question_text,
            "mode": mode,
            "results_count": len(retrieved),
            "precision_at_5": prec,
            "recall_at_5": rec,
            "mrr": mrr,
            "has_citation_query": bool(expected_citations),
            "is_citation_lookup": is_citation_lookup,
        }

        if expected_citations:
            metric["citation_hit_top1"] = any(
                citation_hit_at_k(retrieved, ec, k=1) for ec in expected_citations
            )

        metrics_list.append(metric)

    return metrics_list


def _evaluate_adversarial(
    retrieval_service: RetrievalService,
    questions_path: Path,
) -> list[dict[str, Any]]:
    """Evaluate adversarial questions (out-of-scope, fabricated citations, etc.)."""
    if not questions_path.exists():
        logger.warning("adversarial_dataset_not_found", path=str(questions_path))
        return []

    with open(questions_path) as f:
        dataset = yaml.safe_load(f)

    questions = dataset.get("questions", [])
    metrics_list = []

    for q in questions:
        question_text = q["question"]
        expected_behavior = q.get("expected_behavior", "")

        # Run in attorney mode (most permissive)
        retrieved = retrieval_service.retrieve(question_text, mode="attorney")

        metric: dict[str, Any] = {
            "question": question_text,
            "mode": "adversarial",
            "expected_behavior": expected_behavior,
            "results_count": len(retrieved),
            "precision_at_5": 0.0,
            "recall_at_5": 0.0,
            "mrr": 0.0,
        }

        # For adversarial questions, we mainly check that retrieval doesn't crash
        # and note the results count. The real adversarial testing happens
        # in the answer evaluation (where we check the LLM's response).
        metrics_list.append(metric)

    return metrics_list


def _format_markdown_report(results: dict[str, Any]) -> str:
    """Format evaluation results as a Markdown report."""
    lines = [
        "# Retrieval Evaluation Report",
        "",
        "## Summary",
        "",
        f"- **Total questions**: {results['total_questions']}",
        f"- **Consumer precision@5**: {results['consumer_precision']:.3f} "
        f"({'PASS' if results['pass_fail'].get('consumer_precision') else 'FAIL'} "
        f"threshold: {THRESHOLDS['consumer_precision_at_5']})",
        f"- **Attorney precision@5**: {results['attorney_precision']:.3f} "
        f"({'PASS' if results['pass_fail'].get('attorney_precision') else 'FAIL'} "
        f"threshold: {THRESHOLDS['attorney_precision_at_5']})",
        f"- **Overall MRR**: {results['overall_mrr']:.3f}",
        f"- **Citation top-1 accuracy**: {results['citation_top1_accuracy']:.3f} "
        f"({'PASS' if results['pass_fail'].get('citation_top1') else 'FAIL'} "
        f"threshold: {THRESHOLDS['citation_top1_accuracy']})",
        f"- **Adversarial questions**: {results.get('adversarial_count', 0)}",
        f"- **Overall**: {'PASS' if results.get('overall_pass') else 'FAIL'}",
        "",
        "## Per-Question Results",
        "",
        "| # | Mode | Question | P@5 | R@5 | MRR | Results |",
        "|---|------|----------|-----|-----|-----|---------|",
    ]

    for i, q in enumerate(results.get("per_question", [])):
        question_short = q["question"][:50] + "..." if len(q["question"]) > 50 else q["question"]
        lines.append(
            f"| {i + 1} | {q['mode']} | {question_short} | "
            f"{q['precision_at_5']:.2f} | {q['recall_at_5']:.2f} | "
            f"{q['mrr']:.2f} | {q['results_count']} |"
        )

    return "\n".join(lines) + "\n"
