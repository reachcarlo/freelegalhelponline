"""Tests for ObfuscationEngine — P2.4."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from employee_help.privacy.context import ObfuscationContext
from employee_help.privacy.engine import ObfuscationEngine
from employee_help.privacy.recognizers import EntityRecognizer


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _no_ner_engine() -> ObfuscationEngine:
    """Create an engine with NER disabled (regex only)."""
    recognizer = EntityRecognizer()
    recognizer._nlp = None
    recognizer._ner_loaded = True
    return ObfuscationEngine(recognizer=recognizer)


def _case_context(**kwargs) -> SimpleNamespace:
    """Create a mock CaseContext with given attributes."""
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
# create_context
# ==================================================================


class TestCreateContext:
    def test_returns_fresh_context(self):
        engine = _no_ner_engine()
        ctx = engine.create_context()
        assert isinstance(ctx, ObfuscationContext)
        assert ctx.entity_count == 0

    def test_independent_contexts(self):
        engine = _no_ner_engine()
        ctx1 = engine.create_context()
        ctx2 = engine.create_context()
        ctx1.seed("PERSON", "Alice")
        assert ctx2.entity_count == 0


# ==================================================================
# obfuscate
# ==================================================================


class TestObfuscate:
    def test_empty_text(self):
        engine = _no_ner_engine()
        ctx = engine.create_context()
        assert engine.obfuscate("", ctx) == ""

    def test_no_entities(self):
        engine = _no_ner_engine()
        ctx = engine.create_context()
        result = engine.obfuscate("plain legal text", ctx)
        assert result == "plain legal text"

    def test_ssn_hard_redacted(self):
        engine = _no_ner_engine()
        ctx = engine.create_context()
        result = engine.obfuscate("SSN: 123-45-6789", ctx)
        assert "123-45-6789" not in result
        assert "[REDACTED]" in result

    def test_ein_hard_redacted(self):
        engine = _no_ner_engine()
        ctx = engine.create_context()
        result = engine.obfuscate("EIN: 12-3456789", ctx)
        assert "12-3456789" not in result
        assert "[REDACTED]" in result

    def test_email_obfuscated(self):
        engine = _no_ner_engine()
        ctx = engine.create_context()
        result = engine.obfuscate("Contact john@acme.com", ctx)
        assert "john@acme.com" not in result
        assert "EMAIL_1" in result

    def test_phone_obfuscated(self):
        engine = _no_ner_engine()
        ctx = engine.create_context()
        result = engine.obfuscate("Call 555-123-4567", ctx)
        assert "555-123-4567" not in result
        assert "PHONE_1" in result

    def test_case_number_obfuscated(self):
        engine = _no_ner_engine()
        ctx = engine.create_context()
        result = engine.obfuscate("Case BC-2025-12345", ctx)
        assert "BC-2025-12345" not in result
        assert "CASE_1" in result

    def test_mixed_entities(self):
        engine = _no_ner_engine()
        ctx = engine.create_context()
        text = (
            "SSN 123-45-6789, email john@acme.com, "
            "phone 555-123-4567, case BC-2025-12345"
        )
        result = engine.obfuscate(text, ctx)
        assert "123-45-6789" not in result
        assert "john@acme.com" not in result
        assert "555-123-4567" not in result
        assert "BC-2025-12345" not in result

    def test_seeded_entities_used(self):
        """Entities seeded before obfuscate are applied."""
        engine = _no_ner_engine()
        ctx = engine.create_context()
        ctx.seed("PERSON", "John Smith")
        result = engine.obfuscate("John Smith filed the complaint.", ctx)
        assert "John Smith" not in result
        assert "PERSON_1" in result

    def test_multiple_calls_accumulate(self):
        """Multiple obfuscate calls on same context share entity map."""
        engine = _no_ner_engine()
        ctx = engine.create_context()
        r1 = engine.obfuscate("Email: john@acme.com", ctx)
        r2 = engine.obfuscate("Reply to john@acme.com", ctx)
        assert "EMAIL_1" in r1
        assert "EMAIL_1" in r2

    def test_legal_citations_preserved(self):
        engine = _no_ner_engine()
        ctx = engine.create_context()
        result = engine.obfuscate("Cal. Lab. Code § 1102.5", ctx)
        assert result == "Cal. Lab. Code § 1102.5"

    def test_discovered_entity_registered_in_context(self):
        engine = _no_ner_engine()
        ctx = engine.create_context()
        engine.obfuscate("Contact john@acme.com", ctx)
        assert "john@acme.com" in ctx.forward_map


# ==================================================================
# deobfuscate
# ==================================================================


class TestDeobfuscate:
    def test_basic_deobfuscation(self):
        engine = _no_ner_engine()
        ctx = engine.create_context()
        ctx.seed("PERSON", "John Smith")
        result = engine.deobfuscate("PERSON_1 filed a complaint", ctx)
        assert result == "John Smith filed a complaint"

    def test_empty_text(self):
        engine = _no_ner_engine()
        ctx = engine.create_context()
        assert engine.deobfuscate("", ctx) == ""

    def test_ssn_stays_redacted(self):
        engine = _no_ner_engine()
        ctx = engine.create_context()
        engine.obfuscate("SSN: 123-45-6789", ctx)
        result = engine.deobfuscate("The SSN is [REDACTED].", ctx)
        assert result == "The SSN is [REDACTED]."

    def test_unknown_placeholder_left_intact(self):
        engine = _no_ner_engine()
        ctx = engine.create_context()
        ctx.seed("PERSON", "John Smith")
        result = engine.deobfuscate("PERSON_1 talked to PERSON_5", ctx)
        assert result == "John Smith talked to PERSON_5"


# ==================================================================
# obfuscate_filename
# ==================================================================


class TestObfuscateFilename:
    def test_basic(self):
        engine = _no_ner_engine()
        result = engine.obfuscate_filename("Smith_Complaint.pdf", 1)
        assert result == "Document 1"

    def test_various_indices(self):
        engine = _no_ner_engine()
        assert engine.obfuscate_filename("file.pdf", 1) == "Document 1"
        assert engine.obfuscate_filename("file.docx", 2) == "Document 2"
        assert engine.obfuscate_filename("file.txt", 10) == "Document 10"

    def test_ignores_original_filename(self):
        engine = _no_ner_engine()
        r1 = engine.obfuscate_filename("secret_doc.pdf", 3)
        r2 = engine.obfuscate_filename("public_doc.pdf", 3)
        assert r1 == r2 == "Document 3"


# ==================================================================
# seed_from_case_context
# ==================================================================


class TestSeedFromCaseContext:
    def test_none_is_noop(self):
        engine = _no_ner_engine()
        ctx = engine.create_context()
        engine.seed_from_case_context(None, ctx)
        assert ctx.entity_count == 0

    def test_plaintiffs_seeded_as_person(self):
        engine = _no_ner_engine()
        ctx = engine.create_context()
        case_ctx = _case_context(plaintiffs=[_party("John Smith")])
        engine.seed_from_case_context(case_ctx, ctx)
        assert ctx.forward_map["John Smith"] == "PERSON_1"

    def test_entity_defendant_seeded_as_company(self):
        engine = _no_ner_engine()
        ctx = engine.create_context()
        case_ctx = _case_context(
            defendants=[_party("Acme Corp", is_entity=True)]
        )
        engine.seed_from_case_context(case_ctx, ctx)
        assert ctx.forward_map["Acme Corp"] == "COMPANY_1"

    def test_individual_defendant_seeded_as_person(self):
        engine = _no_ner_engine()
        ctx = engine.create_context()
        case_ctx = _case_context(
            defendants=[_party("Jane Roe", is_entity=False)]
        )
        engine.seed_from_case_context(case_ctx, ctx)
        assert ctx.forward_map["Jane Roe"] == "PERSON_1"

    def test_attorneys_seeded(self):
        engine = _no_ner_engine()
        ctx = engine.create_context()
        case_ctx = _case_context(
            plaintiff_counsel=[_attorney("Alice Atty", firm="Law Firm LLP")],
            defendant_counsel=[_attorney("Bob Atty")],
        )
        engine.seed_from_case_context(case_ctx, ctx)
        assert "Alice Atty" in ctx.forward_map
        assert "Law Firm LLP" in ctx.forward_map
        assert "Bob Atty" in ctx.forward_map

    def test_attorney_without_firm(self):
        engine = _no_ner_engine()
        ctx = engine.create_context()
        case_ctx = _case_context(
            plaintiff_counsel=[_attorney("Solo Atty")],
        )
        engine.seed_from_case_context(case_ctx, ctx)
        assert ctx.entity_count == 1  # only the attorney name

    def test_employer_employee_seeded(self):
        engine = _no_ner_engine()
        ctx = engine.create_context()
        case_ctx = _case_context(
            employer_name="BigCo LLC",
            employee_name="Jane Doe",
        )
        engine.seed_from_case_context(case_ctx, ctx)
        assert ctx.forward_map["BigCo LLC"] == "COMPANY_1"
        assert ctx.forward_map["Jane Doe"] == "PERSON_1"

    def test_case_number_seeded(self):
        engine = _no_ner_engine()
        ctx = engine.create_context()
        case_ctx = _case_context(case_number="BC-2025-12345")
        engine.seed_from_case_context(case_ctx, ctx)
        assert ctx.forward_map["BC-2025-12345"] == "CASE_1"

    def test_full_case_context(self):
        engine = _no_ner_engine()
        ctx = engine.create_context()
        case_ctx = _case_context(
            plaintiffs=[_party("John Smith")],
            defendants=[_party("Acme Corp", is_entity=True)],
            plaintiff_counsel=[
                _attorney("Alice Atty", firm="Smith & Jones")
            ],
            defendant_counsel=[_attorney("Bob Atty", firm="BigLaw LLP")],
            employer_name="Acme Corp",  # same as defendant — idempotent
            employee_name="John Smith",  # same as plaintiff — idempotent
            case_number="BC-2025-12345",
        )
        engine.seed_from_case_context(case_ctx, ctx)
        # Idempotent: Acme Corp and John Smith not double-counted
        assert ctx.forward_map["John Smith"] == "PERSON_1"
        assert ctx.forward_map["Acme Corp"] == "COMPANY_1"
        assert "BC-2025-12345" in ctx.forward_map

    def test_multiple_plaintiffs_numbered(self):
        engine = _no_ner_engine()
        ctx = engine.create_context()
        case_ctx = _case_context(
            plaintiffs=[_party("Alice"), _party("Bob")],
        )
        engine.seed_from_case_context(case_ctx, ctx)
        assert ctx.forward_map["Alice"] == "PERSON_1"
        assert ctx.forward_map["Bob"] == "PERSON_2"

    def test_seeding_order_deterministic(self):
        """Same inputs produce same placeholder assignments."""
        engine = _no_ner_engine()
        ctx1 = engine.create_context()
        ctx2 = engine.create_context()
        case_ctx = _case_context(
            plaintiffs=[_party("John Smith")],
            defendants=[_party("Acme Corp", is_entity=True)],
            employer_name="Acme Corp",
            case_number="BC-2025-12345",
        )
        engine.seed_from_case_context(case_ctx, ctx1)
        engine.seed_from_case_context(case_ctx, ctx2)
        assert ctx1.forward_map == ctx2.forward_map


# ==================================================================
# Round-trip
# ==================================================================


class TestRoundTrip:
    def test_obfuscate_deobfuscate(self):
        engine = _no_ner_engine()
        ctx = engine.create_context()
        ctx.seed("PERSON", "John Smith")
        ctx.seed("COMPANY", "Acme Corp")

        original = "John Smith worked at Acme Corp."
        obfuscated = engine.obfuscate(original, ctx)
        restored = engine.deobfuscate(obfuscated, ctx)

        assert "John Smith" not in obfuscated
        assert "Acme Corp" not in obfuscated
        assert restored == original

    def test_round_trip_with_regex_entities(self):
        engine = _no_ner_engine()
        ctx = engine.create_context()

        original = (
            "Email john@acme.com, phone 555-123-4567, case BC-2025-12345."
        )
        obfuscated = engine.obfuscate(original, ctx)
        restored = engine.deobfuscate(obfuscated, ctx)

        assert "john@acme.com" not in obfuscated
        assert "555-123-4567" not in obfuscated
        assert "BC-2025-12345" not in obfuscated
        assert restored == original

    def test_ssn_not_restored(self):
        engine = _no_ner_engine()
        ctx = engine.create_context()

        original = "SSN: 123-45-6789"
        obfuscated = engine.obfuscate(original, ctx)
        restored = engine.deobfuscate(obfuscated, ctx)

        assert "123-45-6789" not in obfuscated
        assert "123-45-6789" not in restored  # SSN stays redacted

    def test_seeded_plus_discovered(self):
        engine = _no_ner_engine()
        ctx = engine.create_context()
        ctx.seed("PERSON", "John Smith")

        original = "John Smith (john@acme.com) filed case BC-2025-12345."
        obfuscated = engine.obfuscate(original, ctx)
        restored = engine.deobfuscate(obfuscated, ctx)

        assert "John Smith" not in obfuscated
        assert "john@acme.com" not in obfuscated
        assert "BC-2025-12345" not in obfuscated
        assert restored == original

    def test_legal_citations_preserved(self):
        engine = _no_ner_engine()
        ctx = engine.create_context()
        ctx.seed("PERSON", "Jane Doe")

        original = "Jane Doe's claim under Cal. Lab. Code § 1102.5."
        obfuscated = engine.obfuscate(original, ctx)
        restored = engine.deobfuscate(obfuscated, ctx)

        assert "Cal. Lab. Code § 1102.5" in obfuscated
        assert restored == original

    def test_full_pipeline_with_case_context(self):
        """End-to-end: seed from CaseContext → obfuscate → deobfuscate."""
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

        original = (
            "Jane Doe (jane@bigco.com, 555-999-8888) worked at BigCo LLC. "
            "Case BC-2025-12345. SSN: 111-22-3333. "
            "Represented by Alice Atty of Law Firm. "
            "Per Cal. Lab. Code § 1102.5."
        )
        obfuscated = engine.obfuscate(original, ctx)

        # All PII removed
        assert "Jane Doe" not in obfuscated
        assert "BigCo LLC" not in obfuscated
        assert "jane@bigco.com" not in obfuscated
        assert "555-999-8888" not in obfuscated
        assert "111-22-3333" not in obfuscated
        assert "Alice Atty" not in obfuscated
        assert "Law Firm" not in obfuscated
        # Citation preserved
        assert "Cal. Lab. Code § 1102.5" in obfuscated
        # SSN hard-redacted
        assert "[REDACTED]" in obfuscated

        # Round-trip (everything except SSN)
        restored = engine.deobfuscate(obfuscated, ctx)
        assert "Jane Doe" in restored
        assert "BigCo LLC" in restored
        assert "jane@bigco.com" in restored
        assert "555-999-8888" in restored
        assert "Alice Atty" in restored
        assert "Law Firm" in restored
        assert "111-22-3333" not in restored  # SSN stays redacted


# ==================================================================
# Multi-text obfuscation
# ==================================================================


class TestMultiTextObfuscation:
    def test_entities_shared_across_texts(self):
        """Entities discovered in first text get same placeholder in second."""
        engine = _no_ner_engine()
        ctx = engine.create_context()
        r1 = engine.obfuscate("Email: john@acme.com", ctx)
        r2 = engine.obfuscate("Reply to john@acme.com", ctx)
        assert "EMAIL_1" in r1
        assert "EMAIL_1" in r2

    def test_new_entity_in_later_text(self):
        engine = _no_ner_engine()
        ctx = engine.create_context()
        engine.obfuscate("Email: john@acme.com", ctx)
        r2 = engine.obfuscate("Also jane@acme.com", ctx)
        assert "EMAIL_2" in r2

    def test_multi_turn_consistency(self):
        """Simulates multi-turn: seed, scan history, scan current."""
        engine = _no_ner_engine()
        ctx = engine.create_context()
        ctx.seed("PERSON", "John Smith")
        ctx.seed("COMPANY", "Acme Corp")

        # Scan history (populates map from history)
        history = "John Smith was employed by Acme Corp."
        engine.obfuscate(history, ctx)

        # Obfuscate current query
        query = "What happened with John Smith at Acme Corp?"
        obf_query = engine.obfuscate(query, ctx)
        assert "PERSON_1" in obf_query
        assert "COMPANY_1" in obf_query

        # Deobfuscate response
        response = "PERSON_1 was terminated by COMPANY_1."
        restored = engine.deobfuscate(response, ctx)
        assert restored == "John Smith was terminated by Acme Corp."

    def test_obfuscate_history_then_current(self):
        """Multi-turn: entities from history reused in current turn."""
        engine = _no_ner_engine()
        ctx = engine.create_context()

        # History has an email
        engine.obfuscate("Contact john@acme.com for details.", ctx)
        # Current query mentions same email
        result = engine.obfuscate(
            "Did john@acme.com respond to the complaint?", ctx
        )
        assert "EMAIL_1" in result
        assert "john@acme.com" not in result


# ==================================================================
# Default recognizer
# ==================================================================


class TestDefaultRecognizer:
    def test_engine_creates_default_recognizer(self):
        """Engine creates its own EntityRecognizer if none provided."""
        engine = ObfuscationEngine()
        assert engine._recognizer is not None
        assert isinstance(engine._recognizer, EntityRecognizer)

    def test_custom_recognizer_used(self):
        """Custom recognizer is used when provided."""
        recognizer = EntityRecognizer()
        engine = ObfuscationEngine(recognizer=recognizer)
        assert engine._recognizer is recognizer
