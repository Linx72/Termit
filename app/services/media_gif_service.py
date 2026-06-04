"""GIF export from PNG sequences via ffmpeg."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

from app.services.media_compose_service import MediaComposeError, ffmpeg_available


class MediaGifService:
    def __init__(self, *, ffmpeg_path: str = "ffmpeg") -> None:
        self._ffmpeg = ffmpeg_path

    def export_gif(
        self,
        *,
        image_paths: list[Path],
        output_path: Path,
        fps: int = 8,
        width: int = 480,
    ) -> None:
        if not image_paths:
            raise MediaComposeError("export_gif requires at least one image")
        if not ffmpeg_available(self._ffmpeg):
            raise MediaComposeError("ffmpeg required for GIF export")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        vf = f"fps={fps},scale={width}:-1:flags=lanczos,split[s0][s1];[s0]palettegen[p];[s1][p]paletteuse"
        if len(image_paths) == 1:
            cmd = [
                self._ffmpeg,
                "-y",
                "-loop",
                "1",
                "-i",
                str(image_paths[0]),
                "-vf",
                vf,
                str(output_path),
            ]
            proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
            if proc.returncode != 0:
                raise MediaComposeError((proc.stderr or proc.stdout)[:600])
            return
        with tempfile.TemporaryDirectory(prefix="termit-gif-") as tmp:
            tmp_dir = Path(tmp)
            for index, src in enumerate(image_paths):
                shutil.copy(src, tmp_dir / f"frame_{index:03d}.png")
            cmd = [
                self._ffmpeg,
                "-y",
                "-framerate",
                str(max(1, fps)),
                "-i",
                str(tmp_dir / "frame_%03d.png"),
                "-vf",
                vf,
                str(output_path),
            ]
            proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
            if proc.returncode != 0:
                raise MediaComposeError((proc.stderr or proc.stdout)[:600])
