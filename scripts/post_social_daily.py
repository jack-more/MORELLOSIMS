#!/usr/bin/env python3
"""Daily social poster — public Telegram channel + X (@MorelloSims).

Two modes:
  --mode picks   morning teaser: render the MLB social card (reuses
                 render_mlb_social_card.py) and post a short caption that
                 teases the top pick + season record, pointing at the site.
  --mode recap   post-settlement recap: compute yesterday's W-L and P&L from
                 picks/mlb.json, render a P&L card (render_pnl_card.py) and
                 post honest results — wins AND losses.

Destinations:
  Telegram public channel   TELEGRAM_BOT_TOKEN + TELEGRAM_PUBLIC_CHANNEL_ID
                            (the premium channel uses TELEGRAM_PREMIUM_CHANNEL_ID
                            via tg_channel_bot.py — this script never posts there)
  X / Twitter               X_API_KEY, X_API_SECRET, X_ACCESS_TOKEN,
                            X_ACCESS_SECRET (OAuth 1.0a user context)

Missing credentials are never fatal: each destination logs a skip and the
script exits 0, so the workflow stays green while secrets are being set up.
--dry-run renders everything and prints the would-be posts without touching
the network.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import json
import os
import secrets as _secrets
import subprocess
import sys
import time
import urllib.parse
from datetime import datetime, timedelta, timezone
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
ROOT = SCRIPTS.parent
sys.path.insert(0, str(SCRIPTS))

from send_telegram_cards import send_photo as tg_send_photo  # noqa: E402
import render_pnl_card  # noqa: E402

PICKS_MLB = ROOT / "picks" / "mlb.json"
PICKS_NBA = ROOT / "picks" / "nba.json"
BASELINES = ROOT / "picks" / "baselines.json"
MODEL_ERA = ROOT / "picks" / "model_era.json"
OUT_DIR = ROOT / "output" / "social"
SITE = "morellosims.com"

X_TWEET_URL = "https://api.twitter.com/2/tweets"
X_MEDIA_URL = "https://upload.twitter.com/1.1/media/upload.json"
X_ENV = ("X_API_KEY", "X_API_SECRET", "X_ACCESS_TOKEN", "X_ACCESS_SECRET")

# Approximate ET (matches post_daily_cards.py convention).
ET = timezone(timedelta(hours=-4))


# ---------------------------------------------------------------- helpers

def log(msg: str) -> None:
    print(msg, flush=True)


def load_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def today_et() -> str:
    return datetime.now(ET).strftime("%Y-%m-%d")


def pretty_date(iso: str) -> str:
    try:
        return datetime.strptime(iso, "%Y-%m-%d").strftime("%b %d")
    except ValueError:
        return iso


def conf_of(pick: dict) -> int:
    try:
        return int(pick.get("conf") or 0)
    except (TypeError, ValueError):
        return 0


def units_of(pick: dict, key: str) -> float:
    try:
        return float(pick.get(key) or 0)
    except (TypeError, ValueError):
        return 0.0


def fmt_units(value: float) -> str:
    return f"{value:+.1f}u".replace(".0u", "u")


def truncate_caption(text: str, limit: int = 280) -> str:
    """Cap a caption at `limit` chars without cutting mid-word when possible."""
    if len(text) <= limit:
        return text
    cut = text[: limit - 1]
    if " " in cut[limit // 2:]:
        cut = cut[: cut.rfind(" ")]
    return cut.rstrip() + "…"


def season_record(mlb_picks: list[dict]) -> tuple[str, float]:
    """Season-to-date record + P&L: manual baseline plus tracked settled picks.

    Legacy fallback — only used when picks/model_era.json is absent.
    """
    baseline = load_json(BASELINES, {}).get("mlb", {})
    settled = [
        p for p in mlb_picks
        if p.get("sport") == "mlb" and conf_of(p) >= 8
        and p.get("status") in ("win", "loss", "push")
    ]
    wins = (baseline.get("wins") or 0) + sum(1 for p in settled if p["status"] == "win")
    losses = (baseline.get("losses") or 0) + sum(1 for p in settled if p["status"] == "loss")
    pl = (baseline.get("pl") or 0) + sum(units_of(p, "pl") for p in settled)
    return f"{wins}-{losses}", pl


# ---------------------------------------------------------------- model era

def load_era() -> dict | None:
    """Active model era (picks/model_era.json), or None -> legacy captions."""
    era = load_json(MODEL_ERA, None)
    if isinstance(era, dict) and era.get("era") and era.get("start_date"):
        return era
    return None


def era_short(era: dict) -> str:
    return str(era["era"]).upper()


def in_era(pick: dict, era: dict) -> bool:
    """A pick belongs to the era if stamped model_version == era; unstamped
    picks fall back to date >= era start_date."""
    stamp = pick.get("model_version")
    if stamp:
        return str(stamp).lower() == str(era["era"]).lower()
    return str(pick.get("date") or "") >= str(era["start_date"])


def era_record(mlb_picks: list[dict], era: dict) -> tuple[int, int, float, int]:
    """(wins, losses, pl, settled_count) for the era only — no v1 baseline,
    no pre-era picks. The v1 archive lives on the site, not in captions."""
    settled = [
        p for p in mlb_picks
        if p.get("sport") == "mlb" and conf_of(p) >= 8
        and p.get("status") in ("win", "loss", "push")
        and in_era(p, era)
    ]
    wins = sum(1 for p in settled if p["status"] == "win")
    losses = sum(1 for p in settled if p["status"] == "loss")
    pl = sum(units_of(p, "pl") for p in settled)
    return wins, losses, pl, len(settled)


# ---------------------------------------------------------------- X (OAuth 1.0a)

def x_creds() -> dict[str, str] | None:
    values = {name: os.environ.get(name, "").strip() for name in X_ENV}
    if all(values.values()):
        return values
    return None


def _pct(value) -> str:
    return urllib.parse.quote(str(value), safe="~-._")


def _oauth1_header(method: str, url: str, params: dict, creds: dict[str, str]) -> str:
    """Raw HMAC-SHA1 OAuth 1.0a Authorization header (stdlib only).

    `params` = query/form params that participate in the signature base
    string (empty for JSON and multipart bodies).
    """
    oauth = {
        "oauth_consumer_key": creds["X_API_KEY"],
        "oauth_nonce": _secrets.token_hex(16),
        "oauth_signature_method": "HMAC-SHA1",
        "oauth_timestamp": str(int(time.time())),
        "oauth_token": creds["X_ACCESS_TOKEN"],
        "oauth_version": "1.0",
    }
    base_url, _, query = url.partition("?")
    all_params = dict(urllib.parse.parse_qsl(query))
    all_params.update(params)
    all_params.update(oauth)
    pairs = sorted((_pct(k), _pct(v)) for k, v in all_params.items())
    param_str = "&".join(f"{k}={v}" for k, v in pairs)
    base = "&".join((method.upper(), _pct(base_url), _pct(param_str)))
    key = f'{_pct(creds["X_API_SECRET"])}&{_pct(creds["X_ACCESS_SECRET"])}'
    digest = hmac.new(key.encode(), base.encode(), hashlib.sha1).digest()
    oauth["oauth_signature"] = base64.b64encode(digest).decode()
    return "OAuth " + ", ".join(f'{_pct(k)}="{_pct(v)}"' for k, v in sorted(oauth.items()))


def _x_requests_session(creds: dict[str, str]):
    """Prefer requests-oauthlib when installed; fall back to manual signing."""
    try:
        from requests_oauthlib import OAuth1  # type: ignore

        return OAuth1(
            creds["X_API_KEY"], creds["X_API_SECRET"],
            creds["X_ACCESS_TOKEN"], creds["X_ACCESS_SECRET"],
        )
    except ImportError:
        return None


def post_to_x(text: str, image: Path, dry_run: bool) -> bool:
    creds = x_creds()
    if dry_run:
        status = "creds present" if creds else "creds ABSENT"
        log(f"  [dry] X (@MorelloSims, {status}): would upload {image.name} and tweet:\n"
            + "\n".join(f"        {line}" for line in text.splitlines()))
        return True
    if not creds:
        log("  X creds not configured, skipping X post.")
        return False

    import requests

    auth = _x_requests_session(creds)
    try:
        # 1. media upload (v1.1 simple upload, multipart — no body params signed)
        with image.open("rb") as fh:
            files = {"media": (image.name, fh, "image/png")}
            if auth is not None:
                r = requests.post(X_MEDIA_URL, files=files, auth=auth, timeout=60)
            else:
                headers = {"Authorization": _oauth1_header("POST", X_MEDIA_URL, {}, creds)}
                r = requests.post(X_MEDIA_URL, files=files, headers=headers, timeout=60)
        r.raise_for_status()
        media_id = str(r.json()["media_id"])

        # 2. tweet (v2, JSON body — only oauth params signed)
        payload = {"text": text, "media": {"media_ids": [media_id]}}
        if auth is not None:
            r = requests.post(X_TWEET_URL, json=payload, auth=auth, timeout=30)
        else:
            headers = {
                "Authorization": _oauth1_header("POST", X_TWEET_URL, {}, creds),
                "Content-Type": "application/json",
            }
            r = requests.post(X_TWEET_URL, json=payload, headers=headers, timeout=30)
        r.raise_for_status()
        tweet_id = r.json().get("data", {}).get("id", "?")
        log(f"  posted to X: tweet {tweet_id}")
        return True
    except Exception as exc:  # never fail the whole run over X
        log(f"  WARN X post failed: {exc}")
        return False


# ---------------------------------------------------------------- Telegram

def post_to_telegram(caption: str, image: Path, dry_run: bool) -> bool:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.environ.get("TELEGRAM_PUBLIC_CHANNEL_ID", "").strip()
    if dry_run:
        status = "creds present" if (token and chat_id) else "creds ABSENT"
        log(f"  [dry] Telegram public channel ({status}): would send {image.name} with caption:\n"
            + "\n".join(f"        {line}" for line in caption.splitlines()))
        return True
    if not token or not chat_id:
        log("  Telegram public channel creds not configured "
            "(TELEGRAM_BOT_TOKEN / TELEGRAM_PUBLIC_CHANNEL_ID), skipping.")
        return False
    try:
        tg_send_photo(token, chat_id, image, caption)
        log(f"  posted {image.name} to Telegram public channel")
        return True
    except Exception as exc:
        log(f"  WARN Telegram post failed: {exc}")
        return False


# ---------------------------------------------------------------- picks mode

def mode_picks(date: str, dry_run: bool) -> int:
    mlb = load_json(PICKS_MLB, [])
    nba = load_json(PICKS_NBA, [])
    mlb_today = [p for p in mlb if p.get("sport") == "mlb" and p.get("date") == date and conf_of(p) >= 8]
    nba_today = [p for p in nba if p.get("sport") == "nba" and p.get("date") == date and conf_of(p) >= 8]
    if not mlb_today and not nba_today:
        log(f"No published picks for {date}; nothing to post. Exiting clean.")
        return 0

    # Render the MLB card by reusing the existing renderer (subprocess keeps
    # its argparse interface as the single entry point).
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    card = OUT_DIR / f"mlb-social-card-{date}.png"
    if mlb_today:
        cmd = [sys.executable, str(SCRIPTS / "render_mlb_social_card.py"),
               "--kind", "picks", "--out", str(card)]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            log(f"Card render failed:\n{result.stderr.strip()}")
            return 1
        log(f"  rendered {card}")
    else:
        log("  no MLB picks today — skipping card render (NBA-only tease)")
        card = None

    # Caption: tease the top pick only. The full card details stay on-site.
    era = load_era()
    header = str(era.get("label") or era_short(era)) if era else "MLB SIM"
    lines = [f"{header} · {pretty_date(date)}"]
    if mlb_today:
        top = max(mlb_today, key=conf_of)
        n = len(mlb_today)
        lines.append(f"{n} pick{'s' if n != 1 else ''} live · C{conf_of(top)}: {top.get('pick_text', '')}")
    if nba_today:
        n = len(nba_today)
        lines.append(f"+ {n} NBA play{'s' if n != 1 else ''} on the board")
    if era:
        wins, losses, _pl, settled_n = era_record(mlb, era)
        if settled_n:
            lines.append(f"{era_short(era)} record {wins}-{losses} since the break")
        else:
            lines.append(f"{era_short(era)} record 0-0 — fresh slate, every pick tracked")
    else:
        record, _pl = season_record(mlb)
        lines.append(f"Season {record} · every pick tracked in public")
    lines.append(f"Full card → {SITE}")
    caption = truncate_caption("\n".join(lines))

    log(f"Picks post for {date} ({len(mlb_today)} MLB / {len(nba_today)} NBA):")
    if card is not None:
        post_to_telegram(caption, card, dry_run)
        post_to_x(caption, card, dry_run)
    else:
        log("  no card to attach — skipping social post (text-only posts not enabled)")
    return 0


# ---------------------------------------------------------------- recap mode

TEAM_ACCENTS = render_pnl_card.ACCENTS


def recap_rows(picks: list[dict]) -> list[render_pnl_card.ResultRow]:
    rows = []
    for i, p in enumerate(sorted(picks, key=lambda p: (-conf_of(p), p.get("id", "")))):
        side = str(p.get("side") or "")
        home = str(p.get("home") or "")
        away = str(p.get("away") or "")
        opponent = f"vs {away}" if side == home else f"at {home}"
        won = {"win": True, "loss": False}.get(p.get("status"))
        pl = units_of(p, "pl")
        rows.append(render_pnl_card.ResultRow(
            team=side,
            pick=str(p.get("pick_text") or f"{side} ML"),
            opponent=opponent,
            line=str(p.get("odds") or "n/a"),
            final=str(p.get("result") or "-"),
            pnl_label=fmt_units(pl) if won is not None else "push",
            won=won,
            color=TEAM_ACCENTS[i % len(TEAM_ACCENTS)],
        ))
    return rows


def mode_recap(date: str, dry_run: bool) -> int:
    mlb = load_json(PICKS_MLB, [])
    settled = [
        p for p in mlb
        if p.get("sport") == "mlb" and p.get("date") == date and conf_of(p) >= 8
        and p.get("status") in ("win", "loss", "push")
    ]
    if not settled:
        log(f"No settled picks for {date}; nothing to recap. Exiting clean.")
        return 0

    wins = sum(1 for p in settled if p["status"] == "win")
    losses = sum(1 for p in settled if p["status"] == "loss")
    day_pl = sum(units_of(p, "pl") for p in settled)
    day_record = f"{wins}-{losses}"
    perfect = losses == 0 and wins > 0

    era = load_era()
    # Prefix the day line with the era tag only when the recapped day actually
    # belongs to the era (a pre-era recap stays plain "Yesterday").
    day_in_era = bool(era) and all(in_era(p, era) for p in settled)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    card = OUT_DIR / f"mlb-pnl-card-{date}.png"
    date_label = datetime.strptime(date, "%Y-%m-%d").strftime("%b %d, %Y").upper()
    render_pnl_card.render(
        card,
        date_label=date_label,
        rows=recap_rows(settled),
        record=day_record,
        headline="PERFECT CARD" if perfect else "SETTLED IN PUBLIC",
        subline="MLB SWEEP" if perfect else "MLB RESULTS",
        net_label=fmt_units(day_pl),
        footer_center=f"{len(settled)} PICKS / {wins} WINS / {fmt_units(day_pl)}",
        kicker=f"{era.get('label') or era_short(era)} RESULTS" if day_in_era else "MLB SIM RESULTS",
        site_label=f"{SITE}/mlbsim",
    )
    log(f"  rendered {card}")

    day_prefix = f"{era_short(era)} yesterday" if day_in_era else "Yesterday"
    lines = [
        f"{day_prefix}: {day_record}, {fmt_units(day_pl)}"
        + (" — clean sweep" if perfect else ""),
    ]
    if era:
        e_wins, e_losses, e_pl, e_n = era_record(mlb, era)
        if e_n:
            lines.append(f"{era_short(era)} since the break: {e_wins}-{e_losses} ({fmt_units(e_pl)})"
                         " · wins AND losses, all settled in public")
        else:
            lines.append(f"{era_short(era)} record 0-0 — fresh slate, every pick tracked")
    else:
        season, season_pl = season_record(mlb)
        lines.append(f"Season {season} ({fmt_units(season_pl)}) · wins AND losses, all settled in public")
    lines.append(f"Full ledger → {SITE}")
    caption = truncate_caption("\n".join(lines))

    log(f"Recap post for {date} ({day_record}, {fmt_units(day_pl)}):")
    post_to_telegram(caption, card, dry_run)
    post_to_x(caption, card, dry_run)
    return 0


# ---------------------------------------------------------------- main

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--mode", choices=["picks", "recap"], required=True)
    parser.add_argument("--date", default=None,
                        help="Target date YYYY-MM-DD. Default: today ET for picks, yesterday ET for recap.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Render cards and print would-be posts; no network sends.")
    args = parser.parse_args()

    if args.date:
        date = args.date
    elif args.mode == "picks":
        date = today_et()
    else:
        date = (datetime.now(ET) - timedelta(days=1)).strftime("%Y-%m-%d")

    if args.dry_run:
        log("(dry run — nothing will be posted)")
    if args.mode == "picks":
        return mode_picks(date, args.dry_run)
    return mode_recap(date, args.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())
