"""Step 4: the agent's decisions. Reads ONLY agent_inputs.csv (and the menus in RULE.md).

Rule, fixed before any optimizer run:
- Cap: 1.25x by default (the direct lever on concentration). 1.5x when one sector's forecast
  dispersion is at least 2x the median sector's, so a tight cap would cost the most alpha.
  'none' is never chosen: it works against the experiment's goal.
- Band: from the median sector vol (annualised, trailing 3 months). >= 0.25: 1% (sector shocks
  large, neutrality worth most). <= 0.12: 3% (calm, give the optimizer room, trade less).
  Otherwise 2%.
"""
import hashlib
import json
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
text = (HERE / 'agent_inputs.csv').read_text(encoding='utf-8')
x = pd.read_csv(HERE / 'agent_inputs.csv', index_col='ID')
disp = x.filter(like='_disp')
vol = x.filter(like='_vol')
rows = []
for i in x.index:
    ratio = disp.loc[i].max() / disp.loc[i].median()
    top = disp.loc[i].idxmax()[0]
    v = vol.loc[i].median()
    cap = '1.5x' if ratio >= 2 else '1.25x'
    band = '1%' if v >= 0.25 else ('3%' if v <= 0.12 else '2%')
    why_cap = (f'sector {top} dispersion {ratio:.1f}x median, loosen cap' if cap == '1.5x'
               else f'dispersion spread {ratio:.1f}x, tight cap')
    why_band = {'1%': 'high', '3%': 'calm', '2%': 'normal'}[band]
    rows.append({'ID': i, 'band': band, 'cap': cap,
                 'reason': f'median sector vol {v:.2f} ({why_band}) -> band {band}; {why_cap}'})
pd.DataFrame(rows).to_csv(HERE / 'agent_decisions.csv', index=False)
(HERE / 'decisions_meta.json').write_text(json.dumps(
    {'forecast': json.loads((HERE / 'agent_inputs_meta.json').read_text())['forecast'],
     'inputs_sha256': hashlib.sha256(text.replace('\r\n', '\n').encode()).hexdigest()}, indent=2))
print(pd.DataFrame(rows).groupby(['band', 'cap']).size())
