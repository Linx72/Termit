"""Video generation providers: Fal queue + ffmpeg stub I2V."""

from __future__ import annotations

import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import httpx

from app.services.media_compose_service import MediaComposeError, ffmpeg_available


class MediaVideoError(Exception):
    pass


@dataclass(frozen=True)
class VideoRenderResult:
    output_path: Path
    provider: str
    cost_usd: float
    duration_sec: float


class StubVideoProvider:
    """ffmpeg zoompan on source image — local I2V stand-in."""

    def __init__(self, *, ffmpeg_path: str = "ffmpeg", ffprobe_path: str = "ffprobe") -> None:
        self._ffmpeg = ffmpeg_path
        self._ffprobe = ffprobe_path

    def render_image_to_video(
        self,
        *,
        image_path: Path,
        output_path: Path,
        duration_sec: float = 5.0,
        width: int = 1280,
        height: int = 720,
    ) -> VideoRenderResult:
        if not ffmpeg_available(self._ffmpeg):
            raise MediaVideoError("ffmpeg required for stub I2V")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        frames = max(30, int(duration_sec * 30))
        vf = (
            f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
            f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,"
            f"zoompan=z='min(zoom+0.002,1.3)':d={frames}:s={width}x{height},format=yuv420p"
        )
        proc = subprocess.run(
            [
                self._ffmpeg,
                "-y",
                "-loop",
                "1",
                "-i",
                str(image_path),
                "-vf",
                vf,
                "-t",
                str(max(1.0, duration_sec)),
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                str(output_path),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode != 0:
            raise MediaVideoError((proc.stderr or proc.stdout)[:600])
        from app.services.media_compose_service import probe_duration

        return VideoRenderResult(
            output_path=output_path,
            provider="stub_i2v",
            cost_usd=0.0,
            duration_sec=probe_duration(output_path, self._ffprobe),
        )


class FalVideoProvider:
    def __init__(
        self,
        *,
        api_key: str,
        model_id: str = "fal-ai/minimax/video-01-live/image-to-video",
        default_cost_usd: float = 0.50,
        poll_interval_sec: float = 2.0,
        poll_timeout_sec: float = 300.0,
    ) -> None:
        self._api_key = api_key.strip()
        self._model_id = model_id
        self._default_cost = default_cost_usd
        self._poll_interval = poll_interval_sec
        self._poll_timeout = poll_timeout_sec

    @property
    def available(self) -> bool:
        return bool(self._api_key)

    def render_image_to_video(
        self,
        *,
        image_url: str,
        prompt: str,
        output_path: Path,
        duration_sec: float = 5.0,
    ) -> VideoRenderResult:
        if not self._api_key:
            raise MediaVideoError("FAL_KEY is not configured.")
        headers = {"Authorization": f"Key {self._api_key}", "Content-Type": "application/json"}
        payload = {
            "prompt": prompt,
            "image_url": image_url,
            "duration": int(max(3, min(duration_sec, 10))),
        }
        base = f"https://queue.fal.run/{self._model_id}"
        with httpx.Client(timeout=60.0) as client:
            submit = client.post(base, headers=headers, json=payload)
        if submit.status_code >= 400:
            raise MediaVideoError(f"Fal submit {submit.status_code}: {submit.text[:400]}")
        data = submit.json()
        status_url = data.get("status_url") or data.get("response_url")
        if not status_url:
            raise MediaVideoError("Fal response missing status_url")
        deadline = time.time() + self._poll_timeout
        video_url: Optional[str] = None
        with httpx.Client(timeout=60.0) as client:
            while time.time() < deadline:
                poll = client.get(str(status_url), headers=headers)
                if poll.status_code >= 400:
                    raise MediaVideoError(f"Fal poll {poll.status_code}")
                body = poll.json()
                state = str(body.get("status", "")).upper()
                if state in {"COMPLETED", "OK", "SUCCESS"}:
                    result = body.get("response") or body
                    video_url = (
                        result.get("video", {}).get("url")
                        if isinstance(result.get("video"), dict)
                        else result.get("video_url")
                    )
                    if not video_url and isinstance(result.get("video"), str):
                        video_url = result.get("video")
                    break
                if state in {"FAILED", "ERROR"}:
                    raise MediaVideoError(str(body.get("error", "Fal job failed")))
                time.sleep(self._poll_interval)
        if not video_url:
            raise MediaVideoError("Fal job timed out or missing video URL")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with httpx.Client(timeout=120.0) as client:
            video_resp = client.get(str(video_url))
        if video_resp.status_code >= 400:
            raise MediaVideoError(f"Failed to download Fal video: {video_resp.status_code}")
        output_path.write_bytes(video_resp.content)
        from app.services.media_compose_service import probe_duration

        return VideoRenderResult(
            output_path=output_path,
            provider="fal",
            cost_usd=self._default_cost,
            duration_sec=probe_duration(output_path, "ffprobe"),
        )
