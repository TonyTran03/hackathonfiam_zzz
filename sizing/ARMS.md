# Sweep 1 — pre-registered arm list

Written 2026-10-28 BEFORE any arm was run. Six arms, fixed below. Every arm
is reported in comparison.csv whatever it does. No arm is added after seeing
a result; a seventh idea becomes Sweep 2 with its own list.

## Windows

    design   2021-01 .. 2024-08   (44 months)   all sweeping happens here
    holdout  2024-09 .. 2026-08   (24 months)   UNTOUCHED until one arm is frozen

The holdout is run exactly once, on one frozen arm. If we run it twice it is
not a holdout any more and the deck says so.

## Why these parameters are not "tuned"

The IR standard error on 68 months is 0.43 (bootstrap, oliver_base). Picking
the best of N arms by IR buys +0.50 at N=5 and +0.66 at N=10 from noise alone.
So no arm below has a parameter chosen by IR. Each is fixed by either a
measurement or an external target:

  score_scale = 0.004339   MEASURED. Cross-sectional slope of realised return
                           on score, 68 months, oliver_base holdings:
                           +0.4339% per unit of score, t = +2.41, rank IC 0.062.
                           The current objective implies 1.0, i.e. one unit of
                           score = 100% monthly return. It is wrong by 230x.

  risk_penalty = 0.4339    DERIVED, not tuned. The objective
                           mu'w - lambda w'Sw has the same maximiser when mu
                           and lambda are scaled together, so scaling the score
                           by s and risk_penalty by s reproduces the CURRENT
                           portfolio exactly, while making the cost term 230x
                           more important relative to alpha. a1 is therefore
                           the current risk appetite with an honest cost.

  cost_penalty = 1.0       TRUE, not tuned. At score_scale = 0.004339 this
                           charges exactly the stated 20bp and no more.

a2/a3 move risk_penalty by a factor of 2 either way. These are reported with
their ACHIEVED VOLATILITY and selected on volatility if selected at all, never
on IR. Choosing a risk dial by target vol is selection on a non-outcome and
does not inflate the IR.

## The arms

  a0_control    score_scale 1.0      risk 100.0    cost 1.0   beta 0.0   turnover None
                The current objective on a screened universe. Baseline.

  a1_units      score_scale 0.004339 risk 0.4339   cost 1.0   beta 0.0   turnover None
                Same risk appetite, honest cost. The single mechanism fix.

  a2_risk_lo    score_scale 0.004339 risk 0.2170   cost 1.0   beta 0.0   turnover None
  a3_risk_hi    score_scale 0.004339 risk 0.8678   cost 1.0   beta 0.0   turnover None
                Risk dial +/- 2x. Report achieved vol.

  a4_turnover   score_scale 0.004339 risk 0.4339   cost 1.0   beta 0.0   turnover 1.0
                a1 plus a hard two-way turnover cap of 100%/month.

  a5_beta_off   score_scale 0.004339 risk 0.4339   cost 1.0   beta None  turnover None
                a1 with the hard beta constraint REMOVED. Diagnostic: the
                constraint binds estimated beta to 5e-12 while realised beta is
                -0.118. This measures what it is actually buying us.

## Prediction, recorded in advance

a1 cuts turnover sharply versus a0 (the cost term becomes 230x more
significant) at some cost in gross return. If a1 does NOT cut turnover, the
units diagnosis is wrong and I report that.

a5 is expected to show the hard beta constraint costs IR while delivering
little realised beta control.
