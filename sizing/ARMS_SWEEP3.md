# Sweep 3 — sector concentration

Written 2026-10-28 BEFORE either arm was run.

## The problem

sector_limit is wired into build_constraints and is set to None, so nothing
constrains portfolio sector exposure. Measured on a1_units, design window:

    single-sector net exposure, monthly mean      51.2% of NAV
    median                                        48.1%
    maximum                                       75.3%  (2021-03, GICS 40)

Gross is 200%, so on average about a quarter of the book is an uncancelled
directional sector bet that nobody chose.

ranking.py already regresses the signal on sector dummies, so the SIGNAL is
sector-neutral. The PORTFOLIO is not: the optimiser's risk and cost terms push
it back into sector bets after neutralisation. The same gap exists in the
earlier engine -- 06_final has sector neutralisation in f02_signal.py and no
sector exposure constraint anywhere. PROTOCOL_FINAL.md says "Score:
neutralised on sector, size and beta", which is a statement about the score,
not the book. If a reader takes it as portfolio sector neutrality, that is a
documentation problem in the old deck as well as this one.

## Why a sector limit is a constraint and not a signal

The model scores one stock at a time. It has no representation of the fact
that it is short eighty banks simultaneously. Concentration risk is invisible
to the objective by construction, which is what makes it a constraint rather
than another feature. This is the same test my PE idea failed: that was a
return prediction, and return predictions belong in the 147 features, where
eight valuation ratios already live.

## The arms

  c1_sector_0     a1_units + sector_limit = 0.0
  c2_sector_10    a1_units + sector_limit = 0.10

Control is a1_units, already run on this engine.

## How the threshold was chosen, which was not by IR

There is no inherited number: neither engine has ever constrained sector
exposure, so unlike Sweep 2 I cannot reuse our own published value.

  c1 = 0.0 enforces the property the documentation already claims. It is not
       a number I picked; it is the value implied by "neutralised on sector".

  c2 = 0.10 is a conventional house cap, included ONLY to show what the
       constraint costs as it tightens. It is a reference point, not a
       candidate.

DECISION RULE, FIXED NOW: adopt c1 if it is feasible, because the deck already
claims sector neutrality and the portfolio should do what the deck says. If c1
is infeasible, adopt the tightest feasible limit. The choice is made on
feasibility and on consistency with our own documentation, never on IR. c2's
IR does not enter the decision even if it is the higher of the two.

## Expected result, recorded in advance

Unknown, honestly. Unlike Sweep 2 I have no prior measurement pointing either
way. Sector-neutralising often costs little because it removes risk that
carries no compensation, but it may also remove a real sector timing effect
that the model was capturing. Both arms are reported whatever happens.

One thing I will NOT claim: if IR rises, that is not evidence the constraint
"works". With an IR standard error of 0.53 on 44 months, a rise inside half a
point is noise. The case for this constraint is that an unchosen 51% sector
bet is not a risk we can defend in the room, whatever it earns.

---

## Amendment 1 — 2026-10-28, after c1/c2, before c3/c4

Two values added: sector_limit = 0.02 and 0.05.

PROVENANCE, which is what keeps this from being a search: 0.02 was proposed by
Alex in the group chat ("screened universe, sector +/-2%, mid risk penalty")
BEFORE I ran it and WITHOUT reference to c1 or c2's results. It is a value the
team asked for, not one I picked after seeing an outcome. 0.05 is added only
to fill the cost curve between 0.02 and 0.10, so the team can see what the
constraint costs as it tightens rather than reading two isolated points.

Feasibility was checked in advance, not discovered. The necessary lower bound
on achievable single-sector net exposure is 0.35% mean and 0.70% max across
the 44 design months, so 0.02 is not excluded by the mechanism that makes
c1 (0.0) infeasible in all 44 months. That bound ignores the gross budget, so
it is necessary and not sufficient; if 0.02 turns out infeasible, that is
reported as the result.

The decision rule from the original registration is unchanged and still binds:
adopt the tightest feasible limit, chosen on feasibility and on consistency
with our documented sector neutrality, NEVER on IR. If 0.02 is feasible it
supersedes 0.10 regardless of which has the higher IR.

All four values are reported: 0.0, 0.02, 0.05, 0.10.

---

## Amendment 2 — 2026-10-28, the single full-window run

c3_sector_2 is run once on 2021-01..2026-08, the mandate's full OOS window.

The arm is UNCHANGED: sector_limit = 0.02, every other parameter exactly as
registered. Nothing was adjusted after seeing the design-window result. This
is the one declared run on the full window, made so the result is comparable
with Alex's table, which is reported on 2021-26.

This consumes the 2024-09..2026-08 holdout I had kept. I am doing it because
the team is reporting on 2021-26 and a number on a different window cannot be
compared. The rule that stands: this run is final. No setting is changed
afterwards on the basis of what it returns.
