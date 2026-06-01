from __future__ import annotations

import re
from dataclasses import dataclass

SECRET_PATTERNS = (
    re.compile(r"(?i)(api[_-]?key|secret|password|token)\s*[:=]\s*\S{8,}"),
    re.compile(r"-----BEGIN (?:RSA |EC )?PRIVATE KEY-----"),
    re.compile(r"sk-[a-zA-Z0-9]{20,}"),
    re.compile(r"ghp_[a-zA-Z0-9]{20,}"),
)


@dataclass(frozen=True)
class GuardrailResult:
    allowed: bool
    reason: str = ""
    severity: str = "info"


class GuardrailService:
    def __init__(
        self,
        block_secrets_in_prompt: bool = True,
        max_patch_chars: int = 50000,
    ) -> None:
        self.block_secrets_in_prompt = block_secrets_in_prompt
        self.max_patch_chars = max(1024, max_patch_chars)

    def check_prompt(self, text: str) -> GuardrailResult:
        if not self.block_secrets_in_prompt or not text.strip():
            return GuardrailResult(allowed=True)
        for pattern in SECRET_PATTERNS:
            if pattern.search(text):
                return GuardrailResult(
                    allowed=False,
                    reason="Prompt appears to contain secrets or credentials.",
                    severity="block",
                )
        return GuardrailResult(allowed=True)

    def check_patch_content(self, content: str | None) -> GuardrailResult:
        if content is None:
            return GuardrailResult(allowed=True)
        if len(content) > self.max_patch_chars:
            return GuardrailResult(
                allowed=False,
                reason=f"Patch exceeds max size ({self.max_patch_chars} chars).",
                severity="block",
            )
        return GuardrailResult(allowed=True)
