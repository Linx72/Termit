"""Tests for error_handler middleware — taxonomy fields in JSON responses."""

from app.domain.exceptions import (
    TermitError,
    AuthError,
    RateLimitError,
    ProviderError,
    GuardrailBlockedError,
)


class TestErrorCategoryExtraction:
    """Helper functions from domain/exceptions."""

    def test_auth_error_category(self) -> None:
        from app.domain.exceptions import get_error_category
        assert get_error_category(AuthError()) == "auth"

    def test_rate_limit_category(self) -> None:
        from app.domain.exceptions import get_error_category, get_is_recoverable
        exc = RateLimitError()
        assert get_error_category(exc) == "rate_limit"
        assert get_is_recoverable(exc) is True

    def test_provider_category(self) -> None:
        from app.domain.exceptions import get_error_category, get_is_recoverable
        exc = ProviderError()
        assert get_error_category(exc) == "provider"
        assert get_is_recoverable(exc) is True

    def test_non_recoverable_default(self) -> None:
        from app.domain.exceptions import get_is_recoverable
        assert get_is_recoverable(TermitError()) is False

    def test_unknown_exception_defaults(self) -> None:
        from app.domain.exceptions import get_error_category, get_is_recoverable, get_error_code, get_http_status
        exc = ValueError("boom")
        assert get_http_status(exc) == 500
        assert get_error_code(exc) == "INTERNAL_ERROR"
        assert get_error_category(exc) == "internal"
        assert get_is_recoverable(exc) is False


class TestGuardrailErrorResponseShape:
    """Middleware returns category + recoverable for guardrail block."""

    def test_guardrail_blocked_fields(self) -> None:
        from app.domain.exceptions import get_error_category, get_is_recoverable, get_error_code, get_http_status
        exc = GuardrailBlockedError("Secret detected")
        assert get_http_status(exc) == 400
        assert get_error_code(exc) == "GUARDRAIL_BLOCKED"
        assert get_error_category(exc) == "safety"
        assert get_is_recoverable(exc) is False

    def test_auth_error_fields(self) -> None:
        from app.domain.exceptions import get_error_category, get_is_recoverable
        exc = AuthError("Invalid API key")
        assert get_error_category(exc) == "auth"
        assert get_is_recoverable(exc) is False
        assert getattr(exc, "http_status") == 401


class TestErrorHandlerMiddlewareImports:
    """Middleware module imports the new taxonomy helpers."""

    def test_get_error_category_imported(self) -> None:
        from app.middleware.error_handler import get_error_category
        assert callable(get_error_category)

    def test_get_is_recoverable_imported(self) -> None:
        from app.middleware.error_handler import get_is_recoverable
        assert callable(get_is_recoverable)
