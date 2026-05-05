#!/usr/bin/env python3
"""
build_sim_app.py — Generate the standalone NBA Simulator app at /sim/.

Reads:  nba_pipeline/index.html  (full multi-tab NBA dashboard, just generated)
Writes: sim/index.html            (same content, but locked to the SIM tab,
                                   navbars hidden, light app-bar overlay)

This is a derivative artifact — the source of truth is the NBA pipeline.
Re-runs every time the NBA pipeline produces a new dashboard.
"""
import os
import shutil
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(REPO, "nba_pipeline", "index.html")
DST_DIR = os.path.join(REPO, "sim")
DST = os.path.join(DST_DIR, "index.html")

INJECTION = """
    <!-- ═══════════════════════════════════════════════════════════════ -->
    <!-- STANDALONE SIM APP OVERLAY                                      -->
    <!-- This page is a duplicate of /nbasim/ but locked to the SIM tab. -->
    <!-- The full multi-tab dashboard remains at /nbasim/.               -->
    <!-- ═══════════════════════════════════════════════════════════════ -->
    <style>
        /* Hide both navbars — this app shows only the simulator */
        .filter-bar,
        .bottom-nav { display: none !important; }
        /* Reclaim space the navs occupied */
        .content {
            padding-top: 0 !important;
            padding-bottom: 0 !important;
            margin-top: 0 !important;
        }
        /* Hide all tab-content panes; show only the SIM tab */
        .tab-content { display: none !important; }
        .tab-content#tab-sim { display: block !important; }
        /* Standalone-app branding strip */
        .sim-app-bar {
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 10px 16px;
            background: #000;
            border-bottom: 1px solid #1a1a1a;
            font-family: 'Departure Mono', monospace;
            font-size: 11px;
            letter-spacing: 1px;
            color: rgba(255,255,255,0.6);
            position: sticky;
            top: 0;
            z-index: 1000;
        }
        .sim-app-bar a {
            color: var(--green, #00FF55);
            text-decoration: none;
            font-weight: 700;
        }
        .sim-app-bar a:hover { text-decoration: underline; }
    </style>
    <div class="sim-app-bar">
        <span>\U0001F3C0 NBA SIMULATOR</span>
        <a href="/">← MORELLOSIMS</a>
    </div>
    <script>
        // Force SIM tab active on load (defensive — CSS handles display)
        document.addEventListener('DOMContentLoaded', () => {
            document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
            const simTab = document.getElementById('tab-sim');
            if (simTab) simTab.classList.add('active');
            document.title = 'NBA Simulator';
        });
    </script>
"""


def main():
    if not os.path.exists(SRC):
        print(f"ERROR: source not found: {SRC}", file=sys.stderr)
        sys.exit(1)

    os.makedirs(DST_DIR, exist_ok=True)

    with open(SRC, "r") as f:
        html = f.read()

    if "</body>" not in html:
        print(f"ERROR: source has no </body> tag — cannot inject overlay", file=sys.stderr)
        sys.exit(1)

    html = html.replace("</body>", INJECTION + "\n</body>", 1)

    with open(DST, "w") as f:
        f.write(html)

    print(f"OK: wrote {DST} ({os.path.getsize(DST):,} bytes)")


if __name__ == "__main__":
    main()
