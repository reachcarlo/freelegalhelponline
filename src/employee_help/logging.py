"""Structlog processors for PII redaction (A3.4).

Rules:
- Never log email addresses, display names, or file names in application logs.
- user_id (UUID) is safe — it's an opaque identifier.
- IP addresses are redacted in application logs (kept in audit_log DB table).
- The audit_log table is the single source of truth for security-sensitive
  data (IP, user-agent). Application logs get sanitised copies.
"""

from __future__ import annotations

import re

# Matches most email addresses
_EMAIL_RE = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")

# Keys whose values must be fully redacted
_REDACT_KEYS = frozenset({
    "email",
    "filename",
    "file_name",
    "display_name",
    "name",
    "user_agent",
    "ip_address",
    "ip",
    "client_ip",
    "remote_addr",
})

# Keys that are safe even if they look like _REDACT_KEYS
_SAFE_KEYS = frozenset({
    "provider_name",   # "google" / "microsoft" — not a person's name
    "source_name",     # source registry key
    "model_name",      # LLM model identifier
    "table_name",      # DB table name
    "event_name",      # structlog event key
})

_REDACTED = "[REDACTED]"


def redact_pii(
    logger: object,
    method_name: str,
    event_dict: dict,
) -> dict:
    """Structlog processor that strips PII from log event dicts.

    Applied as a processor in structlog's chain so every log call is
    automatically sanitised before output.
    """
    for key in list(event_dict.keys()):
        if key in _SAFE_KEYS:
            continue

        # Redact known PII keys
        if key in _REDACT_KEYS:
            event_dict[key] = _REDACTED
            continue

        # Scan string values for embedded email addresses
        val = event_dict[key]
        if isinstance(val, str) and _EMAIL_RE.search(val):
            event_dict[key] = _EMAIL_RE.sub(_REDACTED, val)

    return event_dict
