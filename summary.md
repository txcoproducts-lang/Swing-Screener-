# Day-trade backtest, 2026-08-14 to 2026-11-20 (70 trading days)

Market check passed on 41 of 70 days (no trades on the other days, except 'any').
$5,000, shares, up to 3 at a time at 30% each, flat by the close, 0.05% slippage each way.

## No day-trade limit

| Version | Bars | End $ | Return | Worst drop | Trades | Win % | Avg trade | Avg win | Avg loss |
|---|---|---|---|---|---|---|---|---|---|
| Buy the list at the open, sell at the close | 5m | 5,395 | +7.9% | -14.1% | 117 | 44 | 0.27% | 3.4% | -2.14% |
| Buy the list at the open, sell at the close | 10m | 5,395 | +7.9% | -14.1% | 117 | 44 | 0.27% | 3.4% | -2.14% |
| Uptrend on the chart (EMA10 > EMA20, price > EMA50) | 5m | 5,512 | +10.2% | -8.1% | 308 | 33 | 0.12% | 1.82% | -0.72% |
| Uptrend on the chart (EMA10 > EMA20, price > EMA50) | 10m | 5,470 | +9.4% | -5.3% | 192 | 39 | 0.18% | 1.96% | -0.97% |
| Full uptrend on the chart (also over the 150 line) | 5m | 5,685 | +13.7% | -7.2% | 267 | 36 | 0.18% | 1.87% | -0.76% |
| Full uptrend on the chart (also over the 150 line) | 10m | 5,550 | +11.0% | -5.4% | 179 | 40 | 0.22% | 2.03% | -1.0% |
| Full uptrend, and SPY's chart is in the full uptrend too | 5m | 5,088 | +1.8% | -5.6% | 124 | 38 | 0.06% | 1.74% | -0.97% |
| Full uptrend, and SPY's chart is in the full uptrend too | 10m | 5,274 | +5.5% | -2.5% | 72 | 39 | 0.25% | 1.87% | -0.77% |
| Full uptrend + SPY up, buy a pullback to the 20 EMA | 5m | 5,151 | +3.0% | -2.5% | 95 | 39 | 0.11% | 1.4% | -0.71% |
| Full uptrend + SPY up, buy a pullback to the 20 EMA | 10m | 4,982 | -0.4% | -2.2% | 69 | 32 | -0.01% | 1.48% | -0.71% |
| Full uptrend + SPY up, sell when EMA10 crosses under EMA20 | 5m | 5,098 | +2.0% | -4.9% | 137 | 36 | 0.06% | 1.65% | -0.86% |
| Full uptrend + SPY up, sell when EMA10 crosses under EMA20 | 10m | 5,233 | +4.7% | -2.9% | 80 | 38 | 0.2% | 1.8% | -0.76% |
| Full uptrend + SPY up, any liquid stock (market check, no sector check) | 5m | 5,061 | +1.2% | -7.1% | 144 | 39 | 0.04% | 2.02% | -1.22% |
| Full uptrend + SPY up, any liquid stock (market check, no sector check) | 10m | 5,300 | +6.0% | -5.7% | 78 | 41 | 0.26% | 2.58% | -1.34% |
| Full uptrend + SPY up, any liquid stock (no daily checks) | 5m | 5,383 | +7.7% | -7.3% | 231 | 40 | 0.12% | 2.04% | -1.16% |
| Full uptrend + SPY up, any liquid stock (no daily checks) | 10m | 5,340 | +6.8% | -7.8% | 134 | 43 | 0.18% | 2.35% | -1.47% |

SPY held over the same days: -10.9%

## Under the $25,000 rule (3 day trades per 5 days)

| Version | Bars | End $ | Return | Worst drop | Trades | Win % | Avg trade | Avg win | Avg loss |
|---|---|---|---|---|---|---|---|---|---|
| Buy the list at the open, sell at the close | 5m | 5,530 | +10.6% | -2.1% | 27 | 63 | 1.27% | 2.99% | -1.66% |
| Buy the list at the open, sell at the close | 10m | 5,530 | +10.6% | -2.1% | 27 | 63 | 1.27% | 2.99% | -1.66% |
| Uptrend on the chart (EMA10 > EMA20, price > EMA50) | 5m | 5,242 | +4.8% | -1.3% | 39 | 49 | 0.41% | 1.55% | -0.67% |
| Uptrend on the chart (EMA10 > EMA20, price > EMA50) | 10m | 5,053 | +1.1% | -4.1% | 38 | 42 | 0.1% | 1.75% | -1.09% |
| Full uptrend on the chart (also over the 150 line) | 5m | 5,121 | +2.4% | -1.3% | 38 | 45 | 0.22% | 1.58% | -0.89% |
| Full uptrend on the chart (also over the 150 line) | 10m | 5,112 | +2.2% | -3.9% | 36 | 50 | 0.21% | 1.69% | -1.26% |
| Full uptrend, and SPY's chart is in the full uptrend too | 5m | 4,860 | -2.8% | -2.7% | 32 | 28 | -0.29% | 1.97% | -1.18% |
| Full uptrend, and SPY's chart is in the full uptrend too | 10m | 5,236 | +4.7% | -1.3% | 26 | 50 | 0.6% | 1.87% | -0.67% |
| Full uptrend + SPY up, buy a pullback to the 20 EMA | 5m | 5,213 | +4.3% | -1.7% | 28 | 39 | 0.51% | 2.2% | -0.59% |
| Full uptrend + SPY up, buy a pullback to the 20 EMA | 10m | 5,064 | +1.3% | -0.7% | 27 | 37 | 0.16% | 1.27% | -0.49% |
| Full uptrend + SPY up, sell when EMA10 crosses under EMA20 | 5m | 4,873 | -2.5% | -2.5% | 32 | 31 | -0.26% | 1.74% | -1.17% |
| Full uptrend + SPY up, sell when EMA10 crosses under EMA20 | 10m | 5,273 | +5.5% | -0.7% | 27 | 56 | 0.67% | 1.71% | -0.64% |
| Full uptrend + SPY up, any liquid stock (market check, no sector check) | 5m | 5,162 | +3.2% | -2.4% | 34 | 41 | 0.32% | 2.51% | -1.21% |
| Full uptrend + SPY up, any liquid stock (market check, no sector check) | 10m | 5,511 | +10.2% | -1.9% | 24 | 58 | 1.38% | 2.98% | -0.86% |
| Full uptrend + SPY up, any liquid stock (no daily checks) | 5m | 4,981 | -0.4% | -3.7% | 57 | 35 | -0.02% | 1.93% | -1.07% |
| Full uptrend + SPY up, any liquid stock (no daily checks) | 10m | 5,440 | +8.8% | -6.4% | 44 | 55 | 0.67% | 2.94% | -2.04% |

SPY held over the same days: -10.9%
