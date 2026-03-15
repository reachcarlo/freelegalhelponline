"""Cross-cutting tests for P2.1-P2.4 — P2.5 gate.

These tests exercise the full obfuscation stack (Engine + Recognizer + Context)
together, covering scenarios that span multiple modules:

- Engine round-trip WITH NER (mocked)
- Full pipeline: CaseContext seed + regex scan + NER scan → obfuscate → deobfuscate
- Date/dollar preservation through the engine pipeline
- Multi-turn rebuild determinism through the engine
- Realistic LLM response deobfuscation patterns
- Edge cases: unicode names, overlapping entities, empty/whitespace inputs
- Graceful degradation through the full engine
- Filename obfuscation in multi-file scenarios
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from employee_help.privacy.context import ObfuscationContext
from employee_help.privacy.engine import ObfuscationEngine
from employee_help.privacy.recognizers import EntityRecognizer


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _ner_entity(
    label: str, text: str, start: int, end: int
) -> SimpleNamespace:
    return SimpleNamespace(
        label_=label, text=text, start_char=start, end_char=end
    )


def _mock_nlp(*entities: SimpleNamespace):
    def nlp(text: str) -> SimpleNamespace:
        return SimpleNamespace(ents=list(entities))
    return nlp


def _engine_with_ner(*entities: SimpleNamespace) -> ObfuscationEngine:
    """Create an engine with a mocked spaCy model returning given entities."""
    rec = EntityRecognizer()
    rec._nlp = _mock_nlp(*entities)
    rec._ner_loaded = True
    return ObfuscationEngine(recognizer=rec)


def _no_ner_engine() -> ObfuscationEngine:
    rec = EntityRecognizer()
    rec._nlp = None
    rec._ner_loaded = True
    return ObfuscationEngine(recognizer=rec)


def _case_context(**kwargs) -> SimpleNamespace:
    defaults = {
        "plaintiffs": [],
        "defendants": [],
        "plaintiff_counsel": [],
        "defendant_counsel": [],
        "employer_name": None,
        "employee_name": None,
        "case_number": None,
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def _party(name: str, is_entity: bool = False) -> SimpleNamespace:
    return SimpleNamespace(name=name, is_entity=is_entity)


def _attorney(name: str, firm: str | None = None) -> SimpleNamespace:
    return SimpleNamespace(name=name, firm=firm)


# ==================================================================
# Engine round-trip WITH NER entities
# ==================================================================


class TestEngineRoundTripWithNER:
    """Round-trip tests where NER detects PERSON/ORG entities."""

    def test_ner_person_round_trip(self):
        text = "John Smith filed the complaint."
        engine = _engine_with_ner(
            _ner_entity("PERSON", "John Smith", 0, 10),
        )
        ctx = engine.create_context()
        obfuscated = engine.obfuscate(text, ctx)
        restored = engine.deobfuscate(obfuscated, ctx)

        assert "John Smith" not in obfuscated
        assert "PERSON_1" in obfuscated
        assert restored == text

    def test_ner_org_round_trip(self):
        text = "Acme Corp terminated the employee."
        engine = _engine_with_ner(
            _ner_entity("ORG", "Acme Corp", 0, 9),
        )
        ctx = engine.create_context()
        obfuscated = engine.obfuscate(text, ctx)
        restored = engine.deobfuscate(obfuscated, ctx)

        assert "Acme Corp" not in obfuscated
        assert "COMPANY_1" in obfuscated
        assert restored == text

    def test_ner_plus_regex_round_trip(self):
        """NER detects names, regex detects structured PII — all round-trip."""
        text = "John Smith (john@acme.com, 555-123-4567) of Acme Corp."
        engine = _engine_with_ner(
            _ner_entity("PERSON", "John Smith", 0, 10),
            _ner_entity("ORG", "Acme Corp", 44, 53),
        )
        ctx = engine.create_context()
        obfuscated = engine.obfuscate(text, ctx)
        restored = engine.deobfuscate(obfuscated, ctx)

        assert "John Smith" not in obfuscated
        assert "Acme Corp" not in obfuscated
        assert "john@acme.com" not in obfuscated
        assert "555-123-4567" not in obfuscated
        assert restored == text

    def test_ner_with_ssn_round_trip(self):
        """SSN is hard-redacted even when NER also detects entities."""
        text = "John Smith SSN: 123-45-6789."
        engine = _engine_with_ner(
            _ner_entity("PERSON", "John Smith", 0, 10),
        )
        ctx = engine.create_context()
        obfuscated = engine.obfuscate(text, ctx)
        restored = engine.deobfuscate(obfuscated, ctx)

        assert "John Smith" not in obfuscated
        assert "123-45-6789" not in obfuscated
        assert "[REDACTED]" in obfuscated
        # Name restores, SSN stays redacted
        assert "John Smith" in restored
        assert "123-45-6789" not in restored

    def test_ner_citation_excluded_entities_round_trip(self):
        """NER entities overlapping citations are excluded from obfuscation."""
        text = "John Smith cited Cal. Lab. Code § 1102.5."
        engine = _engine_with_ner(
            _ner_entity("PERSON", "John Smith", 0, 10),
            _ner_entity("ORG", "Lab", 22, 25),  # inside citation
        )
        ctx = engine.create_context()
        obfuscated = engine.obfuscate(text, ctx)
        restored = engine.deobfuscate(obfuscated, ctx)

        assert "John Smith" not in obfuscated
        assert "Cal. Lab. Code § 1102.5" in obfuscated
        assert restored == text


# ==================================================================
# Full pipeline: CaseContext + regex + NER
# ==================================================================


class TestFullPipelineCaseContextNER:
    """Full stack: seed from CaseContext, regex scan, NER scan, round-trip."""

    def test_seed_plus_ner_plus_regex(self):
        """CaseContext seeds + NER detects unseen person + regex finds email."""
        text = (
            "Jane Doe (jane@bigco.com) worked at BigCo LLC. "
            "Her manager Bob Jones approved the termination."
        )
        engine = _engine_with_ner(
            # NER picks up Bob Jones (not in CaseContext)
            _ner_entity("PERSON", "Bob Jones", 59, 68),
        )
        ctx = engine.create_context()

        case_ctx = _case_context(
            plaintiffs=[_party("Jane Doe")],
            defendants=[_party("BigCo LLC", is_entity=True)],
            employee_name="Jane Doe",
            employer_name="BigCo LLC",
        )
        engine.seed_from_case_context(case_ctx, ctx)

        obfuscated = engine.obfuscate(text, ctx)
        restored = engine.deobfuscate(obfuscated, ctx)

        # All PII removed
        assert "Jane Doe" not in obfuscated
        assert "BigCo LLC" not in obfuscated
        assert "jane@bigco.com" not in obfuscated
        assert "Bob Jones" not in obfuscated
        # Seeded entities get priority numbers
        assert "PERSON_1" in obfuscated  # Jane Doe (seeded first)
        assert "COMPANY_1" in obfuscated  # BigCo LLC (seeded)
        # Bob Jones discovered by NER gets next number
        assert "PERSON_2" in obfuscated
        # Round-trip
        assert restored == text

    def test_seed_priority_over_ner(self):
        """Seeded entities get lower placeholder numbers than NER-discovered."""
        text = "Alice and Bob worked at Acme Corp."
        engine = _engine_with_ner(
            _ner_entity("PERSON", "Alice", 0, 5),
            _ner_entity("PERSON", "Bob", 10, 13),
            _ner_entity("ORG", "Acme Corp", 24, 33),
        )
        ctx = engine.create_context()

        # Seed Alice as known plaintiff
        case_ctx = _case_context(
            plaintiffs=[_party("Alice")],
            defendants=[_party("Acme Corp", is_entity=True)],
        )
        engine.seed_from_case_context(case_ctx, ctx)

        obfuscated = engine.obfuscate(text, ctx)

        # Alice is PERSON_1 (seeded), Acme Corp is COMPANY_1 (seeded)
        # Bob is PERSON_2 (discovered by NER)
        assert "PERSON_1" in obfuscated  # Alice
        assert "PERSON_2" in obfuscated  # Bob
        assert "COMPANY_1" in obfuscated  # Acme Corp

    def test_full_pipeline_all_entity_types(self):
        """Every entity type through the full pipeline."""
        text = (
            "Jane Doe (jane@bigco.com, 555-999-8888) of BigCo LLC "
            "filed case BC-2025-12345. SSN: 111-22-3333. "
            "Her lawyer Alice Atty of Law Firm LLP. "
            "Under Cal. Lab. Code § 1102.5 and CACI No. 2505. "
            "Damages: $250,000. Filed January 15, 2025."
        )
        engine = _engine_with_ner(
            _ner_entity("PERSON", "Alice Atty", 102, 112),
        )
        ctx = engine.create_context()

        case_ctx = _case_context(
            plaintiffs=[_party("Jane Doe")],
            defendants=[_party("BigCo LLC", is_entity=True)],
            plaintiff_counsel=[_attorney("Alice Atty", firm="Law Firm LLP")],
            employer_name="BigCo LLC",
            employee_name="Jane Doe",
            case_number="BC-2025-12345",
        )
        engine.seed_from_case_context(case_ctx, ctx)

        obfuscated = engine.obfuscate(text, ctx)
        restored = engine.deobfuscate(obfuscated, ctx)

        # PII removed
        for pii in [
            "Jane Doe", "BigCo LLC", "jane@bigco.com", "555-999-8888",
            "BC-2025-12345", "111-22-3333", "Alice Atty", "Law Firm LLP",
        ]:
            assert pii not in obfuscated, f"{pii} should be obfuscated"

        # Legal citations preserved
        assert "Cal. Lab. Code § 1102.5" in obfuscated
        assert "CACI No. 2505" in obfuscated

        # Dates and dollar amounts preserved
        assert "$250,000" in obfuscated
        assert "January 15, 2025" in obfuscated

        # SSN hard-redacted
        assert "[REDACTED]" in obfuscated

        # Round-trip for reversible entities
        for entity in [
            "Jane Doe", "BigCo LLC", "jane@bigco.com", "555-999-8888",
            "Alice Atty", "Law Firm LLP",
        ]:
            assert entity in restored, f"{entity} should be restored"

        # SSN stays redacted
        assert "111-22-3333" not in restored
        assert "[REDACTED]" in restored

        # Dates, dollars, citations preserved through round-trip
        assert "$250,000" in restored
        assert "January 15, 2025" in restored
        assert "Cal. Lab. Code § 1102.5" in restored
        assert "CACI No. 2505" in restored


# ==================================================================
# Date/dollar preservation through engine
# ==================================================================


class TestDateDollarPreservationEngine:
    """Verify dates and dollar amounts pass through the engine unchanged."""

    def test_dates_pass_through(self):
        engine = _no_ner_engine()
        ctx = engine.create_context()
        text = "Filed on January 15, 2025 and March 1, 2024."
        result = engine.obfuscate(text, ctx)
        assert result == text

    def test_dollar_amounts_pass_through(self):
        engine = _no_ner_engine()
        ctx = engine.create_context()
        text = "Earned $150,000, bonus $25,000, damages $1,500,000."
        result = engine.obfuscate(text, ctx)
        assert result == text

    def test_dates_and_dollars_with_entities(self):
        engine = _no_ner_engine()
        ctx = engine.create_context()
        ctx.seed("PERSON", "Jane Doe")

        text = "Jane Doe earned $150,000 and was terminated on January 15, 2025."
        obfuscated = engine.obfuscate(text, ctx)
        restored = engine.deobfuscate(obfuscated, ctx)

        assert "$150,000" in obfuscated
        assert "January 15, 2025" in obfuscated
        assert "Jane Doe" not in obfuscated
        assert restored == text

    def test_mixed_dates_dollars_citations_entities(self):
        """All non-PII content preserved alongside entity obfuscation."""
        engine = _no_ner_engine()
        ctx = engine.create_context()
        ctx.seed("PERSON", "Alice")
        ctx.seed("COMPANY", "BigCo")

        text = (
            "Alice worked at BigCo from January 2020 to March 2025, "
            "earning $200,000/year. Per Cal. Gov. Code § 12940, "
            "damages of $500,000 are claimed."
        )
        obfuscated = engine.obfuscate(text, ctx)
        restored = engine.deobfuscate(obfuscated, ctx)

        assert "Alice" not in obfuscated
        assert "BigCo" not in obfuscated
        assert "January 2020" in obfuscated
        assert "March 2025" in obfuscated
        assert "$200,000" in obfuscated
        assert "$500,000" in obfuscated
        assert "Cal. Gov. Code § 12940" in obfuscated
        assert restored == text


# ==================================================================
# Multi-turn rebuild determinism through engine
# ==================================================================


class TestMultiTurnEngineConsistency:
    """Multi-turn: rebuild context each turn, verify determinism."""

    def test_rebuild_produces_same_obfuscation(self):
        """Two fresh contexts seeded identically + same history → same output."""
        case_ctx = _case_context(
            plaintiffs=[_party("John Smith")],
            defendants=[_party("Acme Corp", is_entity=True)],
            case_number="BC-2025-12345",
        )
        history = "John Smith (john@acme.com) worked at Acme Corp."

        # Turn 1
        engine = _no_ner_engine()
        ctx1 = engine.create_context()
        engine.seed_from_case_context(case_ctx, ctx1)
        obf1 = engine.obfuscate(history, ctx1)

        # Turn 2: fresh context, same setup
        ctx2 = engine.create_context()
        engine.seed_from_case_context(case_ctx, ctx2)
        obf2 = engine.obfuscate(history, ctx2)

        assert obf1 == obf2

    def test_multi_turn_history_scan(self):
        """Multi-turn: scan all history, then obfuscate current query."""
        engine = _no_ner_engine()
        case_ctx = _case_context(
            plaintiffs=[_party("Jane Doe")],
            defendants=[_party("BigCo LLC", is_entity=True)],
        )

        # Simulate turn 3: scan history from turns 1+2, then current query
        ctx = engine.create_context()
        engine.seed_from_case_context(case_ctx, ctx)

        # Scan turn 1 history
        engine.obfuscate("Jane Doe was hired by BigCo LLC.", ctx)
        # Scan turn 2 history (introduces new entity via regex)
        engine.obfuscate(
            "Jane Doe emailed jane@bigco.com about the issue.", ctx
        )
        # Current query
        query = "What happened between Jane Doe and BigCo LLC?"
        obf_query = engine.obfuscate(query, ctx)

        assert "PERSON_1" in obf_query
        assert "COMPANY_1" in obf_query
        assert "Jane Doe" not in obf_query
        assert "BigCo LLC" not in obf_query

        # Deobfuscate response
        response = "PERSON_1 was wrongfully terminated by COMPANY_1."
        restored = engine.deobfuscate(response, ctx)
        assert restored == "Jane Doe was wrongfully terminated by BigCo LLC."

    def test_new_entity_discovered_mid_conversation(self):
        """Entity first appearing in turn 2 gets next available number."""
        engine = _no_ner_engine()
        ctx = engine.create_context()
        ctx.seed("PERSON", "John Smith")

        # Turn 1
        engine.obfuscate("John Smith filed the complaint.", ctx)

        # Turn 2: introduces new email
        r2 = engine.obfuscate("Contact john@acme.com for details.", ctx)
        assert "EMAIL_1" in r2

        # Turn 3: same email uses same placeholder
        r3 = engine.obfuscate("Did john@acme.com respond?", ctx)
        assert "EMAIL_1" in r3

    def test_three_turn_consistency(self):
        """Three full turns with growing entity set — all consistent."""
        engine = _no_ner_engine()
        case_ctx = _case_context(
            plaintiffs=[_party("Alice")],
            defendants=[_party("BigCo", is_entity=True)],
        )

        ctx = engine.create_context()
        engine.seed_from_case_context(case_ctx, ctx)

        # Turn 1
        t1 = engine.obfuscate("Alice works at BigCo.", ctx)
        assert "PERSON_1" in t1
        assert "COMPANY_1" in t1

        # Turn 2: new email discovered
        t2 = engine.obfuscate("Alice's email is alice@bigco.com.", ctx)
        assert "PERSON_1" in t2
        assert "EMAIL_1" in t2

        # Turn 3: new phone discovered, all prior entities consistent
        t3 = engine.obfuscate(
            "Alice (alice@bigco.com) called 555-111-2222.", ctx
        )
        assert "PERSON_1" in t3
        assert "EMAIL_1" in t3
        assert "PHONE_1" in t3

        # Deobfuscate turn 3 response
        resp = "PERSON_1 (EMAIL_1) can be reached at PHONE_1."
        restored = engine.deobfuscate(resp, ctx)
        assert restored == "Alice (alice@bigco.com) can be reached at 555-111-2222."


# ==================================================================
# Realistic LLM response deobfuscation
# ==================================================================


class TestRealisticLLMDeobfuscation:
    """Test deobfuscation of patterns typical in LLM responses."""

    def test_llm_response_with_citations(self):
        """LLM response contains placeholders + legal citations."""
        engine = _no_ner_engine()
        ctx = engine.create_context()
        ctx.seed("PERSON", "Jane Doe")
        ctx.seed("COMPANY", "MegaCorp Inc")

        response = (
            "Based on the analysis, PERSON_1's claim against COMPANY_1 "
            "under Cal. Lab. Code § 1102.5 has merit. Per CACI No. 2505, "
            "PERSON_1 must prove that COMPANY_1 retaliated."
        )
        restored = engine.deobfuscate(response, ctx)

        assert "Jane Doe" in restored
        assert "MegaCorp Inc" in restored
        assert "Cal. Lab. Code § 1102.5" in restored
        assert "CACI No. 2505" in restored
        assert "PERSON_1" not in restored
        assert "COMPANY_1" not in restored

    def test_llm_response_with_amounts_and_dates(self):
        engine = _no_ner_engine()
        ctx = engine.create_context()
        ctx.seed("PERSON", "Bob")
        ctx.seed("COMPANY", "TechCo")

        response = (
            "PERSON_1 was employed by COMPANY_1 from January 2020 "
            "to March 2025, earning $180,000 annually. The statute "
            "of limitations runs until December 31, 2027."
        )
        restored = engine.deobfuscate(response, ctx)

        assert "Bob" in restored
        assert "TechCo" in restored
        assert "$180,000" in restored
        assert "January 2020" in restored
        assert "March 2025" in restored
        assert "December 31, 2027" in restored

    def test_llm_response_with_multiple_entity_types(self):
        """Response references various placeholder types."""
        engine = _no_ner_engine()
        ctx = engine.create_context()
        ctx.seed("PERSON", "Alice Smith")
        ctx.seed("COMPANY", "Acme LLC")
        ctx.add("EMAIL", "alice@acme.com")
        ctx.add("PHONE", "555-123-4567")
        ctx.add("CASE", "BC-2025-99999")

        response = (
            "PERSON_1 of COMPANY_1 can be reached at EMAIL_1 or PHONE_1. "
            "Case CASE_1 is pending."
        )
        restored = engine.deobfuscate(response, ctx)

        assert "Alice Smith" in restored
        assert "Acme LLC" in restored
        assert "alice@acme.com" in restored
        assert "555-123-4567" in restored
        assert "BC-2025-99999" in restored

    def test_llm_response_with_redacted_ssn(self):
        """LLM response echoes [REDACTED] — stays redacted."""
        engine = _no_ner_engine()
        ctx = engine.create_context()
        engine.obfuscate("SSN: 123-45-6789", ctx)  # register SSN

        response = "The employee's SSN [REDACTED] should not be disclosed."
        restored = engine.deobfuscate(response, ctx)
        assert "[REDACTED]" in restored

    def test_llm_response_with_unknown_placeholders(self):
        """LLM hallucinates a placeholder that doesn't exist."""
        engine = _no_ner_engine()
        ctx = engine.create_context()
        ctx.seed("PERSON", "Alice")

        response = "PERSON_1 met with PERSON_3 at COMPANY_5."
        restored = engine.deobfuscate(response, ctx)
        # Known placeholder restored, unknown left intact
        assert "Alice" in restored
        assert "PERSON_3" in restored
        assert "COMPANY_5" in restored

    def test_llm_response_placeholder_adjacent_to_punctuation(self):
        """Placeholders next to commas, periods, colons."""
        engine = _no_ner_engine()
        ctx = engine.create_context()
        ctx.seed("PERSON", "Jane")
        ctx.seed("COMPANY", "BigCo")

        response = "PERSON_1, an employee of COMPANY_1, was terminated. PERSON_1."
        restored = engine.deobfuscate(response, ctx)
        assert restored == "Jane, an employee of BigCo, was terminated. Jane."


# ==================================================================
# Graceful degradation through full engine
# ==================================================================


class TestEngineDegradation:
    """Engine works correctly when NER is unavailable."""

    def test_regex_only_round_trip(self):
        """Without NER, regex entities still round-trip correctly."""
        engine = _no_ner_engine()
        ctx = engine.create_context()

        text = (
            "Contact john@acme.com or call 555-123-4567. "
            "Case: BC-2025-12345. SSN: 123-45-6789."
        )
        obfuscated = engine.obfuscate(text, ctx)
        restored = engine.deobfuscate(obfuscated, ctx)

        assert "john@acme.com" not in obfuscated
        assert "555-123-4567" not in obfuscated
        assert "BC-2025-12345" not in obfuscated
        assert "123-45-6789" not in obfuscated
        # Reversible entities restore
        assert "john@acme.com" in restored
        assert "555-123-4567" in restored
        # SSN stays redacted
        assert "123-45-6789" not in restored

    def test_seeded_names_work_without_ner(self):
        """Even without NER, seeded names are obfuscated via context."""
        engine = _no_ner_engine()
        ctx = engine.create_context()
        ctx.seed("PERSON", "John Smith")
        ctx.seed("COMPANY", "Acme Corp")

        text = "John Smith worked at Acme Corp."
        obfuscated = engine.obfuscate(text, ctx)
        restored = engine.deobfuscate(obfuscated, ctx)

        assert "John Smith" not in obfuscated
        assert "Acme Corp" not in obfuscated
        assert restored == text

    def test_full_case_context_without_ner(self):
        """CaseContext seeding covers all known entities without NER."""
        engine = _no_ner_engine()
        ctx = engine.create_context()

        case_ctx = _case_context(
            plaintiffs=[_party("Jane Doe")],
            defendants=[_party("BigCo LLC", is_entity=True)],
            plaintiff_counsel=[_attorney("Alice Atty", firm="Law Firm")],
            employer_name="BigCo LLC",
            employee_name="Jane Doe",
            case_number="BC-2025-12345",
        )
        engine.seed_from_case_context(case_ctx, ctx)

        text = (
            "Jane Doe, represented by Alice Atty of Law Firm, "
            "filed against BigCo LLC in case BC-2025-12345."
        )
        obfuscated = engine.obfuscate(text, ctx)

        for name in ["Jane Doe", "Alice Atty", "Law Firm", "BigCo LLC"]:
            assert name not in obfuscated


# ==================================================================
# Filename obfuscation scenarios
# ==================================================================


class TestFilenameObfuscationScenarios:
    """Multi-file filename obfuscation edge cases."""

    def test_sequential_files(self):
        engine = _no_ner_engine()
        filenames = ["complaint.pdf", "exhibit_A.docx", "payslip.xlsx"]
        obfuscated = [
            engine.obfuscate_filename(fn, i + 1) for i, fn in enumerate(filenames)
        ]
        assert obfuscated == ["Document 1", "Document 2", "Document 3"]

    def test_filename_with_pii(self):
        """Real filenames containing PII are fully replaced."""
        engine = _no_ner_engine()
        assert engine.obfuscate_filename("Jane_Doe_Termination_Letter.pdf", 1) == "Document 1"
        assert engine.obfuscate_filename("BigCo_Payroll_Records.xlsx", 2) == "Document 2"

    def test_filename_zero_index(self):
        engine = _no_ner_engine()
        assert engine.obfuscate_filename("file.pdf", 0) == "Document 0"

    def test_empty_filename(self):
        engine = _no_ner_engine()
        assert engine.obfuscate_filename("", 1) == "Document 1"


# ==================================================================
# Edge cases across the stack
# ==================================================================


class TestCrossCuttingEdgeCases:
    """Edge cases that span multiple modules."""

    def test_entity_value_is_substring_of_another(self):
        """Longest-match-first prevents partial replacement."""
        engine = _no_ner_engine()
        ctx = engine.create_context()
        ctx.seed("PERSON", "John Smith Jr")
        ctx.seed("PERSON", "John Smith")

        text = "John Smith Jr and John Smith attended."
        obfuscated = engine.obfuscate(text, ctx)
        restored = engine.deobfuscate(obfuscated, ctx)

        assert "PERSON_1" in obfuscated  # John Smith Jr
        assert "PERSON_2" in obfuscated  # John Smith
        assert restored == text

    def test_entity_with_special_chars(self):
        """Entity containing regex special characters."""
        engine = _no_ner_engine()
        ctx = engine.create_context()
        ctx.seed("COMPANY", "Smith & Wesson (Inc.)")

        text = "Smith & Wesson (Inc.) manufactures goods."
        obfuscated = engine.obfuscate(text, ctx)
        restored = engine.deobfuscate(obfuscated, ctx)

        assert "Smith & Wesson (Inc.)" not in obfuscated
        assert restored == text

    def test_empty_text_all_layers(self):
        """Empty string handled at every layer."""
        engine = _no_ner_engine()
        ctx = engine.create_context()
        ctx.seed("PERSON", "John")

        assert engine.obfuscate("", ctx) == ""
        assert engine.deobfuscate("", ctx) == ""

    def test_whitespace_only_text(self):
        engine = _no_ner_engine()
        ctx = engine.create_context()
        ctx.seed("PERSON", "John")
        assert engine.obfuscate("   \n\t  ", ctx) == "   \n\t  "

    def test_very_long_text(self):
        """Engine handles text with many entity occurrences."""
        engine = _no_ner_engine()
        ctx = engine.create_context()
        ctx.seed("PERSON", "Alice")
        ctx.seed("COMPANY", "BigCo")

        # 50 repetitions
        text = " ".join(
            ["Alice works at BigCo."] * 50
        )
        obfuscated = engine.obfuscate(text, ctx)
        restored = engine.deobfuscate(obfuscated, ctx)

        assert "Alice" not in obfuscated
        assert "BigCo" not in obfuscated
        assert obfuscated.count("PERSON_1") == 50
        assert obfuscated.count("COMPANY_1") == 50
        assert restored == text

    def test_multiple_ssns_all_redacted(self):
        """Multiple distinct SSNs all become [REDACTED]."""
        engine = _no_ner_engine()
        ctx = engine.create_context()

        text = "SSN1: 111-22-3333, SSN2: 444-55-6666, EIN: 12-3456789."
        obfuscated = engine.obfuscate(text, ctx)

        assert "111-22-3333" not in obfuscated
        assert "444-55-6666" not in obfuscated
        assert "12-3456789" not in obfuscated
        assert obfuscated.count("[REDACTED]") == 3

        # None are reversible
        restored = engine.deobfuscate(obfuscated, ctx)
        assert "111-22-3333" not in restored
        assert "444-55-6666" not in restored
        assert "12-3456789" not in restored

    def test_newlines_preserved(self):
        """Multiline text with entities round-trips correctly."""
        engine = _no_ner_engine()
        ctx = engine.create_context()
        ctx.seed("PERSON", "John Smith")

        text = "John Smith\nfiled a complaint\non January 1, 2025."
        obfuscated = engine.obfuscate(text, ctx)
        restored = engine.deobfuscate(obfuscated, ctx)

        assert "\n" in obfuscated
        assert restored == text

    def test_unicode_entity_names(self):
        """Unicode characters in entity names work correctly."""
        engine = _no_ner_engine()
        ctx = engine.create_context()
        ctx.seed("PERSON", "José García")
        ctx.seed("COMPANY", "Café LLC")

        text = "José García worked at Café LLC."
        obfuscated = engine.obfuscate(text, ctx)
        restored = engine.deobfuscate(obfuscated, ctx)

        assert "José García" not in obfuscated
        assert "Café LLC" not in obfuscated
        assert restored == text

    def test_context_isolation_between_api_calls(self):
        """Each create_context() produces independent state."""
        engine = _no_ner_engine()

        ctx1 = engine.create_context()
        ctx1.seed("PERSON", "Alice")
        engine.obfuscate("Alice filed.", ctx1)

        ctx2 = engine.create_context()
        ctx2.seed("PERSON", "Bob")
        engine.obfuscate("Bob filed.", ctx2)

        # ctx1 knows Alice, ctx2 knows Bob — no cross-contamination
        assert "Alice" in ctx1.forward_map
        assert "Alice" not in ctx2.forward_map
        assert "Bob" in ctx2.forward_map
        assert "Bob" not in ctx1.forward_map

    def test_entity_discovered_via_regex_registered_in_context(self):
        """Entities found by regex during obfuscate() are in the context."""
        engine = _no_ner_engine()
        ctx = engine.create_context()

        engine.obfuscate(
            "Email: john@acme.com, Phone: 555-111-2222, "
            "SSN: 123-45-6789, Case: BC-2025-99999.",
            ctx,
        )

        # Reversible entities in forward map
        assert "john@acme.com" in ctx.forward_map
        assert "555-111-2222" in ctx.forward_map
        assert "BC-2025-99999" in ctx.forward_map
        # SSN is hard-redacted, still in forward map
        assert "123-45-6789" in ctx.forward_map
        # But SSN is NOT in reverse map (irreversible)
        assert "[REDACTED]" not in ctx.reverse_map


# ==================================================================
# Citation whitelist through engine
# ==================================================================


class TestCitationWhitelistEngine:
    """Legal citations preserved through the full engine pipeline."""

    def test_all_citation_types_preserved(self):
        """Every citation pattern passes through the engine untouched."""
        engine = _no_ner_engine()
        ctx = engine.create_context()
        ctx.seed("PERSON", "Jane")

        citations = [
            "Cal. Lab. Code § 1102.5",
            "Cal. Gov. Code § 12940",
            "CCP § 2030.010",
            "CACI No. 2505",
            "29 C.F.R. § 1630.2",
            "42 U.S.C. § 2000e",
            "550 U.S. 398",
            "123 F.3d 456",
            "45 Cal.App.5th 100",
        ]

        for citation in citations:
            text = f"Jane's claim under {citation} has merit."
            obfuscated = engine.obfuscate(text, ctx)
            assert citation in obfuscated, (
                f"Citation '{citation}' should be preserved"
            )
            assert "Jane" not in obfuscated

    def test_multiple_citations_in_one_text(self):
        engine = _no_ner_engine()
        ctx = engine.create_context()
        ctx.seed("PERSON", "Alice")

        text = (
            "Alice's claim under Cal. Lab. Code § 1102.5, "
            "Cal. Gov. Code § 12940, and 42 U.S.C. § 2000e."
        )
        obfuscated = engine.obfuscate(text, ctx)
        restored = engine.deobfuscate(obfuscated, ctx)

        assert "Cal. Lab. Code § 1102.5" in obfuscated
        assert "Cal. Gov. Code § 12940" in obfuscated
        assert "42 U.S.C. § 2000e" in obfuscated
        assert "Alice" not in obfuscated
        assert restored == text
