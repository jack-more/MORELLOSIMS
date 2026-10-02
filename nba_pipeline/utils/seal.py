"""Bridge to the repo-wide seal-mode store (scripts/picks_store.py).

NBA scripts run with nba_pipeline/ as their import root; this appends the
repo's scripts/ dir (appended, so nothing in nba_pipeline is shadowed) and
re-exports the store.
"""

import os
import sys

_SCRIPTS = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "scripts")
if _SCRIPTS not in sys.path:
    sys.path.append(_SCRIPTS)

import picks_store as store  # noqa: E402,F401
