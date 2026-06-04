from __future__ import annotations

import json
import subprocess
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass(frozen=True)
class HookEvent:
    event_type: str
    run_id: str
    agent_id: str
    state: str
    message: str = ""
    extra: dict[str, object] | None = None


class AgentHookService:
    def __init__(
        self,
        config_path: str,
        webhook_url: str = "",
        enabled: bool = True,
    ) -> None:
        self.config_path = Path(config_path)
        self.webhook_url = webhook_url.strip()
        self.enabled = enabled

    def list_configured_events(self) -> list[str]:
        hooks = self._load_hooks_map()
        return sorted(str(key) for key in hooks.keys())

    def count_local_scripts(self) -> int:
        total = 0
        for entries in self._load_hooks_map().values():
            if not isinstance(entries, list):
                continue
            for entry in entries:
                if isinstance(entry, dict) and str(entry.get("command", "")).strip():
                    total += 1
        return total

    def emit(self, event: HookEvent) -> None:
        if not self.enabled:
            return
        body = {
            "event_type": event.event_type,
            "run_id": event.run_id,
            "agent_id": event.agent_id,
            "state": event.state,
            "message": event.message,
            "extra": event.extra or {},
        }
        self._run_local_scripts(event.event_type, body)
        if self.webhook_url:
            self._post_webhook(body)

    def _load_hooks_map(self) -> dict[str, object]:
        if not self.config_path.is_file():
            return {}
        try:
            payload = json.loads(self.config_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
        hooks = payload.get("hooks", {})
        return hooks if isinstance(hooks, dict) else {}

    def _run_local_scripts(self, event_type: str, payload: dict[str, object]) -> None:
        hooks = self._load_hooks_map()
        entries = hooks.get(event_type, [])
        if not isinstance(entries, list):
            return
        input_json = json.dumps(payload, ensure_ascii=True)
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            command = str(entry.get("command", "")).strip()
            if not command:
                continue
            self._exec_hook_command(command, input_json)

    def _exec_hook_command(self, command: str, input_json: str) -> None:
        try:
            subprocess.run(
                command,
                shell=True,
                input=input_json,
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            return

    def _post_webhook(self, payload: dict[str, object]) -> None:
        data = json.dumps(payload, ensure_ascii=True).encode("utf-8")
        request = urllib.request.Request(  # noqa: S310
            url=self.webhook_url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=10):  # noqa: S310
                return
        except (urllib.error.URLError, TimeoutError):
            return
