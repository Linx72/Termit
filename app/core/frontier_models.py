"""Идентификаторы frontier/cloud reference моделей DeepSeek (V4 ladder).

V4-Pro — целевой reference для benchmark и HIGH routing.
V4-Flash — более лёгкий open-weight вариант (self-host / cost cap).
V3 — fallback если V4 недоступен на провайдере.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.core.config import Settings

DEEPSEEK_V4_PRO = "openai_compat:deepseek-ai/DeepSeek-V4-Pro"
DEEPSEEK_V4_FLASH = "openai_compat:deepseek-ai/DeepSeek-V4-Flash"
DEEPSEEK_V3 = "openai_compat:deepseek-ai/DeepSeek-V3"

DEFAULT_FRONTIER_CHAIN: tuple[str, ...] = (
    DEEPSEEK_V4_PRO,
    DEEPSEEK_V4_FLASH,
    DEEPSEEK_V3,
)


def parse_model_chain(raw: str, *, fallback: tuple[str, ...] = DEFAULT_FRONTIER_CHAIN) -> list[str]:
    """Парсит comma-separated chain из env; пустые элементы отбрасываются."""
    text = raw.strip()
    if not text:
        return list(fallback)
    items = [part.strip() for part in text.split(",")]
    return [item for item in items if item]


def frontier_fallback_chain(settings: Settings) -> list[str]:
    """Порядок frontier моделей: explicit chain → single frontier env → default ladder."""
    chain_env = os.getenv("TERMIT_FRONTIER_FALLBACK_CHAIN", "").strip()
    if chain_env:
        return parse_model_chain(chain_env)
    primary = settings.frontier_fallback_model.strip()
    if primary:
        chain = [primary]
        for candidate in DEFAULT_FRONTIER_CHAIN:
            if candidate not in chain:
                chain.append(candidate)
        return chain
    return list(DEFAULT_FRONTIER_CHAIN)


def resolve_frontier_model(settings: Settings) -> str:
    """Первый frontier из ladder (обычно V4-Pro)."""
    chain = frontier_fallback_chain(settings)
    return chain[0] if chain else DEEPSEEK_V3


def resolve_benchmark_reference_model(settings: Settings) -> str:
    """Reference для capability benchmark: explicit env → cloud teacher → frontier."""
    explicit = settings.eval_benchmark_reference_model.strip()
    if explicit:
        return explicit
    cloud = settings.cloud_teacher_model.strip()
    if cloud:
        return cloud
    return resolve_frontier_model(settings)
