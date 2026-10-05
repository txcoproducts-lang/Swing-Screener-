# Paper trading accounts

This branch holds the two paper trading accounts that `paper.py` (on `main`) trades every 30 minutes on market days:

- `paper/A.json`: *Your system* (the screener's setups and your option rules)
- `paper/B.json`: *Claude's picks* (the AI picks list, as shares)

Each file has the account's cash, open positions, closed trades, the daily log with the reason for every buy and sell, and the value at each close. Every trade, morning routine and daily close is its own commit; runs where only prices moved share one rolling "Prices updated" commit. The screener page reads these files to draw the paper trading tiles.
