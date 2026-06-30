"""
Health-check endpoint with circuit breaker state.
GET /health — overall status
GET /health/circuit-breakers — per-provider circuit breaker states
"""

from fastapi import APIRouter

from app.state import get_circuit_breaker

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check() -> dict:
    """Overall health status."""
    cb = get_circuit_breaker()
    states = cb.get_state()
    degraded = any(s.startswith("OPEN") for s in states.values())
    return {
        "status": "degraded" if degraded else "healthy",
        "circuit_breakers": states,
    }


@router.get("/health/circuit-breakers")
async def circuit_breaker_states() -> dict:
    """Per-provider circuit breaker states."""
    return {"circuit_breakers": get_circuit_breaker().get_state()}
