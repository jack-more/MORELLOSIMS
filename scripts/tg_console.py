#!/usr/bin/env python3
"""The owner talks to the model over Telegram: commands in Jack's DM, run by tg_channel_bot.

  /card               tonight's card: every logged pick with the latest sim and book, and what's sent
  /game ATL           one game: the sim's line, the book, the edge, the model's side, tip
  /pick ATL -1.5 2u   log an owner pick (units to win at -110) and send it to members
  /stake ATL 0.5u     change a pick's stake before tip (members get one stake-change email)
  /pull ATL           take a pick off before tip (off the members page, members told; it won't count)
  /resim              re-run the model now (the NBA pipeline); new numbers in about 6 minutes

move_alerts() DMs the owner when a sent pick's edge drops 2+ points from where it stood
(the logged sim, or the first number seen for an owner pick), so a late scratch
(Knueppel, Oct 24) reaches the owner before tip.

Teams can be given as NBA or ESPN codes, city or nickname (ATL, hawks, atlanta).
Ledger changes go through the same files and checks as the pipeline
(utils.ledger, sync_to_picks_json, check_ledger, check_seal_guardrail) and are
committed here; commit messages never name a side.
"""

import json
import os
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
NBA = os.path.join(REPO, "nba_pipeline")
for p in (HERE, NBA, os.path.join(NBA, "scripts")):
    if p not in sys.path:
        sys.path.insert(0, p)

import picks_store  # noqa: E402

ET = timezone(timedelta(hours=-4))
DAILY = os.path.join(NBA, "data", "daily_picks.json")
PICKS_CSV = os.path.join(NBA, "data", "picks.csv")
PICK_LOG = os.path.join(NBA, "data", "pick_log.json")
MOVES = os.path.join(REPO, "ops", "state", "move_alerts.json")
TEAMS_JSON = os.path.join(REPO, "data", "reference", "nba_teams_espn_2026.json")
ESPN_TO_NBA = {"GS": "GSW", "NO": "NOP", "NY": "NYK", "SA": "SAS", "UTAH": "UTA", "WSH": "WAS"}
UNIT = 25           # $PP per unit
JUICE = 1.1         # -110: to win 1u risks 1.1u
MOVE_PTS = 2.0      # edge drop that earns a DM

HELP = (
    "Talk to the model\n"
    "/card: tonight's picks with the latest numbers\n"
    "/game ATL: one game, sim vs book\n"
    "/pick ATL -1.5 2u: log your pick (units to win) and send it to members\n"
    "/stake ATL 0.5u: change a pick's stake before tip\n"
    "/pull ATL: take a pick off before tip\n"
    "/resim: re-run the model now (about 6 minutes)\n"
    "/status · /picks: the check-in and today's list"
)


# ── small helpers ─────────────────────────────────────────────────────────

def today():
    return datetime.now(ET).strftime("%Y-%m-%d")


def _num(v):
    return f"{v:+.1f}".replace("+0.0", "PK").replace("-0.0", "PK")


def _units_txt(u):
    return {0.25: "¼u", 0.5: "½u"}.get(u, f"{u:g}u")


def aliases():
    """'hawks' / 'atlanta' / 'atl' / 'gs' -> NBA code."""
    out = {}
    teams = json.load(open(TEAMS_JSON))["teams"]
    for espn, t in teams.items():
        nba = ESPN_TO_NBA.get(espn, espn)
        for k in (espn, nba, t.get("name"), t.get("location"), f"{t.get('location')} {t.get('name')}"):
            if k:
                out[str(k).lower()] = nba
    out.update({"sixers": "PHI", "76ers": "PHI", "blazers": "POR", "wolves": "MIN", "cavs": "CLE", "mavs": "DAL"})
    return out


def team_code(word):
    return aliases().get((word or "").strip().lower())


def parse_units(word):
    w = (word or "").strip().lower().replace("units", "").replace("unit", "").rstrip("u").strip()
    w = {"½": "0.5", "¼": "0.25", "max": "4"}.get(w, w)
    try:
        u = float(w)
    except ValueError:
        return None
    return u if 0 < u <= 10 else None


def to_win_risk(units, odds=-110):
    """$PP risked to win `units` at American odds (-110 for spreads)."""
    return round(units * UNIT * (abs(odds) / 100 if odds < 0 else 1), 4)


# ── the model's latest numbers ────────────────────────────────────────────

def snapshot():
    """Games from the latest pipeline run (nba_pipeline/data/daily_picks.json), opened with the seal key."""
    from utils.ledger import open_entries
    d = json.load(open(DAILY)) if os.path.exists(DAILY) else {}
    games = open_entries(d.get("games") or [])
    return d, [g for g in games if isinstance(g, dict) and g.get("matchup")]


def find_game(code, games):
    return next((g for g in games if code in (g.get("away"), g.get("home"))), None)


def side_numbers(g, side):
    """(sim line, book line) for `side` in game g; lines are the side's (minus = favoured)."""
    home = side == g.get("home")
    sim = g.get("sim_spread")
    book = g.get("book_spread")
    sim = None if sim is None else (float(sim) if home else -float(sim))
    book = None if book is None else (float(book) if home else -float(book))
    return sim, book


def _sim_txt(g, side, sim):
    """'CHA by 1.5' / 'MIA by 3.5' / 'pick'em' from the side's sim line."""
    if not sim:
        return "pick'em"
    other = g["home"] if side == g["away"] else g["away"]
    return f"{side} by {abs(sim):.1f}" if sim < 0 else f"{other} by {sim:.1f}"


def _ago(iso):
    try:
        t = datetime.fromisoformat(str(iso).replace("Z", "+00:00")).astimezone(ET)
        return t.strftime("%-I:%M %p ET")
    except ValueError:
        return "?"


def _sent(st, p):
    import pick_alerts
    return pick_alerts.released(st, p)


def _stake(p):
    import member_delivery
    return member_delivery._stake_txt(p)


def card():
    import pick_alerts
    d, games = snapshot()
    st = pick_alerts.load(pick_alerts.STATE, {})
    picks = [p for p in picks_store.load_picks(os.path.join(REPO, "picks", "nba.json")) if p.get("date") == today()]
    if not picks:
        return "No NBA picks logged today yet."
    rows = {"sent": [], "model": [], "done": []}
    for p in picks:
        g = find_game(p.get("side"), games) if p.get("side") else None
        line = p.get("line")
        tip = picks_store.start_label(p) or ""
        txt = f"{p.get('pick_text')} · {_stake(p)}"
        if g and line is not None:
            sim, book = side_numbers(g, p["side"])
            if sim is not None:
                edge = float(line) - sim
                txt += f" · sim {_sim_txt(g, p['side'], sim)} · edge {edge:+.1f}"
            if book is not None and abs(book - float(line)) >= 0.5:
                txt += f" · book now {p['side']} {_num(book)}"
        txt += f" · {tip}" if tip else ""
        key = "done" if p.get("status") != "pending" else ("sent" if _sent(st, p) else "model")
        rows[key].append(("C" + str(p.get("conf")) + " " if key == "model" else "") + txt)
    out = [f"Tonight · {datetime.now(ET).strftime('%a %b %-d')} · numbers from the {_ago(d.get('generated_at'))} run"]
    for key, title in (("sent", "SENT TO MEMBERS"), ("model", "MODEL ONLY (not sent)"), ("done", "SETTLED / VOID")):
        if rows[key]:
            out += ["", title] + [f"• {r}" for r in rows[key]]
    out += ["", "Edge = points between the book and the sim on that side. /game ATL for one game."]
    return "\n".join(out)


def game(code_word):
    code = team_code(code_word)
    if not code:
        return f"Don't know the team '{code_word}'. Try ATL, hawks or atlanta."
    d, games = snapshot()
    g = find_game(code, games)
    if not g:
        return f"{code} isn't on the latest slate ({_ago(d.get('generated_at'))} run)."
    a, h = g["away"], g["home"]
    sim_h, book_h = side_numbers(g, h)
    lines = [f"{a} @ {h} · {_ago(g.get('tip_at'))} · {_ago(d.get('generated_at'))} run"]
    if sim_h is not None:
        fav = h if sim_h < 0 else a
        lines.append(f"Sim: {fav} by {abs(sim_h):.1f}" if sim_h else "Sim: pick'em")
    if book_h is not None:
        lines.append(f"Book: {h} {_num(book_h)} / {a} {_num(-book_h)}")
    if g.get("pick_text"):
        side = g["pick_text"].split()[0]
        sim, book = side_numbers(g, side)
        try:
            import capture_picks
            grade = f"C{capture_picks.conf_to_1_10(float(g.get('confidence') or 50))}"
        except Exception:
            grade = ""
        if sim is not None and book is not None:
            lines.append(f"Model side: {side} {_num(book)} · edge {book - sim:+.1f} {grade}".rstrip())
    mine = [p for p in picks_store.load_picks(os.path.join(REPO, "picks", "nba.json"))
            if p.get("date") == today() and code in (p.get("away"), p.get("home"))]
    import pick_alerts
    st = pick_alerts.load(pick_alerts.STATE, {})
    for p in mine:
        lines.append(f"Logged: {p.get('pick_text')} · {_stake(p)} · {p.get('status')}"
                     + (" · SENT" if _sent(st, p) else ""))
    return "\n".join(lines)


# ── ledger changes ────────────────────────────────────────────────────────

def git(*args, check=False):
    return subprocess.run(["git", *args], cwd=REPO, capture_output=True, text=True, check=check)


def git_sync():
    """Fast-forward to main before reading or changing the ledger (the pipeline commits too)."""
    r = git("pull", "--rebase", "-q", "origin", "main")
    if r.returncode != 0:
        git("rebase", "--abort")
        print(f"  WARN git pull: {r.stderr.strip()[:200]}")


def commit_push(paths, message):
    """Commit `paths` after the seal guardrail; push, rebasing on main if it moved. True when pushed."""
    git("add", *paths)
    if git("diff", "--cached", "--quiet").returncode == 0:
        return True
    guard = subprocess.run([sys.executable, os.path.join(HERE, "check_seal_guardrail.py")], cwd=REPO,
                           capture_output=True, text=True)
    if guard.returncode != 0:
        print(guard.stdout[-800:])
        git("reset", "-q")
        raise RuntimeError("seal guardrail refused the commit")
    git("-c", "user.name=TG Channel Bot", "-c", "user.email=noreply@github.com", "commit", "-q", "-m", message)
    for _ in range(4):
        if git("push", "-q", "origin", "HEAD:main").returncode == 0:
            return True
        r = git("pull", "--rebase", "-q", "origin", "main")
        if r.returncode != 0:
            git("rebase", "--abort")
    print("  WARN push failed after retries")
    return False


LEDGER_FILES = ["nba_pipeline/data/picks.csv", "nba_pipeline/data/pick_log.json", "picks/nba.json", "ops/state"]


def _ledger_check():
    r = subprocess.run([sys.executable, os.path.join(NBA, "scripts", "check_ledger.py")], cwd=NBA,
                       capture_output=True, text=True)
    return r.returncode == 0, (r.stdout + r.stderr).strip().splitlines()[-1:]


def _resync():
    import importlib
    import sync_to_picks_json
    importlib.reload(sync_to_picks_json)
    sync_to_picks_json.main()


def _rows():
    from utils.ledger import read_rows
    return read_rows(PICKS_CSV)


def _today_rows(code):
    return [r for r in _rows() if r["date"] == today() and code in [t.strip() for t in r["matchup"].split("@")]]


def _row_tip_passed(r):
    t = picks_store.parse_ts(r.get("tip_at"))
    return t is not None and datetime.now(timezone.utc) >= t


def _set_risk(row, risk):
    """New stake on a pending row, and on its capture record when it has one."""
    from utils.ledger import open_entries, read_rows, seal_entries, write_rows
    rows = read_rows(PICKS_CSV)
    k = (row["date"], row["matchup"], row["side"])
    hit = [r for r in rows if (r["date"], r["matchup"], r["side"]) == k and not r["result"]]
    if len(hit) != 1:
        raise RuntimeError(f"expected one pending row, found {len(hit)}")
    hit[0]["risk"] = f"{risk:g}"
    write_rows(PICKS_CSV, rows)
    ents = open_entries(json.load(open(PICK_LOG)))
    idx = [i for i, e in enumerate(ents) if isinstance(e, dict) and str(e.get("slate_date", "")).startswith(row["date"])
           and e.get("matchup") == row["matchup"] and e.get("side") == row["side"]]
    if len(idx) == 1:
        ents[idx[0]]["risk"] = risk
        json.dump(seal_entries(ents), open(PICK_LOG, "w"), indent=2)


def _pick_for(row):
    import sync_to_picks_json
    pid = sync_to_picks_json.contract_ids().get((row["date"], row["matchup"], row["side"], row.get("type") or "spread"))
    return next((p for p in picks_store.load_picks(os.path.join(REPO, "picks", "nba.json")) if p["id"] == pid), None)


def _check_or_revert():
    ok, last = _ledger_check()
    if not ok:
        git("checkout", "--", *LEDGER_FILES[:3])
        raise RuntimeError(f"ledger check refused it: {' '.join(last)}")


def _finish(message):
    _check_or_revert()
    if not commit_push(LEDGER_FILES, message):
        raise RuntimeError("saved here but the push failed; it goes out on the next cycle")


def pick(team_word, line_word, units_word):
    import pick_alerts
    code = team_code(team_word)
    units = parse_units(units_word)
    try:
        line = float(str(line_word).replace("pk", "0").replace("PK", "0"))
    except ValueError:
        line = None
    if not code or line is None or units is None:
        return "Format: /pick ATL -1.5 2u (team, spread, units to win)."
    git_sync()
    _, games = snapshot()
    g = find_game(code, games)
    matchup = g["matchup"] if g else None
    if not matchup:
        rows = _today_rows(code)
        matchup = rows[0]["matchup"] if rows else None
    if not matchup:
        return f"{code} isn't on tonight's slate."
    side = f"{code} {line:+.1f}"
    risk = to_win_risk(units)
    same = [r for r in _today_rows(code) if r["side"] == side and not r["result"]]
    if same and _row_tip_passed(same[0]):
        return f"Too late: {matchup} has tipped."
    if same:
        p0 = _pick_for(same[0])
        st0 = pick_alerts.load(pick_alerts.STATE, {})
        if p0 and _sent(st0, p0):
            return stake(code, units_word)       # already with members: a stake change, and they're told
        _set_risk(same[0], risk)
        row = same[0]
    else:
        import inject_pick
        if not inject_pick.inject(matchup, side, risk=risk, date_str=today(), force=True):
            return "The ledger didn't take it (see the bot log)."
        row = next(r for r in reversed(_rows()) if r["date"] == today() and r["matchup"] == matchup and r["side"] == side)
        if row["result"] == "V":
            _finish("TG bot — owner pick logged (after tip: void)")
            return f"Too late: {matchup} had tipped, so it's recorded as void and won't count."
    _resync()
    p = _pick_for(row)
    if p is None:
        git("checkout", "--", *LEDGER_FILES[:3])
        return "It didn't reach picks.json, so nothing was logged; check the bot log."
    _check_or_revert()                       # the Send is recorded only for a pick the ledger took
    note = pick_alerts.decide(p["id"], True)
    _finish("TG bot — owner pick logged and sent")
    return f"{side} · {_units_txt(units)} to win (risk {risk / UNIT:g}u) · logged. {note}"


def stake(team_word, units_word):
    import pick_alerts
    code, units = team_code(team_word), parse_units(units_word)
    if not code or units is None:
        return "Format: /stake ATL 0.5u (team, units to win)."
    git_sync()
    st = pick_alerts.load(pick_alerts.STATE, {})
    rows = [r for r in _today_rows(code) if not r["result"]]
    cands = [(r, _pick_for(r)) for r in rows]
    cands = [c for c in cands if c[1]]
    sent = [c for c in cands if _sent(st, c[1])]
    pickd = (sent or cands)
    if len(pickd) != 1:
        return f"Found {len(pickd)} pending {code} picks; say which with /pick {code} <line> <units>."
    row, p = pickd[0]
    if _row_tip_passed(row):
        return f"Too late: {row['matchup']} has tipped."
    was = _stake(p)
    _set_risk(row, to_win_risk(units))
    if _sent(st, p):
        restakes = pick_alerts.load(pick_alerts.RESTAKE, [])
        ref = picks_store.state_ref(p["id"])
        waiting = next((r for r in restakes if r["ref"] == ref and not r.get("done")), None)
        if waiting:                               # not emailed yet: one email, from the stake members last saw
            waiting["at"] = datetime.now(timezone.utc).isoformat()
        else:
            restakes.append({"ref": ref, "was": was, "why": "Stake changed by the owner.",
                             "at": datetime.now(timezone.utc).isoformat()})
        with open(pick_alerts.RESTAKE, "w") as f:
            json.dump(restakes, f, indent=2)
    _resync()
    _finish("TG bot — owner stake change")
    return f"{p['pick_text']}: {was} → {_units_txt(units)} to win." + (" Members get a stake-change email now." if _sent(st, p) else "")


def pull(team_word):
    import member_delivery
    import pick_alerts
    from utils.ledger import read_rows, write_rows
    code = team_code(team_word)
    if not code:
        return "Format: /pull ATL"
    git_sync()
    st = pick_alerts.load(pick_alerts.STATE, {})
    cands = [(r, _pick_for(r)) for r in _today_rows(code) if not r["result"]]
    cands = [c for c in cands if c[1]]
    sent = [c for c in cands if _sent(st, c[1])]
    pickd = sent or cands
    if len(pickd) != 1:
        return f"Found {len(pickd)} pending {code} picks; nothing pulled."
    row, p = pickd[0]
    if _row_tip_passed(row):
        return f"Too late: {row['matchup']} has tipped; it stands."
    was_sent = _sent(st, p)
    if was_sent and member_delivery.email_enabled():
        try:
            member_delivery.email(p, picks_store.start_label(p),
                                  update="Pulled: this pick is off. It won't be graded or counted.")
        except Exception as e:
            print(f"  WARN pull email: {type(e).__name__}")
    rows = read_rows(PICKS_CSV)
    for r in rows:
        if (r["date"], r["matchup"], r["side"]) == (row["date"], row["matchup"], row["side"]) and not r["result"]:
            r.update(result="V", profit="0", void_reason="PULLED: the owner took it off before tip")
    write_rows(PICKS_CSV, rows)
    _resync()
    _finish("TG bot — owner pulled a pick before tip")
    return f"Pulled {p['pick_text']}. It's void and won't count." + (
        " Members were emailed and it comes off the members page now." if was_sent else "")


def resim():
    env = {**os.environ, "GH_TOKEN": os.environ.get("GITHUB_TOKEN", "")}
    r = subprocess.run(["gh", "workflow", "run", "nba-pipeline.yml", "--ref", "main"], cwd=REPO,
                       capture_output=True, text=True, env=env)
    if r.returncode != 0:
        return f"Couldn't start the model run: {r.stderr.strip()[:160]}"
    return "Model re-run started. New numbers in about 6 minutes; /card then shows them."


# ── the command router ────────────────────────────────────────────────────

def handle(text):
    """Reply for an owner command, or None when `text` isn't one of these."""
    words = (text or "").strip().split()
    if not words:
        return None
    cmd, args = words[0].lower().split("@")[0], words[1:]
    try:
        if cmd in ("/card", "/tonight"):
            return card()
        if cmd == "/game":
            return game(args[0]) if args else "Format: /game ATL"
        if cmd == "/pick":
            return pick(*args[:3]) if len(args) >= 3 else "Format: /pick ATL -1.5 2u"
        if cmd == "/stake":
            return stake(*args[:2]) if len(args) >= 2 else "Format: /stake ATL 0.5u"
        if cmd == "/pull":
            return pull(args[0]) if args else "Format: /pull ATL"
        if cmd == "/resim":
            return resim()
        if cmd in ("/help", "/start", "/commands"):
            return HELP
    except Exception as e:
        return f"That didn't go through: {e}"
    return None


# ── line-move alerts ──────────────────────────────────────────────────────

def move_alerts(send):
    """DM when a sent, pending pick's edge has dropped MOVE_PTS+ from its baseline."""
    import pick_alerts
    st = pick_alerts.load(pick_alerts.STATE, {})
    moves = pick_alerts.load(MOVES, {})
    d, games = snapshot()
    changed = False
    for p in picks_store.load_picks(os.path.join(REPO, "picks", "nba.json")):
        if p.get("date") != today() or p.get("status") != "pending" or p.get("line") is None or not _sent(st, p):
            continue
        start = picks_store.start_time(p)
        if start is not None and datetime.now(timezone.utc) >= start:
            continue
        g = find_game(p["side"], games)
        if not g:
            continue
        sim, _book = side_numbers(g, p["side"])
        if sim is None:
            continue
        edge = float(p["line"]) - sim
        ref = picks_store.state_ref(p["id"])
        rec = moves.get(ref)
        if rec is None:
            base = None
            try:
                s = (p.get("sim_projection") or "").split()
                if len(s) == 2 and s[0] == p["side"]:
                    base = float(p["line"]) - (0.0 if s[1] == "PK" else float(s[1]))
            except ValueError:
                base = None
            moves[ref] = rec = {"base": edge if base is None else base, "alerted": None}
            changed = True
        ref_edge = rec["alerted"] if rec["alerted"] is not None else rec["base"]
        if ref_edge - edge >= MOVE_PTS:
            team = p["side"]
            send(f"⚠️ Line move on a sent pick\n{p['pick_text']} · {_stake(p)} · {picks_store.start_label(p)}\n"
                 f"Edge {rec['base']:+.1f} when logged, {edge:+.1f} now (sim {_sim_txt(g, team, sim)}, "
                 f"{_ago(d.get('generated_at'))} run).\n"
                 f"Reply /stake {team} 0.5u, /pull {team}, or nothing to keep it.")
            rec["alerted"] = edge
            changed = True
    if changed:
        with open(MOVES, "w") as f:
            json.dump(moves, f, indent=2)
    return changed
