"""
utils.py — CSV loading, terminal printing, file export helpers (v2)
"""

import csv
import json
import logging
import os
from typing import Dict, List

from tabulate import tabulate

log = logging.getLogger(__name__)

# ── Column name aliases (normalised → canonical) ──────────────────────────────
_COL_MAP = {
    "ticker":          "ticker",
    "symbol":          "ticker",
    "sector":          "sector",
    "industry":        "sector",
    "purchase date":   "purchase_date",
    "purchasedate":    "purchase_date",
    "date":            "purchase_date",
    "quantity":        "quantity",
    "qty":             "quantity",
    "shares":          "quantity",
    "price":           "buy_price",
    "purchase price":  "buy_price",
    "avg buy price":   "buy_price",
    "buy price":       "buy_price",
}

REQUIRED_CANONICAL = {"ticker", "quantity"}


def load_portfolio_csv(path: str) -> tuple:
    """
    Read a portfolio CSV file and return (rows, errors).

    Normalises column names, strips whitespace, upper-cases tickers.
    Returns empty buy_price as None (caller will fetch via yfinance).
    """
    errors: List[str] = []
    rows:   List[dict] = []

    if not os.path.exists(path):
        errors.append(f"File not found: {path}")
        return rows, errors

    try:
        with open(path, newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)

            raw_headers  = [h.strip() for h in (reader.fieldnames or [])]
            header_map   = {}
            for raw in raw_headers:
                canonical = _COL_MAP.get(raw.lower())
                if canonical:
                    header_map[raw] = canonical

            missing = REQUIRED_CANONICAL - set(header_map.values())
            if missing:
                errors.append(f"CSV missing required columns: {missing}")
                return rows, errors

            seen_tickers = set()
            for i, row in enumerate(reader, start=2):
                mapped: dict = {}
                for raw_col, canonical in header_map.items():
                    mapped[canonical] = row.get(raw_col, "").strip()

                ticker = mapped.get("ticker", "").upper().strip().lstrip("$")
                if not ticker:
                    errors.append(f"Row {i}: empty ticker — skipped")
                    continue
                if ticker in seen_tickers:
                    errors.append(f"Row {i}: duplicate ticker '{ticker}' — skipped")
                    continue

                qty_raw = mapped.get("quantity", "")
                try:
                    qty = float(qty_raw)
                    if qty <= 0:
                        raise ValueError
                except (ValueError, TypeError):
                    errors.append(f"Row {i} ({ticker}): invalid quantity '{qty_raw}' — skipped")
                    continue

                buy_price_raw = mapped.get("buy_price", "")
                try:
                    buy_price = float(buy_price_raw) if buy_price_raw else None
                except ValueError:
                    buy_price = None

                seen_tickers.add(ticker)
                rows.append({
                    "ticker":        ticker,
                    "sector_csv":    mapped.get("sector", "Unknown"),
                    "purchase_date": mapped.get("purchase_date", ""),
                    "quantity":      qty,
                    "buy_price":     buy_price,
                })

    except Exception as exc:
        errors.append(f"Failed to read CSV: {exc}")

    log.info("CSV loaded: %d valid rows, %d error(s) from '%s'", len(rows), len(errors), path)
    return rows, errors


# ── Action colour codes (terminal) ────────────────────────────────────────────
_ACTION_DISPLAY = {
    "STRONG BUY":  "STRONG BUY  ▲▲",
    "BUY":         "BUY         ▲",
    "HOLD":        "HOLD        —",
    "REDUCE":      "REDUCE      ▼",
    "PARTIAL SELL":"PART. SELL  ▼",
    "SELL":        "SELL        ▼▼",
    "STRONG SELL": "STRONG SELL ▼▼",
}

_CONFIDENCE_DISPLAY = {
    "HIGH":   "★★★",
    "MEDIUM": "★★☆",
    "LOW":    "★☆☆",
}


def print_report_table_v2(recommendations: List[dict]) -> None:
    """Print the v2 formatted terminal table with trend, allocation, confidence columns."""
    headers = [
        "Ticker", "Sector", "Buy $", "Cur $", "Ret %",
        "Sentiment", "Trend", "Alloc", "Score", "Conf", "Action",
    ]
    rows = []
    for r in recommendations:
        action_str = _ACTION_DISPLAY.get(r.get("action", "HOLD"), r.get("action", "HOLD"))
        conf_str   = _CONFIDENCE_DISPLAY.get(r.get("confidence", "MEDIUM"), "★★☆")
        rows.append([
            r["ticker"],
            (r.get("sector", "")[:14]),
            f"${r['buy_price']:.2f}"     if r.get("buy_price")     else "N/A",
            f"${r['current_price']:.2f}" if r.get("current_price") else "N/A",
            f"{r['return_pct']:+.1f}%"   if r.get("return_pct") is not None else "N/A",
            r.get("sentiment", "—")[:14],
            r.get("trend_label", r.get("trend", "—")),
            r.get("allocation_status", "—")[:12],
            f"{r['score']:.0f}"          if r.get("score") is not None else "—",
            conf_str,
            action_str,
        ])

    print("\n" + "=" * 110)
    print("  NEXUS AI — INTELLIGENT PORTFOLIO MANAGER REPORT")
    print("=" * 110)
    print(tabulate(rows, headers=headers, tablefmt="rounded_outline"))
    print()


def print_portfolio_summary_v2(
    summary:            dict,
    current_allocation: Dict[str, float],
    market_sentiment:   str,
) -> None:
    """Print the enhanced portfolio summary with sector breakdown and top movers."""
    invested    = summary.get("total_invested", 0)
    current_val = summary.get("current_value", 0)
    port_ret    = summary.get("portfolio_return_pct", 0)
    risk        = summary.get("risk_level", "Medium")
    cash_pct    = summary.get("cash_allocation_pct", 10.0)
    ac          = summary.get("action_counts", {})

    print("=" * 110)
    print("  PORTFOLIO SUMMARY")
    print("-" * 110)
    print(f"  Total Invested     : ${invested:>12,.2f}")
    print(f"  Current Value      : ${current_val:>12,.2f}")
    print(f"  Portfolio Return   : {port_ret:>+.2f}%")
    print(f"  Market Sentiment   : {market_sentiment}")
    print(f"  Portfolio Risk     : {risk}")
    print(f"  Recommended Cash   : {cash_pct:.0f}%")
    print()

    # Action distribution
    print("  SIGNALS:")
    for action, count in ac.items():
        if count:
            bar = "█" * count
            print(f"    {action:<12} {bar} ({count})")
    print()

    # Sector allocation table
    sector_data = summary.get("sector_breakdown", {})
    if sector_data:
        print("  SECTOR BREAKDOWN:")
        sec_rows = []
        for sec, info in sector_data.items():
            sec_rows.append([
                sec[:22],
                f"{info.get('allocation_pct', 0):.1f}%",
                f"${info.get('current_value', 0):,.2f}",
                f"{info.get('avg_return_pct', 0):+.1f}%",
                info.get("sentiment", "—")[:15],
            ])
        print(tabulate(
            sec_rows,
            headers=["Sector", "Alloc %", "Value", "Avg Ret", "Sentiment"],
            tablefmt="simple",
        ))
        print()

    # Top gainers
    gainers = summary.get("top_gainers", [])
    if gainers:
        print("  TOP GAINERS:")
        for g in gainers:
            print(f"    {g['ticker']:<6}  {g['return_pct']:>+.1f}%")
        print()

    # Top losers
    losers = summary.get("top_losers", [])
    if losers:
        print("  TOP LOSERS:")
        for l in losers:
            print(f"    {l['ticker']:<6}  {l['return_pct']:>+.1f}%")

    print("=" * 110)


# ── Legacy table (kept for backward compatibility) ────────────────────────────

def print_report_table(recommendations: List[dict]) -> None:
    """Legacy v1 table — BUY/SELL/HOLD only."""
    headers = [
        "Ticker", "Sector", "Buy $", "Cur $", "Return %",
        "Sentiment", "Strength", "Score", "Action",
    ]
    rows = []
    for r in recommendations:
        rows.append([
            r["ticker"],
            r.get("sector", "")[:16],
            f"${r['buy_price']:.2f}"     if r.get("buy_price")     else "N/A",
            f"${r['current_price']:.2f}" if r.get("current_price") else "N/A",
            f"{r['return_pct']:+.1f}%"   if r.get("return_pct") is not None else "N/A",
            r.get("sentiment", "—"),
            r.get("strength",  "—"),
            f"{r['score']:.0f}"          if r.get("score") is not None else "—",
            r.get("action", "—"),
        ])

    print("\n" + "=" * 85)
    print("  NEXUS AI — PORTFOLIO REBALANCING REPORT")
    print("=" * 85)
    print(tabulate(rows, headers=headers, tablefmt="rounded_outline"))

    buys     = sum(1 for r in recommendations if r.get("action") == "BUY")
    sells    = sum(1 for r in recommendations if r.get("action") == "SELL")
    holds    = sum(1 for r in recommendations if r.get("action") == "HOLD")
    total    = sum(r.get("current_value", 0) for r in recommendations)
    invested = sum(r.get("investment_value", 0) for r in recommendations)
    port_return = ((total - invested) / invested * 100) if invested else 0.0

    print(f"\n  Holdings         : {len(recommendations)}")
    print(f"  Total Invested   : ${invested:,.2f}")
    print(f"  Current Value    : ${total:,.2f}")
    print(f"  Portfolio Return : {port_return:+.2f}%")
    print(f"  Signals          : BUY={buys}  SELL={sells}  HOLD={holds}")
    print("=" * 85)


# ── File export helpers ───────────────────────────────────────────────────────

def export_json(data: dict, path: str) -> None:
    """Save a dict as pretty-printed JSON."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    log.info("JSON saved → %s", path)


def export_csv(rows: List[dict], path: str) -> None:
    """Save a list of dicts as CSV."""
    if not rows:
        return
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    log.info("CSV  saved → %s", path)


def print_explanations(explanations: List[str]) -> None:
    """Print per-stock AI explanations with wrapping."""
    if not explanations:
        return
    print("\n  AI EXPLANATIONS (per stock)")
    print("-" * 70)
    for line in explanations:
        words = line.split()
        out   = "  "
        for word in words:
            if len(out) + len(word) + 1 > 82:
                print(out)
                out = "  " + word + " "
            else:
                out += word + " "
        if out.strip():
            print(out)
    print()
