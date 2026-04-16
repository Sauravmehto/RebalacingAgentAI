"""
trend.py — Price trend analysis for the Nexus AI portfolio manager.

For each ticker, fetches 7-day and 30-day closing price history via yfinance,
classifies each window as Uptrend / Downtrend / Sideways, and produces a
normalised trend score (0–1) used in the composite scoring formula.
"""

import logging
from functools import lru_cache
from typing import Dict, List

import yfinance as yf

log = logging.getLogger(__name__)

SIDEWAYS_THRESHOLD = 0.02   # < 2% change between first/second half → Sideways


@lru_cache(maxsize=256)
def fetch_price_history(ticker: str, days: int) -> tuple:
    """
    Return a tuple of recent closing prices for `ticker` over the last `days`.
    Using tuple so the result is hashable and can be lru_cached.
    Returns empty tuple on failure.
    """
    try:
        period = f"{days}d"
        hist = yf.Ticker(ticker).history(period=period)
        if hist.empty:
            log.warning("  [trend] %s: no price history for %dd window", ticker, days)
            return ()
        closes = tuple(float(p) for p in hist["Close"].tolist())
        log.debug("  [trend] %s: %d prices fetched for %dd window", ticker, len(closes), days)
        return closes
    except Exception as exc:
        log.warning("  [trend] fetch_price_history(%s, %d) failed: %s", ticker, days, exc)
        return ()


def classify_trend(prices: tuple) -> str:
    """
    Compare the average of the first half vs the second half of a price series.

    Returns:
      "Uptrend"   — second half avg > first half avg by >= SIDEWAYS_THRESHOLD
      "Downtrend" — second half avg < first half avg by >= SIDEWAYS_THRESHOLD
      "Sideways"  — change is within ± SIDEWAYS_THRESHOLD
    """
    if len(prices) < 4:
        return "Sideways"

    mid = len(prices) // 2
    first_avg  = sum(prices[:mid]) / mid
    second_avg = sum(prices[mid:]) / (len(prices) - mid)

    if first_avg == 0:
        return "Sideways"

    change = (second_avg - first_avg) / first_avg

    if change >= SIDEWAYS_THRESHOLD:
        return "Uptrend"
    if change <= -SIDEWAYS_THRESHOLD:
        return "Downtrend"
    return "Sideways"


def compute_trend_score(trend_7d: str, trend_30d: str) -> float:
    """
    Combine short-term and long-term trends into a single normalised score [0, 1].

    Both Uptrend   → 1.0  (strong bullish momentum)
    Both Downtrend → 0.0  (strong bearish momentum)
    Mixed signals  → 0.5  (uncertain)
    7d Up  / 30d Sideways → 0.65
    7d Down/ 30d Sideways → 0.35
    7d Sideways / 30d Up  → 0.60
    7d Sideways / 30d Down→ 0.40
    """
    _score_map = {
        ("Uptrend",   "Uptrend"):   1.00,
        ("Uptrend",   "Sideways"):  0.65,
        ("Uptrend",   "Downtrend"): 0.50,
        ("Sideways",  "Uptrend"):   0.60,
        ("Sideways",  "Sideways"):  0.50,
        ("Sideways",  "Downtrend"): 0.40,
        ("Downtrend", "Uptrend"):   0.50,
        ("Downtrend", "Sideways"):  0.35,
        ("Downtrend", "Downtrend"): 0.00,
    }
    return _score_map.get((trend_7d, trend_30d), 0.50)


def _combined_trend_label(trend_7d: str, trend_30d: str) -> str:
    """
    Produce a human-readable overall trend label from the two windows.
    Short-term (7d) is given priority.
    """
    if trend_7d == trend_30d:
        return trend_7d
    if trend_7d == "Uptrend":
        return "Uptrend"      # recent momentum outweighs longer term
    if trend_7d == "Downtrend":
        return "Downtrend"
    return trend_30d          # 7d Sideways — fall back to 30d direction


def build_ticker_trends(tickers: List[str]) -> Dict[str, dict]:
    """
    Fetch and analyse price trends for a list of tickers.

    Returns a dict keyed by ticker:
    {
      "MSFT": {
        "trend_7d":    "Uptrend",
        "trend_30d":   "Sideways",
        "trend_label": "Uptrend",
        "trend_score": 0.65,
        "prices_7d":   [...],
        "prices_30d":  [...],
      },
      ...
    }
    """
    results: Dict[str, dict] = {}

    for ticker in tickers:
        prices_7d  = fetch_price_history(ticker, 7)
        prices_30d = fetch_price_history(ticker, 30)

        trend_7d  = classify_trend(prices_7d)
        trend_30d = classify_trend(prices_30d)
        score     = compute_trend_score(trend_7d, trend_30d)
        label     = _combined_trend_label(trend_7d, trend_30d)

        results[ticker] = {
            "trend_7d":    trend_7d,
            "trend_30d":   trend_30d,
            "trend_label": label,
            "trend_score": score,
            "prices_7d":   list(prices_7d),
            "prices_30d":  list(prices_30d),
        }

        log.info(
            "  [trend] %-6s  7d=%-10s  30d=%-10s  label=%-10s  score=%.2f",
            ticker, trend_7d, trend_30d, label, score,
        )

    return results
