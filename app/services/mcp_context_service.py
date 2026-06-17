from __future__ import annotations

import json

from app.domain.schemas import AgentProfileResponse
from app.services.mcp_registry_service import McpRegistryService


class McpContextService:
    """Build MCP resource/prompt catalog lines for agent run context."""

    def __init__(self, registry: McpRegistryService) -> None:
        self._registry = registry

    def build_context_lines(
        self,
        profile: AgentProfileResponse,
        *,
        max_servers: int = 3,
        max_resources_per_server: int = 5,
        max_reads_per_server: int = 2,
        max_read_chars: int = 500,
    ) -> list[str]:
        if not self._mcp_tools_enabled(profile):
            return []

        server_ids = self._allowed_server_ids(profile)
        if not server_ids:
            return []

        lines: list[str] = ["[MCP context]"]
        injected = False

        for server_id in server_ids[:max_servers]:
            try:
                server = self._registry.get_server(server_id)
            except ValueError:
                continue
            if server is None or not server.enabled:
                continue

            try:
                resources = self._registry.list_resources(server_id)
            except Exception:  # noqa: BLE001
                continue
            if not resources:
                continue

            injected = True
            lines.append(f"Server `{server_id}` resources:")
            for resource in resources[:max_resources_per_server]:
                label = resource.name or resource.uri
                mime = f" ({resource.mime_type})" if resource.mime_type else ""
                desc = f" — {resource.description}" if resource.description else ""
                lines.append(f"- {label}{mime}: {resource.uri}{desc}")

            reads = 0
            for resource in resources[:max_reads_per_server]:
                if reads >= max_reads_per_server:
                    break
                try:
                    payload = self._registry.read_resource(server_id, resource.uri)
                except Exception:  # noqa: BLE001
                    continue
                text = self._extract_resource_text(payload, max_read_chars)
                if not text:
                    continue
                reads += 1
                lines.append(f"Resource `{resource.uri}` preview:\n{text}")

        if not injected:
            return []
        lines.append("Use mcp_read_resource / mcp_get_prompt for full content.")
        return lines

    @staticmethod
    def _mcp_tools_enabled(profile: AgentProfileResponse) -> bool:
        enabled = set(profile.enabled_tools)
        return bool(
            {"mcp_invoke", "mcp_read_resource", "mcp_get_prompt"} & enabled
        )

    def _allowed_server_ids(self, profile: AgentProfileResponse) -> list[str]:
        allowed = [item.strip() for item in profile.allowed_mcp_servers if item.strip()]
        if not allowed or "*" in allowed:
            return [server.server_id for server in self._registry.list_servers() if server.enabled]
        return allowed

    @staticmethod
    def _extract_resource_text(payload: dict[str, object], max_chars: int) -> str:
        contents = payload.get("contents")
        if not isinstance(contents, list):
            return ""
        chunks: list[str] = []
        for item in contents:
            if not isinstance(item, dict):
                continue
            text = item.get("text")
            if isinstance(text, str) and text.strip():
                chunks.append(text.strip())
                continue
            blob = item.get("blob")
            if isinstance(blob, str) and blob.strip():
                chunks.append(f"[binary blob {len(blob)} chars omitted]")
        joined = "\n".join(chunks).strip()
        if len(joined) > max_chars:
            return joined[: max_chars - 3] + "..."
        return joined

    @staticmethod
    def serialize_read_result(payload: dict[str, object]) -> str:
        return json.dumps(payload, ensure_ascii=False)

    @staticmethod
    def serialize_prompt_result(payload: dict[str, object]) -> str:
        return json.dumps(payload, ensure_ascii=False)
