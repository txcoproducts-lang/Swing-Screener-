# Pick lists backtest

Produced by `research/picks_backtest.py` in the [Pick lists backtest run](https://github.com/txcoproducts-lang/Swing-Screener-/actions/runs/37290983347) (2026-10-05). Re-run it from the Actions tab ("Pick lists backtest") to refresh these numbers.

Data 2013-06-03 to 2026-10-02, 1493 tickers. Signals from 2014-10; every choice was made on 2014-2021 S&P 500 data and then checked on 2022-2026. Entry at the next open; returns are compared with the average liquid stock in the same universe over the same days.

## The chosen lists

Chosen: {'ai_score': 'rs', 'ai_rule': 'keep20', 'new_up': 'all', 'breakout': 'tight'}. The page (CFG in screener.py) uses: {'new_up': 'all', 'breakout': 'tight', 'ai_score': 'rs', 'ai_rule': 'keep20'}.

### S&P 500 as it was each day

| List | Version | Period | vs avg stock | Notes |
|---|---|---|---|---|
| New uptrends | Every new uptrend | 2014-2021 (chosen here) | +0.03% over 20 days (-0.20 to +0.25) | 8.4 a day, 51% beat the average stock |
| New uptrends | Every new uptrend | 2022-2026 (unseen) | -0.30% over 20 days (-0.58 to -0.02) | 9.9 a day, 48% beat the average stock |
| New uptrends | Every new uptrend | 2014-2026 (all) | -0.10% over 20 days (-0.28 to +0.08) | 9.0 a day, 50% beat the average stock |
| Breakout watch | Uptrend + tightest range, shrinking ranges, drying volume, closest | 2014-2021 (chosen here) | -0.11% over 20 days (-0.49 to +0.27) | broke out within 10 days 49% of the time vs 29% for all stocks |
| Breakout watch | Uptrend + tightest range, shrinking ranges, drying volume, closest | 2022-2026 (unseen) | -0.59% over 20 days (-1.19 to +0.00) | broke out within 10 days 45% of the time vs 25% for all stocks |
| Breakout watch | Uptrend + tightest range, shrinking ranges, drying volume, closest | 2014-2026 (all) | -0.30% over 20 days (-0.61 to +0.02) | broke out within 10 days 47% of the time vs 27% for all stocks |
| AI picks | IBD-style relative strength, keep only while in the top 20 | 2014-2021 (chosen here) | -2.7% a year (-13.34 to +7.84) | +11.9%/yr vs +16.4% average stock and +15.4% SPY; worst drop -31%; 513 picks, median hold 19 days |
| AI picks | IBD-style relative strength, keep only while in the top 20 | 2022-2026 (unseen) | +20.1% a year (+2.19 to +38.07) | +32.3%/yr vs +11.6% average stock and +12.3% SPY; worst drop -29%; 380 picks, median hold 8 days |
| AI picks | IBD-style relative strength, keep only while in the top 20 | 2014-2026 (all) | +6.2% a year (-3.43 to +15.81) | +19.4%/yr vs +14.5% average stock and +14.2% SPY; worst drop -31%; 893 picks, median hold 14 days |

### S&P 400 + 600 (today's members)

| List | Version | Period | vs avg stock | Notes |
|---|---|---|---|---|
| New uptrends | Every new uptrend | 2014-2021 (chosen here) | -0.06% over 20 days (-0.42 to +0.30) | 4.5 a day, 48% beat the average stock |
| New uptrends | Every new uptrend | 2022-2026 (unseen) | +0.06% over 20 days (-0.28 to +0.41) | 7.8 a day, 48% beat the average stock |
| New uptrends | Every new uptrend | 2014-2026 (all) | -0.01% over 20 days (-0.26 to +0.24) | 5.8 a day, 48% beat the average stock |
| Breakout watch | Uptrend + tightest range, shrinking ranges, drying volume, closest | 2014-2021 (chosen here) | -0.13% over 20 days (-0.59 to +0.34) | broke out within 10 days 47% of the time vs 23% for all stocks |
| Breakout watch | Uptrend + tightest range, shrinking ranges, drying volume, closest | 2022-2026 (unseen) | -0.44% over 20 days (-0.96 to +0.08) | broke out within 10 days 46% of the time vs 22% for all stocks |
| Breakout watch | Uptrend + tightest range, shrinking ranges, drying volume, closest | 2014-2026 (all) | -0.25% over 20 days (-0.63 to +0.13) | broke out within 10 days 46% of the time vs 22% for all stocks |
| AI picks | IBD-style relative strength, keep only while in the top 20 | 2014-2021 (chosen here) | +22.9% a year (+4.43 to +41.27) | +35.5%/yr vs +13.1% average stock and +15.4% SPY; worst drop -47%; 476 picks, median hold 18 days |
| AI picks | IBD-style relative strength, keep only while in the top 20 | 2022-2026 (unseen) | +2.7% a year (-18.47 to +23.85) | +6.3%/yr vs +7.8% average stock and +12.3% SPY; worst drop -38%; 403 picks, median hold 12 days |
| AI picks | IBD-style relative strength, keep only while in the top 20 | 2014-2026 (all) | +15.0% a year (+0.98 to +28.97) | +23.2%/yr vs +11.0% average stock and +14.2% SPY; worst drop -47%; 879 picks, median hold 16 days |

## S&P 500 as it was each day
About 331 liquid stocks a day.

### Signal report card
Each signal on its own: the best 10% of stocks by that signal each day, and the worst 10%, against the average stock over the next 20 trading days.

| Signal | Period | Top 10% vs avg stock, 20 days (95% range) | Bottom 10% | Rank correlation |
|---|---|---|---|---|
| 12-month momentum, skip last month | 2014-2021 (chosen here) | -0.33% (-0.70 to +0.05) | +0.35% | -0.019 |
| 12-month momentum, skip last month | 2022-2026 (unseen) | +0.87% (-0.09 to +1.82) | +0.09% | +0.020 |
| 12-month momentum, skip last month | 2014-2026 (all) | +0.14% (-0.32 to +0.60) | +0.25% | -0.004 |
| momentum / volatility | 2014-2021 (chosen here) | -0.40% (-0.88 to +0.09) | +0.23% | -0.018 |
| momentum / volatility | 2022-2026 (unseen) | +0.54% (-0.22 to +1.29) | -0.40% | +0.022 |
| momentum / volatility | 2014-2026 (all) | -0.03% (-0.44 to +0.38) | -0.02% | -0.002 |
| 6-month momentum, skip last month | 2014-2021 (chosen here) | -0.02% (-0.37 to +0.32) | +0.25% | -0.007 |
| 6-month momentum, skip last month | 2022-2026 (unseen) | +0.49% (-0.35 to +1.33) | +0.35% | -0.009 |
| 6-month momentum, skip last month | 2014-2026 (all) | +0.18% (-0.21 to +0.56) | +0.29% | -0.008 |
| IBD-style relative strength | 2014-2021 (chosen here) | -0.27% (-0.61 to +0.08) | +0.17% | -0.015 |
| IBD-style relative strength | 2022-2026 (unseen) | +0.70% (-0.22 to +1.62) | +0.21% | +0.004 |
| IBD-style relative strength | 2014-2026 (all) | +0.11% (-0.31 to +0.53) | +0.18% | -0.008 |
| closeness to the 52-week high | 2014-2021 (chosen here) | -0.31% (-0.68 to +0.06) | +0.47% | -0.025 |
| closeness to the 52-week high | 2022-2026 (unseen) | -0.32% (-0.97 to +0.33) | +0.29% | -0.005 |
| closeness to the 52-week high | 2014-2026 (all) | -0.31% (-0.60 to -0.03) | +0.40% | -0.017 |
| industry strength (6 months) | 2014-2021 (chosen here) | -0.12% (-0.44 to +0.19) | -0.14% | -0.007 |
| industry strength (6 months) | 2022-2026 (unseen) | +0.48% (-0.45 to +1.42) | +0.36% | -0.002 |
| industry strength (6 months) | 2014-2026 (all) | +0.11% (-0.34 to +0.56) | +0.05% | -0.005 |
| share of the sector in an uptrend | 2014-2021 (chosen here) | -0.48% (-1.00 to +0.03) | -0.14% | -0.032 |
| share of the sector in an uptrend | 2022-2026 (unseen) | -0.36% (-1.16 to +0.44) | -0.06% | -0.005 |
| share of the sector in an uptrend | 2014-2026 (all) | -0.44% (-0.89 to +0.02) | -0.11% | -0.021 |
| steady climb (frog in the pan) | 2014-2021 (chosen here) | -0.22% (-0.65 to +0.20) | -0.10% | -0.006 |
| steady climb (frog in the pan) | 2022-2026 (unseen) | +0.23% (-0.34 to +0.79) | -0.08% | +0.021 |
| steady climb (frog in the pan) | 2014-2026 (all) | -0.05% (-0.41 to +0.31) | -0.09% | +0.005 |
| recent power gap that held | 2014-2021 (chosen here) | -0.58% (-1.04 to -0.12) | n/a | -0.008 |
| recent power gap that held | 2022-2026 (unseen) | -0.27% (-1.10 to +0.55) | n/a | -0.003 |
| recent power gap that held | 2014-2026 (all) | -0.46% (-0.89 to -0.02) | n/a | -0.006 |
| up-day vs down-day volume | 2014-2021 (chosen here) | -0.15% (-0.50 to +0.21) | +0.28% | -0.019 |
| up-day vs down-day volume | 2022-2026 (unseen) | -0.09% (-0.57 to +0.39) | +0.27% | -0.018 |
| up-day vs down-day volume | 2014-2026 (all) | -0.12% (-0.40 to +0.15) | +0.28% | -0.019 |
| low volatility | 2014-2021 (chosen here) | -0.13% (-0.66 to +0.41) | +0.29% | -0.010 |
| low volatility | 2022-2026 (unseen) | -0.31% (-0.89 to +0.27) | +1.19% | -0.031 |
| low volatility | 2014-2026 (all) | -0.20% (-0.68 to +0.28) | +0.64% | -0.018 |
| 1-week pullback | 2014-2021 (chosen here) | +0.20% (-0.19 to +0.58) | -0.16% | +0.014 |
| 1-week pullback | 2022-2026 (unseen) | +0.45% (+0.17 to +0.73) | +0.23% | +0.007 |
| 1-week pullback | 2014-2026 (all) | +0.30% (+0.05 to +0.55) | -0.01% | +0.011 |
| 1-month pullback | 2014-2021 (chosen here) | +0.22% (-0.40 to +0.84) | -0.35% | +0.032 |
| 1-month pullback | 2022-2026 (unseen) | +0.20% (-0.34 to +0.75) | +0.43% | -0.002 |
| 1-month pullback | 2014-2026 (all) | +0.21% (-0.18 to +0.61) | -0.05% | +0.019 |
| in an uptrend (your rule) | 2014-2021 (chosen here) | -0.16% (-0.41 to +0.08) | +0.07% | -0.017 |
| in an uptrend (your rule) | 2022-2026 (unseen) | -0.26% (-0.66 to +0.14) | -0.03% | -0.004 |
| in an uptrend (your rule) | 2014-2026 (all) | -0.20% (-0.44 to +0.04) | +0.04% | -0.012 |
| Minervini trend template | 2014-2021 (chosen here) | -0.28% (-0.56 to +0.01) | +0.11% | -0.022 |
| Minervini trend template | 2022-2026 (unseen) | -0.13% (-0.75 to +0.48) | -0.04% | +0.003 |
| Minervini trend template | 2014-2026 (all) | -0.22% (-0.53 to +0.09) | +0.05% | -0.012 |
| not stretched above EMA20 | 2014-2021 (chosen here) | +0.21% (-0.19 to +0.61) | -0.31% | +0.027 |
| not stretched above EMA20 | 2022-2026 (unseen) | +0.05% (-0.33 to +0.43) | +0.08% | -0.002 |
| not stretched above EMA20 | 2014-2026 (all) | +0.15% (-0.12 to +0.42) | -0.16% | +0.015 |
| volume drying up | 2014-2021 (chosen here) | +0.09% (-0.11 to +0.29) | -0.07% | +0.004 |
| volume drying up | 2022-2026 (unseen) | -0.05% (-0.41 to +0.31) | -0.01% | +0.002 |
| volume drying up | 2014-2026 (all) | +0.04% (-0.13 to +0.21) | -0.05% | +0.003 |
| ranges shrinking | 2014-2021 (chosen here) | +0.31% (+0.12 to +0.50) | -0.15% | +0.017 |
| ranges shrinking | 2022-2026 (unseen) | -0.10% (-0.43 to +0.24) | +0.01% | +0.003 |
| ranges shrinking | 2014-2026 (all) | +0.15% (-0.03 to +0.33) | -0.09% | +0.011 |

### AI score: the 10 best stocks each day

| List | Period | Days | Picks/day | 5-day vs avg stock | 10-day | 20-day (95% range) | Beat avg (20d) | Avg 20-day return | Broke out in 10d |
|---|---|---|---|---|---|---|---|---|---|
| 12-month momentum (skip the last month) | 2014-2021 (chosen here) | 1827 | 10.0 | -0.16% | -0.29% | -0.59% (-1.13 to -0.05) | 47% | +0.65% | 29% |
| 12-month momentum (skip the last month) | 2022-2026 (unseen) | 1171 | 10.0 | +0.43% | +0.93% | +2.02% (+0.13 to +3.92) | 54% | +2.95% | 32% |
| 12-month momentum (skip the last month) | 2014-2026 (all) | 2998 | 10.0 | +0.07% | +0.19% | +0.43% (-0.41 to +1.27) | 50% | +1.55% | 30% |
| Momentum per unit of volatility | 2014-2021 (chosen here) | 1827 | 10.0 | -0.15% | -0.31% | -0.66% (-1.22 to -0.10) | 46% | +0.58% | 33% |
| Momentum per unit of volatility | 2022-2026 (unseen) | 1171 | 10.0 | +0.42% | +0.89% | +1.70% (+0.02 to +3.38) | 53% | +2.63% | 32% |
| Momentum per unit of volatility | 2014-2026 (all) | 2998 | 10.0 | +0.07% | +0.16% | +0.27% (-0.54 to +1.07) | 49% | +1.38% | 33% |
| Closeness to the 52-week high | 2014-2021 (chosen here) | 1827 | 10.0 | -0.09% | -0.10% | -0.28% (-0.69 to +0.13) | 48% | +0.96% | 72% |
| Closeness to the 52-week high | 2022-2026 (unseen) | 1171 | 10.0 | -0.08% | -0.16% | -0.34% (-1.03 to +0.35) | 48% | +0.58% | 69% |
| Closeness to the 52-week high | 2014-2026 (all) | 2998 | 10.0 | -0.09% | -0.12% | -0.30% (-0.71 to +0.10) | 48% | +0.81% | 71% |
| IBD-style relative strength | 2014-2021 (chosen here) | 1827 | 10.0 | -0.15% | -0.23% | -0.36% (-0.84 to +0.11) | 47% | +0.88% | 45% |
| IBD-style relative strength | 2022-2026 (unseen) | 1171 | 10.0 | +0.44% | +0.96% | +2.21% (+0.07 to +4.34) | 54% | +3.13% | 45% |
| IBD-style relative strength | 2014-2026 (all) | 2998 | 10.0 | +0.08% | +0.24% | +0.64% (-0.26 to +1.54) | 50% | +1.76% | 45% |
| Momentum/vol + 52w high + industry strength | 2014-2021 (chosen here) | 1827 | 10.0 | -0.23% | -0.40% | -0.79% (-1.33 to -0.26) | 46% | +0.45% | 45% |
| Momentum/vol + 52w high + industry strength | 2022-2026 (unseen) | 1171 | 10.0 | +0.26% | +0.65% | +1.28% (-0.57 to +3.12) | 51% | +2.20% | 45% |
| Momentum/vol + 52w high + industry strength | 2014-2026 (all) | 2998 | 10.0 | -0.04% | +0.01% | +0.01% (-0.88 to +0.91) | 48% | +1.13% | 45% |
| Core + steady climb | 2014-2021 (chosen here) | 1827 | 10.0 | -0.23% | -0.44% | -0.88% (-1.48 to -0.28) | 45% | +0.36% | 44% |
| Core + steady climb | 2022-2026 (unseen) | 1171 | 10.0 | +0.24% | +0.52% | +1.12% (-0.58 to +2.83) | 51% | +2.05% | 41% |
| Core + steady climb | 2014-2026 (all) | 2998 | 10.0 | -0.05% | -0.06% | -0.10% (-0.99 to +0.79) | 48% | +1.02% | 43% |
| Core + steady climb + recent power gap | 2014-2021 (chosen here) | 1827 | 10.0 | -0.27% | -0.49% | -0.98% (-1.53 to -0.42) | 45% | +0.26% | 44% |
| Core + steady climb + recent power gap | 2022-2026 (unseen) | 1171 | 10.0 | +0.21% | +0.46% | +1.04% (-0.72 to +2.80) | 51% | +1.96% | 43% |
| Core + steady climb + recent power gap | 2014-2026 (all) | 2998 | 10.0 | -0.08% | -0.12% | -0.19% (-1.06 to +0.68) | 47% | +0.92% | 44% |

### AI score: the best 10% each day (30-40 stocks, so much less noise; the score is chosen here)

| List | Period | Days | Picks/day | 5-day vs avg stock | 10-day | 20-day (95% range) | Beat avg (20d) | Avg 20-day return | Broke out in 10d |
|---|---|---|---|---|---|---|---|---|---|
| 12-month momentum (skip the last month) | 2014-2021 (chosen here) | 1827 | 30.9 | -0.08% | -0.15% | -0.33% (-0.70 to +0.05) | 48% | +0.92% | 31% |
| 12-month momentum (skip the last month) | 2022-2026 (unseen) | 1171 | 37.6 | +0.17% | +0.40% | +0.87% (-0.09 to +1.82) | 50% | +1.79% | 30% |
| 12-month momentum (skip the last month) | 2014-2026 (all) | 2998 | 33.5 | +0.02% | +0.06% | +0.14% (-0.32 to +0.60) | 49% | +1.26% | 30% |
| Momentum per unit of volatility | 2014-2021 (chosen here) | 1827 | 30.9 | -0.09% | -0.18% | -0.40% (-0.88 to +0.09) | 48% | +0.84% | 33% |
| Momentum per unit of volatility | 2022-2026 (unseen) | 1171 | 37.6 | +0.13% | +0.27% | +0.54% (-0.21 to +1.29) | 50% | +1.46% | 31% |
| Momentum per unit of volatility | 2014-2026 (all) | 2998 | 33.5 | -0.00% | -0.01% | -0.03% (-0.44 to +0.38) | 49% | +1.08% | 32% |
| Closeness to the 52-week high | 2014-2021 (chosen here) | 1750 | 33.6 | -0.08% | -0.12% | -0.30% (-0.67 to +0.07) | 48% | +0.98% | 67% |
| Closeness to the 52-week high | 2022-2026 (unseen) | 1159 | 39.3 | -0.12% | -0.21% | -0.32% (-0.97 to +0.32) | 47% | +0.61% | 61% |
| Closeness to the 52-week high | 2014-2026 (all) | 2909 | 35.9 | -0.10% | -0.16% | -0.31% (-0.60 to -0.02) | 48% | +0.83% | 65% |
| IBD-style relative strength | 2014-2021 (chosen here) | 1827 | 30.9 | -0.10% | -0.15% | -0.27% (-0.61 to +0.08) | 48% | +0.97% | 45% |
| IBD-style relative strength | 2022-2026 (unseen) | 1171 | 37.6 | +0.14% | +0.28% | +0.70% (-0.22 to +1.62) | 50% | +1.62% | 43% |
| IBD-style relative strength | 2014-2026 (all) | 2998 | 33.5 | -0.01% | +0.02% | +0.11% (-0.31 to +0.53) | 49% | +1.23% | 44% |
| Momentum/vol + 52w high + industry strength | 2014-2021 (chosen here) | 1827 | 30.9 | -0.14% | -0.26% | -0.53% (-0.93 to -0.14) | 47% | +0.71% | 44% |
| Momentum/vol + 52w high + industry strength | 2022-2026 (unseen) | 1171 | 37.7 | +0.09% | +0.19% | +0.51% (-0.40 to +1.42) | 50% | +1.43% | 40% |
| Momentum/vol + 52w high + industry strength | 2014-2026 (all) | 2998 | 33.5 | -0.05% | -0.08% | -0.13% (-0.59 to +0.34) | 48% | +0.99% | 42% |
| Core + steady climb | 2014-2021 (chosen here) | 1827 | 30.9 | -0.14% | -0.25% | -0.52% (-0.95 to -0.08) | 47% | +0.73% | 42% |
| Core + steady climb | 2022-2026 (unseen) | 1171 | 37.7 | +0.08% | +0.21% | +0.49% (-0.31 to +1.29) | 50% | +1.41% | 38% |
| Core + steady climb | 2014-2026 (all) | 2998 | 33.5 | -0.05% | -0.07% | -0.12% (-0.57 to +0.32) | 48% | +0.99% | 40% |
| Core + steady climb + recent power gap | 2014-2021 (chosen here) | 1827 | 30.9 | -0.14% | -0.26% | -0.52% (-0.93 to -0.12) | 47% | +0.72% | 42% |
| Core + steady climb + recent power gap | 2022-2026 (unseen) | 1171 | 37.7 | +0.09% | +0.23% | +0.53% (-0.28 to +1.33) | 50% | +1.45% | 39% |
| Core + steady climb + recent power gap | 2014-2026 (all) | 2998 | 33.5 | -0.05% | -0.07% | -0.11% (-0.54 to +0.32) | 48% | +1.00% | 41% |

### AI picks as a managed list (10 stocks, entries and exits at the next open, 0.10% cost each way)

Score versions, all with the same rules (hold 10, keep while in the top 30, max 3 per sector):

| Version | Period | Return/yr | vs avg stock/yr (95% range) | Sharpe | Worst drop | Picks made | Avg pick | Picks up | Days held (median) |
|---|---|---|---|---|---|---|---|---|---|
| 12-month momentum (skip the last month) | 2014-2021 (chosen here) | +3.9% | -9.7% (-20.37 to +0.93) | 0.28 | -41% | 271 | +1.4% | 49% | 46 |
| 12-month momentum (skip the last month) | 2022-2026 (unseen) | +28.8% | +18.4% (-1.06 to +37.93) | 0.93 | -34% | 150 | +13.4% | 53% | 46 |
| 12-month momentum (skip the last month) | 2014-2026 (all) | +13.0% | +1.3% (-8.86 to +11.41) | 0.57 | -41% | 421 | +5.7% | 50% | 46 |
| Momentum per unit of volatility | 2014-2021 (chosen here) | +5.1% | -9.3% (-19.38 to +0.84) | 0.34 | -37% | 323 | +1.4% | 52% | 43 |
| Momentum per unit of volatility | 2022-2026 (unseen) | +25.8% | +14.0% (-1.28 to +29.18) | 1.02 | -22% | 175 | +8.4% | 56% | 45 |
| Momentum per unit of volatility | 2014-2026 (all) | +12.8% | -0.2% (-8.87 to +8.48) | 0.63 | -37% | 498 | +3.9% | 54% | 43 |
| Closeness to the 52-week high | 2014-2021 (chosen here) | -1.3% | -16.8% (-26.08 to -7.54) | -0.01 | -41% | 5144 | +0.2% | 46% | 2 |
| Closeness to the 52-week high | 2022-2026 (unseen) | -9.2% | -20.7% (-31.70 to -9.74) | -0.52 | -43% | 3096 | +0.1% | 44% | 2 |
| Closeness to the 52-week high | 2014-2026 (all) | -4.5% | -18.3% (-25.42 to -11.25) | -0.21 | -51% | 8240 | +0.1% | 45% | 2 |
| IBD-style relative strength | 2014-2021 (chosen here) | +9.4% | -4.9% (-15.58 to +5.69) | 0.50 | -31% | 349 | +2.3% | 46% | 37 |
| IBD-style relative strength | 2022-2026 (unseen) | +31.1% | +19.3% (+0.67 to +37.87) | 1.05 | -33% | 212 | +10.7% | 46% | 29 |
| IBD-style relative strength | 2014-2026 (all) | +17.4% | +4.5% (-5.32 to +14.34) | 0.75 | -33% | 561 | +5.4% | 46% | 34 |
| Momentum/vol + 52w high + industry strength | 2014-2021 (chosen here) | +2.5% | -12.1% (-21.90 to -2.30) | 0.22 | -39% | 547 | +0.6% | 45% | 18 |
| Momentum/vol + 52w high + industry strength | 2022-2026 (unseen) | +14.2% | +3.5% (-10.54 to +17.61) | 0.70 | -24% | 338 | +2.6% | 47% | 20 |
| Momentum/vol + 52w high + industry strength | 2014-2026 (all) | +6.9% | -6.0% (-14.17 to +2.18) | 0.42 | -39% | 885 | +1.4% | 46% | 18 |
| Core + steady climb | 2014-2021 (chosen here) | +2.5% | -12.3% (-22.12 to -2.39) | 0.22 | -41% | 393 | +0.7% | 48% | 33 |
| Core + steady climb | 2022-2026 (unseen) | +13.0% | +2.2% (-11.18 to +15.55) | 0.67 | -22% | 251 | +3.2% | 47% | 27 |
| Core + steady climb | 2014-2026 (all) | +6.5% | -6.6% (-14.65 to +1.42) | 0.41 | -41% | 644 | +1.7% | 48% | 30 |
| Core + steady climb + recent power gap | 2014-2021 (chosen here) | +0.6% | -14.1% (-24.08 to -4.09) | 0.13 | -41% | 524 | +0.3% | 46% | 22 |
| Core + steady climb + recent power gap | 2022-2026 (unseen) | +7.2% | -3.0% (-16.19 to +10.28) | 0.43 | -28% | 363 | +1.4% | 47% | 17 |
| Core + steady climb + recent power gap | 2014-2026 (all) | +3.1% | -9.7% (-17.77 to -1.71) | 0.25 | -41% | 887 | +0.7% | 47% | 19 |
| *Average liquid stock (equal weight)* | 2014-2021 (chosen here) | +16.4% | | 0.96 | -37% | | | | |
| *SPY* | 2014-2021 (chosen here) | +15.4% | | 0.96 | -32% | | | | |
| *Average liquid stock (equal weight)* | 2022-2026 (unseen) | +11.6% | | 0.75 | -21% | | | | |
| *SPY* | 2022-2026 (unseen) | +12.3% | | 0.75 | -26% | | | | |
| *Average liquid stock (equal weight)* | 2014-2026 (all) | +14.5% | | 0.88 | -37% | | | | |
| *SPY* | 2014-2026 (all) | +14.2% | | 0.87 | -32% | | | | |

Score chosen on the best 10% in 2014-2021 (S&P 500): **IBD-style relative strength**. Rule versions for it (chosen on the 2014-2021 Sharpe ratio):

| Version | Period | Return/yr | vs avg stock/yr (95% range) | Sharpe | Worst drop | Picks made | Avg pick | Picks up | Days held (median) |
|---|---|---|---|---|---|---|---|---|---|
| Hold 10, keep while in the top 30, max 3 per sector | 2014-2021 (chosen here) | +9.4% | -4.9% (-15.58 to +5.69) | 0.50 | -31% | 349 | +2.3% | 46% | 37 |
| Hold 10, keep while in the top 30, max 3 per sector | 2022-2026 (unseen) | +31.1% | +19.3% (+0.67 to +37.87) | 1.05 | -33% | 212 | +10.7% | 46% | 29 |
| Hold 10, keep while in the top 30, max 3 per sector | 2014-2026 (all) | +17.4% | +4.5% (-5.32 to +14.34) | 0.75 | -33% | 561 | +5.4% | 46% | 34 |
| Keep only while in the top 20 | 2014-2021 (chosen here) | +11.9% | -2.7% (-13.34 to +7.84) | 0.60 | -31% | 513 | +2.0% | 43% | 19 |
| Keep only while in the top 20 | 2022-2026 (unseen) | +32.3% | +20.1% (+2.19 to +38.07) | 1.08 | -29% | 380 | +7.0% | 44% | 8 |
| Keep only while in the top 20 | 2014-2026 (all) | +19.4% | +6.2% (-3.43 to +15.81) | 0.81 | -31% | 893 | +4.2% | 44% | 14 |
| Keep while in the top 50 | 2014-2021 (chosen here) | +9.2% | -5.0% (-16.20 to +6.24) | 0.49 | -36% | 243 | +3.3% | 46% | 59 |
| Keep while in the top 50 | 2022-2026 (unseen) | +27.1% | +16.3% (-1.92 to +34.53) | 0.93 | -31% | 132 | +16.7% | 48% | 59 |
| Keep while in the top 50 | 2014-2026 (all) | +15.9% | +3.3% (-6.60 to +13.27) | 0.68 | -36% | 375 | +8.0% | 47% | 59 |
| Also sell on a close below EMA50 | 2014-2021 (chosen here) | +7.2% | -7.5% (-18.95 to +3.91) | 0.43 | -26% | 830 | +0.9% | 40% | 12 |
| Also sell on a close below EMA50 | 2022-2026 (unseen) | +12.1% | +2.7% (-15.08 to +20.44) | 0.56 | -32% | 569 | +1.9% | 34% | 11 |
| Also sell on a close below EMA50 | 2014-2026 (all) | +9.1% | -3.5% (-13.38 to +6.31) | 0.49 | -32% | 1399 | +1.3% | 37% | 11 |
| No new picks while SPY is below its 200-day average | 2014-2021 (chosen here) | +8.6% | -5.9% (-16.45 to +4.57) | 0.48 | -27% | 321 | +2.3% | 45% | 38 |
| No new picks while SPY is below its 200-day average | 2022-2026 (unseen) | +28.1% | +16.5% (-2.25 to +35.32) | 1.01 | -32% | 188 | +11.4% | 44% | 31 |
| No new picks while SPY is below its 200-day average | 2014-2026 (all) | +15.8% | +2.8% (-6.98 to +12.66) | 0.71 | -32% | 509 | +5.6% | 45% | 36 |
| Both of the above | 2014-2021 (chosen here) | +7.4% | -7.6% (-19.17 to +3.95) | 0.46 | -27% | 648 | +1.1% | 40% | 16 |
| Both of the above | 2022-2026 (unseen) | +13.2% | +3.1% (-15.55 to +21.70) | 0.63 | -25% | 408 | +2.6% | 35% | 14 |
| Both of the above | 2014-2026 (all) | +9.7% | -3.4% (-13.58 to +6.71) | 0.53 | -27% | 1056 | +1.7% | 38% | 16 |
| *Average liquid stock (equal weight)* | 2014-2021 (chosen here) | +16.4% | | 0.96 | -37% | | | | |
| *SPY* | 2014-2021 (chosen here) | +15.4% | | 0.96 | -32% | | | | |
| *Average liquid stock (equal weight)* | 2022-2026 (unseen) | +11.6% | | 0.75 | -21% | | | | |
| *SPY* | 2022-2026 (unseen) | +12.3% | | 0.75 | -26% | | | | |
| *Average liquid stock (equal weight)* | 2014-2026 (all) | +14.5% | | 0.88 | -37% | | | | |
| *SPY* | 2014-2026 (all) | +14.2% | | 0.87 | -32% | | | | |

Chosen rule: **Keep only while in the top 20**.

Year by year (chosen version):

| Year | AI picks | Average stock | SPY |
|---|---|---|---|
| 2014 | +7.8% | +8.4% | +5.7% |
| 2015 | -3.4% | -0.4% | +0.7% |
| 2016 | +5.0% | +18.6% | +14.4% |
| 2017 | +29.9% | +23.7% | +21.5% |
| 2018 | -2.4% | -6.3% | -6.0% |
| 2019 | +33.4% | +32.5% | +31.8% |
| 2020 | +11.7% | +12.8% | +16.8% |
| 2021 | +9.1% | +35.5% | +31.9% |
| 2022 | -9.3% | -8.6% | -18.7% |
| 2023 | +13.9% | +16.9% | +24.6% |
| 2024 | +52.0% | +16.0% | +26.5% |
| 2025 | +45.7% | +16.2% | +18.2% |
| 2026 | +60.3% | +15.8% | +13.0% |

### New uptrends (each ordering's top 5 a day, against the whole list)

| List | Period | Days | Picks/day | 5-day vs avg stock | 10-day | 20-day (95% range) | Beat avg (20d) | Avg 20-day return | Broke out in 10d |
|---|---|---|---|---|---|---|---|---|---|
| Every new uptrend | 2014-2021 (chosen here) | 1745 | 8.4 | +0.07% | +0.05% | +0.03% (-0.20 to +0.25) | 51% | +1.24% | 36% |
| Every new uptrend | 2022-2026 (unseen) | 1125 | 9.9 | -0.11% | -0.20% | -0.30% (-0.58 to -0.02) | 48% | +0.60% | 36% |
| Every new uptrend | 2014-2026 (all) | 2870 | 9.0 | -0.00% | -0.05% | -0.10% (-0.28 to +0.08) | 50% | +0.99% | 36% |
| Strongest relative strength first | 2014-2021 (chosen here) | 1745 | 4.3 | +0.02% | -0.00% | +0.02% (-0.26 to +0.30) | 51% | +1.23% | 35% |
| Strongest relative strength first | 2022-2026 (unseen) | 1125 | 4.5 | -0.08% | -0.22% | -0.33% (-0.69 to +0.03) | 47% | +0.57% | 34% |
| Strongest relative strength first | 2014-2026 (all) | 2870 | 4.4 | -0.02% | -0.09% | -0.12% (-0.33 to +0.09) | 50% | +0.97% | 34% |
| Closest to the 52-week high first | 2014-2021 (chosen here) | 1745 | 4.3 | +0.09% | +0.04% | +0.03% (-0.29 to +0.35) | 52% | +1.24% | 38% |
| Closest to the 52-week high first | 2022-2026 (unseen) | 1125 | 4.5 | -0.17% | -0.33% | -0.51% (-0.90 to -0.11) | 47% | +0.39% | 35% |
| Closest to the 52-week high first | 2014-2026 (all) | 2870 | 4.4 | -0.01% | -0.10% | -0.18% (-0.45 to +0.09) | 50% | +0.91% | 37% |
| Highest volume on the day it turned | 2014-2021 (chosen here) | 1745 | 4.3 | +0.06% | +0.01% | -0.02% (-0.27 to +0.23) | 51% | +1.19% | 40% |
| Highest volume on the day it turned | 2022-2026 (unseen) | 1125 | 4.5 | -0.05% | -0.14% | -0.27% (-0.60 to +0.07) | 48% | +0.63% | 39% |
| Highest volume on the day it turned | 2014-2026 (all) | 2870 | 4.4 | +0.02% | -0.05% | -0.12% (-0.32 to +0.08) | 50% | +0.97% | 39% |
| Best AI score first | 2014-2021 (chosen here) | 1745 | 4.3 | +0.02% | -0.00% | +0.02% (-0.26 to +0.30) | 51% | +1.23% | 35% |
| Best AI score first | 2022-2026 (unseen) | 1125 | 4.5 | -0.08% | -0.22% | -0.33% (-0.69 to +0.03) | 47% | +0.57% | 34% |
| Best AI score first | 2014-2026 (all) | 2870 | 4.4 | -0.02% | -0.09% | -0.12% (-0.33 to +0.09) | 50% | +0.97% | 34% |
| Out of an uptrend for 20+ days, then relative strength | 2014-2021 (chosen here) | 1270 | 2.6 | -0.07% | -0.07% | -0.17% (-0.65 to +0.30) | 50% | +0.91% | 35% |
| Out of an uptrend for 20+ days, then relative strength | 2022-2026 (unseen) | 871 | 3.0 | -0.01% | -0.09% | -0.08% (-0.56 to +0.40) | 49% | +0.90% | 38% |
| Out of an uptrend for 20+ days, then relative strength | 2014-2026 (all) | 2141 | 2.8 | -0.04% | -0.08% | -0.14% (-0.47 to +0.20) | 49% | +0.91% | 36% |
| Strongest sector first | 2014-2021 (chosen here) | 1745 | 4.3 | +0.06% | +0.03% | -0.03% (-0.25 to +0.19) | 51% | +1.18% | 36% |
| Strongest sector first | 2022-2026 (unseen) | 1125 | 4.5 | -0.08% | -0.15% | -0.24% (-0.63 to +0.16) | 48% | +0.66% | 35% |
| Strongest sector first | 2014-2026 (all) | 2870 | 4.4 | +0.01% | -0.04% | -0.11% (-0.30 to +0.08) | 50% | +0.98% | 36% |
| Baseline: stocks already in an uptrend | 2014-2021 (chosen here) | 1826 | 142.9 | -0.02% | -0.06% | -0.16% (-0.42 to +0.10) | 49% | +1.07% | 50% |
| Baseline: stocks already in an uptrend | 2022-2026 (unseen) | 1171 | 148.3 | -0.07% | -0.13% | -0.27% (-0.69 to +0.15) | 48% | +0.65% | 47% |
| Baseline: stocks already in an uptrend | 2014-2026 (all) | 2997 | 145.0 | -0.04% | -0.09% | -0.21% (-0.46 to +0.05) | 49% | +0.91% | 48% |

Chosen: **Every new uptrend** (an ordering had to beat the whole list by 0.10% in 2014-2021).

### Breakout watch (top 10 a day)

| List | Period | Days | Picks/day | 5-day vs avg stock | 10-day | 20-day (95% range) | Beat avg (20d) | Avg 20-day return | Broke out in 10d |
|---|---|---|---|---|---|---|---|---|---|
| Every stock within 5% of its 50-day high | 2014-2021 (chosen here) | 1812 | 76.7 | -0.02% | -0.03% | -0.13% (-0.36 to +0.09) | 50% | +1.06% | 41% |
| Every stock within 5% of its 50-day high | 2022-2026 (unseen) | 1165 | 67.1 | -0.10% | -0.25% | -0.50% (-0.89 to -0.11) | 47% | +0.38% | 43% |
| Every stock within 5% of its 50-day high | 2014-2026 (all) | 2977 | 72.9 | -0.05% | -0.12% | -0.28% (-0.47 to -0.09) | 49% | +0.79% | 42% |
| Closest to the breakout level | 2014-2021 (chosen here) | 1812 | 9.9 | -0.02% | -0.01% | -0.16% (-0.43 to +0.12) | 50% | +1.04% | 69% |
| Closest to the breakout level | 2022-2026 (unseen) | 1165 | 9.9 | -0.10% | -0.19% | -0.43% (-0.89 to +0.03) | 48% | +0.46% | 65% |
| Closest to the breakout level | 2014-2026 (all) | 2977 | 9.9 | -0.05% | -0.08% | -0.26% (-0.48 to -0.04) | 49% | +0.81% | 67% |
| Uptrend + tightest range, shrinking ranges, drying volume, closest | 2014-2021 (chosen here) | 1809 | 9.8 | -0.03% | -0.04% | -0.11% (-0.49 to +0.27) | 50% | +1.06% | 49% |
| Uptrend + tightest range, shrinking ranges, drying volume, closest | 2022-2026 (unseen) | 1165 | 9.8 | -0.13% | -0.29% | -0.59% (-1.19 to +0.00) | 46% | +0.29% | 45% |
| Uptrend + tightest range, shrinking ranges, drying volume, closest | 2014-2026 (all) | 2974 | 9.8 | -0.07% | -0.14% | -0.30% (-0.61 to +0.02) | 48% | +0.76% | 47% |
| Same + relative strength | 2014-2021 (chosen here) | 1809 | 9.8 | -0.07% | -0.07% | -0.14% (-0.48 to +0.20) | 49% | +1.03% | 50% |
| Same + relative strength | 2022-2026 (unseen) | 1165 | 9.8 | -0.11% | -0.24% | -0.45% (-1.05 to +0.14) | 47% | +0.43% | 47% |
| Same + relative strength | 2014-2026 (all) | 2974 | 9.8 | -0.08% | -0.14% | -0.26% (-0.56 to +0.03) | 48% | +0.79% | 49% |
| Minervini trend template, strongest RS first | 2014-2021 (chosen here) | 1796 | 9.3 | -0.13% | -0.15% | -0.18% (-0.53 to +0.18) | 49% | +0.95% | 47% |
| Minervini trend template, strongest RS first | 2022-2026 (unseen) | 1156 | 9.4 | -0.13% | -0.29% | -0.46% (-1.13 to +0.21) | 46% | +0.40% | 47% |
| Minervini trend template, strongest RS first | 2014-2026 (all) | 2952 | 9.3 | -0.13% | -0.20% | -0.29% (-0.64 to +0.07) | 48% | +0.74% | 47% |
| Uptrend + Bollinger squeeze, strongest RS first | 2014-2021 (chosen here) | 1495 | 6.5 | -0.16% | -0.11% | -0.11% (-0.47 to +0.25) | 49% | +0.75% | 44% |
| Uptrend + Bollinger squeeze, strongest RS first | 2022-2026 (unseen) | 987 | 5.9 | -0.16% | -0.48% | -0.65% (-1.34 to +0.03) | 44% | -0.15% | 40% |
| Uptrend + Bollinger squeeze, strongest RS first | 2014-2026 (all) | 2482 | 6.3 | -0.16% | -0.26% | -0.33% (-0.65 to -0.00) | 48% | +0.39% | 43% |
| Baseline: every liquid stock | 2014-2021 (chosen here) | 1827 | 304.3 | -0.00% | +0.00% | +0.00% (-0.00 to +0.00) | 50% | +1.24% | 29% |
| Baseline: every liquid stock | 2022-2026 (unseen) | 1171 | 372.2 | -0.00% | +0.00% | -0.00% (-0.00 to +0.00) | 48% | +0.92% | 25% |
| Baseline: every liquid stock | 2014-2026 (all) | 2998 | 330.8 | -0.00% | +0.00% | -0.00% (-0.00 to +0.00) | 49% | +1.12% | 27% |

Chosen: **Uptrend + tightest range, shrinking ranges, drying volume, closest** (best 2014-2021 return among lists that broke out at least 1.5x as often as the average stock; returns within 0.01% count as a tie, and a tie goes to the list that broke out more often). Tied on return with **Uptrend + Bollinger squeeze, strongest RS first**; it broke out more often.

## S&P 400 + 600 (today's members)
About 229 liquid stocks a day.

### Signal report card
Each signal on its own: the best 10% of stocks by that signal each day, and the worst 10%, against the average stock over the next 20 trading days.

| Signal | Period | Top 10% vs avg stock, 20 days (95% range) | Bottom 10% | Rank correlation |
|---|---|---|---|---|
| 12-month momentum, skip last month | 2014-2021 (chosen here) | +1.14% (+0.48 to +1.80) | +0.10% | +0.012 |
| 12-month momentum, skip last month | 2022-2026 (unseen) | +0.81% (-0.47 to +2.08) | +0.09% | +0.020 |
| 12-month momentum, skip last month | 2014-2026 (all) | +1.01% (+0.47 to +1.55) | +0.10% | +0.015 |
| momentum / volatility | 2014-2021 (chosen here) | +0.63% (+0.05 to +1.22) | -0.23% | +0.019 |
| momentum / volatility | 2022-2026 (unseen) | +0.50% (-0.58 to +1.57) | -0.60% | +0.023 |
| momentum / volatility | 2014-2026 (all) | +0.58% (+0.07 to +1.08) | -0.38% | +0.020 |
| 6-month momentum, skip last month | 2014-2021 (chosen here) | +1.02% (+0.30 to +1.73) | +0.28% | +0.020 |
| 6-month momentum, skip last month | 2022-2026 (unseen) | +0.48% (-0.74 to +1.69) | -0.13% | +0.005 |
| 6-month momentum, skip last month | 2014-2026 (all) | +0.81% (+0.28 to +1.34) | +0.12% | +0.014 |
| IBD-style relative strength | 2014-2021 (chosen here) | +1.08% (+0.42 to +1.74) | +0.21% | +0.020 |
| IBD-style relative strength | 2022-2026 (unseen) | +0.78% (-0.42 to +1.98) | -0.02% | +0.015 |
| IBD-style relative strength | 2014-2026 (all) | +0.96% (+0.39 to +1.54) | +0.12% | +0.018 |
| closeness to the 52-week high | 2014-2021 (chosen here) | -0.08% (-0.54 to +0.38) | +0.54% | +0.011 |
| closeness to the 52-week high | 2022-2026 (unseen) | -0.38% (-0.88 to +0.13) | +0.25% | +0.012 |
| closeness to the 52-week high | 2014-2026 (all) | -0.20% (-0.52 to +0.12) | +0.43% | +0.012 |
| industry strength (6 months) | 2014-2021 (chosen here) | +0.58% (-0.22 to +1.37) | -0.87% | +0.023 |
| industry strength (6 months) | 2022-2026 (unseen) | +0.29% (-1.11 to +1.69) | -0.37% | +0.002 |
| industry strength (6 months) | 2014-2026 (all) | +0.47% (-0.22 to +1.15) | -0.67% | +0.015 |
| share of the sector in an uptrend | 2014-2021 (chosen here) | -0.49% (-0.99 to +0.00) | -0.53% | -0.007 |
| share of the sector in an uptrend | 2022-2026 (unseen) | +0.11% (-1.34 to +1.56) | -0.03% | -0.007 |
| share of the sector in an uptrend | 2014-2026 (all) | -0.26% (-0.86 to +0.35) | -0.33% | -0.007 |
| steady climb (frog in the pan) | 2014-2021 (chosen here) | +0.14% (-0.46 to +0.74) | -0.79% | +0.019 |
| steady climb (frog in the pan) | 2022-2026 (unseen) | -0.30% (-0.92 to +0.33) | -0.48% | +0.009 |
| steady climb (frog in the pan) | 2014-2026 (all) | -0.03% (-0.46 to +0.39) | -0.67% | +0.015 |
| recent power gap that held | 2014-2021 (chosen here) | -0.25% (-1.04 to +0.55) | n/a | -0.002 |
| recent power gap that held | 2022-2026 (unseen) | +0.06% (-0.74 to +0.85) | n/a | -0.000 |
| recent power gap that held | 2014-2026 (all) | -0.13% (-0.73 to +0.48) | n/a | -0.002 |
| up-day vs down-day volume | 2014-2021 (chosen here) | -0.02% (-0.53 to +0.48) | -0.01% | +0.000 |
| up-day vs down-day volume | 2022-2026 (unseen) | +0.04% (-0.47 to +0.56) | -0.28% | +0.007 |
| up-day vs down-day volume | 2014-2026 (all) | +0.00% (-0.38 to +0.38) | -0.11% | +0.003 |
| low volatility | 2014-2021 (chosen here) | -0.34% (-1.02 to +0.35) | +1.60% | -0.008 |
| low volatility | 2022-2026 (unseen) | -0.52% (-1.17 to +0.13) | +0.44% | +0.000 |
| low volatility | 2014-2026 (all) | -0.41% (-0.97 to +0.16) | +1.14% | -0.005 |
| 1-week pullback | 2014-2021 (chosen here) | +0.48% (-0.06 to +1.02) | +0.06% | +0.014 |
| 1-week pullback | 2022-2026 (unseen) | +0.44% (-0.10 to +0.97) | +0.02% | +0.010 |
| 1-week pullback | 2014-2026 (all) | +0.46% (+0.10 to +0.82) | +0.04% | +0.012 |
| 1-month pullback | 2014-2021 (chosen here) | +0.58% (-0.12 to +1.27) | -0.03% | +0.013 |
| 1-month pullback | 2022-2026 (unseen) | +0.15% (-0.68 to +0.98) | +0.41% | -0.005 |
| 1-month pullback | 2014-2026 (all) | +0.41% (-0.09 to +0.91) | +0.14% | +0.006 |
| in an uptrend (your rule) | 2014-2021 (chosen here) | -0.05% (-0.33 to +0.23) | +0.02% | +0.006 |
| in an uptrend (your rule) | 2022-2026 (unseen) | -0.18% (-0.67 to +0.30) | -0.05% | +0.001 |
| in an uptrend (your rule) | 2014-2026 (all) | -0.10% (-0.38 to +0.18) | -0.00% | +0.004 |
| Minervini trend template | 2014-2021 (chosen here) | +0.26% (-0.18 to +0.71) | -0.02% | +0.011 |
| Minervini trend template | 2022-2026 (unseen) | -0.30% (-1.01 to +0.41) | -0.00% | -0.001 |
| Minervini trend template | 2014-2026 (all) | +0.04% (-0.38 to +0.46) | -0.02% | +0.006 |
| not stretched above EMA20 | 2014-2021 (chosen here) | +0.37% (-0.12 to +0.86) | -0.41% | +0.013 |
| not stretched above EMA20 | 2022-2026 (unseen) | -0.01% (-0.54 to +0.53) | +0.04% | -0.004 |
| not stretched above EMA20 | 2014-2026 (all) | +0.22% (-0.12 to +0.57) | -0.23% | +0.007 |
| volume drying up | 2014-2021 (chosen here) | +0.29% (-0.04 to +0.62) | -0.27% | +0.005 |
| volume drying up | 2022-2026 (unseen) | +0.15% (-0.32 to +0.62) | +0.46% | -0.005 |
| volume drying up | 2014-2026 (all) | +0.24% (-0.08 to +0.55) | +0.01% | +0.001 |
| ranges shrinking | 2014-2021 (chosen here) | +0.39% (-0.03 to +0.82) | -0.18% | +0.011 |
| ranges shrinking | 2022-2026 (unseen) | +0.07% (-0.32 to +0.47) | -0.07% | -0.005 |
| ranges shrinking | 2014-2026 (all) | +0.27% (-0.05 to +0.58) | -0.13% | +0.005 |

### AI score: the 10 best stocks each day

| List | Period | Days | Picks/day | 5-day vs avg stock | 10-day | 20-day (95% range) | Beat avg (20d) | Avg 20-day return | Broke out in 10d |
|---|---|---|---|---|---|---|---|---|---|
| 12-month momentum (skip the last month) | 2014-2021 (chosen here) | 1827 | 10.0 | +0.37% | +0.89% | +1.70% (+0.67 to +2.72) | 51% | +2.75% | 28% |
| 12-month momentum (skip the last month) | 2022-2026 (unseen) | 1171 | 10.0 | +0.39% | +0.75% | +1.44% (-0.34 to +3.23) | 51% | +2.14% | 28% |
| 12-month momentum (skip the last month) | 2014-2026 (all) | 2998 | 10.0 | +0.38% | +0.84% | +1.60% (+0.72 to +2.48) | 51% | +2.51% | 28% |
| Momentum per unit of volatility | 2014-2021 (chosen here) | 1827 | 10.0 | +0.30% | +0.52% | +0.84% (+0.06 to +1.61) | 49% | +1.89% | 28% |
| Momentum per unit of volatility | 2022-2026 (unseen) | 1171 | 10.0 | +0.27% | +0.47% | +0.78% (-0.85 to +2.41) | 51% | +1.48% | 30% |
| Momentum per unit of volatility | 2014-2026 (all) | 2998 | 10.0 | +0.29% | +0.50% | +0.81% (+0.11 to +1.52) | 50% | +1.73% | 29% |
| Closeness to the 52-week high | 2014-2021 (chosen here) | 1827 | 10.0 | +0.00% | -0.05% | +0.00% (-0.54 to +0.54) | 49% | +1.06% | 66% |
| Closeness to the 52-week high | 2022-2026 (unseen) | 1171 | 10.0 | -0.03% | -0.03% | -0.17% (-0.85 to +0.51) | 49% | +0.53% | 66% |
| Closeness to the 52-week high | 2014-2026 (all) | 2998 | 10.0 | -0.01% | -0.05% | -0.06% (-0.53 to +0.40) | 49% | +0.85% | 66% |
| IBD-style relative strength | 2014-2021 (chosen here) | 1827 | 10.0 | +0.38% | +0.75% | +1.59% (+0.54 to +2.65) | 50% | +2.65% | 39% |
| IBD-style relative strength | 2022-2026 (unseen) | 1171 | 10.0 | +0.15% | +0.25% | +0.62% (-1.42 to +2.67) | 49% | +1.32% | 42% |
| IBD-style relative strength | 2014-2026 (all) | 2998 | 10.0 | +0.29% | +0.56% | +1.21% (+0.29 to +2.14) | 50% | +2.13% | 40% |
| Momentum/vol + 52w high + industry strength | 2014-2021 (chosen here) | 1827 | 10.0 | +0.17% | +0.41% | +0.80% (+0.00 to +1.59) | 50% | +1.85% | 41% |
| Momentum/vol + 52w high + industry strength | 2022-2026 (unseen) | 1171 | 10.0 | +0.16% | +0.35% | +0.81% (-0.89 to +2.51) | 51% | +1.51% | 41% |
| Momentum/vol + 52w high + industry strength | 2014-2026 (all) | 2998 | 10.0 | +0.16% | +0.39% | +0.80% (-0.01 to +1.62) | 50% | +1.72% | 41% |
| Core + steady climb | 2014-2021 (chosen here) | 1827 | 10.0 | +0.11% | +0.23% | +0.52% (-0.34 to +1.38) | 49% | +1.58% | 38% |
| Core + steady climb | 2022-2026 (unseen) | 1171 | 10.0 | +0.18% | +0.46% | +0.79% (-0.75 to +2.33) | 51% | +1.49% | 39% |
| Core + steady climb | 2014-2026 (all) | 2998 | 10.0 | +0.14% | +0.32% | +0.63% (-0.14 to +1.39) | 50% | +1.54% | 39% |
| Core + steady climb + recent power gap | 2014-2021 (chosen here) | 1827 | 10.0 | +0.14% | +0.20% | +0.39% (-0.52 to +1.30) | 50% | +1.45% | 40% |
| Core + steady climb + recent power gap | 2022-2026 (unseen) | 1171 | 10.0 | +0.13% | +0.38% | +0.80% (-0.55 to +2.15) | 52% | +1.50% | 41% |
| Core + steady climb + recent power gap | 2014-2026 (all) | 2998 | 10.0 | +0.13% | +0.27% | +0.55% (-0.21 to +1.31) | 51% | +1.47% | 41% |

### AI score: the best 10% each day (30-40 stocks, so much less noise; the score is chosen here)

| List | Period | Days | Picks/day | 5-day vs avg stock | 10-day | 20-day (95% range) | Beat avg (20d) | Avg 20-day return | Broke out in 10d |
|---|---|---|---|---|---|---|---|---|---|
| 12-month momentum (skip the last month) | 2014-2021 (chosen here) | 1827 | 18.1 | +0.22% | +0.54% | +1.14% (+0.48 to +1.80) | 50% | +2.20% | 27% |
| 12-month momentum (skip the last month) | 2022-2026 (unseen) | 1171 | 30.9 | +0.15% | +0.35% | +0.81% (-0.47 to +2.09) | 49% | +1.50% | 26% |
| 12-month momentum (skip the last month) | 2014-2026 (all) | 2998 | 23.1 | +0.19% | +0.46% | +1.01% (+0.47 to +1.55) | 50% | +1.93% | 27% |
| Momentum per unit of volatility | 2014-2021 (chosen here) | 1827 | 18.1 | +0.18% | +0.33% | +0.63% (+0.05 to +1.21) | 49% | +1.69% | 28% |
| Momentum per unit of volatility | 2022-2026 (unseen) | 1171 | 30.9 | +0.12% | +0.23% | +0.49% (-0.58 to +1.56) | 49% | +1.19% | 28% |
| Momentum per unit of volatility | 2014-2026 (all) | 2998 | 23.1 | +0.15% | +0.29% | +0.58% (+0.07 to +1.08) | 49% | +1.49% | 28% |
| Closeness to the 52-week high | 2014-2021 (chosen here) | 1807 | 18.9 | -0.02% | -0.08% | -0.08% (-0.53 to +0.38) | 49% | +0.99% | 60% |
| Closeness to the 52-week high | 2022-2026 (unseen) | 1167 | 31.4 | -0.08% | -0.15% | -0.38% (-0.89 to +0.12) | 47% | +0.33% | 57% |
| Closeness to the 52-week high | 2014-2026 (all) | 2974 | 23.8 | -0.04% | -0.11% | -0.20% (-0.51 to +0.12) | 48% | +0.73% | 59% |
| IBD-style relative strength | 2014-2021 (chosen here) | 1827 | 18.1 | +0.20% | +0.47% | +1.09% (+0.43 to +1.75) | 50% | +2.14% | 39% |
| IBD-style relative strength | 2022-2026 (unseen) | 1171 | 30.9 | +0.16% | +0.39% | +0.79% (-0.41 to +1.99) | 50% | +1.49% | 40% |
| IBD-style relative strength | 2014-2026 (all) | 2998 | 23.1 | +0.18% | +0.44% | +0.97% (+0.39 to +1.55) | 50% | +1.89% | 39% |
| Momentum/vol + 52w high + industry strength | 2014-2021 (chosen here) | 1827 | 18.3 | +0.15% | +0.28% | +0.54% (-0.04 to +1.11) | 49% | +1.60% | 39% |
| Momentum/vol + 52w high + industry strength | 2022-2026 (unseen) | 1171 | 31.0 | +0.05% | +0.15% | +0.30% (-0.91 to +1.50) | 49% | +1.00% | 37% |
| Momentum/vol + 52w high + industry strength | 2014-2026 (all) | 2998 | 23.2 | +0.11% | +0.23% | +0.44% (-0.11 to +1.00) | 49% | +1.36% | 38% |
| Core + steady climb | 2014-2021 (chosen here) | 1827 | 18.3 | +0.08% | +0.18% | +0.32% (-0.20 to +0.84) | 49% | +1.38% | 37% |
| Core + steady climb | 2022-2026 (unseen) | 1171 | 31.0 | +0.05% | +0.11% | +0.24% (-0.82 to +1.30) | 49% | +0.94% | 35% |
| Core + steady climb | 2014-2026 (all) | 2998 | 23.2 | +0.07% | +0.15% | +0.29% (-0.23 to +0.80) | 49% | +1.21% | 36% |
| Core + steady climb + recent power gap | 2014-2021 (chosen here) | 1827 | 18.3 | +0.09% | +0.15% | +0.29% (-0.38 to +0.95) | 49% | +1.35% | 38% |
| Core + steady climb + recent power gap | 2022-2026 (unseen) | 1171 | 31.0 | +0.09% | +0.19% | +0.33% (-0.60 to +1.26) | 49% | +1.03% | 38% |
| Core + steady climb + recent power gap | 2014-2026 (all) | 2998 | 23.2 | +0.09% | +0.17% | +0.31% (-0.25 to +0.86) | 49% | +1.22% | 38% |

### AI picks as a managed list (10 stocks, entries and exits at the next open, 0.10% cost each way)

Score versions, all with the same rules (hold 10, keep while in the top 30, max 3 per sector):

| Version | Period | Return/yr | vs avg stock/yr (95% range) | Sharpe | Worst drop | Picks made | Avg pick | Picks up | Days held (median) |
|---|---|---|---|---|---|---|---|---|---|
| 12-month momentum (skip the last month) | 2014-2021 (chosen here) | +28.3% | +17.0% (-1.43 to +35.49) | 0.85 | -52% | 318 | +9.2% | 47% | 26 |
| 12-month momentum (skip the last month) | 2022-2026 (unseen) | +19.8% | +14.9% (-7.66 to +37.54) | 0.67 | -31% | 228 | +4.2% | 46% | 22 |
| 12-month momentum (skip the last month) | 2014-2026 (all) | +24.9% | +16.2% (+1.91 to +30.52) | 0.78 | -52% | 546 | +7.1% | 46% | 23 |
| Momentum per unit of volatility | 2014-2021 (chosen here) | +19.8% | +8.6% (-7.98 to +25.15) | 0.71 | -47% | 322 | +5.9% | 48% | 29 |
| Momentum per unit of volatility | 2022-2026 (unseen) | +17.4% | +10.8% (-9.15 to +30.68) | 0.67 | -33% | 214 | +5.2% | 52% | 30 |
| Momentum per unit of volatility | 2014-2026 (all) | +18.8% | +9.4% (-3.31 to +22.18) | 0.69 | -47% | 536 | +5.6% | 50% | 30 |
| Closeness to the 52-week high | 2014-2021 (chosen here) | +2.0% | -11.2% (-24.10 to +1.77) | 0.20 | -41% | 2101 | +0.3% | 45% | 4 |
| Closeness to the 52-week high | 2022-2026 (unseen) | +7.4% | -0.9% (-15.09 to +13.38) | 0.44 | -22% | 2062 | +0.4% | 42% | 3 |
| Closeness to the 52-week high | 2014-2026 (all) | +4.1% | -7.1% (-16.79 to +2.52) | 0.30 | -41% | 4163 | +0.4% | 43% | 4 |
| IBD-style relative strength | 2014-2021 (chosen here) | +35.2% | +22.3% (+4.07 to +40.44) | 0.99 | -46% | 328 | +9.4% | 46% | 25 |
| IBD-style relative strength | 2022-2026 (unseen) | +17.2% | +12.8% (-8.56 to +34.15) | 0.61 | -35% | 262 | +3.6% | 41% | 25 |
| IBD-style relative strength | 2014-2026 (all) | +27.9% | +18.6% (+4.68 to +32.44) | 0.84 | -46% | 590 | +6.8% | 44% | 25 |
| Momentum/vol + 52w high + industry strength | 2014-2021 (chosen here) | +26.3% | +13.1% (-2.01 to +28.31) | 0.90 | -46% | 401 | +6.0% | 50% | 25 |
| Momentum/vol + 52w high + industry strength | 2022-2026 (unseen) | +10.7% | +4.2% (-13.24 to +21.66) | 0.49 | -33% | 349 | +2.5% | 43% | 17 |
| Momentum/vol + 52w high + industry strength | 2014-2026 (all) | +20.0% | +9.7% (-1.84 to +21.15) | 0.75 | -46% | 750 | +4.3% | 47% | 21 |
| Core + steady climb | 2014-2021 (chosen here) | +22.5% | +10.0% (-5.58 to +25.55) | 0.81 | -43% | 383 | +5.5% | 52% | 27 |
| Core + steady climb | 2022-2026 (unseen) | +21.2% | +12.9% (-4.62 to +30.49) | 0.82 | -29% | 251 | +5.0% | 47% | 23 |
| Core + steady climb | 2014-2026 (all) | +22.0% | +11.1% (-0.57 to +22.84) | 0.82 | -43% | 634 | +5.3% | 50% | 26 |
| Core + steady climb + recent power gap | 2014-2021 (chosen here) | +19.8% | +7.8% (-7.30 to +22.91) | 0.74 | -42% | 486 | +4.0% | 49% | 21 |
| Core + steady climb + recent power gap | 2022-2026 (unseen) | +15.3% | +8.1% (-9.54 to +25.69) | 0.64 | -32% | 382 | +3.0% | 46% | 16 |
| Core + steady climb + recent power gap | 2014-2026 (all) | +18.1% | +7.9% (-3.59 to +19.41) | 0.70 | -42% | 868 | +3.6% | 47% | 18 |
| *Average liquid stock (equal weight)* | 2014-2021 (chosen here) | +13.1% | | 0.64 | -50% | | | | |
| *SPY* | 2014-2021 (chosen here) | +15.4% | | 0.96 | -32% | | | | |
| *Average liquid stock (equal weight)* | 2022-2026 (unseen) | +7.8% | | 0.44 | -27% | | | | |
| *SPY* | 2022-2026 (unseen) | +12.3% | | 0.75 | -26% | | | | |
| *Average liquid stock (equal weight)* | 2014-2026 (all) | +11.0% | | 0.56 | -50% | | | | |
| *SPY* | 2014-2026 (all) | +14.2% | | 0.87 | -32% | | | | |

Score chosen on the best 10% in 2014-2021 (S&P 500): **IBD-style relative strength**. Rule versions for it (chosen on the 2014-2021 Sharpe ratio):

| Version | Period | Return/yr | vs avg stock/yr (95% range) | Sharpe | Worst drop | Picks made | Avg pick | Picks up | Days held (median) |
|---|---|---|---|---|---|---|---|---|---|
| Hold 10, keep while in the top 30, max 3 per sector | 2014-2021 (chosen here) | +35.2% | +22.3% (+4.07 to +40.44) | 0.99 | -46% | 328 | +9.4% | 46% | 25 |
| Hold 10, keep while in the top 30, max 3 per sector | 2022-2026 (unseen) | +17.2% | +12.8% (-8.56 to +34.15) | 0.61 | -35% | 262 | +3.6% | 41% | 25 |
| Hold 10, keep while in the top 30, max 3 per sector | 2014-2026 (all) | +27.9% | +18.6% (+4.68 to +32.44) | 0.84 | -46% | 590 | +6.8% | 44% | 25 |
| Keep only while in the top 20 | 2014-2021 (chosen here) | +35.5% | +22.9% (+4.43 to +41.27) | 0.97 | -47% | 476 | +6.0% | 43% | 18 |
| Keep only while in the top 20 | 2022-2026 (unseen) | +6.3% | +2.7% (-18.47 to +23.85) | 0.35 | -38% | 403 | +1.3% | 42% | 12 |
| Keep only while in the top 20 | 2014-2026 (all) | +23.2% | +15.0% (+0.98 to +28.97) | 0.74 | -47% | 879 | +3.8% | 42% | 16 |
| Keep while in the top 50 | 2014-2021 (chosen here) | +43.7% | +28.7% (+11.17 to +46.26) | 1.12 | -48% | 246 | +14.9% | 51% | 32 |
| Keep while in the top 50 | 2022-2026 (unseen) | +14.3% | +10.5% (-11.38 to +32.30) | 0.54 | -37% | 180 | +3.2% | 44% | 44 |
| Keep while in the top 50 | 2014-2026 (all) | +31.4% | +21.6% (+7.86 to +35.31) | 0.90 | -48% | 426 | +10.0% | 48% | 38 |
| Also sell on a close below EMA50 | 2014-2021 (chosen here) | +21.8% | +9.8% (-7.49 to +27.08) | 0.78 | -42% | 960 | +2.2% | 38% | 10 |
| Also sell on a close below EMA50 | 2022-2026 (unseen) | +5.2% | +0.5% (-20.26 to +21.23) | 0.32 | -42% | 657 | +0.8% | 36% | 9 |
| Also sell on a close below EMA50 | 2014-2026 (all) | +15.0% | +6.2% (-7.15 to +19.46) | 0.59 | -42% | 1617 | +1.6% | 37% | 10 |
| No new picks while SPY is below its 200-day average | 2014-2021 (chosen here) | +31.9% | +19.3% (+1.12 to +37.40) | 0.94 | -39% | 302 | +9.1% | 44% | 25 |
| No new picks while SPY is below its 200-day average | 2022-2026 (unseen) | +14.6% | +9.8% (-11.59 to +31.17) | 0.56 | -33% | 228 | +3.6% | 40% | 26 |
| No new picks while SPY is below its 200-day average | 2014-2026 (all) | +24.9% | +15.6% (+1.69 to +29.42) | 0.79 | -39% | 530 | +6.7% | 42% | 26 |
| Both of the above | 2014-2021 (chosen here) | +19.1% | +7.1% (-11.79 to +25.96) | 0.72 | -38% | 800 | +2.1% | 37% | 12 |
| Both of the above | 2022-2026 (unseen) | +3.4% | -2.2% (-23.66 to +19.28) | 0.26 | -40% | 498 | +0.7% | 35% | 13 |
| Both of the above | 2014-2026 (all) | +12.7% | +3.5% (-10.79 to +17.71) | 0.54 | -40% | 1298 | +1.6% | 36% | 12 |
| *Average liquid stock (equal weight)* | 2014-2021 (chosen here) | +13.1% | | 0.64 | -50% | | | | |
| *SPY* | 2014-2021 (chosen here) | +15.4% | | 0.96 | -32% | | | | |
| *Average liquid stock (equal weight)* | 2022-2026 (unseen) | +7.8% | | 0.44 | -27% | | | | |
| *SPY* | 2022-2026 (unseen) | +12.3% | | 0.75 | -26% | | | | |
| *Average liquid stock (equal weight)* | 2014-2026 (all) | +11.0% | | 0.56 | -50% | | | | |
| *SPY* | 2014-2026 (all) | +14.2% | | 0.87 | -32% | | | | |

Chosen rule: **Keep only while in the top 20**.

Year by year (chosen version):

| Year | AI picks | Average stock | SPY |
|---|---|---|---|
| 2014 | +4.6% | +2.6% | +5.7% |
| 2015 | +0.3% | -8.2% | +0.7% |
| 2016 | -1.1% | +18.4% | +14.4% |
| 2017 | +39.3% | +18.3% | +21.5% |
| 2018 | +18.9% | -14.0% | -6.0% |
| 2019 | +78.3% | +27.0% | +31.8% |
| 2020 | +82.1% | +19.8% | +16.8% |
| 2021 | +62.2% | +41.5% | +31.9% |
| 2022 | -1.7% | -16.7% | -18.7% |
| 2023 | +10.3% | +18.4% | +24.6% |
| 2024 | +10.4% | +10.2% | +26.5% |
| 2025 | +9.3% | +9.6% | +18.2% |
| 2026 | +1.4% | +19.1% | +13.0% |

### New uptrends (each ordering's top 5 a day, against the whole list)

| List | Period | Days | Picks/day | 5-day vs avg stock | 10-day | 20-day (95% range) | Beat avg (20d) | Avg 20-day return | Broke out in 10d |
|---|---|---|---|---|---|---|---|---|---|
| Every new uptrend | 2014-2021 (chosen here) | 1655 | 4.5 | +0.01% | +0.04% | -0.06% (-0.42 to +0.30) | 48% | +0.91% | 35% |
| Every new uptrend | 2022-2026 (unseen) | 1116 | 7.8 | +0.02% | +0.07% | +0.06% (-0.28 to +0.41) | 48% | +0.74% | 36% |
| Every new uptrend | 2014-2026 (all) | 2771 | 5.8 | +0.02% | +0.05% | -0.01% (-0.26 to +0.24) | 48% | +0.84% | 35% |
| Strongest relative strength first | 2014-2021 (chosen here) | 1652 | 3.4 | +0.02% | +0.06% | -0.04% (-0.42 to +0.34) | 49% | +0.92% | 33% |
| Strongest relative strength first | 2022-2026 (unseen) | 1115 | 4.1 | +0.02% | +0.15% | +0.20% (-0.21 to +0.60) | 47% | +0.87% | 33% |
| Strongest relative strength first | 2014-2026 (all) | 2767 | 3.7 | +0.02% | +0.10% | +0.05% (-0.23 to +0.33) | 48% | +0.90% | 33% |
| Closest to the 52-week high first | 2014-2021 (chosen here) | 1655 | 3.5 | +0.02% | +0.01% | -0.06% (-0.42 to +0.30) | 49% | +0.91% | 34% |
| Closest to the 52-week high first | 2022-2026 (unseen) | 1116 | 4.1 | +0.08% | +0.01% | -0.10% (-0.54 to +0.33) | 46% | +0.58% | 35% |
| Closest to the 52-week high first | 2014-2026 (all) | 2771 | 3.7 | +0.05% | +0.01% | -0.08% (-0.35 to +0.20) | 48% | +0.78% | 34% |
| Highest volume on the day it turned | 2014-2021 (chosen here) | 1655 | 3.5 | -0.03% | +0.03% | -0.05% (-0.42 to +0.33) | 48% | +0.92% | 35% |
| Highest volume on the day it turned | 2022-2026 (unseen) | 1116 | 4.1 | +0.03% | +0.12% | +0.09% (-0.39 to +0.56) | 47% | +0.76% | 38% |
| Highest volume on the day it turned | 2014-2026 (all) | 2771 | 3.7 | -0.01% | +0.06% | +0.01% (-0.26 to +0.27) | 48% | +0.86% | 36% |
| Best AI score first | 2014-2021 (chosen here) | 1652 | 3.4 | +0.02% | +0.06% | -0.04% (-0.42 to +0.34) | 49% | +0.92% | 33% |
| Best AI score first | 2022-2026 (unseen) | 1115 | 4.1 | +0.02% | +0.15% | +0.20% (-0.21 to +0.60) | 47% | +0.87% | 33% |
| Best AI score first | 2014-2026 (all) | 2767 | 3.7 | +0.02% | +0.10% | +0.05% (-0.23 to +0.33) | 48% | +0.90% | 33% |
| Out of an uptrend for 20+ days, then relative strength | 2014-2021 (chosen here) | 1035 | 2.1 | -0.17% | -0.10% | -0.05% (-0.47 to +0.36) | 49% | +0.68% | 38% |
| Out of an uptrend for 20+ days, then relative strength | 2022-2026 (unseen) | 829 | 2.7 | -0.03% | -0.03% | -0.13% (-0.80 to +0.55) | 47% | +0.45% | 38% |
| Out of an uptrend for 20+ days, then relative strength | 2014-2026 (all) | 1864 | 2.3 | -0.11% | -0.07% | -0.09% (-0.40 to +0.23) | 48% | +0.58% | 38% |
| Strongest sector first | 2014-2021 (chosen here) | 1655 | 3.5 | +0.01% | +0.05% | -0.09% (-0.45 to +0.28) | 49% | +0.89% | 34% |
| Strongest sector first | 2022-2026 (unseen) | 1116 | 4.1 | +0.06% | +0.16% | +0.13% (-0.35 to +0.61) | 47% | +0.81% | 35% |
| Strongest sector first | 2014-2026 (all) | 2771 | 3.7 | +0.03% | +0.09% | +0.00% (-0.28 to +0.29) | 48% | +0.86% | 34% |
| Baseline: stocks already in an uptrend | 2014-2021 (chosen here) | 1827 | 69.5 | -0.04% | -0.05% | -0.05% (-0.35 to +0.24) | 48% | +1.01% | 45% |
| Baseline: stocks already in an uptrend | 2022-2026 (unseen) | 1171 | 110.3 | -0.08% | -0.12% | -0.20% (-0.73 to +0.32) | 48% | +0.49% | 44% |
| Baseline: stocks already in an uptrend | 2014-2026 (all) | 2998 | 85.4 | -0.05% | -0.08% | -0.11% (-0.41 to +0.18) | 48% | +0.81% | 44% |

Chosen: **Every new uptrend** (an ordering had to beat the whole list by 0.10% in 2014-2021).

### Breakout watch (top 10 a day)

| List | Period | Days | Picks/day | 5-day vs avg stock | 10-day | 20-day (95% range) | Beat avg (20d) | Avg 20-day return | Broke out in 10d |
|---|---|---|---|---|---|---|---|---|---|
| Every stock within 5% of its 50-day high | 2014-2021 (chosen here) | 1799 | 25.4 | -0.08% | -0.10% | -0.23% (-0.66 to +0.20) | 49% | +0.67% | 43% |
| Every stock within 5% of its 50-day high | 2022-2026 (unseen) | 1166 | 32.8 | -0.10% | -0.20% | -0.44% (-0.80 to -0.08) | 47% | +0.25% | 45% |
| Every stock within 5% of its 50-day high | 2014-2026 (all) | 2965 | 28.3 | -0.09% | -0.14% | -0.31% (-0.60 to -0.03) | 48% | +0.50% | 44% |
| Closest to the breakout level | 2014-2021 (chosen here) | 1799 | 9.5 | -0.02% | -0.04% | -0.13% (-0.58 to +0.32) | 49% | +0.77% | 57% |
| Closest to the breakout level | 2022-2026 (unseen) | 1166 | 9.6 | -0.09% | -0.21% | -0.53% (-0.97 to -0.09) | 46% | +0.16% | 58% |
| Closest to the breakout level | 2014-2026 (all) | 2965 | 9.5 | -0.05% | -0.11% | -0.29% (-0.60 to +0.03) | 48% | +0.53% | 57% |
| Uptrend + tightest range, shrinking ranges, drying volume, closest | 2014-2021 (chosen here) | 1790 | 9.2 | -0.06% | -0.10% | -0.13% (-0.59 to +0.34) | 49% | +0.76% | 47% |
| Uptrend + tightest range, shrinking ranges, drying volume, closest | 2022-2026 (unseen) | 1159 | 9.4 | -0.10% | -0.18% | -0.44% (-0.96 to +0.08) | 46% | +0.21% | 46% |
| Uptrend + tightest range, shrinking ranges, drying volume, closest | 2014-2026 (all) | 2949 | 9.3 | -0.07% | -0.13% | -0.25% (-0.63 to +0.13) | 48% | +0.55% | 46% |
| Same + relative strength | 2014-2021 (chosen here) | 1790 | 9.2 | -0.05% | -0.07% | -0.06% (-0.53 to +0.41) | 49% | +0.83% | 47% |
| Same + relative strength | 2022-2026 (unseen) | 1159 | 9.4 | -0.07% | -0.20% | -0.43% (-0.97 to +0.12) | 47% | +0.22% | 47% |
| Same + relative strength | 2014-2026 (all) | 2949 | 9.3 | -0.06% | -0.12% | -0.20% (-0.60 to +0.19) | 48% | +0.59% | 47% |
| Minervini trend template, strongest RS first | 2014-2021 (chosen here) | 1727 | 7.5 | -0.17% | -0.20% | -0.11% (-0.75 to +0.52) | 49% | +0.59% | 45% |
| Minervini trend template, strongest RS first | 2022-2026 (unseen) | 1147 | 7.9 | -0.12% | -0.32% | -0.57% (-1.43 to +0.30) | 48% | +0.04% | 49% |
| Minervini trend template, strongest RS first | 2014-2026 (all) | 2874 | 7.7 | -0.15% | -0.25% | -0.29% (-0.78 to +0.19) | 48% | +0.37% | 47% |
| Uptrend + Bollinger squeeze, strongest RS first | 2014-2021 (chosen here) | 1348 | 3.3 | -0.11% | -0.08% | +0.05% (-0.81 to +0.92) | 49% | +0.61% | 44% |
| Uptrend + Bollinger squeeze, strongest RS first | 2022-2026 (unseen) | 887 | 3.9 | -0.23% | -0.47% | -0.60% (-1.46 to +0.27) | 46% | -0.35% | 40% |
| Uptrend + Bollinger squeeze, strongest RS first | 2014-2026 (all) | 2235 | 3.5 | -0.16% | -0.23% | -0.20% (-0.78 to +0.37) | 48% | +0.23% | 43% |
| Baseline: every liquid stock | 2014-2021 (chosen here) | 1827 | 178.2 | -0.00% | -0.00% | -0.00% (-0.00 to +0.00) | 48% | +1.06% | 23% |
| Baseline: every liquid stock | 2022-2026 (unseen) | 1171 | 305.4 | -0.00% | -0.00% | -0.00% (-0.00 to +0.00) | 48% | +0.70% | 22% |
| Baseline: every liquid stock | 2014-2026 (all) | 2998 | 227.9 | -0.00% | -0.00% | -0.00% (-0.00 to -0.00) | 48% | +0.92% | 22% |

Chosen: **Uptrend + tightest range, shrinking ranges, drying volume, closest** (best 2014-2021 return among lists that broke out at least 1.5x as often as the average stock; returns within 0.01% count as a tie, and a tie goes to the list that broke out more often).

## Caveats

- S&P 500 membership is rebuilt from Wikipedia's change log. Stocks that left the index and no longer trade (most were bought out) have no Yahoo data, so they are missing from the days they were members.
- The S&P 400 + 600 check uses today's members for all years, so it favors stocks that did well.
- Returns include dividends (Yahoo's adjusted prices). The AI picks list pays 0.10% per buy and per sell; the daily lists have no costs.
- Because of those missing stocks, the average stock in the S&P 500 test returned about 3-4% a year more than RSP (the real equal-weight S&P 500 fund) in 2014-2021. That flatters every list against SPY; the comparison with the average stock in the same test is the fair one.
