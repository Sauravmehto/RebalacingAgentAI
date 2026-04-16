import { useState, useEffect, useCallback } from 'react'
import Header         from '../components/Header.jsx'
import Upload         from '../components/Upload.jsx'
import SummaryCards   from '../components/SummaryCards.jsx'
import PortfolioTable from '../components/PortfolioTable.jsx'
import SectorBreakdown from '../components/SectorBreakdown.jsx'
import NewsSection    from '../components/NewsSection.jsx'
import ExplanationPanel from '../components/ExplanationPanel.jsx'
import RebalanceModule from '../components/RebalanceModule.jsx'
import {
  uploadPortfolio,
  rebalance,
  getLatestNews,
  getHealth,
} from '../services/api.js'

// ── Gainers / Losers ──────────────────────────────────────────────────────────
function GainLosers({ topGainers, topLosers }) {
  if (!topGainers?.length && !topLosers?.length) return null
  return (
    <div className="grid sm:grid-cols-2 gap-4 animate-fade-in">
      {/* Top Gainers */}
      <div className="card p-5">
        <div className="flex items-center gap-2 mb-4">
          <div className="w-1 h-5 bg-green-500 rounded-full" />
          <h2 className="text-base font-semibold text-white">Top Gainers</h2>
        </div>
        <div className="space-y-2">
          {(topGainers ?? []).slice(0, 5).map((s, i) => (
            <div key={s.ticker ?? i}
                 className="flex items-center justify-between py-2 px-3
                            bg-green-500/5 border border-green-500/10 rounded-lg">
              <div className="flex items-center gap-2">
                <span className="text-xs text-gray-600 w-4 tabular-nums">{i + 1}</span>
                <span className="font-mono font-bold text-white text-sm">{s.ticker}</span>
                {s.sector && (
                  <span className="text-xs text-gray-600 hidden sm:inline truncate max-w-[100px]">
                    {s.sector}
                  </span>
                )}
              </div>
              <span className="text-green-400 font-semibold tabular-nums text-sm">
                +{(s.return_pct ?? 0).toFixed(2)}%
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* Top Losers */}
      <div className="card p-5">
        <div className="flex items-center gap-2 mb-4">
          <div className="w-1 h-5 bg-red-500 rounded-full" />
          <h2 className="text-base font-semibold text-white">Top Losers</h2>
        </div>
        <div className="space-y-2">
          {(topLosers ?? []).slice(0, 5).map((s, i) => (
            <div key={s.ticker ?? i}
                 className="flex items-center justify-between py-2 px-3
                            bg-red-500/5 border border-red-500/10 rounded-lg">
              <div className="flex items-center gap-2">
                <span className="text-xs text-gray-600 w-4 tabular-nums">{i + 1}</span>
                <span className="font-mono font-bold text-white text-sm">{s.ticker}</span>
                {s.sector && (
                  <span className="text-xs text-gray-600 hidden sm:inline truncate max-w-[100px]">
                    {s.sector}
                  </span>
                )}
              </div>
              <span className="text-red-400 font-semibold tabular-nums text-sm">
                {(s.return_pct ?? 0).toFixed(2)}%
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

// ── Wrong API / backend banner ────────────────────────────────────────────────
function ApiWarningBanner({ message, onDismiss }) {
  if (!message) return null
  return (
    <div className="flex items-start gap-3 p-4 bg-amber-500/10 border border-amber-500/30 rounded-xl">
      <svg className="w-5 h-5 text-amber-400 flex-shrink-0 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
              d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
      </svg>
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium text-amber-200">Backend API</p>
        <p className="text-xs text-amber-200/80 mt-1 break-words">{message}</p>
      </div>
      <button type="button" onClick={onDismiss} className="text-amber-400/60 hover:text-amber-300 flex-shrink-0">
        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12"/>
        </svg>
      </button>
    </div>
  )
}

// ── Error banner ──────────────────────────────────────────────────────────────
function ErrorBanner({ error, onDismiss }) {
  if (!error) return null
  return (
    <div className="flex items-start gap-3 p-4 bg-red-500/10 border border-red-500/30 rounded-xl animate-fade-in">
      <svg className="w-5 h-5 text-red-400 flex-shrink-0 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
              d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
      </svg>
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium text-red-400">Error</p>
        <p className="text-xs text-red-400/70 mt-0.5 break-words">{error}</p>
      </div>
      <button onClick={onDismiss} className="text-red-400/60 hover:text-red-400 flex-shrink-0">
        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12"/>
        </svg>
      </button>
    </div>
  )
}

// ── Section separator ─────────────────────────────────────────────────────────
function Section({ children }) {
  return <div className="animate-slide-up">{children}</div>
}

// ══════════════════════════════════════════════════════════════════════════════
// Dashboard (main page)
// ══════════════════════════════════════════════════════════════════════════════
export default function Dashboard() {
  const [reportData, setReportData] = useState(null)   // full rebalancing report
  const [csvPath,    setCsvPath]    = useState(null)   // absolute path on server
  const [news,       setNews]       = useState(null)
  const [loading,    setLoading]    = useState(false)
  const [newsLoading, setNewsLoading] = useState(false)
  const [error,      setError]      = useState(null)
  const [apiWarning, setApiWarning] = useState(null)
  const [scenarioPrompt, setScenarioPrompt] = useState('')
  const [selectedHeadlines, setSelectedHeadlines] = useState([])

  // On every full page load: fresh health + news only. Do not restore /report — user must upload + analyze again.
  useEffect(() => {
    let cancelled = false
    ;(async () => {
      setReportData(null)
      setCsvPath(null)
      setError(null)

      const apiBase = import.meta.env.VITE_API_BASE_URL?.trim()
      try {
        const h = await getHealth()
        if (cancelled) return
        if (h?.service && h.service !== 'nexus-ai-v2') {
          setApiWarning(
            apiBase
              ? 'The URL in VITE_API_BASE_URL is not the Nexus v2 API (health.service is not nexus-ai-v2). Check the URL and redeploy with the correct VITE_API_BASE_URL.'
              : 'Wrong API behind the Vite proxy (health missing service:nexus-ai-v2). ' +
                'Set API_PORT in nexus_agent/.env (default 8010), run python src/api.py there, restart npm run dev.',
          )
        }
      } catch {
        if (!cancelled) {
          setApiWarning(
            apiBase
              ? `Cannot reach the API at ${apiBase.replace(/\/$/, '')}. If the service is on Render, wait ~60s for a cold start and refresh. Confirm CORS on the server includes this site (${typeof window !== 'undefined' ? window.location.origin : ''}) and that the URL has no typo.`
              : 'Cannot reach the Nexus API. From nexus_agent run: python src/api.py (uses API_PORT in .env), or from frontend: npm run dev:all. Restart Vite after changing .env.',
          )
        }
      }

      if (cancelled) return
      setNewsLoading(true)
      try {
        const data = await getLatestNews()
        if (!cancelled) setNews(data)
      } catch (e) {
        console.warn('News fetch failed:', e.message)
      } finally {
        if (!cancelled) setNewsLoading(false)
      }
    })()
    return () => { cancelled = true }
  }, [])

  const loadNews = useCallback(async () => {
    setNewsLoading(true)
    try {
      const data = await getLatestNews()
      setNews(data)
    } catch (e) {
      console.warn('News fetch failed:', e.message)
    } finally {
      setNewsLoading(false)
    }
  }, [])

  // Step 1: user drops/selects a CSV → upload immediately
  const handleUpload = useCallback(async (file) => {
    setError(null)
    try {
      const result = await uploadPortfolio(file)
      setCsvPath(result.csv_path)
    } catch (e) {
      setError(`Upload failed: ${e.response?.data?.detail ?? e.message}`)
    }
  }, [])

  const rebalanceOpts = useCallback(
    () => ({
      customPrompt: scenarioPrompt.trim() || undefined,
      selectedHeadlines: selectedHeadlines.length ? selectedHeadlines : undefined,
    }),
    [scenarioPrompt, selectedHeadlines],
  )

  const runPipeline = useCallback(async () => {
    if (!csvPath) return
    setLoading(true)
    setError(null)
    try {
      const data = await rebalance(csvPath, rebalanceOpts())
      setReportData(data)
      await loadNews()
    } catch (e) {
      setError(`Pipeline failed: ${e.response?.data?.detail ?? e.message}`)
    } finally {
      setLoading(false)
    }
  }, [csvPath, loadNews, rebalanceOpts])

  const handleAnalyze = runPipeline

  const toggleHeadline = useCallback((title) => {
    setSelectedHeadlines(prev => {
      if (prev.includes(title)) return prev.filter(x => x !== title)
      if (prev.length >= 20) return prev
      return [...prev, title]
    })
  }, [])

  const clearScenario = useCallback(() => {
    setScenarioPrompt('')
    setSelectedHeadlines([])
  }, [])

  const summary          = reportData?.portfolio_summary
  const stocks           = reportData?.stocks ?? []
  const explanations     = reportData?.explanations ?? []
  const sectorBreakdown  = summary?.sector_breakdown
  const topGainers       = summary?.top_gainers
  const topLosers        = summary?.top_losers
  const marketSentiment  = reportData?.market_sentiment
  const sectorSentiments = reportData?.sector_sentiments
  const currentAlloc     = reportData?.current_allocation
  const targetAlloc      = reportData?.target_allocation
  const portfolioReturn  = summary?.portfolio_return_pct

  return (
    <div className="min-h-screen bg-gray-950">
      <Header
        portfolioReturn={portfolioReturn}
        marketSentiment={marketSentiment}
      />

      <main className="max-w-screen-2xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">
        {/* Error */}
        <ErrorBanner error={error} onDismiss={() => setError(null)} />
        <ApiWarningBanner message={apiWarning} onDismiss={() => setApiWarning(null)} />

        {/* Upload */}
        <Section>
          <Upload
            onUpload={handleUpload}
            onAnalyze={handleAnalyze}
            loading={loading}
            csvPath={csvPath}
          />
        </Section>

        {/* Scenario + headline context (same run as Analyze / full pipeline) */}
        {csvPath && (
          <Section>
            <RebalanceModule
              csvPath={csvPath}
              loading={loading}
              news={news}
              scenarioPrompt={scenarioPrompt}
              onScenarioPromptChange={setScenarioPrompt}
              selectedHeadlines={selectedHeadlines}
              onToggleHeadline={toggleHeadline}
              onClearScenario={clearScenario}
              onRun={runPipeline}
            />
          </Section>
        )}

        {/* Summary cards */}
        {summary && (
          <Section>
            <SummaryCards summary={summary} marketSentiment={marketSentiment} />
          </Section>
        )}

        {/* Portfolio table */}
        {stocks.length > 0 && (
          <Section>
            <PortfolioTable stocks={stocks} />
          </Section>
        )}

        {/* Top gainers / losers */}
        {(topGainers?.length || topLosers?.length) && (
          <Section>
            <GainLosers topGainers={topGainers} topLosers={topLosers} />
          </Section>
        )}

        {/* Sector breakdown */}
        {sectorBreakdown && Object.keys(sectorBreakdown).length > 0 && (
          <Section>
            <SectorBreakdown
              sectorBreakdown={sectorBreakdown}
              currentAllocation={currentAlloc}
              targetAllocation={targetAlloc}
            />
          </Section>
        )}

        {/* News */}
        <Section>
          <NewsSection
            news={news}
            sectorSentiments={sectorSentiments}
            onRefresh={loadNews}
            refreshing={newsLoading}
          />
        </Section>

        {/* AI Explanations */}
        {stocks.length > 0 && (
          <Section>
            <ExplanationPanel stocks={stocks} explanations={explanations} />
          </Section>
        )}

        {/* Footer */}
        <footer className="text-center text-xs text-gray-700 py-6 border-t border-gray-800/50">
          Nexus AI  — Intelligent Portfolio Manager &nbsp;·&nbsp;
          AI estimates are not financial advice
        </footer>
      </main>
    </div>
  )
}
