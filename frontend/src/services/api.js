import axios from 'axios'

/**
 * Resolve API base URL.
 * - Prefer VITE_API_BASE_URL (e.g. http://127.0.0.1:8010 — same as API_PORT in nexus_agent/.env)
 * - Default: same-origin `/api` — Vite dev & preview proxy to FastAPI (see vite.config.js)
 * - This avoids mixed host issues (localhost vs 127.0.0.1) and keeps CORS simple.
 */
function resolveApiBase() {
  const fromEnv = import.meta.env.VITE_API_BASE_URL?.trim()
  if (fromEnv) return fromEnv.replace(/\/$/, '')
  return '/api'
}

const BASE = resolveApiBase()

const client = axios.create({
  baseURL: BASE,
  timeout: 600_000,
})

// Avoid stale cached GET responses after a full page refresh (browser / devtools proxy).
client.interceptors.request.use((config) => {
  const m = (config.method || 'get').toLowerCase()
  if (m === 'get') {
    config.params = { ...config.params, _t: Date.now() }
    config.headers = config.headers || {}
    config.headers['Cache-Control'] = 'no-cache'
    config.headers.Pragma = 'no-cache'
  }
  return config
})

/**
 * Upload a CSV file.
 */
export async function uploadPortfolio(file) {
  const form = new FormData()
  form.append('file', file)
  const { data } = await client.post('/upload-portfolio', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return data
}

/**
 * Run the full LangGraph pipeline.
 * @param {string} csvPath
 * @param {{ customPrompt?: string, selectedHeadlines?: string[] }} [options]
 */
export async function rebalance(csvPath, options = {}) {
  const { customPrompt, selectedHeadlines } = options
  const body = {
    csv_path: csvPath,
    custom_prompt: customPrompt?.trim() || null,
    selected_headlines:
      selectedHeadlines?.length ? selectedHeadlines.slice(0, 20) : null,
  }
  const { data } = await client.post('/rebalance', body)
  return data
}

/**
 * Fetch latest news (sector headlines + flat article list).
 */
export async function getLatestNews() {
  const { data } = await client.get('/latest-news', { timeout: 15_000 })
  return data
}

/**
 * Fetch the last saved report from disk (optional). Not used on dashboard load — user gets a clean slate on refresh.
 */
export async function getLastReport() {
  const { data } = await client.get('/report', { timeout: 10_000 })
  return data
}

/**
 * Health check — confirms the Nexus v2 API is running (see API_PORT in .env / Vite proxy).
 */
export async function getHealth() {
  const { data } = await client.get('/health', { timeout: 5_000 })
  return data
}

/**
 * URL for downloading the CSV report (same origin as API).
 */
export function getDownloadCsvUrl() {
  return `${BASE}/download-csv`
}
