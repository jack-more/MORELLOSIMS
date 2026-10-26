"""A player's second impact read next to time-decay RAPM (player_rapm), the same for every reader.

Every player's impact is time-decay RAPM averaged with a second measure, so one noisy
window is half the read. That measure is LEBRON. A player with no LEBRON missed last
season, and his time-decay RAPM then leans hardest on his last stretch before it:
Haliburton reads +1.9 against +5.5 over three years. For him the second read is his
3-year RAPM, its gap to the time-decay total split evenly between offense and defense
(nbarapm publishes no 3-year split), so the average lands halfway between the two.
"""


def second_read(td_off, td_def, td_total, lb_off, lb_def, rapm_3yr):
    """(offense, defense) per 100 to average with the time-decay split, or (None, None)."""
    if lb_off is not None or lb_def is not None:
        return lb_off, lb_def
    if rapm_3yr is None or td_total is None or td_off is None or td_def is None:
        return None, None
    gap = (float(rapm_3yr) - float(td_total)) / 2
    return float(td_off) + gap, float(td_def) + gap
