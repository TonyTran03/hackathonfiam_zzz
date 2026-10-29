# Sweep 2 — liquidity / capacity

Written 2026-10-28 BEFORE the arm was run. This answers the question Tony
actually asked: what would you consider before buying a stock? First item on
any real desk's checklist is "can I get in and out of this at our size?"

## The arm

  b1_liquidity   = a1_units plus one constraint, nothing else changed.

      |w_i| <= max(minimum_position_weight, days * participation * dolvol_i / NAV)

  Control is a1_units, already run on the design window. The two differ by
  this constraint alone.

## Parameters are inherited, not chosen

    days          = 3.0     from our own 06_final/fconfig.py, max_days_adv
    participation = 0.10    from our own fconfig.py, max_participation

These are the values the team's earlier daily engine already committed to.
Reusing a number we previously published is not a search over that number. No
other value is tried in this sweep; if we ever vary them it becomes Sweep 3
with its own list.

NAV starts at $1bn and compounds with realised net return, so the constraint
tightens as the fund grows, which is the correct direction.

## Measured in advance, on a1_units holdings

    positions above the cap            29.7%
    share of GROSS above the cap       77.9%
    names whose cap is below 0.1%      16.1%

The third number is why the cap is floored at minimum_position_weight: the
engine forces >=0.1% on every selected name, so an unfloored cap is infeasible
for one name in six. Those names are genuinely untradeable at $1bn and the
honest fix is to drop them in selection.py, not to floor them. Flooring is the
minimal change that isolates the constraint; the selection fix is a separate
question and is NOT part of this sweep.

## What this is expected to do, recorded in advance

77.9% of gross currently sits in positions too large for their liquidity, so
this is not a tweak. Expect a materially different portfolio: lower
concentration, more names carrying real weight, and LOWER return, because the
optimizer is currently harvesting alpha in names it could not actually trade.

Prediction: IR falls. If IR RISES, that is suspicious rather than good, and I
will report it as such rather than claiming a free lunch.

A separate observation from the same measurement, not part of this arm: more
than half of a1_units positions sit exactly at the 0.1% floor (5th, 25th and
50th percentiles of |w| are all 0.100%), while the maximum is 5.0%. The book
is far more concentrated than "300 names" suggests. Our earlier daily engine
capped positions at 1.5%; this optimizer allows 5%.

## Success criterion

There is none, because this is not an optimisation. A capacity constraint is a
statement about what we can actually execute. The number it costs is the price
of being honest about size, and that price is the result worth reporting.
