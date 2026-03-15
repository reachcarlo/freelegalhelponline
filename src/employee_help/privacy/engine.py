"""Stateless obfuscation engine for LLM API call boundaries.

ObfuscationEngine sits at the API boundary: it scans outgoing text for
entities (via :class:`EntityRecognizer`), builds an ephemeral
:class:`ObfuscationContext`, and replaces identifying information with
placeholders before data reaches the LLM.  Responses are deobfuscated
(placeholders → real values) before the user sees them.

The entity map is ephemeral — created per API call, never persisted.
"""

from __future__ import annotations

from typing import Any

from employee_help.privacy.context import ObfuscationContext
from employee_help.privacy.recognizers import EntityRecognizer


class ObfuscationEngine:
    """Stateless obfuscation engine for LLM API call boundaries.

    Usage::

        engine = ObfuscationEngine()
        ctx = engine.create_context()

        # Optional: seed with known entities from CaseContext
        engine.seed_from_case_context(case_context, ctx)

        # Scan and obfuscate all text going to the API
        obf_query = engine.obfuscate(query, ctx)

        # ... send to Anthropic ...

        # Deobfuscate the response
        real_response = engine.deobfuscate(response_text, ctx)
        # ctx is discarded (garbage collected)
    """

    def __init__(self, recognizer: EntityRecognizer | None = None) -> None:
        self._recognizer = recognizer or EntityRecognizer()

    def create_context(self) -> ObfuscationContext:
        """Create a fresh, empty context for one API call."""
        return ObfuscationContext()

    def seed_from_case_context(
        self, case_ctx: Any, obf_ctx: ObfuscationContext
    ) -> None:
        """Seed known entities from LITIGAGENTv2 CaseContext metadata.

        Expects *case_ctx* to have:

        - ``plaintiffs``: iterable of objects with ``.name``
        - ``defendants``: iterable of objects with ``.name`` and ``.is_entity``
        - ``plaintiff_counsel``, ``defendant_counsel``: iterables of objects
          with ``.name`` and optional ``.firm``
        - ``employer_name``, ``employee_name``: optional ``str``
        - ``case_number``: optional ``str``

        No-op if *case_ctx* is ``None``.
        """
        if case_ctx is None:
            return

        # Parties (most important — these identify the case)
        for plaintiff in case_ctx.plaintiffs:
            obf_ctx.seed("PERSON", plaintiff.name)
        for defendant in case_ctx.defendants:
            entity_type = "COMPANY" if defendant.is_entity else "PERSON"
            obf_ctx.seed(entity_type, defendant.name)

        # Attorneys
        for atty in list(case_ctx.plaintiff_counsel) + list(
            case_ctx.defendant_counsel
        ):
            obf_ctx.seed("PERSON", atty.name)
            if getattr(atty, "firm", None):
                obf_ctx.seed("COMPANY", atty.firm)

        # Employment relationship
        if case_ctx.employer_name:
            obf_ctx.seed("COMPANY", case_ctx.employer_name)
        if case_ctx.employee_name:
            obf_ctx.seed("PERSON", case_ctx.employee_name)

        # Case number
        if case_ctx.case_number:
            obf_ctx.seed("CASE", case_ctx.case_number)

    def obfuscate(self, text: str, ctx: ObfuscationContext) -> str:
        """Scan *text* for entities, add to *ctx*, replace with placeholders.

        1. Run :class:`EntityRecognizer` to find entities in *text*.
        2. Register each entity in *ctx* (SSN/EIN → hard redaction,
           others → reversible placeholder).
        3. Replace all known entities with their placeholders.
        """
        if not text:
            return text

        # Scan for entities
        entities = self._recognizer.scan(text)

        # Register discovered entities in the context
        for ent in entities:
            if ent.entity_type == "SSN":
                ctx.add_hard_redaction(ent.value)
            else:
                ctx.add(ent.entity_type, ent.value)

        # Replace all known entities (seeded + discovered) with placeholders
        return ctx.obfuscate(text)

    def deobfuscate(self, text: str, ctx: ObfuscationContext) -> str:
        """Replace placeholders in *text* with real values."""
        return ctx.deobfuscate(text)

    def obfuscate_filename(self, filename: str, index: int) -> str:
        """Replace a real filename with ``Document N``."""
        return f"Document {index}"
