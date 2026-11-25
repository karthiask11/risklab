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
ETF_URL = "https://nsearchives.nseindia.com/content/equities/eq_etfseclist.csv"  # every ETF listed on NSE
# REITs and InvITs trade in series RR and IV. Used if NSE's list can't be read.
TRUSTS = [
    ("EMBASSY", "Embassy Office Parks REIT", "REIT"),
    ("MINDSPACE", "Mindspace Business Parks REIT", "REIT"),
    ("BIRET", "Brookfield India Real Estate Trust", "REIT"),
    ("NXST", "Nexus Select Trust (REIT)", "REIT"),
    ("PGINVIT", "POWERGRID Infrastructure Investment Trust", "InvIT"),
    ("IRBINVIT", "IRB InvIT Fund", "InvIT"),
    ("INDIGRID", "IndiGrid Infrastructure Trust", "InvIT"),
]
KIND = {}  # symbol -> "ETF" / "REIT" / "InvIT"
JUMP = 0.6  # a one-day fall below 60% (or rise above 1/0.6) of the day before is treated as a corporate action
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
        ser = df["SERIES"].astype(str).str.strip()
        rows = [(str(s).strip(), str(n).strip(), "") for s, n in zip(df[ser.isin(["EQ", "BE"])]["SYMBOL"],
                                                                     df[ser.isin(["EQ", "BE"])]["NAME OF COMPANY"])]
        print(f"All NSE equities: {len(rows)} stocks")
        for code, kind in (("RR", "REIT"), ("IV", "InvIT")):
            part = df[ser == code]
            for sym, name in zip(part["SYMBOL"], part["NAME OF COMPANY"]):
                KIND[str(sym).strip()] = kind
                rows.append((str(sym).strip(), str(name).strip(), kind))
        return rows
    except Exception as e:  # noqa: BLE001
        print(f"Could not read the full NSE list: {e}")
        return []


def etfs_and_trusts():
    """Every ETF on NSE, plus REITs and InvITs (from the built-in list; NSE's equity list adds the rest)."""
    rows = []
    for sym, name, kind in TRUSTS:
        KIND[sym] = kind
        rows.append((sym, name, kind))
    try:
        s = requests.Session()
        s.headers.update(HEADERS)
        try:
            s.get("https://www.nseindia.com", timeout=20)
        except Exception:  # noqa: BLE001
            pass
        r = s.get(ETF_URL, timeout=30)
        r.raise_for_status()
        df = pd.read_csv(io.StringIO(r.text))
        df.columns = [c.strip() for c in df.columns]
        sc = next(c for c in df.columns if c.lower() == "symbol")
        nc = next((c for c in df.columns if c.lower().replace(" ", "") in ("securityname", "nameofsecurity")), sc)
        uc = next((c for c in df.columns if c.lower() == "underlying"), None)
        for i, row in df.iterrows():
            sym = str(row[sc]).strip()
            if not sym or sym == "nan":
                continue
            KIND[sym] = "ETF"
            name = str(row[nc]).strip()
            if uc and str(row[uc]).strip() not in ("", "nan"):
                name = f"{name} ({str(row[uc]).strip()})"
            rows.append((sym, name, "ETF"))
        print(f"NSE ETFs: {len(df)}")
    except Exception as e:  # noqa: BLE001
        print(f"Could not read the NSE ETF list: {e}")
    return rows


def drop_holidays(dates, vals):
    """Yahoo sometimes adds a row on an NSE holiday (e.g. 15 Jan 2026) that just repeats the day before.
    Drop a row when Nifty 50 has no price that day and the close is unchanged."""
    if MKT is None or len(dates) < 2:
        return dates, vals
    open_days = {d.strftime("%Y-%m-%d") for d in MKT.index}
    first = min(open_days)
    keep = [i for i in range(len(dates))
            if i == 0 or dates[i] in open_days or dates[i] < first or vals[i] != vals[i - 1]]
    return [dates[i] for i in keep], [vals[i] for i in keep]


def fix_jumps(dates, vals, dv=None):
    """Yahoo does not adjust old prices for demergers (e.g. Tata Motors -> TMPV on 14 Oct 2025)
    and has a few bad prints. NSE price bands make a real one-day move of 40%+ very rare, so when the
    price falls below 60% (or rises above 1/0.6) of the day before, the older prices are scaled so that
    day's return is zero. Returns (new values, [[date, factor], ...])."""
    vals, adj = list(vals), []
    for i in range(len(vals) - 1, 0, -1):
        ratio = vals[i] / vals[i - 1]
        if ratio < JUMP or ratio > 1 / JUMP:
            for j in range(i):
                vals[j] = vals[j] * ratio
            if dv:
                dv = [[d, round(a * ratio, 4) if d < dates[i] else a] for d, a in dv]
            adj.append([dates[i], round(ratio, 4)])
    if adj:
        vals = [round(v, 2 if v >= 1 else 4) for v in vals]
    return vals, adj[::-1], dv or []


def file_date(df, col, default):
    """The trading date written inside a bhavcopy file (NSE returns the previous file on holidays)."""
    try:
        return pd.to_datetime(str(df[col].dropna().iloc[0]).strip(), dayfirst=col == "DATE1").date()
    except Exception:  # noqa: BLE001
        return default


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
                fd = file_date(df, "TradDt", d)
                if fd != d:  # market holiday: NSE serves the last trading day's file
                    print(f"NSE file for {d} is dated {fd}; skipping")
                    continue
                df = df[df["SctySrs"].astype(str).str.strip().isin(["EQ", "BE", "BZ", "RR", "IV"])]
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
                fd = file_date(df, "DATE1", d)
                if fd != d:
                    print(f"NSE full file for {d} is dated {fd}; skipping")
                    continue
                df = df[df["SERIES"].astype(str).str.strip().isin(["EQ", "BE", "BZ", "RR", "IV"])]
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


def column(df, ticker, name):
    try:
        if isinstance(df.columns, pd.MultiIndex):
            lv0 = df.columns.get_level_values(0)
            s = df[ticker][name] if ticker in lv0 else df[name][ticker]
        else:
            s = df[name]
        return pd.to_numeric(s, errors="coerce")
    except Exception:  # noqa: BLE001
        return None


def closes(df, ticker):
    """Pull one ticker's Close column out of a yfinance download."""
    s = column(df, ticker, "Close")
    if s is None:
        return None
    s = s.dropna()
    return s[s > 0]


def dividends(df, ticker):
    """Cash dividends per share on their ex-date: [[date, amount], ...] (split adjusted like Close)."""
    s = column(df, ticker, "Dividends")
    if s is None:
        return []
    s = s.dropna()
    return [[d.strftime("%Y-%m-%d"), round(float(v), 4)] for d, v in s[s > 0].items()]


def traded_value(df, ticker):
    """Average daily traded value over the last 3 months, in Rs crore (liquidity)."""
    c, v = column(df, ticker, "Close"), column(df, ticker, "Volume")
    if c is None or v is None:
        return None
    tv = (c * v).dropna().tail(63)
    return round(float(tv.mean()) / 1e7, 2) if len(tv) > 10 else None


def total_return(dates, vals, dv):
    """Price series with dividends reinvested, scaled so the last value equals the last price."""
    if not dv:
        return list(vals)
    pos = {d: i for i, d in enumerate(dates)}
    add = [0.0] * len(vals)
    for d, a in dv:
        j = pos.get(d)
        if j is None:  # ex-date on a day without a price: use the next trading day
            j = next((k for k, x in enumerate(dates) if x > d), None)
        if j is not None and j > 0:
            add[j] += a
    tr = [1.0]
    for i in range(1, len(vals)):
        tr.append(tr[-1] * (vals[i] + add[i]) / vals[i - 1])
    k = vals[-1] / tr[-1]
    return [x * k for x in tr]


def tri_from_etf(nd, nv, ed, ev):
    """Nifty 50 TRI estimate: daily moves of the Nifty 50 price index (accurate volatility and beta)
    plus each calendar year's dividend gap, measured as NIFTYBEES's yearly return minus the index's
    (kept between 0% and 3%). The ETF price alone is noisier, so it is used only for the yearly gap."""
    def year_end(d, v):
        out = {}
        for x, y in zip(d, v):
            out[x[:4]] = y
        return out
    pe, ee = year_end(nd, nv), year_end(ed, ev)
    years = sorted(set(pe) & set(ee))
    gap, prev = {}, None
    for y in years:
        if prev and prev in pe and prev in ee:
            gap[y] = min(0.03, max(0.0, (ee[y] / ee[prev]) - (pe[y] / pe[prev])))
        prev = y
    last_full = [y for y in sorted(gap) if y < nd[-1][:4]]
    default = gap[last_full[-1]] if last_full else 0.012
    if nd[-1][:4] in gap and len([d for d in nd if d[:4] == nd[-1][:4]]) < 200:
        gap[nd[-1][:4]] = default
    count = {}
    for d in nd:
        count[d[:4]] = count.get(d[:4], 0) + 1
    start = max(nd[0], ed[0])
    td, tv, level = [], [], None
    for i, d in enumerate(nd):
        if d < start:
            continue
        if level is None:
            level = nv[i]
        else:
            g = gap.get(d[:4], default)
            level *= (nv[i] / nv[i - 1]) * (1 + g) ** (1 / max(200, count[d[:4]]))
        td.append(d)
        tv.append(round(level, 2))
    return td, tv


def nifty_tri(price_dates, price_vals):
    """Nifty 50 Total Return Index from niftyindices.com, filled to the latest day with price-index moves."""
    try:
        s = requests.Session()
        s.headers.update({**HEADERS, "Content-Type": "application/json; charset=UTF-8", "Accept": "application/json",
                          "Origin": "https://www.niftyindices.com", "Referer": "https://www.niftyindices.com/reports/historical-data"})
        start = dt.date.fromisoformat(price_dates[0])
        end = dt.date.fromisoformat(price_dates[-1])
        out = {}
        a = start
        while a <= end:
            b = min(end, a + dt.timedelta(days=360))
            cinfo = "{'name':'NIFTY 50','startDate':'%s','endDate':'%s','indexName':'NIFTY 50'}" % (a.strftime("%d-%b-%Y"), b.strftime("%d-%b-%Y"))
            r = s.post("https://www.niftyindices.com/Backpage.aspx/getTotalReturnIndexString", json={"cinfo": cinfo}, timeout=40)
            r.raise_for_status()
            rows = json.loads(r.json()["d"])
            for row in rows:
                dk = next(k for k in row if "date" in k.lower())
                vk = next(k for k in row if "total" in k.lower())
                out[pd.to_datetime(row[dk], dayfirst=True).strftime("%Y-%m-%d")] = float(str(row[vk]).replace(",", ""))
            a = b + dt.timedelta(days=1)
            time.sleep(1)
        if len(out) < 200:
            raise ValueError(f"only {len(out)} rows")
        pv = dict(zip(price_dates, price_vals))
        d = [x for x in price_dates if x >= min(out)]
        v, last = [], None
        for x in d:
            if x in out:
                last = out[x]
            elif last is not None and x in pv:  # TRI not published yet: move with the price index
                prev = d[d.index(x) - 1]
                last = last * pv[x] / pv[prev]
            v.append(round(last, 2) if last else None)
        keep = [(x, y) for x, y in zip(d, v) if y]
        print(f"Nifty 50 TRI: {len(out)} days from niftyindices")
        return [x for x, _ in keep], [y for _, y in keep]
    except Exception as e:  # noqa: BLE001
        print(f"Nifty 50 TRI not available ({e}); using the price index")
        return None, None


def download(tickers):
    for attempt in range(3):
        try:
            return yf.download(tickers, period=PERIOD, interval="1d", auto_adjust=False, actions=True,
                               group_by="ticker", threads=True, progress=False)
        except Exception as e:  # noqa: BLE001
            print(f"Download failed (try {attempt + 1}): {e}")
            time.sleep(10 * (attempt + 1))
    return None


def main():
    os.makedirs(OUT, exist_ok=True)
    seen, stocks = set(), []
    for sym, name, ind in stock_list() + extra_stocks() + all_equities() + etfs_and_trusts():
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
        nifty = {"last": nv[-1], "date": nd[-1], "m": metrics(nd, nv), "m30": metrics(*cut30(nd, nv))}
        print(f"Nifty 50: {len(nv)} days")
        td, tv = nifty_tri(nd, nv)
        src = "niftyindices.com"
        if not td:  # NIFTYBEES reinvests dividends, so its price tracks the Nifty 50 Total Return Index
            try:
                e = download(["NIFTYBEES.NS"])
                es = closes(e, "NIFTYBEES.NS") if e is not None else None
                if es is not None and len(es) > 500:
                    ed = [d.strftime("%Y-%m-%d") for d in es.index]
                    ev = [float(v) for v in es.values]
                    ed, ev = drop_holidays(ed, ev)
                    ev, _, _ = fix_jumps(ed, ev)
                    td, tv = tri_from_etf(nd, nv, ed, ev)
                    src = "Nifty 50 price index + yearly dividend gap from NIFTYBEES"
                    print(f"Nifty 50 TRI from NIFTYBEES: {len(td)} days")
            except Exception as ex:  # noqa: BLE001
                print(f"NIFTYBEES fallback failed: {ex}")
        if td:
            with open(os.path.join(OUT, "_NIFTY50TRI.json"), "w", encoding="utf-8") as f:
                json.dump({"s": "NIFTY 50 TRI", "d": td, "c": tv}, f, separators=(",", ":"))
            MKT = pd.Series(tv, index=pd.to_datetime(td))
            nifty.update({"tri": 1, "tri_src": src, "m": metrics(td, tv), "m30": metrics(*cut30(td, tv))})
    else:
        print("Nifty 50 download failed; beta will be blank")
    indices = []
    for tk, key, name in INDICES:  # extra benchmarks (price indices from Yahoo)
        try:
            idf = download([tk])
            ix = closes(idf, tk) if idf is not None else None
            if ix is None or len(ix) < 250:
                print(f"Index {name}: not available")
                continue
            idd = [d.strftime("%Y-%m-%d") for d in ix.index]
            idv = [round(float(v), 2) for v in ix.values]
            idd, idv = drop_holidays(idd, idv)
            fname = "_IDX_" + key
            with open(os.path.join(OUT, fname + ".json"), "w", encoding="utf-8") as f:
                json.dump({"s": name, "d": idd, "c": idv}, f, separators=(",", ":"))
            indices.append({"key": key, "name": name, "file": fname, "last": idv[-1], "date": idd[-1],
                            "m": metrics(idd, idv), "m30": metrics(*cut30(idd, idv))})
            print(f"Index {name}: {len(idv)} days")
        except Exception as e:  # noqa: BLE001
            print(f"Index {name} failed: {e}")
    ff = fama_french()
    apt = {}
    for tk, key, name in APT_FACTORS:  # macro factors for the APT model
        try:
            fdf = download([tk])
            fx = closes(fdf, tk) if fdf is not None else None
            if fx is None or len(fx) < 250:
                print(f"Factor {name}: not available")
                continue
            fd = [d.strftime("%Y-%m-%d") for d in fx.index]
            fv = [round(float(v), 4) for v in fx.values]
            with open(os.path.join(OUT, "_F_" + key + ".json"), "w", encoding="utf-8") as f:
                json.dump({"s": name, "d": fd, "c": fv}, f, separators=(",", ":"))
            apt[key] = {"name": name, "file": "_F_" + key}
            print(f"Factor {name}: {len(fv)} days")
        except Exception as e:  # noqa: BLE001
            print(f"Factor {name} failed: {e}")
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
                        dv = old.get("dv", [])
                        v2, adj, dv = fix_jumps(d2, v2, dv)
                        from_nse += used
                        alladj = old.get("adj", []) + adj
                        if used or adj:
                            with open(path, "w", encoding="utf-8") as f:
                                json.dump({"s": sym, "d": d2, "c": v2, **({"dv": dv} if dv else {}),
                                           **({"adj": alladj} if alladj else {})}, f, separators=(",", ":"))
                        saved.append(entry(sym, name, ind, d2, v2, alladj, dv))
                continue
            dates = [d.strftime("%Y-%m-%d") for d in s.index]
            vals = [round(float(v), 2) for v in s.values]
            dates, vals, used = with_nse(sym, dates, vals, nse_date, nse)
            dates, vals = drop_holidays(dates, vals)
            dv = [x for x in dividends(df, t) if x[0] >= dates[0]]
            vals, adj, dv = fix_jumps(dates, vals, dv)
            from_nse += used
            with open(path, "w", encoding="utf-8") as f:
                json.dump({"s": sym, "d": dates, "c": vals, **({"dv": dv} if dv else {}),
                           **({"adj": adj} if adj else {})}, f, separators=(",", ":"))
            saved.append(entry(sym, name, ind, dates, vals, adj, dv, traded_value(df, t)))
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
                   "nifty": nifty, "indices": indices, "ff": ff, "apt": apt,
                   "source": (f"Latest close: NSE bhavcopy {nse_date}. " if nse_date else "")
                             + "History: Yahoo Finance daily closes, split and bonus adjusted; demerger gaps removed; dividends added for total return"}, f)
    print(f"Saved {len(saved)} stocks ({from_nse} with NSE's official close). Failed: {len(failed)} {failed[:20]}")


APT_FACTORS = [  # (Yahoo ticker, key, name) macro factors for APT
    ("INR=X", "USDINR", "US dollar in rupees"),
    ("BZ=F", "BRENT", "Brent crude oil"),
]
FF_URL = "https://faculty.iima.ac.in/iffm/Indian-Fama-French-Momentum/DATA/{m}_FourFactors_and_Market_Returns_Daily_SurvivorshipBiasAdjusted.csv"


def fama_french():
    """Indian Fama-French and momentum factors (IIM Ahmedabad data library, daily, survivorship-bias adjusted).
    Saves data/_FF.json from 2016 and returns long-run yearly premia (since 1993) for the meta file."""
    today = dt.date.today()
    for back in range(0, 20):
        y, m = today.year, today.month - back
        while m <= 0:
            y, m = y - 1, m + 12
        url = FF_URL.format(m=f"{y}-{m:02d}")
        try:
            r = requests.get(url, headers=HEADERS, timeout=40)
            if not r.ok or len(r.text) < 1000:
                continue
            df = pd.read_csv(io.StringIO(r.text))
            df.columns = [c.strip() for c in df.columns]
            col = lambda *names: next((c for c in df.columns if c.upper().replace(" ", "") in names), None)
            dcol = next(c for c in df.columns if "date" in c.lower())
            cm, cs, ch, cw, cr = col("MF", "MKT-RF", "MKTRF", "MARKETEXCESS", "RM-RF"), col("SMB"), col("HML"), col("WML"), col("RF")
            if not (cm and cs and ch and cr):
                print(f"Fama-French file has unexpected columns: {list(df.columns)}")
                return None
            print(f"Fama-French columns: {list(df.columns)}; first row: {df.iloc[0].tolist()}")
            dates = pd.to_datetime(df[dcol].astype(str), errors="coerce", dayfirst=False)
            if dates.isna().mean() > 0.5 or (dates.dropna().dt.year < 1990).any():
                dates = pd.to_datetime(df[dcol].astype(str), errors="coerce", dayfirst=True)
            df = df.assign(_d=dates).dropna(subset=["_d"]).sort_values("_d")
            vals = df[[cm, cs, ch, cr] + ([cw] if cw else [])].astype(float)
            if vals[cm].abs().median() > 0.05:  # percent → decimal
                vals = vals / 100.0
            days_per_year = len(df) / max(1.0, (df["_d"].iloc[-1] - df["_d"].iloc[0]).days / 365.25)
            prem = {k: round(float(vals[c].mean() * days_per_year), 4) for k, c in (("mkt", cm), ("smb", cs), ("hml", ch), ("wml", cw)) if c}
            keep = df["_d"] >= "2016-01-01"
            out = {"d": [d.strftime("%Y-%m-%d") for d in df["_d"][keep]],
                   "mkt": [round(x, 6) for x in vals[cm][keep]], "smb": [round(x, 6) for x in vals[cs][keep]],
                   "hml": [round(x, 6) for x in vals[ch][keep]], "rf": [round(x, 7) for x in vals[cr][keep]]}
            if cw:
                out["wml"] = [round(x, 6) for x in vals[cw][keep]]
            with open(os.path.join(OUT, "_FF.json"), "w", encoding="utf-8") as f:
                json.dump(out, f, separators=(",", ":"))
            print(f"Fama-French factors: {len(out['d'])} days to {out['d'][-1]} ({y}-{m:02d} release)")
            return {"file": "_FF", "to": out["d"][-1], "release": f"{y}-{m:02d}", "premia": prem,
                    "since": df["_d"].iloc[0].strftime("%Y-%m-%d")}
        except Exception as e:  # noqa: BLE001
            print(f"Fama-French {y}-{m:02d}: {e}")
    print("Fama-French factors not available")
    return None


INDICES = [  # (Yahoo ticker, key, name) extra benchmarks
    ("^CRSLDX", "N500", "Nifty 500"),
    ("^NSMIDCP", "NEXT50", "Nifty Next 50"),
    ("^NSEMDCP50", "MID50", "Nifty Midcap 50"),
    ("^CNXSC", "SMALL100", "Nifty Smallcap 100"),
    ("^NSEBANK", "BANK", "Nifty Bank"),
    ("^CNXIT", "IT", "Nifty IT"),
    ("^CNXPHARMA", "PHARMA", "Nifty Pharma"),
    ("^CNXAUTO", "AUTO", "Nifty Auto"),
    ("^CNXFMCG", "FMCG", "Nifty FMCG"),
    ("^CNXMETAL", "METAL", "Nifty Metal"),
]
MKT = None  # Nifty 50 daily closes (pandas Series), set in main()


def cut30(dates, vals, dv=None):
    """The same series ending 30 days before its last day (education mode: SEBI 30-day lag)."""
    lim = (dt.date.fromisoformat(dates[-1]) - dt.timedelta(days=30)).isoformat()
    n = sum(1 for d in dates if d <= lim)
    return (dates[:n], vals[:n]) if dv is None else (dates[:n], vals[:n], [x for x in dv if x[0] <= lim])


def metrics(dates, vals, dv=None):
    """Annual return, annual risk, price return, CAGR and beta vs Nifty 50 for 1, 3, 5 and 10 years.
    Same formulas as the website: daily returns, mean x 252, sample SD x sqrt(252),
    beta = covariance(stock, Nifty 50) / variance(Nifty 50) on the same days."""
    if len(dates) < 30:
        return {}
    raw = pd.Series(vals, index=pd.to_datetime(dates))
    s = pd.Series(total_return(dates, vals, dv), index=pd.to_datetime(dates))  # dividends reinvested
    end, out = s.index[-1], {}
    for y in (1, 3, 5, 10):
        start = end - pd.DateOffset(years=y)
        p = s[s.index >= start]
        if len(p) < 30 or (p.index[0] - start).days > 15:
            continue
        r = p.pct_change().dropna()
        days = (p.index[-1] - p.index[0]).days
        growth = p.iloc[-1] / p.iloc[0]
        rp = raw[raw.index >= start]
        beta = None
        if MKT is not None:
            both = pd.concat([p, MKT[MKT.index >= p.index[0]]], axis=1, join="inner").pct_change().dropna()
            if len(both) > 20 and both.iloc[:, 1].var() > 0:
                beta = round(float(both.iloc[:, 0].cov(both.iloc[:, 1]) / both.iloc[:, 1].var()), 3)
        out[str(y)] = [round(float(r.mean() * 252), 4), round(float(r.std(ddof=1) * 252 ** 0.5), 4),
                       round(float(rp.iloc[-1] / rp.iloc[0] - 1), 4), round(float(growth ** (365.25 / days) - 1), 4), beta]
    return out


def entry(sym, name, ind, dates, vals, adj=None, dv=None, tv=None):
    prev = vals[-2] if len(vals) > 1 else vals[-1]
    return {"sym": sym, "name": name, "ind": ind, "file": file_name(sym),
            "last": vals[-1], "date": dates[-1], "chg": round(vals[-1] / prev - 1, 4),
            "from": dates[0], "m": metrics(dates, vals, dv), "m30": metrics(*cut30(dates, vals, dv or [])),
            **({"n5": 1} if sym in N500 else {}), **({"tv": tv} if tv is not None else {}),
            **({"dy": round(sum(a for d, a in dv if d > (dt.date.fromisoformat(dates[-1]) - dt.timedelta(days=365)).isoformat()) / vals[-1], 4)} if dv else {}),
            **({"k": KIND[sym]} if sym in KIND else {}), **({"adj": len(adj)} if adj else {})}


if __name__ == "__main__":
    main()
