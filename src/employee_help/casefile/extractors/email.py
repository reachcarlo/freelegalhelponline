"""EmailExtractor — text extraction from email files (.eml, .msg, .mbox)."""

from __future__ import annotations

import email
import email.policy
import email.utils
import io
import mailbox
import tempfile
from email.message import EmailMessage
from pathlib import Path

from employee_help.casefile.extractors.base import ExtractionResult, FileExtractor

try:
    import extract_msg  # type: ignore[import-untyped]
except ImportError:
    extract_msg = None  # type: ignore[assignment]

_SUPPORTED_EXTENSIONS = {"eml", "msg", "mbox"}

_SUPPORTED_MIMES = {
    "message/rfc822",
    "application/vnd.ms-outlook",
    "application/x-msg",
    "application/mbox",
}


class EmailExtractor(FileExtractor):
    """Extract text from email files (.eml, .msg, .mbox).

    Supports:
    - EML: Standard RFC 2822 format (Gmail, Thunderbird, Apple Mail, Outlook export)
    - MSG: Microsoft Outlook proprietary format (requires extract-msg)
    - MBOX: Mailbox archive format (Gmail Takeout)
    """

    def can_extract(self, mime_type: str, extension: str) -> bool:
        return extension in _SUPPORTED_EXTENSIONS or mime_type in _SUPPORTED_MIMES

    @property
    def supported_extensions(self) -> set[str]:
        return set(_SUPPORTED_EXTENSIONS)

    def extract(self, file_bytes: bytes, filename: str) -> ExtractionResult:
        ext = Path(filename).suffix.lower().lstrip(".")

        if ext == "msg":
            return self._extract_msg(file_bytes, filename)
        if ext == "mbox":
            return self._extract_mbox(file_bytes, filename)
        # Default to EML (covers .eml and unknown extensions with matching MIME)
        return self._extract_eml(file_bytes, filename)

    def _extract_eml(self, file_bytes: bytes, filename: str) -> ExtractionResult:
        """Extract text from a standard RFC 2822 .eml file."""
        warnings: list[str] = []

        try:
            msg = email.message_from_bytes(
                file_bytes, policy=email.policy.default
            )
        except Exception as exc:
            return ExtractionResult(
                text="",
                metadata={"extractor": "email", "format": "eml"},
                warnings=[f"Failed to parse email: {exc}"],
            )

        text = self._format_email_message(msg, warnings)

        if not text.strip():
            warnings.append("No text extracted from document")

        return ExtractionResult(
            text=text,
            metadata={"extractor": "email", "format": "eml"},
            warnings=warnings,
        )

    def _extract_msg(self, file_bytes: bytes, filename: str) -> ExtractionResult:
        """Extract text from an Outlook .msg file."""
        warnings: list[str] = []

        if extract_msg is None:
            return ExtractionResult(
                text="",
                metadata={"extractor": "email", "format": "msg"},
                warnings=[
                    "extract-msg not installed — cannot read .msg files. "
                    "Install with: pip install 'employee-help[casefile]'"
                ],
            )

        try:
            msg = extract_msg.Message(io.BytesIO(file_bytes))
        except Exception as exc:
            return ExtractionResult(
                text="",
                metadata={"extractor": "email", "format": "msg"},
                warnings=[f"Failed to parse .msg file: {exc}"],
            )

        try:
            parts: list[str] = []

            # Header block
            header_lines: list[str] = []
            if msg.subject:
                header_lines.append(f"Subject: {msg.subject}")
            if msg.sender:
                header_lines.append(f"From: {msg.sender}")
            if msg.to:
                header_lines.append(f"To: {msg.to}")
            if msg.cc:
                header_lines.append(f"Cc: {msg.cc}")
            if msg.date:
                header_lines.append(f"Date: {msg.date}")

            if header_lines:
                parts.append("\n".join(header_lines))

            # Body
            body = (msg.body or "").strip()
            if body:
                parts.append(body)

            # Attachment listing
            attachments = msg.attachments or []
            if attachments:
                att_names = []
                for att in attachments:
                    name = getattr(att, "longFilename", None) or getattr(
                        att, "shortFilename", None
                    )
                    if name:
                        att_names.append(name)
                if att_names:
                    parts.append(
                        "Attachments: " + ", ".join(att_names)
                    )

            text = "\n\n".join(parts)
        finally:
            msg.close()

        if not text.strip():
            warnings.append("No text extracted from document")

        return ExtractionResult(
            text=text,
            metadata={
                "extractor": "email",
                "format": "msg",
            },
            warnings=warnings,
        )

    def _extract_mbox(self, file_bytes: bytes, filename: str) -> ExtractionResult:
        """Extract text from an mbox archive (e.g. Gmail Takeout)."""
        warnings: list[str] = []
        messages: list[str] = []

        # mailbox.mbox requires a file path — write to a temp file
        try:
            with tempfile.NamedTemporaryFile(suffix=".mbox", delete=False) as tmp:
                tmp.write(file_bytes)
                tmp_path = tmp.name

            mbox = mailbox.mbox(tmp_path)
            for i, msg in enumerate(mbox):
                # Convert to EmailMessage for consistent parsing
                raw = msg.as_bytes()
                parsed = email.message_from_bytes(
                    raw, policy=email.policy.default
                )
                msg_text = self._format_email_message(parsed, warnings)
                if msg_text.strip():
                    messages.append(msg_text)

            mbox.close()
        except Exception as exc:
            return ExtractionResult(
                text="",
                metadata={"extractor": "email", "format": "mbox"},
                warnings=[f"Failed to parse mbox archive: {exc}"],
            )
        finally:
            Path(tmp_path).unlink(missing_ok=True)

        if not messages:
            warnings.append("No text extracted from document")

        separator = "\n\n---\n\n"
        text = separator.join(messages)

        return ExtractionResult(
            text=text,
            metadata={
                "extractor": "email",
                "format": "mbox",
                "message_count": len(messages),
            },
            warnings=warnings,
        )

    def _format_email_message(
        self, msg: EmailMessage, warnings: list[str]
    ) -> str:
        """Format a parsed EmailMessage into structured text."""
        parts: list[str] = []

        # Header block
        header_lines: list[str] = []
        subject = msg.get("Subject", "")
        if subject:
            header_lines.append(f"Subject: {subject}")

        from_addr = msg.get("From", "")
        if from_addr:
            header_lines.append(f"From: {from_addr}")

        to_addr = msg.get("To", "")
        if to_addr:
            header_lines.append(f"To: {to_addr}")

        cc_addr = msg.get("Cc", "")
        if cc_addr:
            header_lines.append(f"Cc: {cc_addr}")

        date = msg.get("Date", "")
        if date:
            header_lines.append(f"Date: {date}")

        if header_lines:
            parts.append("\n".join(header_lines))

        # Body — prefer plain text, fall back to HTML stripped of tags
        body = self._get_body_text(msg)
        if body:
            parts.append(body)

        # Attachment listing
        att_names: list[str] = []
        for part in msg.walk():
            disp = part.get_content_disposition()
            if disp == "attachment":
                name = part.get_filename()
                if name:
                    att_names.append(name)
        if att_names:
            parts.append("Attachments: " + ", ".join(att_names))

        return "\n\n".join(parts)

    def _get_body_text(self, msg: EmailMessage) -> str:
        """Extract body text from an EmailMessage, preferring plain text."""
        # Try plain text first
        body = msg.get_body(preferencelist=("plain",))
        if body is not None:
            content = body.get_content()
            if isinstance(content, str):
                return content.strip()

        # Fall back to HTML (strip tags)
        body = msg.get_body(preferencelist=("html",))
        if body is not None:
            content = body.get_content()
            if isinstance(content, str):
                return self._strip_html(content).strip()

        return ""

    @staticmethod
    def _strip_html(html: str) -> str:
        """Minimal HTML tag stripping for email body fallback."""
        import re

        # Remove style/script blocks
        text = re.sub(r"<(style|script)[^>]*>.*?</\1>", "", html, flags=re.DOTALL | re.IGNORECASE)
        # Replace <br> and <p> with newlines
        text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
        text = re.sub(r"</?p[^>]*>", "\n", text, flags=re.IGNORECASE)
        # Remove remaining tags
        text = re.sub(r"<[^>]+>", "", text)
        # Collapse multiple blank lines
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text
