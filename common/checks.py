"""Automatic rule-compliance checks.

Two independent halves:

  check_features / check_split   -- did we look at the future?
  check_holdings                 -- does the book obey the trading criteria?

Every check returns Finding objects. FAIL means the submission is invalid as
it stands; WARN means a human should look and be able to justify it.
"""
from dataclasses import dataclass

import pandas as pd

from common import config as C


@dataclass
class Finding:
    level: str      # "FAIL" | "WARN" | "OK"
    check: str
    detail: str

    def __str__(self):
        mark = {"FAIL": "[FAIL]", "WARN": "[WARN]", "OK": "[ ok ]"}[self.level]
        return f"{mark} {self.check}: {self.detail}"


def allowed_features():
    return set(pd.read_csv(C.FACTOR_LIST_CSV)["variable"])


# --------------------------------------------------------------------------
# half one: look-ahead
# --------------------------------------------------------------------------
def check_features(feature_names):
    """The predictor list actually handed to the model."""
    out = []
    feats = list(feature_names)
    allowed = allowed_features()

    if C.TARGET in feats:
        out.append(Finding("FAIL", "target-as-predictor",
                           "'%s' is the answer column and is in the predictor list" % C.TARGET))

    contemporaneous = [f for f in feats if f in C.CONTEMPORANEOUS_RETURNS]
    if contemporaneous:
        out.append(Finding("WARN", "same-month returns used",
                           "%s describe month t, not the future, but the rules say to take "
                           "baseline predictors from factor_char_list.csv "
                           "(ret_1_0 already carries this information)" % contemporaneous))

    extras = [f for f in feats
              if f not in allowed and f not in C.CONTEMPORANEOUS_RETURNS and f != C.TARGET]
    if extras:
        shown = extras[:8]
        out.append(Finding("WARN", "predictors outside the supplied list",
                           "%d not in factor_char_list.csv: %s%s -- allowed only if documented "
                           "as external data with a source and an availability date"
                           % (len(extras), shown, "..." if len(extras) > 8 else "")))

    dupes = sorted({f for f in feats if feats.count(f) > 1})
    if dupes:
        out.append(Finding("FAIL", "duplicate predictors", str(dupes)))

    if not out:
        out.append(Finding("OK", "predictor list",
                           "%d predictors, all from the supplied list" % len(feats)))
    return out


def check_split(df, train_mask, val_mask, test_mask, fold_label=""):
    """Splits must be assigned by the TARGET month, not the feature month."""
    out = []
    tag = " [%s]" % fold_label if fold_label else ""
    tm = df["target_month"]

    for name, mask in [("train", train_mask), ("val", val_mask), ("test", test_mask)]:
        if mask.sum() == 0:
            out.append(Finding("FAIL", "empty split" + tag, "%s has no rows" % name))
            return out

    test_lo = tm[test_mask].min()
    for name, mask in [("train", train_mask), ("val", val_mask)]:
        bad = tm[mask] >= test_lo
        if bad.any():
            months = sorted(tm[mask][bad].unique())
            out.append(Finding("FAIL", "future answers in %s%s" % (name, tag),
                               "%d rows with target months %s%s at or after the test period "
                               "start %s" % (bad.sum(), months[:4],
                                             "..." if len(months) > 4 else "", test_lo)))

    for a, b, ma, mb in [("train", "val", train_mask, val_mask),
                         ("train", "test", train_mask, test_mask),
                         ("val", "test", val_mask, test_mask)]:
        overlap = int((ma & mb).sum())
        if overlap:
            out.append(Finding("FAIL", "%s/%s overlap%s" % (a, b, tag),
                               "%d shared rows" % overlap))

    # dropping unanswered rows inside the test window silently restricts the
    # universe to the stocks that turned out to still be there
    missing = int(df.loc[test_mask, C.TARGET].isna().sum())
    if missing:
        out.append(Finding("WARN", "unanswered test rows" + tag,
                           "%d test rows have no realized return; excluding them lets the "
                           "outcome decide the universe -- predict for all of them and handle "
                           "the gap in the portfolio step" % missing))

    if not any(f.level == "FAIL" for f in out):
        out.append(Finding("OK", "split" + tag,
                           "train %s..%s | val %s..%s | test %s..%s"
                           % (tm[train_mask].min(), tm[train_mask].max(),
                              tm[val_mask].min(), tm[val_mask].max(),
                              tm[test_mask].min(), tm[test_mask].max())))
    return out


def check_fit_rows(fit_mask, df, train_end, fold_label=""):
    """Scalers, medians and imputers must be fitted on training months only."""
    tag = " [%s]" % fold_label if fold_label else ""
    late = df.loc[fit_mask, "target_month"] > train_end
    if late.any():
        return [Finding("FAIL", "preprocessing fitted on future data" + tag,
                        "%d of the rows used to fit the transform have target months after %s"
                        % (late.sum(), train_end))]
    return [Finding("OK", "preprocessing fit window" + tag,
                    "fitted on months up to %s" % train_end)]


# --------------------------------------------------------------------------
# half two: the trading criteria
# --------------------------------------------------------------------------
def check_beta_neutrality(stats):
    """Is the book neutral, or only dollar neutral?

    The rules impose no numeric limit on beta, so nothing here is a rule
    breach. They do say plainly that a dollar-neutral book which is long
    high-beta names and short low-beta names is "a levered long position
    wearing a disguise", and that they will read a realised beta far from zero
    as a failure of the mandate rather than a stylistic choice. Dollar
    neutrality is checked elsewhere and is not evidence of this.

    `stats` needs a `beta_net` column: sum(w_i * beta_i) for each month.
    Thresholds come from config.TEAM, not config.COMPETITION.
    """
    if "beta_net" not in stats.columns or stats["beta_net"].isna().all():
        return [Finding("WARN", "beta neutrality",
                        "no beta column available, so the book's market exposure "
                        "was not checked -- dollar neutrality is not the same thing")]

    t = C.TEAM
    b = stats["beta_net"].dropna()
    worst_month = b.abs().idxmax()
    worst = b.loc[worst_month]

    over_fail = b[b.abs() > t["beta_net_fail"]]
    over_warn = b[b.abs() > t["beta_net_warn"]]

    if len(over_fail):
        return [Finding("FAIL", "beta neutrality (house standard, not a rule)",
                        "%d of %d months carry a beta-weighted net beyond %+.2f "
                        "(worst %+.3f in %s) -- this is a directional book"
                        % (len(over_fail), len(b), t["beta_net_fail"],
                           worst, worst_month))]
    if len(over_warn):
        return [Finding("WARN", "beta neutrality (house standard, not a rule)",
                        "%d of %d months carry a beta-weighted net beyond %+.2f "
                        "(worst %+.3f in %s) -- justify it or neutralise it"
                        % (len(over_warn), len(b), t["beta_net_warn"],
                           worst, worst_month))]
    return [Finding("OK", "beta neutrality",
                    "beta-weighted net within %+.2f every month "
                    "(mean %+.3f, worst %+.3f in %s)"
                    % (t["beta_net_warn"], b.mean(), worst, worst_month))]


def check_holdings(holdings, panel=None):
    """`holdings`: one row per stock-month, columns permno / target_month / weight.

    An optional `beta` column turns on the beta-neutrality check. Supply the
    beta that was known at formation time, not one estimated over the test
    period, or the check is answering a different question.

    Weights are a share of capital: positive long, negative short.
    Returns (findings, per-month statistics).
    """
    out = []
    k = C.COMPETITION
    h = holdings.copy()
    h["weight"] = pd.to_numeric(h["weight"], errors="coerce")

    if h["weight"].isna().any():
        out.append(Finding("FAIL", "unusable weights",
                           "%d rows are blank or non-numeric" % h["weight"].isna().sum()))
        h = h.dropna(subset=["weight"])

    zero = int((h["weight"] == 0).sum())
    if zero:
        out.append(Finding("WARN", "zero weights", "%d rows carry no position" % zero))
        h = h[h["weight"] != 0]

    dup = int(h.duplicated(["target_month", "permno"]).sum())
    if dup:
        out.append(Finding("FAIL", "duplicate positions",
                           "%d stock-months appear more than once" % dup))

    by_month = h.groupby("target_month")["weight"]
    stats = pd.DataFrame({
        "n": by_month.size(),
        "gross": by_month.apply(lambda w: w.abs().sum()),
        "net": by_month.sum(),
        "n_long": by_month.apply(lambda w: (w > 0).sum()),
        "n_short": by_month.apply(lambda w: (w < 0).sum()),
        "max_abs": by_month.apply(lambda w: w.abs().max()),
    })

    if "beta" in h.columns:
        b = pd.to_numeric(h["beta"], errors="coerce")
        missing = int(b.isna().sum())
        if missing:
            out.append(Finding("WARN", "beta coverage",
                               "%d of %d positions have no beta; the beta-weighted "
                               "net treats them as zero exposure, which understates it"
                               % (missing, len(h))))
        stats["beta_net"] = (h["weight"] * b.fillna(0.0)).groupby(
            h["target_month"]).sum()

    bad = stats[(stats["n"] < k["min_positions"]) | (stats["n"] > k["max_positions"])]
    if len(bad):
        out.append(Finding("FAIL", "position count",
                           "%d of %d months outside %d-%d names (e.g. %s: %d)"
                           % (len(bad), len(stats), k["min_positions"], k["max_positions"],
                              bad.index[0], int(bad["n"].iloc[0]))))

    tol = 1e-9
    bad = stats[stats["gross"] > k["max_gross"] + tol]
    if len(bad):
        out.append(Finding("FAIL", "gross exposure",
                           "%d months above %.0f%% (worst %.1f%% in %s)"
                           % (len(bad), k["max_gross"] * 100,
                              bad["gross"].max() * 100, bad["gross"].idxmax())))

    lo, hi = k["net_band"]
    bad = stats[(stats["net"] < lo - tol) | (stats["net"] > hi + tol)]
    if len(bad):
        out.append(Finding("FAIL", "net exposure",
                           "%d months outside %+.0f%%..%+.0f%% (worst %+.1f%% in %s)"
                           % (len(bad), lo * 100, hi * 100,
                              bad["net"].abs().max() * 100, bad["net"].abs().idxmax())))

    one_sided = stats[(stats["n_long"] == 0) | (stats["n_short"] == 0)]
    if len(one_sided):
        out.append(Finding("FAIL", "not long/short",
                           "%d months have only one leg" % len(one_sided)))

    expected = list(pd.period_range(k["oos_start"], k["oos_end"], freq="M").astype(str))
    have = set(stats.index)
    gaps = [m for m in expected if m not in have]
    if gaps:
        out.append(Finding("FAIL", "missing months",
                           "%d evaluation months have no holdings: %s%s"
                           % (len(gaps), gaps[:6], "..." if len(gaps) > 6 else "")))
    stray = sorted(have - set(expected))
    if stray:
        out.append(Finding("WARN", "months outside the window", str(stray[:6])))

    concentrated = stats[stats["max_abs"] > 0.10]
    if len(concentrated):
        out.append(Finding("WARN", "single-position size",
                           "%d months hold a name above 10%% of capital (max %.1f%%)"
                           % (len(concentrated), stats["max_abs"].max() * 100)))

    out.extend(check_beta_neutrality(stats))

    if panel is not None:
        key = panel[["permno", "target_month"]].drop_duplicates().assign(_tradable=1)
        merged = h.merge(key, on=["permno", "target_month"], how="left")
        orphan = int(merged["_tradable"].isna().sum())
        if orphan:
            out.append(Finding("FAIL", "untradable positions",
                               "%d stock-months are not in the supplied panel" % orphan))

    if not any(f.level == "FAIL" for f in out):
        out.append(Finding("OK", "trading criteria",
                           "%d months | names %d-%d | gross %.0f%% avg, %.0f%% max | "
                           "net %+.1f%%..%+.1f%%"
                           % (len(stats), int(stats["n"].min()), int(stats["n"].max()),
                              stats["gross"].mean() * 100, stats["gross"].max() * 100,
                              stats["net"].min() * 100, stats["net"].max() * 100)))
    return out, stats


def report(findings, title=""):
    if title:
        print("\n--- %s ---" % title)
    for f in findings:
        print(f)
    fails = sum(f.level == "FAIL" for f in findings)
    warns = sum(f.level == "WARN" for f in findings)
    return fails, warns
