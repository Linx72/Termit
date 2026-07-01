"""Tests for ProviderCircuitBreaker — fail-fast, cooldown, recovery."""

import time
from app.services.provider_circuit_breaker import ProviderCircuitBreaker


class TestCircuitBreakerCore:
    """State transitions per provider: CLOSED → OPEN → HALF_OPEN → CLOSED."""

    def test_starts_available(self) -> None:
        cb = ProviderCircuitBreaker(failure_threshold=3, cooldown_seconds=30)
        assert cb.is_available("test-provider") is True

    def test_opens_after_threshold_failures(self) -> None:
        cb = ProviderCircuitBreaker(failure_threshold=2, cooldown_seconds=30)
        cb.record_failure("test-provider")
        assert cb.is_available("test-provider") is True
        cb.record_failure("test-provider")
        assert cb.is_available("test-provider") is False  # circuit OPEN

    def test_available_after_cooldown(self) -> None:
        # cooldown=0.01 — opens briefly then recovers
        cb = ProviderCircuitBreaker(failure_threshold=1, cooldown_seconds=0.01)
        cb.record_failure("test-provider")
        assert cb.is_available("test-provider") is False
        time.sleep(0.02)
        assert cb.is_available("test-provider") is True

    def test_success_resets_failures(self) -> None:
        cb = ProviderCircuitBreaker(failure_threshold=2, cooldown_seconds=30)
        cb.record_failure("test-provider")
        cb.record_failure("test-provider")
        assert cb.is_available("test-provider") is False
        cb.record_success("test-provider")
        assert cb.is_available("test-provider") is True  # back to CLOSED

    def test_interleaved_success_prevents_opening(self) -> None:
        cb = ProviderCircuitBreaker(failure_threshold=2, cooldown_seconds=30)
        cb.record_failure("test-provider")
        cb.record_success("test-provider")  # resets counter
        cb.record_failure("test-provider")
        assert cb.is_available("test-provider") is True  # only 1 consecutive failure

    def test_providers_are_isolated(self) -> None:
        cb = ProviderCircuitBreaker(failure_threshold=1, cooldown_seconds=30)
        cb.record_failure("provider-A")
        assert cb.is_available("provider-A") is False
        assert cb.is_available("provider-B") is True  # unaffected

    def test_record_success_on_closed_is_idempotent(self) -> None:
        cb = ProviderCircuitBreaker(failure_threshold=3, cooldown_seconds=30)
        cb.record_success("test-provider")  # no-op, no crash
        assert cb.is_available("test-provider") is True


class TestCircuitBreakerParameters:
    """Threshold and cooldown config pinning."""

    def test_custom_threshold_honored(self) -> None:
        cb = ProviderCircuitBreaker(failure_threshold=5, cooldown_seconds=30)
        for _ in range(4):
            cb.record_failure("test-provider")
            assert cb.is_available("test-provider") is True
        cb.record_failure("test-provider")
        assert cb.is_available("test-provider") is False

    def test_default_threshold(self) -> None:
        cb = ProviderCircuitBreaker()  # defaults: threshold=3, cooldown=60
        assert cb.failure_threshold == 3
        assert cb.cooldown_seconds == 60
