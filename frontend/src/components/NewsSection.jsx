import { useState } from 'react'

function sentimentBadgeStyle(sentiment) {
  if (!sentiment) return 'bg-gray-700 text-gray-400 border-gray-600'
  const l = sentiment.toLowerCase()
  if (l.includes('strong positive')) return 'bg-green-500/20 text-green-400 border-green-500/40'
  if (l.includes('positive'))        return 'bg-green-500/15 text-green-500 border-green-600/30'
  if (l.includes('strong negative')) return 'bg-red-500/20 text-red-400 border-red-500/40'
  if (l.includes('negative'))        return 'bg-red-500/15 text-red-500 border-red-600/30'
  return 'bg-yellow-500/15 text-yellow-400 border-yellow-600/30'
}

function timeAgo(dateStr) {
  if (!dateStr) return ''
  try {
    const d    = new Date(typeof dateStr === 'number' ? dateStr * 1000 : dateStr)
    const diff = (Date.now() - d.getTime()) / 1000
    if (diff < 3600)  return `${Math.round(diff / 60)}m ago`
    if (diff < 86400) return `${Math.round(diff / 3600)}h ago`
    return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
  } catch { return '' }
}

function NewsCard({ article, sentiment }) {
  return (
    <div className="bg-gray-800/50 border border-gray-700/50 rounded-lg p-4
                    hover:border-gray-600 hover:bg-gray-800/80 transition-all group">
      <div className="flex items-start justify-between gap-2 mb-2">
        <span className={`badge text-xs border ${sentimentBadgeStyle(sentiment)}`}>
          {article.ticker ?? 'Market'}
        </span>
        <span className="text-xs text-gray-600 flex-shrink-0">{timeAgo(article.date)}</span>
      </div>

      <a
        href={article.url || '#'}
        target="_blank"
        rel="noopener noreferrer"
        className="block text-sm font-medium text-gray-200 leading-snug
                   group-hover:text-white transition-colors line-clamp-3 mb-3"
      >
        {article.title}
      </a>

      <div className="flex items-center justify-between">
        <span className="text-xs text-gray-600 truncate max-w-[140px]">
          {article.source}
        </span>
        {article.url && (
          <a
            href={article.url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-xs text-cyan-500 hover:text-cyan-400 flex items-center gap-1 flex-shrink-0"
          >
            Read
            <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                    d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
            </svg>
          </a>
        )}
      </div>
    </div>
  )
}

function SectorHeadlineCard({ sector, headlines, sentiment }) {
  const [expanded, setExpanded] = useState(false)
  const visible = expanded ? headlines : headlines.slice(0, 2)

  return (
    <div className="bg-gray-800/50 border border-gray-700/50 rounded-lg p-4 hover:border-gray-600 transition-colors">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <span className="text-sm font-semibold text-white">{sector}</span>
          {sentiment && (
            <span className={`badge text-xs border ${sentimentBadgeStyle(sentiment)}`}>
              {sentiment}
            </span>
          )}
        </div>
        <span className="text-xs text-gray-600">{headlines.length} articles</span>
      </div>
      <ul className="space-y-1.5">
        {visible.map((h, i) => (
          <li key={i} className="text-xs text-gray-400 flex gap-2">
            <span className="text-gray-700 flex-shrink-0 mt-0.5">•</span>
            <span className="leading-relaxed">{h}</span>
          </li>
        ))}
      </ul>
      {headlines.length > 2 && (
        <button
          onClick={() => setExpanded(p => !p)}
          className="mt-2 text-xs text-cyan-500 hover:text-cyan-400"
        >
          {expanded ? 'Show less' : `+${headlines.length - 2} more`}
        </button>
      )}
    </div>
  )
}

export default function NewsSection({ news, sectorSentiments, onRefresh, refreshing }) {
  const { sector_headlines = {}, articles = [] } = news ?? {}
  const hasSectorNews = Object.keys(sector_headlines).length > 0
  const hasArticles   = articles.length > 0

  return (
    <section className="card p-6 animate-fade-in">
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-2">
          <div className="w-1 h-5 bg-cyan-500 rounded-full" />
          <h2 className="text-base font-semibold text-white">Market News</h2>
        </div>
        <button
          onClick={onRefresh}
          disabled={refreshing}
          className="btn-secondary text-xs flex items-center gap-1.5"
        >
          <svg className={`w-3.5 h-3.5 ${refreshing ? 'animate-spin' : ''}`}
               fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                  d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
          </svg>
          Refresh
        </button>
      </div>

      {/* Sector headlines */}
      {hasSectorNews && (
        <div className="mb-8">
          <h3 className="text-xs text-gray-500 uppercase tracking-wider font-medium mb-4">
            Sector Headlines
          </h3>
          <div className="grid sm:grid-cols-2 xl:grid-cols-3 gap-3">
            {Object.entries(sector_headlines).map(([sector, headlines]) => (
              <SectorHeadlineCard
                key={sector}
                sector={sector}
                headlines={headlines}
                sentiment={sectorSentiments?.[sector]}
              />
            ))}
          </div>
        </div>
      )}

      {/* Individual articles */}
      {hasArticles && (
        <div>
          <h3 className="text-xs text-gray-500 uppercase tracking-wider font-medium mb-4">
            Latest Articles
          </h3>
          <div className="grid sm:grid-cols-2 xl:grid-cols-3 gap-3">
            {articles.slice(0, 9).map((a, i) => (
              <NewsCard
                key={i}
                article={a}
                sentiment={sectorSentiments?.[a.sector]}
              />
            ))}
          </div>
        </div>
      )}

      {!hasSectorNews && !hasArticles && (
        <div className="text-center py-10 text-gray-600 text-sm">
          No news available. Run an analysis first.
        </div>
      )}
    </section>
  )
}
