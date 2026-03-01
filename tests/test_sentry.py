"""Tests for Sentry error tracking integration.

Verifies that:
  1. Sentry initializes when SENTRY_DSN is set
  2. Sentry does NOT initialize when SENTRY_DSN is absent
  3. Environment and sample rate are configurable
  4. Unhandled FastAPI exceptions return 500
"""

from __future__ import annotations

import importlib
from unittest.mock import patch

import pytest


def _reload_main():
    """Force re-execution of module-level Sentry init code."""
    import employee_help.api.main

    importlib.reload(employee_help.api.main)


class TestSentryInit:
    """Sentry SDK initialization based on environment."""

    def test_initializes_with_dsn(self):
        """Sentry.init() is called when SENTRY_DSN is set."""
        dsn = "https://examplePublicKey@o0.ingest.sentry.io/0"
        with patch.dict("os.environ", {"SENTRY_DSN": dsn}, clear=False), patch(
            "sentry_sdk.init"
        ) as mock_init:
            _reload_main()

            assert mock_init.called
            call_kwargs = mock_init.call_args[1]
            assert call_kwargs["dsn"] == dsn
            assert call_kwargs["enable_tracing"] is True

    def test_skipped_without_dsn(self):
        """Sentry.init() is NOT called when SENTRY_DSN is absent."""
        import os

        env = {k: v for k, v in os.environ.items() if k != "SENTRY_DSN"}
        with patch.dict("os.environ", env, clear=True), patch(
            "sentry_sdk.init"
        ) as mock_init:
            _reload_main()

            mock_init.assert_not_called()

    def test_environment_defaults_to_production(self):
        """Default Sentry environment is 'production'."""
        import os

        os.environ.pop("SENTRY_ENVIRONMENT", None)
        with patch.dict(
            "os.environ",
            {"SENTRY_DSN": "https://x@o0.ingest.sentry.io/0"},
            clear=False,
        ), patch("sentry_sdk.init") as mock_init:
            _reload_main()

            call_kwargs = mock_init.call_args[1]
            assert call_kwargs["environment"] == "production"

    def test_environment_from_env_var(self):
        """Sentry environment reads from SENTRY_ENVIRONMENT."""
        with patch.dict(
            "os.environ",
            {
                "SENTRY_DSN": "https://x@o0.ingest.sentry.io/0",
                "SENTRY_ENVIRONMENT": "staging",
            },
            clear=False,
        ), patch("sentry_sdk.init") as mock_init:
            _reload_main()

            call_kwargs = mock_init.call_args[1]
            assert call_kwargs["environment"] == "staging"

    def test_traces_sample_rate_configurable(self):
        """Traces sample rate reads from SENTRY_TRACES_SAMPLE_RATE."""
        with patch.dict(
            "os.environ",
            {
                "SENTRY_DSN": "https://x@o0.ingest.sentry.io/0",
                "SENTRY_TRACES_SAMPLE_RATE": "0.5",
            },
            clear=False,
        ), patch("sentry_sdk.init") as mock_init:
            _reload_main()

            call_kwargs = mock_init.call_args[1]
            assert call_kwargs["traces_sample_rate"] == 0.5


class TestSentryCapturesErrors:
    """Verify unhandled FastAPI errors return 500 (Sentry captures via ASGI)."""

    def test_unhandled_exception_returns_500(self):
        """An unhandled route exception returns HTTP 500."""
        with patch("sentry_sdk.init"):
            _reload_main()
            from employee_help.api.main import app

        @app.get("/api/_test_sentry_error")
        async def _boom():
            raise RuntimeError("Sentry test exception")

        from fastapi.testclient import TestClient

        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/api/_test_sentry_error")
        assert response.status_code == 500
