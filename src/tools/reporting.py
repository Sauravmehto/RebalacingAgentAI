"""
reporting.py — execution timeline and macro context for the rebalancing report.

Dates are indicative (calendar days from run date), not exchange settlement rules.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Dict, List


def build_execution_timeline(as_of: date | None = None) -> List[Dict[str, Any]]:
    """
    Phased checklist from report date — useful for planning trims / adds.
    """
    d0 = as_of or date.today()
    d1 = d0 + timedelta(days=3)
    d2 = d0 + timedelta(days=7)
    d3 = d0 + timedelta(days=28)
    d4 = d0 + timedelta(days=45)

    return [
        {
            "phase": "Report & orders",
            "date_range": f"{d0.isoformat()} – {d1.isoformat()}",
            "description": "Review actions, tax lots, and place limit orders where possible.",
        },
        {
            "phase": "Settlement window",
            "date_range": f"{d1.isoformat()} – {d2.isoformat()}",
            "description": "Typical T+2 equity settlement; confirm cash available before buys.",
        },
        {
            "phase": "Re-check risk",
            "date_range": f"{d2.isoformat()} – {d3.isoformat()}",
            "description": "Revisit stop-loss / REDUCE names if macro or earnings gap the stock.",
        },
        {
            "phase": "Allocation review",
            "date_range": f"{d3.isoformat()} – {d4.isoformat()}",
            "description": "Compare sector weights vs targets; schedule next full rebalance.",
        },
    ]


# Curated macro checklist — static copy; can later be LLM-augmented.
MACRO_TRIGGERS: List[Dict[str, Any]] = [
    {
        "id": 1,
        "title": "Rates & real yields",
        "detail": "Fed path and 10Y real yields drive growth vs value rotation.",
    },
    {
        "id": 2,
        "title": "Inflation prints",
        "detail": "CPI / PCE surprises move duration and consumer discretionary risk.",
    },
    {
        "id": 3,
        "title": "Earnings season",
        "detail": "Guidance revisions cluster — watch margin and demand commentary.",
    },
    {
        "id": 4,
        "title": "Geopolitical / energy shock",
        "detail": "Energy and defensives can gap on supply headlines.",
    },
    {
        "id": 5,
        "title": "Liquidity & credit",
        "detail": "HY spreads and funding stress flag risk-off for cyclicals and small-caps.",
    },
]


def build_macro_triggers() -> List[Dict[str, Any]]:
    return [dict(x) for x in MACRO_TRIGGERS]


def summarize_cost_basis(stocks: List[dict]) -> Dict[str, int]:
    """Count rows by cost_basis_source for portfolio_summary."""
    counts: Dict[str, int] = {}
    for s in stocks:
        src = s.get("cost_basis_source") or "unknown"
        counts[src] = counts.get(src, 0) + 1
    return counts
