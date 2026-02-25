"""Tests for the crawler URL classification and link discovery."""

import pytest

from employee_help.scraper.crawler import (
    UrlClassification,
    classify_url,
    discover_links,
    normalize_url,
)

# Default scope rules matching the CRD employment content
ALLOWLIST = [
    r"calcivilrights\.ca\.gov/employment",
    r"calcivilrights\.ca\.gov/complaintprocess",
    r"calcivilrights\.ca\.gov/Posters",
    r"calcivilrights\.ca\.gov/wp-content/uploads/sites/32/.*\.pdf",
]

BLOCKLIST = [
    r"calcivilrights\.ca\.gov/housing",
    r"calcivilrights\.ca\.gov/hate-violence",
    r"calcivilrights\.ca\.gov/wp-content/uploads.*_(SP|ARABIC|CHINESE|KOREAN|HMONG|TAGALOG|VIETNAMESE|PUNJABI|MIXTECO|CH|K|VT|TG|ES)\.",
    r"calcivilrights\.ca\.gov/wp-content/uploads.*-Annual-Report",
]


class TestClassifyUrl:
    def test_main_employment_page(self) -> None:
        url = "https://calcivilrights.ca.gov/employment/"
        assert classify_url(url, ALLOWLIST, BLOCKLIST) == UrlClassification.IN_SCOPE

    def test_employer_resources(self) -> None:
        url = "https://calcivilrights.ca.gov/employment/employerResources"
        assert classify_url(url, ALLOWLIST, BLOCKLIST) == UrlClassification.IN_SCOPE

    def test_pdl_bonding_guide(self) -> None:
        url = "https://calcivilrights.ca.gov/employment/pdl-bonding-guide/"
        assert classify_url(url, ALLOWLIST, BLOCKLIST) == UrlClassification.IN_SCOPE

    def test_complaint_process(self) -> None:
        url = "https://calcivilrights.ca.gov/complaintprocess/"
        assert classify_url(url, ALLOWLIST, BLOCKLIST) == UrlClassification.IN_SCOPE

    def test_posters_page(self) -> None:
        url = "https://calcivilrights.ca.gov/Posters/?openTab=2"
        assert classify_url(url, ALLOWLIST, BLOCKLIST) == UrlClassification.IN_SCOPE

    def test_english_pdf_in_scope(self) -> None:
        url = "https://calcivilrights.ca.gov/wp-content/uploads/sites/32/2025/05/Age-Discrimination-in-Employment_ENG_2025.pdf"
        assert classify_url(url, ALLOWLIST, BLOCKLIST) == UrlClassification.PDF_DOWNLOAD

    def test_english_factsheet_pdf(self) -> None:
        url = "https://calcivilrights.ca.gov/wp-content/uploads/sites/32/2022/12/Pregnancy-Disability-Leave-Fact-Sheet_ENG.pdf"
        assert classify_url(url, ALLOWLIST, BLOCKLIST) == UrlClassification.PDF_DOWNLOAD

    def test_spanish_pdf_blocked(self) -> None:
        url = "https://calcivilrights.ca.gov/wp-content/uploads/sites/32/2022/12/Pregnancy-Disability-Leave-Fact-Sheet_SP.pdf"
        assert classify_url(url, ALLOWLIST, BLOCKLIST) == UrlClassification.OUT_OF_SCOPE

    def test_chinese_pdf_blocked(self) -> None:
        url = "https://calcivilrights.ca.gov/wp-content/uploads/sites/32/2020/10/Immigration-Rights-Fact-Sheet_CHINESE.pdf"
        assert classify_url(url, ALLOWLIST, BLOCKLIST) == UrlClassification.OUT_OF_SCOPE

    def test_housing_page_blocked(self) -> None:
        url = "https://calcivilrights.ca.gov/housing/"
        assert classify_url(url, ALLOWLIST, BLOCKLIST) == UrlClassification.OUT_OF_SCOPE

    def test_hate_violence_blocked(self) -> None:
        url = "https://calcivilrights.ca.gov/hate-violence/"
        assert classify_url(url, ALLOWLIST, BLOCKLIST) == UrlClassification.OUT_OF_SCOPE

    def test_annual_report_pdf_blocked(self) -> None:
        url = "https://calcivilrights.ca.gov/wp-content/uploads/sites/32/2024/06/CRD-2022-Annual-Report.pdf"
        assert classify_url(url, ALLOWLIST, BLOCKLIST) == UrlClassification.OUT_OF_SCOPE

    def test_unrelated_external_url(self) -> None:
        url = "https://www.google.com/"
        assert classify_url(url, ALLOWLIST, BLOCKLIST) == UrlClassification.OUT_OF_SCOPE

    def test_crd_homepage_out_of_scope(self) -> None:
        """The CRD homepage itself is not in our employment-focused scope."""
        url = "https://calcivilrights.ca.gov/"
        assert classify_url(url, ALLOWLIST, BLOCKLIST) == UrlClassification.OUT_OF_SCOPE

    def test_url_with_fragment_normalized(self) -> None:
        url = "https://calcivilrights.ca.gov/employment/#main-content"
        assert classify_url(url, ALLOWLIST, BLOCKLIST) == UrlClassification.IN_SCOPE


class TestNormalizeUrl:
    def test_removes_fragment(self) -> None:
        url = "https://calcivilrights.ca.gov/employment/#section1"
        assert normalize_url(url) == "https://calcivilrights.ca.gov/employment/"

    def test_lowercases_host(self) -> None:
        url = "https://CalCivilRights.CA.GOV/employment/"
        assert normalize_url(url) == "https://calcivilrights.ca.gov/employment/"

    def test_preserves_query_params(self) -> None:
        url = "https://calcivilrights.ca.gov/Posters/?openTab=2"
        assert normalize_url(url) == "https://calcivilrights.ca.gov/Posters/?openTab=2"

    def test_preserves_path(self) -> None:
        url = "https://calcivilrights.ca.gov/employment/employerResources"
        assert normalize_url(url) == "https://calcivilrights.ca.gov/employment/employerResources"


class TestDiscoverLinks:
    def test_extracts_absolute_links(self) -> None:
        html = '<html><body><a href="https://calcivilrights.ca.gov/employment/">Link</a></body></html>'
        links = discover_links(html, "https://calcivilrights.ca.gov/")
        assert "https://calcivilrights.ca.gov/employment/" in links

    def test_resolves_relative_links(self) -> None:
        html = '<html><body><a href="/employment/employerResources">Link</a></body></html>'
        links = discover_links(html, "https://calcivilrights.ca.gov/employment/")
        assert "https://calcivilrights.ca.gov/employment/employerResources" in links

    def test_skips_javascript_links(self) -> None:
        html = '<html><body><a href="javascript:void(0)">No</a></body></html>'
        links = discover_links(html, "https://calcivilrights.ca.gov/")
        assert len(links) == 0

    def test_skips_mailto_links(self) -> None:
        html = '<html><body><a href="mailto:test@example.com">Email</a></body></html>'
        links = discover_links(html, "https://calcivilrights.ca.gov/")
        assert len(links) == 0

    def test_deduplicates_links(self) -> None:
        html = """<html><body>
            <a href="https://calcivilrights.ca.gov/employment/">A</a>
            <a href="https://calcivilrights.ca.gov/employment/">B</a>
        </body></html>"""
        links = discover_links(html, "https://calcivilrights.ca.gov/")
        employment_links = [l for l in links if "/employment/" in l]
        assert len(employment_links) == 1

    def test_detects_pdf_links(self) -> None:
        html = '<html><body><a href="/wp-content/uploads/test.pdf">PDF</a></body></html>'
        links = discover_links(html, "https://calcivilrights.ca.gov/")
        pdf_links = [l for l in links if l.endswith(".pdf")]
        assert len(pdf_links) == 1
