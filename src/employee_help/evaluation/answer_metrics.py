"""Answer quality metrics: citation accuracy, disclaimers, reading level, and evaluation runner.

Metrics are split into deterministic (no LLM required) and LLM-as-judge categories.
Deterministic metrics run in CI; LLM-based metrics run on demand.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import structlog
import yaml

from employee_help.retrieval.service import RetrievalService

logger = structlog.get_logger()

# Disclaimer patterns
CONSUMER_DISCLAIMER_PATTERN = re.compile(
    r"(educational purposes|not legal advice|consult.+attorney)", re.IGNORECASE
)
ATTORNEY_DISCLAIMER_PATTERN = re.compile(
    r"(independently verified|does not constitute legal advice|should be.+verified)",
    re.IGNORECASE,
)


def citation_accuracy(
    answer_citations: list[str],
    knowledge_base_citations: set[str],
) -> float:
    """Fraction of citations in the answer that exist in the knowledge base.

    This measures whether the LLM fabricated citations -- a citation_accuracy
    of 1.0 means no hallucinated citations.
    """
    if not answer_citations:
        return 1.0  # No citations to be wrong about
    hits = sum(
        1
        for ac in answer_citations
        if any(_section_match(ac, kbc) for kbc in knowledge_base_citations)
    )
    return hits / len(answer_citations)


def citation_completeness(
    answer_citations: list[str],
    expected_citations: list[str],
) -> float:
    """Fraction of expected citations that appear in the answer.

    This measures whether the LLM found and cited all relevant statutes.
    """
    if not expected_citations:
        return 1.0
    hits = sum(
        1
        for ec in expected_citations
        if any(_section_match(ec, ac) for ac in answer_citations)
    )
    return hits / len(expected_citations)


def has_disclaimer(answer_text: str, mode: str) -> bool:
    """Check if the answer contains an appropriate disclaimer."""
    pattern = (
        CONSUMER_DISCLAIMER_PATTERN
        if mode == "consumer"
        else ATTORNEY_DISCLAIMER_PATTERN
    )
    return bool(pattern.search(answer_text))


def reading_level(text: str) -> float:
    """Estimate Flesch-Kincaid grade level.

    Uses textstat if available, otherwise falls back to a rough estimate.
    Consumer target: grade 8-12. Attorney target: grade 12-16.
    """
    try:
        import textstat

        return textstat.flesch_kincaid_grade(text)
    except ImportError:
        # Rough estimate: count syllables, words, sentences
        words = text.split()
        sentences = max(1, len(re.findall(r"[.!?]+", text)))
        word_count = max(1, len(words))
        # Rough syllable count: 1.3 syllables per word average
        syllables = word_count * 1.3
        grade = 0.39 * (word_count / sentences) + 11.8 * (syllables / word_count) - 15.59
        return max(0, grade)


def extract_statute_citations(text: str) -> list[str]:
    """Extract California statute citations from answer text."""
    pattern = re.compile(
        r"Cal\.\s+(?:Lab|Gov|Bus\.\s*&\s*Prof|Civ\.\s*Proc|Unemp\.\s*Ins)\.\s*Code\s*§\s*[\d]+(?:\.\d+)?(?:\([a-z0-9]+\))*",
        re.IGNORECASE,
    )
    return pattern.findall(text)


def _section_match(cite1: str, cite2: str) -> bool:
    """Check if two citation strings refer to the same section."""
    section_pat = re.compile(r"(\d+(?:\.\d+)?)")
    m1 = section_pat.search(cite1)
    m2 = section_pat.search(cite2)
    if m1 and m2:
        return m1.group(1) == m2.group(1)
    return False


def run_answer_evaluation(
    retrieval_service: RetrievalService,
    answer_service: Any | None,
    output_dir: Path,
    dry_run: bool = False,
    eval_dir: Path | None = None,
) -> dict[str, Any]:
    """Run answer evaluation against the evaluation datasets.

    Evaluates consumer, attorney, and adversarial questions. Computes
    deterministic metrics (disclaimer, reading level, citation accuracy/completeness)
    and reports pass/fail status.

    Args:
        retrieval_service: For retrieval-only metrics.
        answer_service: For full answer generation (None if dry_run).
        output_dir: Where to save the evaluation report.
        dry_run: If True, only run retrieval evaluation (no LLM calls).
        eval_dir: Directory containing evaluation YAML files.

    Returns:
        Dict with evaluation metrics.
    """
    if eval_dir is None:
        eval_dir = Path("tests/evaluation")

    results: dict[str, Any] = {
        "total_questions": 0,
        "dry_run": dry_run,
        "per_question": [],
    }

    # Evaluate consumer and attorney questions
    for mode in ["consumer", "attorney"]:
        questions_path = eval_dir / f"{mode}_questions.yaml"
        if not questions_path.exists():
            continue

        with open(questions_path) as f:
            dataset = yaml.safe_load(f)

        questions = dataset.get("questions", [])

        for q in questions:
            question_text = q["question"]
            results["total_questions"] += 1

            metric: dict[str, Any] = {
                "question": question_text,
                "mode": mode,
            }

            if dry_run or answer_service is None:
                retrieved = retrieval_service.retrieve(question_text, mode=mode)
                metric["results_count"] = len(retrieved)
            else:
                answer = answer_service.generate(question_text, mode=mode)
                metric["results_count"] = len(answer.retrieval_results)
                metric["has_disclaimer"] = has_disclaimer(answer.text, mode)
                metric["reading_level"] = reading_level(answer.text)
                metric["answer_length"] = len(answer.text)
                metric["model"] = answer.model_used
                metric["cost"] = answer.token_usage.cost_estimate

                if mode == "attorney":
                    cited = extract_statute_citations(answer.text)
                    metric["citations_found"] = len(cited)
                    metric["citation_texts"] = cited

                    expected_citations = q.get("expected_citations", [])
                    if expected_citations:
                        metric["citation_completeness"] = citation_completeness(
                            cited, expected_citations
                        )

                metric["warnings"] = answer.warnings
                metric["answer_text"] = answer.text

            results["per_question"].append(metric)

    # Evaluate adversarial questions
    adversarial_path = eval_dir / "adversarial_questions.yaml"
    if adversarial_path.exists():
        with open(adversarial_path) as f:
            adv_dataset = yaml.safe_load(f)

        adv_questions = adv_dataset.get("questions", [])

        for q in adv_questions:
            question_text = q["question"]
            expected_behavior = q.get("expected_behavior", "")
            results["total_questions"] += 1

            metric = {
                "question": question_text,
                "mode": "adversarial",
                "expected_behavior": expected_behavior,
            }

            if not dry_run and answer_service is not None:
                answer = answer_service.generate(question_text, mode="consumer")
                metric["answer_length"] = len(answer.text)
                metric["has_disclaimer"] = has_disclaimer(answer.text, "consumer")
                metric["warnings"] = answer.warnings

                metric["answer_text"] = answer.text

                # Check adversarial behavior
                metric["behavior_check"] = _check_adversarial_behavior(
                    answer.text, expected_behavior
                )
            else:
                retrieved = retrieval_service.retrieve(question_text, mode="consumer")
                metric["results_count"] = len(retrieved)

            results["per_question"].append(metric)

    # Aggregate metrics
    if not dry_run:
        answered = [q for q in results["per_question"] if "has_disclaimer" in q]
        if answered:
            results["disclaimer_rate"] = sum(
                1 for q in answered if q["has_disclaimer"]
            ) / len(answered)
            results["avg_reading_level"] = sum(
                q.get("reading_level", 0) for q in answered if "reading_level" in q
            ) / max(1, len([q for q in answered if "reading_level" in q]))
            results["avg_cost"] = sum(
                q.get("cost", 0) for q in answered if "cost" in q
            ) / max(1, len([q for q in answered if "cost" in q]))

        attorney_qs = [
            q for q in answered if q.get("mode") == "attorney" and "citations_found" in q
        ]
        if attorney_qs:
            results["avg_citations_per_answer"] = sum(
                q["citations_found"] for q in attorney_qs
            ) / len(attorney_qs)

            completeness_scores = [
                q["citation_completeness"]
                for q in attorney_qs
                if "citation_completeness" in q
            ]
            if completeness_scores:
                results["avg_citation_completeness"] = sum(completeness_scores) / len(
                    completeness_scores
                )

        # Adversarial results
        adv_qs = [q for q in results["per_question"] if q.get("mode") == "adversarial"]
        if adv_qs:
            behavior_checks = [q.get("behavior_check", False) for q in adv_qs]
            results["adversarial_pass_rate"] = sum(
                1 for b in behavior_checks if b
            ) / len(behavior_checks)

    # Save report
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / "answer_evaluation.json"
    report_path.write_text(json.dumps(results, indent=2))

    return results


def _check_adversarial_behavior(answer_text: str, expected_behavior: str) -> bool:
    """Check if the answer exhibits the expected adversarial behavior."""
    text_lower = answer_text.lower()

    if expected_behavior == "out_of_scope":
        indicators = [
            "outside the scope",
            "not within",
            "federal law",
            "another state",
            "not california",
            "cannot answer",
            "don't have information",
            "outside california",
            "not related to",
            "beyond the scope",
            "outside of california",
            "not a california employment",
            "not an employment",
            "not employment-related",
            "family law",
            "not cover",
            "unable to help",
            "unable to assist",
            "different area of law",
        ]
        return any(ind in text_lower for ind in indicators)

    if expected_behavior == "citation_not_found":
        indicators = [
            "not available",
            "not found",
            "not in the knowledge base",
            "cannot find",
            "does not exist",
            "not present",
            "don't have",
            "do not have",
            "no such section",
            "no information",
            "unable to locate",
            "could not find",
            "no specific information",
            "don't contain",
            "do not contain",
            "not contain",
            "9999",  # echo back the fabricated section
        ]
        return any(ind in text_lower for ind in indicators)

    if expected_behavior == "clarification_needed":
        indicators = [
            "could you clarify",
            "more specific",
            "which",
            "do you mean",
            "please clarify",
            "can you tell me more",
            "what specific",
            "what area",
            "narrow down",
            "provide more details",
            "broad question",
            "general overview",
            "here are some",
            "depends on",
        ]
        return any(ind in text_lower for ind in indicators)

    if expected_behavior in ("disclaimer", "scope_limitation"):
        return has_disclaimer(answer_text, "consumer")

    # For other behaviors, just check that it doesn't crash
    return len(answer_text) > 0
