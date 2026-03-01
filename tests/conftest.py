"""Test suite configuration and marker documentation.

Test tiers (controlled via pytest markers in pyproject.toml):

  Default (fast unit + mock):  uv run pytest
  Spot checks (live DB):       uv run pytest -m spot_check
  Slow (ML model loading):     uv run pytest -m slow
  Live (network access):       uv run pytest -m live
  Evaluation (LanceDB):        uv run pytest -m evaluation
  LLM (API key required):      uv run pytest -m llm
  Everything:                  uv run pytest -m ""
"""
