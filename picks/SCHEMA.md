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
  "units":         50,                               // $PP risked (NBA/MLB: C10=100)
  "sim_projection": "NYK -9.5",                      // model's spread/total projection
  "sim_edge":      7.0,                              // edge in points (spread) or % (ML)
  "status":        "win",                            // "pending" | "win" | "loss" | "push" | "void" (NBA: kept, never counted; see void_reason)
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
5. **MLB official tracking is C:8+ only**: below-C8 MLB rows may remain in historical JSON for auditability, but renderers and record cards must exclude them.
6. **One door**: read and write these files through `scripts/picks_store.py` (`load_picks` / `save_picks`; public renderers use `load_public_picks`). Never `json.load` them directly.

## Seal mode (`ops/config/monetization.json`, off by default)

With `"seal_mode": true`, a `pending` pick whose game has not started is written
**sealed** — only these fields stay public:

```jsonc
{
  "id": "2026-10-21-mlb-NYY-BOS-ml",   // NBA: "...-spread-sealed-<commitment[:10]>" (real NBA ids end with the side)
  "sport": "mlb", "date": "2026-10-21", "away": "NYY", "home": "BOS", "matchup": "NYY @ BOS",
  "bet_type": "ml", "conf": 9, "units": 50, "game_time": "7:10 PM ET",
  "published_at": "...", "status": "pending",
  "sealed": true,
  "unlocks_at": "2026-10-21T23:10:00Z",               // first pitch / tip
  "commitment": "<sha256 hex>",                        // sha256(canonical(pick) + nonce)
  "sealed_blob": "v1.<AES-256-GCM, key from PICKS_SEAL_KEY>"
}
```

Every pipeline run starts with `scripts/unseal_picks.py`: once the game has
started the record is rewritten in plaintext plus `nonce`, `unsealed_at`,
`seal_keys` (the committed field names) and, for NBA, `sealed_id`.
`python3 scripts/verify_seal.py <id> [--history]` recomputes the commitment;
`--history` shows the commit that published it while sealed. Lifecycle fields
(`status`, `result`, `pl`, `settled_at`, closing line, `last_odds`, `gates_now`,
`void_reason`) are not committed, so settlement does not break verification.
Settlement refuses sealed rows; `scripts/check_seal_guardrail.py` blocks any
pipeline commit that would expose a sealed pick.
