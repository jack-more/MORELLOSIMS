"""
Generate pitcher tier assignments for all pitcher-seasons.

Reads:  atlas/pitcher_seasons.json, atlas/pitcher_siera.json, atlas/clusters.json
Writes: atlas/pitcher_tiers.json

Each pitcher-season gets assigned T1_Apex / T2_Core / T3_Standard / T4_Fringe
based on SIERA z-score within their archetype cluster.

SIERA (Skill-Interactive ERA) captures K%, BB%, and GB/FB ratio — rewarding
both strikeout pitchers AND contact managers like Logan Webb.

Tier multipliers scale by archetype dominance (SIERA-based instead of whiff-based).
"""

import numpy as np
from collections import defaultdict
from common import (
    load_atlas, save_atlas, assign_tier,
    BASE_TIER_MULTIPLIERS, BAYESIAN_PRIOR_WEIGHT,
)


def compute_effective_multiplier_siera(base_mult, archetype_siera, league_avg_siera):
    """
    Scale the base tier multiplier by archetype dominance (SIERA-based).

    Lower SIERA = more dominant archetype → amplified tier effects.
    dominance = league_avg / archetype_avg (inverted because lower SIERA = better)
    """
    if archetype_siera == 0 or league_avg_siera == 0:
        return base_mult
    # Invert: lower SIERA = higher dominance
    dominance = league_avg_siera / archetype_siera
    return 1.0 + (base_mult - 1.0) * dominance


def main():
    pitcher_seasons = load_atlas('pitcher_seasons.json')
    clusters_meta = load_atlas('clusters.json')

    # Load SIERA data
    try:
        siera_data = load_atlas('pitcher_siera.json')
    except FileNotFoundError:
        print("ERROR: pitcher_siera.json not found. Run SIERA fetch first.")
        return

    print(f"Loaded {len(pitcher_seasons)} pitcher-seasons")
    print(f"Loaded {len(clusters_meta)} archetype clusters")
    print(f"Loaded {len(siera_data)} SIERA records")

    # Build SIERA index: pitcher_id_year → siera value
    siera_idx = {}
    for key, rec in siera_data.items():
        pid = rec.get("pitcher")
        yr = rec.get("game_year")
        if pid and yr:
            siera_idx[(pid, yr)] = rec.get("siera")

    # Match SIERA to pitcher-seasons
    matched = 0
    unmatched = 0
    for ps in pitcher_seasons:
        pid = ps['pitcher']
        yr = ps['game_year']
        siera = siera_idx.get((pid, yr))
        if siera is not None:
            ps['siera'] = siera
            matched += 1
        else:
            ps['siera'] = None
            unmatched += 1

    print(f"SIERA matched: {matched}, unmatched: {unmatched}")

    # ── 1. Group by cluster ──────────────────────────────────────────────
    by_cluster = defaultdict(list)
    for ps in pitcher_seasons:
        if ps['siera'] is not None:
            by_cluster[ps['cluster']].append(ps)

    # ── 2. Global pooled stdev (for Bayesian shrinkage) ──────────────────
    all_siera = [ps['siera'] for ps in pitcher_seasons if ps['siera'] is not None]
    global_mean = np.mean(all_siera)
    global_stdev = np.std(all_siera, ddof=1)
    league_avg_siera = global_mean

    print(f"\nGlobal SIERA stats: mean={global_mean:.4f}, stdev={global_stdev:.4f}")

    # ── 3. Assign tiers per cluster ──────────────────────────────────────
    tiers_output = {}
    cluster_summaries = {}

    for cluster_id, records in sorted(by_cluster.items()):
        sieras = [r['siera'] for r in records]
        n = len(sieras)
        if n == 0:
            continue

        cluster_mean = np.mean(sieras)
        cluster_stdev = np.std(sieras, ddof=1) if n > 1 else global_stdev

        # Bayesian shrinkage: blend cluster stdev with global stdev
        effective_stdev = (
            (n * cluster_stdev + BAYESIAN_PRIOR_WEIGHT * global_stdev)
            / (n + BAYESIAN_PRIOR_WEIGHT)
        )

        # Archetype SIERA for dominance calc
        arch_siera = cluster_mean

        tier_counts = defaultdict(int)

        for r in records:
            # INVERT z-score: lower SIERA = higher z (better pitcher)
            z = -(r['siera'] - cluster_mean) / effective_stdev if effective_stdev > 0 else 0.0
            tier = assign_tier(z)
            base_mult = BASE_TIER_MULTIPLIERS[tier]
            eff_mult = compute_effective_multiplier_siera(base_mult, arch_siera, league_avg_siera)

            key = f"{r['pitcher']}_{r['game_year']}"
            tiers_output[key] = {
                'pitcher': r['pitcher'],
                'player_name': r['player_name'],
                'game_year': r['game_year'],
                'cluster': cluster_id,
                'archetype': r.get('archetype', ''),
                'siera': round(r['siera'], 2),
                'whiff_rate': round(r.get('whiff_rate', 0), 4),
                'z_score': round(z, 4),
                'tier': tier,
                'base_multiplier': base_mult,
                'effective_multiplier': round(eff_mult, 4),
                'archetype_dominance': round(league_avg_siera / arch_siera, 4) if arch_siera > 0 else 1.0,
            }
            tier_counts[tier] += 1

        cluster_summaries[cluster_id] = {
            'n': n,
            'mean_siera': round(cluster_mean, 4),
            'stdev': round(cluster_stdev, 4),
            'effective_stdev': round(effective_stdev, 4),
            'dominance': round(league_avg_siera / arch_siera, 4) if arch_siera > 0 else 1.0,
            'tiers': dict(tier_counts),
        }

    # ── 4. Save output ───────────────────────────────────────────────────
    save_atlas('pitcher_tiers.json', tiers_output)

    # ── 5. Print summary ─────────────────────────────────────────────────
    total = len(tiers_output)
    overall_counts = defaultdict(int)
    for v in tiers_output.values():
        overall_counts[v['tier']] += 1

    print(f"\n{'='*60}")
    print(f"PITCHER TIER SUMMARY (SIERA-BASED)")
    print(f"{'='*60}")
    print(f"Total pitcher-seasons tiered: {total}")
    for t in ['T1_Apex', 'T2_Core', 'T3_Standard', 'T4_Fringe']:
        c = overall_counts[t]
        print(f"  {t:15s}: {c:5d} ({100*c/total:5.1f}%)")

    print(f"\n{'─'*60}")
    print(f"PER-CLUSTER BREAKDOWN")
    print(f"{'─'*60}")
    print(f"{'Cluster':<8} {'N':>5} {'SIERA':>6} {'StDev':>6} {'Dom':>5} │ {'T1':>4} {'T2':>4} {'T3':>4} {'T4':>4}")
    print(f"{'─'*8} {'─'*5} {'─'*6} {'─'*6} {'─'*5} ┼ {'─'*4} {'─'*4} {'─'*4} {'─'*4}")

    for cid in sorted(cluster_summaries.keys()):
        s = cluster_summaries[cid]
        t = s['tiers']
        print(
            f"{cid:<8} {s['n']:>5} {s['mean_siera']:>6.2f} {s['effective_stdev']:>6.4f} {s['dominance']:>5.2f} │ "
            f"{t.get('T1_Apex',0):>4} {t.get('T2_Core',0):>4} {t.get('T3_Standard',0):>4} {t.get('T4_Fringe',0):>4}"
        )

    # Spot-check key pitchers
    print(f"\n{'─'*60}")
    print(f"KEY PITCHER CHECK")
    print(f"{'─'*60}")
    check = ['Webb, Logan', 'Fried, Max', 'Skubal, Tarik', 'Sale, Chris', 'Cole, Gerrit']
    for name in check:
        matches = [(k,v) for k,v in tiers_output.items() if name in v.get('player_name', '') and v['game_year'] >= 2023]
        for k, v in sorted(matches, key=lambda x: x[1]['game_year']):
            print(
                f"  {v['player_name']:25s} ({v['game_year']}) "
                f"{v['archetype']:15s} SIERA={v['siera']:.2f} "
                f"z={v['z_score']:+.2f} tier={v['tier']} mult={v['effective_multiplier']:.3f}"
            )


if __name__ == '__main__':
    main()
