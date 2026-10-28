"""Sample of large firms that left our panel before 2024, for the CA0032 8-K coverage card.

The supplied 8-K file is missing almost every company that exits (round one: 13% of later-exiting
firms have any 8-K in it, against 93% of survivors). This draws the firms an agent looks up by
name in Carbon Arc's CA0032 to see whether EDGAR has the 8-Ks the supplied file lacks.

Exited = last panel month between 2015-01 and 2023-12. Large = me >= US$1bn in that last month.
The name is the latest labelled one, at most a month before exit. A fixed seed draws N per exit
year so every year is represented.

    python 06_final/carbonarc/dd_sample_exited.py --per-year 3
"""
import argparse
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]


def exited(chars, min_me=1000., before='2024-01-01'):
    c = pd.read_parquet(chars, columns=['permno', 'gvkey', 'eom', 'me', 'ticker', 'company_name', 'gics'])
    c['eom'] = pd.to_datetime(c.eom)
    c = c.sort_values(['permno', 'eom'])
    last = c.groupby('permno').tail(1).set_index('permno')
    named = c[c.company_name.notna()].groupby('permno').tail(1).set_index('permno')
    out = last[['gvkey', 'eom', 'me', 'gics']].rename(columns={'eom': 'last_panel_month', 'me': 'me_last_million'})
    out = out.join(named[['eom', 'ticker', 'company_name']].rename(columns={'eom': 'name_month'}))
    out = out[(out.last_panel_month < before) & (out.me_last_million >= min_me)]
    return out.reset_index()


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--chars', type=Path, default=ROOT / '01_data/raw/chars_final_with_names.parquet')
    p.add_argument('--per-year', type=int, default=3)
    p.add_argument('--seed', type=int, default=2026)
    p.add_argument('--output', type=Path, default=Path(__file__).with_name('dd_exited_sample.csv'))
    a = p.parse_args()
    e = exited(a.chars)
    unnamed = e.company_name.isna()
    e = e[~unnamed]
    s = (e.assign(exit_year=e.last_panel_month.dt.year)
          .groupby('exit_year', group_keys=False).apply(lambda g: g.sample(min(a.per_year, len(g)), random_state=a.seed))
          .sort_values('last_panel_month'))
    s['last_panel_month'] = s.last_panel_month.dt.strftime('%Y-%m')
    s['name_month'] = s.name_month.dt.strftime('%Y-%m')
    s.to_csv(a.output, index=False)
    print(f'{len(e) + unnamed.sum()} large firms exit 2015-2023 ({unnamed.sum()} without a name); sampled {len(s)} -> {a.output}')


if __name__ == '__main__':
    main()
