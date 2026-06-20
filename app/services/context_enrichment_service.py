from __future__ import annotations

import re

from app.domain.schemas import AgentProfileResponse, AgentRunRequest, ChatMessage, ChatRequest
from app.services.agent_prompt_cache_service import AgentPromptCacheService
from app.services.code_retrieval_service import CodeRetrievalService
from app.services.context_packing_service import ContextPackingService
from app.services.cursor_rules_importer import CursorRulesImporter
from app.services.project_rules_store import ProjectRulesStore
from app.services.repo_map_service import RepoMapService
from app.services.skill_store import SkillStore
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
        skill_store: SkillStore | None = None,
        cursor_rules: CursorRulesImporter | None = None,
        repo_map_enabled: bool = True,
        context_packing_enabled: bool = True,
        context_packing_incremental: bool = True,
        prompt_cache: AgentPromptCacheService | None = None,
    ) -> None:
        self._repo_map = repo_map
        self._context_packing = context_packing
        self._symbol_index = symbol_index
        self._retrieval = retrieval
        self._rules_store = rules_store
        self._skill_store = skill_store
        self._cursor_rules = cursor_rules or CursorRulesImporter()
        self._repo_map_enabled = repo_map_enabled
        self._context_packing_enabled = context_packing_enabled
        self._context_packing_incremental = context_packing_incremental
        self._prompt_cache = prompt_cache
        self._packing_seen_paths: set[str] = set()
        self._packing_query: str = ""

    @staticmethod
    def _infer_symbol_query(message: str) -> str | None:
        text = message.strip()
        if not text:
            return None
        match = re.search(
            r"(?:where is|where's|find|locate|где)\s+[`'\"]?([A-Za-z_][\w]*)[`'\"]?",
            text,
            flags=re.IGNORECASE,
        )
        if match:
            return match.group(1)
        at_match = re.search(r"@([A-Za-z_][\w]*)", text)
        if at_match:
            return at_match.group(1)
        return None

    def build_system_messages(
        self,
        payload: ChatRequest,
        *,
        include_skills: bool = True,
    ) -> list[ChatMessage]:
        messages: list[ChatMessage] = []
        prefix = payload.retrieval_path_prefix or ""

        if payload.project_id and self._rules_store is not None:
            rules_text = self._rules_store.format_for_prompt(
                payload.project_id,
                skill_store=self._skill_store,
                include_skills=include_skills,
            )
            if rules_text:
                messages.append(ChatMessage(role="system", content=rules_text))

        workspace_root = payload.retrieval_path_prefix or ""
        if workspace_root:
            cursor_block = self._cursor_rules.build_prompt_block(
                workspace_root,
                active_path=prefix,
            )
            if cursor_block:
                messages.append(ChatMessage(role="system", content=cursor_block))

        use_enrichment = (
            payload.use_retrieval
            or payload.use_repo_map
            or payload.use_context_packing
            or payload.symbol_query
            or self._infer_symbol_query(payload.message)
        )
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
                for item in hits[:2]:
                    graph = self._symbol_index.graph_context_for(item.name, limit=5)
                    if graph:
                        messages.append(ChatMessage(role="system", content=graph))
        elif self._symbol_index is not None:
            inferred = self._infer_symbol_query(payload.message)
            if inferred:
                hits = self._symbol_index.search(inferred, limit=5, path_prefix=prefix)
                if hits:
                    lines = ["[Symbol matches (inferred)]"]
                    for item in hits:
                        lines.append(f"- {item.kind} {item.name} @ {item.path}:{item.line}")
                    messages.append(ChatMessage(role="system", content="\n".join(lines)))
                    graph = self._symbol_index.graph_context_for(hits[0].name, limit=5)
                    if graph:
                        messages.append(ChatMessage(role="system", content=graph))

        if payload.use_context_packing and self._context_packing_enabled and self._context_packing is not None:
            if (
                self._context_packing_incremental
                and self._packing_query
                and payload.message != self._packing_query
            ):
                packed, seen = self._context_packing.pack_incremental(
                    query=payload.message,
                    changed_files=list(payload.changed_files),
                    seen_paths=self._packing_seen_paths,
                    retrieval=self._retrieval if payload.use_retrieval else None,
                    symbol_index=self._symbol_index,
                    retrieval_limit=payload.retrieval_limit,
                    path_prefix=prefix,
                    include_retrieval=False,
                )
                self._packing_seen_paths = seen
            elif self._context_packing_incremental and not self._packing_query:
                packed, seen = self._context_packing.pack_incremental(
                    query=payload.message,
                    changed_files=list(payload.changed_files),
                    seen_paths=self._packing_seen_paths,
                    retrieval=self._retrieval if payload.use_retrieval else None,
                    symbol_index=self._symbol_index,
                    retrieval_limit=payload.retrieval_limit,
                    path_prefix=prefix,
                    include_retrieval=True,
                )
                self._packing_query = payload.message
                self._packing_seen_paths = seen
            else:
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
        *,
        use_prompt_cache: bool = True,
    ) -> list[str]:
        cache_key = ""
        if use_prompt_cache and self._prompt_cache is not None:
            cache_key = AgentPromptCacheService.enrichment_key(
                agent_id=profile.agent_id,
                path_prefix=payload.retrieval_path_prefix or profile.retrieval_path_prefix or "",
                instruction=payload.input,
                changed_files=list(payload.changed_files),
            )
            cached = self._prompt_cache.get(cache_key)
            if cached is not None:
                return list(cached)

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
            symbol_query=payload.input if "@" in payload.input else self._infer_symbol_query(payload.input),
        )
        lines = [message.content for message in self.build_system_messages(chat_payload, include_skills=False)]
        if use_prompt_cache and self._prompt_cache is not None and cache_key:
            self._prompt_cache.put(cache_key, lines)
        return lines

    def list_project_skill_ids(self, project_id: str | None) -> list[str]:
        if not project_id or self._rules_store is None:
            return []
        payload = self._rules_store.get_rules(project_id)
        skills = payload.get("skills", [])
        if not isinstance(skills, list):
            return []
        return [str(item).strip() for item in skills if str(item).strip()]
