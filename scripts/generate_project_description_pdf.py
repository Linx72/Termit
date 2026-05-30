#!/usr/bin/env python3
"""Generate PROJECT_DESCRIPTION_RU.pdf from PROJECT_DESCRIPTION_RU.md."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    Preformatted,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "PROJECT_DESCRIPTION_RU.md"
DEFAULT_OUTPUT = ROOT / "PROJECT_DESCRIPTION_RU.pdf"

FONT_CANDIDATES = [
    Path("/System/Library/Fonts/Supplemental/Arial Unicode.ttf"),
    Path("/Library/Fonts/Arial Unicode.ttf"),
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
]


def _resolve_font() -> str:
    for candidate in FONT_CANDIDATES:
        if candidate.is_file():
            pdfmetrics.registerFont(TTFont("BodyFont", str(candidate)))
            return "BodyFont"
    raise FileNotFoundError(
        "Unicode TTF font not found. Install Arial Unicode or DejaVu Sans."
    )


def _escape_xml(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def _inline_md_to_xml(text: str) -> str:
    text = _escape_xml(text)
    text = re.sub(r"`([^`]+)`", r"\1", text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"\*([^*]+)\*", r"<i>\1</i>", text)
    return text


def _styles(font_name: str) -> dict[str, ParagraphStyle]:
    return {
        "h1": ParagraphStyle(
            "H1",
            fontName=font_name,
            fontSize=18,
            leading=22,
            spaceAfter=10,
            spaceBefore=6,
        ),
        "h2": ParagraphStyle(
            "H2",
            fontName=font_name,
            fontSize=14,
            leading=18,
            spaceAfter=8,
            spaceBefore=14,
        ),
        "h3": ParagraphStyle(
            "H3",
            fontName=font_name,
            fontSize=12,
            leading=16,
            spaceAfter=6,
            spaceBefore=10,
        ),
        "body": ParagraphStyle(
            "Body",
            fontName=font_name,
            fontSize=10,
            leading=14,
            spaceAfter=6,
        ),
        "bullet": ParagraphStyle(
            "Bullet",
            fontName=font_name,
            fontSize=10,
            leading=14,
            leftIndent=14,
            bulletIndent=6,
            spaceAfter=4,
        ),
        "code": ParagraphStyle(
            "Code",
            fontName=font_name,
            fontSize=8,
            leading=11,
            backColor=colors.HexColor("#f4f4f4"),
            borderPadding=6,
            spaceAfter=8,
        ),
        "footer": ParagraphStyle(
            "Footer",
            fontName=font_name,
            fontSize=8,
            textColor=colors.grey,
            alignment=TA_CENTER,
        ),
    }


def _is_table_row(line: str) -> bool:
    stripped = line.strip()
    return stripped.startswith("|") and stripped.endswith("|") and "|" in stripped[1:-1]


def _parse_table_row(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def _is_separator_row(cells: list[str]) -> bool:
    return bool(cells) and all(
        re.fullmatch(r":?-{3,}:?", cell.replace(" ", "")) for cell in cells if cell
    )


def _table_flowable(rows: list[list[str]], styles: dict[str, ParagraphStyle]) -> Table:
    body_style = styles["body"]
    data = [
        [Paragraph(_inline_md_to_xml(cell), body_style) for cell in row]
        for row in rows
    ]
    col_count = max(len(row) for row in rows)
    page_width, _ = A4
    usable = page_width - 4.4 * cm
    col_width = usable / col_count
    table = Table(data, colWidths=[col_width] * col_count, repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, -1), body_style.fontName),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#efefef")),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#bbbbbb")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return table


def md_to_flowables(text: str, styles: dict[str, ParagraphStyle]) -> list:
    flowables: list = []
    lines = text.splitlines()

    in_code = False
    code_buffer: list[str] = []
    table_buffer: list[list[str]] = []

    def flush_table() -> None:
        nonlocal table_buffer
        if table_buffer:
            flowables.append(_table_flowable(table_buffer, styles))
            flowables.append(Spacer(1, 8))
            table_buffer = []

    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if stripped.startswith("```"):
            if in_code:
                block = "\n".join(code_buffer)
                flowables.append(Preformatted(block, styles["code"]))
                flowables.append(Spacer(1, 6))
                code_buffer = []
                in_code = False
            else:
                flush_table()
                in_code = True
            i += 1
            continue

        if in_code:
            code_buffer.append(line)
            i += 1
            continue

        if not stripped:
            flush_table()
            i += 1
            continue

        if stripped == "---":
            flush_table()
            flowables.append(Spacer(1, 6))
            i += 1
            continue

        if _is_table_row(line):
            cells = _parse_table_row(line)
            if _is_separator_row(cells):
                i += 1
                continue
            table_buffer.append(cells)
            i += 1
            continue

        flush_table()

        if stripped.startswith("# "):
            flowables.append(Paragraph(_inline_md_to_xml(stripped[2:]), styles["h1"]))
            i += 1
            continue

        if stripped.startswith("## "):
            flowables.append(Paragraph(_inline_md_to_xml(stripped[3:]), styles["h2"]))
            i += 1
            continue

        if stripped.startswith("### "):
            flowables.append(Paragraph(_inline_md_to_xml(stripped[4:]), styles["h3"]))
            i += 1
            continue

        bullet_match = re.match(r"^[-*]\s+(.+)$", stripped)
        if bullet_match:
            flowables.append(
                Paragraph(
                    f"• {_inline_md_to_xml(bullet_match.group(1))}",
                    styles["bullet"],
                )
            )
            i += 1
            continue

        numbered_match = re.match(r"^(\d+)\.\s+(.+)$", stripped)
        if numbered_match:
            flowables.append(
                Paragraph(
                    f"{numbered_match.group(1)}. {_inline_md_to_xml(numbered_match.group(2))}",
                    styles["bullet"],
                )
            )
            i += 1
            continue

        flowables.append(Paragraph(_inline_md_to_xml(stripped), styles["body"]))
        i += 1

    flush_table()
    return flowables


def build_pdf(input_path: Path, output_path: Path) -> None:
    font_name = _resolve_font()
    styles = _styles(font_name)
    md_text = input_path.read_text(encoding="utf-8")
    flowables = md_to_flowables(md_text, styles)

    output_path.parent.mkdir(parents=True, exist_ok=True)

    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        leftMargin=2.2 * cm,
        rightMargin=2.2 * cm,
        topMargin=2 * cm,
        bottomMargin=2.2 * cm,
        title="Описание проекта Termit",
        author="Termit",
    )

    def _footer(canvas, doc_obj) -> None:  # noqa: ANN001
        canvas.saveState()
        canvas.setFont(font_name, 8)
        canvas.setFillColor(colors.grey)
        canvas.drawCentredString(
            A4[0] / 2,
            1.2 * cm,
            f"Termit — {canvas.getPageNumber()}",
        )
        canvas.restoreState()

    doc.build(flowables, onFirstPage=_footer, onLaterPages=_footer)


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate PROJECT_DESCRIPTION_RU.pdf")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    if not args.input.is_file():
        print(f"Input not found: {args.input}", file=sys.stderr)
        return 1

    try:
        build_pdf(args.input, args.output)
    except Exception as exc:  # noqa: BLE001
        print(f"PDF generation failed: {exc}", file=sys.stderr)
        return 1

    print(f"Wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
