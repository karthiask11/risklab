"""Daily price updater for Portfolio Risk Lab.

Runs on GitHub Actions every weekday evening:
  1. gets the Nifty 500 stock list from NSE (falls back to the last saved list, then a built-in Nifty 100 list)
  2. downloads up to 10 years of daily closing prices from Yahoo Finance (split/bonus adjusted, not dividend adjusted)
  2b. replaces the latest day with NSE's official closing price from the NSE bhavcopy (if NSE can be reached)
  3. writes data/stocks.json (the list), data/<SYMBOL>.json (prices) and data/meta.json (update time)
Extra stocks: add lines "SYMBOL,Company name" to stocks.txt in the repository.
"""
import datetime as dt
import io
import json
import os
import re
import sys
import time
import zipfile

import pandas as pd
import requests
import yfinance as yf

OUT = "data"
PERIOD = "10y"
BATCH = 40
EQUITY_URL = "https://nsearchives.nseindia.com/content/equities/EQUITY_L.csv"  # every stock listed on NSE
N500 = set()  # Nifty 500 symbols, marked "n5" in stocks.json
LIST_URLS = [
    "https://nsearchives.nseindia.com/content/indices/ind_nifty500list.csv",
    "https://www.niftyindices.com/IndexConstituent/ind_nifty500list.csv",
]
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept": "text/csv,text/plain,*/*",
    "Referer": "https://www.nseindia.com/",
}
FALLBACK = [
    ("RELIANCE", "Reliance Industries"),
    ("BHARTIARTL", "Bharti Airtel"),
    ("HDFCBANK", "HDFC Bank"),
    ("ICICIBANK", "ICICI Bank"),
    ("SBIN", "State Bank of India"),
    ("TCS", "Tata Consultancy Services"),
    ("BAJFINANCE", "Bajaj Finance"),
    ("LT", "Larsen & Toubro"),
    ("KOTAKBANK", "Kotak Mahindra Bank"),
    ("HINDUNILVR", "Hindustan Unilever"),
    ("INFY", "Infosys"),
    ("SUNPHARMA", "Sun Pharmaceutical"),
    ("MARUTI", "Maruti Suzuki India"),
    ("ADANIPORTS", "Adani Ports & SEZ"),
    ("AXISBANK", "Axis Bank"),
    ("TITAN", "Titan Company"),
    ("ADANIPOWER", "Adani Power"),
    ("ULTRACEMCO", "UltraTech Cement"),
    ("ITC", "ITC"),
    ("HCLTECH", "HCL Technologies"),
    ("ADANIENT", "Adani Enterprises"),
    ("ETERNAL", "Eternal (Zomato)"),
    ("JSWSTEEL", "JSW Steel"),
    ("HAL", "Hindustan Aeronautics"),
    ("NTPC", "NTPC"),
    ("BAJAJFINSV", "Bajaj Finserv"),
    ("DIVISLAB", "Divi's Laboratories"),
    ("BAJAJ-AUTO", "Bajaj Auto"),
    ("BEL", "Bharat Electronics"),
    ("ONGC", "Oil & Natural Gas Corp"),
    ("NESTLEIND", "Nestle India"),
    ("ASIANPAINT", "Asian Paints"),
    ("POWERGRID", "Power Grid Corp"),
    ("COALINDIA", "Coal India"),
    ("SHRIRAMFIN", "Shriram Finance"),
    ("ADANIGREEN", "Adani Green Energy"),
    ("DMART", "Avenue Supermarts"),
    ("EICHERMOT", "Eicher Motors"),
    ("HINDZINC", "Hindustan Zinc"),
    ("TVSMOTOR", "TVS Motor Company"),
    ("INDIGO", "InterGlobe Aviation"),
    ("GRASIM", "Grasim Industries"),
    ("IOC", "Indian Oil Corp"),
    ("TATASTEEL", "Tata Steel"),
    ("HINDALCO", "Hindalco Industries"),
    ("DLF", "DLF"),
    ("WIPRO", "Wipro"),
    ("SBILIFE", "SBI Life Insurance"),
    ("TORNTPHARM", "Torrent Pharmaceuticals"),
    ("ADANIENSOL", "Adani Energy Solutions"),
    ("TECHM", "Tech Mahindra"),
    ("HYUNDAI", "Hyundai Motor India"),
    ("MOTHERSON", "Samvardhana Motherson Intl"),
    ("PNB", "Punjab National Bank"),
    ("TRENT", "Trent"),
    ("SOLARINDS", "Solar Industries India"),
    ("TMCV", "Tata Motors (Commercial Vehicles)"),
    ("PIDILITIND", "Pidilite Industries"),
    ("UNIONBANK", "Union Bank of India"),
    ("CHOLAFIN", "Cholamandalam Inv & Fin"),
    ("JIOFIN", "Jio Financial Services"),
    ("ABB", "ABB India"),
    ("TATACAP", "Tata Capital"),
    ("VBL", "Varun Beverages"),
    ("BOSCHLTD", "Bosch"),
    ("BANKBARODA", "Bank of Baroda"),
    ("APOLLOHOSP", "Apollo Hospitals"),
    ("BPCL", "Bharat Petroleum Corp"),
    ("INDHOTEL", "Indian Hotels Co"),
    ("BAJAJHLDNG", "Bajaj Holdings & Investment"),
    ("SIEMENS", "Siemens"),
    ("LTM", "LTM (LTIMindtree)"),
    ("HDFCLIFE", "HDFC Life Insurance"),
    ("CGPOWER", "CG Power & Industrial Solutions"),
    ("GAIL", "GAIL (India)"),
    ("CANBK", "Canara Bank"),
    ("LODHA", "Lodha Developers"),
    ("ZYDUSLIFE", "Zydus Lifesciences"),
    ("BRITANNIA", "Britannia Industries"),
    ("DRREDDY", "Dr. Reddy's Laboratories"),
    ("HDFCAMC", "HDFC AMC"),
    ("JINDALSTEL", "Jindal Steel"),
    ("CUMMINSIND", "Cummins India"),
    ("CIPLA", "Cipla"),
    ("TATACONSUM", "Tata Consumer Products"),
    ("PFC", "Power Finance Corp"),
    ("IRFC", "Indian Railway Finance Corp"),
    ("TATAPOWER", "Tata Power"),
    ("UNITDSPR", "United Spirits"),
    ("MAXHEALTH", "Max Healthcare"),
    ("ENRIN", "Siemens Energy India"),
    ("MUTHOOTFIN", "Muthoot Finance"),
    ("AMBUJACEM", "Ambuja Cements"),
    ("TMPV", "Tata Motors Passenger Vehicles"),
    ("GODREJCP", "Godrej Consumer Products"),
    ("VEDL", "Vedanta"),
    ("SHREECEM", "Shree Cement"),
    ("RECLTD", "REC"),
    ("MAZDOCK", "Mazagon Dock Shipbuilders")
]


def file_name(sym):
    return re.sub(r"[^A-Za-z0-9-]", "_", sym)


def stock_list():
    """Return a list of (symbol, name, industry)."""
    for url in LIST_URLS:
        try:
            r = requests.get(url, headers=HEADERS, timeout=30)
            r.raise_for_status()
            df = pd.read_csv(io.StringIO(r.text))
            df.columns = [c.strip() for c in df.columns]
            rows = [(str(s).strip(), str(n).strip(), str(i).strip())
                    for s, n, i in zip(df["Symbol"], df["Company Name"], df["Industry"])]
            if len(rows) >= 100:
                print(f"Nifty 500 list: {len(rows)} stocks from {url}")
                N500.update(s for s, _, _ in rows)
                return rows
        except Exception as e:  # noqa: BLE001
            print(f"Could not read {url}: {e}")
    path = os.path.join(OUT, "stocks.json")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            old = json.load(f)["stocks"]
        print(f"Using the saved list of {len(old)} stocks")
        N500.update(s["sym"] for s in old if s.get("n5"))
        return [(s["sym"], s["name"], s.get("ind", "")) for s in old]
    print("Using the built-in Nifty 100 list")
    N500.update(s for s, _ in FALLBACK)
    return [(s, n, "") for s, n in FALLBACK]


def all_equities():
    """Every equity listed on NSE (series EQ and BE) from NSE's EQUITY_L file. Returns [] if NSE can't be reached."""
    try:
        s = requests.Session()
        s.headers.update(HEADERS)
        try:
            s.get("https://www.nseindia.com", timeout=20)
        except Exception:  # noqa: BLE001
            pass
        r = s.get(EQUITY_URL, timeout=30)
        r.raise_for_status()
        df = pd.read_csv(io.StringIO(r.text))
        df.columns = [c.strip() for c in df.columns]
        df = df[df["SERIES"].astype(str).str.strip().isin(["EQ", "BE"])]
        rows = [(str(s).strip(), str(n).strip(), "") for s, n in zip(df["SYMBOL"], df["NAME OF COMPANY"])]
        print(f"All NSE equities: {len(rows)} stocks")
        return rows
    except Exception as e:  # noqa: BLE001
        print(f"Could not read the full NSE list: {e}")
        return []


def nse_closes():
    """Official closing prices from NSE's daily bhavcopy (end-of-day price file).
    Tries today and the previous days until a file is found.
    Returns (date "YYYY-MM-DD", {symbol: close}) or (None, {}) if NSE cannot be reached."""
    s = requests.Session()
    s.headers.update(HEADERS)
    try:
        s.get("https://www.nseindia.com", timeout=20)  # NSE sets cookies on its home page
    except Exception:  # noqa: BLE001
        pass
    today = (dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=5, minutes=30)).date()
    for back in range(0, 8):
        d = today - dt.timedelta(days=back)
        if d.weekday() >= 5:
            continue
        # 1) new-format bhavcopy (zip)
        url = f"https://nsearchives.nseindia.com/content/cm/BhavCopy_NSE_CM_0_0_0_{d:%Y%m%d}_F_0000.csv.zip"
        try:
            r = s.get(url, timeout=30)
            if r.ok and r.content[:2] == b"PK":
                with zipfile.ZipFile(io.BytesIO(r.content)) as z:
                    df = pd.read_csv(z.open(z.namelist()[0]))
                df.columns = [c.strip() for c in df.columns]
                df = df[df["SctySrs"].astype(str).str.strip().isin(["EQ", "BE", "BZ"])]
                out = {str(k).strip(): float(v) for k, v in zip(df["TckrSymb"], df["ClsPric"]) if float(v) > 0}
                if len(out) > 500:
                    print(f"NSE bhavcopy {d}: {len(out)} closing prices")
                    return d.isoformat(), out
        except Exception as e:  # noqa: BLE001
            print(f"NSE zip {d}: {e}")
        # 2) full bhavcopy (csv)
        url = f"https://nsearchives.nseindia.com/products/content/sec_bhavdata_full_{d:%d%m%Y}.csv"
        try:
            r = s.get(url, timeout=30)
            if r.ok and r.text.lstrip().upper().startswith("SYMBOL"):
                df = pd.read_csv(io.StringIO(r.text))
                df.columns = [c.strip() for c in df.columns]
                df = df[df["SERIES"].astype(str).str.strip().isin(["EQ", "BE", "BZ"])]
                out = {str(k).strip(): float(v) for k, v in zip(df["SYMBOL"], df["CLOSE_PRICE"]) if float(v) > 0}
                if len(out) > 500:
                    print(f"NSE full bhavcopy {d}: {len(out)} closing prices")
                    return d.isoformat(), out
        except Exception as e:  # noqa: BLE001
            print(f"NSE csv {d}: {e}")
    print("NSE bhavcopy not reachable; using Yahoo prices only")
    return None, {}


def with_nse(sym, dates, vals, nse_date, nse):
    """Put NSE's official close on the latest day (replace the same day, or add a newer day)."""
    if not nse_date or sym not in nse:
        return dates, vals, False
    dates, vals = list(dates), list(vals)
    if dates and dates[-1] == nse_date:
        vals[-1] = round(nse[sym], 2)
    elif not dates or dates[-1] < nse_date:
        dates.append(nse_date)
        vals.append(round(nse[sym], 2))
    else:
        return dates, vals, False
    return dates, vals, True


def extra_stocks():
    rows = []
    if os.path.exists("stocks.txt"):
        with open("stocks.txt", encoding="utf-8") as f:
            for line in f:
                parts = [p.strip() for p in line.split(",")]
                if parts and parts[0] and not parts[0].startswith("#"):
                    rows.append((parts[0].upper(), parts[1] if len(parts) > 1 else parts[0], ""))
    return rows


def closes(df, ticker):
    """Pull one ticker's Close column out of a yfinance download."""
    try:
        if isinstance(df.columns, pd.MultiIndex):
            lv0 = df.columns.get_level_values(0)
            s = df[ticker]["Close"] if ticker in lv0 else df["Close"][ticker]
        else:
            s = df["Close"]
        s = pd.to_numeric(s, errors="coerce").dropna()
        return s[s > 0]
    except Exception:  # noqa: BLE001
        return None


def download(tickers):
    for attempt in range(3):
        try:
            return yf.download(tickers, period=PERIOD, interval="1d", auto_adjust=False,
                               group_by="ticker", threads=True, progress=False)
        except Exception as e:  # noqa: BLE001
            print(f"Download failed (try {attempt + 1}): {e}")
            time.sleep(10 * (attempt + 1))
    return None


def main():
    os.makedirs(OUT, exist_ok=True)
    seen, stocks = set(), []
    for sym, name, ind in stock_list() + extra_stocks() + all_equities():
        if sym not in seen:
            seen.add(sym)
            stocks.append((sym, name, ind))

    global MKT
    nse_date, nse = nse_closes()
    nifty = None
    df = download(["^NSEI"])
    s = None if df is None else closes(df, "^NSEI")
    if s is not None and len(s) > 30:
        MKT = s
        nd = [d.strftime("%Y-%m-%d") for d in s.index]
        nv = [round(float(v), 2) for v in s.values]
        with open(os.path.join(OUT, "_NIFTY50.json"), "w", encoding="utf-8") as f:
            json.dump({"s": "NIFTY 50", "d": nd, "c": nv}, f, separators=(",", ":"))
        nifty = {"last": nv[-1], "date": nd[-1], "m": metrics(nd, nv)}
        print(f"Nifty 50: {len(nv)} days")
    else:
        print("Nifty 50 download failed; beta will be blank")
    saved, failed, from_nse = [], [], 0
    for i in range(0, len(stocks), BATCH):
        part = stocks[i:i + BATCH]
        tickers = [s + ".NS" for s, _, _ in part]
        df = download(tickers)
        for (sym, name, ind), t in zip(part, tickers):
            s = None if df is None else closes(df, t)
            path = os.path.join(OUT, file_name(sym) + ".json")
            if s is None or len(s) < 30:
                failed.append(sym)
                if os.path.exists(path):  # keep yesterday's file
                    with open(path, encoding="utf-8") as f:
                        old = json.load(f)
                    if old.get("d"):
                        d2, v2, used = with_nse(sym, old["d"], old["c"], nse_date, nse)
                        from_nse += used
                        if used:
                            with open(path, "w", encoding="utf-8") as f:
                                json.dump({"s": sym, "d": d2, "c": v2}, f, separators=(",", ":"))
                        saved.append(entry(sym, name, ind, d2, v2))
                continue
            dates = [d.strftime("%Y-%m-%d") for d in s.index]
            vals = [round(float(v), 2) for v in s.values]
            dates, vals, used = with_nse(sym, dates, vals, nse_date, nse)
            from_nse += used
            with open(path, "w", encoding="utf-8") as f:
                json.dump({"s": sym, "d": dates, "c": vals}, f, separators=(",", ":"))
            saved.append(entry(sym, name, ind, dates, vals))
        print(f"{min(i + BATCH, len(stocks))}/{len(stocks)} done")
        time.sleep(3)

    if not saved:
        print("No prices downloaded; keeping existing data.")
        sys.exit(1)
    saved.sort(key=lambda x: x["name"].lower())
    with open(os.path.join(OUT, "stocks.json"), "w", encoding="utf-8") as f:
        json.dump({"stocks": saved}, f, separators=(",", ":"))
    with open(os.path.join(OUT, "meta.json"), "w", encoding="utf-8") as f:
        json.dump({"updated": dt.datetime.now(dt.timezone.utc).isoformat(timespec="minutes"),
                   "count": len(saved), "failed": failed, "nse_date": nse_date, "nse_count": from_nse,
                   "nifty": nifty,
                   "source": (f"Latest close: NSE bhavcopy {nse_date}. " if nse_date else "")
                             + "History: Yahoo Finance daily closes, split and bonus adjusted"}, f)
    print(f"Saved {len(saved)} stocks ({from_nse} with NSE's official close). Failed: {len(failed)} {failed[:20]}")


MKT = None  # Nifty 50 daily closes (pandas Series), set in main()


def metrics(dates, vals):
    """Annual return, annual risk, price return, CAGR and beta vs Nifty 50 for 1, 3, 5 and 10 years.
    Same formulas as the website: daily returns, mean x 252, sample SD x sqrt(252),
    beta = covariance(stock, Nifty 50) / variance(Nifty 50) on the same days."""
    s = pd.Series(vals, index=pd.to_datetime(dates))
    end, out = s.index[-1], {}
    for y in (1, 3, 5, 10):
        start = end - pd.DateOffset(years=y)
        p = s[s.index >= start]
        if len(p) < 30 or (p.index[0] - start).days > 15:
            continue
        r = p.pct_change().dropna()
        days = (p.index[-1] - p.index[0]).days
        growth = p.iloc[-1] / p.iloc[0]
        beta = None
        if MKT is not None:
            both = pd.concat([p, MKT[MKT.index >= p.index[0]]], axis=1, join="inner").pct_change().dropna()
            if len(both) > 20 and both.iloc[:, 1].var() > 0:
                beta = round(float(both.iloc[:, 0].cov(both.iloc[:, 1]) / both.iloc[:, 1].var()), 3)
        out[str(y)] = [round(float(r.mean() * 252), 4), round(float(r.std(ddof=1) * 252 ** 0.5), 4),
                       round(float(growth - 1), 4), round(float(growth ** (365.25 / days) - 1), 4), beta]
    return out


def entry(sym, name, ind, dates, vals):
    prev = vals[-2] if len(vals) > 1 else vals[-1]
    return {"sym": sym, "name": name, "ind": ind, "file": file_name(sym),
            "last": vals[-1], "date": dates[-1], "chg": round(vals[-1] / prev - 1, 4),
            "from": dates[0], "m": metrics(dates, vals), **({"n5": 1} if sym in N500 else {})}


if __name__ == "__main__":
    main()
