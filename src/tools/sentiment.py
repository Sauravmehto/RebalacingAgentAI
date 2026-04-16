"""
sentiment.py — Claude-powered sector sentiment classifier (v2).

Returns 5-level intensity labels per sector:
  Strong Positive / Positive / Neutral / Negative / Strong Negative

Maps to numeric scores:
  Strong Positive = +2,  Positive = +1,  Neutral = 0,
  Negative = -1,  Strong Negative = -2

Normalised to [0, 1] for use in the scoring formula: (raw + 2) / 4
"""

import json
import logging
from typing import Dict, List, Optional

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage

log = logging.getLogger(__name__)

VALID_LABELS = {
    "Strong Positive",
    "Positive",
    "Neutral",
    "Negative",
    "Strong Negative",
}

SENTIMENT_SCORES: Dict[str, int] = {
    "Strong Positive": 2,
    "Positive":        1,
    "Neutral":         0,
    "Negative":       -1,
    "Strong Negative":-2,
}

# Keyword sets for fallback heuristic
_POS_WORDS = [
    "growth", "beat", "surge", "record", "strong", "rally",
    "boost", "rises", "approval", "rebound", "inflows", "outperforms",
    "upgrade", "breakout", "accelerates", "expands", "gains",
]
_NEG_WORDS = [
    "slow", "decline", "fall", "risk", "loss", "cut", "down",
    "miss", "weak", "stress", "contraction", "delinquencies", "headwind",
    "downgrade", "selloff", "collapse", "plunge", "warning", "concern",
]


def sentiment_to_norm(label: str) -> float:
    """Convert a sentiment label to a normalised [0, 1] score for the formula."""
    raw = SENTIMENT_SCORES.get(label, 0)
    return (raw + 2) / 4.0


def _keyword_sentiment(headlines: List[str]) -> str:
    """
    Heuristic fallback: count positive vs negative keywords in the headlines.
    Returns a 5-level label based on the magnitude of the difference.
    """
    text = " ".join(headlines).lower()
    pos  = sum(text.count(w) for w in _POS_WORDS)
    neg  = sum(text.count(w) for w in _NEG_WORDS)
    diff = pos - neg

    if diff >= 3:
        return "Strong Positive"
    if diff >= 1:
        return "Positive"
    if diff <= -3:
        return "Strong Negative"
    if diff <= -1:
        return "Negative"
    return "Neutral"


def classify_sentiments(
    sector_news: Dict[str, List[str]],
    llm: ChatAnthropic,
    *,
    scenario_prompt: str = "",
    extra_headlines: Optional[List[str]] = None,
) -> Dict[str, str]:
    """
    Classify sentiment intensity for every sector in one Claude call.

    Returns {sector: label} where label is one of the five VALID_LABELS.
    Falls back to keyword heuristic per sector on any LLM failure.

    Optional scenario_prompt / extra_headlines are appended as thematic context
    for news-aware rebalancing (user scenario + selected articles).
    """
    if not sector_news:
        return {}

    blocks = []
    for sector, headlines in sector_news.items():
        bullets = "\n".join(f"  - {h}" for h in headlines)
        blocks.append(f"{sector}:\n{bullets}")

    scenario_block = ""
    xh = extra_headlines or []
    sp = (scenario_prompt or "").strip()
    if sp or xh:
        parts = []
        if sp:
            parts.append(
                "Investor scenario / focus (treat as additional market-wide thematic context):\n"
                + sp
            )
        if xh:
            parts.append(
                "User-selected headline(s):\n"
                + "\n".join(f"  - {h}" for h in xh)
            )
        scenario_block = (
            "\n\n--- Additional context ---\n"
            + "\n\n".join(parts)
            + "\n\nWeigh this thematic context together with the sector headlines when "
            "assigning labels.\n"
        )

    prompt = (
        "Below are recent news headlines grouped by market sector.\n\n"
        + "\n\n".join(blocks)
        + scenario_block
        + "\n"
        "For EACH sector, classify the overall sentiment intensity as EXACTLY one of:\n"
        "  Strong Positive, Positive, Neutral, Negative, Strong Negative\n\n"
        "Guidelines:\n"
        "  - Strong Positive: multiple clearly bullish signals, strong momentum\n"
        "  - Positive: generally good news, mild optimism\n"
        "  - Neutral: mixed or unclear signals\n"
        "  - Negative: generally bad news, mild concern\n"
        "  - Strong Negative: multiple clearly bearish signals, serious risk\n\n"
        "Reply ONLY with a valid JSON object. Example:\n"
        '{"Technology": "Strong Positive", "Energy": "Neutral", "Financials": "Negative"}'
    )

    try:
        response = llm.invoke([
            SystemMessage(content=(
                "You are a senior financial news sentiment analyst. "
                "Assess sentiment INTENSITY carefully. "
                "Reply only with a JSON object mapping sector names to one of: "
                "Strong Positive, Positive, Neutral, Negative, Strong Negative."
            )),
            HumanMessage(content=prompt),
        ])
        raw = response.content.strip()

        if raw.startswith("```"):
            parts = raw.split("```")
            raw   = parts[1] if len(parts) > 1 else raw
            if raw.startswith("json"):
                raw = raw[4:]

        parsed: Dict[str, str] = json.loads(raw)

        result: Dict[str, str] = {}
        for sector, label in parsed.items():
            # Normalise capitalisation — "strong positive" → "Strong Positive"
            clean = " ".join(w.capitalize() for w in str(label).strip().split())
            result[sector] = clean if clean in VALID_LABELS else "Neutral"

        # Fill any missing sectors with keyword fallback
        for sector, headlines in sector_news.items():
            if sector not in result:
                log.warning(
                    "Sector '%s' missing from LLM response — using keyword heuristic", sector
                )
                result[sector] = _keyword_sentiment(headlines)

        log.info("Sentiments (v2): %s", result)
        return result

    except Exception as exc:
        log.warning("LLM sentiment classification failed (%s) — falling back to keywords", exc)
        return {s: _keyword_sentiment(h) for s, h in sector_news.items()}


def compute_market_sentiment(sentiments: Dict[str, str]) -> str:
    """
    Aggregate all sector sentiments into a single overall market sentiment label.

    Averages the numeric scores across all sectors and maps back to a label.
    """
    if not sentiments:
        return "Neutral"

    scores = [SENTIMENT_SCORES.get(label, 0) for label in sentiments.values()]
    avg    = sum(scores) / len(scores)

    if avg >= 1.5:
        return "Strong Positive"
    if avg >= 0.5:
        return "Positive"
    if avg <= -1.5:
        return "Strong Negative"
    if avg <= -0.5:
        return "Negative"
    return "Neutral"


def build_scenario_summary(
    custom_prompt: str,
    selected_headlines: Optional[List[str]] = None,
    *,
    max_prompt_chars: int = 600,
    max_headlines: int = 6,
    max_headline_chars: int = 220,
) -> str:
    """Short text for explanation prompts (user scenario + selected news)."""
    parts: List[str] = []
    s = (custom_prompt or "").strip()
    if s:
        parts.append(f"Scenario: {s[:max_prompt_chars]}")
    for h in (selected_headlines or [])[:max_headlines]:
        t = str(h).strip()
        if t:
            parts.append(f"Headline: {t[:max_headline_chars]}")
    return " | ".join(parts) if parts else ""


def generate_stock_explanations(
    recommendations: List[dict],
    llm: ChatAnthropic,
    *,
    scenario_summary: str = "",
) -> List[str]:
    """
    Generate one explanatory sentence per stock in a single Claude call.

    Returns a list of strings in the same order as `recommendations`.
    Each string is formatted: "TICKER: <reason sentence>."

    The prompt now includes trend, allocation status, and confidence so
    Claude can produce richer, more specific reasoning.
    """
    if not recommendations:
        return []

    lines = []
    for r in recommendations:
        lines.append(
            f"{r['ticker']} ({r.get('sector','?')}): "
            f"action={r['action']}, return={r.get('return_pct', 0):+.1f}%, "
            f"sentiment={r.get('sentiment','?')}, "
            f"trend={r.get('trend_label', r.get('trend', '?'))}, "
            f"allocation={r.get('allocation_status','?')}, "
            f"strength={r.get('strength','?')}, "
            f"score={r.get('score', 0):.0f}, "
            f"confidence={r.get('confidence','?')}"
        )

    prompt_body = (
        "For each stock below, write exactly ONE concise sentence explaining "
        "the recommended action. Mention the most decisive factor(s): "
        "return performance, sector sentiment intensity, price trend direction, "
        "portfolio allocation status, and confidence level where relevant.\n"
        "Format each line as: 'TICKER: <explanation>.'\n\n"
        + "\n".join(lines)
    )
    if (scenario_summary or "").strip():
        prompt_body = (
            "Optional rebalance context from the user (thematic / news focus):\n"
            + scenario_summary.strip()
            + "\n\n"
            + prompt_body
        )

    try:
        response = llm.invoke([
            SystemMessage(content=(
                "You are a senior portfolio analyst. "
                "Be concise, specific, and professional. "
                "One sentence per stock, starting with the ticker symbol. "
                "Reference the specific signals that drove the recommendation. "
                "If rebalance context is provided, you may briefly tie it in when relevant."
            )),
            HumanMessage(content=prompt_body),
        ])
        raw_lines = [l.strip() for l in response.content.strip().splitlines() if l.strip()]
        log.info("Generated %d stock explanations", len(raw_lines))
        return raw_lines

    except Exception as exc:
        log.warning("LLM explanation failed (%s) — using template fallback", exc)
        fallbacks = []
        for r in recommendations:
            trend   = r.get("trend_label", r.get("trend", "unknown trend"))
            alloc   = r.get("allocation_status", "neutral allocation")
            fallbacks.append(
                f"{r['ticker']}: Recommended {r['action']} based on "
                f"{r.get('sentiment','?').lower()} sentiment, {trend.lower()}, "
                f"{alloc.lower()} allocation, and "
                f"{r.get('return_pct', 0):+.1f}% return."
            )
        return fallbacks
