"""Tests for LITIGAGENT EmailExtractor (L1.7)."""

from __future__ import annotations

import email
import email.mime.multipart
import email.mime.text
import email.mime.base
import email.utils
import mailbox
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from employee_help.casefile.extractors.base import ExtractionResult, FileExtractor
from employee_help.casefile.extractors.email import EmailExtractor


# --- Helpers ---


def _make_eml(
    subject: str = "Test Subject",
    from_addr: str = "sender@example.com",
    to_addr: str = "recipient@example.com",
    cc_addr: str | None = None,
    body: str = "Hello, this is a test email.",
    html_body: str | None = None,
    date: str | None = None,
    attachments: list[tuple[str, bytes]] | None = None,
) -> bytes:
    """Build a minimal .eml in memory and return its bytes."""
    if html_body and not attachments:
        # Multipart alternative (plain + HTML)
        msg = email.mime.multipart.MIMEMultipart("alternative")
        msg.attach(email.mime.text.MIMEText(body, "plain"))
        msg.attach(email.mime.text.MIMEText(html_body, "html"))
    elif attachments:
        msg = email.mime.multipart.MIMEMultipart("mixed")
        msg.attach(email.mime.text.MIMEText(body, "plain"))
        for att_name, att_data in attachments:
            att = email.mime.base.MIMEBase("application", "octet-stream")
            att.set_payload(att_data)
            att.add_header(
                "Content-Disposition", "attachment", filename=att_name
            )
            msg.attach(att)
    else:
        msg = email.mime.text.MIMEText(body, "plain")

    msg["Subject"] = subject
    msg["From"] = from_addr
    msg["To"] = to_addr
    if cc_addr:
        msg["Cc"] = cc_addr
    msg["Date"] = date or email.utils.formatdate(localtime=True)

    return msg.as_bytes()


def _make_mbox(messages: list[dict]) -> bytes:
    """Build a minimal .mbox archive in memory and return its bytes."""
    with tempfile.NamedTemporaryFile(suffix=".mbox", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        mbox = mailbox.mbox(tmp_path)
        for msg_data in messages:
            eml_bytes = _make_eml(**msg_data)
            parsed = email.message_from_bytes(eml_bytes)
            mbox.add(parsed)
        mbox.close()
        return Path(tmp_path).read_bytes()
    finally:
        Path(tmp_path).unlink(missing_ok=True)


# --- Interface tests ---


class TestEmailExtractorInterface:
    def test_can_extract_eml_extension(self):
        assert EmailExtractor().can_extract("application/octet-stream", "eml") is True

    def test_can_extract_msg_extension(self):
        assert EmailExtractor().can_extract("application/octet-stream", "msg") is True

    def test_can_extract_mbox_extension(self):
        assert EmailExtractor().can_extract("application/octet-stream", "mbox") is True

    def test_can_extract_by_mime_rfc822(self):
        assert EmailExtractor().can_extract("message/rfc822", "unknown") is True

    def test_can_extract_by_mime_ms_outlook(self):
        assert EmailExtractor().can_extract("application/vnd.ms-outlook", "unknown") is True

    def test_can_extract_by_mime_x_msg(self):
        assert EmailExtractor().can_extract("application/x-msg", "unknown") is True

    def test_can_extract_by_mime_mbox(self):
        assert EmailExtractor().can_extract("application/mbox", "unknown") is True

    def test_cannot_extract_other(self):
        ext = EmailExtractor()
        assert ext.can_extract("application/pdf", "pdf") is False
        assert ext.can_extract("text/plain", "txt") is False
        assert ext.can_extract("application/msword", "doc") is False
        assert ext.can_extract("image/png", "png") is False

    def test_supported_extensions(self):
        assert EmailExtractor().supported_extensions == {"eml", "msg", "mbox"}

    def test_isinstance_file_extractor(self):
        assert isinstance(EmailExtractor(), FileExtractor)


# --- EML extraction ---


class TestEmlExtraction:
    def test_simple_email(self):
        data = _make_eml()
        result = EmailExtractor().extract(data, "test.eml")

        assert isinstance(result, ExtractionResult)
        assert result.metadata["extractor"] == "email"
        assert result.metadata["format"] == "eml"
        assert result.warnings == []
        assert "Test Subject" in result.text
        assert "sender@example.com" in result.text
        assert "recipient@example.com" in result.text
        assert "Hello, this is a test email." in result.text

    def test_subject_in_headers(self):
        data = _make_eml(subject="Important Legal Notice")
        result = EmailExtractor().extract(data, "notice.eml")

        assert "Subject: Important Legal Notice" in result.text

    def test_from_in_headers(self):
        data = _make_eml(from_addr="attorney@lawfirm.com")
        result = EmailExtractor().extract(data, "legal.eml")

        assert "From: attorney@lawfirm.com" in result.text

    def test_to_in_headers(self):
        data = _make_eml(to_addr="client@company.com")
        result = EmailExtractor().extract(data, "reply.eml")

        assert "To: client@company.com" in result.text

    def test_cc_in_headers(self):
        data = _make_eml(cc_addr="cc@example.com")
        result = EmailExtractor().extract(data, "cc.eml")

        assert "Cc: cc@example.com" in result.text

    def test_date_in_headers(self):
        data = _make_eml(date="Mon, 01 Jan 2026 10:00:00 -0800")
        result = EmailExtractor().extract(data, "dated.eml")

        assert "Date:" in result.text
        assert "2026" in result.text

    def test_body_text(self):
        body = "This is a detailed email body with multiple sentences. It discusses employment matters."
        data = _make_eml(body=body)
        result = EmailExtractor().extract(data, "body.eml")

        assert body in result.text

    def test_multiline_body(self):
        body = "Line 1\nLine 2\nLine 3"
        data = _make_eml(body=body)
        result = EmailExtractor().extract(data, "multi.eml")

        assert "Line 1" in result.text
        assert "Line 2" in result.text
        assert "Line 3" in result.text

    def test_html_only_fallback(self):
        # Build an email with only HTML content
        msg = email.mime.text.MIMEText(
            "<html><body><p>HTML only content</p></body></html>", "html"
        )
        msg["Subject"] = "HTML Email"
        msg["From"] = "sender@example.com"
        msg["To"] = "recipient@example.com"
        data = msg.as_bytes()
        result = EmailExtractor().extract(data, "html.eml")

        assert "HTML only content" in result.text

    def test_multipart_prefers_plain_text(self):
        data = _make_eml(
            body="Plain text version",
            html_body="<html><body><p>HTML version</p></body></html>",
        )
        result = EmailExtractor().extract(data, "multipart.eml")

        assert "Plain text version" in result.text

    def test_attachment_listed(self):
        data = _make_eml(
            attachments=[("document.pdf", b"fake pdf content")]
        )
        result = EmailExtractor().extract(data, "with_att.eml")

        assert "Attachments:" in result.text
        assert "document.pdf" in result.text

    def test_multiple_attachments_listed(self):
        data = _make_eml(
            attachments=[
                ("report.pdf", b"pdf"),
                ("spreadsheet.xlsx", b"xlsx"),
            ]
        )
        result = EmailExtractor().extract(data, "multi_att.eml")

        assert "report.pdf" in result.text
        assert "spreadsheet.xlsx" in result.text

    def test_unicode_subject(self):
        data = _make_eml(subject="Re: Café résumé — urgent")
        result = EmailExtractor().extract(data, "unicode.eml")

        assert "Café" in result.text
        assert "résumé" in result.text

    def test_empty_email(self):
        msg = email.mime.text.MIMEText("", "plain")
        msg["Subject"] = ""
        msg["From"] = ""
        msg["To"] = ""
        data = msg.as_bytes()
        result = EmailExtractor().extract(data, "empty.eml")

        assert any("No text extracted" in w for w in result.warnings)

    def test_invalid_eml_bytes(self):
        result = EmailExtractor().extract(b"\x00\x01\x02", "bad.eml")

        # stdlib email parser is lenient — it may parse garbage without error
        # but should still return an ExtractionResult
        assert isinstance(result, ExtractionResult)
        assert result.metadata["format"] == "eml"


# --- MSG extraction ---


class TestMsgExtraction:
    def test_msg_without_extract_msg_installed(self):
        with patch("employee_help.casefile.extractors.email.extract_msg", None):
            result = EmailExtractor().extract(b"fake msg", "test.msg")

        assert result.text == ""
        assert any("extract-msg not installed" in w for w in result.warnings)
        assert result.metadata["format"] == "msg"

    def test_msg_invalid_bytes(self):
        # If extract_msg is available, it should handle invalid input gracefully
        try:
            import extract_msg as _em  # noqa: F401
        except ImportError:
            pytest.skip("extract-msg not installed")

        result = EmailExtractor().extract(b"not a valid msg file", "bad.msg")

        assert result.text == ""
        assert any("Failed to parse" in w for w in result.warnings)
        assert result.metadata["format"] == "msg"

    def test_msg_returns_extraction_result(self):
        # Even without extract-msg, should return ExtractionResult
        result = EmailExtractor().extract(b"fake", "test.msg")
        assert isinstance(result, ExtractionResult)


# --- MBOX extraction ---


class TestMboxExtraction:
    def test_single_message_mbox(self):
        data = _make_mbox([
            {"subject": "First Email", "body": "Content of first email."},
        ])
        result = EmailExtractor().extract(data, "archive.mbox")

        assert isinstance(result, ExtractionResult)
        assert result.metadata["format"] == "mbox"
        assert result.metadata["message_count"] == 1
        assert "First Email" in result.text
        assert "Content of first email." in result.text

    def test_multiple_messages_mbox(self):
        data = _make_mbox([
            {"subject": "Email One", "body": "Body one."},
            {"subject": "Email Two", "body": "Body two."},
            {"subject": "Email Three", "body": "Body three."},
        ])
        result = EmailExtractor().extract(data, "archive.mbox")

        assert result.metadata["message_count"] == 3
        assert "Email One" in result.text
        assert "Email Two" in result.text
        assert "Email Three" in result.text
        assert "Body one." in result.text
        assert "Body three." in result.text

    def test_mbox_messages_separated(self):
        data = _make_mbox([
            {"subject": "First", "body": "Content A"},
            {"subject": "Second", "body": "Content B"},
        ])
        result = EmailExtractor().extract(data, "archive.mbox")

        # Messages should be separated by a horizontal rule
        assert "---" in result.text

    def test_empty_mbox(self):
        # Create an empty mbox file
        with tempfile.NamedTemporaryFile(suffix=".mbox", delete=False) as tmp:
            tmp_path = tmp.name
        try:
            mbox = mailbox.mbox(tmp_path)
            mbox.close()
            data = Path(tmp_path).read_bytes()
        finally:
            Path(tmp_path).unlink(missing_ok=True)

        result = EmailExtractor().extract(data, "empty.mbox")

        assert any("No text extracted" in w for w in result.warnings)
        assert result.metadata["format"] == "mbox"

    def test_mbox_invalid_bytes(self):
        # mbox parser is lenient with malformed content — test graceful handling
        result = EmailExtractor().extract(b"\x00\x01\x02\x03", "bad.mbox")

        assert isinstance(result, ExtractionResult)
        assert result.metadata["format"] == "mbox"


# --- Format routing ---


class TestFormatRouting:
    def test_eml_extension_routes_to_eml(self):
        data = _make_eml(subject="EML Test")
        result = EmailExtractor().extract(data, "test.eml")

        assert result.metadata["format"] == "eml"
        assert "EML Test" in result.text

    def test_msg_extension_routes_to_msg(self):
        result = EmailExtractor().extract(b"fake", "test.msg")
        assert result.metadata["format"] == "msg"

    def test_mbox_extension_routes_to_mbox(self):
        result = EmailExtractor().extract(b"", "test.mbox")
        assert result.metadata["format"] == "mbox"

    def test_unknown_extension_defaults_to_eml(self):
        data = _make_eml(subject="Fallback")
        result = EmailExtractor().extract(data, "test.email")

        assert result.metadata["format"] == "eml"

    def test_uppercase_extension(self):
        data = _make_eml(subject="Upper")
        result = EmailExtractor().extract(data, "test.EML")

        assert result.metadata["format"] == "eml"
        assert "Upper" in result.text


# --- HTML stripping ---


class TestHtmlStripping:
    def test_strip_p_tags(self):
        html_email = email.mime.text.MIMEText(
            "<p>Paragraph one</p><p>Paragraph two</p>", "html"
        )
        html_email["Subject"] = "HTML"
        html_email["From"] = "a@b.com"
        html_email["To"] = "c@d.com"
        result = EmailExtractor().extract(html_email.as_bytes(), "html.eml")

        assert "Paragraph one" in result.text
        assert "Paragraph two" in result.text

    def test_strip_br_tags(self):
        html_email = email.mime.text.MIMEText(
            "Line one<br>Line two<br/>Line three", "html"
        )
        html_email["Subject"] = "BR"
        html_email["From"] = "a@b.com"
        html_email["To"] = "c@d.com"
        result = EmailExtractor().extract(html_email.as_bytes(), "br.eml")

        assert "Line one" in result.text
        assert "Line two" in result.text
        assert "Line three" in result.text

    def test_strip_style_blocks(self):
        html_email = email.mime.text.MIMEText(
            "<style>body{color:red}</style><p>Visible text</p>", "html"
        )
        html_email["Subject"] = "Style"
        html_email["From"] = "a@b.com"
        html_email["To"] = "c@d.com"
        result = EmailExtractor().extract(html_email.as_bytes(), "style.eml")

        assert "Visible text" in result.text
        assert "color:red" not in result.text


# --- Edge cases ---


class TestEmailEdgeCases:
    def test_returns_extraction_result(self):
        data = _make_eml()
        result = EmailExtractor().extract(data, "test.eml")
        assert isinstance(result, ExtractionResult)

    def test_very_long_body(self):
        body = "A" * 100_000
        data = _make_eml(body=body)
        result = EmailExtractor().extract(data, "large.eml")

        assert len(result.text) >= 100_000
        assert result.warnings == []

    def test_no_subject(self):
        msg = email.mime.text.MIMEText("Body text", "plain")
        msg["From"] = "a@b.com"
        msg["To"] = "c@d.com"
        data = msg.as_bytes()
        result = EmailExtractor().extract(data, "no_subj.eml")

        assert "Body text" in result.text
        assert "Subject:" not in result.text

    def test_multiple_to_recipients(self):
        data = _make_eml(to_addr="a@b.com, c@d.com, e@f.com")
        result = EmailExtractor().extract(data, "multi_to.eml")

        assert "a@b.com" in result.text
        assert "c@d.com" in result.text
        assert "e@f.com" in result.text
