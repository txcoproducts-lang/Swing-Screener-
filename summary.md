# Day-trade backtest, 2026-08-14 to 2026-11-06 (60 trading days)

Market check passed on 41 of 60 days (no trades on the other days, except 'any').
$5,000, shares, up to 3 at a time at 30% each, flat by the close, 0.05% slippage each way.

## No day-trade limit

| Version | Bars | End $ | Return | Worst drop | Trades | Win % | Avg trade | Avg win | Avg loss |
|---|---|---|---|---|---|---|---|---|---|
| Buy the list at the open, sell at the close | 5m | 4,237 | -15.3% | -17.9% | 117 | 37 | -0.46% | 1.96% | -1.86% |
| Buy the list at the open, sell at the close | 10m | 4,237 | -15.3% | -17.9% | 117 | 37 | -0.46% | 1.96% | -1.86% |
| Uptrend on the chart (EMA10 > EMA20, price > EMA50) | 5m | 4,847 | -3.1% | -9.7% | 288 | 34 | -0.03% | 1.33% | -0.73% |
| Uptrend on the chart (EMA10 > EMA20, price > EMA50) | 10m | 5,141 | +2.8% | -2.9% | 178 | 42 | 0.06% | 1.39% | -0.89% |
| Full uptrend on the chart (also over the 150 line) | 5m | 4,956 | -0.9% | -6.7% | 248 | 35 | -0.01% | 1.33% | -0.73% |
| Full uptrend on the chart (also over the 150 line) | 10m | 5,241 | +4.8% | -3.1% | 165 | 43 | 0.1% | 1.44% | -0.91% |
| Full uptrend, and SPY's chart is in the full uptrend too | 5m | 4,896 | -2.1% | -5.5% | 122 | 38 | -0.05% | 1.27% | -0.85% |
| Full uptrend, and SPY's chart is in the full uptrend too | 10m | 5,105 | +2.1% | -2.5% | 73 | 40 | 0.1% | 1.49% | -0.82% |
| Full uptrend + SPY up, buy a pullback to the 20 EMA | 5m | 5,055 | +1.1% | -2.4% | 97 | 32 | 0.04% | 1.53% | -0.66% |
| Full uptrend + SPY up, buy a pullback to the 20 EMA | 10m | 4,919 | -1.6% | -3.1% | 69 | 32 | -0.08% | 1.39% | -0.76% |
| Full uptrend + SPY up, sell when EMA10 crosses under EMA20 | 5m | 4,859 | -2.8% | -4.6% | 140 | 36 | -0.06% | 1.19% | -0.76% |
| Full uptrend + SPY up, sell when EMA10 crosses under EMA20 | 10m | 5,064 | +1.3% | -3.0% | 81 | 37 | 0.06% | 1.5% | -0.79% |
| Full uptrend + SPY up, any liquid stock (market check, no sector check) | 5m | 5,071 | +1.4% | -7.1% | 144 | 39 | 0.04% | 2.02% | -1.22% |
| Full uptrend + SPY up, any liquid stock (market check, no sector check) | 10m | 5,272 | +5.4% | -5.6% | 78 | 40 | 0.24% | 2.68% | -1.37% |
| Full uptrend + SPY up, any liquid stock (no daily checks) | 5m | 5,415 | +8.3% | -7.2% | 209 | 39 | 0.14% | 2.09% | -1.13% |
| Full uptrend + SPY up, any liquid stock (no daily checks) | 10m | 5,761 | +15.2% | -6.9% | 114 | 46 | 0.43% | 2.59% | -1.38% |

SPY held over the same days: -5.1%

## Under the $25,000 rule (3 day trades per 5 days)

| Version | Bars | End $ | Return | Worst drop | Trades | Win % | Avg trade | Avg win | Avg loss |
|---|---|---|---|---|---|---|---|---|---|
| Buy the list at the open, sell at the close | 5m | 5,252 | +5.0% | -2.1% | 27 | 56 | 0.62% | 2.35% | -1.54% |
| Buy the list at the open, sell at the close | 10m | 5,252 | +5.0% | -2.1% | 27 | 56 | 0.62% | 2.35% | -1.54% |
| Uptrend on the chart (EMA10 > EMA20, price > EMA50) | 5m | 5,368 | +7.4% | -1.2% | 38 | 50 | 0.63% | 1.78% | -0.52% |
| Uptrend on the chart (EMA10 > EMA20, price > EMA50) | 10m | 5,228 | +4.6% | -1.3% | 36 | 50 | 0.42% | 1.51% | -0.67% |
| Full uptrend on the chart (also over the 150 line) | 5m | 5,235 | +4.7% | -1.2% | 37 | 46 | 0.42% | 1.78% | -0.74% |
| Full uptrend on the chart (also over the 150 line) | 10m | 5,289 | +5.8% | -1.1% | 34 | 59 | 0.56% | 1.48% | -0.76% |
| Full uptrend, and SPY's chart is in the full uptrend too | 5m | 5,034 | +0.7% | -1.5% | 31 | 35 | 0.08% | 1.9% | -0.92% |
| Full uptrend, and SPY's chart is in the full uptrend too | 10m | 5,147 | +2.9% | -1.2% | 26 | 54 | 0.38% | 1.31% | -0.71% |
| Full uptrend + SPY up, buy a pullback to the 20 EMA | 5m | 5,111 | +2.2% | -1.5% | 28 | 29 | 0.27% | 2.26% | -0.53% |
| Full uptrend + SPY up, buy a pullback to the 20 EMA | 10m | 5,128 | +2.6% | -0.8% | 25 | 48 | 0.34% | 1.35% | -0.58% |
| Full uptrend + SPY up, sell when EMA10 crosses under EMA20 | 5m | 5,014 | +0.3% | -2.1% | 33 | 36 | 0.03% | 1.68% | -0.91% |
| Full uptrend + SPY up, sell when EMA10 crosses under EMA20 | 10m | 5,174 | +3.5% | -0.7% | 27 | 56 | 0.43% | 1.3% | -0.67% |
| Full uptrend + SPY up, any liquid stock (market check, no sector check) | 5m | 5,155 | +3.1% | -2.5% | 34 | 41 | 0.31% | 2.51% | -1.22% |
| Full uptrend + SPY up, any liquid stock (market check, no sector check) | 10m | 5,513 | +10.3% | -1.9% | 24 | 54 | 1.38% | 3.25% | -0.83% |
| Full uptrend + SPY up, any liquid stock (no daily checks) | 5m | 4,891 | -2.2% | -3.7% | 49 | 33 | -0.15% | 1.84% | -1.11% |
| Full uptrend + SPY up, any liquid stock (no daily checks) | 10m | 5,813 | +16.3% | -1.4% | 36 | 58 | 1.42% | 3.29% | -1.19% |

SPY held over the same days: -5.1%
