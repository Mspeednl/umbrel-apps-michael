"""Wrappers rond yfinance met een in-memory cache, zodat we Yahoo Finance
niet bij elke dashboard-load opnieuw bevragen."""

import time
from datetime import datetime

import requests
import yfinance as yf

CACHE_TTL_SECONDS = 900  # 15 minuten
_cache: dict[str, tuple[float, object]] = {}


def _cached(key: str, fetch_fn, force: bool = False):
    now = time.time()
    if not force and key in _cache:
        ts, value = _cache[key]
        if now - ts < CACHE_TTL_SECONDS:
            return value
    value = fetch_fn()
    _cache[key] = (now, value)
    return value


def _last_close(ticker_obj: "yf.Ticker"):
    try:
        hist = ticker_obj.history(period="5d")
    except Exception:
        return None
    if hist is not None and not hist.empty:
        return float(hist["Close"].iloc[-1])
    return None


def get_quote(ticker: str, force: bool = False) -> dict:
    def fetch():
        t = yf.Ticker(ticker)
        try:
            info = t.get_info()
        except Exception:
            info = {}

        price = _last_close(t)
        if price is None:
            price = info.get("currentPrice") or info.get("regularMarketPrice")

        ex_div_raw = info.get("exDividendDate")
        ex_div = None
        if isinstance(ex_div_raw, (int, float)):
            ex_div = datetime.utcfromtimestamp(ex_div_raw).date().isoformat()
        elif isinstance(ex_div_raw, str):
            ex_div = ex_div_raw

        return {
            "price": price,
            "currency": (info.get("currency") or "USD").upper(),
            "name": info.get("longName") or info.get("shortName") or ticker,
            "sector": info.get("sector") or "Onbekend",
            "ex_dividend_date": ex_div,
        }

    return _cached(f"quote:{ticker}", fetch, force)


def get_fx_rate(currency: str, force: bool = False) -> float:
    """Koers om 1 eenheid `currency` om te rekenen naar EUR."""
    currency = (currency or "EUR").upper()
    if currency == "EUR":
        return 1.0

    def fetch():
        pair = f"{currency}EUR=X"
        rate = _last_close(yf.Ticker(pair))
        return rate if rate else 1.0

    return _cached(f"fx:{currency}", fetch, force)


def search_symbols(query: str, limit: int = 8) -> list[dict]:
    """Zoekt tickers (aandelen én crypto) bij Yahoo Finance op naam of symbool."""
    query = (query or "").strip()
    if not query:
        return []

    def fetch():
        url = "https://query2.finance.yahoo.com/v1/finance/search"
        params = {"q": query, "quotesCount": limit, "newsCount": 0, "listsCount": 0}
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        try:
            response = requests.get(url, params=params, headers=headers, timeout=5)
            response.raise_for_status()
            quotes = response.json().get("quotes", [])
        except Exception:
            return []

        results = []
        for q in quotes:
            symbol = q.get("symbol")
            if not symbol:
                continue
            results.append(
                {
                    "symbol": symbol,
                    "name": q.get("longname") or q.get("shortname") or symbol,
                    "exchange": q.get("exchange") or q.get("exchDisp") or "",
                    "type": q.get("quoteType") or "",
                }
            )
        return results

    return _cached(f"search:{query.lower()}", fetch)


def get_dividend_history(ticker: str, force: bool = False):
    """Pandas Series met dividend per aandeel, geïndexeerd op betaaldatum."""

    def fetch():
        try:
            return yf.Ticker(ticker).dividends
        except Exception:
            return None

    return _cached(f"div:{ticker}", fetch, force)
