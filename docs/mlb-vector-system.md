# MLB Pitcher Vector System

This branch adds the first version of a vector-based matchup layer for MLB SIM.
It does not replace the live pick model yet. It builds the data foundation we
need before changing picks.

## Goal

Move from hard pitcher archetype matching toward calibrated matchup features:

1. Build pitcher vectors from pitch-level Statcast data.
2. Build hitter inverse vectors from how hitters perform against those shapes.
3. Score lineup compatibility with shrinkage.
4. Feed the resulting run means into a simulation engine.
5. Pick only when simulated win probability clears no-vig market probability.

## Why This Exists

The current model can turn noisy matchup splits into oversized run projections.
That makes confidence look stronger than the market edge really is. The vector
layer keeps the useful pitcher-shape idea, but uses continuous features first.
Archetype should become a secondary derived feature.

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

This is an inspection score, not a bet decision.

## Next Implementation Step

The next branch should wire this into a backtest:

1. Build vectors from historical Statcast up to each game date.
2. Score both projected lineups against probable starters.
3. Convert hitter projected xwOBA into team run means.
4. Add bullpen availability and starter leash.
5. Simulate game scores.
6. Compare simulated win probability to no-vig market probability.
7. Publish only buckets that clear the ROI target on holdout data.

## Important Guardrail

Do not let archetype duplicate the same information already captured by pitch
mix, velocity, movement, and location. If archetype remains, use it as a small
residual feature after the direct vector features are accounted for.
