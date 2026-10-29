"""Shared loaders for the standalone Carbon Arc test.

Reads the licensed Carbon Arc CSVs and the characteristics panel, read-only.
Nothing here writes raw Carbon Arc values anywhere.
"""
from pathlib import Path

import pandas as pd

CA_DIR = Path(r"C:\Users\b0079\Desktop\Carbon Arc")
PANEL = Path(r"C:\Users\b0079\Desktop\chars_final_with_names.parquet")
OUT = Path(__file__).resolve().parent

DATASETS = {
    "foot_traffic": CA_DIR / "foot_traffic_permno.csv",
    "card_spend": CA_DIR / "card_spend_permno.csv",
    "web_traffic": CA_DIR / "web_traffic_permno.csv",
}
LABEL = {"foot_traffic": "Foot traffic", "card_spend": "Card spend", "web_traffic": "Web traffic"}
STATUS = {"foot_traffic": "primary", "card_spend": "descriptive", "web_traffic": "descriptive"}


def load_ca(name):
    d = pd.read_csv(DATASETS[name], usecols=["permno", "date", "value"], parse_dates=["date"])
    d["eom"] = d["date"] + pd.offsets.MonthEnd(0)
    return d[["permno", "eom", "value"]]


def load_panel(cols=("permno", "eom", "gics", "prc", "size_grp", "me", "ret_exc_lead1m", "ret_12_1")):
    p = pd.read_parquet(PANEL, columns=list(cols))
    p["eom"] = pd.to_datetime(p["eom"])
    if "gics" in p:
        p["sector"] = p["gics"].str[:2]
    return p
