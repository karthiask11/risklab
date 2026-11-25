"""Prices during market hours, every 15 minutes (run by .github/workflows/live.yml).

Writes out/live.json: {"t": time, "d": date, "n": count, "nifty": [price, change],
                       "p": {symbol: [price, change vs previous close]}}
The workflow pushes it to the "live" branch; the website reads it from there.
Yahoo Finance prices are about 15 minutes delayed. Risk and return still use daily closes.
"""
import datetime as dt
import json
import os
import sys

import pandas as pd
import yfinance as yf

IST = dt.timezone(dt.timedelta(hours=5, minutes=30))
BATCH = 250


def last_two(df, ticker):
    try:
        if isinstance(df.columns, pd.MultiIndex):
            lv0 = df.columns.get_level_values(0)
            s = df[ticker]["Close"] if ticker in lv0 else df["Close"][ticker]
        else:
            s = df["Close"]
        s = pd.to_numeric(s, errors="coerce").dropna()
        s = s[s > 0]
        return s if len(s) >= 2 else None
    except Exception:  # noqa: BLE001
        return None


def main():
    now = dt.datetime.now(IST)
    force = os.environ.get("FORCE") == "1"
    if not force and (now.weekday() >= 5 or not dt.time(9, 14) <= now.time() <= dt.time(15, 50)):
        print(f"Market closed at {now:%a %H:%M} IST; nothing to do")
        return
    today = now.date()
    with open("data/stocks.json", encoding="utf-8") as f:
        syms = [x["sym"] for x in json.load(f)["stocks"]]
    tickers = [s + ".NS" for s in syms] + ["^NSEI"]
    names = dict(zip(tickers, syms + ["^NSEI"]))
    prices, nifty = {}, None
    for i in range(0, len(tickers), BATCH):
        part = tickers[i:i + BATCH]
        try:
            df = yf.download(part, period="5d", interval="1d", auto_adjust=False,
                             group_by="ticker", threads=True, progress=False)
        except Exception as e:  # noqa: BLE001
            print(f"Batch {i}: {e}")
            continue
        for t in part:
            s = last_two(df, t)
            if s is None or s.index[-1].date() != today:
                continue  # no trade today (holiday, suspended or not yet traded)
            p, prev = float(s.iloc[-1]), float(s.iloc[-2])
            row = [round(p, 2), round(p / prev - 1, 4)]
            if t == "^NSEI":
                nifty = row
            else:
                prices[names[t]] = row
    print(f"{len(prices)} live prices at {now:%H:%M} IST")
    if len(prices) < 100 and not force:
        print("Too few prices for today (market holiday?); not publishing")
        sys.exit(0)
    os.makedirs("out", exist_ok=True)
    with open("out/live.json", "w", encoding="utf-8") as f:
        json.dump({"t": now.isoformat(timespec="minutes"), "d": today.isoformat(), "n": len(prices),
                   "nifty": nifty, "p": prices}, f, separators=(",", ":"))


if __name__ == "__main__":
    main()
