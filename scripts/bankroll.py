#!/usr/bin/env python3
"""Real-money bankroll ledger for the pick pilot.

One ledger file (bankroll/ledger.json) holds deposits, per-pick stakes, and
settled P&L synced from the pick contracts. Staking follows the pilot rules
and the kill switch halts staking on drawdown until manually cleared.

Pilot rules (2026-07-06):
  - stake per pick: PILOT_STAKE flat while in pilot mode, else 1% of roll
    scaled by tier (C10 1.0x, C9 0.75x, C8 0.5x)
  - hard cap: no stake above MAX_STAKE_PCT of current roll
  - kill switch: total drawdown from peak >= KILL_DRAWDOWN halts staking;
    clearing requires deleting the "halted" flag by hand, on purpose
  - no manual overrides of model picks; the ledger only stakes picks that
    exist in picks/{mlb,nba}.json at C8+

Usage:
  python3 scripts/bankroll.py init --deposit 2500        # open the pilot
  python3 scripts/bankroll.py stake                      # stake today's picks
  python3 scripts/bankroll.py settle                     # sync settled P&L
  python3 scripts/bankroll.py report                     # weekly report text
  python3 scripts/bankroll.py status                     # one-line health
"""

import argparse
import json
import os
from datetime import datetime, timedelta, timezone

REPO = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
LEDGER = os.path.join(REPO, "bankroll", "ledger.json")
PICK_FILES = [os.path.join(REPO, "picks", "mlb.json"), os.path.join(REPO, "picks", "nba.json")]

PILOT_MODE = True
PILOT_STAKE = 25.0          # flat $ per pick during pilot
MAX_STAKE_PCT = 0.015       # never above 1.5% of current roll
KILL_DRAWDOWN = 0.20        # halt at -20% from peak
TIER_SCALE = {10: 1.0, 9: 0.75, 8: 0.5}
MIN_CONF = 8

ET = timezone(timedelta(hours=-4))


def now_iso():
    return datetime.now(ET).strftime("%Y-%m-%dT%H:%M:%S%z")


def load_ledger():
    if not os.path.exists(LEDGER):
        return None
    with open(LEDGER) as f:
        return json.load(f)


def save_ledger(led):
    os.makedirs(os.path.dirname(LEDGER), exist_ok=True)
    with open(LEDGER, "w") as f:
        json.dump(led, f, indent=2)


def load_picks():
    picks = []
    for pf in PICK_FILES:
        if os.path.exists(pf):
            with open(pf) as f:
                picks.extend(json.load(f))
    return picks


def roll(led):
    dep = sum(d["amount"] for d in led["deposits"])
    pl = sum(s.get("pl") or 0 for s in led["stakes"])
    return dep + pl


def peak_roll(led):
    """Highest roll over the settled history, chronological by settle order."""
    dep = sum(d["amount"] for d in led["deposits"])
    peak = cur = dep
    for s in sorted((s for s in led["stakes"] if s.get("settled_at")),
                    key=lambda s: s["settled_at"]):
        cur += s.get("pl") or 0
        peak = max(peak, cur)
    return peak


def check_kill(led):
    p = peak_roll(led)
    r = roll(led)
    dd = (p - r) / p if p > 0 else 0.0
    if dd >= KILL_DRAWDOWN and not led.get("halted"):
        led["halted"] = {"at": now_iso(), "drawdown": round(dd, 4), "roll": round(r, 2)}
        print(f"  KILL SWITCH: drawdown {dd*100:.1f}% from peak — staking halted.")
        print("  Review the model before clearing 'halted' from the ledger by hand.")
    return dd


def stake_amount(led, conf):
    r = roll(led)
    if PILOT_MODE:
        amt = PILOT_STAKE
    else:
        amt = r * 0.01 * TIER_SCALE.get(int(conf), 0.5)
    return round(min(amt, r * MAX_STAKE_PCT), 2)


def cmd_init(deposit):
    led = load_ledger()
    if led is None:
        led = {"created": now_iso(), "venue": "kalshi", "deposits": [], "stakes": [], "halted": None}
    led["deposits"].append({"at": now_iso(), "amount": float(deposit)})
    save_ledger(led)
    print(f"  deposit ${deposit:,.2f} recorded — roll ${roll(led):,.2f}")


def cmd_stake():
    led = load_ledger()
    if led is None:
        raise SystemExit("no ledger — run: bankroll.py init --deposit <amt>")
    if led.get("halted"):
        raise SystemExit(f"staking halted since {led['halted']['at']} — clear by hand after review")
    today = datetime.now(ET).strftime("%Y-%m-%d")
    have = {s["pick_id"] for s in led["stakes"]}
    added = 0
    for p in load_picks():
        if p["date"] != today or p["status"] != "pending":
            continue
        if int(p.get("conf") or 0) < MIN_CONF or p["id"] in have:
            continue
        amt = stake_amount(led, p.get("conf"))
        led["stakes"].append({
            "pick_id": p["id"], "sport": p["sport"], "date": p["date"],
            "pick_text": p.get("pick_text"), "conf": p.get("conf"),
            "odds": p.get("odds"), "amount": amt,
            "placed_at": now_iso(), "pl": None, "settled_at": None,
        })
        added += 1
        print(f"  STAKE ${amt:.2f} on {p['sport'].upper()} {p.get('pick_text')} (C{p.get('conf')}, {p.get('odds')})")
    save_ledger(led)
    if not added:
        print("  nothing new to stake")


def cmd_settle():
    led = load_ledger()
    if led is None:
        raise SystemExit("no ledger")
    by_id = {p["id"]: p for p in load_picks()}
    n = 0
    for s in led["stakes"]:
        if s.get("settled_at"):
            continue
        p = by_id.get(s["pick_id"])
        if not p or p["status"] == "pending":
            continue
        if p["status"] == "push":
            s["pl"] = 0.0
        else:
            try:
                ml = int(str(p.get("odds") or -110).replace("+", ""))
            except ValueError:
                ml = -110
            if p["status"] == "win":
                s["pl"] = round(s["amount"] * (ml / 100 if ml > 0 else 100 / abs(ml)), 2)
            else:
                s["pl"] = -s["amount"]
        s["settled_at"] = p.get("settled_at") or now_iso()
        n += 1
        print(f"  {s['pick_text']}: {p['status'].upper()} {s['pl']:+.2f}")
    dd = check_kill(led)
    save_ledger(led)
    print(f"  settled {n} — roll ${roll(led):,.2f} (drawdown {dd*100:.1f}% from peak)")


def cmd_report(days=7):
    led = load_ledger()
    if led is None:
        raise SystemExit("no ledger")
    cutoff = (datetime.now(ET) - timedelta(days=days)).strftime("%Y-%m-%d")
    recent = [s for s in led["stakes"] if s["date"] >= cutoff]
    settled = [s for s in recent if s.get("settled_at")]
    w = sum(1 for s in settled if (s.get("pl") or 0) > 0)
    l = sum(1 for s in settled if (s.get("pl") or 0) < 0)
    staked = sum(s["amount"] for s in settled)
    pl = sum(s.get("pl") or 0 for s in settled)
    dep = sum(d["amount"] for d in led["deposits"])
    lines = [
        f"BANKROLL WEEK — since {cutoff}",
        f"  roll: ${roll(led):,.2f} (deposited ${dep:,.2f}, all-time P&L {roll(led)-dep:+,.2f})",
        f"  week: {w}-{l} on ${staked:,.2f} staked, P&L {pl:+,.2f}" + (f" (ROI {pl/staked*100:+.1f}%)" if staked else ""),
        f"  pending: {sum(1 for s in recent if not s.get('settled_at'))} open stakes",
        f"  status: {'HALTED — review required' if led.get('halted') else 'active'}",
    ]
    text = "\n".join(lines)
    print(text)
    return text


def cmd_status():
    led = load_ledger()
    if led is None:
        print("no ledger")
        return
    open_n = sum(1 for s in led["stakes"] if not s.get("settled_at"))
    print(f"roll ${roll(led):,.2f} | {len(led['stakes'])} stakes ({open_n} open) | "
          f"{'HALTED' if led.get('halted') else 'active'}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["init", "stake", "settle", "report", "status"])
    ap.add_argument("--deposit", type=float)
    ap.add_argument("--days", type=int, default=7)
    a = ap.parse_args()
    if a.cmd == "init":
        if not a.deposit:
            raise SystemExit("--deposit required")
        cmd_init(a.deposit)
    elif a.cmd == "stake":
        cmd_stake()
    elif a.cmd == "settle":
        cmd_settle()
    elif a.cmd == "report":
        cmd_report(a.days)
    else:
        cmd_status()


if __name__ == "__main__":
    main()
