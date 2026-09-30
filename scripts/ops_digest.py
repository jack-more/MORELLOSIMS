#!/usr/bin/env python3
"""Owner check-ins + watchdog, so the system runs itself.

  python3 scripts/ops_digest.py digest    # morning / pre-game check-in DM
  python3 scripts/ops_digest.py watchdog  # re-run pipelines GitHub skipped
  python3 scripts/ops_digest.py failure --workflow NAME --url URL

Watchdog: GitHub drops scheduled runs under load (2026-09-29: three NBA
runs never fired). On a game day, if a pipeline has no successful run in
its window, dispatch it and tell the owner once.

Needs GITHUB_TOKEN + GITHUB_REPOSITORY for run history/dispatch (provided in
Actions); TELEGRAM_* for the DM. Missing → prints instead of sending.
"""

import argparse
import json
import os
import sys
import urllib.request
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ops_tg  # noqa: E402

REPO = os.path.dirname(HERE)
ET = timezone(timedelta(hours=-4))
GH = os.environ.get("GITHUB_TOKEN", "").strip()
GH_REPO = os.environ.get("GITHUB_REPOSITORY", "jack-more/MORELLOSIMS")
WATCH_STATE = os.path.join(REPO, "telegram", "watchdog.json")

# workflow file, label, max hours without a success on a game day, dispatch inputs
PIPELINES = [
    ("mlb-pipeline.yml", "MLB", 4, {"run_type": "picks"}),
    ("nba-pipeline.yml", "NBA", 8, {}),
]


def load(path, default):
    try:
        with open(path) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def gh(path, method="GET", body=None):
    if not GH:
        return None
    req = urllib.request.Request(f"https://api.github.com/repos/{GH_REPO}/{path}", method=method,
                                 data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Authorization": f"Bearer {GH}", "Accept": "application/vnd.github+json"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            raw = r.read()
            return json.loads(raw) if raw else {}
    except Exception as e:
        print(f"  WARN github {path}: {e}")
        return None


def get_json(url):
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "morellosims-ops"}), timeout=15) as r:
            return json.loads(r.read())
    except Exception:
        return None


def games_today():
    d = datetime.now(ET).strftime("%Y-%m-%d")
    mlb = get_json(f"https://statsapi.mlb.com/api/v1/schedule?sportId=1&date={d}") or {}
    n_mlb = sum(len(x.get("games", [])) for x in mlb.get("dates", []))
    nba = get_json(f"https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates={d.replace('-', '')}") or {}
    n_nba = sum(1 for e in nba.get("events", []) if (e.get("season") or {}).get("type") in (2, 3, 5))
    return {"MLB": n_mlb, "NBA": n_nba}


def last_runs(wf):
    r = gh(f"actions/workflows/{wf}/runs?per_page=15") or {}
    return r.get("workflow_runs", [])


def ago(ts):
    t = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    h = (datetime.now(timezone.utc) - t).total_seconds() / 3600
    return f"{h:.0f}h ago" if h >= 1 else f"{h * 60:.0f}m ago"


def odds_str(p):
    o = str(p.get("odds") or "")
    return o if not o or o.startswith(("+", "-")) else f"+{o}"


def picks_block(today):
    lines = []
    for sport, path in (("MLB", "picks/mlb.json"), ("NBA", "picks/nba.json")):
        todays = [p for p in load(os.path.join(REPO, path), []) if p.get("date") == today
                  and int(p.get("conf") or 0) >= 8]
        if todays:
            lines.append(f"{sport} · {len(todays)} pick{'s' if len(todays) != 1 else ''}")
            for p in sorted(todays, key=lambda p: -int(p.get("conf") or 0)):
                lines.append(f"  C{p.get('conf')} {p['pick_text']} {odds_str(p)} · {p.get('matchup')} "
                             f"{p.get('game_time') or ''} [{p.get('status')}]")
    return lines


def results_block(day):
    lines = []
    for sport, path in (("MLB", "picks/mlb.json"), ("NBA", "picks/nba.json")):
        done = [p for p in load(os.path.join(REPO, path), []) if p.get("date") == day
                and p.get("status") in ("win", "loss", "push")]
        if done:
            w = sum(p["status"] == "win" for p in done)
            l = sum(p["status"] == "loss" for p in done)
            pl = sum(p.get("pl") or 0 for p in done)
            lines.append(f"{sport} yesterday {w}-{l} ({pl:+.0f} $PP)")
    return lines


def alerts_block():
    out = []
    if not all(os.environ.get(k) for k in ("X_API_KEY", "X_API_SECRET", "X_ACCESS_TOKEN", "X_ACCESS_SECRET")):
        out.append("X secrets not set — nothing is posting to X (repo Settings → Secrets → Actions)")
    try:
        from mlb_model_gates import WP_CALIBRATION_STATUS, load_wp_calibration
        load_wp_calibration()
        if WP_CALIBRATION_STATUS["state"] != "fresh":
            out.append(f"MLB win-prob curve {WP_CALIBRATION_STATUS['state']} "
                       f"({WP_CALIBRATION_STATUS.get('age_days') or '?'}d) — refit is due")
    except Exception:
        pass
    return out


def digest(label):
    now = datetime.now(ET)
    today = now.strftime("%Y-%m-%d")
    g = games_today()
    lines = [f"☀️ {label} · {now.strftime('%a %b %-d, %-I:%M %p ET')}",
             f"Slate: {g['MLB']} MLB · {g['NBA']} NBA games"]
    lines += results_block((now - timedelta(days=1)).strftime("%Y-%m-%d"))
    pb = picks_block(today)
    lines += ["", *pb] if pb else ["", "No C8+ picks published yet today."]
    lines.append("")
    for wf, name, _, _ in PIPELINES + [("social-daily.yml", "Social", 0, {}), ("tg-channel-bot.yml", "Bot", 0, {})]:
        runs = last_runs(wf)
        if runs:
            r = runs[0]
            mark = {"success": "✅", "failure": "❌", None: "⏳"}.get(r.get("conclusion"), "⚠️")
            lines.append(f"{mark} {name}: {r.get('conclusion') or r.get('status')} {ago(r['created_at'])}")
    al = alerts_block()
    if al:
        lines += ["", "Needs you:"] + [f"• {a}" for a in al]
    else:
        lines += ["", "Nothing needs you."]
    ops_tg.send("\n".join(lines), [[("🔄 Refresh", "status"), ("📋 Today's picks", "picks")]])


def watchdog():
    g = games_today()
    st = load(WATCH_STATE, {})
    now = datetime.now(timezone.utc)
    hour_et = datetime.now(ET).hour
    for wf, sport, max_h, inputs in PIPELINES:
        if not g.get(sport) or not (9 <= hour_et <= 22):
            continue
        runs = last_runs(wf)
        if not runs:
            continue
        if any(r.get("status") in ("queued", "in_progress") for r in runs):
            continue
        ok = [r for r in runs if r.get("conclusion") == "success"]
        age_h = ((now - datetime.fromisoformat(ok[0]["created_at"].replace("Z", "+00:00"))).total_seconds() / 3600
                 if ok else 99)
        if age_h <= max_h:
            continue
        key = f"{wf}:{now.strftime('%Y-%m-%dT%H')}"
        if st.get(wf) and (now - datetime.fromisoformat(st[wf])).total_seconds() < 2 * 3600:
            continue  # dispatched recently; give it time
        res = gh(f"actions/workflows/{wf}/dispatches", "POST", {"ref": "main", "inputs": inputs})
        st[wf] = now.isoformat()
        ops_tg.send(f"🐕 Watchdog: {sport} pipeline had no successful run in {age_h:.0f}h on a game day "
                    f"— {'re-ran it' if res is not None else 'could not re-run it (token?)'}.")
        print(f"  dispatched {wf} ({key})")
    os.makedirs(os.path.dirname(WATCH_STATE), exist_ok=True)
    with open(WATCH_STATE, "w") as f:
        json.dump(st, f, indent=2)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["digest", "watchdog", "failure"])
    ap.add_argument("--label", default="")
    ap.add_argument("--workflow", default="")
    ap.add_argument("--url", default="")
    a = ap.parse_args()
    if a.cmd == "digest":
        h = datetime.now(ET).hour
        digest(a.label or ("Morning check-in" if h < 14 else "Pre-game check-in"))
    elif a.cmd == "watchdog":
        watchdog()
    else:
        ops_tg.send(f"❌ {a.workflow} failed.\n{a.url}")
