## Main table

| dataset | status | window | months | first-last return month | avg names/month | sectors covered | mean IC | IC t (NW3) | hit rate | L-S mean %/mo | L-S Sharpe (ann.) | L-S t |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Foot traffic | primary | design | 10 | 2020-03 to 2020-12 | 66 | 2 | -0.071 | -2.24 | 40% | -2.61 | -1.17 | -1.06 |
| Foot traffic | primary | test | 68 | 2021-01 to 2026-08 | 68 | 2 | +0.026 | +1.45 | 57% | +0.55 | +0.52 | +1.24 |
| Card spend | descriptive | design | 10 | 2020-03 to 2020-12 | 68 | 2 | +0.045 | +0.43 | 60% | +1.92 | +0.70 | +0.64 |
| Card spend | descriptive | test | 68 | 2021-01 to 2026-08 | 75 | 2 | +0.019 | +1.56 | 56% | +0.19 | +0.18 | +0.42 |
| Web traffic | descriptive | design | 0 | – | – | – | – | – | – | – | – | – |
| Web traffic | descriptive | test | 61 | 2021-08 to 2026-08 | 253 | 7 | +0.023 | +2.54 | 64% | +0.53 | +0.85 | +1.93 |

## Per year, test window (by return year)

| dataset | year | months | avg names | mean IC | hit rate | L-S mean %/mo | L-S t |
|---|---:|---:|---:|---:|---:|---:|---:|
| Foot traffic | 2021 | 12 | 75 | -0.004 | 42% | +0.19 | +0.16 |
| Foot traffic | 2022 | 12 | 76 | +0.062 | 75% | +1.23 | +1.50 |
| Foot traffic | 2023 | 12 | 75 | +0.025 | 58% | -0.02 | -0.02 |
| Foot traffic | 2024 | 12 | 67 | +0.066 | 67% | +1.97 | +1.45 |
| Foot traffic | 2025 | 12 | 59 | +0.072 | 83% | +1.71 | +2.39 |
| Foot traffic | 2026 | 8 | 52 | -0.113 | 0% | -2.95 | -3.34 |
| Card spend | 2021 | 12 | 80 | -0.035 | 42% | -0.82 | -0.58 |
| Card spend | 2022 | 12 | 82 | +0.048 | 58% | +1.14 | +1.17 |
| Card spend | 2023 | 12 | 84 | -0.013 | 50% | -1.31 | -1.07 |
| Card spend | 2024 | 12 | 76 | +0.041 | 58% | +0.74 | +0.68 |
| Card spend | 2025 | 12 | 67 | +0.050 | 67% | +1.30 | +1.63 |
| Card spend | 2026 | 8 | 58 | +0.021 | 62% | +0.02 | +0.04 |
| Web traffic | 2021 | 5 | 227 | +0.040 | 80% | +1.06 | +0.99 |
| Web traffic | 2022 | 12 | 249 | +0.005 | 50% | -0.20 | -0.36 |
| Web traffic | 2023 | 12 | 262 | +0.003 | 58% | +0.31 | +0.71 |
| Web traffic | 2024 | 12 | 257 | +0.024 | 67% | +0.74 | +1.41 |
| Web traffic | 2025 | 12 | 258 | +0.031 | 67% | +0.40 | +0.52 |
| Web traffic | 2026 | 8 | 248 | +0.052 | 75% | +1.49 | +1.55 |

## Correlation with each other and with momentum

| window | pair | avg monthly Spearman | months used | avg shared names |
|---|---:|---:|---:|---:|
| test | Foot traffic vs momentum (ret_12_1) | +0.074 | 68 | 68 |
| test | Foot traffic vs Card spend | +0.257 | 68 | 63 |
| test | Foot traffic vs Web traffic | n/a (never >=20 shared names) | 0 | 0 |
| test | Card spend vs momentum (ret_12_1) | +0.200 | 68 | 75 |
| test | Card spend vs Web traffic | n/a (never >=20 shared names) | 0 | 0 |
| test | Web traffic vs momentum (ret_12_1) | +0.057 | 61 | 253 |
| all | Foot traffic vs momentum (ret_12_1) | +0.098 | 78 | 68 |
| all | Foot traffic vs Card spend | +0.251 | 78 | 62 |
| all | Foot traffic vs Web traffic | n/a (never >=20 shared names) | 0 | 0 |
| all | Card spend vs momentum (ret_12_1) | +0.226 | 78 | 74 |
| all | Card spend vs Web traffic | n/a (never >=20 shared names) | 0 | 0 |
| all | Web traffic vs momentum (ret_12_1) | +0.057 | 61 | 253 |
