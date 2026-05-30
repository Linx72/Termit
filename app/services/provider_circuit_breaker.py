import time
from threading import Lock


class ProviderCircuitBreaker:
    def __init__(self, failure_threshold: int = 3, cooldown_seconds: int = 60) -> None:
        self.failure_threshold = failure_threshold
        self.cooldown_seconds = cooldown_seconds
        self._failures: dict[str, int] = {}
        self._opened_at: dict[str, float] = {}
        self._lock = Lock()

    def is_available(self, provider_name: str) -> bool:
        with self._lock:
            opened_at = self._opened_at.get(provider_name)
            if opened_at is None:
                return True
            if time.time() - opened_at >= self.cooldown_seconds:
                self._opened_at.pop(provider_name, None)
                self._failures[provider_name] = 0
                return True
            return False

    def record_success(self, provider_name: str) -> None:
        with self._lock:
            self._failures[provider_name] = 0
            self._opened_at.pop(provider_name, None)

    def record_failure(self, provider_name: str) -> None:
        with self._lock:
            count = self._failures.get(provider_name, 0) + 1
            self._failures[provider_name] = count
            if count >= self.failure_threshold:
                self._opened_at[provider_name] = time.time()
