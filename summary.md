# Pick lists backtest

Data 2013-06-03 to 2026-10-14, 1489 tickers. Signals from 2014-10; every choice was made on 2014-2021 S&P 500 data and then checked on 2022-2026. Entry at the next open; returns are compared with the average liquid stock in the same universe over the same days. Your overbought rule is on, as on the page: no list spot or new AI pick while its sector's breadth is over 75, and nothing new while the S&P 500's breadth is over 75.

## The chosen lists

Chosen: {'ai_score': 'rs', 'ai_rule': 'keep20', 'new_up': 'all', 'breakout': 'near'}. The page (CFG in screener.py) uses: {'new_up': 'all', 'breakout': 'tight', 'ai_score': 'rs', 'ai_rule': 'keep20'} **(different!)**.

### S&P 500 as it was each day

| List | Version | Period | vs avg stock | Notes |
|---|---|---|---|---|
| New uptrends | Every new uptrend | 2014-2021 (chosen here) | -0.01% over 20 days (-0.28 to +0.26) | 6.7 a day, 52% beat the average stock |
| New uptrends | Every new uptrend | 2022-2026 (unseen) | -0.42% over 20 days (-0.81 to -0.04) | 7.9 a day, 48% beat the average stock |
| New uptrends | Every new uptrend | 2014-2026 (all) | -0.19% over 20 days (-0.41 to +0.04) | 7.2 a day, 50% beat the average stock |
| Breakout watch | Closest to the breakout level | 2014-2021 (chosen here) | -0.05% over 20 days (-0.42 to +0.32) | broke out within 10 days 64% of the time vs 29% for all stocks |
| Breakout watch | Closest to the breakout level | 2022-2026 (unseen) | -0.65% over 20 days (-1.10 to -0.19) | broke out within 10 days 60% of the time vs 24% for all stocks |
| Breakout watch | Closest to the breakout level | 2014-2026 (all) | -0.30% over 20 days (-0.64 to +0.04) | broke out within 10 days 62% of the time vs 27% for all stocks |
| AI picks | IBD-style relative strength, keep only while in the top 20 | 2014-2021 (chosen here) | -4.3% a year (-14.51 to +5.98) | +10.4%/yr vs +16.4% average stock and +15.4% SPY; worst drop -31%; 570 picks, median hold 14 days |
| AI picks | IBD-style relative strength, keep only while in the top 20 | 2022-2026 (unseen) | +16.1% a year (-0.62 to +32.80) | +26.7%/yr vs +11.1% average stock and +11.9% SPY; worst drop -29%; 400 picks, median hold 6 days |
| AI picks | IBD-style relative strength, keep only while in the top 20 | 2014-2026 (all) | +3.7% a year (-5.40 to +12.83) | +16.6%/yr vs +14.3% average stock and +14.0% SPY; worst drop -31%; 970 picks, median hold 10 days |

### S&P 400 + 600 (today's members)

| List | Version | Period | vs avg stock | Notes |
|---|---|---|---|---|
| New uptrends | Every new uptrend | 2014-2021 (chosen here) | -0.00% over 20 days (-0.54 to +0.54) | 3.6 a day, 50% beat the average stock |
| New uptrends | Every new uptrend | 2022-2026 (unseen) | -0.25% over 20 days (-0.72 to +0.23) | 6.3 a day, 47% beat the average stock |
| New uptrends | Every new uptrend | 2014-2026 (all) | -0.11% over 20 days (-0.46 to +0.24) | 4.8 a day, 48% beat the average stock |
| Breakout watch | Closest to the breakout level | 2014-2021 (chosen here) | -0.13% over 20 days (-0.71 to +0.45) | broke out within 10 days 52% of the time vs 23% for all stocks |
| Breakout watch | Closest to the breakout level | 2022-2026 (unseen) | -0.66% over 20 days (-1.08 to -0.24) | broke out within 10 days 54% of the time vs 22% for all stocks |
| Breakout watch | Closest to the breakout level | 2014-2026 (all) | -0.35% over 20 days (-0.77 to +0.06) | broke out within 10 days 53% of the time vs 22% for all stocks |
| AI picks | IBD-style relative strength, keep only while in the top 20 | 2014-2021 (chosen here) | +17.9% a year (+0.42 to +35.32) | +30.4%/yr vs +12.9% average stock and +15.4% SPY; worst drop -50%; 502 picks, median hold 15 days |
| AI picks | IBD-style relative strength, keep only while in the top 20 | 2022-2026 (unseen) | +1.3% a year (-20.28 to +22.80) | +4.7%/yr vs +7.4% average stock and +11.9% SPY; worst drop -40%; 430 picks, median hold 10 days |
| AI picks | IBD-style relative strength, keep only while in the top 20 | 2014-2026 (all) | +11.4% a year (-2.24 to +24.95) | +19.6%/yr vs +10.7% average stock and +14.0% SPY; worst drop -50%; 932 picks, median hold 12 days |

## S&P 500 as it was each day
About 331 liquid stocks a day.

### Signal report card
Each signal on its own: the best 10% of stocks by that signal each day, and the worst 10%, against the average stock over the next 20 trading days.

| Signal | Period | Top 10% vs avg stock, 20 days (95% range) | Bottom 10% | Rank correlation |
|---|---|---|---|---|
| 12-month momentum, skip last month | 2014-2021 (chosen here) | -0.33% (-0.70 to +0.05) | +0.35% | -0.019 |
| 12-month momentum, skip last month | 2022-2026 (unseen) | +0.90% (-0.06 to +1.85) | +0.11% | +0.021 |
| 12-month momentum, skip last month | 2014-2026 (all) | +0.15% (-0.30 to +0.60) | +0.26% | -0.004 |
| momentum / volatility | 2014-2021 (chosen here) | -0.40% (-0.88 to +0.09) | +0.23% | -0.018 |
| momentum / volatility | 2022-2026 (unseen) | +0.57% (-0.18 to +1.32) | -0.42% | +0.023 |
| momentum / volatility | 2014-2026 (all) | -0.02% (-0.42 to +0.39) | -0.03% | -0.002 |
| 6-month momentum, skip last month | 2014-2021 (chosen here) | -0.02% (-0.37 to +0.32) | +0.25% | -0.007 |
| 6-month momentum, skip last month | 2022-2026 (unseen) | +0.52% (-0.31 to +1.36) | +0.32% | -0.008 |
| 6-month momentum, skip last month | 2014-2026 (all) | +0.19% (-0.18 to +0.57) | +0.28% | -0.007 |
| IBD-style relative strength | 2014-2021 (chosen here) | -0.27% (-0.62 to +0.08) | +0.17% | -0.015 |
| IBD-style relative strength | 2022-2026 (unseen) | +0.73% (-0.18 to +1.65) | +0.23% | +0.005 |
| IBD-style relative strength | 2014-2026 (all) | +0.12% (-0.28 to +0.53) | +0.19% | -0.007 |
| closeness to the 52-week high | 2014-2021 (chosen here) | -0.31% (-0.68 to +0.06) | +0.47% | -0.025 |
| closeness to the 52-week high | 2022-2026 (unseen) | -0.33% (-0.98 to +0.31) | +0.31% | -0.006 |
| closeness to the 52-week high | 2014-2026 (all) | -0.32% (-0.61 to -0.03) | +0.41% | -0.017 |
| industry strength (6 months) | 2014-2021 (chosen here) | -0.12% (-0.43 to +0.20) | -0.13% | -0.007 |
| industry strength (6 months) | 2022-2026 (unseen) | +0.46% (-0.40 to +1.33) | +0.32% | -0.003 |
| industry strength (6 months) | 2014-2026 (all) | +0.11% (-0.33 to +0.55) | +0.04% | -0.006 |
| share of the sector in an uptrend | 2014-2021 (chosen here) | -0.49% (-1.00 to +0.02) | -0.12% | -0.032 |
| share of the sector in an uptrend | 2022-2026 (unseen) | -0.35% (-1.15 to +0.46) | -0.05% | -0.004 |
| share of the sector in an uptrend | 2014-2026 (all) | -0.43% (-0.88 to +0.01) | -0.09% | -0.021 |
| steady climb (frog in the pan) | 2014-2021 (chosen here) | -0.23% (-0.65 to +0.19) | -0.10% | -0.006 |
| steady climb (frog in the pan) | 2022-2026 (unseen) | +0.25% (-0.32 to +0.83) | -0.09% | +0.022 |
| steady climb (frog in the pan) | 2014-2026 (all) | -0.04% (-0.40 to +0.32) | -0.10% | +0.005 |
| recent power gap that held | 2014-2021 (chosen here) | -0.58% (-1.04 to -0.12) | n/a | -0.008 |
| recent power gap that held | 2022-2026 (unseen) | -0.26% (-1.06 to +0.55) | n/a | -0.003 |
| recent power gap that held | 2014-2026 (all) | -0.45% (-0.88 to -0.02) | n/a | -0.006 |
| up-day vs down-day volume | 2014-2021 (chosen here) | -0.15% (-0.50 to +0.21) | +0.29% | -0.019 |
| up-day vs down-day volume | 2022-2026 (unseen) | -0.08% (-0.56 to +0.40) | +0.28% | -0.018 |
| up-day vs down-day volume | 2014-2026 (all) | -0.12% (-0.40 to +0.16) | +0.28% | -0.019 |
| low volatility | 2014-2021 (chosen here) | -0.13% (-0.66 to +0.41) | +0.29% | -0.010 |
| low volatility | 2022-2026 (unseen) | -0.32% (-0.90 to +0.26) | +1.26% | -0.033 |
| low volatility | 2014-2026 (all) | -0.20% (-0.68 to +0.28) | +0.67% | -0.019 |
| 1-week pullback | 2014-2021 (chosen here) | +0.20% (-0.19 to +0.59) | -0.16% | +0.014 |
| 1-week pullback | 2022-2026 (unseen) | +0.47% (+0.20 to +0.74) | +0.25% | +0.007 |
| 1-week pullback | 2014-2026 (all) | +0.30% (+0.05 to +0.56) | +0.00% | +0.011 |
| 1-month pullback | 2014-2021 (chosen here) | +0.22% (-0.40 to +0.84) | -0.35% | +0.032 |
| 1-month pullback | 2022-2026 (unseen) | +0.22% (-0.33 to +0.77) | +0.42% | -0.001 |
| 1-month pullback | 2014-2026 (all) | +0.22% (-0.18 to +0.62) | -0.05% | +0.019 |
| in an uptrend (your rule) | 2014-2021 (chosen here) | -0.16% (-0.41 to +0.08) | +0.07% | -0.017 |
| in an uptrend (your rule) | 2022-2026 (unseen) | -0.26% (-0.66 to +0.14) | -0.02% | -0.005 |
| in an uptrend (your rule) | 2014-2026 (all) | -0.20% (-0.44 to +0.04) | +0.04% | -0.012 |
| Minervini trend template | 2014-2021 (chosen here) | -0.28% (-0.56 to +0.01) | +0.11% | -0.022 |
| Minervini trend template | 2022-2026 (unseen) | -0.12% (-0.74 to +0.49) | -0.05% | +0.004 |
| Minervini trend template | 2014-2026 (all) | -0.22% (-0.53 to +0.09) | +0.05% | -0.012 |
| not stretched above EMA20 | 2014-2021 (chosen here) | +0.21% (-0.19 to +0.61) | -0.31% | +0.027 |
| not stretched above EMA20 | 2022-2026 (unseen) | +0.06% (-0.32 to +0.44) | +0.08% | -0.002 |
| not stretched above EMA20 | 2014-2026 (all) | +0.15% (-0.12 to +0.42) | -0.16% | +0.015 |
| volume drying up | 2014-2021 (chosen here) | +0.09% (-0.11 to +0.29) | -0.07% | +0.004 |
| volume drying up | 2022-2026 (unseen) | -0.05% (-0.39 to +0.29) | -0.00% | +0.002 |
| volume drying up | 2014-2026 (all) | +0.03% (-0.13 to +0.20) | -0.04% | +0.003 |
| ranges shrinking | 2014-2021 (chosen here) | +0.31% (+0.11 to +0.50) | -0.15% | +0.017 |
| ranges shrinking | 2022-2026 (unseen) | -0.05% (-0.39 to +0.28) | +0.03% | +0.003 |
| ranges shrinking | 2014-2026 (all) | +0.17% (-0.04 to +0.37) | -0.08% | +0.012 |

### AI score: the 10 best stocks each day

| List | Period | Days | Picks/day | 5-day vs avg stock | 10-day | 20-day (95% range) | Beat avg (20d) | Avg 20-day return | Broke out in 10d |
|---|---|---|---|---|---|---|---|---|---|
| 12-month momentum (skip the last month) | 2014-2021 (chosen here) | 1827 | 10.0 | -0.16% | -0.29% | -0.59% (-1.13 to -0.05) | 47% | +0.65% | 29% |
| 12-month momentum (skip the last month) | 2022-2026 (unseen) | 1179 | 10.0 | +0.44% | +0.97% | +2.04% (+0.14 to +3.94) | 54% | +2.94% | 32% |
| 12-month momentum (skip the last month) | 2014-2026 (all) | 3006 | 10.0 | +0.08% | +0.21% | +0.44% (-0.39 to +1.27) | 50% | +1.55% | 30% |
| Momentum per unit of volatility | 2014-2021 (chosen here) | 1827 | 10.0 | -0.15% | -0.31% | -0.66% (-1.22 to -0.10) | 46% | +0.58% | 33% |
| Momentum per unit of volatility | 2022-2026 (unseen) | 1179 | 10.0 | +0.44% | +0.95% | +1.78% (+0.08 to +3.48) | 53% | +2.68% | 33% |
| Momentum per unit of volatility | 2014-2026 (all) | 3006 | 10.0 | +0.08% | +0.18% | +0.30% (-0.51 to +1.11) | 49% | +1.41% | 33% |
| Closeness to the 52-week high | 2014-2021 (chosen here) | 1827 | 10.0 | -0.07% | -0.08% | -0.29% (-0.67 to +0.10) | 48% | +0.96% | 72% |
| Closeness to the 52-week high | 2022-2026 (unseen) | 1179 | 10.0 | -0.10% | -0.15% | -0.29% (-1.02 to +0.45) | 48% | +0.62% | 69% |
| Closeness to the 52-week high | 2014-2026 (all) | 3006 | 10.0 | -0.08% | -0.11% | -0.29% (-0.69 to +0.12) | 48% | +0.82% | 71% |
| IBD-style relative strength | 2014-2021 (chosen here) | 1827 | 10.0 | -0.15% | -0.23% | -0.36% (-0.84 to +0.11) | 47% | +0.88% | 45% |
| IBD-style relative strength | 2022-2026 (unseen) | 1179 | 10.0 | +0.45% | +1.01% | +2.22% (+0.11 to +4.32) | 54% | +3.12% | 45% |
| IBD-style relative strength | 2014-2026 (all) | 3006 | 10.0 | +0.09% | +0.26% | +0.65% (-0.22 to +1.52) | 50% | +1.76% | 45% |
| Momentum/vol + 52w high + industry strength | 2014-2021 (chosen here) | 1827 | 10.0 | -0.23% | -0.40% | -0.80% (-1.34 to -0.27) | 46% | +0.44% | 45% |
| Momentum/vol + 52w high + industry strength | 2022-2026 (unseen) | 1179 | 10.0 | +0.25% | +0.64% | +1.28% (-0.56 to +3.11) | 51% | +2.18% | 45% |
| Momentum/vol + 52w high + industry strength | 2014-2026 (all) | 3006 | 10.0 | -0.04% | +0.01% | +0.01% (-0.87 to +0.90) | 48% | +1.12% | 45% |
| Core + steady climb | 2014-2021 (chosen here) | 1827 | 10.0 | -0.24% | -0.44% | -0.89% (-1.50 to -0.29) | 45% | +0.35% | 44% |
| Core + steady climb | 2022-2026 (unseen) | 1179 | 10.0 | +0.24% | +0.54% | +1.14% (-0.56 to +2.84) | 51% | +2.04% | 41% |
| Core + steady climb | 2014-2026 (all) | 3006 | 10.0 | -0.05% | -0.06% | -0.10% (-0.97 to +0.78) | 48% | +1.01% | 43% |
| Core + steady climb + recent power gap | 2014-2021 (chosen here) | 1827 | 10.0 | -0.27% | -0.49% | -0.98% (-1.53 to -0.43) | 45% | +0.26% | 44% |
| Core + steady climb + recent power gap | 2022-2026 (unseen) | 1179 | 10.0 | +0.21% | +0.47% | +1.04% (-0.70 to +2.79) | 51% | +1.95% | 43% |
| Core + steady climb + recent power gap | 2014-2026 (all) | 3006 | 10.0 | -0.08% | -0.11% | -0.19% (-1.04 to +0.67) | 47% | +0.92% | 44% |

### AI score: the best 10% each day (30-40 stocks, so much less noise; the score is chosen here)

| List | Period | Days | Picks/day | 5-day vs avg stock | 10-day | 20-day (95% range) | Beat avg (20d) | Avg 20-day return | Broke out in 10d |
|---|---|---|---|---|---|---|---|---|---|
| 12-month momentum (skip the last month) | 2014-2021 (chosen here) | 1827 | 30.8 | -0.08% | -0.15% | -0.33% (-0.70 to +0.05) | 48% | +0.92% | 31% |
| 12-month momentum (skip the last month) | 2022-2026 (unseen) | 1179 | 37.5 | +0.18% | +0.42% | +0.90% (-0.06 to +1.85) | 51% | +1.80% | 30% |
| 12-month momentum (skip the last month) | 2014-2026 (all) | 3006 | 33.4 | +0.02% | +0.07% | +0.15% (-0.30 to +0.60) | 49% | +1.26% | 30% |
| Momentum per unit of volatility | 2014-2021 (chosen here) | 1827 | 30.8 | -0.09% | -0.18% | -0.40% (-0.88 to +0.09) | 48% | +0.85% | 33% |
| Momentum per unit of volatility | 2022-2026 (unseen) | 1179 | 37.5 | +0.14% | +0.29% | +0.57% (-0.18 to +1.33) | 50% | +1.48% | 31% |
| Momentum per unit of volatility | 2014-2026 (all) | 3006 | 33.4 | +0.00% | +0.01% | -0.02% (-0.42 to +0.39) | 49% | +1.09% | 32% |
| Closeness to the 52-week high | 2014-2021 (chosen here) | 1750 | 33.6 | -0.09% | -0.12% | -0.31% (-0.68 to +0.06) | 48% | +0.98% | 67% |
| Closeness to the 52-week high | 2022-2026 (unseen) | 1167 | 39.1 | -0.12% | -0.22% | -0.34% (-0.98 to +0.31) | 47% | +0.58% | 61% |
| Closeness to the 52-week high | 2014-2026 (all) | 2917 | 35.8 | -0.10% | -0.16% | -0.32% (-0.61 to -0.03) | 48% | +0.82% | 65% |
| IBD-style relative strength | 2014-2021 (chosen here) | 1827 | 30.8 | -0.10% | -0.15% | -0.27% (-0.62 to +0.08) | 48% | +0.97% | 45% |
| IBD-style relative strength | 2022-2026 (unseen) | 1179 | 37.5 | +0.15% | +0.31% | +0.73% (-0.18 to +1.65) | 50% | +1.64% | 43% |
| IBD-style relative strength | 2014-2026 (all) | 3006 | 33.4 | -0.00% | +0.03% | +0.12% (-0.28 to +0.53) | 49% | +1.23% | 44% |
| Momentum/vol + 52w high + industry strength | 2014-2021 (chosen here) | 1827 | 30.9 | -0.14% | -0.26% | -0.54% (-0.94 to -0.14) | 47% | +0.70% | 44% |
| Momentum/vol + 52w high + industry strength | 2022-2026 (unseen) | 1179 | 37.5 | +0.09% | +0.21% | +0.51% (-0.38 to +1.39) | 50% | +1.41% | 40% |
| Momentum/vol + 52w high + industry strength | 2014-2026 (all) | 3006 | 33.5 | -0.05% | -0.08% | -0.13% (-0.59 to +0.33) | 48% | +0.98% | 42% |
| Core + steady climb | 2014-2021 (chosen here) | 1827 | 30.9 | -0.14% | -0.25% | -0.51% (-0.95 to -0.08) | 47% | +0.73% | 42% |
| Core + steady climb | 2022-2026 (unseen) | 1179 | 37.5 | +0.08% | +0.22% | +0.48% (-0.29 to +1.26) | 50% | +1.39% | 38% |
| Core + steady climb | 2014-2026 (all) | 3006 | 33.5 | -0.05% | -0.07% | -0.12% (-0.56 to +0.31) | 48% | +0.99% | 40% |
| Core + steady climb + recent power gap | 2014-2021 (chosen here) | 1827 | 30.9 | -0.14% | -0.26% | -0.53% (-0.93 to -0.12) | 47% | +0.72% | 42% |
| Core + steady climb + recent power gap | 2022-2026 (unseen) | 1179 | 37.5 | +0.09% | +0.24% | +0.53% (-0.26 to +1.32) | 50% | +1.43% | 39% |
| Core + steady climb + recent power gap | 2014-2026 (all) | 3006 | 33.5 | -0.05% | -0.06% | -0.11% (-0.54 to +0.32) | 48% | +1.00% | 41% |

### AI picks as a managed list (10 stocks, entries and exits at the next open, 0.10% cost each way)

Score versions, all with the same rules (hold 10, keep while in the top 30, max 3 per sector):

| Version | Period | Return/yr | vs avg stock/yr (95% range) | Sharpe | Worst drop | Picks made | Avg pick | Picks up | Days held (median) |
|---|---|---|---|---|---|---|---|---|---|
| 12-month momentum (skip the last month) | 2014-2021 (chosen here) | +7.6% | -6.4% (-16.67 to +3.89) | 0.42 | -41% | 300 | +2.2% | 52% | 35 |
| 12-month momentum (skip the last month) | 2022-2026 (unseen) | +28.1% | +18.2% (-1.10 to +37.56) | 0.92 | -34% | 170 | +11.3% | 54% | 34 |
| 12-month momentum (skip the last month) | 2014-2026 (all) | +15.2% | +3.3% (-6.66 to +13.19) | 0.65 | -41% | 470 | +5.5% | 53% | 35 |
| Momentum per unit of volatility | 2014-2021 (chosen here) | +8.6% | -6.2% (-15.49 to +3.06) | 0.49 | -37% | 367 | +2.1% | 55% | 30 |
| Momentum per unit of volatility | 2022-2026 (unseen) | +25.8% | +14.5% (-0.45 to +29.47) | 1.00 | -23% | 185 | +7.1% | 58% | 43 |
| Momentum per unit of volatility | 2014-2026 (all) | +15.0% | +1.9% (-6.31 to +10.14) | 0.72 | -37% | 552 | +3.7% | 56% | 34 |
| Closeness to the 52-week high | 2014-2021 (chosen here) | +2.8% | -12.9% (-22.09 to -3.68) | 0.27 | -38% | 3571 | +0.3% | 48% | 2 |
| Closeness to the 52-week high | 2022-2026 (unseen) | -6.8% | -17.8% (-28.28 to -7.36) | -0.40 | -33% | 2577 | +0.1% | 44% | 2 |
| Closeness to the 52-week high | 2014-2026 (all) | -1.1% | -14.8% (-21.76 to -7.88) | -0.00 | -38% | 6148 | +0.2% | 46% | 2 |
| IBD-style relative strength | 2014-2021 (chosen here) | +8.3% | -6.1% (-16.85 to +4.63) | 0.47 | -35% | 384 | +1.9% | 45% | 28 |
| IBD-style relative strength | 2022-2026 (unseen) | +27.4% | +16.9% (-1.76 to +35.50) | 0.96 | -31% | 232 | +9.1% | 44% | 23 |
| IBD-style relative strength | 2014-2026 (all) | +15.4% | +2.9% (-6.98 to +12.78) | 0.68 | -35% | 616 | +4.6% | 44% | 26 |
| Momentum/vol + 52w high + industry strength | 2014-2021 (chosen here) | +2.1% | -12.7% (-21.96 to -3.44) | 0.21 | -40% | 594 | +0.6% | 46% | 14 |
| Momentum/vol + 52w high + industry strength | 2022-2026 (unseen) | +12.8% | +2.6% (-11.71 to +16.93) | 0.66 | -26% | 400 | +2.0% | 48% | 15 |
| Momentum/vol + 52w high + industry strength | 2014-2026 (all) | +6.2% | -6.7% (-14.70 to +1.31) | 0.40 | -40% | 994 | +1.1% | 47% | 14 |
| Core + steady climb | 2014-2021 (chosen here) | +4.4% | -10.5% (-20.06 to -0.96) | 0.32 | -41% | 419 | +1.0% | 49% | 24 |
| Core + steady climb | 2022-2026 (unseen) | +14.4% | +3.8% (-9.20 to +16.73) | 0.74 | -22% | 274 | +3.0% | 50% | 22 |
| Core + steady climb | 2014-2026 (all) | +8.2% | -4.9% (-12.70 to +2.88) | 0.49 | -41% | 693 | +1.8% | 49% | 23 |
| Core + steady climb + recent power gap | 2014-2021 (chosen here) | +0.1% | -14.7% (-24.29 to -5.18) | 0.10 | -45% | 542 | +0.2% | 48% | 17 |
| Core + steady climb + recent power gap | 2022-2026 (unseen) | +10.2% | +0.4% (-13.40 to +14.13) | 0.55 | -27% | 373 | +1.9% | 47% | 14 |
| Core + steady climb + recent power gap | 2014-2026 (all) | +3.9% | -8.8% (-16.81 to -0.82) | 0.29 | -45% | 915 | +0.9% | 47% | 17 |
| *Average liquid stock (equal weight)* | 2014-2021 (chosen here) | +16.4% | | 0.96 | -37% | | | | |
| *SPY* | 2014-2021 (chosen here) | +15.4% | | 0.96 | -32% | | | | |
| *Average liquid stock (equal weight)* | 2022-2026 (unseen) | +11.1% | | 0.72 | -21% | | | | |
| *SPY* | 2022-2026 (unseen) | +11.9% | | 0.73 | -26% | | | | |
| *Average liquid stock (equal weight)* | 2014-2026 (all) | +14.3% | | 0.87 | -37% | | | | |
| *SPY* | 2014-2026 (all) | +14.0% | | 0.86 | -32% | | | | |

Score chosen on the best 10% in 2014-2021 (S&P 500): **IBD-style relative strength**. Rule versions for it (chosen on the 2014-2021 Sharpe ratio):

| Version | Period | Return/yr | vs avg stock/yr (95% range) | Sharpe | Worst drop | Picks made | Avg pick | Picks up | Days held (median) |
|---|---|---|---|---|---|---|---|---|---|
| Hold 10, keep while in the top 30, max 3 per sector | 2014-2021 (chosen here) | +8.3% | -6.1% (-16.85 to +4.63) | 0.47 | -35% | 384 | +1.9% | 45% | 28 |
| Hold 10, keep while in the top 30, max 3 per sector | 2022-2026 (unseen) | +27.4% | +16.9% (-1.76 to +35.50) | 0.96 | -31% | 232 | +9.1% | 44% | 23 |
| Hold 10, keep while in the top 30, max 3 per sector | 2014-2026 (all) | +15.4% | +2.9% (-6.98 to +12.78) | 0.68 | -35% | 616 | +4.6% | 44% | 26 |
| Keep only while in the top 20 | 2014-2021 (chosen here) | +10.4% | -4.3% (-14.51 to +5.98) | 0.56 | -31% | 570 | +1.8% | 44% | 14 |
| Keep only while in the top 20 | 2022-2026 (unseen) | +26.7% | +16.1% (-0.62 to +32.80) | 0.96 | -29% | 400 | +5.6% | 44% | 6 |
| Keep only while in the top 20 | 2014-2026 (all) | +16.6% | +3.7% (-5.40 to +12.83) | 0.74 | -31% | 970 | +3.4% | 44% | 10 |
| Keep while in the top 50 | 2014-2021 (chosen here) | +9.8% | -4.7% (-15.32 to +5.94) | 0.52 | -36% | 261 | +3.1% | 47% | 53 |
| Keep while in the top 50 | 2022-2026 (unseen) | +23.8% | +14.1% (-3.29 to +31.59) | 0.86 | -32% | 139 | +13.6% | 44% | 51 |
| Keep while in the top 50 | 2014-2026 (all) | +15.1% | +2.7% (-6.77 to +12.18) | 0.67 | -36% | 400 | +6.8% | 46% | 52 |
| Also sell on a close below EMA50 | 2014-2021 (chosen here) | +6.5% | -8.4% (-19.69 to +2.91) | 0.41 | -28% | 868 | +0.8% | 39% | 9 |
| Also sell on a close below EMA50 | 2022-2026 (unseen) | +8.5% | -0.4% (-16.60 to +15.86) | 0.45 | -32% | 611 | +1.4% | 35% | 9 |
| Also sell on a close below EMA50 | 2014-2026 (all) | +7.3% | -5.2% (-14.62 to +4.13) | 0.43 | -35% | 1479 | +1.1% | 37% | 9 |
| Also sell on your exit (10 EMA under the 20 and price under the 50, daily) | 2014-2021 (chosen here) | +5.3% | -9.4% (-20.62 to +1.80) | 0.36 | -29% | 810 | +0.8% | 40% | 11 |
| Also sell on your exit (10 EMA under the 20 and price under the 50, daily) | 2022-2026 (unseen) | +12.3% | +3.2% (-13.77 to +20.10) | 0.57 | -36% | 557 | +2.5% | 38% | 10 |
| Also sell on your exit (10 EMA under the 20 and price under the 50, daily) | 2014-2026 (all) | +8.0% | -4.5% (-14.03 to +5.07) | 0.45 | -42% | 1367 | +1.5% | 39% | 10 |
| No new picks while SPY is below its 200-day average | 2014-2021 (chosen here) | +5.5% | -8.9% (-19.73 to +1.84) | 0.36 | -30% | 356 | +1.5% | 43% | 28 |
| No new picks while SPY is below its 200-day average | 2022-2026 (unseen) | +24.6% | +14.1% (-4.68 to +32.92) | 0.92 | -31% | 194 | +10.1% | 42% | 24 |
| No new picks while SPY is below its 200-day average | 2014-2026 (all) | +12.6% | +0.1% (-9.85 to +10.05) | 0.61 | -31% | 550 | +4.5% | 43% | 26 |
| Both of the above | 2014-2021 (chosen here) | +6.6% | -8.6% (-20.28 to +3.00) | 0.44 | -26% | 666 | +1.0% | 40% | 13 |
| Both of the above | 2022-2026 (unseen) | +11.2% | +1.4% (-16.15 to +18.89) | 0.57 | -25% | 421 | +2.2% | 36% | 12 |
| Both of the above | 2014-2026 (all) | +8.3% | -4.7% (-14.59 to +5.17) | 0.50 | -26% | 1087 | +1.5% | 38% | 13 |
| *Average liquid stock (equal weight)* | 2014-2021 (chosen here) | +16.4% | | 0.96 | -37% | | | | |
| *SPY* | 2014-2021 (chosen here) | +15.4% | | 0.96 | -32% | | | | |
| *Average liquid stock (equal weight)* | 2022-2026 (unseen) | +11.1% | | 0.72 | -21% | | | | |
| *SPY* | 2022-2026 (unseen) | +11.9% | | 0.73 | -26% | | | | |
| *Average liquid stock (equal weight)* | 2014-2026 (all) | +14.3% | | 0.87 | -37% | | | | |
| *SPY* | 2014-2026 (all) | +14.0% | | 0.86 | -32% | | | | |

Chosen rule: **Keep only while in the top 20**.

Year by year (chosen version):

| Year | AI picks | Average stock | SPY |
|---|---|---|---|
| 2014 | +9.4% | +8.4% | +5.7% |
| 2015 | -8.8% | -0.4% | +0.7% |
| 2016 | +6.1% | +18.6% | +14.4% |
| 2017 | +31.1% | +23.7% | +21.5% |
| 2018 | -2.9% | -6.3% | -6.0% |
| 2019 | +30.9% | +32.5% | +31.8% |
| 2020 | +3.3% | +12.8% | +16.8% |
| 2021 | +12.9% | +35.5% | +31.9% |
| 2022 | -10.8% | -8.5% | -18.7% |
| 2023 | +20.1% | +17.0% | +24.6% |
| 2024 | +48.0% | +16.0% | +26.5% |
| 2025 | +38.7% | +16.0% | +18.2% |
| 2026 | +37.8% | +13.6% | +11.7% |

### New uptrends (each ordering's top 5 a day, against the whole list)

| List | Period | Days | Picks/day | 5-day vs avg stock | 10-day | 20-day (95% range) | Beat avg (20d) | Avg 20-day return | Broke out in 10d |
|---|---|---|---|---|---|---|---|---|---|
| Every new uptrend | 2014-2021 (chosen here) | 1260 | 6.7 | +0.10% | +0.01% | -0.01% (-0.28 to +0.26) | 52% | +1.31% | 37% |
| Every new uptrend | 2022-2026 (unseen) | 918 | 7.9 | -0.13% | -0.21% | -0.42% (-0.81 to -0.04) | 48% | +0.69% | 35% |
| Every new uptrend | 2014-2026 (all) | 2178 | 7.2 | +0.00% | -0.08% | -0.19% (-0.41 to +0.04) | 50% | +1.04% | 36% |
| Strongest relative strength first | 2014-2021 (chosen here) | 1260 | 3.9 | +0.05% | -0.05% | -0.09% (-0.42 to +0.23) | 51% | +1.23% | 36% |
| Strongest relative strength first | 2022-2026 (unseen) | 918 | 4.2 | -0.07% | -0.22% | -0.38% (-0.91 to +0.15) | 47% | +0.73% | 35% |
| Strongest relative strength first | 2014-2026 (all) | 2178 | 4.0 | +0.00% | -0.12% | -0.22% (-0.50 to +0.07) | 49% | +1.01% | 35% |
| Closest to the 52-week high first | 2014-2021 (chosen here) | 1260 | 3.9 | +0.10% | +0.00% | -0.04% (-0.39 to +0.31) | 52% | +1.28% | 39% |
| Closest to the 52-week high first | 2022-2026 (unseen) | 918 | 4.2 | -0.14% | -0.30% | -0.59% (-1.14 to -0.04) | 47% | +0.52% | 36% |
| Closest to the 52-week high first | 2014-2026 (all) | 2178 | 4.0 | -0.00% | -0.13% | -0.27% (-0.58 to +0.04) | 50% | +0.96% | 38% |
| Highest volume on the day it turned | 2014-2021 (chosen here) | 1260 | 3.9 | +0.09% | -0.02% | -0.06% (-0.36 to +0.24) | 52% | +1.26% | 40% |
| Highest volume on the day it turned | 2022-2026 (unseen) | 918 | 4.2 | -0.11% | -0.20% | -0.48% (-0.92 to -0.05) | 47% | +0.63% | 38% |
| Highest volume on the day it turned | 2014-2026 (all) | 2178 | 4.0 | +0.01% | -0.09% | -0.24% (-0.49 to +0.01) | 50% | +0.99% | 39% |
| Best AI score first | 2014-2021 (chosen here) | 1260 | 3.9 | +0.05% | -0.05% | -0.09% (-0.42 to +0.23) | 51% | +1.23% | 36% |
| Best AI score first | 2022-2026 (unseen) | 918 | 4.2 | -0.07% | -0.22% | -0.38% (-0.91 to +0.15) | 47% | +0.73% | 35% |
| Best AI score first | 2014-2026 (all) | 2178 | 4.0 | +0.00% | -0.12% | -0.22% (-0.50 to +0.07) | 49% | +1.01% | 35% |
| Out of an uptrend for 20+ days, then relative strength | 2014-2021 (chosen here) | 789 | 2.2 | -0.06% | -0.08% | -0.11% (-0.63 to +0.41) | 49% | +1.07% | 31% |
| Out of an uptrend for 20+ days, then relative strength | 2022-2026 (unseen) | 653 | 2.6 | -0.01% | -0.07% | -0.12% (-0.72 to +0.48) | 48% | +1.13% | 34% |
| Out of an uptrend for 20+ days, then relative strength | 2014-2026 (all) | 1442 | 2.4 | -0.04% | -0.07% | -0.11% (-0.49 to +0.26) | 49% | +1.10% | 33% |
| Strongest sector first | 2014-2021 (chosen here) | 1260 | 3.9 | +0.10% | +0.00% | -0.04% (-0.33 to +0.25) | 52% | +1.28% | 37% |
| Strongest sector first | 2022-2026 (unseen) | 918 | 4.2 | -0.11% | -0.26% | -0.52% (-0.98 to -0.07) | 47% | +0.59% | 34% |
| Strongest sector first | 2014-2026 (all) | 2178 | 4.0 | +0.01% | -0.11% | -0.24% (-0.50 to +0.01) | 50% | +0.99% | 36% |
| Baseline: stocks already in an uptrend | 2014-2021 (chosen here) | 1826 | 142.8 | -0.02% | -0.06% | -0.17% (-0.43 to +0.10) | 49% | +1.07% | 50% |
| Baseline: stocks already in an uptrend | 2022-2026 (unseen) | 1179 | 147.4 | -0.06% | -0.13% | -0.27% (-0.69 to +0.15) | 48% | +0.63% | 47% |
| Baseline: stocks already in an uptrend | 2014-2026 (all) | 3005 | 144.6 | -0.04% | -0.09% | -0.21% (-0.46 to +0.05) | 49% | +0.90% | 48% |

Chosen: **Every new uptrend** (an ordering had to beat the whole list by 0.10% in 2014-2021).

### Breakout watch (top 10 a day)

| List | Period | Days | Picks/day | 5-day vs avg stock | 10-day | 20-day (95% range) | Beat avg (20d) | Avg 20-day return | Broke out in 10d |
|---|---|---|---|---|---|---|---|---|---|
| Every stock within 5% of its 50-day high | 2014-2021 (chosen here) | 1358 | 51.9 | -0.01% | -0.03% | -0.10% (-0.41 to +0.21) | 51% | +1.18% | 39% |
| Every stock within 5% of its 50-day high | 2022-2026 (unseen) | 976 | 46.3 | -0.17% | -0.37% | -0.64% (-1.01 to -0.27) | 46% | +0.40% | 41% |
| Every stock within 5% of its 50-day high | 2014-2026 (all) | 2334 | 49.5 | -0.08% | -0.17% | -0.32% (-0.60 to -0.05) | 49% | +0.86% | 40% |
| Closest to the breakout level | 2014-2021 (chosen here) | 1358 | 9.8 | +0.01% | +0.04% | -0.05% (-0.42 to +0.32) | 51% | +1.23% | 64% |
| Closest to the breakout level | 2022-2026 (unseen) | 976 | 9.8 | -0.15% | -0.31% | -0.65% (-1.10 to -0.19) | 46% | +0.39% | 60% |
| Closest to the breakout level | 2014-2026 (all) | 2334 | 9.8 | -0.06% | -0.11% | -0.30% (-0.64 to +0.04) | 49% | +0.88% | 62% |
| Uptrend + tightest range, shrinking ranges, drying volume, closest | 2014-2021 (chosen here) | 1354 | 9.6 | -0.01% | -0.06% | -0.12% (-0.44 to +0.20) | 50% | +1.13% | 48% |
| Uptrend + tightest range, shrinking ranges, drying volume, closest | 2022-2026 (unseen) | 976 | 9.7 | -0.16% | -0.32% | -0.59% (-1.23 to +0.05) | 46% | +0.45% | 45% |
| Uptrend + tightest range, shrinking ranges, drying volume, closest | 2014-2026 (all) | 2330 | 9.7 | -0.07% | -0.17% | -0.31% (-0.66 to +0.03) | 48% | +0.85% | 46% |
| Same + relative strength | 2014-2021 (chosen here) | 1354 | 9.6 | -0.01% | -0.06% | -0.16% (-0.48 to +0.16) | 49% | +1.09% | 49% |
| Same + relative strength | 2022-2026 (unseen) | 976 | 9.7 | -0.15% | -0.28% | -0.46% (-1.12 to +0.19) | 47% | +0.58% | 46% |
| Same + relative strength | 2014-2026 (all) | 2330 | 9.7 | -0.07% | -0.15% | -0.29% (-0.64 to +0.07) | 48% | +0.87% | 48% |
| Minervini trend template, strongest RS first | 2014-2021 (chosen here) | 1334 | 8.9 | -0.09% | -0.14% | -0.24% (-0.64 to +0.15) | 49% | +0.92% | 46% |
| Minervini trend template, strongest RS first | 2022-2026 (unseen) | 964 | 8.9 | -0.20% | -0.43% | -0.65% (-1.32 to +0.01) | 46% | +0.40% | 46% |
| Minervini trend template, strongest RS first | 2014-2026 (all) | 2298 | 8.9 | -0.14% | -0.26% | -0.42% (-0.76 to -0.07) | 48% | +0.70% | 46% |
| Uptrend + Bollinger squeeze, strongest RS first | 2014-2021 (chosen here) | 1027 | 5.5 | -0.09% | -0.02% | +0.10% (-0.42 to +0.62) | 50% | +0.95% | 44% |
| Uptrend + Bollinger squeeze, strongest RS first | 2022-2026 (unseen) | 778 | 5.0 | -0.19% | -0.43% | -0.54% (-1.15 to +0.06) | 45% | +0.08% | 41% |
| Uptrend + Bollinger squeeze, strongest RS first | 2014-2026 (all) | 1805 | 5.3 | -0.14% | -0.20% | -0.18% (-0.59 to +0.24) | 48% | +0.58% | 43% |
| Baseline: every liquid stock | 2014-2021 (chosen here) | 1827 | 304.1 | -0.00% | +0.00% | +0.00% (-0.00 to +0.00) | 50% | +1.24% | 29% |
| Baseline: every liquid stock | 2022-2026 (unseen) | 1179 | 370.7 | +0.00% | -0.00% | -0.00% (-0.00 to +0.00) | 48% | +0.90% | 24% |
| Baseline: every liquid stock | 2014-2026 (all) | 3006 | 330.2 | +0.00% | +0.00% | -0.00% (-0.00 to +0.00) | 49% | +1.11% | 27% |

Chosen: **Closest to the breakout level** (best 2014-2021 return among lists that broke out at least 1.5x as often as the average stock; returns within 0.01% count as a tie, and a tie goes to the list that broke out more often).

## S&P 400 + 600 (today's members)
About 227 liquid stocks a day.

### Signal report card
Each signal on its own: the best 10% of stocks by that signal each day, and the worst 10%, against the average stock over the next 20 trading days.

| Signal | Period | Top 10% vs avg stock, 20 days (95% range) | Bottom 10% | Rank correlation |
|---|---|---|---|---|
| 12-month momentum, skip last month | 2014-2021 (chosen here) | +1.15% (+0.50 to +1.80) | +0.10% | +0.011 |
| 12-month momentum, skip last month | 2022-2026 (unseen) | +0.84% (-0.42 to +2.11) | +0.13% | +0.020 |
| 12-month momentum, skip last month | 2014-2026 (all) | +1.03% (+0.47 to +1.59) | +0.11% | +0.015 |
| momentum / volatility | 2014-2021 (chosen here) | +0.62% (+0.04 to +1.21) | -0.23% | +0.018 |
| momentum / volatility | 2022-2026 (unseen) | +0.51% (-0.56 to +1.58) | -0.59% | +0.022 |
| momentum / volatility | 2014-2026 (all) | +0.58% (+0.06 to +1.10) | -0.37% | +0.020 |
| 6-month momentum, skip last month | 2014-2021 (chosen here) | +1.00% (+0.28 to +1.71) | +0.25% | +0.019 |
| 6-month momentum, skip last month | 2022-2026 (unseen) | +0.52% (-0.71 to +1.74) | -0.10% | +0.006 |
| 6-month momentum, skip last month | 2014-2026 (all) | +0.81% (+0.25 to +1.37) | +0.11% | +0.014 |
| IBD-style relative strength | 2014-2021 (chosen here) | +1.06% (+0.40 to +1.71) | +0.20% | +0.019 |
| IBD-style relative strength | 2022-2026 (unseen) | +0.81% (-0.39 to +2.02) | +0.03% | +0.015 |
| IBD-style relative strength | 2014-2026 (all) | +0.96% (+0.36 to +1.57) | +0.14% | +0.017 |
| closeness to the 52-week high | 2014-2021 (chosen here) | -0.08% (-0.53 to +0.37) | +0.53% | +0.011 |
| closeness to the 52-week high | 2022-2026 (unseen) | -0.38% (-0.89 to +0.12) | +0.31% | +0.011 |
| closeness to the 52-week high | 2014-2026 (all) | -0.20% (-0.51 to +0.12) | +0.45% | +0.011 |
| industry strength (6 months) | 2014-2021 (chosen here) | +0.46% (-0.31 to +1.23) | -0.86% | +0.020 |
| industry strength (6 months) | 2022-2026 (unseen) | +0.34% (-1.07 to +1.76) | -0.39% | +0.002 |
| industry strength (6 months) | 2014-2026 (all) | +0.41% (-0.28 to +1.10) | -0.68% | +0.013 |
| share of the sector in an uptrend | 2014-2021 (chosen here) | -0.55% (-1.06 to -0.03) | -0.49% | -0.008 |
| share of the sector in an uptrend | 2022-2026 (unseen) | +0.13% (-1.30 to +1.57) | -0.02% | -0.007 |
| share of the sector in an uptrend | 2014-2026 (all) | -0.28% (-0.89 to +0.33) | -0.31% | -0.008 |
| steady climb (frog in the pan) | 2014-2021 (chosen here) | +0.13% (-0.46 to +0.71) | -0.78% | +0.017 |
| steady climb (frog in the pan) | 2022-2026 (unseen) | -0.27% (-0.88 to +0.33) | -0.51% | +0.009 |
| steady climb (frog in the pan) | 2014-2026 (all) | -0.03% (-0.46 to +0.39) | -0.67% | +0.014 |
| recent power gap that held | 2014-2021 (chosen here) | -0.20% (-0.99 to +0.58) | n/a | -0.002 |
| recent power gap that held | 2022-2026 (unseen) | +0.08% (-0.72 to +0.87) | n/a | -0.000 |
| recent power gap that held | 2014-2026 (all) | -0.09% (-0.70 to +0.51) | n/a | -0.001 |
| up-day vs down-day volume | 2014-2021 (chosen here) | -0.03% (-0.53 to +0.48) | -0.04% | +0.001 |
| up-day vs down-day volume | 2022-2026 (unseen) | +0.05% (-0.46 to +0.57) | -0.31% | +0.008 |
| up-day vs down-day volume | 2014-2026 (all) | +0.01% (-0.37 to +0.38) | -0.14% | +0.004 |
| low volatility | 2014-2021 (chosen here) | -0.31% (-1.00 to +0.38) | +1.59% | -0.007 |
| low volatility | 2022-2026 (unseen) | -0.55% (-1.20 to +0.10) | +0.50% | -0.001 |
| low volatility | 2014-2026 (all) | -0.41% (-0.96 to +0.15) | +1.16% | -0.004 |
| 1-week pullback | 2014-2021 (chosen here) | +0.48% (-0.07 to +1.03) | +0.05% | +0.014 |
| 1-week pullback | 2022-2026 (unseen) | +0.45% (-0.09 to +1.00) | +0.05% | +0.010 |
| 1-week pullback | 2014-2026 (all) | +0.47% (+0.11 to +0.83) | +0.05% | +0.013 |
| 1-month pullback | 2014-2021 (chosen here) | +0.58% (-0.12 to +1.28) | -0.05% | +0.013 |
| 1-month pullback | 2022-2026 (unseen) | +0.16% (-0.66 to +0.99) | +0.41% | -0.004 |
| 1-month pullback | 2014-2026 (all) | +0.42% (-0.08 to +0.91) | +0.13% | +0.006 |
| in an uptrend (your rule) | 2014-2021 (chosen here) | -0.06% (-0.34 to +0.22) | +0.02% | +0.006 |
| in an uptrend (your rule) | 2022-2026 (unseen) | -0.19% (-0.67 to +0.29) | -0.04% | +0.001 |
| in an uptrend (your rule) | 2014-2026 (all) | -0.11% (-0.38 to +0.16) | -0.00% | +0.004 |
| Minervini trend template | 2014-2021 (chosen here) | +0.25% (-0.19 to +0.68) | -0.02% | +0.010 |
| Minervini trend template | 2022-2026 (unseen) | -0.29% (-0.99 to +0.42) | -0.00% | -0.000 |
| Minervini trend template | 2014-2026 (all) | +0.04% (-0.37 to +0.45) | -0.01% | +0.006 |
| not stretched above EMA20 | 2014-2021 (chosen here) | +0.40% (-0.10 to +0.90) | -0.42% | +0.014 |
| not stretched above EMA20 | 2022-2026 (unseen) | -0.01% (-0.56 to +0.53) | +0.03% | -0.004 |
| not stretched above EMA20 | 2014-2026 (all) | +0.24% (-0.11 to +0.58) | -0.24% | +0.007 |
| volume drying up | 2014-2021 (chosen here) | +0.27% (-0.06 to +0.60) | -0.26% | +0.005 |
| volume drying up | 2022-2026 (unseen) | +0.17% (-0.31 to +0.65) | +0.46% | -0.004 |
| volume drying up | 2014-2026 (all) | +0.23% (-0.07 to +0.54) | +0.02% | +0.002 |
| ranges shrinking | 2014-2021 (chosen here) | +0.39% (-0.04 to +0.82) | -0.18% | +0.011 |
| ranges shrinking | 2022-2026 (unseen) | +0.06% (-0.34 to +0.45) | -0.07% | -0.004 |
| ranges shrinking | 2014-2026 (all) | +0.26% (-0.06 to +0.58) | -0.14% | +0.005 |

### AI score: the 10 best stocks each day

| List | Period | Days | Picks/day | 5-day vs avg stock | 10-day | 20-day (95% range) | Beat avg (20d) | Avg 20-day return | Broke out in 10d |
|---|---|---|---|---|---|---|---|---|---|
| 12-month momentum (skip the last month) | 2014-2021 (chosen here) | 1827 | 10.0 | +0.37% | +0.90% | +1.70% (+0.67 to +2.73) | 50% | +2.74% | 28% |
| 12-month momentum (skip the last month) | 2022-2026 (unseen) | 1179 | 10.0 | +0.42% | +0.82% | +1.50% (-0.29 to +3.29) | 51% | +2.18% | 27% |
| 12-month momentum (skip the last month) | 2014-2026 (all) | 3006 | 10.0 | +0.39% | +0.87% | +1.62% (+0.72 to +2.52) | 51% | +2.52% | 28% |
| Momentum per unit of volatility | 2014-2021 (chosen here) | 1827 | 10.0 | +0.30% | +0.54% | +0.84% (+0.06 to +1.62) | 49% | +1.88% | 28% |
| Momentum per unit of volatility | 2022-2026 (unseen) | 1179 | 10.0 | +0.30% | +0.54% | +0.83% (-0.79 to +2.45) | 51% | +1.51% | 30% |
| Momentum per unit of volatility | 2014-2026 (all) | 3006 | 10.0 | +0.30% | +0.54% | +0.84% (+0.10 to +1.57) | 50% | +1.74% | 29% |
| Closeness to the 52-week high | 2014-2021 (chosen here) | 1827 | 10.0 | +0.02% | -0.03% | +0.01% (-0.51 to +0.54) | 49% | +1.05% | 66% |
| Closeness to the 52-week high | 2022-2026 (unseen) | 1179 | 10.0 | -0.06% | -0.11% | -0.25% (-0.92 to +0.42) | 49% | +0.43% | 66% |
| Closeness to the 52-week high | 2014-2026 (all) | 3006 | 10.0 | -0.01% | -0.06% | -0.09% (-0.53 to +0.35) | 49% | +0.81% | 66% |
| IBD-style relative strength | 2014-2021 (chosen here) | 1827 | 10.0 | +0.39% | +0.77% | +1.60% (+0.52 to +2.67) | 50% | +2.64% | 39% |
| IBD-style relative strength | 2022-2026 (unseen) | 1179 | 10.0 | +0.18% | +0.32% | +0.71% (-1.33 to +2.75) | 50% | +1.39% | 42% |
| IBD-style relative strength | 2014-2026 (all) | 3006 | 10.0 | +0.31% | +0.59% | +1.25% (+0.25 to +2.25) | 50% | +2.15% | 40% |
| Momentum/vol + 52w high + industry strength | 2014-2021 (chosen here) | 1827 | 10.0 | +0.15% | +0.35% | +0.66% (-0.14 to +1.46) | 49% | +1.70% | 41% |
| Momentum/vol + 52w high + industry strength | 2022-2026 (unseen) | 1179 | 10.0 | +0.16% | +0.37% | +0.82% (-0.88 to +2.53) | 51% | +1.50% | 41% |
| Momentum/vol + 52w high + industry strength | 2014-2026 (all) | 3006 | 10.0 | +0.15% | +0.36% | +0.72% (-0.15 to +1.60) | 50% | +1.62% | 41% |
| Core + steady climb | 2014-2021 (chosen here) | 1827 | 10.0 | +0.08% | +0.19% | +0.43% (-0.43 to +1.30) | 49% | +1.47% | 38% |
| Core + steady climb | 2022-2026 (unseen) | 1179 | 10.0 | +0.18% | +0.47% | +0.84% (-0.70 to +2.38) | 51% | +1.52% | 39% |
| Core + steady climb | 2014-2026 (all) | 3006 | 10.0 | +0.12% | +0.30% | +0.59% (-0.26 to +1.44) | 50% | +1.49% | 38% |
| Core + steady climb + recent power gap | 2014-2021 (chosen here) | 1827 | 10.0 | +0.13% | +0.19% | +0.31% (-0.60 to +1.22) | 49% | +1.35% | 40% |
| Core + steady climb + recent power gap | 2022-2026 (unseen) | 1179 | 10.0 | +0.13% | +0.40% | +0.81% (-0.55 to +2.17) | 52% | +1.49% | 41% |
| Core + steady climb + recent power gap | 2014-2026 (all) | 3006 | 10.0 | +0.13% | +0.27% | +0.51% (-0.31 to +1.33) | 50% | +1.41% | 40% |

### AI score: the best 10% each day (30-40 stocks, so much less noise; the score is chosen here)

| List | Period | Days | Picks/day | 5-day vs avg stock | 10-day | 20-day (95% range) | Beat avg (20d) | Avg 20-day return | Broke out in 10d |
|---|---|---|---|---|---|---|---|---|---|
| 12-month momentum (skip the last month) | 2014-2021 (chosen here) | 1827 | 17.9 | +0.22% | +0.53% | +1.14% (+0.49 to +1.80) | 50% | +2.18% | 27% |
| 12-month momentum (skip the last month) | 2022-2026 (unseen) | 1179 | 30.6 | +0.16% | +0.39% | +0.85% (-0.42 to +2.11) | 50% | +1.53% | 26% |
| 12-month momentum (skip the last month) | 2014-2026 (all) | 3006 | 22.9 | +0.20% | +0.47% | +1.03% (+0.46 to +1.59) | 50% | +1.93% | 27% |
| Momentum per unit of volatility | 2014-2021 (chosen here) | 1827 | 17.9 | +0.17% | +0.33% | +0.63% (+0.05 to +1.22) | 49% | +1.67% | 28% |
| Momentum per unit of volatility | 2022-2026 (unseen) | 1179 | 30.6 | +0.13% | +0.25% | +0.51% (-0.56 to +1.58) | 49% | +1.20% | 27% |
| Momentum per unit of volatility | 2014-2026 (all) | 3006 | 22.9 | +0.15% | +0.30% | +0.59% (+0.06 to +1.11) | 49% | +1.49% | 28% |
| Closeness to the 52-week high | 2014-2021 (chosen here) | 1807 | 18.6 | -0.01% | -0.08% | -0.08% (-0.53 to +0.37) | 49% | +0.97% | 60% |
| Closeness to the 52-week high | 2022-2026 (unseen) | 1175 | 31.2 | -0.07% | -0.16% | -0.39% (-0.89 to +0.12) | 47% | +0.31% | 57% |
| Closeness to the 52-week high | 2014-2026 (all) | 2982 | 23.6 | -0.04% | -0.11% | -0.20% (-0.52 to +0.12) | 48% | +0.71% | 59% |
| IBD-style relative strength | 2014-2021 (chosen here) | 1827 | 17.9 | +0.19% | +0.46% | +1.06% (+0.40 to +1.72) | 50% | +2.10% | 38% |
| IBD-style relative strength | 2022-2026 (unseen) | 1179 | 30.6 | +0.18% | +0.42% | +0.82% (-0.39 to +2.03) | 50% | +1.50% | 39% |
| IBD-style relative strength | 2014-2026 (all) | 3006 | 22.9 | +0.18% | +0.44% | +0.97% (+0.36 to +1.57) | 50% | +1.87% | 39% |
| Momentum/vol + 52w high + industry strength | 2014-2021 (chosen here) | 1827 | 18.0 | +0.14% | +0.25% | +0.46% (-0.12 to +1.04) | 49% | +1.50% | 39% |
| Momentum/vol + 52w high + industry strength | 2022-2026 (unseen) | 1179 | 30.8 | +0.07% | +0.19% | +0.35% (-0.86 to +1.56) | 49% | +1.03% | 37% |
| Momentum/vol + 52w high + industry strength | 2014-2026 (all) | 3006 | 23.0 | +0.11% | +0.23% | +0.42% (-0.16 to +1.00) | 49% | +1.32% | 38% |
| Core + steady climb | 2014-2021 (chosen here) | 1827 | 18.0 | +0.06% | +0.14% | +0.25% (-0.28 to +0.77) | 49% | +1.29% | 36% |
| Core + steady climb | 2022-2026 (unseen) | 1179 | 30.8 | +0.06% | +0.13% | +0.26% (-0.78 to +1.31) | 49% | +0.95% | 35% |
| Core + steady climb | 2014-2026 (all) | 3006 | 23.0 | +0.06% | +0.14% | +0.25% (-0.29 to +0.80) | 49% | +1.15% | 35% |
| Core + steady climb + recent power gap | 2014-2021 (chosen here) | 1827 | 18.0 | +0.07% | +0.12% | +0.20% (-0.47 to +0.87) | 49% | +1.24% | 38% |
| Core + steady climb + recent power gap | 2022-2026 (unseen) | 1179 | 30.8 | +0.10% | +0.21% | +0.34% (-0.58 to +1.27) | 49% | +1.03% | 37% |
| Core + steady climb + recent power gap | 2014-2026 (all) | 3006 | 23.0 | +0.08% | +0.15% | +0.26% (-0.32 to +0.83) | 49% | +1.16% | 38% |

### AI picks as a managed list (10 stocks, entries and exits at the next open, 0.10% cost each way)

Score versions, all with the same rules (hold 10, keep while in the top 30, max 3 per sector):

| Version | Period | Return/yr | vs avg stock/yr (95% range) | Sharpe | Worst drop | Picks made | Avg pick | Picks up | Days held (median) |
|---|---|---|---|---|---|---|---|---|---|
| 12-month momentum (skip the last month) | 2014-2021 (chosen here) | +24.1% | +13.4% (-4.17 to +30.92) | 0.78 | -52% | 298 | +9.0% | 48% | 28 |
| 12-month momentum (skip the last month) | 2022-2026 (unseen) | +17.9% | +13.4% (-9.01 to +35.88) | 0.63 | -32% | 227 | +3.8% | 49% | 20 |
| 12-month momentum (skip the last month) | 2014-2026 (all) | +21.6% | +13.4% (-0.43 to +27.23) | 0.72 | -52% | 525 | +6.7% | 49% | 24 |
| Momentum per unit of volatility | 2014-2021 (chosen here) | +22.0% | +10.0% (-6.15 to +26.23) | 0.79 | -49% | 327 | +7.4% | 48% | 25 |
| Momentum per unit of volatility | 2022-2026 (unseen) | +16.3% | +10.0% (-9.42 to +29.49) | 0.65 | -32% | 226 | +4.9% | 51% | 26 |
| Momentum per unit of volatility | 2014-2026 (all) | +19.8% | +10.0% (-2.41 to +22.49) | 0.73 | -49% | 553 | +6.4% | 49% | 26 |
| Closeness to the 52-week high | 2014-2021 (chosen here) | +1.8% | -11.5% (-23.95 to +0.92) | 0.19 | -41% | 1548 | +0.4% | 45% | 5 |
| Closeness to the 52-week high | 2022-2026 (unseen) | +3.4% | -4.5% (-19.95 to +10.89) | 0.27 | -29% | 1862 | +0.3% | 41% | 3 |
| Closeness to the 52-week high | 2014-2026 (all) | +2.4% | -8.8% (-18.47 to +0.91) | 0.22 | -41% | 3410 | +0.4% | 43% | 4 |
| IBD-style relative strength | 2014-2021 (chosen here) | +36.0% | +22.3% (+4.67 to +40.00) | 1.04 | -46% | 340 | +10.3% | 44% | 24 |
| IBD-style relative strength | 2022-2026 (unseen) | +13.0% | +9.2% (-13.15 to +31.59) | 0.51 | -38% | 265 | +2.8% | 41% | 23 |
| IBD-style relative strength | 2014-2026 (all) | +26.5% | +17.2% (+3.30 to +31.08) | 0.83 | -46% | 605 | +7.0% | 43% | 24 |
| Momentum/vol + 52w high + industry strength | 2014-2021 (chosen here) | +22.0% | +9.5% (-5.22 to +24.26) | 0.82 | -46% | 445 | +5.8% | 48% | 20 |
| Momentum/vol + 52w high + industry strength | 2022-2026 (unseen) | +16.6% | +9.5% (-7.73 to +26.75) | 0.69 | -31% | 358 | +2.8% | 43% | 15 |
| Momentum/vol + 52w high + industry strength | 2014-2026 (all) | +19.9% | +9.5% (-1.71 to +20.74) | 0.77 | -46% | 803 | +4.5% | 46% | 17 |
| Core + steady climb | 2014-2021 (chosen here) | +14.9% | +3.3% (-11.34 to +18.04) | 0.62 | -48% | 428 | +4.6% | 48% | 19 |
| Core + steady climb | 2022-2026 (unseen) | +21.8% | +13.7% (-3.67 to +31.04) | 0.85 | -29% | 282 | +4.3% | 49% | 19 |
| Core + steady climb | 2014-2026 (all) | +17.5% | +7.4% (-3.83 to +18.64) | 0.71 | -48% | 710 | +4.4% | 48% | 19 |
| Core + steady climb + recent power gap | 2014-2021 (chosen here) | +21.4% | +8.8% (-5.77 to +23.39) | 0.81 | -43% | 496 | +5.2% | 48% | 16 |
| Core + steady climb + recent power gap | 2022-2026 (unseen) | +14.0% | +7.1% (-9.59 to +23.70) | 0.61 | -30% | 414 | +2.2% | 44% | 14 |
| Core + steady climb + recent power gap | 2014-2026 (all) | +18.5% | +8.1% (-2.89 to +19.13) | 0.74 | -43% | 910 | +3.8% | 46% | 15 |
| *Average liquid stock (equal weight)* | 2014-2021 (chosen here) | +12.9% | | 0.63 | -50% | | | | |
| *SPY* | 2014-2021 (chosen here) | +15.4% | | 0.96 | -32% | | | | |
| *Average liquid stock (equal weight)* | 2022-2026 (unseen) | +7.4% | | 0.42 | -27% | | | | |
| *SPY* | 2022-2026 (unseen) | +11.9% | | 0.73 | -26% | | | | |
| *Average liquid stock (equal weight)* | 2014-2026 (all) | +10.7% | | 0.55 | -50% | | | | |
| *SPY* | 2014-2026 (all) | +14.0% | | 0.86 | -32% | | | | |

Score chosen on the best 10% in 2014-2021 (S&P 500): **IBD-style relative strength**. Rule versions for it (chosen on the 2014-2021 Sharpe ratio):

| Version | Period | Return/yr | vs avg stock/yr (95% range) | Sharpe | Worst drop | Picks made | Avg pick | Picks up | Days held (median) |
|---|---|---|---|---|---|---|---|---|---|
| Hold 10, keep while in the top 30, max 3 per sector | 2014-2021 (chosen here) | +36.0% | +22.3% (+4.67 to +40.00) | 1.04 | -46% | 340 | +10.3% | 44% | 24 |
| Hold 10, keep while in the top 30, max 3 per sector | 2022-2026 (unseen) | +13.0% | +9.2% (-13.15 to +31.59) | 0.51 | -38% | 265 | +2.8% | 41% | 23 |
| Hold 10, keep while in the top 30, max 3 per sector | 2014-2026 (all) | +26.5% | +17.2% (+3.30 to +31.08) | 0.83 | -46% | 605 | +7.0% | 43% | 24 |
| Keep only while in the top 20 | 2014-2021 (chosen here) | +30.4% | +17.9% (+0.42 to +35.32) | 0.93 | -50% | 502 | +5.7% | 44% | 15 |
| Keep only while in the top 20 | 2022-2026 (unseen) | +4.7% | +1.3% (-20.28 to +22.80) | 0.31 | -40% | 430 | +0.9% | 39% | 10 |
| Keep only while in the top 20 | 2014-2026 (all) | +19.6% | +11.4% (-2.24 to +24.95) | 0.68 | -50% | 932 | +3.5% | 42% | 12 |
| Keep while in the top 50 | 2014-2021 (chosen here) | +36.8% | +22.7% (+5.17 to +40.28) | 1.06 | -45% | 252 | +14.6% | 48% | 34 |
| Keep while in the top 50 | 2022-2026 (unseen) | +22.5% | +17.5% (-3.89 to +38.89) | 0.73 | -31% | 169 | +4.9% | 45% | 49 |
| Keep while in the top 50 | 2014-2026 (all) | +31.0% | +20.7% (+7.10 to +34.25) | 0.93 | -45% | 421 | +10.7% | 47% | 39 |
| Also sell on a close below EMA50 | 2014-2021 (chosen here) | +24.2% | +11.3% (-5.23 to +27.90) | 0.87 | -42% | 933 | +2.2% | 40% | 9 |
| Also sell on a close below EMA50 | 2022-2026 (unseen) | +0.9% | -3.9% (-23.86 to +16.11) | 0.19 | -37% | 653 | +0.5% | 37% | 8 |
| Also sell on a close below EMA50 | 2014-2026 (all) | +14.5% | +5.4% (-7.42 to +18.16) | 0.59 | -45% | 1586 | +1.5% | 39% | 9 |
| Also sell on your exit (10 EMA under the 20 and price under the 50, daily) | 2014-2021 (chosen here) | +24.0% | +11.3% (-5.48 to +28.16) | 0.85 | -41% | 873 | +2.3% | 40% | 10 |
| Also sell on your exit (10 EMA under the 20 and price under the 50, daily) | 2022-2026 (unseen) | +1.4% | -3.1% (-23.35 to +17.07) | 0.21 | -34% | 612 | +0.4% | 37% | 10 |
| Also sell on your exit (10 EMA under the 20 and price under the 50, daily) | 2014-2026 (all) | +14.6% | +5.7% (-7.30 to +18.63) | 0.59 | -41% | 1485 | +1.5% | 39% | 10 |
| No new picks while SPY is below its 200-day average | 2014-2021 (chosen here) | +34.1% | +20.3% (+2.29 to +38.28) | 1.03 | -37% | 295 | +11.4% | 42% | 26 |
| No new picks while SPY is below its 200-day average | 2022-2026 (unseen) | +14.4% | +9.6% (-12.70 to +31.93) | 0.56 | -37% | 218 | +3.7% | 41% | 24 |
| No new picks while SPY is below its 200-day average | 2014-2026 (all) | +26.0% | +16.1% (+2.08 to +30.12) | 0.85 | -37% | 513 | +8.1% | 42% | 25 |
| Both of the above | 2014-2021 (chosen here) | +19.4% | +6.9% (-11.40 to +25.24) | 0.77 | -34% | 750 | +2.2% | 39% | 11 |
| Both of the above | 2022-2026 (unseen) | -1.9% | -7.6% (-28.37 to +13.09) | 0.08 | -35% | 485 | +0.2% | 34% | 11 |
| Both of the above | 2014-2026 (all) | +10.6% | +1.2% (-12.60 to +15.03) | 0.50 | -44% | 1235 | +1.4% | 37% | 11 |
| *Average liquid stock (equal weight)* | 2014-2021 (chosen here) | +12.9% | | 0.63 | -50% | | | | |
| *SPY* | 2014-2021 (chosen here) | +15.4% | | 0.96 | -32% | | | | |
| *Average liquid stock (equal weight)* | 2022-2026 (unseen) | +7.4% | | 0.42 | -27% | | | | |
| *SPY* | 2022-2026 (unseen) | +11.9% | | 0.73 | -26% | | | | |
| *Average liquid stock (equal weight)* | 2014-2026 (all) | +10.7% | | 0.55 | -50% | | | | |
| *SPY* | 2014-2026 (all) | +14.0% | | 0.86 | -32% | | | | |

Chosen rule: **Keep only while in the top 20**.

Year by year (chosen version):

| Year | AI picks | Average stock | SPY |
|---|---|---|---|
| 2014 | +6.2% | +2.6% | +5.7% |
| 2015 | -3.1% | -8.1% | +0.7% |
| 2016 | +5.7% | +18.2% | +14.4% |
| 2017 | +32.5% | +18.1% | +21.5% |
| 2018 | +19.7% | -14.5% | -6.0% |
| 2019 | +80.0% | +26.9% | +31.8% |
| 2020 | +49.0% | +19.0% | +16.8% |
| 2021 | +48.5% | +41.5% | +31.9% |
| 2022 | -1.5% | -16.2% | -18.7% |
| 2023 | -5.3% | +18.2% | +24.6% |
| 2024 | +25.4% | +10.4% | +26.5% |
| 2025 | +7.7% | +9.6% | +18.2% |
| 2026 | -1.8% | +16.3% | +11.7% |

### New uptrends (each ordering's top 5 a day, against the whole list)

| List | Period | Days | Picks/day | 5-day vs avg stock | 10-day | 20-day (95% range) | Beat avg (20d) | Avg 20-day return | Broke out in 10d |
|---|---|---|---|---|---|---|---|---|---|
| Every new uptrend | 2014-2021 (chosen here) | 1151 | 3.6 | +0.01% | +0.12% | -0.00% (-0.54 to +0.54) | 50% | +1.00% | 35% |
| Every new uptrend | 2022-2026 (unseen) | 913 | 6.3 | -0.11% | -0.17% | -0.25% (-0.72 to +0.23) | 47% | +0.69% | 35% |
| Every new uptrend | 2014-2026 (all) | 2064 | 4.8 | -0.04% | -0.01% | -0.11% (-0.46 to +0.24) | 48% | +0.86% | 35% |
| Strongest relative strength first | 2014-2021 (chosen here) | 1149 | 3.0 | +0.01% | +0.11% | -0.03% (-0.61 to +0.55) | 49% | +0.95% | 33% |
| Strongest relative strength first | 2022-2026 (unseen) | 911 | 3.9 | -0.03% | -0.04% | -0.05% (-0.56 to +0.47) | 47% | +0.89% | 33% |
| Strongest relative strength first | 2014-2026 (all) | 2060 | 3.4 | -0.01% | +0.05% | -0.04% (-0.43 to +0.36) | 48% | +0.92% | 33% |
| Closest to the 52-week high first | 2014-2021 (chosen here) | 1151 | 3.0 | +0.03% | +0.10% | -0.06% (-0.62 to +0.50) | 49% | +0.95% | 34% |
| Closest to the 52-week high first | 2022-2026 (unseen) | 913 | 3.9 | -0.08% | -0.20% | -0.37% (-0.84 to +0.11) | 46% | +0.57% | 35% |
| Closest to the 52-week high first | 2014-2026 (all) | 2064 | 3.4 | -0.02% | -0.03% | -0.20% (-0.58 to +0.19) | 48% | +0.78% | 34% |
| Highest volume on the day it turned | 2014-2021 (chosen here) | 1151 | 3.0 | -0.02% | +0.09% | -0.01% (-0.56 to +0.55) | 49% | +1.00% | 35% |
| Highest volume on the day it turned | 2022-2026 (unseen) | 913 | 3.9 | -0.10% | -0.15% | -0.29% (-0.76 to +0.19) | 47% | +0.65% | 36% |
| Highest volume on the day it turned | 2014-2026 (all) | 2064 | 3.4 | -0.06% | -0.02% | -0.13% (-0.51 to +0.25) | 48% | +0.84% | 36% |
| Best AI score first | 2014-2021 (chosen here) | 1149 | 3.0 | +0.01% | +0.11% | -0.03% (-0.61 to +0.55) | 49% | +0.95% | 33% |
| Best AI score first | 2022-2026 (unseen) | 911 | 3.9 | -0.03% | -0.04% | -0.05% (-0.56 to +0.47) | 47% | +0.89% | 33% |
| Best AI score first | 2014-2026 (all) | 2060 | 3.4 | -0.01% | +0.05% | -0.04% (-0.43 to +0.36) | 48% | +0.92% | 33% |
| Out of an uptrend for 20+ days, then relative strength | 2014-2021 (chosen here) | 624 | 1.8 | -0.40% | -0.26% | -0.02% (-1.12 to +1.08) | 49% | +0.89% | 35% |
| Out of an uptrend for 20+ days, then relative strength | 2022-2026 (unseen) | 624 | 2.4 | -0.16% | -0.19% | -0.51% (-0.92 to -0.10) | 46% | +0.33% | 36% |
| Out of an uptrend for 20+ days, then relative strength | 2014-2026 (all) | 1248 | 2.1 | -0.28% | -0.22% | -0.26% (-0.90 to +0.38) | 48% | +0.61% | 35% |
| Strongest sector first | 2014-2021 (chosen here) | 1151 | 3.0 | +0.00% | +0.11% | -0.06% (-0.57 to +0.45) | 49% | +0.95% | 34% |
| Strongest sector first | 2022-2026 (unseen) | 913 | 3.9 | -0.10% | -0.20% | -0.32% (-0.94 to +0.30) | 46% | +0.61% | 33% |
| Strongest sector first | 2014-2026 (all) | 2064 | 3.4 | -0.04% | -0.03% | -0.18% (-0.53 to +0.18) | 48% | +0.80% | 34% |
| Baseline: stocks already in an uptrend | 2014-2021 (chosen here) | 1827 | 68.5 | -0.04% | -0.05% | -0.06% (-0.36 to +0.23) | 48% | +0.98% | 45% |
| Baseline: stocks already in an uptrend | 2022-2026 (unseen) | 1179 | 109.4 | -0.08% | -0.13% | -0.21% (-0.73 to +0.31) | 48% | +0.47% | 43% |
| Baseline: stocks already in an uptrend | 2014-2026 (all) | 3006 | 84.6 | -0.06% | -0.08% | -0.12% (-0.41 to +0.17) | 48% | +0.78% | 44% |

Chosen: **Every new uptrend** (an ordering had to beat the whole list by 0.10% in 2014-2021).

### Breakout watch (top 10 a day)

| List | Period | Days | Picks/day | 5-day vs avg stock | 10-day | 20-day (95% range) | Beat avg (20d) | Avg 20-day return | Broke out in 10d |
|---|---|---|---|---|---|---|---|---|---|
| Every stock within 5% of its 50-day high | 2014-2021 (chosen here) | 1346 | 16.8 | -0.09% | -0.12% | -0.24% (-0.79 to +0.31) | 49% | +0.75% | 42% |
| Every stock within 5% of its 50-day high | 2022-2026 (unseen) | 976 | 22.7 | -0.12% | -0.28% | -0.52% (-0.87 to -0.18) | 46% | +0.37% | 46% |
| Every stock within 5% of its 50-day high | 2014-2026 (all) | 2322 | 19.2 | -0.10% | -0.19% | -0.36% (-0.74 to +0.02) | 47% | +0.59% | 44% |
| Closest to the breakout level | 2014-2021 (chosen here) | 1346 | 9.0 | -0.04% | -0.05% | -0.13% (-0.71 to +0.45) | 50% | +0.86% | 52% |
| Closest to the breakout level | 2022-2026 (unseen) | 976 | 9.3 | -0.18% | -0.37% | -0.66% (-1.08 to -0.24) | 46% | +0.23% | 54% |
| Closest to the breakout level | 2014-2026 (all) | 2322 | 9.1 | -0.10% | -0.19% | -0.35% (-0.77 to +0.06) | 48% | +0.60% | 53% |
| Uptrend + tightest range, shrinking ranges, drying volume, closest | 2014-2021 (chosen here) | 1335 | 8.3 | -0.09% | -0.18% | -0.33% (-0.91 to +0.24) | 48% | +0.65% | 46% |
| Uptrend + tightest range, shrinking ranges, drying volume, closest | 2022-2026 (unseen) | 969 | 8.9 | -0.14% | -0.28% | -0.64% (-1.01 to -0.27) | 45% | +0.20% | 45% |
| Uptrend + tightest range, shrinking ranges, drying volume, closest | 2014-2026 (all) | 2304 | 8.6 | -0.11% | -0.22% | -0.46% (-0.85 to -0.07) | 47% | +0.46% | 46% |
| Same + relative strength | 2014-2021 (chosen here) | 1335 | 8.3 | -0.09% | -0.17% | -0.31% (-0.89 to +0.27) | 48% | +0.67% | 46% |
| Same + relative strength | 2022-2026 (unseen) | 969 | 8.9 | -0.15% | -0.33% | -0.67% (-1.07 to -0.26) | 46% | +0.18% | 46% |
| Same + relative strength | 2014-2026 (all) | 2304 | 8.6 | -0.11% | -0.24% | -0.46% (-0.86 to -0.06) | 47% | +0.46% | 46% |
| Minervini trend template, strongest RS first | 2014-2021 (chosen here) | 1256 | 6.5 | -0.18% | -0.22% | -0.11% (-0.91 to +0.69) | 48% | +0.51% | 44% |
| Minervini trend template, strongest RS first | 2022-2026 (unseen) | 951 | 7.0 | -0.14% | -0.44% | -0.76% (-1.64 to +0.12) | 46% | +0.03% | 48% |
| Minervini trend template, strongest RS first | 2014-2026 (all) | 2207 | 6.7 | -0.16% | -0.32% | -0.39% (-0.97 to +0.19) | 47% | +0.30% | 46% |
| Uptrend + Bollinger squeeze, strongest RS first | 2014-2021 (chosen here) | 877 | 2.6 | -0.34% | -0.24% | -0.14% (-0.97 to +0.69) | 49% | +0.58% | 44% |
| Uptrend + Bollinger squeeze, strongest RS first | 2022-2026 (unseen) | 667 | 3.0 | -0.37% | -0.75% | -0.73% (-1.36 to -0.10) | 44% | -0.30% | 39% |
| Uptrend + Bollinger squeeze, strongest RS first | 2014-2026 (all) | 1544 | 2.8 | -0.35% | -0.46% | -0.39% (-0.93 to +0.15) | 47% | +0.20% | 41% |
| Baseline: every liquid stock | 2014-2021 (chosen here) | 1827 | 175.8 | +0.00% | -0.00% | +0.00% (-0.00 to +0.00) | 48% | +1.04% | 23% |
| Baseline: every liquid stock | 2022-2026 (unseen) | 1179 | 303.1 | +0.00% | -0.00% | +0.00% (-0.00 to +0.00) | 48% | +0.68% | 22% |
| Baseline: every liquid stock | 2014-2026 (all) | 3006 | 225.8 | +0.00% | -0.00% | +0.00% (-0.00 to +0.00) | 48% | +0.90% | 22% |

Chosen: **Closest to the breakout level** (best 2014-2021 return among lists that broke out at least 1.5x as often as the average stock; returns within 0.01% count as a tie, and a tie goes to the list that broke out more often).

## Caveats

- S&P 500 membership is rebuilt from Wikipedia's change log. Stocks that left the index and no longer trade (most were bought out) have no Yahoo data, so they are missing from the days they were members.
- The S&P 400 + 600 check uses today's members for all years, so it favors stocks that did well.
- Returns include dividends (Yahoo's adjusted prices). The AI picks list pays 0.10% per buy and per sell; the daily lists have no costs.
