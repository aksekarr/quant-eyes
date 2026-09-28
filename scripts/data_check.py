#!/usr/bin/env python3
"""Data check: which candidate instruments can each free provider actually supply?

Run by Avi in his own terminal (it makes network requests and needs API keys).
Codex must never run this without --list.

What it reports, per candidate (metadata only)
- whether the request worked, first and last month, number of months
- whether a dividend-adjusted (total-return) series exists
- data-quality flags: missing months, non-positive values, and extreme one-month moves
  (a sign of a quoting-unit change such as pounds vs pence, or a bad data point).
  Only the month of a flag is printed, never a price.

Price values are held in memory for the run and then discarded. Nothing is written to
disk. No prices are printed. (See docs/DATA-RIGHTS.md.)

Keys: environment variables TIINGO_API_KEY and ALPHAVANTAGE_API_KEY. A provider with
no key is skipped. Keys are never printed.

Usage
  python3 scripts/data_check.py --list                    # show the plan, no network
  python3 scripts/data_check.py                           # check everything
  python3 scripts/data_check.py --provider tiingo         # one provider only
  python3 scripts/data_check.py --only btcusd,AZN.LON     # named symbols only
"""

import argparse
import datetime
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

# Pause between Alpha Vantage calls: the free tier limits requests per minute and per day.
AV_PAUSE_SECONDS = 13
TIMEOUT_SECONDS = 30

# One-month move beyond these ratios is flagged for a human to look at.
# Bitcoin has had genuine months beyond 3x, so a flag is a question, not a verdict.
EXTREME_UP_RATIO = 3.0
EXTREME_DOWN_RATIO = 0.25

# Each candidate: (label, provider, kind, symbol).
CANDIDATES = [
    # Tiingo: US-listed stocks and ETFs, crypto.
    ("Microsoft", "tiingo", "equity", "MSFT"),
    ("Apple", "tiingo", "equity", "AAPL"),
    ("Nvidia", "tiingo", "equity", "NVDA"),
    ("Vanguard Total World (US-listed global tracker)", "tiingo", "equity", "VT"),
    ("iShares Gold Trust (US-listed gold fund)", "tiingo", "equity", "IAU"),
    ("SPDR Gold Shares (US-listed gold fund)", "tiingo", "equity", "GLD"),
    ("Bitcoin in USD", "tiingo", "crypto", "btcusd"),
    # Alpha Vantage: London-listed funds and UK large caps in GBP, a US stock for
    # comparison, bitcoin in GBP and the GBP/USD rate.
    ("Microsoft", "alphavantage", "equity", "MSFT"),
    ("Vanguard FTSE All-World, distributing (London)", "alphavantage", "equity", "VWRL.LON"),
    ("Vanguard FTSE All-World, accumulating (London)", "alphavantage", "equity", "VWRP.LON"),
    ("iShares Core MSCI World, accumulating (London)", "alphavantage", "equity", "SWDA.LON"),
    ("iShares Physical Gold (London)", "alphavantage", "equity", "SGLN.LON"),
    ("iShares Core UK Gilts (London)", "alphavantage", "equity", "IGLT.LON"),
    ("AstraZeneca (London)", "alphavantage", "equity", "AZN.LON"),
    ("Shell (London)", "alphavantage", "equity", "SHEL.LON"),
    ("Bitcoin in GBP", "alphavantage", "crypto", "BTC"),
    ("GBP/USD exchange rate", "alphavantage", "fx", "GBP/USD"),
]

KEY_ENV = {"tiingo": "TIINGO_API_KEY", "alphavantage": "ALPHAVANTAGE_API_KEY"}


class CheckError(Exception):
    """A reportable problem with one candidate. Message must never contain a key."""


def http_get_json(url, headers=None):
    """GET a URL and parse JSON. Errors are re-raised without the URL (it may hold a key)."""
    request = urllib.request.Request(url, headers=headers or {})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            body = response.read()
    except urllib.error.HTTPError as exc:
        raise CheckError(f"HTTP {exc.code}") from None
    except urllib.error.URLError as exc:
        # Includes certificate errors. Never work around these by disabling verification.
        raise CheckError(f"connection problem: {exc.reason}") from None
    except TimeoutError:
        raise CheckError("timed out") from None
    try:
        return json.loads(body)
    except ValueError:
        raise CheckError("response was not JSON") from None


def to_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def summarise(points):
    """points: list of (date string, value or None). Returns a metadata-only summary.

    Keeps the last value in each calendar month, then checks the month-to-month series.
    """
    by_month = {}
    for date, value in sorted((p for p in points if isinstance(p[0], str) and len(p[0]) >= 7), key=lambda p: p[0]):
        by_month[date[:7]] = value
    months = sorted(by_month)
    if not months:
        raise CheckError("no dated rows returned")

    first, last = months[0], months[-1]
    y0, m0 = int(first[:4]), int(first[5:7])
    y1, m1 = int(last[:4]), int(last[5:7])
    expected = (y1 - y0) * 12 + (m1 - m0) + 1

    values = [by_month[m] for m in months]
    non_positive = sum(1 for v in values if v is None or v <= 0)
    extreme = []
    for prev_month, month in zip(months, months[1:]):
        a, b = by_month[prev_month], by_month[month]
        if a and b and a > 0 and b > 0:
            ratio = b / a
            if ratio > EXTREME_UP_RATIO or ratio < EXTREME_DOWN_RATIO:
                extreme.append(month)

    return {
        "first": first,
        "last": last,
        "months": len(months),
        "missing_months": expected - len(months),
        "non_positive": non_positive,
        "extreme_months": extreme,
    }


# ---------------------------------------------------------------- Tiingo

def tiingo_check(kind, symbol, key):
    headers = {"Authorization": f"Token {key}", "Content-Type": "application/json"}
    base = "https://api.tiingo.com"
    result = {}

    if kind == "equity":
        meta = http_get_json(f"{base}/tiingo/daily/{urllib.parse.quote(symbol)}", headers)
        if not isinstance(meta, dict):
            raise CheckError("unexpected metadata response")
        if not meta.get("ticker"):
            raise CheckError(f"not found ({str(meta.get('detail', ''))[:80]})")
        result["name"] = meta.get("name")
        result["exchange"] = meta.get("exchangeCode")
        query = urllib.parse.urlencode({"startDate": "1990-01-01", "resampleFreq": "monthly"})
        rows = http_get_json(f"{base}/tiingo/daily/{urllib.parse.quote(symbol)}/prices?{query}", headers)
        if not isinstance(rows, list):
            raise CheckError(f"unexpected response ({str(rows)[:80]})")
        rows = [r for r in rows if isinstance(r, dict)]
        result["total_return_series"] = any(r.get("adjClose") is not None for r in rows)
        points = [(r.get("date"), to_float(r.get("adjClose", r.get("close")))) for r in rows]

    elif kind == "crypto":
        # The crypto endpoint caps how many rows one request returns, so ask one
        # calendar year at a time.
        points = []
        this_year = datetime.date.today().year
        for year in range(2010, this_year + 1):
            query = urllib.parse.urlencode({
                "tickers": symbol,
                "startDate": f"{year}-01-01",
                "endDate": f"{year}-12-31",
                "resampleFreq": "1day",
            })
            payload = http_get_json(f"{base}/tiingo/crypto/prices?{query}", headers)
            if not isinstance(payload, list) or not payload or not isinstance(payload[0], dict):
                continue
            for r in payload[0].get("priceData", []):
                if isinstance(r, dict):
                    points.append((r.get("date"), to_float(r.get("close"))))
            time.sleep(1)
        result["total_return_series"] = "n/a (no dividends)"

    else:
        raise CheckError(f"unknown kind {kind}")

    result.update(summarise(points))
    return result


# ---------------------------------------------------------------- Alpha Vantage

def av_call(params, key):
    query = urllib.parse.urlencode({**params, "apikey": key})
    payload = http_get_json(f"https://www.alphavantage.co/query?{query}")
    if not isinstance(payload, dict):
        raise CheckError("unexpected response")
    # Premium endpoints, rate limits and bad symbols come back as a message, not an HTTP error.
    for message_key in ("Information", "Note", "Error Message"):
        if message_key in payload:
            raise CheckError(f"{message_key}: {str(payload[message_key])[:140]}")
    return payload


def av_series(payload):
    """Return the time-series dict from an Alpha Vantage response, whatever its key is called."""
    for k, v in payload.items():
        # Names vary: "Monthly Time Series", "Monthly Adjusted Time Series",
        # "Time Series FX (Monthly)", "Time Series (Digital Currency Monthly)".
        if "time series" in k.lower() and isinstance(v, dict):
            return v
    raise CheckError(f"no time series in response (keys: {list(payload)[:4]})")


def av_value(row, preferred):
    """Pick the first matching field, e.g. '5. adjusted close' before '4. close'."""
    if not isinstance(row, dict):
        return None
    for wanted in preferred:
        for k, v in row.items():
            if wanted in k.lower():
                return to_float(v)
    return None


def alphavantage_check(kind, symbol, key):
    result = {}
    if kind == "equity":
        # Try the dividend-adjusted series first; fall back to price-only so we learn
        # which one the free tier actually gives.
        try:
            series = av_series(av_call({"function": "TIME_SERIES_MONTHLY_ADJUSTED", "symbol": symbol}, key))
            result["total_return_series"] = True
        except CheckError as adjusted_error:
            result["adjusted_endpoint"] = str(adjusted_error)
            time.sleep(AV_PAUSE_SECONDS)
            series = av_series(av_call({"function": "TIME_SERIES_MONTHLY", "symbol": symbol}, key))
            result["total_return_series"] = False
        preferred = ["adjusted close", "close"]
    elif kind == "crypto":
        series = av_series(av_call({"function": "DIGITAL_CURRENCY_MONTHLY", "symbol": symbol, "market": "GBP"}, key))
        result["total_return_series"] = "n/a (no dividends)"
        preferred = ["close"]
    elif kind == "fx":
        base, quote = symbol.split("/")
        series = av_series(av_call({"function": "FX_MONTHLY", "from_symbol": base, "to_symbol": quote}, key))
        result["total_return_series"] = "n/a (exchange rate)"
        preferred = ["close"]
    else:
        raise CheckError(f"unknown kind {kind}")

    points = [(date, av_value(row, preferred)) for date, row in series.items()]
    result.update(summarise(points))
    return result


CHECKERS = {"tiingo": tiingo_check, "alphavantage": alphavantage_check}


# ---------------------------------------------------------------- report

def main():
    parser = argparse.ArgumentParser(description="Check provider coverage. Prints metadata only.")
    parser.add_argument("--list", action="store_true", help="show the plan and exit (no network)")
    parser.add_argument("--provider", choices=["tiingo", "alphavantage", "all"], default="all")
    parser.add_argument("--only", help="comma-separated symbols to check, e.g. btcusd,AZN.LON")
    args = parser.parse_args()

    plan = [c for c in CANDIDATES if args.provider in ("all", c[1])]
    if args.only:
        wanted = {s.strip().lower() for s in args.only.split(",") if s.strip()}
        plan = [c for c in plan if c[3].lower() in wanted]

    if args.list:
        for label, provider, kind, symbol in plan:
            print(f"{provider:13} {kind:7} {symbol:10} {label}")
        print(f"\n{len(plan)} candidates. No requests made.")
        return 0

    keys = {p: os.environ.get(env) for p, env in KEY_ENV.items()}
    for provider in sorted({c[1] for c in plan}):
        if not keys.get(provider):
            print(f"[skip] {provider}: {KEY_ENV[provider]} is not set in this terminal.")

    ok_count = 0
    checked = 0
    last_av_call = None
    for label, provider, kind, symbol in plan:
        key = keys.get(provider)
        if not key:
            continue
        checked += 1
        if provider == "alphavantage":
            if last_av_call is not None:
                time.sleep(AV_PAUSE_SECONDS)
            last_av_call = time.time()
        print(f"\n{provider} | {symbol} | {label}")
        try:
            r = CHECKERS[provider](kind, symbol, key)
        except CheckError as exc:
            print(f"  FAILED: {exc}")
            continue
        except Exception as exc:  # anything unexpected: report the type only, never the URL
            print(f"  FAILED: unexpected {type(exc).__name__}")
            continue
        ok_count += 1
        if r.get("name") or r.get("exchange"):
            print(f"  name/exchange: {r.get('name')} / {r.get('exchange')}")
        print(f"  history: {r['first']} to {r['last']} ({r['months']} months, {r['months'] / 12:.1f}y)")
        print(f"  dividend-adjusted series: {r['total_return_series']}")
        if "adjusted_endpoint" in r:
            print(f"  adjusted endpoint said: {r['adjusted_endpoint']}")
        flags = []
        if r["missing_months"]:
            flags.append(f"{r['missing_months']} missing months")
        if r["non_positive"]:
            flags.append(f"{r['non_positive']} empty or non-positive values")
        if r["extreme_months"]:
            shown = ", ".join(r["extreme_months"][:8])
            more = "" if len(r["extreme_months"]) <= 8 else f" (+{len(r['extreme_months']) - 8} more)"
            flags.append(f"extreme one-month moves in {shown}{more}")
        print(f"  quality: {'; '.join(flags) if flags else 'no flags'}")

    print(f"\nDone. {ok_count} of {checked} checked candidates returned data.")
    print("Nothing was written to disk. No prices were printed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
