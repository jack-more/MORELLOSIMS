#!/usr/bin/env python3
"""Publish the NBA SIM dashboard as the members dashboard: /members/dashboard/.

generate_frontend.py writes the full dashboard (game lines, the court sim,
player stats and Top 50 MOJO, trends) to nba_pipeline/nba_sim.html on every
run; nothing published it since /nbasim/ became the data page. This copies it
to members/dashboard/index.html with the brand applied (header bar, palette)
and a members gate.

The gate is a courtesy, not security: GitHub Pages serves the file to anyone.
What has to stay private, tonight's picks, is sealed inside it under seal
mode (generate_frontend renders a picked game as a sealed card, and
check_seal_guardrail.py scans this file like every other staged file);
members read the picks themselves on /members/ (Firestore).

  python3 scripts/publish_member_dashboard.py
"""

import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(REPO, "nba_pipeline", "nba_sim.html")
OUT = os.path.join(REPO, "members", "dashboard", "index.html")

HEAD = """
<link href="https://fonts.googleapis.com/css2?family=Archivo:wdth,wght@75..100,400..900&display=swap" rel="stylesheet">
<link rel="stylesheet" href="/assets/brand/v2/brand.css?v=20261020">
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
.ms-bar{position:relative;z-index:50}
</style>
"""

BAR = """
<header class="ms-bar"><div class="in">
  <a class="ms-logo" href="/" aria-label="Morello Sims"><img src="/assets/brand/v2/lockup-on-dark.svg" alt="Morello Sims"></a>
  <nav class="ms-links" aria-label="Main"><a href="/members/">Tonight's picks</a><a class="on" href="/members/dashboard/">Dashboard</a><a class="opt" href="/ledger/nba/">Ledger</a></nav>
</div></header>
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
  (function wait(n) {
    if (typeof firebase !== "undefined" && firebase.apps && firebase.apps.length) {
      return firebase.auth().onAuthStateChanged(function (user) {
        var gate = document.getElementById("ms-gate");
        if (!user) { gate.hidden = false; return; }
        firebase.firestore().collection("users").doc(user.uid).get().then(function (s) {
          gate.hidden = active(s.exists ? s.data() : null);
        }).catch(function () { gate.hidden = false; });
      });
    }
    if (n < 150) setTimeout(function () { wait(n + 1); }, 100);
  })(0);
})();
</script>
"""

# the dashboard's neon greens, mapped onto the brand
PALETTE = {"#00FF55": "#1FA255", "#00ff55": "#1FA255", "#00CC44": "#14743C", "#00cc44": "#14743C"}


def build(src=SRC, out=OUT):
    html = open(src, encoding="utf-8").read()
    for a, b in PALETTE.items():
        html = html.replace(a, b)
    if "</head>" not in html or "<body" not in html or "</body>" not in html:
        raise SystemExit(f"{src}: not a full page")
    html = html.replace("</head>", HEAD + "</head>", 1)
    i = html.index(">", html.index("<body")) + 1
    html = html[:i] + BAR + html[i:]
    j = html.rindex("</body>")
    html = html[:j] + GATE_JS + html[j:]
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    return out


if __name__ == "__main__":
    if not os.path.exists(SRC):
        print(f"{SRC} not found — run generate_frontend.py first")
        sys.exit(0)
    print("members dashboard:", os.path.relpath(build(), REPO))
