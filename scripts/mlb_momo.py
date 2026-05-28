"""MOMO/MOMI scoring helpers for MLB SIM."""


def woba_to_output_score(woba):
    """Convert projected wOBA into the main 1-99 matchup-output scale."""
    w = max(0.0, float(woba or 0.0))
    if w >= 0.400:
        return min(99, 90 + int((w - 0.400) / 0.030 * 9))
    if w >= 0.370:
        return 80 + int((w - 0.370) / 0.030 * 9)
    if w >= 0.340:
        return 70 + int((w - 0.340) / 0.030 * 9)
    if w >= 0.310:
        return 60 + int((w - 0.310) / 0.030 * 9)
    if w >= 0.270:
        return 50 + int((w - 0.270) / 0.040 * 9)
    return max(40, 40 + int((w - 0.200) / 0.070 * 9))


def matchup_swing_to_momo(base_woba, vs_woba):
    """Map pitcher-DNA output to MOMO without erasing elite baselines.

    MOMO is Optimized Matchup Output, so the score is anchored by the
    absolute pitcher-DNA projection. The hitter's own baseline and the
    matchup swing still matter, but they behave as modifiers.
    """
    base = float(base_woba or 0.0)
    vs = float(vs_woba or 0.0)
    base_score = woba_to_output_score(base)
    matchup_score = woba_to_output_score(vs)
    swing_adjust = (vs - base) * 80.0
    score = matchup_score * 0.75 + base_score * 0.25 + swing_adjust
    return max(1, min(99, int(round(score))))


def momentum_to_momi(momo, streak, last7_avg):
    """Apply live hitting form to MOMO and return a 1-99 momentum impact."""
    momo = max(1, min(99, int(round(float(momo or 50)))))
    streak = int(streak or 0)
    last7 = float(last7_avg or 0.0)

    adjustment = 0.0
    if streak >= 2:
        adjustment += 2.0 + streak * 1.4 + max(0, streak - 5) * 0.8 + max(0, streak - 10) * 1.0
    elif streak == 1:
        adjustment += 1.0
    else:
        adjustment -= 4.0

    if last7 > 0:
        adjustment += max(-12.0, min(15.0, (last7 - 0.250) * 55.0))

    return max(1, min(99, int(round(momo + adjustment))))


def ms_class(ms):
    if ms >= 85:
        return "ms-elite"
    if ms >= 70:
        return "ms-favorable"
    if ms >= 50:
        return "ms-neutral"
    return "ms-tough"


def woba_class(base, vs):
    diff = vs - base
    if diff > 0.03:
        return "hot"
    if diff < -0.03:
        return "cold"
    return "neutral"
