"""Stage 5h (optional) -- which characteristics the traded model actually uses.

Deck pages 2 and 8 ask which predictive signals form the strategy and which
fundamental signals drive the performance. Stage 3 fits the trees but does not
keep them, so this refits the gradient-boosted model for each fold exactly as
stage 3 does (same table, same grid, same early stopping on the same
validation block) and records split-gain importance. It changes nothing that
is traded; it only reports what the forecast is made of.

    python 04_backtest_scoring/12_feature_importance.py

Writes 05_submission/feature_importance.csv (gain share per characteristic,
per fold and averaged) and 05_submission/figures/feature_importance.png.
"""
import importlib.util
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common import config as C

# stage files start with a digit, so load stage 3 by path to reuse its recipe
_spec = importlib.util.spec_from_file_location(
    "stage3", C.ROOT / "02_prediction" / "03_train_predict.py")
S3 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(S3)

OUT_CSV = C.ROOT / "05_submission" / "feature_importance.csv"
OUT_PNG = C.ROOT / "05_submission" / "figures" / "feature_importance.png"

# Coarse families for the deck narrative, from the JKP characteristic names.
FAMILIES = [
    ("past returns / momentum", ("ret_", "resff3", "seas_", "prc_highprc")),
    ("risk / volatility / beta", ("beta", "ivol", "rvol", "rmax", "rskew", "iskew", "coskew", "corr_", "ni_ivol", "earnings_variability")),
    ("liquidity / trading", ("dolvol", "turnover", "zero_trades", "ami_", "bidaskhl", "prc", "market_equity")),
    ("investment / growth", ("_gr1", "_gr2", "_gr3", "capex_abn", "chcsho", "emp_gr", "sale_emp")),
    ("profitability", ("gp_", "op_", "ope_", "ebit", "ni_", "niq_", "ocf", "cop_", "f_score", "qmj", "pi_nix", "opex", "dgp_dsale", "dsale_", "sale_bev", "at_turnover")),
    ("valuation", ("_me", "be_me", "at_me", "intrinsic", "eq_dur", "bev_mev", "ebitda_mev", "eqnpo", "eqpo", "eqnetis", "netis", "dbnetis", "div12m")),
    ("accruals / quality / distress", ("accrual", "o_score", "z_score", "kz_index", "mispricing", "age", "tangibility", "cash_at", "aliq", "at_be", "nfna", "lnoa", "noa", "ncoa", "ncol", "coa_", "col_", "cowc", "fnl", "lti", "sti", "tax_gr", "rd_", "rd5")),
]


def family(name):
    for label, keys in FAMILIES:
        if any(k in name for k in keys):
            return label
    return "other"


def main():
    features = pd.read_csv(C.FACTOR_LIST_CSV)["variable"].tolist()
    sparse = pd.read_parquet(S3.SPARSE_FILE, columns=["permno", "target_month", C.TARGET] + features)
    tm = sparse["target_month"]
    answered = sparse[C.TARGET].notna()

    shares = {}
    for train_end, val_start, val_end, test_start, test_end in C.training_schedule():
        train = (tm <= train_end) & answered
        val = (tm >= val_start) & (tm <= val_end) & answered
        ytr = S3.demean_and_clip(sparse.loc[train, C.TARGET].values, tm[train])
        yva = S3.demean_and_clip(sparse.loc[val, C.TARGET].values, tm[val])
        Xtr, Xva = sparse.loc[train, features], sparse.loc[val, features]
        best, best_mse = None, np.inf
        for cfg in S3.GBM_GRID:
            import lightgbm as lgb
            m = lgb.LGBMRegressor(**S3.GBM_FIXED, **cfg)
            m.fit(Xtr, ytr, eval_set=[(Xva, yva)], eval_metric="l2",
                  callbacks=[lgb.early_stopping(S3.GBM_EARLY_STOP, verbose=False)])
            mse = np.mean((yva - m.predict(Xva)) ** 2)
            if mse < best_mse:
                best, best_mse = m, mse
        gain = best.booster_.feature_importance(importance_type="gain")
        shares[test_start[:4]] = pd.Series(gain / gain.sum(), index=features)
        print("fold %s: %d trees, top 5 by gain: %s"
              % (test_start[:4], best.best_iteration_,
                 ", ".join("%s %.1f%%" % (k, 100 * v)
                           for k, v in shares[test_start[:4]].nlargest(5).items())), flush=True)

    table = pd.DataFrame(shares)
    table["mean_gain_share"] = table.mean(axis=1)
    table["family"] = [family(f) for f in table.index]
    table = table.sort_values("mean_gain_share", ascending=False)
    table["rank"] = np.arange(1, len(table) + 1)
    table.index.name = "characteristic"
    table.to_csv(OUT_CSV)

    print("\nTOP 20 CHARACTERISTICS BY SPLIT GAIN, averaged over the six folds")
    print("  (an average characteristic would take %.2f%%)" % (100 / len(features)))
    for name, r in table.head(20).iterrows():
        print("  %2d  %-22s %5.2f%%   %s" % (r["rank"], name, 100 * r["mean_gain_share"], r["family"]))
    fam = table.groupby("family")["mean_gain_share"].sum().sort_values(ascending=False)
    print("\nBY FAMILY (share of total gain)")
    for k, v in fam.items():
        print("  %-32s %5.1f%%" % (k, 100 * v))

    top = table.head(20).iloc[::-1]
    fig, ax = plt.subplots(figsize=(7, 5))
    ax.barh(top.index, 100 * top["mean_gain_share"], color="#1f4e79")
    ax.set_xlabel("share of split gain, %, mean of six annual refits")
    ax.set_title("Top 20 characteristics in the traded tree model")
    ax.spines["top"].set_visible(False); ax.spines["right"].set_visible(False)
    OUT_PNG.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT_PNG, dpi=130, bbox_inches="tight")
    print("\nwrote %s and %s" % (OUT_CSV.relative_to(C.ROOT), OUT_PNG.relative_to(C.ROOT)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
