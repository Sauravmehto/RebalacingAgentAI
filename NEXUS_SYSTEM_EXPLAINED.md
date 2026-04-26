# Nexus AI v2 — Intelligent Portfolio Manager: Full System Explanation

## What This System Does

Nexus AI **v2** reads your stock portfolio from a CSV file, fetches live market prices (Yahoo Finance), pulls recent headlines (**Event Registry** first, **Finnhub** as fallback, then mock data), computes **7-day and 30-day price trends**, uses **Claude** to classify each sector’s mood on a **five-level scale**, compares your holdings to **target sector weights**, scores every stock with a **five-factor composite model**, and recommends one of **seven actions** — from `STRONG BUY` through `STRONG SELL` — with **confidence** and optional **capital-flow hints**. You can run it from the terminal, via a **FastAPI** backend, or through a **React (Vite) dashboard**. On rebalance, you may pass a **custom scenario** and **selected headlines** so sentiment reflects your focus.

---

## The 11-Step Pipeline

The system runs as a **LangGraph state machine** — a chain of **11 nodes** where each node reads from a shared **`AgentState`** and writes results back. Data flows in one direction: each step enriches the state for the next.

```
START
  ↓
  Node 1  — load_portfolio        (read CSV)
  ↓
  Node 2  — analyze_portfolio     (compute position sizes, quantity-weighted)
  ↓
  Node 3  — gather_data           (live prices via Yahoo Finance / yfinance)
  ↓
  Node 4  — trend_analysis        (7d / 30d trends, trend_score)
  ↓
  Node 5  — fetch_news            (headlines: Event Registry → Finnhub → mock)
  ↓
  Node 6  — analyze_sentiment     (Claude: 5-level sector labels; optional scenario + headlines)
  ↓
  Node 7  — allocation_check      (vs TARGET_ALLOCATION, Over/Underweight, cash_pct)
  ↓
  Node 8  — analyze_stock        (composite score 0–100, v2 formula)
  ↓
  Node 9  — rebalance_portfolio   (7 action types + reason + confidence)
  ↓
  Node 10 — generate_output       (JSON, CSV, terminal tables, capital_flows heuristics)
  ↓
  Node 11 — explain_results       (Claude: one sentence per stock)
  ↓
END
```

---

## Step-by-Step Breakdown

### Node 1 — `load_portfolio` (`utils.py` → `load_portfolio_csv`)

**What it does:** Reads and validates your CSV.

- Accepts flexible column names: `Ticker` / `Symbol`, `Quantity` / `Shares` / `Qty`, `Price` / `Buy Price` / `Avg Buy Price`, `Purchase Date`, `Sector`.
- Normalizes tickers (e.g. strips leading `$`).
- Skips blank rows, duplicate tickers, and invalid quantities — logs warnings.
- `buy_price` may be blank; Node 3 can fill it from historical Yahoo data using `purchase_date`.

**Output added to state:** `portfolio` — cleaned rows, e.g.:

```json
{ "ticker": "MSFT", "quantity": 10, "buy_price": 380.0, "purchase_date": "01/15/2024", "sector_csv": "Technology" }
```

---

### Node 2 — `analyze_portfolio` (`graph.py`)

**What it does:** Computes an initial **position weight** per stock using quantities (before live prices).

```
position_size_pct ≈ (stock_quantity / total_quantity) × 100
```

This is refined in Node 3 once **dollar** `current_value` exists.

**Output added to state:** `analyzed` — rows with `position_size_pct` and related fields.

---

### Node 3 — `gather_data` (`tools/data_fetch.py` → `enrich_ticker`)

**What it does:** Enriches each ticker with Yahoo Finance data.

For each stock it typically obtains:

- **Current price** — latest close via `yfinance`
- **Buy price** — if missing in CSV, historical close near `purchase_date` (with a short forward window for weekends)
- **Sector** — from `ticker.info` when available (often preferred over CSV)

Then:

```
return_pct      = (current_price - buy_price) / buy_price × 100   (if buy_price present)
current_value   = current_price × quantity
investment_value = buy_price × quantity
```

After enrichment, **position_size_pct** is recomputed from **real portfolio value**:

```
position_size_pct = current_value / total_portfolio_value × 100
```

If price history fails, the code may optionally ask **Claude** for an estimated price (clearly marked as an estimate in logs).

**Output added to state:** `market_data` — enriched rows with prices, returns, sectors, position sizes.

---

### Node 4 — `trend_analysis` (`tools/trend.py` → `build_ticker_trends`)

**What it does:** For each ticker, loads recent closes and classifies **7-day** and **30-day** windows as **Uptrend**, **Downtrend**, or **Sideways** (by comparing first-half vs second-half average price; small moves ≈ Sideways).

- **`compute_trend_score(trend_7d, trend_30d)`** maps the pair to a **normalized score in [0, 1]** for the composite formula (aligned bulls vs mixed vs bears).

**Output added to state:** `trends` — per ticker: `trend_7d`, `trend_30d`, `trend_label` (combined), `trend_score`, etc.

---

### Node 5 — `fetch_news` (`tools/news.py` → `build_sector_news`)

**What it does:** Collects **headlines per sector** (bucketed by sector so e.g. MSFT and NVDA share a Technology bucket).

**Source priority:**

1. **Event Registry** (`POST https://eventregistry.org/api/v1/article/getArticles`) when `EVENT_REGISTRY_API_KEY` is set  
2. **Finnhub** — e.g. `/company-news` per ticker; general `/news` may top up thin sectors  
3. **Built-in mock headlines** — always available if APIs fail or keys are missing  

Headlines are trimmed to a small cap per ticker/sector; raw responses can be saved under `output/raw_news_json/` (e.g. `company_news_<TICKER>.json`, `sector_headlines.json`, `market_news_general.json`) for debugging.

**Output added to state:** `news` — `{ "Technology": ["headline …", …], "Energy": […], … }`

---

### Node 6 — `analyze_sentiment` (`tools/sentiment.py` → `classify_sentiments`)

**What it does:** Sends **sector headline blocks** to **Claude** in **one** call and asks for a **five-level** label per sector:

`Strong Positive` · `Positive` · `Neutral` · `Negative` · `Strong Negative`

**Optional context (rebalance / dashboard):**

- **`custom_prompt`** — user scenario (thematic focus)  
- **`selected_headlines`** — user-picked strings appended as extra context  

If the LLM call fails, a **keyword heuristic** maps headline text to the same five labels.

**Normalization for scoring:** `sentiment_to_norm(label)` maps labels to **[0, 1]** via integer scores −2…+2:  
`(raw + 2) / 4`.

**Also:** `compute_market_sentiment` aggregates sector labels into an overall **`market_sentiment`** string.

**Output added to state:** `sentiments`, `sentiment_scores`, `market_sentiment`.

---

### Node 7 — `allocation_check` (`graph.py`)

**What it does:** Compares **actual** sector weights (`current_allocation`) to **`TARGET_ALLOCATION`** in `graph.py` (e.g. Technology, ETF, Financial Services, Others), using **`ALLOCATION_TOLERANCE`** (±%) to label each sector **Overweight**, **Underweight**, or **Neutral**. Sets a recommended **`cash_pct`** reserve where applicable.

**Output added to state:** `current_allocation`, `allocation_status`, `cash_pct`.

---

### Node 8 — `analyze_stock` (`tools/scoring.py` → `calculate_score_v2`)

**What it does:** For each holding, combines:

- **Return** — normalized from `return_pct`  
- **Sentiment** — `sentiment_norm` from Node 6  
- **Trend** — `trend_score` from Node 4  
- **Allocation** — `get_allocation_score(allocation_status)` (Underweight → higher, Overweight → lower)  
- **Risk** — `compute_risk_score(return_pct)` (penalizes extreme moves)  

**Composite score (0–100):**

```
score = return_norm       × 30%
      + sentiment_norm    × 25%
      + trend_score       × 20%
      + allocation_score  × 15%
      + risk_score        × 10%
```

where `return_norm = clamp(return_pct / 100 + 0.5, 0, 1)` (same spirit as v1’s price leg).

**Strength label** (from return): ≥ +10% → **Strong**, ≤ −10% → **Weak**, else **Neutral** (`label_strength`).

**Output added to state:** `scored_stocks` — each row includes `sentiment`, `strength`, `score`, `trend_label`, etc.

---

### Node 9 — `rebalance_portfolio` (`tools/scoring.py` → `rebalance_decision_v2`)

**What it does:** Maps each stock to an **action**, **reason**, and **confidence** (`HIGH` / `MEDIUM` / `LOW` from signal agreement counts).

**Priority order (simplified):**

1. **Profit booking** — very high returns → `PARTIAL SELL` or `STRONG SELL` (thresholds in code, e.g. +20% / +40%)  
2. **Stop / trim** — deep drawdowns → `REDUCE` (e.g. ≤ −10%) or `SELL` (e.g. ≤ −15%)  
3. **Allocation** — e.g. Overweight + bad sentiment → `SELL`; Underweight + good sentiment + Uptrend → `STRONG BUY`  
4. **Trend + sentiment** — e.g. Downtrend + negative → `SELL`; Uptrend + positive → `BUY`  
5. **Score** — very high score → `STRONG BUY`; very low → `STRONG SELL`  
6. Else **`HOLD`**

See `scoring.py` for exact constants (`PARTIAL_SELL_THRESHOLD`, `STOP_LOSS_THRESHOLD`, `STRONG_BUY_SCORE`, …).

**Output added to state:** `recommendations` — `action`, `reason`, `confidence` per symbol.

---

### Node 10 — `generate_output` (`graph.py` + `utils.py` + `scoring.py`)

**What it does:**

1. Builds **portfolio summary v2** (`compute_portfolio_summary_v2`) — totals, sector breakdown, action counts, risk, cash.  
2. Runs **`compute_capital_flows`** — **heuristic** estimated sell proceeds and buy deployment (not broker orders); may list **`sell_candidates`** and per-row **`priority_sell`**, **`estimated_flow_usd`**.  
3. **Prints** v2 tables to the terminal (`print_report_table_v2`, `print_portfolio_summary_v2`).  
4. **Writes** `output/rebalancing_report.json` and `output/Nexus_AI_Portfolio_With_Live_Prices.csv`.

---

### Node 11 — `explain_results` (`tools/sentiment.py` → `generate_stock_explanations`)

**What it does:** Sends compact per-stock facts (and optionally a short **scenario summary** from `build_scenario_summary`) to **Claude** and asks for **one concise sentence per ticker** explaining the recommendation. Lines appear in the report and terminal (`print_explanations`).

**Output added to state:** `explanations` — array of strings, often `"TICKER: …"`.

---

## Data Flow Summary

```
CSV File
   │
   ▼
[load_portfolio]
ticker, quantity, buy_price?, purchase_date, sector_csv
   │
   ▼
[analyze_portfolio]
+ position_size_pct (quantity-based, initial)
   │
   ▼
[gather_data]  ──── Yahoo Finance ────► current_price, buy_price?, sector, return_pct, current_value
+ position_size_pct (real $ weights)
   │
   ▼
[trend_analysis] ─── yfinance history ───► trend_7d, trend_30d, trend_label, trend_score
+ trends{ ticker: … }
   │
   ▼
[fetch_news]   ─── Event Registry / Finnhub / mock ───► news{ sector: [headlines] }
   │
   ▼
[analyze_sentiment]  ── Claude (+ optional scenario/headlines) ──► 5-level sentiments + scores
   │
   ▼
[allocation_check]  ── TARGET_ALLOCATION ──► current_allocation, allocation_status, cash_pct
   │
   ▼
[analyze_stock]
+ score (v2 five-factor), strength, …
   │
   ▼
[rebalance_portfolio]
+ action (7 types), reason, confidence
   │
   ▼
[generate_output]
→ terminal tables
→ output/rebalancing_report.json
→ output/Nexus_AI_Portfolio_With_Live_Prices.csv
→ portfolio_summary.capital_flows (heuristic)
   │
   ▼
[explain_results]  ── Claude ──────────► explanations[]
```

---

## Output Files

| File | Description |
|------|-------------|
| `output/rebalancing_report.json` | Full v2 report: portfolio summary, sector sentiments, **capital_flows**, per-stock actions, confidence, explanations |
| `output/Nexus_AI_Portfolio_With_Live_Prices.csv` | Flat CSV — one row per stock |
| `output/raw_news_json/company_news_<TICKER>.json` | Raw company news payload (source-dependent) |
| `output/raw_news_json/market_news_general.json` | General market news snapshot when fetched |
| `output/raw_news_json/sector_headlines.json` | Grouped headlines used for sentiment |
| `output/uploads/*.csv` | Copies uploaded via the API (when using dashboard upload) |

If your repo still generates **`output/agent_graph.png`**, it reflects the pipeline diagram from an older export; the **live** graph is defined in `graph.py` (**11 nodes**).

---

## Scoring & Decision Quick Reference (v2)

| Concept | Typical handling |
|--------|-------------------|
| Strength | Return ≥ **+10%** → Strong; ≤ **−10%** → Weak; else Neutral |
| Composite score | Five factors: return 30%, sentiment 25%, trend 20%, allocation 15%, risk 10% |
| Profit booking | High **+return** → `PARTIAL SELL` / `STRONG SELL` (see `PARTIAL_SELL_THRESHOLD`, `STRONG_SELL_THRESHOLD`) |
| Drawdown | e.g. ≤ **−15%** → `SELL`; ≤ **−10%** → `REDUCE` |
| Strong score | Score ≥ **75** → can yield `STRONG BUY`; score ≤ **25** → can yield `STRONG SELL` |
| Confidence | **HIGH** if ≥3 aligned bull/bear signals; **MEDIUM** if 2; else **LOW** |

Exact numbers live in `src/tools/scoring.py` (`STRONG_RETURN_THRESHOLD`, `STOP_LOSS_THRESHOLD`, etc.).

---

## External Services Used

| Service | What for | Notes |
|---------|----------|--------|
| Yahoo Finance (`yfinance`) | Live prices, history, sector | Free; rate limits apply |
| Event Registry (newsapi.ai) | Primary news articles | Needs `EVENT_REGISTRY_API_KEY` |
| Finnhub API | Fallback company/general news | Free tier rate limited; `FINNHUB_API_KEY` |
| Anthropic Claude | Sentiment, explanations, optional price fallback | Paid API (`ANTHROPIC_API_KEY`) |

---

## HTTP API (dashboard backend)

From the `nexus_agent` folder run **`python src/api.py`**. Uvicorn binds to **`0.0.0.0`** and port **`API_PORT`** from `.env` (often **8010** so it does not clash with other apps on **8000**). The Vite dev server proxies `/api/*` to that port using the same **`API_PORT`**.

**In a browser**, open **`http://127.0.0.1:<API_PORT>/docs`** or **`http://localhost:<API_PORT>/docs`** — **not** `http://0.0.0.0:...` (invalid in browsers). **`GET /health`** should report **`"service":"nexus-ai-v2"`**.

**`POST /rebalance`** accepts JSON with `csv_path` and optionally **`custom_prompt`** and **`selected_headlines`** for news-aware sentiment.

---

## Environment Variables (`.env`)

| Variable | Required | Description |
|----------|----------|-------------|
| `ANTHROPIC_API_KEY` | Yes (for LLM features) | Claude API key |
| `CLAUDE_MODEL` | No | Model id (see `env_example` / code defaults) |
| `EVENT_REGISTRY_API_KEY` | No | If set, Event Registry is used for news |
| `FINNHUB_API_KEY` | No | Fallback news; if both news keys missing, mock headlines |
| `API_PORT` | No | FastAPI port; align with Vite proxy |
| `DEBUG_NEWS` | No | Set to `1` for verbose news logging |

---

## Relationship to `SYSTEM_EXPLAINED.md`

**`SYSTEM_EXPLAINED.md`** describes an **older 9-node** narrative (Finnhub-centric, **3-level** sentiment, **3** actions BUY/SELL/HOLD, older scoring). **`NEXUS_SYSTEM_EXPLAINED.md` (this file)** is the **canonical v2** reference: **11 nodes**, **Event Registry + Finnhub**, **5-level** sentiment, **seven** action types, **trends**, **allocation**, **capital-flow heuristics**, and **scenario rebalance**. Prefer **this document** for current behavior.

---

## Disclaimer

Outputs are **analytical and educational**. Heuristic dollar amounts, scores, and AI-generated text are **not** financial advice or executable orders. Verify all figures and decisions independently.
