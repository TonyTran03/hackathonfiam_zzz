# Market-Neutral Alpha

**5th Place — 2026 McGill–FIAM Asset Management Hackathon**

A systematic long-short US equity strategy combining machine learning, factor-adjusted stock rankings, and convex portfolio optimization.

## 1. Prediction Model

We use **LightGBM** trained on 147 firm characteristics to forecast next-month stock returns.

Key predictive features include:
- Idiosyncratic volatility
- Investment growth
- Operating profitability

Models are trained using historical data to avoid look-ahead bias.

## 2. Ranking

Raw forecasts are adjusted for systematic exposures:

- Market beta
- Market capitalization (size)
- Sector

The resulting selection scores are smoothed over three observations to improve ranking stability and reduce unnecessary turnover.

## 3. Candidate Selection

Eligibility requirements:
- Share price ≥ $5
- Exclude nano-cap and micro-cap stocks
- Market capitalization ≥ $500M for short candidates

**Portfolio: 100 longs and 100 shorts**

- **Long:** Top 100 stocks by adjusted selection score.
- **Short:** Select 100 stocks from approximately the bottom 1,000–2,000 ranks, accounting for sector balance.

The broader short-selection pool allows greater flexibility in controlling sector exposure.

## 4. Portfolio Optimization

We use convex optimization to allocate capital across the selected stocks, balancing expected returns, covariance risk, and turnover.

### Objective Function

```math
\min_w \quad
-\alpha^\top w
+ 0.024\|w-w^-\|_1
+ 0.5w^\top\Sigma^{3000}w
```

### Constraints

```math
\begin{aligned}
w_i &> 0,\quad i\in L
&& \text{Long positions}\\[6pt]
w_i &< 0,\quad i\in S
&& \text{Short positions}\\[6pt]
\|w\|_1 &\leq 2.00
&& \text{Gross exposure}\\[6pt]
\mathbf{1}^\top w &= 0
&& \text{Dollar neutrality}\\[6pt]
|w_i| &\leq 0.035,\quad \forall i
&& \text{Position cap}\\[6pt]
\hat{\beta}^\top w &= 0
&& \text{Market-beta neutrality}\\[6pt]
d_iw_i &\geq 0.001,\quad \forall i
&& \text{Minimum allocation}
\end{aligned}
```

### Notation

- $\alpha$: Adjusted stock-selection scores
- $w$: Portfolio weights
- $w^-$: Pre-rebalance weights
- $\Sigma$: Estimated covariance matrix
- $\hat{\beta}$: Estimated market betas
- $L, S$: Long and short candidate sets
- $d_i$: +1 for longs, -1 for shorts

The portfolio is rebalanced monthly.
