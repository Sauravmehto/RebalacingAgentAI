"""
news.py — News fetcher with three-tier source priority.

Source priority for company/sector news:
  1. Event Registry (newsapi.ai)  — if EVENT_REGISTRY_API_KEY is set
  2. Finnhub                      — if FINNHUB_API_KEY is set
  3. Built-in mock headlines      — always available as final fallback

Event Registry endpoint:
  POST https://eventregistry.org/api/v1/article/getArticles
  Body: { apiKey, keyword, dateStart, dateEnd, articlesCount, lang, ... }
  Response: data["articles"]["results"][*]["title"]

Finnhub endpoints (all free-tier):
  GET /api/v1/company-news   — per-ticker news for last N days
  GET /api/v1/news           — general market news by category
"""

import json
import logging
import os
from datetime import date, timedelta
from typing import Dict, List, Optional

import requests

log = logging.getLogger(__name__)

# ── API base URLs ─────────────────────────────────────────────────────────────
FINNHUB_BASE_URL      = "https://finnhub.io/api/v1"
EVENT_REGISTRY_URL    = "https://eventregistry.org/api/v1/article/getArticles"
TIMEOUT               = 12   # seconds

# ── Per-session caches ────────────────────────────────────────────────────────
_company_news_cache: Dict[str, List[dict]] = {}   # {ticker: [article, ...]}
_market_news_cache:  Optional[List[dict]]  = None
_er_cache:           Dict[str, List[str]]  = {}   # {ticker: [headline, ...]}

# Directory where raw JSON dumps are saved (created on first use)
_OUTPUT_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "output", "raw_news_json")
)


def _save_json(filename: str, data) -> None:
    """Write data as pretty-printed JSON to output/raw_news_json/<filename>."""
    os.makedirs(_OUTPUT_DIR, exist_ok=True)
    path = os.path.join(_OUTPUT_DIR, filename)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    log.debug("  [JSON saved] %s", path)

# ── Mock headlines (fallback when Finnhub is unavailable) ─────────────────────
_MOCK: Dict[str, List[str]] = {
    "technology": [
        "AI spending boom drives Big Tech to record-high earnings",
        "Semiconductor demand rebounds sharply on data-centre orders",
        "Cloud revenue growth accelerates as enterprise adoption widens",
        "Microsoft and Nvidia lead gains amid strong AI infrastructure build-out",
    ],
    "tech": [
        "AI spending boom drives Big Tech to record-high earnings",
        "Semiconductor demand rebounds on data-centre build-out",
        "Cloud revenue growth accelerates; margins expand across sector",
    ],
    "financial services": [
        "Banks report solid NII beat as rate environment remains supportive",
        "JPMorgan raises full-year guidance on loan growth and trading revenue",
        "Credit card delinquencies tick higher, signalling consumer stress at margin",
    ],
    "financials": [
        "Banks report solid NII beat on higher net interest income",
        "JPMorgan raises full-year guidance on strong trading revenue",
    ],
    "energy": [
        "Oil steadies above $80 after OPEC+ announces surprise output cut",
        "Exxon posts strong free cash flow on higher refining margins",
        "Renewable energy investment hits record globally, pressuring fossil margins",
    ],
    "consumer defensive": [
        "Staples sector outperforms as investors rotate to defensive names",
        "Procter & Gamble raises dividend amid stable household-goods demand",
    ],
    "consumer": [
        "Consumer confidence dips for third consecutive month",
        "Staples resilient; discretionary spending contracts amid rate pressures",
    ],
    "consumer cyclical": [
        "Auto sales miss estimates as high interest rates crimp affordability",
        "Discretionary spending contracts; inventory builds at major retailers",
    ],
    "industrials": [
        "Manufacturing PMI rebounds, signalling factory activity recovery",
        "Caterpillar and Honeywell cite strong infrastructure-driven backlog",
        "Supply chain normalisation boosts industrial margins across the board",
    ],
    "healthcare": [
        "FDA approves two breakthrough oncology therapies, boosting biotech",
        "Pharmaceutical M&A surges as large-caps seek pipeline assets",
    ],
    "etf": [
        "Broad equity ETFs see record inflows as institutional buying accelerates",
        "S&P 500 rallies; QQQ and SPY lead on renewed growth optimism",
        "ETF market hits $12 trillion AUM milestone driven by passive investing",
    ],
    "gold etf": [
        "Gold prices climb on safe-haven demand amid geopolitical uncertainty",
        "GLD sees inflows as investors hedge against inflation and dollar weakness",
    ],
    "communication services": [
        "Digital ad revenue recovers strongly; Meta and Alphabet beat estimates",
        "Streaming subscriber growth reaccelerates; content spending stabilises",
    ],
}

_DEFAULT_MOCK = [
    "{sector} sector shows mixed performance amid uncertain macro backdrop",
    "Analysts divided on {sector} near-term outlook as earnings season approaches",
]


def _mock_headlines(sector: str, max_results: int = 4) -> List[str]:
    key = sector.lower().strip()
    for k, v in _MOCK.items():
        if k == key or k in key or key in k:
            return v[:max_results]
    return [h.format(sector=sector) for h in _DEFAULT_MOCK]


# ══════════════════════════════════════════════════════════════════════════════
# Event Registry helpers
# ══════════════════════════════════════════════════════════════════════════════

def _event_registry_get(
    keyword:     str,
    api_key:     str,
    days:        int = 7,
    max_results: int = 10,
) -> List[dict]:
    """
    POST to Event Registry article search and return raw article list.

    Returns a list of article dicts with at least a 'title' field.
    Returns [] on any failure.
    """
    to_date   = date.today()
    from_date = to_date - timedelta(days=days)

    payload = {
        "apiKey":          api_key,
        "keyword":         keyword,
        "dateStart":       from_date.strftime("%Y-%m-%d"),
        "dateEnd":         to_date.strftime("%Y-%m-%d"),
        "articlesCount":   max_results,
        "resultType":      "articles",
        "articlesSortBy":  "date",
        "articlesSortByAsc": False,
        "lang":            "eng",
        "isDuplicateFilter": "skipDuplicates",
    }
    log.debug("  [ER] POST %s  keyword=%r  dateStart=%s",
              EVENT_REGISTRY_URL, keyword, from_date)
    try:
        resp = requests.post(EVENT_REGISTRY_URL, json=payload, timeout=TIMEOUT)
        log.debug("  [ER] status=%d", resp.status_code)
        if resp.status_code == 401:
            log.warning("  [ER] Invalid API key — check EVENT_REGISTRY_API_KEY")
            return []
        if resp.status_code == 429:
            log.warning("  [ER] Rate limit hit")
            return []
        resp.raise_for_status()
        data = resp.json()
        articles = data.get("articles", {}).get("results", [])
        log.debug("  [ER] returned %d articles for keyword=%r", len(articles), keyword)
        return articles
    except Exception as exc:
        log.warning("  [ER] request failed: %s", exc)
        return []


def fetch_company_news_er(
    ticker:      str,
    sector:      str,
    api_key:     str,
    days:        int = 7,
    max_results: int = 5,
) -> List[str]:
    """
    Fetch recent news headlines for a ticker via Event Registry.

    Searches with "{ticker} {sector}" keyword for better relevance.
    Results are cached per ticker per session.
    Returns a list of headline strings (empty list on failure).
    """
    cache_key = f"er_{ticker.upper()}"
    if cache_key in _er_cache:
        return _er_cache[cache_key][:max_results]

    # Build a keyword that combines the ticker and sector for relevance
    keyword   = f"{ticker} {sector}" if sector and sector != "Unknown" else ticker
    articles  = _event_registry_get(keyword, api_key, days=days,
                                    max_results=max_results * 2)

    headlines = [
        a["title"] for a in articles
        if a.get("title") and a["title"].strip()
    ]

    _er_cache[cache_key] = headlines
    log.info("  [ER] company-news: %s → %d headlines", ticker, len(headlines))
    _save_json(f"er_company_news_{ticker}.json", articles)

    if headlines:
        log.debug("  [ER] %s top headlines: %s", ticker, headlines[:max_results])

    return headlines[:max_results]


def fetch_general_news_er(
    api_key:     str,
    max_results: int = 10,
) -> List[str]:
    """
    Fetch general financial market news via Event Registry.
    Cached once per session.
    """
    cache_key = "er_general"
    if cache_key in _er_cache:
        return _er_cache[cache_key][:max_results]

    articles  = _event_registry_get(
        keyword="stock market finance investing",
        api_key=api_key,
        days=3,
        max_results=max_results * 2,
    )
    headlines = [
        a["title"] for a in articles
        if a.get("title") and a["title"].strip()
    ]
    _er_cache[cache_key] = headlines
    log.info("  [ER] general market-news: %d headlines", len(headlines))
    _save_json("er_market_news_general.json", articles)
    return headlines[:max_results]


# ══════════════════════════════════════════════════════════════════════════════
# Finnhub helpers
# ══════════════════════════════════════════════════════════════════════════════

def _finnhub_get(path: str, params: dict, api_key: str) -> Optional[dict | list]:
    """Generic GET against Finnhub API. Returns parsed JSON or None on error."""
    url = f"{FINNHUB_BASE_URL}{path}"
    safe_params = {k: v for k, v in params.items()}  # exclude token from log
    log.debug("  [HTTP GET] %s  params=%s", url, safe_params)
    try:
        resp = requests.get(
            url,
            params={**params, "token": api_key},
            timeout=TIMEOUT,
        )
        log.debug("  [HTTP] status=%d  content-length=%s",
                  resp.status_code, resp.headers.get("content-length", "?"))
        if resp.status_code == 429:
            log.warning("Finnhub rate limit hit for %s", path)
            return None
        resp.raise_for_status()
        data = resp.json()
        count = len(data) if isinstance(data, list) else "object"
        log.debug("  [JSON] %s returned %s items", path, count)
        return data
    except Exception as exc:
        log.warning("Finnhub %s failed: %s", path, exc)
        return None


def fetch_company_news(
    ticker:  str,
    api_key: str,
    days:    int = 5,
    max_results: int = 5,
) -> List[str]:
    """
    Fetch recent news headlines for a single ticker via Finnhub /company-news.

    Returns a list of headline strings (empty list on failure).
    Results cached per ticker per session.
    """
    cache_key = ticker.upper()
    if cache_key in _company_news_cache:
        articles = _company_news_cache[cache_key]
    else:
        to_date   = date.today()
        from_date = to_date - timedelta(days=days)
        data = _finnhub_get(
            "/company-news",
            {
                "symbol": ticker,
                "from":   from_date.strftime("%Y-%m-%d"),
                "to":     to_date.strftime("%Y-%m-%d"),
            },
            api_key,
        )
        articles = data if isinstance(data, list) else []
        _company_news_cache[cache_key] = articles
        log.info("  Finnhub company-news: %s → %d articles", ticker, len(articles))
        _save_json(f"company_news_{ticker}.json", articles)
        if articles:
            log.debug("  [RAW JSON sample for %s] first article keys: %s",
                      ticker, list(articles[0].keys()))
            log.debug("  [RAW JSON sample for %s] first article: %s",
                      ticker, {k: articles[0].get(k) for k in
                                ("headline", "source", "datetime", "url", "summary")
                                if k in articles[0]})

    headlines = [
        a["headline"] for a in articles
        if a.get("headline") and a["headline"].strip()
    ]
    log.debug("  [%s] %d/%d articles have valid headlines → keeping top %d: %s",
              ticker, len(headlines), len(articles), min(max_results, len(headlines)),
              headlines[:max_results])
    return headlines[:max_results]


def fetch_market_news(api_key: str, max_results: int = 8) -> List[str]:
    """
    Fetch general market news via Finnhub /news?category=general.
    Cached once per session.
    """
    global _market_news_cache
    if _market_news_cache is not None:
        return [a["headline"] for a in _market_news_cache if a.get("headline")][:max_results]

    data = _finnhub_get("/news", {"category": "general"}, api_key)
    _market_news_cache = data if isinstance(data, list) else []
    headlines = [a["headline"] for a in _market_news_cache if a.get("headline")]
    log.info("  Finnhub market-news: %d articles", len(_market_news_cache))
    _save_json("market_news_general.json", _market_news_cache)
    log.debug("  [market-news] top %d headlines: %s", max_results, headlines[:max_results])
    return headlines[:max_results]


# ══════════════════════════════════════════════════════════════════════════════
# Public API — called from graph.py nodes
# ══════════════════════════════════════════════════════════════════════════════

def fetch_ticker_news(
    ticker:     str,
    sector:     str,
    fh_key:     str = "",
    er_key:     str = "",
) -> List[str]:
    """
    Return up to 5 headlines for a ticker.

    Priority:
      1. Event Registry  (if er_key set)
      2. Finnhub         (if fh_key set)
      3. Mock headlines for the sector
    """
    if er_key and er_key not in ("YOUR_EVENT_REGISTRY_API_KEY", ""):
        headlines = fetch_company_news_er(ticker, sector, er_key)
        if headlines:
            return headlines

    if fh_key and fh_key not in ("YOUR_FINNHUB_API_KEY", ""):
        headlines = fetch_company_news(ticker, fh_key)
        if headlines:
            return headlines

    log.info("  Using mock headlines for %s (%s)", ticker, sector)
    return _mock_headlines(sector)


def build_sector_news(
    ticker_sector_pairs: List[tuple],   # [(ticker, sector), ...]
    api_key:             str = "",      # kept for backward compatibility (Finnhub key)
    max_per_sector:      int = 5,
) -> Dict[str, List[str]]:
    """
    Build a {sector: [headlines]} dict using a three-tier source priority.

    Priority per ticker:
      1. Event Registry  — richer, broader coverage
      2. Finnhub         — company-specific news
      3. Mock headlines  — always available as final fallback

    Sectors with < 2 headlines are topped up from general market news
    (Event Registry or Finnhub, whichever is active).
    """
    er_key = os.getenv("EVENT_REGISTRY_API_KEY", "").strip()
    fh_key = api_key or os.getenv("FINNHUB_API_KEY", "").strip()

    er_active = bool(er_key) and er_key not in ("YOUR_EVENT_REGISTRY_API_KEY", "")
    fh_active = bool(fh_key) and fh_key not in ("YOUR_FINNHUB_API_KEY", "")

    if er_active:
        log.info("  [build_sector_news] Primary source: Event Registry")
    elif fh_active:
        log.info("  [build_sector_news] Primary source: Finnhub (Event Registry key not set)")
    else:
        log.info("  [build_sector_news] No API keys set — using mock headlines")

    sector_headlines: Dict[str, List[str]] = {}

    if er_active or fh_active:
        log.info("  [build_sector_news] Fetching news for %d tickers …",
                 len(ticker_sector_pairs))

        for ticker, sector in ticker_sector_pairs:
            headlines: List[str] = []

            # ── Tier 1: Event Registry ────────────────────────────────────
            if er_active:
                headlines = fetch_company_news_er(ticker, sector, er_key)
                if headlines:
                    log.debug("  [ER bucket] %s (%s): %d headlines", ticker, sector, len(headlines))

            # ── Tier 2: Finnhub (if ER returned nothing) ──────────────────
            if not headlines and fh_active:
                headlines = fetch_company_news(ticker, fh_key)
                if headlines:
                    log.debug("  [FH bucket] %s (%s): %d headlines", ticker, sector, len(headlines))

            if headlines:
                bucket = sector_headlines.setdefault(sector, [])
                before = len(bucket)
                for h in headlines:
                    if h not in bucket:
                        bucket.append(h)
                added = len(sector_headlines[sector]) - before
                log.debug("  [bucket] %s (%s): added %d (bucket now %d)",
                          ticker, sector, added, len(sector_headlines[sector]))
            else:
                log.debug("  [bucket] %s (%s): no headlines from any live source", ticker, sector)

        # ── Top up sparse sectors with general market news ─────────────────
        general: List[str] = []
        for sector in {s for _, s in ticker_sector_pairs}:
            count = len(sector_headlines.get(sector, []))
            if count < 2:
                if not general:
                    if er_active:
                        general = fetch_general_news_er(er_key, max_results=20)
                    if not general and fh_active:
                        general = fetch_market_news(fh_key, max_results=20)
                if general:
                    log.info("  [top-up] Sector '%s' only has %d headline(s) — topping up",
                             sector, count)
                    sector_headlines.setdefault(sector, []).extend(general[:max_per_sector])

    # ── Mock fallback for any sector still missing ─────────────────────────
    for _, sector in ticker_sector_pairs:
        if sector not in sector_headlines or not sector_headlines[sector]:
            log.info("  Mock fallback for sector '%s'", sector)
            sector_headlines[sector] = _mock_headlines(sector, max_per_sector)

    # Trim to max_per_sector per sector and log
    for sector in sector_headlines:
        sector_headlines[sector] = sector_headlines[sector][:max_per_sector]
        log.info("  Sector '%-22s' → %d headlines", sector, len(sector_headlines[sector]))

    _save_json("sector_headlines.json", sector_headlines)
    log.info("  Raw JSON saved → %s", _OUTPUT_DIR)
    return sector_headlines
