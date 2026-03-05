"""LLM-powered objection analysis engine.

Determines which objection grounds apply to each discovery request and
generates request-specific explanations. Uses Claude tool_use for
guaranteed structured output.
"""

from __future__ import annotations

import math
import time
from pathlib import Path
from typing import Any

import structlog
from jinja2 import Environment, FileSystemLoader

from employee_help.discovery.objections.knowledge_base import ObjectionKnowledgeBase
from employee_help.discovery.objections.models import (
    AnalysisResult,
    BatchAnalysisResult,
    CaseCitation,
    DISCOVERY_TYPE_LABELS,
    GeneratedObjection,
    ObjectionGround,
    ObjectionRequest,
    ObjectionStrength,
    PartyRole,
    ResponseDiscoveryType,
    StatutoryCitation,
    Verbosity,
)
from employee_help.discovery.objections.validator import CitationValidator
from employee_help.generation.llm import LLMClient
from employee_help.generation.models import TokenUsage

logger = structlog.get_logger(__name__)

PROMPTS_DIR = Path("config/prompts")
BATCH_CHUNK_SIZE = 15  # Max requests per LLM call
DEFAULT_TIMEOUT = 120.0  # seconds


def _build_tool_schema(ground_ids: list[str]) -> dict[str, Any]:
    """Build the tool_use schema for structured objection output."""
    return {
        "name": "submit_objections",
        "description": "Submit the analysis of which objections apply to each discovery request.",
        "input_schema": {
            "type": "object",
            "properties": {
                "request_analyses": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "request_number": {"type": "integer"},
                            "applicable_objections": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "ground_id": {
                                            "type": "string",
                                            "enum": ground_ids,
                                        },
                                        "explanation": {"type": "string"},
                                        "strength": {
                                            "type": "string",
                                            "enum": ["high", "medium", "low"],
                                        },
                                        "statutory_citation_keys": {
                                            "type": "array",
                                            "items": {"type": "string"},
                                        },
                                        "case_citation_keys": {
                                            "type": "array",
                                            "items": {"type": "string"},
                                        },
                                    },
                                    "required": [
                                        "ground_id",
                                        "explanation",
                                        "strength",
                                    ],
                                },
                            },
                            "no_objections_rationale": {
                                "type": "string",
                                "description": "Explain why no objections apply (only when applicable_objections is empty)",
                            },
                        },
                        "required": ["request_number", "applicable_objections"],
                    },
                },
            },
            "required": ["request_analyses"],
        },
    }


class ObjectionAnalyzer:
    """Analyze discovery requests and generate objections via LLM tool_use.

    Supports batch processing with automatic chunking at BATCH_CHUNK_SIZE
    boundaries for large request sets.
    """

    def __init__(
        self,
        llm_client: LLMClient,
        knowledge_base: ObjectionKnowledgeBase,
        validator: CitationValidator | None = None,
    ) -> None:
        self._llm = llm_client
        self._kb = knowledge_base
        self._validator = validator
        self._jinja_env = Environment(
            loader=FileSystemLoader(str(PROMPTS_DIR)),
            autoescape=False,
        )

    def analyze_single(
        self,
        request: ObjectionRequest,
        verbosity: Verbosity = Verbosity.MEDIUM,
        party_role: PartyRole = PartyRole.DEFENDANT,
        *,
        model: str | None = None,
    ) -> AnalysisResult:
        """Analyze a single request. Convenience wrapper around analyze_batch."""
        batch = self.analyze_batch(
            [request],
            verbosity=verbosity,
            party_role=party_role,
            model=model,
        )
        if batch.results:
            return batch.results[0]
        return AnalysisResult(request=request, objections=[])

    def analyze_batch(
        self,
        requests: list[ObjectionRequest],
        verbosity: Verbosity = Verbosity.MEDIUM,
        party_role: PartyRole = PartyRole.DEFENDANT,
        *,
        model: str | None = None,
        ground_ids: list[str] | None = None,
    ) -> BatchAnalysisResult:
        """Analyze a batch of requests, chunking if necessary.

        Args:
            requests: List of requests to analyze.
            verbosity: Verbosity level for explanations.
            party_role: Plaintiff or defendant.
            model: Override model selection.
            ground_ids: Restrict to these ground IDs (None = all applicable).

        Returns:
            BatchAnalysisResult with all results and usage info.
        """
        if not requests:
            return BatchAnalysisResult(results=[])

        start_time = time.monotonic()

        # Get applicable grounds
        discovery_type = requests[0].discovery_type
        all_grounds = self._kb.get_grounds(discovery_type=discovery_type)
        if ground_ids:
            all_grounds = [g for g in all_grounds if g.ground_id in ground_ids]

        # Chunk if necessary
        chunks = [
            requests[i:i + BATCH_CHUNK_SIZE]
            for i in range(0, len(requests), BATCH_CHUNK_SIZE)
        ]

        all_results: list[AnalysisResult] = []
        total_input = 0
        total_output = 0
        model_used = ""
        warnings: list[str] = []

        for chunk_idx, chunk in enumerate(chunks):
            try:
                results, usage = self._analyze_chunk(
                    chunk,
                    all_grounds,
                    verbosity=verbosity,
                    party_role=party_role,
                    discovery_type=discovery_type,
                    model=model,
                )
                all_results.extend(results)
                total_input += usage.input_tokens
                total_output += usage.output_tokens
                model_used = usage.model
            except Exception as e:
                logger.error(
                    "chunk_analysis_failed",
                    chunk_index=chunk_idx,
                    chunk_size=len(chunk),
                    error=str(e),
                )
                # Create empty results for failed chunk
                for req in chunk:
                    all_results.append(AnalysisResult(
                        request=req, objections=[]
                    ))
                warnings.append(
                    f"Analysis failed for requests "
                    f"{chunk[0].request_number}-{chunk[-1].request_number}. "
                    f"Error: {e}"
                )

        duration_ms = int((time.monotonic() - start_time) * 1000)
        usage = TokenUsage(
            input_tokens=total_input,
            output_tokens=total_output,
            model=model_used,
        )

        logger.info(
            "batch_analysis_complete",
            request_count=len(requests),
            chunks=len(chunks),
            total_objections=sum(len(r.objections) for r in all_results),
            model=model_used,
            input_tokens=total_input,
            output_tokens=total_output,
            cost_estimate=f"${usage.cost_estimate:.4f}",
            duration_ms=duration_ms,
        )

        return BatchAnalysisResult(
            results=all_results,
            model_used=model_used,
            input_tokens=total_input,
            output_tokens=total_output,
            cost_estimate=usage.cost_estimate,
            duration_ms=duration_ms,
            warnings=warnings,
        )

    def _analyze_chunk(
        self,
        requests: list[ObjectionRequest],
        grounds: list[ObjectionGround],
        *,
        verbosity: Verbosity,
        party_role: PartyRole,
        discovery_type: ResponseDiscoveryType,
        model: str | None,
    ) -> tuple[list[AnalysisResult], TokenUsage]:
        """Analyze a single chunk of requests via one LLM call."""
        # Build system prompt
        template = self._jinja_env.get_template("objection_system.j2")
        system_prompt = template.render(
            party_role=party_role.value,
            verbosity=verbosity.value,
            discovery_type_label=DISCOVERY_TYPE_LABELS.get(
                discovery_type, "Discovery Requests"
            ),
            grounds=grounds,
        )

        # Build user message with request texts
        user_parts = ["Analyze the following discovery requests:\n"]
        for req in requests:
            user_parts.append(
                f"--- Request No. {req.request_number} ---\n"
                f"{req.request_text}\n"
            )
        user_message = "\n".join(user_parts)

        # Build tool schema
        available_ids = [g.ground_id for g in grounds]
        tool = _build_tool_schema(available_ids)

        # Call LLM
        result = self._llm.generate_with_tools(
            system_prompt=system_prompt,
            user_message=user_message,
            tools=[tool],
            model=model,
            mode="attorney",
            max_tokens=4096,
            temperature=0.0,
        )

        usage = TokenUsage(
            input_tokens=result["input_tokens"],
            output_tokens=result["output_tokens"],
            model=result["model"],
        )

        # Parse tool output
        tool_input = result["tool_input"]
        analyses = tool_input.get("request_analyses", [])

        # Build ground lookup
        ground_map = {g.ground_id: g for g in grounds}

        # Map LLM output to AnalysisResult objects
        results = self._map_tool_output(
            analyses, requests, ground_map, verbosity
        )

        return results, usage

    def _map_tool_output(
        self,
        analyses: list[dict[str, Any]],
        requests: list[ObjectionRequest],
        ground_map: dict[str, ObjectionGround],
        verbosity: Verbosity,
    ) -> list[AnalysisResult]:
        """Map raw tool_use output to typed AnalysisResult objects."""
        # Build request lookup by number
        req_map: dict[int | str, ObjectionRequest] = {
            r.request_number: r for r in requests
        }

        results: list[AnalysisResult] = []

        for analysis in analyses:
            req_num = analysis.get("request_number")
            request = req_map.get(req_num)
            if request is None:
                logger.warning(
                    "unknown_request_number",
                    request_number=req_num,
                )
                continue

            objections: list[GeneratedObjection] = []
            for obj_data in analysis.get("applicable_objections", []):
                ground_id = obj_data.get("ground_id", "")
                ground = ground_map.get(ground_id)
                if ground is None:
                    logger.warning(
                        "unknown_ground_id",
                        ground_id=ground_id,
                        request_number=req_num,
                    )
                    continue

                # Resolve citations from knowledge base
                stat_cites = self._resolve_statutory_citations(
                    obj_data.get("statutory_citation_keys", []), ground
                )
                case_cites = self._resolve_case_citations(
                    obj_data.get("case_citation_keys", []), ground
                )

                # Fall back to ground's citations if LLM didn't specify
                if not stat_cites:
                    stat_cites = list(ground.statutory_citations)
                if not case_cites:
                    case_cites = list(ground.case_citations)

                objection = GeneratedObjection(
                    ground=ground,
                    explanation=obj_data.get("explanation", ""),
                    verbosity=verbosity,
                    strength=ObjectionStrength(
                        obj_data.get("strength", "medium")
                    ),
                    statutory_citations=stat_cites,
                    case_citations=case_cites,
                )

                objections.append(objection)

            # Validate citations
            if self._validator and objections:
                self._validator.validate_batch(objections)

            result = AnalysisResult(
                request=request,
                objections=objections,
                no_objections_rationale=analysis.get("no_objections_rationale"),
            )
            results.append(result)

        # Add empty results for any requests not in the LLM output
        seen = {r.request.request_number for r in results}
        for req in requests:
            if req.request_number not in seen:
                results.append(AnalysisResult(request=req, objections=[]))

        # Sort by request number
        results.sort(key=lambda r: (
            r.request.request_number
            if isinstance(r.request.request_number, int)
            else 0
        ))

        return results

    def _resolve_statutory_citations(
        self,
        keys: list[str],
        ground: ObjectionGround,
    ) -> list[StatutoryCitation]:
        """Resolve statutory citation keys to StatutoryCitation objects."""
        resolved: list[StatutoryCitation] = []
        for key in keys:
            for sc in ground.statutory_citations:
                full_key = f"{sc.code} {sc.section}"
                if full_key == key or sc.section == key:
                    resolved.append(sc)
                    break
        return resolved

    def _resolve_case_citations(
        self,
        keys: list[str],
        ground: ObjectionGround,
    ) -> list[CaseCitation]:
        """Resolve case citation keys (reporter_key) to CaseCitation objects."""
        resolved: list[CaseCitation] = []
        for key in keys:
            for cc in ground.case_citations:
                if cc.reporter_key == key:
                    resolved.append(cc)
                    break
        return resolved
