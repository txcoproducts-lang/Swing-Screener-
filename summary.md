# Order block backtest

1,000 stocks (S&P 500: 499, S&P 400: 399, S&P 600: 102), daily bars 2016-10-03 to 2026-10-02, plus the same stocks on weekly bars. Run 2026-10-05 06:36 UTC.

Each order block gives one trade: the first time price comes back to the zone, buy at the entry level (short for bearish blocks), stop 0.1 ATR past the far side of the zone (at least 0.25 ATR away), target 2x the risk, exit after 20 bars otherwise. Results are the average per trade in R (1R = the amount risked), with a 95% range, the share of winning trades and the number of trades. "Edge" is the result minus random zones built and traded the same way.

## Best variation (daily bars)

**Strong move: same, but the move must be 2 ATR or more**, entering at the **near edge (full wick range)**.

- Bullish blocks (buy at support): +0.102R ±0.073 · 35% win · 17,296; edge -0.025R (-0.098 to +0.032)
- Bearish blocks (short at resistance): -0.030R ±0.057 · 31% win · 21,406; edge +0.047R (+0.010 to +0.084)

## Ranking (daily bars, best average of bullish and bearish first)

| # | Definition | Enter at | Bullish | Bearish | Edge bullish | Edge bearish |
|---|---|---|---|---|---|---|
| 1 | Strong move | near edge (full wick range) | +0.102R (17,296) | -0.030R (21,406) | -0.025R (-0.098 to +0.032) | +0.047R (+0.010 to +0.084) |
| 2 | Volume surge | near edge (full wick range) | +0.116R (30,878) | -0.050R (35,407) | -0.012R (-0.084 to +0.039) | +0.027R (+0.003 to +0.052) |
| 3 | Classic | near edge (full wick range) | +0.108R (81,821) | -0.063R (80,908) | -0.020R (-0.084 to +0.022) | +0.014R (-0.005 to +0.032) |
| 4 | Strong move | candle body | +0.064R (16,895) | -0.020R (21,143) | -0.034R (-0.105 to +0.022) | +0.044R (+0.012 to +0.075) |
| 5 | Break of structure | near edge (full wick range) | +0.098R (51,834) | -0.057R (44,751) | -0.030R (-0.094 to +0.011) | +0.020R (-0.001 to +0.040) |
| 6 | Break of structure + fair value gap | near edge (full wick range) | +0.096R (46,216) | -0.056R (39,445) | -0.031R (-0.095 to +0.010) | +0.021R (-0.001 to +0.041) |
| 7 | Volume surge | candle body | +0.078R (30,184) | -0.044R (35,022) | -0.019R (-0.088 to +0.031) | +0.019R (-0.004 to +0.043) |
| 8 | LuxAlgo style | 50% of the candle | +0.082R (73,153) | -0.056R (61,892) | +0.022R (-0.032 to +0.059) | -0.006R (-0.030 to +0.018) |
| 9 | Classic | candle body | +0.075R (79,816) | -0.050R (79,980) | -0.023R (-0.086 to +0.017) | +0.014R (-0.004 to +0.031) |
| 10 | LuxAlgo style | candle body | +0.104R (64,564) | -0.081R (50,653) | +0.006R (-0.062 to +0.050) | -0.018R (-0.047 to +0.011) |
| 11 | Break of structure | candle body | +0.065R (50,628) | -0.045R (44,222) | -0.033R (-0.097 to +0.007) | +0.019R (-0.000 to +0.038) |
| 12 | LuxAlgo style | near edge (full wick range) | +0.117R (55,660) | -0.098R (40,837) | -0.011R (-0.078 to +0.034) | -0.021R (-0.055 to +0.011) |
| 13 | Break of structure + fair value gap | candle body | +0.063R (45,148) | -0.046R (38,971) | -0.035R (-0.098 to +0.006) | +0.018R (-0.001 to +0.036) |
| 14 | Strong move | 50% of the candle | +0.018R (16,508) | -0.009R (20,911) | -0.042R (-0.097 to +0.007) | +0.041R (+0.013 to +0.071) |
| 15 | Volume surge | 50% of the candle | +0.040R (29,458) | -0.033R (34,723) | -0.020R (-0.075 to +0.021) | +0.017R (-0.004 to +0.042) |
| 16 | Classic | 50% of the candle | +0.037R (77,837) | -0.034R (79,164) | -0.023R (-0.074 to +0.009) | +0.016R (-0.001 to +0.032) |
| 17 | Break of structure | 50% of the candle | +0.027R (49,538) | -0.028R (43,801) | -0.033R (-0.087 to +0.002) | +0.021R (+0.002 to +0.044) |
| 18 | Break of structure + fair value gap | 50% of the candle | +0.028R (44,182) | -0.031R (38,600) | -0.032R (-0.085 to +0.004) | +0.019R (+0.000 to +0.039) |
| | Random zones | near edge (full wick range) | +0.127R (159,077) | -0.077R (144,542) | | |

## Detail for the best variation (daily bars)

| Slice | Bullish | Bearish |
|---|---|---|
| All trades | +0.102R ±0.073 · 35% win · 17,296 | -0.030R ±0.057 · 31% win · 21,406 |
| With your trend (uptrend for longs, downtrend for shorts) | +0.077R ±0.083 · 34% win · 6,120 | +0.032R ±0.100 · 33% win · 4,146 |
| No clear trend | +0.112R ±0.082 · 35% win · 6,232 | -0.043R ±0.069 · 31% win · 7,942 |
| Against the trend | +0.121R ±0.102 · 35% win · 4,944 | -0.046R ±0.057 · 31% win · 9,318 |
| First half (2016-10-03 to 2021-10-02) | +0.079R ±0.132 · 34% win · 7,679 | -0.027R ±0.089 · 31% win · 10,671 |
| Second half (2021-10-02 to 2026-10-02) | +0.121R ±0.075 · 35% win · 9,617 | -0.033R ±0.071 · 31% win · 10,735 |
| S&P 500 stocks only | +0.094R ±0.072 · 34% win · 8,810 | -0.041R ±0.060 · 31% win · 11,692 |
| Zone revisited within 21 bars | +0.114R ±0.082 · 35% win · 9,297 | -0.005R ±0.069 · 32% win · 11,096 |
| Zone revisited after 21 bars | +0.089R ±0.079 · 34% win · 7,999 | -0.057R ±0.068 · 30% win · 10,310 |
| Target 1R / 2R / 3R | +0.028 / +0.102 / +0.135 | -0.002 / -0.030 / -0.064 |
| Zone held (no close through it in 10 bars) | 42% held, 75% of zones revisited | 41% held, 88% of zones revisited |
| Weekly bars, same rules | +0.114R ±0.151 · 38% win · 3,572; edge -0.023R (-0.094 to +0.052) | -0.090R ±0.108 · 31% win · 4,225; edge +0.066R (-0.008 to +0.142) |

## Daily bars, bullish blocks, buy the first pullback into the zone

| Definition | Enter at near edge (full wick range) | Enter at candle body | Enter at 50% of the candle |
|---|---|---|---|
| Classic | +0.108R ±0.060 · 36% win · 81,821 | +0.075R ±0.053 · 34% win · 79,816 | +0.037R ±0.046 · 32% win · 77,837 |
| Strong move | +0.102R ±0.073 · 35% win · 17,296 | +0.064R ±0.067 · 33% win · 16,895 | +0.018R ±0.061 · 31% win · 16,508 |
| Break of structure | +0.098R ±0.058 · 35% win · 51,834 | +0.065R ±0.052 · 33% win · 50,628 | +0.027R ±0.047 · 31% win · 49,538 |
| Break of structure + fair value gap | +0.096R ±0.059 · 35% win · 46,216 | +0.063R ±0.053 · 33% win · 45,148 | +0.028R ±0.048 · 31% win · 44,182 |
| Volume surge | +0.116R ±0.060 · 36% win · 30,878 | +0.078R ±0.055 · 34% win · 30,184 | +0.040R ±0.050 · 32% win · 29,458 |
| LuxAlgo style | +0.117R ±0.063 · 39% win · 55,660 | +0.104R ±0.058 · 37% win · 64,564 | +0.082R ±0.053 · 34% win · 73,153 |
| Baseline | +0.127R ±0.084 · 36% win · 159,077 | +0.098R ±0.079 · 34% win · 154,995 | +0.060R ±0.066 · 32% win · 150,951 |

## Daily bars, bearish blocks, short the first rally into the zone

| Definition | Enter at near edge (full wick range) | Enter at candle body | Enter at 50% of the candle |
|---|---|---|---|
| Classic | -0.063R ±0.050 · 30% win · 80,908 | -0.050R ±0.042 · 30% win · 79,980 | -0.034R ±0.036 · 30% win · 79,164 |
| Strong move | -0.030R ±0.057 · 31% win · 21,406 | -0.020R ±0.047 · 31% win · 21,143 | -0.009R ±0.041 · 30% win · 20,911 |
| Break of structure | -0.057R ±0.052 · 31% win · 44,751 | -0.045R ±0.045 · 30% win · 44,222 | -0.028R ±0.041 · 30% win · 43,801 |
| Break of structure + fair value gap | -0.056R ±0.053 · 31% win · 39,445 | -0.046R ±0.045 · 30% win · 38,971 | -0.031R ±0.041 · 30% win · 38,600 |
| Volume surge | -0.050R ±0.050 · 31% win · 35,407 | -0.044R ±0.042 · 30% win · 35,022 | -0.033R ±0.038 · 30% win · 34,723 |
| LuxAlgo style | -0.098R ±0.063 · 32% win · 40,837 | -0.081R ±0.054 · 31% win · 50,653 | -0.056R ±0.042 · 31% win · 61,892 |
| Baseline | -0.077R ±0.051 · 30% win · 144,542 | -0.063R ±0.043 · 30% win · 142,694 | -0.050R ±0.037 · 30% win · 140,814 |

## Weekly bars, bullish blocks, buy the first pullback into the zone

| Definition | Enter at near edge (full wick range) | Enter at candle body | Enter at 50% of the candle |
|---|---|---|---|
| Classic | +0.152R ±0.119 · 39% win · 17,371 | +0.093R ±0.115 · 37% win · 16,621 | +0.022R ±0.110 · 34% win · 15,849 |
| Strong move | +0.114R ±0.151 · 38% win · 3,572 | +0.038R ±0.141 · 34% win · 3,404 | -0.016R ±0.144 · 32% win · 3,262 |
| Break of structure | +0.130R ±0.120 · 38% win · 11,673 | +0.072R ±0.117 · 36% win · 11,210 | +0.006R ±0.111 · 33% win · 10,792 |
| Break of structure + fair value gap | +0.145R ±0.123 · 39% win · 9,642 | +0.084R ±0.121 · 36% win · 9,260 | +0.012R ±0.115 · 33% win · 8,905 |
| Volume surge | +0.137R ±0.130 · 39% win · 5,523 | +0.100R ±0.125 · 37% win · 5,309 | +0.040R ±0.125 · 34% win · 5,084 |
| LuxAlgo style | +0.187R ±0.096 · 43% win · 12,693 | +0.163R ±0.096 · 41% win · 14,498 | +0.108R ±0.102 · 37% win · 15,969 |
| Baseline | +0.138R ±0.124 · 39% win · 30,979 | +0.088R ±0.122 · 37% win · 29,536 | +0.020R ±0.125 · 34% win · 28,106 |

## Weekly bars, bearish blocks, short the first rally into the zone

| Definition | Enter at near edge (full wick range) | Enter at candle body | Enter at 50% of the candle |
|---|---|---|---|
| Classic | -0.165R ±0.083 · 28% win · 16,413 | -0.147R ±0.069 · 28% win · 16,142 | -0.117R ±0.063 · 29% win · 15,825 |
| Strong move | -0.090R ±0.108 · 31% win · 4,225 | -0.112R ±0.087 · 30% win · 4,164 | -0.094R ±0.084 · 30% win · 4,061 |
| Break of structure | -0.174R ±0.104 · 28% win · 7,846 | -0.146R ±0.089 · 29% win · 7,719 | -0.121R ±0.080 · 29% win · 7,568 |
| Break of structure + fair value gap | -0.164R ±0.104 · 28% win · 6,592 | -0.148R ±0.088 · 28% win · 6,489 | -0.122R ±0.080 · 29% win · 6,356 |
| Volume surge | -0.136R ±0.094 · 29% win · 8,069 | -0.113R ±0.077 · 30% win · 7,948 | -0.094R ±0.069 · 30% win · 7,784 |
| LuxAlgo style | -0.219R ±0.082 · 30% win · 7,053 | -0.204R ±0.077 · 29% win · 9,441 | -0.164R ±0.069 · 29% win · 12,511 |
| Baseline | -0.155R ±0.089 · 29% win · 26,062 | -0.133R ±0.078 · 29% win · 25,524 | -0.119R ±0.066 · 29% win · 24,982 |

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
