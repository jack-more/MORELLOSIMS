# Picks Contract

`picks/nba.json` and `picks/mlb.json` are the **single source of truth** for the
homepage dispatch log. The dispatch HTML is regenerated deterministically from
these files by `scripts/render_dispatch.py`. **Never hand-edit the dispatch
section of `index.html`** — your edit will be wiped on the next render.

## Lanes
| Writer                        | May write to                                  |
|-------------------------------|------------------------------------------------|
| MLB Pipeline (build_mlb_sim)  | `mlbsim/`, `picks/mlb.json`, `atlas/`         |
| NBA Pipeline (jack-more/nbasim) | `nbasim/`, `picks/nba.json`                  |
| `render_dispatch.py`          | `index.html` (dispatch section only)          |
| Humans                        | anything                                      |

## Schema

Each file is a JSON array of pick objects, sorted by `date` descending.
Append-only — settled picks should never have their `result`/`pl` mutated.

```jsonc
{
  "id":            "2026-04-30-nba-NYK-ATL-spread",  // unique, stable
  "sport":         "nba",                            // "nba" | "mlb"
  "date":          "2026-04-30",                     // ISO YYYY-MM-DD
  "away":          "NYK",
  "home":          "ATL",
  "matchup":       "NYK @ ATL",
  "bet_type":      "spread",                         // "spread" | "ml" | "total"
  "side":          "NYK",                            // team or "OVER"/"UNDER"
  "line":          -2.5,                             // null for ML
  "odds":          -110,                             // null if standard -110 spread
  "pick_text":     "NYK -2.5",                       // display string
  "conf":          10,                               // 1-10
  "units":         50,                               // $PP risked
  "sim_projection": "NYK -9.5",                      // model's spread/total projection
  "sim_edge":      7.0,                              // edge in points (spread) or % (ML)
  "status":        "win",                            // "pending" | "win" | "loss" | "push"
  "result":        "108-105",                        // final score, null if pending
  "pl":            50,                               // $PP gained/lost, null if pending
  "settled_at":    "2026-05-01"                      // ISO date, null if pending
}
```

## Rules
1. **Append-only**: pipelines may add new picks and update `pending` → settled, but never edit settled rows.
2. **One id per pick**: format `{date}-{sport}-{away}-{home}-{bet_type}`. Duplicates → render fails.
3. **Settle, don't replace**: when settling, the pipeline mutates the existing pick in place (`status`, `result`, `pl`, `settled_at`). Don't delete-and-readd.
4. **No HTML in JSON**: this file is data only. Render layer owns presentation.
