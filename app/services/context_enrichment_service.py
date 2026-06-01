from __future__ import annotations

from app.domain.schemas import AgentProfileResponse, AgentRunRequest, ChatMessage, ChatRequest
from app.services.code_retrieval_service import CodeRetrievalService
from app.services.context_packing_service import ContextPackingService
from app.services.project_rules_store import ProjectRulesStore
from app.services.repo_map_service import RepoMapService
from app.services.symbol_index_service import SymbolIndexService


class ContextEnrichmentService:
    def __init__(
        self,
        *,
        repo_map: RepoMapService | None = None,
        context_packing: ContextPackingService | None = None,
        symbol_index: SymbolIndexService | None = None,
        retrieval: CodeRetrievalService | None = None,
        rules_store: ProjectRulesStore | None = None,
        repo_map_enabled: bool = True,
        context_packing_enabled: bool = True,
    ) -> None:
        self._repo_map = repo_map
        self._context_packing = context_packing
        self._symbol_index = symbol_index
        self._retrieval = retrieval
        self._rules_store = rules_store
        self._repo_map_enabled = repo_map_enabled
        self._context_packing_enabled = context_packing_enabled

    def build_system_messages(self, payload: ChatRequest) -> list[ChatMessage]:
        messages: list[ChatMessage] = []
        prefix = payload.retrieval_path_prefix or ""

        if payload.project_id and self._rules_store is not None:
            rules_text = self._rules_store.format_for_prompt(payload.project_id)
            if rules_text:
                messages.append(ChatMessage(role="system", content=rules_text))

        use_enrichment = payload.use_retrieval or payload.use_repo_map or payload.use_context_packing
        if not use_enrichment:
            return messages

        if payload.use_repo_map and self._repo_map_enabled and self._repo_map is not None:
            messages.append(
                ChatMessage(role="system", content=self._repo_map.build_summary(path_prefix=prefix))
            )

        if payload.symbol_query and self._symbol_index is not None:
            hits = self._symbol_index.search(
                payload.symbol_query,
                limit=8,
                path_prefix=prefix,
            )
            if hits:
                lines = ["[Symbol matches]"]
                for item in hits:
                    lines.append(f"- {item.kind} {item.name} @ {item.path}:{item.line}")
                messages.append(ChatMessage(role="system", content="\n".join(lines)))

        if payload.use_context_packing and self._context_packing_enabled and self._context_packing is not None:
            packed = self._context_packing.pack(
                query=payload.message,
                changed_files=list(payload.changed_files),
                retrieval=self._retrieval if payload.use_retrieval else None,
                symbol_index=self._symbol_index,
                retrieval_limit=payload.retrieval_limit,
                path_prefix=prefix,
            )
            if packed:
                messages.append(ChatMessage(role="system", content=packed))
        elif payload.use_retrieval and self._retrieval is not None:
            hits = self._retrieval.search(
                payload.message,
                limit=payload.retrieval_limit,
                path_prefix=prefix,
            )
            if hits:
                from app.services.context_compaction import ContextCompactor

                body = ContextCompactor.format_retrieval_context(
                    [(item.path, item.excerpt, item.score) for item in hits]
                )
                messages.append(ChatMessage(role="system", content=body))

        return messages

    def build_agent_context_lines(
        self,
        payload: AgentRunRequest,
        profile: AgentProfileResponse,
    ) -> list[str]:
        use_retrieval = (
            profile.use_retrieval if payload.use_retrieval is None else payload.use_retrieval
        )
        chat_payload = ChatRequest(
            message=payload.input,
            task_type=profile.task_type,
            use_retrieval=bool(use_retrieval),
            use_repo_map=True,
            use_context_packing=True,
            retrieval_limit=payload.retrieval_limit or profile.retrieval_limit,
            retrieval_path_prefix=payload.retrieval_path_prefix or profile.retrieval_path_prefix or "",
            changed_files=list(payload.changed_files),
            project_id=payload.project_id,
            symbol_query=payload.input if "@" in payload.input else None,
        )
        return [message.content for message in self.build_system_messages(chat_payload)]
