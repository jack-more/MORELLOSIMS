#!/usr/bin/env python3
"""Render MLB social cards from the generated MLB page."""
from __future__ import annotations

import argparse
import html
import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "mlbsim" / "index.html"
PICKS_JSON = ROOT / "picks" / "mlb.json"
POSTERS = ROOT / "posters"
LOGO = ROOT / "logo-grok-transparent.png"

W, H = 1080, 1350

BG = (158, 158, 158)
CARD = (255, 255, 255)
INK = (8, 8, 8)
SOFT = (74, 74, 74)
MUTED = (112, 112, 112)
YELLOW = (255, 234, 0)
GREEN = (0, 163, 52)
ORANGE = (255, 107, 0)
WHITE = (255, 255, 255)

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
class GameRow:
    matchup: str
    pick_text: str
    odds: int
    conf: int
    run_edge: float
    model_prob: float
    break_even: float | None
    price_edge: float | None
    projection: str
    status: str


@dataclass(frozen=True)
class HrRow:
    rank: str
    name: str
    meta: str
    lane: str
    status: str
    hr_rate: float
    signal: str
    metrics: dict[str, str]


@dataclass(frozen=True)
class TrackingStats:
    record: str
    roi: str
    streak: str


def load_font(kind: str, size: int) -> ImageFont.ImageFont:
    for candidate in FONT_CANDIDATES[kind]:
        path = Path(candidate)
        if path.exists():
            return ImageFont.truetype(str(path), size=size)
    return ImageFont.load_default()


def strip_tags(value: str) -> str:
    value = re.sub(r"<br\s*/?>", " ", value, flags=re.I)
    value = re.sub(r"<.*?>", " ", value, flags=re.S)
    value = html.unescape(value).replace("\xa0", " ")
    return re.sub(r"\s+", " ", value).strip()


def text_w(draw: ImageDraw.ImageDraw, text: str, fnt: ImageFont.ImageFont) -> int:
    box = draw.textbbox((0, 0), text, font=fnt)
    return box[2] - box[0]


def truncate(draw: ImageDraw.ImageDraw, text: str, fnt: ImageFont.ImageFont, max_w: int) -> str:
    if text_w(draw, text, fnt) <= max_w:
        return text
    text = text.strip()
    while text and text_w(draw, text + "...", fnt) > max_w:
        text = text[:-1].rstrip()
    return text + "..."


def center_text(draw: ImageDraw.ImageDraw, center: tuple[int, int], text: str, fnt: ImageFont.ImageFont, fill):
    box = draw.textbbox((0, 0), text, font=fnt)
    x = center[0] - (box[2] - box[0]) / 2 - box[0]
    y = center[1] - (box[3] - box[1]) / 2 - box[1]
    draw.text((x, y), text, font=fnt, fill=fill)


def right_text(draw: ImageDraw.ImageDraw, right_x: int, y: int, text: str, fnt: ImageFont.ImageFont, fill):
    box = draw.textbbox((0, 0), text, font=fnt)
    draw.text((right_x - (box[2] - box[0]), y), text, font=fnt, fill=fill)


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


def fmt_pct(value: float | None, digits: int = 1, signed: bool = False) -> str:
    if value is None:
        return "n/a"
    sign = "+" if signed and value >= 0 else ""
    return f"{sign}{value * 100:.{digits}f}%"


def generated_label(doc: str) -> str:
    match = re.search(r"Generated\s+(\d{4}-\d{2}-\d{2})\s+(\d{1,2}:\d{2})\s+ET", doc)
    if not match:
        return datetime.now().strftime("%b %d, %Y").upper()
    try:
        date_label = datetime.strptime(match.group(1), "%Y-%m-%d").strftime("%b %d, %Y").upper()
    except ValueError:
        date_label = match.group(1)
    return f"{date_label}  {match.group(2)} ET"


def generated_date(doc: str) -> str | None:
    match = re.search(r"Generated\s+(\d{4}-\d{2}-\d{2})\s+\d{1,2}:\d{2}\s+ET", doc)
    return match.group(1) if match else None


def parse_tracking_stats(doc: str) -> TrackingStats | None:
    block = re.search(r"TRACKED PICKS BOX.*?FILTER BAR", doc, re.S)
    if not block:
        return None
    text = strip_tags(block.group(0))
    record = re.search(r"TRACKED\s+([0-9]+-[0-9]+)", text)
    roi = re.search(r"ROI\s+([+-]?[0-9.]+%)", text)
    streak = re.search(r"STREAK\s+([WL][0-9]+)", text)
    if not (record and roi and streak):
        return None
    return TrackingStats(record=record.group(1), roi=roi.group(1), streak=streak.group(1))


def split_by_marker(doc: str, marker_re: re.Pattern[str], stop: str | None = None) -> list[tuple[re.Match[str], str]]:
    matches = list(marker_re.finditer(doc))
    blocks = []
    for idx, match in enumerate(matches):
        end = matches[idx + 1].start() if idx + 1 < len(matches) else -1
        if end < 0 and stop:
            end = doc.find(stop, match.start())
        if end < 0:
            end = len(doc)
        blocks.append((match, doc[match.start():end]))
    return blocks


def parse_projection(block: str) -> tuple[str, float, float] | None:
    match = re.search(r'class="model-formula">.*?<strong>(.*?)</strong>', block, re.S)
    if not match:
        return None
    values = re.findall(r"([A-Z]{2,3})\s+([0-9]+(?:\.[0-9]+)?)", strip_tags(match.group(1)))
    if len(values) < 2:
        return None
    away, away_runs = values[0]
    home, home_runs = values[1]
    away_runs_f = float(away_runs)
    home_runs_f = float(home_runs)
    return f"{away} {away_runs_f:.1f} - {home} {home_runs_f:.1f}", away_runs_f, home_runs_f


def parse_sim_pick(block: str) -> str:
    match = re.search(r'<div class="sim-pick"[^>]*>(.*?)</div>', block, re.S)
    return strip_tags(match.group(1)) if match else ""


def parse_games(doc: str) -> list[GameRow]:
    card_re = re.compile(
        r'<div class="game-card"\s+data-conf="(?P<conf>\d+)"\s+data-value="[^"]*"\s+data-edge="(?P<edge>[^"]*)">',
        re.S,
    )
    rows: list[GameRow] = []
    for match, block in split_by_marker(doc, card_re, "</main>"):
        teams = re.findall(r'<div class="team-abbr">([A-Z]{2,3})</div>', block)
        lines = re.findall(r'<div class="team-ml">([^<]+)</div>', block)
        spread = re.search(r'<div class="spread">([^<]+)</div>', block)
        if len(teams) < 2 or len(lines) < 2 or not spread:
            continue

        away, home = teams[:2]
        away_ml = parse_int_moneyline(lines[0])
        home_ml = parse_int_moneyline(lines[1])
        probs = [float(x) / 100 for x in re.findall(r"([0-9]+(?:\.[0-9]+)?)%", spread.group(1))]
        if away_ml is None or home_ml is None or len(probs) < 2:
            continue

        projection = parse_projection(block)
        if projection:
            projection_text, away_runs, home_runs = projection
            pick_team = away if away_runs > home_runs else home
        else:
            projection_text = f"{away} @ {home}"
            pick_team = away if probs[0] > probs[1] else home

        sim_pick = parse_sim_pick(block)
        official = "NO PLAY" not in sim_pick.upper() and "MODEL EDGE" not in sim_pick.upper()
        official_team = re.search(r"\b([A-Z]{2,3})\s+ML\b", sim_pick)
        visible_conf = re.search(r"\bC:?\s*(\d+)", sim_pick)
        row_conf = int(visible_conf.group(1)) if official and visible_conf else int(match.group("conf"))
        if official and official_team:
            pick_team = official_team.group(1)

        odds = home_ml if pick_team == home else away_ml
        model_prob = probs[1] if pick_team == home else probs[0]
        break_even = moneyline_break_even(odds)
        price_edge = model_prob - break_even if break_even is not None else None
        try:
            run_edge = float(match.group("edge"))
        except ValueError:
            run_edge = 0.0

        rows.append(
            GameRow(
                matchup=f"{away} @ {home}",
                pick_text=f"{pick_team} ML",
                odds=odds,
                conf=row_conf,
                run_edge=run_edge,
                model_prob=model_prob,
                break_even=break_even,
                price_edge=price_edge,
                projection=projection_text,
                status="official" if official else "watch",
            )
        )
    return rows


def load_official_pick_rows(doc: str, parsed_rows: list[GameRow]) -> list[GameRow]:
    if not PICKS_JSON.exists():
        return []

    try:
        picks = json.loads(PICKS_JSON.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []

    target_date = generated_date(doc)
    pending_dates = sorted(
        {
            str(pick.get("date"))
            for pick in picks
            if pick.get("sport") == "mlb" and pick.get("status") == "pending"
        },
        reverse=True,
    )
    if not target_date and pending_dates:
        target_date = pending_dates[0]

    html_by_key = {(row.matchup, row.pick_text): row for row in parsed_rows}
    rows: list[GameRow] = []
    seen = set()
    for pick in picks:
        if pick.get("sport") != "mlb" or pick.get("status") != "pending":
            continue
        if target_date and pick.get("date") != target_date:
            continue
        try:
            conf = int(pick.get("conf") or 0)
        except (TypeError, ValueError):
            conf = 0
        if conf < 8:
            continue

        matchup = str(pick.get("matchup") or f'{pick.get("away", "")} @ {pick.get("home", "")}').strip()
        pick_text = str(pick.get("pick_text") or f'{pick.get("side", "")} ML').strip()
        key = (matchup, pick_text)
        if key in seen:
            continue
        seen.add(key)

        html_row = html_by_key.get(key)
        odds = parse_int_moneyline(str(pick.get("odds") or ""))
        if odds is None and html_row:
            odds = html_row.odds
        if odds is None:
            continue

        break_even = moneyline_break_even(odds)
        model_prob = html_row.model_prob if html_row else 0
        price_edge = model_prob - break_even if model_prob and break_even is not None else None
        try:
            run_edge = float(pick.get("sim_edge") or 0)
        except (TypeError, ValueError):
            run_edge = 0.0
        projection = str(pick.get("sim_projection") or (html_row.projection if html_row else matchup))

        rows.append(
            GameRow(
                matchup=matchup,
                pick_text=pick_text,
                odds=odds,
                conf=conf,
                run_edge=run_edge,
                model_prob=model_prob,
                break_even=break_even,
                price_edge=price_edge,
                projection=projection,
                status="official",
            )
        )
    return rows


def parse_hr_rows(doc: str) -> list[HrRow]:
    row_re = re.compile(
        r'<div class="hr-row [^"]*" data-hr-card="1" data-hr-lane="(?P<lane>[^"]+)" data-hr-status="(?P<status>lotto|watch)">',
        re.S,
    )
    rows: list[HrRow] = []
    for match, block in split_by_marker(doc, row_re, "</main>"):
        rank = re.search(r'<div class="hr-rank">(.*?)</div>', block, re.S)
        name = re.search(r'<div class="hr-name">(.*?)</div>', block, re.S)
        meta = re.search(r'<div class="hr-meta">(.*?)</div>', block, re.S)
        signal = re.search(r'<div class="hr-signal">(.*?)</div>', block, re.S)
        rate = re.search(r'<div class="hr-rate">([0-9.]+)%</div>', block)
        if not name or not meta or not rate:
            continue
        metrics = {
            strip_tags(label).lower(): strip_tags(value)
            for label, value in re.findall(
                r'<div class="hr-metric[^"]*">\s*<span>(.*?)</span>\s*<strong>(.*?)</strong>',
                block,
                re.S,
            )
        }
        rows.append(
            HrRow(
                rank=strip_tags(rank.group(1)) if rank else str(len(rows) + 1),
                name=strip_tags(name.group(1)),
                meta=strip_tags(meta.group(1)),
                lane=match.group("lane"),
                status=match.group("status"),
                hr_rate=float(rate.group(1)),
                signal=strip_tags(signal.group(1)) if signal else "",
                metrics=metrics,
            )
        )
    return rows


def draw_logo(img: Image.Image, x: int, y: int, size: int):
    if not LOGO.exists():
        return
    logo = Image.open(LOGO).convert("RGBA")
    logo.thumbnail((size, size), Image.Resampling.LANCZOS)
    img.alpha_composite(logo, (x, y))


def dot_field(draw: ImageDraw.ImageDraw, xy, step: int = 20):
    x1, y1, x2, y2 = xy
    for y in range(y1, y2, step):
        for x in range(x1, x2, step):
            draw.ellipse((x, y, x + 2, y + 2), fill=(0, 0, 0, 18))


def init_card(title: str, subtitle: str, date_label: str) -> tuple[Image.Image, ImageDraw.ImageDraw]:
    img = Image.new("RGBA", (W, H), BG)
    draw = ImageDraw.Draw(img, "RGBA")
    draw.rectangle((70, 70, 1034, 1308), fill=YELLOW)
    draw.rectangle((54, 54, 1018, 1292), fill=CARD, outline=INK, width=3)
    dot_field(draw, (66, 66, 1006, 1280))
    draw_logo(img, 86, 86, 58)
    draw.text((160, 86), "MORELLO SIMS", font=load_font("display", 48), fill=INK)
    draw.text((162, 127), subtitle.upper(), font=load_font("mono", 15), fill=SOFT)
    right_text(draw, 982, 100, date_label, load_font("mono", 17), SOFT)
    draw.line((86, 174, 986, 174), fill=INK, width=3)
    draw.text((86, 206), title.upper(), font=load_font("display", 96), fill=INK)
    return img, draw


def pill(draw: ImageDraw.ImageDraw, xy, text: str, fill, text_fill=INK, outline=INK):
    draw.rectangle(xy, fill=fill, outline=outline, width=2)
    center_text(draw, ((xy[0] + xy[2]) // 2, (xy[1] + xy[3]) // 2), text, load_font("mono", 17), text_fill)


def draw_stat_strip(draw: ImageDraw.ImageDraw, y: int, stats: list[tuple[str, str, tuple[int, int, int]]]):
    draw.rectangle((92, y + 8, 1000, y + 102), fill=YELLOW)
    draw.rectangle((86, y, 994, y + 94), fill=INK, outline=YELLOW, width=2)
    col_w = 908 / len(stats)
    for idx, (label, value, fill) in enumerate(stats):
        x = 86 + int(idx * col_w)
        if idx:
            draw.line((x, y + 18, x, y + 76), fill=(255, 255, 255, 40), width=1)
        center_x = 86 + int((idx + 0.5) * col_w)
        center_text(draw, (center_x, y + 31), label.upper(), load_font("mono", 13), (145, 145, 145))
        center_text(draw, (center_x, y + 64), value, load_font("display", 45), fill)


def draw_section_label(draw: ImageDraw.ImageDraw, x: int, y: int, label: str, detail: str = ""):
    draw.rectangle((x, y, x + 16, y + 26), fill=YELLOW, outline=INK, width=2)
    draw.text((x + 26, y - 1), label.upper(), font=load_font("mono", 20), fill=INK)
    if detail:
        right_text(draw, 994, y + 1, detail.upper(), load_font("mono", 13), SOFT)


def draw_footer(draw: ImageDraw.ImageDraw, note: str, y: int = 1238):
    draw.line((86, y, 994, y), fill=INK, width=3)
    draw.text((86, y + 34), "morellosims.com/mlbsim", font=load_font("display", 32), fill=INK, anchor="lm")
    right_text(draw, 994, y + 19, note.upper(), load_font("mono", 13), SOFT)


def draw_game_row(draw: ImageDraw.ImageDraw, row: GameRow, idx: int, y: int, compact: bool = False):
    if compact:
        draw.line((86, y, 994, y), fill=(0, 0, 0, 75), width=1)
        center_text(draw, (107, y + 36), f"{idx}", load_font("mono", 16), MUTED)
        draw.text((138, y + 11), row.pick_text, font=load_font("display", 38), fill=INK)
        draw.text((140, y + 48), row.matchup, font=load_font("mono", 15), fill=SOFT)
        pill(draw, (430, y + 18, 526, y + 51), fmt_odds(row.odds), WHITE, INK)
        pill(draw, (538, y + 18, 604, y + 51), f"C{row.conf}", INK, YELLOW)
        right_text(draw, 974, y + 13, fmt_pct(row.price_edge, signed=True), load_font("display", 35), ORANGE)
        draw.text((826, y + 49), "EDGE WATCH", font=load_font("mono", 11), fill=SOFT)
        return

    draw.rectangle((86, y, 994, y + 126), fill=WHITE, outline=INK, width=2)
    draw.rectangle((86, y, 144, y + 126), fill=YELLOW, outline=INK, width=2)
    center_text(draw, (115, y + 63), f"{idx}", load_font("display", 35), INK)
    draw.text((164, y + 13), row.pick_text, font=load_font("display", 58), fill=INK)
    draw.text((166, y + 69), row.matchup, font=load_font("body", 24), fill=SOFT)
    draw.text((166, y + 95), row.projection, font=load_font("mono", 15), fill=MUTED)
    pill(draw, (506, y + 25, 612, y + 62), fmt_odds(row.odds), WHITE, INK)
    pill(draw, (626, y + 25, 698, y + 62), f"C{row.conf}", INK, YELLOW)
    right_text(draw, 966, y + 10, fmt_pct(row.price_edge, signed=True), load_font("display", 50), GREEN)
    right_text(draw, 966, y + 63, fmt_pct(row.model_prob), load_font("display", 34), INK)
    draw.text((802, y + 99), "EDGE / MODEL", font=load_font("mono", 12), fill=SOFT)


def clean_hr_meta(meta: str) -> str:
    return re.sub(r"\s+\W+\s+team.*", "", meta)


def draw_hr_row(draw: ImageDraw.ImageDraw, row: HrRow, y: int, compact: bool = False):
    lane = "POWER" if row.lane == "DAMAGE" else row.lane
    meta = clean_hr_meta(row.meta)
    blast = row.metrics.get("blast") or row.metrics.get("power") or "-"
    pressure = row.metrics.get("pressure") or "-"
    rank_fill = YELLOW if row.status == "lotto" else INK
    rank_text = INK if row.status == "lotto" else YELLOW

    if compact:
        draw.line((86, y, 994, y), fill=(0, 0, 0, 75), width=1)
        draw.rectangle((86, y + 13, 130, y + 50), fill=rank_fill, outline=INK, width=2)
        center_text(draw, (108, y + 32), row.rank, load_font("mono", 14), rank_text)
        draw.text((148, y + 4), truncate(draw, row.name, load_font("display", 36), 450), font=load_font("display", 36), fill=INK)
        draw.text((150, y + 40), truncate(draw, meta, load_font("body", 17), 520), font=load_font("body", 17), fill=SOFT)
        right_text(draw, 970, y + 6, f"{row.hr_rate:.1f}%", load_font("display", 39), ORANGE)
        draw.text((858, y + 46), "WATCH RATE", font=load_font("mono", 10), fill=SOFT)
        return

    draw.rectangle((86, y, 994, y + 88), fill=WHITE, outline=INK, width=2)
    draw.rectangle((86, y, 142, y + 88), fill=rank_fill, outline=INK, width=2)
    center_text(draw, (114, y + 44), row.rank, load_font("display", 29), rank_text)
    name_font = load_font("display", 37)
    draw.text((162, y + 4), truncate(draw, row.name, name_font, 430), font=name_font, fill=INK)
    draw.text((164, y + 41), truncate(draw, meta, load_font("body", 17), 520), font=load_font("body", 17), fill=SOFT)
    pill(draw, (164, y + 62, 252, y + 84), lane, INK, YELLOW)
    draw.text((270, y + 67), f"BLAST {blast}  PRESSURE {pressure}", font=load_font("mono", 11), fill=SOFT)
    right_text(draw, 970, y + 7, f"{row.hr_rate:.1f}%", load_font("display", 43), INK)
    draw.text((866, y + 54), "HR RATE", font=load_font("mono", 11), fill=SOFT)


def render_picks(source: Path, out: Path, max_picks: int, max_watch: int) -> Path:
    doc = source.read_text(encoding="utf-8", errors="ignore")
    rows = parse_games(doc)
    official_source = load_official_pick_rows(doc, rows)
    if official_source:
        official_keys = {(row.matchup, row.pick_text) for row in official_source}
        rows = [
            *official_source,
            *[
                row
                for row in rows
                if (row.matchup, row.pick_text) not in official_keys
            ],
        ]
    official = sorted(
        [row for row in rows if row.status == "official"],
        key=lambda row: (-row.conf, -(row.price_edge or -9), -row.run_edge),
    )
    watch = sorted(
        [row for row in rows if row.status != "official" and (row.conf >= 6 or row.run_edge >= 1.4)],
        key=lambda row: (-row.run_edge, -row.conf, -(row.price_edge or -9)),
    )

    avg_edge = None
    if official:
        edges = [row.price_edge for row in official if row.price_edge is not None]
        avg_edge = sum(edges) / len(edges) if edges else None

    img, draw = init_card("MLB Card", "MLB SIM", generated_label(doc))
    draw.text((88, 304), "OFFICIAL MONEYLINE CARD", font=load_font("mono", 18), fill=SOFT)
    tracking = parse_tracking_stats(doc)
    if tracking:
        strip_stats = [
            ("tracked", tracking.record, GREEN),
            ("roi", tracking.roi, YELLOW),
            ("streak", tracking.streak, WHITE),
        ]
    else:
        strip_stats = [
            ("posted", str(len(official)), YELLOW),
            ("top conf", f"C{max([r.conf for r in official], default=0)}", WHITE),
            ("avg edge", fmt_pct(avg_edge, signed=True), GREEN),
        ]
    draw_stat_strip(draw, 334, strip_stats)

    y = 466
    official_to_draw = official[:max_picks]
    draw_section_label(draw, 86, y, "Official Picks", f"{len(official_to_draw)} posted")
    y += 46
    watch_to_draw = watch[:max_watch]
    if official_to_draw:
        for idx, row in enumerate(official_to_draw, 1):
            draw_game_row(draw, row, idx, y)
            y += 142
    else:
        draw.text((86, y), "No official MLB plays.", font=load_font("display", 44), fill=SOFT)
        y += 96

    y += 2
    draw_section_label(draw, 86, y, "Watchlist", "model context")
    y += 42
    for idx, row in enumerate(watch_to_draw, 1):
        draw_game_row(draw, row, idx, y, compact=True)
        y += 72

    draw_footer(draw, "check live board for line movement", y=1238)
    out.parent.mkdir(parents=True, exist_ok=True)
    img.convert("RGB").filter(ImageFilter.UnsharpMask(radius=0.7, percent=105, threshold=3)).save(out, quality=95)
    return out


def render_hr(source: Path, out: Path, max_lotto: int, max_watch: int) -> Path:
    doc = source.read_text(encoding="utf-8", errors="ignore")
    rows = parse_hr_rows(doc)
    lotto = [row for row in rows if row.status == "lotto"]
    watch = [row for row in rows if row.status == "watch"]

    img, draw = init_card("Go-Yard", "MLB HR CARD", generated_label(doc))
    draw.text((88, 304), "LOTTO CARD FIRST. WATCHLIST BELOW.", font=load_font("mono", 18), fill=SOFT)
    top = max([row.hr_rate for row in lotto], default=0)
    draw_stat_strip(
        draw,
        334,
        [
            ("lotto", str(len(lotto)), YELLOW),
            ("top hr", f"{top:.1f}%", WHITE),
            ("watch", str(len(watch)), ORANGE),
        ],
    )

    y = 456
    draw_section_label(draw, 86, y, "Lotto Card", "board order")
    y += 40
    lotto_to_draw = lotto[:max_lotto]
    watch_to_draw = watch[:max_watch]
    if lotto_to_draw:
        for row in lotto_to_draw:
            draw_hr_row(draw, row, y)
            y += 92
    else:
        draw.text((86, y), "No HR Lotto qualifiers.", font=load_font("display", 44), fill=SOFT)
        y += 96

    if watch_to_draw:
        y += 8
        draw_section_label(draw, 86, y, "Watchlist", "secondary")
        y += 38
        for row in watch_to_draw:
            draw_hr_row(draw, row, y, compact=True)
            y += 62

    draw_footer(draw, "HR props are volatile", y=1240)
    out.parent.mkdir(parents=True, exist_ok=True)
    img.convert("RGB").filter(ImageFilter.UnsharpMask(radius=0.7, percent=105, threshold=3)).save(out, quality=95)
    return out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", default=str(SOURCE), help="Generated mlbsim/index.html to parse.")
    parser.add_argument("--kind", choices=["picks", "hr", "both"], default="picks")
    parser.add_argument("--out", default=str(POSTERS / "mlb-social-card.png"), help="Moneyline PNG output path.")
    parser.add_argument("--hr-out", default=str(POSTERS / "mlb-hr-card.png"), help="HR PNG output path.")
    parser.add_argument("--max-picks", type=int, default=3)
    parser.add_argument("--max-watch", type=int, default=2)
    parser.add_argument("--max-hr-lotto", type=int, default=6)
    parser.add_argument("--max-hr-watch", type=int, default=2)
    args = parser.parse_args()

    source = Path(args.source)
    outputs = []
    if args.kind in ("picks", "both"):
        outputs.append(render_picks(source, Path(args.out), args.max_picks, args.max_watch))
    if args.kind in ("hr", "both"):
        outputs.append(render_hr(source, Path(args.hr_out), args.max_hr_lotto, args.max_hr_watch))
    for output in outputs:
        print(output)


if __name__ == "__main__":
    main()
