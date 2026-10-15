# Order block backtest

1,000 stocks (S&P 500: 498, S&P 400: 399, S&P 600: 103), daily bars 2016-10-17 to 2026-10-14, plus the same stocks on weekly bars. Run 2026-10-15 02:18 UTC.

Each order block gives one trade: the first time price comes back to the zone, buy at the entry level (short for bearish blocks), stop 0.1 ATR past the far side of the zone (at least 0.25 ATR away), target 2x the risk, exit after 20 bars otherwise. Results are the average per trade in R (1R = the amount risked), with a 95% range, the share of winning trades and the number of trades. "Edge" is the result minus random zones built and traded the same way.

## Best variation (daily bars)

**Strong move: same, but the move must be 2 ATR or more**, entering at the **near edge (full wick range)**.

- Bullish blocks (buy at support): +0.172R ±0.163 · 35% win · 17,352; edge +0.076R (-0.023 to +0.246)
- Bearish blocks (short at resistance): -0.033R ±0.057 · 31% win · 21,415; edge +0.042R (+0.005 to +0.080)

## Ranking (daily bars, best average of bullish and bearish first)

| # | Definition | Enter at | Bullish | Bearish | Edge bullish | Edge bearish |
|---|---|---|---|---|---|---|
| 1 | Strong move | near edge (full wick range) | +0.172R (17,352) | -0.033R (21,415) | +0.076R (-0.023 to +0.246) | +0.042R (+0.005 to +0.080) |
| 2 | Volume surge | near edge (full wick range) | +0.153R (30,767) | -0.050R (35,230) | +0.056R (-0.007 to +0.154) | +0.025R (-0.001 to +0.051) |
| 3 | Break of structure + fair value gap | near edge (full wick range) | +0.121R (46,273) | -0.057R (39,407) | +0.025R (-0.015 to +0.088) | +0.018R (-0.006 to +0.040) |
| 4 | Break of structure | near edge (full wick range) | +0.119R (51,900) | -0.057R (44,698) | +0.023R (-0.014 to +0.080) | +0.018R (-0.005 to +0.040) |
| 5 | Classic | near edge (full wick range) | +0.123R (81,897) | -0.063R (80,860) | +0.027R (-0.001 to +0.065) | +0.011R (-0.009 to +0.031) |
| 6 | Strong move | candle body | +0.063R (16,948) | -0.019R (21,162) | -0.002R (-0.037 to +0.036) | +0.042R (+0.008 to +0.077) |
| 7 | Volume surge | candle body | +0.077R (30,092) | -0.045R (34,845) | +0.013R (-0.016 to +0.044) | +0.016R (-0.009 to +0.042) |
| 8 | LuxAlgo style | 50% of the candle | +0.083R (73,209) | -0.058R (61,838) | +0.052R (+0.030 to +0.074) | -0.020R (-0.043 to +0.004) |
| 9 | Classic | candle body | +0.075R (79,879) | -0.050R (79,934) | +0.011R (-0.004 to +0.027) | +0.012R (-0.008 to +0.032) |
| 10 | LuxAlgo style | candle body | +0.105R (64,608) | -0.083R (50,618) | +0.040R (+0.019 to +0.060) | -0.021R (-0.049 to +0.008) |
| 11 | Break of structure | candle body | +0.064R (50,700) | -0.044R (44,168) | -0.000R (-0.017 to +0.015) | +0.017R (-0.004 to +0.039) |
| 12 | LuxAlgo style | near edge (full wick range) | +0.117R (55,710) | -0.100R (40,830) | +0.021R (-0.001 to +0.042) | -0.026R (-0.057 to +0.006) |
| 13 | Break of structure + fair value gap | candle body | +0.062R (45,216) | -0.047R (38,925) | -0.002R (-0.019 to +0.015) | +0.015R (-0.006 to +0.036) |
| 14 | Volume surge | 50% of the candle | +0.040R (29,374) | -0.033R (34,542) | +0.009R (-0.019 to +0.036) | +0.005R (-0.017 to +0.029) |
| 15 | Strong move | 50% of the candle | +0.015R (16,559) | -0.009R (20,926) | -0.016R (-0.049 to +0.019) | +0.029R (-0.001 to +0.060) |
| 16 | Classic | 50% of the candle | +0.036R (77,912) | -0.034R (79,108) | +0.005R (-0.009 to +0.020) | +0.003R (-0.014 to +0.020) |
| 17 | Break of structure | 50% of the candle | +0.027R (49,619) | -0.028R (43,743) | -0.005R (-0.022 to +0.012) | +0.009R (-0.010 to +0.032) |
| 18 | Break of structure + fair value gap | 50% of the candle | +0.028R (44,254) | -0.031R (38,554) | -0.003R (-0.021 to +0.015) | +0.006R (-0.014 to +0.026) |
| | Random zones | near edge (full wick range) | +0.096R (159,131) | -0.074R (144,642) | | |

## Detail for the best variation (daily bars)

| Slice | Bullish | Bearish |
|---|---|---|
| All trades | +0.172R ±0.163 · 35% win · 17,352 | -0.033R ±0.057 · 31% win · 21,415 |
| With your trend (uptrend for longs, downtrend for shorts) | +0.077R ±0.083 · 34% win · 6,086 | +0.028R ±0.101 · 33% win · 4,145 |
| No clear trend | +0.110R ±0.081 · 35% win · 6,316 | -0.049R ±0.069 · 31% win · 7,965 |
| Against the trend | +0.369R ±0.507 · 35% win · 4,950 | -0.045R ±0.058 · 31% win · 9,305 |
| First half (2016-10-17 to 2021-10-15) | +0.236R ±0.359 · 34% win · 7,692 | -0.031R ±0.090 · 31% win · 10,657 |
| Second half (2021-10-15 to 2026-10-14) | +0.122R ±0.074 · 35% win · 9,660 | -0.034R ±0.071 · 31% win · 10,758 |
| S&P 500 stocks only | +0.097R ±0.072 · 34% win · 8,826 | -0.041R ±0.060 · 31% win · 11,685 |
| Zone revisited within 21 bars | +0.244R ±0.276 · 35% win · 9,323 | -0.009R ±0.070 · 32% win · 11,104 |
| Zone revisited after 21 bars | +0.089R ±0.078 · 34% win · 8,029 | -0.059R ±0.068 · 30% win · 10,311 |
| Target 1R / 2R / 3R | +0.097 / +0.172 / +0.204 | -0.002 / -0.033 / -0.066 |
| Zone held (no close through it in 10 bars) | 42% held, 75% of zones revisited | 41% held, 88% of zones revisited |
| Weekly bars, same rules | +0.127R ±0.151 · 38% win · 3,605; edge -0.003R (-0.072 to +0.070) | -0.088R ±0.108 · 31% win · 4,217; edge +0.054R (-0.017 to +0.122) |

## Daily bars, bullish blocks, buy the first pullback into the zone

| Definition | Enter at near edge (full wick range) | Enter at candle body | Enter at 50% of the candle |
|---|---|---|---|
| Classic | +0.123R ±0.070 · 36% win · 81,897 | +0.075R ±0.053 · 34% win · 79,879 | +0.036R ±0.046 · 32% win · 77,912 |
| Strong move | +0.172R ±0.163 · 35% win · 17,352 | +0.063R ±0.066 · 33% win · 16,948 | +0.015R ±0.061 · 31% win · 16,559 |
| Break of structure | +0.119R ±0.078 · 35% win · 51,900 | +0.064R ±0.052 · 33% win · 50,700 | +0.027R ±0.047 · 31% win · 49,619 |
| Break of structure + fair value gap | +0.121R ±0.083 · 35% win · 46,273 | +0.062R ±0.053 · 33% win · 45,216 | +0.028R ±0.048 · 31% win · 44,254 |
| Volume surge | +0.153R ±0.104 · 36% win · 30,767 | +0.077R ±0.055 · 34% win · 30,092 | +0.040R ±0.050 · 32% win · 29,374 |
| LuxAlgo style | +0.117R ±0.063 · 39% win · 55,710 | +0.105R ±0.058 · 37% win · 64,608 | +0.083R ±0.053 · 34% win · 73,209 |
| Baseline | +0.096R ±0.059 · 36% win · 159,131 | +0.064R ±0.053 · 34% win · 155,026 | +0.031R ±0.048 · 32% win · 151,027 |

## Daily bars, bearish blocks, short the first rally into the zone

| Definition | Enter at near edge (full wick range) | Enter at candle body | Enter at 50% of the candle |
|---|---|---|---|
| Classic | -0.063R ±0.050 · 30% win · 80,860 | -0.050R ±0.041 · 30% win · 79,934 | -0.034R ±0.035 · 30% win · 79,108 |
| Strong move | -0.033R ±0.057 · 31% win · 21,415 | -0.019R ±0.047 · 31% win · 21,162 | -0.009R ±0.040 · 30% win · 20,926 |
| Break of structure | -0.057R ±0.052 · 31% win · 44,698 | -0.044R ±0.045 · 30% win · 44,168 | -0.028R ±0.041 · 30% win · 43,743 |
| Break of structure + fair value gap | -0.057R ±0.053 · 31% win · 39,407 | -0.047R ±0.045 · 30% win · 38,925 | -0.031R ±0.040 · 30% win · 38,554 |
| Volume surge | -0.050R ±0.051 · 31% win · 35,230 | -0.045R ±0.043 · 30% win · 34,845 | -0.033R ±0.038 · 30% win · 34,542 |
| LuxAlgo style | -0.100R ±0.062 · 32% win · 40,830 | -0.083R ±0.054 · 31% win · 50,618 | -0.058R ±0.042 · 30% win · 61,838 |
| Baseline | -0.074R ±0.053 · 31% win · 144,642 | -0.062R ±0.045 · 30% win · 142,807 | -0.037R ±0.038 · 30% win · 141,059 |

## Weekly bars, bullish blocks, buy the first pullback into the zone

| Definition | Enter at near edge (full wick range) | Enter at candle body | Enter at 50% of the candle |
|---|---|---|---|
| Classic | +0.150R ±0.118 · 39% win · 17,405 | +0.092R ±0.115 · 36% win · 16,658 | +0.020R ±0.110 · 34% win · 15,884 |
| Strong move | +0.127R ±0.151 · 38% win · 3,605 | +0.051R ±0.143 · 35% win · 3,435 | -0.011R ±0.146 · 33% win · 3,287 |
| Break of structure | +0.127R ±0.120 · 38% win · 11,564 | +0.069R ±0.118 · 36% win · 11,114 | +0.005R ±0.111 · 33% win · 10,699 |
| Break of structure + fair value gap | +0.143R ±0.123 · 39% win · 9,541 | +0.082R ±0.122 · 36% win · 9,168 | +0.010R ±0.116 · 33% win · 8,816 |
| Volume surge | +0.133R ±0.129 · 39% win · 5,523 | +0.098R ±0.125 · 37% win · 5,313 | +0.035R ±0.126 · 34% win · 5,080 |
| LuxAlgo style | +0.190R ±0.096 · 43% win · 12,724 | +0.164R ±0.096 · 41% win · 14,514 | +0.108R ±0.102 · 37% win · 15,993 |
| Baseline | +0.131R ±0.127 · 39% win · 31,039 | +0.085R ±0.127 · 37% win · 29,657 | +0.025R ±0.125 · 34% win · 28,194 |

## Weekly bars, bearish blocks, short the first rally into the zone

| Definition | Enter at near edge (full wick range) | Enter at candle body | Enter at 50% of the candle |
|---|---|---|---|
| Classic | -0.161R ±0.083 · 28% win · 16,376 | -0.142R ±0.069 · 29% win · 16,097 | -0.111R ±0.063 · 29% win · 15,779 |
| Strong move | -0.088R ±0.108 · 31% win · 4,217 | -0.108R ±0.085 · 30% win · 4,154 | -0.090R ±0.082 · 30% win · 4,052 |
| Break of structure | -0.177R ±0.104 · 28% win · 7,871 | -0.149R ±0.089 · 28% win · 7,738 | -0.121R ±0.079 · 29% win · 7,586 |
| Break of structure + fair value gap | -0.166R ±0.104 · 28% win · 6,611 | -0.149R ±0.087 · 28% win · 6,503 | -0.122R ±0.079 · 29% win · 6,368 |
| Volume surge | -0.138R ±0.093 · 29% win · 8,046 | -0.115R ±0.077 · 29% win · 7,923 | -0.094R ±0.068 · 30% win · 7,763 |
| LuxAlgo style | -0.220R ±0.082 · 30% win · 7,047 | -0.204R ±0.077 · 29% win · 9,425 | -0.166R ±0.068 · 29% win · 12,496 |
| Baseline | -0.142R ±0.091 · 30% win · 26,221 | -0.126R ±0.078 · 30% win · 25,625 | -0.110R ±0.069 · 29% win · 25,101 |

## Definitions

- **Classic**: last opposite candle before a move of 1 ATR or more within 3 bars
- **Strong move**: same, but the move must be 2 ATR or more
- **Break of structure**: classic, and the move also closes past the last swing high/low
- **Break of structure + fair value gap**: the move also leaves a price gap (strict ICT)
- **Volume surge**: classic, and the move comes on 1.5x the 20-day average volume
- **LuxAlgo style**: the biggest volume of 11 bars at a swing low/high
- **Baseline**: a random candle that price later moved 1 ATR away from

Entry levels for a bullish block (mirror for bearish): near edge = the candle's high, body = the top of the candle's body, 50% = halfway between high and low. The stop is always below the candle's low.

Notes: today's index members are used for the whole 10 years, so stocks that were dropped or went bust are missing (this flatters long trades; the random zones have the same bias). No commissions; orders that gap are filled at the open. Inside a bar, the extreme nearer the open is assumed to come first (TradingView's rule).
