"""Company fundamentals (P/E, P/B, ROE, debt to equity, market cap, profit margin) from Yahoo Finance.

Runs after update.py. Each run refreshes the oldest entries (Nifty 500 first), so the whole list
is renewed about once a week without slowing the daily update. Writes data/fund.json:
{"updated": time, "f": {symbol: [pe, pb, roe, debt_to_equity, market_cap_crore, profit_margin, eps, date, sector_pe]}}
"""
import datetime as dt
import json
import os
import time

import requests
import yfinance as yf

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
           "Accept": "application/json,text/plain,*/*", "Referer": "https://www.nseindia.com/"}


def nse_session():
    s = requests.Session()
    s.headers.update(HEADERS)
    try:
        s.get("https://www.nseindia.com", timeout=20)
        s.get("https://www.nseindia.com/get-quotes/equity?symbol=TCS", timeout=20)
    except Exception:  # noqa: BLE001
        pass
    return s


def nse_row(s, sym, today):
    """P/E, sector P/E and market cap from NSE's quote page data (when Yahoo refuses)."""
    r = s.get("https://www.nseindia.com/api/quote-equity", params={"symbol": sym}, timeout=20)
    r.raise_for_status()
    j = r.json()
    md, si, pi = j.get("metadata", {}), j.get("securityInfo", {}), j.get("priceInfo", {})
    pe = num(md.get("pdSymbolPe"), 2)
    mc = None
    try:
        mc = round(float(si.get("issuedSize")) * float(pi.get("lastPrice")) / 1e7)
    except (TypeError, ValueError):
        pass
    return [pe if pe and pe > 0 else None, None, None, None, mc, None, None, today, num(md.get("pdSectorPe"), 2)]

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
    use_nse = False
    nse = None
    for s in eq[:PER_RUN]:
        sym = s["sym"]
        if use_nse:
            try:
                row = nse_row(nse, sym, today)
                if row[0] is not None or row[4] is not None:
                    prev = old.get(sym, [None] * 8)
                    old[sym] = [row[0], prev[1], prev[2], prev[3], row[4], prev[5], prev[6], today, row[8]]
                    done += 1
                    fails = 0
                else:
                    fails += 1
            except Exception as e:  # noqa: BLE001
                fails += 1
                print(f"NSE {sym}: {e}")
                if fails in (5, 15):
                    nse = nse_session()
            if fails >= 40:
                print("NSE quotes not reachable; stopping for today")
                break
            time.sleep(0.6)
            continue
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
        if fails >= 8 and not use_nse and done == 0:
            print("Yahoo refuses company data; switching to NSE quotes (P/E and market cap only)")
            use_nse, fails, nse = True, 0, nse_session()
            continue
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
