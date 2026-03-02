"""Unit tests for the guided intake questionnaire."""

from __future__ import annotations

import pytest

from employee_help.tools.deadlines import ClaimType
from employee_help.tools.intake import (
    DISCLAIMER,
    ISSUE_TO_CLAIM,
    QUESTIONS,
    SCORE_THRESHOLD,
    SIGNAL_MAP,
    AnswerKey,
    IdentifiedIssue,
    IntakeResult,
    evaluate_intake,
    get_questions,
)
from employee_help.tools.routing import ISSUE_TYPE_LABELS, IssueType


# ── Question registry ───────────────────────────────────────────────


def test_at_least_five_questions():
    questions = get_questions()
    assert len(questions) >= 5


def test_unique_question_ids():
    questions = get_questions()
    ids = [q.question_id for q in questions]
    assert len(ids) == len(set(ids))


def test_all_questions_have_at_least_two_options():
    for q in get_questions():
        assert len(q.options) >= 2, f"Question {q.question_id} has < 2 options"


def test_all_option_keys_are_valid_answer_keys():
    for q in get_questions():
        for opt in q.options:
            assert isinstance(opt.key, AnswerKey), f"{opt.key} is not AnswerKey"


def test_all_answer_keys_used_in_some_question():
    """Every AnswerKey value appears in at least one question option."""
    used_keys: set[AnswerKey] = set()
    for q in get_questions():
        for opt in q.options:
            used_keys.add(opt.key)
    for key in AnswerKey:
        assert key in used_keys, f"AnswerKey {key} is unused"


def test_show_if_references_valid_answer_keys():
    for q in get_questions():
        if q.show_if is not None:
            for key in q.show_if:
                assert isinstance(key, AnswerKey), f"show_if {key} is not AnswerKey"


# ── Signal map ──────────────────────────────────────────────────────


def test_signal_map_covers_all_answer_keys():
    for key in AnswerKey:
        assert key in SIGNAL_MAP, f"AnswerKey {key} missing from SIGNAL_MAP"


def test_signal_map_covers_all_issue_types():
    """Every IssueType is reachable from at least one answer."""
    reachable: set[IssueType] = set()
    for signals in SIGNAL_MAP.values():
        reachable.update(signals.keys())
    for it in IssueType:
        assert it in reachable, f"IssueType {it} unreachable from SIGNAL_MAP"


def test_all_weights_positive():
    for key, signals in SIGNAL_MAP.items():
        for issue_type, weight in signals.items():
            assert weight > 0, f"SIGNAL_MAP[{key}][{issue_type}] = {weight} <= 0"


# ── ISSUE_TO_CLAIM ──────────────────────────────────────────────────


def test_issue_to_claim_covers_all_issue_types():
    for it in IssueType:
        assert it in ISSUE_TO_CLAIM, f"IssueType {it} missing from ISSUE_TO_CLAIM"


def test_issue_to_claim_values_are_valid_claim_types():
    valid_values = {ct.value for ct in ClaimType}
    for it, claim_list in ISSUE_TO_CLAIM.items():
        for claim_val in claim_list:
            assert claim_val in valid_values, (
                f"ISSUE_TO_CLAIM[{it}] contains invalid claim type: {claim_val}"
            )


# ── Tool recommendations ───────────────────────────────────────────


def test_all_issue_types_have_tool_recommendations():
    """Every IssueType produces at least one tool recommendation."""
    from employee_help.tools.intake import _build_tool_recommendations

    for it in IssueType:
        tools = _build_tool_recommendations(it)
        assert len(tools) >= 1, f"IssueType {it} has no tool recommendations"


def test_tool_paths_start_with_tools():
    from employee_help.tools.intake import _build_tool_recommendations

    for it in IssueType:
        for tool in _build_tool_recommendations(it):
            assert tool.tool_path.startswith("/tools/"), (
                f"Tool path {tool.tool_path} doesn't start with /tools/"
            )


# ── Parametrized scoring scenarios ──────────────────────────────────


@pytest.mark.parametrize(
    "answers, expected_issue",
    [
        # Pure unpaid wages
        (["not_paid", "pay_not_received", "retaliation_no", "status_still_employed", "employer_private", "need_none"], IssueType.unpaid_wages),
        # Discrimination
        (["treated_unfairly", "unfair_protected_class", "retaliation_no", "status_still_employed", "employer_private", "need_none"], IssueType.discrimination),
        # Harassment
        (["treated_unfairly", "unfair_hostile_env", "retaliation_no", "status_still_employed", "employer_private", "need_none"], IssueType.harassment),
        # Wrongful termination + retaliation
        (["fired_laid_off", "retaliation_yes", "reported_legal_violation", "status_terminated", "employer_private", "need_none"], IssueType.wrongful_termination),
        # Misclassification
        (["not_paid", "pay_misclassified", "retaliation_no", "status_still_employed", "employer_private", "need_none"], IssueType.misclassification),
        # Meal/rest breaks
        (["not_paid", "pay_breaks_denied", "retaliation_no", "status_still_employed", "employer_private", "need_none"], IssueType.meal_rest_breaks),
        # Workplace safety
        (["unsafe_conditions", "retaliation_no", "status_still_employed", "employer_private", "need_none"], IssueType.workplace_safety),
        # Whistleblower + retaliation
        (["reported_problem", "retaliation_yes", "reported_safety", "status_still_employed", "employer_private", "need_none"], IssueType.whistleblower),
        # EDD unemployment
        (["benefits_issue", "retaliation_no", "status_terminated", "employer_private", "need_unemployment"], IssueType.unemployment_benefits),
        # Family medical leave
        (["treated_unfairly", "unfair_leave_denied", "retaliation_no", "status_still_employed", "employer_private", "need_family_leave"], IssueType.family_medical_leave),
    ],
    ids=[
        "unpaid_wages",
        "discrimination",
        "harassment",
        "wrongful_termination",
        "misclassification",
        "meal_rest_breaks",
        "workplace_safety",
        "whistleblower",
        "unemployment_benefits",
        "family_medical_leave",
    ],
)
def test_scoring_scenario(answers: list[str], expected_issue: IssueType):
    result = evaluate_intake(answers)
    issue_types = [i.issue_type for i in result.identified_issues]
    assert expected_issue in issue_types, (
        f"Expected {expected_issue} in results but got {issue_types}"
    )


# ── Government employee detection ──────────────────────────────────


def test_government_employee_detected():
    result = evaluate_intake([
        "not_paid", "pay_not_received",
        "retaliation_no", "status_still_employed",
        "employer_government", "need_none",
    ])
    assert result.is_government_employee is True


def test_government_employee_adds_claim_type():
    result = evaluate_intake([
        "not_paid", "pay_not_received",
        "retaliation_no", "status_still_employed",
        "employer_government", "need_none",
    ])
    assert result.is_government_employee is True
    # Find the unpaid_wages issue
    wages_issue = next(
        (i for i in result.identified_issues if i.issue_type == IssueType.unpaid_wages),
        None,
    )
    assert wages_issue is not None
    assert "government_employee" in wages_issue.related_claim_types


def test_private_employer_not_government():
    result = evaluate_intake([
        "not_paid", "pay_not_received",
        "retaliation_no", "status_still_employed",
        "employer_private", "need_none",
    ])
    assert result.is_government_employee is False


# ── Employment status detection ─────────────────────────────────────


def test_employment_status_terminated():
    result = evaluate_intake([
        "fired_laid_off", "retaliation_no",
        "status_terminated", "employer_private", "need_none",
    ])
    assert result.employment_status == "terminated"


def test_employment_status_still_employed():
    result = evaluate_intake([
        "not_paid", "pay_not_received",
        "retaliation_no", "status_still_employed",
        "employer_private", "need_none",
    ])
    assert result.employment_status == "still_employed"


def test_employment_status_quit():
    result = evaluate_intake([
        "not_paid", "pay_not_received",
        "retaliation_no", "status_quit",
        "employer_private", "need_none",
    ])
    assert result.employment_status == "quit"


# ── Result structure ────────────────────────────────────────────────


def test_result_summary_non_empty():
    result = evaluate_intake([
        "not_paid", "pay_not_received",
        "retaliation_no", "status_still_employed",
        "employer_private", "need_none",
    ])
    assert isinstance(result.summary, str)
    assert len(result.summary) > 0


def test_result_is_intake_result():
    result = evaluate_intake([
        "not_paid", "pay_not_received",
        "retaliation_no", "status_still_employed",
        "employer_private", "need_none",
    ])
    assert isinstance(result, IntakeResult)
    for issue in result.identified_issues:
        assert isinstance(issue, IdentifiedIssue)


# ── Disclaimer ──────────────────────────────────────────────────────


def test_disclaimer_has_key_phrases():
    assert "not legal advice" in DISCLAIMER.lower()
    assert "attorney" in DISCLAIMER.lower()


# ── Edge cases ──────────────────────────────────────────────────────


def test_invalid_answer_key_raises():
    with pytest.raises(ValueError, match="Invalid answer key"):
        evaluate_intake(["not_a_real_key"])


def test_all_na_answers_produce_no_issues():
    result = evaluate_intake([
        "pay_na", "unfair_na", "retaliation_no",
        "status_still_employed", "employer_private", "need_none",
    ])
    assert len(result.identified_issues) == 0


def test_high_confidence_threshold():
    """Issues scoring >= 1.5 should have 'high' confidence."""
    result = evaluate_intake([
        "not_paid", "pay_not_received",
        "retaliation_no", "status_still_employed",
        "employer_private", "need_none",
    ])
    wages_issue = next(
        (i for i in result.identified_issues if i.issue_type == IssueType.unpaid_wages),
        None,
    )
    assert wages_issue is not None
    # not_paid (1.0) + pay_not_received (1.0) = 2.0 >= 1.5
    assert wages_issue.confidence == "high"


def test_medium_confidence_threshold():
    """Issues scoring >= 0.8 but < 1.5 should have 'medium' confidence."""
    result = evaluate_intake([
        "not_paid", "pay_na",
        "retaliation_no", "status_still_employed",
        "employer_private", "need_none",
    ])
    wages_issue = next(
        (i for i in result.identified_issues if i.issue_type == IssueType.unpaid_wages),
        None,
    )
    assert wages_issue is not None
    # not_paid (1.0) + pay_na (0) = 1.0 → medium
    assert wages_issue.confidence == "medium"
