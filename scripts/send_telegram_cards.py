#!/usr/bin/env python3
"""Send generated social cards to Telegram when secrets are configured."""
from __future__ import annotations

import argparse
import os
from pathlib import Path

import requests


def send_photo(token: str, chat_id: str, photo: Path, caption: str) -> None:
    url = f"https://api.telegram.org/bot{token}/sendPhoto"
    with photo.open("rb") as fh:
        response = requests.post(
            url,
            data={"chat_id": chat_id, "caption": caption},
            files={"photo": (photo.name, fh, "image/png")},
            timeout=30,
        )
    response.raise_for_status()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cards", nargs="+", required=True)
    parser.add_argument("--caption", default="Morello Sims card")
    parser.add_argument("--require", action="store_true", help="Fail if Telegram env vars are missing.")
    args = parser.parse_args()

    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat_id:
        message = "Telegram secrets missing, skipping card send."
        if args.require:
            raise SystemExit(message)
        print(message)
        return

    cards = [Path(card) for card in args.cards]
    for card in cards:
        if not card.exists():
            raise SystemExit(f"Missing card: {card}")
    for index, card in enumerate(cards, start=1):
        caption = args.caption if index == 1 else ""
        try:
            send_photo(token, chat_id, card, caption)
        except Exception as exc:
            message = f"Telegram send failed for {card}: {exc}"
            if args.require:
                raise SystemExit(message) from exc
            print(message)
            continue
        print(f"Sent {card} to Telegram")


if __name__ == "__main__":
    main()
