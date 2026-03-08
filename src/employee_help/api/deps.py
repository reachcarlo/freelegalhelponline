"""Service singletons for the FastAPI application.

Mirrors the wiring in cli.py but exposes services as module-level singletons
loaded once at startup via the FastAPI lifespan context manager.
"""

from __future__ import annotations

from pathlib import Path

import structlog
import yaml

logger = structlog.get_logger(__name__)

# Module-level singletons — populated by init_services(), cleared by shutdown_services()
_retrieval_service = None
_answer_service = None
_feedback_store = None
_case_storage = None
_auth_storage = None
_session_manager = None
_google_provider = None
_microsoft_provider = None


def _load_rag_config() -> dict:
    """Load RAG pipeline configuration from config/rag.yaml."""
    config_path = Path("config/rag.yaml")
    if config_path.exists():
        with open(config_path) as f:
            return yaml.safe_load(f)
    return {}


def init_services() -> None:
    """Initialize all services. Called once at FastAPI startup."""
    global _retrieval_service, _answer_service, _feedback_store, _case_storage

    from employee_help.generation.llm import LLMClient
    from employee_help.generation.prompts import PromptBuilder
    from employee_help.generation.service import AnswerService
    from employee_help.retrieval.embedder import EmbeddingService
    from employee_help.retrieval.query import QueryPreprocessor
    from employee_help.retrieval.reranker import Reranker
    from employee_help.retrieval.service import RetrievalService
    from employee_help.retrieval.vector_store import VectorStore

    rag_config = _load_rag_config()

    # Build retrieval service (same pattern as cli.py:_build_retrieval_service)
    emb_cfg = rag_config.get("embedding", {})
    embedding_service = EmbeddingService(
        model_name=emb_cfg.get("model", "BAAI/bge-base-en-v1.5"),
        device=emb_cfg.get("device", "cpu"),
    )

    vs_cfg = rag_config.get("vector_store", {})
    vector_store = VectorStore(
        db_path=vs_cfg.get("path", "data/lancedb"),
    )

    rr_cfg = rag_config.get("reranker", {})
    reranker = None
    if rr_cfg.get("enabled", True):
        try:
            reranker = Reranker(
                model_name=rr_cfg.get("model", "mixedbread-ai/mxbai-rerank-base-v2"),
                device=rr_cfg.get("device", "cpu"),
            )
        except Exception:
            logger.warning("reranker_load_failed", exc_info=True)

    ret_cfg = rag_config.get("retrieval", {})
    _retrieval_service = RetrievalService(
        vector_store=vector_store,
        embedding_service=embedding_service,
        reranker=reranker,
        query_preprocessor=QueryPreprocessor(),
        top_k_search=ret_cfg.get("top_k_search", 50),
        top_k_rerank=ret_cfg.get("top_k_rerank", 10),
        top_k_final=ret_cfg.get("top_k_final", 5),
        citation_boost=ret_cfg.get("citation_boost", 1.5),
        statutory_boost=ret_cfg.get("statutory_boost", 1.2),
        diversity_max_per_doc=ret_cfg.get("diversity_max_per_doc", 3),
    )

    # Build answer service (same pattern as cli.py:_handle_ask)
    gen_cfg = rag_config.get("generation", {})

    llm_client = LLMClient(
        timeout=gen_cfg.get("timeout_seconds", 30),
        consumer_model=gen_cfg.get("consumer_model"),
        attorney_model=gen_cfg.get("attorney_model"),
    )

    prompt_builder = PromptBuilder(
        max_context_tokens=gen_cfg.get("max_context_tokens", 6000),
        rag_config=rag_config,
    )

    # Optionally create citation verifiers for attorney-mode verification
    from employee_help.generation.citation_verifier import (
        CaseCitationVerifier,
        StatuteCitationVerifier,
    )
    from employee_help.storage.storage import Storage

    case_verifier = CaseCitationVerifier()  # Uses COURTLISTENER_API_TOKEN env var
    statute_verifier = None
    try:
        storage = Storage()
        statute_verifier = StatuteCitationVerifier(storage)
    except Exception:
        logger.warning("statute_verifier_init_failed", exc_info=True)

    _answer_service = AnswerService(
        retrieval_service=_retrieval_service,
        llm_client=llm_client,
        prompt_builder=prompt_builder,
        citation_validation=gen_cfg.get("citation_validation", "strict"),
        case_verifier=case_verifier,
        statute_verifier=statute_verifier,
    )

    # Initialize feedback store
    from employee_help.feedback.store import FeedbackStore

    _feedback_store = FeedbackStore()

    # Initialize case storage (LITIGAGENT)
    from employee_help.storage.case_storage import CaseStorage

    _case_storage = CaseStorage(db_path="data/employee_help.db")

    # Initialize auth services
    _init_auth_services()

    logger.info(
        "services_initialized",
        embedding_model=emb_cfg.get("model", "BAAI/bge-base-en-v1.5"),
        reranker_enabled=reranker is not None,
    )


def _init_auth_services() -> None:
    """Initialize auth-related services (providers, storage, session manager)."""
    global _auth_storage, _session_manager, _google_provider, _microsoft_provider

    import os

    from employee_help.auth.session import SessionManager
    from employee_help.auth.storage import AuthStorage

    # AuthStorage shares the same DB as case storage
    _auth_storage = AuthStorage(db_path="data/employee_help.db")

    jwt_secret = os.environ.get("AUTH_JWT_SECRET")
    if not jwt_secret:
        logger.warning(
            "auth_jwt_secret_missing",
            msg="AUTH_JWT_SECRET not set — auth endpoints will not work",
        )
        return

    _session_manager = SessionManager(
        auth_storage=_auth_storage,
        jwt_secret=jwt_secret,
    )

    # Google OAuth (optional — only if credentials configured)
    google_client_id = os.environ.get("GOOGLE_CLIENT_ID")
    google_client_secret = os.environ.get("GOOGLE_CLIENT_SECRET")
    if google_client_id and google_client_secret:
        from employee_help.auth.google import GoogleOIDCProvider

        _google_provider = GoogleOIDCProvider(google_client_id, google_client_secret)
        logger.info("google_oauth_configured")
    else:
        logger.info("google_oauth_not_configured")

    # Microsoft OAuth (optional — only if credentials configured)
    ms_client_id = os.environ.get("MICROSOFT_CLIENT_ID")
    ms_client_secret = os.environ.get("MICROSOFT_CLIENT_SECRET")
    if ms_client_id and ms_client_secret:
        from employee_help.auth.microsoft import MicrosoftOIDCProvider

        _microsoft_provider = MicrosoftOIDCProvider(ms_client_id, ms_client_secret)
        logger.info("microsoft_oauth_configured")
    else:
        logger.info("microsoft_oauth_not_configured")

    logger.info("auth_services_initialized")


def shutdown_services() -> None:
    """Clean up services. Called at FastAPI shutdown."""
    global _retrieval_service, _answer_service, _feedback_store, _case_storage
    global _auth_storage, _session_manager, _google_provider, _microsoft_provider
    if _feedback_store is not None:
        _feedback_store.close()
    if _case_storage is not None:
        _case_storage.close()
    if _auth_storage is not None:
        _auth_storage.close()
    _retrieval_service = None
    _answer_service = None
    _feedback_store = None
    _case_storage = None
    _auth_storage = None
    _session_manager = None
    _google_provider = None
    _microsoft_provider = None
    logger.info("services_shutdown")


def get_retrieval_service():
    """Return the retrieval service singleton."""
    if _retrieval_service is None:
        raise RuntimeError("Services not initialized. Is the server starting up?")
    return _retrieval_service


def get_answer_service():
    """Return the answer service singleton."""
    if _answer_service is None:
        raise RuntimeError("Services not initialized. Is the server starting up?")
    return _answer_service


def get_feedback_store():
    """Return the feedback store singleton (may be None if not initialized)."""
    return _feedback_store


def get_case_storage():
    """Return the CaseStorage singleton."""
    if _case_storage is None:
        raise RuntimeError("Case storage not initialized. Is the server starting up?")
    return _case_storage


def get_conversation_config() -> dict:
    """Return conversation config from rag.yaml."""
    config = _load_rag_config()
    conv = config.get("conversation", {})
    return {
        "max_turns": conv.get("max_turns", {"consumer": 3, "attorney": 5}),
        "history_token_budget": conv.get("history_token_budget", 2000),
        "short_followup_threshold": conv.get("short_followup_threshold", 6),
    }


def get_auth_storage():
    """Return the AuthStorage singleton."""
    if _auth_storage is None:
        raise RuntimeError("Auth storage not initialized. Is AUTH_JWT_SECRET set?")
    return _auth_storage


def get_session_manager():
    """Return the SessionManager singleton."""
    if _session_manager is None:
        raise RuntimeError("Session manager not initialized. Is AUTH_JWT_SECRET set?")
    return _session_manager


def get_google_provider():
    """Return the Google OIDC provider (None if not configured)."""
    return _google_provider


def get_microsoft_provider():
    """Return the Microsoft OIDC provider (None if not configured)."""
    return _microsoft_provider
