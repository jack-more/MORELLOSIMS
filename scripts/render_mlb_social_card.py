#!/usr/bin/env python3
"""Render a social-ready MLB SIM card from the generated MLB page."""
from __future__ import annotations

import argparse
import html
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "mlbsim" / "index.html"
POSTERS = ROOT / "posters"
LOGO = ROOT / "logo-grok-transparent.png"

W, H = 1080, 1350

BLACK = (7, 9, 8)
CARD = (15, 17, 15)
PANEL = (22, 25, 21)
PANEL_ALT = (246, 247, 238)
WHITE = (246, 247, 238)
MUTED = (166, 173, 164)
GREEN = (32, 220, 55)
YELLOW = (255, 234, 0)
ORANGE = (255, 112, 38)
RED = (255, 51, 51)
BLUE = (0, 108, 255)

FONT_CANDIDATES = {
    "display": [
        "/System/Library/Fonts/Supplemental/DIN Condensed Bold.ttf",
        "/System/Library/Fonts/Supplemental/Impact.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ],
    "body": [
        "/System/Library/Fonts/Avenir Next Condensed.ttc",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ],
    "mono": [
        "/System/Library/Fonts/Menlo.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
    ],
}


@dataclass(frozen=True)
class GameRow:
    matchup: str
    pick_team: str
    pick_text: str
    odds: int
    conf: int
    run_edge: float
    model_prob: float
    break_even: float | None
    price_edge: float | None
    projection: str
    status: str
    reason: str


def load_font(kind: str, size: int) -> ImageFont.ImageFont:
    for candidate in FONT_CANDIDATES[kind]:
        path = Path(candidate)
        if path.exists():
            return ImageFont.truetype(str(path), size=size)
    return ImageFont.load_default()


def text_size(draw: ImageDraw.ImageDraw, text: str, fnt: ImageFont.ImageFont) -> tuple[int, int]:
    box = draw.textbbox((0, 0), text, font=fnt)
    return box[2] - box[0], box[3] - box[1]


def center_text(
    draw: ImageDraw.ImageDraw,
    center: tuple[int, int],
    text: str,
    fnt: ImageFont.ImageFont,
    fill,
    stroke_width: int = 0,
    stroke_fill=None,
):
    box = draw.textbbox((0, 0), text, font=fnt, stroke_width=stroke_width)
    x = center[0] - (box[2] - box[0]) / 2 - box[0]
    y = center[1] - (box[3] - box[1]) / 2 - box[1]
    draw.text((x, y), text, font=fnt, fill=fill, stroke_width=stroke_width, stroke_fill=stroke_fill)


def right_text(draw: ImageDraw.ImageDraw, right_x: int, center_y: int, text: str, fnt, fill):
    box = draw.textbbox((0, 0), text, font=fnt)
    y = center_y - (box[3] - box[1]) / 2 - box[1]
    draw.text((right_x - (box[2] - box[0]), y), text, font=fnt, fill=fill)


def truncate(draw: ImageDraw.ImageDraw, text: str, fnt: ImageFont.ImageFont, max_w: int) -> str:
    if text_size(draw, text, fnt)[0] <= max_w:
        return text
    ellipsis = "..."
    while text and text_size(draw, text + ellipsis, fnt)[0] > max_w:
        text = text[:-1]
    return text.rstrip() + ellipsis


def rounded(draw: ImageDraw.ImageDraw, xy, radius: int, fill, outline=None, width: int = 1):
    draw.rounded_rectangle(xy, radius=radius, fill=fill, outline=outline, width=width)


def strip_tags(value: str) -> str:
    value = re.sub(r"<br\s*/?>", " ", value, flags=re.I)
    value = re.sub(r"<.*?>", " ", value, flags=re.S)
    value = html.unescape(value)
    value = value.replace("\xa0", " ")
    return re.sub(r"\s+", " ", value).strip()


def parse_int_moneyline(value: str) -> int | None:
    try:
        return int(value.replace("+", "").strip())
    except (TypeError, ValueError):
        return None


def moneyline_break_even(odds: int | None) -> float | None:
    if odds is None or odds == 0:
        return None
    if odds < 0:
        return abs(odds) / (abs(odds) + 100)
    return 100 / (odds + 100)


def fmt_odds(odds: int) -> str:
    return f"+{odds}" if odds > 0 else str(odds)


def fmt_pct(value: float | None, digits: int = 1) -> str:
    if value is None:
        return "n/a"
    return f"{value * 100:+.{digits}f}%" if value < 0 else f"+{value * 100:.{digits}f}%"


def fmt_plain_pct(value: float | None, digits: int = 1) -> str:
    if value is None:
        return "n/a"
    return f"{value * 100:.{digits}f}%"


def generated_label(doc: str) -> str:
    m = re.search(r"Generated\s+(\d{4}-\d{2}-\d{2})\s+(\d{1,2}:\d{2})\s+ET", doc)
    if not m:
        return datetime.now().strftime("%b %d, %Y").upper()
    try:
        dt = datetime.strptime(m.group(1), "%Y-%m-%d")
        date_part = dt.strftime("%b %d, %Y").upper()
    except ValueError:
        date_part = m.group(1)
    return f"{date_part} - {m.group(2)} ET"


def split_game_cards(doc: str) -> list[tuple[re.Match[str], str]]:
    card_re = re.compile(
        r'<div class="game-card"\s+data-conf="(?P<conf>\d+)"\s+data-value="[^"]*"\s+data-edge="(?P<edge>[^"]*)">',
        re.S,
    )
    matches = list(card_re.finditer(doc))
    cards = []
    for idx, match in enumerate(matches):
        end = matches[idx + 1].start() if idx + 1 < len(matches) else doc.find("</main>", match.start())
        if end < 0:
            end = len(doc)
        cards.append((match, doc[match.start():end]))
    return cards


def parse_projection(block: str) -> tuple[str, str, float, float] | None:
    m = re.search(r'class="model-formula">.*?<strong>(.*?)</strong>', block, re.S)
    if not m:
        return None
    text = strip_tags(m.group(1))
    values = re.findall(r"([A-Z]{2,3})\s+([0-9]+(?:\.[0-9]+)?)", text)
    if len(values) < 2:
        return None
    away, away_runs = values[0]
    home, home_runs = values[1]
    projection = f"{away} {float(away_runs):.1f} - {home} {float(home_runs):.1f}"
    return projection, home, float(away_runs), float(home_runs)


def parse_sim_pick(block: str) -> tuple[str, str]:
    m = re.search(r'<div class="sim-pick"([^>]*)>(.*?)</div>', block, re.S)
    if not m:
        return "", ""
    attrs = m.group(1)
    text = strip_tags(m.group(2))
    title = ""
    title_m = re.search(r'title="([^"]+)"', attrs)
    if title_m:
        title = html.unescape(title_m.group(1))
    return text, title


def parse_games(doc: str) -> list[GameRow]:
    rows: list[GameRow] = []
    for match, block in split_game_cards(doc):
        conf = int(match.group("conf"))
        try:
            run_edge = float(match.group("edge"))
        except ValueError:
            run_edge = 0.0

        teams = re.findall(r'<div class="team-abbr">([A-Z]{2,3})</div>', block)
        moneylines = re.findall(r'<div class="team-ml">([^<]+)</div>', block)
        if len(teams) < 2 or len(moneylines) < 2:
            continue
        away, home = teams[:2]
        away_ml = parse_int_moneyline(moneylines[0])
        home_ml = parse_int_moneyline(moneylines[1])
        if away_ml is None or home_ml is None:
            continue

        spread_m = re.search(r'<div class="spread">([^<]+)</div>', block)
        probs = [float(x) / 100 for x in re.findall(r"([0-9]+(?:\.[0-9]+)?)%", spread_m.group(1) if spread_m else "")]
        if len(probs) < 2:
            continue
        away_prob, home_prob = probs[:2]

        projection_data = parse_projection(block)
        if projection_data:
            projection, _projection_home, away_runs, home_runs = projection_data
            pick_team = away if away_runs > home_runs else home
        else:
            projection = f"{away} at {home}"
            pick_team = away if away_prob > home_prob else home

        sim_pick, sim_title = parse_sim_pick(block)
        is_official = "NO PLAY" not in sim_pick.upper() and "MODEL EDGE" not in sim_pick.upper()
        official_team = re.search(r"\b([A-Z]{2,3})\s+ML\b", sim_pick)
        if is_official and official_team:
            pick_team = official_team.group(1)

        odds = home_ml if pick_team == home else away_ml
        model_prob = home_prob if pick_team == home else away_prob
        break_even = moneyline_break_even(odds)
        price_edge = model_prob - break_even if break_even is not None else None
        reason = sim_title
        if not reason and not is_official:
            if price_edge is not None:
                reason = f"{fmt_plain_pct(model_prob)} model vs {fmt_plain_pct(break_even)} break-even"
            else:
                reason = "Below official board threshold"

        rows.append(
            GameRow(
                matchup=f"{away} @ {home}",
                pick_team=pick_team,
                pick_text=f"{pick_team} ML",
                odds=odds,
                conf=conf,
                run_edge=run_edge,
                model_prob=model_prob,
                break_even=break_even,
                price_edge=price_edge,
                projection=projection,
                status="official" if is_official else "watch",
                reason=reason,
            )
        )
    return rows


def draw_logo(img: Image.Image, x: int, y: int, size: int):
    if not LOGO.exists():
        return
    logo = Image.open(LOGO).convert("RGBA")
    logo.thumbnail((size, size), Image.Resampling.LANCZOS)
    img.alpha_composite(logo, (x, y))


def draw_background(img: Image.Image):
    draw = ImageDraw.Draw(img, "RGBA")
    draw.rectangle((0, 0, W, H), fill=BLACK)
    for x in range(-40, W + 80, 96):
        draw.line((x, 0, x + 380, H), fill=(255, 255, 255, 10), width=1)
    for y in range(0, H, 110):
        draw.line((0, y, W, y), fill=(255, 255, 255, 8), width=1)
    draw.line((-60, 1180, 1120, 720), fill=(*GREEN, 48), width=7)
    draw.line((-60, 1040, 1120, 560), fill=(*ORANGE, 42), width=5)
    draw.line((180, -20, 1120, 280), fill=(*YELLOW, 40), width=5)
    draw.line((-80, 730, 770, 460), fill=(*BLUE, 38), width=5)


def draw_header(draw: ImageDraw.ImageDraw, img: Image.Image, date_label: str):
    draw_logo(img, 76, 70, 76)
    draw.text((166, 76), "MORELLO SIMS", font=load_font("display", 58), fill=WHITE)
    draw.text((168, 126), "MLB SIM SOCIAL BOARD", font=load_font("display", 31), fill=MUTED)
    rounded(draw, (714, 80, 1000, 138), 22, YELLOW, BLACK, 3)
    center_text(draw, (857, 110), date_label, load_font("display", 29), BLACK)
    draw.line((76, 184, 1002, 184), fill=(255, 255, 255, 78), width=2)


def draw_metric(draw: ImageDraw.ImageDraw, xy, big: str, label: str, accent):
    rounded(draw, xy, 18, PANEL, (255, 255, 255, 72), 2)
    x0, y0, x1, y1 = xy
    center_text(draw, ((x0 + x1) // 2, y0 + 43), big, load_font("display", 52), accent)
    center_text(draw, ((x0 + x1) // 2, y0 + 78), label, load_font("mono", 14), MUTED)


def draw_hero(draw: ImageDraw.ImageDraw, official: list[GameRow], watch: list[GameRow]):
    rounded(draw, (76, 220, 1004, 438), 24, (12, 15, 13), (255, 255, 255, 92), 2)
    draw.text((112, 246), "TODAY'S MONEYLINE BOARD", font=load_font("mono", 18), fill=GREEN)
    draw.text((108, 292), f"{len(official)}", font=load_font("display", 128), fill=WHITE, stroke_width=4, stroke_fill=BLACK)
    draw.text((232, 315), "OFFICIAL PLAYS", font=load_font("display", 62), fill=YELLOW, stroke_width=2, stroke_fill=BLACK)
    draw.text((112, 384), "Price gates decide what gets risk. Model leans stay visible below.", font=load_font("body", 29), fill=MUTED)

    avg_edge = None
    if official:
        edges = [row.price_edge for row in official if row.price_edge is not None]
        avg_edge = sum(edges) / len(edges) if edges else None
    draw_metric(draw, (76, 468, 368, 568), str(len(official)), "POSTABLE PICKS", GREEN)
    top_conf = max([row.conf for row in official], default=0)
    draw_metric(draw, (394, 468, 686, 568), f"C{top_conf}" if top_conf else "NONE", "TOP CONF", YELLOW)
    draw_metric(draw, (712, 468, 1004, 568), fmt_pct(avg_edge), "AVG PRICE EDGE", ORANGE)


def row_color(row: GameRow):
    if row.status == "official":
        return GREEN if row.conf >= 9 else YELLOW
    return ORANGE if row.price_edge is not None and row.price_edge > 0 else RED


def watch_reason(row: GameRow) -> str:
    if row.price_edge is not None and row.price_edge < 0:
        return "Model below break-even price"
    if row.conf <= 8 and row.odds < -180:
        return "Too much juice for C8"
    if row.conf <= 9 and row.odds < -200:
        return "Too much juice for C9"
    if row.odds < -220:
        return "Heavy favorite cap"
    if row.price_edge is not None and row.price_edge < 0.055:
        return "Need +5.5% to make C8 board"
    return "Below official board threshold"


def draw_pick_row(draw: ImageDraw.ImageDraw, row: GameRow, idx: int, y: int):
    accent = row_color(row)
    rounded(draw, (96, y, 984, y + 92), 15, PANEL if row.status == "official" else (18, 17, 13), (255, 255, 255, 70), 1)
    draw.rounded_rectangle((96, y, 109, y + 92), radius=6, fill=accent)
    center_text(draw, (141, y + 46), str(idx), load_font("display", 32), accent)

    label_font = load_font("display", 36)
    meta_font = load_font("body", 21)
    small_font = load_font("mono", 15)
    draw.text((178, y + 9), truncate(draw, row.pick_text, label_font, 210), font=label_font, fill=WHITE)
    draw.text((180, y + 45), truncate(draw, row.matchup, meta_font, 235), font=meta_font, fill=MUTED)

    rounded(draw, (410, y + 14, 510, y + 50), 11, WHITE)
    center_text(draw, (460, y + 32), fmt_odds(row.odds), load_font("mono", 20), BLACK)
    rounded(draw, (522, y + 14, 596, y + 50), 11, accent)
    center_text(draw, (559, y + 32), f"C{row.conf}", load_font("mono", 20), BLACK)
    draw.text((414, y + 64), truncate(draw, row.projection, small_font, 190), font=small_font, fill=MUTED)

    right_text(draw, 820, y + 29, fmt_plain_pct(row.model_prob), load_font("display", 32), WHITE)
    draw.text((662, y + 52), "MODEL WIN", font=small_font, fill=MUTED)
    edge_text = fmt_pct(row.price_edge)
    edge_fill = GREEN if row.status == "official" and row.price_edge is not None and row.price_edge >= 0.055 else ORANGE
    right_text(draw, 954, y + 29, edge_text, load_font("display", 32), edge_fill)
    draw.text((846, y + 52), "VS MARKET", font=small_font, fill=MUTED)

    if row.status != "official":
        draw.text((662, y + 71), truncate(draw, watch_reason(row), small_font, 292), font=small_font, fill=ORANGE)


def draw_section(
    draw: ImageDraw.ImageDraw,
    title: str,
    subtitle: str,
    rows: list[GameRow],
    y0: int,
    max_rows: int,
    empty: str,
) -> int:
    draw.text((92, y0), title, font=load_font("display", 42), fill=WHITE)
    draw.text((94, y0 + 38), subtitle, font=load_font("body", 23), fill=MUTED)
    y = y0 + 76
    if not rows:
        rounded(draw, (96, y, 984, y + 82), 16, PANEL, (255, 255, 255, 70), 1)
        center_text(draw, (540, y + 41), empty, load_font("display", 34), MUTED)
        return y + 100
    for idx, row in enumerate(rows[:max_rows], start=1):
        draw_pick_row(draw, row, idx, y)
        y += 100
    return y + 18


def draw_footer(draw: ImageDraw.ImageDraw):
    rounded(draw, (76, 1280, 1004, 1330), 15, (12, 16, 12), GREEN, 2)
    draw.text((112, 1305), "morellosims.com/mlbsim", font=load_font("display", 29), fill=WHITE, anchor="lm")
    right_text(draw, 962, 1305, "lines move - check board", load_font("mono", 15), MUTED)


def render(source: Path, out: Path, max_picks: int, max_watch: int) -> Path:
    doc = source.read_text(encoding="utf-8", errors="ignore")
    rows = parse_games(doc)
    official = sorted(
        [row for row in rows if row.status == "official"],
        key=lambda row: (-row.conf, -(row.price_edge or -9), -row.run_edge, row.matchup),
    )
    watch = sorted(
        [
            row
            for row in rows
            if row.status != "official" and (row.conf >= 6 or row.run_edge >= 1.4 or (row.price_edge or 0) >= 0.0)
        ],
        key=lambda row: (-row.run_edge, -row.conf, -(row.price_edge or -9), row.matchup),
    )

    out.parent.mkdir(parents=True, exist_ok=True)
    img = Image.new("RGBA", (W, H), (0, 0, 0, 255))
    draw_background(img)
    draw = ImageDraw.Draw(img, "RGBA")
    rounded(draw, (36, 34, 1044, 1316), 46, CARD, (255, 255, 255, 210), 2)
    rounded(draw, (58, 56, 1022, 1294), 36, (12, 14, 12, 238), (255, 255, 255, 56), 1)
    draw_header(draw, img, generated_label(doc))
    draw_hero(draw, official, watch)
    shown_official = official[:max_picks]
    watch_limit = max_watch if len(shown_official) <= 2 else min(max_watch, 2)
    next_y = draw_section(
        draw,
        "OFFICIAL BOARD",
        "Moneyline plays that cleared confidence and price gates.",
        official,
        612,
        max_picks,
        "NO OFFICIAL MLB PLAYS",
    )
    draw_section(
        draw,
        "PRICE WATCH",
        "Model leans filtered out by bankroll rules.",
        watch,
        next_y,
        watch_limit,
        "NO NOTABLE FILTERED LEANS",
    )
    draw_footer(draw)
    img = img.convert("RGB").filter(ImageFilter.UnsharpMask(radius=1.0, percent=110, threshold=3))
    img.save(out, quality=95)
    return out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", default=str(SOURCE), help="Generated mlbsim/index.html to parse.")
    parser.add_argument("--out", default=str(POSTERS / "mlb-social-card.png"), help="PNG output path.")
    parser.add_argument("--max-picks", type=int, default=3)
    parser.add_argument("--max-watch", type=int, default=3)
    args = parser.parse_args()
    print(render(Path(args.source), Path(args.out), args.max_picks, args.max_watch))


if __name__ == "__main__":
    main()
