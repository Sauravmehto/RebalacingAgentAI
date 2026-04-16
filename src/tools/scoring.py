"""
scoring.py — Portfolio analysis, stock scoring, and rebalancing decision engine (v2).

Composite score formula (5 factors):
  score = return_score   * 0.30
        + sentiment_norm * 0.25
        + trend_score    * 0.20
        + alloc_score    * 0.15
        + risk_score     * 0.10

Action types: STRONG BUY / BUY / HOLD / REDUCE / PARTIAL SELL / SELL / STRONG SELL
Confidence:   HIGH / MEDIUM / LOW
"""

import logging
from typing import List

log = logging.getLogger(__name__)

# ── Strength thresholds ───────────────────────────────────────────────────────
STRONG_RETURN_THRESHOLD = 10.0    # return_pct >= +10%  → Strong
WEAK_RETURN_THRESHOLD   = -10.0   # return_pct <= -10%  → Weak

# ── Profit-booking thresholds ─────────────────────────────────────────────────
PARTIAL_SELL_THRESHOLD  = 20.0    # return > +20%  → PARTIAL SELL
STRONG_SELL_THRESHOLD   = 40.0    # return > +40%  → STRONG SELL

# ── Stop-loss thresholds ──────────────────────────────────────────────────────
REDUCE_THRESHOLD        = -10.0   # return < -10%  → REDUCE (early warning)
STOP_LOSS_THRESHOLD     = -15.0   # return < -15%  → SELL   (hard stop)

# ── Score action thresholds ───────────────────────────────────────────────────
STRONG_BUY_SCORE        = 75.0
STRONG_SELL_SCORE       = 25.0

# ── Legacy thresholds (kept for backward compatibility) ───────────────────────
SELL_PROFIT_THRESHOLD   = 5.0
SELL_LOSS_THRESHOLD     = -20.0
BUY_MIN_RETURN_THRESHOLD = -10.0


# ── Helpers ───────────────────────────────────────────────────────────────────

def label_strength(return_pct: float) -> str:
    """Classify a stock as Strong / Neutral / Weak by price return."""
    if return_pct >= STRONG_RETURN_THRESHOLD:
        return "Strong"
    if return_pct <= WEAK_RETURN_THRESHOLD:
        return "Weak"
    return "Neutral"


def get_allocation_score(allocation_status: str) -> float:
    """
    Convert allocation status to a score component.

    Underweight → 1.0  (portfolio needs more of this sector — encourages BUY)
    Neutral     → 0.5
    Overweight  → 0.0  (portfolio already over-allocated — discourages BUY)
    """
    return {"Underweight": 1.0, "Neutral": 0.5, "Overweight": 0.0}.get(
        allocation_status, 0.5
    )


# ── Scoring ───────────────────────────────────────────────────────────────────

def calculate_score(return_pct: float, sentiment: str, position_size_pct: float) -> float:
    """
    Legacy composite score (v1) — kept for backward compatibility.
    Weights: price 40%, sentiment 40%, concentration 20%.
    """
    sentiment_val  = {"Positive": 1.0, "Neutral": 0.5, "Negative": 0.0}.get(sentiment, 0.5)
    price_norm     = min(max(return_pct / 100.0 + 0.5, 0.0), 1.0)
    conc_score     = max(1.0 - position_size_pct / 30.0, 0.0)
    raw = (price_norm * 0.40 + sentiment_val * 0.40 + conc_score * 0.20) * 100.0
    return round(min(max(raw, 0.0), 100.0), 1)


def calculate_score_v2(
    return_pct:       float,
    sentiment_norm:   float,   # already in [0, 1]  — from sentiment_to_norm()
    trend_score:      float,   # [0, 1]              — from compute_trend_score()
    allocation_score: float,   # [0, 1]              — from get_allocation_score()
    risk_score:       float,   # [0, 1]              — computed below
) -> float:
    """
    5-factor composite score in [0, 100].

    Weights:
      return performance  30%
      sentiment intensity 25%
      price trend         20%
      sector allocation   15%
      risk (volatility)   10%
    """
    return_norm = min(max(return_pct / 100.0 + 0.5, 0.0), 1.0)

    raw = (
        return_norm       * 0.30 +
        sentiment_norm    * 0.25 +
        trend_score       * 0.20 +
        allocation_score  * 0.15 +
        risk_score        * 0.10
    ) * 100.0

    return round(min(max(raw, 0.0), 100.0), 1)


def compute_risk_score(return_pct: float) -> float:
    """
    Risk score: penalises extreme moves in either direction.
    Stable, near-zero returns score highest (1.0).
    Very large gains or losses both score lower (extreme = uncertain).

    risk_score = 1 - abs(return_pct) / 50, clamped to [0, 1]
    """
    return round(min(max(1.0 - abs(return_pct) / 50.0, 0.0), 1.0), 4)


# ── Decision engine ───────────────────────────────────────────────────────────

def _count_bullish_signals(
    return_pct:       float,
    sentiment:        str,
    trend_label:      str,
    allocation_status: str,
    score:            float,
) -> int:
    """Count how many signals are pointing bullish (for confidence calculation)."""
    count = 0
    if return_pct > 0:
        count += 1
    if sentiment in ("Positive", "Strong Positive"):
        count += 1
    if trend_label == "Uptrend":
        count += 1
    if allocation_status == "Underweight":
        count += 1
    if score > 60:
        count += 1
    return count


def _count_bearish_signals(
    return_pct:       float,
    sentiment:        str,
    trend_label:      str,
    allocation_status: str,
    score:            float,
) -> int:
    """Count how many signals are pointing bearish (for confidence calculation)."""
    count = 0
    if return_pct < 0:
        count += 1
    if sentiment in ("Negative", "Strong Negative"):
        count += 1
    if trend_label == "Downtrend":
        count += 1
    if allocation_status == "Overweight":
        count += 1
    if score < 40:
        count += 1
    return count


def _compute_confidence(
    return_pct:        float,
    sentiment:         str,
    trend_label:       str,
    allocation_status: str,
    score:             float,
) -> str:
    """
    HIGH   — ≥ 3 signals agree in one direction
    MEDIUM — 2 signals agree
    LOW    — signals conflict or < 2 agree
    """
    bulls = _count_bullish_signals(return_pct, sentiment, trend_label, allocation_status, score)
    bears = _count_bearish_signals(return_pct, sentiment, trend_label, allocation_status, score)
    dominant = max(bulls, bears)

    if dominant >= 3:
        return "HIGH"
    if dominant >= 2:
        return "MEDIUM"
    return "LOW"


def rebalance_decision_v2(
    return_pct:        float,
    sentiment:         str,
    trend_label:       str,
    allocation_status: str,
    score:             float,
) -> tuple:
    """
    Apply v2 rebalancing rules and return (action, reason, confidence).

    Priority order (highest first):
      1. Profit booking  — return thresholds override all other signals
      2. Stop loss       — capital protection
      3. Allocation-aware rules
      4. Trend + sentiment combinations
      5. Score thresholds
      6. Default HOLD
    """
    confidence = _compute_confidence(
        return_pct, sentiment, trend_label, allocation_status, score
    )

    # ── 1. Profit booking ─────────────────────────────────────────────────────
    if return_pct >= STRONG_SELL_THRESHOLD:
        return (
            "STRONG SELL",
            f"Booking maximum profit at {return_pct:+.1f}% return — lock in gains before reversal",
            confidence,
        )
    if return_pct >= PARTIAL_SELL_THRESHOLD:
        return (
            "PARTIAL SELL",
            f"Partial profit booking at {return_pct:+.1f}% — trim position while keeping upside exposure",
            confidence,
        )

    # ── 2. Stop loss ──────────────────────────────────────────────────────────
    if return_pct <= STOP_LOSS_THRESHOLD:
        return (
            "SELL",
            f"Stop loss triggered at {return_pct:.1f}% — protecting capital from further downside",
            confidence,
        )
    if return_pct <= REDUCE_THRESHOLD:
        return (
            "REDUCE",
            f"Early warning: {return_pct:.1f}% drawdown — reducing position to manage risk",
            confidence,
        )

    # ── 3. Allocation-aware rules ─────────────────────────────────────────────
    if allocation_status == "Overweight" and sentiment in ("Negative", "Strong Negative"):
        return (
            "SELL",
            f"Sector overweight ({allocation_status}) with {sentiment.lower()} sentiment — reduce exposure",
            confidence,
        )
    if (allocation_status == "Underweight"
            and sentiment in ("Positive", "Strong Positive")
            and trend_label == "Uptrend"):
        return (
            "STRONG BUY",
            f"Underweight sector with {sentiment.lower()} sentiment and confirmed uptrend — add aggressively",
            confidence,
        )

    # ── 4. Trend + sentiment combinations ─────────────────────────────────────
    if trend_label == "Downtrend" and sentiment in ("Negative", "Strong Negative"):
        return (
            "SELL",
            f"Downtrend confirmed with {sentiment.lower()} sector sentiment — exit position",
            confidence,
        )
    if trend_label == "Uptrend" and sentiment in ("Positive", "Strong Positive"):
        return (
            "BUY",
            f"Uptrend with {sentiment.lower()} sector sentiment — momentum favours adding",
            confidence,
        )

    # ── 5. Score-based thresholds ─────────────────────────────────────────────
    if score >= STRONG_BUY_SCORE:
        return (
            "STRONG BUY",
            f"High composite score ({score:.0f}/100) — top-ranked performer across all factors",
            confidence,
        )
    if score <= STRONG_SELL_SCORE:
        return (
            "STRONG SELL",
            f"Low composite score ({score:.0f}/100) — fundamentally weak across multiple factors",
            confidence,
        )

    # ── 6. Default HOLD ───────────────────────────────────────────────────────
    return (
        "HOLD",
        (
            f"Mixed signals — score={score:.0f}, sentiment={sentiment}, "
            f"trend={trend_label}, allocation={allocation_status}, return={return_pct:+.1f}%"
        ),
        confidence,
    )


# ── Legacy decision (v1) — kept for backward compatibility ────────────────────

def rebalance_decision(
    return_pct: float,
    sentiment:  str,
    strength:   str,
    score:      float,
) -> tuple:
    """Legacy v1 decision engine — returns (action, reason) with 3 action types."""
    if sentiment == "Negative" and return_pct > SELL_PROFIT_THRESHOLD:
        return "SELL", f"Locking in +{return_pct:.1f}% profit while sector sentiment is Negative"
    if sentiment == "Negative" and return_pct < SELL_LOSS_THRESHOLD:
        return "SELL", f"Cutting loss at {return_pct:.1f}% on Negative sector outlook"
    if score < 30:
        return "SELL", f"Low composite score ({score:.0f}) signals fundamental weakness"
    if sentiment == "Positive" and return_pct > BUY_MIN_RETURN_THRESHOLD:
        return "BUY",  f"Positive sector sentiment with {return_pct:+.1f}% return suggests continued upside"
    if score > 75:
        return "BUY",  f"High composite score ({score:.0f}) with {strength.lower()} performance warrants adding"
    return "HOLD", f"Mixed or Neutral signals (score={score:.0f}, sentiment={sentiment}, return={return_pct:+.1f}%)"


# ── Portfolio summary ─────────────────────────────────────────────────────────

def compute_portfolio_summary(stocks: List[dict]) -> dict:
    """Legacy v1 portfolio summary."""
    total_invested = sum(s.get("investment_value", 0) for s in stocks)
    total_current  = sum(s.get("current_value", 0) for s in stocks)
    port_return    = (
        (total_current - total_invested) / total_invested * 100
        if total_invested else 0.0
    )
    action_counts = {"BUY": 0, "SELL": 0, "HOLD": 0}
    for s in stocks:
        action = s.get("action", "HOLD")
        if action in action_counts:
            action_counts[action] += 1
    return {
        "total_invested":       round(total_invested, 2),
        "current_value":        round(total_current, 2),
        "portfolio_return_pct": round(port_return, 2),
        "holdings_count":       len(stocks),
        **action_counts,
    }


def compute_portfolio_summary_v2(
    stocks:     List[dict],
    sentiments: dict,
    cash_pct:   float,
) -> dict:
    """
    Enhanced portfolio summary with sector breakdown, top movers, risk level,
    and cash allocation recommendation.
    """
    total_invested = sum(s.get("investment_value", 0) for s in stocks)
    total_current  = sum(s.get("current_value", 0) for s in stocks)
    port_return    = (
        (total_current - total_invested) / total_invested * 100
        if total_invested else 0.0
    )

    # Action counts (v2 — 7 action types)
    action_counts: dict = {
        "STRONG BUY":  0, "BUY": 0, "HOLD": 0,
        "REDUCE": 0, "PARTIAL SELL": 0, "SELL": 0, "STRONG SELL": 0,
    }
    for s in stocks:
        action = s.get("action", "HOLD")
        if action in action_counts:
            action_counts[action] += 1

    # Sector breakdown
    sector_values: dict = {}
    sector_returns: dict = {}
    sector_counts: dict  = {}
    for s in stocks:
        sec = s.get("sector", "Unknown")
        val = s.get("current_value", 0)
        ret = s.get("return_pct", 0)
        sector_values[sec]  = sector_values.get(sec, 0) + val
        sector_returns[sec] = sector_returns.get(sec, 0) + ret
        sector_counts[sec]  = sector_counts.get(sec, 0) + 1

    sector_breakdown = {}
    for sec, val in sector_values.items():
        pct = round(val / total_current * 100, 2) if total_current else 0.0
        avg_ret = round(sector_returns[sec] / sector_counts[sec], 2) if sector_counts[sec] else 0.0
        sector_breakdown[sec] = {
            "current_value": round(val, 2),
            "allocation_pct": pct,
            "avg_return_pct": avg_ret,
            "sentiment": sentiments.get(sec, "Neutral"),
        }

    # Top gainers and losers (top 3 each)
    sorted_by_return = sorted(stocks, key=lambda s: s.get("return_pct", 0), reverse=True)
    top_gainers = [
        {"ticker": s["ticker"], "return_pct": round(s.get("return_pct", 0), 2)}
        for s in sorted_by_return[:3]
    ]
    top_losers = [
        {"ticker": s["ticker"], "return_pct": round(s.get("return_pct", 0), 2)}
        for s in sorted_by_return[-3:]
    ]

    # Portfolio risk level
    negative_count = sum(
        1 for s in stocks if s.get("sentiment", "Neutral") in ("Negative", "Strong Negative")
    )
    loss_count = sum(1 for s in stocks if s.get("return_pct", 0) < REDUCE_THRESHOLD)
    total = len(stocks) or 1
    risk_ratio = (negative_count + loss_count) / (2 * total)

    if risk_ratio >= 0.5:
        risk_level = "High"
    elif risk_ratio >= 0.25:
        risk_level = "Medium"
    else:
        risk_level = "Low"

    return {
        "total_invested":       round(total_invested, 2),
        "current_value":        round(total_current, 2),
        "portfolio_return_pct": round(port_return, 2),
        "holdings_count":       len(stocks),
        "cash_allocation_pct":  round(cash_pct, 1),
        "risk_level":           risk_level,
        "action_counts":        action_counts,
        "sector_breakdown":     sector_breakdown,
        "top_gainers":          top_gainers,
        "top_losers":           top_losers,
    }


# ── Heuristic capital flows (indicative only — not execution advice) ───────────
SELL_TRIM_FRACTION: dict = {
    "REDUCE":       0.25,
    "PARTIAL SELL": 0.50,
    "SELL":         1.00,
    "STRONG SELL":  1.00,
}
BUY_INDICATIVE_FRACTION: dict = {
    "BUY":        0.02,
    "STRONG BUY": 0.04,
}
SELL_ACTION_TYPES = frozenset(SELL_TRIM_FRACTION.keys())
BUY_ACTION_TYPES = frozenset(BUY_INDICATIVE_FRACTION.keys())


def estimated_flow_usd_for_action(action: str, current_value: float) -> float:
    """Rough notional tied to an action (sell-side trim or buy-side add vs position)."""
    cv = float(current_value or 0.0)
    if action in SELL_TRIM_FRACTION:
        return round(cv * SELL_TRIM_FRACTION[action], 2)
    if action in BUY_INDICATIVE_FRACTION:
        return round(cv * BUY_INDICATIVE_FRACTION[action], 2)
    return 0.0


def compute_capital_flows(stocks: List[dict], cash_pct: float) -> dict:
    """
    Aggregate indicative sell proceeds and buy deployment, and rank sell candidates.

    cash_pct is retained for documentation only in assumptions (recommended reserve).
    """
    _ = cash_pct
    estimated_sell = 0.0
    estimated_buy = 0.0
    sell_candidates: List[dict] = []

    for s in stocks:
        action = s.get("action", "HOLD")
        cv = float(s.get("current_value", 0) or 0)
        t = s.get("ticker", "?")
        reason = (s.get("reason") or "")[:400]

        if action in SELL_TRIM_FRACTION:
            usd = round(cv * SELL_TRIM_FRACTION[action], 2)
            estimated_sell += usd
            sell_candidates.append({
                "ticker":             t,
                "action":             action,
                "current_value":      round(cv, 2),
                "estimated_trim_usd": usd,
                "reason":             reason,
            })
        elif action in BUY_INDICATIVE_FRACTION:
            usd = round(cv * BUY_INDICATIVE_FRACTION[action], 2)
            estimated_buy += usd

    sell_candidates.sort(key=lambda x: x["estimated_trim_usd"], reverse=True)

    return {
        "estimated_sell_proceeds_usd": round(estimated_sell, 2),
        "estimated_buy_deployment_usd": round(estimated_buy, 2),
        "sell_candidates":             sell_candidates,
        "assumptions": (
            "Indicative only, not execution advice. Sell-side: fraction of position value — "
            + ", ".join(f"{k}={v:.0%}" for k, v in SELL_TRIM_FRACTION.items())
            + ". Buy-side: "
            + ", ".join(f"{k}={v:.0%} of position" for k, v in BUY_INDICATIVE_FRACTION.items())
            + "."
        ),
    }
