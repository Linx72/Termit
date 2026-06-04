"""ffmpeg-based media composition: slideshow, audio mix, subtitles."""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from uuid import uuid4


class MediaComposeError(Exception):
    pass


PRESETS: dict[str, tuple[int, int]] = {
    "youtube_16x9": (1280, 720),
    "reels_9x16": (720, 1280),
    "telegram_1x1": (1080, 1080),
}


@dataclass(frozen=True)
class ComposeResult:
    output_path: Path
    duration_sec: float
    width: int
    height: int


def ffmpeg_available(ffmpeg_path: str = "ffmpeg") -> bool:
    return shutil.which(ffmpeg_path) is not None


def _run(cmd: list[str], *, cwd: Optional[Path] = None) -> None:
    proc = subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise MediaComposeError(
            f"ffmpeg failed ({proc.returncode}): {(proc.stderr or proc.stdout)[:800]}"
        )


def probe_duration(path: Path, ffprobe_path: str = "ffprobe") -> float:
    if not shutil.which(ffprobe_path):
        return 0.0
    proc = subprocess.run(
        [
            ffprobe_path,
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        return 0.0
    try:
        return float(proc.stdout.strip())
    except ValueError:
        return 0.0


class MediaComposeService:
    def __init__(
        self,
        *,
        ffmpeg_path: str = "ffmpeg",
        ffprobe_path: str = "ffprobe",
    ) -> None:
        self._ffmpeg = ffmpeg_path
        self._ffprobe = ffprobe_path

    def ensure_ffmpeg(self) -> None:
        if not ffmpeg_available(self._ffmpeg):
            raise MediaComposeError(
                f"ffmpeg not found at '{self._ffmpeg}'. Install ffmpeg or set TERMIT_FFMPEG_PATH."
            )

    def compose_slideshow(
        self,
        *,
        slides: list[dict[str, object]],
        output_path: Path,
        preset: str = "youtube_16x9",
        crossfade_sec: float = 0.3,
        fps: int = 30,
        audio_path: Optional[Path] = None,
        subtitle_path: Optional[Path] = None,
    ) -> ComposeResult:
        """Build MP4 from image paths + optional audio/subtitles."""
        self.ensure_ffmpeg()
        if not slides:
            raise MediaComposeError("compose_media requires at least one slide.")
        width, height = PRESETS.get(preset, PRESETS["youtube_16x9"])
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with tempfile.TemporaryDirectory(prefix="termit-compose-") as tmp:
            tmp_dir = Path(tmp)
            clip_paths: list[Path] = []
            for index, slide in enumerate(slides):
                image_path = Path(str(slide["path"]))
                duration = float(slide.get("duration_sec", 3))
                if not image_path.is_file():
                    raise MediaComposeError(f"Slide image missing: {image_path}")
                if image_path.suffix.lower() in {".mp4", ".mov", ".webm", ".mkv"}:
                    clip_paths.append(image_path)
                    continue
                clip = tmp_dir / f"clip_{index:03d}.mp4"
                scale_pad = (
                    f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
                    f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,format=yuv420p"
                )
                _run(
                    [
                        self._ffmpeg,
                        "-y",
                        "-loop",
                        "1",
                        "-framerate",
                        str(fps),
                        "-t",
                        str(max(0.5, duration)),
                        "-i",
                        str(image_path),
                        "-vf",
                        scale_pad,
                        "-c:v",
                        "libx264",
                        "-pix_fmt",
                        "yuv420p",
                        str(clip),
                    ]
                )
                clip_paths.append(clip)

            if len(clip_paths) == 1:
                video_only = clip_paths[0]
            elif crossfade_sec > 0 and len(clip_paths) > 1:
                video_only = tmp_dir / "xfade.mp4"
                self._xfade_clips(clip_paths, video_only, crossfade_sec=crossfade_sec, fps=fps)
            else:
                video_only = tmp_dir / "concat.mp4"
                self._concat_clips(clip_paths, video_only)

            final_input = video_only
            if audio_path is not None and audio_path.is_file():
                merged = tmp_dir / "merged.mp4"
                _run(
                    [
                        self._ffmpeg,
                        "-y",
                        "-i",
                        str(video_only),
                        "-i",
                        str(audio_path),
                        "-c:v",
                        "copy",
                        "-c:a",
                        "aac",
                        "-shortest",
                        str(merged),
                    ]
                )
                final_input = merged

            vf_parts: list[str] = []
            if subtitle_path is not None and subtitle_path.is_file():
                escaped = str(subtitle_path).replace("\\", "\\\\").replace(":", "\\:")
                vf_parts.append(f"subtitles='{escaped}'")

            cmd = [self._ffmpeg, "-y", "-i", str(final_input)]
            if vf_parts:
                cmd.extend(["-vf", ",".join(vf_parts)])
                cmd.extend(["-c:v", "libx264", "-c:a", "copy"])
            else:
                cmd.extend(["-c", "copy"])
            cmd.append(str(output_path))
            _run(cmd)

        duration = probe_duration(output_path, self._ffprobe)
        return ComposeResult(
            output_path=output_path,
            duration_sec=duration,
            width=width,
            height=height,
        )

    def _concat_clips(self, clips: list[Path], output: Path) -> None:
        list_file = output.parent / "concat_list.txt"
        lines = [f"file '{clip.as_posix()}'" for clip in clips]
        list_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
        _run(
            [
                self._ffmpeg,
                "-y",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(list_file),
                "-c",
                "copy",
                str(output),
            ]
        )

    def _xfade_clips(self, clips: list[Path], output: Path, *, crossfade_sec: float, fps: int) -> None:
        if len(clips) == 1:
            shutil.copy(clips[0], output)
            return
        inputs: list[str] = []
        for clip in clips:
            inputs.extend(["-i", str(clip)])
        durations = [probe_duration(c, self._ffprobe) for c in clips]
        filter_parts: list[str] = []
        offset = max(0.0, durations[0] - crossfade_sec)
        filter_parts.append(f"[0:v][1:v]xfade=transition=fade:duration={crossfade_sec}:offset={offset}[v01]")
        prev = "v01"
        accumulated = durations[0] + durations[1] - crossfade_sec
        for idx in range(2, len(clips)):
            offset = max(0.0, accumulated - crossfade_sec)
            out_label = f"v{idx:02d}"
            filter_parts.append(
                f"[{prev}][{idx}:v]xfade=transition=fade:duration={crossfade_sec}:offset={offset}[{out_label}]"
            )
            prev = out_label
            accumulated += durations[idx] - crossfade_sec
        filter_complex = ";".join(filter_parts)
        cmd = [self._ffmpeg, "-y", *inputs, "-filter_complex", filter_complex, "-map", f"[{prev}]", str(output)]
        _run(cmd)


def parse_timeline(timeline: dict[str, object]) -> tuple[list[dict[str, object]], str, float, Optional[str], Optional[str]]:
    preset = str(timeline.get("preset", "youtube_16x9"))
    crossfade = float(timeline.get("crossfade_sec", 0.3))
    audio_asset_id = timeline.get("audio_asset_id")
    subtitle_asset_id = timeline.get("subtitle_asset_id")
    clips_raw = timeline.get("clips", [])
    if not isinstance(clips_raw, list):
        raise MediaComposeError("timeline.clips must be a list")
    slides: list[dict[str, object]] = []
    for item in clips_raw:
        if not isinstance(item, dict):
            continue
        if "path" not in item and "asset_id" not in item:
            raise MediaComposeError("Each clip requires path or asset_id")
        slides.append(item)
    return (
        slides,
        preset,
        crossfade,
        str(audio_asset_id) if audio_asset_id else None,
        str(subtitle_asset_id) if subtitle_asset_id else None,
    )


def load_timeline_file(path: Path) -> dict[str, object]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise MediaComposeError("Timeline file must be a JSON object")
    return data
