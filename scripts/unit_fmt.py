"""Public-facing units. Picks store stakes and P/L in $PP; 1u = 50 $PP.

  stake_u(50) -> "1u"     stake_u(30) -> "0.6u"    stake_u(100) -> "2u"
  pl_u(45.45) -> "+0.9u"  pl_u(-50)   -> "-1.0u"   pl_u(0)      -> "0.0u"
"""

PP_PER_UNIT = 50.0


def to_u(pp):
    try:
        return float(pp or 0) / PP_PER_UNIT
    except (TypeError, ValueError):
        return 0.0


def stake_u(pp):
    return f"{round(to_u(pp), 2):g}u"


def pl_u(pp):
    u = to_u(pp)
    return "0.0u" if abs(u) < 0.05 else f"{u:+.1f}u"
