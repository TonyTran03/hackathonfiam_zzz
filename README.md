
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
