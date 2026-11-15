"""Every label on the screener pages carries a specific date and time (the user's rule, 2026-11-15: nothing says just
"today", "tonight" or "now").

The pages are written with relative words in many places (keys, hints, table headers). stamp() runs over a finished
page and swaps those words, in the visible text only (not in scripts, styles or attributes), for the date and time
they mean: the close the page was built on, the open of that day, and the close before it. Text that the page's
scripts draw (pop-ups, paper tiles) is dated where it is written.
"""
import datetime as dt
import re
import zoneinfo

CT = zoneinfo.ZoneInfo("America/Chicago")


def md(d):
    """Fri Nov 13"""
    return f"{d:%a %b} {d.day}"


def labels(day, prev=None, close="3:00 PM CT", open_="8:30 AM CT", live=None):
    """The words a page's dates turn into. day / prev: the trading day the page is built on and the one before.
    live: a "2:15 PM CT" string when the page was built during the session (its prices are not closes)."""
    day = dt.date.fromisoformat(str(day)[:10])
    prev = dt.date.fromisoformat(str(prev)[:10]) if prev else day - dt.timedelta(days=3 if day.weekday() == 0 else 1)
    D = md(day)
    return dict(D=D, CLOSE=f"{D} {live} prices" if live else f"{D} close ({close})", OPEN=f"{D} open ({open_})",
                PREV=f"{md(prev)} close ({close})", DT=f"{D}, {live}" if live else f"{D}, {close} close")


def _swap(t, L):
    D, C, O, P = L["D"], L["CLOSE"], L["OPEN"], L["PREV"]
    for a, b in (("with yesterday's", f"with the {P} reading"), ("since yesterday", f"since the {P}"), ("than yesterday", f"than at the {P}"),
                 ("for tonight", f"for the {C}"), ("yesterday's close", f"the {P}"), ("yesterday's", f"the {P}'s"), ("yesterday", f"on the {P}"),
                 ("today's open", f"the {O}"), ("today's close", f"the {C}"), ("tonight's close", f"the {C}"),
                 ("so far today", f"as of the {C}"), ("before today", f"before {D}"), ("new today", f"new {D}"),
                 ("up than down today", f"up than down on {D}"), ("% today", f"% on {D}"),
                 ("Today's", f"{D}'s"), ("today's", f"{D}'s"), ("Tonight's", f"{D}'s"), ("tonight's", f"{D}'s"),
                 ("the Today tab", f"the {D} tab"), ("as on Today", f"as on the {D} tab"), ("Today checks", f"{D} checks"),
                 ("Tonight bar", f"{D} bar"), ("= tonight", f"= the {C}"), ("here tonight sits", f"here the {C} sits"),
                 ("back to tonight", f"back to the {C}"), ("right now", f"at the {C}"), ("this morning", f"on the {O}")):
        t = t.replace(a, b)
    if t.strip() == "Now":                 # a table header
        return t.replace("Now", f"{D} close")
    t = t.replace("Price then / Now", f"Price then / {D} close")
    t = re.sub(r"\b[Tt]onight\b", f"at the {C}", t)
    t = re.sub(r"\btoday\b", f"on {D}", t)
    t = re.sub(r"\bToday\b", D, t)
    t = re.sub(r"(\b(?:at|by|on) )?(?<![A-Za-z])now\b", lambda m: f"{m.group(1) or 'at '}the {C}", t)   # lower case only: ticker NOW stays
    return t.replace("at at the", "at the").replace("on at the", "at the")


def _js(h, L):
    """Exact phrases that the page's scripts and data write into the page."""
    D, C = L["D"], L["CLOSE"]
    for a, b in (("is that close tonight.", f"is that close at the {C}."), (" passes tonight. ", f" passes at the {C}. "),
                 (", in a trade now", f", in a trade at the {C}"), ("the market card above is tonight\\'s.", f"the market card above is the {C}."),
                 ("% today</b>", f"% on {D}</b>"), ("% today<\\/b>", f"% on {D}<\\/b>"),
                 ("None right now, all cash.", "None at its last update, all cash.")):
        h = h.replace(a, b)
    h = re.sub(r"today's (~?\d+ )?(largest coins|largest|list|index members|members)", r"the \1\2 on the test's run date", h)  # backtest notes
    return re.sub(r"Each of tonight's (\d+) liquid (stocks|coins)", lambda m: f"Each of the {m.group(1)} liquid {m.group(2)} at the {C}", h)


def stamp(html, L):
    """Swap the relative time words in a page's visible text for dates and times (scripts, styles and tags untouched,
    apart from a few exact phrases the scripts write)."""
    parts = re.split(r"(<script\b.*?</script>|<style\b.*?</style>|<[^>]+>)", _js(html, L), flags=re.S | re.I)
    return "".join(p if i % 2 else _swap(p, L) for i, p in enumerate(parts))


def stamp_obj(o, L):
    """The same for every string in a JSON-ready object (the ticker search's signals.json)."""
    if isinstance(o, str):
        return stamp(o, L)
    if isinstance(o, dict):
        return {k: stamp_obj(v, L) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [stamp_obj(v, L) for v in o]
    return o
