#!/usr/bin/env python3
"""Render MLB social cards from the generated MLB page."""
from __future__ import annotations

import argparse
import html
import json
import re
import urllib.request
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "mlbsim" / "index.html"
PICKS_JSON = ROOT / "picks" / "mlb.json"
POSTERS = ROOT / "posters"
LOGO = ROOT / "logo-grok-transparent.png"
TEAM_LOGO_DIR = POSTERS / "assets" / "mlb-team-logos"

W, H = 1080, 1350
BOARD_LEFT = 72
BOARD_RIGHT = 1008
BOARD_CENTER = W // 2

BG = (164, 164, 162)
CARD = (174, 174, 172)
INK = (24, 24, 23)
SOFT = (57, 57, 56)
MUTED = (92, 92, 90)
FAINT = (24, 24, 23, 72)
RULE = (24, 24, 23, 115)
PANEL_FILL = (186, 186, 183, 70)
PANEL_FILL_LIGHT = (180, 180, 177, 45)
PALE = (210, 210, 206)
WHITE = (238, 238, 234)
YELLOW = (255, 234, 0)
GREEN = INK
ORANGE = SOFT

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

TEAM_IDS = {
    "ARI": 109,
    "AZ": 109,
    "ATL": 144,
    "BAL": 110,
    "BOS": 111,
    "CHC": 112,
    "CIN": 113,
    "CLE": 114,
    "COL": 115,
    "CWS": 145,
    "CHW": 145,
    "DET": 116,
    "HOU": 117,
    "KC": 118,
    "LAA": 108,
    "LAD": 119,
    "MIA": 146,
    "MIL": 158,
    "MIN": 142,
    "NYM": 121,
    "NYY": 147,
    "ATH": 133,
    "OAK": 133,
    "PHI": 143,
    "PIT": 134,
    "SD": 135,
    "SEA": 136,
    "SF": 137,
    "STL": 138,
    "TB": 139,
    "TEX": 140,
    "TOR": 141,
    "WSH": 120,
}

TEAM_ID_TO_ESPN = {
    108: "laa",
    109: "ari",
    110: "bal",
    111: "bos",
    112: "chc",
    113: "cin",
    114: "cle",
    115: "col",
    116: "det",
    117: "hou",
    118: "kc",
    119: "lad",
    120: "wsh",
    121: "nym",
    133: "oak",
    134: "pit",
    135: "sd",
    136: "sea",
    137: "sf",
    138: "stl",
    139: "tb",
    140: "tex",
    141: "tor",
    142: "min",
    143: "phi",
    144: "atl",
    145: "chw",
    146: "mia",
    147: "nyy",
    158: "mil",
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
    away: str
    home: str
    pick_team: str
    away_id: int | None
    home_id: int | None


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
    team: str
    team_id: int | None


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


def paste_contained(
    img: Image.Image,
    source: Image.Image,
    center: tuple[int, int],
    size: int,
    opacity: float = 1.0,
):
    logo = source.copy().convert("RGBA")
    logo.thumbnail((size, size), Image.Resampling.LANCZOS)
    if opacity < 1:
        alpha = logo.getchannel("A").point(lambda value: int(value * opacity))
        logo.putalpha(alpha)
    x = int(center[0] - logo.width / 2)
    y = int(center[1] - logo.height / 2)
    img.alpha_composite(logo, (x, y))


def load_morello_logo() -> Image.Image | None:
    if not LOGO.exists():
        return None
    return Image.open(LOGO).convert("RGBA")


def ensure_team_logo(team_id: int | None) -> Path | None:
    if not team_id:
        return None
    code = TEAM_ID_TO_ESPN.get(team_id)
    if not code:
        return None
    TEAM_LOGO_DIR.mkdir(parents=True, exist_ok=True)
    png = TEAM_LOGO_DIR / f"espn-{code}.png"
    if png.exists():
        return png

    try:
        urllib.request.urlretrieve(f"https://a.espncdn.com/i/teamlogos/mlb/500/{code}.png", png)
    except Exception:
        return None
    return png if png.exists() else None


def load_team_logo(team_id: int | None) -> Image.Image | None:
    path = ensure_team_logo(team_id)
    if not path:
        return None
    return Image.open(path).convert("RGBA")


def draw_team_logo(img: Image.Image, team_id: int | None, center: tuple[int, int], size: int, opacity: float = 0.92):
    logo = load_team_logo(team_id)
    if logo:
        paste_contained(img, logo, center, size, opacity)


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


def team_id_for(team: str | None) -> int | None:
    if not team:
        return None
    return TEAM_IDS.get(team.upper())


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
        logo_ids = [int(value) for value in re.findall(r"team-logos/(\d+)\.svg", block)]
        away_id = logo_ids[0] if len(logo_ids) >= 1 else team_id_for(away)
        home_id = logo_ids[1] if len(logo_ids) >= 2 else team_id_for(home)
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
                away=away,
                home=home,
                pick_team=pick_team,
                away_id=away_id,
                home_id=home_id,
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
        away = str(pick.get("away") or (html_row.away if html_row else "")).strip()
        home = str(pick.get("home") or (html_row.home if html_row else "")).strip()
        if (not away or not home) and " @ " in matchup:
            away, home = matchup.split(" @ ", 1)
        pick_team = str(pick.get("side") or pick_text.split()[0]).strip()

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
                away=away,
                home=home,
                pick_team=pick_team,
                away_id=html_row.away_id if html_row else team_id_for(away),
                home_id=html_row.home_id if html_row else team_id_for(home),
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
        meta_text = strip_tags(meta.group(1))
        team_match = re.search(r"#\w+\s+([A-Z]{2,3})\s+vs\b", meta_text)
        team = team_match.group(1) if team_match else ""
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
                meta=meta_text,
                lane=match.group("lane"),
                status=match.group("status"),
                hr_rate=float(rate.group(1)),
                signal=strip_tags(signal.group(1)) if signal else "",
                metrics=metrics,
                team=team,
                team_id=team_id_for(team),
            )
        )
    return rows


def draw_centered(draw: ImageDraw.ImageDraw, y: int, text: str, fnt: ImageFont.ImageFont, fill=INK):
    box = draw.textbbox((0, 0), text, font=fnt)
    draw.text(((W - (box[2] - box[0])) / 2, y), text, font=fnt, fill=fill)


def init_background() -> Image.Image:
    img = Image.new("RGBA", (W, H), BG)
    draw = ImageDraw.Draw(img, "RGBA")
    for y in range(H):
        shade = int(172 - 12 * (y / H))
        draw.line((0, y, W, y), fill=(shade, shade, shade - 2, 255))
    noise = Image.effect_noise((W, H), 18).convert("L").filter(ImageFilter.GaussianBlur(1.4))
    grain = Image.new("RGBA", (W, H), (150, 150, 148, 18))
    grain.putalpha(noise.point(lambda value: int(abs(value - 128) * 0.18)))
    return Image.alpha_composite(img, grain)


def init_card(title: str, subtitle: str, date_label: str) -> tuple[Image.Image, ImageDraw.ImageDraw]:
    img = init_background()
    draw = ImageDraw.Draw(img, "RGBA")
    draw.line((0, 0, W, 0), fill=(18, 18, 18, 210), width=3)

    brand_font = load_font("display", 36)
    brand_text = "MORELLO SIMS"
    brand_logo = load_morello_logo()
    brand_w = text_w(draw, brand_text, brand_font)
    brand_total = brand_w + (70 if brand_logo else 0)
    brand_x = (W - brand_total) / 2
    if brand_logo:
        paste_contained(img, brand_logo, (int(brand_x + 26), 88), 52, opacity=0.95)
        brand_x += 70
    draw.text((brand_x, 67), brand_text, font=brand_font, fill=INK)
    draw_centered(draw, 124, "sports simulation x matchup intelligence", load_font("mono", 19), SOFT)
    draw_centered(draw, 196, title.upper(), load_font("display", 96), INK)
    draw_centered(draw, 292, subtitle.upper(), load_font("body", 21), SOFT)
    draw_centered(draw, 1216, "morellosims.com/mlbsim", load_font("display", 32), INK)
    draw_centered(draw, 1260, date_label.upper(), load_font("mono", 14), MUTED)
    return img, draw


def draw_stat_strip(draw: ImageDraw.ImageDraw, y: int, stats: list[tuple[str, str, tuple[int, int, int]]]):
    x1, x2 = BOARD_LEFT, BOARD_RIGHT
    draw_panel(draw, (x1, y - 18, x2, y + 106), fill=(185, 185, 182, 80), radius=8)
    xs = [228, BOARD_CENTER, 852]
    for idx, (x, (label, value, _fill)) in enumerate(zip(xs, stats)):
        if idx:
            draw.line((x - 156, y + 4, x - 156, y + 84), fill=FAINT, width=1)
        center_text(draw, (x, y + 18), label.upper(), load_font("mono", 15), MUTED)
        center_text(draw, (x, y + 69), value, load_font("display", 49), INK)


def draw_section_label(draw: ImageDraw.ImageDraw, y: int, label: str, detail: str = ""):
    draw_centered(draw, y, label.upper(), load_font("display", 31), INK)
    if detail:
        draw_centered(draw, y + 34, detail, load_font("body", 17), SOFT)


def draw_footer(draw: ImageDraw.ImageDraw, note: str, y: int = 1168):
    draw_centered(draw, y, note.upper(), load_font("mono", 13), MUTED)


def draw_panel(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], fill=PANEL_FILL, rule=RULE, radius: int = 6):
    draw.rectangle(box, fill=fill, outline=rule, width=2)


def draw_confidence_badge(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], conf: int, large: bool = False):
    x1, y1, x2, y2 = box
    draw.rounded_rectangle(box, radius=5, fill=INK)
    label_font = load_font("mono", 11 if large else 10)
    value_font = load_font("display", 34 if large else 25)
    center_text(draw, ((x1 + x2) / 2, y1 + (14 if large else 12)), "CONFIDENCE", label_font, PALE)
    center_text(draw, ((x1 + x2) / 2, y1 + (46 if large else 39)), f"{conf}/10", value_font, WHITE)


def draw_game_row(img: Image.Image, draw: ImageDraw.ImageDraw, row: GameRow, idx: int, y: int, compact: bool = False):
    if compact:
        draw_panel(draw, (BOARD_LEFT, y, BOARD_RIGHT, y + 112), fill=PANEL_FILL_LIGHT)
        draw_team_logo(img, row.away_id, (146, y + 56), 52, opacity=0.82)
        draw_team_logo(img, row.home_id, (936, y + 56), 52, opacity=0.82)
        draw.text((214, y + 24), f"{idx:02d}", font=load_font("mono", 17), fill=MUTED)
        draw.text((268, y + 17), row.pick_text.upper(), font=load_font("display", 45), fill=INK)
        draw.text((268, y + 64), f"{row.matchup}   {fmt_odds(row.odds)}", font=load_font("mono", 18), fill=SOFT)
        draw_confidence_badge(draw, (492, y + 20, 606, y + 92), row.conf)
        right_text(draw, 862, y + 22, f"RUN SPREAD {row.run_edge:+.1f}", load_font("mono", 18), INK)
        right_text(draw, 862, y + 62, "PRICE ALREADY JUICED", load_font("mono", 14), MUTED)
        return

    draw_panel(draw, (BOARD_LEFT, y, BOARD_RIGHT, y + 296), fill=PANEL_FILL, radius=8)
    draw_centered(draw, y + 21, "OFFICIAL PICK", load_font("mono", 17), MUTED)
    draw_team_logo(img, row.away_id, (188, y + 133), 132, opacity=0.96)
    draw_team_logo(img, row.home_id, (892, y + 133), 132, opacity=0.96)
    draw_centered(draw, y + 61, row.pick_text.upper(), load_font("display", 104), INK)
    draw_centered(draw, y + 158, f"{row.matchup}   {fmt_odds(row.odds)}", load_font("mono", 27), SOFT)
    draw_centered(draw, y + 197, row.projection.upper(), load_font("mono", 17), MUTED)
    metrics = [
        ("CONFIDENCE", f"{row.conf}/10"),
        ("PRICE EDGE", fmt_pct(row.price_edge, signed=True)),
        ("MODEL WIN", fmt_pct(row.model_prob)),
        ("RUN SPREAD", f"{row.run_edge:+.1f}"),
    ]
    xs = [226, 430, 650, 854]
    for x, (label, value) in zip(xs, metrics):
        if label == "CONFIDENCE":
            draw_confidence_badge(draw, (x - 76, y + 220, x + 76, y + 284), row.conf, large=True)
        else:
            center_text(draw, (x, y + 244), value, load_font("display", 36), INK)
            center_text(draw, (x, y + 272), label, load_font("mono", 12), MUTED)


def clean_hr_meta(meta: str) -> str:
    return re.sub(r"\s+\W+\s+team.*", "", meta)


def draw_hr_row(img: Image.Image, draw: ImageDraw.ImageDraw, row: HrRow, y: int, compact: bool = False):
    lane = "POWER" if row.lane == "DAMAGE" else row.lane
    meta = clean_hr_meta(row.meta)
    blast = row.metrics.get("blast") or row.metrics.get("power") or "-"
    pressure = row.metrics.get("pressure") or "-"

    if compact:
        draw_panel(draw, (BOARD_LEFT, y, BOARD_RIGHT, y + 62), fill=PANEL_FILL_LIGHT)
        draw_team_logo(img, row.team_id, (138, y + 31), 34, opacity=0.76)
        draw.text((210, y + 8), f"{row.rank}  {row.name}".upper(), font=load_font("display", 29), fill=INK)
        right_text(draw, 936, y + 9, f"{row.hr_rate:.1f}%", load_font("display", 29), INK)
        draw.text((212, y + 40), meta.upper(), font=load_font("mono", 11), fill=MUTED)
        return

    draw_panel(draw, (BOARD_LEFT, y, BOARD_RIGHT, y + 80), fill=PANEL_FILL_LIGHT)
    draw_team_logo(img, row.team_id, (138, y + 40), 48, opacity=0.88)
    left = f"{row.rank}. {row.name}"
    draw.text((210, y + 7), left.upper(), font=load_font("display", 32), fill=INK)
    right_text(draw, 936, y + 10, f"{row.hr_rate:.1f}%", load_font("display", 32), INK)
    draw.text((212, y + 41), meta.upper(), font=load_font("mono", 12), fill=SOFT)
    detail = f"{lane.upper()}   BLAST {blast}   PRESSURE {pressure}"
    draw.text((212, y + 60), detail, font=load_font("mono", 11), fill=MUTED)


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

    img, draw = init_card("MLB MONEYLINE", "official pick board", generated_label(doc))
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
    draw_stat_strip(draw, 378, strip_stats)

    y = 508
    official_to_draw = official[:max_picks]
    draw_section_label(draw, y, "official picks", f"{len(official_to_draw)} posted")
    y += 64
    watch_to_draw = watch[:max_watch]
    if official_to_draw:
        for idx, row in enumerate(official_to_draw, 1):
            draw_game_row(img, draw, row, idx, y)
            y += 302
    else:
        draw.text((86, y), "No official MLB plays.", font=load_font("display", 44), fill=SOFT)
        y += 96

    y += 2
    draw_section_label(draw, y, "watchlist", "large run spread, but ML price is already juiced")
    y += 70
    for idx, row in enumerate(watch_to_draw, 1):
        draw_game_row(img, draw, row, idx, y, compact=True)
        y += 124

    draw_footer(draw, "watchlist means run gap is there, but the price is too juiced", y=1194)
    out.parent.mkdir(parents=True, exist_ok=True)
    img.convert("RGB").filter(ImageFilter.UnsharpMask(radius=0.7, percent=105, threshold=3)).save(out, quality=95)
    return out


def render_hr(source: Path, out: Path, max_lotto: int, max_watch: int) -> Path:
    doc = source.read_text(encoding="utf-8", errors="ignore")
    rows = parse_hr_rows(doc)
    lotto = [row for row in rows if row.status == "lotto"]
    watch = [row for row in rows if row.status == "watch"]

    img, draw = init_card("GO-YARD LOTTO", "lotto first / watchlist below", generated_label(doc))
    top = max([row.hr_rate for row in lotto], default=0)
    draw_stat_strip(
        draw,
        340,
        [
            ("lotto", str(len(lotto)), YELLOW),
            ("top hr", f"{top:.1f}%", WHITE),
            ("watch", str(len(watch)), ORANGE),
        ],
    )

    y = 452
    draw_section_label(draw, y, "lotto card", "board order")
    y += 52
    lotto_to_draw = lotto[:max_lotto]
    watch_to_draw = watch[:max_watch]
    if lotto_to_draw:
        for row in lotto_to_draw:
            draw_hr_row(img, draw, row, y)
            y += 83
    else:
        draw.text((86, y), "No HR Lotto qualifiers.", font=load_font("display", 44), fill=SOFT)
        y += 96

    if watch_to_draw:
        y += 2
        draw_section_label(draw, y, "watchlist")
        y += 42
        for row in watch_to_draw:
            draw_hr_row(img, draw, row, y, compact=True)
            y += 64

    draw_footer(draw, "HR props are volatile", y=1194)
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
