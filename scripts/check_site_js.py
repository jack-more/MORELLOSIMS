#!/usr/bin/env python3
"""Fail if any inline <script> on a public page doesn't parse.

One syntax error kills a page's whole script (2026-10-05: a duplicate
`const` left the homepage with no sets, no checkout, no numbers). Runs on
every push (bot-scope-check workflow) and is safe to run locally.

  python3 scripts/check_site_js.py
"""
import os
import re
import subprocess
import sys
import tempfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAGES = ["index.html", "ledger/nba/index.html", "nbasim/index.html", "nfl/index.html", "extra/index.html",
         "scripts/templates/nba_ledger.html", "scripts/templates/data_page.html", "morello-auth.js"]

bad = 0
for rel in PAGES:
    path = os.path.join(REPO, rel)
    if not os.path.exists(path):
        continue
    src = open(path).read()
    blocks = [src] if rel.endswith(".js") else re.findall(r"<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>", src, re.S)
    for i, js in enumerate(blocks):
        with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as f:
            f.write(js)
        r = subprocess.run(["node", "--check", f.name], capture_output=True, text=True)
        os.unlink(f.name)
        if r.returncode:
            bad += 1
            msg = next((l for l in r.stderr.splitlines() if "Error" in l), r.stderr.strip()[:200])
            print(f"::error file={rel}::inline script {i + 1} does not parse: {msg}")
print(f"site js: {'FAIL' if bad else 'ok'} ({len(PAGES)} pages)")
sys.exit(1 if bad else 0)
