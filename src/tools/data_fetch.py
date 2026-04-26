"""
data_fetch.py — yfinance wrappers for price and sector data.

Fallback chain for price fetching:
  1. yfinance Ticker.history()
  2. yfinance download() (different code path, sometimes succeeds when history() fails)
  3. Claude (Anthropic API) best-effort estimate — logged clearly as an estimate
  (skipped for cost basis when SKIP_CLAUDE_COST_BASIS=1)
"""

import logging
import os
import re
import json
import urllib.parse
import urllib.request
from datetime import datetime, timedelta
from functools import lru_cache
from typing import Optional, Tuple

import yfinance as yf

log = logging.getLogger(__name__)

# Cost basis source labels (API / JSON)
COST_BASIS_CSV = "csv"
COST_BASIS_HISTORICAL = "historical_close"
COST_BASIS_CLAUDE = "claude_estimate"
COST_BASIS_UNKNOWN_FLAT = "unknown_flat"

_SERPAPI_STOCK_EXCHANGE = {
    "MSFT": "NASDAQ",
    "NVDA": "NASDAQ",
    "JPM": "NYSE",
    "XOM": "NYSE",
    "PG": "NYSE",
    "NKE": "NYSE",
    "CAT": "NYSE",
    "HON": "NASDAQ",
    "SPY": "NYSEARCA",
    "QQQ": "NASDAQ",
    "VT": "NYSEARCA",
    "ARKK": "NYSEARCA",
    "GLD": "NYSEARCA",
}


def _to_float(value) -> Optional[float]:
    """Parse numbers from strings like '$424.62' or '23,235.63'."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    cleaned = re.sub(r"[^\d.\-]", "", str(value))
    if not cleaned:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def _serpapi_extract_price(payload: dict) -> Optional[float]:
    """Best-effort extraction across known google_finance response shapes."""
    for key in ("price", "extracted_price"):
        parsed = _to_float(payload.get(key))
        if parsed and parsed > 0:
            return parsed

    summary = payload.get("summary") or {}
    if isinstance(summary, dict):
        for key in ("price", "extracted_price"):
            parsed = _to_float(summary.get(key))
            if parsed and parsed > 0:
                return parsed

    for key in ("about_panel", "knowledge_graph"):
        section = payload.get(key) or {}
        if isinstance(section, dict):
            for price_key in ("price", "extracted_price"):
                parsed = _to_float(section.get(price_key))
                if parsed and parsed > 0:
                    return parsed

    return None


def _build_serpapi_query(ticker: str) -> list[str]:
    """Try known exchange-qualified query first, then common fallbacks."""
    ticker_u = (ticker or "").strip().upper()
    queries = []
    mapped_exch = _SERPAPI_STOCK_EXCHANGE.get(ticker_u)
    if mapped_exch:
        queries.append(f"{ticker_u}:{mapped_exch}")
    queries.append(ticker_u)
    queries.append(f"{ticker_u}:NASDAQ")
    queries.append(f"{ticker_u}:NYSE")
    return list(dict.fromkeys(queries))


def get_current_price_serpapi(ticker: str) -> Optional[float]:
    """Fetch current price via SerpAPI google_finance engine when key is configured."""
    api_key = os.getenv("SERPAPI_API_KEY", "").strip()
    if not api_key:
        return None

    for query in _build_serpapi_query(ticker):
        params = urllib.parse.urlencode(
            {
                "engine": "google_finance",
                "q": query,
                "api_key": api_key,
                "hl": "en",
            }
        )
        url = f"https://serpapi.com/search.json?{params}"
        try:
            with urllib.request.urlopen(url, timeout=12) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
            price = _serpapi_extract_price(payload)
            if price and price > 0:
                log.info("  %s current price (SerpAPI %s) = $%.4f", ticker, query, price)
                return price
        except Exception as exc:
            log.debug("SerpAPI fetch failed for %s (%s): %s", ticker, query, exc)

    return None


def get_price_from_claude(ticker: str, context: str) -> Optional[float]:
    """
    Ask Claude for an approximate stock price when yfinance has failed.

    This is a best-effort fallback — Claude's knowledge has a training cutoff
    and cannot access live markets.  The result is logged clearly as an estimate
    so the user knows it is not a real-time figure.

    context: human-readable string describing what price is needed,
             e.g. "current price" or "price on 2024-03-15"
    """
    try:
        import anthropic  # imported lazily so the module still loads without it

        api_key = os.getenv("ANTHROPIC_API_KEY", "")
        model   = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-5-20250929")
        if not api_key:
            return None

        client = anthropic.Anthropic(api_key=api_key)
        prompt = (
            f"What is the approximate {context} for stock ticker {ticker}? "
            "Reply with ONLY a single decimal number representing the USD price "
            "(e.g. 415.20). No dollar sign, no text, no explanation."
        )
        message = client.messages.create(
            model=model,
            max_tokens=20,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = message.content[0].text.strip()
        # Strip any stray $ or commas before parsing
        cleaned = re.sub(r"[^\d.]", "", raw)
        price   = float(cleaned)
        log.warning(
            "  [Claude fallback] %s %s ≈ $%.4f  (ESTIMATE — not live data)",
            ticker, context, price,
        )
        return price
    except Exception as exc:
        log.debug("  [Claude fallback] failed for %s: %s", ticker, exc)
        return None


@lru_cache(maxsize=256)
def get_current_price_with_source(ticker: str) -> Tuple[Optional[float], str]:
    """
    Fetch the latest closing price for a ticker and source label.

    Fallback chain:
      1. SerpAPI google_finance (if SERPAPI_API_KEY is set)
      2. yfinance Ticker.history(period="2d")
      3. yfinance download() for the last 5 days
      4. Claude best-effort estimate
    """
    # ── Attempt 1: SerpAPI google_finance ────────────────────────────────────
    serpapi_price = get_current_price_serpapi(ticker)
    if serpapi_price and serpapi_price > 0:
        return serpapi_price, "serpapi"

    # ── Attempt 2: Ticker.history ────────────────────────────────────────────
    try:
        hist = yf.Ticker(ticker).history(period="2d")
        if not hist.empty:
            price = float(hist["Close"].iloc[-1])
            log.info("  %s current price = $%.4f", ticker, price)
            return price, "yahoo_history"
        log.warning("%s: Ticker.history() returned empty — trying download()", ticker)
    except Exception as exc:
        log.warning("%s: Ticker.history() failed (%s) — trying download()", ticker, exc)

    # ── Attempt 3: yf.download ───────────────────────────────────────────────
    try:
        dl = yf.download(ticker, period="5d", progress=False, auto_adjust=True)
        if not dl.empty:
            price = float(dl["Close"].iloc[-1])
            log.info("  %s current price (download) = $%.4f", ticker, price)
            return price, "yahoo_download"
        log.warning("%s: yf.download() also empty — trying Claude fallback", ticker)
    except Exception as exc:
        log.warning("%s: yf.download() failed (%s) — trying Claude fallback", ticker, exc)

    # ── Attempt 4: Claude ────────────────────────────────────────────────────
    c_price = get_price_from_claude(ticker, "current stock price")
    if c_price is not None:
        return c_price, "claude_estimate"
    return None, "unavailable"


@lru_cache(maxsize=256)
def get_current_price(ticker: str) -> Optional[float]:
    """Backward-compatible wrapper: returns only the price."""
    p, _ = get_current_price_with_source(ticker)
    return p


@lru_cache(maxsize=256)
def get_purchase_price_detail(ticker: str, purchase_date_str: str) -> Tuple[Optional[float], str]:
    """
    Historical cost basis when CSV buy price is missing.

    Returns (price_or_None, source):
      - ("historical_close", price) from yfinance
      - ("claude_estimate", price) from Claude (unless SKIP_CLAUDE_COST_BASIS)
      - ("", None) if nothing resolved
    """
    if not (purchase_date_str or "").strip():
        return None, ""

    buy_date = None
    for fmt in ("%m/%d/%Y", "%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            buy_date = datetime.strptime(purchase_date_str.strip(), fmt).date()
            break
        except ValueError:
            continue
    if buy_date is None:
        log.warning("Cannot parse purchase date '%s' for %s", purchase_date_str, ticker)
        return None, ""

    # ── Attempt 1: Ticker.history — up to 14 days forward ───────────────────
    try:
        for offset in range(14):
            start = buy_date + timedelta(days=offset)
            end   = start    + timedelta(days=1)
            hist  = yf.Ticker(ticker).history(
                start=start.strftime("%Y-%m-%d"),
                end=end.strftime("%Y-%m-%d"),
            )
            if not hist.empty:
                price = float(hist["Close"].iloc[-1])
                log.info("  %s purchase price on %s = $%.4f", ticker, start, price)
                return price, COST_BASIS_HISTORICAL
        log.warning(
            "  %s: Ticker.history() found nothing near %s — trying download()",
            ticker, purchase_date_str,
        )
    except Exception as exc:
        log.warning("  %s: Ticker.history() error (%s) — trying download()", ticker, exc)

    # ── Attempt 2: yf.download — 30-day window ───────────────────────────────
    try:
        window_start = (buy_date - timedelta(days=5)).strftime("%Y-%m-%d")
        window_end   = (buy_date + timedelta(days=25)).strftime("%Y-%m-%d")
        dl = yf.download(ticker, start=window_start, end=window_end,
                         progress=False, auto_adjust=True)
        if not dl.empty:
            price = float(dl["Close"].iloc[0])
            log.info(
                "  %s purchase price (download ~%s) = $%.4f",
                ticker, purchase_date_str, price,
            )
            return price, COST_BASIS_HISTORICAL
        log.warning(
            "  %s: yf.download() also empty near %s — trying Claude fallback",
            ticker, purchase_date_str,
        )
    except Exception as exc:
        log.warning("  %s: yf.download() failed (%s) — trying Claude fallback", ticker, exc)

    skip_claude = os.getenv("SKIP_CLAUDE_COST_BASIS", "").strip().lower() in (
        "1", "true", "yes",
    )
    if skip_claude:
        log.info("  %s: SKIP_CLAUDE_COST_BASIS set — no Claude estimate for cost basis", ticker)
        return None, ""

    p = get_price_from_claude(ticker, f"stock price on or near {purchase_date_str}")
    if p is not None:
        return p, COST_BASIS_CLAUDE
    return None, ""


def get_purchase_price(ticker: str, purchase_date_str: str) -> Optional[float]:
    """Backward-compatible: price only."""
    p, _ = get_purchase_price_detail(ticker, purchase_date_str)
    return p


@lru_cache(maxsize=256)
def get_sector(ticker: str) -> str:
    """
    Return the sector string from yfinance Ticker.info.
    Falls back to 'Unknown' on any error.
    """
    try:
        info   = yf.Ticker(ticker).info
        sector = info.get("sector") or info.get("quoteType") or "Unknown"
        log.info("  %s sector = %s", ticker, sector)
        return sector
    except Exception as exc:
        log.error("get_sector(%s) failed: %s", ticker, exc)
        return "Unknown"


def enrich_ticker(
    ticker:            str,
    purchase_date:     str,
    quantity:          float,
    buy_price_csv:     Optional[float],
    current_price_csv: Optional[float] = None,
) -> dict:
    """
    Fetch all market data for one ticker and return an enriched dict.

    buy_price logic:
      1. Use CSV value if provided and > 0  → cost_basis_source csv, trusted return
      2. Else historical / Claude on purchase_date → estimated return
      3. Else current price as buy (0% return) → unknown_flat, estimated

    If current_price_csv is set and > 0, it is used only as a validation reference.
    Rebalancing always uses the freshest market quote available in yahoo_price/current_price.

    yahoo_price: reference quote when CSV current is not provided.
    """
    yahoo_price = get_current_price(ticker)
    cost_basis_source = COST_BASIS_UNKNOWN_FLAT
    return_pct_is_estimated = True
    current_price_source = "yahoo"
    if os.getenv("SERPAPI_API_KEY", "").strip():
        serpapi_ref = get_current_price_serpapi(ticker)
        if (
            serpapi_ref
            and yahoo_price
            and abs(float(serpapi_ref) - float(yahoo_price)) <= 0.05
        ):
            current_price_source = "serpapi"
    price_discrepancy_note: Optional[str] = None
    current_price = yahoo_price
    if not (current_price and current_price > 0) and current_price_csv and current_price_csv > 0:
        # Fallback only when live quote is unavailable.
        current_price = current_price_csv
        current_price_source = "csv_fallback"

    if current_price_csv and current_price_csv > 0 and yahoo_price and yahoo_price > 0:
        rel = abs(current_price_csv - yahoo_price) / yahoo_price
        if rel > 0.02:
            price_discrepancy_note = (
                f"CSV current ${current_price_csv:.2f} vs market ref ~${yahoo_price:.2f} "
                f"({rel * 100:.1f}% diff) — using market ref for rebalancing; verify stale export."
            )

    if buy_price_csv and buy_price_csv > 0:
        buy_price = buy_price_csv
        cost_basis_source = COST_BASIS_CSV
        return_pct_is_estimated = False
    else:
        buy_price, hist_src = get_purchase_price_detail(ticker, purchase_date)
        if buy_price is not None and buy_price > 0:
            cost_basis_source = hist_src or COST_BASIS_HISTORICAL
        else:
            buy_price = current_price
            cost_basis_source = COST_BASIS_UNKNOWN_FLAT

    sector = get_sector(ticker)

    if current_price and buy_price and buy_price > 0:
        return_pct = (current_price - buy_price) / buy_price * 100
    else:
        return_pct = 0.0

    current_value    = round((current_price or 0) * quantity, 2)
    investment_value = round((buy_price    or 0) * quantity, 2)

    return {
        "ticker":                    ticker,
        "sector":                    sector,
        "purchase_date":             purchase_date,
        "quantity":                  quantity,
        "buy_price":                 round(buy_price    or 0, 4),
        "current_price":             round(current_price or 0, 4),
        "return_pct":                round(return_pct, 2),
        "current_value":             current_value,
        "investment_value":          investment_value,
        "cost_basis_source":         cost_basis_source,
        "return_pct_is_estimated":   return_pct_is_estimated,
        "current_price_source":     current_price_source,
        "price_discrepancy_note":   price_discrepancy_note,
    }
