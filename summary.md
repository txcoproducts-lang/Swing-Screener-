# Day-trade backtest, 2026-08-14 to 2026-10-30 (55 trading days)

Market check passed on 41 of 55 days (no trades on the other days, except 'any').
$5,000, shares, up to 3 at a time at 30% each, flat by the close, 0.05% slippage each way.

## No day-trade limit

| Version | Bars | End $ | Return | Worst drop | Trades | Win % | Avg trade | Avg win | Avg loss |
|---|---|---|---|---|---|---|---|---|---|
| Buy the list at the open, sell at the close | 5m | 4,290 | -14.2% | -17.8% | 117 | 38 | -0.42% | 1.93% | -1.89% |
| Buy the list at the open, sell at the close | 10m | 4,290 | -14.2% | -17.8% | 117 | 38 | -0.42% | 1.93% | -1.89% |
| Uptrend on the chart (EMA10 > EMA20, price > EMA50) | 5m | 4,872 | -2.6% | -10.1% | 278 | 35 | -0.03% | 1.31% | -0.74% |
| Uptrend on the chart (EMA10 > EMA20, price > EMA50) | 10m | 5,222 | +4.4% | -3.8% | 177 | 43 | 0.09% | 1.43% | -0.92% |
| Full uptrend on the chart (also over the 150 line) | 5m | 5,053 | +1.1% | -5.5% | 237 | 36 | 0.02% | 1.34% | -0.72% |
| Full uptrend on the chart (also over the 150 line) | 10m | 5,331 | +6.6% | -2.9% | 161 | 45 | 0.14% | 1.45% | -0.93% |
| Full uptrend, and SPY's chart is in the full uptrend too | 5m | 4,971 | -0.6% | -5.8% | 118 | 41 | -0.01% | 1.22% | -0.85% |
| Full uptrend, and SPY's chart is in the full uptrend too | 10m | 5,198 | +4.0% | -2.1% | 70 | 44 | 0.19% | 1.44% | -0.81% |
| Full uptrend + SPY up, buy a pullback to the 20 EMA | 5m | 5,071 | +1.4% | -2.7% | 93 | 38 | 0.05% | 1.23% | -0.66% |
| Full uptrend + SPY up, buy a pullback to the 20 EMA | 10m | 5,145 | +2.9% | -1.8% | 61 | 41 | 0.16% | 1.39% | -0.7% |
| Full uptrend + SPY up, sell when EMA10 crosses under EMA20 | 5m | 4,912 | -1.8% | -5.2% | 137 | 38 | -0.04% | 1.13% | -0.76% |
| Full uptrend + SPY up, sell when EMA10 crosses under EMA20 | 10m | 5,143 | +2.9% | -3.3% | 80 | 40 | 0.12% | 1.44% | -0.76% |
| Full uptrend + SPY up, any liquid stock (market check, no sector check) | 5m | 5,123 | +2.5% | -6.8% | 143 | 39 | 0.07% | 2.03% | -1.2% |
| Full uptrend + SPY up, any liquid stock (market check, no sector check) | 10m | 5,373 | +7.5% | -5.5% | 79 | 42 | 0.32% | 2.55% | -1.28% |
| Full uptrend + SPY up, any liquid stock (no daily checks) | 5m | 5,537 | +10.7% | -6.8% | 194 | 41 | 0.19% | 2.03% | -1.11% |
| Full uptrend + SPY up, any liquid stock (no daily checks) | 10m | 5,672 | +13.4% | -6.8% | 111 | 47 | 0.39% | 2.35% | -1.33% |

SPY held over the same days: -2.4%

## Under the $25,000 rule (3 day trades per 5 days)

| Version | Bars | End $ | Return | Worst drop | Trades | Win % | Avg trade | Avg win | Avg loss |
|---|---|---|---|---|---|---|---|---|---|
| Buy the list at the open, sell at the close | 5m | 5,228 | +4.6% | -2.1% | 27 | 56 | 0.56% | 2.25% | -1.54% |
| Buy the list at the open, sell at the close | 10m | 5,228 | +4.6% | -2.1% | 27 | 56 | 0.56% | 2.25% | -1.54% |
| Uptrend on the chart (EMA10 > EMA20, price > EMA50) | 5m | 5,389 | +7.8% | -0.9% | 38 | 53 | 0.66% | 1.72% | -0.51% |
| Uptrend on the chart (EMA10 > EMA20, price > EMA50) | 10m | 5,277 | +5.5% | -1.0% | 37 | 49 | 0.49% | 1.58% | -0.54% |
| Full uptrend on the chart (also over the 150 line) | 5m | 5,290 | +5.8% | -0.8% | 39 | 49 | 0.49% | 1.64% | -0.6% |
| Full uptrend on the chart (also over the 150 line) | 10m | 5,318 | +6.4% | -0.8% | 35 | 54 | 0.59% | 1.62% | -0.63% |
| Full uptrend, and SPY's chart is in the full uptrend too | 5m | 5,030 | +0.6% | -1.9% | 31 | 39 | 0.07% | 1.61% | -0.9% |
| Full uptrend, and SPY's chart is in the full uptrend too | 10m | 5,168 | +3.4% | -1.3% | 26 | 54 | 0.43% | 1.41% | -0.71% |
| Full uptrend + SPY up, buy a pullback to the 20 EMA | 5m | 5,076 | +1.5% | -1.1% | 29 | 31 | 0.18% | 1.58% | -0.45% |
| Full uptrend + SPY up, buy a pullback to the 20 EMA | 10m | 5,186 | +3.7% | -0.4% | 22 | 59 | 0.56% | 1.33% | -0.55% |
| Full uptrend + SPY up, sell when EMA10 crosses under EMA20 | 5m | 5,009 | +0.2% | -1.8% | 33 | 39 | 0.02% | 1.43% | -0.89% |
| Full uptrend + SPY up, sell when EMA10 crosses under EMA20 | 10m | 5,195 | +3.9% | -0.7% | 27 | 56 | 0.48% | 1.4% | -0.67% |
| Full uptrend + SPY up, any liquid stock (market check, no sector check) | 5m | 5,135 | +2.7% | -2.2% | 34 | 41 | 0.27% | 2.37% | -1.2% |
| Full uptrend + SPY up, any liquid stock (market check, no sector check) | 10m | 5,534 | +10.7% | -1.9% | 24 | 58 | 1.44% | 3.08% | -0.86% |
| Full uptrend + SPY up, any liquid stock (no daily checks) | 5m | 4,984 | -0.3% | -3.1% | 46 | 37 | -0.02% | 1.7% | -1.03% |
| Full uptrend + SPY up, any liquid stock (no daily checks) | 10m | 5,609 | +12.2% | -1.4% | 33 | 61 | 1.18% | 2.79% | -1.3% |

SPY held over the same days: -2.4%
