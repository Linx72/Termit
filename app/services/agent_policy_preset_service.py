"""Policy presets for agent runs (solo / team / strict)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from app.domain.schemas import AgentProfileResponse, AgentRunRequest


@dataclass(frozen=True)
class AgentPolicyPreset:
    preset_id: str
    name: str
    description_ru: str
    description_en: str
    max_tool_steps: int
    allow_online: bool
    auto_confirm_risky_tools: bool
    verify_after_patch: bool
    enabled_tools: list[str]
    execution_mode: str


class AgentPolicyPresetService:
    def __init__(self, presets_path: str) -> None:
        self._path = Path(presets_path)
        self._presets: dict[str, AgentPolicyPreset] = {}
        self._load()

    def _load(self) -> None:
        self._presets.clear()
        if not self._path.is_file():
            return
        payload = json.loads(self._path.read_text(encoding="utf-8"))
        for item in payload.get("presets", []):
            preset = AgentPolicyPreset(
                preset_id=str(item["preset_id"]),
                name=str(item["name"]),
                description_ru=str(item.get("description_ru", "")),
                description_en=str(item.get("description_en", "")),
                max_tool_steps=int(item.get("max_tool_steps", 6)),
                allow_online=bool(item.get("allow_online", False)),
                auto_confirm_risky_tools=bool(item.get("auto_confirm_risky_tools", False)),
                verify_after_patch=bool(item.get("verify_after_patch", True)),
                enabled_tools=[str(tool) for tool in item.get("enabled_tools", [])],
                execution_mode=str(item.get("execution_mode", "local")),
            )
            self._presets[preset.preset_id] = preset

    def list_presets(self) -> list[AgentPolicyPreset]:
        return list(self._presets.values())

    def get_preset(self, preset_id: str) -> Optional[AgentPolicyPreset]:
        return self._presets.get(preset_id.strip())

    def apply_to_run(
        self,
        profile: AgentProfileResponse,
        payload: AgentRunRequest,
    ) -> tuple[AgentProfileResponse, AgentRunRequest]:
        preset_id = (payload.policy_preset or "").strip()
        if not preset_id:
            return profile, payload
        preset = self.get_preset(preset_id)
        if preset is None:
            return profile, payload

        profile_tools = set(profile.enabled_tools or [])
        preset_tools = set(preset.enabled_tools)
        merged_tools = sorted(profile_tools & preset_tools if profile_tools else preset_tools)

        updated_profile = profile.model_copy(
            update={
                "max_tool_steps": preset.max_tool_steps,
                "allow_online": preset.allow_online,
                "enabled_tools": merged_tools or list(preset.enabled_tools),
                "use_tool_loop": True,
            }
        )
        execution_mode = payload.execution_mode or preset.execution_mode
        updated_payload = payload.model_copy(update={"execution_mode": execution_mode})
        return updated_profile, updated_payload

    def preset_to_dict(self, preset: AgentPolicyPreset) -> dict[str, object]:
        return {
            "preset_id": preset.preset_id,
            "name": preset.name,
            "description_ru": preset.description_ru,
            "description_en": preset.description_en,
            "max_tool_steps": preset.max_tool_steps,
            "allow_online": preset.allow_online,
            "auto_confirm_risky_tools": preset.auto_confirm_risky_tools,
            "verify_after_patch": preset.verify_after_patch,
            "enabled_tools": preset.enabled_tools,
            "execution_mode": preset.execution_mode,
        }
