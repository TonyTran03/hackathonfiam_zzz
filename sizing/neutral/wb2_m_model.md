# Model `wb2_m`: whiteboard design, sector- and size-neutral

Rebalanced monthly, January 2021 to August 2026 (68 months), with walk-forward forecasts `current_gbm_no8k`. Weights $w$ are fractions of current NAV: $w_i>0$ is long and $w_i<0$ is short.

## 1. Universe and signal

**Eligible universe** each month: stocks with $|\text{Price}_i| \ge \$5$, $\text{SizeGroup}_i \notin \{\text{nano}, \text{micro}\}$, and finite beta, volatility and market cap. That is about 1,870 stocks.

**Score.** The forecast is turned into a cross-sectional rank $f_i$ (standardised). It is then neutralised against size, beta and sector:

$$
f_i = c_0 + c_1\,\text{size}_i + c_2\,\hat\beta_i + \sum_k c_k\,\mathbb{1}[i \in k] + \varepsilon_i,
\qquad
\tilde s_i = \varepsilon_i
$$

The score $s_i$ is the 3-month moving average of $\tilde s_i$. Here $\text{size}_i$ is the standardised rank of market cap and $\hat\beta_i$ is the estimated market beta, clipped to $[-0.5, 3.5]$.

## 2. Candidates

- **Long set** $L$: the 100 highest scores, with a retention buffer for names already held.
- **Short pool** $P$: the 1,000 lowest scores among stocks with $\text{MarketCap}_i \ge \$500\text{M}$, excluding $L$.

The optimiser chooses which 100 names in $P$ to short.

## 3. Objective (Tony's)

$$
\max_{w}\; s^\top w \;-\; 100\, w^\top \Sigma\, w \;-\; 0.002\left(\lVert w - w^{-} \rVert_1 + F\right)
$$

| Symbol | Meaning |
|---|---|
| $s$ | Score vector (section 1). This is a ranking, not an expected return. |
| $\Sigma$ | Monthly covariance: 36 monthly returns, Ledoit–Wolf shrunk correlation $\times$ sample volatilities. |
| $w^{-}$ | Weights before rebalancing, after the month's price drift. |
| $F$ | Total absolute weight of holdings that leave the candidate list and must be sold. It is a constant, so it does not change the solution. |

## 4. Constraints

**Stage 1** solves over $L \cup P$, about 1,100 names:

$$
\begin{aligned}
\lVert w \rVert_1 &\le 0.75 && \text{gross exposure} \\
-0.50 \le \mathbf{1}^\top w &\le 0.50 && \text{net exposure} \\
|w_i| &\le 0.02 \quad \forall i && \text{position cap} \\
\hat\beta^\top w &= 0 && \text{estimated beta neutral} \\
w_i &\ge 0.001 \quad \forall i \in L && \text{top 100 long, minimum 0.1\%} \\
w_i &\le 0 \quad \forall i \in P && \text{short pool: short or zero} \\
\Big|\sum_{i \in k} w_i\Big| &\le 0.02 \quad \forall \text{ sectors } k && \text{sector neutral (GICS 2-digit)} \\
|\text{size}^\top w| &\le 0.02 && \text{size neutral (market cap)}
\end{aligned}
$$

**Stage 2** keeps the 100 names in $P$ with the largest short weights from stage 1; call this set $S^{*}$. It then re-solves on $L \cup S^{*}$ with every constraint above, replacing the short-pool rule with:

$$
w_i \le -0.001 \quad \forall i \in S^{*}
$$

so that $d_i w_i \ge 0.001$ holds for all 200 names, where $d_i = +1$ for longs and $-1$ for shorts.

The mandate limits ($\lVert w\rVert_1 \le 2$, $|w_i| \le 0.05$, net within $\pm 0.5$, 200–500 names, shorts $\ge \$500$M) are also enforced, and the house limits above are tighter.

**Why two stages:** if stage 1 stood alone, the optimiser would hold only 25–52 shorts, about 125–152 names in total, which breaks the 200-name minimum.

## 5. Accounting

$$
r_t = r_{f,t} + w_t^\top (r_t^{\text{stock}} - r_{f,t}) \;-\; 0.002\left(\lVert w_t - w_t^{-} \rVert_1 + F_t\right),
\qquad
\text{hurdle}_t = r_{f,t} + \tfrac{4\%}{12}
$$

Missing realised returns are marked at zero. Borrow fees, market impact and financing spreads are not modelled.

## 6. Results (2021-01 to 2026-08)

| Metric | Value |
|---|---|
| Information ratio vs T-bill + 4% | **0.75** |
| Sharpe ratio (vs T-bill) | 1.15 |
| CAGR | 15.5% |
| Annualised volatility | 10.2% |
| Max drawdown | **−9.35%** (peak Nov 2022, low Jul 2023, back to peak Jul 2024) |
| Worst month | −5.7% (Dec 2022) |
| Losing months | 22 of 68 |
| Realised market beta | −0.01 |
| Max sector net exposure | 2.0% |
| Max size exposure | 0.020 |
| Positions | 200 every month (100 long, 100 short) |
| Net exposure range | −17.5% to +12.1% |
| One-way turnover | 3.56× NAV per year (about 30% of the book a month) |
| Trading costs at 20bp | 1.42% of NAV per year |
| P&L from sector bets | +0.79% per year |
| P&L from stock selection within sector | **+12.47% per year** |
| Ending NAV ($1bn start) | $2.26bn |

**IR by year:** 2021 2.13 · 2022 1.12 · 2023 −1.24 · 2024 0.53 · 2025 0.27 · 2026 (Jan–Aug) 1.13

**Cost sensitivity (IR):** 20bp 0.75 · 50bp 0.54 · 65bp + 1% borrow 0.40 · 100bp + 2% borrow 0.12

## 7. Limitations

- The risk model uses only 36 monthly observations for about 1,100 names. Its predicted volatility is about half the realised. A daily covariance (about 750 observations, as the mentor recommended) gives an IR of 0.63 (`wb2_d`).
- The sector and size bands (2%) come from the mentor and were not tuned. Exactly zero is infeasible once every held name must be at least 0.1%.
- The 75% gross and 2% position cap were chosen by the team using the same 2021–2026 window, so this is a retrospective test, not an untouched holdout.
- Rebalancing is monthly, so weights drift within the month. A 20bp flat cost is optimistic for names trading about $28M a day.

Reproduce from `sizing/neutral/`:

```
N_LONG=100 N_SHORT=1000 LONG_FLOOR=0.001 SHORT_FLOOR=0 K_SHORT=100 python run_neutral.py wb2_m 0.02 0.02 m
```
