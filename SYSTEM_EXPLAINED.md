# Nexus AI — Portfolio Rebalancing Agent: Full System Explanation

## What This System Does

Nexus AI reads your stock portfolio from a CSV file, fetches live market prices, pulls real news headlines from Finnhub, uses Claude (AI) to judge the mood of each sector, scores every stock, and tells you whether to **BUY**, **SELL**, or **HOLD** each position — all in one automated pipeline.

---

## The 9-Step Pipeline

The system runs as a **LangGraph state machine** — a chain of 9 nodes where each node reads from a shared state object and writes its results back in. Data flows in one direction: each step enriches the state for the next.

```
START
  ↓
  Node 1 — load_portfolio        (read CSV)
  ↓
  Node 2 — analyze_portfolio     (compute position sizes)
  ↓
  Node 3 — gather_data           (live prices via Yahoo Finance)
  ↓
  Node 4 — fetch_news            (headlines via Finnhub API)
  ↓
  Node 5 — analyze_sentiment     (Claude classifies each sector)
  ↓
  Node 6 — analyze_stock         (score every stock 0–100)
  ↓
  Node 7 — rebalance_portfolio   (BUY / SELL / HOLD decision)
  ↓
  Node 8 — generate_output       (print table, save JSON + CSV)
  ↓
  Node 9 — explain_results       (Claude writes one sentence per stock)
  ↓
END
```

---

## Step-by-Step Breakdown

### Node 1 — `load_portfolio` (`utils.py → load_portfolio_csv`)

**What it does:** Reads your CSV file.

- Accepts flexible column names: `Ticker` / `Symbol`, `Quantity` / `Shares` / `Qty`, `Price` / `Buy Price` / `Avg Buy Price`, `Purchase Date`, `Sector`.
- Skips blank rows, duplicate tickers, and invalid quantities — logs a warning for each.
- `buy_price` is optional. If blank, the system will fetch the historical price from Yahoo Finance in Node 3.

**Output added to state:** `portfolio` — a list of cleaned rows, e.g.:
```json
{ "ticker": "MSFT", "quantity": 10, "buy_price": 380.0, "purchase_date": "01/15/2024", "sector_csv": "Technology" }
```

---

### Node 2 — `analyze_portfolio` (`graph.py`)

**What it does:** Calculates an initial position size for each stock using quantity as a proxy weight (live prices are not available yet).

```
position_size_pct = (stock_quantity / total_quantity) * 100
```

This is a placeholder — it gets recalculated with real dollar values in Node 3.

**Output added to state:** `analyzed` — same rows with `position_size_pct` attached.

---

### Node 3 — `gather_data` (`tools/data_fetch.py → enrich_ticker`)

**What it does:** Fetches live market data from **Yahoo Finance** for every ticker.

For each stock it fetches:
- **Current price** — latest closing price from `yfinance`
- **Buy price** — if blank in CSV, fetches the historical closing price on/near `purchase_date` (tries up to 7 calendar days forward to skip weekends/holidays)
- **Sector** — from Yahoo Finance `ticker.info["sector"]` (more reliable than CSV)

Then it calculates:
```
return_pct = (current_price - buy_price) / buy_price * 100
current_value    = current_price × quantity
investment_value = buy_price    × quantity
```

After all tickers are enriched, `position_size_pct` is **recalculated** using real dollar values:
```
position_size_pct = current_value / total_portfolio_value * 100
```

**Output added to state:** `market_data` — fully enriched rows with prices, returns, sector, and position sizes.

---

### Node 4 — `fetch_news` (`tools/news.py → build_sector_news`)

**What it does:** Fetches recent news headlines for every ticker and groups them by sector.

**Flow:**

1. For each ticker, calls **Finnhub `/company-news`**:
   ```
   GET https://finnhub.io/api/v1/company-news
       ?symbol=MSFT&from=2026-04-08&to=2026-04-13&token=<key>
   ```
   Finnhub returns a JSON array of articles. Each article looks like:
   ```json
   {
     "headline": "Microsoft wins Pentagon AI contract...",
     "source":   "Reuters",
     "summary":  "Full article text...",
     "url":      "https://...",
     "datetime": 1744563600,
     "image":    "https://..."
   }
   ```
   The code extracts only the `headline` field, keeps the top 5 per ticker.

2. Headlines are **bucketed by sector** — all Technology tickers (MSFT, NVDA) share one bucket.

3. If any sector has fewer than 2 headlines, it is **topped up** from the general market news endpoint:
   ```
   GET https://finnhub.io/api/v1/news?category=general&token=<key>
   ```

4. If Finnhub is unavailable or returns nothing, the system **falls back to hardcoded mock headlines** per sector.

**Raw JSON files saved to** `output/raw_news_json/`:

| File | Contents |
|------|----------|
| `company_news_MSFT.json` | All articles returned by Finnhub for MSFT |
| `company_news_NVDA.json` | All articles for NVDA |
| `market_news_general.json` | General market news articles |
| `sector_headlines.json` | Final grouped headlines fed to Claude |

**Output added to state:** `news` — a dict like:
```json
{
  "Technology":         ["headline 1", "headline 2", ...],
  "Financial Services": ["headline 1", ...],
  "Energy":             ["headline 1", ...]
}
```

---

### Node 5 — `analyze_sentiment` (`tools/sentiment.py → classify_sentiments`)

**What it does:** Sends all sector headlines to **Claude** in one call and asks it to classify each sector as `Positive`, `Neutral`, or `Negative`.

**Prompt sent to Claude:**
```
Below are recent news headlines grouped by market sector.

Technology:
  - 1 "Magnificent Seven" Stock That's a Better Buy Than the Other 6 Right Now
  - The Outcome Economy: Surviving The Agentic Blitz
  ...

Financial Services:
  - Persian Gulf, Oil Outlooks Damp Wall Street Pre-Bell
  ...

For EACH sector, classify the overall sentiment as exactly one of:
Positive, Neutral, or Negative.

Reply ONLY with a valid JSON object. Example:
{"Technology": "Positive", "Energy": "Neutral", "Financials": "Negative"}
```

**Claude replies with JSON**, e.g.:
```json
{
  "Technology":         "Positive",
  "Financial Services": "Neutral",
  "Energy":             "Negative"
}
```

If the Claude call fails, the system falls back to a **keyword heuristic** — counts positive words (`growth`, `beat`, `surge`, `record`, `rally`) vs negative words (`decline`, `fall`, `risk`, `loss`, `miss`) across the headlines.

**Output added to state:** `sentiments` — `{sector: "Positive"|"Neutral"|"Negative"}`.

---

### Node 6 — `analyze_stock` (`tools/scoring.py`)

**What it does:** Attaches the sentiment to each stock and computes a **composite score 0–100**.

**Strength label** (from return %):
| Return | Strength |
|--------|----------|
| ≥ +10% | Strong   |
| ≤ −10% | Weak     |
| Between | Neutral |

**Composite score formula:**
```
score = (price_performance × 40%)
      + (sentiment_value   × 40%)
      + (concentration     × 20%)
```

Where:
- `price_performance` = `return_pct / 100 + 0.5` clamped to [0, 1] → −50% maps to 0, 0% maps to 0.5, +50% maps to 1
- `sentiment_value` = Positive→1.0, Neutral→0.5, Negative→0.0
- `concentration` = `1 - position_size_pct / 30` → penalises stocks that are already >30% of the portfolio

**Output added to state:** `scored_stocks` — each stock now has `sentiment`, `strength`, and `score`.

---

### Node 7 — `rebalance_portfolio` (`tools/scoring.py → rebalance_decision`)

**What it does:** Applies rule-based logic to turn each score into a `BUY`, `SELL`, or `HOLD` recommendation.

**SELL rules (checked first):**

| Condition | Reason |
|-----------|--------|
| Negative sentiment AND return > +5% | Lock in profit before sector deteriorates further |
| Negative sentiment AND return < −20% | Cut losses — sector outlook is bad |
| Score < 30 (any sentiment) | Fundamentally weak across all factors |

**BUY rules:**

| Condition | Reason |
|-----------|--------|
| Positive sentiment AND return > −10% | Sector tailwind + stock not in deep loss |
| Score > 75 (any sentiment) | Top performer across all three factors |

**HOLD:** Everything that does not match a SELL or BUY rule.

**Output added to state:** `recommendations` — each stock now has `action` and `reason`.

---

### Node 8 — `generate_output` (`utils.py`)

**What it does:** Produces all final outputs.

1. **Prints a formatted table** to the terminal:
   ```
   ╭────────┬──────────────────┬──────────┬──────────┬──────────┬───────────┬──────────┬───────┬────────╮
   │ Ticker │ Sector           │ Buy $    │ Cur $    │ Return % │ Sentiment │ Strength │ Score │ Action │
   ├────────┼──────────────────┼──────────┼──────────┼──────────┼───────────┼──────────┼───────┼────────┤
   │ MSFT   │ Technology       │ $380.00  │ $415.20  │ +9.3%    │ Positive  │ Neutral  │  72   │ BUY    │
   ...
   ```

2. **Saves `output/rebalancing_report.json`** — full structured report.
3. **Saves `output/Nexus_AI_Portfolio_With_Live_Prices.csv`** — flat table, one row per stock.

**Portfolio summary** is also computed:
```
total_invested       = sum of (buy_price × quantity) for all stocks
current_value        = sum of (current_price × quantity) for all stocks
portfolio_return_pct = (current_value - total_invested) / total_invested × 100
```

---

### Node 9 — `explain_results` (`tools/sentiment.py → generate_stock_explanations`)

**What it does:** Sends all recommendations to **Claude** and asks for one plain-English sentence per stock explaining the decision.

**Prompt sent to Claude:**
```
For each stock below, write exactly ONE concise sentence explaining the recommended action.

MSFT (Technology): action=BUY, return=+9.3%, sentiment=Positive, strength=Neutral, score=72
NVDA (Technology): action=BUY, return=+42.1%, sentiment=Positive, strength=Strong, score=88
...
```

**Claude replies:**
```
MSFT: Strong positive sector momentum combined with near-double-digit gains makes this a compelling add.
NVDA: Exceptional AI-driven returns and broad sector tailwind justify further accumulation.
...
```

These sentences are printed to the terminal under "AI EXPLANATIONS".

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
+ position_size_pct (quantity-weighted, placeholder)
   │
   ▼
[gather_data]  ──── Yahoo Finance ────► current_price, buy_price, sector
+ current_price, buy_price, return_pct, current_value, position_size_pct (real $)
   │
   ▼
[fetch_news]   ──── Finnhub API ──────► JSON articles per ticker
+ news: { sector: [headline, ...] }
   │
   ▼
[analyze_sentiment]  ── Claude ───────► { sector: Positive/Neutral/Negative }
+ sentiments
   │
   ▼
[analyze_stock]
+ sentiment, strength (Strong/Neutral/Weak), score (0–100)
   │
   ▼
[rebalance_portfolio]
+ action (BUY/SELL/HOLD), reason
   │
   ▼
[generate_output]
→ terminal table
→ output/rebalancing_report.json
→ output/Nexus_AI_Portfolio_With_Live_Prices.csv
   │
   ▼
[explain_results]  ── Claude ──────────► one sentence per stock
→ printed to terminal
```

---

## Output Files

| File | Description |
|------|-------------|
| `output/rebalancing_report.json` | Full report with portfolio summary, sector sentiments, and per-stock recommendations |
| `output/Nexus_AI_Portfolio_With_Live_Prices.csv` | Flat CSV — one row per stock, all columns |
| `output/agent_graph.png` | Visual diagram of the 9-node LangGraph pipeline |
| `output/raw_news_json/company_news_<TICKER>.json` | Raw Finnhub JSON for each ticker (all fields) |
| `output/raw_news_json/market_news_general.json` | Raw general market news from Finnhub |
| `output/raw_news_json/sector_headlines.json` | Final 5 headlines per sector sent to Claude |

---

## Scoring Thresholds (Quick Reference)

| Threshold | Value | Purpose |
|-----------|-------|---------|
| Strong return | ≥ +10% | Label as "Strong" |
| Weak return | ≤ −10% | Label as "Weak" |
| SELL profit-lock | return > +5% + Negative sentiment | Sell to protect gains |
| SELL loss-cut | return < −20% + Negative sentiment | Stop-loss exit |
| SELL weak score | score < 30 | Fundamentally weak |
| BUY positive entry | Positive sentiment + return > −10% | Buy into tailwind |
| BUY high score | score > 75 | Top performer |
| Concentration penalty | position > 30% of portfolio | Score reduction |

---

## External Services Used

| Service | What For | Free Tier? |
|---------|----------|------------|
| Yahoo Finance (`yfinance`) | Live prices, historical prices, sector info | Yes |
| Finnhub API | Company news headlines, general market news | Yes (rate limited) |
| Anthropic Claude | Sentiment classification, stock explanations | Paid API |

---

## HTTP API (dashboard backend)

From the `nexus_agent` folder run `python src/api.py`. The server listens on `0.0.0.0` and port **`API_PORT`** from `.env` (default **8010** so it does not clash with other apps on **8000**). The Vite dev server reads the same `API_PORT` and proxies `http://localhost:5173/api/*` to that port. **In a browser, open `http://127.0.0.1:<API_PORT>/docs`** — not `http://0.0.0.0:...` (invalid in browsers). Use `/health` and check for `"service":"nexus-ai-v2"`.

---

## Environment Variables (`.env`)

| Variable | Required | Description |
|----------|----------|-------------|
| `ANTHROPIC_API_KEY` | Yes | Claude API key |
| `CLAUDE_MODEL` | No | Defaults to `claude-sonnet-4-5-20250929` |
| `FINNHUB_API_KEY` | No | If missing, uses mock headlines |
| `DEBUG_NEWS` | No | Set to `1` to log raw HTTP requests and JSON samples |
