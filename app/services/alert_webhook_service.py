from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Optional


class AlertWebhookService:
    def __init__(self, webhook_url: str = "") -> None:
        self.webhook_url = webhook_url.strip()

    @property
    def enabled(self) -> bool:
        return bool(self.webhook_url)

    def send(self, *, title: str, status: str, detail: str, payload: Optional[dict[str, object]] = None) -> dict[str, object]:
        if not self.enabled:
            return {"sent": False, "reason": "webhook_not_configured"}

        body = {
            "text": f"[Termit:{status}] {title}\n{detail}",
            "blocks": [
                {"type": "section", "text": {"type": "mrkdwn", "text": f"*{title}* (`{status}`)"}},
                {"type": "section", "text": {"type": "mrkdwn", "text": detail}},
            ],
        }
        if payload:
            body["attachments"] = [{"text": json.dumps(payload, ensure_ascii=False)[:3000]}]

        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(  # noqa: S310
            self.webhook_url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=8) as response:  # noqa: S310
                return {"sent": True, "status_code": response.status}
        except urllib.error.URLError as exc:
            return {"sent": False, "reason": str(exc)}
