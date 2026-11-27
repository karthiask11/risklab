"""Company fundamentals (P/E, P/B, ROE, debt to equity, market cap, profit margin) from Yahoo Finance only.

Runs after update.py. Each run refreshes the oldest entries (Nifty 500 first), so the whole list
is renewed about once a week without slowing the daily update. Writes data/fund.json:
{"updated": time, "f": {symbol: [pe, pb, roe, debt_to_equity, market_cap_crore, profit_margin, eps, date, sector_pe]}}
"""
import datetime as dt
import json
import os
import time

import yfinance as yf

OUT = "data"
PER_RUN = int(os.environ.get("FUND_PER_RUN", "300"))


def num(x, d=4):
    try:
        x = float(x)
        return round(x, d) if x == x and abs(x) != float("inf") else None
    except (TypeError, ValueError):
        return None


def main():
    with open(os.path.join(OUT, "stocks.json"), encoding="utf-8") as f:
        stocks = json.load(f)["stocks"]
    path = os.path.join(OUT, "fund.json")
    old = {}
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            old = json.load(f).get("f", {})
    eq = [s for s in stocks if not s.get("k")]  # skip ETFs, REITs, InvITs
    # never-fetched first (Nifty 500 before others), then the oldest
    eq.sort(key=lambda s: (s["sym"] in old, old.get(s["sym"], [None] * 8)[7] or "", 0 if s.get("n5") else 1))
    today = dt.date.today().isoformat()
    done = fails = 0
    for s in eq[:PER_RUN]:
        sym = s["sym"]
        try:
            info = yf.Ticker(sym + ".NS").info or {}
            mc = num(info.get("marketCap"), 0)
            row = [num(info.get("trailingPE"), 2), num(info.get("priceToBook"), 2), num(info.get("returnOnEquity")),
                   num(info.get("debtToEquity"), 2), round(mc / 1e7) if mc else None, num(info.get("profitMargins")),
                   num(info.get("trailingEps"), 2), today]
            if any(v is not None for v in row[:7]):
                old[sym] = row
                done += 1
                fails = 0
            else:
                old.setdefault(sym, [None] * 7 + [today])
                fails += 1
        except Exception as e:  # noqa: BLE001
            fails += 1
            print(f"{sym}: {e}")
        if fails >= 25:
            print("Too many failures in a row (Yahoo may be limiting requests); stopping for today")
            break
        time.sleep(0.4)
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"updated": dt.datetime.now(dt.timezone.utc).isoformat(timespec="minutes"), "f": old},
                  f, separators=(",", ":"))
    print(f"Fundamentals: {done} refreshed, {len(old)} stored")


if __name__ == "__main__":
    main()
