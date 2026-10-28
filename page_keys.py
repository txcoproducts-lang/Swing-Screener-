"""
"How to read this" keys for every section of the three pages (Stocks, Crypto and the OVTLYR page), asked for by the user
on 2026-10-28: a detailed key for everything inside each section, on how to read it and use it.

Each key is a closed <details> panel under the section's heading, so the pages stay clean until it's opened. The words
follow the live rules (CFG / OV from the screener that calls this), and the stock and crypto pages share the same text
with their own words swapped in (stock / coin, sector / category, SPY / BTC). Change a rule there and its key here.
"""

CSS = """details.hk{margin:2px 0 8px}details.hk>summary{display:inline-flex;align-items:center;gap:6px;cursor:pointer;list-style:none;
font-size:12px;font-weight:700;color:var(--acc);background:color-mix(in srgb,var(--acc) 8%,transparent);border-radius:999px;padding:3px 11px 3px 8px;user-select:none}
details.hk>summary::-webkit-details-marker{display:none}details.hk>summary::before{content:'i';display:inline-flex;align-items:center;justify-content:center;
width:15px;height:15px;border-radius:50%;background:var(--acc);color:#fff;font:italic 700 10px/1 Georgia,serif}
details.hk>summary::after{content:'▸';font-size:10px}details.hk[open]>summary::after{content:'▾'}
.hk-b{background:var(--card);border:1px solid var(--line);border-left:3px solid var(--acc);border-radius:10px;padding:10px 14px;margin-top:6px;
font-size:13px;line-height:1.5;color:var(--fg);font-weight:400;text-align:left;white-space:normal;max-width:980px}
.hk-h{font-size:11px;font-weight:800;letter-spacing:.05em;text-transform:uppercase;color:var(--mut);margin:10px 0 3px}.hk-h:first-child{margin-top:0}
.hk-r{display:grid;grid-template-columns:minmax(120px,190px) minmax(0,1fr);gap:2px 12px;padding:4px 0;border-top:1px solid var(--line)}
.hk-h+.hk-r,.hk-b>.hk-r:first-child{border-top:0}.hk-r>b{font-weight:700}.hk-r>span{color:var(--fg)}
.hk-s{display:inline-block;width:12px;height:12px;border-radius:3px;vertical-align:-1px;margin-right:5px;border:1px solid rgba(0,0,0,.08)}
.hk-l{display:inline-block;width:16px;height:0;border-top:3px solid;vertical-align:3px;margin-right:5px}.hk-l.d{border-top-style:dashed;border-top-width:2px}.hk-l.o{border-top-style:dotted}
.hk-u{background:color-mix(in srgb,var(--up) 9%,transparent);border-radius:8px;padding:8px 10px;margin-top:10px}.hk-u b:first-child{color:var(--up)}
.hk-n{color:var(--mut);font-size:12px;margin-top:8px}
@media(max-width:600px){.hk-r{grid-template-columns:minmax(0,1fr);gap:0}.hk-b{padding:9px 11px}}"""

RED, GREEN, YELLOW = "#f4a6a0", "#a8e0bf", "#f7dc7a"      # the user's three colours: overbought / good / oversold
UP, DN, WARN, ACC, MUT = "#12936b", "#d6453d", "#e0a020", "#2f6fed", "#8a94a3"


def sw(c):
    """A colour swatch."""
    return f'<i class="hk-s" style="background:{c}"></i>'


def ln(c, kind=""):
    """A line sample: solid, d = dashed, o = dotted."""
    return f'<i class="hk-l {kind}" style="border-color:{c}"></i>'


def H(t):
    return f'<div class="hk-h">{t}</div>'


def R(term, text):
    return f'<div class="hk-r"><b>{term}</b><span>{text}</span></div>'


def U(t):
    return f'<div class="hk-u"><b>How to use it:</b> {t}</div>'


def N(t):
    return f'<div class="hk-n">{t}</div>'


def key(*parts, title="How to read this"):
    return f'<details class="hk"><summary>{title}</summary><div class="hk-b">{"".join(parts)}</div></details>'


def words(market):
    """The words that differ between the stock and crypto pages."""
    if market == "crypto":
        return dict(crypto=True, u="coin", us="coins", U="Coin", Us="Coins", g="category", gs="categories", G="Category",
                    Gs="Categories", b="BTC", mk="crypto market", Mk="Crypto market", mem="coins in the scan",
                    etf="its equal-weight category index", liq="coins trading $10M+ a day",
                    cash="$1,000", year="365 days (coins trade every day)")
    return dict(crypto=False, u="stock", us="stocks", U="Stock", Us="Stocks", g="sector", gs="sectors", G="Sector",
                Gs="Sectors", b="SPY", mk="S&amp;P 500", Mk="S&amp;P 500", mem="S&amp;P 500 stocks",
                etf="its SPDR ETF", liq="S&amp;P 500 + Nasdaq 100 stocks over $10 averaging 1M+ shares a day",
                cash="$5,000", year="252 trading days")


def page_keys(market, cfg, ov):
    """Every key for the stock page (market="stock") or the crypto page (market="crypto"), by section."""
    w = words(market)
    c = w["crypto"]
    ob, os_, ma = cfg["OB_BREADTH"], cfg["OS_BREADTH"], cfg["LONG_MA_TYPE"]
    u, us, U_, Us, g, gs, G, Gs, b, mk, Mk = (w[k] for k in ("u", "us", "U", "Us", "g", "gs", "G", "Gs", "b", "mk", "Mk"))
    rising = (f"<b>Rising</b> = the share of {w['mem']} with the 10 EMA over the 20 EMA and the close over the 50 EMA "
              "(your rule). The page's main breadth number.")
    upswing = ("<b>Upswing</b> (▲) = Rising is above its own 10-day average, so more " + us + " are turning up each day; "
               "<b>fading</b> (▼) = below it.")
    uptrend = f"your uptrend: EMA10 over EMA20, the close over EMA50 and over the 150-day {'EMA' if ma == 'EMA' else 'average'}"
    out = {}

    # ---------------------------------------------------------------- Today
    out["today"] = key(
        H("The top line"),
        R(f"{sw(UP)}Strong / Mixed / {sw(DN)}Weak",
          f"The market badge. Six votes: more than half of the {us} over their 20-, 50- and 200-day averages (3 votes), more new "
          "52-week highs than lows, more volume in rising " + us + " than falling ones, more " + us + " up than down today. "
          "5-6 votes = Strong / risk-on (green), 3-4 = Mixed (grey), 0-2 = Weak / risk-off (red)."),
        R("Data as of", "Which close the page is built on. \"Prices at ... New York time\" means it was built during market "
          "hours, so prices are not closes yet." if not c else "Which daily close the page is built on (coins trade every day)."),
        R("Counts", "How many Super, Regular, Momentum and Pullback setups tonight, and how many were left out as overbought."),
        H(f"Step 1 · The market"),
        R("✓ / ✕ headline", f"\"{b} is moving up\" only when every check below passes. One ✕ and it says \"not moving up\"."),
        R("The checks", f"{b}'s 10 EMA over its 20 EMA · {b} closed over its 50 EMA · {b} over its 150-day "
          f"{'EMA' if ma == 'EMA' else 'average'} · more {w['mem'] if not c else 'coins'} turning up (Rising above its 10-day "
          f"average and not over {ob}) · market not overbought (Rising not over your {ob} line). The grey line under each is the "
          "actual numbers."),
        R("Small line", f"{b}'s last 30 closes: green when every check passes, red when one fails. Price and % today next to it."),
        H(f"Step 2 · Strongest {g}"),
        R(f"Strongest {g}", f"The {g} with the most {us} Rising that also has at least one {u} on the strongest list. If the "
          f"top {g} by Rising is skipped, the line under it says why (over {ob}, fading, or no {u} in your uptrend)."),
        R(f"{sw(UP)}{sw(DN)}{sw(WARN)} Bars", f"Bar length = Rising %. Green = upswing, red = fading, amber = over your {ob} "
          f"line (overbought). The small tick = its 10-day average; the faint mark = the {ob} line."),
        R("Pills", f"\"3 {us}\" = how many of its {us} are on the strongest list · \"Over {ob}\" = overbought, nothing bought · "
          f"\"Near {ob}\" = within 5 points of it with no {u} on the list · \"fading\" / \"none pass\" = no {u} qualifies."),
        H(f"Step 3 · Strongest {u}"),
        R("Score", f"The top {u} on the strongest {g}, strongest {u} list, out of 100: 40 points market + 40 points "
          f"{g} + 20 points {u}. More in the {Us} tab's \"Strongest {g}, strongest {u}\" key."),
        R(f"{sw('#a9bff5')}{sw(ACC)}{sw(UP)} Score bar", f"Light blue = the market's part, blue = the {g}'s part, green = the "
          f"{u}'s own part. A longer bar = a higher score."),
        R("Under the name", f"Its {g}, its setup (\"Super Momentum\", \"Regular Pullback\" or \"no setup\"), RSI, price and "
          "% today."),
        H("The cards below"),
        R(f"All {gs}, strongest first", f"Every {g} with the same bars and pills as Step 2. Tap one to open the {Us} tab "
          f"filtered to that {g}."),
        R(f"Strongest {us}", f"The top 10 of the strongest list, same bars as Step 3. \"All N ›\" opens the full list."),
        R("Top picks", "The first names on New uptrends, Breakout watch and AI picks. \"Open ›\" goes to the Top picks tab."),
        R("Paper trading", "Each paper account's value right now. Tap one for every trade."),
        R("OVTLYR plan", "Whether Plan M is on, which market checks fail, and whether Plan ETF is set up."),
        R("Blue tickers", "Any ticker with a dotted underline opens its chart (trend, order blocks and its 10-year backtest)."),
        U(f"Read it top to bottom, the way you pick: the market first, then the {g}, then the {u}. Only look for a buy when "
          f"Step 1 is all ✓. Then go to the Step 2 {g} and the Step 3 {u}, open its chart and check it's a Super setup in a "
          f"green, rising {g}. If Step 1 shows a ✕, wait: everything has to be working in your favor."))

    # ---------------------------------------------------------------- Market tab: the cards
    out["market"] = key(
        R("In uptrend", f"How many {us} pass {uptrend}, out of every liquid {u} ({w['liq']}). Green when more than half do."),
        R(f"{Mk} {'coins' if c else 'stocks'} rising", f"{rising} The state under it: ▲ upswing or ▼ fading and since when; "
          f"\"overbought\" when it's over {ob}, \"oversold\" under {os_}; plus its 10-day average. Green = upswing, red = fading, "
          f"black = overbought. The line = the last 60 days."),
        R("% above 20 / 50 / 200-day", f"The share of {us} closing over their 20-, 50- and 200-day simple averages. ▲ / ▼ = up or "
          "down vs 5 days ago. Green over 50%. 20-day = short term, 50-day = the swing, 200-day = the long trend."),
        R("Advance / Decline", f"How many {us} closed up vs down today. The line is the running total over 60 days: rising = more "
          f"{us} going up than down, day after day."),
        R("New 52w highs / lows", f"{Us} at a new 52-week closing high vs a new low today ({w['year']}). The line = highs minus "
          "lows over time."),
        R("Up / down volume", f"Volume in {us} that rose ÷ volume in {us} that fell. Over 1 = buyers are doing more of the trading."),
        R(f"{sw(UP)}{sw(DN)} Colours", "Green number = healthy reading, red = weak. Each small line = the last 60 days."),
        N(f"Rising counts {w['mem']} only{', so each sector matches its SPDR ETF' if not c else ''}; the other cards count the whole scan, so the numbers can differ a little."),
        U(f"A healthy market for your calls: most cards green and Rising on a ▲ upswing between {os_} and {ob}. Over {ob} is "
          f"overbought and your rule blocks buys. % above the 50-day and the A/D line turning down are early warnings."))

    # ---------------------------------------------------------------- VIX (stocks only)
    out["vix"] = "" if c else key(
        R("The number", "The VIX close: how much the S&amp;P 500 is expected to move over the next 30 days, from option prices. "
          "Low = calm, high = fear. It usually rises when stocks fall."),
        R(f"{sw(UP)}{sw(MUT)}{sw(WARN)}{sw(DN)} Zone badge", "Calm under 15 · Normal 15-20 · Nervous 20-30 · Fear 30 and up (common "
          "rules of thumb, not your rule)."),
        R("vs the day before", "Red when the VIX rose (more fear, bad for calls), green when it fell. Then the change vs 5 days ago."),
        R("Higher than X%", "Where tonight sits in the last year: higher than X% of the year's closes. Plus the year's range and average."),
        R("The chart", "The last year of VIX closes over the four zone bands; dashed lines at 15, 20 and 30; the dot on the right = "
          "tonight, in its zone's colour."),
        U("Calm and Normal suit buying calls: premiums are cheaper and trends tend to hold. Nervous and Fear mean bigger swings and "
          "pricier calls, and uptrends break more often. A VIX spike that turns back down often marks the end of a sell-off. "
          "Information only: no rule on the page or in the paper accounts uses it."))

    # ---------------------------------------------------------------- Breadth over time
    out["breadth"] = key(
        H("The heatmap"),
        R("Rows", f"{Mk} first, then each {g}, the most Rising tonight first. Each small cell is one {'day' if c else 'trading day'}, "
          "the last 3 months, newest on the right."),
        R(f"{sw(GREEN)} Green", f"{os_}-{ob}% Rising and rising that day (above its 10-day average): the good zone. Green only "
          "while it's rising."),
        R(f"{sw(YELLOW)} Yellow", f"Falling: {os_}-{ob}% but under its 10-day average (a downswing), or under {os_} (oversold, "
          "washed out)."),
        R(f"{sw(RED)} Red", f"Over {ob}: overbought. Your rule: no upswing then, and nothing in it gets bought."),
        R("Right column", f"Rising tonight and its state: ▲ upswing, ▼ fading, <b>OB</b> overbought (over {ob}), <b>OS</b> oversold "
          f"(under {os_})."),
        R("Tap or hover", "A cell shows that day's Rising, its 10-day average, the share in your full uptrend and the state. "
          "Tap a row's name to show it in the breadth line below."),
        H("The breadth line"),
        R(f"{ln('#14202e')}Rising", f"Day by day, for the {mk} or the {g} picked in the list."),
        R(f"{ln('#c96a12')}5-day average", "The fast average (exponential). Rising crossing it is the earliest turn."),
        R(f"{ln('#2a5bd7')}10-day average", "The slow average (exponential). Rising above it = an upswing, below it = fading, the "
          "same test the heatmap and the paper accounts use."),
        R(f"{ln(WARN, 'd')}Dashed lines", f"Your {ob} overbought and {os_} oversold lines."),
        R("Buttons", "3M / 6M / 1Y / All = how far back. The line above the chart says where Rising is against each average and since when."),
        U(f"The best time for your system is Rising crossing up through its 10-day average while it's between {os_} and {ob}: more "
          f"{us} turning up each day. Rising dropping under the 5-day line is the first warning, under the 10-day is fading. Over "
          f"{ob} is stretched: your rule buys nothing. Under {os_} is washed out: watch for the turn up."))

    # ---------------------------------------------------------------- Sectors tab
    out["tiles"] = key(
        R("Each tile", f"One {g}, the most Rising first. The big number = Rising %: its {us} with the 10 EMA over the 20 and the "
          "close over the 50 EMA."),
        R(f"{sw(GREEN)}{sw(YELLOW)}{sw(RED)} Tile colour", f"Green = rising (Rising above its 10-day average) · yellow = falling "
          f"(under its 10-day average) or oversold (under {os_}) · red = over {ob} (overbought)."),
        R("Badge", f"RISING = upswing (above its 10-day average) · FADING = below it · NEAR {ob} = within 5 points of overbought · "
          f"OVER {ob} = overbought, nothing bought."),
        R("Small line", "Rising over the last 5 days."),
        R("Under the name", (f"Its SPDR ETF and " if not c else "") + f"how many of its {us} are on the strongest list (\"none pass\" "
          "= none)."),
        R("Tap a tile", f"Opens the {Us} tab filtered to that {g}."),
        U(f"You want a green tile with a RISING badge and {us} on the list: that's a {g} turning up with room to run. NEAR {ob} is "
          f"getting stretched; FADING {gs} are skipped by your system."))
    out["sector_table"] = key(
        R(G, f"Click a row to filter the {u} list to that {g}. Click any header to sort."),
        R("In uptrend", f"{Us} passing {uptrend}, out of the liquid {us} in it, with the %. The bar is green from 50% up."),
        R("Rising (10 &gt; 20, &gt; 50)", f"Its Rising % ({w['mem']} only) with ▲ upswing / ▼ fading since a date, or OB / OS. "
          "Sorting it sorts by how far Rising is above its 10-day average."),
        R("Momentum / Pullback", "How many of each setup it has tonight."),
        R("% &gt; 20d / 50d / 200d", f"Share of its {us} over their 20-, 50- and 200-day simple averages. The ± after it = the "
          "change vs 5 days ago (green = improving)."),
        R("Adv / Dec", f"{Us} up vs down today."),
        R("52w Hi / Lo", f"{Us} at a new 52-week high vs a new low."),
        U(f"Look for {gs} where In uptrend and Rising are both high and the ± numbers are green: breadth getting better, not worse."))
    out["sector_charts"] = key(
        R("Each chart", (f"The {g}'s SPDR ETF (SPY for the S&amp;P 500)" if not c else
                         "Bitcoin for the market; each category is an equal-weight index of its coins")
          + ": green / red candles, volume at the bottom. Top right = the last price and its change over the last bar."),
        R("Lines", f"{ln('#e8a33d')}EMA 10 {ln(ACC)}EMA 20 {ln('#a259d9')}EMA 50."),
        R("Daily / Weekly / Monthly", "About 6 months, 2 years or 10 years of bars."),
        R("The strip under it", f"{ln('#14202e')}Rising {ln('#14202e', 'o')}share in your full uptrend. "
          f"Shading: {sw(UP)}upswing, {sw(DN)}fading, {sw(WARN)}overbought (Rising over {ob}). Faint lines at {ob} and {os_}. "
          "Daily and weekly only: the prices behind it go back 2 years."),
        R("Hover / tap", "The line above the strip shows that bar's numbers."),
        R("Ticker next to the name", "Opens its full chart."),
        U(f"The {g} you buy from should have its price over the 10, 20 and 50 EMAs, stacked 10 over 20 over 50, with green shading "
          "in the strip. Amber shading = stretched: wait for it to cool."))

    # ---------------------------------------------------------------- strongest sector, strongest stock
    out["strongest"] = key(
        H("The score (100 at most)"),
        R("Market (40)", f"40% of the {mk}'s Rising. The same for every {u} tonight."),
        R(f"{G} (40)", f"40% of its {g}'s Rising."),
        R(f"{U_} (20)", f"20% of its relative-strength rank inside its {g}: the strongest {u} in its {g} gets 20."),
        H(f"The {g} table"),
        R("Rising / 10-day avg", f"The {g}'s Rising % and its 10-day average."),
        R("State", f"▲ upswing since a date, ▼ fading, or OB (over {ob})."),
        R(f"Strongest {us}", f"Its top 3 on the list by RS, or why none: over the {ob} line, fading, all overbought, or no {u} in "
          "your uptrend."),
        H("The list"),
        R("#, Score", "Rank and total score, highest first."),
        R(f"RS rank in {g}", f"\"3 of 60\" = third strongest of the 60 liquid {us} in its {g}."),
        R("RS", "Relative strength, IBD-style: a weighted return with 40% on the last 3 months and 20% each on 6, 9 and 12 months."),
        R("Setup", f"Super or Regular, Momentum or Pullback (green = Momentum); \"no setup\" = strong but not at an entry yet."),
        R("Close / 1M", "Last price and the change over a month."),
        R("Who gets on it", f"A {u} in your uptrend, or with a Regular setup (EMA10 over EMA20 and the close over EMA50, under the "
          f"150 line), in a {g} on an upswing that isn't over {ob}, and not overbought itself."),
        U(f"This is the list Your system and Your system, after 2 PM buy from: Super setups first, then Regular, highest score "
          f"first. Strong {us} with \"no setup\" are your watch list for the next entry."))

    # ---------------------------------------------------------------- the stock table
    opt = "" if c else (
        H("Option columns (top " + str(cfg["OPT_TOP_N"]) + " by score)")
        + R("Contract", f"The call nearest {cfg['TARGET_DELTA']} delta, {cfg['DTE_MIN']}-{cfg['DTE_MAX']} days out (about "
            f"{cfg['TARGET_DTE']}), open interest {cfg['MIN_OI']}+ and a spread under {cfg['MAX_SPREAD_PCT']:.0f}%: expiry, days "
            "left, strike. This table's helper; the Top picks tab uses your own rules (15-30 days, 0.50-0.80 delta, OI over 500).")
        + R("Δ Γ Θ/day Vega", "Delta (how much the call moves per $1 in the stock), gamma (how fast delta changes), theta (value "
            "lost per day), vega (change per 1 point of IV). Black-Scholes from Yahoo's IV.")
        + R("IV / Bid/Ask / OI", "Implied volatility, the quote (\"last\" = no live quote, after hours) and open interest. "
            "Confirm in your broker: Yahoo's numbers can be off."))
    out["stock_table"] = key(
        H("Buttons"),
        R("Setups / Super / Regular", f"Setups (the default) = every {u} with a setup. Super = also over the 150 line; Regular = not."),
        R("Momentum / Pullback", "Only that kind of setup."),
        R("Overbought", f"{Us} that would have a setup but sit in a {g} (or market) over your {ob} breadth line."),
        R("All uptrend", f"Every {u} in {uptrend}."),
        H("Setups"),
        R("Momentum", f"EMA10 over EMA20, the close over EMA50, RSI 55-80, not more than 3 ATR over the EMA20, and a close over "
          f"the last 20 days' high or within 3% of the 52-week high."),
        R("Pullback", "The close over EMA50, EMA20 over EMA50, RSI 50 or under, 3%+ off the 15-day high and back near or under the "
          "EMA20 (the EMA10 may dip under the 20)."),
        R(f"{sw('color-mix(in srgb,#12936b 25%,transparent)')}Super / {sw('color-mix(in srgb,#6b7686 20%,transparent)')}Regular",
          f"Super = the price is also over the 150-day {'EMA' if ma == 'EMA' else 'average'}; Regular = it isn't. Super are listed first."),
        R(f"{sw('color-mix(in srgb,#e0a020 30%,transparent)')}Overbought", "Left out by your breadth rule, with why under it."),
        H("Columns"),
        R("Ticker", f"Tap for its chart. The {g} is under it. {sw(UP)}A green left edge = full stack: EMA10 over 20 over 50 over "
          f"the 150 over the 200."),
        R("Score", "Trend structure (70%) plus setup quality (up to 30 points). Higher = a cleaner trend and a better setup."),
        R("10y rules vs hold", f"The last 10 years of this {u} traded on your rules, minus just holding it, in percentage points "
          "(green = your rules won). The small line = both returns. Tap the ticker for every trade."),
        R("Close / Open / 1D 5D 1M %", "Last price, today's open, and the change over 1 day, 5 days and a month."),
        R("RSI", f"14-day RSI. <b>OB</b> = over {cfg['OB_RSI']}, <b>OS</b> = under {cfg['OS_RSI']}. Information only since Oct 15."),
        R("CCI", f"20-day CCI. OB over {cfg['OB_CCI']}, OS under {cfg['OS_CCI']}. Information only."),
        R("ATR %", "The average daily range (14 days) as % of the price: how much it swings in a normal day."),
        R("RelVol", "Today's volume ÷ the 20-day average. Over 1.2 = heavier than usual."),
        R("From 52w hi", "How far under its 52-week high."),
        R("vs EMA10 / 20 / 50", "How far the price is above (+) or below (−) each average."),
        R("&gt;150 / &gt;200", f"✓ = over the 150- / 200-day {'EMA' if ma == 'EMA' else 'average'}."),
        R("50x150", "\"new (3d ago)\" = the EMA50 crossed over the 150 line in the last 10 days; \"above\" = it's been over longer."),
        opt,
        U(f"Start with Super, sorted by Score. Prefer Momentum with RelVol over 1.2 and a 10y number in green; for a Pullback, "
          f"check the price is holding near the EMA20. Then open the chart: green trend shading, no orange order block just above."))

    # ---------------------------------------------------------------- the chart pop-up
    out["chart"] = key(
        R("Trend / Indicators", "Trend = this page's own chart. Indicators = TradingView's chart with RSI, MACD and Bollinger Bands "
          "(swap studies from its Indicators menu)."),
        R("4H / Daily / Weekly / Monthly", "Bar size. 1Y / 5Y = how far back on the daily chart."),
        R(f"{sw(UP)}{sw(DN)} Shading and arrows", f"Green = {uptrend}. Red = all three reversed (downtrend). Arrows mark where each "
          "trend starts."),
        R("Lines", f"{ln('#e8a33d')}EMA 10 {ln(ACC)}EMA 20 {ln('#a259d9')}EMA 50 {ln(MUT, 'd')}150 line. Volume at the bottom."),
        R(f"{sw('#2962ff')}{sw('#f57c00')} Order blocks", "Daily chart. Blue = bullish block (support): the last down candle "
          "before a rise of 2+ ATR. Orange = bearish (resistance). Bright boxes are still untouched; a box ends where the price "
          "first came back. The line above names the nearest untouched support and resistance and how far away. In a 10-year "
          "test they did no better than random price zones as support."),
        R("Info line", f"Its {g}'s rank by Rising, Rising % and state; the market line with {b}'s price and % today, how many "
          "of the Today checks pass and the market's breadth."),
        R("Backtest line", f"10 years on your rules vs holding it vs holding {b}, what $1,000 became, and every trade (tap to open)."),
        U("Before you buy: green shading, the price over the EMAs, room up to the nearest orange block, and a 10-year line that "
          "shows your rules work on this name."), title="How to read this chart")

    # ---------------------------------------------------------------- Top picks
    opt_cols = (H("Volume columns (all three lists)") + R("Volume / 5-day volume", "Dollars traded on the last day, and the "
                "total over the last 5 days. Coins have no option columns.")) if c else (
        H("Volume and option columns (all three lists)")
        + R("Volume / 5-day volume", "Shares traded on the last day, and the total over the last 5 days.")
        + R("Call 15-30d", f"The call nearest {sum(cfg['PK_DELTA']) / 2:.2f} delta among contracts {cfg['PK_DTE'][0]}-"
            f"{cfg['PK_DTE'][1]} days out, delta {cfg['PK_DELTA'][0]:.2f}-{cfg['PK_DELTA'][1]:.2f}, open interest over "
            f"{cfg['PK_OI_OVER']} (your rules): expiry, strike and days left. Hover for how many fit.")
        + R("Δ / Premium / OI", "Its delta, price (the bid/ask middle, or the last trade after hours) and open interest.")
        + R(f"<span style='color:{MUT}'>Grey</span> / <span style='color:{DN}'>red</span>", "Grey = no call fits all three rules, "
            "so the closest one is shown; the rule it misses is in red. \"none fits\" / \"n/a\" = nothing to show.")
        + R(f"<span style='color:{DN}'>E</span> / Earnings", "E = earnings come before the call expires. The Earnings column turns "
            "red within a week."))
    out["picks"] = key(
        R("The three buttons", "Switch lists. The number on each = how many names it has tonight."),
        H("New uptrends"),
        R("Who", f"{Us} that turned into {uptrend} on the last close after missing it the day before. Strongest RS first."),
        R("Out (days)", "How long it had been out of an uptrend."),
        R("RS / From 52w hi / Vol vs avg", "Relative strength 1-99 (99 = strongest), distance under the 52-week high, and that "
          "day's volume ÷ the 20-day average."),
        H("Breakout watch"),
        R("Who", f"{Us} in an uptrend within 5% of a 50-day high set at least 5 days ago (a base). Tightest first."),
        R("Breakout level / Below it", "The 50-day high, and how far under it the close is. A breakout is a close over it."),
        R("Base / 10-day range / Vol 10d/50d", "Days since the high; the last 10 days' high-to-low range (smaller = tighter); "
          "recent volume ÷ the 50-day (under 1 = drying up, which is good before a breakout)."),
        H("AI picks"),
        R("Who", f"Claude's list: up to {cfg['AI_N']} {us} with the best relative strength, at most {cfg['AI_CAP']} per {g}. A pick "
          f"stays while it ranks in the top {cfg['AI_KEEP']}. Claude's picks paper account trades it."),
        R("Rank / Picked / Price then / Now", "Today's RS rank, the day it was added, the close that day and now."),
        R("Since picked / SPY since" if not c else "Since picked / BTC since",
          f"Its return since the pick vs {b} over the same days (\"new today\" = just added)."),
        R("Why / Dropped / Track record", "Why it's on the list, which picks left today and why, and the list's average "
          f"return vs {b} since it started."),
        R("Left out as overbought", f"Under each list: names your rule skipped because their {g}'s breadth is over {ob}."),
        opt_cols,
        U(f"New uptrends is a place to look, not a buy signal (no edge in the backtest). Breakout watch breaks out more often "
          "than average, but its gains weren't better. AI picks beat the average stock in the test, not by a proven margin, with "
          + ("long stretches behind. Before buying a call, check the E flag and the Earnings column." if not c else
             "long stretches behind; none of these lists were tested on coins.")))

    # ---------------------------------------------------------------- OVTLYR plan (inside the stock / crypto page)
    etfs = "BTC or ETH on their own signals" if c else "TQQQ on QQQ's signals or SPXL on SPY's"
    out["ovtlyr"] = key(
        R("Plan / Screener", "Two views of OVTLYR's plan. Plan = tonight's decision; Screener = every " + u + " against the rules."),
        R("Stand-ins", "OVTLYR's heatmap and signals are private, so: heat = 14-day RSI; buy signal = the 10 EMA crossing over the "
          f"20 (it counts for {ov['SIGNAL_DAYS']} days); sell signal = the 10 under the 20; breadth = the share of {us} with the 10 "
          "EMA over the 20, against its 10-day average."),
        H("Plan view"),
        R("Market box", f"{b} heat under {ov['HEAT_MAX']} and rising · {b} buy signal · {b} uptrend (10/20/50) · breadth rising · "
          f"not overbought (your {ob} rule). ✓ = passes. All must pass for \"Plan M is on\"."),
        R(f"{Gs} box", f"Each {g}: breadth vs its 10-day average, average RSI and the first rule it misses. A {g} passes with breadth "
          f"over its average and heat above {b}'s, under {ov['HEAT_MAX']} and rising" + ("" if c else "; Health Care is always out")
          + f"; your rule also drops any {g} over {ob}."),
        R("Plan ETF box", f"For spare cash: {etfs}, with each check and any sell signal in red. Neither set up = cash waits in "
          "SGOV (Plan #SICADFU)."),
        R(f"Plan M {us}", f"Tap to open every {u} that passes tonight. New = first night on it; \"since\" = the day it joined. "
          "Buy signal = the day of the cross; RSI with yesterday's; vs 10 EMA; ATR (the normal daily range); Order block above = "
          f"the nearest untouched one and its distance{'' if c else '; Earnings'}; RS 1-99. Dropped = left the list, with the first "
          "rule it failed. The line under the table counts how many fell out at each rule."),
        H("Screener view"),
        R("Ready / 2 rules away / All", f"Filters: {us} passing every rule, within 2, or all. The menu narrows to one {g}."),
        R(f"{sw(GREEN)}{sw(YELLOW)}{sw(RED)} Heat", f"14-day RSI: green = 30-70 and rising, yellow = falling or under 30, "
          "red = 70+ (overbought)."),
        R("Signal", "Days since the 10 EMA crossed over the 20 (— = no cross)."),
        R("✓ ✗ ·", "Each rule column: passes, fails, not checked. Hover a column for the rule. On a phone the dots sit under the "
          "ticker in the same order."),
        R(f"{sw('#e5f6ef')}Ready / {sw('#fff4de')}N away", "Passes everything, or how many rules it misses (listed under Missing)."),
        U("Plan M only trades when the Market box says on: then take Ready names, freshest signal first. When it's off, see "
          "whether Plan ETF is set up; if not, cash sits in SGOV. The OVTLYR switch at the top of the page shows the deck's "
          "rules alone, without your overbought rule."))

    # ---------------------------------------------------------------- Paper trading
    out["paper"] = key(
        H("Each tile"),
        R("Name and time", "The account, and when it last updated (New York time)."),
        R("Big number", f"What the account is worth now (started at {w['cash']})."),
        R(f"{sw(UP)}{sw(DN)} Change", f"Dollars and % since the start (green up, red down), and {b} over the same days to compare."),
        R("Line", "The account's value since the start; the flat line is the starting cash."),
        R("Footer", "Open positions and closed trades. Tap the tile for the full breakdown."),
        H("The breakdown"),
        R("Value / Return / Cash / Closed trades", f"Worth now, % vs {b}, cash not invested, and wins vs losses."),
        R(f"{ln(ACC)}{ln(MUT)}{ln(MUT, 'd')} Chart", f"The account vs the same money put in {b}, and the starting line. \"Show these "
          "numbers as a table\" lists every close."),
        R("Open positions", "What it holds, what it paid, its value now, the Plan (stop and exits) and why it was bought."),
        R("Closed trades / Daily log", "Every finished trade (tap for both reasons) and every decision, newest first."),
        R("How this account trades", "Its full rules, written out."),
        H("The four accounts"),
        R("Your system", "Your setups on the strongest list at about 10:00 AM New York time; 2 positions, each 30% of the account "
          "at most" + ("; a call by your rules when one fits, else shares" if not c else "; coins (no options)")
          + ". Sells when a 4-hour bar closes with EMA10 under EMA20 and the price under EMA50" + (", -50% on a call, 5 days "
          "before expiry, or an 8% drop on shares." if not c else ", or on an 8% drop.")),
        R("Your system, after 2 PM", "The same rules, buying only after 2:00 PM Central."),
        R("Claude's picks", f"Copies the AI picks list, about a tenth of the account each; sells on your 4-hour exit or when a pick "
          "leaves the list."),
        R("OVTLYR plan", "Trades the OVTLYR plan section: Plan M, then Plan ETF, else SGOV."),
        U(f"Compare each account with {b} and with each other: that's the trial's question. Open the breakdown to see why each "
          "trade happened, so you can judge the rule, not just the result."))

    # ---------------------------------------------------------------- Backtests
    out["backtests"] = key(
        H("The summary strip"),
        R("Backtests on this page", "How many plans and research tests are below."),
        R(f"Plans that beat {b}", f"How many of the four plans ended ahead of holding {b} over 10 years."),
        R("Paper trial / Leading the trial", "Which day of the live paper trial it is, and the account ahead right now."),
        H("Plans side by side"),
        R("Paper trial / 10-year backtest", f"Switch between the live trial and the 10-year test. "
          f"{ln('#2f6fed')}Your system {ln('#12936b')}after 2 PM {ln('#d6453d')}Claude's picks {ln('#8e44c9')}OVTLYR "
          f"{ln(MUT, 'd')}{b}. The flat dashed line = the starting cash."),
        R("Log scale", "The 10-year chart uses equal spacing for equal % moves, so early years aren't squashed. Hover or tap for the values."),
        H("Each plan's card"),
        R(f"Beat / Trailed {b}", f"Whether its 10-year test ended ahead of {b}."),
        R("Two charts", "Left: its 10-year backtest. Right: its paper trial so far."),
        R("Worst drop / In the market", f"The biggest fall from a high (and {b}'s), and how much of the time it held something."),
        R("With calls (modeled)", "The same plan with calls priced by a model: a rough guide, since there's no free option history."),
        R("Full backtest", "Its rules, year by year vs " + b + " (green = it won that year), trades, win rate and average trade."),
        H("Research"),
        R("Each row", "A test behind one of the page's lists or signals: what was tested, on what, and the verdict. Tap to read "
          f"it and see its chart: {sw(ACC)}the idea tested, {sw(MUT)}what it's measured against, {sw('#c27a00')}a loss."),
        U("The backtests tell you which plan has an edge over just holding the market, and how deep its bad stretches get. "
          "A plan that trails " + b + " for 10 years needs a reason to keep using it. Past results don't promise future ones."))

    # ---------------------------------------------------------------- News
    out["news"] = key(
        R("Market", f"The {'crypto market' if c else 'whole market'}'s news feed, from TradingView's free widget."),
        R(f"{G} buttons", (f"News on that sector's SPDR ETF" if not c else "News on that category's strongest coins")
          + f", strongest {g} first; the % = its Rising."),
        R(f"{Us} row", f"After you pick a {g}, its strongest {us} on the list show up: tap one for news on just that {u}."),
        U(f"Check the news on your Step 3 {u} and its {g} before buying: an earnings date, a downgrade or a big headline can "
          "break a clean setup."))
    return out


# ---------------------------------------------------------------- the OVTLYR page (ovtlyr/)
def ovtlyr_keys(heat_max=70):
    """Keys for the OVTLYR page's tabs (ovtlyr_page.py): the deck's rules alone, no rule of the user's own."""
    out = {}
    out["today"] = key(
        R("Three plan boxes", "Which of OVTLYR's plans runs tonight. The one outlined in green is on. Plan M = buy stocks that "
          "pass every rule; Plan ETF = spare cash in TQQQ or SPXL; Plan #SICADFU = cash in SGOV when nothing else is set up."),
        R("Market · Sector · Stock", "The deck's order and weights: the market is 40% of a move, the sector 30%, the stock 30%. "
          "✓ = that layer passes. \"Open ›\" goes to its tab."),
        R(f"{sw(RED)}{sw(GREEN)}{sw(YELLOW)} Plan M list", f"Stocks passing every rule, freshest buy signal first. The coloured "
          f"number = heat (14-day RSI): green = 30-{heat_max} and rising, yellow = falling or under 30, red = {heat_max}+."),
        R("Stand-ins", "OVTLYR's heatmap and signals are private, so: heat = 14-day RSI; buy signal = the 10 EMA crossing over "
          "the 20; sell signal = under it; breadth = share of stocks with the 10 EMA over the 20."),
        U("Follow the deck top down: if the market fails, Plan M is off whatever the stocks look like. Then sectors, then the "
          "Ready stocks. This page has none of your own rules (no 75 breadth line): it's OVTLYR's plan alone."))
    out["market"] = key(
        R("✓ / ✗ on each card", "Whether that market check passes. All four must pass for Plan M."),
        R("SPY heat", f"SPY's 14-day RSI and yesterday's. Passes when under {heat_max} and rising. The chart = 3 months, with the "
          f"{heat_max} line dashed."),
        R("SPY buy signal", "Passes when SPY's 10 EMA is over its 20 EMA."),
        R("SPY bullish trend", "Passes when the 10 EMA is over the 20 and the price is over the 50 EMA."),
        R(f"{ln('#14202e')}{ln('#e8890c')}{ln('#2f6fed')} Breadth", "The share of S&amp;P 500 + Nasdaq 100 stocks with the 10 EMA "
          "over the 20 (black), its 5-day (orange) and 10-day (blue) averages. Passes when breadth is above its 10-day average."),
        U("When a card turns ✗, stop new Plan M buys and look at Plan ETF or SGOV. Breadth crossing back over the blue line is "
          "usually the first card to turn green again."))
    out["sectors"] = key(
        R(f"{sw(GREEN)}{sw(YELLOW)}{sw(RED)} Tile colour", f"The sector's heat (average RSI of its stocks): green = 30-{heat_max} "
          f"and rising since yesterday, yellow = falling or under 30 (oversold), red = {heat_max}+ (overbought). The heat badge in "
          "the table uses the same colours."),
        R("Pill", "passes = all four sector rules pass · fails = one or more fail · excluded = Health Care, always out in the deck."),
        R(f"{ln('#14202e')}{ln('#e8890c')}{ln('#2f6fed')} Lines", "Breadth (share of its stocks with the 10 EMA over the 20) and "
          "its 5-day and 10-day averages, 3 months. The line under the chart says whether breadth is over or under each."),
        H("The table (the four rules)"),
        R("Breadth over its 10-day avg", "✓ when breadth is above its 10-day average (a bullish cross)."),
        R("Relative greed &gt; 1", "The sector's heat ÷ SPY's heat. Over 1 = greedier than the market."),
        R("Heat under 70 / Heat rising", f"✓ when its heat is under {heat_max}, and when it's higher than yesterday."),
        R("Ready", "How many of its stocks pass every Plan M rule."),
        U("Plan M only buys in sectors that pass all four. A sector with breadth crossing up and heat in the green, rising, is "
          "where the next setups usually come from."))
    out["heat"] = key(
        R("Rows", "One block per sector, passing sectors first, its heat on the left. Each tile = a stock, hottest first."),
        R(f"{sw(GREEN)}{sw(YELLOW)}{sw(RED)} Colour", f"Heat (14-day RSI): green = 30-{heat_max} and rising, yellow = falling "
          f"or under 30 (oversold), red = {heat_max}+ (overbought). The sector's badge on the left works the same way."),
        R("▲ / ▼", "Heat rising or falling since yesterday. Plan M wants it rising."),
        R("Outlined tile", "Passes every Plan M rule (Ready)."),
        R("Buttons", "All stocks · Ready only · Heat rising. Tap a stock to open its chart on TradingView."),
        U("Look for outlined green tiles (rising) in a passing sector: warming up but not yet hot. Red tiles are stretched; the deck's "
          "heat targets sell into them."))
    out["stocks"] = key(
        R("Ready / 1 rule away / 2 rules away / All", "Filters by how many rules a stock misses. The menu narrows to one sector."),
        R(f"{sw(GREEN)}{sw(YELLOW)}{sw(RED)} Heat", f"14-day RSI: green = 30-{heat_max} and rising, yellow = falling or under 30, "
          f"red = {heat_max}+."),
        R("Signal", "Days since the 10 EMA crossed over the 20 (\"today\" = this close; — = none). Counts for 5 trading days."),
        R("Rule columns ✓ ✗ ·", "Buy signal · Uptrend (10/20/50) · Over 10 EMA · Heat rising · $10-$350 · Sector passes · "
          "Clear of order blocks (more than 2% away) · No earnings within 4 days. · = not checked. Hover a header for the rule."),
        R("ATR", "The average daily range (14 days)."),
        R("½ ATR stop / 2 ATR exit", "The deck's stop loss (a close half an ATR under today's price) and emergency exit (2 ATR under)."),
        R("Shares per $10k", "The deck's size: account × 5% ÷ (2 × ATR), for a $10,000 account. For calls, shares ÷ 80."),
        R("Heat target", "Where the deck takes profit: heat under 50 → 63; 50-75 → 10 points higher; 75+ → 5 points higher."),
        R("Earnings / last column", "Next earnings date; Ready, or the first rules it misses."),
        U("Buy only Ready stocks while Plan M is on. Size with Shares per $10k scaled to your account, set the ½ ATR stop, and "
          "watch for the heat target. \"1 rule away\" is tomorrow's watch list."))
    out["etf"] = key(
        R("TQQQ / SPXL", "The 3x funds, judged on QQQ's and SPY's own charts. The pill says set up or not."),
        R("Value zone bar", "Green band = the 20 EMA up to 2 ATR above it; the black mark = the last close. The deck buys only "
          "inside the zone."),
        R("✓ ✗ checks", f"Heat under {heat_max}, a buy signal, the uptrend, in the value zone, no order block 30+ days old within 2%."),
        R(f"<span style='color:{DN}'>Sell signal</span>", "Any exit firing now, in red."),
        R("Exit signals card", "What ends a Plan ETF trade, then where the cash goes (SGOV)."),
        U("Plan ETF is for cash with no Plan M setups. When neither fund is set up, the deck parks cash in SGOV."))
    out["rules"] = key(
        R("✓ / ·", "✓ = this page checks the rule from public data. · (grey) = OVTLYR-only data, can't be checked here."),
        R("Market · Sector · Stock", "The entry rules, in the deck's order and weights (40 / 30 / 30)."),
        R("Plan M exits", "Listed for reference: this page doesn't track trades. The OVTLYR plan paper account on the Stocks page "
          "trades them."),
        U("Use this tab to see exactly what \"passes\" means anywhere else on the page."))
    return out


