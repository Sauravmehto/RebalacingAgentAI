import { useState } from 'react'
import { actionAnimationClass } from '../utils/actionAnimation.js'

const ACTION_COLOR = {
  'STRONG BUY':  'bg-green-500/25 text-green-300 border-green-500/40',
  'BUY':         'bg-green-500/15 text-green-400 border-green-600/30',
  'HOLD':        'bg-yellow-500/15 text-yellow-400 border-yellow-600/30',
  'REDUCE':      'bg-orange-500/15 text-orange-400 border-orange-600/30',
  'PARTIAL SELL':'bg-orange-500/20 text-orange-300 border-orange-500/40',
  'SELL':        'bg-red-500/15 text-red-400 border-red-600/30',
  'STRONG SELL': 'bg-red-500/25 text-red-300 border-red-500/40',
}

function TrendIcon({ trend }) {
  if (trend === 'Uptrend')   return <span className="text-green-400">↑</span>
  if (trend === 'Downtrend') return <span className="text-red-400">↓</span>
  return <span className="text-gray-500">→</span>
}

function ConfBadge({ confidence }) {
  const map = {
    HIGH:   'text-yellow-400 bg-yellow-500/10',
    MEDIUM: 'text-gray-400 bg-gray-700/50',
    LOW:    'text-gray-600 bg-gray-800',
  }
  return (
    <span className={`px-2 py-0.5 rounded text-xs font-medium ${map[confidence] ?? map.MEDIUM}`}>
      {confidence}
    </span>
  )
}

function parseExplanations(stocks, explanationLines) {
  // explanationLines is an array like ["MSFT: reason.", "NVDA: reason."]
  const byTicker = {}
  for (const line of (explanationLines ?? [])) {
    const match = line.match(/^([A-Z]{1,6}):\s*(.+)$/)
    if (match) byTicker[match[1]] = match[2]
  }
  return stocks.map(s => ({
    ...s,
    explanation: byTicker[s.symbol] ?? s.reason ?? '',
  }))
}

function StockRow({ stock }) {
  const [open, setOpen] = useState(false)
  const actionCls = ACTION_COLOR[stock.action] ?? 'bg-gray-700 text-gray-300 border-gray-600'
  const motion = actionAnimationClass(stock.action)

  return (
    <div className="border border-gray-800/60 rounded-lg overflow-hidden
                    hover:border-gray-700 transition-colors">
      {/* Header row */}
      <button
        onClick={() => setOpen(p => !p)}
        className="w-full flex items-center gap-3 px-4 py-3 text-left
                   hover:bg-gray-800/40 transition-colors"
      >
        <span className="font-mono font-bold text-white w-16 flex-shrink-0">
          {stock.symbol}
        </span>
        <span className={`badge text-xs border flex-shrink-0 font-bold rounded-full ${actionCls} ${motion}`}>
          {stock.action}
        </span>
        <span className="text-sm text-gray-400 flex-1 min-w-0 truncate">
          {stock.explanation || stock.reason || 'No explanation available'}
        </span>
        <svg
          className={`w-4 h-4 text-gray-600 flex-shrink-0 transition-transform ${open ? 'rotate-180' : ''}`}
          fill="none" viewBox="0 0 24 24" stroke="currentColor"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {/* Expanded detail */}
      {open && (
        <div className="px-4 pb-4 pt-1 bg-gray-900/40 border-t border-gray-800/60 animate-fade-in">
          <p className="text-sm text-gray-300 leading-relaxed mb-4">
            {stock.explanation || stock.reason || 'No detailed explanation available.'}
          </p>

          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <div className="bg-gray-800/60 rounded-lg px-3 py-2">
              <p className="text-xs text-gray-600 mb-1">Score</p>
              <div className="flex items-center gap-2">
                <div className="w-12 h-1.5 bg-gray-700 rounded-full overflow-hidden">
                  <div
                    className={`h-full rounded-full ${
                      (stock.score ?? 0) >= 65 ? 'bg-green-500' :
                      (stock.score ?? 0) >= 40 ? 'bg-yellow-500' : 'bg-red-500'
                    }`}
                    style={{ width: `${stock.score ?? 0}%` }}
                  />
                </div>
                <span className="text-sm font-bold text-white tabular-nums">
                  {(stock.score ?? 0).toFixed(0)}
                </span>
              </div>
            </div>

            <div className="bg-gray-800/60 rounded-lg px-3 py-2">
              <p className="text-xs text-gray-600 mb-1">Confidence</p>
              <ConfBadge confidence={stock.confidence} />
            </div>

            <div className="bg-gray-800/60 rounded-lg px-3 py-2">
              <p className="text-xs text-gray-600 mb-1">Trend</p>
              <div className="flex items-center gap-1.5 text-sm">
                <TrendIcon trend={stock.trend} />
                <span className="text-gray-300">{stock.trend}</span>
              </div>
            </div>

            <div className="bg-gray-800/60 rounded-lg px-3 py-2">
              <p className="text-xs text-gray-600 mb-1">Allocation</p>
              <span className="text-sm text-gray-300">{stock.allocation_status}</span>
            </div>
          </div>

          <div className="flex flex-wrap gap-4 mt-3 text-xs text-gray-500">
            <span>7-day trend: <span className="text-gray-300">{stock.trend_7d}</span></span>
            <span>30-day trend: <span className="text-gray-300">{stock.trend_30d}</span></span>
            <span>Sentiment: <span className="text-gray-300">{stock.sentiment}</span></span>
            <span>Return: <span className={
              (stock.return_pct ?? 0) >= 0 ? 'text-green-400' : 'text-red-400'
            }>{(stock.return_pct ?? 0) >= 0 ? '+' : ''}{(stock.return_pct ?? 0).toFixed(2)}%</span></span>
          </div>
        </div>
      )}
    </div>
  )
}

export default function ExplanationPanel({ stocks, explanations }) {
  const enriched = parseExplanations(stocks ?? [], explanations ?? [])

  if (!enriched.length) return null

  return (
    <section className="card p-6 animate-fade-in">
      <div className="flex items-center gap-2 mb-5">
        <div className="w-1 h-5 bg-cyan-500 rounded-full" />
        <h2 className="text-base font-semibold text-white">AI Explanations</h2>
        <span className="text-xs text-gray-600 ml-1">({enriched.length} stocks)</span>
      </div>

      <div className="space-y-2">
        {enriched.map(s => (
          <StockRow key={s.symbol} stock={s} />
        ))}
      </div>
    </section>
  )
}
