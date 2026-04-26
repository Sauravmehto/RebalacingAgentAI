# Deploy: Render (API) + Netlify (UI)

## 1. Backend — [Render](https://render.com)

### Option A — Blueprint (uses `render.yaml`)

1. Push this repo to GitHub/GitLab/Bitbucket.
2. Render → **New** → **Blueprint** → connect the repo → apply.
3. Open the new **Web Service** → **Environment** → add:

| Variable | Notes |
|----------|--------|
| `ANTHROPIC_API_KEY` | Required for `/rebalance` and Claude steps |
| `CLAUDE_MODEL` | Optional; default `claude-sonnet-4-5-20250929` |
| `FINNHUB_API_KEY` | Optional; news fallback exists |
| `EVENT_REGISTRY_API_KEY` | Optional |
| `SERPAPI_API_KEY` | Optional; enables Google Finance quote lookup before yfinance fallback |
| `DEBUG_NEWS` | Optional; `1` for verbose news logs |
| `STRICT_COST_BASIS` | Optional; `1` — reject CSV rows without a positive buy/price column |
| `SKIP_CLAUDE_COST_BASIS` | Optional; `1` — do not use Claude to guess missing historical cost basis |

4. **Manual Deploy** → **Deploy latest commit** if the first build ran before env vars were set.
5. Copy the service URL, e.g. `https://nexus-ai-api.onrender.com` (your name may differ).

### Option B — Web Service manually

- **Root directory:** leave empty (repo root).
- **Build command:** `pip install -r requirements.txt`
- **Start command:** `cd src && uvicorn api:app --host 0.0.0.0 --port $PORT`
- **Health check path:** `/health`

Python version follows `runtime.txt` (`python-3.12.7`).

### Notes

- **Cold starts:** Free tier sleeps; first request after idle can take ~30–60s.
- **Long requests:** `/rebalance` can run several minutes. If the browser or Render times out, try again after the service is warm or consider a paid instance / background jobs later.

---

## 2. Frontend — [Netlify](https://netlify.com)

1. **Add new site** → Import from Git → same repo.
2. Netlify reads root `netlify.toml` (`base = "frontend"`). No need to set “base directory” twice if the file is present.
3. **Site configuration → Environment variables →** add for **Build** scope:

   - **`VITE_API_BASE_URL`** = `https://YOUR-RENDER-SERVICE.onrender.com`  
     (exact URL from step 1.5, **no** trailing slash)

4. Trigger **Deploy site** (or push a commit). Vite bakes this URL into the client at build time.

### Custom Netlify domain

- API CORS already allows `*.netlify.app`.
- For `https://yourname.com`, add in **Render** → service → **Environment**:

  `CORS_ORIGINS=https://yourname.com`

  (comma-separate multiple origins if needed.)

---

## 3. Verify

- API: open `https://YOUR-RENDER.onrender.com/health` → JSON with `"service":"nexus-ai-v2"`.
- UI: open your Netlify URL → dashboard should load; running a rebalance calls the Render API (check browser Network tab → requests go to your Render host).

---

## Local development

- Do **not** set `VITE_API_BASE_URL` (or use `.env.development.local` with an empty value) so the app uses the Vite proxy to `http://127.0.0.1:8010`.
- Keep secrets in `.env` locally; production secrets live only in Render / Netlify dashboards.
