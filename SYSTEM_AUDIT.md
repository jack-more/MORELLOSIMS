# System Audit — 2026-05-05

A scripted walk-through of every link in the MORELLOSIMS data pipeline.
What runs, what reads/writes what, what's broken, what's been silently
broken before today and is now fixed.

## The system in one diagram

```
                        MLB                                   NBA
                        ───                                   ───
DAILY DATA REFRESH      atlas-refresh job                     update-lines / refresh-trends
                        ↓ writes atlas/                       ↓ writes nba_pipeline/db/, /data/
                        pitcher_seasons.json                  nba_sim.db
                        pitcher_siera.json                    daily_picks.json
                        pitcher_tiers.json                    pick_log.json
                        hitter_vs_cluster.json                pick_log.json
                        batters.json (NEW: hitter refresh
                        was missing for ~70 days, fixed today)

PICK GENERATION         build_mlb_sim.py                      generate_frontend.py
                        ↓ writes mlbsim/index.html            ↓ writes nba_pipeline/index.html
                          picks/mlb.json                      copied to nbasim/index.html
                        Filter: C:8+ only,                    Filter: confidence outside 35-65
                        |odds| <= 340                         (capture_picks threshold)

PICK CAPTURE            (build_mlb_sim writes the pick        capture_picks.py
                         directly to picks/mlb.json)          ↓ appends nba_pipeline/data/picks.csv
                                                                appends pick_log.json

SETTLEMENT              settle_mlb.py                         grade_picks.py
                        ↓ updates picks/mlb.json status       ↓ updates picks.csv result column
                          via MLB Stats API                   via ESPN scoreboard

CONTRACT TRANSLATION    (no bridge needed — build_mlb_sim     sync_to_picks_json.py
                         writes picks/mlb.json directly)      ↓ rebuilds picks/nba.json from
                                                                picks.csv (filtered to
                                                                tracking_started cutoff)

DISPLAY (HOMEPAGE)      render_dispatch.py
                        ↓ reads picks/{mlb,nba}.json
                        + picks/baselines.json (manual record through 4/30)
                        ↓ writes index.html (DISPATCH:MLB:* and DISPATCH:NBA:* sections)
```

## Bots and lanes (post-cleanup)

| Bot | Workflow | Cron | Writes ONLY |
|---|---|---|---|
| MLB Pipeline Bot | mlb-pipeline.yml | 6×/day | mlbsim/, picks/mlb.json, atlas/ |
| NBA Pipeline Bot | nba-pipeline.yml | 5×/day | nbasim/, sim/, picks/nba.json, nba_pipeline/data, nba_pipeline/db |
| Dispatch Bot | render-dispatch.yml | on workflow_run completion | index.html only |
| (decommissioned) MLB_PitcherChart | jack-more/MLB_PitcherChart Daily MLB Pipeline | DISABLED | — |
| (decommissioned) NBAsim | jack-more/NBAsim Daily NBA SIM Update | DISABLED | — |

## Bugs found, root causes, fixes

### 1. `render_dispatch.py` crashed every cron from May 2 onward

- **Symptom:** site stuck on May 1 data; "no picks today" appearance.
- **Root cause:** `f'{p["odds"]:+d}'` against `p["odds"]` which is a string like `"-326"`. `:+d` requires int.
- **Fix (commit `9ce5e71`):** coerce string-or-int → int before formatting; string fallback.
- **Class:** type-mismatch from undocumented contract — `picks/mlb.json` schema says int but writers used strings.

### 2. `settle_mlb.py` crashed every morning, silently

- **Symptom:** picks/mlb.json had 6 picks dated May 1-5, all `pending`, none ever moving to `win`/`loss`. Hero record stuck.
- **Root cause:** same string-odds bug as #1 — `if ml > 0` against `"-326"` raises TypeError.
- **Compounding cause:** workflow's `python3 ... | tee` swallowed the exit code (`pipefail` not set). "Settle MLB" commits landed daily with zero picks settled. No log alert.
- **Fix (commit `e7d1625` / `05a6e6f`):** coerce odds to int; added `set -o pipefail`. Backfilled 4 missed picks (3-1, +$23).
- **Class:** same bug class as #1; should have been caught by grep'ing the codebase when fixing #1. **It wasn't.**

### 3. `atlas/batters.json` frozen since Feb 22

- **Symptom:** Will Smith and 2,710 other batters showed preseason stats in the Atlas explorer.
- **Root cause:** `refresh_atlas_2026.py` only saved 4 atlas files (all pitcher-related); it loaded `batters.json` for name lookup but never wrote back.
- **Fix (commit `366e0c2` / `8a51713`):** added `compute_hitter_seasons` + `merge_batters` with idempotent `baseline_PA + season_PA_2026` accumulator.
- **Class:** missing functionality, not bug. Pipeline did what it was coded to do; coded to do too little.

### 4. NBAsim and MLB_PitcherChart bots clobbered each other's files

- **Symptom:** every few hours, files in MORELLOSIMS would revert. User had to manually re-apply hero stats. Three commits this week labeled "Re-apply hero stats post-rebase."
- **Root cause:** two cross-repo bots (NBAsim's `daily-update.yml` and MLB_PitcherChart's `daily-mlb.yml`) both checked out MORELLOSIMS via PAT and `git push`'d. They wrote overlapping files (`mlbsim/index.html`, `index.html`) under the same identity (`MLB Pipeline Bot` / `github-actions[bot]`).
- **Fix:** disabled both crons (`gh workflow disable`); migrated NBAsim into MORELLOSIMS as `nba_pipeline/`; introduced three-bot architecture with non-overlapping lanes enforced by `bot-scope-check.yml`.
- **Class:** architectural — two repos racing to be the source of truth for the same files.

### 5. `picks/baselines.json` existed but render_dispatch never read it

- **Symptom:** homepage hero showed `0-0` for both sports after MLB_PitcherChart's `update_mlb_blog.py` was disabled (it had been injecting hardcoded numbers).
- **Root cause:** `picks/baselines.json` (NBA 108-85, MLB 44-19) was committed but `scripts/render_dispatch.py` only loaded `picks/{mlb,nba}.json`.
- **Fix (commit `3d72a0b`):** wired `load_baselines()` into the aggregate. `aggregate(picks, baseline=baseline)` adds wins/losses/risked/pl onto computed totals. Handles empty picks lists (NBA had `[]` initially) without crashing.
- **Class:** dangling contract — file present, schema documented in `_doc`, never consumed.

### 6. NBA picks-contract bridge was missing entirely

- **Symptom:** `picks/nba.json` was `[]`. NBA dispatch block on homepage was empty. NBA hero showed only the baseline.
- **Root cause:** NBAsim writes `nba_pipeline/data/picks.csv` (and `pick_log.json`); the contract says `picks/nba.json`. Nothing translated CSV → JSON.
- **Fix (commit `c3ba33e`):** wrote `nba_pipeline/scripts/sync_to_picks_json.py`. Idempotent — rebuilds `picks/nba.json` from `picks.csv` each run.
- **Class:** missing translation step between two existing schemas.

### 7. The bridge double-counted picks already in baseline

- **Symptom:** NBA hero jumped from 108-85 to 181-134 — wins counted twice.
- **Root cause:** I dumped every row of picks.csv into picks/nba.json, including Feb-April rows that the manual baseline already counted. `baselines.json._doc` literally says "Auto-tracked picks from 2026-05-01 onward live in picks/{nba,mlb}.json. No overlap." I violated my own contract.
- **Fix (commit `765bbd6`):** bridge now reads `tracking_started` from baselines.json (default `2026-05-01`) and skips rows with `date < cutoff`. Result: 109-85 (real).
- **Class:** I didn't read the schema doc I wrote.

### 8. NBA `capture_picks.py` had stopped writing on April 1

- **Symptom:** `picks.csv` last entry dated 2026-04-01. No new picks recorded for 5 weeks despite NBAsim cron firing nominally.
- **Root cause:** confidence threshold filter (>65 or <35) — strong picks fell into the neutral zone for many slates. Plus NBAsim's cron had ALSO been failing or running but never being checked. After cutover to MORELLOSIMS' new pipeline, `grade_picks.py` was finally re-run today and settled the 3 long-pending Apr 1 picks (2-1).
- **Fix:** new pipeline runs grade_picks every cycle; capture continues to filter conservatively. **Threshold is a knob, not a bug**; if you want to capture more picks, set threshold lower in the workflow's capture_picks step.
- **Class:** half silent failure, half configuration choice.

### 9. MLB lineup positions showed `?` for almost every batter

- **Symptom:** lineup matchup page rendered `? · R` instead of `C · R`, `2B · L`, etc.
- **Root cause:** MLB schedule API's `lineups` hydrate returns batters with `id` and `fullName` only — `primaryPosition` lives on the player record, not the lineup record. Code defaulted to `"?"`.
- **Fix (in flight):** added `_bulk_fetch_positions()` — one bulk `/people?personIds=...` call per game, fills a cache, render gracefully omits position when missing instead of showing `?`.
- **Class:** unstated dependency on a hydrate field that the API doesn't include there.

### 10. MLB filter chip text was stale

- **Symptom:** dashboard chip read `C:10 ONLY |ODDS|<200` while the actual code permitted C:8+ at -340.
- **Root cause:** filter constants were updated; display string was hardcoded separately.
- **Fix:** hardcoded display string updated to `C:8+ |ODDS|<340`. Better fix: derive display from constants.
- **Class:** duplicate truth — same fact in code and display, only one updated.

## Recurring patterns across the bugs

- **Type-mismatch from undocumented contract** (#1, #2). `picks/mlb.json` says odds is int; some writers used string. Should: ratify the schema in the writers (write int) OR coerce in the readers (current fix). Either is fine; both should not exist.
- **Pipe-to-tee swallowing exit codes** (#2). Always `set -o pipefail` in CI scripts. **Audit applied: both `mlb-pipeline.yml` build steps now have it; settle did already.**
- **Workflow `continue-on-error: true` masking real failures** (#8). Five steps in `nba-pipeline.yml` are `continue-on-error`. They protect against transient API failures but also let real bugs persist invisibly. Trade-off; current settings retained but flagged.
- **Dangling files** (#5, #6). Committed but never read. Lesson: `grep -rn "filename"` before assuming a file is wired in.

## What's NOT broken (verified working)

- All 19 MORELLOSIMS scripts compile (`py_compile`).
- All 10 nba_pipeline/scripts/ compile.
- `settle_mlb.py` ran clean against current picks; settled 4 picks.
- `grade_picks.py` ran clean; settled 3 long-pending NBA picks.
- `render_dispatch.py` produces valid HTML against current picks.
- `sync_to_picks_json.py` produces correct picks/nba.json (1 entry now: MIN +11 W).
- `refresh_atlas_2026.py` ran against current statcast and updated batters.json.
- All three workflows (`mlb-pipeline.yml`, `nba-pipeline.yml`, `render-dispatch.yml`) registered active in GitHub Actions.
- `bot-scope-check.yml` correctly enforced lanes on every commit today.
- Live site shows MAY 5 on /mlbsim/ and /nbasim/.
- Hero stats show NBA 109-85, +5.5% ROI / MLB 47-20, +6.1% ROI.

## Knobs the user controls

- `picks/baselines.json::tracking_started` — date from which auto-tracked picks count toward the hero. Anything before is the manual baseline.
- `MIN_CONF_PICK` and `MAX_FAV_BY_CONF` in `scripts/build_mlb_sim.py` — MLB pick filter.
- `--threshold` arg to `capture_picks.py` — NBA capture filter.
- `MAX_FAV_BY_CONF` could be lifted into a config file if the user wants to tune without touching code.
