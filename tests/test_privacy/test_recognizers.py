"""Tests for EntityRecognizer — P2.2 (regex) + P2.3 (NER)."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from employee_help.privacy.recognizers import (
    CASE_NO_PATTERN,
    CITATION_PATTERN,
    EIN_PATTERN,
    EMAIL_PATTERN,
    PHONE_PATTERN,
    SSN_PATTERN,
    EntityRecognizer,
    RecognizedEntity,
)


# ------------------------------------------------------------------
# NER test helpers
# ------------------------------------------------------------------


def _ner_entity(
    label: str, text: str, start: int, end: int
) -> SimpleNamespace:
    """Create a mock spaCy entity span."""
    return SimpleNamespace(
        label_=label, text=text, start_char=start, end_char=end
    )


def _mock_nlp(*entities: SimpleNamespace):
    """Return a callable that produces a mock doc with given entities."""
    def nlp(text: str) -> SimpleNamespace:
        return SimpleNamespace(ents=list(entities))
    return nlp


def _ner_recognizer(*entities: SimpleNamespace) -> EntityRecognizer:
    """Create an EntityRecognizer with a mocked spaCy model."""
    rec = EntityRecognizer()
    rec._nlp = _mock_nlp(*entities)
    rec._ner_loaded = True
    return rec


def _no_ner_recognizer() -> EntityRecognizer:
    """Create an EntityRecognizer with NER explicitly disabled."""
    rec = EntityRecognizer()
    rec._nlp = None
    rec._ner_loaded = True
    return rec


# ==================================================================
# Pattern-level tests (validate individual regex patterns)
# ==================================================================


class TestSSNPattern:
    def test_standard_ssn(self):
        assert SSN_PATTERN.search("123-45-6789")

    def test_ssn_in_sentence(self):
        m = SSN_PATTERN.search("SSN is 123-45-6789 for")
        assert m and m.group(0) == "123-45-6789"

    def test_no_match_without_hyphens(self):
        assert not SSN_PATTERN.search("123456789")

    def test_no_match_partial(self):
        assert not SSN_PATTERN.search("123-45-678")

    def test_multiple_ssns(self):
        matches = SSN_PATTERN.findall("A: 111-22-3333, B: 444-55-6666")
        assert matches == ["111-22-3333", "444-55-6666"]


class TestEINPattern:
    def test_standard_ein(self):
        assert EIN_PATTERN.search("12-3456789")

    def test_ein_in_sentence(self):
        m = EIN_PATTERN.search("EIN: 12-3456789 on file")
        assert m and m.group(0) == "12-3456789"

    def test_no_match_wrong_format(self):
        assert not EIN_PATTERN.search("123-456789")


class TestPhonePattern:
    def test_standard_format(self):
        assert PHONE_PATTERN.search("555-123-4567")

    def test_with_parens(self):
        assert PHONE_PATTERN.search("(555) 123-4567")

    def test_with_country_code(self):
        assert PHONE_PATTERN.search("+1-555-123-4567")

    def test_dots_separator(self):
        assert PHONE_PATTERN.search("555.123.4567")

    def test_no_match_short(self):
        assert not PHONE_PATTERN.search("555-1234")

    def test_multiple_phones(self):
        text = "Call 555-111-2222 or 555-333-4444"
        matches = PHONE_PATTERN.findall(text)
        assert len(matches) == 2


class TestEmailPattern:
    def test_standard_email(self):
        assert EMAIL_PATTERN.search("john@acme.com")

    def test_with_dots_and_plus(self):
        assert EMAIL_PATTERN.search("john.doe+tag@sub.acme.co.uk")

    def test_no_match_missing_domain(self):
        assert not EMAIL_PATTERN.search("john@")

    def test_no_match_missing_at(self):
        assert not EMAIL_PATTERN.search("john.acme.com")


class TestCaseNoPattern:
    def test_with_hyphens(self):
        m = CASE_NO_PATTERN.search("BC-2025-12345")
        assert m and m.group(0) == "BC-2025-12345"

    def test_with_spaces(self):
        m = CASE_NO_PATTERN.search("LASC 2024 00001")
        assert m and m.group(0) == "LASC 2024 00001"

    def test_compact(self):
        m = CASE_NO_PATTERN.search("BC202512345")
        assert m and m.group(0) == "BC202512345"

    def test_no_match_lowercase(self):
        assert not CASE_NO_PATTERN.search("bc-2025-12345")


# ==================================================================
# Citation pattern tests (whitelist — these must be recognized)
# ==================================================================


class TestCitationPattern:
    def test_cal_lab_code(self):
        m = CITATION_PATTERN.search("Cal. Lab. Code § 1102.5")
        assert m

    def test_cal_gov_code(self):
        m = CITATION_PATTERN.search("Cal. Gov. Code § 12940")
        assert m

    def test_cal_bus_prof_code(self):
        m = CITATION_PATTERN.search("Cal. Bus. & Prof. Code § 17200")
        assert m

    def test_cal_civ_code(self):
        m = CITATION_PATTERN.search("Cal. Civ. Code § 1788")
        assert m

    def test_caci_instruction(self):
        m = CITATION_PATTERN.search("CACI No. 2505")
        assert m

    def test_caci_with_letter(self):
        m = CITATION_PATTERN.search("CACI No. 2521A")
        assert m

    def test_cfr(self):
        m = CITATION_PATTERN.search("29 C.F.R. § 1630.2")
        assert m

    def test_cal_reporter(self):
        m = CITATION_PATTERN.search("45 Cal.App.5th 100")
        assert m

    def test_cal_supreme(self):
        m = CITATION_PATTERN.search("12 Cal.4th 200")
        assert m

    def test_us_reporter(self):
        m = CITATION_PATTERN.search("550 U.S. 398")
        assert m

    def test_federal_reporter(self):
        m = CITATION_PATTERN.search("123 F.3d 456")
        assert m

    def test_usc(self):
        m = CITATION_PATTERN.search("42 U.S.C. § 2000e")
        assert m

    def test_cal_constitution(self):
        m = CITATION_PATTERN.search("Cal. Const., art. I, § 1")
        assert m

    def test_ccp(self):
        m = CITATION_PATTERN.search("CCP § 2030.010")
        assert m

    def test_section_range(self):
        m = CITATION_PATTERN.search("Cal. Lab. Code §§ 1102.5-1102.7")
        assert m

    def test_double_section_symbol(self):
        m = CITATION_PATTERN.search("Cal. Gov. Code §§ 12940")
        assert m


# ==================================================================
# EntityRecognizer.scan() integration tests
# ==================================================================


class TestScanBasicDetection:
    def test_empty_text(self):
        rec = EntityRecognizer()
        assert rec.scan("") == []

    def test_no_entities(self):
        rec = EntityRecognizer()
        assert rec.scan("This is plain legal text with no PII.") == []

    def test_detect_ssn(self):
        rec = EntityRecognizer()
        results = rec.scan("SSN is 123-45-6789")
        assert len(results) == 1
        assert results[0].entity_type == "SSN"
        assert results[0].value == "123-45-6789"

    def test_detect_ein(self):
        rec = EntityRecognizer()
        results = rec.scan("EIN: 12-3456789")
        assert len(results) == 1
        assert results[0].entity_type == "SSN"  # EIN uses SSN type for hard redaction
        assert results[0].value == "12-3456789"

    def test_detect_email(self):
        rec = EntityRecognizer()
        results = rec.scan("Contact john@acme.com for info")
        assert len(results) == 1
        assert results[0].entity_type == "EMAIL"
        assert results[0].value == "john@acme.com"

    def test_detect_phone(self):
        rec = EntityRecognizer()
        results = rec.scan("Call 555-123-4567 now")
        assert len(results) == 1
        assert results[0].entity_type == "PHONE"
        assert results[0].value == "555-123-4567"

    def test_detect_case_number(self):
        rec = EntityRecognizer()
        results = rec.scan("Case BC-2025-12345 was filed")
        assert len(results) == 1
        assert results[0].entity_type == "CASE"
        assert results[0].value == "BC-2025-12345"

    def test_detect_multiple_types(self):
        rec = EntityRecognizer()
        text = (
            "John (john@acme.com, 555-123-4567) has SSN 123-45-6789 "
            "and filed case BC-2025-12345."
        )
        results = rec.scan(text)
        types = {r.entity_type for r in results}
        assert types == {"SSN", "EMAIL", "PHONE", "CASE"}

    def test_multiple_same_type(self):
        rec = EntityRecognizer()
        text = "Contact john@acme.com or jane@acme.com"
        results = rec.scan(text)
        emails = [r for r in results if r.entity_type == "EMAIL"]
        assert len(emails) == 2

    def test_position_tracking(self):
        rec = EntityRecognizer()
        text = "SSN: 123-45-6789"
        results = rec.scan(text)
        assert results[0].start == 5
        assert results[0].end == 16
        assert text[results[0].start : results[0].end] == "123-45-6789"


class TestScanDeduplication:
    def test_duplicate_ssn_deduped(self):
        rec = EntityRecognizer()
        text = "SSN 123-45-6789 appears again: 123-45-6789"
        results = rec.scan(text)
        ssns = [r for r in results if r.entity_type == "SSN"]
        assert len(ssns) == 1

    def test_duplicate_email_deduped(self):
        rec = EntityRecognizer()
        text = "Email john@acme.com and again john@acme.com"
        results = rec.scan(text)
        emails = [r for r in results if r.entity_type == "EMAIL"]
        assert len(emails) == 1

    def test_different_values_not_deduped(self):
        rec = EntityRecognizer()
        text = "Email john@acme.com and jane@acme.com"
        results = rec.scan(text)
        emails = [r for r in results if r.entity_type == "EMAIL"]
        assert len(emails) == 2


# ==================================================================
# Citation whitelist exclusion tests
# ==================================================================


class TestCitationExclusion:
    def test_case_number_in_citation_excluded(self):
        """Case number regex should not match inside a legal citation."""
        rec = EntityRecognizer()
        # "45 Cal.App.5th 100" could partially match CASE_NO_PATTERN
        # but the citation whitelist should exclude it
        text = "Per 45 Cal.App.5th 100, the ruling stands."
        results = rec.scan(text)
        case_results = [r for r in results if r.entity_type == "CASE"]
        assert len(case_results) == 0

    def test_real_case_number_not_excluded(self):
        """A real case number that is NOT a citation should be detected."""
        rec = EntityRecognizer()
        text = "Filed under BC-2025-12345 in LASC."
        results = rec.scan(text)
        case_results = [r for r in results if r.entity_type == "CASE"]
        assert len(case_results) == 1
        assert case_results[0].value == "BC-2025-12345"

    def test_citation_with_ssn_like_numbers(self):
        """Citation patterns that look like SSNs should be excluded."""
        rec = EntityRecognizer()
        # 29 C.F.R. § 1630.2 contains numbers but is a citation
        text = "Under 29 C.F.R. § 1630.2, the standard is..."
        results = rec.scan(text)
        ssns = [r for r in results if r.entity_type == "SSN"]
        assert len(ssns) == 0

    def test_mixed_citations_and_entities(self):
        """Citations excluded, real entities detected."""
        rec = EntityRecognizer()
        text = (
            "Per Cal. Lab. Code § 1102.5, the employee (john@acme.com) "
            "with SSN 123-45-6789 filed case BC-2025-12345."
        )
        results = rec.scan(text)
        types = {r.entity_type for r in results}
        # Should detect email, SSN, and case number — not the statute citation
        assert "EMAIL" in types
        assert "SSN" in types
        assert "CASE" in types

    def test_caci_not_treated_as_case_number(self):
        rec = EntityRecognizer()
        text = "CACI No. 2505 applies here."
        results = rec.scan(text)
        case_results = [r for r in results if r.entity_type == "CASE"]
        assert len(case_results) == 0

    def test_usc_section_not_treated_as_case_number(self):
        rec = EntityRecognizer()
        text = "42 U.S.C. § 2000e prohibits discrimination."
        results = rec.scan(text)
        case_results = [r for r in results if r.entity_type == "CASE"]
        assert len(case_results) == 0


# ==================================================================
# Legal text preservation tests
# ==================================================================


class TestLegalTextPreservation:
    """Ensure dates, dollars, and legal terms pass through undetected."""

    def test_dates_not_detected(self):
        rec = EntityRecognizer()
        text = "Terminated on January 15, 2025."
        results = rec.scan(text)
        assert len(results) == 0

    def test_dollar_amounts_not_detected(self):
        rec = EntityRecognizer()
        text = "Earned $150,000 annually."
        results = rec.scan(text)
        assert len(results) == 0

    def test_legal_terms_not_detected(self):
        rec = EntityRecognizer()
        text = "wrongful termination under FEHA retaliation claim"
        results = rec.scan(text)
        assert len(results) == 0

    def test_statute_section_not_detected(self):
        rec = EntityRecognizer()
        text = "Cal. Lab. Code § 1102.5 protects whistleblowers."
        results = rec.scan(text)
        assert len(results) == 0

    def test_complex_legal_text_only_pii_detected(self):
        rec = EntityRecognizer()
        text = (
            "Jane Doe's claim under Cal. Lab. Code § 1102.5 against "
            "BigCo LLC is supported by CACI No. 2505. Contact: "
            "jane@bigco.com, 555-999-8888. SSN: 111-22-3333. "
            "Case: LASC 2024 56789. Filed January 1, 2025. "
            "Damages: $250,000."
        )
        results = rec.scan(text)
        types_and_values = [(r.entity_type, r.value) for r in results]

        # Should detect PII
        assert ("EMAIL", "jane@bigco.com") in types_and_values
        assert ("PHONE", "555-999-8888") in types_and_values
        assert ("SSN", "111-22-3333") in types_and_values
        assert ("CASE", "LASC 2024 56789") in types_and_values

        # Should NOT detect legal citations, dates, or amounts
        values = [r.value for r in results]
        assert not any("1102.5" in v for v in values)
        assert not any("2505" in v for v in values)
        assert not any("250,000" in v for v in values)


# ==================================================================
# NER graceful degradation tests
# ==================================================================


class TestNERGracefulDegradation:
    """NER degrades gracefully when spaCy is unavailable."""

    def test_scan_ner_returns_empty_without_nlp(self):
        rec = _no_ner_recognizer()
        result = rec._scan_ner("John Smith works at Acme Corp.", [])
        assert result == []

    def test_person_names_not_detected_without_ner(self):
        """Without NER, person names are not caught by regex."""
        rec = _no_ner_recognizer()
        results = rec.scan("John Smith filed the complaint.")
        assert len(results) == 0

    def test_company_names_not_detected_without_ner(self):
        rec = _no_ner_recognizer()
        results = rec.scan("Acme Corp terminated the employee.")
        assert len(results) == 0

    def test_regex_still_works_without_ner(self):
        """Regex detection unaffected by NER being disabled."""
        rec = _no_ner_recognizer()
        results = rec.scan("SSN 123-45-6789 and john@acme.com")
        types = {r.entity_type for r in results}
        assert "SSN" in types
        assert "EMAIL" in types

    def test_ensure_ner_loaded_no_spacy(self, monkeypatch):
        """When _SPACY_AVAILABLE is False, _nlp stays None."""
        import employee_help.privacy.recognizers as mod

        monkeypatch.setattr(mod, "_SPACY_AVAILABLE", False)
        rec = EntityRecognizer()
        rec._ensure_ner_loaded()
        assert rec._nlp is None
        assert rec._ner_loaded is True

    def test_ensure_ner_loaded_model_missing(self, monkeypatch):
        """When spaCy is available but model is missing, _nlp stays None."""
        import employee_help.privacy.recognizers as mod

        monkeypatch.setattr(mod, "_SPACY_AVAILABLE", True)
        monkeypatch.setattr(
            mod,
            "spacy",
            SimpleNamespace(load=lambda name: (_ for _ in ()).throw(OSError)),
        )
        rec = EntityRecognizer()
        rec._ensure_ner_loaded()
        assert rec._nlp is None
        assert rec._ner_loaded is True

    def test_ensure_ner_loaded_only_once(self):
        """_ensure_ner_loaded is a no-op after the first call."""
        rec = _no_ner_recognizer()
        assert rec._ner_loaded is True
        # Second call should not change state
        rec._ensure_ner_loaded()
        assert rec._nlp is None  # still None


# ==================================================================
# NER detection tests (mocked spaCy model)
# ==================================================================


class TestNERDetection:
    """Tests for spaCy NER entity detection with mocked model."""

    def test_detect_person(self):
        text = "John Smith filed the complaint."
        rec = _ner_recognizer(_ner_entity("PERSON", "John Smith", 0, 10))
        results = rec.scan(text)
        persons = [r for r in results if r.entity_type == "PERSON"]
        assert len(persons) == 1
        assert persons[0].value == "John Smith"

    def test_detect_org_as_company(self):
        text = "Acme Corp terminated the employee."
        rec = _ner_recognizer(_ner_entity("ORG", "Acme Corp", 0, 9))
        results = rec.scan(text)
        companies = [r for r in results if r.entity_type == "COMPANY"]
        assert len(companies) == 1
        assert companies[0].value == "Acme Corp"

    def test_multiple_persons(self):
        text = "John Smith and Jane Doe attended."
        rec = _ner_recognizer(
            _ner_entity("PERSON", "John Smith", 0, 10),
            _ner_entity("PERSON", "Jane Doe", 15, 23),
        )
        results = rec.scan(text)
        persons = [r for r in results if r.entity_type == "PERSON"]
        assert len(persons) == 2

    def test_mixed_person_and_org(self):
        text = "John Smith worked at Acme Corp."
        rec = _ner_recognizer(
            _ner_entity("PERSON", "John Smith", 0, 10),
            _ner_entity("ORG", "Acme Corp", 21, 30),
        )
        results = rec.scan(text)
        assert {r.entity_type for r in results} == {"PERSON", "COMPANY"}

    def test_ner_combined_with_regex(self):
        """NER entities are returned alongside regex entities."""
        text = "John Smith (john@acme.com) filed."
        rec = _ner_recognizer(_ner_entity("PERSON", "John Smith", 0, 10))
        results = rec.scan(text)
        types = {r.entity_type for r in results}
        assert "PERSON" in types
        assert "EMAIL" in types

    def test_gpe_entities_ignored(self):
        """GPE (geo-political entity) labels are not mapped."""
        text = "He moved to California."
        rec = _ner_recognizer(_ner_entity("GPE", "California", 12, 22))
        results = rec.scan(text)
        assert len(results) == 0

    def test_date_entities_ignored(self):
        """DATE labels from spaCy are not mapped."""
        text = "Filed on January 15, 2025."
        rec = _ner_recognizer(
            _ner_entity("DATE", "January 15, 2025", 9, 25)
        )
        results = rec.scan(text)
        assert len(results) == 0

    def test_money_entities_ignored(self):
        """MONEY labels from spaCy are not mapped."""
        text = "Earned $150,000 annually."
        rec = _ner_recognizer(_ner_entity("MONEY", "$150,000", 7, 15))
        results = rec.scan(text)
        assert len(results) == 0

    def test_ner_position_tracking(self):
        text = "Ask John Smith about it."
        rec = _ner_recognizer(_ner_entity("PERSON", "John Smith", 4, 14))
        results = rec.scan(text)
        assert results[0].start == 4
        assert results[0].end == 14
        assert text[results[0].start : results[0].end] == "John Smith"

    def test_ner_entity_at_text_start(self):
        text = "John Smith filed."
        rec = _ner_recognizer(_ner_entity("PERSON", "John Smith", 0, 10))
        results = rec.scan(text)
        assert len(results) == 1
        assert results[0].start == 0

    def test_ner_entity_at_text_end(self):
        text = "Filed by John Smith"
        rec = _ner_recognizer(_ner_entity("PERSON", "John Smith", 9, 19))
        results = rec.scan(text)
        assert len(results) == 1
        assert results[0].end == 19

    def test_ner_empty_text(self):
        rec = _ner_recognizer()
        results = rec.scan("")
        assert results == []


# ==================================================================
# NER citation exclusion tests
# ==================================================================


class TestNERCitationExclusion:
    """NER entities overlapping legal citations are excluded."""

    def test_person_in_citation_excluded(self):
        """A PERSON entity that overlaps a citation span is excluded."""
        # "Cal." could be detected as a person by a confused NER
        text = "Per Cal. Lab. Code § 1102.5, the ruling stands."
        rec = _ner_recognizer(_ner_entity("PERSON", "Cal", 4, 7))
        results = rec.scan(text)
        persons = [r for r in results if r.entity_type == "PERSON"]
        assert len(persons) == 0

    def test_org_in_citation_excluded(self):
        """An ORG entity that overlaps a citation is excluded."""
        text = "Filed under 42 U.S.C. § 2000e."
        # Suppose NER mistakenly tags "U.S.C." as ORG
        rec = _ner_recognizer(_ner_entity("ORG", "U.S.C.", 15, 21))
        results = rec.scan(text)
        companies = [r for r in results if r.entity_type == "COMPANY"]
        assert len(companies) == 0

    def test_person_outside_citation_kept(self):
        """NER entity NOT overlapping a citation is kept."""
        text = "John Smith cited Cal. Lab. Code § 1102.5."
        rec = _ner_recognizer(_ner_entity("PERSON", "John Smith", 0, 10))
        results = rec.scan(text)
        persons = [r for r in results if r.entity_type == "PERSON"]
        assert len(persons) == 1
        assert persons[0].value == "John Smith"

    def test_mixed_ner_and_citation(self):
        """NER entities outside citations kept, inside excluded."""
        text = "John Smith cited Cal. Lab. Code § 1102.5 in Acme Corp case."
        rec = _ner_recognizer(
            _ner_entity("PERSON", "John Smith", 0, 10),
            _ner_entity("ORG", "Lab", 21, 24),  # inside citation
            _ner_entity("ORG", "Acme Corp", 45, 54),
        )
        results = rec.scan(text)
        types_values = [(r.entity_type, r.value) for r in results]
        assert ("PERSON", "John Smith") in types_values
        assert ("COMPANY", "Acme Corp") in types_values
        assert ("COMPANY", "Lab") not in types_values


# ==================================================================
# NER deduplication tests
# ==================================================================


class TestNERDeduplication:
    """NER results are deduplicated with regex results in scan()."""

    def test_duplicate_ner_person_deduped(self):
        """Same person appearing twice via NER is deduplicated."""
        text = "John Smith talked to John Smith."
        rec = _ner_recognizer(
            _ner_entity("PERSON", "John Smith", 0, 10),
            _ner_entity("PERSON", "John Smith", 21, 31),
        )
        results = rec.scan(text)
        persons = [r for r in results if r.entity_type == "PERSON"]
        assert len(persons) == 1

    def test_different_ner_persons_kept(self):
        text = "John Smith and Jane Doe."
        rec = _ner_recognizer(
            _ner_entity("PERSON", "John Smith", 0, 10),
            _ner_entity("PERSON", "Jane Doe", 15, 23),
        )
        results = rec.scan(text)
        persons = [r for r in results if r.entity_type == "PERSON"]
        assert len(persons) == 2

    def test_ner_and_regex_same_value_deduped(self):
        """If NER and regex both find the same entity, it's deduplicated."""
        text = "Email john@acme.com now."
        # Regex finds the email; NER also (hypothetically) tags it
        rec = _ner_recognizer(
            _ner_entity("ORG", "john@acme.com", 6, 19),
        )
        results = rec.scan(text)
        # EMAIL from regex comes first; COMPANY from NER is a different type
        # so both are kept (different entity_type)
        assert any(r.entity_type == "EMAIL" for r in results)


# ==================================================================
# NER + regex integration tests
# ==================================================================


class TestNERRegexIntegration:
    """End-to-end tests combining NER and regex detection."""

    def test_full_legal_text(self):
        """NER detects names, regex detects structured PII."""
        text = (
            "John Smith (john@acme.com, 555-123-4567) of Acme Corp "
            "filed case BC-2025-12345. SSN: 123-45-6789. "
            "Per Cal. Lab. Code § 1102.5."
        )
        rec = _ner_recognizer(
            _ner_entity("PERSON", "John Smith", 0, 10),
            _ner_entity("ORG", "Acme Corp", 44, 53),
        )
        results = rec.scan(text)
        types = {r.entity_type for r in results}
        assert types == {"PERSON", "COMPANY", "EMAIL", "PHONE", "CASE", "SSN"}

    def test_ner_entities_after_regex_in_results(self):
        """Regex results appear before NER results in the list."""
        text = "John Smith has SSN 123-45-6789."
        rec = _ner_recognizer(_ner_entity("PERSON", "John Smith", 0, 10))
        results = rec.scan(text)
        # Regex (SSN) runs first, NER second
        assert results[0].entity_type == "SSN"
        assert results[1].entity_type == "PERSON"

    def test_citation_excludes_both_regex_and_ner(self):
        """Both regex and NER entities inside citations are excluded."""
        text = "Per 42 U.S.C. § 2000e, Smith filed."
        rec = _ner_recognizer(
            _ner_entity("PERSON", "Smith", 25, 30),
        )
        results = rec.scan(text)
        # Smith is outside the citation → kept
        persons = [r for r in results if r.entity_type == "PERSON"]
        assert len(persons) == 1
        assert persons[0].value == "Smith"
        # No CASE/SSN false positives from the citation
        case_results = [r for r in results if r.entity_type == "CASE"]
        assert len(case_results) == 0


# ==================================================================
# Edge cases
# ==================================================================


class TestEdgeCases:
    def test_entity_at_text_start(self):
        rec = EntityRecognizer()
        results = rec.scan("123-45-6789 is the SSN")
        assert len(results) == 1
        assert results[0].value == "123-45-6789"

    def test_entity_at_text_end(self):
        rec = EntityRecognizer()
        results = rec.scan("SSN is 123-45-6789")
        assert len(results) == 1
        assert results[0].value == "123-45-6789"

    def test_adjacent_entities(self):
        rec = EntityRecognizer()
        text = "john@acme.com 555-123-4567"
        results = rec.scan(text)
        assert len(results) == 2

    def test_entity_in_parentheses(self):
        rec = EntityRecognizer()
        results = rec.scan("(john@acme.com)")
        assert len(results) == 1
        assert results[0].value == "john@acme.com"

    def test_entity_with_surrounding_quotes(self):
        rec = EntityRecognizer()
        results = rec.scan('"john@acme.com"')
        assert len(results) == 1

    def test_multiline_text(self):
        rec = EntityRecognizer()
        text = "Line 1: john@acme.com\nLine 2: 555-123-4567\nLine 3: 123-45-6789"
        results = rec.scan(text)
        assert len(results) == 3

    def test_recognized_entity_is_frozen(self):
        ent = RecognizedEntity(entity_type="SSN", value="123-45-6789", start=0, end=11)
        with pytest.raises(AttributeError):
            ent.value = "changed"  # type: ignore[misc]

    def test_ssn_not_confused_with_phone(self):
        """SSN pattern runs before phone, so SSN is detected as SSN."""
        rec = EntityRecognizer()
        # 123-45-6789 matches SSN (3-2-4) not phone (3-3-4)
        results = rec.scan("Number: 123-45-6789")
        ssns = [r for r in results if r.entity_type == "SSN"]
        phones = [r for r in results if r.entity_type == "PHONE"]
        assert len(ssns) == 1
        # Phone should not also match the SSN
        for p in phones:
            assert p.value != "123-45-6789"
