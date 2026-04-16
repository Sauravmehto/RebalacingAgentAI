"""
graph.py — All 11 LangGraph node functions + StateGraph assembly (v2)

Node flow:
  START
  → load_portfolio
  → analyze_portfolio
  → gather_data
  → trend_analysis       [NEW]
  → fetch_news
  → analyze_sentiment
  → allocation_check     [NEW]
  → analyze_stock
  → rebalance_portfolio
  → generate_output
  → explain_results
  → END
"""

import logging
import os
from typing import Dict, List

from langchain_anthropic import ChatAnthropic
from langgraph.graph import StateGraph, START, END
from typing_extensions import TypedDict

from tools.data_fetch import enrich_ticker
from tools.news import build_sector_news
from tools.trend import build_ticker_trends
from tools.scoring import (
    calculate_score_v2,
    compute_capital_flows,
    compute_portfolio_summary_v2,
    compute_risk_score,
    estimated_flow_usd_for_action,
    get_allocation_score,
    label_strength,
    rebalance_decision_v2,
    SELL_ACTION_TYPES,
)
from tools.sentiment import (
    build_scenario_summary,
    classify_sentiments,
    compute_market_sentiment,
    generate_stock_explanations,
    sentiment_to_norm,
)
from utils import (
    export_csv,
    export_json,
    load_portfolio_csv,
    print_explanations,
    print_report_table_v2,
    print_portfolio_summary_v2,
)

log = logging.getLogger(__name__)

# ── Shared LLM instance (injected at runtime) ─────────────────────────────────
_llm: ChatAnthropic = None   # set by build_graph()

# ── Target allocation configuration ──────────────────────────────────────────
# Sectors not listed here fall under "Others".
# Values are percentages (must sum to 100).
TARGET_ALLOCATION: Dict[str, float] = {
    "Technology":         30.0,
    "ETF":                30.0,
    "Financial Services": 20.0,
    "Others":             20.0,
}

# ±N% before a sector is flagged as Overweight / Underweight
ALLOCATION_TOLERANCE: float = 5.0


# ══════════════════════════════════════════════════════════════════════════════
# STATE
# ══════════════════════════════════════════════════════════════════════════════

class AgentState(TypedDict):
    csv_path:           str
    portfolio:          List[dict]           # raw cleaned rows from CSV
    analyzed:           List[dict]           # + total_investment, position_size_pct
    market_data:        List[dict]           # + current_price, sector, return_pct
    trends:             Dict[str, dict]      # {ticker: {trend_7d, trend_30d, trend_label, trend_score}}
    news:               Dict[str, List[str]] # {sector: [headlines]}
    sentiments:         Dict[str, str]       # {sector: 5-level label}
    sentiment_scores:   Dict[str, float]     # {sector: normalised 0-1}
    market_sentiment:   str                  # overall market label
    current_allocation: Dict[str, float]     # {sector: actual_%}
    allocation_status:  Dict[str, str]       # {sector: Overweight/Underweight/Neutral}
    cash_pct:           float                # recommended cash reserve %
    scored_stocks:      List[dict]           # + sentiment, strength, score, trend_label
    recommendations:    List[dict]           # + action, reason, confidence
    output:             Dict                 # final JSON report dict
    explanations:       List[str]            # one sentence per stock
    errors:             List[str]
    # Optional rebalance scenario (news-aware run)
    custom_prompt:      str                  # user scenario text; may be ""
    selected_headlines: List[str]            # user-picked headline strings; may be []


# ══════════════════════════════════════════════════════════════════════════════
# NODE 1 — load_portfolio
# ══════════════════════════════════════════════════════════════════════════════

def load_portfolio(state: AgentState) -> AgentState:
    """Read and validate the CSV file."""
    log.info("── Node 1: load_portfolio ──")
    rows, errors = load_portfolio_csv(state["csv_path"])

    if not rows:
        log.error("No valid rows found in CSV — pipeline will abort at generate_output")

    return {**state, "portfolio": rows, "errors": errors}


# ══════════════════════════════════════════════════════════════════════════════
# NODE 2 — analyze_portfolio
# ══════════════════════════════════════════════════════════════════════════════

def analyze_portfolio(state: AgentState) -> AgentState:
    """
    Compute portfolio-level statistics using raw CSV data only
    (no live prices yet — uses quantity as proxy weight).
    """
    log.info("── Node 2: analyze_portfolio ──")
    portfolio = state["portfolio"]

    if not portfolio:
        return {**state, "analyzed": []}

    total_qty = sum(p["quantity"] for p in portfolio)

    analyzed = []
    for stock in portfolio:
        qty          = stock["quantity"]
        position_pct = round(qty / total_qty * 100, 2) if total_qty else 0.0

        analyzed.append({**stock, "position_size_pct": position_pct})
        log.info("  %-6s qty=%.0f  position_size_pct=%.1f%%",
                 stock["ticker"], qty, position_pct)

    return {**state, "analyzed": analyzed}


# ══════════════════════════════════════════════════════════════════════════════
# NODE 3 — gather_data
# ══════════════════════════════════════════════════════════════════════════════

def gather_data(state: AgentState) -> AgentState:
    """
    Fetch live prices and sector info for every ticker via yfinance.
    Reconstructs buy_price from purchase_date when CSV Price column is blank.
    """
    log.info("── Node 3: gather_data ──")
    market_data = []
    errors      = list(state.get("errors", []))

    for stock in state["analyzed"]:
        ticker = stock["ticker"]
        log.info("  Fetching data for %s …", ticker)
        try:
            enriched = enrich_ticker(
                ticker        = ticker,
                purchase_date = stock.get("purchase_date", ""),
                quantity      = stock["quantity"],
                buy_price_csv = stock.get("buy_price"),
            )
            market_data.append({**stock, **enriched})
        except Exception as exc:
            msg = f"{ticker}: data fetch failed ({exc})"
            log.error(msg)
            errors.append(msg)
            market_data.append({
                **stock,
                "current_price":    0.0,
                "buy_price":        stock.get("buy_price") or 0.0,
                "return_pct":       0.0,
                "current_value":    0.0,
                "investment_value": 0.0,
                "sector":           stock.get("sector_csv", "Unknown"),
            })

    # Re-compute position_size_pct now that we have real dollar values
    total_value = sum(s.get("current_value", 0) for s in market_data)
    for s in market_data:
        s["position_size_pct"] = (
            round(s.get("current_value", 0) / total_value * 100, 2)
            if total_value else 0.0
        )

    log.info("  Enriched %d tickers. Total portfolio value: $%.2f",
             len(market_data), total_value)
    return {**state, "market_data": market_data, "errors": errors}


# ══════════════════════════════════════════════════════════════════════════════
# NODE 4 — trend_analysis  [NEW]
# ══════════════════════════════════════════════════════════════════════════════

def trend_analysis(state: AgentState) -> AgentState:
    """
    Fetch 7-day and 30-day price history for every ticker.
    Classify each as Uptrend / Downtrend / Sideways.
    Produces a trend_score [0, 1] per ticker used in the composite score.
    """
    log.info("── Node 4: trend_analysis ──")
    tickers = [s["ticker"] for s in state["market_data"]]
    trends  = build_ticker_trends(tickers)
    return {**state, "trends": trends}


# ══════════════════════════════════════════════════════════════════════════════
# NODE 5 — fetch_news
# ══════════════════════════════════════════════════════════════════════════════

def fetch_news(state: AgentState) -> AgentState:
    """
    Fetch recent news headlines grouped by sector.

    Source priority (resolved inside build_sector_news):
      1. Event Registry  — if EVENT_REGISTRY_API_KEY is set
      2. Finnhub         — if FINNHUB_API_KEY is set
      3. Mock headlines  — always available as final fallback
    """
    log.info("── Node 5: fetch_news ──")
    finnhub_key = os.getenv("FINNHUB_API_KEY", "")

    ticker_sector_pairs = [
        (s["ticker"], s.get("sector") or s.get("sector_csv", "Unknown"))
        for s in state["market_data"]
    ]

    # build_sector_news reads EVENT_REGISTRY_API_KEY from env itself;
    # pass Finnhub key for backward compatibility.
    news = build_sector_news(ticker_sector_pairs, api_key=finnhub_key)
    return {**state, "news": news}


# ══════════════════════════════════════════════════════════════════════════════
# NODE 6 — analyze_sentiment
# ══════════════════════════════════════════════════════════════════════════════

def analyze_sentiment(state: AgentState) -> AgentState:
    """
    Call Claude to classify each sector's sentiment at 5-level intensity.
    Also computes the normalised numeric score per sector.
    """
    log.info("── Node 6: analyze_sentiment ──")
    sentiments = classify_sentiments(
        state["news"],
        _llm,
        scenario_prompt=state.get("custom_prompt", ""),
        extra_headlines=state.get("selected_headlines") or [],
    )

    sentiment_scores: Dict[str, float] = {}
    for sector, label in sentiments.items():
        norm = sentiment_to_norm(label)
        sentiment_scores[sector] = norm
        log.info("  %-30s → %-15s (norm=%.2f)", sector, label, norm)

    return {**state, "sentiments": sentiments, "sentiment_scores": sentiment_scores}


# ══════════════════════════════════════════════════════════════════════════════
# NODE 7 — allocation_check  [NEW]
# ══════════════════════════════════════════════════════════════════════════════

def allocation_check(state: AgentState) -> AgentState:
    """
    Compute current sector allocation from live portfolio values.
    Compare to TARGET_ALLOCATION and flag each sector as
    Overweight / Underweight / Neutral.
    Also computes the overall market sentiment and recommended cash %.
    """
    log.info("── Node 7: allocation_check ──")
    market_data = state["market_data"]
    total_value = sum(s.get("current_value", 0) for s in market_data)

    # ── Compute current allocation per sector ─────────────────────────────────
    sector_values: Dict[str, float] = {}
    for s in market_data:
        sec = s.get("sector") or s.get("sector_csv", "Unknown")
        sector_values[sec] = sector_values.get(sec, 0) + s.get("current_value", 0)

    current_allocation: Dict[str, float] = {}
    for sec, val in sector_values.items():
        current_allocation[sec] = round(val / total_value * 100, 2) if total_value else 0.0

    # ── Compare against target ────────────────────────────────────────────────
    # Sectors not in TARGET_ALLOCATION are grouped under "Others"
    allocation_status: Dict[str, str] = {}
    for sec, actual_pct in current_allocation.items():
        # Find target — use Others for unknown sectors
        target_key    = sec if sec in TARGET_ALLOCATION else "Others"
        target_pct    = TARGET_ALLOCATION.get(target_key, TARGET_ALLOCATION.get("Others", 20.0))
        diff          = actual_pct - target_pct

        if diff > ALLOCATION_TOLERANCE:
            status = "Overweight"
        elif diff < -ALLOCATION_TOLERANCE:
            status = "Underweight"
        else:
            status = "Neutral"

        allocation_status[sec] = status
        log.info(
            "  %-25s  actual=%.1f%%  target=%.1f%%  diff=%+.1f%%  → %s",
            sec, actual_pct, target_pct, diff, status,
        )

    # ── Overall market sentiment and cash recommendation ──────────────────────
    market_sentiment = compute_market_sentiment(state["sentiments"])
    cash_pct = 20.0 if market_sentiment in ("Negative", "Strong Negative") else 10.0

    log.info("  Market sentiment: %s → recommended cash reserve: %.0f%%",
             market_sentiment, cash_pct)

    return {
        **state,
        "current_allocation": current_allocation,
        "allocation_status":  allocation_status,
        "market_sentiment":   market_sentiment,
        "cash_pct":           cash_pct,
    }


# ══════════════════════════════════════════════════════════════════════════════
# NODE 8 — analyze_stock
# ══════════════════════════════════════════════════════════════════════════════

def analyze_stock(state: AgentState) -> AgentState:
    """
    Attach sentiment, trend, allocation signals to each stock.
    Compute the 5-factor composite score using calculate_score_v2.
    """
    log.info("── Node 8: analyze_stock ──")
    scored = []

    for stock in state["market_data"]:
        ticker    = stock["ticker"]
        sector    = stock.get("sector") or stock.get("sector_csv", "Unknown")
        ret_pct   = stock.get("return_pct", 0.0)
        pos_pct   = stock.get("position_size_pct", 0.0)

        # Pull values from upstream nodes
        sentiment        = state["sentiments"].get(sector, "Neutral")
        sentiment_norm   = state["sentiment_scores"].get(sector, 0.5)
        alloc_status     = state["allocation_status"].get(sector, "Neutral")
        trend_info       = state["trends"].get(ticker, {})
        t_score          = trend_info.get("trend_score", 0.5)
        trend_label      = trend_info.get("trend_label", "Sideways")

        # Derived factor scores
        alloc_score  = get_allocation_score(alloc_status)
        risk_score   = compute_risk_score(ret_pct)
        strength     = label_strength(ret_pct)

        score = calculate_score_v2(
            return_pct       = ret_pct,
            sentiment_norm   = sentiment_norm,
            trend_score      = t_score,
            allocation_score = alloc_score,
            risk_score       = risk_score,
        )

        log.info(
            "  %-6s  ret=%+.1f%%  sent=%-16s  trend=%-10s  alloc=%-12s  score=%.1f",
            ticker, ret_pct, sentiment, trend_label, alloc_status, score,
        )

        scored.append({
            **stock,
            "sector":            sector,
            "sentiment":         sentiment,
            "sentiment_norm":    sentiment_norm,
            "strength":          strength,
            "trend_label":       trend_label,
            "trend_7d":          trend_info.get("trend_7d", "Sideways"),
            "trend_30d":         trend_info.get("trend_30d", "Sideways"),
            "trend_score":       t_score,
            "allocation_status": alloc_status,
            "score":             score,
        })

    return {**state, "scored_stocks": scored}


# ══════════════════════════════════════════════════════════════════════════════
# NODE 9 — rebalance_portfolio
# ══════════════════════════════════════════════════════════════════════════════

def rebalance_portfolio(state: AgentState) -> AgentState:
    """Apply v2 BUY/SELL/HOLD rules with profit booking, stop loss, and confidence."""
    log.info("── Node 9: rebalance_portfolio ──")
    recommendations = []

    for stock in state["scored_stocks"]:
        action, reason, confidence = rebalance_decision_v2(
            return_pct        = stock.get("return_pct", 0.0),
            sentiment         = stock.get("sentiment", "Neutral"),
            trend_label       = stock.get("trend_label", "Sideways"),
            allocation_status = stock.get("allocation_status", "Neutral"),
            score             = stock.get("score", 50.0),
        )
        log.info("  %-6s → %-12s  [%s]  %s",
                 stock["ticker"], action, confidence, reason)
        recommendations.append({
            **stock,
            "action":     action,
            "reason":     reason,
            "confidence": confidence,
        })

    return {**state, "recommendations": recommendations}


# ══════════════════════════════════════════════════════════════════════════════
# NODE 10 — generate_output
# ══════════════════════════════════════════════════════════════════════════════

def generate_output(state: AgentState) -> AgentState:
    """
    Build the final JSON report, print the table to terminal,
    and export CSV + JSON to nexus_agent/output/.
    """
    log.info("── Node 10: generate_output ──")
    recs = state["recommendations"]

    if not recs:
        log.warning("No recommendations to output.")
        return {**state, "output": {}}

    cash_pct = state.get("cash_pct", 10.0)
    summary = compute_portfolio_summary_v2(
        stocks     = recs,
        sentiments = state["sentiments"],
        cash_pct   = cash_pct,
    )
    summary["capital_flows"] = compute_capital_flows(recs, cash_pct)

    print_report_table_v2(recs)
    print_portfolio_summary_v2(summary, state["current_allocation"], state["market_sentiment"])

    output_report = {
        "portfolio_summary": summary,
        "market_sentiment":  state.get("market_sentiment", "Neutral"),
        "sector_sentiments": state["sentiments"],
        "current_allocation": state.get("current_allocation", {}),
        "target_allocation":  TARGET_ALLOCATION,
        "stocks": [
            {
                "symbol":            r["ticker"],
                "sector":            r.get("sector", ""),
                "buy_price":         r.get("buy_price", 0),
                "current_price":     r.get("current_price", 0),
                "current_value":     r.get("current_value", 0),
                "return_pct":        r.get("return_pct", 0),
                "sentiment":         r.get("sentiment", "Neutral"),
                "strength":          r.get("strength", "Neutral"),
                "trend":             r.get("trend_label", "Sideways"),
                "trend_7d":          r.get("trend_7d", "Sideways"),
                "trend_30d":         r.get("trend_30d", "Sideways"),
                "allocation_status": r.get("allocation_status", "Neutral"),
                "score":             r.get("score", 0),
                "action":            r.get("action", "HOLD"),
                "confidence":        r.get("confidence", "MEDIUM"),
                "reason":            r.get("reason", ""),
                "priority_sell":     r.get("action", "HOLD") in SELL_ACTION_TYPES,
                "estimated_flow_usd": estimated_flow_usd_for_action(
                    r.get("action", "HOLD"),
                    float(r.get("current_value", 0) or 0),
                ),
            }
            for r in recs
        ],
    }

    out_dir  = os.path.join(os.path.dirname(__file__), "..", "output")
    json_out = os.path.join(out_dir, "rebalancing_report.json")
    csv_out  = os.path.join(out_dir, "rebalancing_report.csv")

    export_json(output_report, json_out)
    export_csv(output_report["stocks"], csv_out)

    return {**state, "output": output_report}


# ══════════════════════════════════════════════════════════════════════════════
# NODE 11 — explain_results
# ══════════════════════════════════════════════════════════════════════════════

def explain_results(state: AgentState) -> AgentState:
    """Ask Claude for a one-sentence explanation per stock using all v2 signals."""
    log.info("── Node 11: explain_results ──")
    explanations = generate_stock_explanations(
        state["recommendations"],
        _llm,
        scenario_summary=build_scenario_summary(
            state.get("custom_prompt", ""),
            state.get("selected_headlines") or [],
        ),
    )
    print_explanations(explanations)
    return {**state, "explanations": explanations}


# ══════════════════════════════════════════════════════════════════════════════
# GRAPH BUILDER
# ══════════════════════════════════════════════════════════════════════════════

def build_graph(llm: ChatAnthropic):
    """Compile and return the LangGraph agent (v2, 11 nodes)."""
    global _llm
    _llm = llm

    builder = StateGraph(AgentState)

    builder.add_node("load_portfolio",      load_portfolio)
    builder.add_node("analyze_portfolio",   analyze_portfolio)
    builder.add_node("gather_data",         gather_data)
    builder.add_node("trend_analysis",      trend_analysis)
    builder.add_node("fetch_news",          fetch_news)
    builder.add_node("analyze_sentiment",   analyze_sentiment)
    builder.add_node("allocation_check",    allocation_check)
    builder.add_node("analyze_stock",       analyze_stock)
    builder.add_node("rebalance_portfolio", rebalance_portfolio)
    builder.add_node("generate_output",     generate_output)
    builder.add_node("explain_results",     explain_results)

    builder.add_edge(START,                  "load_portfolio")
    builder.add_edge("load_portfolio",       "analyze_portfolio")
    builder.add_edge("analyze_portfolio",    "gather_data")
    builder.add_edge("gather_data",          "trend_analysis")
    builder.add_edge("trend_analysis",       "fetch_news")
    builder.add_edge("fetch_news",           "analyze_sentiment")
    builder.add_edge("analyze_sentiment",    "allocation_check")
    builder.add_edge("allocation_check",     "analyze_stock")
    builder.add_edge("analyze_stock",        "rebalance_portfolio")
    builder.add_edge("rebalance_portfolio",  "generate_output")
    builder.add_edge("generate_output",      "explain_results")
    builder.add_edge("explain_results",      END)

    return builder.compile()
