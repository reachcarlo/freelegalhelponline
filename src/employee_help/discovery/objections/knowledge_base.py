"""Load and query the objection knowledge base from YAML."""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

import structlog
import yaml

from employee_help.discovery.objections.models import (
    CaseCitation,
    ObjectionCategory,
    ObjectionGround,
    ResponseDiscoveryType,
    StatutoryCitation,
    Verbosity,
)

logger = structlog.get_logger(__name__)

DEFAULT_GROUNDS_PATH = Path("config/objections/grounds.yaml")
STALENESS_THRESHOLD_DAYS = 180  # 6 months


class ObjectionKnowledgeBase:
    """Load, validate, and query objection grounds from YAML.

    The knowledge base is loaded once and cached. Grounds are immutable
    frozen dataclasses, safe to share across requests.
    """

    def __init__(self, path: Path | str = DEFAULT_GROUNDS_PATH) -> None:
        self._path = Path(path)
        self._grounds: dict[str, ObjectionGround] = {}
        self._load()

    def _load(self) -> None:
        """Load and validate the YAML knowledge base."""
        if not self._path.exists():
            raise FileNotFoundError(f"Knowledge base not found: {self._path}")

        with open(self._path) as f:
            data = yaml.safe_load(f)

        if not data or "grounds" not in data:
            raise ValueError(f"Invalid knowledge base: missing 'grounds' key in {self._path}")

        for entry in data["grounds"]:
            ground = self._parse_ground(entry)
            if ground.ground_id in self._grounds:
                raise ValueError(f"Duplicate ground_id: {ground.ground_id}")
            self._grounds[ground.ground_id] = ground

        logger.info("knowledge_base_loaded", ground_count=len(self._grounds), path=str(self._path))

    def _parse_ground(self, entry: dict) -> ObjectionGround:
        """Parse a single ground entry from YAML into a frozen dataclass."""
        required = ("ground_id", "label", "category", "description", "last_verified",
                     "applies_to", "sample_language")
        for key in required:
            if key not in entry:
                raise ValueError(
                    f"Ground '{entry.get('ground_id', '?')}' missing required field: {key}"
                )

        statutory_citations = tuple(
            StatutoryCitation(
                code=c["code"],
                section=c["section"],
                description=c.get("description", ""),
            )
            for c in entry.get("statutory_citations", [])
        )

        case_citations = tuple(
            CaseCitation(
                name=c["name"],
                year=c["year"],
                citation=c["citation"],
                reporter_key=c["reporter_key"],
                holding=c.get("holding", ""),
                use=c.get("use", ""),
            )
            for c in entry.get("case_citations", [])
        )

        applies_to = tuple(
            ResponseDiscoveryType(t) for t in entry["applies_to"]
        )

        sample_language = {
            Verbosity(k): v for k, v in entry["sample_language"].items()
        }

        strength_signals = tuple(entry.get("strength_signals", []))

        return ObjectionGround(
            ground_id=entry["ground_id"],
            label=entry["label"],
            category=ObjectionCategory(entry["category"]),
            description=entry["description"],
            last_verified=entry["last_verified"],
            statutory_citations=statutory_citations,
            case_citations=case_citations,
            applies_to=applies_to,
            sample_language=sample_language,
            strength_signals=strength_signals,
        )

    # ── Public query methods ──────────────────────────────────────────────

    def get_all_grounds(self) -> list[ObjectionGround]:
        """Return all objection grounds."""
        return list(self._grounds.values())

    def get_ground(self, ground_id: str) -> ObjectionGround | None:
        """Return a single ground by ID, or None if not found."""
        return self._grounds.get(ground_id)

    def get_grounds(
        self,
        discovery_type: ResponseDiscoveryType | None = None,
        category: ObjectionCategory | None = None,
    ) -> list[ObjectionGround]:
        """Return grounds filtered by discovery type and/or category."""
        results = list(self._grounds.values())

        if discovery_type is not None:
            results = [g for g in results if discovery_type in g.applies_to]

        if category is not None:
            results = [g for g in results if g.category == category]

        return results

    def get_ground_ids(self) -> list[str]:
        """Return all ground IDs in knowledge base order."""
        return list(self._grounds.keys())

    def get_stale_grounds(self, reference_date: date | None = None) -> list[ObjectionGround]:
        """Return grounds whose last_verified is older than the staleness threshold."""
        ref = reference_date or date.today()
        stale = []
        for ground in self._grounds.values():
            try:
                verified = datetime.strptime(ground.last_verified, "%Y-%m-%d").date()
                if (ref - verified).days > STALENESS_THRESHOLD_DAYS:
                    stale.append(ground)
            except ValueError:
                stale.append(ground)  # Can't parse date → treat as stale
        return stale

    def get_reporter_keys(self) -> dict[str, tuple[str, str]]:
        """Return a mapping of reporter_key → (ground_id, case_name) for validation."""
        keys: dict[str, tuple[str, str]] = {}
        for ground in self._grounds.values():
            for case in ground.case_citations:
                keys[case.reporter_key] = (ground.ground_id, case.name)
        return keys

    @property
    def ground_count(self) -> int:
        return len(self._grounds)
