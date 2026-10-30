# Model `wbmv`: the mentor's whiteboard objective and constraints

Rebalanced monthly, January 2021 to August 2026 (68 months), with walk-forward forecasts `current_gbm_no8k`. Weights $w$ are fractions of current NAV: $w_i>0$ is long and $w_i<0$ is short.

## 1. Universe, signal and alpha

**Eligible universe** each month: $|\text{Price}_i|\ge\$5$, $\text{SizeGroup}_i\notin\{\text{nano},\text{micro}\}$. That is about 1,870 stocks.

**Score.** The model's forecast rank $f_i$ is neutralised against size, beta and sector:

$$
f_i = c_0 + c_1\,\text{size}_i + c_2\,\hat\beta_i + \sum_k c_k\,\mathbb{1}[i\in k] + \varepsilon_i
$$

The score $s_i$ is the 3-month average of $\varepsilon_i$.

**Annual alpha.** The score is put back into the units of the model's monthly return forecast $r^{\text{fc}}$, then annualised:

$$
\alpha_i = 12 \cdot \frac{s_i}{\operatorname{sd}(s)} \cdot \operatorname{sd}\!\left(r^{\text{fc}}\right)
$$

Both standard deviations are taken across that month's universe. $\alpha$ is therefore the model's own expected return, with market, size and sector effects removed. The typical spread is $\operatorname{sd}(r^{\text{fc}}) \approx 1.4\%$ a month.

## 2. Candidates

- **Long set** $L$: ranks 1–100 by score.
- **Short pool** $P$: the 1,000 lowest scores among stocks with market cap $\ge\$500$M, excluding $L$.

The optimiser chooses which 100 names in $P$ to short.

## 3. Objective (mentor's whiteboard)

$$
\min_{w}\; -\,\alpha^\top w \;+\; 0.024\,\lVert w - w^{-}\rVert_1 \;+\; 0.5\, w^\top \Sigma_{\text{ann}}\, w
$$

| Symbol | Meaning |
|---|---|
| $\alpha$ | Annual expected alpha (section 1) |
| $0.024$ | $20\text{bp} \times 12$: trading cost in annual units |
| $w^{-}$ | Weights before rebalancing, after the month's price drift |
| $\Sigma_{\text{ann}}$ | $12\times$ the monthly covariance: Ledoit–Wolf shrunk correlation $\times$ sample volatilities, estimated on the candidate set ($L\cup P$, about 1,100 names) |
| $0.5$ | Weight on risk, exactly as written on the board |

## 4. Constraints

**Stage 1** solves over $L\cup P$:

$$
\begin{aligned}
\lVert w\rVert_1 &\le 0.75 && \text{gross exposure}\\
-0.50 \le \mathbf 1^\top w &\le 0.50 && \text{net exposure}\\
|w_i| &\le 0.02\quad\forall i && \text{position cap}\\
\hat\beta^\top w &= 0 && \text{estimated beta neutral}\\
w_i &\ge 0.001\quad\forall i\in L && \text{ranks 1–100: long}\\
w_i &\le 0\quad\forall i\in P && \text{pool of 1,000: short or zero}\\
\Big|\sum_{i\in k} w_i\Big| &\le 0.02\quad\forall\text{ sectors } k && \text{sector neutral (GICS 2-digit)}\\
|\text{size}^\top w| &\le 0.02 && \text{size neutral (market-cap rank)}
\end{aligned}
$$

**Stage 2** keeps the 100 names in $P$ with the largest stage-1 short weights; call this set $S^{*}$. It re-solves on $L\cup S^{*}$ with every constraint above, plus $w_i\le-0.001$ for all $i\in S^{*}$, so the book holds exactly 200 names ($d_i w_i\ge 0.001$).

Exactly zero sector and size exposure (the circled "= 0") is infeasible once every held name must be at least 0.1%, so the band is $\pm 2\%$.

## 5. Results, 2021-01 to 2026-08 (20bp costs in the P&L)

| | **Mentor's objective** | Reference: `wb2_m` (Tony's objective, same constraints) |
|---|---|---|
| Information ratio vs T-bill + 4% | **0.85** | 0.75 |
| IR at 50bp costs | 0.76 | 0.54 |
| IR at 65bp + 1% borrow | **0.67** | 0.40 |
| IR at 100bp + 2% borrow | 0.53 | 0.12 |
| Sharpe ratio (vs T-bill) | 1.26 | 1.15 |
| CAGR | 16.2% | 15.5% |
| Ending NAV ($1bn start) | $2.34bn | $2.26bn |
| Volatility | 9.7% | 10.2% |
| Max drawdown | **−6.0%** | −9.3% |
| Worst month | −3.8% (Dec 2022) | −5.7% (Dec 2022) |
| Months beating the hurdle | 60% | 62% |
| Realised beta | −0.02 | −0.01 |
| Max sector net / size exposure | 2.0% / 0.020 | 2.0% / 0.020 |
| Names | 200 | 200 |
| One-way turnover per year | **1.43** (about 12% of the book a month) | 3.56 |
| Trading costs per year | 0.57% | 1.42% |
| Stock-selection P&L per year | 12.6% | 12.5% |
| Sector P&L per year | +0.40% | +0.79% |

**IR by year:** 2021 1.58 · 2022 1.56 · 2023 −0.72 · 2024 0.65 · 2025 0.52 · 2026 (Jan–Aug) 0.81

With the daily covariance (about 750 observations) instead: IR 0.58, vol 8.9%, max drawdown −8.5%, turnover 1.40 (`wbmv_score_d`).

## 6. How alpha was chosen, and why it matters

We tried three ways of turning the signal into an annual expected return. The objective, the 0.024 cost and the 0.5 weight on risk stayed exactly as on the board:

| Alpha | IR | Turnover/yr | Comment |
|---|---|---|---|
| $12 \cdot \text{IC} \cdot \sigma_i \cdot z_i$ (IC 0.035) | −0.01 | 2.37 | Alpha grows with each stock's volatility, so the book piles into volatile names |
| $12 \cdot (r^{\text{fc}}_i - \overline{r^{\text{fc}}})$, the raw forecast | 0.54 | 2.52 | Not sector or size neutral, so the constraints have to undo it |
| **$12 \cdot s_i/\operatorname{sd}(s) \cdot \operatorname{sd}(r^{\text{fc}})$** | **0.85** | **1.43** | The neutralised signal, in the model's return units |

The third choice keeps the signal consistent with the constraints: the score is already neutral to sector, size and beta, which is what the mentor asked for. All three were tried on the 2021–2026 window, so the choice among them is a mild selection effect and should be disclosed.

## 7. Limitations

- The monthly covariance (36 observations) underestimates volatility. The daily version gives IR 0.58.
- Rebalancing is monthly, so weights drift within the month. Missing returns are marked at zero.
- The 75% gross, 2% cap and the alpha definition were chosen by the team on the 2021–2026 window, so this is a retrospective test.

## Reproduce (from `sizing/neutral/`)

```
B="N_LONG=100 N_SHORT=1000 LONG_FLOOR=0.001 SHORT_FLOOR=0 K_SHORT=100 OBJECTIVE=mv_ann ANNUAL_COST=0.024 ALPHA=score"
env $B python run_neutral.py wbmv_score_m 0.02 0.02 m
```
