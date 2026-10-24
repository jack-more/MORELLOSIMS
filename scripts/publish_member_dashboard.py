#!/usr/bin/env python3
"""Publish the NBA SIM dashboard as the members dashboard: /members/dashboard/.

generate_frontend.py writes the full dashboard (game lines, the court sim,
player stats and Top 50 MOJO, trends) to nba_pipeline/nba_sim.html on every
run; nothing published it since /nbasim/ became the data page. This copies it
to members/dashboard/index.html with the brand applied and a members gate:
the brand header, assets/brand/v2/dashboard.css over the page's own styles,
lineups (with archetypes) open on every game, and a few markup rewrites that
CSS cannot reach (old edge colours, the sealed card's link).

The gate is a courtesy, not security: GitHub Pages serves the file to anyone.
What has to stay private, tonight's picks, is sealed inside it under seal
mode (generate_frontend renders a picked game as a sealed card, and
check_seal_guardrail.py scans this file like every other staged file);
members read the picks themselves on /members/ (Firestore). The full cards of
those games (lineups, the sim's side) go to Firestore member_cards
(publish_member_cards.py); GATE_JS swaps them in for a member after sign-in.

  python3 scripts/publish_member_dashboard.py
"""

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import brand_head  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(REPO, "nba_pipeline", "nba_sim.html")
OUT = os.path.join(REPO, "members", "dashboard", "index.html")

HEAD = """
<link href="https://fonts.googleapis.com/css2?family=Archivo:wdth,wght@75..100,400..900&display=swap" rel="stylesheet">
<link rel="stylesheet" href="/assets/brand/v2/brand.css?v=20261021d">
<link rel="stylesheet" href="/assets/brand/v2/dashboard.css?v=20261023a">
<link rel="icon" href="/assets/brand/v2/mark.svg" type="image/svg+xml">
<meta name="robots" content="noindex">
<style>
#ms-gate{position:fixed;inset:0;z-index:9999;background:rgba(16,35,63,.94);display:flex;align-items:center;justify-content:center;padding:24px}
#ms-gate[hidden]{display:none}
#ms-gate .box{max-width:460px;text-align:center;color:#fff;font-family:var(--ms-font)}
#ms-gate img{height:54px;margin:0 auto 22px;display:block}
#ms-gate h2{font:900 34px/1.05 var(--ms-font);letter-spacing:-.02em}
#ms-gate p{margin:14px 0 24px;color:#DCE6F4;font-size:16px;line-height:1.5}
#ms-gate .b{display:flex;gap:10px;justify-content:center;flex-wrap:wrap}
#ms-gate a,#ms-gate button{display:inline-flex;align-items:center;min-height:50px;padding:0 22px;border-radius:3px;font:700 16px var(--ms-font);text-decoration:none;cursor:pointer}
#ms-gate a{background:var(--ms-green);color:#fff;border:0}
#ms-gate button{background:transparent;color:#fff;border:1.5px solid #fff}
/* one view: the members zone row replaces the old tab bars (Game Lines / Player Stats / Trends / Info) */
.sticky-header,.bottom-nav{display:none!important}
/* a sealed game swapped for its full card after sign-in */
.matchup-card.ms-pick-card{box-shadow:0 0 0 3px var(--ms-green),0 12px 30px rgba(0,0,0,.12)}
.ms-pick-tag{display:block;width:fit-content;margin:0 0 6px;padding:4px 8px;border-radius:4px;background:var(--ms-green);color:#fff;font:800 11px/1 var(--ms-font);letter-spacing:.06em;text-transform:uppercase;vertical-align:1px}
</style>
"""

BAR = """
<div class="ms-head">
<header class="ms-top"><div class="in">
  <a href="/" aria-label="Morello Sims"><span class="foil-logo"><i></i></span></a>
  <nav aria-label="Main"><a class="opt" href="/">Home</a><a href="/ledger/nba/">Ledger</a><a class="on" href="/members/" aria-current="page">Members<span class="lg"> zone</span></a><a class="acct" href="#" id="ms-acct">Account</a></nav>
</div></header>
<div class="ms-zone"><div class="in"><span class="k">Members zone</span><nav aria-label="Members zone"><a class="on" href="/members/dashboard/" aria-current="page">Lineups + info</a><a href="/members/">Tonight’s picks</a><a href="/members/breakdown/">Breakdown</a></nav></div></div>
</div>
<div id="ms-gate"><div class="box">
  <img src="/assets/brand/v2/lockup-on-dark.svg" alt="Morello Sims">
  <h2>The members dashboard.</h2>
  <p>Every game on tonight's slate, the court sim, player MOJO and trends. Included with every pass.</p>
  <div class="b"><a href="/#plans">Get a pass</a><button type="button" onclick="window.morelloAuth &amp;&amp; morelloAuth.openModal('signin')">Sign in</button></div>
</div></div>
"""

GATE_JS = """
<script>
(function () {
  // same pass rule as hasActiveAccess in functions/index.js
  function active(u) {
    if (!u) return false;
    if (u.tier === "admin") return true;
    var exp = u.accessExpiresAt && u.accessExpiresAt.toMillis ? u.accessExpiresAt.toMillis() : 0;
    if (exp > Date.now()) return true;
    return u.checkoutMode === "subscription" && !!u.tier && u.tier !== "free";
  }
  document.getElementById("ms-acct").addEventListener("click", function (e) {
    e.preventDefault();
    var a = window.morelloAuth;
    if (a) a.openModal(a.getCurrentUser() ? "profile" : "signin");
  });
  // tonight's picked games: the sealed card gives way to the full card (member_cards)
  function picks() {
    var since = new Date(Date.now() - 30 * 36e5).toISOString().slice(0, 10), db = firebase.firestore(), logged = {};
    db.collection("member_picks").where("date", ">=", since).get().then(function (q) {
      q.forEach(function (d) { var p = d.data(); if (p.sport === "nba" && p.away) logged[p.away + "@" + p.home] = p; });
    }).catch(function () {}).then(function () {
      return db.collection("member_cards").where("date", ">=", since).get();
    }).then(function (q) {
      var by = {};
      q.forEach(function (d) { var c = d.data(); if (!by[c.game] || by[c.game].date < c.date) by[c.game] = c; });
      document.querySelectorAll(".sealed-card").forEach(function (old) {
        var g = old.dataset.game || Array.prototype.map.call(old.querySelectorAll(".gc-matchup b"),
          function (b) { return b.textContent.trim(); }).join("@");
        var c = by[g], t = document.createElement("div");
        if (!c) return;
        t.innerHTML = c.html.trim();
        var card = t.firstElementChild;
        if (!card) return;
        card.dataset.pick = "1";
        card.dataset.idx = old.dataset.idx;
        var p = logged[g], tag = "Tonight\u2019s pick";
        card.dataset.conf = (p && p.conf) || old.dataset.conf || card.dataset.conf;   // the grade it was logged at
        card.classList.add("ms-pick-card");
        if (p && p.pick_text) tag += " \u00b7 " + p.pick_text + " \u00b7 C" + p.conf + " \u00b7 " + p.units + "U";
        var when = card.querySelector(".gc-when"), el = document.createElement("span");
        el.className = "ms-pick-tag";
        el.textContent = tag;
        if (when) when.insertBefore(el, when.firstChild);
        old.replaceWith(card);
        msOpenLineups(card);
        msTips(card);
      });
    }).catch(function () {});
  }
  (function wait(n) {
    if (typeof firebase !== "undefined" && firebase.apps && firebase.apps.length) {
      return firebase.auth().onAuthStateChanged(function (user) {
        var gate = document.getElementById("ms-gate");
        document.getElementById("ms-acct").textContent = user ? "Account" : "Sign in";
        if (!user) { gate.hidden = false; return; }
        firebase.firestore().collection("users").doc(user.uid).get().then(function (s) {
          if (active(s.exists ? s.data() : null)) return true;
          // whitelisted (friends & family): the member_picks rule decides
          return firebase.firestore().collection("member_picks").limit(1).get().then(function () { return true; });
        }).then(function (ok) { gate.hidden = ok; if (ok) picks(); }).catch(function () { gate.hidden = false; });
      });
    }
    if (n < 150) setTimeout(function () { wait(n + 1); }, 100);
  })(0);
})();
</script>
"""

# Lineups open on every game, bench folded under a button, so each player's
# archetype is on the card without a click.
LINEUPS_JS = """
<script>
function msOpenLineups(root) {
root.querySelectorAll(".expand-btn").forEach(function (btn) {
  var ex = btn.closest(".matchup-card").querySelector(".mc-expanded");
  if (!ex) return;
  ex.style.display = "grid";
  btn.classList.add("open");
  btn.querySelector("span").textContent = "Hide lineups";
  var n = ex.querySelectorAll(".player-row.bench").length;
  if (!n) return;
  ex.classList.add("ms-bench-hidden");
  var t = document.createElement("button");
  t.type = "button";
  t.className = "ms-bench-toggle";
  t.textContent = "Show bench (" + n + ")";
  t.onclick = function () {
    var hidden = ex.classList.toggle("ms-bench-hidden");
    t.textContent = hidden ? "Show bench (" + n + ")" : "Hide bench";
  };
  ex.appendChild(t);
});
}
msOpenLineups(document);
document.querySelectorAll(".sealed-card .mc-center").forEach(function (c) {
  if (c.querySelector(".sealed-cta")) return;
  var a = document.createElement("a");
  a.className = "sealed-cta";
  a.href = "/members/";
  a.innerHTML = "Open the pick &rarr;";
  c.appendChild(a);
});
</script>
"""

# Explanations: hover on desktop, tap on a phone. Game-card terms carry their
# wording in data-tip (generate_frontend.BOARD_TIPS); on desktop, archetypes take
# theirs from the Info tab and MOJO numbers get a short read.
TIPS_JS = """
<script>
(function () {
  var hover = window.matchMedia("(hover: hover)").matches;
  var desc = {};
  document.querySelectorAll(".info-arch-card").forEach(function (c) {
    var n = c.querySelector(".info-arch-name"), d = c.querySelector(".info-arch-desc");
    if (n && d) desc[n.textContent.trim()] = d.textContent.trim();
  });
  window.msTips = function (root) {
    if (hover) root.querySelectorAll(".player-row[data-arch]").forEach(function (r) {
      var a = r.getAttribute("data-arch"), meta = r.querySelector(".pr-meta"), mojo = r.querySelector(".pr-mojo");
      if (meta && desc[a]) { meta.setAttribute("data-tip", a + ": " + desc[a]); meta.classList.add("tip"); }
      if (mojo) mojo.setAttribute("data-tip", "MOJO " + r.getAttribute("data-mojo") + ", on a 33 to 99 scale: player impact, " +
        "25% box score and 75% lineup impact. Tonight's likely range: " + r.getAttribute("data-range") + ".");
    });
    root.querySelectorAll(".gc [data-tip], .gc[data-tip]").forEach(function (el) { el.tabIndex = 0; });
  };
  msTips(document);
  var tip = document.createElement("div"), cur = null;
  tip.className = "ms-tip"; tip.setAttribute("role", "tooltip");
  document.body.appendChild(tip);
  function show(el) {
    cur = el; tip.textContent = el.getAttribute("data-tip"); tip.classList.add("on");
    var r = el.getBoundingClientRect(), w = tip.offsetWidth, h = tip.offsetHeight;
    var x = Math.min(Math.max(8, r.left + r.width / 2 - w / 2), document.documentElement.clientWidth - w - 8);
    var y = r.top - h - 10;
    if (y < 8) y = r.bottom + 10;
    tip.style.left = x + "px"; tip.style.top = (y + window.scrollY) + "px";
  }
  function hide() { cur = null; tip.classList.remove("on"); }
  if (hover) {
    document.addEventListener("mouseover", function (e) { var el = e.target.closest("[data-tip]"); if (el && el !== cur) show(el); });
    document.addEventListener("mouseout", function (e) { var el = e.target.closest("[data-tip]"); if (el && !el.contains(e.relatedTarget)) hide(); });
  }
  document.addEventListener("click", function (e) {
    var el = e.target.closest("[data-tip]");
    if (!el) return hide();
    if (hover) return;
    e.preventDefault(); e.stopPropagation();
    cur === el ? hide() : show(el);
  }, true);
  window.addEventListener("scroll", function () { if (!hover) hide(); }, {passive: true});
  // keyboard focus only: a tap also focuses, and the click handler owns taps
  document.addEventListener("focusin", function (e) {
    var el = e.target.closest && e.target.closest("[data-tip]");
    if (el && el.matches(":focus-visible")) show(el); else if (!el) hide();
  });
})();
</script>
"""

TITLE = """
<div class="ms-dash-title"><h1>Lineups + info</h1><span>{date}</span></div>
"""

# the dashboard's neon greens, mapped onto the brand
PALETTE = {"#00FF55": "#1FA255", "#00ff55": "#1FA255", "#00CC44": "#14743C", "#00cc44": "#14743C"}

# plain string swaps: old fonts out (dashboard.css sets Archivo), labels in sentence case
SWAPS = [
    ('<link href="https://fonts.googleapis.com/css2?family=Anton&family=Inter:wght@400;500;600;700;800;900&family=JetBrains+Mono:wght@400;500;700&display=swap" rel="stylesheet">', ""),
    ("\u25bc VIEW LINEUPS", "Show lineups"),
    ("\u25b2 HIDE LINEUPS", "Hide lineups"),
    (">SIM (desktop)</button>", ">Sim</button>"),
    # edge colours drawn for the old dark cards, readable on white
    ('style="color:rgba(0,255,85,0.6)"', 'style="color:#14743C"'),
    ('style="color:rgba(255,80,80,0.5)"', 'style="color:#C4574A"'),
    ('style="color:rgba(255,255,255,0.3)"', 'style="color:#8A938F"'),
    ('class="formula-row" style="color:rgba(0,0,0,0.7)"', 'class="formula-row" style="color:#3FCB74"'),
]

# the sealed card sends members to Tonight's picks instead of checkout
SEALED_CTA = re.compile(r'<a class="sealed-cta" href="[^"]*"[^>]*>[^<]*</a>')
SLATE_DATE = re.compile(r'<span class="logo-date">([^<]+)</span>')


def brand(html):
    """The markup rewrites, on the page or on one card (publish_member_cards.py)."""
    for a, b in PALETTE.items():
        html = html.replace(a, b)
    for a, b in SWAPS:
        html = html.replace(a, b)
    return SEALED_CTA.sub('<a class="sealed-cta" href="/members/">Open the pick &rarr;</a>', html)


OG = """    <meta property="og:type" content="website">
    <meta property="og:url" content="https://morellosims.com/members/dashboard/">
    <meta property="og:title" content="Lineups + info · Morello Sims Members">
    <meta property="og:description" content="Tonight&#39;s lineups, injuries and matchup notes. Members only.">
"""  # icons and preview image: brand_head.apply in build()


def build(src=SRC, out=OUT):
    html = brand(open(src, encoding="utf-8").read())
    html = re.sub(r"<title>[^<]*</title>", "<title>Lineups + info · Morello Sims</title>", html, count=1)
    html = re.sub(r'\s*<meta property="og:image"[^>]*>', "", html)
    html = html.replace("</title>", "</title>\n" + OG.rstrip("\n"), 1)
    if "</head>" not in html or "<body" not in html or "</body>" not in html:
        raise SystemExit(f"{src}: not a full page")
    html = html.replace("</head>", HEAD + "</head>", 1)
    i = html.index(">", html.index("<body")) + 1
    html = html[:i] + BAR + html[i:]
    m = SLATE_DATE.search(html)
    date = m.group(1).strip().title() if m else ""
    k = html.find('<main class="content">')
    if k != -1:
        html = html[:k] + TITLE.format(date=date) + html[k:]
    j = html.rindex("</body>")
    html = html[:j] + LINEUPS_JS + TIPS_JS + GATE_JS + html[j:]
    html = brand_head.apply(html, "https://morellosims.com/members/dashboard/")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    return out


if __name__ == "__main__":
    if not os.path.exists(SRC):
        print(f"{SRC} not found — run generate_frontend.py first")
        sys.exit(0)
    print("members dashboard:", os.path.relpath(build(), REPO))
