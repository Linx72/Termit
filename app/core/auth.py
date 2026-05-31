from typing import Optional

from fastapi import Request


def extract_api_key(request: Request) -> Optional[str]:
    header_key = request.headers.get("X-API-Key")
    if header_key:
        return header_key.strip()

    auth_header = request.headers.get("Authorization", "")
    if auth_header.lower().startswith("bearer "):
        token = auth_header[7:].strip()
        return token or None
    return None


def is_public_path(path: str) -> bool:
    if path in {
        "/",
        "/health",
        "/healthz",
        "/docs",
        "/openapi.json",
        "/redoc",
        "/api/ops/readiness",
        "/api/metrics/thresholds",
    }:
        return True
    return path.startswith("/docs/")
