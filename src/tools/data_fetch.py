"""
data_fetch.py — yfinance wrappers for price and sector data.

Fallback chain for price fetching:
  1. yfinance Ticker.history()
  2. yfinance download() (different code path, sometimes succeeds when history() fails)
  3. Claude (Anthropic API) best-effort estimate — logged clearly as an estimate
"""

import logging
import os
import re
from datetime import datetime, timedelta
from functools import lru_cache
from typing import Optional

import yfinance as yf

log = logging.getLogger(__name__)


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
def get_current_price(ticker: str) -> Optional[float]:
    """
    Fetch the latest closing price for a ticker.

    Fallback chain:
      1. yfinance Ticker.history(period="2d")
      2. yfinance download() for the last 5 days
      3. Claude best-effort estimate
    """
    # ── Attempt 1: Ticker.history ────────────────────────────────────────────
    try:
        hist = yf.Ticker(ticker).history(period="2d")
        if not hist.empty:
            price = float(hist["Close"].iloc[-1])
            log.info("  %s current price = $%.4f", ticker, price)
            return price
        log.warning("%s: Ticker.history() returned empty — trying download()", ticker)
    except Exception as exc:
        log.warning("%s: Ticker.history() failed (%s) — trying download()", ticker, exc)

    # ── Attempt 2: yf.download ───────────────────────────────────────────────
    try:
        dl = yf.download(ticker, period="5d", progress=False, auto_adjust=True)
        if not dl.empty:
            price = float(dl["Close"].iloc[-1])
            log.info("  %s current price (download) = $%.4f", ticker, price)
            return price
        log.warning("%s: yf.download() also empty — trying Claude fallback", ticker)
    except Exception as exc:
        log.warning("%s: yf.download() failed (%s) — trying Claude fallback", ticker, exc)

    # ── Attempt 3: Claude ────────────────────────────────────────────────────
    return get_price_from_claude(ticker, "current stock price")


@lru_cache(maxsize=256)
def get_purchase_price(ticker: str, purchase_date_str: str) -> Optional[float]:
    """
    Fetch the closing price on or near a given purchase date.

    Fallback chain:
      1. yfinance Ticker.history() — tries up to 14 days forward
      2. yfinance download() for a 30-day window around the purchase date
      3. Claude best-effort estimate for that date

    purchase_date_str: 'MM/DD/YYYY' or 'YYYY-MM-DD'
    """
    if not purchase_date_str:
        return None

    # Parse flexible date formats
    buy_date = None
    for fmt in ("%m/%d/%Y", "%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            buy_date = datetime.strptime(purchase_date_str.strip(), fmt).date()
            break
        except ValueError:
            continue
    if buy_date is None:
        log.warning("Cannot parse purchase date '%s' for %s", purchase_date_str, ticker)
        return None

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
                return price
        log.warning("  %s: Ticker.history() found nothing near %s — trying download()",
                    ticker, purchase_date_str)
    except Exception as exc:
        log.warning("  %s: Ticker.history() error (%s) — trying download()", ticker, exc)

    # ── Attempt 2: yf.download — 30-day window ───────────────────────────────
    try:
        window_start = (buy_date - timedelta(days=5)).strftime("%Y-%m-%d")
        window_end   = (buy_date + timedelta(days=25)).strftime("%Y-%m-%d")
        dl = yf.download(ticker, start=window_start, end=window_end,
                         progress=False, auto_adjust=True)
        if not dl.empty:
            # Pick the row closest to (but not before) buy_date
            price = float(dl["Close"].iloc[0])
            log.info("  %s purchase price (download ~%s) = $%.4f",
                     ticker, purchase_date_str, price)
            return price
        log.warning("  %s: yf.download() also empty near %s — trying Claude fallback",
                    ticker, purchase_date_str)
    except Exception as exc:
        log.warning("  %s: yf.download() failed (%s) — trying Claude fallback", ticker, exc)

    # ── Attempt 3: Claude ────────────────────────────────────────────────────
    return get_price_from_claude(ticker, f"stock price on or near {purchase_date_str}")


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
    ticker:        str,
    purchase_date: str,
    quantity:      float,
    buy_price_csv: Optional[float],
) -> dict:
    """
    Fetch all market data for one ticker and return an enriched dict.

    buy_price logic:
      1. Use CSV value if provided and > 0
      2. Otherwise fetch historical close on purchase_date
      3. Fall back to current price (0% return)
    """
    current_price = get_current_price(ticker)

    if buy_price_csv and buy_price_csv > 0:
        buy_price = buy_price_csv
    else:
        buy_price = get_purchase_price(ticker, purchase_date)

    if buy_price is None:
        buy_price = current_price   # treat as 0% return if we can't determine entry

    sector = get_sector(ticker)

    if current_price and buy_price and buy_price > 0:
        return_pct = (current_price - buy_price) / buy_price * 100
    else:
        return_pct = 0.0

    current_value    = round((current_price or 0) * quantity, 2)
    investment_value = round((buy_price    or 0) * quantity, 2)

    return {
        "ticker":           ticker,
        "sector":           sector,
        "purchase_date":    purchase_date,
        "quantity":         quantity,
        "buy_price":        round(buy_price    or 0, 4),
        "current_price":    round(current_price or 0, 4),
        "return_pct":       round(return_pct, 2),
        "current_value":    current_value,
        "investment_value": investment_value,
    }
