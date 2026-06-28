# MLB Pitcher Vector System

This is the active vector-based matchup layer for MLB SIM. Atlas now scores
pitcher and hitter vectors from recent Statcast data, converts lineup projected
xwOBA into a capped team run adjustment, recomputes win probability and market
filters, then applies the vector agreement gate to the final C8+ board.

## Goal

Move from hard pitcher archetype matching toward calibrated matchup features:

1. Build pitcher vectors from pitch-level Statcast data.
2. Build hitter inverse vectors from how hitters perform against those shapes.
3. Score lineup compatibility with shrinkage.
4. Translate projected lineup xwOBA into team run means.
5. Pick only when the adjusted model clears the market and vector gate.

## Why This Exists

The current model can turn noisy matchup splits into oversized run projections.
That makes confidence look stronger than the market edge really is. The vector
layer keeps the useful pitcher-shape idea, but uses continuous features first.
Archetype is now a secondary context/fallback feature.

## Generated Data

Run:

```bash
python3 scripts/build_mlb_vector_db.py --start 2026-06-01 --end 2026-06-26
```

Outputs:

- `data/mlb_vectors.sqlite`
- `atlas/pitcher_vectors.json`
- `atlas/hitter_inverse_vectors.json`

These files are ignored by git because they are reproducible and can get large.

## Pitcher Vector

Each pitcher vector includes:

- Pitch mix percentages by family
- Velocity bands and family velocity
- IVB/horizontal movement bands
- Release height, side, and extension
- Location shape: heart, zone edge, chase, waste
- K%, BB%, K-BB, CSW, swinging strike
- GB, FB, LD, hard-hit, barrel proxy
- Platoon xwOBA allowed
- Recent 30-day velo, zone, CSW, and xwOBA trends
- Times-through-order penalty
- Expected leash proxy from starts, pitches/start, and batters faced/start

## Hitter Inverse Vector

Each hitter inverse vector includes:

- Baseline xwOBA, wOBA, K%, BB%, hard-hit, barrel proxy
- Skill against pitch families
- Skill against velocity bands
- Skill against movement bands
- Skill against location buckets
- Skill against pitcher handedness
- Recent form deltas

Every split is shrunk toward hitter baseline:

```text
shrunk = sample_weight * split + (1 - sample_weight) * baseline
sample_weight = sample / (sample + prior)
```

This prevents small samples from becoming fake certainty.

## Matchup Score

Use:

```bash
python3 scripts/score_mlb_matchup_vectors.py \
  --pitcher 650911 \
  --hitters 656941,607208,547180
```

The scorer returns a hitter-level xwOBA delta:

```text
pitch_family matchup
+ velocity matchup
+ movement matchup
+ location matchup
+ handedness matchup
+ recent form
```

The live builder uses this same score as an input to team run projection.

## Rolling Backtest

Use:

```bash
python3 scripts/backtest_mlb_vector_matchups.py \
  --start 2026-06-21 \
  --end 2026-06-25 \
  --lookback-days 21
```

The backtest:

- loads settled C8+ MLB picks
- builds rolling vectors using only pitch rows before each pick date
- fetches actual MLB boxscores for starters and lineups
- scores the published side's lineup matchup against the opponent's
- compares vector, projected xwOBA, and combined agreement buckets against ROI

By default it builds focused vectors for only the starters and hitters needed
on each test date. That produces the same scores for those games while keeping
the run fast enough for iteration. Use `--full-vectors` when validating the
whole generated vector database.

The first preview read should focus on `projected_xwoba_edge` and combined
thresholds. Raw `vector_edge` is useful for inspection, but early samples show
the lineup-level projected xwOBA gap is the stronger separator.

The script writes `atlas/vector_backtest_preview.json` by default. Statcast CSV
caches and per-date vector snapshots live under ignored `atlas/` paths.

For larger research passes, prefer a 45-day lookback once enough season data is
available:

```bash
python3 scripts/backtest_mlb_vector_matchups.py \
  --start 2026-05-24 \
  --end 2026-06-26 \
  --lookback-days 45
```

The first larger read showed that 21-day history was too noisy over the full
May/June sample. A 45-day lookback improved the candidate gate:

- `vector_edge >= 0` and `projected_xwoba_edge >= 0.000`: 36 picks, +9.93% ROI
- `vector_edge >= 0` and `projected_xwoba_edge >= 0.010`: 24 picks, +23.04% ROI
- `projected_xwoba_edge >= 0.030`: 16 picks, +33.68% ROI

The live rule currently uses the broad agreement bucket:

- `vector_edge >= 0`
- `projected_xwoba_edge >= 0.000`

That bucket hit the 9% ROI standard in the first 45-day rolling read. Keep
expanding holdout tests before tightening or loosening thresholds.

## Live Run Translation

The live builder starts with the existing Atlas BaseRuns estimate, then applies
a vector xwOBA adjustment before tier, bullpen, park, win probability, and
market filters:

```text
team_vector_delta = projected_lineup_xwOBA - atlas_lineup_wOBA
team_run_delta = clamp(team_vector_delta * 12.0, -1.2, +1.2)
vector_raw_runs = atlas_raw_runs + team_run_delta
final_runs = (vector_raw_runs * opposing_pitcher_tier + bullpen_delta) * park
```

This is deliberately conservative. It lets the new vectors move real run means
without throwing away the existing context stack for lineup components, starter
quality, bullpen exposure, and park.

The card renderer labels vector-scored games as `xwOBA` and `VECTOR 45D`.
Published pick artifacts include:

- `model_mode`
- `away_vector_run_delta`
- `home_vector_run_delta`
- `away_vector_xwoba`
- `home_vector_xwoba`
- `vector_edge`
- `vector_xwoba_edge`
- `vector_gate`

## Remaining Research

The next research pass should improve the projection stack around:

1. Bullpen availability and leverage-rest penalties.
2. Starter leash using pitch count, rest, opener probability, and recent workload.
3. Location/approach-angle hitter splits with stronger shrinkage.
4. No-vig market probability and full score simulation.
5. Larger holdout tests before changing the active 0/0 vector gate.

## Important Guardrail

Do not let archetype duplicate the same information already captured by pitch
mix, velocity, movement, and location. If archetype remains, use it as a small
residual feature after the direct vector features are accounted for.
