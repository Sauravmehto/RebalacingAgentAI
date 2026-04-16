"""
api.py — FastAPI server for Nexus AI Intelligent Portfolio Manager

Endpoints:
  POST /upload-portfolio  — save uploaded CSV, return its path
  POST /rebalance         — run the full LangGraph pipeline, return report JSON
  GET  /latest-news       — return sector_headlines + flat article list

Run:
    cd d:/shop/nexus_agent
    python src/api.py
"""

import asyncio
import json
import logging
import os
import shutil
import sys
from pathlib import Path

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from typing import List, Optional

from pydantic import BaseModel, field_validator

# ── Bootstrap ─────────────────────────────────────────────────────────────────
ROOT_DIR = Path(__file__).resolve().parent.parent   # nexus_agent/
SRC_DIR  = ROOT_DIR / "src"
sys.path.insert(0, str(SRC_DIR))

from io_encoding import ensure_utf8_stdio

# Before logging: agent thread prints Unicode (utils tabulate, symbols); Windows cp1252 breaks.
ensure_utf8_stdio()

_env_path = ROOT_DIR / ".env"
load_dotenv(dotenv_path=str(_env_path))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

# ── FastAPI app ───────────────────────────────────────────────────────────────
app = FastAPI(
    title="Nexus AI",
    description="Intelligent Portfolio Manager API",
    version="2.0.0",
)

# Local dev + optional production frontends (e.g. Netlify): set CORS_ORIGINS on Render
# to a comma-separated list, e.g. https://your-app.netlify.app,https://your-domain.com
_default_cors = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]
_extra_cors = [o.strip() for o in os.getenv("CORS_ORIGINS", "").split(",") if o.strip()]
_cors_allow = list(dict.fromkeys(_default_cors + _extra_cors))

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_allow,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Paths ─────────────────────────────────────────────────────────────────────
OUTPUT_DIR   = ROOT_DIR / "output"
UPLOAD_DIR   = OUTPUT_DIR / "uploads"
NEWS_DIR     = OUTPUT_DIR / "raw_news_json"
REPORT_JSON  = OUTPUT_DIR / "rebalancing_report.json"
REPORT_CSV   = OUTPUT_DIR / "rebalancing_report.csv"

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


# ══════════════════════════════════════════════════════════════════════════════
# Request / Response models
# ══════════════════════════════════════════════════════════════════════════════

MAX_PROMPT_LEN = 4000
MAX_HEADLINES = 20
MAX_HEADLINE_ITEM_LEN = 500


class RebalanceRequest(BaseModel):
    csv_path: str
    custom_prompt: Optional[str] = None
    selected_headlines: Optional[List[str]] = None

    @field_validator("custom_prompt", mode="before")
    @classmethod
    def strip_prompt(cls, v):
        if v is None:
            return None
        s = str(v).strip()
        return s[:MAX_PROMPT_LEN] if s else None

    @field_validator("selected_headlines", mode="before")
    @classmethod
    def cap_headlines(cls, v):
        if not v:
            return None
        out = [str(h).strip()[:MAX_HEADLINE_ITEM_LEN] for h in v[:MAX_HEADLINES] if str(h).strip()]
        return out or None


# ══════════════════════════════════════════════════════════════════════════════
# Helper — build and run the LangGraph agent
# ══════════════════════════════════════════════════════════════════════════════

def _run_agent(
    csv_path: str,
    custom_prompt: str = "",
    selected_headlines: Optional[List[str]] = None,
) -> dict:
    """
    Build the LangGraph agent, invoke it with the given CSV path,
    and return the output_report dict.
    Runs synchronously (called via asyncio.to_thread from the async endpoint).
    """
    from langchain_anthropic import ChatAnthropic
    from graph import AgentState, build_graph

    anthropic_key = os.getenv("ANTHROPIC_API_KEY", "")
    claude_model  = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-5-20250929")

    if not anthropic_key:
        raise ValueError("ANTHROPIC_API_KEY not set in .env")

    os.environ["ANTHROPIC_API_KEY"] = anthropic_key
    llm   = ChatAnthropic(model=claude_model, temperature=0)
    agent = build_graph(llm)

    headlines = selected_headlines or []
    initial: AgentState = {
        "csv_path":           csv_path,
        "portfolio":          [],
        "analyzed":           [],
        "market_data":        [],
        "trends":             {},
        "news":               {},
        "sentiments":         {},
        "sentiment_scores":   {},
        "market_sentiment":   "Neutral",
        "current_allocation": {},
        "allocation_status":  {},
        "cash_pct":           10.0,
        "scored_stocks":      [],
        "recommendations":    [],
        "output":             {},
        "explanations":       [],
        "errors":             [],
        "custom_prompt":      custom_prompt or "",
        "selected_headlines": headlines,
    }

    log.info(
        "Agent starting for CSV: %s (scenario=%s, selected_headlines=%d)",
        csv_path,
        bool((custom_prompt or "").strip()),
        len(headlines),
    )
    final = agent.invoke(initial)
    log.info("Agent finished. errors=%s", final.get("errors", []))

    output = final.get("output", {})
    if not output:
        raise ValueError("Agent returned empty output — check logs for errors")

    # Attach explanations to output for the frontend
    output["explanations"] = final.get("explanations", [])
    output["errors"]       = final.get("errors", [])
    return output


# ══════════════════════════════════════════════════════════════════════════════
# Endpoints
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/")
async def root():
    return {"service": "Nexus AI", "status": "running"}


@app.get("/health")
async def health():
    """Identify this service (avoids confusing another FastAPI app bound to :8000)."""
    return {"status": "ok", "service": "nexus-ai-v2", "version": "2.0.0"}


@app.post("/upload-portfolio")
async def upload_portfolio(file: UploadFile = File(...)):
    """
    Accept a CSV file, save it to output/uploads/, and return the absolute path.
    """
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files are accepted")

    dest = UPLOAD_DIR / file.filename
    with open(dest, "wb") as f:
        shutil.copyfileobj(file.file, f)

    log.info("Portfolio uploaded: %s", dest)
    return {
        "csv_path": str(dest.resolve()),
        "filename": file.filename,
        "size_bytes": dest.stat().st_size,
    }


@app.post("/rebalance")
async def rebalance(req: RebalanceRequest):
    """
    Run the full 11-node LangGraph pipeline.
    Returns the complete rebalancing_report dict including explanations.

    This can take 2–5 minutes — the frontend shows a loading spinner.
    """
    csv_path = req.csv_path

    if not os.path.exists(csv_path):
        raise HTTPException(status_code=404,
                            detail=f"CSV file not found: {csv_path}")

    try:
        result = await asyncio.to_thread(
            _run_agent,
            csv_path,
            req.custom_prompt or "",
            req.selected_headlines,
        )
        return result
    except Exception as exc:
        log.error("Agent run failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/latest-news")
@app.get("/news")  # legacy alias (older dashboard server used GET /news)
async def latest_news():
    """
    Return sector headlines (from last run) plus a flat article list.

    sector_headlines: { "Technology": ["headline1", ...], ... }
    articles: [ { "title": "...", "sector": "...", "source": "..." }, ... ]
    """
    sector_headlines = {}
    headlines_path   = NEWS_DIR / "sector_headlines.json"

    if headlines_path.exists():
        with open(headlines_path, encoding="utf-8") as f:
            sector_headlines = json.load(f)

    # Build flat article list from er_company_news_*.json files
    articles = []
    for er_file in sorted(NEWS_DIR.glob("er_company_news_*.json")):
        ticker = er_file.stem.replace("er_company_news_", "")
        try:
            with open(er_file, encoding="utf-8") as f:
                raw = json.load(f)
            for item in raw[:3]:  # max 3 per ticker
                title  = item.get("title", "").strip()
                source = item.get("source", {})
                source_name = (
                    source.get("title", "") if isinstance(source, dict) else str(source)
                )
                if title:
                    articles.append({
                        "title":  title,
                        "source": source_name or "Unknown",
                        "ticker": ticker,
                        "url":    item.get("url", ""),
                        "date":   item.get("dateTime", item.get("datetime", "")),
                    })
        except Exception:
            pass

    # Also pull from Finnhub company news if ER articles are sparse
    if len(articles) < 6:
        for fh_file in sorted(NEWS_DIR.glob("company_news_*.json")):
            ticker = fh_file.stem.replace("company_news_", "")
            try:
                with open(fh_file, encoding="utf-8") as f:
                    raw = json.load(f)
                for item in raw[:2]:
                    title = item.get("headline", "").strip()
                    if title:
                        articles.append({
                            "title":  title,
                            "source": item.get("source", "Unknown"),
                            "ticker": ticker,
                            "url":    item.get("url", ""),
                            "date":   str(item.get("datetime", "")),
                        })
            except Exception:
                pass

    return {
        "sector_headlines": sector_headlines,
        "articles":         articles[:30],
    }


@app.get("/report")
async def get_report():
    """Return the last saved rebalancing_report.json, or an empty payload (HTTP 200)."""
    if not REPORT_JSON.exists():
        # Avoid 404 spam in the browser Network tab when no run has been completed yet
        return {
            "stocks": [],
            "portfolio_summary": None,
            "market_sentiment": "Neutral",
            "_empty": True,
        }
    with open(REPORT_JSON, encoding="utf-8") as f:
        return json.load(f)


@app.get("/download-csv")
async def download_csv():
    """Download the last rebalancing_report.csv."""
    if not REPORT_CSV.exists():
        raise HTTPException(status_code=404, detail="No CSV report found.")
    return FileResponse(
        path=str(REPORT_CSV),
        media_type="text/csv",
        filename="rebalancing_report.csv",
    )


# ══════════════════════════════════════════════════════════════════════════════
# Entry point
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    api_port = int(os.getenv("API_PORT", "8010"))
    log.info(
        "Starting Nexus AI API — routes: /upload-portfolio, /rebalance, "
        "/latest-news, /news, /report, /download-csv, /health"
    )
    log.info(
        "Listening on port %s (set API_PORT in .env to change). "
        "Browser: http://127.0.0.1:%s/docs — not http://0.0.0.0:%s (invalid in browsers).",
        api_port,
        api_port,
        api_port,
    )
    uvicorn.run(
        "api:app",
        host="0.0.0.0",
        port=api_port,
        reload=False,
        log_level="info",
    )
