from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from uuid import uuid4

from app.domain.schemas import AgentProfileCreateRequest, AgentProfileResponse


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class AgentRegistryStore:
    def __init__(self, file_path: str) -> None:
        self._path = Path(file_path)
        self._lock = Lock()
        self._agents: dict[str, AgentProfileResponse] = {}
        self._load()

    def list_agents(self) -> list[AgentProfileResponse]:
        with self._lock:
            agents = [item.model_copy(deep=True) for item in self._agents.values()]
        return sorted(agents, key=lambda item: item.updated_at, reverse=True)

    def get_agent(self, agent_id: str) -> AgentProfileResponse | None:
        with self._lock:
            item = self._agents.get(agent_id)
            return item.model_copy(deep=True) if item else None

    def create_agent(self, payload: AgentProfileCreateRequest) -> AgentProfileResponse:
        now = _utc_now_iso()
        agent = AgentProfileResponse(
            agent_id=f"agt_{uuid4().hex[:12]}",
            name=payload.name.strip(),
            description=payload.description.strip(),
            system_prompt=payload.system_prompt,
            task_type=payload.task_type,
            model=payload.model,
            use_memory=payload.use_memory,
            use_retrieval=payload.use_retrieval,
            retrieval_limit=payload.retrieval_limit,
            retrieval_path_prefix=payload.retrieval_path_prefix,
            temperature=payload.temperature,
            max_tokens=payload.max_tokens,
            allow_online=payload.allow_online,
            online_max_steps=payload.online_max_steps,
            online_timeout_seconds=payload.online_timeout_seconds,
            online_capture_links_limit=payload.online_capture_links_limit,
            enabled_tools=list(payload.enabled_tools),
            created_at=now,
            updated_at=now,
        )
        with self._lock:
            self._agents[agent.agent_id] = agent
            self._persist_locked()
        return agent.model_copy(deep=True)

    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            payload = json.loads(self._path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return
        if not isinstance(payload, dict):
            return
        raw_agents = payload.get("agents", [])
        if not isinstance(raw_agents, list):
            return
        loaded: dict[str, AgentProfileResponse] = {}
        for raw in raw_agents:
            if not isinstance(raw, dict):
                continue
            try:
                model = AgentProfileResponse.model_validate(raw)
            except Exception:  # noqa: BLE001
                continue
            loaded[model.agent_id] = model
        self._agents = loaded

    def _persist_locked(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "agents": [agent.model_dump(mode="json") for agent in self._agents.values()],
            "updated_at": _utc_now_iso(),
        }
        self._path.write_text(json.dumps(data, ensure_ascii=True, indent=2), encoding="utf-8")
