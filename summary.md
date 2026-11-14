# Day-trade backtest, 2026-08-14 to 2026-11-13 (65 trading days)

Market check passed on 41 of 65 days (no trades on the other days, except 'any').
$5,000, shares, up to 3 at a time at 30% each, flat by the close, 0.05% slippage each way.

## No day-trade limit

| Version | Bars | End $ | Return | Worst drop | Trades | Win % | Avg trade | Avg win | Avg loss |
|---|---|---|---|---|---|---|---|---|---|
| Buy the list at the open, sell at the close | 5m | 4,262 | -14.8% | -17.4% | 117 | 38 | -0.44% | 1.91% | -1.86% |
| Buy the list at the open, sell at the close | 10m | 4,262 | -14.8% | -17.4% | 117 | 38 | -0.44% | 1.91% | -1.86% |
| Uptrend on the chart (EMA10 > EMA20, price > EMA50) | 5m | 4,787 | -4.3% | -10.3% | 293 | 33 | -0.04% | 1.31% | -0.72% |
| Uptrend on the chart (EMA10 > EMA20, price > EMA50) | 10m | 5,054 | +1.1% | -4.1% | 184 | 40 | 0.02% | 1.38% | -0.89% |
| Full uptrend on the chart (also over the 150 line) | 5m | 4,954 | -0.9% | -6.9% | 253 | 36 | -0.01% | 1.3% | -0.73% |
| Full uptrend on the chart (also over the 150 line) | 10m | 5,168 | +3.4% | -3.9% | 172 | 41 | 0.07% | 1.42% | -0.88% |
| Full uptrend, and SPY's chart is in the full uptrend too | 5m | 4,877 | -2.5% | -5.6% | 123 | 37 | -0.06% | 1.27% | -0.86% |
| Full uptrend, and SPY's chart is in the full uptrend too | 10m | 5,104 | +2.1% | -2.5% | 73 | 40 | 0.1% | 1.49% | -0.82% |
| Full uptrend + SPY up, buy a pullback to the 20 EMA | 5m | 5,013 | +0.3% | -3.1% | 100 | 31 | 0.01% | 1.53% | -0.67% |
| Full uptrend + SPY up, buy a pullback to the 20 EMA | 10m | 4,919 | -1.6% | -3.1% | 69 | 32 | -0.08% | 1.39% | -0.76% |
| Full uptrend + SPY up, sell when EMA10 crosses under EMA20 | 5m | 4,838 | -3.2% | -4.8% | 141 | 35 | -0.07% | 1.18% | -0.77% |
| Full uptrend + SPY up, sell when EMA10 crosses under EMA20 | 10m | 5,063 | +1.3% | -2.9% | 81 | 37 | 0.06% | 1.49% | -0.79% |
| Full uptrend + SPY up, any liquid stock (market check, no sector check) | 5m | 5,061 | +1.2% | -7.1% | 144 | 39 | 0.04% | 2.02% | -1.22% |
| Full uptrend + SPY up, any liquid stock (market check, no sector check) | 10m | 5,300 | +6.0% | -5.7% | 78 | 41 | 0.26% | 2.58% | -1.34% |
| Full uptrend + SPY up, any liquid stock (no daily checks) | 5m | 5,545 | +10.9% | -7.3% | 225 | 40 | 0.16% | 2.05% | -1.1% |
| Full uptrend + SPY up, any liquid stock (no daily checks) | 10m | 5,688 | +13.8% | -7.0% | 131 | 44 | 0.34% | 2.35% | -1.26% |

SPY held over the same days: -2.6%

## Under the $25,000 rule (3 day trades per 5 days)

| Version | Bars | End $ | Return | Worst drop | Trades | Win % | Avg trade | Avg win | Avg loss |
|---|---|---|---|---|---|---|---|---|---|
| Buy the list at the open, sell at the close | 5m | 5,277 | +5.5% | -2.1% | 27 | 59 | 0.68% | 2.24% | -1.6% |
| Buy the list at the open, sell at the close | 10m | 5,277 | +5.5% | -2.1% | 27 | 59 | 0.68% | 2.24% | -1.6% |
| Uptrend on the chart (EMA10 > EMA20, price > EMA50) | 5m | 5,361 | +7.2% | -1.3% | 38 | 53 | 0.62% | 1.67% | -0.55% |
| Uptrend on the chart (EMA10 > EMA20, price > EMA50) | 10m | 5,220 | +4.4% | -1.3% | 36 | 50 | 0.41% | 1.5% | -0.69% |
| Full uptrend on the chart (also over the 150 line) | 5m | 5,237 | +4.7% | -1.3% | 37 | 49 | 0.42% | 1.71% | -0.8% |
| Full uptrend on the chart (also over the 150 line) | 10m | 5,281 | +5.6% | -1.1% | 34 | 59 | 0.54% | 1.48% | -0.79% |
| Full uptrend, and SPY's chart is in the full uptrend too | 5m | 5,033 | +0.7% | -1.5% | 31 | 35 | 0.07% | 1.91% | -0.93% |
| Full uptrend, and SPY's chart is in the full uptrend too | 10m | 5,145 | +2.9% | -1.3% | 26 | 54 | 0.37% | 1.3% | -0.71% |
| Full uptrend + SPY up, buy a pullback to the 20 EMA | 5m | 5,100 | +2.0% | -1.6% | 26 | 27 | 0.26% | 2.45% | -0.54% |
| Full uptrend + SPY up, buy a pullback to the 20 EMA | 10m | 5,128 | +2.6% | -0.8% | 25 | 48 | 0.34% | 1.34% | -0.58% |
| Full uptrend + SPY up, sell when EMA10 crosses under EMA20 | 5m | 5,012 | +0.2% | -2.1% | 33 | 36 | 0.03% | 1.68% | -0.92% |
| Full uptrend + SPY up, sell when EMA10 crosses under EMA20 | 10m | 5,173 | +3.5% | -0.7% | 27 | 56 | 0.42% | 1.3% | -0.67% |
| Full uptrend + SPY up, any liquid stock (market check, no sector check) | 5m | 5,162 | +3.2% | -2.4% | 34 | 41 | 0.32% | 2.51% | -1.21% |
| Full uptrend + SPY up, any liquid stock (market check, no sector check) | 10m | 5,511 | +10.2% | -1.9% | 24 | 58 | 1.38% | 2.98% | -0.86% |
| Full uptrend + SPY up, any liquid stock (no daily checks) | 5m | 4,954 | -0.9% | -3.7% | 54 | 33 | -0.05% | 1.98% | -1.07% |
| Full uptrend + SPY up, any liquid stock (no daily checks) | 10m | 5,794 | +15.9% | -1.4% | 41 | 59 | 1.22% | 2.94% | -1.2% |

SPY held over the same days: -2.6%
