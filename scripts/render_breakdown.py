#!/usr/bin/env python3
"""The members breakdown: every game on tonight's slate through the possession sim, step by step.

Reads sim.explain's JSON (nba_pipeline/sim/explain.py) and takes the night's
calls from the ledger (picks/nba.json, opened with PICKS_SEAL_KEY): a logged pick
shows as the pick, at its stake, with the sim's chance to cover at its number; a
pick voided before tip says so; every other game shows the sim's best side and why
it isn't a pick. publish_member_breakdown.py puts the result in Firestore
(member_breakdowns/{date}) for /members/breakdown/. Never committed: the repo is
public and the picks are sealed until tip.

  python3 scripts/render_breakdown.py walk.json out.html
"""

import html
import json
import math
import os
import sys
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import picks_store  # noqa: E402

ET = timezone(timedelta(hours=-4))
SD = 13.0                      # NBA results scatter ~13 points around a good line (sim/run.py MARGIN_SD)
MIN_COVER, MAX_GAP = 0.58, 6.0
UNIT = 25.0                    # $PP per unit
e = html.escape
# ESPN's logo codes (the members page and pick notes use the same files)
ESPN = {"GSW": "gs", "NOP": "no", "NYK": "ny", "SAS": "sa", "UTA": "utah", "WAS": "wsh"}


def logo(abbr, cls="lg"):
    return (f'<img class="{cls}" src="https://a.espncdn.com/i/teamlogos/nba/500/{ESPN.get(abbr, abbr.lower())}.png" '
            f'alt="" loading="lazy" onerror="this.style.visibility=\'hidden\'">')


def face(pid, cls="hs"):
    """NBA.com headshot; hidden when the player has none."""
    if not pid:
        return ""
    return (f'<img class="{cls}" src="https://cdn.nba.com/headshots/nba/latest/260x190/{int(pid)}.png" alt="" '
            f'loading="lazy" onerror="this.style.visibility=\'hidden\'">')


def phi(x):
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def cover(margin, side_is_home, line):
    """Chance the side covers `line` (its own spread) when the home margin is ~ N(margin, SD)."""
    m = margin if side_is_home else -margin
    return phi((m + line) / SD)


def fmt(v):
    return "PK" if abs(v) < 0.05 else f"{v:+.1f}"


def _tips():
    try:
        daily = json.load(open(os.path.join(REPO, "nba_pipeline", "data", "daily_picks.json")))
    except (OSError, ValueError):
        return {}
    return {g["matchup"].replace(" ", ""): g.get("tip_at") for g in daily.get("games", [])}


TIPS = _tips()


def tip(game):
    try:
        return datetime.fromisoformat(TIPS.get(game)).astimezone(ET).strftime("%-I:%M %p ET")
    except (TypeError, ValueError):
        return "Tonight"


def ledger(date):
    """{"AWY@HOM": [pick, ...]} for the night, sealed picks opened with the key."""
    out = {}
    for p in picks_store.load_picks(os.path.join(REPO, "picks", "nba.json")):
        if p.get("date") == date and p.get("bet_type") == "spread" and p.get("away"):
            out.setdefault(f"{p['away']}@{p['home']}", []).append(p)
    return out


def decide(g, logged):
    h, a, mg = g["home"], g["away"], g["margin"]
    bs = g["book_home_spread"]
    out = {"sim_line": ("PK" if abs(mg) < 0.25 else f"{h if mg > 0 else a} {-abs(mg):+.1f}"),
           "book": None, "call": "no_line", "voided": [p for p in logged if p.get("status") == "void"]}
    live = [p for p in logged if p.get("status") == "pending" and not picks_store.is_raw_sealed(p)]
    if bs is not None:
        out["book"] = f"{h} {fmt(bs)}" if bs <= 0 else f"{a} {fmt(-bs)}"
        out["gap"] = abs(-mg - bs)
    if live:                                       # the ledger's pick, at its own number
        p = live[0]
        side, line = p["side"], float(p["line"])
        out.update(call="pick", side=side, line=line, cover=cover(mg, side == h, line),
                   units=float(p.get("units") or 0) / UNIT)
        return out
    if bs is None:
        return out
    home_side = -mg < bs
    side, line = (h, bs) if home_side else (a, -bs)
    out.update(side=side, line=line, cover=cover(mg, home_side, line))
    out["call"] = "hold" if out["gap"] > MAX_GAP else "pass"
    return out


def _hurt_out(g, team):
    outs = g["teams"][team]["out"]
    return ", ".join(o.split()[-1] for o in outs[:3]) + ("" if len(outs) <= 3 else f" and {len(outs) - 3} more")


def explain_step(g, name, pts):
    """One plain sentence for what a step did tonight."""
    h, a = g["home"], g["away"]
    fav = h if pts > 0 else a
    other = a if fav == h else h
    if name.startswith("Players"):
        return "Both rotations on a neutral court: player for player, who is better."
    if name.startswith("Home court"):
        return f"{h}'s measured home edge" + (" and the back-to-back" if "back" in name else "") + "."
    if name == "Lineup plan":
        return f"Minutes go to each coach's strongest fives; {fav}'s best units get more of the game than a random rotation would give them."
    if name == "Usage load":
        if g["teams"][other]["out"]:
            return (f"{other} is missing {_hurt_out(g, other)}. Their possessions go to teammates above their normal usage, "
                    f"and each one's efficiency drops along his own usage curve.")
        return f"{other}'s fives lean harder on a few players than usual, and their efficiency drops along their usage curves."
    if name == "Spacing":
        return f"{fav}'s fives carry more shooting, so cuts, rolls, posts and drives get more room."
    if name == "Chemistry":
        return f"{fav}'s pairs and units have outplayed what their players' own numbers predict."
    if name == "Scheme vs play type":
        return f"{fav}'s defensive scheme takes away more of what the other team runs most."
    if name == "Fatigue":
        return "Heavy minutes or a back-to-back cost efficiency."
    return "Layers overlap (better units also carry the chemistry and spacing); this squares the total."


def pull_chart(g):
    """Rows: each step's pull from the centre line (away left, home right), its points, the running total."""
    steps = [s for s in g["steps"] if abs(s["pts"]) >= 0.05 or s["step"].startswith("Players")]
    full = max(6.0, max(abs(s["pts"]) for s in steps))
    run_, rows = 0.0, []
    for s in steps:
        run_ += s["pts"]
        side = "h" if s["pts"] > 0 else "a"
        team = g["home"] if s["pts"] > 0 else g["away"]
        w = min(50.0, abs(s["pts"]) / full * 50)
        lead = g["home"] if run_ > 0 else g["away"]
        rows.append(f'<div class="pr"><div class="pl"><b>{e(s["step"])}</b><span>{e(explain_step(g, s["step"], s["pts"]))}</span></div>'
                    f'<div class="pb"><i class="{side}" style="width:{w:.1f}%"></i></div>'
                    f'<div class="pv {side}">{e(team)} +{abs(s["pts"]):.1f}</div>'
                    f'<div class="pt">{e(lead)} by {abs(run_):.1f}</div></div>')
    fin = g["margin"]
    side = "h" if fin > 0 else "a"
    team = g["home"] if fin > 0 else g["away"]
    w = min(50.0, abs(fin) / max(full, abs(fin)) * 50)
    rows.append(f'<div class="pr sum"><div class="pl"><b>Sim margin</b><span>Everything above, played out 5,000 times.</span></div>'
                f'<div class="pb"><i class="{side}" style="width:{w:.1f}%"></i></div>'
                f'<div class="pv {side}">{e(team)} by {abs(fin):.1f}</div><div class="pt"></div></div>')
    head = (f'<div class="ph"><span>Step</span><span class="ends"><em>← {e(g["away"])}</em><em>{e(g["home"])} →</em></span>'
            f'<span>Pull</span><span>Running</span></div>')
    return f'<div class="pull">{head}{"".join(rows)}</div>'


def units_table(g, abbr):
    units = g["teams"][abbr].get("units") or []
    color = g["home_color"] if abbr == g["home"] else g["away_color"]
    per12 = g["pace"] / 100 / 4
    rows = "".join(
        f'<tr><td class="five"><span class="faces">{"".join(face(p, "hs xs") for p in u.get("pids", []))}</span>{e(" · ".join(u["five"]))}'
        + ('<span class="tag st">Starts</span>' if u["start"] else "") + ('<span class="tag cl">Closes</span>' if u["close"] else "")
        + f'</td><td>{u["min"]:.0f}</td><td class="{"pos" if u["net"] > 0 else "neg"}">{u["net"]:+.1f}</td>'
        f'<td>{u["net"] * per12:+.1f}</td><td>{u["chem"]:+.1f}</td></tr>' for u in units)
    return (f'<div class="rot" style="--tc:{color}"><h4>{logo(abbr, "lg sm")}{e(abbr)} <span>tonight’s units</span></h4><table class="units"><thead><tr>'
            f'<th>Five</th><th title="Minutes the plan gives this five">Min</th><th title="Net per 100 possessions: impact + chemistry">Net/100</th>'
            f'<th title="The same, per 12 minutes together">Per 12</th><th title="Pairs plus the unit’s own record, per 100">Chem</th></tr></thead>'
            f'<tbody>{rows}</tbody></table></div>')


def histogram(g, d):
    """SVG: 5,000 simulated home margins, the book line marked; bars on the covering side shaded."""
    edges, raw = g["hist"]["edges"], g["hist"]["counts"]
    # the margins are whole points narrowed to the 13-point spread, which aliases against 2-point
    # bins; a 1-2-1 smooth shows the shape without the comb
    counts = [(raw[max(0, i - 1)] + 2 * raw[i] + raw[min(len(raw) - 1, i + 1)]) / 4 for i in range(len(raw))]
    W, H, pad_b, pad_t = 640, 200, 34, 14
    n = len(counts)
    cmax = max(counts) or 1
    bw = (W - 20) / n
    out = [f'<svg viewBox="0 0 {W} {H}" class="hist" role="img" aria-label="Margins over 5,000 games">']
    bs = g["book_home_spread"]
    cut = -bs if bs is not None else None            # home margin that pushes the book line
    for i, c in enumerate(counts):
        lo_e = edges[i]
        x = 10 + i * bw
        h = (H - pad_b - pad_t) * c / cmax
        center = lo_e + 1
        fill = "#C9D3CE"
        if d.get("side") and cut is not None:
            covers = center > cut if d["side"] == g["home"] else center < cut
            fill = (g["home_color"] if d["side"] == g["home"] else g["away_color"]) if covers else "#C9D3CE"
        out.append(f'<rect x="{x + 1:.1f}" y="{H - pad_b - h:.1f}" width="{bw - 2:.1f}" height="{h:.1f}" fill="{fill}"/>')
    sx = lambda v: 10 + (v - edges[0]) / (edges[-1] - edges[0]) * (W - 20)
    for v in (-30, -20, -10, 0, 10, 20, 30):
        out.append(f'<text x="{sx(v):.1f}" y="{H - 14}" class="tick" text-anchor="middle">{"0" if v == 0 else (g["home"] + " +" + str(v) if v > 0 else g["away"] + " +" + str(-v))}</text>')
    if cut is not None:
        out.append(f'<line x1="{sx(cut):.1f}" y1="{pad_t - 6}" x2="{sx(cut):.1f}" y2="{H - pad_b + 4}" class="bookline"/>')
        out.append(f'<text x="{sx(cut) + 6:.1f}" y="{pad_t + 6}" class="tick b">Book line</text>')
    out.append(f'<line x1="{sx(g["margin"]):.1f}" y1="{pad_t - 6}" x2="{sx(g["margin"]):.1f}" y2="{H - pad_b + 4}" class="simline"/>')
    out.append("</svg>")
    return "".join(out)


def rotation_table(g, abbr):
    t = g["teams"][abbr]
    rows = []
    for r in t["rotation"]:
        tags = []
        if r["gravity"] >= 0.8:
            tags.append('<span class="tag shoot">Shooter</span>')
        if r["role"]:
            tags.append(f'<span class="tag role" title="Measured in games a regular teammate missed">'
                        f'role {r["role"]["usg"]:+.1f} usg</span>')
        rows.append(f'<tr class="{"st" if r["starter"] else ""}"><td class="nm">{face(r.get("pid"))}<div><span class="pn">{e(r["name"])}</span>{"".join(tags)}'
                    f'<small>{e(" · ".join(r["plays"]))}</small></div></td><td>{r["min"]:.0f}</td><td>{r["usg"]:.0f}%</td>'
                    f'<td>{r["per_use"]:.2f}</td><td>{r["off"] + r["def"]:+.1f}</td></tr>')
    out = "".join(f'<span class="out">{e(n)}</span>' for n in t["out"]) or '<span class="none">Nobody out</span>'
    color = g["home_color"] if abbr == g["home"] else g["away_color"]
    return (f'<div class="rot" style="--tc:{color}"><h4>{logo(abbr, "lg sm")}{e(abbr)} <span>{e(g["home_name"] if abbr == g["home"] else g["away_name"])}</span></h4>'
            f'<table><thead><tr><th>Player</th><th title="Projected minutes">Min</th><th title="Share of possessions he ends">Usg</th>'
            f'<th title="Points per possession he ends">Pts/poss</th><th title="RAPM/LEBRON impact per 100">Impact</th></tr></thead>'
            f'<tbody>{"".join(rows)}</tbody></table><div class="outs"><b>Out</b>{out}</div></div>')


def box_table(g, abbr):
    rows = "".join(f'<tr><td class="nm">{face(p.get("pid"))}<div><span class="pn">{e(p["name"])}</span></div></td><td>{p["min"]:.0f}</td><td><b>{p["pts"]:.1f}</b></td></tr>' for p in g["box"][abbr])
    return f'<table class="box"><thead><tr><th>{logo(abbr, "lg xs")}{e(abbr)}</th><th>Min</th><th>Pts</th></tr></thead><tbody>{rows}</tbody></table>'


def reasons(g, d):
    h, a = g["home"], g["away"]
    st = {s["step"]: s["pts"] for s in g["steps"]}
    lean = lambda v: (h if v > 0 else a)
    out = []
    base = st.get("Players on a neutral court", 0)
    out.append(f"On a neutral court the two rotations alone make it {lean(base)} by {abs(base):.1f}.")
    movers = sorted(((k, v) for k, v in st.items() if k not in ("Players on a neutral court", "How the layers combine")
                     and abs(v) >= 0.5), key=lambda kv: -abs(kv[1]))
    for k, v in movers[:3]:
        out.append(f"{k} moves it {abs(v):.1f} toward {lean(v)}.")
    if d.get("side"):
        out.append(f"Sim line {d['sim_line']} against the book's {d['book']}: {d['gap']:.1f} points apart. "
                   f"{d['side']} {fmt(d['line'])} covers in {d['cover']:.0%} of the 5,000 games.")
    if d.get("gap", 0) > MAX_GAP:
        out.append(f"The sim is {d['gap']:.1f} points off the market here. Past {MAX_GAP:.0f} points the market has "
                   f"usually seen something the model hasn't.")
    return "".join(f"<li>{e(x)}</li>" for x in out)


VERDICT = {"pick": "Pick", "hold": "No pick: off the market", "pass": "No pick", "no_line": "No line"}


def card(g, d):
    gid = g["game"].replace("@", "-").lower()
    call = d["call"]
    if call == "pick":
        verdict = f'<b>{e(d["side"])} {fmt(d["line"])}</b> · {d["cover"]:.0%} to cover · {d["units"]:g}U'
        why = "Logged before tip. The stake is frozen on the ledger."
    elif call == "hold":
        verdict = f'Best side {e(d["side"])} {fmt(d["line"])} · {d["cover"]:.0%} to cover'
        why = f"Not a pick: the sim is {d['gap']:.1f} points off the market, past the {MAX_GAP:.0f}-point limit."
    elif call == "pass":
        verdict = f'Best side {e(d["side"])} {fmt(d["line"])} · {d["cover"]:.0%} to cover'
        why = f"Not a pick: under a {MIN_COVER:.0%} chance to cover."
    else:
        verdict, why = "No book line yet", ""
    void = "".join(f'<p class="old">Voided before tip: <b>{e(p.get("pick_text") or "")}</b>. '
                   f'{e((p.get("void_reason") or "").split(": ", 1)[-1])}</p>' for p in d["voided"])
    return f"""
<section class="game" id="{gid}" style="--ac:{g['away_color']};--hc:{g['home_color']}">
  <header class="gh">
    <div class="tm">{logo(g['away'])}<div><b>{e(g['away'])}</b><span>{e(g['away_name'])}</span></div></div>
    <div class="mid"><span class="k">{e(tip(g['game']))} · Sim line</span><strong>{e(d['sim_line'])}</strong>
      <span class="bk">Book {e(d['book'] or 'none yet')}</span></div>
    <div class="tm r">{logo(g['home'])}<div><b>{e(g['home'])}</b><span>{e(g['home_name'])}</span></div></div>
  </header>
  <div class="verdict {call}"><span class="vk">{VERDICT[call]}</span><span>{verdict}</span></div>
  <ol class="steps">
    <li><h3>Who's playing</h3><p class="lede">Tonight's rotations: RotoWire's starters and injury list, minutes for a 240-minute game, each player's numbers from his own games.</p>
      <div class="rots">{rotation_table(g, g['away'])}{rotation_table(g, g['home'])}</div></li>
    <li><h3>Tonight's units</h3><p class="lede">Every possible five from each rotation, scored on its players' impact plus its chemistry (its pairs and its own record together). Minutes go to the strongest fives first, the way a coach stacks his best units, inside each player's minutes. Starters open both halves; the best five of the regulars closes.</p>
      <div class="rots">{units_table(g, g['away'])}{units_table(g, g['home'])}</div></li>
    <li><h3>Every possession</h3><p class="lede">About {g['pace']:.0f} possessions each. Each one: who ends it (usage), how (his play types), what it's worth against these five defenders and this scheme, then a shot, a turnover or a putback.</p>
      <div class="env">
        <div><span class="k">{e(g['away'])} offense vs this D</span><b>{g['away_ortg']:.1f}</b><small>pts / 100</small></div>
        <div><span class="k">{e(g['home'])} offense vs this D</span><b>{g['home_ortg']:.1f}</b><small>pts / 100</small></div>
        <div><span class="k">Spacing vs an average five</span><b>{g['spacing']['away']:+.1f} / {g['spacing']['home']:+.1f}</b><small>{e(g['away'])} / {e(g['home'])} shooters</small></div>
        <div><span class="k">Chemistry</span><b>{g['chemistry']['away']:+.1f} / {g['chemistry']['home']:+.1f}</b><small>pts / 100, {e(g['away'])} / {e(g['home'])}</small></div>
      </div></li>
    <li><h3>What moved the line</h3><p class="lede">Start from the two rotations on a neutral court, then add each layer. Each bar pulls toward the team it helps; the last column keeps the running score.</p>
      {pull_chart(g)}</li>
    <li><h3>5,000 games</h3><p class="lede">Every simulated final margin. Shaded bars are the games where {e(d.get('side') or 'the sim side')} covers.</p>
      {histogram(g, d)}
      <p class="read">{e(g['away'])} {g['away_pts']:.0f} – {e(g['home'])} {g['home_pts']:.0f} on average. {e(g['home'] if g['margin'] > 0 else g['away'])} wins {max(g['home_win'], 1 - g['home_win']):.0%} of them.</p></li>
    <li><h3>Projected box</h3><div class="boxes">{box_table(g, g['away'])}{box_table(g, g['home'])}</div></li>
  </ol>
  <div class="why"><h3>Why</h3><ul>{reasons(g, d)}</ul><p class="rule">{e(why)}</p>{void}</div>
</section>"""


def render(walk, date):
    book = ledger(date)
    decided = [(g, decide(g, book.get(g["game"], []))) for g in walk["games"]]
    order = {"pick": 0, "hold": 1, "pass": 2, "no_line": 3}
    decided.sort(key=lambda x: (order[x[1]["call"]], TIPS.get(x[0]["game"]) or ""))
    picks = [(g, d) for g, d in decided if d["call"] == "pick"]
    cards = "".join(card(g, d) for g, d in picks)
    rest = "".join(f'<details><summary>{logo(g["away"], "lg xs")}{e(g["away"])} @ {logo(g["home"], "lg xs")}{e(g["home"])} · {e(tip(g["game"]))} · sim {e(d["sim_line"])}, book {e(d["book"] or "none")}'
                   + (f' · best side {e(d["side"])} {fmt(d["line"])} {d["cover"]:.0%}' if d.get("side") else "")
                   + f'</summary>{card(g, d)}</details>' for g, d in decided if d["call"] != "pick")
    rows = []
    for g, d in sorted(decided, key=lambda x: TIPS.get(x[0]["game"]) or ""):
        call_txt = f"{d['side']} {fmt(d['line'])} · {d['units']:g}U" if d["call"] == "pick" else "—"
        rows.append(f'<tr class="{d["call"]}"><td>{e(tip(g["game"]))}</td><td><a href="#{g["game"].replace("@", "-").lower()}">{logo(g["away"], "lg xs")}{e(g["away"])} @ {logo(g["home"], "lg xs")}{e(g["home"])}</a></td>'
                    f'<td>{e(d["book"] or "—")}</td><td>{e(d["sim_line"])}</td><td>{d.get("gap", 0):.1f}</td>'
                    f'<td>{(str(round(d["cover"] * 100)) + "%") if d.get("cover") is not None else "—"}</td>'
                    f'<td class="c">{e(call_txt)}</td></tr>')
    units = sum(d["units"] for _, d in picks)
    chips = "".join(f'<a class="chip" href="#{g["game"].replace("@", "-").lower()}">{e(d["side"])} {fmt(d["line"])}</a>' for g, d in picks)
    run_at = datetime.fromisoformat(walk["generated"].replace("Z", "+00:00")).astimezone(ET).strftime("%-I:%M %p ET")
    return f"""<div class="bd">
  <div class="intro"><p>{len(picks)} pick{"" if len(picks) == 1 else "s"} tonight, {units:g}U in all, from {len(decided)} games. Every game was played 5,000 times, possession by possession, with tonight's rotations (sim run {run_at}).</p>
    <div class="chips">{chips}</div></div>
  {cards}
  <section class="rest"><h2>The other games</h2><p>The same walkthrough for every game without a pick.</p>{rest}</section>
  <section class="sum"><h2>Summary</h2><p>The whole slate in tip order.</p>
    <div class="tw"><table><thead><tr><th>Tip</th><th>Game</th><th>Book</th><th>Sim</th><th>Gap</th><th>Covers</th><th>Pick</th></tr></thead>
    <tbody>{"".join(rows)}</tbody></table>
    <div class="totals"><span>Picks: {len(picks)}</span><span>Stake: {units:g}U total</span></div></div>
    <p class="notes"><b>How to read it.</b> Chances use a 13-point spread around the sim's margin, the scatter NBA results show around a good line. The sim isn't a pick past {MAX_GAP:.0f} points off the market, or under a {MIN_COVER:.0%} chance to cover. Simulations, not guarantees.</p>
  </section>
</div>"""


if __name__ == "__main__":
    walk = json.load(open(sys.argv[1]))
    date = datetime.fromisoformat(walk["generated"].replace("Z", "+00:00")).astimezone(ET).strftime("%Y-%m-%d")
    open(sys.argv[2], "w").write(render(walk, date))
    print(f"breakdown: {len(walk['games'])} games for {date}")
