#!/usr/bin/env python3
"""
Comprehensive validation test runner for Employee Help API.

Sends questions to the live API (localhost:8000), captures responses via SSE,
and evaluates answer quality, timing, sources, and consistency.

Usage:
    python tests/evaluation/validation_runner.py [--mode consumer|attorney|both] [--limit N] [--output DIR]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import statistics
import sys
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx
import yaml


BASE_URL = "http://127.0.0.1:8000"
API_ENDPOINT = f"{BASE_URL}/api/ask"
HEALTH_ENDPOINT = f"{BASE_URL}/api/health"

# Timeouts
CONNECT_TIMEOUT = 10.0
RESPONSE_TIMEOUT = 60.0  # Attorney mode can take 35+ seconds; allow buffer over 45s server timeout


@dataclass
class SSEResult:
    """Parsed SSE response from the API."""

    sources: list[dict] = field(default_factory=list)
    answer: str = ""
    metadata: dict = field(default_factory=dict)
    error: str | None = None
    time_to_first_token_ms: int = 0
    total_duration_ms: int = 0
    raw_events: list[dict] = field(default_factory=list)


@dataclass
class TestResult:
    """Result of a single test question."""

    question_id: str
    question: str
    mode: str
    category: str
    sse_result: SSEResult
    # Validation checks
    has_answer: bool = False
    answer_length: int = 0
    source_count: int = 0
    expected_elements_found: list[str] = field(default_factory=list)
    expected_elements_missing: list[str] = field(default_factory=list)
    expected_categories_found: list[str] = field(default_factory=list)
    expected_categories_missing: list[str] = field(default_factory=list)
    has_correct_format: bool = False
    format_sections_found: list[str] = field(default_factory=list)
    format_sections_missing: list[str] = field(default_factory=list)
    # Timing
    time_to_first_token_ms: int = 0
    total_duration_ms: int = 0
    server_duration_ms: int = 0
    # Cost
    input_tokens: int = 0
    output_tokens: int = 0
    cost_estimate: float = 0.0
    # Error
    error: str | None = None
    # Additional checks
    mentions_disclaimer: bool = False
    mentions_sources_or_agencies: bool = False
    is_on_topic: bool = False


@dataclass
class ConversationTestResult:
    """Result of a multi-turn conversation test."""

    test_name: str
    mode: str
    turns: list[TestResult] = field(default_factory=list)
    session_id: str = ""
    reached_limit: bool = False
    limit_enforced: bool = False
    error: str | None = None


def send_question(
    query: str,
    mode: str = "consumer",
    session_id: str | None = None,
    conversation_history: list[dict] | None = None,
    turn_number: int = 1,
) -> SSEResult:
    """Send a question to the API and parse SSE response."""
    result = SSEResult()
    start_time = time.monotonic()
    first_token_time = None

    body: dict[str, Any] = {"query": query, "mode": mode}
    if session_id:
        body["session_id"] = session_id
    if conversation_history:
        body["conversation_history"] = conversation_history
    if turn_number > 1:
        body["turn_number"] = turn_number

    try:
        with httpx.stream(
            "POST",
            API_ENDPOINT,
            json=body,
            timeout=httpx.Timeout(CONNECT_TIMEOUT, read=RESPONSE_TIMEOUT),
        ) as response:
            if response.status_code != 200:
                body = response.read().decode()
                result.error = f"HTTP {response.status_code}: {body[:200]}"
                return result

            buffer = ""
            for chunk in response.iter_text():
                buffer += chunk
                lines = buffer.split("\n")
                buffer = lines.pop()

                event_type = ""
                data_lines = []

                for line in lines:
                    if line.startswith("event: "):
                        event_type = line[7:].strip()
                    elif line.startswith("data: "):
                        data_lines.append(line[6:])
                    elif line == "" and event_type and data_lines:
                        data_str = "\n".join(data_lines)
                        try:
                            data = json.loads(data_str)
                            result.raw_events.append(
                                {"event": event_type, "data": data}
                            )

                            if event_type == "sources":
                                result.sources = data.get("sources", [])
                            elif event_type == "token":
                                if first_token_time is None:
                                    first_token_time = time.monotonic()
                                result.answer += data.get("text", "")
                            elif event_type == "done":
                                result.metadata = data
                            elif event_type == "error":
                                result.error = data.get("message", "Unknown error")
                        except json.JSONDecodeError:
                            pass

                        event_type = ""
                        data_lines = []

    except httpx.TimeoutException:
        result.error = "Request timed out"
    except httpx.ConnectError:
        result.error = "Could not connect to API"
    except Exception as e:
        result.error = f"Unexpected error: {e}"

    end_time = time.monotonic()
    result.total_duration_ms = int((end_time - start_time) * 1000)
    if first_token_time:
        result.time_to_first_token_ms = int((first_token_time - start_time) * 1000)

    return result


def validate_answer(
    sse_result: SSEResult,
    question: dict,
    mode: str,
) -> TestResult:
    """Validate an SSE result against expected criteria."""
    q_text = question.get("question") or question.get("query", "")
    category = question.get("category", "unknown")
    q_id = hashlib.sha256(q_text.encode()).hexdigest()[:12]

    result = TestResult(
        question_id=q_id,
        question=q_text,
        mode=mode,
        category=category,
        sse_result=sse_result,
    )

    if sse_result.error:
        result.error = sse_result.error
        return result

    answer = sse_result.answer
    result.has_answer = len(answer.strip()) > 50
    result.answer_length = len(answer)
    result.source_count = len(sse_result.sources)
    result.time_to_first_token_ms = sse_result.time_to_first_token_ms
    result.total_duration_ms = sse_result.total_duration_ms
    result.server_duration_ms = sse_result.metadata.get("duration_ms", 0)
    result.input_tokens = sse_result.metadata.get("input_tokens", 0)
    result.output_tokens = sse_result.metadata.get("output_tokens", 0)
    result.cost_estimate = sse_result.metadata.get("cost_estimate", 0.0)

    # Check expected elements in answer
    answer_lower = answer.lower()
    for element in question.get("expected_elements", []):
        if element.lower() in answer_lower:
            result.expected_elements_found.append(element)
        else:
            result.expected_elements_missing.append(element)

    # Check expected source categories
    source_cats = {s.get("content_category", "") for s in sse_result.sources}
    for cat in question.get("expected_categories", []):
        if cat in source_cats:
            result.expected_categories_found.append(cat)
        else:
            result.expected_categories_missing.append(cat)

    # Check response format
    if mode == "consumer":
        expected_sections = ["Short Answer", "What You Should Know", "Next Steps"]
    else:
        expected_sections = ["tl;dr", "Short Answer", "Analysis"]

    for section in expected_sections:
        # Check for bold heading format: **Section:**
        pattern = rf"\*\*{re.escape(section)}"
        if re.search(pattern, answer, re.IGNORECASE):
            result.format_sections_found.append(section)
        else:
            result.format_sections_missing.append(section)

    result.has_correct_format = len(result.format_sections_missing) == 0

    # Check for disclaimer language
    disclaimer_phrases = [
        "consult an attorney",
        "consult a lawyer",
        "legal advice",
        "not legal advice",
        "speak with an attorney",
        "speak with a lawyer",
        "contact an attorney",
        "qualified attorney",
        "legal professional",
        "specific legal advice",
    ]
    result.mentions_disclaimer = any(
        phrase in answer_lower for phrase in disclaimer_phrases
    )

    # Check for source/agency references
    agency_phrases = [
        "labor commissioner",
        "civil rights department",
        "crd",
        "dir",
        "edd",
        "cal/osha",
        "eeoc",
        "dlse",
        "department of industrial relations",
        "employment development department",
        "department of fair employment",
        "labor code",
        "government code",
        "gov. code",
        "lab. code",
        "cal. lab. code",
        "cal. gov. code",
    ]
    result.mentions_sources_or_agencies = any(
        phrase in answer_lower for phrase in agency_phrases
    )

    # Basic on-topic check: answer should reference key terms from the question
    question_lower = q_text.lower()
    topic_keywords = question.get("topic_keywords", [])
    if topic_keywords:
        topics_found = sum(1 for kw in topic_keywords if kw.lower() in answer_lower)
        result.is_on_topic = topics_found >= len(topic_keywords) // 2
    else:
        # Fallback: check if answer mentions at least some question words
        q_words = set(
            w
            for w in question_lower.split()
            if len(w) > 4 and w not in {"about", "would", "could", "should", "their", "there", "where", "which", "these", "those"}
        )
        matched = sum(1 for w in q_words if w in answer_lower)
        result.is_on_topic = matched >= min(2, len(q_words))

    return result


def run_conversation_test(
    test_config: dict,
    mode: str,
) -> ConversationTestResult:
    """Run a multi-turn conversation test."""
    test_name = test_config["name"]
    turns_config = test_config["turns"]

    conv_result = ConversationTestResult(
        test_name=test_name,
        mode=mode,
        session_id=str(uuid.uuid4()),
    )

    conversation_history: list[dict] = []

    for i, turn_config in enumerate(turns_config):
        turn_number = i + 1
        query = turn_config["query"]

        sse_result = send_question(
            query=query,
            mode=mode,
            session_id=conv_result.session_id,
            conversation_history=conversation_history if turn_number > 1 else None,
            turn_number=turn_number,
        )

        test_result = validate_answer(sse_result, turn_config, mode)
        conv_result.turns.append(test_result)

        if sse_result.error:
            if "TURN_LIMIT_EXCEEDED" in (sse_result.error or ""):
                conv_result.reached_limit = True
                conv_result.limit_enforced = True
            else:
                conv_result.error = sse_result.error
            break

        # Check if this was the final turn
        if sse_result.metadata.get("is_final_turn"):
            conv_result.reached_limit = True

        # Build history for next turn
        conversation_history.append({"role": "user", "content": query})
        conversation_history.append({"role": "assistant", "content": sse_result.answer})

    return conv_result


def load_test_questions(filepath: str) -> list[dict]:
    """Load test questions from a YAML file."""
    with open(filepath) as f:
        data = yaml.safe_load(f)
    return data.get("questions", [])


def load_conversation_tests(filepath: str) -> list[dict]:
    """Load conversation test scenarios from a YAML file."""
    with open(filepath) as f:
        data = yaml.safe_load(f)
    return data.get("conversations", [])


def check_api_health() -> bool:
    """Check if the API is healthy."""
    try:
        resp = httpx.get(HEALTH_ENDPOINT, timeout=5.0)
        data = resp.json()
        return data.get("status") == "ok" and data.get("embedding_model_loaded", False)
    except Exception:
        return False


def generate_report(
    consumer_results: list[TestResult],
    attorney_results: list[TestResult],
    conversation_results: list[ConversationTestResult],
    output_dir: Path,
) -> str:
    """Generate a comprehensive markdown report from test results."""

    def stats_for(results: list[TestResult]) -> dict:
        if not results:
            return {}

        successful = [r for r in results if not r.error]
        errors = [r for r in results if r.error]

        # Timing
        durations = [r.total_duration_ms for r in successful]
        ttft = [r.time_to_first_token_ms for r in successful if r.time_to_first_token_ms > 0]
        server_durations = [r.server_duration_ms for r in successful if r.server_duration_ms > 0]

        # Quality
        with_answer = [r for r in successful if r.has_answer]
        with_format = [r for r in successful if r.has_correct_format]
        with_disclaimer = [r for r in successful if r.mentions_disclaimer]
        with_sources = [r for r in successful if r.mentions_sources_or_agencies]
        on_topic = [r for r in successful if r.is_on_topic]

        # Element coverage
        total_expected = sum(
            len(r.expected_elements_found) + len(r.expected_elements_missing)
            for r in successful
        )
        total_found = sum(len(r.expected_elements_found) for r in successful)
        element_coverage = total_found / total_expected if total_expected > 0 else 0

        # Category coverage
        total_cat_expected = sum(
            len(r.expected_categories_found) + len(r.expected_categories_missing)
            for r in successful
        )
        total_cat_found = sum(len(r.expected_categories_found) for r in successful)
        cat_coverage = total_cat_found / total_cat_expected if total_cat_expected > 0 else 0

        # Tokens & cost
        costs = [r.cost_estimate for r in successful if r.cost_estimate > 0]
        input_tokens = [r.input_tokens for r in successful if r.input_tokens > 0]
        output_tokens = [r.output_tokens for r in successful if r.output_tokens > 0]

        return {
            "total": len(results),
            "successful": len(successful),
            "errors": len(errors),
            "error_rate": f"{len(errors) / len(results) * 100:.1f}%",
            "answer_rate": f"{len(with_answer) / len(successful) * 100:.1f}%" if successful else "N/A",
            "format_compliance": f"{len(with_format) / len(successful) * 100:.1f}%" if successful else "N/A",
            "disclaimer_rate": f"{len(with_disclaimer) / len(successful) * 100:.1f}%" if successful else "N/A",
            "source_reference_rate": f"{len(with_sources) / len(successful) * 100:.1f}%" if successful else "N/A",
            "on_topic_rate": f"{len(on_topic) / len(successful) * 100:.1f}%" if successful else "N/A",
            "element_coverage": f"{element_coverage * 100:.1f}%",
            "category_coverage": f"{cat_coverage * 100:.1f}%",
            "avg_duration_ms": int(statistics.mean(durations)) if durations else 0,
            "median_duration_ms": int(statistics.median(durations)) if durations else 0,
            "p95_duration_ms": int(sorted(durations)[int(len(durations) * 0.95)]) if durations else 0,
            "avg_ttft_ms": int(statistics.mean(ttft)) if ttft else 0,
            "avg_server_duration_ms": int(statistics.mean(server_durations)) if server_durations else 0,
            "avg_answer_length": int(statistics.mean([r.answer_length for r in successful])) if successful else 0,
            "avg_source_count": round(statistics.mean([r.source_count for r in successful]), 1) if successful else 0,
            "avg_cost": round(statistics.mean(costs), 6) if costs else 0,
            "total_cost": round(sum(costs), 4) if costs else 0,
            "avg_input_tokens": int(statistics.mean(input_tokens)) if input_tokens else 0,
            "avg_output_tokens": int(statistics.mean(output_tokens)) if output_tokens else 0,
        }

    def category_breakdown(results: list[TestResult]) -> dict[str, dict]:
        categories: dict[str, list[TestResult]] = {}
        for r in results:
            categories.setdefault(r.category, []).append(r)

        breakdown = {}
        for cat, cat_results in sorted(categories.items()):
            successful = [r for r in cat_results if not r.error]
            with_answer = [r for r in successful if r.has_answer]
            total_elements = sum(
                len(r.expected_elements_found) + len(r.expected_elements_missing)
                for r in successful
            )
            found_elements = sum(len(r.expected_elements_found) for r in successful)

            breakdown[cat] = {
                "count": len(cat_results),
                "success": len(successful),
                "answer_rate": f"{len(with_answer) / len(successful) * 100:.0f}%" if successful else "N/A",
                "element_coverage": f"{found_elements / total_elements * 100:.0f}%" if total_elements else "N/A",
                "avg_duration_ms": int(statistics.mean([r.total_duration_ms for r in successful])) if successful else 0,
            }
        return breakdown

    # Build report
    lines = []
    lines.append("# Employee Help Validation Test Report")
    lines.append(f"\nGenerated: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"API: {BASE_URL}")
    lines.append("")

    # Executive summary
    lines.append("## Executive Summary\n")

    for mode, results in [("Consumer", consumer_results), ("Attorney", attorney_results)]:
        if not results:
            continue
        s = stats_for(results)
        lines.append(f"### {mode} Mode\n")
        lines.append(f"| Metric | Value |")
        lines.append(f"|--------|-------|")
        lines.append(f"| Questions tested | {s['total']} |")
        lines.append(f"| Successful | {s['successful']} ({100 - float(s['error_rate'].rstrip('%')):.0f}%) |")
        lines.append(f"| Errors | {s['errors']} ({s['error_rate']}) |")
        lines.append(f"| Answer rate | {s['answer_rate']} |")
        lines.append(f"| Format compliance | {s['format_compliance']} |")
        lines.append(f"| On-topic rate | {s['on_topic_rate']} |")
        lines.append(f"| Element coverage | {s['element_coverage']} |")
        lines.append(f"| Source category match | {s['category_coverage']} |")
        lines.append(f"| Disclaimer rate | {s['disclaimer_rate']} |")
        lines.append(f"| Source/agency references | {s['source_reference_rate']} |")
        lines.append(f"| Avg response time | {s['avg_duration_ms']}ms |")
        lines.append(f"| Median response time | {s['median_duration_ms']}ms |")
        lines.append(f"| P95 response time | {s['p95_duration_ms']}ms |")
        lines.append(f"| Avg time to first token | {s['avg_ttft_ms']}ms |")
        lines.append(f"| Avg answer length | {s['avg_answer_length']} chars |")
        lines.append(f"| Avg sources per answer | {s['avg_source_count']} |")
        lines.append(f"| Avg cost per query | ${s['avg_cost']:.4f} |")
        lines.append(f"| Total test cost | ${s['total_cost']:.4f} |")
        lines.append(f"| Avg input tokens | {s['avg_input_tokens']} |")
        lines.append(f"| Avg output tokens | {s['avg_output_tokens']} |")
        lines.append("")

    # Category breakdown
    lines.append("## Category Breakdown\n")

    for mode, results in [("Consumer", consumer_results), ("Attorney", attorney_results)]:
        if not results:
            continue
        lines.append(f"### {mode} Mode\n")
        breakdown = category_breakdown(results)
        lines.append("| Category | Qs | Success | Answer Rate | Element Coverage | Avg Time |")
        lines.append("|----------|----|---------|----|---------|----------|")
        for cat, info in breakdown.items():
            lines.append(
                f"| {cat} | {info['count']} | {info['success']} | "
                f"{info['answer_rate']} | {info['element_coverage']} | {info['avg_duration_ms']}ms |"
            )
        lines.append("")

    # Conversation tests
    if conversation_results:
        lines.append("## Multi-Turn Conversation Tests\n")
        for conv in conversation_results:
            status = "PASS" if not conv.error else f"FAIL: {conv.error}"
            lines.append(f"### {conv.test_name} ({conv.mode})\n")
            lines.append(f"- **Status**: {status}")
            lines.append(f"- **Turns completed**: {len(conv.turns)}")
            lines.append(f"- **Turn limit reached**: {conv.reached_limit}")
            lines.append(f"- **Turn limit enforced**: {conv.limit_enforced}")
            if conv.turns:
                total_time = sum(t.total_duration_ms for t in conv.turns)
                total_cost = sum(t.cost_estimate for t in conv.turns)
                lines.append(f"- **Total time**: {total_time}ms")
                lines.append(f"- **Total cost**: ${total_cost:.4f}")
                lines.append("")
                for i, turn in enumerate(conv.turns):
                    q_short = turn.question[:80] + "..." if len(turn.question) > 80 else turn.question
                    lines.append(f"  Turn {i + 1}: \"{q_short}\"")
                    lines.append(f"    - Duration: {turn.total_duration_ms}ms | Tokens: {turn.input_tokens}→{turn.output_tokens}")
                    lines.append(f"    - Format OK: {turn.has_correct_format} | On-topic: {turn.is_on_topic}")
                    if turn.error:
                        lines.append(f"    - Error: {turn.error}")
            lines.append("")

    # Failures and issues
    lines.append("## Issues Found\n")

    all_results = consumer_results + attorney_results
    errors = [r for r in all_results if r.error]
    no_answer = [r for r in all_results if not r.error and not r.has_answer]
    bad_format = [r for r in all_results if not r.error and r.has_answer and not r.has_correct_format]
    off_topic = [r for r in all_results if not r.error and r.has_answer and not r.is_on_topic]
    missing_elements = [r for r in all_results if r.expected_elements_missing]
    slow = [r for r in all_results if r.total_duration_ms > 30000]

    if errors:
        lines.append(f"### Errors ({len(errors)})\n")
        for r in errors:
            lines.append(f"- [{r.mode}] \"{r.question[:60]}...\" → {r.error}")
        lines.append("")

    if no_answer:
        lines.append(f"### No Answer / Too Short ({len(no_answer)})\n")
        for r in no_answer:
            lines.append(f"- [{r.mode}] \"{r.question[:60]}...\" (length: {r.answer_length})")
        lines.append("")

    if bad_format:
        lines.append(f"### Format Non-Compliance ({len(bad_format)})\n")
        for r in bad_format[:20]:
            lines.append(f"- [{r.mode}] \"{r.question[:60]}...\" — missing: {r.format_sections_missing}")
        lines.append("")

    if off_topic:
        lines.append(f"### Potentially Off-Topic ({len(off_topic)})\n")
        for r in off_topic[:20]:
            lines.append(f"- [{r.mode}] \"{r.question[:60]}...\"")
        lines.append("")

    if missing_elements:
        lines.append(f"### Missing Expected Elements ({len(missing_elements)})\n")
        for r in sorted(missing_elements, key=lambda x: len(x.expected_elements_missing), reverse=True)[:20]:
            lines.append(f"- [{r.mode}/{r.category}] \"{r.question[:50]}...\" — missing: {r.expected_elements_missing}")
        lines.append("")

    if slow:
        lines.append(f"### Slow Responses >30s ({len(slow)})\n")
        for r in sorted(slow, key=lambda x: x.total_duration_ms, reverse=True)[:10]:
            lines.append(f"- [{r.mode}] \"{r.question[:60]}...\" — {r.total_duration_ms}ms")
        lines.append("")

    report = "\n".join(lines)
    return report


def run_single_turn_tests(
    questions: list[dict],
    mode: str,
    limit: int | None = None,
) -> list[TestResult]:
    """Run single-turn tests for a set of questions."""
    results = []
    total = min(len(questions), limit) if limit else len(questions)

    for i, q in enumerate(questions[:total]):
        q_text = q["question"]
        category = q.get("category", "unknown")
        q_short = q_text[:60] + "..." if len(q_text) > 60 else q_text
        print(f"  [{i + 1}/{total}] [{category}] {q_short}", end="", flush=True)

        sse_result = send_question(query=q_text, mode=mode)
        test_result = validate_answer(sse_result, q, mode)
        results.append(test_result)

        status = "OK" if not test_result.error else f"ERR: {test_result.error[:30]}"
        duration = test_result.total_duration_ms
        print(f" → {status} ({duration}ms)")

    return results


def run_conversation_tests(
    scenarios: list[dict],
    mode: str,
) -> list[ConversationTestResult]:
    """Run multi-turn conversation tests."""
    results = []

    for scenario in scenarios:
        name = scenario["name"]
        print(f"  Conversation: {name}", flush=True)

        conv_result = run_conversation_test(scenario, mode)
        results.append(conv_result)

        turns = len(conv_result.turns)
        status = "OK" if not conv_result.error else f"ERR: {conv_result.error[:30]}"
        print(f"    → {turns} turns | {status}")

    return results


def main():
    parser = argparse.ArgumentParser(description="Employee Help Validation Runner")
    parser.add_argument(
        "--mode",
        choices=["consumer", "attorney", "both"],
        default="both",
        help="Which mode to test",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Max questions per mode (for quick tests)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="data/validation",
        help="Output directory for reports",
    )
    parser.add_argument(
        "--skip-conversations",
        action="store_true",
        help="Skip multi-turn conversation tests",
    )
    parser.add_argument(
        "--questions-dir",
        type=str,
        default="tests/evaluation",
        help="Directory containing question YAML files",
    )
    args = parser.parse_args()

    # Check API health
    print("Checking API health...", end=" ")
    if not check_api_health():
        print("FAILED - API not responding or not healthy")
        print(f"Make sure the backend is running: uv run uvicorn employee_help.api.main:app --port 8000")
        sys.exit(1)
    print("OK")

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    questions_dir = Path(args.questions_dir)

    consumer_results: list[TestResult] = []
    attorney_results: list[TestResult] = []
    conversation_results: list[ConversationTestResult] = []

    start_time = time.monotonic()

    # Consumer tests
    if args.mode in ("consumer", "both"):
        consumer_file = questions_dir / "consumer_validation.yaml"
        if consumer_file.exists():
            print(f"\n{'=' * 60}")
            print(f"CONSUMER MODE TESTS")
            print(f"{'=' * 60}")
            questions = load_test_questions(str(consumer_file))
            print(f"Loaded {len(questions)} consumer questions")
            consumer_results = run_single_turn_tests(questions, "consumer", args.limit)

            if not args.skip_conversations:
                conv_file = questions_dir / "consumer_conversations.yaml"
                if conv_file.exists():
                    print(f"\nConversation tests:")
                    scenarios = load_conversation_tests(str(conv_file))
                    conversation_results.extend(
                        run_conversation_tests(scenarios, "consumer")
                    )
        else:
            print(f"Warning: {consumer_file} not found, skipping consumer tests")

    # Attorney tests
    if args.mode in ("attorney", "both"):
        attorney_file = questions_dir / "attorney_validation.yaml"
        if attorney_file.exists():
            print(f"\n{'=' * 60}")
            print(f"ATTORNEY MODE TESTS")
            print(f"{'=' * 60}")
            questions = load_test_questions(str(attorney_file))
            print(f"Loaded {len(questions)} attorney questions")
            attorney_results = run_single_turn_tests(questions, "attorney", args.limit)

            if not args.skip_conversations:
                conv_file = questions_dir / "attorney_conversations.yaml"
                if conv_file.exists():
                    print(f"\nConversation tests:")
                    scenarios = load_conversation_tests(str(conv_file))
                    conversation_results.extend(
                        run_conversation_tests(scenarios, "attorney")
                    )
        else:
            print(f"Warning: {attorney_file} not found, skipping attorney tests")

    total_time = time.monotonic() - start_time
    print(f"\n{'=' * 60}")
    print(f"Tests completed in {total_time:.1f}s")
    print(f"{'=' * 60}")

    # Generate report
    report = generate_report(
        consumer_results, attorney_results, conversation_results, output_dir
    )

    report_path = output_dir / "validation_report.md"
    report_path.write_text(report)
    print(f"\nReport saved to: {report_path}")

    # Save raw results as JSON for further analysis
    raw_data = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "total_duration_s": round(total_time, 1),
        "consumer": [
            {
                "question": r.question,
                "category": r.category,
                "has_answer": r.has_answer,
                "answer_length": r.answer_length,
                "has_correct_format": r.has_correct_format,
                "format_sections_found": r.format_sections_found,
                "format_sections_missing": r.format_sections_missing,
                "is_on_topic": r.is_on_topic,
                "mentions_disclaimer": r.mentions_disclaimer,
                "mentions_sources_or_agencies": r.mentions_sources_or_agencies,
                "expected_elements_found": r.expected_elements_found,
                "expected_elements_missing": r.expected_elements_missing,
                "expected_categories_found": r.expected_categories_found,
                "expected_categories_missing": r.expected_categories_missing,
                "source_count": r.source_count,
                "total_duration_ms": r.total_duration_ms,
                "time_to_first_token_ms": r.time_to_first_token_ms,
                "server_duration_ms": r.server_duration_ms,
                "input_tokens": r.input_tokens,
                "output_tokens": r.output_tokens,
                "cost_estimate": r.cost_estimate,
                "error": r.error,
            }
            for r in consumer_results
        ],
        "attorney": [
            {
                "question": r.question,
                "category": r.category,
                "has_answer": r.has_answer,
                "answer_length": r.answer_length,
                "has_correct_format": r.has_correct_format,
                "format_sections_found": r.format_sections_found,
                "format_sections_missing": r.format_sections_missing,
                "is_on_topic": r.is_on_topic,
                "mentions_disclaimer": r.mentions_disclaimer,
                "mentions_sources_or_agencies": r.mentions_sources_or_agencies,
                "expected_elements_found": r.expected_elements_found,
                "expected_elements_missing": r.expected_elements_missing,
                "expected_categories_found": r.expected_categories_found,
                "expected_categories_missing": r.expected_categories_missing,
                "source_count": r.source_count,
                "total_duration_ms": r.total_duration_ms,
                "time_to_first_token_ms": r.time_to_first_token_ms,
                "server_duration_ms": r.server_duration_ms,
                "input_tokens": r.input_tokens,
                "output_tokens": r.output_tokens,
                "cost_estimate": r.cost_estimate,
                "error": r.error,
            }
            for r in attorney_results
        ],
        "conversations": [
            {
                "test_name": c.test_name,
                "mode": c.mode,
                "turns": len(c.turns),
                "reached_limit": c.reached_limit,
                "limit_enforced": c.limit_enforced,
                "error": c.error,
                "turn_details": [
                    {
                        "question": t.question,
                        "duration_ms": t.total_duration_ms,
                        "has_answer": t.has_answer,
                        "has_correct_format": t.has_correct_format,
                        "error": t.error,
                    }
                    for t in c.turns
                ],
            }
            for c in conversation_results
        ],
    }

    json_path = output_dir / "validation_results.json"
    json_path.write_text(json.dumps(raw_data, indent=2))
    print(f"Raw data saved to: {json_path}")

    # Print quick summary
    all_results = consumer_results + attorney_results
    if all_results:
        total = len(all_results)
        errors = sum(1 for r in all_results if r.error)
        print(f"\nQuick Summary: {total} questions, {errors} errors, "
              f"{total - errors} successful")


if __name__ == "__main__":
    main()
