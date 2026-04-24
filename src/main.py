"""
main.py — Nexus AI Intelligent Portfolio Manager entry point (v2)

Usage:
    cd d:/shop/nexus_agent
    python src/main.py

The agent will prompt for a CSV path (or press Enter for a resolved default).
Default resolution: PORTFOLIO_CSV in .env if set and file exists, else
~/Downloads/Nexus_AI_Portfolio_Tracker(Portfolio).csv, else the same filename in nexus_agent/.
"""

import logging
import os
import sys
from pathlib import Path

# Add src/ to path so tool imports work cleanly
sys.path.insert(0, os.path.dirname(__file__))

from io_encoding import ensure_utf8_stdio

ensure_utf8_stdio()

from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic

# Load .env from nexus_agent/.env
_env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
load_dotenv(dotenv_path=_env_path)

from graph import AgentState, build_graph

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

# Set DEBUG_NEWS=1 in .env (or environment) to see raw JSON / HTTP details
if os.getenv("DEBUG_NEWS", "").strip() in ("1", "true", "yes"):
    logging.getLogger("tools.news").setLevel(logging.DEBUG)
    log.info("News debug logging ENABLED (DEBUG_NEWS=1)")

# ── Config ────────────────────────────────────────────────────────────────────
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
CLAUDE_MODEL      = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-5-20250929")

if not ANTHROPIC_API_KEY:
    print("ERROR: ANTHROPIC_API_KEY not set. Add it to nexus_agent/.env")
    sys.exit(1)

os.environ["ANTHROPIC_API_KEY"] = ANTHROPIC_API_KEY

_CSV_FILENAME = "Nexus_AI_Portfolio_Tracker(Portfolio).csv"


def resolve_default_csv() -> str:
    """
    Path used when the user presses Enter at the prompt.

    Order: PORTFOLIO_CSV env (if file exists) → ~/Downloads → repo root nexus_agent/
    If none exist, return ~/Downloads/... so the user can drop the file there.
    """
    env_path = (os.getenv("PORTFOLIO_CSV") or "").strip().strip('"')
    if env_path and os.path.isfile(env_path):
        return str(Path(env_path).resolve())

    home = Path.home()
    downloads = home / "Downloads" / _CSV_FILENAME
    in_repo = Path(__file__).resolve().parent.parent / _CSV_FILENAME

    if downloads.is_file():
        return str(downloads.resolve())
    if in_repo.is_file():
        return str(in_repo.resolve())
    return str(downloads.resolve())


def main() -> None:
    print("\n" + "=" * 65)
    print("   NEXUS AI — Intelligent Portfolio Manager")
    print("=" * 65)
    print("\nThis agent will:")
    print("  1.  Read your portfolio CSV")
    print("  2.  Fetch live prices (Yahoo Finance)")
    print("  3.  Analyse 7-day & 30-day price trends per ticker")
    print("  4.  Fetch sector news (Finnhub)")
    print("  5.  Classify sentiment intensity (Claude — 5 levels)")
    print("  6.  Check sector allocation vs targets")
    print("  7.  Score holdings with 5-factor composite model")
    print("  8.  Generate STRONG BUY → STRONG SELL recommendations")
    print("        including profit booking and stop-loss rules")
    print("  9.  Print sector breakdown, top gainers/losers, risk level")
    print("  10. Provide AI explanations per stock (Claude)\n")
    default = resolve_default_csv()
    print(f"Default CSV: {default}\n")

    raw_path = input("CSV file path (or Enter for default): ").strip()
    csv_path = raw_path if raw_path else default

    if not os.path.exists(csv_path):
        print(f"\nFile not found: {csv_path}")
        print(
            f"  Tip: copy your tracker export to:\n"
            f"    {Path.home() / 'Downloads' / _CSV_FILENAME}\n"
            f"  Or set PORTFOLIO_CSV in nexus_agent/.env to the full path."
        )
        sys.exit(1)

    print(f"\nUsing: {csv_path}\n")

    # ── Build LLM ────────────────────────────────────────────────────────────
    llm = ChatAnthropic(model=CLAUDE_MODEL, temperature=0)

    # ── Build and visualise graph ─────────────────────────────────────────────
    agent = build_graph(llm)

    graph_out = os.path.join(os.path.dirname(__file__), "..", "output", "agent_graph.png")
    try:
        os.makedirs(os.path.dirname(graph_out), exist_ok=True)
        png = agent.get_graph(xray=True).draw_mermaid_png()
        with open(graph_out, "wb") as f:
            f.write(png)
        log.info("Graph saved → %s", graph_out)
        os.startfile(os.path.abspath(graph_out))
    except Exception as exc:
        log.warning("Could not render agent graph: %s", exc)

    # ── Initial state ─────────────────────────────────────────────────────────
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
        "custom_prompt":      "",
        "selected_headlines": [],
    }

    log.info("Starting Nexus AI — Intelligent Portfolio Manager…")
    final = agent.invoke(initial)

    # ── Print any errors / warnings ───────────────────────────────────────────
    if final.get("errors"):
        print("\n  WARNINGS / ERRORS:")
        for e in final["errors"]:
            print(f"    • {e}")
        print()

    print("  Output files saved to nexus_agent/output/")
    print("    • rebalancing_report.json")
    print("    • rebalancing_report.csv")
    print("    • agent_graph.png\n")


if __name__ == "__main__":
    main()
