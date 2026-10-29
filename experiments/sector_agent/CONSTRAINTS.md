# Sector-agent experiment: optimisation problem and constraints

Both arms solve the same convex problem each month (`sizing/optimizer/constraints.py`). The agent
arm adds one constraint, a cap on each sector's gross share (C8), and chooses its sector net band
each month.

## Notation

| Symbol | Meaning |
|---|---|
| $w \in \mathbb{R}^{N}$, $N = 300$ | Weights of the month's candidates, as fractions of NAV |
| $d_i \in \{+1, -1\}$ | Fixed side: 150 long and 150 short candidates |
| $s \in \mathbb{R}^{N}$ | Neutralised ranking score |
| $\Sigma$ | Covariance: Ledoit–Wolf shrunk correlation × stock volatility, from the last 36 months |
| $\beta_i$ | Market beta (`beta_use`), clipped to $[-0.5,\, 3.5]$ |
| $\tilde w$ | Previous book, drifted by this month's returns |
| $f$ | Turnover forced by exiting names that are no longer candidates |
| $S_k$ | The candidates in GICS sector $k$ |
| $u_{k,t}$ | Sector $k$'s share (by count) of the tradable universe in month $t$ |
| $G = 2$ | Gross limit |

## Objective

$$
\max_{w}\;\; s^\top w \;-\; \lambda\, w^\top \Sigma\, w \;-\; \gamma\,\frac{c}{10^4}\Big(\lVert w - \tilde w \rVert_1 + f\Big)
$$

$$
\lambda = 100, \qquad \gamma = 230, \qquad c = 20\ \text{bp}
$$

## Constraints in both arms

$$
\begin{aligned}
&\text{(C1) Gross:} && \lVert w \rVert_1 = \sum_{i} |w_i| \;\le\; 2.0 \\[4pt]
&\text{(C2) Net:} && -0.5 \;\le\; \sum_{i} w_i \;\le\; 0.5 \\[4pt]
&\text{(C3) Single name:} && |w_i| \;\le\; 0.05 && \forall i \\[4pt]
&\text{(C4) Side, long candidates:} && 0 \;\le\; w_i \;\le\; 0.05 && \forall i: d_i = +1 \\
&\text{(C4) Side, short candidates:} && -0.05 \;\le\; w_i \;\le\; 0 && \forall i: d_i = -1 \\[4pt]
&\text{(C5) Minimum position:} && d_i\, w_i \;\ge\; 0.001 && \forall i \\[4pt]
&\text{(C6) Beta neutral:} && \big|\beta^\top w\big| \;\le\; 0 \;\;\Longleftrightarrow\;\; \beta^\top w = 0 \\[4pt]
&\text{(C7) Sector net band:} && \Big|\sum_{i \in S_k} w_i\Big| \;\le\; b_t && \forall k
\end{aligned}
$$

$$
b_t =
\begin{cases}
0.02 & \text{control (every month)} \\[4pt]
\in \{0.01,\; 0.02,\; 0.03\} & \text{agent; if } 0.01 \text{ is infeasible, use } 0.02
\end{cases}
$$

## Agent arm only

$$
\text{(C8) Sector gross cap:}\qquad \sum_{i \in S_k} |w_i| \;\le\; m_t \, u_{k,t}\, G \qquad \forall k
$$

$$
m_t \in \{1.25,\; 1.5,\; \infty\}, \qquad \text{fallback order: } 1.25 \;\to\; 1.5 \;\to\; \infty
$$

**Why the right-hand side uses the constant $G$.** It uses $G$ rather than the realised gross
$\lVert w \rVert_1$, because "convex $\le$ convex" is not DCP-compliant. C1 always binds
($\lVert w\rVert_1 = 2$), so the constraint is equivalent to a cap on the sector's share of gross:

$$
\frac{\sum_{i \in S_k} |w_i|}{\lVert w \rVert_1} \;\le\; m_t\, u_{k,t}
$$

**Example.** In 2024-04, Health Care had $u = 0.161$ and $m = 1.25$, so its share was capped at
$1.25 \times 0.161 = 20.2\%$ of gross.

## Overlay (both arms, from `VOL_TARGET_RULE.md`)

$r^{\text{base}}_\tau$ is the unscaled, fully costed excess return. Every estimate uses only months
up to $t-1$.

$$
\begin{aligned}
h_t &= \operatorname{OLS\ slope}\Big(r^{\text{base}}_\tau \;\sim\; \text{SPX}_\tau - \text{cash}_\tau\Big),
      && \tau \in [t-24,\; t-1], \;\; \text{at least 12 months, else } h_t = 0 \\[6pt]
\sigma_t &= \sqrt{12}\;\operatorname{sd}\Big(r^{\text{base}}_\tau - h_\tau\,(\text{SPX}_\tau - \text{cash}_\tau)\Big),
      && \tau \in [t-12,\; t-1] \\[6pt]
k_t &= \operatorname{clip}\!\left(\frac{0.10}{\sigma_t},\; 0.25,\; 1.00\right),
      && k_t = 1 \text{ with fewer than 12 months}
\end{aligned}
$$

**Final book.** The stock weights are $k_t\, w_t$, plus an SPX futures hedge of $-k_t h_t$.

**Monthly net return**, with $r_t$ the vector of stock returns, $\mathbf{1}$ a vector of ones and
$\tilde w_{t-1}$ last month's scaled book after drift:

$$
\begin{aligned}
R_t \;=\;& \text{cash}_t \;+\; k_t\, w_t^\top \big(r_t - \text{cash}_t \mathbf{1}\big) \;-\; k_t h_t \big(\text{SPX}_t - \text{cash}_t\big) \\[4pt]
&-\; 0.0065\, \big\lVert k_t w_t - \tilde w_{t-1} \big\rVert_1 \\[4pt]
&-\; \frac{0.0152}{12}\, k_t \sum_i \max(-w_{i,t},\, 0)
\end{aligned}
$$

## Mandate checks (monthly, after the overlay)

$$
\begin{aligned}
&\text{Names:} && 200 \;\le\; \#\{\, i : |k_t w_{i,t}| > 10^{-6} \,\} \;\le\; 500 \\[4pt]
&\text{Gross:} && k_t \lVert w_t \rVert_1 \;\le\; 2 \\[4pt]
&\text{Net:} && \Big| k_t \sum_i w_{i,t} \Big| \;\le\; 0.5 \\[4pt]
&\text{Single name:} && k_t\, |w_{i,t}| \;\le\; 0.05 \quad \forall i \\[4pt]
&\text{Short book:} && k_t \sum_i \max(-w_{i,t},\, 0)\cdot \text{NAV}_t \;\ge\; \$500\text{m} \\[4pt]
&\text{Sectors held:} && \#\{\, k : \textstyle\sum_{i \in S_k} |w_{i,t}| > 0 \,\} \;\ge\; 5 \\[4pt]
&\text{Sector net:} && \max_k \Big| k_t \sum_{i \in S_k} w_{i,t} \Big| \;\le\; 0.20
\end{aligned}
$$

**What the overlay can break.** Since $k_t \le 1$, scaling only loosens C1–C3 and C7. The one
mandate the overlay can break is the $500m short floor, because $k_t$ can fall to 0.25. It is not
an optimizer constraint. In the worst month the short book was $875m (control) and $801m
(agent), so both cleared it.
