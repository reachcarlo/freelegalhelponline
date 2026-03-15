"""Tests for ObfuscationContext — P2.1."""

from __future__ import annotations

import pytest

from employee_help.privacy.context import ObfuscationContext


# ------------------------------------------------------------------
# seed / add basics
# ------------------------------------------------------------------


class TestSeedAndAdd:
    def test_seed_returns_placeholder(self):
        ctx = ObfuscationContext()
        placeholder = ctx.seed("PERSON", "John Smith")
        assert placeholder == "PERSON_1"

    def test_seed_sequential_numbering(self):
        ctx = ObfuscationContext()
        assert ctx.seed("PERSON", "John Smith") == "PERSON_1"
        assert ctx.seed("PERSON", "Jane Doe") == "PERSON_2"

    def test_seed_different_types_independent_counters(self):
        ctx = ObfuscationContext()
        assert ctx.seed("PERSON", "John Smith") == "PERSON_1"
        assert ctx.seed("COMPANY", "Acme Corp") == "COMPANY_1"
        assert ctx.seed("PERSON", "Jane Doe") == "PERSON_2"
        assert ctx.seed("COMPANY", "Globex Inc") == "COMPANY_2"

    def test_seed_idempotent(self):
        ctx = ObfuscationContext()
        p1 = ctx.seed("PERSON", "John Smith")
        p2 = ctx.seed("PERSON", "John Smith")
        assert p1 == p2 == "PERSON_1"
        assert ctx.entity_count == 1

    def test_add_returns_placeholder(self):
        ctx = ObfuscationContext()
        placeholder = ctx.add("EMAIL", "john@acme.com")
        assert placeholder == "EMAIL_1"

    def test_add_idempotent(self):
        ctx = ObfuscationContext()
        p1 = ctx.add("EMAIL", "john@acme.com")
        p2 = ctx.add("EMAIL", "john@acme.com")
        assert p1 == p2 == "EMAIL_1"
        assert ctx.entity_count == 1

    def test_seed_then_add_same_value(self):
        """seed() and add() share the same registry — no double-mapping."""
        ctx = ObfuscationContext()
        p1 = ctx.seed("PERSON", "John Smith")
        p2 = ctx.add("PERSON", "John Smith")
        assert p1 == p2
        assert ctx.entity_count == 1

    def test_empty_value_returns_empty(self):
        ctx = ObfuscationContext()
        assert ctx.seed("PERSON", "") == ""
        assert ctx.add("PERSON", "") == ""
        assert ctx.entity_count == 0


# ------------------------------------------------------------------
# hard redaction
# ------------------------------------------------------------------


class TestHardRedaction:
    def test_hard_redact_returns_redacted(self):
        ctx = ObfuscationContext()
        result = ctx.add_hard_redaction("123-45-6789")
        assert result == "[REDACTED]"

    def test_hard_redact_not_in_reverse_map(self):
        ctx = ObfuscationContext()
        ctx.add_hard_redaction("123-45-6789")
        assert "[REDACTED]" not in ctx.reverse_map

    def test_hard_redact_irreversible(self):
        ctx = ObfuscationContext()
        ctx.add_hard_redaction("123-45-6789")
        text = "SSN is [REDACTED] for the record"
        assert ctx.deobfuscate(text) == text  # unchanged

    def test_hard_redact_idempotent(self):
        ctx = ObfuscationContext()
        r1 = ctx.add_hard_redaction("123-45-6789")
        r2 = ctx.add_hard_redaction("123-45-6789")
        assert r1 == r2 == "[REDACTED]"

    def test_hard_redact_in_obfuscate(self):
        ctx = ObfuscationContext()
        ctx.add_hard_redaction("123-45-6789")
        result = ctx.obfuscate("My SSN is 123-45-6789 ok?")
        assert result == "My SSN is [REDACTED] ok?"


# ------------------------------------------------------------------
# obfuscate
# ------------------------------------------------------------------


class TestObfuscate:
    def test_basic_obfuscation(self):
        ctx = ObfuscationContext()
        ctx.seed("PERSON", "John Smith")
        result = ctx.obfuscate("John Smith filed a complaint")
        assert result == "PERSON_1 filed a complaint"

    def test_multiple_entities(self):
        ctx = ObfuscationContext()
        ctx.seed("PERSON", "John Smith")
        ctx.seed("COMPANY", "Acme Corp")
        result = ctx.obfuscate("John Smith worked at Acme Corp")
        assert result == "PERSON_1 worked at COMPANY_1"

    def test_multiple_occurrences(self):
        ctx = ObfuscationContext()
        ctx.seed("PERSON", "John Smith")
        result = ctx.obfuscate("John Smith said that John Smith would file")
        assert result == "PERSON_1 said that PERSON_1 would file"

    def test_empty_text(self):
        ctx = ObfuscationContext()
        ctx.seed("PERSON", "John Smith")
        assert ctx.obfuscate("") == ""

    def test_no_entities(self):
        ctx = ObfuscationContext()
        text = "This text has no entities"
        assert ctx.obfuscate(text) == text

    def test_no_mappings(self):
        ctx = ObfuscationContext()
        text = "John Smith worked at Acme"
        assert ctx.obfuscate(text) == text


# ------------------------------------------------------------------
# deobfuscate
# ------------------------------------------------------------------


class TestDeobfuscate:
    def test_basic_deobfuscation(self):
        ctx = ObfuscationContext()
        ctx.seed("PERSON", "John Smith")
        result = ctx.deobfuscate("PERSON_1 filed a complaint")
        assert result == "John Smith filed a complaint"

    def test_multiple_entities(self):
        ctx = ObfuscationContext()
        ctx.seed("PERSON", "John Smith")
        ctx.seed("COMPANY", "Acme Corp")
        result = ctx.deobfuscate("PERSON_1 worked at COMPANY_1")
        assert result == "John Smith worked at Acme Corp"

    def test_empty_text(self):
        ctx = ObfuscationContext()
        ctx.seed("PERSON", "John Smith")
        assert ctx.deobfuscate("") == ""

    def test_no_mappings(self):
        ctx = ObfuscationContext()
        text = "PERSON_1 filed a complaint"
        assert ctx.deobfuscate(text) == text

    def test_unknown_placeholder_left_intact(self):
        ctx = ObfuscationContext()
        ctx.seed("PERSON", "John Smith")
        result = ctx.deobfuscate("PERSON_1 talked to PERSON_5")
        assert result == "John Smith talked to PERSON_5"


# ------------------------------------------------------------------
# round-trip
# ------------------------------------------------------------------


class TestRoundTrip:
    def test_round_trip_simple(self):
        ctx = ObfuscationContext()
        ctx.seed("PERSON", "John Smith")
        ctx.seed("COMPANY", "Acme Corp")
        ctx.seed("EMAIL", "john@acme.com")

        original = "John Smith (john@acme.com) was employed by Acme Corp."
        obfuscated = ctx.obfuscate(original)
        restored = ctx.deobfuscate(obfuscated)

        assert "John Smith" not in obfuscated
        assert "Acme Corp" not in obfuscated
        assert "john@acme.com" not in obfuscated
        assert restored == original

    def test_round_trip_with_legal_text(self):
        ctx = ObfuscationContext()
        ctx.seed("PERSON", "Jane Doe")
        ctx.seed("COMPANY", "BigCo LLC")

        original = (
            "Jane Doe's claim under Cal. Lab. Code § 1102.5 against "
            "BigCo LLC is supported by CACI No. 2505."
        )
        obfuscated = ctx.obfuscate(original)
        restored = ctx.deobfuscate(obfuscated)

        # Entities replaced
        assert "Jane Doe" not in obfuscated
        assert "BigCo LLC" not in obfuscated
        # Legal citations preserved
        assert "Cal. Lab. Code § 1102.5" in obfuscated
        assert "CACI No. 2505" in obfuscated
        # Round-trip
        assert restored == original

    def test_round_trip_with_dates_and_dollars(self):
        """Dates and dollar amounts pass through unchanged."""
        ctx = ObfuscationContext()
        ctx.seed("PERSON", "Alice")

        original = "Alice earned $150,000 and was terminated on January 15, 2025."
        obfuscated = ctx.obfuscate(original)
        restored = ctx.deobfuscate(obfuscated)

        assert "$150,000" in obfuscated
        assert "January 15, 2025" in obfuscated
        assert restored == original

    def test_round_trip_preserves_whitespace_and_newlines(self):
        ctx = ObfuscationContext()
        ctx.seed("PERSON", "John Smith")

        original = "John Smith\nfiled on\n  January 1, 2025"
        obfuscated = ctx.obfuscate(original)
        restored = ctx.deobfuscate(obfuscated)
        assert restored == original


# ------------------------------------------------------------------
# longest-match-first / word-boundary
# ------------------------------------------------------------------


class TestLongestMatchFirst:
    def test_smithfield_before_smith(self):
        ctx = ObfuscationContext()
        ctx.seed("COMPANY", "Smithfield Foods")
        ctx.seed("PERSON", "Smith")

        result = ctx.obfuscate("Smithfield Foods hired Smith")
        assert result == "COMPANY_1 hired PERSON_1"

    def test_no_partial_match_in_longer_word(self):
        """'Smith' should NOT match inside 'locksmith'."""
        ctx = ObfuscationContext()
        ctx.seed("PERSON", "Smith")

        result = ctx.obfuscate("The locksmith fixed the door")
        assert result == "The locksmith fixed the door"

    def test_word_boundary_start_of_text(self):
        ctx = ObfuscationContext()
        ctx.seed("PERSON", "Smith")
        result = ctx.obfuscate("Smith went home")
        assert result == "PERSON_1 went home"

    def test_word_boundary_end_of_text(self):
        ctx = ObfuscationContext()
        ctx.seed("PERSON", "Smith")
        result = ctx.obfuscate("called Smith")
        assert result == "called PERSON_1"

    def test_adjacent_punctuation(self):
        ctx = ObfuscationContext()
        ctx.seed("PERSON", "Smith")
        result = ctx.obfuscate("Dear Smith, welcome. Smith.")
        assert result == "Dear PERSON_1, welcome. PERSON_1."

    def test_entity_with_special_regex_chars(self):
        """Entity values with regex special chars are escaped properly."""
        ctx = ObfuscationContext()
        ctx.seed("COMPANY", "A+B Corp.")
        result = ctx.obfuscate("At A+B Corp. we do things")
        assert result == "At COMPANY_1 we do things"

    def test_deobfuscate_longest_match(self):
        """Deobfuscation also uses longest-match-first."""
        ctx = ObfuscationContext()
        ctx.seed("COMPANY", "Smithfield Foods")
        ctx.seed("PERSON", "Smith")

        obf = "COMPANY_1 hired PERSON_1"
        result = ctx.deobfuscate(obf)
        assert result == "Smithfield Foods hired Smith"


# ------------------------------------------------------------------
# multi-turn consistency
# ------------------------------------------------------------------


class TestMultiTurnConsistency:
    def test_deterministic_rebuild(self):
        """Simulates multi-turn: rebuilding the map from the same inputs
        produces the same entity→placeholder assignments.

        Note: ObfuscationContext only replaces *known* entities.
        Discovery of new entities (e.g. emails in history text) is the
        engine's responsibility (P2.4).  Here we simulate the engine
        re-adding the same entities in the same order.
        """
        # Turn 1
        ctx1 = ObfuscationContext()
        ctx1.seed("PERSON", "John Smith")
        ctx1.seed("COMPANY", "Acme Corp")
        ctx1.add("EMAIL", "john@acme.com")
        obf1 = ctx1.obfuscate("John Smith at Acme Corp (john@acme.com)")

        # Turn 2: fresh context, same seeding order + same discovered entities
        ctx2 = ObfuscationContext()
        ctx2.seed("PERSON", "John Smith")
        ctx2.seed("COMPANY", "Acme Corp")
        # Engine would re-discover email by scanning history text
        ctx2.add("EMAIL", "john@acme.com")
        obf2 = ctx2.obfuscate("John Smith at Acme Corp (john@acme.com)")

        assert obf1 == obf2

    def test_new_entity_in_later_turn_gets_next_number(self):
        ctx = ObfuscationContext()
        ctx.seed("PERSON", "John Smith")
        # Simulate turn 1
        ctx.obfuscate("John Smith called")
        # Turn 2 introduces a new person
        ctx.add("PERSON", "Jane Doe")
        result = ctx.obfuscate("Jane Doe replied to John Smith")
        assert result == "PERSON_2 replied to PERSON_1"


# ------------------------------------------------------------------
# property accessors
# ------------------------------------------------------------------


class TestProperties:
    def test_entity_count(self):
        ctx = ObfuscationContext()
        assert ctx.entity_count == 0
        ctx.seed("PERSON", "A")
        assert ctx.entity_count == 1
        ctx.seed("COMPANY", "B")
        assert ctx.entity_count == 2

    def test_forward_map_is_copy(self):
        ctx = ObfuscationContext()
        ctx.seed("PERSON", "A")
        fwd = ctx.forward_map
        fwd["X"] = "Y"
        assert "X" not in ctx.forward_map

    def test_reverse_map_is_copy(self):
        ctx = ObfuscationContext()
        ctx.seed("PERSON", "A")
        rev = ctx.reverse_map
        rev["X"] = "Y"
        assert "X" not in ctx.reverse_map


# ------------------------------------------------------------------
# edge cases
# ------------------------------------------------------------------


class TestEdgeCases:
    def test_none_text_obfuscate(self):
        """obfuscate handles None-ish empty string gracefully."""
        ctx = ObfuscationContext()
        ctx.seed("PERSON", "John")
        assert ctx.obfuscate("") == ""

    def test_entity_at_text_boundaries(self):
        ctx = ObfuscationContext()
        ctx.seed("PERSON", "Alice")
        assert ctx.obfuscate("Alice") == "PERSON_1"

    def test_overlapping_entity_names(self):
        """When one entity name contains another."""
        ctx = ObfuscationContext()
        ctx.seed("PERSON", "John Smith Jr")
        ctx.seed("PERSON", "John Smith")

        result = ctx.obfuscate("John Smith Jr and John Smith attended")
        assert result == "PERSON_1 and PERSON_2 attended"

    def test_email_entity_not_partial_matched(self):
        ctx = ObfuscationContext()
        ctx.add("EMAIL", "john@acme.com")
        result = ctx.obfuscate("Contact john@acme.com for info")
        assert result == "Contact EMAIL_1 for info"

    def test_phone_number_entity(self):
        ctx = ObfuscationContext()
        ctx.add("PHONE", "555-123-4567")
        result = ctx.obfuscate("Call 555-123-4567 now")
        assert result == "Call PHONE_1 now"

    def test_case_number_entity(self):
        ctx = ObfuscationContext()
        ctx.add("CASE", "BC-2025-12345")
        result = ctx.obfuscate("Case BC-2025-12345 was filed")
        assert result == "Case CASE_1 was filed"

    def test_mixed_entity_types(self):
        ctx = ObfuscationContext()
        ctx.seed("PERSON", "John Smith")
        ctx.seed("COMPANY", "Acme Corp")
        ctx.add("EMAIL", "john@acme.com")
        ctx.add("PHONE", "555-123-4567")
        ctx.add("CASE", "BC-2025-12345")
        ctx.add_hard_redaction("123-45-6789")

        text = (
            "John Smith (john@acme.com, 555-123-4567) of Acme Corp "
            "filed case BC-2025-12345. SSN: 123-45-6789."
        )
        obfuscated = ctx.obfuscate(text)

        assert "John Smith" not in obfuscated
        assert "Acme Corp" not in obfuscated
        assert "john@acme.com" not in obfuscated
        assert "555-123-4567" not in obfuscated
        assert "BC-2025-12345" not in obfuscated
        assert "123-45-6789" not in obfuscated
        assert "[REDACTED]" in obfuscated

        # Reversible entities round-trip
        deobfuscated = ctx.deobfuscate(obfuscated)
        assert "John Smith" in deobfuscated
        assert "Acme Corp" in deobfuscated
        assert "john@acme.com" in deobfuscated
        assert "555-123-4567" in deobfuscated
        assert "BC-2025-12345" in deobfuscated
        # SSN stays redacted
        assert "123-45-6789" not in deobfuscated
        assert "[REDACTED]" in deobfuscated

    def test_multiple_hard_redactions_all_become_same_label(self):
        ctx = ObfuscationContext()
        ctx.add_hard_redaction("123-45-6789")
        ctx.add_hard_redaction("987-65-4321")
        text = "SSN1: 123-45-6789, SSN2: 987-65-4321"
        result = ctx.obfuscate(text)
        assert result == "SSN1: [REDACTED], SSN2: [REDACTED]"
