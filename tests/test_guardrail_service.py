"""Tests for GuardrailService — secret/credential detection in prompts."""

from app.services.guardrail_service import GuardrailService
from app.domain.exceptions import GuardrailBlockedError


class TestGuardrailSecretDetection:
    """Core detection logic — no side effects, pure string scanning."""

    def test_safe_prompt_passes(self) -> None:
        gs = GuardrailService()
        result = gs.check_prompt("Hello, how are you?")
        assert result.allowed
        assert not result.reason

    def test_openai_api_key_blocked(self) -> None:
        gs = GuardrailService()
        result = gs.check_prompt("sk-abc123def456ghijklmnopqrstuvwx")
        assert not result.allowed

    def test_aws_secret_key_blocked(self) -> None:
        gs = GuardrailService()
        # Pattern matches 'secret = ...'
        result = gs.check_prompt("AWS secret = wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY")
        assert not result.allowed

    def test_github_token_blocked(self) -> None:
        gs = GuardrailService()
        # ghp_ + 20+ alphanumeric
        result = gs.check_prompt("ghp_1234567890abcdef1234567890abcdef1234")
        assert not result.allowed

    def test_pem_private_key_blocked(self) -> None:
        gs = GuardrailService()
        result = gs.check_prompt("-----BEGIN PRIVATE KEY-----\nMIIEvQIBADANBgkqhkiG9w0BAQ")
        assert not result.allowed

    def test_empty_string_passes(self) -> None:
        gs = GuardrailService()
        result = gs.check_prompt("")
        assert result.allowed

    def test_unicode_safe_text_passes(self) -> None:
        gs = GuardrailService()
        result = gs.check_prompt("Привет, как дела? こんにちは")
        assert result.allowed


class TestGuardrailIntegration:
    """Verify GuardrailBlockedError is usable after taxonomy changes."""

    def test_blocked_error_category(self) -> None:
        assert GuardrailBlockedError.error_category == "safety"

    def test_blocked_is_not_recoverable(self) -> None:
        assert GuardrailBlockedError.is_recoverable is False
