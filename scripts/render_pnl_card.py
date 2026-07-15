#!/usr/bin/env python3
"""Render a simple, reusable Morello SIM PNL card.

Importable interface (used by post_social_daily.py):

    from render_pnl_card import ResultRow, render
    render(out, date_label, rows=[ResultRow(...)], headline="DAILY RECAP",
           subline="MLB RESULTS", net_label="+63u", footer_center="4 PICKS / 3 WINS / +63u")

Running the script directly renders the legacy 2026-05-27 sweep demo card.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont


ROOT = Path(__file__).resolve().parents[1]
POSTERS = ROOT / "posters"
LOGO = ROOT / "logo-grok-transparent.png"

W, H = 1080, 1350

BLACK = (8, 10, 8)
CARD = (15, 17, 14)
ROW = (20, 23, 19)
ROW_ALT = (17, 20, 16)
WHITE = (246, 247, 238)
MUTED = (174, 179, 170)
GREEN = (32, 220, 55)
YELLOW = (255, 207, 43)
ORANGE = (255, 105, 31)
BLUE = (0, 67, 160)
RED = (238, 28, 46)
GRAY = (120, 126, 118)

# Font fallbacks so the card renders on macOS and on GitHub Actions (ubuntu).
FONT_CANDIDATES = {
    "impact": [
        "/System/Library/Fonts/Supplemental/Impact.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ],
    "din": [
        "/System/Library/Fonts/Supplemental/DIN Condensed Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ],
    "avenir": [
        "/System/Library/Fonts/Avenir Next Condensed.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ],
    "mono": [
        "/System/Library/Fonts/Menlo.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
    ],
}

ACCENTS = [RED, ORANGE, BLUE, YELLOW, GREEN]


@dataclass(frozen=True)
class ResultRow:
    team: str
    pick: str
    opponent: str
    line: str
    final: str
    pnl_label: str
    won: bool | None = True  # True=win, False=loss, None=push
    color: tuple[int, int, int] = RED


DEMO_ROWS = [
    ResultRow("PHILLIES", "PHI ML", "at San Diego", "-146", "3-0", "+13.7%", True, RED),
    ResultRow("METS", "NYM ML", "vs Cincinnati", "-118", "4-2", "+17.0%", True, ORANGE),
    ResultRow("YANKEES", "NYY ML", "at Kansas City", "-160", "7-0", "+12.5%", True, BLUE),
    ResultRow("GUARDIANS", "CLE ML", "vs Washington", "-180", "3-2", "+11.1%", True, RED),
    ResultRow("BREWERS", "MIL ML", "vs St. Louis", "-180", "2-1", "+11.1%", True, YELLOW),
]


def font(kind: str, size: int) -> ImageFont.ImageFont:
    for candidate in FONT_CANDIDATES[kind]:
        if Path(candidate).exists():
            return ImageFont.truetype(candidate, size=size)
    return ImageFont.load_default()


def rounded(draw: ImageDraw.ImageDraw, xy, radius, fill, outline=None, width=1):
    draw.rounded_rectangle(xy, radius=radius, fill=fill, outline=outline, width=width)


def centered_text(
    draw: ImageDraw.ImageDraw,
    center: tuple[int, int],
    text: str,
    fnt: ImageFont.ImageFont,
    fill,
    stroke_width: int = 0,
    stroke_fill=None,
):
    """Center by actual glyph bounds, not font line box."""
    box = draw.textbbox((0, 0), text, font=fnt, stroke_width=stroke_width)
    x = center[0] - (box[2] - box[0]) / 2 - box[0]
    y = center[1] - (box[3] - box[1]) / 2 - box[1]
    draw.text((x, y), text, font=fnt, fill=fill, stroke_width=stroke_width, stroke_fill=stroke_fill)


def right_text(draw: ImageDraw.ImageDraw, right_x: int, center_y: int, text: str, fnt, fill):
    box = draw.textbbox((0, 0), text, font=fnt)
    y = center_y - (box[3] - box[1]) / 2 - box[1]
    draw.text((right_x - (box[2] - box[0]), y), text, font=fnt, fill=fill)


def fitted_font(draw: ImageDraw.ImageDraw, text: str, kind: str, size: int, max_w: int, min_size: int) -> ImageFont.ImageFont:
    for font_size in range(size, min_size - 1, -1):
        fnt = font(kind, font_size)
        box = draw.textbbox((0, 0), text, font=fnt)
        if box[2] - box[0] <= max_w:
            return fnt
    return font(kind, min_size)


def draw_logo(img: Image.Image, x: int, y: int, size: int):
    if not LOGO.exists():
        return
    logo = Image.open(LOGO).convert("RGBA")
    logo.thumbnail((size, size), Image.Resampling.LANCZOS)
    img.alpha_composite(logo, (x, y))


def draw_background(img: Image.Image):
    d = ImageDraw.Draw(img, "RGBA")
    d.rectangle((0, 0, W, H), fill=BLACK)

    # Quiet SIM-color signal lines. Decorative only, never fighting the table.
    for x in range(0, W, 120):
        d.line((x, 0, x, H), fill=(255, 255, 255, 8), width=1)
    for y in range(0, H, 120):
        d.line((0, y, W, y), fill=(255, 255, 255, 8), width=1)
    d.line((-40, 980, 1120, 520), fill=(*GREEN, 48), width=6)
    d.line((-40, 1150, 1120, 760), fill=(*ORANGE, 44), width=5)
    d.line((180, -20, 1100, 300), fill=(*YELLOW, 42), width=5)


def draw_header(draw: ImageDraw.ImageDraw, img: Image.Image, date_label: str, kicker: str):
    draw_logo(img, 86, 72, 72)
    draw.text((178, 76), "MORELLO SIMS", font=font("din", 58), fill=WHITE)
    draw.text((180, 126), kicker, font=font("din", 31), fill=MUTED)

    rounded(draw, (756, 82, 994, 138), 27, YELLOW, (0, 0, 0), 3)
    date_font = fitted_font(draw, date_label, "din", 34, 216, 20)
    centered_text(draw, (875, 111), date_label, date_font, (5, 6, 5))
    draw.line((82, 182, 998, 182), fill=(255, 255, 255, 74), width=2)


def draw_hero(
    draw: ImageDraw.ImageDraw,
    rows: list[ResultRow],
    record: str,
    headline: str,
    subline: str,
    net_label: str,
):
    net_positive = not net_label.startswith("-")

    draw.text((92, 246), headline, font=font("mono", 18), fill=GREEN if net_positive else RED)
    record_font = fitted_font(draw, record, "impact", 196, 560, 90)
    draw.text((88, 292), record, font=record_font, fill=WHITE, stroke_width=5, stroke_fill=(0, 0, 0))
    sub_font = fitted_font(draw, subline, "din", 78, 560, 40)
    draw.text((92, 485), subline, font=sub_font, fill=YELLOW, stroke_width=3, stroke_fill=(0, 0, 0))

    # The metric block is the main PNL read.
    rounded(draw, (674, 268, 996, 508), 22, (18, 21, 18), (255, 255, 255, 92), 2)
    draw.text((704, 296), "NET PNL", font=font("mono", 22), fill=MUTED)
    net_font = fitted_font(draw, net_label, "impact", 102, 280, 44)
    centered_text(draw, (834, 391), net_label, net_font, GREEN if net_positive else RED,
                  stroke_width=3, stroke_fill=(0, 0, 0))
    draw.text((704, 466), "PROFIT / TOTAL RISK", font=font("mono", 15), fill=MUTED)

    teams = "  /  ".join(r.team for r in rows[:5])
    teams_font = fitted_font(draw, teams, "din", 30, 900, 18)
    draw.text((94, 570), teams, font=teams_font, fill=WHITE)


def draw_result_badge(draw: ImageDraw.ImageDraw, cx: int, cy: int, won: bool | None):
    r = 22
    if won is True:
        fill, mark = GREEN, "W"
    elif won is False:
        fill, mark = RED, "L"
    else:
        fill, mark = GRAY, "P"
    draw.ellipse((cx - r, cy - r, cx + r, cy + r), fill=fill, outline=WHITE, width=2)
    centered_text(draw, (cx, cy), mark, font("din", 27), (0, 0, 0) if won else WHITE)


def draw_rows(draw: ImageDraw.ImageDraw, rows: list[ResultRow]):
    table = (82, 632, 998, 1118)
    rounded(draw, table, 22, (13, 15, 13), (255, 255, 255, 100), 2)

    header_y = 681
    draw.text((190, header_y), "PICK", font=font("mono", 16), fill=MUTED)
    centered_text(draw, (566, header_y + 10), "LINE", font("mono", 16), MUTED)
    centered_text(draw, (724, header_y + 10), "FINAL", font("mono", 16), MUTED)
    right_text(draw, 944, header_y + 10, "PNL", font("mono", 16), MUTED)
    draw.line((104, 710, 976, 710), fill=(255, 255, 255, 78), width=1)

    rows = rows[:6]
    row_top = 724
    row_h = min(76, max(58, (1118 - row_top - 12) // max(len(rows), 1)))
    box_h = row_h - 12
    for i, row in enumerate(rows):
        y0 = row_top + i * row_h
        y1 = y0 + box_h
        mid_y = (y0 + y1) // 2
        fill = ROW if i % 2 == 0 else ROW_ALT
        rounded(draw, (104, y0, 976, y1), 12, fill, (255, 255, 255, 66), 1)
        draw.rounded_rectangle((104, y0, 114, y1), radius=5, fill=row.color)

        draw_result_badge(draw, 150, mid_y, row.won)
        team_font = fitted_font(draw, row.team, "din", 39, 250, 24)
        draw.text((190, y0 + 8), row.team, font=team_font, fill=WHITE)
        detail = f"{row.pick}  /  {row.opponent}"
        detail_font = fitted_font(draw, detail, "avenir", 22, 260, 14)
        draw.text((192, y1 - 24), detail, font=detail_font, fill=(204, 209, 199))

        centered_text(draw, (566, mid_y), row.line, font("mono", 26), WHITE)
        rounded(draw, (658, mid_y - 21, 790, mid_y + 21), 12, WHITE)
        final_font = fitted_font(draw, row.final, "din", 39, 122, 22)
        centered_text(draw, (724, mid_y), row.final, final_font, (0, 0, 0))
        pnl_fill = GREEN if row.won is True else (RED if row.won is False else MUTED)
        right_text(draw, 944, mid_y, row.pnl_label, font("din", 37), pnl_fill)


def draw_footer(draw: ImageDraw.ImageDraw, footer_center: str, site_label: str, positive: bool):
    rounded(draw, (82, 1160, 998, 1238), 17, (13, 16, 13), GREEN if positive else RED, 2)
    mid_y = 1200
    draw.text((122, mid_y), "MORELLO MLB SIM", font=font("din", 36), fill=WHITE, anchor="lm")
    centered_text(draw, (520, mid_y), footer_center, font("din", 31), GREEN if positive else RED)
    draw.text((962, mid_y), site_label, font=font("din", 28), fill=WHITE, anchor="rm")


def render(
    out: Path,
    date_label: str = "MAY 27, 2026",
    rows: list[ResultRow] | None = None,
    record: str | None = None,
    headline: str | None = None,
    subline: str | None = None,
    net_label: str | None = None,
    footer_center: str | None = None,
    kicker: str = "MLB SIM RESULTS",
    site_label: str = "morellosims.com/mlbsim",
) -> Path:
    if rows is None:
        rows = DEMO_ROWS
        record = record or "5-0"
        headline = headline or "PERFECT CARD"
        subline = subline or "MLB SWEEP"
        net_label = net_label or "+65.4%"
        footer_center = footer_center or "5 PICKS / 5 WINS / +65.4%"

    wins = sum(1 for r in rows if r.won is True)
    losses = sum(1 for r in rows if r.won is False)
    record = record or f"{wins}-{losses}"
    headline = headline or ("PERFECT CARD" if losses == 0 and wins else "DAILY RECAP")
    subline = subline or "MLB RESULTS"
    net_label = net_label or ""
    footer_center = footer_center or f"{len(rows)} PICKS / {wins} WINS"

    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    img = Image.new("RGBA", (W, H), (0, 0, 0, 255))
    draw_background(img)
    draw = ImageDraw.Draw(img, "RGBA")

    rounded(draw, (38, 36, 1042, 1314), 50, CARD, (255, 255, 255, 220), 2)
    rounded(draw, (58, 56, 1022, 1294), 40, (14, 16, 14, 230), (255, 255, 255, 62), 1)

    draw_header(draw, img, date_label, kicker)
    draw_hero(draw, rows, record, headline, subline, net_label)
    draw_rows(draw, rows)
    draw_footer(draw, footer_center, site_label, positive=not net_label.startswith("-"))

    img = img.convert("RGB").filter(ImageFilter.UnsharpMask(radius=1.0, percent=110, threshold=3))
    img.save(out, quality=96)
    return out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=str(POSTERS / "mlb-sim-pnl-2026-05-27.png"))
    parser.add_argument("--date", default="MAY 27, 2026")
    args = parser.parse_args()
    print(render(Path(args.out), args.date))


if __name__ == "__main__":
    main()
