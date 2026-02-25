"""Tests for the HTML content extractor."""

import pytest

from employee_help.scraper.extractors.html import extract_html


@pytest.fixture
def sample_crd_html() -> str:
    """Sample HTML mimicking the CRD Divi-based page structure."""
    return """
    <html>
    <head><title>Employment | CRD</title></head>
    <body>
        <header id="main-header">
            <nav id="top-menu-nav"><a href="/">Home</a></nav>
        </header>

        <div id="et-main-area">
            <div class="et_pb_section">
                <div class="et_pb_row">
                    <div class="et_pb_text_inner">
                        <h1>Employment Discrimination</h1>
                        <p>The Civil Rights Department (CRD) is responsible for enforcing
                        state laws that make it illegal to discriminate.</p>
                    </div>
                </div>
                <div class="et_pb_row">
                    <div class="et_pb_text_inner">
                        <h2>Protected Characteristics</h2>
                        <p>California law protects individuals from illegal discrimination
                        by employers based on the following:</p>
                        <ul>
                            <li>Race, color</li>
                            <li>Ancestry, national origin</li>
                            <li>Religion, creed</li>
                            <li>Age (40 and over)</li>
                            <li>Disability (mental and physical)</li>
                        </ul>
                    </div>
                </div>
                <div class="et_pb_row">
                    <div class="et_pb_text_inner">
                        <h2>FAQ</h2>
                    </div>
                    <!-- Accordion pattern from CRD -->
                    <div class="js-accordion">
                        <h2>Who is covered by FEHA?</h2>
                        <div class="js-accordion__panel">
                            <p>The FEHA applies to public and private employers,
                            labor organizations, and employment agencies.</p>
                            <p>An employer can be one or more individuals, partnerships,
                            corporations, or companies.</p>
                        </div>
                        <h2>What are the time limits?</h2>
                        <div class="js-accordion__panel">
                            <p>In general, a complaint must be filed within three years
                            from the date an alleged discriminatory act occurred.</p>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <footer id="main-footer">
            <div id="footer-widgets">Footer content</div>
            <div id="footer-info">Copyright info</div>
        </footer>
    </body>
    </html>
    """


class TestHtmlExtraction:
    def test_extracts_title(self, sample_crd_html: str) -> None:
        result = extract_html(sample_crd_html, "https://calcivilrights.ca.gov/employment/")
        assert result.title == "Employment"

    def test_strips_navigation(self, sample_crd_html: str) -> None:
        result = extract_html(sample_crd_html, "https://calcivilrights.ca.gov/employment/")
        assert "Home" not in result.markdown  # Nav link removed
        assert "top-menu" not in result.markdown

    def test_strips_footer(self, sample_crd_html: str) -> None:
        result = extract_html(sample_crd_html, "https://calcivilrights.ca.gov/employment/")
        assert "Footer content" not in result.markdown
        assert "Copyright info" not in result.markdown

    def test_preserves_headings(self, sample_crd_html: str) -> None:
        result = extract_html(sample_crd_html, "https://calcivilrights.ca.gov/employment/")
        assert "# Employment Discrimination" in result.markdown
        assert "## Protected Characteristics" in result.markdown
        assert "## FAQ" in result.markdown

    def test_preserves_lists(self, sample_crd_html: str) -> None:
        result = extract_html(sample_crd_html, "https://calcivilrights.ca.gov/employment/")
        assert "- Race, color" in result.markdown
        assert "- Ancestry, national origin" in result.markdown
        assert "- Age (40 and over)" in result.markdown

    def test_preserves_paragraph_text(self, sample_crd_html: str) -> None:
        result = extract_html(sample_crd_html, "https://calcivilrights.ca.gov/employment/")
        assert "Civil Rights Department" in result.markdown
        assert "illegal to discriminate" in result.markdown

    def test_extracts_accordion_content(self, sample_crd_html: str) -> None:
        result = extract_html(sample_crd_html, "https://calcivilrights.ca.gov/employment/")
        assert "FEHA applies to public and private employers" in result.markdown
        assert "three years" in result.markdown

    def test_captures_headings_list(self, sample_crd_html: str) -> None:
        result = extract_html(sample_crd_html, "https://calcivilrights.ca.gov/employment/")
        assert "Employment Discrimination" in result.headings
        assert "Protected Characteristics" in result.headings

    def test_sets_source_url(self, sample_crd_html: str) -> None:
        url = "https://calcivilrights.ca.gov/employment/"
        result = extract_html(sample_crd_html, url)
        assert result.source_url == url

    def test_handles_empty_main_content(self) -> None:
        html = "<html><head><title>Empty</title></head><body></body></html>"
        result = extract_html(html, "https://example.com")
        assert result.title == "Empty"
        assert result.markdown == ""

    def test_strips_skip_to_content(self) -> None:
        html = """<html><body>
            <div id="et-main-area">
                <a href="#main">Skip to Main Content</a>
                <h1>Title</h1>
                <p>Content here.</p>
            </div>
        </body></html>"""
        result = extract_html(html, "https://example.com")
        assert "Skip to" not in result.markdown
        assert "Content here" in result.markdown

    def test_handles_table(self) -> None:
        html = """<html><body>
            <div id="et-main-area">
                <h2>Leave Requirements</h2>
                <table>
                    <tr><th>Leave Type</th><th>Duration</th></tr>
                    <tr><td>PDL</td><td>4 months</td></tr>
                    <tr><td>CFRA</td><td>12 weeks</td></tr>
                </table>
            </div>
        </body></html>"""
        result = extract_html(html, "https://example.com")
        assert "Leave Type" in result.markdown
        assert "PDL" in result.markdown
        assert "4 months" in result.markdown
