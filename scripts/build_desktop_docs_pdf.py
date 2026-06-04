#!/usr/bin/env python3
"""Build Russian PDF help and training docs for Termit desktop (offline bundle)."""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS_RU = ROOT / "clients" / "termit-desktop" / "docs" / "ru"
PDF_OUT = ROOT / "clients" / "termit-desktop" / "docs" / "pdf"

SOURCES = {
    "TERMIT_HELP_RU.pdf": DOCS_RU / "TERMIT_HELP_RU.md",
    "TERMIT_TRAINING_RU.pdf": DOCS_RU / "TERMIT_TRAINING_RU.md",
}


def _ensure_fpdf():
    try:
        from fpdf import FPDF  # type: ignore

        return FPDF
    except ImportError:
        import subprocess

        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "-q", "fpdf2"],
        )
        from fpdf import FPDF  # type: ignore

        return FPDF


def _find_fonts() -> tuple[Path, Path]:
    here = Path(__file__).resolve().parent / "pdf_fonts"
    candidates_regular = [
        here / "DejaVuSans.ttf",
        Path("/System/Library/Fonts/Supplemental/Arial Unicode.ttf"),
        Path("/Library/Fonts/Arial Unicode.ttf"),
    ]
    candidates_bold = [
        here / "DejaVuSans-Bold.ttf",
        Path("/System/Library/Fonts/Supplemental/Arial Bold.ttf"),
        candidates_regular[1],
        candidates_regular[2],
    ]
    regular = next((p for p in candidates_regular if p.exists()), None)
    bold = next((p for p in candidates_bold if p and p.exists()), None)
    if regular is None:
        raise FileNotFoundError(
            "Unicode TTF not found. Install DejaVu into scripts/pdf_fonts/ or use macOS Arial Unicode."
        )
    if bold is None:
        bold = regular
    return regular, bold


def _sanitize(text: str) -> str:
    return (
        text.replace("\t", "    ")
        .replace("—", "-")
        .replace("→", "->")
        .replace("«", '"')
        .replace("»", '"')
    )


class TermitPdfBuilder:
    def __init__(self) -> None:
        FPDF = _ensure_fpdf()
        self.pdf = FPDF()
        self.pdf.set_auto_page_break(auto=True, margin=15)
        regular, bold = _find_fonts()
        self.pdf.add_font("TermitDoc", "", str(regular))
        self.pdf.add_font("TermitDoc", "B", str(bold))
        self.font_family = "TermitDoc"

    def _set_font(self, size: float, style: str = "") -> None:
        self.pdf.set_font(self.font_family, style, size)

    def render_markdown(self, md_text: str) -> None:
        from fpdf.enums import XPos, YPos

        self.pdf.add_page()
        in_code = False
        width = self.pdf.epw
        for raw_line in md_text.splitlines():
            line = raw_line.rstrip()
            if line.strip().startswith("```"):
                in_code = not in_code
                continue
            if line.strip() == "---":
                self.pdf.ln(4)
                continue

            def write_block(text: str, size: float, style: str = "", line_h: float = 6) -> None:
                self._set_font(size, style)
                chunk = _sanitize(text)
                if not chunk.strip():
                    self.pdf.ln(line_h / 2)
                    return
                self.pdf.multi_cell(
                    w=width,
                    h=line_h,
                    text=chunk,
                    new_x=XPos.LMARGIN,
                    new_y=YPos.NEXT,
                )

            if in_code:
                write_block(line or " ", 9, line_h=5)
                continue
            if line.startswith("# "):
                write_block(line[2:].strip(), 16, "B", 9)
                self.pdf.ln(2)
                continue
            if line.startswith("## "):
                write_block(line[3:].strip(), 13, "B", 8)
                self.pdf.ln(1)
                continue
            if line.startswith("### "):
                write_block(line[4:].strip(), 11, "B", 7)
                continue
            if line.startswith("|") and "|" in line[1:]:
                cells = [c.strip() for c in line.strip("|").split("|")]
                write_block(" | ".join(cells), 9, line_h=5)
                continue
            if line.startswith("- "):
                write_block(f"• {line[2:].strip()}", 10)
                continue
            if re.match(r"^\d+\.\s", line):
                write_block(line, 10)
                continue
            if not line.strip():
                self.pdf.ln(3)
                continue
            write_block(line, 10)

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.pdf.output(str(path))


def download_fonts() -> None:
    """Optional: user can add DejaVu fonts to scripts/pdf_fonts for Cyrillic."""
    font_dir = Path(__file__).resolve().parent / "pdf_fonts"
    font_dir.mkdir(parents=True, exist_ok=True)


def build_all() -> int:
    download_fonts()
    PDF_OUT.mkdir(parents=True, exist_ok=True)
    for pdf_name, md_path in SOURCES.items():
        if not md_path.exists():
            print(f"error: missing source {md_path}", file=sys.stderr)
            return 1
        text = md_path.read_text(encoding="utf-8")
        builder = TermitPdfBuilder()
        builder.render_markdown(text)
        out = PDF_OUT / pdf_name
        builder.save(out)
        print(f"Wrote {out} ({out.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(build_all())
