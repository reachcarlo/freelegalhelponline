"""Ephemeral bidirectional entity mapping for API call obfuscation.

ObfuscationContext holds a forward map (real value → placeholder) and a
reverse map (placeholder → real value) for one request-response cycle.
Created before an API call, used to obfuscate outgoing text and deobfuscate
incoming text.  Discarded after the call completes.  Never persisted.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class ObfuscationContext:
    """Ephemeral bidirectional mapping for one API call lifecycle.

    Created before an API call, used to obfuscate outgoing text
    and deobfuscate incoming text.  Discarded after the call completes.
    Never persisted.
    """

    _forward: dict[str, str] = field(default_factory=dict)
    _reverse: dict[str, str] = field(default_factory=dict)
    _counters: dict[str, int] = field(default_factory=dict)

    # SSN/EIN are hard-redacted (irreversible)
    _HARD_REDACT_LABEL = "[REDACTED]"

    def seed(self, entity_type: str, real_value: str) -> str:
        """Add a known entity.  Returns the placeholder assigned.

        Seeded entities get stable, deterministic placeholder numbers
        based on insertion order.  Idempotent — returns existing
        placeholder if *real_value* is already mapped.
        """
        return self._register(entity_type, real_value)

    def add(self, entity_type: str, real_value: str) -> str:
        """Add a discovered entity.  Returns the placeholder assigned.

        Idempotent — returns existing placeholder if *real_value* is
        already mapped.
        """
        return self._register(entity_type, real_value)

    def add_hard_redaction(self, real_value: str) -> str:
        """Register a value for irreversible redaction (e.g. SSN/EIN).

        The value is replaced with ``[REDACTED]`` and cannot be reversed.
        """
        if real_value in self._forward:
            return self._forward[real_value]
        self._forward[real_value] = self._HARD_REDACT_LABEL
        # No reverse mapping — hard redactions are intentionally irreversible
        return self._HARD_REDACT_LABEL

    def obfuscate(self, text: str) -> str:
        """Replace all known entities in *text* with their placeholders.

        Uses longest-match-first ordering to prevent partial replacements
        (e.g. "Smithfield" is matched before "Smith").  Matches are
        restricted to word boundaries so "Smith" does not match inside
        "locksmith".
        """
        if not text or not self._forward:
            return text

        return self._replace(text, self._forward)

    def deobfuscate(self, text: str) -> str:
        """Replace all placeholders in *text* with real values.

        Uses longest-match-first ordering to prevent partial replacements.
        Hard-redacted values (``[REDACTED]``) are left as-is since there
        is no reverse mapping.
        """
        if not text or not self._reverse:
            return text

        return self._replace(text, self._reverse)

    @property
    def entity_count(self) -> int:
        """Number of distinct real values currently mapped."""
        return len(self._forward)

    @property
    def forward_map(self) -> dict[str, str]:
        """Read-only copy of the forward map (for testing/debugging)."""
        return dict(self._forward)

    @property
    def reverse_map(self) -> dict[str, str]:
        """Read-only copy of the reverse map (for testing/debugging)."""
        return dict(self._reverse)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _register(self, entity_type: str, real_value: str) -> str:
        """Register a real value under *entity_type*.  Idempotent."""
        if not real_value:
            return real_value

        if real_value in self._forward:
            return self._forward[real_value]

        counter = self._counters.get(entity_type, 0) + 1
        self._counters[entity_type] = counter
        placeholder = f"{entity_type}_{counter}"

        self._forward[real_value] = placeholder
        self._reverse[placeholder] = real_value
        return placeholder

    @staticmethod
    def _replace(text: str, mapping: dict[str, str]) -> str:
        """Replace all keys in *mapping* found in *text* with their values.

        Keys are sorted longest-first to prevent partial matches.
        Each key is matched only at word boundaries.
        """
        if not mapping:
            return text

        # Sort keys longest-first so "Smithfield Foods" is matched before "Smith"
        sorted_keys = sorted(mapping.keys(), key=len, reverse=True)

        # Build a single regex alternation with word-boundary anchors.
        # re.escape each key so special regex chars in entity values are safe.
        pattern = "|".join(
            _word_boundary_pattern(key) for key in sorted_keys
        )
        regex = re.compile(pattern)

        def _sub(match: re.Match[str]) -> str:
            return mapping[match.group(0)]

        return regex.sub(_sub, text)


def _word_boundary_pattern(literal: str) -> str:
    r"""Build a regex fragment that matches *literal* at word boundaries.

    Uses ``\b`` on sides adjacent to a word character and a zero-width
    lookaround on sides adjacent to a non-word character (so that
    patterns like ``[REDACTED]`` still match correctly even though
    ``[`` is not a word character).
    """
    escaped = re.escape(literal)

    # Determine appropriate boundary for the start of the literal
    if literal and re.match(r"\w", literal[0]):
        prefix = r"\b"
    else:
        # Non-word start: require not preceded by a word character
        prefix = r"(?<!\w)"

    # Determine appropriate boundary for the end of the literal
    if literal and re.match(r"\w", literal[-1]):
        suffix = r"\b"
    else:
        # Non-word end: require not followed by a word character
        suffix = r"(?!\w)"

    return f"{prefix}{escaped}{suffix}"
