#!/usr/bin/env python3
"""Render an NBA SIM share card from picks/nba.json."""
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from render_dispatch import aggregate


ROOT = Path(__file__).resolve().parents[1]
PICKS_JSON = ROOT / "picks" / "nba.json"
BASELINES_JSON = ROOT / "picks" / "baselines.json"
POSTERS = ROOT / "posters"
LOGO = ROOT / "logo-grok-transparent.png"

W, H = 1080, 1350

BG = (189, 189, 180)
PAPER = (226, 225, 216)
PANEL = (210, 210, 201)
INK = (22, 23, 21)
SOFT = (91, 93, 88)
LINE = (158, 158, 149)
GREEN = (29, 110, 74)
RUST = (137, 84, 51)
CREAM = (238, 237, 229)

FONT_CANDIDATES = {
    "display": [
        "/System/Library/Fonts/Supplemental/DIN Condensed Bold.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ],
    "body": [
        "/System/Library/Fonts/Avenir Next Condensed.ttc",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ],
    "mono": [
        "/System/Library/Fonts/Menlo.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
    ],
}


@dataclass(frozen=True)
class PickRow:
    pick_text: str
    matchup: str
    conf: int
    projection: str
    status: str
    result: str
    pl: float | None


def load_font(kind: str, size: int) -> ImageFont.ImageFont:
    for candidate in FONT_CANDIDATES[kind]:
        path = Path(candidate)
        if path.exists():
            return ImageFont.truetype(str(path), size=size)
    return ImageFont.load_default()


def text_w(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont) -> int:
    box = draw.textbbox((0, 0), text, font=font)
    return box[2] - box[0]


def truncate(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, max_w: int) -> str:
    if text_w(draw, text, font) <= max_w:
        return text
    text = text.strip()
    while text and text_w(draw, text + "...", font) > max_w:
        text = text[:-1].rstrip()
    return text + "..."


def center_text(draw: ImageDraw.ImageDraw, center: tuple[int, int], text: str, font, fill):
    box = draw.textbbox((0, 0), text, font=font)
    x = center[0] - (box[2] - box[0]) / 2 - box[0]
    y = center[1] - (box[3] - box[1]) / 2 - box[1]
    draw.text((x, y), text, font=font, fill=fill)


def right_text(draw: ImageDraw.ImageDraw, right_x: int, y: int, text: str, font, fill):
    box = draw.textbbox((0, 0), text, font=font)
    draw.text((right_x - (box[2] - box[0]), y), text, font=font, fill=fill)


def rounded(draw: ImageDraw.ImageDraw, xy, radius: int, fill, outline=None, width: int = 1):
    draw.rounded_rectangle(xy, radius=radius, fill=fill, outline=outline, width=width)


def draw_logo(img: Image.Image, x: int, y: int, size: int):
    if not LOGO.exists():
        return
    logo = Image.open(LOGO).convert("RGBA")
    logo.thumbnail((size, size), Image.Resampling.LANCZOS)
    img.alpha_composite(logo, (x, y))


def stat_box(draw: ImageDraw.ImageDraw, x: int, y: int, value: str, label: str):
    rounded(draw, (x, y, x + 280, y + 96), 10, PANEL, (174, 174, 164), 1)
    center_text(draw, (x + 140, y + 39), value, load_font("display", 48), INK)
    center_text(draw, (x + 140, y + 72), label.upper(), load_font("mono", 13), SOFT)


def pill(draw: ImageDraw.ImageDraw, xy, text: str, fill, text_fill=CREAM):
    rounded(draw, xy, 11, fill)
    center_text(draw, ((xy[0] + xy[2]) // 2, (xy[1] + xy[3]) // 2), text, load_font("mono", 17), text_fill)


def load_data() -> tuple[list[dict], dict]:
    picks = json.loads(PICKS_JSON.read_text(encoding="utf-8"))
    baselines = json.loads(BASELINES_JSON.read_text(encoding="utf-8"))
    return picks, baselines.get("nba", {})


def pick_rows(picks: list[dict]) -> tuple[list[PickRow], list[PickRow]]:
    pending = []
    settled = []
    for pick in picks:
        row = PickRow(
            pick_text=str(pick.get("pick_text") or ""),
            matchup=str(pick.get("matchup") or ""),
            conf=int(pick.get("conf") or 0),
            projection=str(pick.get("sim_projection") or ""),
            status=str(pick.get("status") or ""),
            result=str(pick.get("result") or ""),
            pl=pick.get("pl"),
        )
        if row.status == "pending":
            pending.append(row)
        elif row.status in ("win", "loss", "push"):
            settled.append(row)
    pending.sort(key=lambda row: (-row.conf, row.matchup))
    return pending[:4], settled[:4]


def draw_pick_row(draw: ImageDraw.ImageDraw, row: PickRow, idx: int, y: int, mode: str):
    accent = GREEN if mode == "official" else RUST
    draw.line((86, y - 10, 994, y - 10), fill=LINE, width=1)
    center_text(draw, (112, y + 38), str(idx), load_font("mono", 18), SOFT)
    draw.text((152, y), truncate(draw, row.pick_text, load_font("display", 43), 300), font=load_font("display", 43), fill=INK)
    draw.text((154, y + 42), row.matchup, font=load_font("body", 23), fill=SOFT)
    if row.projection:
        draw.text((154, y + 68), truncate(draw, row.projection, load_font("mono", 15), 440), font=load_font("mono", 15), fill=SOFT)
    pill(draw, (506, y + 8, 574, y + 44), f"C{row.conf}", accent)
    if mode == "official":
        right_text(draw, 970, y + 5, "PENDING", load_font("display", 38), INK)
        draw.text((858, y + 48), "OFFICIAL", font=load_font("mono", 13), fill=SOFT)
    else:
        result = "PUSH" if row.status == "push" else row.status.upper()
        pnl = "" if row.pl is None else f"{row.pl:+.0f}"
        right_text(draw, 970, y + 5, result, load_font("display", 38), accent if row.status == "win" else RUST)
        draw.text((858, y + 48), pnl, font=load_font("mono", 15), fill=SOFT)


def draw_footer(draw: ImageDraw.ImageDraw):
    draw.line((86, 1236, 994, 1236), fill=LINE, width=1)
    draw.text((86, 1268), "morellosims.com/nbasim", font=load_font("display", 31), fill=INK, anchor="lm")
    right_text(draw, 994, 1254, "lines move, check board", load_font("mono", 15), SOFT)


def render(out: Path) -> Path:
    picks, baseline = load_data()
    agg = aggregate(picks, baseline=baseline)
    pending, recent = pick_rows(picks)
    date_label = datetime.now().strftime("%b %d, %Y").upper()

    img = Image.new("RGBA", (W, H), BG)
    draw = ImageDraw.Draw(img, "RGBA")
    rounded(draw, (54, 54, 1026, 1296), 14, PAPER, (138, 138, 130), 2)
    draw_logo(img, 86, 86, 58)
    draw.text((160, 87), "MORELLO SIMS", font=load_font("display", 47), fill=INK)
    draw.text((162, 128), "NBA SIM", font=load_font("mono", 15), fill=SOFT)
    right_text(draw, 982, 100, date_label, load_font("mono", 18), SOFT)
    draw.line((86, 174, 994, 174), fill=LINE, width=2)

    draw.text((86, 218), "NBA END CARD", font=load_font("display", 78), fill=INK)
    draw.text((88, 296), "Season tracker plus the current official board.", font=load_font("body", 28), fill=SOFT)
    stat_box(draw, 86, 354, f'{agg["wins"]}-{agg["losses"]}', "record")
    stat_box(draw, 400, 354, f'{agg["roi"]:+.0f}%', "roi")
    stat_box(draw, 714, 354, agg["streak"], "streak")

    y = 510
    draw.text((86, y), "OFFICIAL BOARD", font=load_font("mono", 18), fill=INK)
    y += 52
    if pending:
        for idx, row in enumerate(pending[:3], 1):
            draw_pick_row(draw, row, idx, y, "official")
            y += 126
    else:
        draw.text((86, y), "No pending NBA plays.", font=load_font("display", 44), fill=SOFT)
        y += 96

    y += 12
    draw.text((86, y), "RECENT RESULTS", font=load_font("mono", 18), fill=INK)
    y += 52
    for idx, row in enumerate(recent[:2], 1):
        draw_pick_row(draw, row, idx, y, "recent")
        y += 126

    draw_footer(draw)
    out.parent.mkdir(parents=True, exist_ok=True)
    img.convert("RGB").filter(ImageFilter.UnsharpMask(radius=0.7, percent=105, threshold=3)).save(out, quality=95)
    return out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=str(POSTERS / "nba-social-card.png"))
    args = parser.parse_args()
    print(render(Path(args.out)))


if __name__ == "__main__":
    main()
