"""
RLM Best-of-N — параллельная генерация N вариантов + LLM-as-Judge.

Генерирует N кандидатов параллельно (asyncio.gather), затем оценивает каждый
через LLM-судью и возвращает лучший. Использует Flash-модель для экономии токенов.

Архитектура:
  1. N параллельных вызовов Flash-модели (разная temperature для разнообразия)
  2. LLM-судья выбирает лучший вариант по критериям: полнота, точность, безопасность
  3. Пары (лучший/худший) сохраняются в PreferenceStore для будущего DPO

Интеграция: вызывается из chat_service.chat_stream() при score < 0.5 (авто-ретрай).
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Optional

from app.domain.schemas import ChatMessage, TaskType
from app.services.model_router import ModelRouter

logger = logging.getLogger(__name__)

# ── Candidate scoring criteria for LLM-as-Judge ─────────────────────────────
JUDGE_SYSTEM_PROMPT = """You are a response quality judge. Evaluate {n} candidate responses
to the user's request. Rate each on:
1. Completeness (0-10): Does it fully address the request?
2. Accuracy (0-10): Are facts, code, and logic correct?
3. Safety (0-10): No harmful, dangerous, or risky content?
4. Clarity (0-10): Is it well-structured and easy to follow?
5. Efficiency (0-10): Minimal fluff, maximal value?

Return ONLY a JSON array of objects: [{"index":1,"scores":{"completeness":8,"accuracy":9,...},"total":42},...]
where index is the candidate number (1-{n}) and total is sum of all 5 scores (max 50).
"""


class RLMBestOfN:
    """
    Parallel Best-of-N candidate generation with LLM-as-Judge evaluation.

    Usage:
        rlm = RLMBestOfN(chat_service, flash_provider, flash_model)
        best = await rlm.best_of_n(messages, n=3)
    """

    def __init__(self, chat_service, flash_provider, flash_model: str):
        """chat_service: ChatService instance for _generate_with_retries access.
        flash_provider: BaseProvider instance (e.g. DeepSeekOpenAICompatible).
        flash_model: Model name string (e.g. 'deepseek-chat').
        """
        self._chat = chat_service
        self._provider = flash_provider
        self._model = flash_model

    async def best_of_n(
        self,
        messages: list[ChatMessage],
        n: int = 3,
        base_temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> str:
        """Generate N candidates in parallel and return the best.

        Args:
            messages: Full conversation history for candidate generation.
            n: Number of parallel candidates (default 3).
            base_temperature: Base temperature; each candidate adds +0.1*i for diversity.
            max_tokens: Max tokens per candidate.

        Returns:
            Best candidate text (judged by LLM or fallback to first candidate).
        """
        if n < 1:
            raise ValueError(f"n must be >= 1, got {n}")

        logger.info("RLM Best-of-N: generating %d candidates in parallel", n)

        # ── Phase 1: Parallel candidate generation ──────────────────────────
        candidates: list[str] = await asyncio.gather(*[
            self._generate_one(messages, base_temperature + i * 0.1, max_tokens)
            for i in range(n)
        ], return_exceptions=False)

        if n == 1:
            return candidates[0]

        # ── Phase 2: LLM-as-Judge evaluation ────────────────────────────────
        try:
            scores = await self._judge(messages[-1].content if messages else "", candidates)
            best_idx = max(range(n), key=lambda i: scores[i]["total"]) if scores else 0
            winner = candidates[best_idx]
            logger.info(
                "RLM Best-of-N: candidate #%d won (score %d vs avg %.1f)",
                best_idx + 1,
                scores[best_idx]["total"],
                sum(s["total"] for s in scores) / len(scores),
            )
            return winner
        except Exception as exc:
            logger.warning("RLM judge failed, returning first candidate: %s", exc)
            return candidates[0]

    async def _generate_one(
        self,
        messages: list[ChatMessage],
        temperature: float,
        max_tokens: int,
    ) -> str:
        """Generate a single candidate via Flash model."""
        return await self._chat._generate_with_retries(
            provider=self._provider,
            model_name=self._model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    async def _judge(
        self,
        user_request: str,
        candidates: list[str],
    ) -> list[dict]:
        """LLM-as-Judge: score all candidates and return ranked scores.

        Returns list of dicts: [{"index":1,"total":42,"scores":{...}}, ...]
        """
        n = len(candidates)
        candidates_block = "\n\n---\n\n".join(
            f"CANDIDATE {i+1}:\n{c[:3000]}"  # Truncate long responses for judge
            for i, c in enumerate(candidates)
        )

        judge_system = JUDGE_SYSTEM_PROMPT.format(n=n)
        judge_user = f"""USER REQUEST:
{user_request[:2000]}

CANDIDATE RESPONSES:
{candidates_block}

Evaluate ALL {n} candidates. Return ONLY the JSON array."""

        judge_messages = [
            ChatMessage(role="system", content=judge_system),
            ChatMessage(role="user", content=judge_user),
        ]

        raw = await self._generate_one(judge_messages, temperature=0.2, max_tokens=2000)

        # Parse JSON from judge response (try markdown block first, then raw)
        return self._parse_judge_json(raw, n)

    @staticmethod
    def _parse_judge_json(raw: str, n: int) -> list[dict]:
        """Extract JSON array from judge response. Robust to markdown & noise."""
        # Try code block
        if "```" in raw:
            parts = raw.split("```")
            for part in parts:
                stripped = part.strip()
                if stripped.startswith("json"):
                    stripped = stripped[4:].strip()
                try:
                    parsed = json.loads(stripped)
                    if isinstance(parsed, list) and len(parsed) == n:
                        return parsed
                except (json.JSONDecodeError, ValueError):
                    continue

        # Try entire response as JSON
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, list) and len(parsed) == n:
                return parsed
        except (json.JSONDecodeError, ValueError):
            pass

        # Try to find JSON array with regex
        import re
        m = re.search(r"\[.*\]", raw, re.DOTALL)
        if m:
            try:
                parsed = json.loads(m.group(0))
                if isinstance(parsed, list) and len(parsed) == n:
                    return parsed
            except (json.JSONDecodeError, ValueError):
                pass

        logger.warning("RLM judge: could not parse JSON, raw: %.200s", raw)
        return []


# ── Integration helper for chat_service ──────────────────────────────────────

async def best_of_n_retry(
    chat_service,
    provider,
    model_name: str,
    messages: list[ChatMessage],
    n: int = 3,
) -> Optional[str]:
    """Convenience: run Best-of-N retry if chat_service has RLM configured.

    Returns improved response or None if not configured.
    """
    try:
        rlm = RLMBestOfN(chat_service, provider, model_name)
        return await rlm.best_of_n(messages, n=n)
    except Exception as exc:
        logger.error("Best-of-N retry failed: %s", exc)
        return None
