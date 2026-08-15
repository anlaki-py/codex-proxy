"""Tests for static proxy configuration."""

from codex_proxy.config import CODEX_MODEL_IDS, CODEX_MODELS, DEFAULT_CODEX_MODEL


def test_codex_models_match_current_chatgpt_subscription_catalog():
    assert DEFAULT_CODEX_MODEL == "gpt-5.6"
    assert CODEX_MODEL_IDS == (
        "gpt-5.6",
        "gpt-5.6-sol",
        "gpt-5.6-terra",
        "gpt-5.6-luna",
        "gpt-5.5",
        "gpt-5.4",
        "gpt-5.4-mini",
        "gpt-5.3-codex-spark",
    )
    assert [model["id"] for model in CODEX_MODELS] == list(CODEX_MODEL_IDS)
